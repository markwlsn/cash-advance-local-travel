#!/usr/bin/env python3
"""
inspect_approval_and_fields.py
------------------------------
Read-only diagnostic script for Cash Advance (Local Travel):
1. Authenticates with Lark OpenAPI using LARK_APP_ID / LARK_APP_SECRET from .env
2. Verifies Bot access to Base ExBjbp1ORa1bSDst0NOlcJMOgRc (Table 1 & Table 2 fields)
3. Fetches sample Approval instances from Table 1 SourceIDs
4. Fetches the full Approval Definition (node_id -> node_name, form widget IDs)
"""

import base64
import json
import os
import sys
from pathlib import Path
import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load_dotenv(path: Path) -> dict:
    env = {}
    if not path.is_file():
        return env
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


DOTENV = load_dotenv(Path(__file__).resolve().parent / ".env")


def get_env(key: str, default: str = "") -> str:
    return os.getenv(key) or DOTENV.get(key) or default


APP_ID = get_env("LARK_APP_ID", "cli_aa75292d72b8df08")
APP_SECRET = get_env("LARK_APP_SECRET", "")
BASE_TOKEN = get_env("LARK_BASE_TOKEN", "ExBjbp1ORa1bSDst0NOlcJMOgRc")
MAIN_TABLE_ID = get_env("LARK_MAIN_TABLE_ID", "tbl37NnVUPwWL5tL")
LOG_TABLE_ID = get_env("LARK_LOG_TABLE_ID", "tblpD8bOXcSWTudq")


def get_token() -> str:
    res = requests.post(
        "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": APP_ID, "app_secret": APP_SECRET},
        timeout=15,
    ).json()
    if res.get("code") != 0:
        raise RuntimeError(f"Auth failed: {res}")
    return res["tenant_access_token"]


def decode_source_id(val) -> str:
    if isinstance(val, list) and val:
        raw = val[0].get("text", "") if isinstance(val[0], dict) else str(val[0])
    elif isinstance(val, str):
        raw = val
    else:
        return ""
    raw = raw.strip()
    if not raw:
        return ""
    try:
        dec = base64.b64decode(raw + "===").decode("utf-8", "ignore")
        if ":" in dec:
            return dec.split(":")[1].strip()
        return dec.strip()
    except Exception:
        return raw


def main():
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}
    print(f"[OK] Authenticated App {APP_ID}")

    # 1. Check Base Table 1 & Table 2 access
    for label, tid in [("Table 1 (Main)", MAIN_TABLE_ID), ("Table 2 (Step Log)", LOG_TABLE_ID)]:
        r = requests.get(
            f"https://open.larksuite.com/open-apis/bitable/v1/apps/{BASE_TOKEN}/tables/{tid}/fields?page_size=100",
            headers=headers,
            timeout=15,
        ).json()
        if r.get("code") != 0:
            print(f"[ERROR] {label} ({tid}) access failed: code={r.get('code')} msg={r.get('msg')}")
        else:
            items = r.get("data", {}).get("items", [])
            print(f"[OK] {label} ({tid}): {len(items)} fields accessible")
            if tid == LOG_TABLE_ID:
                type_counts = {}
                for f in items:
                    t = f.get("type")
                    type_counts[t] = type_counts.get(t, 0) + 1
                print(f"     Table 2 field type distribution: {type_counts}")

    # 2. Fetch first 10 records from Table 1 to inspect Approval Instances
    r_rec = requests.get(
        f"https://open.larksuite.com/open-apis/bitable/v1/apps/{BASE_TOKEN}/tables/{MAIN_TABLE_ID}/records?page_size=20",
        headers=headers,
        timeout=15,
    ).json()
    sample_codes = []
    if r_rec.get("code") == 0:
        items = r_rec.get("data", {}).get("items", [])
        total = r_rec.get("data", {}).get("total", len(items))
        print(f"[OK] Table 1 total records: {total}")
        for rec in items:
            fields = rec.get("fields", {})
            sid = decode_source_id(fields.get("SourceID"))
            if sid:
                sample_codes.append((sid, fields.get("Status"), fields.get("Is Flight Booking Required?"), fields.get("Is Hotel Booking Required?")))
    else:
        print(f"[WARN] Could not list Table 1 records: {r_rec.get('code')} {r_rec.get('msg')}")
        sample_codes = [
            ("629354AA-529A-4A0E-93C9-9A009C9EEE61", None, None, None),
            ("08268B3B-876C-4CA7-A641-65B4718CB82F", None, None, None),
            ("17D94BEB-BA3C-405B-839F-92FAF31BC48E", None, None, None),
        ]

    # 3. Inspect sample Approval Instances & discover approval_code + all node_ids
    approval_code = None
    observed_nodes = {}
    observed_widgets = {}
    for code, status, flight, hotel in sample_codes[:10]:
        ri = requests.get(
            f"https://open.larksuite.com/open-apis/approval/v4/instances/{code}",
            headers=headers,
            timeout=15,
        ).json()
        if ri.get("code") != 0:
            print(f"[ERROR] Instance {code}: code={ri.get('code')} msg={ri.get('msg')}")
            continue
        data = ri.get("data", {})
        if not approval_code:
            approval_code = data.get("approval_code")
            print(f"\n[OK] Discovered Approval Definition Code: {approval_code}")
            print(f"     Approval Name: {data.get('approval_name')}")
        for t in data.get("task_list", []):
            nid = t.get("node_id")
            nname = t.get("node_name")
            if nid:
                observed_nodes[nid] = nname
        for tl in data.get("timeline", []):
            nid = tl.get("node_key")
            if nid and nid not in observed_nodes:
                observed_nodes[nid] = tl.get("type")
        try:
            form_list = json.loads(data.get("form", "[]"))
            for w in form_list:
                wid = w.get("id")
                wname = w.get("name")
                if wid:
                    observed_widgets[wid] = (wname, w.get("type"))
        except Exception:
            pass

    print("\n--- OBSERVED TASK NODES FROM LIVE INSTANCES ---")
    for nid, nname in observed_nodes.items():
        print(f"  {nid} -> {nname}")

    # 4. Fetch full Approval Definition via /approvals/{approval_code}
    if approval_code:
        rd = requests.get(
            f"https://open.larksuite.com/open-apis/approval/v4/approvals/{approval_code}",
            headers=headers,
            timeout=15,
        ).json()
        if rd.get("code") != 0:
            print(f"[ERROR] Approval definition fetch failed: {rd.get('code')} {rd.get('msg')}")
        else:
            d = rd.get("data", {})
            print("\n--- FULL APPROVAL DEFINITION NODES ---")
            for n in d.get("node_list", []):
                print(f"  node_id={n.get('node_id')} | name={n.get('name')!r} | type={n.get('node_type')} | custom={n.get('custom_node_id')}")
            print("\n--- FORM WIDGETS (Vendor Bill / Check No / Travel Flags) ---")
            try:
                fw = json.loads(d.get("form", "[]"))
                for w in fw:
                    name = w.get("name", "")
                    if any(k in name.lower() for k in ["vendor", "check", "flight", "hotel", "total", "cash", "amount", "travel", "purpose"]):
                        print(f"  {w.get('id')} | {w.get('type')} | {name!r}")
            except Exception as e:
                print("Form parse error:", e)


if __name__ == "__main__":
    main()
