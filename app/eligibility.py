from typing import Optional, Tuple

# ── Payout ─────────────────────────────────────────────────────────────────────

def compute_payout(buybox: float, referral_fee_pct: float, fba_pick_pack_cents: int) -> float:
    """
    Net payout after Amazon fees.
    buybox: in dollars
    referral_fee_pct: e.g. 15.0 for 15%
    fba_pick_pack_cents: Keepa returns cents
    """
    if buybox <= 0 or referral_fee_pct < 0:
        return 0.0
    referral = buybox * (referral_fee_pct / 100)
    fba = (fba_pick_pack_cents or 0) / 100
    storage = 0.50  # monthly storage estimate
    return buybox - referral - fba - storage


def compute_roi(
    buybox: float,
    referral_pct: float,
    fba_pick_pack_cents: int,
    supplier_cost: float,
    n_items: Optional[int],
) -> Optional[float]:
    """
    ROI = 100 * (payout - total_cost) / total_cost
    total_cost = supplier_cost * max(n_items or 1, 1)
    Returns None if cost is zero or negative.
    """
    if supplier_cost is None or supplier_cost <= 0:
        return None
    payout = compute_payout(buybox, referral_pct, fba_pick_pack_cents)
    items = max(n_items or 1, 1)
    total_cost = supplier_cost * items
    if total_cost <= 0:
        return None
    return 100 * (payout - total_cost) / total_cost


# ── Eligibility checks ─────────────────────────────────────────────────────────

def check_eligibility(
    referral_fee_pct: Optional[float],
    sales_rank: Optional[int],
    monthly_sold: Optional[int],
    buybox: Optional[float],
    amazon_buybox_pct: Optional[float],
) -> Tuple[bool, Optional[str]]:
    """
    Returns (eligible: bool, filter_failed: str or None).
    Applies 5 rules in order; returns the first failed rule name.
    """
    # Rule 1: referral_fee_pct must exist (> 0)
    if referral_fee_pct is None or referral_fee_pct <= 0:
        return False, "referral_fee_pct"

    # Rule 2: sales_rank <= 100,000 OR monthly_sold >= 100 (demand exemption)
    rank_ok = (sales_rank is not None and sales_rank <= 100_000)
    sold_ok = (monthly_sold is not None and monthly_sold >= 100)
    if not (rank_ok or sold_ok):
        return False, "rank"

    # Rule 3: buybox >= $10
    if buybox is None or buybox < 10:
        return False, "buybox"

    # Rule 4: amazon_buybox_pct <= 80
    if amazon_buybox_pct is None or amazon_buybox_pct > 80:
        return False, "amazon_pct"

    # Rule 5: monthly_sold is null OR >= 100
    if monthly_sold is not None and monthly_sold < 100:
        return False, "monthly_sold"

    return True, None
