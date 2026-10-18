#!/usr/bin/env python3
"""Granite narrate service for the BLACKBOX showcase (advisory only).

Speaks the minimal contract backend/intelligence/llm_explain.py
expects when BLACKBOX_LLM_URL points here:

    POST /narrate  {"prompt": "..."}  ->  {"text": "...", "model": ..., ...}
    GET  /health   -> {"status": "ok"|"loading", "model": ..., "loaded": bool}

Two load backends, auto-detected from the --model value:
    *.gguf path    llama.cpp via llama-cpp-python (CPU, no torch required;
                   the portable path for the LinuxONE guest and CI)
    anything else  transformers+torch (local_files_only), as shipped in the
                   LinuxONE Jupyter container

    python scripts/llm_service.py                     # default port 38899
    LLM_SERVICE_MODEL=ibm-granite/granite-3.0-1b-a400m-instruct \
    LLM_SERVICE_PORT=38899 python scripts/llm_service.py
    python scripts/llm_service.py --model /opt/models/granite-4.2-3b-Q4_K_M.gguf
"""
from __future__ import annotations

import argparse
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_MODEL = "ibm-granite/granite-3.0-1b-a400m-instruct"
try:
    MAX_NEW_TOKENS = int(os.environ.get("LLM_SERVICE_MAX_TOKENS", "128"))
except ValueError:
    MAX_NEW_TOKENS = 128
# Cap the request body: a huge POST must not be read fully into RAM.
MAX_REQUEST_BYTES = 64 * 1024

# Literal ChatML wrapping for Granite GGUFs without an embedded chat template.
# Mirrors ibm-granite/granite-4.2-3b chat_template.jinja with thinking off:
#   <|im_start|>system ... <|im_end|>
#   <|im_start|>user ... <|im_end|>
#   <|im_start|>assistant
#   <think></think>
# Verified against granite-4.2-3b Q4_K_M: grounded 3-5 sentence narratives
# that reach EOS within 128 tokens (the 3.x <|system|>/<|user|> form made the
# model echo its own instructions instead).
_ROLE_WRAP = (
    "<|im_start|>system\n"
    "You are a concise, factual assistant for payment-operations staff.<|im_end|>\n"
    "<|im_start|>user\n{prompt}<|im_end|>\n"
    "<|im_start|>assistant\n<think></think>"
)

_state: dict = {
    "model_id": None, "tokenizer": None, "model": None, "error": None,
    "loaded": False, "backend": None, "llama": None,
}
_load_lock = threading.Lock()
_generate_lock = threading.Lock()  # one generate at a time on the shared model
_lazy_model_id: str | None = None


def _load(model_id: str) -> None:
    _state["model_id"] = model_id
    # GGUF -> llama.cpp (CPU-only, greedy; no torch dependency).
    if model_id.lower().endswith(".gguf"):
        try:
            from llama_cpp import Llama

            _state["llama"] = Llama(
                model_path=model_id,
                n_ctx=4096,
                n_threads=max(1, (os.cpu_count() or 4) - 1),
                verbose=False,
            )
            _state["backend"] = "llama-cpp"
            _state["loaded"] = True
        except Exception as exc:  # noqa: BLE001 - surface the reason, never fake text
            _state["error"] = f"{type(exc).__name__}: {exc}"
            _state["loaded"] = False
        return
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        _state["tokenizer"] = AutoTokenizer.from_pretrained(model_id, local_files_only=True)
        _state["model"] = AutoModelForCausalLM.from_pretrained(
            model_id, torch_dtype=torch.float32, low_cpu_mem_usage=True, local_files_only=True
        )
        _state["model"].eval()
        _state["backend"] = "transformers"
        _state["loaded"] = True
    except Exception as exc:  # noqa: BLE001 - surface the reason, never fake text
        _state["error"] = f"{type(exc).__name__}: {exc}"
        _state["loaded"] = False


def _maybe_load_lazy() -> None:
    """Load once on first /narrate when started with --lazy (thread-safe)."""
    if _state["loaded"] or _state["error"] or _lazy_model_id is None:
        return
    with _load_lock:
        if not _state["loaded"] and _state["error"] is None:
            _load(_lazy_model_id)


