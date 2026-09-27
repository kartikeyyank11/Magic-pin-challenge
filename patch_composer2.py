"""Patch 2 — fix remaining quality issues in composer.py."""

with open("composer.py", "r", encoding="utf-8") as f:
    src = f.read()

fixes = 0

# -------------------------------------------------------------------
# FIX A — dormant CTR: use round(), not int(), so 0.375 -> 0% becomes 4%
# -------------------------------------------------------------------
old_a = 'f"One fresh photo + a Google post typically moves CTR {int(peer_ctr * 0.15 * 100)}%+ in under a week. "'
new_a = 'f"One fresh photo + a Google post typically moves CTR {max(2, round(peer_ctr * 15))}%+ in under a week. "'
if old_a in src:
    src = src.replace(old_a, new_a)
    print("FIX A: dormant CTR rounding fixed")
    fixes += 1
else:
    print("FIX A NOT FOUND")

# -------------------------------------------------------------------
# FIX B — perf_spike: remove double "your" from driver_human
# -------------------------------------------------------------------
old_b = '        # Translate driver to human terms\n        driver_human = driver.replace("_", " ")'
new_b = '        # Translate driver to human terms\n        driver_human = driver.replace("_", " ").replace("your ", "").strip()'
if old_b in src:
    src = src.replace(old_b, new_b)
    print("FIX B: perf_spike driver 'your' dedup")
    fixes += 1
else:
    print("FIX B NOT FOUND")

# -------------------------------------------------------------------
# FIX C — recall_due: fix "6-month preventive 6 month cleaning recall" redundancy
# -------------------------------------------------------------------
old_c = (
    '                body = (\n'
    '                    f"Hi {c_name}, {m_name} yahan 🦷 Aapki last visit ko {elapsed_months} months ho gaye hain — "\n'
    '                    f"aapka {elapsed_months}-month preventive {service_due} recall due hai. "\n'
    '                    f"Aapke liye 2 slots ready hain: {slot_str}. {offer_snippet}. "\n'
    '                    f"Reply 1 for first slot, 2 for second slot, ya koi aur time batayein jo suit kare."\n'
    '                )\n'
    '            else:\n'
    '                body = (\n'
    '                    f"Hi {c_name}, {m_name} here 🦷 It\'s been {elapsed_months} months since your last visit — "\n'
    '                    f"your {elapsed_months}-month preventive {service_due} recall is due. "\n'
    '                    f"We have 2 slots ready for you: {slot_str}. {offer_snippet}. "\n'
    '                    f"Reply 1 for the first slot, 2 for second slot, or let us know a preferred time."\n'
    '                )'
)
new_c = (
    '                service_label = service_due.replace(f"{elapsed_months} month ", "").replace(f"{elapsed_months}-month ", "").strip()\n'
    '                body = (\n'
    '                    f"Hi {c_name}, {m_name} yahan 🦷 Aapki last visit ko {elapsed_months} months ho gaye hain — "\n'
    '                    f"aapka {elapsed_months}-month preventive {service_label or \'cleaning\'} recall due hai. "\n'
    '                    f"Aapke liye 2 slots ready hain: {slot_str}. {offer_snippet}. "\n'
    '                    f"Reply 1 for first slot, 2 for second slot, ya koi aur time batayein jo suit kare."\n'
    '                )\n'
    '            else:\n'
    '                service_label = service_due.replace(f"{elapsed_months} month ", "").replace(f"{elapsed_months}-month ", "").strip()\n'
    '                body = (\n'
    '                    f"Hi {c_name}, {m_name} here 🦷 It\'s been {elapsed_months} months since your last visit — "\n'
    '                    f"your {elapsed_months}-month preventive {service_label or \'cleaning\'} recall is due. "\n'
    '                    f"We have 2 slots ready for you: {slot_str}. {offer_snippet}. "\n'
    '                    f"Reply 1 for the first slot, 2 for second slot, or let us know a preferred time."\n'
    '                )'
)
if old_c in src:
    src = src.replace(old_c, new_c)
    print("FIX C: recall_due service label deduplication")
    fixes += 1
else:
    print("FIX C NOT FOUND — checking alternatives")
    # Try a lighter version
    old_c2 = 'f"aapka {elapsed_months}-month preventive {service_due} recall due hai. "'
    new_c2 = 'f"aapka {elapsed_months}-month preventive cleaning recall due hai. "'
    if old_c2 in src:
        src = src.replace(old_c2, new_c2)
        old_c3 = 'f"your {elapsed_months}-month preventive {service_due} recall is due. "'
        new_c3 = 'f"your {elapsed_months}-month preventive cleaning recall is due. "'
        src = src.replace(old_c3, new_c3)
        print("FIX C (lite): hardcoded 'cleaning' for dentist recall")
        fixes += 1
    else:
        print("FIX C LITE ALSO NOT FOUND")

# -------------------------------------------------------------------
# FIX D — festival: fix "26-week run-up" when Diwali is 188 days away
#   The surge window is typically 3-4 weeks before, not the whole run-up
# -------------------------------------------------------------------
old_d = (
    '        surge_multiplier = "2.5x" if days_until <= 21 else "1.8x"\n'
    '        lead_time_weeks = max(1, days_until // 7)\n'
    '\n'
    '        body = (\n'
    '            f"{owner_salut}, {fest} is {days_until} days away! "\n'
    '            f"Search demand for {cat_slug} in {locality} typically surges {surge_multiplier} in the "\n'
    '            f"{lead_time_weeks}-week run-up. "\n'
    '            f"With {lead_time_weeks} weeks to go, now is the ideal moment to launch: "\n'
    '            f"want me to draft a festive promotional campaign featuring "\n'
    '            f"\'{active_offer_title or \'your signature festival package\'}\' "\n'
    '            f"to publish across your Google profile & WhatsApp today?"\n'
    '        )'
)
new_d = (
    '        surge_multiplier = "2.5x" if days_until <= 21 else "1.8x"\n'
    '        lead_time_weeks = max(1, days_until // 7)\n'
    '        # The actual peak search surge happens in the final 3 weeks, not the whole period\n'
    '        peak_weeks = min(3, lead_time_weeks)\n'
    '        timing_str = (\n'
    '            f"{days_until} days away — this is prime time"\n'
    '            if days_until <= 21 else\n'
    '            f"{days_until} days away — the 3-week peak window starts soon"\n'
    '        )\n'
    '\n'
    '        body = (\n'
    '            f"{owner_salut}, {fest} is {timing_str}! "\n'
    '            f"Search demand for {cat_slug} in {locality} surges {surge_multiplier} in the "\n'
    '            f"final {peak_weeks} weeks before the festival. "\n'
    '            f"Want me to draft a festive promotional campaign featuring "\n'
    '            f"\'{active_offer_title or \'your signature festival package\'}\' "\n'
    '            f"and schedule it to go live at peak search time? Done in 2 min."\n'
    '        )'
)
if old_d in src:
    src = src.replace(old_d, new_d)
    print("FIX D: festival surge window improved")
    fixes += 1
else:
    print("FIX D NOT FOUND")

with open("composer.py", "w", encoding="utf-8") as f:
    f.write(src)

print(f"\nPatch 2 complete — {fixes} fixes applied.")
