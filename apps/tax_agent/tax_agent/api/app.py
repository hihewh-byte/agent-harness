"""Minimal API: Chinese resident + Futu tax workbook + upload + chat + compute."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from tax_agent.chat_orchestrator import orchestrate_user_message
from tax_agent.compute_engine import ComputeEngine, ComputeRequest
from tax_agent.export import events_to_csv
from tax_agent.fx import apply_fx_to_events
from tax_agent.fx_filing_rules import filing_date_for_request
from tax_agent.fx_rates import FxRateProvider
from tax_agent.llm_orchestrator import SessionContext, get_llm_status, llm_enabled, orchestrate_with_llm
from tax_agent.models import ResidentStatus
from tax_agent.parser.broker_parser import BrokerParser
from tax_agent.regulation_monitor import RULE_PACK_DEFAULT
from tax_agent.coverage_check import (
    build_coverage_report,
    format_coverage_reply_zh,
    try_coverage_fast_turn,
    uploaded_tax_years,
)
from tax_agent.filing_session_state import FilingSessionState
from tax_agent.filing_table import build_filing_report
from tax_agent.harness_report import REPORT_SCHEMA, harness_report_enabled, write_harness_report
from tax_agent.filing_narrative import (
    deliver_filing_narrative,
    should_polish_narrative,
    try_narrative_fast_turn,
)
from tax_agent.chat_sse import iter_chat_sse_events
from tax_agent.chat_turn_service import (
    ChatTurnRequest,
    chat_turn_request_from_body,
    resolve_chat_turn,
)
from tax_agent.session_turn_focus import (
    get_tax_session_focus,
    record_turn_focus,
    revive_tax_session_focus,
)
from tax_agent.tax_insight import build_tax_insight, format_insight_reply_zh
from tax_agent.tax_provenance import build_fx_provenance, format_fx_provenance_reply_zh
from tax_agent.tax_turn_resolver import scope_primary_year
from tax_agent.report_composer import compose_markdown_report
from tax_agent.rule_registry import RuleRegistry
from tax_agent.store_singleton import get_app_store

store = get_app_store()
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
_rule_registry = RuleRegistry()
FUTU_TEMPLATE = "broker_futu_v1"


def _fx_provider_for_rules(engine: ComputeEngine, rule_snapshot_id: str = "latest_stable") -> FxRateProvider | None:
    snapshot_id = engine.repo.resolve_snapshot_id(RULE_PACK_DEFAULT, rule_snapshot_id)
    snap_folder = snapshot_id.split("@", 1)[1] if "@" in snapshot_id else ""
    snap_dir = engine.repo.rules_dir / RULE_PACK_DEFAULT / "snapshots" / snap_folder
    return FxRateProvider.from_snapshot_dir(snap_dir)


class ComputeBody(BaseModel):
    datasetId: str
    taxYear: int = Field(ge=2000, le=2100)
    residentStatus: str = "cn_tax_resident"
    ruleSnapshotId: str = "latest_stable"
    fxPolicy: str = "cn_supplemental"
    filingDate: str | None = None
    defaultFxRate: float | None = 7.10
    filingScope: str = "foreign_only"
    sessionId: str | None = None


class ChatBody(BaseModel):
    sessionId: str
    userKey: str | None = None
    message: str
    datasetId: str | None = None
    lastRunId: str | None = None
    taxYear: int = 2022
    residentStatus: str = "cn_tax_resident"
    ruleSnapshotId: str = "latest_stable"
    fxPolicy: str = "cn_supplemental"
    filingDate: str | None = None
    filingScope: str = "foreign_only"
    defaultFxRate: float = 7.10
    llmModel: str | None = None  # auto | __off__ | ollama model name
    replyVerbosity: str | None = None  # brief | normal | detailed
    narrativePolish: bool | None = None  # None=自动；False=仅确定性叙述


def _load_env_on_startup() -> None:
    try:
        from tax_agent.ollama_local import load_dotenv_if_present

        load_dotenv_if_present()
        tax_env = Path(__file__).resolve().parent.parent.parent / ".env"
        if tax_env.is_file():
            from dotenv import load_dotenv

            load_dotenv(tax_env, override=False)
        try:
            from tax_agent.pha_llm import ensure_pha_importable

            ensure_pha_importable()
        except Exception:
            pass
    except Exception:
        pass


def _run_compute(body: ComputeBody, engine: ComputeEngine) -> dict[str, Any]:
    ds = store.get(body.datasetId)
    if not ds:
        raise HTTPException(404, f"dataset not found: {body.datasetId}")

    if ds.broker_template_id != FUTU_TEMPLATE:
        raise HTTPException(400, "仅支持富途税表 xlsx，请重新上传 Annual_Statement")

    try:
        resident = ResidentStatus(body.residentStatus)
    except ValueError as e:
        raise HTTPException(400, f"invalid residentStatus: {body.residentStatus}") from e

    snapshot_id = engine.repo.resolve_snapshot_id(RULE_PACK_DEFAULT, body.ruleSnapshotId)
    snap_folder = snapshot_id.split("@", 1)[1] if "@" in snapshot_id else ""
    snap_dir = engine.repo.rules_dir / RULE_PACK_DEFAULT / "snapshots" / snap_folder
    fx_provider = FxRateProvider.from_snapshot_dir(snap_dir)
    fx_default = Decimal(str(body.defaultFxRate)) if body.defaultFxRate else None
    override = fx_default if body.fxPolicy == "user_override" else None
    resolved_filing_date = filing_date_for_request(
        policy=body.fxPolicy,
        tax_year=body.taxYear,
        filing_date=body.filingDate,
    )
    events = apply_fx_to_events(
        list(ds.events),
        provider=fx_provider,
        policy=body.fxPolicy,
        override_rate=override,
        fallback_rate=fx_default,
        filing_date=resolved_filing_date,
        tax_year=body.taxYear,
    )

    if not ds.events:
        raise HTTPException(400, "未解析到有效事件，请确认上传的是富途税表 xlsx")

    req = ComputeRequest(
        events=events,
        tax_year=body.taxYear,
        resident_status=resident,
        rule_snapshot_id=body.ruleSnapshotId,
        fx_policy=body.fxPolicy,
        filing_date=resolved_filing_date,
        filing_scope=body.filingScope,
        domestic_income=None,
        data_quality=ds.data_quality,
        broker_template_id=ds.broker_template_id,
        parsed_account_count=max(1, len(set(ds.file_names))),
        input_file_hashes=ds.file_hashes,
    )
    result = engine.compute(req)
    markdown = compose_markdown_report(result)
    filing = build_filing_report(
        ds.data_quality or {},
        provider=_fx_provider_for_rules(engine, body.ruleSnapshotId),
        events=list(ds.events),
    )
    if filing.get("markdown"):
        markdown = markdown + "\n\n---\n\n" + filing["markdown"]
    store.save_report(result.run_id, body.datasetId, markdown, result)

    if hasattr(store, "append_chat") and body.sessionId:
        store.append_chat(
            body.sessionId,
            "assistant",
            markdown[:1500],
            meta={"runId": result.run_id},
        )

    return {
        "runId": result.run_id,
        "datasetId": body.datasetId,
        "status": result.status,
        "riskLevel": result.risk_level.value,
        "summary": result.summary,
        "netTaxDueRangeCny": result.net_tax_due_range_cny,
        "triggeredRiskRules": result.triggered_risk_rules,
        "notes": result.notes,
        "filingTable": filing if not filing.get("error") else None,
        "reportPreview": markdown[:2000],
    }


async def _handle_upload(
    data: bytes,
    file_name: str,
    session_id: str | None,
) -> dict[str, Any]:
    if not data:
        raise HTTPException(400, "empty file")
    lower = (file_name or "").lower()
    if not lower.endswith((".xlsx", ".xls")):
        raise HTTPException(400, "仅支持富途税表 xlsx（Annual_Statement）")

    sid = session_id or str(uuid4())
    parser = BrokerParser(template_id=FUTU_TEMPLATE)
    try:
        parse = parser.parse_bytes(data, file_name or "upload.bin", sid)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except ImportError as e:
        raise HTTPException(501, str(e)) from e

    if parse.broker_template_id != FUTU_TEMPLATE:
        raise HTTPException(
            400,
            "无法识别为富途税表。请从富途 App 导出含「证券-交易流水」的 Annual_Statement xlsx。",
        )

    if session_id:
        stored = store.merge_into_session(session_id, parse)
    else:
        stored = store.save_parse(parse)

    if hasattr(store, "append_chat"):
        store.append_chat(
            stored.session_id,
            "system",
            f"已上传 {file_name}，解析 {len(stored.events)} 条事件。",
            meta={"datasetId": stored.dataset_id},
        )

    return {
        "datasetId": stored.dataset_id,
        "sessionId": stored.session_id,
        "brokerTemplateId": parse.broker_template_id,
        "eventCount": len(stored.events),
        "dataQuality": stored.data_quality,
        "warnings": parse.warnings,
        "errors": parse.errors,
        "fileName": file_name,
    }


def create_app() -> FastAPI:
    engine = ComputeEngine()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        _load_env_on_startup()
        yield

    app = FastAPI(
        title="Futu Tax Agent",
        version="1.0.0",
        description="中国税务居民 · 富途境外所得测算",
        lifespan=lifespan,
    )

    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    def index() -> FileResponse:
        index_path = STATIC_DIR / "index.html"
        if not index_path.exists():
            raise HTTPException(404, "UI not found")
        return FileResponse(index_path)

    @app.get("/health")
    def health() -> dict[str, Any]:
        backend = "sqlite" if type(store).__name__ == "SqliteDatasetStore" else "memory"
        manifest = _rule_registry.load_manifest(RULE_PACK_DEFAULT)
        return {
            "status": "ok",
            "store": backend,
            "product": "futu_cn_resident",
            "latestStable": manifest.get("latestStable"),
        }

    @app.get("/tax/user/profile")
    def tax_user_profile(userKey: str) -> dict[str, Any]:
        from tax_agent.tax_user_profile import profile_preferences_payload

        key = (userKey or "").strip()
        if not key:
            raise HTTPException(400, "userKey required")
        return profile_preferences_payload(key)

    @app.get("/tax/llm/status")
    def tax_llm_status() -> dict[str, Any]:
        try:
            return get_llm_status()
        except FileNotFoundError as e:
            raise HTTPException(503, str(e)) from e

    @app.post("/tax/session/new")
    def new_session() -> dict[str, str]:
        return {"sessionId": str(uuid4())}

    @app.post("/tax/upload")
    async def tax_upload(
        file: UploadFile = File(...),
        sessionId: str | None = Form(None),
    ) -> dict[str, Any]:
        data = await file.read()
        return await _handle_upload(data, file.filename or "upload.bin", sessionId)

    @app.post("/tax/upload/batch")
    async def tax_upload_batch(
        files: list[UploadFile] = File(...),
        sessionId: str | None = Form(None),
    ) -> dict[str, Any]:
        if not files:
            raise HTTPException(400, "no files")
        sid = sessionId or str(uuid4())
        results: list[dict[str, Any]] = []
        last: dict[str, Any] | None = None
        for f in files:
            data = await f.read()
            last = await _handle_upload(data, f.filename or "upload.bin", sid)
            sid = last["sessionId"]
            results.append(
                {
                    "fileName": last["fileName"],
                    "eventCount": last["eventCount"],
                    "warnings": last.get("warnings") or [],
                }
            )
        assert last is not None
        ds = store.get(last["datasetId"])
        return {
            "datasetId": last["datasetId"],
            "sessionId": last["sessionId"],
            "brokerTemplateId": last["brokerTemplateId"],
            "eventCount": len(ds.events) if ds else last["eventCount"],
            "files": results,
            "dataQuality": last["dataQuality"],
            "warnings": last.get("warnings") or [],
        }

    @app.get("/tax/provenance")
    def tax_provenance_global(
        taxYear: int = 2023,
        taxYears: str | None = None,
        fxPolicy: str = "cn_supplemental",
        filingDate: str | None = None,
    ) -> dict[str, Any]:
        provider = _fx_provider_for_rules(engine)
        years = (
            [int(y.strip()) for y in taxYears.split(",") if y.strip().isdigit()]
            if taxYears
            else [taxYear]
        )
        from tax_agent.tax_provenance import format_multi_fx_provenance_reply_zh

        rows = [
            build_fx_provenance(
                tax_year=y,
                fx_policy=fxPolicy,
                filing_date=filingDate,
                provider=provider,
            )
            for y in years
        ]
        return {
            "taxYear": years[0] if len(years) == 1 else None,
            "taxYears": years,
            "provenance": rows[0] if len(rows) == 1 else rows,
            "reply": format_multi_fx_provenance_reply_zh(rows, fx_policy=fxPolicy),
        }

    @app.get("/tax/dataset/{dataset_id}/provenance")
    def dataset_provenance(
        dataset_id: str,
        taxYear: int = 2023,
        fxPolicy: str = "cn_supplemental",
        filingDate: str | None = None,
    ) -> dict[str, Any]:
        ds = store.get(dataset_id)
        if not ds:
            raise HTTPException(404, f"dataset not found: {dataset_id}")
        prov = build_fx_provenance(
            tax_year=taxYear,
            fx_policy=fxPolicy,
            filing_date=filingDate,
            provider=_fx_provider_for_rules(engine),
        )
        return {
            "datasetId": dataset_id,
            "taxYear": taxYear,
            "provenance": prov,
            "reply": format_fx_provenance_reply_zh(prov),
        }

    @app.get("/tax/dataset/{dataset_id}/insight")
    def dataset_insight(
        dataset_id: str,
        taxYear: int = 2023,
        focus: str = "realized_vs_deferred",
        lastRunId: str | None = None,
    ) -> dict[str, Any]:
        ds = store.get(dataset_id)
        if not ds:
            raise HTTPException(404, f"dataset not found: {dataset_id}")
        last_summary = None
        if lastRunId:
            rep = store.get_report(lastRunId)
            if rep:
                last_summary = rep.result_json.get("summary")
        insight = build_tax_insight(
            focus=focus,
            tax_year=taxYear,
            data_quality=ds.data_quality,
            events=list(ds.events),
            last_summary=last_summary,
            fx_provider=_fx_provider_for_rules(engine),
        )
        if insight.get("error"):
            raise HTTPException(400, insight["error"])
        return {
            "datasetId": dataset_id,
            "taxYear": taxYear,
            "focus": focus,
            "insight": insight,
            "reply": format_insight_reply_zh(insight),
        }

    @app.get("/tax/dataset/{dataset_id}/filing-table")
    def dataset_filing_table(dataset_id: str) -> dict[str, Any]:
        ds = store.get(dataset_id)
        if not ds:
            raise HTTPException(404, f"dataset not found: {dataset_id}")
        report = build_filing_report(
            ds.data_quality or {},
            provider=_fx_provider_for_rules(engine),
            events=list(ds.events),
        )
        if report.get("error"):
            raise HTTPException(400, report["error"])
        return report

    @app.get("/tax/dataset/{dataset_id}/coverage")
    def dataset_coverage(
        dataset_id: str,
        taxYear: int | None = None,
    ) -> dict[str, Any]:
        ds = store.get(dataset_id)
        if not ds:
            raise HTTPException(404, f"dataset not found: {dataset_id}")
        report = build_coverage_report(
            data_quality=ds.data_quality,
            events=list(ds.events),
            focus_tax_year=taxYear,
        )
        return {
            "datasetId": dataset_id,
            "coverage": report,
            "reply": format_coverage_reply_zh(report),
        }

    @app.get("/tax/dataset/{dataset_id}/narrative")
    def dataset_narrative(
        dataset_id: str,
        taxYear: int = 2023,
        polish: bool = False,
        llmModel: str | None = None,
    ) -> dict[str, Any]:
        ds = store.get(dataset_id)
        if not ds:
            raise HTTPException(404, f"dataset not found: {dataset_id}")
        ctx = SessionContext(
            dataset_id=dataset_id,
            tax_year=taxYear,
            data_quality=ds.data_quality,
            fx_provider=_fx_provider_for_rules(engine),
        )
        do_polish = polish and should_polish_narrative(
            "润色申报说明",
            llm_on=llm_enabled() and (llmModel or "") != "__off__",
        )
        override = llmModel if llmModel and llmModel not in ("auto", "__off__") else None
        result = deliver_filing_narrative(
            ctx,
            taxYear,
            polish=do_polish,
            model_override=override,
        )
        if result.get("error"):
            raise HTTPException(400, result["error"])
        return {
            "datasetId": dataset_id,
            "taxYear": taxYear,
            "narrative": result.get("narrative"),
            "polished": bool(result.get("polished")),
            "polishMeta": result.get("polishMeta"),
        }

    @app.get("/tax/harness/status")
    def harness_status() -> dict[str, Any]:
        return {
            "reportEnabled": harness_report_enabled(),
            "reportPath": os.environ.get(
                "TAX_HARNESS_REPORT_PATH", "/tmp/tax-harness-reports.jsonl"
            ),
            "schema": REPORT_SCHEMA,
        }

    @app.get("/tax/dataset/{dataset_id}/journey")
    def dataset_journey(
        dataset_id: str,
        lastRunId: str | None = None,
        taxYear: int = 2024,
        sessionId: str | None = None,
    ) -> dict[str, Any]:
        ds = store.get(dataset_id)
        if not ds:
            raise HTTPException(404, f"dataset not found: {dataset_id}")
        ctx = SessionContext(
            session_id=sessionId,
            dataset_id=dataset_id,
            last_run_id=lastRunId,
            tax_year=taxYear,
            data_quality=ds.data_quality,
            events=list(ds.events),
            broker_template_id=FUTU_TEMPLATE,
            fx_provider=_fx_provider_for_rules(engine),
        )
        if lastRunId:
            rep = store.get_report(lastRunId)
            if rep:
                ctx.last_summary = rep.result_json.get("summary")
        state = FilingSessionState.from_session_context(ctx)
        coverage = build_coverage_report(
            data_quality=ds.data_quality,
            events=list(ds.events),
            focus_tax_year=taxYear,
        )
        filing_table = None
        if ds.data_quality and (ds.data_quality.get("futuTaxPackages") or ds.data_quality.get("futuTaxPackage")):
            filing_table = build_filing_report(
                ds.data_quality,
                provider=_fx_provider_for_rules(engine),
                events=list(ds.events),
            )
            if filing_table.get("error"):
                filing_table = None
        return {
            "datasetId": dataset_id,
            "journeyPhase": state.journey_phase,
            "focusTaxYear": state.focus_tax_year,
            "uploadedYears": state.uploaded_years,
            "hasCompute": state.has_compute,
            "coverage": coverage,
            "filingTable": filing_table,
            "riskFlags": state.risk_flags,
            "turnFocus": _turn_focus_payload(sessionId or ""),
        }

    @app.post("/tax/compute")
    def tax_compute(body: ComputeBody) -> dict[str, Any]:
        return _run_compute(body, engine)

    @app.get("/tax/report/{run_id}")
    def tax_report(run_id: str) -> dict[str, Any]:
        rep = store.get_report(run_id)
        if not rep:
            raise HTTPException(404, f"report not found: {run_id}")
        return {
            "runId": rep.run_id,
            "datasetId": rep.dataset_id,
            "markdown": rep.markdown,
            "result": rep.result_json,
            "summary": rep.result_json.get("summary"),
        }

    def _turn_focus_payload(session_id: str) -> dict[str, Any]:
        focus = get_tax_session_focus(session_id)
        if not focus or focus.focus_tax_year <= 0:
            return {}
        years = focus.focus_tax_years or [focus.focus_tax_year]
        return {
            "taxYear": focus.focus_tax_year,
            "taxYears": years,
            "profile": focus.focus_profile,
            "ttl": focus.turns_remaining,
            "summary": focus.focus_summary,
            "lastMode": focus.last_mode,
        }

    def _session_context(body: ChatBody) -> SessionContext:
        ctx = SessionContext(
            session_id=body.sessionId,
            user_key=body.userKey,
            dataset_id=body.datasetId,
            last_run_id=body.lastRunId,
            tax_year=body.taxYear,
            resident_status=body.residentStatus,
            filing_scope=body.filingScope,
            domestic_income_provided=False,
            broker_template_id=FUTU_TEMPLATE,
            fx_provider=_fx_provider_for_rules(engine),
            fx_policy=body.fxPolicy,
            filing_date=body.filingDate,
        )
        if body.datasetId:
            ds = store.get(body.datasetId)
            if ds:
                ctx.event_count = len(ds.events)
                ctx.data_quality = ds.data_quality
                ctx.events = list(ds.events)
                counts: dict[str, int] = {}
                for ev in ds.events:
                    k = ev.event_type.value
                    counts[k] = counts.get(k, 0) + 1
                ctx.event_counts = counts
        if body.lastRunId:
            rep = store.get_report(body.lastRunId)
            if rep:
                ctx.last_summary = rep.result_json.get("summary")
        if hasattr(store, "list_chat"):
            hist = store.list_chat(body.sessionId, limit=12)
            ctx.chat_history = [
                {"role": m["role"], "content": m["content"]}
                for m in hist
                if m["role"] in ("user", "assistant")
            ]
        return ctx

    def _finalize_chat_outcome(
        outcome,
        *,
        user_message: str,
        body: ChatBody,
    ) -> dict[str, Any]:
        sid = body.sessionId
        if outcome.plan is not None:
            scope_years = (outcome.llm_meta.get("turnScope") or {}).get("taxYears") or (
                outcome.turn_scope.tax_years if outcome.turn_scope else []
            )
            record_turn_focus(
                sid,
                tax_year=outcome.plan.tax_year,
                tax_years=list(scope_years) if scope_years else [outcome.plan.tax_year],
                profile=outcome.plan.profile,
                user_message=user_message,
                assistant_reply=outcome.reply,
                mode=str(outcome.llm_meta.get("mode") or "rules"),
            )
            outcome.harness["turnFocus"] = _turn_focus_payload(sid)
            outcome.harness["uploadedYears"] = uploaded_tax_years(outcome.ctx.data_quality)

            harness_report = write_harness_report(
                session_id=sid,
                user_message=user_message,
                plan=outcome.plan,
                meta=outcome.llm_meta,
                mode=str(outcome.llm_meta.get("mode") or "rules"),
                turn_focus=_turn_focus_payload(sid),
                action=outcome.action,
            )
        else:
            harness_report = None
            outcome.harness["turnFocus"] = _turn_focus_payload(sid)
            outcome.harness["uploadedYears"] = uploaded_tax_years(outcome.ctx.data_quality)
            if outcome.clarify_choices and outcome.turn_scope:
                outcome.harness["focusTaxYear"] = scope_primary_year(
                    outcome.turn_scope, body.taxYear
                )

        out: dict[str, Any] = {
            "reply": outcome.reply,
            "action": outcome.action,
            "sessionId": sid,
            "llm": outcome.llm_meta,
            "harness": outcome.harness,
        }
        if outcome.clarify_choices:
            out["clarifyChoices"] = list(outcome.clarify_choices)
        if outcome.filing_table:
            out["filingTable"] = outcome.filing_table
        if outcome.follow_ups:
            out["followUps"] = list(outcome.follow_ups)
        if outcome.nba:
            out["nba"] = outcome.nba
            out["harness"]["nba"] = outcome.nba
        if harness_report:
            out["harnessReport"] = harness_report
        if outcome.insight:
            out["insight"] = outcome.insight
        if outcome.provenance:
            out["provenance"] = outcome.provenance

        if outcome.action == "compute" and body.datasetId and outcome.compute_params:
            params = outcome.compute_params
            comp = _run_compute(
                ComputeBody(
                    datasetId=body.datasetId,
                    sessionId=body.sessionId,
                    taxYear=int(params.get("taxYear", body.taxYear)),
                    fxPolicy=params.get("fxPolicy", body.fxPolicy),
                    filingDate=params.get("filingDate", body.filingDate),
                ),
                engine,
            )
            out.update(comp)
            out["reply"] = outcome.reply or f"{params.get('taxYear', body.taxYear)} 年度测算完成。"

        return out

    @app.post("/tax/chat")
    def tax_chat(body: ChatBody) -> dict[str, Any]:
        if hasattr(store, "append_chat"):
            store.append_chat(body.sessionId, "user", body.message)

        ctx = _session_context(body)
        req = chat_turn_request_from_body(body)
        outcome = resolve_chat_turn(req, ctx, apply_composer=True)
        out = _finalize_chat_outcome(outcome, user_message=body.message, body=body)

        if hasattr(store, "append_chat"):
            store.append_chat(body.sessionId, "assistant", out["reply"][:2000])
        return out

    @app.get("/tax/chat/stream")
    def tax_chat_stream(
        sessionId: str,
        message: str,
        userKey: str | None = None,
        datasetId: str | None = None,
        lastRunId: str | None = None,
        taxYear: int = 2022,
        residentStatus: str = "cn_tax_resident",
        fxPolicy: str = "cn_supplemental",
        filingDate: str | None = None,
        filingScope: str = "foreign_only",
        llmModel: str | None = None,
        replyVerbosity: str | None = None,
        narrativePolish: bool | None = None,
    ) -> StreamingResponse:
        body = ChatBody(
            sessionId=sessionId,
            userKey=userKey,
            message=message,
            datasetId=datasetId,
            lastRunId=lastRunId,
            taxYear=taxYear,
            residentStatus=residentStatus,
            fxPolicy=fxPolicy,
            filingDate=filingDate,
            filingScope=filingScope,
            llmModel=llmModel,
            replyVerbosity=replyVerbosity,
            narrativePolish=narrativePolish,
        )
        if hasattr(store, "append_chat"):
            store.append_chat(sessionId, "user", message)

        ctx = _session_context(body)
        req = chat_turn_request_from_body(body)

        def _harness_report_builder(**kwargs):
            return write_harness_report(**kwargs)

        def _gen():
            final_reply = ""
            for chunk in iter_chat_sse_events(
                req,
                ctx,
                build_harness_report=_harness_report_builder,
                turn_focus_payload=_turn_focus_payload,
            ):
                yield chunk
                if chunk.startswith("event: done"):
                    try:
                        import json as _json

                        data_line = next(
                            (ln for ln in chunk.split("\n") if ln.startswith("data: ")),
                            "",
                        )
                        if data_line:
                            payload = _json.loads(data_line[6:])
                            final_reply = str(payload.get("reply") or "")
                    except Exception:
                        pass
            if hasattr(store, "append_chat") and final_reply:
                store.append_chat(sessionId, "assistant", final_reply[:2000])

        return StreamingResponse(_gen(), media_type="text/event-stream")

    @app.get("/tax/chat/history/{session_id}")
    def chat_history(session_id: str, limit: int = 30) -> dict[str, Any]:
        if not hasattr(store, "list_chat"):
            return {"messages": []}
        return {"messages": store.list_chat(session_id, limit=limit)}

    return app


app = create_app()
