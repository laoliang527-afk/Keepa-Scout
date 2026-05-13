"""
Keepa API 集成测试（手动运行，不接入 CI）。

用途：
  通过实际调用 Keepa API，观察以下行为：
    - 每批最大 ASIN 数量
    - 不同 UPC 格式的接受情况
    - stats.current[] 字段含义
    - buyBoxSellerIdHistory 解码方式
    - Token 消耗规律

运行：
  python -m app.tests.keepa_integration              # 列出所有测试
  python -m app.tests.keepa_integration max_asins   # 仅运行最大 ASIN 数量测试
  python -m app.tests.keepa_integration upc          # UPC 格式测试
  python -m app.tests.keepa_integration stats        # stats 字段测试
  python -m app.tests.keepa_integration history       # BuyBox 历史记录测试
  python -m app.tests.keepa_integration tokens       # Token 消耗测试
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from app.keepa_client import KeepaClient


async def test_max_asins():
    """测试 Keepa 每批最大接受 ASIN 数量（逐步增加直到返回空）"""
    client = KeepaClient()
    known = [
        "B010MU00UM", "B0CPRLHYRB", "B0DJDMVQJG",
        "B0BZ5DMMS4", "B006JVZXJM", "B001FB5MBK",
    ]

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
    """测试 Keepa 对不同长度/格式 UPC 的接受情况"""
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
    """打印 stats.current[] 完整结构，用于理解字段含义"""
    client = KeepaClient()

    print("\n=== stats.current[] index inspection ===")
    prods = await client.fetch_products_by_asins(["B010MU00UM"], stats=90, buybox=1)
    if not prods:
        print("  No product")
        return

    p = prods[0]
    current = p.get("current", [])
    stats = p.get("stats", {})
    print(f"  ASIN: {p.get('asin')}")
    print(f"  current[] ({len(current)} entries): {current}")
    print(f"  stats.current: {stats.get('current')}")
    print(f"  buyBox object keys: {list(p.get('buybox', {}).keys())}")


async def test_buybox_history():
    """
    检查 buyBoxSellerIdHistory 的解码方式。

    Keepa 返回格式：[timestamp, sellerId, timestamp, sellerId, ...]
    取奇数位（索引 1, 3, 5, ...）即为 seller ID 序列。
    """
    client = KeepaClient()

    print("\n=== buyBoxSellerIdHistory inspection ===")
    for asin in ["B010MU00UM", "B0CPRLHYRB", "B0DJDMVQJG", "B006JVZXJM"]:
        prods = await client.fetch_products_by_asins([asin], buybox=1)
        if not prods:
            continue
        p = prods[0]
        hist = p.get("buyBoxSellerIdHistory", [])
        if not hist:
            continue
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
    """观察不同参数组合下的 Keepa token 消耗量"""
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
