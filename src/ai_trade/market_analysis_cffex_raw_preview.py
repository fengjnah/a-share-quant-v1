"""Isolated TASK-005 preparation; intentionally not wired into formal M3.

Only synthetic evidence in an explicitly supplied test database is supported.
No flag in this module authorizes display of real raw evidence. A formal
adapter requires a separately approved display contract and independent review.
"""
from dataclasses import asdict, replace

from ai_trade.m3_store_catalog import CatalogRepository
from ai_trade.m3_store_values import one, rows
from ai_trade.market_data.cffex_rankings import parse
from ai_trade.market_data.cffex_rankings_models import CffexRankingsRequest
from ai_trade.storage.db import Database


def _test_reader(database):
    # Check before making any connection. Never use environment/path fallbacks.
    if database.config.environment != "test":
        raise ValueError("RAW_PREVIEW_BLOCKED: synthetic test database required")
    return Database(replace(database.config, read_only=True, require_existing=True))


def synthetic_attempts(database):
    reader = _test_reader(database)
    with reader.connection() as conn:
        attempts = rows(conn, "ingestion_attempts")
        evidence = {e["evidence_id"]: e for e in rows(conn, "evidence_objects")}
        sources = {s["source_id"]: s for s in rows(conn, "data_sources")}
    return sorted([
        a for a in attempts
        if evidence.get(a["evidence_id"], {}).get("evidence_kind") == "synthetic"
        and sources[a["source_id"]]["dataset_key"] == "cffex_rankings"
    ], key=lambda a: (a["finished_at"], a["attempt_id"]))


def load_synthetic_preview(database, evidence_root, attempt_id):
    """Verify archived bytes then parse; never build a time-certified record."""
    reader = _test_reader(database)
    repo = CatalogRepository(reader, evidence_root)
    with reader.connection() as conn:
        attempt = one(conn, "ingestion_attempts", attempt_id=attempt_id)
        evidence = one(conn, "evidence_objects", evidence_id=attempt["evidence_id"])
        source = one(conn, "data_sources", source_id=attempt["source_id"])
        if evidence["evidence_kind"] != "synthetic":
            raise ValueError("RAW_PREVIEW_BLOCKED: real evidence display is not authorized")
        if source["dataset_key"] != "cffex_rankings":
            raise ValueError("RAW_PREVIEW_BLOCKED: wrong source dataset")
        parameters = attempt["request_json"]["parameters"]
        request = CffexRankingsRequest("CFFEX", parameters["variety"], parameters["trade_date"])
        request.validate()
        # Existing Evidence API checks path containment, byte limit, size and hash.
        payload = repo.evidence_bytes(evidence["evidence_id"], conn)
    rank_format, parsed = parse(payload, request)
    return {
        "attempt_id": attempt_id, "variety": request.variety,
        "trade_date": request.trade_date, "format": rank_format,
        "source": source, "evidence_id": evidence["evidence_id"],
        "payload_sha256": evidence["sha256"], "hash_status": "MATCH",
        "captured_at": evidence["captured_at"],
        "attempt_finished_at": attempt["finished_at"],
        "rows": [dict(asdict(row), side=row.side.value,
                      member_scope=row.member_scope.value) for row in parsed],
    }


def filter_preview_rows(preview, *, contract=None, member=None, side=None):
    return [row for row in preview["rows"]
            if (contract is None or row["contract"] == contract)
            and (member is None or row["member"] == member)
            and (side is None or row["side"] == side)]


def render_synthetic_raw_preview(database, evidence_root, *, enabled=False):
    """Offline UI preparation. `enabled` is a test control, not an admission."""
    import pandas as pd
    import streamlit as st

    st.subheader("原始证据预览｜未经独立来源认证")
    st.warning("UNVERIFIED | NOT ADMITTED | NOT FOR RESEARCH OR TRADING")
    st.info("SYNTHETIC TEST FIXTURE：隔离合成测试，不是已采集的真实持仓。")
    st.caption("当前内容仅反映隔离测试保存的合成原始响应及其解析结果，"
               "不代表已通过 CFFEX 官方来源认证，不作为交易信号。")
    if not enabled:
        st.info("预览默认关闭；正式原始证据展示授权仍 BLOCKED。")
        return
    try:
        _test_reader(database)
    except ValueError as exc:
        st.error(str(exc))
        return
    if not st.checkbox("启用合成证据预览", value=False, key="raw-preview-enable"):
        return
    try:
        attempts = synthetic_attempts(database)
        variety = st.selectbox("预览品种", ["IF", "IH", "IC", "IM"])
        matching = [a for a in attempts
                    if a["request_json"]["parameters"].get("variety") == variety]
        dates = sorted({a["request_json"]["parameters"]["trade_date"] for a in matching})
        if not dates:
            st.info("无合成证据；缺失不表示持仓为零。")
            return
        day = st.selectbox("预览交易日期", dates)
        ids = [a["attempt_id"] for a in matching
               if a["request_json"]["parameters"]["trade_date"] == day]
        selected = st.selectbox("预览采集尝试", ids)
        preview = load_synthetic_preview(database, evidence_root, selected)
    except (ValueError, KeyError, OSError) as exc:
        st.error(f"原始证据预览失败：{type(exc).__name__}；未展示数值。")
        return
    source = preview["source"]
    st.write({"source_id": source["source_id"], "provider": source["provider"],
              "endpoint": source["endpoint_key"], "adapter": source["adapter_version"],
              "attempt_id": selected, "evidence_id": preview["evidence_id"],
              "captured_at": preview["captured_at"],
              "attempt_finished_at": preview["attempt_finished_at"],
              "payload_sha256": preview["payload_sha256"],
              "hash_status": preview["hash_status"]})
    st.caption("captured_at 为存档采集时间；UNKNOWN 保留为空。"
               "attempt_finished_at 是尝试结束时间，不能当作历史首次可得时间。")
    all_rows = preview["rows"]
    contract = st.selectbox("预览合约", ["全部"] + sorted({r["contract"] for r in all_rows}))
    member = st.selectbox("预览会员", ["全部"] + sorted({r["member"] for r in all_rows}))
    side = st.selectbox("预览排名类别", ["全部", "volume", "long", "short"])
    selected_rows = filter_preview_rows(preview, contract=None if contract == "全部" else contract,
                                        member=None if member == "全部" else member,
                                        side=None if side == "全部" else side)
    if not selected_rows:
        st.info("筛选无匹配；不补零或推断榜外持仓。")
        return
    st.dataframe(pd.DataFrame(selected_rows).sort_values(["contract", "side", "rank"]),
                 hide_index=True, use_container_width=True)
    st.caption("成交量与多/空持仓分别展示，缺失为 UNKNOWN；无研究或交易准入。")
