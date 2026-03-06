import json
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from llm_canary.core import (
    evaluate_exact,
    evaluate_contains,
    evaluate_not_contains,
    evaluate_startswith,
    evaluate_json,
    evaluate_semantic,
    run_test,
    load_suite,
    detect_drift,
    send_alerts,
    show_history,
)


class TestEvaluateExact:
    def test_match(self):
        passed, score = evaluate_exact("PONG", "PONG")
        assert passed is True and score == 1.0

    def test_case_insensitive(self):
        passed, _ = evaluate_exact("pong", "PONG")
        assert passed is True

    def test_no_match(self):
        passed, score = evaluate_exact("something else", "PONG")
        assert passed is False and score == 0.0

    def test_strips_whitespace(self):
        passed, _ = evaluate_exact("  Paris  ", "Paris")
        assert passed is True

    def test_numbers(self):
        passed, _ = evaluate_exact("25", "25")
        assert passed is True


class TestEvaluateContains:
    def test_match(self):
        passed, score = evaluate_contains("The capital is Paris, France.", "paris")
        assert passed is True and score == 1.0

    def test_no_match(self):
        passed, score = evaluate_contains("Berlin is the capital.", "paris")
        assert passed is False and score == 0.0

    def test_case_insensitive(self):
        passed, _ = evaluate_contains("HELLO WORLD", "hello")
        assert passed is True


class TestEvaluateNotContains:
    def test_absent(self):
        passed, score = evaluate_not_contains("The sky is blue.", "apology")
        assert passed is True and score == 1.0

    def test_present_fails(self):
        passed, score = evaluate_not_contains("I'm sorry, I cannot help with that.", "sorry")
        assert passed is False and score == 0.0

    def test_case_insensitive(self):
        passed, _ = evaluate_not_contains("SORRY about that", "sorry")
        assert passed is False


class TestEvaluateStartswith:
    def test_match(self):
        passed, score = evaluate_startswith("Yes, that is correct.", "yes")
        assert passed is True and score == 1.0

    def test_no_match(self):
        passed, score = evaluate_startswith("No, that is incorrect.", "yes")
        assert passed is False and score == 0.0

    def test_strips_whitespace(self):
        passed, _ = evaluate_startswith("  Yes indeed", "yes")
        assert passed is True

    def test_case_insensitive(self):
        passed, _ = evaluate_startswith("YES absolutely", "yes")
        assert passed is True


class TestEvaluateJson:
    def test_plain_json(self):
        passed, score = evaluate_json(
            '{"name": "Alice", "age": 30, "city": "NYC"}',
            {"name": "", "age": 0, "city": ""},
        )
        assert passed is True and score == 1.0

    def test_fenced_json(self):
        passed, score = evaluate_json('```json\n{"name": "Bob", "age": 25}\n```', {"name": "", "age": 0})
        assert passed is True and score == 1.0

    def test_fence_no_lang(self):
        passed, _ = evaluate_json('```\n{"key": "value"}\n```', {"key": ""})
        assert passed is True

    def test_partial_keys(self):
        passed, score = evaluate_json('{"name": "Carol"}', {"name": "", "age": 0})
        assert passed is False and score == pytest.approx(0.5)

    def test_invalid_json(self):
        passed, score = evaluate_json("not json at all", {"key": ""})
        assert passed is False and score == 0.0

    def test_no_expected_keys(self):
        passed, score = evaluate_json('{"anything": true}', {})
        assert passed is True and score == 1.0

    def test_json_key_with_json_word(self):
        # regression: old strip("```json") ate j,s,o,n chars from values
        passed, _ = evaluate_json('{"json_format": "raw value"}', {"json_format": ""})
        assert passed is True


