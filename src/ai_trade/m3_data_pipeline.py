"""Read-only M3 evidence composition. Admission belongs exclusively to M3 core.

Transport PASS is deliberately separate from certification. No receipt is issued
here, no historical timestamp is inferred, and raw CFFEX CSV is not a read record.
The envelope is a candidate handoff while independent core review is pending.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import pandas as pd

from ai_trade.market_analysis_contract import CALCULATION_VERSION, CONTRACT_VERSION, Request, SourceEvidence
from ai_trade.market_analysis_core import (
    breadth_diagnostic, cffex_diagnostic, environment_diagnostic,
    fear_greed_diagnostic, price_diagnostics,
)
from ai_trade.market_analysis_data import INDEX_SOURCE, BREADTH_SOURCE
from ai_trade.market_data.cffex_rankings_models import MemberScope

VERSION = "m3-pipeline-evidence-v1"
BASELINE = "94cdd487bfd4633ecc2f002aad014f98dec961a5"
CORE_REVIEW = {"state": "PENDING", "issue": "https://github.com/fengjnah/a-share-quant-v1/issues/37",
               "review_head": "d60fa8809a248cb4b4a63ed4ee514296645bed2b"}

# Field units are reviewed mapping declarations, not certification of a vendor.
SOURCE_INVENTORY = {
    "sina_index": dict(provider="Sina / AKShare 1.19.1", interface="stock_zh_index_daily",
        endpoint="https://finance.sina.com.cn/realstock/company/sh000300/hisdata/klc_kl.js",
        fields={"trade_date": "Shanghai date", "open/high/low/close": "index points"},
        history="SDK history response; local retained sample <=550 completed dates; calendar denominator UNKNOWN"),
    "eastmoney_stock": dict(provider="Eastmoney / AKShare 1.19.1", interface="stock_zh_a_hist",
        endpoint="https://push2his.eastmoney.com/api/qt/stock/kline/get",
        fields={"trade_date": "Shanghai date", "OHLC": "CNY/share", "volume": "shares (SDK lots x100 in adapter)", "amount": "CNY"},
        history="Explicit 600000.SH, 2026-10-14..15, daily, unadjusted; not an identity/history certification"),
    "tencent_stock": dict(provider="Tencent / AKShare 1.19.1", interface="stock_zh_a_hist_tx",
        endpoint="https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get",
        fields={"trade_date": "Shanghai date", "OHLC": "CNY/share", "volume": "shares (SDK normalizes)", "amount": "CNY (SDK normalizes)"},
        history="Same explicit two-date sample; SDK start-year probe + one year page, not bounded server date filtering"),
    "legu_breadth": dict(provider="Legulegu / AKShare 1.19.1", interface="stock_market_activity_legu",
        endpoint="https://legulegu.com/stockdata/market-activity",
        fields={"advances/declines/flat/limit_up/limit_down": "security count", "trade_date": "source statistical date"},
        history="Current aggregate snapshot only; no point-in-time universe/partition/market amount"),
    "cffex_rankings": dict(provider="CFFEX", interface="CffexRankingsClient + parse",
        endpoint="https://www.cffex.com.cn/sj/ccpm/202610/16/IF_1.csv",
        fields={"contract/member/member_scope/side/rank": "explicit publication identity",
                "open_interest/open_interest_change/volume/volume_change": "source contract counts, not A-share units"},
        history="One IF date only; raw observation cannot replace certified calendar/time/version record"),
    "all_a_turnover": dict(provider="UNKNOWN", interface=None, endpoint=None,
        fields={"market_amount_cny": "CNY, full-A scope; finite nonnegative supported numeric scalar"},
        history="No registered full-A historical turnover source; index/stock amount is not a substitute"),
    "cn_a_calendar": dict(provider="UNKNOWN", interface="SQLiteTradingCalendar (storage/query only)", endpoint=None,
        fields={"exchange/session_date/is_trading_day": "sourced dated boolean, missing != closed"},
        history="SH/SZ/BJ dated versions supported; no accepted live source configured"),
    "cffex_calendar": dict(provider="UNKNOWN", interface="RankingCalendar (port only)", endpoint=None,
        fields={"exchange/session_date/opens_at/closes_at": "CFFEX aware session window + visible calendar provenance"},
        history="Not provided by existing SH/SZ/BJ SQLite calendar; cannot copy its sessions"),
    "security_identity": dict(provider="UNKNOWN", interface="SQLiteSecurityMaster (storage/query only)", endpoint=None,
        fields={"instrument_id/symbol/effective_from/effective_to/listing_date": "listing entity, point-in-time intervals"},
        history="No live historical identity provider; sample instrument_id is an observation label only"),
    "historical_st": dict(provider="UNKNOWN", interface=None, endpoint=None,
        fields={"risk_status/effective_interval": "explicit historical ST state; UNKNOWN is not normal"},
        history="Existing master risk_status remains unknown; current name cannot backfill ST"),
    "suspension": dict(provider="UNKNOWN", interface=None, endpoint=None,
        fields={"instrument_id/trade_date/suspended": "dated explicit status; missing bars != suspension"},
        history="No certified daily status source; breadth suspension count also needs universe evidence"),
    "delisting": dict(provider="UNKNOWN", interface="SecurityMaster lifecycle (storage only)", endpoint=None,
        fields={"delisting_date/available_at": "first non-listed date + actual visible version time"},
        history="No accepted historical lifecycle feed; null delisting date is not proof of continued listing"),
    "fear_greed": dict(provider="derived", interface="market_analysis_core.fear_greed_diagnostic", endpoint=None,
        fields={"trend/momentum/low_volatility": "price factors", "advancing/limit_ratio": "certified full-A counts",
                "turnover_factor": "full-A market_amount_cny history"},
        history="Existing six-factor formula only; incomplete factors => null full score, separate price proxy"),
}

DIMENSIONS = {
    "semantics_units": "Reviewed field mapping plus source definition/unit evidence; no cross-scope substitutions",
    "source_authorization": "Separate source, research/storage/automation/display/redistribution evidence; SDK MIT is not data permission",
    "coverage": "Independent visible calendar and point-in-time full-A universe denominator; no weekday or response-date denominator",
    "freshness": "Requested analysis date and actual cutoff; expected latest session requires certified calendar",
    "quality": "Explicit per-record decision, finite scalars/cross-field identities; UNKNOWN is not accepted",
    "historical_status": "Point-in-time security lifecycle/ST/suspension and calendar; no current snapshot backfill",
    "time": "Actual observed/ingested/event/available timestamps <= as_of; collection is not historical first publication",
    "reproduction": "Pinned code/rules, batch, source versions, local evidence digest; snapshot digest is not source authenticity",
    "admission": "Only core Diagnostic admission/reasons/allowed_uses; L3 requires separate independent review/execution/OOS receipt",
}


def inventory():
    return deepcopy(SOURCE_INVENTORY)


def _source(item, default):
    if item is None:
        return SourceEvidence(default, "not-observed", ("unavailable:no-observation",))
    digest = hashlib.sha256(json.dumps(item, sort_keys=True, allow_nan=False).encode()).hexdigest()
    return SourceEvidence(item["source"], "observation-sha256:" + digest,
                          ("observation-sha256:" + digest,), latest_source_date=item["trade_date"])


def _stock_frame(item):
    if item is None:
        return pd.DataFrame()
    frame = pd.DataFrame(item["records"], dtype=object)
    if not frame.empty:
        # The ingestion batch actually measured this time. Missing stays absent.
        if item.get("observed_at") is not None:
            frame["observed_at"] = item["observed_at"]
    return frame


def _index_frame(item):
    if item is None:
        return pd.DataFrame()
    # A collector supplies batch metadata for rows that lack it. Preserve any
    # explicit row fields, including invalid/null identities, for core to reject.
    # Object construction prevents inference from failing before core validation.
    frame = pd.DataFrame(item["prices"], dtype=object)
    for key in ("symbol", "source", "observed_at", "ingested_at", "available_at"):
        if key in item and key not in frame:
            frame[key] = item[key]
    return frame


def build_bundle(observations, *, analysis_date, as_of, mode="research", run_id):
    """Compose local observations; no I/O, no selection of conflicting versions.

    Each source supplies one already-selected observation. Unknown external
    receipts stay UNKNOWN. Metadata never upgrades or rewrites a core result.
    """
    index = observations.get("sina_index")
    market = observations.get("legu_breadth")
    request = Request(analysis_date, as_of, "sh000300", "INDEX", mode)
    prices = _index_frame(index)
    price_source = _source(index, INDEX_SOURCE)
    market_source = _source(market, BREADTH_SOURCE)
    breadth = pd.DataFrame()
    if market:
        row = dict(market["breadth"], trade_date=market["trade_date"], symbol="ALL_A", source=market["source"])
        for key in ("event_time", "observed_at", "ingested_at", "available_at", "quality_status"):
            if key in market:
                row[key] = market[key]
        breadth = pd.DataFrame([row])
    diagnostics = price_diagnostics(prices, request=request, source=price_source)
    diagnostics["market_breadth"] = breadth_diagnostic(breadth,
        request=Request(analysis_date, as_of, "ALL_A", "ALL_A", mode), source=market_source)
    diagnostics["fear_greed"] = fear_greed_diagnostic(prices, request=request, source=price_source,
        market_frame=breadth, market_source=market_source)
    raw = observations.get("cffex_rankings")
    diagnostics["cffex_position"] = cffex_diagnostic((),
        request=Request(analysis_date, as_of, "IF2611", "CFFEX", mode),
        source=_source(raw, "cffex:public-rankings:task-022a-h-v2"), member="UNKNOWN", scope=MemberScope.AGENT)
    diagnostics["environment"] = environment_diagnostic(diagnostics, request=request)
    for key in ("eastmoney_stock", "tencent_stock"):
        item = observations.get(key)
        if item:
            stock_request = Request(analysis_date, as_of, "600000.SH", "STOCK", mode)
            for indicator, diagnostic in price_diagnostics(_stock_frame(item), request=stock_request,
                    source=_source(item, key)).items():
                diagnostics[key + ":" + indicator] = diagnostic
    return dict(schema_version=VERSION, run_id=run_id, baseline_sha=BASELINE,
        core_contract_version=CONTRACT_VERSION, calculation_version=CALCULATION_VERSION,
        core_review=deepcopy(CORE_REVIEW), request=dict(analysis_date=analysis_date, as_of=request.as_of, mode=mode),
        diagnostics={key: diagnostic.to_dict() for key, diagnostic in diagnostics.items()},
        requirements=deepcopy(DIMENSIONS))


def public_summary(bundle, source_results):
    """Reviewed-summary shape: excludes raw prices/CSV/SDK frames and numeric outputs."""
    result = {k: deepcopy(v) for k, v in bundle.items() if k != "diagnostics"}
    result["sources"] = deepcopy(source_results)
    result["diagnostics"] = {name: {key: deepcopy(d[key]) for key in (
        "indicator", "request", "data_latest_date", "times", "coverage", "status", "admission",
        "calculated", "reasons", "missing_fields", "data_snapshot_id", "allowed_uses")}
        for name, d in bundle["diagnostics"].items()}
    return result
