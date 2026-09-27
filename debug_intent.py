"""Debug why commitment triggers 'end' from the bot HTTP endpoint."""
import sys, json, urllib.request
sys.stdout.reconfigure(encoding='utf-8')

BASE = "http://localhost:8088"

def post(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

# Send the commitment message the judge uses
payload = {
    "conversation_id": "conv_debug_intent",
    "merchant_id": "m_001_drmeera_dentist_delhi",
    "message": "Ok lets do it. Whats next?",
    "turn_number": 2,
    "from_role": "merchant"
}

print("Sending:", json.dumps(payload, indent=2))
result = post("/v1/reply", payload)
print("Response:", json.dumps(result, indent=2, ensure_ascii=False))
