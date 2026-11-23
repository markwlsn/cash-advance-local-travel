#!/usr/bin/env python3
"""
configure_table2_schema.py
--------------------------
Configures and standardizes Lark Base schema for Cash Advance (Local Travel):
Base Token: ExBjbp1ORa1bSDst0NOlcJMOgRc
Table 1: tbl37NnVUPwWL5tL (Cash Advance Form - Travelling Expenses (Local))
Table 2: tblpD8bOXcSWTudq (Step Approver Log)

Table 2 was initially created with 50 Type 1 (Text) columns + 1 AutoNumber (ID) and no SourceID.
This script converts all Table 2 fields to mirror the production 2-table SLA Watchdog schema:
1. Enforces Standard Header Field Types (Zero Type 19 cross-table lookup bugs):
   - Task ID (fldfoJQZGO) -> Type 15 (URL)
   - Overall Status (fldsMW9FB2) -> Type 3 (SingleSelect with 11 canonical options)
   - Requester (fldMwbJ7rT) -> Type 11 (User, multiple=True)
   - SourceID -> Created as Type 1 (Text) if missing
2. Converts All 45 Stage Columns (9 Stages x 5 Columns) in Dependency Order:
   - <Stage> Approver -> Type 11 (User, multiple=True)
   - <Stage> Start -> Type 5 (DateTime, yyyy/MM/dd HH:mm)
   - <Stage> End -> Type 5 (DateTime, yyyy/MM/dd HH:mm)
   - <Stage> Duration -> Type 20 (Formula referencing exact Start & End field IDs)
   - <Stage> Action -> Type 3 (SingleSelect with 12 canonical action options)

Usage:
  python configure_table2_schema.py --dry-run   # Preview all schema mutations without calling PUT/POST
  python configure_table2_schema.py             # Execute live schema standardization (requires LARK_APP_SECRET)
"""

import argparse
import os
import sys
import time
from pathlib import Path
import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load_dotenv_file(dotenv_path: Path) -> dict:
    env_vars = {}
    if not dotenv_path.is_file():
        return env_vars
    for raw_line in dotenv_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env_vars[k.strip()] = v.strip().strip('"').strip("'")
    return env_vars


_DOTENV = load_dotenv_file(Path(__file__).resolve().parent / ".env")


def get_env(key: str, default: str = "") -> str:
    return os.getenv(key) or _DOTENV.get(key) or default


APP_ID = get_env("LARK_APP_ID", "cli_aa75292d72b8df08")
APP_SECRET = get_env("LARK_APP_SECRET", "")
BASE_TOKEN = get_env("LARK_BASE_TOKEN", "ExBjbp1ORa1bSDst0NOlcJMOgRc")
MAIN_TABLE_ID = get_env("LARK_MAIN_TABLE_ID", "tbl37NnVUPwWL5tL")
LOG_TABLE_ID = get_env("LARK_LOG_TABLE_ID", "tblpD8bOXcSWTudq")

# The 9 Canonical Stages for Cash Advance (Local Travel) Table 2 (tblpD8bOXcSWTudq)
ALL_9_STAGES = [
    "Direct Supervisor (if none, enter requester name)",
    "Team Head (if none, enter requester name)",
    "Department Head",
    "Accounting Processing",
    "Booking of Flight",
    "Booking of Hotel",
    "Booking of Hotel (No Flight)",
    "Treasury Processing",
    "For Check Releasing",
]

KNOWN_HEADER_FIELD_IDS = {
    "ID": "fldRELyBuz",
    "Approval Instance Code": "fldVFdNRwd",
    "Request No": "fld1WHwWjk",
    "Task ID": "fldfoJQZGO",
    "Overall Status": "fldsMW9FB2",
    "Requester": "fldMwbJ7rT",
}

