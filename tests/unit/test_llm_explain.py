"""LLM narrative: honest degradation, prompt grounding, URL mode contract.

Stdlib-only style: no pytest fixtures (``scripts/run_tests.py`` calls each
test function with zero arguments).
"""
from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from backend.intelligence import llm_explain
from backend.shared import config

_SUMMARY = {
    "transaction_id": "TX-1",
    "impact_score": 0.516452,
    "gate_decision": False,
    "status": "NO_SIMULATION",
    "backend": "sklearn",
}


@contextmanager
def _env(**overrides):
    """Set/clear env vars (value None = delete); restore exactly on exit."""
    saved = {k: os.environ.get(k) for k in overrides}
    try:
        for k, v in overrides.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class _EchoHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802 - http.server API
        length = int(self.headers.get("Content-Length", "0"))
        req = json.loads(self.rfile.read(length))
        assert "prompt" in req
        body = json.dumps({"text": "TX-1 was reviewed; no simulation ran."}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # quiet
        pass


def test_prompt_contains_only_facts_and_refusal_rule():
    prompt = llm_explain.build_prompt(_SUMMARY)
    assert "TX-1" in prompt and "0.516452" in prompt
    assert "Never invent" in prompt
    assert prompt == llm_explain.build_prompt(dict(_SUMMARY))


def test_narrate_without_configuration_is_honest_unavailable():
    with _env(**{config.LLM_URL_ENV: None, config.LLM_MODEL_ENV: None}):
        result = llm_explain.narrate(_SUMMARY)
    assert result["available"] is False
    assert result["text"] is None
    assert result["advisory_only"] is True
    assert config.LLM_URL_ENV in (result["reason"] or "")


def test_narrate_url_mode_returns_service_text():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _EchoHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with _env(**{config.LLM_URL_ENV: f"http://127.0.0.1:{port}/narrate", config.LLM_MODEL_ENV: None}):
            result = llm_explain.narrate(_SUMMARY, timeout_s=5.0)
    finally:
        server.shutdown()
    assert result["available"] is True
    assert result["text"].startswith("TX-1")
    assert result["latency_ms"] is not None and result["latency_ms"] >= 0
    assert result["advisory_only"] is True


def test_narrate_url_failure_degrades_honestly():
    with _env(**{config.LLM_URL_ENV: "http://127.0.0.1:1/narrate", config.LLM_MODEL_ENV: None}):
        result = llm_explain.narrate(_SUMMARY, timeout_s=2.0)
    assert result["available"] is False
    assert "failed" in (result["reason"] or "")


def test_narrate_respects_master_disable():
    original = config.LLM_NARRATIVE_ENABLED
    try:
        config.LLM_NARRATIVE_ENABLED = False
        with _env(**{config.LLM_URL_ENV: "http://127.0.0.1:1/narrate"}):
            result = llm_explain.narrate(_SUMMARY)
    finally:
        config.LLM_NARRATIVE_ENABLED = original
    assert result["available"] is False
    assert "disabled" in (result["reason"] or "")


def test_explain_endpoint_always_carries_llm_narrative_field():
    from fastapi.testclient import TestClient

    from backend.main import app

    with TestClient(app) as client:
        r = client.post("/explain", json={"demo_mode": True})
    assert r.status_code == 200
    llm = r.json().get("llm_narrative")
    assert isinstance(llm, dict)
    assert llm["available"] in (True, False)
    assert llm["advisory_only"] is True
    if llm["available"] is False:
        assert llm["reason"]
