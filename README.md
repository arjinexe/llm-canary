# llm-canary

Runs a fixed set of behavioral tests against your LLM on a schedule and tells you when the model starts answering differently than it used to.

```
  [01/27] universal-v1/ping-pong ... ✅  (1.00, 0.41s)
  [02/27] universal-v1/prime-100 ... ✅  (1.00, 0.83s)
  [03/27] json-reliability/simple-object ... ✅  (1.00, 0.92s)
  [04/27] reasoning/word-reversal ... ❌ ← score: 0.00

🚨 drift detected: -12.5% since 2025-12-01
   100.0% → 87.5%
   newly failing: word-reversal
```

## Why

Providers update their models constantly without telling you. [Chen et al. (2023)](https://arxiv.org/abs/2307.09009) showed GPT-4's accuracy on math problems dropped from 84% to 51% between March and June 2023 — no announcement, no changelog. You find out when something in production breaks.

llm-canary keeps a behavioral baseline and diffs every run against it.

## Install

```bash
# from PyPI
pip install llm-canary

# or from source (required if you forked the repo)
pip install .
```

> **Note for GitHub Actions users**: the included workflow installs with `pip install .` so it works without a PyPI release. If you previously had `pip install llm-canary` in your workflow, that's what caused the `Could not find a version` error — update to `pip install .`.

## Quick start

```bash
llm-canary init
export OPENAI_API_KEY=sk-...
llm-canary run
```

The first run saves a baseline. Every subsequent run compares against the previous one and prints the delta.

## Supported providers

| provider | env var(s) | example model |
|----------|-----------|---------------|
| `openai` | `OPENAI_API_KEY` | `gpt-4o` |
| `anthropic` | `ANTHROPIC_API_KEY` | `claude-3-5-sonnet-20241022` |
| `google` | `GOOGLE_API_KEY` | `gemini-1.5-pro` |
| `mistral` | `MISTRAL_API_KEY` | `mistral-large-latest` |
| `cohere` | `COHERE_API_KEY` | `command-r-plus` |
| `groq` | `GROQ_API_KEY` | `llama-3.1-70b-versatile` |
| `ollama` | `OLLAMA_HOST` (optional, default: `http://localhost:11434`) | `llama3.2` |
| `azure` | `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` | your deployment name |
| `bedrock` | `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` + `AWS_REGION` | `anthropic.claude-3-5-sonnet-20241022-v2:0` |

Bedrock requires `pip install "llm-canary[bedrock]"`.

Override provider and model at runtime without editing config:

```bash
llm-canary run --provider mistral --model mistral-large-latest
```

## Config

```yaml
# .llm-canary.yml
provider: openai
model: gpt-4o

suites:
  - universal-v1
  - json-reliability
  - reasoning

parallel: 5      # concurrent API calls
fail_under: 80   # exit 1 if pass rate drops below 80%

custom_tests:
  - name: my-classifier
    prompt: "Classify 'This is great!' as positive, negative, or neutral. One word."
    eval: exact
    expected: "positive"

  - name: email-format
    prompt: "Generate a valid email address."
    eval: regex
    expected: "^[\\w.-]+@[\\w.-]+\\.[a-z]{2,}$"

  - name: no-apologies
    prompt: "Tell me about the history of Rome."
    eval: not_contains
    expected: "I'm sorry"

  - name: answer-first
    prompt: "Is Paris the capital of France? Start your reply with Yes or No."
    eval: startswith
    expected: "Yes"

  - name: tone-check
    prompt: "Respond to an angry customer complaining about a delayed order."
    eval: llm_judge
    judge_prompt: "Is this response polite and professional? Reply yes or no.\n\nResponse: {response}"

judge:
  provider: openai
  model: gpt-4o-mini  # cheaper model for judging

alerts:
  slack_webhook: https://hooks.slack.com/services/...
  # always: false
```

## Evaluators

| evaluator | what it checks |
|-----------|----------------|
| `exact` | case-insensitive string match |
| `contains` | expected substring present in response |
| `not_contains` | expected substring absent from response |
| `startswith` | response begins with expected prefix |
| `regex` | response matches a regular expression |
| `json` | valid JSON with expected keys present |
| `semantic` | cosine similarity (falls back to word overlap without sentence-transformers) |
| `llm_judge` | another model judges the response using your prompt |

## Multi-assertion

A single test can have multiple assertions — all must pass:

```yaml
- name: structured-output
  prompt: "Return a JSON object with name and age fields."
  assert:
    - eval: json
      expected:
        name: ""
        age: 0
    - eval: not_contains
      expected: "```"
```

## Template variables

One test definition, many expansions:

```yaml
- name: translation-{{lang}}
  prompt: "Translate 'hello' to {{lang}}. Reply with only the translation."
  eval: contains
  vars:
    - lang: French
      expected: bonjour
    - lang: Spanish
      expected: hola
    - lang: Turkish
      expected: merhaba
```

## Multi-model comparison

```yaml
# .llm-canary.yml
providers:
  - provider: openai
    model: gpt-4o
  - provider: anthropic
    model: claude-3-5-sonnet-20241022
  - provider: google
    model: gemini-1.5-pro
```

```bash
llm-canary compare
```

```
  provider/model                       pass rate
  ────────────────────────────────── ──────────
  anthropic/claude-3-5-sonnet-20241022  ✅ 100.0%  (27/27)
  openai/gpt-4o                         ✅  96.3%  (26/27)
  google/gemini-1.5-pro                 ⚠️  88.9%  (24/27)
```

## History

```bash
llm-canary history --provider openai --model gpt-4o
```

Prints a trend table with a bar chart for the last 10 runs.

## Test suites

| suite | tests | what it covers |
|-------|-------|----------------|
| `universal-v1` | 15 | basic consistency, instruction following, arithmetic |
| `json-reliability` | 5 | valid JSON output, no markdown fences, required fields |
| `reasoning` | 7 | logic, pattern recognition, word manipulation |

## Report

```bash
llm-canary report
# filter by provider/model:
llm-canary report --provider anthropic --model claude-3-5-sonnet-20241022
```

Writes `canary-report.html`. No external dependencies, works offline. Includes a pass-rate sparkline across recent runs when history is available.

## CLI reference

```
llm-canary run
  --config .llm-canary.yml
  --output-dir .canary-results
  --provider PROVIDER
  --model MODEL
  --suite SUITE          run only this suite
  --tests PATH           CSV file of additional tests
  --fail-under N         exit 1 if pass rate < N%
  --quiet                suppress per-test output
  --json                 print summary as JSON

llm-canary report
  --results-dir .canary-results
  --output canary-report.html
  --provider PROVIDER
  --model MODEL

llm-canary history
  --results-dir .canary-results
  --provider PROVIDER    (required)
  --model MODEL          (required)
  --limit N              number of recent runs (default: 10)

llm-canary compare
  --config .llm-canary.yml
  --output-dir .canary-results
```

## Automated monitoring

The repo includes `.github/workflows/canary.yml`. It runs every Monday at 09:00 UTC, caches results between runs so drift detection has history to diff against, and uploads an HTML report as a build artifact.

To use it in your repo: copy the workflow file, add your API key(s) as repository secrets under **Settings → Secrets → Actions**, and set your provider in `.llm-canary.yml`. You can also set `fail_under` via the manual `workflow_dispatch` input.

## Parallel execution

```yaml
parallel: 10  # concurrent API calls
```

Keep this under your provider's rate limit. For sequential execution omit it or set it to `1`.

## Optional dependencies

```bash
pip install "llm-canary[semantic]"  # sentence-transformers for the semantic evaluator
pip install "llm-canary[bedrock]"   # boto3 for AWS Bedrock
```

## FAQ

**Does this send prompts anywhere besides my provider?** No.

**What does it cost?** 27 API calls per full run. At GPT-4o pricing that's under $0.05.

**What do I do when drift is detected?** Run `llm-canary report`, check which tests changed, then decide whether to update your prompts or pin a specific model version.

**Can I add my own tests?** Yes — `custom_tests` in `.llm-canary.yml`, a CSV file via `--tests`, or a new suite folder under `llm_canary/suites/`. See [CONTRIBUTING.md](CONTRIBUTING.md).

**Why is my GitHub Actions step failing with `command not found`?** The workflow must install the package before the CLI is available. Make sure the install step is `pip install .` (not `pip install llm-canary` unless the package is published to PyPI).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Adding test cases is the most useful contribution.

## License

MIT
