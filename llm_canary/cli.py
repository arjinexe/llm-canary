import sys
import json
import argparse
from pathlib import Path

from llm_canary import __version__


INIT_TEMPLATE = """\
provider: openai          # openai | anthropic | google | mistral | cohere | groq | ollama | azure | bedrock
model: gpt-4o

suites:
  - universal-v1
  - json-reliability
  # - reasoning

# parallel: 5  # run tests concurrently (default: 1, sequential)

# test_files:  # load tests from CSV files
#   - tests/my-tests.csv

custom_tests:
  - name: my-first-canary
    prompt: "Reply with only the word PONG."
    eval: exact
    expected: "PONG"

  # template variables — expands into one test per var entry
  # - name: translation-{{lang}}
  #   prompt: "Translate 'hello' to {{lang}}. Reply with only the translation."
  #   eval: contains
  #   vars:
  #     - lang: French
  #       expected: bonjour
  #     - lang: Spanish
  #       expected: hola
  #     - lang: Turkish
  #       expected: merhaba

  # regex example
  # - name: email-check
  #   prompt: "Generate a valid email address."
  #   eval: regex
  #   expected: "^[\\w.-]+@[\\w.-]+\\.[a-z]{2,}$"

  # multi-assertion — all must pass
  # - name: structured-output
  #   prompt: "Return a JSON object with name and age fields."
  #   assert:
  #     - eval: json
  #       expected:
  #         name: ""
  #         age: 0
  #     - eval: contains
  #       expected: "age"

  # llm_judge example
  # - name: tone-check
  #   prompt: "Respond to an angry customer complaining about a delayed order."
  #   eval: llm_judge
  #   judge_prompt: "Is this response polite and professional? Reply with only yes or no.\\n\\nResponse: {response}"

# judge:       # model used for llm_judge evaluations
#   provider: openai
#   model: gpt-4o-mini

# providers:   # used by `llm-canary compare`
#   - provider: openai
#     model: gpt-4o
#   - provider: anthropic
#     model: claude-3-5-sonnet-20241022
#   - provider: google
#     model: gemini-1.5-pro

# alerts:
#   slack_webhook: https://hooks.slack.com/services/YOUR/WEBHOOK/URL
#   always: false   # true = alert on every run, false (default) = only on drift
"""


def cmd_init(args):
    config_path = Path(".llm-canary.yml")
    if config_path.exists() and not args.force:
        print(".llm-canary.yml already exists. Use --force to overwrite.")
        return
    config_path.write_text(INIT_TEMPLATE)
    print("created .llm-canary.yml")
    print("\nnext:")
    print("  export OPENAI_API_KEY=sk-...")
    print("  llm-canary run")


def cmd_run(args):
    from llm_canary.core import run_canary
    try:
        summary = run_canary(
            config_path=args.config,
            output_dir=args.output_dir,
            provider_override=args.provider or None,
            model_override=args.model or None,
            csv_file=args.tests or None,
        )
        if args.json:
            print(json.dumps(summary, indent=2))
        if summary["failed"] > 0:
            sys.exit(1)
    except FileNotFoundError as e:
        print(f"error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"error: {e}")
        sys.exit(2)


def cmd_report(args):
    from llm_canary.report import generate_html_report
    results_dir = Path(args.results_dir)
    files = sorted(results_dir.glob("*.json"))
    if not files:
        print(f"no result files in {results_dir}")
        sys.exit(1)

    if args.provider or args.model:
        provider = args.provider.lower() if args.provider else None
        model = args.model.replace("/", "-").replace(":", "-") if args.model else None
        filtered = []
        for f in files:
            stem = f.stem  # e.g. 20250301_openai_gpt-4o
            parts = stem.split("_", 2)  # [date, provider, model]
            if len(parts) < 3:
                continue
            _, file_provider, file_model = parts
            if provider and file_provider != provider:
                continue
            if model and file_model != model:
                continue
            filtered.append(f)
        if not filtered:
            print(f"no result files matched provider={args.provider!r} model={args.model!r}")
            sys.exit(1)
        files = filtered

    out_path = Path(args.output)
    generate_html_report(files[-1], out_path)
    print(f"report saved to {out_path}")


def cmd_compare(args):
    from llm_canary.core import run_compare
    try:
        run_compare(config_path=args.config, output_dir=args.output_dir)
    except FileNotFoundError as e:
        print(f"error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"error: {e}")
        sys.exit(2)


def main():
    parser = argparse.ArgumentParser(prog="llm-canary", description="LLM behavioral drift detector")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="create .llm-canary.yml")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("run", help="run canary tests")
    p.add_argument("--config", default=".llm-canary.yml")
    p.add_argument("--output-dir", default=".canary-results")
    p.add_argument("--provider", default="")
    p.add_argument("--model", default="")
    p.add_argument("--tests", default="", help="path to a CSV test file")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("compare", help="run suite against multiple providers and compare")
    p.add_argument("--config", default=".llm-canary.yml")
    p.add_argument("--output-dir", default=".canary-results")
    p.set_defaults(func=cmd_compare)

    p = sub.add_parser("report", help="generate HTML report")
    p.add_argument("--results-dir", default=".canary-results")
    p.add_argument("--output", default="canary-report.html")
    p.add_argument("--provider", default="", help="filter by provider (e.g. openai)")
    p.add_argument("--model", default="", help="filter by model (e.g. gpt-4o)")
    p.set_defaults(func=cmd_report)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
