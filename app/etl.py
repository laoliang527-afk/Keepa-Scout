"""
ETL script: reads sample_asins.csv, fetches Keepa data, upserts into DB.

Run: python -m app.etl
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
BATCH_SIZE = 20  # Keepa recommended batch size


async def load_supplier_costs(csv_path: str) -> dict[str, float]:
    """Load asin -> supplier_cost from CSV."""
    costs = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            asin = row["asin"].strip()
            cost = float(row["supplier_cost"].strip())
            costs[asin] = cost
    return costs


async def fetch_asins_in_batches(client: KeepaClient, asins: list[str]) -> list[dict]:
    """Fetch all ASINs from Keepa in batches. Partial success is OK."""
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
    """Compute all derived fields for one ASIN."""
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
    """Insert or replace ASIN records. Idempotent via INSERT OR REPLACE."""
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
    """Main ETL entry point."""
    csv_abspath = os.path.join(os.path.dirname(os.path.dirname(__file__)), CSV_PATH)
    if not os.path.exists(csv_abspath):
        print(f"ERROR: CSV not found at {csv_abspath}")
        return

    await init_db()

    # Load supplier costs
    costs = await load_supplier_costs(csv_abspath)
    asins = list(costs.keys())
    print(f"Loaded {len(asins)} ASINs from CSV")

    # Fetch from Keepa
    client = KeepaClient()
    keepa_results: dict[str, dict] = {}

    print(f"Fetching {len(asins)} ASINs from Keepa (batches of {BATCH_SIZE})...")
    products = await fetch_asins_in_batches(client, asins)
    for p in products:
        if p.get("asin"):
            keepa_results[p["asin"]] = p

    print(f"Got {len(keepa_results)} products from Keepa")

    # Build records
    records = []
    for asin, supplier_cost in costs.items():
        keepa_data = keepa_results.get(asin, {})
        rec = build_record(asin, supplier_cost, keepa_data)
        records.append(rec)

    await upsert_asins(records)
    print(f"ETL complete — {len(records)} ASINs upserted")
    print(f"Keepa tokens used: {client.tokens_used}")

    eligible_count = sum(1 for r in records if r.get("eligible"))
    print(f"Eligible ASINs: {eligible_count}")


if __name__ == "__main__":
    asyncio.run(run_etl())
