"""
UPC / EAN / ISBN 归一化模块。

背景：
  Keepa /product?code= 接口接受特定格式的条码：
    - 12 位 UPC-A（最常见）
    - 13 位 EAN-13
    - 14 位 ITF-14（箱级）

痛点：
  - 用户输入可能有 11 位（UPC-E 需展开）
  - 可能含连字符/空格（需去除）
  - 13 位 ISBN-13 可能需要加前缀 '0' 变成 14 位
  - 不同格式的接受度不同，需要尝试多种变体

策略：
  1. 去掉所有非数字字符
  2. 按位数分类，生成所有可能的变体
  3. 逐一查询 Keepa，直到有结果返回
  4. 对所有成功变体去重合并 ASIN
"""

from typing import Optional


def normalize_upc(raw: str) -> list[str]:
    """
    将原始输入字符串归一化为 Keepa 可接受的条码变体列表。

    处理逻辑：
      - 11 位：UPC-E 模式 → 尝试补前导 0 + UPC-E 展开
      - 12 位：UPC-A → 原样 + 尝试去前缀 0（EAN-13）
      - 13 位：EAN-13 → 原样 + ISBN-10 转换 + 去前缀 0
      - 14 位：ITF-14 → 原样 + 去前导零
      - 其他：直接返回纯数字版本

    返回：归一化后的条码列表（第一个最可能成功）
    """
    # 去除所有非数字字符
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        return []

    variants: list[str] = []

    # ── 11 位 → 两种尝试 ──────────────────────────────────
    # 情况 A：UPC-E（压缩格式），需展开为 12 位 UPC-A
    # 情况 B：普通 11 位数字直接补前导 0
    if len(digits) == 11:
        variants.append("0" + digits)  # 补前导 0 → 12 位
        expanded = upce_to_upca(digits)
        if expanded:
            variants.append(expanded)
        return _dedupe(variants)

    # ── 12 位 → UPC-A ────────────────────────────────────
    if len(digits) == 12:
        variants.append(digits)
        # 13 位 ISBN-13 无校验位时，加前缀 0 变成 ITF-14
        isbn13_no_check = "0" + digits
        if isbn13_no_check != digits:
            variants.append(isbn13_no_check)
        return _dedupe(variants)

    # ── 13 位 → EAN-13 或 ISBN-13 ──────────────────────
    if len(digits) == 13:
        variants.append(digits)
        # ISBN-13 "978" 前缀 → 去掉 "978" 前缀 + 加 "0" 前缀 = UPC-A
        if digits.startswith("978"):
            isbn10 = digits[3:12]  # 去掉 "978" + 去掉校验位
            variants.append("0" + isbn10)
        # 去掉前导 0 → 尝试 12 位 UPC-A 格式
        if digits.startswith("0"):
            variants.append(digits[1:])
        return _dedupe(variants)

    # ── 14 位 → ITF-14 ──────────────────────────────────
    if len(digits) == 14:
        variants.append(digits)
        stripped = digits.lstrip("0")
        if stripped and stripped != digits:
            variants.append(stripped)
        return _dedupe(variants)

    # ── 其他长度 → 直接返回纯数字 ────────────────────────
    variants.append(digits)
    return variants


def upce_to_upca(upce: str) -> Optional[str]:
    """
    将 11 位 UPC-E（含校验位）展开为 12 位 UPC-A。

    UPC-E 是压缩格式，用最后一位（校验位）决定中间 6 位数字的解读方式。
    规则来自 GS1 标准：
      - 数字系统位（第 0 位）决定展开方式
      - 最后一位为校验位

    参数：11 位字符串，格式为 [数字系统][6位数据][校验位]
    返回：12 位 UPC-A 字符串，或 None（格式不正确）
    """
    if len(upce) != 11:
        return None

    ns = upce[0]           # 数字系统位（0 或 1）
    d1, d2, d3, d4, d5, d6 = upce[1:7]  # 6 位编码数据
    check = upce[-1]        # 校验位

    # 展开规则：校验位决定最后一位数字的放置位置（GS1 标准简化版本）
    expansions = {
        "0": f"{ns}{d1}{d2}{d3}{d4}{d5}{d6}0000{check}",
        "1": f"{ns}{d1}{d2}{d3}{d4}{d5}{d6}0000{check}",
        "2": f"{ns}{d1}{d2}{d3}{d4}{d5}{d6}0000{check}",
        "3": f"{ns}{d1}{d2}{d3}{d4}{d5}0000{check}",
        "4": f"{ns}{d1}{d2}{d3}{d4}0000{check}",
        "5": f"{ns}{d1}{d2}{d3}{d4}{d5}0000{check}",
        "6": f"{ns}{d1}{d2}{d3}{d4}{d5}{d6}0000{check}",
        "7": f"{ns}{d1}{d2}{d3}{d4}{d5}{d6}0000{check}",
        "8": f"{ns}{d1}{d2}{d3}{d4}{d5}{d6}0000{check}",
        "9": f"{ns}{d1}{d2}{d3}{d4}{d5}{d6}0000{check}",
    }
    return expansions.get(ns)


def _dedupe(lst: list[str]) -> list[str]:
    """去重并保持顺序"""
    seen = set()
    result = []
    for x in lst:
        if x not in seen:
            seen.add(x)
            result.append(x)
    return result
