import os
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Float, Integer, Boolean, DateTime, JSON, Index, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Asin(Base):
    __tablename__ = "asins"

    asin: Mapped[str] = mapped_column(String(20), primary_key=True)
    title: Mapped[Optional[str]] = mapped_column(String, default=None)
    brand: Mapped[Optional[str]] = mapped_column(String, default=None)
    buybox: Mapped[Optional[float]] = mapped_column(Float, default=None)
    referral_fee_pct: Mapped[Optional[float]] = mapped_column(Float, default=None)
    fba_pick_pack_cents: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    sales_rank: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    monthly_sold: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    number_of_items: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    amazon_buybox_pct: Mapped[Optional[float]] = mapped_column(Float, default=None)
    supplier_cost: Mapped[Optional[float]] = mapped_column(Float, default=None)
    computed_roi_pct: Mapped[Optional[float]] = mapped_column(Float, default=None)
    eligible: Mapped[Optional[bool]] = mapped_column(Boolean, default=None)
    filter_failed: Mapped[Optional[str]] = mapped_column(String(50), default=None)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        Index("idx_eligible", "eligible"),
        Index("idx_roi", "computed_roi_pct"),
        Index("idx_amazon_buybox_pct", "amazon_buybox_pct"),
        Index("idx_eligible_roi", "eligible", "computed_roi_pct"),
    )


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_state: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
