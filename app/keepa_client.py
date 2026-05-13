"""
Keepa API client with key rotation, batch requests, and token tracking.
"""

import os
from typing import Optional

import httpx

from dotenv import load_dotenv

load_dotenv()

KEEPA_KEYS: list[str] = [
    k.strip()
    for k in os.getenv("KEEPA_API_KEYS", "").split(",")
    if k.strip()
]
KEEPA_DOMAIN = 1  # 1 = Amazon.com (US)
KEEPA_BASE = "https://api.keepa.com"

# Key order: prefer key index 1 (has stable ~300 token quota);
# fall back to key 0 if key 1 is exhausted.
_KEY_ORDER = [1, 0]

# Keepa stats.current[] index mapping (domain=1 / US)
# https://keepa.com/#!discuss/t/product-object/116
STAT_BUYBOX_PRICE = 0
STAT_BUYBOX_SHIPPING = 3
STAT_SALES_RANK = 2
STAT_NEW_PRICE = 1
STAT_NEW_SHIPPING = 4

# Keepa seller ID for Amazon itself
AMAZON_SELLER_ID = "ATVPDKIKX0DER"


class KeepaClient:
    def __init__(self, keys: Optional[list[str]] = None):
        self.keys = keys or KEEPA_KEYS
        self._idx = 0
        self._tokens_used = 0

    @property
    def _key(self) -> str:
        return self.keys[self._idx % len(self.keys)]

    def _next_key(self):
        self._idx += 1
        if self._idx >= len(self.keys):
            self._idx = 0

    async def _request(self, params: dict) -> dict:
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
                    print(f"  [keepa] key_idx={order_idx} status={resp.status_code} tokensLeft={body.get('tokensLeft')} consumed={body.get('tokensConsumed')}")
                    if resp.status_code == 200:
                        if "tokensConsumed" in body:
                            self._tokens_used += body["tokensConsumed"]
                        return body
                    elif resp.status_code in (402, 429):
                        print(f"  [keepa] key_idx={order_idx} returned {resp.status_code}, skipping to next key")
                        continue
                    elif resp.status_code == 422:
                        # Invalid ASIN/UPC/code format — return empty result for this key
                        print(f"  [keepa] key_idx={order_idx} returned 422 (invalid code), skipping to next key")
                        continue
                    else:
                        resp.raise_for_status()
                except httpx.HTTPStatusError as e:
                    print(f"  [keepa] HTTPError key_idx={order_idx} status={e.response.status_code}")
                    if e.response.status_code in (402, 429):
                        print(f"  [keepa] key_idx={order_idx} returned {e.response.status_code}, skipping to next key")
                        continue
                    elif e.response.status_code == 422:
                        print(f"  [keepa] key_idx={order_idx} returned 422 (invalid code), skipping to next key")
                        continue
                    raise
        raise RuntimeError("All Keepa keys exhausted")

    async def fetch_products_by_asins(
        self, asins: list[str], stats: int = 90, buybox: int = 1, fbafees: int = 1
    ) -> list[dict]:
        """
        Fetch product data for a list of ASINs.
        Keepa accepts up to ~100 ASINs per request.
        Returns a list of product dicts (or empty list if none found).
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
        Fetch product data by UPC/EAN code.
        Returns a list of product dicts (can be multiple ASINs for same UPC).
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
        Parse a Keepa product dict into normalized fields.
        All prices in dollars (Keepa returns cents).
        -1 or missing values become None.

        Data source strategy:
        - BuyBox price  → stats.buyBoxPrice (most reliable), fallback to current[0]
        - Sales rank    → stats.avg[3] (90-day average, most stable), fallback to current[2]
        The top-level current[] is often stale or -1; always prefer the stats snapshot.
        """
        result = {}

        result["asin"] = p.get("asin")
        result["title"] = p.get("title")
        result["brand"] = p.get("brand")

        # numberOfItems (e.g. "6-pack" has 6)
        result["number_of_items"] = p.get("numberOfItems") or p.get("packageQuantity")

        # ── BuyBox price ──────────────────────────────────────────────
        # stats.buyBoxPrice is the most reliable source (directly from stats snapshot).
        # Fall back to top-level current[0] if stats.buyBoxPrice is missing.
        stats_data = p.get("stats", {}) or {}
        buybox_cents = stats_data.get("buyBoxPrice")
        if buybox_cents is None or buybox_cents < 0:
            buybox_cents = _safe_idx(p.get("current") or [], 0)
        result["buybox"] = _cents_to_dollars(buybox_cents)

        # ── Sales rank ──────────────────────────────────────────────
        # stats.avg[3] = 90-day average sales rank — most stable source.
        # Fall back to top-level current[2] if unavailable.
        stats_avg = stats_data.get("avg") or []
        sales_rank_cents = _safe_idx(stats_avg, 3)
        if sales_rank_cents is None or sales_rank_cents < 0:
            sales_rank_cents = _safe_idx(p.get("current") or [], 2)
        result["sales_rank"] = int(sales_rank_cents) if sales_rank_cents is not None else None

        # Referral fee %
        result["referral_fee_pct"] = p.get("referralFeePercentage")
        if result["referral_fee_pct"] == -1:
            result["referral_fee_pct"] = None

        # FBA pick & pack fee (cents → cents int)
        fba_fees = p.get("fbaFees") or {}
        result["fba_pick_pack_cents"] = fba_fees.get("pickAndPackFee")
        if result["fba_pick_pack_cents"] == -1:
            result["fba_pick_pack_cents"] = None

        # Monthly sold (from stats)
        result["monthly_sold"] = stats_data.get("monthlySoldAverage")
        if result["monthly_sold"] == -1:
            result["monthly_sold"] = None

        # Amazon BuyBox %
        result["amazon_buybox_pct"] = self._calc_amazon_pct(p)

        return result

    def _calc_amazon_pct(self, p: dict) -> Optional[float]:
        """
        Calculate the fraction of BuyBox wins by Amazon.
        buyBoxSellerIdHistory: alternating [timestamp, sellerId, ...]
        Count entries where sellerId == ATVPDKIKX0DER, divide by total.
        """
        history = p.get("buyBoxSellerIdHistory", [])
        if not history or len(history) < 2:
            return None
        # history is [ts, sellerId, ts, sellerId, ...]
        seller_ids = history[1::2]  # every other item starting at index 1
        if not seller_ids:
            return None
        amazon_count = sum(1 for sid in seller_ids if sid == AMAZON_SELLER_ID)
        return round(100.0 * amazon_count / len(seller_ids), 2)

    @property
    def tokens_used(self) -> int:
        return self._tokens_used


def _safe_idx(lst: list, idx: int) -> Optional[int]:
    try:
        val = lst[idx]
        return None if (val is None or val < 0) else int(val)
    except (IndexError, TypeError):
        return None


def _cents_to_dollars(cents: Optional[int]) -> Optional[float]:
    if cents is None:
        return None
    return round(cents / 100.0, 2)
