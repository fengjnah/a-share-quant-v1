"""CFFEX member-holdings module for the existing M3 page.

Reads stored CFFEX reports from the workbench's explicit read-only connection.
Standalone test use still requires explicit test settings; no mock fallback.
"""
from dataclasses import replace
from pathlib import Path

import pandas as pd
import streamlit as st

from ai_trade.market_analysis_cffex_db import cffex_report, cffex_net_position, open_test_db

DB_ENV = "AI_TRADE_M3_TEST_DB_PATH"
EVIDENCE_ENV = "AI_TRADE_M3_TEST_EVIDENCE_ROOT"


def _open_test_db():
    import os
    db_path = os.environ.get(DB_ENV)
    if not db_path:
        return None, None, f"{DB_ENV} not set; no test database available."
    evidence_root = os.environ.get(EVIDENCE_ENV)
    try:
        db, _ = open_test_db(Path(db_path), Path(evidence_root) if evidence_root else None)
        return db, Path(evidence_root) if evidence_root else None, None
    except Exception as exc:
        return None, None, f"test database open failed: {type(exc).__name__}: {exc}"


def _report_state(db, variety, trade_date, evidence_root):
    """Return (report, error_message); exactly one is non-None."""
    if db is None:
        return None, "No test database connected."
    try:
        report = cffex_report(db, variety, trade_date, evidence_root=evidence_root)
    except Exception as exc:
        return None, f"Report readback failed: {type(exc).__name__}: {exc}"
    if report is None:
        return None, (f"No stored CFFEX report for {variety} on {trade_date}; "
                      "database may be empty or the date not yet collected. "
                      "Missing file does not mean closed session or zero holdings.")
    return report, None


def render_cffex_holdings(db=None):
    """Render the CFFEX member-holdings module; call from the M3 page."""
    st.subheader("CFFEX Member Holdings (IF / IH / IC / IM)")
    st.caption("Data is exchange-published Top-N member seat holdings; "
               "it is not final-client or own-account position, and not a trading signal.")

    if db is None:
        db, evidence_root, db_error = _open_test_db()
        if db_error:
            st.error(db_error)
            return
        st.info(f"Connected to test database: {db.config.path}")
        st.caption("Standalone isolated test database; not formal workbench data.")
    else:
        from ai_trade.storage.db import Database
        # Reopen with actual SQLite mode=ro even if a caller supplied a writable
        # handle. Do not initialize, migrate or consult test database settings.
        try:
            db = Database(replace(db.config, read_only=True, require_existing=True))
        except (AttributeError, TypeError, ValueError) as exc:
            st.error(f"Workbench database binding invalid: {type(exc).__name__}")
            return
        evidence_root = Path(db.config.path).parent / 'evidence'
        st.info(f"Connected to workbench database: {db.config.path}")
        st.caption("只读工作台已保存数据；不联网采集。原始 Top-N 展示不解除来源认证或研究准入门禁。")

    variety = st.selectbox("Variety", ["IF", "IH", "IC", "IM"],
                          help="CFFEX stock index futures varieties")
    trade_date = st.text_input("Trade date (YYYY-MM-DD)", value="2026-10-23")

    report, error = _report_state(db, variety, trade_date, evidence_root)
    if error:
        if error.startswith('No stored CFFEX report for '):
            st.info(error)
        else:
            st.error(error)
        return

    st.metric("Stored rows", report["row_count"])
    st.metric("Version", report["version_id"][:16])
    st.caption(
        f"Trade date: {report['trade_date']}  |  "
        f"Quality status (storage): {report['quality_status']}  |  "
        f"Evidence kind: {report['evidence_kind']}  |  "
        f"Ingested at: {report['ingested_at']}  |  "
        f"Available at: {report['available_at']}  |  "
        f"Source: {report['source']}\n"
        f"Payload SHA-256: {report['payload_sha256']}  |  "
        f"Contracts: {', '.join(report['contracts'])}")
    st.caption("Storage quality is not source/publication/scope certification; M3 core admission remains unchanged.")
    if report.get("warnings"):
        st.warning("; ".join(report["warnings"]))

    # Per-contract, per-member table
    contract_options = report["contracts"] + ["__select__"]
    selected_contract = st.selectbox("Contract", contract_options)

    rows = report["rows"]
    if selected_contract != "__select__":
        rows = [r for r in rows if r["contract"] == selected_contract]

    df = pd.DataFrame(rows).sort_values(
        by=["contract", "side", "rank"],
        key=lambda s: s.map({"long": 0, "short": 1, "volume": 2}) if s.name == "side" else s
    )
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.caption("Open interest / volume values are shown only when `open_interest_known` or "
               "`volume_known` is True; otherwise the field is UNKNOWN (not zero).")

    # Net position for a specific member
    col1, col2, col3 = st.columns(3)
    with col1:
        member = st.text_input("Member (exact name from the table above)",
                              placeholder="e.g. 中信期货(代客)")
        available_members = sorted({r["member"] for r in rows if r["member"]})
        if available_members:
            member_pick = st.selectbox("Or pick a member", available_members,
                                       key="cffex-member-pick")
        else:
            member_pick = ""
        if member:
            member = member.strip()
        elif member_pick:
            member = member_pick
    with col2:
        target_contract = st.selectbox("Net position contract", ["__select__"] + report["contracts"])
    with col3:
        scope = st.selectbox("Member scope", ["代客", "自营", "代客+自营", "unknown"],
                             help="Net is computed only when both long and short "
                                   "sides for the member are in the Top-N disclosure")

    if member and target_contract != "__select__":
        net = cffex_net_position(report["rows"], member, target_contract, scope)
        st.write(f"**Net position ({member} on {target_contract}, scope={scope}):**")
        if net["net"] is None:
            st.warning(net["note"])
        else:
            st.metric("Net OI (long - short)", net["net"])
        st.caption(f"Long OI: {net['long_oi']}  |  Short OI: {net['short_oi']}")
        st.caption(net["note"])
