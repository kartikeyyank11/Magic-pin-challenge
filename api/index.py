import os
import sys
import json
import time
from datetime import datetime, timezone
from pathlib import Path

# Add project root directory to path for imports
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from composer import compose
from conversation_handlers import respond

START_TIME = time.time()
contexts = {}
conversations = {}


def app(environ, start_response):
    raw_path = environ.get("PATH_INFO", "/")
    path = raw_path.rstrip("/")
    if not path:
        path = "/"
    method = environ.get("REQUEST_METHOD", "GET").upper()

    headers = [
        ("Access-Control-Allow-Origin", "*"),
        ("Access-Control-Allow-Headers", "*"),
        ("Access-Control-Allow-Methods", "*"),
    ]

    if method == "OPTIONS":
        start_response("200 OK", headers)
        return [b""]

    if method == "GET":
        if path in ("/", "/dashboard", "/index.html", "/index"):
            dash_path = ROOT_DIR / "dashboard.html"
            if dash_path.exists():
                with open(dash_path, "rb") as f:
                    content = f.read()
                headers.append(("Content-Type", "text/html; charset=utf-8"))
                start_response("200 OK", headers)
                return [content]

        if path == "/v1/healthz":
            res = {
                "status": "ok",
                "uptime_seconds": int(time.time() - START_TIME),
                "contexts_loaded": {
                    "category": sum(1 for k in contexts if k[0] == "category"),
                    "merchant": sum(1 for k in contexts if k[0] == "merchant"),
                    "customer": sum(1 for k in contexts if k[0] == "customer"),
                    "trigger": sum(1 for k in contexts if k[0] == "trigger"),
                }
            }
            headers.append(("Content-Type", "application/json; charset=utf-8"))
            start_response("200 OK", headers)
            return [json.dumps(res).encode("utf-8")]

        if path == "/v1/metadata":
            res = {
                "team_name": "Vera-Next",
                "team_members": ["Magicpin AI Challenger"],
                "model": "4-context-hybrid",
                "approach": "Deterministic 4-context compositional engine with Cialdini compulsion levers & multi-turn intent transition",
                "contact_email": "candidate@magicpin.in",
                "version": "1.0.0",
                "submitted_at": "2026-04-26T08:00:00Z"
            }
            headers.append(("Content-Type", "application/json; charset=utf-8"))
            start_response("200 OK", headers)
            return [json.dumps(res).encode("utf-8")]

    elif method == "POST":
        try:
            length = int(environ.get("CONTENT_LENGTH", "0") or "0")
        except ValueError:
            length = 0
        body_bytes = environ["wsgi.input"].read(length) if length > 0 else b"{}"
        try:
            data = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
        except Exception:
            headers.append(("Content-Type", "application/json; charset=utf-8"))
            start_response("400 Bad Request", headers)
            return [json.dumps({"accepted": False, "reason": "invalid_json"}).encode("utf-8")]

        if path == "/v1/context":
            scope = data.get("scope")
            cid = data.get("context_id")
            version = data.get("version", 1)
            payload = data.get("payload", {})

            if not scope or not cid:
                headers.append(("Content-Type", "application/json; charset=utf-8"))
                start_response("400 Bad Request", headers)
                return [json.dumps({"accepted": False, "reason": "missing_scope_or_context_id"}).encode("utf-8")]

            key = (scope, cid)
            cur = contexts.get(key)
            if cur and cur.get("version", 0) > version:
                headers.append(("Content-Type", "application/json; charset=utf-8"))
                start_response("409 Conflict", headers)
                return [json.dumps({"accepted": False, "reason": "stale_version", "current_version": cur.get("version", 0)}).encode("utf-8")]

            contexts[key] = {"version": version, "payload": payload}
            res = {"accepted": True, "ack_id": f"ack_{cid}_v{version}", "stored_at": datetime.now(timezone.utc).isoformat()}
            headers.append(("Content-Type", "application/json; charset=utf-8"))
            start_response("200 OK", headers)
            return [json.dumps(res).encode("utf-8")]

        if path == "/v1/tick":
            available_triggers = data.get("available_triggers", [])
            actions = []
            for trg_id in available_triggers:
                trg_entry = contexts.get(("trigger", trg_id))
                if not trg_entry:
                    continue
                trg = trg_entry.get("payload", {})
                mid = trg.get("merchant_id")
                if not mid:
                    continue
                m_entry = contexts.get(("merchant", mid))
                merchant = m_entry.get("payload") if m_entry else {"merchant_id": mid}
                cat_slug = merchant.get("category_slug", "")
                cat_entry = contexts.get(("category", cat_slug))
                category = cat_entry.get("payload") if cat_entry else {"slug": cat_slug}

                cid = trg.get("customer_id")
                customer = None
                if cid:
                    c_entry = contexts.get(("customer", cid))
                    customer = c_entry.get("payload") if c_entry else None

                composed = compose(category, merchant, trg, customer)
                actions.append({
                    "conversation_id": f"conv_tick_{trg_id}",
                    "merchant_id": mid,
                    "customer_id": cid,
                    "send_as": composed.get("send_as", "vera"),
                    "trigger_id": trg_id,
                    "template_name": f"vera_{trg.get('kind', 'generic')}_v1",
                    "template_params": [merchant.get("identity", {}).get("name", "")],
                    "body": composed.get("body", ""),
                    "cta": composed.get("cta", "binary"),
                    "suppression_key": composed.get("suppression_key", ""),
                    "rationale": composed.get("rationale", "")
                })

            res = {"actions": actions}
            headers.append(("Content-Type", "application/json; charset=utf-8"))
            start_response("200 OK", headers)
            return [json.dumps(res).encode("utf-8")]

        if path == "/v1/reply":
            conv_id = data.get("conversation_id", "default")
            mid = data.get("merchant_id")
            msg = data.get("message", "")
            turn = data.get("turn_number", 1)
            from_role = data.get("from_role", "merchant")

            history = conversations.setdefault(conv_id, [])
            merchant = None
            if mid:
                m_entry = contexts.get(("merchant", mid))
                merchant = m_entry.get("payload") if m_entry else None

            res = respond(conv_id, msg, turn, history, merchant)
            history.append({"from": from_role, "msg": msg, "turn": turn, "ts": data.get("received_at", datetime.now(timezone.utc).isoformat())})
            if res.get("action") == "send" and res.get("body"):
                history.append({"from": "vera", "msg": res.get("body"), "turn": turn + 1, "ts": datetime.now(timezone.utc).isoformat()})

            headers.append(("Content-Type", "application/json; charset=utf-8"))
            start_response("200 OK", headers)
            return [json.dumps(res).encode("utf-8")]

        if path == "/v1/teardown":
            contexts.clear()
            conversations.clear()
            headers.append(("Content-Type", "application/json; charset=utf-8"))
            start_response("200 OK", headers)
            return [json.dumps({"status": "cleared"}).encode("utf-8")]

    # 404 fallback
    headers.append(("Content-Type", "application/json; charset=utf-8"))
    start_response("404 Not Found", headers)
    return [json.dumps({"error": "not_found", "path": path, "raw_path": raw_path}).encode("utf-8")]


# Alias handler for Vercel Serverless Function entrypoint
handler = app
