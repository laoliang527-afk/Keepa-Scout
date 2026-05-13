"""
Keepa API empirical tests.
Run individually: python -m app.tests.keepa_integration [test_name]
"""

import asyncio
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.keepa_client import KeepaClient


async def test_max_asins():
    """Find the max ASINs Keepa accepts per /product call."""
    client = KeepaClient()
    known = ["B010MU00UM", "B0CPRLHYRB", "B0DJDMVQJG",
             "B0BZ5DMMS4", "B006JVZXJM", "B001FB5MBK"]

    print("\n=== Max ASINs per call test ===")
    for size in [5, 10, 20, 50, 100, 200, 500]:
        asins = (known * (size // len(known) + 1))[:size]
        try:
            prods = await client.fetch_products_by_asins(asins)
            print(f"  size={size}: got {len(prods)} products")
            if len(prods) == 0:
                break
        except Exception as e:
            print(f"  size={size}: ERROR {e}")
            break


async def test_upc_formats():
    """Test which UPC lengths Keepa accepts."""
    client = KeepaClient()

    cases = [
        ("11d-UPCE",  "01234567895"),
        ("12d-UPCA",  "012345678905"),
        ("13d-EAN13", "0012345678905"),
        ("14d-ITF14", "00012345678905"),
        ("R-12d-UPCA","0081124101532"),
        ("R-13d-EAN", "5901234123457"),
        ("R-14d-ITF", "00012345678901"),
        ("F-11d",     "12345678901"),
        ("F-12d",     "123456789012"),
        ("F-13d",     "1234567890123"),
        ("F-14d",     "12345678901234"),
    ]

    print("\n=== UPC format acceptance ===")
    for label, code in cases:
        try:
            prods = await client.fetch_product_by_upc(code)
            asins = [p.get("asin") for p in prods[:3]]
            print(f"  [{label}] '{code}' ({len(code)}d) -> {len(prods)} products  asins={asins}")
        except Exception as e:
            print(f"  [{label}] '{code}' -> ERROR: {e}")


async def test_stats_current():
    """Print full stats.current[] for inspection."""
    client = KeepaClient()

    print("\n=== stats.current[] index inspection ===")
    prods = await client.fetch_products_by_asins(["B010MU00UM"], stats=90, buybox=1)
    if not prods:
        print("  No product"); return

    p = prods[0]
    current = p.get("current", [])
    stats = p.get("stats", {})
    print(f"  ASIN: {p.get('asin')}")
    print(f"  current[] ({len(current)} entries): {current}")
    print(f"  stats.current: {stats.get('current')}")
    print(f"  buyBox object keys: {list(p.get('buybox',{}).keys())}")


async def test_buybox_history():
    """Inspect buyBoxSellerIdHistory decoding."""
    client = KeepaClient()

    print("\n=== buyBoxSellerIdHistory inspection ===")
    for asin in ["B010MU00UM", "B0CPRLHYRB", "B0DJDMVQJG", "B006JVZXJM"]:
        prods = await client.fetch_products_by_asins([asin], buybox=1)
        if not prods: continue
        p = prods[0]
        hist = p.get("buyBoxSellerIdHistory", [])
        if not hist: continue
        sellers = hist[1::2]
        amazon_count = sum(1 for s in sellers if s == "ATVPDKIKX0DER")
        total = len(sellers)
        pct = round(100 * amazon_count / total, 2) if total else 0
        print(f"  ASIN={asin}  history_len={len(hist)}  seller_entries={total}")
        print(f"  amazon={amazon_count}/{total} = {pct}%")
        print(f"  first 6 seller IDs: {sellers[:6]}")
        print(f"  first 12 history entries: {hist[:12]}")
        return

    print("  No ASIN with history found")


async def test_token_cost():
    """Token cost formula observation."""
    client = KeepaClient()

    print("\n=== Token cost observation ===")

    def reset():
        client._tokens_used = 0

    reset()
    await client.fetch_products_by_asins(["B010MU00UM"])
    t1 = client.tokens_used
    print(f"  1 ASIN (stats=90,buybox=1,fbafees=1): {t1} tokens consumed")

    reset()
    await client.fetch_products_by_asins(["B010MU00UM"], stats=0, buybox=0, fbafees=0)
    t2 = client.tokens_used
    print(f"  1 ASIN (stats=0,buybox=0,fbafees=0): {t2} tokens consumed")

    reset()
    await client.fetch_products_by_asins(["B010MU00UM"] * 20)
    t3 = client.tokens_used
    print(f"  20 ASINs (default params): {t3} tokens consumed")

    reset()
    await client.fetch_products_by_asins(["B010MU00UM"] * 20, stats=0, buybox=0, fbafees=0)
    t4 = client.tokens_used
    print(f"  20 ASINs (minimal params): {t4} tokens consumed")

    if t3 and t4:
        print(f"  cost_per_asin_full=~{t3/20:.1f}, cost_per_asin_minimal=~{t4/20:.1f}")


async def main():
    tests = {
        "max_asins": test_max_asins,
        "upc": test_upc_formats,
        "stats": test_stats_current,
        "history": test_buybox_history,
        "tokens": test_token_cost,
    }

    name = sys.argv[1] if len(sys.argv) > 1 else None

    if name and name in tests:
        await tests[name]()
    else:
        print("Usage: python -m app.tests.keepa_integration [max_asins|upc|stats|history|tokens]")
        for n in tests:
            print(f"  - {n}")


if __name__ == "__main__":
    asyncio.run(main())
