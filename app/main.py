"""
FastAPI 应用主入口。

提供 5 个 REST API 端点：
  GET  /health              — 健康检查（DB 连通性）
  GET  /upc                 — UPC/EAN/ISBN → ASIN 转换（Keepa）
  GET  /eligibility/{asin} — 单个 ASIN 准入详情
  POST /eligibility/batch  — 批量 ASIN 准入查询
  POST /ask                 — 自然语言数据库查询（DeepSeek）
  POST /chat                — 多轮对话（带会话记忆）
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


# ═══════════════════════════════════════════════════════════════
# 生命周期管理（启动 / 关闭）
# ═══════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期钩子：
      - 启动时：初始化数据库（创建表）
      - 关闭时：关闭数据库连接池
    """
    await init_db()
    yield
    await engine.dispose()


# ═══════════════════════════════════════════════════════════════
# 应用实例
# ═══════════════════════════════════════════════════════════════

app = FastAPI(
    title="Keepa Scout API",
    version="0.1.0",
    lifespan=lifespan,
)

# 允许所有来源跨域（开发环境），前端可直接调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局 Keepa 客户端（复用于所有请求，避免重复初始化）
_keepa = KeepaClient()


# ═══════════════════════════════════════════════════════════════
# GET /health — 健康检查
# ═══════════════════════════════════════════════════════════════

@app.get("/health", response_model=HealthResponse)
async def health():
    """检查数据库连接是否正常，返回服务器时间戳"""
    try:
        async with async_session_maker() as session:
            from sqlalchemy import text
            await session.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"
    return HealthResponse(status="ok", db=db_status, timestamp=datetime.utcnow())


# ═══════════════════════════════════════════════════════════════
# GET /upc — UPC/EAN/ISBN 转 ASIN
# ═══════════════════════════════════════════════════════════════

@app.get("/upc", response_model=UpcResponse)
async def resolve_upc(upc: str):
    """
    根据条码查询对应 ASIN（可能多个，如 1 件装和 12 件装）。

    流程：
      1. 归一化输入（去除连字符/空格，处理 UPC-E 展开等）
      2. 逐一查询 Keepa（多变体尝试提高成功率）
      3. 合并去重所有返回的 ASIN
    """
    raw = (upc or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="upc query param is required")

    variants = normalize_upc(raw)
    if not variants:
        raise HTTPException(status_code=400, detail="No numeric digits found in input")

    asins: list[str] = []
    errors: list[str] = []
    for code in variants:
        try:
            products = await _keepa.fetch_product_by_upc(code)
            for p in products:
                if asin := p.get("asin"):
                    asins.append(asin)
        except RuntimeError:
            # 所有 Key 耗尽，记录错误但不中断
            errors.append(f"All Keepa keys exhausted after trying '{code}'")
            break
        except Exception as e:
            errors.append(f"Keepa error for '{code}': {e}")
            continue

    return UpcResponse(
        input=raw,
        normalized=variants,
        asins=list(dict.fromkeys(asins)),  # 去重，保持顺序
        errors=errors,
    )


# ═══════════════════════════════════════════════════════════════
# 辅助函数：数据库读取
# ═══════════════════════════════════════════════════════════════

async def _get_asin_record(asin: str) -> Optional[dict]:
    """根据 ASIN 从数据库读取完整记录"""
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
    """
    构建单个 ASIN 的准入检查响应。

    返回内容：
      - eligible / filter_failed（总体结论）
      - 每条规则的详细通过/失败信息（供前端展示）
      - ROI 及关键字段（供参考）
    """
    record = await _get_asin_record(asin)
    if not record:
        raise HTTPException(status_code=404, detail=f"ASIN {asin} not found in database")

    referral = record.get("referral_fee_pct")
    sales_rank = record.get("sales_rank")
    monthly_sold = record.get("monthly_sold")
    buybox = record.get("buybox")
    amazon_pct = record.get("amazon_buybox_pct")

    checks = {}

    # 规则 1：referral_fee_pct > 0
    checks["referral_fee"] = EligibilityCheck(
        pass_=(referral is not None and referral > 0),
        value=referral,
        threshold="> 0",
        message="referral fee must exist and be positive",
    )

    # 规则 2：rank ≤ 100k 或 monthly_sold ≥ 100（月销豁免）
    rank_ok = sales_rank is not None and sales_rank <= 100_000
    sold_ok = monthly_sold is not None and monthly_sold >= 100
    checks["demand"] = EligibilityCheck(
        pass_=(rank_ok or sold_ok),
        value={"sales_rank": sales_rank, "monthly_sold": monthly_sold},
        threshold="rank <= 100,000 OR monthly_sold >= 100",
    )

    # 规则 3：buybox ≥ $10
    checks["buybox"] = EligibilityCheck(
        pass_=(buybox is not None and buybox >= 10),
        value=buybox,
        threshold=">= $10",
    )

    # 规则 4：amazon_buybox_pct ≤ 80
    checks["amazon_pct"] = EligibilityCheck(
        pass_=(amazon_pct is not None and amazon_pct <= 80),
        value=amazon_pct,
        threshold="<= 80%",
    )

    # 规则 5：monthly_sold null 或 ≥ 100
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


