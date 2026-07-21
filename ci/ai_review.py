#!/usr/bin/env python3
"""Run a structured AI PR review with Ollama/Qwen and publish it to GitHub."""

from __future__ import annotations

import argparse
import json
import random
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

MARKER = "<!-- ai-pr-review:qwen-ollama -->"
MAX_INLINE_COMMENTS = 10
MAX_FILE_EXCERPT_BYTES = 12000
MAX_TOTAL_EXCERPT_BYTES = 48000
MAX_REVIEW_BATCH_FILES = 1
MAX_BATCH_DIFF_BYTES = 45000
MAX_BATCH_EXCERPT_BYTES = 18000
MAX_POSITIVE_NOTES = 4
MAX_TEST_GAPS = 6

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}
SEVERITY_SCORE = {"high": 3, "medium": 2, "low": 1}

REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "overall_risk": {
            "type": "string",
            "enum": ["low", "medium", "high"],
        },
        "verdict": {
            "type": "string",
            "enum": ["comment", "request_changes"],
        },
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "path": {"type": "string"},
                    "line": {"type": "integer"},
                    "suspected_code": {"type": "string"},
                    "severity": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                    },
                    "category": {"type": "string"},
                    "suggested_fix": {"type": "string"},
                },
                "required": ["title", "body", "severity", "category"],
            },
        },
        "test_gaps": {
            "type": "array",
            "items": {"type": "string"},
        },
        "positive_notes": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": [
        "summary",
        "overall_risk",
        "verdict",
        "findings",
        "test_gaps",
        "positive_notes",
    ],
}


