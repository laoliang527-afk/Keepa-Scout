"""
API 请求/响应数据结构（Pydantic 模型）。

按功能分组：
  - UPC     ：/upc  端点的入参和返回值
  - Eligibility ： /eligibility 端点的入参和返回值
  - Ask     ：/ask  端点（自然语言查询）
  - Chat    ：/chat 端点（多轮对话）
  - Health  ：/health 端点
"""

from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════
# UPC — UPC/EAN/ISBN 转 ASIN
# ═══════════════════════════════════════════════════════════════

class UpcResponse(BaseModel):
    """GET /upc 的响应"""
    input: str                                   # 用户原始输入（可能含连字符/空格）
    normalized: List[str]                         # 归一化后的 UPC 变体列表（逐一查询 Keepa）
    asins: List[str]                             # 从所有变体去重后的 ASIN 列表
    errors: List[str] = Field(default_factory=list)  # 查询过程中遇到错误


# ═══════════════════════════════════════════════════════════════
# Eligibility — ASIN 准入规则检查
# ═══════════════════════════════════════════════════════════════

class EligibilityCheck(BaseModel):
    """单条准入规则的检查结果"""
    pass_: bool                       # 是否通过
    value: Optional[Any] = None       # 实际值
    threshold: Optional[Any] = None    # 阈值描述
    message: Optional[str] = None      # 说明文字


class EligibilityResponse(BaseModel):
    """GET /eligibility/{asin} 的响应"""
    asin: str
    title: Optional[str] = None
    eligible: bool                     # 是否符合全部准入规则
    filter_failed: Optional[str] = None  # 第一条失败的规则名，全部通过则为 None
    checks: Dict[str, Any]             # 每条规则的详细结果
    computed_roi_pct: Optional[float] = None
    supplier_cost: Optional[float] = None
    buybox: Optional[float] = None
    amazon_buybox_pct: Optional[float] = None


class BatchEligibilityRequest(BaseModel):
    """POST /eligibility/batch 的入参"""
    asins: List[str]


class BatchEligibilityItem(BaseModel):
    """批量查询中单个 ASIN 的结果"""
    asin: str
    eligible: bool
    filter_failed: Optional[str] = None
    computed_roi_pct: Optional[float] = None
    supplier_cost: Optional[float] = None
    buybox: Optional[float] = None
    amazon_buybox_pct: Optional[float] = None


class BatchEligibilityResponse(BaseModel):
    """POST /eligibility/batch 的响应"""
    results: List[BatchEligibilityItem]


# ═══════════════════════════════════════════════════════════════
# Ask — 自然语言数据库查询
# ═══════════════════════════════════════════════════════════════

class AskRequest(BaseModel):
    """POST /ask 的入参"""
    question: str   # 用户自然语言问题，如 "有多少 ASIN 符合条件？"


class AskResponse(BaseModel):
    """POST /ask 的响应"""
    answer: str                        # LLM 生成的自然语言回答
    sql: Optional[str] = None          # 实际执行的 SQL（供调试）
    rows: List[Dict[str, Any]] = Field(default_factory=list)   # 原始数据行
    row_count: int = 0                 # 行数
    out_of_scope: bool = False         # True = 超出范围，直接拒绝回答


# ═══════════════════════════════════════════════════════════════
# Chat — 多轮对话
# ═══════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    """POST /chat 的入参"""
    session_id: str   # 客户端生成的会话 ID（UUID 等）
    message: str      # 用户本轮输入


class IntentInfo(BaseModel):
    """对话意图元信息（由 LLM 解析）"""
    resolved_asin: Optional[str] = None   # 本轮解析到的 ASIN
    topic_reset: bool = False              # True = 用户显式切换了话题（如"忘了那个"）
    intent: Optional[str] = None            # 意图类型（list_eligible / filter / ask_asin 等）


class ChatResponse(BaseModel):
    """POST /chat 的响应"""
    answer: str                              # 助手回复
    results: List[Dict[str, Any]] = Field(default_factory=list)  # 可选的表格数据
    session_state: Dict[str, Any] = Field(default_factory=dict)   # 当前会话状态（含历史）
    intent: Optional[IntentInfo] = None     # 意图信息


# ═══════════════════════════════════════════════════════════════
# Health — 健康检查
# ═══════════════════════════════════════════════════════════════

class HealthResponse(BaseModel):
    """GET /health 的响应"""
    status: str      # 整体状态（固定 "ok"）
    db: str          # 数据库状态（"ok" 或 "error"）
    timestamp: datetime  # 服务器当前时间
