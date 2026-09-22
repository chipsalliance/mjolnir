# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Publishes Mjolnir PR diff scan findings as GitHub Pull Request review and inline comments."""

import argparse
import json
import os
from pathlib import Path
import re
import sys
from typing import Any
import urllib.error
import urllib.request

# Matches https://github.com/<owner>/<repo>/pull/<number>
# Example: "https://github.com/chipsalliance/mjolnir/pull/123" -> ("chipsalliance/mjolnir", "123")
_PR_URL_RE = re.compile(r"github\.com/([^/]+/[^/]+)/pull/(\d+)")

# Matches https://github.com/<owner>/<repo>(.git)
# Example: "https://github.com/chipsalliance/mjolnir.git" -> "chipsalliance/mjolnir"
_REPO_URL_RE = re.compile(r"github\.com[:/]([^/]+/[^/.]+?)(?:\.git)?/?$")

# Matches the first positive integer line number in a finding's `location` string.
# Examples: "42" -> 42, "L120-L135" -> 120, "rom_ext_main (line 88)" -> 88
_LINE_NUM_RE = re.compile(r"\b(\d+)\b")


def _find_latest_run_dir(search_root: Path) -> Path | None:
    """Locates the most recently modified Mjolnir run directory containing vulnerabilities_minimal.json."""
    if not search_root.exists():
        return None
    if (search_root / "vulnerabilities_minimal.json").is_file() or (
        search_root / "vulnerabilities.json"
    ).is_file():
        return search_root

    candidates: list[tuple[float, Path]] = []
    for name in ("vulnerabilities_minimal.json", "vulnerabilities.json"):
        for path in search_root.rglob(name):
            try:
                candidates.append((path.stat().st_mtime, path.parent))
            except OSError:
                continue
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _extract_line_number(location: str) -> int | None:
    """Extracts a 1-indexed line number from a finding location string if present."""
    if not location:
        return None
    if match := _LINE_NUM_RE.search(str(location)):
        line = int(match.group(1))
        return line if line > 0 else None
    return None


def _fetch_pr_patch_lines(repo: str, pr_num: str, token: str) -> dict[str, set[int]]:
    """Fetches PR unified diff from GitHub API and returns {filepath: set_of_patch_lines}."""
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_num}"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github.v3.diff",
            "Authorization": f"Bearer {token}",
            "User-Agent": "mjolnir-security-auditor",
        },
    )
    diff_lines: dict[str, set[int]] = {}
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return diff_lines

    cur_file = None
    cur_line = 0
    for line in content.splitlines():
        if line.startswith("diff --git"):
            m = re.search(r" b/(.*)$", line)
            cur_file = m.group(1).strip().lstrip("./") if m else None
            if cur_file and cur_file not in diff_lines:
                diff_lines[cur_file] = set()
        elif line.startswith("@@") and cur_file:
            m = re.search(r"\+(\d+)", line)
            cur_line = int(m.group(1)) if m else 0
        elif cur_line > 0 and cur_file:
            if line.startswith("+"):
                diff_lines[cur_file].add(cur_line)
                cur_line += 1
            elif line.startswith(" "):
                cur_line += 1
    return diff_lines


def _finding_line_in_patch(finding: dict[str, Any], patch_lines: dict[str, set[int]]) -> int | None:
    """Returns the line number within the patch if finding intersects the diff, else None."""
    file_path = str(finding.get("file", "")).strip().lstrip("./")
    valid_lines = patch_lines.get(file_path)
    if not valid_lines:
        return None
    loc = str(finding.get("location", ""))
    nums = [int(n) for n in re.findall(r"\d+", loc) if int(n) > 0]
    if not nums:
        return None
    target_lines = (
        set(range(nums[0], nums[1] + 1)) if len(nums) >= 2 and nums[1] >= nums[0] else set(nums)
    )
    overlap = target_lines & valid_lines
    return min(overlap) if overlap else None


