# Changelog

## [2.0.0] — 2025-03-06

### Fixed
- **GitHub Actions**: replaced `pip install llm-canary` with `pip install .` so the workflow installs from the local repository rather than PyPI, fixing both the `Could not find a version` error and the subsequent `command not found` error.

### Added
- `not_contains` evaluator — assert that a string does **not** appear in the response (useful for checking a model hasn't regressed into apologetic or off-topic phrasing).
- `startswith` evaluator — assert the response begins with an expected prefix.
- `--fail-under N` flag for `llm-canary run` — exits with code 1 if the pass rate drops below N percent. Also configurable via `fail_under:` in `.llm-canary.yml`. The GitHub Actions workflow now exposes this as a `workflow_dispatch` input.
- `--suite` flag for `llm-canary run` — run only a single named suite instead of all suites in the config.
- `--quiet` flag for `llm-canary run` — suppress per-test output (useful in CI when you only care about the exit code).
- `llm-canary history` command — prints a pass-rate trend table with an inline bar chart for a given provider/model combination.
- HTML report now includes a sparkline chart (inline SVG) showing the pass-rate trend across the last 10 runs.
- `detect_drift` and `run_canary` accept a `quiet` flag so callers can suppress output.

### Changed
- `generate_html_report` now accepts an optional `results_dir` argument to pull history for the sparkline without a separate call.
- Updated `pyproject.toml` classifier from Beta to Production/Stable.
- Ollama connection error message is now in English.
- JSON eval and assertion warnings are now in English.

---

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
