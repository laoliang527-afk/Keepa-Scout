"""
Keepa API 客户端。

功能：
  - 支持多个 API Key 轮询（KEEPA_API_KEYS，支持逗号分隔多个）
  - 自动处理 402（Token 耗尽）/429（限流）并切换 Key
  - 批量查询 ASIN（最多约 100 个/请求）
  - 通过 UPC/EAN 查询 ASIN
  - 解析 Keepa 返回的原始数据，转换为标准化字段
  - 追踪 token 消耗量

数据来源策略（见 parse_product）：
  - BuyBox 价格：优先使用 stats.buyBoxPrice（快照数据，最可靠），
                降级到 top-level current[0]
  - 销量排名：优先使用 stats.avg[3]（90 天平均，最稳定），
              降级到 current[2]
"""

import os
from typing import Optional

import httpx

from dotenv import load_dotenv

load_dotenv()

# 从环境变量读取 Keepa API Key（支持多个，逗号分隔）
KEEPA_KEYS: list[str] = [
    k.strip()
    for k in os.getenv("KEEPA_API_KEYS", "").split(",")
    if k.strip()
]
KEEPA_DOMAIN = 1   # 1 = Amazon.com（美国站）
KEEPA_BASE = "https://api.keepa.com"

# Key 优先级：index 1 优先（有更稳定的约 300 token 配额），
# index 0 作为备选（key 1 耗尽时使用）
_KEY_ORDER = [1, 0]

# Keepa stats.current[] 索引映射（domain=1 / Amazon.com US）
# 参考：https://keepa.com/#!discuss/t/product-object/116
STAT_BUYBOX_PRICE = 0
STAT_BUYBOX_SHIPPING = 3
STAT_SALES_RANK = 2
STAT_NEW_PRICE = 1
STAT_NEW_SHIPPING = 4

# 亚马逊自营卖家 ID（用于计算亚马逊 BuyBox 占比）
AMAZON_SELLER_ID = "ATVPDKIKX0DER"