# Complete verified 45-field ID map for Table 2 (tblpD8bOXcSWTudq)
KNOWN_STAGE_FIELD_IDS = {
    "Direct Supervisor (if none, enter requester name)": {
        "approver": "fldtRKIMJr",
        "start": "fldNGhJvS4",
        "end": "fldd6SoKkA",
        "dur": "fldFqimN77",
        "action": "fld95psWCU",
    },
    "Team Head (if none, enter requester name)": {
        "approver": "fldmVP7gle",
        "start": "fldd2TSpyd",
        "end": "fldakax5AU",
        "dur": "fldiFJDHaW",
        "action": "fld0a84Mvr",
    },
    "Department Head": {
        "approver": "fldlcYzEh0",
        "start": "fldLKZUZPX",
        "end": "fldV52ZtUP",
        "dur": "fld0PbIQob",
        "action": "flddxrNL5b",
    },
    "Accounting Processing": {
        "approver": "fldHUDUF3I",
        "start": "fldLPoTHZi",
        "end": "fldEvs0dPL",
        "dur": "fldy6M7d1S",
        "action": "fldYXBRpFi",
    },
    "Booking of Flight": {
        "approver": "fldUsvyS6A",
        "start": "fldqdYNYcc",
        "end": "fldHTACLJy",
        "dur": "fldTBbspts",
        "action": "fldSTnXt3O",
    },
    "Booking of Hotel": {
        "approver": "fld0b9vbHq",
        "start": "fldGsY05HK",
        "end": "fldhqClED8",
        "dur": "fldWb2MldB",
        "action": "fldPToy8d9",
    },
    "Booking of Hotel (No Flight)": {
        "approver": "fldr2j7hF8",
        "start": "fldBFxqyRK",
        "end": "fldcA9h1nc",
        "dur": "fldJCwirLI",
        "action": "fldR8SRYy1",
    },
    "Treasury Processing": {
        "approver": "fld6KUnk7d",
        "start": "fldKZHBw0v",
        "end": "fldsl3tPt2",
        "dur": "fldKvSF4IB",
        "action": "fldRgQjyjO",
    },
    "For Check Releasing": {
        "approver": "fldnejR03X",
        "start": "fldXsVwcHa",
        "end": "fldUsedObs",
        "dur": "fldhtQssVw",
        "action": "fldWJ3TA8V",
    },
}

ACTION_OPTIONS = [
    {"name": "PENDING", "color": 0},
    {"name": "APPROVED", "color": 1},
    {"name": "COMPLETED", "color": 2},
    {"name": "RESOLVED", "color": 3},
    {"name": "NOT APPLICABLE", "color": 4},
    {"name": "AUTO-PASSED", "color": 5},
    {"name": "REJECTED", "color": 6},
    {"name": "RECALLED", "color": 7},
    {"name": "CANCELLED", "color": 8},
    {"name": "DONE", "color": 9},
    {"name": "TRANSFERRED", "color": 10},
    {"name": "INVALID_STATUS", "color": 11},
]

OVERALL_STATUS_OPTIONS = [
    {"name": "Phase 1: Line & Dept Review", "color": 0},
    {"name": "Phase 2: Accounting Processing", "color": 1},
    {"name": "Phase 3: Travel Booking", "color": 2},
    {"name": "Phase 4: Treasury Processing & Check Release", "color": 3},
    {"name": "COMPLETED: Cash Advance Released", "color": 5},
    {"name": "Approved", "color": 6},
    {"name": "Under Review", "color": 39},
    {"name": "Pending", "color": 36},
    {"name": "Rejected", "color": 44},
    {"name": "Recalled", "color": 44},
    {"name": "Canceled", "color": 44},
]


DEFAULT_SLA_WORKING_DAYS = 10


def build_duration_formula(table_id: str, start_fid: str, end_fid: str) -> str:
    return (
        f"IF(OR(ISBLANK(bitable::$table[{table_id}].$field[{start_fid}]),"
        f"ISBLANK(bitable::$table[{table_id}].$field[{end_fid}]),"
        f"bitable::$table[{table_id}].$field[{end_fid}]<bitable::$table[{table_id}].$field[{start_fid}]),"
        f'"",DATEDIF(bitable::$table[{table_id}].$field[{start_fid}],'
        f'bitable::$table[{table_id}].$field[{end_fid}],"d")&" day "&'
        f"TEXT(bitable::$table[{table_id}].$field[{end_fid}]-"
        f'bitable::$table[{table_id}].$field[{start_fid}],"hh:mm:ss"))'
    )