def _resolve_repo_and_pr(
    args_repo: str | None,
    args_pr: str | None,
    metadata: dict[str, Any],
) -> tuple[str | None, str | None]:
    """Resolves (owner/repo, pr_number) from CLI flags, metadata.json, or GitHub Actions env vars."""
    repo = args_repo or os.environ.get("GITHUB_REPOSITORY")
    pr_num = None

    raw_pr = args_pr or metadata.get("pr") or ""
    if raw_pr:
        if url_match := _PR_URL_RE.search(str(raw_pr)):
            repo = repo or url_match.group(1)
            pr_num = url_match.group(2)
        elif str(raw_pr).strip().isdigit():
            pr_num = str(raw_pr).strip()

    if not repo and metadata.get("repo"):
        if repo_match := _REPO_URL_RE.search(str(metadata["repo"])):
            repo = repo_match.group(1)

    return repo, pr_num


def _format_inline_comment_body(finding: dict[str, Any]) -> str:
    """Formats a single vulnerability finding as a concise inline GitHub PR review comment."""
    sev = str(finding.get("severity", "LOW")).upper()
    title = finding.get("title", "Untitled Security Finding")
    desc = finding.get("description", "").strip()
    rec = finding.get("recommendation", "").strip()

    lines = [f"**[Mjolnir `{sev}`] {title}**"]
    if desc:
        lines.append(f"\n{desc}")
    if rec:
        lines.append(f"\n**Recommendation:**\n{rec}")
    return "\n".join(lines)


def _build_review_payload(
    open_findings: list[dict[str, Any]],
    metadata: dict[str, Any],
    commit_id: str | None,
    patch_lines: dict[str, set[int]] | None = None,
) -> dict[str, Any]:
    """Constructs a GitHub Pull Request Review API payload with summary body and inline comments."""
    inline_comments: list[dict[str, Any]] = []
    unmapped_findings: list[dict[str, Any]] = []

    # Deterministically scrub findings whose lines are outside the PR patch diff
    if patch_lines is not None:
        filtered_findings = []
        for finding in open_findings:
            line_num = _finding_line_in_patch(finding, patch_lines)
            if line_num is not None:
                filtered_findings.append(finding)
                inline_comments.append(
                    {
                        "path": str(finding.get("file", "")).strip().lstrip("./"),
                        "line": line_num,
                        "side": "RIGHT",
                        "body": _format_inline_comment_body(finding),
                    }
                )
        open_findings = filtered_findings
    else:
        for finding in open_findings:
            file_path = str(finding.get("file", "")).strip().lstrip("./")
            line_num = _extract_line_number(str(finding.get("location", "")))
            if file_path and line_num is not None:
                inline_comments.append(
                    {
                        "path": file_path,
                        "line": line_num,
                        "side": "RIGHT",
                        "body": _format_inline_comment_body(finding),
                    }
                )
            else:
                unmapped_findings.append(finding)

    model = metadata.get("model", "Unknown")
    short_commit = str(commit_id or metadata.get("target_commit") or "HEAD")[:8]

    if not open_findings:
        summary = (
            f"### Mjolnir Security Audit (`{short_commit}`)\n\n"
            f"No open security vulnerabilities were identified in this pull request diff (Model: `{model}`)."
        )
    else:
        summary_lines = [
            f"### Mjolnir Security Audit (`{short_commit}`)",
            "",
            f"Identified **{len(open_findings)}** open security finding(s) in this pull request diff (Model: `{model}`):",
            "",
            "| Severity | Title | Location |",
            "| :--- | :--- | :--- |",
        ]
        for finding in open_findings:
            sev = str(finding.get("severity", "LOW")).upper()
            title = finding.get("title", "Untitled")
            loc_str = finding.get("file", "")
            if finding.get("location"):
                loc_str = f"{loc_str}:{finding['location']}"
            summary_lines.append(f"| **{sev}** | {title} | `{loc_str}` |")

        if unmapped_findings:
            summary_lines.extend(["", "#### Additional Findings Details", ""])
            for finding in unmapped_findings:
                summary_lines.append(_format_inline_comment_body(finding))
                summary_lines.append("\n---\n")

        summary = "\n".join(summary_lines)

    payload: dict[str, Any] = {
        "body": summary,
        "event": "COMMENT",
        "comments": inline_comments,
    }
    if commit_id and commit_id not in ("unknown", "local-untracked", "HEAD"):
        payload["commit_id"] = commit_id
    return payload


