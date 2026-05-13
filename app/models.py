"""
数据模型模块。

定义两张表：
  - Asin     — 核心商品表，每行对应一个 ASIN
  - ChatSession — 聊天会话状态（支持 /chat 多轮对话）
"""

import os
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Float, Integer, Boolean, DateTime, JSON, Index, text

from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Asin(Base):
    """
    ASIN 主表，存储 Keepa 商品数据及计算结果。

    字段说明：
      asin              — Amazon 商品 ID，主键
      title / brand     — 商品名称与品牌（Keepa 返回）
      buybox            — BuyBox 价格（美元，来源见 keepa_client.py）
      referral_fee_pct  — 亚马逊类目佣金百分比（Keepa 返回）
      fba_pick_pack_cents — FBA 拣货包装费（美分，由 keepa_client.py 转换）
      sales_rank        — 畅销榜排名（越低越好，Keepa stats.avg[3]）
      monthly_sold      — 月均销量（Keepa stats.monthlySoldAverage）
      number_of_items  — 包装数量（如 6 件装），用于多件装 ROI 计算
      amazon_buybox_pct — 亚马逊自营赢得 BuyBox 的历史占比（%）
      supplier_cost     — 供应商进货成本（来自 CSV）
      computed_roi_pct  — 计算所得 ROI = 100 * (payout - cost) / cost
      eligible          — 是否符合 FBA 套利准入条件（由 eligibility.py 计算）
      filter_failed     — 第一条失败的规则名，无失败则为 None
      updated_at        — 最后更新时间（自动维护）
    """
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

    # 常用查询字段加索引，加速 WHERE eligible=1、ORDER BY roi 等操作
    __table_args__ = (
        Index("idx_eligible", "eligible"),                            # 筛选合格品
        Index("idx_roi", "computed_roi_pct"),                        # 按 ROI 排序
        Index("idx_amazon_buybox_pct", "amazon_buybox_pct"),          # 按亚马逊占比排序
        Index("idx_eligible_roi", "eligible", "computed_roi_pct"),  # 联合索引：合格 + 高 ROI
    )


class ChatSession(Base):
    """
    聊天会话表，支持 /chat 端点的多轮对话记忆。

    session_id    — 会话唯一 ID（由客户端生成并传入）
    session_state — JSON 字段，存储：
                    history          — 最近 20 条对话历史
                    resolved_asin    — 当前已解析的 ASIN（用于代词引用）
                    active_filters   — 当前生效的筛选条件
                    user_constraints — 用户偏好（如预算）
    updated_at    — 最后活跃时间
    """
    __tablename__ = "chat_sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_state: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
