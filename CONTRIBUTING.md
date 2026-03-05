# Contributing

## Adding a test

The most useful contribution is a new test case. A good test has a deterministic answer that won't vary across reasonable model versions and is provider-agnostic — it should pass on GPT-4o, Claude, Gemini, and Llama without prompt tuning.

```yaml
# llm_canary/suites/universal-v1/01_basic_consistency.yml

- name: fibonacci-8th
  prompt: "What is the 8th number in the Fibonacci sequence (starting 1,1,2,3,...)? Reply with only the number."
  eval: exact
  expected: "21"
```

Open a PR with the test and a short note on why it matters.

## Adding a new suite

Create a folder under `llm_canary/suites/your-suite-name/`, add a `README.md` explaining what it tests and why, then add test files as `01_something.yml`, `02_something.yml`, etc. Reference it in `examples/.llm-canary.example.yml`.

## Running locally

```bash
git clone https://github.com/arjinexe/llm-canary
cd llm-canary
pip install -e ".[dev]"
cp examples/.llm-canary.example.yml .llm-canary.yml
export OPENAI_API_KEY=sk-...
llm-canary run
```

Unit tests don't need an API key:

```bash
pytest tests/ -v
```

## Code style

`black` + `ruff`, one feature or fix per PR.

## Reporting drift

If llm-canary catches a real model change in the wild, open an issue with the provider, model name, approximate date, and which tests started failing. Useful for building a record of when providers actually ship changes.
