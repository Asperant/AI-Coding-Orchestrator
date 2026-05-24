import re
import os
from pathlib import Path
from typing import Any

from core.safety import guard_text_output
from core.approved_paths import ensure_approved_path
from brain.ai_brain_reader import REQUIRED_CORE_FILES

GLOBAL_ALWAYS_INCLUDE = {
    "global_rules.md",
    "provider_rules.md",
    "testing_strategy.md",
    "coding_principles.md",
    "CORE-RULES.md",
}

ALL_AI_BRAIN_FILES = {
    "global_rules.md",
    "coding_principles.md",
    "architecture_decisions.md",
    "risk_registry.md",
    "testing_strategy.md",
    "provider_rules.md",
    "memory_log.md",
    "reusable_patterns.md",
}

ALL_PROJECT_FILES = {
    "AGENTS.md",
    "docs/product-context.md",
    "docs/architecture.md",
    "docs/project-map.md",
    "docs/quality-gates.md",
    "docs/risk-registry.md",
    "docs/test-scenarios.md",
}

def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_]+", text.lower()))

def _get_project_name(project_path: str) -> str:
    return Path(project_path).name

def _extract_relevant_lines(content: str, keywords: set[str], always_include: bool, max_chars: int) -> list[str]:
    lines = content.splitlines()
    selected: list[str] = []
    chars_used = 0
    
    # Very crude relevance logic: if always include, we just take lines until max_chars.
    # Otherwise, check if line or neighboring lines match keywords.
    for i, line in enumerate(lines):
        if chars_used >= max_chars:
            break
            
        line_stripped = line.strip()
        if not line_stripped:
            continue
            
        line_tokens = _tokenize(line_stripped)
        
        is_relevant = always_include or bool(line_tokens & keywords)
        
        # also match hardcoded terms
        if not is_relevant:
            hardcoded = {"mock", "provider", "token", "test", "risk", "architecture", "codex", "orchestrator", "mcp", "allowed"}
            if line_tokens & hardcoded:
                is_relevant = True
                
        if is_relevant:
            if chars_used + len(line_stripped) > max_chars:
                break
            selected.append(line_stripped)
            chars_used += len(line_stripped)
            
    return selected

def build_ai_brain_context_pack(
    task: str,
    project_path: str,
    ai_brain_path: str | None,
    approved_paths: list[str] | None = None,
    context_budget: int = 5000,
) -> dict[str, Any]:
    task_tokens = _tokenize(task)
    
    files_read = []
    files_missing = []
    relevant_rules = []
    project_guidance = []
    architecture_notes = []
    risk_notes = []
    testing_notes = []
    provider_security_notes = []
    memory_notes = []
    blocked = False
    safety_notes = []
    
    chars_remaining = context_budget
    
    def process_file(path: Path, is_global: bool, category_hint: str, report_missing: bool = True):
        nonlocal chars_remaining, blocked
        if chars_remaining <= 0:
            return
            
        if not path.is_file():
            if report_missing:
                files_missing.append(path.name)
            return
            
        files_read.append(path.name)
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            safety_notes.append(f"Failed to read {path.name}: {e}")
            return
            
        guard_result = guard_text_output(content, f"Read {path.name}")
        if not guard_result["allowed"]:
            blocked = True
            safety_notes.append(f"Blocked content in {path.name}: {guard_result['safe_message']}")
            return
            
        always_include = is_global and path.name in GLOBAL_ALWAYS_INCLUDE
        selected_lines = _extract_relevant_lines(content, task_tokens, always_include, chars_remaining)
        
        if not selected_lines:
            return
            
        snippet = f"[{path.name}] " + " | ".join(selected_lines)
        if len(snippet) > chars_remaining:
            snippet = snippet[:chars_remaining]
            
        chars_remaining -= len(snippet)
        
        # Categorize
        if "architecture" in category_hint:
            architecture_notes.append(snippet)
        elif "risk" in category_hint:
            risk_notes.append(snippet)
        elif "testing" in category_hint or "quality" in category_hint:
            testing_notes.append(snippet)
        elif "provider" in category_hint or "AGENTS" in path.name:
            provider_security_notes.append(snippet)
        elif "memory" in category_hint:
            memory_notes.append(snippet)
        elif is_global:
            relevant_rules.append(snippet)
        else:
            project_guidance.append(snippet)

    # 1. Read AI-Brain files
    if ai_brain_path and os.path.isdir(ai_brain_path):
        brain_dir = Path(ai_brain_path)
        for fname in ALL_AI_BRAIN_FILES:
            process_file(brain_dir / fname, is_global=True, category_hint=fname, report_missing=False)
            
        # Fallback to existing core files
        for core_name, rel_path in REQUIRED_CORE_FILES.items():
            cat_hint = "memory" if "budget" in core_name or "readme" in core_name else "project"
            process_file(brain_dir / rel_path, is_global=True, category_hint=cat_hint, report_missing=True)
            
        # Try project profile
        proj_name = _get_project_name(project_path)
        profile_path = brain_dir / "project_profiles" / f"{proj_name}.md"
        if profile_path.is_file():
            process_file(profile_path, is_global=True, category_hint="profile", report_missing=False)

    # 2. Read project docs
    if project_path:
        # Check approved paths
        try:
            safe_proj = ensure_approved_path(project_path, approved_paths)
            for fname in ALL_PROJECT_FILES:
                process_file(safe_proj / fname, is_global=False, category_hint=fname, report_missing=False)
        except Exception as e:
            safety_notes.append(f"Project path error: {e}")

    summary = f"Read {len(files_read)} files. Missing {len(files_missing)} files. Budget remaining: {chars_remaining} chars."

    return {
        "task": task,
        "ai_brain_path": ai_brain_path,
        "project_path": project_path,
        "files_read": files_read,
        "files_missing": files_missing,
        "relevant_rules": relevant_rules,
        "project_guidance": project_guidance,
        "architecture_notes": architecture_notes,
        "risk_notes": risk_notes,
        "testing_notes": testing_notes,
        "provider_security_notes": provider_security_notes,
        "memory_notes": memory_notes,
        "context_summary": summary,
        "blocked": blocked,
        "safety_notes": safety_notes,
    }

