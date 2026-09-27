"""Audit trigger payloads for key test cases."""
import json, sys, os
sys.stdout.reconfigure(encoding='utf-8')

expanded = 'dataset/expanded'
trigger_files = [
    'trg_046_dormant_with_vera_m_029_anand_restaura',
    'trg_025_dormancy_glamour',
    'trg_010_ipl_match_delhi',
    'trg_015_winback_rashmi',
    'trg_006_festival_diwali',
    'trg_061_festival_upcoming_m_037_pooja_gym_bang',
    'trg_016_kids_yoga_program_drafting',
    'trg_022_cde_webinar_dentists',
    'trg_002_compliance_dci_radiograph',
    'trg_012_milestone_mylari',
    'trg_041_milestone_reached_m_032_mukesh_restaur',
    'trg_008_curious_ask_studio11',
    'trg_021_unverified_gbp_sunrise',
    'trg_020_summer_demand_shift',
    'trg_066_recall_due_m_008_zenyoga_gym_ch',
]

for tf in trigger_files:
    for ext in ['.json']:
        path = os.path.join(expanded, 'triggers', tf + ext)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                t = json.load(f)
            print(f"=== {tf} ===")
            print(f"kind: {t['kind']}")
            print(f"payload: {json.dumps(t['payload'], ensure_ascii=False, indent=2)}")
            print()