class TestEvaluateSemantic:
    def test_identical(self):
        passed, score = evaluate_semantic("hello world", "hello world", threshold=0.9)
        assert passed is True and score == pytest.approx(1.0)

    def test_partial_overlap(self):
        _, score = evaluate_semantic("vast deep ocean", "vast blue ocean", threshold=0.1)
        assert score > 0.0

    def test_no_overlap(self):
        passed, _ = evaluate_semantic("xyz abc", "vast deep blue", threshold=0.5)
        assert passed is False

    def test_empty_response(self):
        passed, _ = evaluate_semantic("", "expected answer", threshold=0.1)
        assert passed is False

    def test_both_empty(self):
        passed, score = evaluate_semantic("", "", threshold=0.5)
        assert passed is True and score == 1.0


def _pong(model, prompt, system):
    return "PONG"


class TestRunTest:
    def test_pass(self):
        r = run_test({"name": "t", "prompt": "x", "eval": "exact", "expected": "PONG"}, _pong, "m")
        assert r["passed"] is True and r["score"] == 1.0 and r["error"] is None

    def test_fail(self):
        r = run_test({"name": "t", "prompt": "x", "eval": "exact", "expected": "PING"}, _pong, "m")
        assert r["passed"] is False and r["score"] == 0.0

    def test_not_contains(self):
        def apology(m, p, s): return "I'm sorry, I can't help."
        r = run_test({"name": "t", "prompt": "x", "eval": "not_contains", "expected": "sorry"}, apology, "m")
        assert r["passed"] is False

    def test_startswith(self):
        def yes_fn(m, p, s): return "Yes, absolutely."
        r = run_test({"name": "t", "prompt": "x", "eval": "startswith", "expected": "Yes"}, yes_fn, "m")
        assert r["passed"] is True

    def test_missing_prompt(self):
        r = run_test({"name": "broken", "eval": "exact", "expected": "x"}, _pong, "m")
        assert r["passed"] is False and "missing" in r["error"] and r["eval_type"] == "exact"

    def test_empty_dict(self):
        r = run_test({}, _pong, "m")
        assert r["passed"] is False and r["eval_type"] == "contains"

    def test_provider_exception(self):
        def boom(m, p, s): raise ConnectionError("network error")
        r = run_test({"name": "t", "prompt": "x", "eval": "exact", "expected": "x"}, boom, "m")
        assert r["passed"] is False and "network error" in r["error"]

    def test_preview_truncated(self):
        def long(m, p, s): return "x" * 300
        r = run_test({"name": "t", "prompt": "x", "eval": "contains", "expected": "x"}, long, "m")
        assert len(r["response_preview"]) == 200


class TestLoadSuite:
    def test_universal_v1(self):
        suite_dir = Path(__file__).parent.parent / "llm_canary" / "suites" / "universal-v1"
        tests = load_suite(suite_dir)
        assert len(tests) >= 8
        for t in tests:
            assert "prompt" in t

    def test_json_reliability(self):
        suite_dir = Path(__file__).parent.parent / "llm_canary" / "suites" / "json-reliability"
        assert len(load_suite(suite_dir)) >= 3

    def test_reasoning(self):
        suite_dir = Path(__file__).parent.parent / "llm_canary" / "suites" / "reasoning"
        assert len(load_suite(suite_dir)) >= 5

    def test_readme_not_loaded(self):
        suite_dir = Path(__file__).parent.parent / "llm_canary" / "suites" / "universal-v1"
        names = [t.get("name", "") for t in load_suite(suite_dir)]
        assert "README" not in names


