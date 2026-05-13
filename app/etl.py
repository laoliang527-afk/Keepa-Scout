"""
ETL script: reads sample_asins.csv, upserts ASIN records into SQLite.

This file is the "business logic" layer of the ETL:
  - read CSV
  - call Keepa API (added in commit 3)
  - compute ROI / eligibility
  - upsert into DB

Run: python -m app.etl
"""

import asyncio
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from sqlalchemy import select

from app.database import get_db, init_db, async_session_maker
from app.models import Asin
from app.eligibility import compute_roi, check_eligibility

load_dotenv()


CSV_PATH = os.getenv("CSV_PATH", "data/sample_asins.csv")


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


async def compute_fields_for_asin(
    asin: str,
    supplier_cost: float,
    buybox: float | None,
    referral_fee_pct: float | None,
    fba_pick_pack_cents: int | None,
    sales_rank: int | None,
    monthly_sold: int | None,
    number_of_items: int | None,
    amazon_buybox_pct: float | None,
) -> dict:
    """
    Compute ROI + eligibility + metadata for a single ASIN.
    All Keepa-sourced fields are passed in; this function only computes derived values.
    """
    roi = None
    if buybox is not None and referral_fee_pct is not None:
        roi = compute_roi(buybox, referral_fee_pct, fba_pick_pack_cents or 0,
                           supplier_cost, number_of_items)

    eligible, filter_failed = check_eligibility(
        referral_fee_pct,
        sales_rank,
        monthly_sold,
        buybox,
        amazon_buybox_pct,
    )

    return {
        "asin": asin,
        "supplier_cost": supplier_cost,
        "buybox": buybox,
        "referral_fee_pct": referral_fee_pct,
        "fba_pick_pack_cents": fba_pick_pack_cents,
        "sales_rank": sales_rank,
        "monthly_sold": monthly_sold,
        "number_of_items": number_of_items,
        "amazon_buybox_pct": amazon_buybox_pct,
        "computed_roi_pct": roi,
        "eligible": eligible,
        "filter_failed": filter_failed,
    }


async def upsert_asins(records: list[dict]):
    """Insert or replace ASIN records. Idempotent."""
    if not records:
        return
    async with async_session_maker() as session:
        for rec in records:
            obj = Asin(**rec)
            session.add(obj)
        await session.commit()


async def run_etl():
    """
    Main ETL entry point.
    In this skeleton (commit 2) we only load supplier costs from CSV.
    Keepa data will be fetched in commit 3.
    """
    csv_abspath = os.path.join(os.path.dirname(os.path.dirname(__file__)), CSV_PATH)
    if not os.path.exists(csv_abspath):
        print(f"ERROR: CSV not found at {csv_abspath}")
        return

    await init_db()
    costs = await load_supplier_costs(csv_abspath)
    print(f"Loaded {len(costs)} supplier costs from CSV")

    # Build skeleton records with only supplier_cost populated.
    # Keepa fields will be added in commit 3.
    records = []
    for asin, supplier_cost in costs.items():
        # Placeholder values for Keepa fields — will be filled by keepa_client
        rec = await compute_fields_for_asin(
            asin=asin,
            supplier_cost=supplier_cost,
            buybox=None,
            referral_fee_pct=None,
            fba_pick_pack_cents=None,
            sales_rank=None,
            monthly_sold=None,
            number_of_items=None,
            amazon_buybox_pct=None,
        )
        records.append(rec)

    await upsert_asins(records)
    print(f"ETL complete — {len(records)} ASINs upserted")


if __name__ == "__main__":
    asyncio.run(run_etl())
