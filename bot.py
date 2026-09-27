"""
bot.py — magicpin AI Challenge Merchant Assistant ("Vera")
=========================================================

Exposes the required 5 HTTP endpoints matching challenge-testing-brief.md:
    1. GET  /v1/healthz
    2. GET  /v1/metadata
    3. POST /v1/context
    4. POST /v1/tick
    5. POST /v1/reply

Also exports module-level:
    compose(category, merchant, trigger, customer) -> dict

Can be run via:
    python bot.py --port 8080
or
    uvicorn bot:app --host 0.0.0.0 --port 8080
"""

import sys
import os
import json
import time
from datetime import datetime, timezone
from threading import Lock
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from typing import Dict, Any, List, Optional, Tuple

from composer import compose
from conversation_handlers import respond

START_TIME = time.time()
CONTEXT_LOCK = Lock()

# In-memory context and conversation stores
# (scope, context_id) -> {"version": int, "payload": dict}
contexts: Dict[Tuple[str, str], Dict[str, Any]] = {}

# conversation_id -> list of {"from": role, "msg": str, "turn": int, "ts": str}
conversations: Dict[str, List[Dict[str, Any]]] = {}


def get_contexts_count() -> Dict[str, int]:
    """Count loaded contexts by scope."""
    counts = {"category": 0, "merchant": 0, "customer": 0, "trigger": 0}
    with CONTEXT_LOCK:
        for (scope, _), _ in contexts.items():
            if scope in counts:
                counts[scope] += 1
            else:
                counts[scope] = counts.get(scope, 0) + 1
    return counts


def handle_push_context(data: dict) -> Tuple[int, dict]:
    """Store pushed context with version idempotency."""
    scope = data.get("scope")
    cid = data.get("context_id")
    version = data.get("version", 1)
    payload = data.get("payload", {})

    if not scope or not cid:
        return 400, {"accepted": False, "reason": "missing_scope_or_context_id"}

    key = (scope, cid)
    with CONTEXT_LOCK:
        cur = contexts.get(key)
        # Idempotent: re-posting the same version is accepted as a no-op
        # Only strictly lower versions are rejected as stale
        if cur and cur.get("version", 0) > version:
            return 409, {
                "accepted": False,
                "reason": "stale_version",
                "current_version": cur.get("version", 0)
            }
        contexts[key] = {"version": version, "payload": payload}

    return 200, {
        "accepted": True,
        "ack_id": f"ack_{cid}_v{version}",
        "stored_at": datetime.now(timezone.utc).isoformat()
    }


def handle_tick(data: dict) -> Tuple[int, dict]:
    """Process active triggers and produce proactive actions."""
    available_triggers = data.get("available_triggers", [])
    actions = []

    with CONTEXT_LOCK:
        for trg_id in available_triggers:
            trg_entry = contexts.get(("trigger", trg_id))
            if not trg_entry:
                continue
            trg = trg_entry.get("payload", {})
            
            mid = trg.get("merchant_id")
            if not mid:
                mid = trg.get("payload", {}).get("merchant_id")
            if not mid:
                continue

            merchant_entry = contexts.get(("merchant", mid))
            merchant = merchant_entry.get("payload") if merchant_entry else None
            if not merchant:
                continue

            cat_slug = merchant.get("category_slug", "")
            cat_entry = contexts.get(("category", cat_slug))
            category = cat_entry.get("payload") if cat_entry else {"slug": cat_slug}

            cid = trg.get("customer_id")
            customer = None
            if cid:
                cust_entry = contexts.get(("customer", cid))
                customer = cust_entry.get("payload") if cust_entry else None

            # Compose message
            composed = compose(category, merchant, trg, customer)
            actions.append({
                "conversation_id": f"conv_{mid}_{trg_id}",
                "merchant_id": mid,
                "customer_id": cid,
                "send_as": composed.get("send_as", "vera"),
                "trigger_id": trg_id,
                "template_name": f"vera_{trg.get('kind', 'generic')}_v1",
                "template_params": [merchant.get("identity", {}).get("name", ""), trg_id],
                "body": composed.get("body", ""),
                "cta": composed.get("cta", "binary"),
                "suppression_key": composed.get("suppression_key", trg.get("suppression_key", "")),
                "rationale": composed.get("rationale", "")
            })

    return 200, {"actions": actions}


def handle_reply(data: dict) -> Tuple[int, dict]:
    """Process incoming reply from merchant or customer."""
    conv_id = data.get("conversation_id", "conv_default")
    mid = data.get("merchant_id")
    msg = data.get("message", "")
    turn = data.get("turn_number", 1)
    from_role = data.get("from_role", "merchant")

    # Get conversation history
    history = conversations.setdefault(conv_id, [])
    
    # Lookup merchant context if available
    merchant = None
    if mid:
        with CONTEXT_LOCK:
            m_entry = contexts.get(("merchant", mid))
            merchant = m_entry.get("payload") if m_entry else None

    # Produce response
    res = respond(conv_id, msg, turn, history, merchant)

    # Record turn
    history.append({
        "from": from_role,
        "msg": msg,
        "turn": turn,
        "ts": data.get("received_at", datetime.now(timezone.utc).isoformat())
    })
    if res.get("action") == "send" and res.get("body"):
        history.append({
            "from": "vera",
            "msg": res.get("body"),
            "turn": turn + 1,
            "ts": datetime.now(timezone.utc).isoformat()
        })

    return 200, res


