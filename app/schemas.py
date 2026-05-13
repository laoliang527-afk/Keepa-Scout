from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field


# ── UPC ──────────────────────────────────────────────────────────────────────

class UpcResponse(BaseModel):
    input: str
    normalized: List[str]
    asins: List[str]


# ── Eligibility ────────────────────────────────────────────────────────────────

class EligibilityCheck(BaseModel):
    pass_: bool
    value: Optional[Any] = None
    threshold: Optional[Any] = None
    message: Optional[str] = None


class EligibilityResponse(BaseModel):
    asin: str
    title: Optional[str] = None
    eligible: bool
    filter_failed: Optional[str] = None
    checks: Dict[str, Any]
    computed_roi_pct: Optional[float] = None
    supplier_cost: Optional[float] = None
    buybox: Optional[float] = None
    amazon_buybox_pct: Optional[float] = None


class BatchEligibilityRequest(BaseModel):
    asins: List[str]


class BatchEligibilityItem(BaseModel):
    asin: str
    eligible: bool
    filter_failed: Optional[str] = None
    computed_roi_pct: Optional[float] = None
    supplier_cost: Optional[float] = None
    buybox: Optional[float] = None
    amazon_buybox_pct: Optional[float] = None


class BatchEligibilityResponse(BaseModel):
    results: List[BatchEligibilityItem]


# ── Ask ───────────────────────────────────────────────────────────────────────

class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str
    sql: Optional[str] = None
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    out_of_scope: bool = False


# ── Chat ──────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: str
    message: str


class IntentInfo(BaseModel):
    resolved_asin: Optional[str] = None
    topic_reset: bool = False
    intent: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    results: List[Dict[str, Any]] = Field(default_factory=list)
    session_state: Dict[str, Any] = Field(default_factory=dict)
    intent: Optional[IntentInfo] = None


# ── Health ─────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    db: str
    timestamp: datetime
