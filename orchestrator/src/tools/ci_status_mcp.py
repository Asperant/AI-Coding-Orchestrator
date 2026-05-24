import json
import re
import subprocess
import shutil
from typing import Protocol

from core.safety import guard_text_output

class CiClient(Protocol):
    def read_ci_status(self, repo: str, branch: str | None, pr_number: str | None, limit: int) -> str:
        ...

class MockCiClient:
    def __init__(self, responses: dict[tuple[str, str | None, str | None], str] | None = None):
        self._responses = responses or {}

    def read_ci_status(self, repo: str, branch: str | None, pr_number: str | None, limit: int) -> str:
        key = (repo, branch, pr_number)
        if key in self._responses:
            return self._responses[key]
        return "Mock CI status output"

class GhCiClient:
    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    def read_ci_status(self, repo: str, branch: str | None, pr_number: str | None, limit: int) -> str:
        if not shutil.which("gh"):
            raise ValueError("gh CLI is not installed or not in PATH.")

        cmd = ["gh", "run", "list", "--repo", repo, "--limit", str(limit), "--json", "status,conclusion,name,url,headBranch,event"]
        if branch:
            cmd.extend(["--branch", branch])
        # If PR number is provided, we can't directly filter run list by PR using gh natively without complex querying,
        # but we can omit branch filter and just fetch recent runs, perhaps noting PR is not strictly filtered by gh.
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout)
            if result.returncode != 0:
                raise ValueError(f"gh CLI error: {result.stderr.strip()}")
                
            runs = json.loads(result.stdout)
        except subprocess.TimeoutExpired:
            raise ValueError("gh CLI request timed out.")
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON received from gh CLI.")

        if not runs:
            return f"No recent CI runs found for {repo}."

        lines = [f"Found {len(runs)} recent CI runs for {repo}."]
        
        has_failed = False
        has_running = False
        
        for run in runs:
            name = run.get("name", "Unknown")
            status = run.get("status", "unknown")
            conclusion = run.get("conclusion", "")
            head_branch = run.get("headBranch", "unknown")
            event = run.get("event", "unknown")
            
            if status in ("in_progress", "queued", "waiting", "pending"):
                has_running = True
                display_status = status
            else:
                display_status = conclusion if conclusion else status
                if conclusion == "failure":
                    has_failed = True

            lines.append(f"- {name} (branch: {head_branch}, event: {event}): {display_status}")

        if has_running:
            overall_status = "running"
        elif has_failed:
            overall_status = "failed"
        else:
            overall_status = "passed"
            
        lines.insert(1, f"Overall status summary of these runs: {overall_status}")

        return "\n".join(lines)


def run_ci_status_tool(
    tool_name: str,
    provider: str,
    repo: str | None = None,
    branch: str | None = None,
    pr_number: str | None = None,
    limit: int = 5,
    github_client: str = "gh",
    client: CiClient | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "executed": False,
        "blocked": False,
        "tool_name": tool_name,
        "provider": provider,
        "repo": repo,
        "branch": branch,
        "pr_number": pr_number,
        "content_summary": None,
        "context_blocks": [],
        "message": "",
        "safety_notes": [],
    }

    if tool_name != "test.ci_status.read":
        result["blocked"] = True
        result["message"] = f"Tool {tool_name} is not allowed or supported."
        return result

    if provider != "github_actions":
        result["blocked"] = True
        result["message"] = f"Provider {provider} is not supported."
        return result

    if not repo:
        result["blocked"] = True
        result["message"] = "repo is required for test.ci_status.read."
        return result

    if not re.match(r"^[a-zA-Z0-9_\-\.]+/[a-zA-Z0-9_\-\.]+$", repo):
        result["blocked"] = True
        result["message"] = "Invalid repo format. Must be owner/repo."
        return result

    if branch and not re.match(r"^[a-zA-Z0-9_\-\.\/]+$", branch):
        result["blocked"] = True
        result["message"] = "Invalid branch name format."
        return result
        
    if pr_number and not re.match(r"^\d+$", pr_number):
        result["blocked"] = True
        result["message"] = "Invalid PR number format."
        return result

    if not (1 <= limit <= 50):
        result["blocked"] = True
        result["message"] = "Limit must be between 1 and 50."
        return result

    if client is None:
        if github_client == "gh":
            client = GhCiClient()
        else:
            result["blocked"] = True
            result["message"] = "Real provider is not implemented/configured for this tool."
            return result

    try:
        content = client.read_ci_status(repo, branch, pr_number, limit)
        guard_result = guard_text_output(content, "CI status read")
        
        if not guard_result["allowed"]:
            result["blocked"] = True
            result["message"] = guard_result["safe_message"]
            return result

        result["executed"] = True
        result["message"] = "Successfully read CI status."
        
        # Determine overall status for summary
        status_match = re.search(r"Overall status summary of these runs: (running|failed|passed)", content)
        overall_status = status_match.group(1) if status_match else "unknown"
        
        if "No recent CI runs found" in content:
            overall_status = "unknown"

        result["content_summary"] = f"Overall status: {overall_status}"
        
        source = f"{provider}:{repo}"
        if branch:
            source += f"@{branch}"
        if pr_number:
            source += f"#PR{pr_number}"
            
        blocks = result["context_blocks"]
        assert isinstance(blocks, list)
        blocks.append({
            "source": source,
            "tool_name": tool_name,
            "content": content,
            "safe": True,
            "blocked": False,
        })
        
    except Exception as e:
        result["blocked"] = True
        result["message"] = f"Error reading CI status: {e}"

    return result


def format_ci_status_result(result: dict[str, object]) -> str:
    lines = [
        f"CI tool: {result['tool_name']}",
        f"Provider: {result['provider']}",
        f"Repo: {result['repo']}",
    ]
    if result.get('branch'):
        lines.append(f"Branch: {result['branch']}")
    if result.get('pr_number'):
        lines.append(f"PR Number: {result['pr_number']}")
        
    lines.extend([
        f"Executed: {'yes' if result.get('executed') else 'no'}",
        f"Blocked: {'yes' if result.get('blocked') else 'no'}",
        f"Message: {result.get('message')}",
    ])
    
    notes = result.get("safety_notes")
    if notes and isinstance(notes, list):
        lines.append(f"Safety notes: {'; '.join(notes)}")
        
    if result.get("content_summary"):
        lines.append(f"Summary: {result['content_summary']}")
        
    blocks = result.get("context_blocks")
    if blocks and isinstance(blocks, list):
        lines.append(f"Context blocks: {len(blocks)}")
        for i, b in enumerate(blocks):
            safe_val = "yes" if b.get("safe") else "no"
            blocked_val = "yes" if b.get("blocked") else "no"
            lines.append(f"Block {i + 1} - source={b.get('source')} safe={safe_val} blocked={blocked_val}")
            
    return "\n".join(lines)
