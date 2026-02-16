# Monte Carlo Stock Screener

Bulk screening tool that runs Monte Carlo simulations across an entire ticker universe to find statistically dislocated equities. Uses the same simulation engine as the standalone Monte Carlo Risk Engine (Student-t shocks, EWMA vol clustering, distributed jumps) but applies it at scale across thousands of tickers.

The screener does not generate trade signals. It narrows a universe of 12,000+ tickers down to a shortlist of names where price has moved to a statistical extreme relative to recent volatility, and where basic valuation metrics don't suggest the move is justified by deteriorating fundamentals.

---

## How It Works

Three stage pipeline:

**Stage 1 — Prescreener** (`prescreener.py`)
Reads a full ticker universe from JSON. Filters on minimum price and average volume using bulk yfinance downloads. Cuts 12,000+ tickers down to 2,000-4,000 liquid names. Output is a filtered text file.

**Stage 2 — Monte Carlo Screener** (`main_enhanced.py`)
Runs Monte Carlo simulation on every ticker that passed the prescreener. For each stock it computes forward return percentiles (p5, p10, p50), annualized volatility, VaR, and CVaR. On top of that it pulls P/E ratio, forward P/E, sector, earnings date, and calculates a 60-day Z-score for mean reversion context. Results save to Excel with auto-save every 100 tickers so you don't lose progress if you interrupt.

**Stage 3 — Opportunity Analyzer** (`analyze_opportunities.py`)
Reads the Excel output from stage 2 and scores each stock on a composite of Z-score, P/E, drop from high, forward p10, and volatility. Ranks opportunities into tiers (Strong / Review / Pass) and flags sector concentration risk and earnings proximity. Outputs a ranked Excel workbook.

---

## Project Structure

```
/Screener/
├── prescreener.py              (stage 1: bulk filter from JSON)
├── main_enhanced.py            (stage 2: MC screener runner)
├── analyze_opportunities.py    (stage 3: scoring and ranking)
└── /engine/
    ├── screener_engine_simple.py   (per-stock analysis wrapper)
    ├── excel_writer_simple.py      (Excel output formatting)
    └── ticker_loader.py            (reads filtered ticker list)
```

The screener engine imports the Monte Carlo Risk Engine from the Tail End Risk project. It uses the same simulation model: Student-t distributed shocks, EWMA conditional volatility, distributed jump process, risk-free drift proxy, and volatility stress ladder.

**Total:** ~920 lines (excluding the shared MC engine)

---

## Usage

### Stage 1: Prescreener

Configure paths and thresholds at the top of `prescreener.py`:

```python
INPUT_JSON = "path/to/ticker.json"
OUTPUT_TICKERS = "path/to/ticker_filtered.txt"
MIN_PRICE = 5
MIN_AVG_VOL = 800_000
```

```bash
python prescreener.py
```

### Stage 2: Monte Carlo Screener

Configure in `main_enhanced.py`:

```python
TICKER_FILE = "path/to/ticker_filtered.txt"
OUTPUT_FILE = "path/to/screening_results_enhanced.xlsx"
DAYS_TO_SIMULATE = 90
NUM_SIMULATIONS = 10000
HISTORICAL_WINDOW = 252 * 6
```

```bash
python main_enhanced.py
```

Press Ctrl+C at any time to save partial results and exit. Auto-saves every 100 stocks.

### Stage 3: Opportunity Analyzer

```bash
python analyze_opportunities.py
```

Reads the Excel from stage 2 and outputs a ranked workbook.

---

## Output

### Screener Excel (Stage 2)

Three sheets:

| Sheet | Contents |
|-------|----------|
| All Results | Every stock sorted by Z-score |
| Oversold | Z-score below -2 only |
| Overbought | Z-score above 2 only |

Columns include ticker, signal, Z-score, distance from mean, P/E, forward P/E, sector, earnings date, days to earnings, current price, 52-week high, drop from high, forward p5/p10/p50, volatility, and average volume.

### Ranked Opportunities Excel (Stage 3)

Three sheets:

| Sheet | Contents |
|-------|----------|
| Ranked Opportunities | All filtered stocks scored and sorted |
| Strong Setups | Score above 70 only |
| Sector Summary | Count and average score by sector |

Each stock gets a composite opportunity score (0-100) based on weighted criteria:

| Metric | Weight | Optimal Range |
|--------|--------|--------------|
| Z-score | 25% | -3.0 to -2.0 |
| P/E ratio | 20% | 5 to 25 |
| Drop from high | 15% | -40% to -20% |
| Forward p10 | 20% | -40% to -15% |
| Volatility | 20% | 30% to 60% |

---

## What Each Metric Means

**Z-score:** How far current price has deviated from its 60-day rolling mean in standard deviation terms. Below -2 is statistically oversold. Above 2 is overbought. This is a measure of statistical dislocation, not a trade signal.

**Forward percentiles (p5, p10, p50):** From the Monte Carlo simulation. p10 of -8% means 90% of simulated paths stayed above an 8% loss over the simulation horizon. Used to gauge how much further downside the model expects under current vol conditions.

**Drop from 52-week high:** How far the stock has already fallen from its peak. Context for whether the Z-score dislocation happened from a reasonable level or from an already extended price.

**P/E ratio:** Basic survivability check. A stock at Z-score -2.5 with a P/E of 12 is a different situation than one with a P/E of 200 or negative earnings.

**Volatility:** Annualized realized vol from the Monte Carlo engine. Needs to be high enough that options premium is worth selling but not so high that the name is untradeable.



---

## Limitations

* Runs 10,000 simulations per stock instead of 25,000 to keep runtime manageable across thousands of tickers. Tail estimates are noisier than the standalone engine.
* Z-score uses a simple 60-day rolling window. Not regime-aware.
* Opportunity scoring weights and ranges are hardcoded assumptions, not calibrated.
* No implied volatility data. The screener identifies statistical dislocation but cannot tell you whether options premium is favorable.
* Single asset simulations with no correlation or portfolio context.
* Earnings dates from yfinance are sometimes missing or stale.
* The 6-year historical window for volatility calculation is long. Shorter windows would be more responsive to current conditions.

---

## Intended Use

Narrowing a large equity universe down to a manageable watchlist of statistically dislocated names that warrant deeper fundamental and options analysis. The screener finds candidates. You still need to verify the thesis, check IV conditions, and structure the trade independently.