class KeepaClient:
    """
    Keepa API 异步客户端。

    用法：
      client = KeepaClient()
      products = await client.fetch_products_by_asins(["B010MU00UM", "B0CPRLHYRB"])
    """

    def __init__(self, keys: Optional[list[str]] = None):
        self.keys = keys or KEEPA_KEYS          # API Key 列表
        self._idx = 0                           # 当前 Key 索引
        self._tokens_used = 0                   # 累计消耗的 token 数

    @property
    def _key(self) -> str:
        """当前活跃的 API Key"""
        return self.keys[self._idx % len(self.keys)]

    def _next_key(self):
        """切换到下一个 Key（超过列表长度则循环）"""
        self._idx += 1
        if self._idx >= len(self.keys):
            self._idx = 0

    async def _request(self, params: dict) -> dict:
        """
        向 Keepa 发起一次 GET 请求。

        逻辑：
          - 按优先级顺序尝试每个 Key
          - 遇到 402/429/422 错误自动跳过并尝试下一个 Key
          - 记录 token 消耗
          - 全部 Key 失败后抛出 RuntimeError
        """
        params["key"] = self._key
        params["domain"] = KEEPA_DOMAIN

        async with httpx.AsyncClient(timeout=60.0) as client:
            tried = set()
            for order_idx in _KEY_ORDER:
                self._idx = order_idx
                if order_idx in tried:
                    continue
                tried.add(order_idx)
                try:
                    resp = await client.get(
                        f"{KEEPA_BASE}/product",
                        params=params,
                    )
                    body = resp.json()
                    if resp.status_code == 200:
                        if "tokensConsumed" in body:
                            self._tokens_used += body["tokensConsumed"]
                        return body
                    elif resp.status_code in (402, 429):
                        # Token 耗尽或限流，尝试下一个 Key
                        continue
                    elif resp.status_code == 422:
                        # 无效 ASIN/UPC 格式，本轮请求结束
                        continue
                    else:
                        resp.raise_for_status()
                except httpx.HTTPStatusError as e:
                    if e.response.status_code in (402, 429, 422):
                        continue
                    raise
        raise RuntimeError("All Keepa keys exhausted")

    async def fetch_products_by_asins(
        self,
        asins: list[str],
        stats: int = 90,
        buybox: int = 1,
        fbafees: int = 1,
    ) -> list[dict]:
        """
        批量查询 ASIN 的商品数据。

        参数：
          asins   — ASIN 列表（Keepa 建议每批最多 100 个）
          stats   — 历史快照天数（90 = 近 90 天统计数据，默认开启）
          buybox  — 1 = 请求 BuyBox 相关数据（亚马逊自营占比等）
          fbafees — 1 = 请求 FBA 费用明细

        返回：Keepa product 对象列表（可能少于请求数量）
        """
        if not asins:
            return []

        params = {
            "asin": ",".join(asins),
            "stats": stats,
            "buybox": buybox,
            "fbafees": fbafees,
        }
        data = await self._request(params)
        return data.get("products", [])

    async def fetch_product_by_upc(
        self,
        code: str,
        buybox: int = 1,
        fbafees: int = 1,
        stats: int = 90,
    ) -> list[dict]:
        """
        通过 UPC/EAN/ISBN 条码查询商品。

        返回：可能返回多个 ASIN（如 1 件装和 12 件装共用同一 UPC）
        """
        params = {
            "code": code,
            "buybox": buybox,
            "fbafees": fbafees,
            "stats": stats,
        }
        data = await self._request(params)
        return data.get("products", [])

    def parse_product(self, p: dict) -> dict:
        """
        将 Keepa 返回的原始 product 对象解析为标准化字段。

        所有价格均转换为美元（Keepa 原生返回单位为美分）。

        字段说明：
          buybox             — BuyBox 价格（美元），优先从 stats.buyBoxPrice 获取
          sales_rank         — 销量排名，优先从 stats.avg[3]（90 天均值）获取
          referral_fee_pct  — 亚马逊佣金比例（%），-1 表示无数据
          fba_pick_pack_cents — FBA 拣货包装费（美分），-1 表示无数据
          monthly_sold       — 月均销量，-1 表示无数据
          amazon_buybox_pct  — 亚马逊自营 BuyBox 历史占比（%）
        """
        result = {}

        result["asin"] = p.get("asin")
        result["title"] = p.get("title")
        result["brand"] = p.get("brand")

        # 包装数量（numberOfItems）：如 6 件装
        result["number_of_items"] = p.get("numberOfItems") or p.get("packageQuantity")

        # ── BuyBox 价格 ──────────────────────────────────
        # stats.buyBoxPrice 是快照数据，最可靠；
        # top-level current[0] 可能过时或为 -1，作为降级方案
        stats_data = p.get("stats", {}) or {}
        buybox_cents = stats_data.get("buyBoxPrice")
        if buybox_cents is None or buybox_cents < 0:
            buybox_cents = _safe_idx(p.get("current") or [], 0)
        result["buybox"] = _cents_to_dollars(buybox_cents)

        # ── 销量排名 ────────────────────────────────────
        # stats.avg[3] = 90 天平均排名，最稳定；
        # top-level current[2] 作为降级方案
        stats_avg = stats_data.get("avg") or []
        sales_rank_cents = _safe_idx(stats_avg, 3)
        if sales_rank_cents is None or sales_rank_cents < 0:
            sales_rank_cents = _safe_idx(p.get("current") or [], 2)
        result["sales_rank"] = int(sales_rank_cents) if sales_rank_cents is not None else None

        # ── 佣金比例 ────────────────────────────────────
        result["referral_fee_pct"] = p.get("referralFeePercentage")
        if result["referral_fee_pct"] == -1:
            result["referral_fee_pct"] = None

        # ── FBA 拣货包装费（美分）───────────────────────
        fba_fees = p.get("fbaFees") or {}
        result["fba_pick_pack_cents"] = fba_fees.get("pickAndPackFee")
        if result["fba_pick_pack_cents"] == -1:
            result["fba_pick_pack_cents"] = None

        # ── 月均销量 ────────────────────────────────────
        result["monthly_sold"] = stats_data.get("monthlySoldAverage")
        if result["monthly_sold"] == -1:
            result["monthly_sold"] = None

        # ── 亚马逊 BuyBox 占比 ──────────────────────────
        result["amazon_buybox_pct"] = self._calc_amazon_pct(p)

        return result

    def _calc_amazon_pct(self, p: dict) -> Optional[float]:
        """
        计算亚马逊自营赢得 BuyBox 的历史占比。

        数据来源：buyBoxSellerIdHistory
        格式：[timestamp, sellerId, timestamp, sellerId, ...]
        算法：统计 sellerId == ATVPDKIKX0DER 的次数 / 总次数

        返回：百分比（0~100），历史数据不足时返回 None
        """
        history = p.get("buyBoxSellerIdHistory", [])
        if not history or len(history) < 2:
            return None
        # 每两个元素为一组（timestamp, sellerId），取所有 sellerId
        seller_ids = history[1::2]
        if not seller_ids:
            return None
        amazon_count = sum(1 for sid in seller_ids if sid == AMAZON_SELLER_ID)
        return round(100.0 * amazon_count / len(seller_ids), 2)

    @property
    def tokens_used(self) -> int:
        """本次客户端生命周期内累计消耗的 Keepa token 数量"""
        return self._tokens_used


def _safe_idx(lst: list, idx: int) -> Optional[int]:
    """安全获取列表元素：越界或负值返回 None"""
    try:
        val = lst[idx]
        return None if (val is None or val < 0) else int(val)
    except (IndexError, TypeError):
        return None


def _cents_to_dollars(cents: Optional[int]) -> Optional[float]:
    """美分转美元（保留两位小数）"""
    if cents is None:
        return None
    return round(cents / 100.0, 2)
