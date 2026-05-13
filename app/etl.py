"""
ETL 脚本：从 CSV 读取 ASIN 列表，调用 Keepa API，批量入库。

流程：
  1. 读取 data/sample_asins.csv（ASIN + supplier_cost）
  2. 批量请求 Keepa API（每批最多 20 个 ASIN）
  3. 解析 Keepa 响应，计算 ROI 及准入状态
  4. INSERT OR REPLACE 入库（幂等，可重复运行）

运行：python -m app.etl
"""

import asyncio
import csv
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

from app.database import async_session_maker, init_db
from app.models import Asin
from app.eligibility import compute_roi, check_eligibility
from app.keepa_client import KeepaClient

load_dotenv()

CSV_PATH = os.getenv("CSV_PATH", "data/sample_asins.csv")
BATCH_SIZE = 20  # Keepa 建议每批 20 个 ASIN


async def load_supplier_costs(csv_path: str) -> dict[str, float]:
    """
    读取 CSV 文件，返回 {asin: supplier_cost} 字典。

    CSV 格式：asin,supplier_cost
    """
    costs = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            asin = row["asin"].strip()
            cost = float(row["supplier_cost"].strip())
            costs[asin] = cost
    return costs


async def fetch_asins_in_batches(client: KeepaClient, asins: list[str]) -> list[dict]:
    """
    批量从 Keepa 获取 ASIN 数据。

    遇到网络错误时保存已获取的 ASIN 并退出；
    每批之间等待 0.5 秒避免触发限流。
    """
    all_parsed = []
    for i in range(0, len(asins), BATCH_SIZE):
        batch = asins[i : i + BATCH_SIZE]
        print(f"  Fetching batch {i // BATCH_SIZE + 1}: {batch[:3]}... ({len(batch)} ASINs)")
        try:
            products = await client.fetch_products_by_asins(batch)
            for p in products:
                parsed = client.parse_product(p)
                all_parsed.append(parsed)
        except RuntimeError as e:
            print(f"  Batch failed, saving {len(all_parsed)} products so far: {e}")
            break
        await asyncio.sleep(0.5)
    return all_parsed


def build_record(
    asin: str,
    supplier_cost: float,
    keepa_data: dict,
) -> dict:
    """
    根据 Keepa 数据和供应商成本，构建一条完整的 ASIN 记录。

    计算步骤：
      1. 提取 BuyBox、佣金、FBA 费等字段
      2. 调用 compute_roi() 计算 ROI
      3. 调用 check_eligibility() 判断是否符合准入规则
    """
    buybox = keepa_data.get("buybox") if keepa_data else None
    referral_fee = keepa_data.get("referral_fee_pct") if keepa_data else None
    fba_cents = keepa_data.get("fba_pick_pack_cents") or 0
    sales_rank = keepa_data.get("sales_rank") if keepa_data else None
    monthly_sold = keepa_data.get("monthly_sold") if keepa_data else None
    n_items = keepa_data.get("number_of_items") if keepa_data else None
    amazon_pct = keepa_data.get("amazon_buybox_pct") if keepa_data else None

    title = keepa_data.get("title") if keepa_data else None
    brand = keepa_data.get("brand") if keepa_data else None

    if keepa_data:
        roi = compute_roi(buybox, referral_fee, fba_cents, supplier_cost, n_items)
        eligible, filter_failed = check_eligibility(
            referral_fee, sales_rank, monthly_sold, buybox, amazon_pct
        )
    else:
        roi = None
        eligible = False
        filter_failed = "not_found"

    return {
        "asin": asin,
        "title": title,
        "brand": brand,
        "buybox": buybox,
        "referral_fee_pct": referral_fee,
        "fba_pick_pack_cents": fba_cents or None,
        "sales_rank": sales_rank,
        "monthly_sold": monthly_sold,
        "number_of_items": n_items,
        "amazon_buybox_pct": amazon_pct,
        "supplier_cost": supplier_cost,
        "computed_roi_pct": roi,
        "eligible": eligible,
        "filter_failed": filter_failed,
        "updated_at": datetime.now(timezone.utc),
    }


async def upsert_asins(records: list[dict]):
    """
    将 ASIN 记录批量写入数据库。

    使用 INSERT OR REPLACE：ASIN 存在则更新，不存在则插入。
    每次运行 ETL 时结果一致（幂等）。
    """
    if not records:
        return
    from sqlalchemy import text
    async with async_session_maker() as session:
        for rec in records:
            await session.execute(
                text("""
                    INSERT OR REPLACE INTO asins
                    (asin, title, brand, buybox, referral_fee_pct, fba_pick_pack_cents,
                     sales_rank, monthly_sold, number_of_items, amazon_buybox_pct,
                     supplier_cost, computed_roi_pct, eligible, filter_failed, updated_at)
                    VALUES
                    (:asin, :title, :brand, :buybox, :referral_fee_pct, :fba_pick_pack_cents,
                     :sales_rank, :monthly_sold, :number_of_items, :amazon_buybox_pct,
                     :supplier_cost, :computed_roi_pct, :eligible, :filter_failed, :updated_at)
                """),
                {**rec, "updated_at": datetime.now(timezone.utc)},
            )
        await session.commit()


async def run_etl():
    """ETL 主入口"""
    csv_abspath = os.path.join(os.path.dirname(os.path.dirname(__file__)), CSV_PATH)
    if not os.path.exists(csv_abspath):
        print(f"ERROR: CSV not found at {csv_abspath}")
        return

    await init_db()

    # 1. 读取供应商成本
    costs = await load_supplier_costs(csv_abspath)
    asins = list(costs.keys())
    print(f"Loaded {len(asins)} ASINs from CSV")

    # 2. 从 Keepa 获取数据
    client = KeepaClient()
    keepa_results: dict[str, dict] = {}

    print(f"Fetching {len(asins)} ASINs from Keepa (batches of {BATCH_SIZE})...")
    products = await fetch_asins_in_batches(client, asins)
    for p in products:
        if p.get("asin"):
            keepa_results[p["asin"]] = p

    print(f"Got {len(keepa_results)} products from Keepa")

    # 3. 构建记录（计算 ROI + 准入状态）
    records = []
    for asin, supplier_cost in costs.items():
        keepa_data = keepa_results.get(asin, {})
        rec = build_record(asin, supplier_cost, keepa_data)
        records.append(rec)

    # 4. 入库
    await upsert_asins(records)
    print(f"ETL complete — {len(records)} ASINs upserted")
    print(f"Keepa tokens used: {client.tokens_used}")

    eligible_count = sum(1 for r in records if r.get("eligible"))
    print(f"Eligible ASINs: {eligible_count}")


if __name__ == "__main__":
    asyncio.run(run_etl())
