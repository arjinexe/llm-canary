# llm-canary

Runs a fixed set of behavioral tests against your LLM on a schedule and tells you when it starts answering differently than it used to.

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

Providers update their models constantly without telling you. [Chen et al. (2023)](https://arxiv.org/abs/2307.09009) showed GPT-4's accuracy on math problems dropped from 84% to 51% between March and June — no announcement, no changelog. You usually find out when something in production breaks.

llm-canary keeps a baseline of how your model behaves and diffs every run against it.

## Install

```bash
pip install llm-canary
```

## Quick start

```bash
llm-canary init
export OPENAI_API_KEY=sk-...
llm-canary run
```

First run saves a baseline. Every run after that compares against the previous one.

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

Override provider and model at runtime:

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

parallel: 5  # run tests concurrently

custom_tests:
  - name: my-classifier
    prompt: "Classify 'This is great!' as positive, negative, or neutral. One word."
    eval: exact
    expected: "positive"

  - name: email-format
    prompt: "Generate a valid email address."
    eval: regex
    expected: "^[\\w.-]+@[\\w.-]+\\.[a-z]{2,}$"

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
| `regex` | response matches a regular expression |
| `json` | valid JSON with expected keys present |
| `semantic` | cosine similarity (falls back to word overlap without sentence-transformers) |
| `llm_judge` | another model judges the response using your prompt |

## Multi-model comparison

Run the same suite across multiple models at once:

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

Output:

```
  provider/model                       pass rate
  ────────────────────────────────── ──────────
  anthropic/claude-3-5-sonnet-20241022  ✅ 100.0%  (27/27)
  openai/gpt-4o                         ✅  96.3%  (26/27)
  google/gemini-1.5-pro                 ⚠️  88.9%  (24/27)
```

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

Writes `canary-report.html` — no dependencies, works offline.

## Parallel execution

```yaml
parallel: 10  # concurrent API calls
```

Speeds up large suites significantly. Keep under your provider's rate limit.

## Automated monitoring

The repo includes `.github/workflows/canary.yml`. It runs every Monday, caches results between runs so drift detection has history to compare against, and uploads an HTML report as a build artifact.

To use it in your own repo: copy the workflow file, add your API key(s) as repository secrets under Settings → Secrets → Actions, and set your provider in `.llm-canary.yml`.

For semantic similarity:

```bash
pip install "llm-canary[semantic]"
```

## FAQ

**Does this send prompts anywhere besides my provider?** No.

**What does it cost?** 27 API calls per full run. At GPT-4o pricing that's under $0.05.

**What do I do when drift is detected?** Run `llm-canary report`, check which tests changed, then decide whether to update your prompts or pin to a specific model version.

**Can I add my own tests?** Yes — either add them to `custom_tests` in `.llm-canary.yml`, or add a new suite folder under `llm_canary/suites/`. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Adding test cases is the most useful thing you can do.

## License

MIT
