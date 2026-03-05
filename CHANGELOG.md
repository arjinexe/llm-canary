# Changelog

## [0.4.0] — 2025-03-05

- Template variables: use `{{var}}` in prompt/expected, expand a single test into many with `vars` list
- CSV test import: `llm-canary run --tests my-tests.csv` or `test_files:` in config
- Multi-assertion: `assert:` list in a test — all assertions must pass, score is the mean


## [0.3.0] — 2025-03-05

- `llm_judge` evaluator: use a model to judge open-ended responses
- `regex` evaluator: match response against a regular expression
- `parallel` config option: run tests concurrently
- `llm-canary compare`: run suite against multiple providers/models and print comparison table
- `judge` config block: configure a separate model for llm_judge evaluations

## [0.2.0] — 2025-02-20

New providers: Mistral, Cohere, Groq, Ollama (local), Azure OpenAI, AWS Bedrock.

- `llm-canary report` now accepts `--provider` and `--model` flags to filter results when multiple providers are in the results directory
- Fixed GitHub Actions cache key — results were not persisting between runs, breaking drift detection
- CLI `--version` now reads from the package version instead of a hardcoded string
- `json` evaluator now warns when `expected` is not a dict instead of silently passing everything
- `alerts.always` option documented in the generated config template
- Bedrock available as optional dependency: `pip install "llm-canary[bedrock]"`

## [0.1.0] — 2025-02-10

Initial release.

- CLI: `init`, `run`, `report`
- `--provider` and `--model` flags to override config at runtime
- Providers: OpenAI, Anthropic, Google Gemini
- Evaluators: `exact`, `contains`, `json`, `semantic`
- Built-in suites: `universal-v1` (15 tests), `json-reliability` (5 tests), `reasoning` (7 tests)
- Drift detection against previous run with delta reporting
- Slack webhook alerts on drift
- Retry with exponential backoff on 429/5xx
- GitHub Actions workflow with result caching
- `suites_dir` config option for custom suite directories
