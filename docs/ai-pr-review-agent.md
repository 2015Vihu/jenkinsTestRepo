# AI Pull Request Review Agent

This repository now includes a Jenkins-driven PR review flow for Flutter projects that uses a local Qwen model through Ollama and posts the result back to GitHub.

The current pipeline is configured as a blocking quality gate: the PR build should stay red until `flutter analyze`, `flutter test`, and the Ollama-powered expert review all complete successfully.

## Implementation plan

1. GitHub sends a pull request webhook to Jenkins.
2. Jenkins checks out the PR branch and resolves the repository metadata.
3. Jenkins runs `flutter analyze` and stores the full output in `analyze_output.txt`.
4. Jenkins runs `flutter test` and stores the full output in `test_output.txt`.
5. Only when both stages pass, Jenkins fetches the target branch and computes the PR merge base.
6. The Python worker builds an AI review prompt from:
   - PR metadata
   - changed file list
   - git diff
   - current file excerpts
   - `flutter analyze` output
   - `flutter test` output
7. Jenkins checks `GET /api/tags` on the configured Ollama host to verify the service is reachable and models are visible.
8. The worker calls `POST /api/chat` on Ollama with a structured JSON schema.
9. The worker validates the Qwen response, converts eligible findings into inline GitHub review comments, and falls back to a general PR comment when needed.
10. Jenkins archives the raw AI request and response artifacts for debugging.

## Files added

- [Jenkinsfile](/Users/Alok/Desktop/TestProject/jenkinsTestRepo/Jenkinsfile)
- [ci/ai_review.py](/Users/Alok/Desktop/TestProject/jenkinsTestRepo/ci/ai_review.py)
- [ci/prompts/qwen_pr_review_prompt.txt](/Users/Alok/Desktop/TestProject/jenkinsTestRepo/ci/prompts/qwen_pr_review_prompt.txt)

## Jenkins credentials

Create these Jenkins credentials before enabling the flow:

- `github-pat`: GitHub token with permission to comment on pull requests.
- `android-upload-keystore`: file credential for Android release builds.
- `android-store-password`: secret text.
- `android-key-password`: secret text.
- `android-key-alias`: secret text.
- `firebase-service-account`: file credential.
- `firebase-android-app-id`: secret text.

For GitHub, prefer a GitHub App installation token or a fine-grained PAT with pull request write access instead of a classic PAT.

## Ollama integration example

Local test call:

```bash
curl -X POST http://127.0.0.1:11434/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2.5-coder:7b",
    "stream": false,
    "messages": [
      {
        "role": "user",
        "content": "Review this Flutter diff and return structured JSON findings."
      }
    ]
  }'
```

Load the model on the Jenkins agent or Ollama host ahead of time:

```bash
ollama pull qwen2.5-coder:7b
```

If `ollama` is not found on your terminal, install Ollama first. The official download page provides a macOS download and install script, and notes that macOS 14 Sonoma or later is required. The official API docs also show that `GET /api/tags` is the health check for listing locally available models. Sources: [Ollama download](https://ollama.com/download/mac), [Ollama API docs](https://github.com/ollama/ollama/blob/main/docs/api.md).

## GitHub PR comment strategy

The Python worker uses two GitHub endpoints:

- Pull request reviews for inline comments on changed lines.
- Issue comments as a fallback when GitHub rejects inline placement.

This means developers still see the AI review inside the PR conversation even if a precise inline anchor cannot be created.

## Error handling and retries

The implementation uses retry logic at two levels:

- Jenkins wraps the Expert Review stage in `retry(2)` for transient failures.
- `ci/ai_review.py` retries Ollama and GitHub requests with exponential backoff on `429` and `5xx` responses.

Fallback behavior:

- If Ollama cannot be reached, the Expert Review stage fails and the PR build stays red.
- If Qwen returns invalid JSON, the Expert Review stage fails and the PR build stays red.
- If GitHub rejects inline comments, the script posts a regular PR comment with the same review summary.
- All request and response payloads are archived in `build/ai-review/` for debugging.

## Production architecture recommendation

Use this layout in production:

1. Run Jenkins agents close to the Ollama host to avoid large diff payload latency.
2. Keep Ollama on a dedicated node with pinned CPU or GPU resources.
3. Pre-pull the Qwen model during node provisioning instead of at build time.
4. If you want softer rollout behavior, you can temporarily switch the AI stage back to non-blocking. The current repository version keeps it blocking.
5. Enforce prompt and diff size limits to control latency and memory usage.
6. Archive every model request and response with the build for auditability.
7. Add a review marker or idempotency key if you later want the bot to update its prior comment instead of posting a new one each run.
8. Move secrets to Jenkins credentials only. Do not hardcode GitHub tokens, keystore values, or model host URLs in source control.

## Example local dry run

After `flutter analyze` and `flutter test` have produced output files, you can dry-run the worker from the repo root:

```bash
python3 ci/ai_review.py \
  --repo owner/repo \
  --pr-number 42 \
  --pr-title "Add onboarding flow" \
  --pr-author "octocat" \
  --pr-url "https://github.com/owner/repo/pull/42" \
  --base-ref origin/main \
  --head-ref feature/onboarding \
  --head-sha "$(git rev-parse HEAD)" \
  --ollama-url http://127.0.0.1:11434 \
  --ollama-model qwen2.5-coder:7b \
  --github-token "$GITHUB_TOKEN" \
  --github-api-url https://api.github.com \
  --prompt-file ci/prompts/qwen_pr_review_prompt.txt \
  --analysis-file analyze_output.txt \
  --test-file test_output.txt \
  --output-dir build/ai-review
```
