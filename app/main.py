"""
FastAPI application entry point.
"""

import os
import sys
from contextlib import asynccontextmanager

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from dotenv import load_dotenv

from app.database import async_session_maker, init_db, engine
from app.keepa_client import KeepaClient
from app.schemas import (
    UpcResponse,
    EligibilityCheck,
    EligibilityResponse,
    BatchEligibilityRequest,
    BatchEligibilityResponse,
    BatchEligibilityItem,
    AskRequest,
    AskResponse,
    ChatRequest,
    ChatResponse,
    IntentInfo,
    HealthResponse,
)
from app.eligibility import compute_roi, check_eligibility
from app.upc_normalizer import normalize_upc
from app.services.deepseek import ask_deepseek

load_dotenv()


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await engine.dispose()


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Keepa Scout API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_keepa = KeepaClient()


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health():
    try:
        async with async_session_maker() as session:
            from sqlalchemy import text
            await session.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"
    return HealthResponse(status="ok", db=db_status, timestamp=datetime.utcnow())


# ── UPC ──────────────────────────────────────────────────────────────────────

@app.get("/upc", response_model=UpcResponse)
async def resolve_upc(upc: str):
    """
    GET /upc?upc=...  — resolves a UPC/EAN/ISBN to ASIN(s) via Keepa.
    Input may be 11/12/13/14 digits, with or without hyphens/spaces.
    Multiple ASINs are possible (e.g. 1-pack vs 12-pack) — all returned.
    """
    raw = (upc or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="upc query param is required")

    variants = normalize_upc(raw)
    if not variants:
        raise HTTPException(status_code=400, detail="No numeric digits found in input")

    asins: list[str] = []
    for code in variants:
        products = await _keepa.fetch_product_by_upc(code)
        for p in products:
            if asin := p.get("asin"):
                asins.append(asin)

    return UpcResponse(input=raw, normalized=variants, asins=list(dict.fromkeys(asins)))


# ── Eligibility ───────────────────────────────────────────────────────────────

async def _get_asin_record(asin: str) -> Optional[dict]:
    from app.models import Asin
    from sqlalchemy import select
    async with async_session_maker() as session:
        result = await session.execute(select(Asin).where(Asin.asin == asin))
        row = result.scalar_one_or_none()
        if not row:
            return None
        return {
            "title": row.title,
            "buybox": row.buybox,
            "referral_fee_pct": row.referral_fee_pct,
            "fba_pick_pack_cents": row.fba_pick_pack_cents,
            "sales_rank": row.sales_rank,
            "monthly_sold": row.monthly_sold,
            "amazon_buybox_pct": row.amazon_buybox_pct,
            "supplier_cost": row.supplier_cost,
            "eligible": row.eligible,
            "filter_failed": row.filter_failed,
            "computed_roi_pct": row.computed_roi_pct,
        }


async def _build_eligibility_response(asin: str) -> EligibilityResponse:
    record = await _get_asin_record(asin)
    if not record:
        raise HTTPException(status_code=404, detail=f"ASIN {asin} not found in database")

    referral = record.get("referral_fee_pct")
    sales_rank = record.get("sales_rank")
    monthly_sold = record.get("monthly_sold")
    buybox = record.get("buybox")
    amazon_pct = record.get("amazon_buybox_pct")

    checks = {}
    checks["referral_fee"] = EligibilityCheck(
        pass_=(referral is not None and referral > 0),
        value=referral,
        threshold="> 0",
        message="referral fee must exist and be positive",
    )
    rank_ok = sales_rank is not None and sales_rank <= 100_000
    sold_ok = monthly_sold is not None and monthly_sold >= 100
    checks["demand"] = EligibilityCheck(
        pass_=(rank_ok or sold_ok),
        value={"sales_rank": sales_rank, "monthly_sold": monthly_sold},
        threshold="rank <= 100,000 OR monthly_sold >= 100",
    )
    checks["buybox"] = EligibilityCheck(
        pass_=(buybox is not None and buybox >= 10),
        value=buybox,
        threshold=">= $10",
    )
    checks["amazon_pct"] = EligibilityCheck(
        pass_=(amazon_pct is not None and amazon_pct <= 80),
        value=amazon_pct,
        threshold="<= 80%",
    )
    checks["monthly_sold_min"] = EligibilityCheck(
        pass_=(monthly_sold is None or monthly_sold >= 100),
        value=monthly_sold,
        threshold="null OR >= 100",
    )

    return EligibilityResponse(
        asin=asin,
        title=record.get("title"),
        eligible=record.get("eligible", False),
        filter_failed=record.get("filter_failed"),
        checks=checks,
        computed_roi_pct=record.get("computed_roi_pct"),
        supplier_cost=record.get("supplier_cost"),
        buybox=buybox,
        amazon_buybox_pct=amazon_pct,
    )


