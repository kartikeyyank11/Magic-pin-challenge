"""Debug why commitment message returns 'end'."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import re

HOSTILE_PATTERNS = [
    r"stop messaging",
    r"useless spam",
    r"stop",
    r"unsubscribe",
    r"not interested",
    r"harassment",
    r"don't message",
    r"do not message",
    r"remove me",
    r"block",
    r"report",
]

msg = "Ok lets do it. Whats next?"
msg_clean = msg.strip()

print("Testing message:", repr(msg_clean))
for pat in HOSTILE_PATTERNS:
    if re.search(pat, msg_clean, re.IGNORECASE):
        print(f"  HOSTILE MATCH: pattern={pat!r}")
    else:
        print(f"  No match: {pat!r}")

# Also test lower
msg_lower = msg_clean.lower()
print("\nLower version:", repr(msg_lower))
for pat in HOSTILE_PATTERNS:
    if re.search(pat, msg_lower):
        print(f"  HOSTILE MATCH (lower): pattern={pat!r}")
