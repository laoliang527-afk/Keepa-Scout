# Keepa API Integration Notes

> Empirical findings and official docs summary for `keepa_scout_challenge`.
> These notes are the **source of truth** for the codebase — update here first, then update code if needed.

---

## 1. Max ASINs per `/product` Call

**Keepa accepts up to ~100 ASINs per request** (confirmed by Keepa API docs and official library).
Passing more returns an error or partial results. We use a safe batch size of **20** to stay well under the limit and leave headroom for retries.

**Current code:** `BATCH_SIZE = 20` in `app/etl.py`.

**If you want to test empirically**, run:

```bash
python -m app.tests.keepa_integration max_asins
```

---

## 2. Token Cost Formula

### How tokens work

- Keepa uses a **token bucket** model: your plan generates N tokens/minute, unused tokens expire after **1 hour**.
- Every `/product` response includes `tokensConsumed` and `tokensLeft`.
- **1 token = 1 product** (with no optional params).
- Optional params **add token cost** on top of the base:

| Parameter | Extra token cost |
|---|---|
| `stats=N` (N > 0) | +1 per ASIN |
| `buybox=1` | +1 per ASIN |
| `fbafees=1` | +1 per ASIN |
| `offers=20`..`100` | significant extra (up to ~10x base) |
| `update=live` | +1 per ASIN |
| `history=True` (default) | included in base |

### Formula (approximate)

```
tokens_consumed ≈ base_asins
                + (stats > 0 ? asins * 1 : 0)
                + (buybox == 1  ? asins * 1 : 0)
                + (fbafees == 1 ? asins * 1 : 0)
```

**Example:** 20 ASINs with stats + buybox + fbafees = 20 + 20 + 20 + 20 = **~80 tokens**.

**Current code:** `client.tokens_used` accumulates from `tokensConsumed` in every response (actual server-reported value).

**To observe actual costs**, run:

```bash
python -m app.tests.keepa_integration tokens
```

---

## 3. `stats.current[]` Index Mapping (domain=1 / US)

Source: [Keepa product object docs](https://keepa.com/#!discuss/t/product-object/116) and empirical observation.

```python
STAT_BUYBOX_PRICE    = 0   # current BuyBox price (cents, -1 = none)
STAT_NEW_PRICE       = 1   # current New price (cents)
STAT_SALES_RANK      = 2   # current Sales Rank (integer, -1 = none)
STAT_BUYBOX_SHIPPING = 3   # current BuyBox shipping (cents)
STAT_NEW_SHIPPING    = 4   # current New shipping (cents)
```

Values of **-1** or missing mean the data is unavailable — treat as `None` in Python.

**Current code:** defined in `app/keepa_client.py`.

**To inspect empirically**, run:

```bash
python -m app.tests.keepa_integration stats
```

---

## 4. `buyBoxSellerIdHistory` — Decoding Amazon BuyBox %

### Data structure

`buyBoxSellerIdHistory` is a flat array of **alternating `[timestamp, sellerId, timestamp, sellerId, ...]`**.

```
history = [ts0, "ATVPDKIKX0DER", ts1, "A2XYZ...", ts2, "ATVPDKIKX0DER", ...]
seller_ids = history[1::2]   # every other item, starting at index 1
```

Amazon's seller ID is **ATVPDKIKX0DER**.

### Decoding formula

```python
AMAZON_SELLER_ID = "ATVPDKIKX0DER"
seller_ids = history[1::2]
amazon_count = sum(1 for sid in seller_ids if sid == AMAZON_SELLER_ID)
total = len(seller_ids)
amazon_buybox_pct = round(100 * amazon_count / total, 2)  # returns None if empty
```

**Current code:** `KeepaClient._calc_amazon_pct()` in `app/keepa_client.py`.

**To inspect empirically**, run:

```bash
python -m app.tests.keepa_integration history
```

---

## 5. UPC / EAN / ISBN Format Acceptance

### What Keepa accepts

Keepa's `/product?code=` endpoint accepts these barcode formats:

| Digits | Format | Accepted? | Notes |
|---|---|---|---|
| 12 | UPC-A | ✅ | Standard retail barcode |
| 13 | EAN-13 | ✅ | International equivalent of UPC |
| 14 | ITF-14 | ✅ | Case-level shipping carton barcode |
| 10 | ISBN-10 | ✅ (via ASIN or ISBN-13) | Legacy book ISBN |
| 13 | ISBN-13 | ✅ | Modern book ISBN |

### What needs client-side preprocessing

| Digits | Format | Accepted? | Preprocessing needed |
|---|---|---|---|
| 11 | UPC-E | ❌ **rejected / 0 results** | Expand to 12-digit UPC-A first |
| 10 | UPC-A without leading zero | ❌ | Left-pad to 12 digits |

### UPC-E → UPC-A expansion

UPC-E (11 digits, compact) must be **expanded to 12-digit UPC-A** before querying Keepa.

```python
# 11-digit UPC-E: "01234567895"
# Expanded to 12-digit UPC-A based on check digit (last char):
expansions = {
    "0": f"00000{middle[:2]}000{check}",
    "1": f"10000{middle[:2]}000{check}",
    ...
    "4": f"40000{middle[:3]}00{check}",
    "5": f"50000{middle[:4]}0{check}",
    "6": f"60000{middle[:4]}0{check}",
    "7": f"70000{middle[:4]}0{check}",
    "8": f"80000{middle[:4]}0{check}",
    "9": f"90000{middle[:4]}0{check}",
}
```

**Current code:** `upc_normalizer.py` handles all of the above.

### UPC normalization strategy

```python
def normalize_upc(raw: str) -> list[str]:
    digits = "".join(ch for ch in raw if ch.isdigit())

    if len(digits) == 11:           # UPC-E → expand to UPC-A
        return [upce_to_upca(digits), digits]  # try both

    if len(digits) == 12:           # UPC-A → try as-is + 0-prefix for ISBN
        return [digits, "0" + digits]

    if len(digits) == 13:           # EAN-13 → try as-is + drop leading 0
        return [digits, digits[1:]] if digits.startswith("0") else [digits]

    if len(digits) == 14:           # ITF-14 → try as-is
        return [digits]

    return [digits]                  # fallback: try whatever we have
```

**To test empirically**, run:

```bash
python -m app.tests.keepa_integration upc
```

---

## 6. Running the Tests

All integration tests are in `app/tests/keepa_integration.py`.

```bash
# Run all tests (requires valid Keepa keys with tokens remaining)
python -m app.tests.keepa_integration

# Run individual tests
python -m app.tests.keepa_integration max_asins   # max ASINs per call
python -m app.tests.keepa_integration tokens      # token cost observation
python -m app.tests.keepa_integration stats       # stats.current[] indices
python -m app.tests.keepa_integration history      # buyBoxSellerIdHistory
python -m app.tests.keepa_integration upc         # UPC format acceptance
```

> **Note:** Tests consume real Keepa tokens. If your keys are rate-limited (429), tests will hang. Run them individually and skip when keys are exhausted.