# =============================================================================
# HTTP SERVER IMPLEMENTATION (ZERO DEPENDENCY, ROBUST, THREADED)
# =============================================================================

class VeraRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress routine access logs for clean console
        pass

    def _send_json(self, status_code: int, data: dict):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "*")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "*")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/dashboard", "/index.html"):
            dash_path = os.path.join(os.path.dirname(__file__), "dashboard.html")
            if os.path.exists(dash_path):
                with open(dash_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
        if path == "/v1/healthz":
            res = {
                "status": "ok",
                "uptime_seconds": int(time.time() - START_TIME),
                "contexts_loaded": get_contexts_count()
            }
            self._send_json(200, res)
        elif path == "/v1/metadata":
            res = {
                "team_name": "Vera-Next",
                "team_members": ["Magicpin AI Challenger"],
                "model": "4-context-hybrid",
                "approach": "Deterministic 4-context compositional engine with Cialdini compulsion levers & multi-turn intent transition",
                "contact_email": "candidate@magicpin.in",
                "version": "1.0.0",
                "submitted_at": "2026-04-26T08:00:00Z"
            }
            self._send_json(200, res)
        else:
            self._send_json(404, {"error": "not_found"})

    def do_POST(self):
        path = self.path.split("?")[0]
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            data = json.loads(post_data.decode("utf-8")) if post_data else {}
        except Exception:
            self._send_json(400, {"accepted": False, "reason": "invalid_json"})
            return

        if path == "/v1/context":
            status, res = handle_push_context(data)
            self._send_json(status, res)
        elif path == "/v1/tick":
            status, res = handle_tick(data)
            self._send_json(status, res)
        elif path == "/v1/reply":
            status, res = handle_reply(data)
            self._send_json(status, res)
        elif path == "/v1/teardown":
            with CONTEXT_LOCK:
                contexts.clear()
                conversations.clear()
            self._send_json(200, {"status": "cleared"})
        else:
            self._send_json(404, {"error": "not_found"})


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


# =============================================================================
# ASGI COMPLIANT APP FOR UVICORN SUPPORT
# =============================================================================

async def app(scope, receive, send):
    """Minimal ASGI application callable for uvicorn."""
    if scope["type"] != "http":
        return

    path = scope.get("path", "")
    method = scope.get("method", "GET")

    body_bytes = b""
    more_body = True
    while more_body:
        message = await receive()
        body_bytes += message.get("body", b"")
        more_body = message.get("more_body", False)

    try:
        data = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
    except Exception:
        data = {}

    if method == "GET":
        if path == "/v1/healthz":
            status, res = 200, {
                "status": "ok",
                "uptime_seconds": int(time.time() - START_TIME),
                "contexts_loaded": get_contexts_count()
            }
        elif path == "/v1/metadata":
            status, res = 200, {
                "team_name": "Vera-Next",
                "team_members": ["Magicpin AI Challenger"],
                "model": "4-context-hybrid",
                "approach": "Deterministic 4-context compositional engine with Cialdini compulsion levers & multi-turn intent transition",
                "contact_email": "candidate@magicpin.in",
                "version": "1.0.0",
                "submitted_at": "2026-04-26T08:00:00Z"
            }
        else:
            status, res = 404, {"error": "not_found"}
    elif method == "POST":
        if path == "/v1/context":
            status, res = handle_push_context(data)
        elif path == "/v1/tick":
            status, res = handle_tick(data)
        elif path == "/v1/reply":
            status, res = handle_reply(data)
        elif path == "/v1/teardown":
            with CONTEXT_LOCK:
                contexts.clear()
                conversations.clear()
            status, res = 200, {"status": "cleared"}
        else:
            status, res = 404, {"error": "not_found"}
    else:
        status, res = 405, {"error": "method_not_allowed"}

    resp_bytes = json.dumps(res).encode("utf-8")
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [
            [b"content-type", b"application/json; charset=utf-8"],
            [b"content-length", str(len(resp_bytes)).encode("ascii")]
        ]
    })
    await send({
        "type": "http.response.body",
        "body": resp_bytes
    })


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

def run_server(port: int = 8088, host: str = "0.0.0.0"):
    default_port = int(os.getenv("PORT", str(port)))
    ports_to_try = [default_port, 8088, 8081, 8082, 8080]
    server = None
    actual_port = default_port
    
    for p in ports_to_try:
        try:
            server = ThreadedHTTPServer((host, p), VeraRequestHandler)
            actual_port = p
            break
        except (PermissionError, OSError) as e:
            continue

    if not server:
        # Fallback to localhost binding
        for p in ports_to_try:
            try:
                server = ThreadedHTTPServer(("127.0.0.1", p), VeraRequestHandler)
                actual_port = p
                host = "127.0.0.1"
                break
            except (PermissionError, OSError):
                continue

    if not server:
        raise RuntimeError("Could not bind bot server to any available port!")

    print(f"[*] Vera Bot server listening at http://{host}:{actual_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Shutting down server...")
        server.shutdown()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Vera Bot Server")
    parser.add_argument("--port", type=int, default=8088, help="Port to listen on (default 8088)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host interface to bind to")
    args = parser.parse_args()
    run_server(args.port, args.host)
