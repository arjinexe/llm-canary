import os
import re
import json
import time
import hashlib
import datetime
from pathlib import Path
from datetime import timezone

import yaml
import requests

from llm_canary import __version__


def _post_with_retry(url, *, headers, payload, timeout=60, max_retries=3):
    """POST with exponential backoff on 429/5xx. Other errors raise immediately."""
    for attempt in range(1, max_retries + 1):
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
        if resp.status_code == 429 or resp.status_code >= 500:
            if attempt == max_retries:
                resp.raise_for_status()
            wait = 2.0 * (2 ** (attempt - 1))
            print(f"\n  HTTP {resp.status_code} — retry in {wait:.0f}s ({attempt}/{max_retries})", flush=True)
            time.sleep(wait)
        else:
            resp.raise_for_status()
            return resp
    resp.raise_for_status()
    return resp


def call_openai(model, prompt, system=""):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set.")
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    resp = _post_with_retry(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        payload={"model": model, "messages": messages, "temperature": 0},
    )
    return resp.json()["choices"][0]["message"]["content"].strip()


def call_anthropic(model, prompt, system=""):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set.")
    payload = {
        "model": model,
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        payload["system"] = system
    resp = _post_with_retry(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        payload=payload,
    )
    return resp.json()["content"][0]["text"].strip()


def call_google(model, prompt, system=""):
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable not set.")
    full_prompt = f"{system}\n\n{prompt}" if system else prompt
    resp = _post_with_retry(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
        headers={},
        payload={"contents": [{"parts": [{"text": full_prompt}]}]},
    )
    data = resp.json()
    candidates = data.get("candidates", [])
    if not candidates:
        raise ValueError(f"Google API returned no candidates: {data}")
    candidate = candidates[0]
    finish_reason = candidate.get("finishReason", "STOP")
    if finish_reason not in ("STOP", "MAX_TOKENS"):
        raise ValueError(f"Google API stopped early: finishReason={finish_reason}")
    if "content" not in candidate:
        raise ValueError(f"Google API candidate missing content: finishReason={finish_reason}")
    return candidate["content"]["parts"][0]["text"].strip()


def call_mistral(model, prompt, system=""):
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        raise ValueError("MISTRAL_API_KEY environment variable not set.")
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    resp = _post_with_retry(
        "https://api.mistral.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        payload={"model": model, "messages": messages, "temperature": 0},
    )
    return resp.json()["choices"][0]["message"]["content"].strip()


def call_cohere(model, prompt, system=""):
    api_key = os.environ.get("COHERE_API_KEY")
    if not api_key:
        raise ValueError("COHERE_API_KEY environment variable not set.")
    payload = {"model": model, "message": prompt, "temperature": 0}
    if system:
        payload["preamble"] = system
    resp = _post_with_retry(
        "https://api.cohere.com/v1/chat",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        payload=payload,
    )
    return resp.json()["text"].strip()


def call_groq(model, prompt, system=""):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable not set.")
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    resp = _post_with_retry(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        payload={"model": model, "messages": messages, "temperature": 0},
    )
    return resp.json()["choices"][0]["message"]["content"].strip()


def call_ollama(model, prompt, system=""):
    """Local Ollama instance. Set OLLAMA_HOST to override default http://localhost:11434."""
    base_url = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    try:
        resp = requests.post(
            f"{base_url}/api/chat",
            json={"model": model, "messages": messages, "stream": False,
                  "options": {"temperature": 0}},
            timeout=120,
        )
        resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        raise ConnectionError(
            f"Ollama connection error ({base_url}). "
            "Is 'ollama serve' running? Is OLLAMA_HOST correct?"
        )
    return resp.json()["message"]["content"].strip()


def call_azure(model, prompt, system=""):
    """Azure OpenAI. Requires AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_VERSION."""
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-01")
    if not api_key:
        raise ValueError("AZURE_OPENAI_API_KEY environment variable not set.")
    if not endpoint:
        raise ValueError("AZURE_OPENAI_ENDPOINT environment variable not set.")
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    url = f"{endpoint}/openai/deployments/{model}/chat/completions?api-version={api_version}"
    resp = _post_with_retry(
        url,
        headers={"api-key": api_key, "Content-Type": "application/json"},
        payload={"messages": messages, "temperature": 0},
    )
    return resp.json()["choices"][0]["message"]["content"].strip()


def call_bedrock(model, prompt, system=""):
    """AWS Bedrock. Requires boto3 and AWS credentials (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION)."""
    try:
        import boto3
        import json as _json
    except ImportError:
        raise ImportError("boto3 is required: pip install boto3")

    region = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
    client = boto3.client("bedrock-runtime", region_name=region)

    if model.startswith("anthropic."):
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            body["system"] = system
    elif model.startswith("amazon.titan"):
        body = {
            "inputText": f"{system}\n\n{prompt}" if system else prompt,
            "textGenerationConfig": {"temperature": 0, "maxTokenCount": 1024},
        }
    elif model.startswith("meta.llama"):
        body = {"prompt": f"[INST] {prompt} [/INST]", "temperature": 0, "max_gen_len": 1024}
    elif model.startswith("mistral."):
        body = {"prompt": f"<s>[INST] {prompt} [/INST]", "temperature": 0, "max_tokens": 1024}
    else:
        body = {"messages": [{"role": "user", "content": prompt}], "temperature": 0, "max_tokens": 1024}

    response = client.invoke_model(
        modelId=model,
        body=_json.dumps(body),
        contentType="application/json",
        accept="application/json",
    )
    result = _json.loads(response["body"].read())

    if model.startswith("anthropic."):
        return result["content"][0]["text"].strip()
    elif model.startswith("amazon.titan"):
        return result["results"][0]["outputText"].strip()
    elif model.startswith("meta.llama"):
        return result["generation"].strip()
    elif model.startswith("mistral."):
        return result["outputs"][0]["text"].strip()
    else:
        return str(result)


PROVIDERS = {
    "openai": call_openai,
    "anthropic": call_anthropic,
    "google": call_google,
    "mistral": call_mistral,
    "cohere": call_cohere,
    "groq": call_groq,
    "ollama": call_ollama,
    "azure": call_azure,
    "bedrock": call_bedrock,
}


# ---------------------------------------------------------------------------
# Evaluators
# ---------------------------------------------------------------------------

def evaluate_exact(response, expected):
    match = response.strip().lower() == expected.strip().lower()
    return match, 1.0 if match else 0.0


def evaluate_contains(response, expected):
    match = expected.lower() in response.lower()
    return match, 1.0 if match else 0.0


def evaluate_not_contains(response, expected):
    match = expected.lower() not in response.lower()
    return match, 1.0 if match else 0.0


def evaluate_startswith(response, expected):
    match = response.strip().lower().startswith(expected.strip().lower())
    return match, 1.0 if match else 0.0


def evaluate_regex(response, expected):
    try:
        match = bool(re.search(expected, response, re.IGNORECASE | re.DOTALL))
        return match, 1.0 if match else 0.0
    except re.error as e:
        raise ValueError(f"invalid regex pattern: {e}")


def evaluate_json(response, expected):
    try:
        clean = re.sub(r"^```(?:json)?\s*", "", response.strip(), flags=re.IGNORECASE)
        clean = re.sub(r"\s*```$", "", clean.strip()).strip()
        parsed = json.loads(clean)
        if not expected:
            return True, 1.0
        score = sum(1.0 for k in expected if k in parsed) / len(expected)
        return score >= 1.0, score
    except Exception:
        return False, 0.0


_sentence_transformer = None


def evaluate_semantic(response, expected, threshold=0.85):
    global _sentence_transformer
    try:
        from sentence_transformers import SentenceTransformer, util as st_util
        if _sentence_transformer is None:
            _sentence_transformer = SentenceTransformer("all-MiniLM-L6-v2")
        e1 = _sentence_transformer.encode(response, convert_to_tensor=True)
        e2 = _sentence_transformer.encode(expected, convert_to_tensor=True)
        score = float(st_util.cos_sim(e1, e2)[0][0])
        return score >= threshold, score
    except ImportError:
        s1 = set(response.lower().split())
        s2 = set(expected.lower().split())
        if not s1 and not s2:
            return True, 1.0
        if not s1 or not s2:
            return False, 0.0
        score = len(s1 & s2) / len(s1 | s2)
        return score >= threshold, score


def evaluate_llm_judge(response, judge_prompt_template, judge_fn, threshold=0.5):
    """
    Calls a judge model to evaluate the response.
    judge_prompt_template should contain a {response} placeholder.
    The judge must reply with a score between 0.0–1.0, or yes/no.
    """
    prompt = judge_prompt_template.replace("{response}", response)
    try:
        verdict = judge_fn(prompt, "").strip().lower()
        if verdict in ("yes", "true", "pass", "1"):
            return True, 1.0
        if verdict in ("no", "false", "fail", "0"):
            return False, 0.0
        score = float(verdict)
        score = max(0.0, min(1.0, score))
        return score >= threshold, score
    except (ValueError, TypeError):
        m = re.search(r"\b(yes|no|true|false|pass|fail)\b", verdict, re.IGNORECASE)
        if m:
            word = m.group(1).lower()
            passed = word in ("yes", "true", "pass")
            return passed, 1.0 if passed else 0.0
        m = re.search(r"\b([01](?:\.\d+)?)\b", verdict)
        if m:
            score = float(m.group(1))
            return score >= threshold, score
        raise ValueError(f"judge returned unparseable verdict: {verdict!r}")


EVALUATORS = {
    "exact": evaluate_exact,
    "contains": evaluate_contains,
    "not_contains": evaluate_not_contains,
    "startswith": evaluate_startswith,
    "regex": evaluate_regex,
    "json": evaluate_json,
    "semantic": evaluate_semantic,
    "llm_judge": evaluate_llm_judge,
}


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

def send_alerts(config, summary, drift_info):
    alerts = config.get("alerts", {})
    if not alerts:
        return

    pass_rate = summary.get("pass_rate", 0)
    model = summary.get("model", "unknown")
    provider = summary.get("provider", "unknown")
    passed = summary.get("passed", 0)
    total = summary.get("total", 0)
    run_at = summary.get("run_at", "")
    delta = drift_info.get("delta", 0)
    newly_failed = drift_info.get("newly_failed", [])

    emoji = "✅" if pass_rate == 100 else ("⚠️" if pass_rate >= 70 else "🚨")
    title = (
        f"🚨 llm-canary: drift on {provider}/{model}"
        if delta < -1
        else f"{emoji} llm-canary: {provider}/{model} — {pass_rate}%"
    )
    lines = [
        f"*Pass rate:* {pass_rate}% ({passed}/{total})",
        f"*Model:* `{provider}/{model}`",
        f"*Run at:* {run_at[:16].replace('T', ' ')} UTC",
    ]
    if newly_failed:
        lines.append(f"*Newly failing:* {', '.join(f'`{t}`' for t in newly_failed)}")
    if delta:
        lines.append(f"*Change:* {delta:+.1f}%")

    webhook = alerts.get("slack_webhook", "")
    if webhook:
        payload = {
            "text": title,
            "blocks": [
                {"type": "header", "text": {"type": "plain_text", "text": title}},
                {"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}},
            ],
        }
        try:
            r = requests.post(webhook, json=payload, timeout=10)
            r.raise_for_status()
            print("   Slack alert sent.")
        except Exception as exc:
            print(f"   Slack alert failed: {exc}")


# ---------------------------------------------------------------------------
# Suite and test loading
# ---------------------------------------------------------------------------

def load_suite(suite_path):
    tests = []
    for yml_file in sorted(suite_path.glob("*.yml")):
        with open(yml_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if isinstance(data, list):
            tests.extend(data)
        elif isinstance(data, dict):
            tests.append(data)
    return tests


def load_csv_tests(csv_path):
    """Load tests from a CSV file.

    Required columns: name, prompt, eval, expected
    Optional columns: system, threshold, judge_prompt
    """
    import csv
    tests = []
    with open(csv_path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, 1):
            if not row.get("prompt", "").strip():
                continue
            test = {
                "name": row.get("name", f"csv-{i}").strip(),
                "prompt": row["prompt"].strip(),
                "eval": row.get("eval", "contains").strip(),
                "expected": row.get("expected", "").strip(),
            }
            if row.get("system", "").strip():
                test["system"] = row["system"].strip()
            if row.get("threshold", "").strip():
                try:
                    test["threshold"] = float(row["threshold"].strip())
                except ValueError:
                    pass
            if row.get("judge_prompt", "").strip():
                test["judge_prompt"] = row["judge_prompt"].strip()
            tests.append(test)
    return tests


def _expand_vars(test):
    """Expand a test with a 'vars' list into multiple concrete tests.

    Each entry in vars is a dict of variable name → value. Variables are
    substituted using {{var_name}} syntax in name, prompt, system, expected,
    judge_prompt, and inside assert list items.
    """
    var_list = test.get("vars")
    if not var_list:
        return [test]

    def substitute(value, var_dict):
        if not isinstance(value, str):
            return value
        for k, v in var_dict.items():
            value = value.replace("{{" + k + "}}", str(v))
        return value

    expanded = []
    top_fields = ("name", "prompt", "system", "expected", "judge_prompt")
    for var_dict in var_list:
        t = {k: v for k, v in test.items() if k != "vars"}
        for field in top_fields:
            if field in t and isinstance(t[field], str):
                t[field] = substitute(t[field], var_dict)
        if "expected" in var_dict and "vars" not in str(var_dict.get("expected", "")):
            t["expected"] = str(var_dict["expected"])
        if "assert" in t and isinstance(t["assert"], list):
            new_assertions = []
            for assertion in t["assert"]:
                a = dict(assertion)
                for field in ("expected", "judge_prompt"):
                    if field in a and isinstance(a[field], str):
                        a[field] = substitute(a[field], var_dict)
                new_assertions.append(a)
            t["assert"] = new_assertions
        expanded.append(t)
    return expanded


def _run_assertions(response, assertions, judge_fn, test_name):
    """Run a list of assertion dicts against a single response.

    Returns (passed, score, eval_type_str) where score is the mean across
    all assertions and passed is True only when every assertion passes.
    """
    if not assertions:
        return True, 1.0, "multi"

    scores = []
    all_passed = True
    eval_types = []

    for assertion in assertions:
        eval_type = assertion.get("eval", "contains")
        expected = assertion.get("expected", "")
        threshold = assertion.get("threshold", 0.85)
        eval_types.append(eval_type)

        if eval_type == "semantic":
            p, s = evaluate_semantic(response, str(expected), threshold)
        elif eval_type == "json":
            if expected and not isinstance(expected, dict):
                print(f"  ⚠️  '{test_name}': json assertion expected must be a dict")
            p, s = evaluate_json(response, expected if isinstance(expected, dict) else {})
        elif eval_type == "regex":
            p, s = evaluate_regex(response, str(expected))
        elif eval_type == "not_contains":
            p, s = evaluate_not_contains(response, str(expected))
        elif eval_type == "startswith":
            p, s = evaluate_startswith(response, str(expected))
        elif eval_type == "llm_judge":
            if judge_fn is None:
                raise ValueError("llm_judge assertion requires 'judge' config in .llm-canary.yml")
            judge_prompt = assertion.get("judge_prompt",
                "Is this response correct? Reply yes or no.\n\nResponse: {response}")
            p, s = evaluate_llm_judge(response, judge_prompt, judge_fn, threshold)
        else:
            evaluator = EVALUATORS.get(eval_type, evaluate_contains)
            p, s = evaluator(response, str(expected))

        scores.append(s)
        if not p:
            all_passed = False

    mean_score = sum(scores) / len(scores)
    label = "+".join(dict.fromkeys(eval_types))
    return all_passed, mean_score, label


def run_test(test, provider_fn, model, judge_fn=None):
    name = test.get("name", hashlib.md5(str(test).encode()).hexdigest()[:8])
    assertions = test.get("assert")
    eval_type = test.get("eval", "contains") if not assertions else "multi"
    start = time.time()
    try:
        if "prompt" not in test:
            raise ValueError(f"test '{name}' is missing 'prompt'")
        prompt = test["prompt"]
        system = test.get("system", "")
        expected = test.get("expected", "")
        threshold = test.get("threshold", 0.85)

        response = provider_fn(model, prompt, system)
        latency = round(time.time() - start, 3)

        if assertions:
            passed, score, eval_type = _run_assertions(response, assertions, judge_fn, name)
        elif eval_type == "json" and expected and not isinstance(expected, dict):
            print(f"  ⚠️  '{name}': json eval expected must be a dict, got {type(expected).__name__}")
            passed, score = evaluate_json(response, {})
        elif eval_type == "semantic":
            passed, score = evaluate_semantic(response, expected, threshold)
        elif eval_type == "json":
            passed, score = evaluate_json(response, expected if isinstance(expected, dict) else {})
        elif eval_type == "regex":
            passed, score = evaluate_regex(response, str(expected))
        elif eval_type == "not_contains":
            passed, score = evaluate_not_contains(response, str(expected))
        elif eval_type == "startswith":
            passed, score = evaluate_startswith(response, str(expected))
        elif eval_type == "llm_judge":
            if judge_fn is None:
                raise ValueError("llm_judge eval requires 'judge' config in .llm-canary.yml")
            judge_prompt = test.get("judge_prompt",
                "Is this response correct? Reply yes or no.\n\nResponse: {response}")
            passed, score = evaluate_llm_judge(response, judge_prompt, judge_fn, threshold)
        else:
            evaluator = EVALUATORS.get(eval_type, evaluate_contains)
            passed, score = evaluator(response, str(expected))

        return {
            "name": name,
            "passed": passed,
            "score": round(score, 4),
            "latency_s": latency,
            "response_preview": response[:200],
            "eval_type": eval_type,
            "error": None,
        }
    except Exception as e:
        return {
            "name": name,
            "passed": False,
            "score": 0.0,
            "latency_s": round(time.time() - start, 3),
            "response_preview": "",
            "eval_type": eval_type,
            "error": str(e),
        }


def _run_tests_parallel(all_tests, provider_fn, model, judge_fn, workers):
    from concurrent.futures import ThreadPoolExecutor, as_completed

    total = len(all_tests)
    lock = __import__("threading").Lock()
    completed = [0]

    def run_one(item):
        i, test = item
        result = run_test(test, provider_fn, model, judge_fn)
        with lock:
            completed[0] += 1
            name = test.get("name", f"test-{i}")
            suite = test.get("_suite", "unknown")
            idx = f"{completed[0]:02d}/{total:02d}"
            if result["passed"]:
                print(f"  [{idx}] {suite}/{name} ... ✅  ({result['score']:.2f}, {result['latency_s']}s)")
            else:
                err = f" ← {result['error']}" if result["error"] else f" ← score: {result['score']:.2f}"
                print(f"  [{idx}] {suite}/{name} ... ❌{err}")
        return i, result

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(run_one, (i, t)): i for i, t in enumerate(all_tests)}
        ordered = {}
        for f in as_completed(futures):
            i, result = f.result()
            ordered[i] = result

    return [ordered[i] for i in range(len(all_tests))]


def _load_all_tests(config, csv_file=None, suite_filter=None):
    builtin_suites = Path(__file__).parent / "suites"
    custom_suites_dir = config.get("suites_dir", "")
    extra_suites = Path(custom_suites_dir) if custom_suites_dir else None

    requested_suites = config.get("suites", ["universal-v1"])
    if suite_filter:
        requested_suites = [s for s in requested_suites if s == suite_filter]

    all_tests = []
    for suite_name in requested_suites:
        suite_path = None
        if extra_suites and (extra_suites / suite_name).exists():
            suite_path = extra_suites / suite_name
        elif (builtin_suites / suite_name).exists():
            suite_path = builtin_suites / suite_name

        if suite_path:
            tests = load_suite(suite_path)
            for t in tests:
                t["_suite"] = suite_name
            all_tests.extend(tests)
        else:
            print(f"  suite not found: {suite_name}")

    if not suite_filter:
        for custom in config.get("custom_tests", []):
            custom["_suite"] = "custom"
            all_tests.append(custom)

    csv_paths = []
    if csv_file:
        csv_paths.append(csv_file)
    for p in config.get("test_files", []):
        csv_paths.append(p)
    for cp in csv_paths:
        cp = Path(cp)
        if not cp.exists():
            print(f"  test file not found: {cp}")
            continue
        csv_tests = load_csv_tests(cp)
        for t in csv_tests:
            t["_suite"] = cp.stem
        print(f"  loaded {len(csv_tests)} tests from {cp.name}")
        all_tests.append(csv_tests)

    flat = []
    for t in all_tests:
        if isinstance(t, list):
            for item in t:
                flat.extend(_expand_vars(item))
        else:
            flat.extend(_expand_vars(t))

    return flat


def run_canary(
    config_path=".llm-canary.yml",
    output_dir=".canary-results",
    provider_override=None,
    model_override=None,
    csv_file=None,
    suite_filter=None,
    fail_under=None,
    quiet=False,
):
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"{config_path} not found — run `llm-canary init` first")

    with open(config_file, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    provider_name = (provider_override or config.get("provider", "openai")).lower()
    model = model_override or config.get("model", "gpt-4o")

    provider_fn = PROVIDERS.get(provider_name)
    if not provider_fn:
        raise ValueError(f"unknown provider '{provider_name}', choose from: {list(PROVIDERS)}")

    judge_fn = None
    judge_cfg = config.get("judge", {})
    if judge_cfg:
        judge_provider = PROVIDERS.get(judge_cfg.get("provider", provider_name))
        judge_model = judge_cfg.get("model", model)
        if judge_provider:
            judge_fn = lambda prompt, system="": judge_provider(judge_model, prompt, system)

    all_tests = _load_all_tests(config, csv_file=csv_file, suite_filter=suite_filter)

    if not all_tests:
        raise ValueError("no tests found — add suites or custom_tests to .llm-canary.yml")

    workers = config.get("parallel", 1)
    parallel = isinstance(workers, int) and workers > 1

    if not quiet:
        print(f"\nllm-canary v{__version__}")
        print(f"  provider : {provider_name} / {model}")
        print(f"  tests    : {len(all_tests)}")
        if suite_filter:
            print(f"  suite    : {suite_filter}")
        if parallel:
            print(f"  workers  : {workers}")
        print(f"  time     : {datetime.datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n")

    if parallel:
        results_list = _run_tests_parallel(all_tests, provider_fn, model, judge_fn, workers)
        results = [{**r, "suite": all_tests[i].get("_suite", "unknown")} for i, r in enumerate(results_list)]
    else:
        results = []
        for i, test in enumerate(all_tests, 1):
            name = test.get("name", f"test-{i}")
            suite = test.get("_suite", "unknown")
            if not quiet:
                print(f"  [{i:02d}/{len(all_tests):02d}] {suite}/{name} ...", end=" ", flush=True)
            result = run_test(test, provider_fn, model, judge_fn)
            results.append({**result, "suite": suite})
            if not quiet:
                if result["passed"]:
                    print(f"✅  ({result['score']:.2f}, {result['latency_s']}s)")
                else:
                    err = f" ← {result['error']}" if result["error"] else f" ← score: {result['score']:.2f}"
                    print(f"❌{err}")

    passed = sum(1 for r in results if r["passed"])
    failed = len(results) - passed
    total = len(results)
    pass_rate = round(passed / total * 100, 1) if total else 0.0

    summary = {
        "run_at": datetime.datetime.now(timezone.utc).isoformat(),
        "provider": provider_name,
        "model": model,
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": pass_rate,
        "results": results,
    }

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_model = model.replace("/", "-").replace(":", "-")
    result_file = out_dir / f"{ts}_{provider_name}_{safe_model}.json"
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    status = "✅" if pass_rate == 100 else ("⚠️" if pass_rate >= 70 else "🚨")
    if not quiet:
        print(f"\n{status}  {pass_rate}% ({passed}/{total})")

    drift_info = detect_drift(out_dir, summary, provider_name, model, quiet=quiet)

    if drift_info.get("delta", 0) < -1 or config.get("alerts", {}).get("always", False):
        send_alerts(config, summary, drift_info)

    # --fail-under threshold
    effective_threshold = fail_under if fail_under is not None else config.get("fail_under")
    if effective_threshold is not None:
        try:
            threshold_val = float(effective_threshold)
            if pass_rate < threshold_val:
                import sys
                print(f"\n  fail-under threshold not met: {pass_rate}% < {threshold_val}%")
                sys.exit(1)
        except (ValueError, TypeError):
            pass

    return summary


def run_compare(config_path=".llm-canary.yml", output_dir=".canary-results"):
    """Run the same suite against multiple providers/models and print a comparison table."""
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"{config_path} not found — run `llm-canary init` first")

    with open(config_file, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    targets = config.get("providers", [])
    if not targets:
        raise ValueError(
            "no 'providers' list in .llm-canary.yml — add a list of {provider, model} entries"
        )

    all_tests = _load_all_tests(config)
    if not all_tests:
        raise ValueError("no tests found — add suites or custom_tests to .llm-canary.yml")

    workers = config.get("parallel", 1)
    parallel = isinstance(workers, int) and workers > 1

    summaries = []
    for target in targets:
        p_name = target.get("provider", "openai").lower()
        m_name = target.get("model", "gpt-4o")

        provider_fn = PROVIDERS.get(p_name)
        if not provider_fn:
            print(f"  skipping unknown provider '{p_name}'")
            continue

        judge_fn = None
        judge_cfg = config.get("judge", {})
        if judge_cfg:
            j_provider = PROVIDERS.get(judge_cfg.get("provider", p_name))
            j_model = judge_cfg.get("model", m_name)
            if j_provider:
                judge_fn = lambda prompt, system="", _jp=j_provider, _jm=j_model: _jp(_jm, prompt, system)

        print(f"\n{'─' * 52}")
        print(f"  {p_name} / {m_name}")
        print(f"{'─' * 52}")

        if parallel:
            results_list = _run_tests_parallel(all_tests, provider_fn, m_name, judge_fn, workers)
            results = [{**r, "suite": all_tests[i].get("_suite", "unknown")} for i, r in enumerate(results_list)]
        else:
            results = []
            for i, test in enumerate(all_tests, 1):
                name = test.get("name", f"test-{i}")
                suite = test.get("_suite", "unknown")
                print(f"  [{i:02d}/{len(all_tests):02d}] {suite}/{name} ...", end=" ", flush=True)
                result = run_test(test, provider_fn, m_name, judge_fn)
                results.append({**result, "suite": suite})
                if result["passed"]:
                    print(f"✅  ({result['score']:.2f}, {result['latency_s']}s)")
                else:
                    err = f" ← {result['error']}" if result["error"] else f" ← score: {result['score']:.2f}"
                    print(f"❌{err}")

        passed = sum(1 for r in results if r["passed"])
        failed = len(results) - passed
        total = len(results)
        pass_rate = round(passed / total * 100, 1) if total else 0.0

        summary = {
            "run_at": datetime.datetime.now(timezone.utc).isoformat(),
            "provider": p_name,
            "model": m_name,
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": pass_rate,
            "results": results,
        }

        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_model = m_name.replace("/", "-").replace(":", "-")
        result_file = out_dir / f"{ts}_{p_name}_{safe_model}.json"
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        summaries.append(summary)

    print(f"\n{'═' * 52}")
    print("  COMPARISON")
    print(f"{'═' * 52}")
    print(f"  {'provider/model':<36} {'pass rate':>10}")
    print(f"  {'─' * 36} {'─' * 10}")

    summaries_sorted = sorted(summaries, key=lambda s: s["pass_rate"], reverse=True)
    for s in summaries_sorted:
        label = f"{s['provider']}/{s['model']}"[:36]
        rate = s["pass_rate"]
        icon = "✅" if rate == 100 else ("⚠️ " if rate >= 70 else "🚨")
        print(f"  {label:<36} {icon} {rate:>5.1f}%  ({s['passed']}/{s['total']})")

    print()
    return summaries


def show_history(results_dir, provider, model, limit=10):
    """Print a pass-rate trend table for a given provider/model."""
    safe_model = model.replace("/", "-").replace(":", "-")
    files = sorted(results_dir.glob(f"*_{provider}_{safe_model}.json"))

    if not files:
        print(f"  no history for {provider}/{model}")
        return []

    records = []
    for f in files[-limit:]:
        try:
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            records.append({
                "date": data.get("run_at", "")[:10],
                "pass_rate": data.get("pass_rate", 0),
                "passed": data.get("passed", 0),
                "total": data.get("total", 0),
            })
        except (json.JSONDecodeError, OSError):
            continue

    if not records:
        return []

    print(f"\n  history: {provider}/{model}  (last {len(records)} runs)\n")
    print(f"  {'date':<12} {'pass rate':>10}   chart")
    print(f"  {'─' * 12} {'─' * 10}   {'─' * 20}")

    for rec in records:
        rate = rec["pass_rate"]
        bar_len = int(rate / 5)
        bar = "█" * bar_len
        icon = "✅" if rate == 100 else ("⚠️ " if rate >= 70 else "🚨")
        print(f"  {rec['date']:<12} {icon} {rate:>5.1f}%   {bar}")

    print()
    return records


def detect_drift(results_dir, current, provider, model, quiet=False):
    safe_model = model.replace("/", "-").replace(":", "-")
    history = sorted(results_dir.glob(f"*_{provider}_{safe_model}.json"))[:-1]

    if not history:
        if not quiet:
            print("  (first run — baseline saved)")
        return {"delta": 0, "newly_failed": []}

    try:
        with open(history[-1], encoding="utf-8") as f:
            previous = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        if not quiet:
            print(f"  couldn't read previous result ({e}), skipping drift check")
        return {"delta": 0, "newly_failed": []}

    delta = current["pass_rate"] - previous["pass_rate"]
    prev_date = previous["run_at"][:10]
    prev_pass = {r["name"] for r in previous["results"] if r["passed"]}
    curr_fail = {r["name"] for r in current["results"] if not r["passed"]}
    newly_failed = sorted(prev_pass & curr_fail)

    if not quiet:
        if abs(delta) < 1.0:
            print(f"  no significant drift vs {prev_date}")
        elif delta < 0:
            print(f"\n🚨 drift detected: -{abs(delta):.1f}% since {prev_date}")
            print(f"   {previous['pass_rate']}% → {current['pass_rate']}%")
            if newly_failed:
                print(f"   newly failing: {', '.join(newly_failed)}")
        else:
            print(f"  +{delta:.1f}% vs {prev_date}")

    return {"delta": delta, "newly_failed": newly_failed, "prev_date": prev_date}
