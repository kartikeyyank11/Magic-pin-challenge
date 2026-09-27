"""Print all 30 submission messages in full for quality review."""
import json, sys
sys.stdout.reconfigure(encoding='utf-8')

with open("submission.jsonl", "r", encoding="utf-8") as f:
    lines = f.readlines()

for line in lines:
    obj = json.loads(line.strip())
    tid = obj.get("test_id", "?")
    body = obj.get("body", "")
    send_as = obj.get("send_as", "")
    rationale = obj.get("rationale", "")
    cta = obj.get("cta", "")
    print(f"\n{'='*70}")
    print(f"[{tid}] send_as={send_as} | cta={cta}")
    print(f"BODY: {body}")
    print(f"WHY: {rationale}")
