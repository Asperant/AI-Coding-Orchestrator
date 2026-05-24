from typing import Any
from core.safety import guard_text_output

ALLOWED_DECISIONS = {"approve", "needs_changes", "needs_context", "block"}
ALLOWED_CONFIDENCE = {"low", "medium", "high"}
ALLOWED_RISK_LEVEL = {"low", "medium", "high"}

def normalize_agent_decision(data: dict[str, Any]) -> dict[str, Any]:
    decision = data.get("decision", "").lower()
    if decision not in ALLOWED_DECISIONS:
        decision = "needs_context"

    confidence = data.get("confidence", "").lower()
    if confidence not in ALLOWED_CONFIDENCE:
        confidence = "low"

    risk_level = data.get("risk_level", "").lower()
    if risk_level not in ALLOWED_RISK_LEVEL:
        risk_level = "high"

    def _safe_list(val: Any) -> list[str]:
        if isinstance(val, list):
            return [str(v) for v in val]
        if isinstance(val, str) and val:
            return [val]
        return []

    return {
        "agent_role": str(data.get("agent_role", "unknown_agent")),
        "decision": decision,
        "confidence": confidence,
        "risk_level": risk_level,
        "findings": _safe_list(data.get("findings", [])),
        "required_fixes": _safe_list(data.get("required_fixes", [])),
        "suggested_tests": _safe_list(data.get("suggested_tests", [])),
        "blocked_reasons": _safe_list(data.get("blocked_reasons", [])),
        "next_action": str(data.get("next_action", "")),
        "safety_notes": _safe_list(data.get("safety_notes", [])),
    }

def format_agent_decision(decision_dict: dict[str, Any]) -> str:
    norm = normalize_agent_decision(decision_dict)
    
    lines = [
        f"Agent: {norm['agent_role']}",
        f"Decision: {norm['decision']} (Risk: {norm['risk_level']}, Confidence: {norm['confidence']})",
    ]
    
    if norm["findings"]:
        lines.append("Findings:")
        for f in norm["findings"]:
            lines.append(f"  - {f}")
            
    if norm["required_fixes"]:
        lines.append("Required Fixes:")
        for rf in norm["required_fixes"]:
            lines.append(f"  - {rf}")
            
    if norm["suggested_tests"]:
        lines.append("Suggested Tests:")
        for st in norm["suggested_tests"]:
            lines.append(f"  - {st}")
            
    if norm["blocked_reasons"]:
        lines.append("Blocked Reasons:")
        for br in norm["blocked_reasons"]:
            lines.append(f"  - {br}")
            
    if norm["next_action"]:
        lines.append(f"Next Action: {norm['next_action']}")
        
    if norm["safety_notes"]:
        lines.append("Safety Notes:")
        for sn in norm["safety_notes"]:
            lines.append(f"  - {sn}")
            
    raw_output = "\n".join(lines)
    guard_result = guard_text_output(raw_output, "Agent Decision")
    if not guard_result["allowed"]:
        return guard_result["safe_message"]
    return raw_output

def format_agent_decision_list(decisions: list[dict[str, Any]]) -> str:
    if not decisions:
        return "No agent decisions recorded."
    return "\n\n".join(format_agent_decision(d) for d in decisions)

def aggregate_agent_decisions(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    if not decisions:
        return {
            "final_decision": "needs_context",
            "risk_level": "high",
            "confidence": "low",
            "agents_used": [],
            "findings": [],
            "required_fixes": [],
            "suggested_tests": [],
            "blocked_reasons": ["No decisions to aggregate."],
            "next_action": "Gather context.",
            "safety_notes": [],
        }

    norms = [normalize_agent_decision(d) for d in decisions]
    
    # Decisions priority: block > needs_changes > needs_context > approve
    has_block = any(d["decision"] == "block" for d in norms)
    has_needs_changes = any(d["decision"] == "needs_changes" for d in norms)
    has_needs_context = any(d["decision"] == "needs_context" for d in norms)
    
    if has_block:
        final_decision = "block"
    elif has_needs_changes:
        final_decision = "needs_changes"
    elif has_needs_context:
        final_decision = "needs_context"
    else:
        final_decision = "approve"

    # Risk priority: high > medium > low
    has_high_risk = any(d["risk_level"] == "high" for d in norms)
    has_medium_risk = any(d["risk_level"] == "medium" for d in norms)
    
    if has_high_risk:
        final_risk = "high"
    elif has_medium_risk:
        final_risk = "medium"
    else:
        final_risk = "low"
        
    # Confidence priority: low > medium > high (take the lowest confidence as overall)
    has_low_conf = any(d["confidence"] == "low" for d in norms)
    has_medium_conf = any(d["confidence"] == "medium" for d in norms)
    
    if has_low_conf:
        final_conf = "low"
    elif has_medium_conf:
        final_conf = "medium"
    else:
        final_conf = "high"
        
    agents_used = list({d["agent_role"] for d in norms})
    
    findings = []
    required_fixes = []
    suggested_tests = []
    blocked_reasons = []
    safety_notes = []
    
    for d in norms:
        for f in d["findings"]:
            if f not in findings: findings.append(f)
        for rf in d["required_fixes"]:
            if rf not in required_fixes: required_fixes.append(rf)
        for st in d["suggested_tests"]:
            if st not in suggested_tests: suggested_tests.append(st)
        for br in d["blocked_reasons"]:
            if br not in blocked_reasons: blocked_reasons.append(br)
        for sn in d["safety_notes"]:
            if sn not in safety_notes: safety_notes.append(sn)
            
    next_action_parts = []
    if blocked_reasons:
        next_action_parts.append("Address blocked reasons.")
    if required_fixes:
        next_action_parts.append("Apply required fixes.")
    if final_decision == "needs_context":
        next_action_parts.append("Gather more context.")
    if not next_action_parts:
        next_action_parts.append("Proceed with task.")
        
    return {
        "final_decision": final_decision,
        "risk_level": final_risk,
        "confidence": final_conf,
        "agents_used": sorted(agents_used),
        "findings": findings,
        "required_fixes": required_fixes,
        "suggested_tests": suggested_tests,
        "blocked_reasons": blocked_reasons,
        "next_action": " ".join(next_action_parts),
        "safety_notes": safety_notes,
    }

def format_aggregated_decision(aggregated: dict[str, Any]) -> str:
    lines = [
        "Multi-Agent Decision:",
        f"- Final decision: {aggregated.get('final_decision')}",
        f"- Risk: {aggregated.get('risk_level')}",
        f"- Confidence: {aggregated.get('confidence')}",
        f"- Agents: {', '.join(aggregated.get('agents_used', []))}",
        f"- Required fixes: {len(aggregated.get('required_fixes', []))}",
        f"- Suggested tests: {len(aggregated.get('suggested_tests', []))}",
        f"- Next action: {aggregated.get('next_action')}"
    ]
    return "\n".join(lines)
