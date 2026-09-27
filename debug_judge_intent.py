"""Replicate exact judge test for intent."""
import sys, json, urllib.request
sys.stdout.reconfigure(encoding='utf-8')

BASE = "http://localhost:8088"

def post(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

# This replicates exact judge call (line 778 of judge_simulator.py)
# client.reply("conv_intent_1", mid, commitment, 2)
# Let's look at what client.reply sends

# Check the client reply implementation
import importlib.util
spec = importlib.util.spec_from_file_location("judge", "judge_simulator.py")
mod = importlib.util.module_from_spec(spec)
# Don't execute — just read the reply method signature

# Direct HTTP test replicating exactly what the judge does
mid = "m_001_drmeera_dentist_delhi"  # first merchant key
commitment = "Ok lets do it. Whats next?"

print(f"Testing conv_intent_1 / turn=2 / merchant={mid}")
print(f"Message: {commitment!r}")

payload = {
    "conversation_id": "conv_intent_1",
    "merchant_id": mid,
    "message": commitment,
    "turn_number": 2,
    "from_role": "merchant"
}

result = post("/v1/reply", payload)
print("Response:", json.dumps(result, indent=2, ensure_ascii=False))
print("\nAction:", result.get("action"))
print("Body:", result.get("body", "")[:100])