def _generate(prompt: str) -> dict:
    if not _state["loaded"]:
        raise RuntimeError(f"model not loaded: {_state['error'] or 'still loading'}")
    start = time.perf_counter()
    # Serialize access: the shared model is not reentrant, and N concurrent
    # generates would each allocate activations for MAX_NEW_TOKENS.
    with _generate_lock:
        if _state["backend"] == "llama-cpp":
            llama = _state["llama"]
            # Embedded chat template? Use it. Some Granite GGUFs ship without
            # one: fall back to the literal ChatML format Granite 4.2 was
            # trained with (see _ROLE_WRAP).
            meta = getattr(llama, "metadata", None) or {}
            try:
                has_template = bool(meta.get("chat_template"))
            except Exception:  # noqa: BLE001
                has_template = False
            if has_template:
                out = llama.create_chat_completion(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,  # greedy, matching do_sample=False
                    max_tokens=MAX_NEW_TOKENS,
                )
                text = (out["choices"][0]["message"]["content"] or "").strip()
            else:
                out = llama.create_completion(
                    prompt=_ROLE_WRAP.format(prompt=prompt),
                    temperature=0.0,
                    max_tokens=MAX_NEW_TOKENS,
                    stop=["<|im_end|>", "<|im_start|>"],
                )
                text = (out["choices"][0]["text"] or "").strip()
        else:
            import torch

            tokenizer, model = _state["tokenizer"], _state["model"]
            inputs = tokenizer(prompt, return_tensors="pt")
            with torch.no_grad():
                out = model.generate(**inputs, max_new_tokens=MAX_NEW_TOKENS, do_sample=False)
            text = tokenizer.decode(
                out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True
            ).strip()
    return {
        "text": text,
        "model": _state["model_id"],
        "backend": _state["backend"],
        "latency_ms": round((time.perf_counter() - start) * 1000.0, 1),
        "advisory_only": True,
    }


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        if self.path.rstrip("/") in {"", "/health"}:
            # 503 when the model failed to load so orchestrators can detect it.
            code = 200 if _state["loaded"] or not _state["error"] else 503
            self._send(
                code,
                {
                    "status": "ok" if _state["loaded"] else ("error" if _state["error"] else "loading"),
                    "model": _state["model_id"],
                    "backend": _state["backend"],
                    "loaded": _state["loaded"],
                    "error": _state["error"],
                },
            )
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802 - http.server API
        if self.path.rstrip("/") != "/narrate":
            self._send(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0 or length > MAX_REQUEST_BYTES:
                self._send(413, {"error": f"request too large (max {MAX_REQUEST_BYTES} bytes)"})
                return
            req = json.loads(self.rfile.read(length).decode("utf-8"))
            prompt = req.get("prompt")
            if not isinstance(prompt, str) or not prompt.strip():
                self._send(422, {"error": "prompt (string) is required"})
                return
            _maybe_load_lazy()  # --lazy: load on first request
            self._send(200, _generate(prompt))
        except Exception as exc:  # noqa: BLE001
            self._send(500, {"error": f"{type(exc).__name__}: {exc}"})

    def log_message(self, fmt: str, *args) -> None:  # quiet container logs
        print(f"llm_service: {fmt % args}", flush=True)


def main() -> None:
    global _lazy_model_id
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=int(os.environ.get("LLM_SERVICE_PORT", "38899")))
    parser.add_argument("--model", default=os.environ.get("LLM_SERVICE_MODEL", DEFAULT_MODEL))
    parser.add_argument(
        "--bind",
        default=os.environ.get("LLM_SERVICE_BIND", "127.0.0.1"),
        help="interface to bind (default loopback; use 0.0.0.0 only behind a trusted network)",
    )
    parser.add_argument("--lazy", action="store_true", help="load the model on first /narrate")
    args = parser.parse_args()
    if args.lazy:
        _lazy_model_id = args.model
    else:
        print(f"llm_service: loading {args.model} ...", flush=True)
        _load(args.model)
        print(f"llm_service: loaded={_state['loaded']} error={_state['error']}", flush=True)
    server = ThreadingHTTPServer((args.bind, args.port), Handler)
    print(f"llm_service: listening on {args.bind}:{args.port} model={args.model}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