class TestDetectDrift:
    def _write(self, path, filename, pass_rate, passed_names):
        data = {
            "run_at": "2025-01-01T09:00:00",
            "provider": "openai", "model": "gpt-4o",
            "pass_rate": pass_rate,
            "results": [{"name": n, "passed": True} for n in passed_names],
        }
        (path / filename).write_text(json.dumps(data))

    def test_no_history(self, tmp_path):
        cur = {"pass_rate": 100.0, "run_at": "2025-03-01T09:00:00", "results": []}
        info = detect_drift(tmp_path, cur, "openai", "gpt-4o", quiet=True)
        assert info["delta"] == 0

    def test_drift_detected(self, tmp_path):
        self._write(tmp_path, "20250101_openai_gpt-4o.json", 100.0, ["a", "b", "c"])
        cur = {
            "pass_rate": 66.7, "run_at": "2025-03-01T09:00:00",
            "results": [
                {"name": "a", "passed": True},
                {"name": "b", "passed": False},
                {"name": "c", "passed": False},
            ],
        }
        (tmp_path / "20250301_openai_gpt-4o.json").write_text(json.dumps(cur))
        info = detect_drift(tmp_path, cur, "openai", "gpt-4o", quiet=True)
        assert info["delta"] < -1
        assert "b" in info["newly_failed"] and "c" in info["newly_failed"]

    def test_corrupt_history_skipped(self, tmp_path):
        (tmp_path / "20250101_openai_gpt-4o.json").write_text("CORRUPT{{{")
        cur = {"pass_rate": 100.0, "run_at": "2025-03-01T09:00:00", "results": []}
        (tmp_path / "20250301_openai_gpt-4o.json").write_text(json.dumps(cur))
        info = detect_drift(tmp_path, cur, "openai", "gpt-4o", quiet=True)
        assert info["delta"] == 0


class TestShowHistory:
    def _write(self, path, filename, pass_rate):
        data = {
            "run_at": "2025-01-01T09:00:00",
            "provider": "openai", "model": "gpt-4o",
            "pass_rate": pass_rate,
            "passed": int(pass_rate), "total": 100,
            "results": [],
        }
        (path / filename).write_text(json.dumps(data))

    def test_returns_records(self, tmp_path):
        self._write(tmp_path, "20250101_openai_gpt-4o.json", 100.0)
        self._write(tmp_path, "20250108_openai_gpt-4o.json", 88.0)
        records = show_history(tmp_path, "openai", "gpt-4o", limit=10)
        assert len(records) == 2
        assert records[0]["pass_rate"] == 100.0
        assert records[1]["pass_rate"] == 88.0

    def test_empty_dir(self, tmp_path):
        records = show_history(tmp_path, "openai", "gpt-4o")
        assert records == []

    def test_limit(self, tmp_path):
        for i in range(1, 8):
            self._write(tmp_path, f"2025010{i}_openai_gpt-4o.json", float(i * 10))
        records = show_history(tmp_path, "openai", "gpt-4o", limit=3)
        assert len(records) == 3


class TestSendAlerts:
    def test_no_config(self):
        send_alerts({}, {}, {})

    def test_slack_called(self):
        with patch("llm_canary.core.requests.post") as mp:
            mp.return_value = MagicMock()
            mp.return_value.raise_for_status.return_value = None
            send_alerts(
                {"alerts": {"slack_webhook": "https://hooks.slack.com/fake"}},
                {"pass_rate": 75.0, "passed": 3, "total": 4, "model": "gpt-4o",
                 "provider": "openai", "run_at": "2025-01-01T00:00:00"},
                {"delta": -25.0, "newly_failed": ["word-reversal"]},
            )
            assert mp.call_count == 1

    def test_slack_failure_no_crash(self):
        with patch("llm_canary.core.requests.post", side_effect=ConnectionError("down")):
            send_alerts(
                {"alerts": {"slack_webhook": "https://hooks.slack.com/fake"}},
                {"pass_rate": 50.0, "passed": 1, "total": 2, "model": "m",
                 "provider": "p", "run_at": "2025-01-01T00:00:00"},
                {"delta": -50.0, "newly_failed": []},
            )

    def test_empty_summary_no_crash(self):
        with patch("llm_canary.core.requests.post") as mp:
            mp.return_value = MagicMock()
            mp.return_value.raise_for_status.return_value = None
            send_alerts({"alerts": {"slack_webhook": "https://x.com"}}, {}, {})