def build_sla_status_formula(
    table_id: str, start_fid: str, end_fid: str, sla_days: int = DEFAULT_SLA_WORKING_DAYS
) -> str:
    return (
        f"IF(OR(ISBLANK(bitable::$table[{table_id}].$field[{start_fid}]),"
        f"ISBLANK(bitable::$table[{table_id}].$field[{end_fid}]),"
        f"bitable::$table[{table_id}].$field[{end_fid}]<bitable::$table[{table_id}].$field[{start_fid}]),"
        f'"",IF(NETWORKDAYS(bitable::$table[{table_id}].$field[{start_fid}],'
        f'bitable::$table[{table_id}].$field[{end_fid}])-1<={sla_days},"Within SLA","Over SLA"))'
    )


def get_tenant_access_token() -> str:
    if not APP_SECRET or APP_SECRET == "replace_with_lark_app_secret":
        raise RuntimeError(
            "Missing LARK_APP_SECRET. Set LARK_APP_SECRET in environment or .env before running live migration."
        )
    url = "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal"
    res = requests.post(url, json={"app_id": APP_ID, "app_secret": APP_SECRET}, timeout=15).json()
    if res.get("code") != 0:
        raise RuntimeError(f"Failed to get tenant token: {res}")
    return res["tenant_access_token"]


def fetch_table_fields(token: str, table_id: str) -> tuple[dict, dict]:
    url = f"https://open.larksuite.com/open-apis/bitable/v1/apps/{BASE_TOKEN}/tables/{table_id}/fields?page_size=100"
    res = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=15).json()
    if res.get("code") != 0:
        raise RuntimeError(f"Failed to list fields for {table_id}: {res}")
    items = res.get("data", {}).get("items", [])
    by_name = {f["field_name"]: f for f in items}
    by_id = {f["field_id"]: f for f in items}
    return by_name, by_id


def update_field(token: str, table_id: str, field_id: str, payload: dict, dry_run: bool = False) -> dict:
    if dry_run:
        return {"code": 0, "msg": "DRY_RUN"}
    url = f"https://open.larksuite.com/open-apis/bitable/v1/apps/{BASE_TOKEN}/tables/{table_id}/fields/{field_id}"
    return requests.put(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=20,
    ).json()


def create_field(token: str, table_id: str, payload: dict, dry_run: bool = False) -> dict:
    if dry_run:
        return {"code": 0, "msg": "DRY_RUN", "data": {"field": {"field_id": "fld_DRY_RUN_SOURCEID"}}}
    url = f"https://open.larksuite.com/open-apis/bitable/v1/apps/{BASE_TOKEN}/tables/{table_id}/fields"
    return requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=20,
    ).json()


