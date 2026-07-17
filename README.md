# Deep Value Screener

A fundamentals-based stock screener that reduces a large ticker universe down to a
ranked shortlist of statistically cheap, financially healthy names.

The pipeline is a two-stage funnel:

```
ticker.json  ──(prescreener)──▶  ticker_filtered.txt  ──(main_enhanced)──▶  screener_results.xlsx
   ~10k+                            liquid / profitable                        scored & ranked
   symbols                          survivors                                  candidates
```

All work lives in `Value_dislocation/`.

---

## Stage 1 — Prescreener

`Value_dislocation/prescreener/` — a fast structural filter that trims the full SEC
ticker universe (`ticker.json`) down to a manageable list.

Gates applied:

* **Price** ≥ $5
* **Liquidity** — average volume ≥ 4M shares/day
* **Drawdown** — meaningful pullback from the 1-year high
* **Profitability** — trailing P/E must be positive
* **Revenue** — reject severe revenue collapse (worse than −25% YoY)
* **Balance sheet** — current ratio ≥ 0.8

Output: **`ticker_filtered.txt`** (tab-separated `ticker<TAB>volume`), the input to
Stage 2.

---

## Stage 2 — `main_enhanced.py`

`Value_dislocation/main_enhanced.py` is the main controller. It loads the filtered
tickers and runs the deep-value engine over each one, pulling fundamentals live from
Yahoo Finance (`yfinance`).

### What it computes per stock

For every ticker, `engine/screener_engine_simple.py`:

1. Pulls fundamentals (price, market cap, sector, P/E, forward P/E, EV, EBITDA, debt,
   cash, shares, average volume).
2. Looks up the **next earnings date** (3 fallback methods) and the **ex-dividend date**.
3. Derives five core value metrics:

   | Metric | Meaning | Cheaper when |
   |---|---|---|
   | **FCF Yield %** | Free cash flow ÷ market cap | Higher |
   | **EV / EBITDA** | Enterprise value ÷ operating earnings | Lower |
   | **Earnings Yield %** | Inverse of P/E | Higher |
   | **Net Debt / EBITDA** | Leverage vs. earnings | Lower |
   | **FCF-to-Debt** | Ability to pay down debt from cash flow | Higher |

   > Financials (`Financial Services`) are excluded from FCF math — bank cash flow
   > isn't comparable to operating businesses.

### Scoring & signals

Each metric scores 0, 1, or 2 against fixed thresholds → a **0–10 deep-value score**.

| Signal | Rule |
|---|---|
| `DEEP_VALUE` | score ≥ 8 — cheap on nearly every metric |
| `VALUE` | score ≥ 5 — cheap on several metrics |
| `NEUTRAL` | score < 5 — not obviously cheap |

**High conviction** flag = `DEEP_VALUE` **and** no earnings report within the next
14 days — i.e. names you could actually deploy into today without walking into a
binary earnings event.

### Output

`engine/excel_writer_simple.py` writes **`screener_results.xlsx`**, sorted best-first,
with three tabs:

* **All Results** — every successfully screened stock with full metrics
* **High Conviction** — the high-conviction subset
* **Deep Value** — all `DEEP_VALUE` names

### Reliability

* **Autosave** every 25 tickers, so a crash or rate-limit never loses progress.
* **Ctrl+C** finishes the current ticker, saves, then exits cleanly.
* A throttle delay between calls avoids Yahoo rate limits.

---

## How to run

```bash
# 1. (optional) rebuild the filtered universe
python Value_dislocation/prescreener/prescreener3.py

# 2. run the screener
python Value_dislocation/main_enhanced.py
#    → writes Value_dislocation/screener_results.xlsx
#    → Ctrl+C any time; progress is autosaved
```

Paths are resolved relative to the repo root, so `ticker_filtered.txt` (input) and
`screener_results.xlsx` (output) are picked up automatically.

Dependencies: see `requirements.txt` (`yfinance`, `pandas`, `numpy`, `openpyxl`).

---

## What this is — and isn't

This is a **screening tool**. It flags statistically cheap, liquid, financially sound
candidates for deeper human research. It does **not** compute intrinsic value — that
requires a per-company DCF with company-specific assumptions. The score is for
**ranking**, not for making buy decisions.

For research and educational purposes only. Not financial advice.
