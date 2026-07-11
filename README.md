# 💰 DCF Valuation Engine

Streamlit app that builds a full discounted-cash-flow valuation from yfinance
financial statements.

## Pipeline
1. 4 years of historical **free cash flow** (OCF + capex fallback if Yahoo's FCF row is missing)
2. 5-year projection with sliders for growth (default = historical CAGR)
3. Gordon-growth terminal value
4. Discounted at **WACC** — CAPM cost of equity (rf + β·ERP) blended with cost
   of debt derived from interest expense / total debt, tax-shielded

## Features
- Intrinsic value vs market price with upside %
- FCF history + projection chart, terminal-value share breakdown
- **Sensitivity heatmap** (growth × WACC) centered on the current price
- **Peer comps** tab: P/E, forward P/E, EV/EBITDA, P/S, margins

## Run it
```bash
pip install -r requirements.txt
streamlit run app.py
```
