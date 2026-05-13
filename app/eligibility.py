"""
FBA 套利准入规则模块。

包含两组核心函数：
  1. compute_payout  / compute_roi — 利润与 ROI 计算
  2. check_eligibility            — 5 条准入规则检查

公式依据（CHALLENGE.md）：
  payout = buybox - referral - fba - $0.50
  roi    = 100 * (payout - cost) / cost
"""

from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════
# 利润计算
# ═══════════════════════════════════════════════════════════════

def compute_payout(
    buybox: Optional[float],
    referral_fee_pct: Optional[float],
    fba_pick_pack_cents: Optional[int],
) -> float:
    """
    计算 FBA 出单后的净收入（payout）。

    参数（均来自 Keepa）：
      buybox             — BuyBox 价格（美元）
      referral_fee_pct  — 亚马逊类目佣金（如 15.0 表示 15%）
      fba_pick_pack_cents — FBA 拣货包装费（美分，Keepa 原生返回）

    公式：
      referral = buybox * referral_fee_pct / 100
      fba      = fba_pick_pack_cents / 100（转换为美元）
      storage  = $0.50（月度仓储估算）
      payout  = buybox - referral - fba - storage
    """
    if buybox is None or buybox <= 0:
        return 0.0
    if referral_fee_pct is None or referral_fee_pct < 0:
        return 0.0
    referral = buybox * (referral_fee_pct / 100)
    fba = (fba_pick_pack_cents or 0) / 100
    storage = 0.50  # 月度仓储费估算
    return buybox - referral - fba - storage


def compute_roi(
    buybox: float,
    referral_pct: float,
    fba_pick_pack_cents: int,
    supplier_cost: float,
    n_items: Optional[int],
) -> Optional[float]:
    """
    计算投资回报率（ROI）。

    参数：
      n_items — 包装件数（如 6 件装），用于计算总进货成本
                多件装时总成本 = supplier_cost * n_items
                单件装时总成本 = supplier_cost

    公式：
      payout  = compute_payout(...)  # 扣减所有亚马逊费用后的净收入
      cost    = supplier_cost * max(n_items or 1, 1)
      roi     = 100 * (payout - cost) / cost

    返回 None 表示无法计算（成本为零或价格为负）。
    """
    if supplier_cost is None or supplier_cost <= 0:
        return None
    if buybox is None or buybox <= 0:
        return None
    payout = compute_payout(buybox, referral_pct, fba_pick_pack_cents)
    items = max(n_items or 1, 1)
    total_cost = supplier_cost * items
    if total_cost <= 0:
        return None
    return 100 * (payout - total_cost) / total_cost


# ═══════════════════════════════════════════════════════════════
# 准入规则检查（5 条，顺序执行，遇首条失败即返回）
# ═══════════════════════════════════════════════════════════════

def check_eligibility(
    referral_fee_pct: Optional[float],
    sales_rank: Optional[int],
    monthly_sold: Optional[int],
    buybox: Optional[float],
    amazon_buybox_pct: Optional[float],
) -> Tuple[bool, Optional[str]]:
    """
    检查 ASIN 是否符合 FBA 套利准入条件。

    返回 (eligible, filter_failed)：
      eligible     — True = 全部通过，False = 至少一条失败
      filter_failed — 第一个失败的规则名，全部通过则为 None

    5 条规则（按优先级顺序）：
      1. referral_fee_pct > 0          — 必须存在有效佣金（否则无法盈利）
      2. sales_rank ≤ 100,000 OR monthly_sold ≥ 100
         — 需求充足：排名够好或有月销豁免（高销量可弥补排名不足）
      3. buybox ≥ $10                   — 单价太低则利润空间不足
      4. amazon_buybox_pct ≤ 80        — 亚马逊自营占比过高（>80%）难以竞争
      5. monthly_sold is null OR ≥ 100  — 月销不足（1~99）会被过滤
    """
    # 规则 1：referral_fee_pct 必须存在且大于 0
    if referral_fee_pct is None or referral_fee_pct <= 0:
        return False, "referral_fee_pct"

    # 规则 2：排名达标（≤100k）或月销豁免（≥100）
    rank_ok = (sales_rank is not None and sales_rank <= 100_000)
    sold_ok = (monthly_sold is not None and monthly_sold >= 100)
    if not (rank_ok or sold_ok):
        return False, "rank"

    # 规则 3：BuyBox 单价不低于 $10
    if buybox is None or buybox < 10:
        return False, "buybox"

    # 规则 4：亚马逊自营 BuyBox 占比不超过 80%
    if amazon_buybox_pct is None or amazon_buybox_pct > 80:
        return False, "amazon_pct"

    # 规则 5：月销 null 或 ≥100（1~99 之间会被过滤）
    if monthly_sold is not None and monthly_sold < 100:
        return False, "monthly_sold"

    return True, None