def format_ai_brain_context_pack(pack: dict[str, Any], heading: str = "AI-Brain Context Pack:") -> str:
    lines = [heading]
    lines.append(f"- Files read: {', '.join(pack.get('files_read', [])) or 'none'}")
    lines.append(f"- Missing: {', '.join(pack.get('files_missing', [])) or 'none'}")
    
    sections = [
        ("Relevant rules", pack.get("relevant_rules", [])),
        ("Project guidance", pack.get("project_guidance", [])),
        ("Risk notes", pack.get("risk_notes", [])),
        ("Testing notes", pack.get("testing_notes", [])),
        ("Provider/security notes", pack.get("provider_security_notes", [])),
        ("Architecture notes", pack.get("architecture_notes", [])),
        ("Memory notes", pack.get("memory_notes", [])),
    ]
    
    for label, items in sections:
        if items:
            lines.append(f"- {label}:")
            for item in items:
                lines.append(f"  * {item}")
        else:
            lines.append(f"- {label}: none")
            
    lines.append(f"- Context summary: {pack.get('context_summary', '')}")
    if pack.get("blocked"):
        lines.append("- Safety status: BLOCKED due to secret-like content")
    if pack.get("safety_notes"):
        lines.append("- Safety notes:")
        for note in pack.get("safety_notes", []):
            lines.append(f"  * {note}")
            
    return "\n".join(lines)

def format_ai_brain_guidance_for_codex(pack: dict[str, Any], max_chars: int = 1800) -> str:
    lines = ["AI-Brain Guidance:"]
    
    def _clean_and_dedupe(items: list[str], max_items: int = 5) -> list[str]:
        cleaned = []
        for item in items:
            item = re.sub(r'\[\[(.*?)\]\]', r'\1', item)
            item = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', item)
            cleaned.append(item)
        unique = list(dict.fromkeys(cleaned))
        return unique[:max_items]

    sections = [
        ("Operating rules", pack.get("relevant_rules", []) + pack.get("project_guidance", []) + pack.get("architecture_notes", [])),
        ("Task-relevant risks", pack.get("risk_notes", [])),
        ("Testing expectations", pack.get("testing_notes", [])),
        ("Provider/security constraints", pack.get("provider_security_notes", [])),
        ("Memory sync", pack.get("memory_notes", [])),
    ]

    has_content = False
    for label, raw_items in sections:
        items = _clean_and_dedupe(raw_items, max_items=5)
        if items:
            has_content = True
            lines.append(f"- {label}:")
            for item in items:
                lines.append(f"  - {item}")
                
    if not has_content:
        lines.append("- Context summary: no task-relevant AI-Brain guidance found.")
    else:
        files_read = pack.get("files_read", [])
        missing = pack.get("files_missing", [])
        lines.append("- Context summary:")
        if files_read:
            lines.append(f"  - Files read: {', '.join(files_read)}")
        if missing:
            lines.append(f"  - Missing: {', '.join(missing)}")
            
    if pack.get("blocked"):
        lines.append("- Safety status: BLOCKED due to secret-like content")
        
    result = "\n".join(lines)
    if len(result) > max_chars:
        return result[:max_chars] + "\n  - [Guidance truncated to fit budget]"
    return result