def _github_post(url: str, token: str, payload: dict[str, Any]) -> None:
    """Sends an authenticated POST request to the GitHub REST API."""
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "mjolnir-security-auditor",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp.read()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Post Mjolnir PR diff scan findings as inline GitHub PR review comments."
    )
    parser.add_argument(
        "--output-dir",
        default="./test-out/results",
        help="Root directory containing Mjolnir scan runs (default: ./test-out/results)",
    )
    parser.add_argument("--run-dir", help="Explicit Mjolnir run directory")
    parser.add_argument("--repo", help="GitHub repository in owner/repo format")
    parser.add_argument("--pr", help="Pull request number or URL")
    parser.add_argument("--commit-id", help="Explicit HEAD commit SHA for the PR review")
    parser.add_argument(
        "--post-empty",
        action="store_true",
        help="Post a clean summary comment even when 0 open findings were discovered",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the GitHub review JSON payload to stdout without calling the GitHub API",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir) if args.run_dir else _find_latest_run_dir(Path(args.output_dir))
    if not run_dir or not run_dir.exists():
        print(
            f"No Mjolnir run directory found under {args.run_dir or args.output_dir}.",
            file=sys.stderr,
        )
        return 1

    minimal_file = run_dir / "vulnerabilities_minimal.json"
    full_file = run_dir / "vulnerabilities.json"
    meta_file = run_dir / "metadata.json"

    if minimal_file.is_file():
        raw_findings = json.loads(minimal_file.read_text(encoding="utf-8"))
    elif full_file.is_file():
        all_findings = json.loads(full_file.read_text(encoding="utf-8"))
        raw_findings = [f for f in all_findings if str(f.get("status", "Open")).lower() == "open"]
    else:
        raw_findings = []

    metadata = json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.is_file() else {}
    commit_id = args.commit_id or os.environ.get("GITHUB_SHA") or metadata.get("target_commit")
    repo, pr_num = _resolve_repo_and_pr(args.repo, args.pr, metadata)
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

    patch_lines = (
        _fetch_pr_patch_lines(repo, pr_num, token) if (repo and pr_num and token) else None
    )
    payload = _build_review_payload(raw_findings, metadata, commit_id, patch_lines)

    if args.dry_run:
        print(json.dumps(payload, indent=2))
        return 0

    if not payload["comments"] and not args.post_empty:
        print("0 open findings in PR diff; skipping PR comment (--post-empty not set).")
        return 0

    if not repo or not pr_num or not token:
        print(
            "Error: GITHUB_TOKEN, --repo (or GITHUB_REPOSITORY), and --pr are required to post PR comments.",
            file=sys.stderr,
        )
        return 1

    review_url = f"https://api.github.com/repos/{repo}/pulls/{pr_num}/reviews"
    try:
        _github_post(review_url, token, payload)
        print(
            f"Posted PR review to {repo}#{pr_num} with {len(payload['comments'])} inline comment(s)."
        )
    except urllib.error.HTTPError as err:
        # If GitHub rejects an inline line number outside the diff hunk (HTTP 422),
        # gracefully fall back to posting the full markdown summary + details as a PR comment.
        if err.code == 422 and payload.get("comments"):
            fallback_lines = [payload["body"], "", "#### Inline Finding Details", ""]
            for comment in payload["comments"]:
                fallback_lines.append(
                    f"**`{comment['path']}:{comment['line']}`**\n{comment['body']}"
                )
                fallback_lines.append("\n---\n")
            issue_comment_url = f"https://api.github.com/repos/{repo}/issues/{pr_num}/comments"
            _github_post(issue_comment_url, token, {"body": "\n".join(fallback_lines)})
            print(f"Posted fallback PR summary comment to {repo}#{pr_num}.")
        else:
            raise

    return 0


if __name__ == "__main__":
    sys.exit(main())
