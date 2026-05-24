from __future__ import annotations

import re


PRIVATE_KEY_BLOCK_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
BEARER_TOKEN_RE = re.compile(r"\bbearer\s+[A-Za-z0-9._=/-]{8,}", re.IGNORECASE)
ASSIGNMENT_RE = re.compile(
    r"^\s*(?:[+-]\s*)?(?:export\s+)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*(?P<operator>=|:)\s*(?P<value>.+?)\s*$"
)
ASSIGNMENT_CANDIDATE_RE = re.compile(
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*(?P<operator>=|:)\s*(?P<value>[^,\n]+)"
)

SERVICE_ADMIN_HINTS = ("service", "admin", "service_role", "service_role_key", "root")
API_KEY_HINTS = ("api_key", "apikey", "access_key", "client_secret")
TOKEN_HINTS = ("token", "bearer")
PASSWORD_HINTS = ("password", "passwd", "pwd")
SECRET_HINTS = ("secret", "private_key")
PLACEHOLDER_VALUES = {
    "",
    "example",
    "example_value",
    "example-value",
    "your_value_here",
    "your-token-here",
    "changeme",
    "replace_me",
    "<redacted>",
    "<secret>",
}


def _risk_rank(risk_level: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}[risk_level]


def _normalize_value(value: str) -> str:
    stripped = value.strip().strip("'").strip('"')
    return stripped.lower()


def _is_placeholder_value(value: str) -> bool:
    normalized_value = _normalize_value(value)
    return normalized_value in PLACEHOLDER_VALUES


def _build_finding(
    finding_type: str,
    risk_level: str,
    line_number: int,
    summary: str,
) -> dict[str, object]:
    return {
        "type": finding_type,
        "risk_level": risk_level,
        "line_number": line_number,
        "summary": summary,
    }


def _finding_from_assignment_candidate(
    variable_name: str,
    value: str,
    line_number: int,
) -> dict[str, object] | None:
    variable_name_lower = variable_name.lower()
    if _is_placeholder_value(value):
        return None

    if any(hint in variable_name_lower for hint in SERVICE_ADMIN_HINTS) and any(
        hint in variable_name_lower for hint in ("key", "secret", "token")
    ):
        return _build_finding(
            "service_admin_key_hint",
            "high",
            line_number,
            f"Detected service/admin secret-style assignment on line {line_number} for {variable_name}. Value redacted.",
        )

    if any(hint in variable_name_lower for hint in PASSWORD_HINTS):
        return _build_finding(
            "password_assignment",
            "high",
            line_number,
            f"Detected password-style assignment on line {line_number} for {variable_name}. Value redacted.",
        )

    if any(hint in variable_name_lower for hint in API_KEY_HINTS):
        return _build_finding(
            "api_key_assignment",
            "high",
            line_number,
            f"Detected API key-style assignment on line {line_number} for {variable_name}. Value redacted.",
        )

    if any(hint in variable_name_lower for hint in TOKEN_HINTS):
        return _build_finding(
            "token_assignment",
            "high",
            line_number,
            f"Detected token-style assignment on line {line_number} for {variable_name}. Value redacted.",
        )

    if any(hint in variable_name_lower for hint in SECRET_HINTS):
        return _build_finding(
            "secret_assignment",
            "high",
            line_number,
            f"Detected secret-style assignment on line {line_number} for {variable_name}. Value redacted.",
        )

    return None


def _detect_assignment_finding(line: str, line_number: int) -> dict[str, object] | None:
    candidate_matches = []
    anchored_match = ASSIGNMENT_RE.match(line)
    if anchored_match is not None:
        candidate_matches.append(anchored_match)
    candidate_matches.extend(ASSIGNMENT_CANDIDATE_RE.finditer(line))

    for match in candidate_matches:
        variable_name = match.group("name")
        value = match.group("value")
        finding = _finding_from_assignment_candidate(variable_name, value, line_number)
        if finding is not None:
            return finding

        if "=" in value or ":" in value:
            for nested_match in ASSIGNMENT_CANDIDATE_RE.finditer(value):
                nested_finding = _finding_from_assignment_candidate(
                    nested_match.group("name"),
                    nested_match.group("value"),
                    line_number,
                )
                if nested_finding is not None:
                    return nested_finding

    return None


def scan_text_for_secrets(text: str) -> dict[str, object]:
    findings: list[dict[str, object]] = []

    private_key_match = PRIVATE_KEY_BLOCK_RE.search(text)
    if private_key_match is not None:
        line_number = text[: private_key_match.start()].count("\n") + 1
        findings.append(
            _build_finding(
                "private_key_block",
                "high",
                line_number,
                f"Detected private key block starting near line {line_number}. Content redacted.",
            )
        )

    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped_line = line.strip()
        if not stripped_line or stripped_line.startswith("#"):
            continue

        assignment_finding = _detect_assignment_finding(line, line_number)
        if assignment_finding is not None:
            findings.append(assignment_finding)
            continue

        if BEARER_TOKEN_RE.search(line):
            findings.append(
                _build_finding(
                    "bearer_token",
                    "high",
                    line_number,
                    f"Detected bearer token-style content on line {line_number}. Value redacted.",
                )
            )

    highest_risk = "low"
    for finding in findings:
        finding_risk = str(finding["risk_level"])
        if _risk_rank(finding_risk) > _risk_rank(highest_risk):
            highest_risk = finding_risk

    if findings:
        recommended_action = (
            "Do not print, save, or forward this text until the secret-like content is removed or redacted."
        )
    else:
        recommended_action = "No secret-like content was detected by the current rule-based scan."

    return {
        "has_findings": bool(findings),
        "risk_level": highest_risk,
        "findings": findings,
        "recommended_action": recommended_action,
    }


def guard_text_output(text: str, context_label: str) -> dict[str, object]:
    scan_result = scan_text_for_secrets(text)
    findings = list(scan_result["findings"])
    has_findings = bool(scan_result["has_findings"])

    if has_findings:
        safe_message = (
            f"{context_label} blocked because secret-like content was detected. "
            "Findings are redacted."
        )
    else:
        safe_message = f"{context_label} allowed. No secret-like content was detected."

    return {
        "allowed": not has_findings,
        "risk_level": scan_result["risk_level"],
        "safe_message": safe_message,
        "findings": findings,
        "should_block_save": has_findings,
    }


def format_safety_scan(result: dict[str, object]) -> str:
    findings = list(result.get("findings", []))
    lines = [
        f"Secret-like findings: {'yes' if result.get('has_findings') else 'no'}",
        f"Risk level: {result.get('risk_level', 'low')}",
        f"Findings count: {len(findings)}",
    ]

    if findings:
        for finding in findings:
            lines.append(f"Finding: {finding['summary']}")
    else:
        lines.append("Finding: none")

    lines.append(f"Recommended action: {result.get('recommended_action', '')}")
    return "\n".join(lines)
