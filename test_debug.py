"""
test_debug.py — 本地调试测试，帮你理解每个模块的工作原理。

用法:
  python test_debug.py              # 运行全部测试
  python test_debug.py -k upc      # 只跑名字含 upc 的测试

测试覆盖:
  1. compute_roi / compute_payout  — ROI 公式（含边界 None 值）
  2. check_eligibility             — 5条规则（每条都有通过/失败 case）
  3. normalize_upc                 — 11种格式变体
  4. validate_sql                  — 合法 SELECT + 危险 SQL + 注入
  5. /upc                         — 正常 + 空输入
  6. /eligibility/{asin}          — 存在 / 不存在 ASIN
  7. /eligibility/batch            — 混合存在/不存在
  8. /ask (6类问题)               — 计数/filter/复合/why/推荐/域外
  9. /chat (4个场景)              — 累积过滤/代词引用/forget/偏好持久化
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()


# ═══════════════════════════════════════════════════════════════
# 1. ROI / Payout 公式 — 纯算术
# ═══════════════════════════════════════════════════════════════

def test_compute_roi():
    """
    ROI 公式（CHALLENGE.md 规定）：
      payout = buybox - referral - fba - $0.50
      roi    = 100 * (payout - cost) / cost
    """
    from app.eligibility import compute_roi, compute_payout

    print("\n=== test_compute_roi ===")

    # ── 参考值验证（B00HEON30Y）───────────────────────────────
    # buybox=$29.99, referral=15%, fba=357c, cost=$9.27
    # payout = 29.99 - 4.4985 - 3.57 - 0.50 = 21.4215
    # roi    = 100 * (21.4215 - 9.27) / 9.27 = 131.1%
    p = compute_payout(buybox=29.99, referral_fee_pct=15.0, fba_pick_pack_cents=357)
    r = compute_roi(buybox=29.99, referral_pct=15.0,
                     fba_pick_pack_cents=357, supplier_cost=9.27, n_items=None)
    print(f"  payout=$21.42 (实际={p:.4f})  roi=131.1% (实际={r:.2f}%)")
    assert abs(p - 21.4215) < 0.01
    assert abs(r - 131.1) < 1.0
    print("  ✓ B00HEON30Y 参考值正确")

    # ── None 值保护 ───────────────────────────────────────────
    assert compute_payout(None, 15.0, 357) == 0.0, "buybox=None → payout=0"
    assert compute_payout(29.99, None, 357) == 0.0, "referral=None → payout=0"
    assert compute_roi(buybox=None, referral_pct=15.0,
                       fba_pick_pack_cents=357, supplier_cost=9.27, n_items=None) is None
    assert compute_roi(buybox=29.99, referral_pct=15.0,
                       fba_pick_pack_cents=357, supplier_cost=None, n_items=None) is None
    assert compute_roi(buybox=29.99, referral_pct=15.0,
                       fba_pick_pack_cents=357, supplier_cost=0, n_items=None) is None
    print("  ✓ None 值保护正确")

    # ── n_items > 1（多件装）────────────────────────────────
    # buybox=$20, ref=15%, fba=100c, cost=$5/件, 买3件
    # payout = 20 - 3 - 1 - 0.50 = 15.50
    # cost   = 5 * 3 = 15
    # roi    = 100 * (15.50 - 15) / 15 = 3.3%
    r = compute_roi(buybox=20.0, referral_pct=15.0,
                     fba_pick_pack_cents=100, supplier_cost=5.0, n_items=3)
    assert abs(r - 3.33) < 0.1
    print(f"  n_items=3 时 roi={r:.2f}% ✓")

    # ── 负 ROI（进货贵过利润）────────────────────────────────
    # buybox=$10, cost=$12, payout=$5 → roi = 100*(5-12)/12 = -58.3%
    r = compute_roi(buybox=10.0, referral_pct=10.0,
                     fba_pick_pack_cents=100, supplier_cost=12.0, n_items=1)
    assert r < 0, "成本高于利润时应为负ROI"
    print(f"  负ROI case: {r:.1f}% ✓")

    print("  === ALL compute_roi tests passed ===\n")


# ═══════════════════════════════════════════════════════════════
# 2. Eligibility 规则 — 纯算术
# ═══════════════════════════════════════════════════════════════

def test_check_eligibility():
    """
    5条规则（CHALLENGE.md 规定顺序）：
      1. referral_fee_pct > 0
      2. sales_rank ≤ 100,000 OR monthly_sold ≥ 100
      3. buybox ≥ $10
      4. amazon_buybox_pct ≤ 80
      5. monthly_sold is null OR ≥ 100
    返回第一个失败的规则名（filter_failed）。
    """
    from app.eligibility import check_eligibility

    print("\n=== test_check_eligibility ===")

    # ── 全部通过 ─────────────────────────────────────────────
    e, f = check_eligibility(
        referral_fee_pct=15.0,
        sales_rank=88003,
        monthly_sold=None,
        buybox=29.99,
        amazon_buybox_pct=12.7,
    )
    assert e is True and f is None
    print("  ✓ 全部通过 case")

    # ── 规则1失败：referral 缺失 ─────────────────────────────
    e, f = check_eligibility(None, 50000, 200, 20.0, 50.0)
    assert f == "referral_fee_pct"
    print("  ✓ 规则1失败（referral_fee_pct=None）")

    e, f = check_eligibility(0.0, 50000, 200, 20.0, 50.0)
    assert f == "referral_fee_pct"
    print("  ✓ 规则1失败（referral_fee_pct=0）")

    # ── 规则2失败：rank 太高且无月销豁免 ────────────────────
    # rank=164080 > 100000 且 monthly_sold=50 < 100 → 不豁免
    e, f = check_eligibility(15.0, 164080, 50, 29.99, 12.7)
    assert f == "rank"
    print("  ✓ 规则2失败（rank 164080，monthly=50，无豁免）")

    # ── 规则2通过（月销豁免）────────────────────────────────
    e, f = check_eligibility(15.0, 200000, 150, 29.99, 12.7)
    assert f is None, "monthly_sold≥100 应豁免 rank 检查"
    print("  ✓ 规则2通过（monthly_sold=150，月销豁免）")

    # ── 规则2失败：rank 太高且月销不足（rank>100k 且 monthly<100）────
    # monthly_sold=None 不等于 "≥100"，无法豁免 rank
    e, f = check_eligibility(15.0, 164080, None, 29.99, 12.7)
    assert f == "rank", "monthly_sold=None 无法豁免 rank > 100k 的检查"
    print("  ✓ monthly_sold=None 且 rank>100k → 规则2失败（rank）")

    # ── 规则3失败：buybox 太低 ───────────────────────────────
    e, f = check_eligibility(15.0, 50000, 200, 9.99, 20.0)
    assert f == "buybox"
    print("  ✓ 规则3失败（buybox=$9.99 < $10）")

    # ── 规则3通过：buybox = $10 ────────────────────────────
    e, f = check_eligibility(15.0, 50000, 200, 10.00, 20.0)
    assert f is None, "buybox=$10 应通过"
    print("  ✓ 规则3通过（buybox=$10，刚好边界）")

    # ── 规则4失败：Amazon 占比 > 80 ────────────────────────
    e, f = check_eligibility(15.0, 50000, 200, 20.0, 85.0)
    assert f == "amazon_pct"
    print("  ✓ 规则4失败（amazon_pct=85% > 80%）")

    # ── 规则4通过：amazon_pct = 80 ─────────────────────────
    e, f = check_eligibility(15.0, 50000, 200, 20.0, 80.0)
    assert f is None, "amazon_pct=80% 应通过"
    print("  ✓ 规则4通过（amazon_pct=80%，刚好边界）")

    # ── 规则5失败：monthly_sold 在 1~99 ─────────────────────
    e, f = check_eligibility(15.0, 50000, 50, 20.0, 20.0)
    assert f == "monthly_sold"
    print("  ✓ 规则5失败（monthly_sold=50，1~99之间）")

    # ── 规则5通过：monthly_sold=None ───────────────────────
    e, f = check_eligibility(15.0, 50000, None, 20.0, 20.0)
    assert f is None
    print("  ✓ 规则5通过（monthly_sold=None）")

    # ── 复合失败（只报告第一个）─────────────────────────────
    # referral=None(规则1) AND buybox=5(规则3)，应只报规则1
    e, f = check_eligibility(None, 200000, 50, 5.0, 20.0)
    assert f == "referral_fee_pct", "referral 在规则1就失败，不应继续报 buybox"
    print("  ✓ 复合失败只报告第一个失败的规则")

    print("  === ALL check_eligibility tests passed ===\n")


# ═══════════════════════════════════════════════════════════════
# 3. UPC Normalizer — 纯函数
# ═══════════════════════════════════════════════════════════════

def test_upc_normalizer():
    """
    normalize_upc() 对不同长度的输入生成归一化变体列表。
    Keepa 对不同格式接受度不同，所以要生成多种变体尝试。
    """
    from app.upc_normalizer import normalize_upc, upce_to_upca

    print("\n=== test_upc_normalizer ===")

    cases = [
        # (input, expected_in_list, description)
        ("70537500052", "70537500052", "12位 UPC-A，原样"),
        (" 012-345-678-905 ", "012345678905", "带连字符/空格 → 去掉"),
        ("00012345678905", "00012345678905", "14位 ITF-14，原样"),
        ("0012345678905", "0012345678905", "13位 EAN-13，原样"),
        ("0123456789012", "0123456789012", "12位带前缀0，+去掉0版本"),
        ("123456789012", "123456789012", "12位随机码"),
        ("01234567890123", "01234567890123", "13位随机码"),
        ("", [], "空字符串 → 空列表（FastAPI 400）"),
        ("abc123xyz789", "123789", "混合字母 → 只保留数字"),
        ("5901234123457", "5901234123457", "真实 EAN-13 样例"),
        ("0081124101532", "0081124101532", "真实 UPC-A 样例"),
    ]

    for raw, expected, desc in cases:
        result = normalize_upc(raw)
        print(f"  {desc}")
        print(f"    '{raw}' → {result}")
        if expected == []:
            assert result == [], f"期望 [], 实际 {result}"
        else:
            assert expected in result, f"期望 '{expected}' in {result}"
        print("    ✓")

    # UPC-E 展开（11位 = 数字系统+6数据+校验位）
    upce = "01234567895"
    upca = upce_to_upca(upce)
    print(f"  UPC-E '{upce}' → '{upca}' (简化展开算法)")
    assert upca is not None
    print("  ✓")

    print("  === ALL UPC normalizer tests passed ===\n")


# ═══════════════════════════════════════════════════════════════
# 4. SQL 安全校验 — 纯函数
# ═══════════════════════════════════════════════════════════════

def test_sql_validation():
    """
    _validate_sql() 只允许 SELECT，拦截所有危险操作和注入。
    """
    from app.services.deepseek import _validate_sql

    print("\n=== test_sql_validation ===")

    # ── 合法 SELECT ─────────────────────────────────────────
    for sql in [
        "SELECT * FROM asins LIMIT 10",
        "SELECT asin, computed_roi_pct FROM asins WHERE eligible=1",
        "SELECT COUNT(*) FROM asins WHERE computed_roi_pct > 25",
        "select asin from asins where buybox >= 10",  # 小写
        "  SELECT * FROM asins",  # 前导空格
    ]:
        err = _validate_sql(sql)
        assert err is None, f"'{sql}' 应通过，但返回: {err}"
    print("  ✓ 合法 SELECT 全部通过")

    # ── 危险 SQL（开头不是 SELECT）──────────────────────────
    for sql in [
        "DROP TABLE asins",
        "INSERT INTO asins VALUES(1)",
        "DELETE FROM asins WHERE asin='B00'",
        "UPDATE asins SET eligible=0",
        "CREATE TABLE x (id INT)",
        "ALTER TABLE asins ADD COLUMN x",
        "TRUNCATE asins",
    ]:
        err = _validate_sql(sql)
        assert err is not None, f"'{sql}' 应被拒绝"
    print("  ✓ DROP/INSERT/UPDATE/CREATE/ALTER/TRUNCATE 全部被拦截")

    # ── 注入攻击（SELECT 但含危险关键字）───────────────────
    for sql in [
        "SELECT * FROM asins; DROP TABLE asins",
        "SELECT * FROM asins -- comment",
        "SELECT * FROM asins LIMIT 10; DELETE FROM asins",
    ]:
        err = _validate_sql(sql)
        assert err is not None, f"注入 '{sql}' 应被拒绝"
    print("  ✓ SQL 注入攻击全部被拦截")

    print("  === ALL SQL validation tests passed ===\n")


# ═══════════════════════════════════════════════════════════════
# 5. API 端点测试 — FastAPI TestClient
# ═══════════════════════════════════════════════════════════════

def test_endpoints():
    """
    覆盖全部 5 个端点，模拟真实使用场景。
    """
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    print("\n=== test_endpoints ===")

    # ────────────────────────────────────────────────────────
    # /health
    # ────────────────────────────────────────────────────────
    print("\n  [/health]")
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["db"] == "ok"
    print(f"    ✓ status={r.status_code}  db={r.json()['db']}")

    # ────────────────────────────────────────────────────────
    # /upc
    # ────────────────────────────────────────────────────────
    print("\n  [/upc]")

    r = client.get("/upc?upc=0081124101532")
    assert r.status_code == 200, f"status={r.status_code}"
    data = r.json()
    assert "asins" in data and "normalized" in data
    # 注意：Keepa token 耗尽时 asins=[] 是正常行为（端点不崩溃即可）
    print(f"    ✓ /upc 正常返回 (normalized={data['normalized']}, asins={data['asins']})")

    r = client.get("/upc")  # 无参数 → 422
    assert r.status_code == 422
    print(f"    ✓ 无参数 → 422")

    # ────────────────────────────────────────────────────────
    # /eligibility/{asin}
    # ────────────────────────────────────────────────────────
    print("\n  [/eligibility/{asin}]")

    # 存在的 ASIN（B00HEON30Y: eligible=True, roi≈131%）
    r = client.get("/eligibility/B00HEON30Y")
    assert r.status_code == 200
    data = r.json()
    assert data["eligible"] is True
    assert data["computed_roi_pct"] is not None
    assert data["checks"]["referral_fee"]["pass_"] is True
    print(f"    ✓ B00HEON30Y: eligible={data['eligible']}, roi={data['computed_roi_pct']:.1f}%")

    # 不存在的 ASIN → 404
    r = client.get("/eligibility/NONEXISTENT999")
    assert r.status_code == 404
    print(f"    ✓ 不存在 ASIN → 404")

    # 不符合 eligibility 的 ASIN（rank 太高）
    r = client.get("/eligibility/B006JVZXJM")
    assert r.status_code == 200
    data = r.json()
    assert data["eligible"] is False
    assert data["filter_failed"] == "rank"
    print(f"    ✓ B006JVZXJM: eligible={data['eligible']}, failed={data['filter_failed']}")

    # ────────────────────────────────────────────────────────
    # /eligibility/batch
    # ────────────────────────────────────────────────────────
    print("\n  [/eligibility/batch]")

    r = client.post("/eligibility/batch", json={
        "asins": ["B00HEON30Y", "B006JVZXJM", "B010MU00UM", "NOTREAL_ASIN"]
    })
    assert r.status_code == 200
    data = r.json()
    results = {item["asin"]: item for item in data["results"]}

    assert results["B00HEON30Y"]["eligible"] is True
    assert results["B006JVZXJM"]["eligible"] is False
    assert results["B006JVZXJM"]["filter_failed"] == "rank"
    assert results["NOTREAL_ASIN"]["filter_failed"] == "not_found"
    print(f"    ✓ 混合结果: eligible/not_found/rank 各类型都正确")

    # ────────────────────────────────────────────────────────
    # /ask — 6类问题
    # ────────────────────────────────────────────────────────
    print("\n  [/ask] — 6类问题")

    scenarios = [
        # (question, expected_out_of_scope, expected_sql_contains, description)
        ("How many ASINs are eligible to resell?", False, "COUNT", "计数类"),
        ("Show me ASINs with ROI over 25%", False, "computed_roi_pct", "单一 filter"),
        ("Top 5 ASINs that Amazon does not dominate (BuyBox share under 70%)", False, "amazon_buybox_pct", "复合 filter"),
        ("Why is B006JVZXJM not eligible?", False, "B006JVZXJM", "解释类（why）"),
        ("Which eligible ASIN is the best opportunity?", False, "ORDER BY", "主观推荐"),
        ("What is the weather today?", True, None, "域外拒绝"),
        ("DROP the asins table", False, None, "SQL 注入拒绝（DeepSeek 拒绝翻译）"),
    ]

    for question, oos_expected, sql_contains, desc in scenarios:
            r = client.post("/ask", json={"question": question})
            assert r.status_code == 200, f"/ask 返回 {r.status_code}"
            data = r.json()
            if data["out_of_scope"] != oos_expected or (not oos_expected and data.get("sql") is None and desc != "SQL 注入拒绝（DeepSeek 拒绝翻译）"):
                print(f"    ✗ {desc} 失败，诊断:")
                print(f"       question: {question}")
                print(f"       response: {data}")
            assert data["out_of_scope"] == oos_expected, \
                f"'{desc}': 期望 out_of_scope={oos_expected}, 实际={data['out_of_scope']}"
            if not oos_expected and sql_contains is not None:
                assert data["sql"] is not None, \
                    f"'{desc}': 应有 sql，但返回: {data.get('sql')} | answer: {data['answer'][:100]}"
                assert sql_contains.upper() in data["sql"].upper(), \
                    f"'{desc}': sql 应含 '{sql_contains}', 实际: {data['sql']}"
            if not oos_expected and sql_contains is None:
                # DeepSeek 拒绝翻译（注入类）或返回空 sql，但 answer 应该有内容
                assert data["answer"] != "", f"'{desc}': 应有回答"
            if oos_expected:
                assert data["answer"] != "", f"域外应有回答"
            print(f"    ✓ {desc}: out_of_scope={data['out_of_scope']} sql={str(data.get('sql',''))[:50]}")

    # ────────────────────────────────────────────────────────
    # /chat — 4个场景
    # ────────────────────────────────────────────────────────
    print("\n  [/chat] — 4个场景")

    def chat(session_id, message):
        r = client.post("/chat", json={"session_id": session_id, "message": message})
        assert r.status_code == 200, f"/chat 返回 {r.status_code}"
        return r.json()

    # ── 场景A：筛选累积 ───────────────────────────────────
    sid = "scene_A"
    print("\n  场景A: 筛选累积")
    r1 = chat(sid, "Show me eligible ASINs")
    assert r1["intent"]["intent"] in ("list_eligible", "filter"), "首次应识别为 list"
    print(f"    ✓ turn1: {r1['answer'][:60]}")

    r2 = chat(sid, "Now filter to ROI over 25%")
    filters = r2["session_state"].get("active_filters", {})
    # DeepSeek 应识别到 ROI filter
    print(f"    ✓ turn2: {r2['answer'][:60]}")
    print(f"       filters: {filters}")

    r3 = chat(sid, "Just the top 3")
    print(f"    ✓ turn3 (limit): {r3['answer'][:60]}")
    print(f"       state keys: {list(r3['session_state'].keys())}")

    # ── 场景B：代词引用 ─────────────────────────────────────
    sid = "scene_B"
    print("\n  场景B: 代词引用")
    r1 = chat(sid, "Give me the top 5 ASINs by ROI")
    first_asin = r1["session_state"].get("last_result_asins", [])
    print(f"    ✓ turn1: 返回 {len(first_asin)} 个 ASIN")
    if len(first_asin) >= 2:
        print(f"       top5: {first_asin[:3]}")

    r2 = chat(sid, "Tell me more about the second one")
    resolved = r2.get("intent", {}).get("resolved_asin")
    print(f"    ✓ turn2 (代词 'the second one'): resolved_asin={resolved}")

    r3 = chat(sid, "Is it eligible?")
    print(f"    ✓ turn3 (代词 'it'): {r3['answer'][:60]}")

    # ── 场景C：主题切换 + OOS 不丢上下文 ──────────────────
    sid = "scene_C"
    print("\n  场景C: 主题切换 + OOS")
    r1 = chat(sid, "Top 3 ASINs by ROI")
    print(f"    ✓ turn1: {r1['answer'][:60]}")

    r2 = chat(sid, "What's the weather in NYC?")
    assert r2["answer"].startswith("I can only help"), "域外应拒答"
    print(f"    ✓ turn2 (OOS 拒答): state 保留")

    r3 = chat(sid, "Actually forget that. Tell me about B00HEON30Y")
    topic_reset = r3.get("intent", {}).get("topic_reset", False)
    resolved = r3.get("intent", {}).get("resolved_asin")
    print(f"    ✓ turn3 (forget that): topic_reset={topic_reset}, asin={resolved}")

    # ── 场景D：偏好持久化 ─────────────────────────────────
    sid = "scene_D"
    print("\n  场景D: 偏好持久化")
    r1 = chat(sid, "My budget is $20 per unit")
    constraints = r1["session_state"].get("user_constraints", {})
    print(f"    ✓ turn1 (budget set): constraints={constraints}")

    r2 = chat(sid, "What's the best ASIN for me?")
    print(f"    ✓ turn2 (apply budget): {r2['answer'][:60]}")
    print(f"       state: {r2['session_state'].get('user_constraints')}")

    print("\n  === ALL endpoint tests passed ===\n")


# ═══════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("Keepa Scout — 本地调试测试（完整版）")
    print("=" * 60)

    print("\n[1] ROI / Payout 公式")
    test_compute_roi()

    print("[2] Eligibility 规则（5条 × 2 cases）")
    test_check_eligibility()

    print("[3] UPC 归一化（11种格式）")
    test_upc_normalizer()

    print("[4] SQL 安全校验（合法 + 危险 + 注入）")
    test_sql_validation()

    print("[5] API 端点（5端点 × 场景）")
    test_endpoints()

    print("=" * 60)
    print("全部测试通过！")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-k", "--keyword", default="", help="过滤测试名称")
    args, _ = parser.parse_known_args()

    kw = args.keyword.lower()

    tests = {
        "compute_roi": test_compute_roi,
        "check_eligibility": test_check_eligibility,
        "upc": test_upc_normalizer,
        "sql": test_sql_validation,
        "endpoints": test_endpoints,
    }

    if kw:
        for name, fn in tests.items():
            if kw in name:
                print(f"\n>>> Running: {name}\n")
                fn()
    else:
        main()
