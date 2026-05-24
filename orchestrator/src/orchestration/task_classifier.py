from __future__ import annotations

import re


TASK_TYPE_RULES = {
    "project assessment": (
        "review this project",
        "review this repo",
        "review this codebase",
        "assess this codebase",
        "assess this repo",
        "assess this project",
        "onboard this repo",
        "onboard this project",
        "project assessment",
        "repo assessment",
        "codebase assessment",
        "safest next coding task",
        "onboard",
        "codebase",
        "repo",
    ),
    "feature": ("add", "build", "create", "implement", "feature", "new feature", "support"),
    "bug fix": ("bug", "fix", "broken", "error", "issue", "crash", "failing"),
    "refactor": ("refactor", "cleanup", "clean up", "rename", "restructure", "simplify"),
    "test writing": ("test", "tests", "testing", "coverage", "smoke test", "unittest"),
    "database change": (
        "database",
        "migration",
        "schema",
        "sql",
        "query",
        "table",
        "rls",
        "supabase",
        "postgres",
    ),
    "UI change": ("ui", "screen", "component", "layout", "page", "button", "form", "responsive"),
    "AI pipeline change": (
        "ai",
        "model",
        "prompt",
        "llm",
        "inference",
        "embedding",
        "retrieval",
        "fallback",
        "queue",
        "rate limit",
    ),
    "security/privacy change": (
        "auth",
        "authentication",
        "authorization",
        "permission",
        "secret",
        "token",
        "privacy",
        "security",
        "payment",
        "sensitive",
        "pii",
    ),
    "performance change": (
        "performance",
        "optimize",
        "latency",
        "slow",
        "faster",
        "cache",
        "throughput",
    ),
    "documentation change": ("docs", "documentation", "readme", "guide", "comment"),
    "release/deploy review": (
        "release",
        "deploy",
        "deployment",
        "rollback",
        "production",
        "prod",
        "ci/cd",
        "ship",
    ),
}

TASK_TYPE_PRIORITY = (
    "security/privacy change",
    "database change",
    "AI pipeline change",
    "release/deploy review",
    "project assessment",
    "performance change",
    "bug fix",
    "UI change",
    "refactor",
    "test writing",
    "documentation change",
    "feature",
    "unknown",
)

HIGH_RISK_TASK_TYPES = {
    "security/privacy change",
    "database change",
    "release/deploy review",
}
MEDIUM_RISK_TASK_TYPES = {
    "AI pipeline change",
    "performance change",
    "bug fix",
    "UI change",
    "feature",
    "refactor",
    "test writing",
}

TOKEN_PATTERN = re.compile(r"[a-z0-9_/.-]+")


def _normalize(task: str) -> str:
    return " ".join(task.strip().lower().split())


def _tokenize(task: str) -> set[str]:
    return set(TOKEN_PATTERN.findall(task))


def _find_matches(normalized_task: str, tokens: set[str], keywords: tuple[str, ...]) -> list[str]:
    matches: list[str] = []
    padded_task = f" {normalized_task} "
    for keyword in keywords:
        if " " in keyword or "/" in keyword:
            if keyword in normalized_task:
                matches.append(keyword)
        else:
            if keyword in tokens or f" {keyword} " in padded_task:
                matches.append(keyword)
    return matches


def _priority_index(task_type: str) -> int:
    return TASK_TYPE_PRIORITY.index(task_type)


def _build_risk_level(primary_task_type: str) -> str:
    if primary_task_type in HIGH_RISK_TASK_TYPES:
        return "high"
    if primary_task_type in MEDIUM_RISK_TASK_TYPES:
        return "medium"
    return "low"


def classify_task(task: str) -> dict[str, object]:
    normalized_task = _normalize(task)
    if not normalized_task:
        return {
            "primary_task_type": "unknown",
            "secondary_task_types": [],
            "confidence": "low",
            "risk_level": "low",
            "rationale": "Empty task description.",
        }

    tokens = _tokenize(normalized_task)
    scored_matches: list[tuple[str, list[str]]] = []
    for task_type, keywords in TASK_TYPE_RULES.items():
        matches = _find_matches(normalized_task, tokens, keywords)
        if matches:
            scored_matches.append((task_type, matches))

    if not scored_matches:
        return {
            "primary_task_type": "unknown",
            "secondary_task_types": [],
            "confidence": "low",
            "risk_level": "low",
            "rationale": "No strong rule-based match found.",
        }

    scored_matches.sort(key=lambda item: (-len(item[1]), _priority_index(item[0])))
    primary_task_type, primary_matches = scored_matches[0]
    secondary_task_types = [task_type for task_type, _ in scored_matches[1:]]

    top_score = len(primary_matches)
    tied_top_matches = [item for item in scored_matches if len(item[1]) == top_score]
    if len(tied_top_matches) > 1:
        confidence = "low"
        rationale = (
            f"Ambiguous rule match; selected {primary_task_type} from keywords: "
            f"{', '.join(primary_matches)}."
        )
    elif top_score >= 2:
        confidence = "high"
        rationale = f"Matched {primary_task_type} keywords: {', '.join(primary_matches)}."
    else:
        confidence = "medium"
        rationale = f"Matched {primary_task_type} keyword: {primary_matches[0]}."

    return {
        "primary_task_type": primary_task_type,
        "secondary_task_types": secondary_task_types,
        "confidence": confidence,
        "risk_level": _build_risk_level(primary_task_type),
        "rationale": rationale,
    }
