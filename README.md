# Lark Cash Advance (Local Travel) SLA Watchdog & Auto-Healing System
[![Edge Worker CI](https://github.com/markwlsn/cash-advance-local-travel/actions/workflows/ci.yml/badge.svg)](https://github.com/markwlsn/cash-advance-local-travel/actions/workflows/ci.yml)
[![Free Tier Egress](https://img.shields.io/badge/egress-%240.00%20free-blue.svg)]()

Production-grade two-tier serverless architecture synchronizing **Lark Approval v4**, **Lark AnyCross** (creation trigger only), **Cloudflare Workers**, and **Lark Base (Bitable)** for **Cash Advance Form - Travelling Expenses (Local)**.

---

## 1. Core Stack Identifiers

| Parameter | Identifier / Value | Description |
| :--- | :--- | :--- |
| **Lark Base Token** | `ExBjbp1ORa1bSDst0NOlcJMOgRc` | `Cash Advance Form - Travelling Expenses (Local)` |
| **Table 1 ID (Master)** | `tbl37NnVUPwWL5tL` | Native Approval-synced master table (33 fields + auto-healed `Vendor Bill No.` & `Check No.`) |
| **Table 2 ID (Step Log)** | `tblpD8bOXcSWTudq` | `Step Approver Log` (View `vewr6Pmy7e`, 52 standardized native fields, 9 stages) |
| **Approval Definition Code** | `56DB2AA0-15B5-4AE9-954A-2BD485F267F8` | `Cash Advance Form - Travelling Expenses (Local)` |
| **Dedicated Bot App ID** | `cli_aa75292d72b8df08` | `Cash Advance LT Bot` |
| **Cloudflare Worker** | `cash-advance-local-travel` | `https://cash-advance-local-travel.markwlsn.workers.dev` (Account `98aa9b41c7867464e61d89b0d86cf59b`) |
| **Lark AnyCross Project** | `7710042861424643854` | `Cash Advance (Local Travel) Bot` (Creation Trigger ONLY: `status = PENDING` → `GET /sync`) |
| **GitHub Repository** | `markwlsn/cash-advance-local-travel` | Source control & automated GitHub Actions CI |

---

## 2. The 9 Monitored Approval Stages

1. **Direct Supervisor (if none, enter requester name)** (`cdab9cee83f7969bc24bfcdcdd33e8aa`) — Phase 1
2. **Team Head (if none, enter requester name)** (`c1e48274b814fdce8dc77ddc6be0cd82`) — Phase 1
3. **Department Head** (`2bc64761cd7fa34d3905a13b982c73f2`) — Phase 1
4. **Accounting Processing** (`8197b572a369af49e3478390190dcf4f`) — Phase 2
5. **Booking of Flight** (`9fb7bf6d70a142917e3a01c4ba4db848`) — Phase 3 (`Is Flight Booking Required? = Yes`)
6. **Booking of Hotel** (`fb1f0c3e7fe4f2f0ea3f2b8a6e54704b`) — Phase 3 (Flight branch)
7. **Booking of Hotel (No Flight)** (`57f6a1eaf7360efadac5a69066df327e`) — Phase 3 (`Is Flight Booking Required? = No`)
8. **Treasury Processing** (`d9857f658e65147acddeb6004a31696d`) — Phase 4
9. **For Check Releasing** (`faed3a241c33d9d842fa39daf7ce19f1`) — Phase 4

---

## 3. Local Verification & Deployment

```bash
# Run unit & simulated integration tests
node test_cloudflare_worker_logic.js

# Preview or execute Table 2 schema standardization
python configure_table2_schema.py --dry-run
python configure_table2_schema.py

# Provision secret and deploy Worker
npx wrangler secret put LARK_APP_SECRET
npx wrangler deploy
```
