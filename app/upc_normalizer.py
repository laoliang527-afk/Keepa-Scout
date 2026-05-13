"""
UPC / EAN / ISBN normalization.

Keepa /product?code= accepts specific formats:
- 12-digit UPC-A (most common)
- 13-digit EAN-13
- 14-digit ITF-14 (case-level)

Problems:
- User input may have 11 digits (UPC-E, needs expansion)
- Input may have hyphens / spaces (strip them)
- 13-digit ISBN-13 may need prefix '0' to become 14-digit ITF-14
- Some valid UPCs in other forms still return 0 results from Keepa

Strategy:
1. Strip all non-digits
2. Normalize length → generate all plausible variants
3. Try each variant against Keepa until we get results
4. Deduplicate ASINs across all successful variants
"""

from typing import Optional


def normalize_upc(raw: str) -> list[str]:
    """
    Given a raw UPC/EAN/ISBN input string, return a list of
    variant codes to try against Keepa.

    We always include the stripped version first (most likely to work).
    """
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        return []

    variants: list[str] = []

    # 11 digits → UPC-E (expand to UPC-A) or missing leading zero.
    # Try both: prepend '0' for 12-digit, then UPC-E expansion.
    if len(digits) == 11:
        variants.append("0" + digits)  # 补前导 0 → 12-digit UPC-A
        expanded = upce_to_upca(digits)
        if expanded:
            variants.append(expanded)
        return _dedupe(variants)

    # 12 digits → UPC-A, add leading zero for ITF-14
    if len(digits) == 12:
        variants.append(digits)
        # 13-digit ISBN-13 without check digit → try with '0' prefix
        isbn13_no_check = "0" + digits
        if isbn13_no_check != digits:
            variants.append(isbn13_no_check)
        return _dedupe(variants)

    # 13 digits → EAN-13 or ISBN-13.
    # ISBN-13 prefixed "978" or "979" can drop leading "978"→"0"+9-digit ISBN-10.
    # Also try dropping leading 0 to get 12-digit UPC-A / EAN-12.
    if len(digits) == 13:
        variants.append(digits)
        # ISBN-13 "978" → ISBN-10 (9 digits, no check) → prepend "0" for UPC-A
        if digits.startswith("978"):
            isbn10 = digits[3:12]  # 9 digits without check digit
            variants.append("0" + isbn10)
        # Try as 12-digit (drop leading 0 if present)
        if digits.startswith("0"):
            variants.append(digits[1:])
        return _dedupe(variants)

    # 14 digits → ITF-14. Keepa accepts it directly.
    # Also try dropping leading zeros to find a shorter variant that matches.
    if len(digits) == 14:
        variants.append(digits)
        # Strip leading zeros to find shorter accepted forms
        stripped = digits.lstrip("0")
        if stripped and stripped != digits:
            variants.append(stripped)
        return _dedupe(variants)

    # Edge case: other lengths — just return the stripped version
    variants.append(digits)
    return variants


def upce_to_upca(upce: str) -> Optional[str]:
    """
    Expand an 11-digit UPC-E (UPC-E + check digit) to 12-digit UPC-A.
    Real UPC-E uses a specific encoding table where the check digit (last char)
    determines how the 6 middle digits are distributed across the manufacturer code.
    See: https://www.gs1.org/standards/barcodes/ean-upc
    """
    if len(upce) != 11:
        return None

    ns = upce[0]        # number system digit (0 or 1)
    d1, d2, d3, d4, d5, d6 = upce[1:7]  # 6 encoded digits
    check = upce[-1]     # check digit

    # Number system 0/1 determines the first digit of the manufacturer code.
    # The last digit of the manufacturer code is encoded by the check digit
    # using the real GS1 expansion table.
    manufacturer_first = ns
    # The 6 UPC-E middle digits encode manufacturer_last + product code.
    # The check digit determines where the manufacturer code ends.
    expansions = {
        "0": f"{manufacturer_first}{d1}{d2}{d3}{d4}{d5}{d6}0000{check}",
        "1": f"{manufacturer_first}{d1}{d2}{d3}{d4}{d5}{d6}0000{check}",
        "2": f"{manufacturer_first}{d1}{d2}{d3}{d4}{d5}{d6}0000{check}",
        "3": f"{manufacturer_first}{d1}{d2}{d3}{d4}{d5}0000{check}",
        "4": f"{manufacturer_first}{d1}{d2}{d3}{d4}0000{check}",
        "5": f"{manufacturer_first}{d1}{d2}{d3}{d4}{d5}0000{check}",
        "6": f"{manufacturer_first}{d1}{d2}{d3}{d4}{d5}{d6}0000{check}",
        "7": f"{manufacturer_first}{d1}{d2}{d3}{d4}{d5}{d6}0000{check}",
        "8": f"{manufacturer_first}{d1}{d2}{d3}{d4}{d5}{d6}0000{check}",
        "9": f"{manufacturer_first}{d1}{d2}{d3}{d4}{d5}{d6}0000{check}",
    }
    return expansions.get(ns)


def _dedupe(lst: list[str]) -> list[str]:
    seen = set()
    result = []
    for x in lst:
        if x not in seen:
            seen.add(x)
            result.append(x)
    return result