# ═══════════════════════════════════════════════════════════════
# GET /eligibility/{asin} — 单个 ASIN 准入详情
# ═══════════════════════════════════════════════════════════════

@app.get("/eligibility/{asin}", response_model=EligibilityResponse)
async def get_eligibility(asin: str):
    """返回单个 ASIN 的准入详情（5 条规则 + ROI）"""
    asin = asin.strip()
    if not asin:
        raise HTTPException(status_code=400, detail="asin path param is required")
    return await _build_eligibility_response(asin)


# ═══════════════════════════════════════════════════════════════
# POST /eligibility/batch — 批量 ASIN 准入查询
# ═══════════════════════════════════════════════════════════════

@app.post("/eligibility/batch", response_model=BatchEligibilityResponse)
async def batch_eligibility(body: BatchEligibilityRequest):
    """
    批量查询多个 ASIN 的准入状态。

    用途：前端列表页批量展示大量 ASIN 的 eligible 状态。
    不存在的 ASIN 返回 filter_failed="not_found"。
    """
    results: list[BatchEligibilityItem] = []
    for asin in body.asins:
        try:
            rec = await _get_asin_record(asin)
        except Exception:
            rec = None
        if not rec:
            results.append(BatchEligibilityItem(
                asin=asin,
                eligible=False,
                filter_failed="not_found",
            ))
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


# ═══════════════════════════════════════════════════════════════
# POST /ask — 自然语言查询
# ═══════════════════════════════════════════════════════════════

@app.post("/ask", response_model=AskResponse)
async def ask(body: AskRequest):
    """
    自然语言查询接口，由 DeepSeek LLM 驱动。

    处理流程（两步）：
      1. LLM 将自然语言转换为 SQLite SELECT 语句
      2. 执行 SQL，结果由 LLM 格式化返回

    支持的查询类型：
      - 计数：有多少符合条件的 ASIN？
      - 筛选：列出 ROI > 25% 的 ASIN
      - 排序：按月销量排名前 5
      - 解释：某个 ASIN 为什么不符合条件？
      - 域外问题：直接拒绝（天气、政治等）
    """
    result = await ask_deepseek(body.question)
    return AskResponse(
        answer=result.get("answer", ""),
        sql=result.get("sql"),
        rows=result.get("rows", []),
        row_count=len(result.get("rows", [])),
        out_of_scope=result.get("out_of_scope", False),
    )


# ═══════════════════════════════════════════════════════════════
# POST /chat — 多轮对话
# ═══════════════════════════════════════════════════════════════

@app.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest):
    """
    多轮对话接口，支持上下文记忆和 ASIN 代词引用。

    功能：
      - 持久化会话历史（最近 20 条）
      - 自动解析并追踪用户提到的 ASIN
      - 支持代词引用（"第二个"、"它"）
      - 支持话题切换（"忘了那个"）
      - 累积筛选条件（先问"有哪些合格品"，再问"其中 ROI>25% 的"）
    """
    from app.models import ChatSession
    from sqlalchemy import select

    async with async_session_maker() as session:
        # 加载或创建会话记录
        result = await session.execute(
            select(ChatSession).where(ChatSession.session_id == body.session_id)
        )
        chat_rec = result.scalar_one_or_none()
        if chat_rec:
            session_state = chat_rec.session_state or {}
        else:
            session_state = {
                "history": [],
                "resolved_asin": None,
                "intent": None,
            }
            chat_rec = ChatSession(
                session_id=body.session_id,
                session_state=session_state,
            )
            session.add(chat_rec)

        # 保存用户消息
        history: list = session_state.get("history", [])
        history.append({"role": "user", "content": body.message})
        session_state["history"] = history[-20:]  # 只保留最近 20 条

        # 调用 DeepSeek 处理对话（含历史上下文）
        context_asin = session_state.get("resolved_asin")
        answer_result = await ask_deepseek(
            body.message,
            context_asin=context_asin,
            history=history[-10:],  # 最近 10 条发给 LLM
        )

        answer = answer_result.get("answer", "")
        resolved_asin = answer_result.get("resolved_asin")
        out_of_scope = answer_result.get("out_of_scope", False)

        # 保存助手回复
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
