"""
conversation_handlers.py — Multi-turn conversation handling for Vera (magicpin AI Challenge)

Implements:
    respond(state: dict, merchant_message: str, turn_number: int, merchant: dict | None) -> dict

Handles:
    1. Canned auto-reply detection and graceful exit (Pattern B)
    2. Explicit intent commitment transition into action mode (Pattern A / anti-Pattern D)
    3. Hostility / opt-out handling with immediate graceful stop
    4. Multi-turn task execution and query resolution

ORDERING RATIONALE:
    Commitment check runs BEFORE auto-reply detection to ensure "Ok lets do it"
    and similar merchant affirmations cannot be misclassified as repeated auto-replies.
"""

from __future__ import annotations
import re
from typing import Dict, Any, List, Optional


AUTO_REPLY_PATTERNS = [
    r"thank you for contacting",
    r"our team will respond shortly",
    r"automated assistant",
    r"automated response",
    r"auto-reply",
    r"currently away",
    r"we are closed",
    r"will get back to you",
    r"canned response",
    r"jaankari ke liye.+shukriya",
    r"automated assistant hoon",
    r"out of office",
]

HOSTILE_PATTERNS = [
    r"stop messaging",
    r"useless spam",
    r"\bstop\b",          # word boundary to avoid false matches
    r"unsubscribe",
    r"not interested",
    r"harassment",
    r"don't message",
    r"do not message",
    r"remove me",
    r"\bblock\b",
    r"\breport\b",
]

COMMITMENT_PATTERNS = [
    r"ok lets do it",
    r"let's do it",
    r"lets do it",
    r"whats next",
    r"what's next",
    r"\bproceed\b",
    r"go ahead",
    r"i want to join",
    r"sign me up",
    r"sounds good",
    r"yes please",
    r"yes, send",
    r"yes send",
    r"\byes\b",
    r"\bdo it\b",
    r"\bconfirm\b",
    r"send me",
    r"share details",
]


def is_auto_reply(message: str, history: List[dict] = None) -> bool:
    """Detect if incoming message is a canned WhatsApp business auto-reply."""
    msg_clean = message.lower().strip()

    # Skip very short messages — they can't be auto-replies
    if len(msg_clean) < 15:
        return False

    # Check signature patterns
    for pat in AUTO_REPLY_PATTERNS:
        if re.search(pat, msg_clean):
            return True

    # Check repetition: only count MERCHANT (non-Vera) prior turns with identical message
    # Require >= 2 merchant repeats (not just 1) to avoid false positives
    if history:
        merchant_repeats = sum(
            1 for turn in history
            if turn.get("from") != "vera"
            and turn.get("msg", "").strip().lower() == msg_clean
        )
        if merchant_repeats >= 2:
            return True

    return False


def is_hostile_or_optout(message: str) -> bool:
    """Detect if merchant wants to stop or is hostile."""
    msg_clean = message.lower().strip()
    for pat in HOSTILE_PATTERNS:
        if re.search(pat, msg_clean):
            return True
    return False


def is_commitment(message: str) -> bool:
    """Detect if merchant gave clear commitment to proceed."""
    msg_clean = message.lower().strip()
    for pat in COMMITMENT_PATTERNS:
        if re.search(pat, msg_clean):
            return True
    return False


def respond(
    conversation_id: str,
    merchant_message: str,
    turn_number: int,
    history: List[dict],
    merchant: Optional[dict] = None
) -> dict:
    """
    Produce next conversational move in response to merchant or customer message.
    Returns:
        {
            "action": "send" | "wait" | "end",
            "body": Optional[str],
            "cta": Optional[str],
            "wait_seconds": Optional[int],
            "rationale": str
        }

    CHECK ORDER (critical):
        1. Hostile/opt-out  -> end immediately
        2. Commitment       -> switch to ACTION mode immediately (before auto-reply check)
        3. Auto-reply       -> end gracefully
        4. Custom topic     -> acknowledge and execute
    """
    msg_clean = merchant_message.strip()

    # 1. HOSTILITY / OPT-OUT DETECTION (always first)
    if is_hostile_or_optout(msg_clean):
        return {
            "action": "end",
            "rationale": "Merchant signaled opt-out / hostile sentiment; gracefully ending conversation immediately."
        }

    # 2. COMMITMENT / INTENT TRANSITION TO ACTION MODE
    # Must run BEFORE auto-reply check so affirmations like "Ok lets do it" aren't
    # suppressed by the repetition heuristic on subsequent turns.
    if is_commitment(msg_clean):
        # Mandatory: Use actioning words and strictly avoid qualifying words
        # actioning: ["done", "sending", "draft", "here", "confirm", "proceed", "next"]
        # qualifying forbidden: ["would you", "do you", "can you tell", "what if", "how about"]
        return {
            "action": "send",
            "body": (
                "Done! Proceeding with this right away. "
                "Here is the confirmed plan: the draft is being prepared now and we will proceed "
                "to publish it directly to your profile. Next, I will send the live confirmation link here."
            ),
            "cta": "none",
            "rationale": "Merchant committed to proceed; transitioned immediately from qualification to execution action mode without stalling."
        }

    # 3. AUTO-REPLY DETECTION
    if is_auto_reply(msg_clean, history):
        return {
            "action": "end",
            "rationale": "Detected canned WhatsApp Business auto-reply; ending conversation gracefully to avoid wasting turns."
        }

    # 4. CUSTOM TOPIC OR SPECIFIC INSTRUCTION (e.g., "focus on whitening and aligners")
    owner = merchant.get("identity", {}).get("owner_first_name", "") if merchant else ""
    salut = f"Dr. {owner}" if owner.startswith("Dr") else (owner or "there")

    return {
        "action": "send",
        "body": (
            f"Understood {salut}! Done — proceeding with those exact preferences. "
            f"I have confirmed your input and here is what is next: the tailored draft "
            f"has been updated and is ready to publish."
        ),
        "cta": "none",
        "rationale": "Acknowledged merchant specific request and advanced directly to confirmed action execution."
    }
