"""LLM narrative layer: pair structured gate evidence with LLM reasoning.

Rubric: "Pair structured predictive models with LLM reasoning (Granite)".
The narrative is ADVISORY ONLY: it never changes scores, decisions, or the
certificate; the JSON remains the source of truth. The prompt contains only
the certificate facts, and the generator is instructed never to invent them.

Availability chain (first that applies):
  1. ``BLACKBOX_LLM_URL``    POST {"prompt": ...} -> {"text": "..."} — any
     HTTP service speaking that shape (``scripts/llm_service.py`` on the
     LinuxONE showcase runs IBM Granite behind it).
  2. ``BLACKBOX_LLM_MODEL``  local transformers+torch model id/path, greedy
     decoding on CPU (slow on purpose; used in the showcase notebook).
  3. otherwise               ``available=False`` with the exact reason.
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import time
import urllib.error
import urllib.request

from backend.shared import config

# Narratives are a few hundred bytes; cap the read so a compromised or malicious
# endpoint cannot exhaust RAM by returning a huge body.
_MAX_LLM_RESPONSE_BYTES = 64 * 1024
_ALLOWED_URL_SCHEMES = ("http://", "https://")

_SYSTEM = (
    "You explain ML-gate decision certificates to payment-operations staff. "
    "Use ONLY the facts provided in the certificate summary. Be concise "
    "(max 120 words). Never invent numbers or outcomes. If a fact is "
    "missing or unknown, say so explicitly."
)

_local_cache: dict[str, object] = {}


def build_prompt(summary: dict) -> str:
    """Deterministic, grounding-only prompt from a flat fact dict."""
    facts = json.dumps(summary, sort_keys=True, default=str)
    return (
        f"{_SYSTEM}\n\n"
        f"Certificate facts (JSON):\n{facts}\n\n"
        "Write the 3-4 sentence narrative an operator should read first."
    )


def _http_narrate(prompt: str, url: str, timeout_s: float) -> str:
    if not url.lower().startswith(_ALLOWED_URL_SCHEMES):
        raise ValueError(f"LLM_URL scheme not allowed (http/https only): {url[:60]!r}")
    body = json.dumps({"prompt": prompt}).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310 - operator-configured URL
        raw = resp.read(_MAX_LLM_RESPONSE_BYTES + 1)
    if len(raw) > _MAX_LLM_RESPONSE_BYTES:
        raise ValueError(f"LLM response exceeds {_MAX_LLM_RESPONSE_BYTES} bytes")
    payload = json.loads(raw.decode("utf-8"))
    text = (payload or {}).get("text")
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f"LLM service returned no text: {payload!r:.200}")
    return text.strip()


def _call_with_deadline(fn, timeout_s: float):
    """Run ``fn`` with a hard wall-clock deadline.

    ``urllib``'s timeout is per socket operation, not a total deadline: a
    trickling service (1 byte/sec) can hold the calling thread open
    indefinitely. Running the call in a worker and returning on timeout frees
    the request thread; the abandoned worker finishes or dies on its own.
    """
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        return executor.submit(fn).result(timeout=timeout_s)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _local_narrate(prompt: str, model_id: str, timeout_s: float) -> str:
    import torch  # noqa: PLC0415
    from transformers import AutoModelForCausalLM, AutoTokenizer  # noqa: PLC0415

    key = f"model::{model_id}"
    if key not in _local_cache:
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=torch.float32)
        model.eval()
        _local_cache[key] = (tokenizer, model)
    tokenizer, model = _local_cache[key]
    inputs = tokenizer(prompt, return_tensors="pt")
    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=config.LLM_MAX_NEW_TOKENS,
            do_sample=False,
        )
    text = tokenizer.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
    _ = timeout_s  # local generation is not interruptible; timeout reserved for URL mode
    return text.strip()


def _unavailable(reason: str, model: str | None = None) -> dict:
    return {
        "available": False,
        "text": None,
        "model": model,
        "latency_ms": None,
        "reason": reason,
        "advisory_only": True,
    }


def narrate(summary: dict, *, timeout_s: float | None = None) -> dict:
    """Return an honest narrative result; never raises for infrastructure gaps."""
    if not config.LLM_NARRATIVE_ENABLED:
        return _unavailable("llm narrative disabled by configuration")
    timeout = float(timeout_s if timeout_s is not None else config.LLM_TIMEOUT_S)
    prompt = build_prompt(summary)

    url = os.environ.get(config.LLM_URL_ENV, "").strip()
    if url:
        start = time.perf_counter()
        try:
            text = _call_with_deadline(
                lambda: _http_narrate(prompt, url, timeout), timeout
            )
            return {
                "available": True,
                "text": text,
                "model": f"http:{url}",
                "latency_ms": round((time.perf_counter() - start) * 1000.0, 1),
                "reason": None,
                "advisory_only": True,
            }
        except (
            urllib.error.URLError, TimeoutError, ValueError, OSError,
            concurrent.futures.TimeoutError,
        ) as exc:
            return _unavailable(
                f"LLM_URL configured but request failed: {type(exc).__name__}: {exc}",
                model=f"http:{url}",
            )

    model_id = os.environ.get(config.LLM_MODEL_ENV, "").strip()
    if model_id:
        start = time.perf_counter()
        try:
            text = _local_narrate(prompt, model_id, timeout)
            return {
                "available": True,
                "text": text,
                "model": model_id,
                "latency_ms": round((time.perf_counter() - start) * 1000.0, 1),
                "reason": None,
                "advisory_only": True,
            }
        except Exception as exc:  # noqa: BLE001 - any local failure degrades honestly
            return _unavailable(
                f"local model {model_id!r} failed: {type(exc).__name__}: {exc}",
                model=model_id,
            )

    return _unavailable(
        f"no LLM configured (set {config.LLM_URL_ENV} to a narrate service "
        f"e.g. scripts/llm_service.py, or {config.LLM_MODEL_ENV} for a local "
        "transformers model)"
    )