class ApiError(RuntimeError):
    """Raised when an external API request fails."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="owner/repo")
    parser.add_argument("--pr-number", required=True, type=int)
    parser.add_argument("--pr-title", default="")
    parser.add_argument("--pr-author", default="")
    parser.add_argument("--pr-url", default="")
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--head-ref", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--ollama-url", required=True)
    parser.add_argument("--ollama-model", required=True)
    parser.add_argument("--github-token", required=True)
    parser.add_argument("--github-api-url", required=True)
    parser.add_argument("--prompt-file", required=True)
    parser.add_argument("--analysis-file", required=True)
    parser.add_argument("--test-file", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-diff-bytes", type=int, default=180000)
    parser.add_argument("--max-files", type=int, default=25)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--fail-on-high-risk", action="store_true")
    return parser.parse_args()


def run_command(args: list[str]) -> str:
    result = subprocess.run(
        args,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def read_text(path: str) -> str:
    file_path = Path(path)
    if not file_path.exists():
        return ""
    return file_path.read_text(encoding="utf-8", errors="replace")


def trim_bytes(text: str, max_bytes: int) -> str:
    raw = text.encode("utf-8")
    if len(raw) <= max_bytes:
        return text

    suffix = "\n...[truncated]..."
    budget = max(0, max_bytes - len(suffix.encode("utf-8")))
    trimmed = raw[:budget].decode("utf-8", errors="ignore")
    return trimmed + suffix


def is_text_file(path: Path) -> bool:
    if not path.exists() or not path.is_file():
        return False

    sample = path.read_bytes()[:1024]
    return b"\x00" not in sample


def coerce_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def git_merge_base(base_ref: str, head_sha: str) -> str:
    return run_command(["git", "merge-base", base_ref, head_sha]).strip()


def git_changed_files(merge_base: str, head_sha: str) -> list[str]:
    output = run_command(
        ["git", "diff", "--name-only", "--find-renames", merge_base, head_sha, "--"]
    )
    return [line.strip() for line in output.splitlines() if line.strip()]


def git_patch(
    merge_base: str,
    head_sha: str,
    path: str | None = None,
    context_lines: int = 3,
) -> str:
    cmd = [
        "git",
        "diff",
        "--find-renames",
        f"--unified={context_lines}",
        merge_base,
        head_sha,
        "--",
    ]
    if path is not None:
        cmd.append(path)
    return run_command(cmd)


def file_priority(path: str) -> tuple[int, str]:
    if path.startswith("lib/") and path.endswith(".dart"):
        return (0, path)
    if path.startswith("test/") and path.endswith(".dart"):
        return (1, path)
    if path.endswith(".dart"):
        return (2, path)
    if path in {"pubspec.yaml", "analysis_options.yaml"}:
        return (3, path)
    if path.startswith("android/") or path.startswith("ios/"):
        return (4, path)
    return (5, path)


def build_prompt_inputs(
    merge_base: str,
    head_sha: str,
    changed_files: list[str],
    max_files: int,
    max_diff_bytes: int,
) -> tuple[list[str], str, list[str]]:
    selected_files: list[str] = []
    patches: list[str] = []
    omitted_files: list[str] = []
    remaining_bytes = max_diff_bytes

    for path in sorted(changed_files, key=file_priority):
        if len(selected_files) >= max_files:
            omitted_files.append(path)
            continue

        patch = git_patch(merge_base, head_sha, path=path, context_lines=3).strip()
        if not patch:
            continue

        patch_size = len(patch.encode("utf-8"))
        if patch_size > remaining_bytes and selected_files:
            omitted_files.append(path)
            continue

        if patch_size > remaining_bytes:
            patch = trim_bytes(patch, remaining_bytes)

        selected_files.append(path)
        patches.append(patch)
        remaining_bytes -= min(patch_size, remaining_bytes)

        if remaining_bytes <= 0:
            break

    diff_text = "\n\n".join(patches).strip()
    if omitted_files:
        omitted = ", ".join(omitted_files[:20])
        diff_text = (
            f"{diff_text}\n\n# Additional changed files omitted from the prompt\n# {omitted}"
            if diff_text
            else f"# Additional changed files omitted from the prompt\n# {omitted}"
        )

    return selected_files, diff_text, omitted_files


def build_file_excerpts(
    selected_files: list[str],
    *,
    max_total_bytes: int = MAX_TOTAL_EXCERPT_BYTES,
) -> str:
    chunks: list[str] = []
    remaining_bytes = max_total_bytes

    for relative_path in selected_files:
        file_path = Path(relative_path)
        if not is_text_file(file_path):
            continue

        raw_text = read_text(relative_path)
        if not raw_text.strip():
            continue

        excerpt = trim_bytes(raw_text, min(MAX_FILE_EXCERPT_BYTES, remaining_bytes))
        chunk = f"### {relative_path}\n{excerpt}".strip()
        chunk = trim_bytes(chunk, remaining_bytes)
        chunk_size = len(chunk.encode("utf-8"))

        if chunk_size == 0:
            break

        chunks.append(chunk)
        remaining_bytes -= chunk_size
        if remaining_bytes <= 0:
            break

    return "\n\n".join(chunks) if chunks else "No file excerpts were included."


def load_prompt(template_path: str, values: dict[str, str]) -> str:
    template = read_text(template_path)
    return template.format(**values)


def http_json(
    url: str,
    payload: dict[str, Any],
    *,
    token: str | None,
    retries: int,
) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["X-GitHub-Api-Version"] = "2026-03-10"
        headers["Accept"] = "application/vnd.github+json"

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                data = response.read().decode("utf-8")
                if not data.strip():
                    return {}
                return json.loads(data)
        except urllib.error.HTTPError as error:
            payload_text = error.read().decode("utf-8", errors="replace")
            status = error.code
            if status in {429, 500, 502, 503, 504} and attempt < retries:
                sleep_seconds = (2 ** attempt) + random.random()
                time.sleep(sleep_seconds)
                last_error = ApiError(
                    f"HTTP {status} from {url}: {payload_text[:500]}"
                )
                continue

            raise ApiError(f"HTTP {status} from {url}: {payload_text[:1000]}") from error
        except urllib.error.URLError as error:
            last_error = error
            if attempt >= retries:
                break
            sleep_seconds = (2 ** attempt) + random.random()
            time.sleep(sleep_seconds)

    raise ApiError(f"Request to {url} failed after {retries} attempts: {last_error}")


def call_ollama(
    args: argparse.Namespace,
    prompt: str,
    *,
    schema: dict[str, Any] = REVIEW_SCHEMA,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    request_payload = {
        "model": args.ollama_model,
        "stream": False,
        "format": schema,
        "options": {
            "temperature": 0.05,
            "top_p": 0.9,
            "repeat_penalty": 1.1,
        },
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a staff-level Flutter and Dart reviewer. "
                    "Review one changed file at a time. Prioritize technical correctness, "
                    "performance, code quality, architecture risks, and missing tests. "
                    "Return only valid JSON matching the provided schema."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    }

    response = http_json(
        f"{args.ollama_url.rstrip('/')}/api/chat",
        request_payload,
        token=None,
        retries=args.retries,
    )

    content = response.get("message", {}).get("content", "").strip()
    if not content:
        raise ApiError("Ollama returned an empty response body.")

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as error:
        raise ApiError(f"Ollama returned invalid JSON: {content[:1000]}") from error

    return request_payload, response, parsed


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def dedupe_strings(items: list[str], limit: int | None = None) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for item in items:
        normalized = normalize_whitespace(str(item))
        if not normalized:
            continue

        key = normalized.lower()
        if key in seen:
            continue

        seen.add(key)
        result.append(normalized)

        if limit is not None and len(result) >= limit:
            break

    return result


def format_code_snippet(snippet: str) -> str:
    cleaned = snippet.strip()
    if not cleaned or cleaned == "Snippet not provided by model.":
        return "_Snippet not provided by model._"
    return f"```dart\n{trim_bytes(cleaned, 500)}\n```"


def build_ci_summary(analyze_output: str, test_output: str) -> str:
    analyze_summary = "flutter analyze passed."
    if "No issues found!" in analyze_output:
        analyze_summary = "flutter analyze passed with no issues."
    elif analyze_output.strip():
        analyze_summary = trim_bytes(analyze_output.strip(), 1200)

    test_summary = "flutter test passed."
    if "All tests passed!" in test_output:
        test_summary = "flutter test passed."
    elif test_output.strip():
        test_summary = trim_bytes(test_output.strip(), 1200)

    return f"- {analyze_summary}\n- {test_summary}"


def chunked(items: list[str], size: int) -> list[list[str]]:
    return [items[index:index + size] for index in range(0, len(items), size)]


def build_review_batches(
    merge_base: str,
    head_sha: str,
    selected_files: list[str],
) -> list[dict[str, Any]]:
    batches: list[dict[str, Any]] = []

    for batch_files in chunked(selected_files, MAX_REVIEW_BATCH_FILES):
        patches: list[str] = []
        remaining_bytes = MAX_BATCH_DIFF_BYTES

        for path in batch_files:
            patch = git_patch(merge_base, head_sha, path=path, context_lines=8).strip()
            if not patch:
                continue

            patch = trim_bytes(patch, remaining_bytes)
            patch_bytes = len(patch.encode("utf-8"))
            if patch_bytes == 0:
                break

            patches.append(patch)
            remaining_bytes -= patch_bytes
            if remaining_bytes <= 0:
                break

        batches.append(
            {
                "files": batch_files,
                "diff_text": "\n\n".join(patches).strip() or "# No diff content detected.",
                "file_excerpts": build_file_excerpts(
                    batch_files,
                    max_total_bytes=MAX_BATCH_EXCERPT_BYTES,
                ),
            }
        )

    return batches


def normalize_findings(
    review: dict[str, Any],
    changed_files: set[str],
    *,
    default_path: str = "",
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    for raw in coerce_list(review.get("findings")):
        if not isinstance(raw, dict):
            continue

        title = str(raw.get("title", "")).strip()
        body = str(raw.get("body", "")).strip()
        severity = str(raw.get("severity", "medium")).strip().lower()
        category = str(raw.get("category", "general")).strip()
        suggested_fix = str(raw.get("suggested_fix", "")).strip()
        path = str(raw.get("path", "")).strip()
        suspected_code = str(raw.get("suspected_code", "")).strip()
        line_value = raw.get("line")

        if not title or not body:
            continue

        if severity not in {"low", "medium", "high"}:
            severity = "medium"

        if path and path not in changed_files:
            path = ""
        if not path and default_path:
            path = default_path

        line: int | None = None
        if isinstance(line_value, int) and line_value > 0:
            line = line_value
        elif isinstance(line_value, str) and line_value.isdigit():
            line = int(line_value)

        if not suspected_code:
            suspected_code = "Snippet not provided by model."

        findings.append(
            {
                "title": title,
                "body": body,
                "path": path,
                "line": line,
                "suspected_code": trim_bytes(suspected_code, 500),
                "severity": severity,
                "category": category,
                "suggested_fix": suggested_fix,
            }
        )

    findings.sort(key=lambda item: (SEVERITY_ORDER[item["severity"]], item["title"]))
    return findings


def normalize_review(
    parsed_review: dict[str, Any],
    changed_files: set[str],
    *,
    default_path: str = "",
) -> dict[str, Any]:
    summary = str(parsed_review.get("summary", "")).strip() or (
        "No summary was returned by the model."
    )
    overall_risk = str(parsed_review.get("overall_risk", "medium")).strip().lower()
    verdict = str(parsed_review.get("verdict", "comment")).strip().lower()

    if overall_risk not in {"low", "medium", "high"}:
        overall_risk = "medium"

    if verdict not in {"comment", "request_changes"}:
        verdict = "comment"

    positive_notes = [
        str(item).strip()
        for item in coerce_list(parsed_review.get("positive_notes"))
        if str(item).strip()
    ]
    test_gaps = [
        str(item).strip()
        for item in coerce_list(parsed_review.get("test_gaps"))
        if str(item).strip()
    ]

    findings = normalize_findings(
        parsed_review,
        changed_files,
        default_path=default_path,
    )

    if not findings and overall_risk == "high":
        verdict = "comment"

    return {
        "summary": summary,
        "overall_risk": overall_risk,
        "verdict": verdict,
        "findings": findings,
        "positive_notes": positive_notes,
        "test_gaps": test_gaps,
    }


def parse_diff_positions(diff_text: str) -> dict[str, dict[int, int]]:
    positions: dict[str, dict[int, int]] = {}
    current_path: str | None = None
    current_position = 0
    old_line: int | None = None
    new_line: int | None = None

    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            current_path = None
            current_position = 0
            old_line = None
            new_line = None
            continue

        if line.startswith("+++ "):
            path_marker = line[4:].strip()
            if path_marker.startswith("b/"):
                current_path = path_marker[2:]
                positions.setdefault(current_path, {})
            else:
                current_path = None
            continue

        if line.startswith("@@ "):
            match = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            if not match:
                continue
            old_line = int(match.group(1))
            new_line = int(match.group(2))
            continue

        if current_path is None or old_line is None or new_line is None:
            continue

        if line.startswith("\\ No newline at end of file"):
            continue

        prefix = line[:1]
        if prefix not in {" ", "+", "-"}:
            continue

        current_position += 1

        if prefix == " ":
            positions[current_path][new_line] = current_position
            old_line += 1
            new_line += 1
        elif prefix == "+":
            positions[current_path][new_line] = current_position
            new_line += 1
        elif prefix == "-":
            old_line += 1

    return positions


def inline_comment_body(finding: dict[str, Any]) -> str:
    lines = [
        f"**{finding['title']}**",
        "",
        f"File: `{finding['path'] or 'unknown'}`",
        f"Severity: `{finding['severity']}`",
        f"Category: `{finding['category']}`",
    ]

    if finding["line"] is not None:
        lines.append(f"Line: `{finding['line']}`")

    lines.extend(
        [
            "",
            "**Suspected code**",
            format_code_snippet(finding["suspected_code"]),
            "",
            "**Issue**",
            finding["body"],
        ]
    )

    if finding["suggested_fix"]:
        lines.extend(["", f"**Suggested fix**\n{finding['suggested_fix']}"])

    return "\n".join(lines).strip()


def split_review_comments(
    findings: list[dict[str, Any]],
    diff_positions: dict[str, dict[int, int]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    inline_comments: list[dict[str, Any]] = []
    summary_findings: list[dict[str, Any]] = []
    seen: set[tuple[str, int | None, str]] = set()

    for finding in findings:
        key = (finding["path"], finding["line"], finding["title"])
        if key in seen:
            continue
        seen.add(key)

        line = finding["line"]
        path = finding["path"]
        position = None

        if path and line is not None:
            position = diff_positions.get(path, {}).get(line)

        if position is not None and len(inline_comments) < MAX_INLINE_COMMENTS:
            inline_comments.append(
                {
                    "path": path,
                    "position": position,
                    "body": inline_comment_body(finding),
                }
            )
        else:
            summary_findings.append(finding)

    return inline_comments, summary_findings


def merge_batch_reviews(
    batch_reviews: list[dict[str, Any]],
    changed_files: set[str],
    selected_files: list[str],
) -> dict[str, Any]:
    merged_findings: list[dict[str, Any]] = []
    positive_notes: list[str] = []
    test_gaps: list[str] = []
    seen_findings: set[tuple[str, int | None, str, str]] = set()

    for review in batch_reviews:
        positive_notes.extend(review["positive_notes"])
        test_gaps.extend(review["test_gaps"])

        for finding in review["findings"]:
            key = (
                finding["path"],
                finding["line"],
                finding["title"].strip().lower(),
                normalize_whitespace(finding["body"]).lower(),
            )
            if key in seen_findings:
                continue

            seen_findings.add(key)
            merged_findings.append(finding)

    merged_findings.sort(
        key=lambda item: (SEVERITY_ORDER[item["severity"]], item["title"])
    )

    high_findings = [item for item in merged_findings if item["severity"] == "high"]
    medium_findings = [item for item in merged_findings if item["severity"] == "medium"]

    if high_findings:
        overall_risk = "high"
        verdict = "request_changes"
    elif medium_findings:
        overall_risk = "medium"
        verdict = "comment"
    else:
        overall_risk = "low"
        verdict = "comment"

    if merged_findings:
        category_counts: dict[str, int] = {}
        for finding in merged_findings:
            category = finding["category"].strip() or "general"
            category_counts[category] = category_counts.get(category, 0) + 1

        top_categories = ", ".join(
            category
            for category, _count in sorted(
                category_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )[:3]
        )

        summary = (
            f"Reviewed {len(selected_files)} changed files individually and found "
            f"{len(merged_findings)} material issue(s)."
        )
        if top_categories:
            summary += f" Main themes: {top_categories}."
        summary += f" Highest risk level: {overall_risk}."
    else:
        summary = (
            f"Reviewed {len(selected_files)} changed files individually and did not find any "
            "material issues in the supplied diff."
        )

    return {
        "summary": summary,
        "overall_risk": overall_risk,
        "verdict": verdict,
        "findings": normalize_findings({"findings": merged_findings}, changed_files),
        "positive_notes": dedupe_strings(positive_notes, limit=MAX_POSITIVE_NOTES),
        "test_gaps": dedupe_strings(test_gaps, limit=MAX_TEST_GAPS),
    }


def build_summary_markdown(
    args: argparse.Namespace,
    review: dict[str, Any],
    inline_comments: list[dict[str, Any]],
    summary_findings: list[dict[str, Any]],
    selected_files: list[str],
    omitted_files: list[str],
) -> str:
    lines = [
        MARKER,
        "## LMS AI agent review",
        "",
        #f"- Model: `{args.ollama_model}`",
        f"- PR: `#{args.pr_number}`",
        f"- Overall risk: `{review['overall_risk']}`",
        f"- Review action: `{review['verdict']}`",
        "",
        review["summary"],
    ]

    if inline_comments:
        lines.extend(
            [
                "",
                f"Inline comments posted: `{len(inline_comments)}`",
            ]
        )

    if summary_findings:
        lines.extend(["", "### Additional findings"])
        for finding in summary_findings:
            lines.extend(
                [
                    "",
                    f"#### {finding['title']}",
                    f"File: `{finding['path'] or 'unknown'}`",
                    f"Severity: `{finding['severity']}`",
                    f"Category: `{finding['category']}`",
                ]
            )
            if finding["line"] is not None:
                lines.append(f"Line: `{finding['line']}`")
            lines.extend(
                [
                    "Suspected code:",
                    format_code_snippet(finding["suspected_code"]),
                    f"Issue: {finding['body']}",
                ]
            )
            if finding["suggested_fix"]:
                lines.append(f"Suggested fix: {finding['suggested_fix']}")

    if review["test_gaps"]:
        lines.extend(["", "### Missing test scenarios"])
        for item in review["test_gaps"]:
            lines.append(f"- {item}")

    if review["positive_notes"]:
        lines.extend(["", "### Positive notes"])
        for item in review["positive_notes"]:
            lines.append(f"- {item}")

    lines.extend(
        [
            "",
            "### Review context",
            f"- Reviewed files included in prompt: `{len(selected_files)}`",
        ]
    )

    if omitted_files:
        lines.append(f"- Omitted from prompt due to size limits: `{len(omitted_files)}`")

    return "\n".join(lines).strip()


def publish_review(
    args: argparse.Namespace,
    review: dict[str, Any],
    inline_comments: list[dict[str, Any]],
    summary_findings: list[dict[str, Any]],
    selected_files: list[str],
    omitted_files: list[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    owner, repo = args.repo.split("/", 1)
    summary_body = build_summary_markdown(
        args,
        review,
        inline_comments,
        summary_findings,
        selected_files,
        omitted_files,
    )

    if inline_comments:
        review_payload = {
            "commit_id": args.head_sha,
            "body": summary_body,
            "event": "REQUEST_CHANGES"
            if review["verdict"] == "request_changes"
            else "COMMENT",
            "comments": inline_comments,
        }

        try:
            response = http_json(
                (
                    f"{args.github_api_url.rstrip('/')}/repos/{owner}/{repo}/pulls/"
                    f"{args.pr_number}/reviews"
                ),
                review_payload,
                token=args.github_token,
                retries=args.retries,
            )
            return review_payload, response
        except ApiError as error:
            fallback_payload = {
                "body": (
                    f"{summary_body}\n\n"
                    f"_Inline review publishing failed, so this run was posted as a PR comment._\n\n"
                    f"`{error}`"
                )
            }
            response = http_json(
                (
                    f"{args.github_api_url.rstrip('/')}/repos/{owner}/{repo}/issues/"
                    f"{args.pr_number}/comments"
                ),
                fallback_payload,
                token=args.github_token,
                retries=args.retries,
            )
            return fallback_payload, response

    issue_comment_payload = {"body": summary_body}
    response = http_json(
        (
            f"{args.github_api_url.rstrip('/')}/repos/{owner}/{repo}/issues/"
            f"{args.pr_number}/comments"
        ),
        issue_comment_payload,
        token=args.github_token,
        retries=args.retries,
    )
    return issue_comment_payload, response


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def gate_failed(review: dict[str, Any], args: argparse.Namespace) -> bool:
    return args.fail_on_high_risk and (
        review["overall_risk"] == "high" or review["verdict"] == "request_changes"
    )


def print_gate_failure(review: dict[str, Any]) -> None:
    print("AI review gate failed: LMS AI agent review marked this PR as high risk.", file=sys.stderr)
    print(f"Overall risk: {review['overall_risk']}", file=sys.stderr)
    print(f"Review action: {review['verdict']}", file=sys.stderr)

    findings = review.get("findings", [])
    for finding in findings[:5]:
        location = finding["path"] or "unknown"
        if finding["line"] is not None:
            location = f"{location}:{finding['line']}"
        print(
            f"- {finding['title']} [{finding['severity']}] at {location}: {finding['body']}",
            file=sys.stderr,
        )


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        merge_base = git_merge_base(args.base_ref, args.head_sha)
        changed_files = git_changed_files(merge_base, args.head_sha)
        selected_files, diff_text, omitted_files = build_prompt_inputs(
            merge_base,
            args.head_sha,
            changed_files,
            args.max_files,
            args.max_diff_bytes,
        )
        analyze_output = read_text(args.analysis_file)
        test_output = read_text(args.test_file)
        ci_summary = build_ci_summary(analyze_output, test_output)
        review_batches = build_review_batches(merge_base, args.head_sha, selected_files)

        batch_requests: list[dict[str, Any]] = []
        batch_responses: list[dict[str, Any]] = []
        batch_reviews: list[dict[str, Any]] = []

        for index, batch in enumerate(review_batches, start=1):
            prompt_values = {
                "repo": args.repo,
                "pr_number": str(args.pr_number),
                "pr_title": args.pr_title or "(no title provided by Jenkins)",
                "pr_author": args.pr_author or "(unknown)",
                "pr_url": args.pr_url or "(not provided)",
                "base_ref": args.base_ref,
                "head_ref": args.head_ref,
                "ci_summary": ci_summary,
                "batch_number": str(index),
                "batch_count": str(len(review_batches)),
                "changed_files": "\n".join(f"- {path}" for path in batch["files"])
                or "- No changed files detected.",
                "diff_text": batch["diff_text"],
                "file_excerpts": batch["file_excerpts"],
            }

            prompt = load_prompt(args.prompt_file, prompt_values)
            ollama_request, ollama_response, parsed_review = call_ollama(args, prompt)
            normalized_batch_review = normalize_review(
                parsed_review,
                set(batch["files"]),
                default_path=batch["files"][0] if batch["files"] else "",
            )

            batch_requests.append(
                {
                    "batch_number": index,
                    "files": batch["files"],
                    "request": ollama_request,
                }
            )
            batch_responses.append(
                {
                    "batch_number": index,
                    "files": batch["files"],
                    "response": ollama_response,
                }
            )
            batch_reviews.append(normalized_batch_review)

        normalized_review = merge_batch_reviews(
            batch_reviews,
            set(changed_files),
            selected_files,
        )
        diff_positions = parse_diff_positions(diff_text)
        inline_comments, summary_findings = split_review_comments(
            normalized_review["findings"],
            diff_positions,
        )
        publish_request, publish_response = publish_review(
            args,
            normalized_review,
            inline_comments,
            summary_findings,
            selected_files,
            omitted_files,
        )

        write_json(output_dir / "ollama_request.json", batch_requests)
        write_json(output_dir / "ollama_response.json", batch_responses)
        write_json(output_dir / "batch_reviews.json", batch_reviews)
        write_json(output_dir / "per_file_reviews.json", batch_reviews)
        write_json(output_dir / "normalized_review.json", normalized_review)
        write_json(output_dir / "publish_request.json", publish_request)
        write_json(output_dir / "publish_response.json", publish_response)
        write_json(
            output_dir / "review_context.json",
            {
                "merge_base": merge_base,
                "changed_files": changed_files,
                "selected_files": selected_files,
                "omitted_files": omitted_files,
                "review_batches": [
                    {
                        "files": batch["files"],
                    }
                    for batch in review_batches
                ],
                "inline_comment_count": len(inline_comments),
                "summary_finding_count": len(summary_findings),
            },
        )
        write_json(
            output_dir / "gate_result.json",
            {
                "fail_on_high_risk": args.fail_on_high_risk,
                "gate_failed": gate_failed(normalized_review, args),
                "overall_risk": normalized_review["overall_risk"],
                "verdict": normalized_review["verdict"],
            },
        )

        print(
            json.dumps(
                {
                    "status": "ok",
                    "selected_files": len(selected_files),
                    "inline_comments": len(inline_comments),
                    "summary_findings": len(summary_findings),
                    "overall_risk": normalized_review["overall_risk"],
                }
            )
        )
        if gate_failed(normalized_review, args):
            print_gate_failure(normalized_review)
            return 2
        return 0
    except Exception as error:
        write_json(output_dir / "error.json", {"error": str(error)})
        print(f"AI review failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