@app.get("/eligibility/{asin}", response_model=EligibilityResponse)
async def get_eligibility(asin: str):
    """
    GET /eligibility/{asin} — returns each rule's pass/fail + filter_failed + ROI.
    """
    asin = asin.strip()
    if not asin:
        raise HTTPException(status_code=400, detail="asin path param is required")
    return await _build_eligibility_response(asin)


@app.post("/eligibility/batch", response_model=BatchEligibilityResponse)
async def batch_eligibility(body: BatchEligibilityRequest):
    results: list[BatchEligibilityItem] = []
    for asin in body.asins:
        try:
            rec = await _get_asin_record(asin)
        except Exception:
            rec = None
        if not rec:
            results.append(BatchEligibilityItem(asin=asin, eligible=False, filter_failed="not_found"))
            continue
        results.append(BatchEligibilityItem(
            asin=asin,
            eligible=rec.get("eligible", False),
            filter_failed=rec.get("filter_failed"),
            computed_roi_pct=rec.get("computed_roi_pct"),
            supplier_cost=rec.get("supplier_cost"),
            buybox=rec.get("buybox"),
            amazon_buybox_pct=rec.get("amazon_buybox_pct"),
        ))
    return BatchEligibilityResponse(results=results)


# ── Ask ────────────────────────────────────────────────────────────────────────

@app.post("/ask", response_model=AskResponse)
async def ask(body: AskRequest):
    """
    Natural language query against the ASIN database, powered by DeepSeek.
    """
    result = await ask_deepseek(body.question)
    return AskResponse(
        answer=result.get("answer", ""),
        sql=result.get("sql"),
        rows=result.get("rows", []),
        row_count=len(result.get("rows", [])),
        out_of_scope=result.get("out_of_scope", False),
    )


# ── Chat ───────────────────────────────────────────────────────────────────────

@app.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest):
    """
    Conversational interface with session memory.
    Resolves ASIN mentions, maintains context across turns.
    """
    from app.models import ChatSession
    from sqlalchemy import select

    # Load or create session
    async with async_session_maker() as session:
        result = await session.execute(
            select(ChatSession).where(ChatSession.session_id == body.session_id)
        )
        chat_rec = result.scalar_one_or_none()
        if chat_rec:
            session_state = chat_rec.session_state or {}
        else:
            session_state = {"history": [], "resolved_asin": None, "intent": None}
            chat_rec = ChatSession(session_id=body.session_id, session_state=session_state)
            session.add(chat_rec)

        history: list = session_state.get("history", [])
        history.append({"role": "user", "content": body.message})
        session_state["history"] = history[-20:]  # keep last 20 turns

        # Build context for DeepSeek
        context_asin = session_state.get("resolved_asin")
        answer_result = await ask_deepseek(body.message, context_asin=context_asin, history=history[-10:])

        answer = answer_result.get("answer", "")
        resolved_asin = answer_result.get("resolved_asin")
        out_of_scope = answer_result.get("out_of_scope", False)

        history.append({"role": "assistant", "content": answer})
        session_state["history"] = history[-20:]
        if resolved_asin:
            session_state["resolved_asin"] = resolved_asin

        chat_rec.session_state = session_state
        await session.commit()

        return ChatResponse(
            answer=answer,
            results=answer_result.get("rows", []),
            session_state=session_state,
            intent=IntentInfo(
                resolved_asin=resolved_asin,
                topic_reset=answer_result.get("topic_reset", False),
                intent=answer_result.get("intent"),
            ) if resolved_asin or answer_result.get("intent") else None,
        )