def build_offline_field_maps() -> tuple[dict, dict]:
    by_name = {}
    by_id = {}
    for name, fid in KNOWN_HEADER_FIELD_IDS.items():
        f_type = 1005 if name == "ID" else 1
        obj = {"field_id": fid, "field_name": name, "type": f_type}
        by_name[name] = obj
        by_id[fid] = obj
    for stage in ALL_9_STAGES:
        s_map = KNOWN_STAGE_FIELD_IDS[stage]
        for suffix, key in [
            ("Approver", "approver"),
            ("Start", "start"),
            ("End", "end"),
            ("Duration", "dur"),
            ("Action", "action"),
        ]:
            fname = f"{stage} {suffix}"
            fid = s_map[key]
            obj = {"field_id": fid, "field_name": fname, "type": 1}
            by_name[fname] = obj
            by_id[fid] = obj
    return by_name, by_id


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Standardize Lark Base Table 2 (tblpD8bOXcSWTudq) schema for Cash Advance (Local Travel)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview all 48 field type conversions and 1 field creation (SourceID) without modifying live Bitable.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dry_run = args.dry_run
    mode_banner = "DRY-RUN PREVIEW (No Live Bitable Mutations)" if dry_run else "LIVE EXECUTION"

    print("=" * 80)
    print(f"Configuring Cash Advance (Local Travel) Table 2 Schema Standard [{mode_banner}]")
    print(f"Base Token      : {BASE_TOKEN}")
    print(f"Table 1 (Master): {MAIN_TABLE_ID}")
    print(f"Table 2 (Log)   : {LOG_TABLE_ID}")
    print(f"App ID          : {APP_ID}")
    print("=" * 80)

    token = ""
    if dry_run and (not APP_SECRET or APP_SECRET == "replace_with_lark_app_secret"):
        print("[*] Dry-run mode without LARK_APP_SECRET: using verified offline schema map (51 fields).")
        fields_by_name, fields_by_id = build_offline_field_maps()
    else:
        token = get_tenant_access_token()
        fields_by_name, fields_by_id = fetch_table_fields(token, LOG_TABLE_ID)
        print(f"[*] Fetched {len(fields_by_id)} live fields from Table 2 ({LOG_TABLE_ID}).")

    errors = []

    # Step 1: Header Columns & SourceID
    print("\n[1/2] Enforcing Standard Types on Header Columns (Zero Type 19 Lookups)...")
    header_conversions = [
        (
            "Overall Status",
            KNOWN_HEADER_FIELD_IDS["Overall Status"],
            {"field_name": "Overall Status", "type": 3, "property": {"options": OVERALL_STATUS_OPTIONS}},
            "Type 3 (SingleSelect, 11 options)",
        ),
        (
            "Task ID",
            KNOWN_HEADER_FIELD_IDS["Task ID"],
            {"field_name": "Task ID", "type": 15},
            "Type 15 (URL)",
        ),
        (
            "Requester",
            KNOWN_HEADER_FIELD_IDS["Requester"],
            {"field_name": "Requester", "type": 11, "property": {"multiple": True}},
            "Type 11 (User, multiple=True)",
        ),
    ]

    for fname, known_fid, payload, desc in header_conversions:
        f_obj = fields_by_id.get(known_fid) or fields_by_name.get(fname)
        if not f_obj:
            msg = f"Missing header field '{fname}' ({known_fid})"
            print(f"  [!] {msg}")
            errors.append(msg)
            continue
        fid = f_obj["field_id"]
        res = update_field(token, LOG_TABLE_ID, fid, payload, dry_run=dry_run)
        if res.get("code") in [0, 1254606]:
            status = "DRY-RUN OK" if dry_run else "OK"
        else:
            status = f"Error {res.get('code')}: {res.get('msg')}"
            errors.append(f"{fname} ({fid}): {status}")
        print(f"  -> {fname:<24} ({fid}) -> {desc}: {status}")
        if not dry_run:
            time.sleep(0.15)

    has_source_id = "SourceID" in fields_by_name or any(
        f.get("field_name") == "SourceID" for f in fields_by_id.values()
    )
    if not has_source_id:
        res = create_field(token, LOG_TABLE_ID, {"field_name": "SourceID", "type": 1}, dry_run=dry_run)
        if res.get("code") == 0:
            new_fid = res.get("data", {}).get("field", {}).get("field_id", "created")
            status = f"DRY-RUN OK ({new_fid})" if dry_run else f"OK ({new_fid})"
        else:
            status = f"Error {res.get('code')}: {res.get('msg')}"
            errors.append(f"SourceID create: {status}")
        print(f"  -> {'SourceID':<24} (CREATE)    -> Type 1 (Text): {status}")
        if not dry_run:
            time.sleep(0.15)
    else:
        print(f"  -> {'SourceID':<24} (EXISTING)  -> Type 1 (Text): Already exists")

    # Step 2: Convert All 45 Stage Columns (9 Stages x 5 Columns)
    print("\n[2/2] Converting All 45 Stage Columns Across 9 Stages (Approver -> Start -> End -> Duration -> Action)...")
    if not dry_run:
        fields_by_name, fields_by_id = fetch_table_fields(token, LOG_TABLE_ID)

    for idx, stage in enumerate(ALL_9_STAGES, start=1):
        known = KNOWN_STAGE_FIELD_IDS[stage]
        approver_fid = (
            known["approver"]
            if known["approver"] in fields_by_id
            else (fields_by_name.get(f"{stage} Approver") or {}).get("field_id")
        )
        start_fid = (
            known["start"]
            if known["start"] in fields_by_id
            else (fields_by_name.get(f"{stage} Start") or {}).get("field_id")
        )
        end_fid = (
            known["end"]
            if known["end"] in fields_by_id
            else (fields_by_name.get(f"{stage} End") or {}).get("field_id")
        )
        dur_fid = (
            known["dur"]
            if known["dur"] in fields_by_id
            else (fields_by_name.get(f"{stage} Duration") or {}).get("field_id")
        )
        action_fid = (
            known["action"]
            if known["action"] in fields_by_id
            else (fields_by_name.get(f"{stage} Action") or {}).get("field_id")
        )

        print(f"\n  Stage {idx}/9: {stage}")
        if not all([approver_fid, start_fid, end_fid, dur_fid, action_fid]):
            msg = (
                f"Missing stage field IDs for '{stage}': "
                f"Approver={approver_fid}, Start={start_fid}, End={end_fid}, Duration={dur_fid}, Action={action_fid}"
            )
            print(f"    [!] {msg}")
            errors.append(msg)
            continue

        dur_formula = build_duration_formula(LOG_TABLE_ID, start_fid, end_fid)

        stage_mutations = [
            (
                f"{stage} Approver",
                approver_fid,
                {"field_name": f"{stage} Approver", "type": 11, "property": {"multiple": True}},
                "Type 11 (User)",
            ),
            (
                f"{stage} Start",
                start_fid,
                {"field_name": f"{stage} Start", "type": 5, "property": {"date_formatter": "yyyy/MM/dd HH:mm"}},
                "Type 5 (DateTime)",
            ),
            (
                f"{stage} End",
                end_fid,
                {"field_name": f"{stage} End", "type": 5, "property": {"date_formatter": "yyyy/MM/dd HH:mm"}},
                "Type 5 (DateTime)",
            ),
            (
                f"{stage} Duration",
                dur_fid,
                {"field_name": f"{stage} Duration", "type": 20, "property": {"formula_expression": dur_formula}},
                "Type 20 (Formula)",
            ),
            (
                f"{stage} Action",
                action_fid,
                {"field_name": f"{stage} Action", "type": 3, "property": {"options": ACTION_OPTIONS}},
                "Type 3 (SingleSelect)",
            ),
        ]

        for col_name, fid, payload, desc in stage_mutations:
            res = update_field(token, LOG_TABLE_ID, fid, payload, dry_run=dry_run)
            if res.get("code") in [0, 1254606]:
                status = "DRY-RUN OK" if dry_run else "OK"
            else:
                status = f"Error {res.get('code')}: {res.get('msg')}"
                errors.append(f"{col_name} ({fid}): {status}")
            print(f"    -> {col_name:<58} ({fid}) -> {desc:<21}: {status}")
            if not dry_run:
                time.sleep(0.15)

        # Stage <Stage> Status (Type 20 SLA Formula: Within SLA / Over SLA)
        status_col_name = f"{stage} Status"
        sla_formula = build_sla_status_formula(LOG_TABLE_ID, start_fid, end_fid, DEFAULT_SLA_WORKING_DAYS)
        status_payload = {
            "field_name": status_col_name,
            "type": 20,
            "property": {"formula_expression": sla_formula},
        }
        existing_status = fields_by_name.get(status_col_name)
        if existing_status:
            sfid = existing_status["field_id"]
            res = update_field(token, LOG_TABLE_ID, sfid, status_payload, dry_run=dry_run)
            action_tag = sfid
        else:
            res = create_field(token, LOG_TABLE_ID, status_payload, dry_run=dry_run)
            action_tag = res.get("data", {}).get("field", {}).get("field_id", "CREATE")
        if res.get("code") in [0, 1254606]:
            status = "DRY-RUN OK" if dry_run else f"OK ({action_tag})"
        else:
            status = f"Error {res.get('code')}: {res.get('msg')}"
            errors.append(f"{status_col_name} ({action_tag}): {status}")
        print(f"    -> {status_col_name:<58} ({action_tag}) -> {'Type 20 (SLA Formula)':<21}: {status}")
        if not dry_run:
            time.sleep(0.15)

    print("\n" + "=" * 80)
    if errors:
        print(f"[!] Completed with {len(errors)} error(s):")
        for err in errors:
            print(f"  - {err}")
        print("=" * 80)
        return 1

    print(f"Table 2 Schema Standardization Completed Successfully [{mode_banner}]")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(main())
