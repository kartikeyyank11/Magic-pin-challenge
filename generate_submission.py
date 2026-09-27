"""
generate_submission.py — Generates submission.jsonl from test_pairs.json using compose()
"""

import sys
import json
from pathlib import Path
from composer import compose

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

EXPANDED_DIR = Path(__file__).parent / "dataset" / "expanded"
OUTPUT_FILE = Path(__file__).parent / "submission.jsonl"


def main():
    test_pairs_path = EXPANDED_DIR / "test_pairs.json"
    if not test_pairs_path.exists():
        raise FileNotFoundError(f"Missing {test_pairs_path}. Run generate_dataset.py first.")

    with open(test_pairs_path, "r", encoding="utf-8") as f:
        test_pairs = json.load(f)["pairs"]

    # Cache categories, merchants, customers, triggers
    categories = {}
    for f in (EXPANDED_DIR / "categories").glob("*.json"):
        with open(f, "r", encoding="utf-8") as fp:
            cat = json.load(fp)
            categories[cat.get("slug", f.stem)] = cat

    merchants = {}
    for f in (EXPANDED_DIR / "merchants").glob("*.json"):
        with open(f, "r", encoding="utf-8") as fp:
            m = json.load(fp)
            merchants[m["merchant_id"]] = m

    customers = {}
    for f in (EXPANDED_DIR / "customers").glob("*.json"):
        with open(f, "r", encoding="utf-8") as fp:
            c = json.load(fp)
            customers[c["customer_id"]] = c

    triggers = {}
    for f in (EXPANDED_DIR / "triggers").glob("*.json"):
        with open(f, "r", encoding="utf-8") as fp:
            t = json.load(fp)
            triggers[t["id"]] = t

    lines = []
    print(f"Generating compositions for {len(test_pairs)} test pairs...")
    
    for pair in test_pairs:
        test_id = pair["test_id"]
        tid = pair["trigger_id"]
        mid = pair["merchant_id"]
        cid = pair.get("customer_id")

        trg = triggers.get(tid)
        if not trg:
            raise ValueError(f"Trigger not found: {tid}")
        
        merchant = merchants.get(mid)
        if not merchant:
            raise ValueError(f"Merchant not found: {mid}")

        cat_slug = merchant.get("category_slug", "")
        category = categories.get(cat_slug, {"slug": cat_slug})
        customer = customers.get(cid) if cid else None

        res = compose(category, merchant, trg, customer)

        submission_entry = {
            "test_id": test_id,
            "body": res["body"],
            "cta": res["cta"],
            "send_as": res["send_as"],
            "suppression_key": res["suppression_key"],
            "rationale": res["rationale"]
        }
        lines.append(json.dumps(submission_entry, ensure_ascii=False))
        print(f"[{test_id}] ({res['send_as']}) {res['body'][:75]}...")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"\nSuccessfully wrote {len(lines)} lines to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
