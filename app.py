"""Company Valuation Engine (DCF) — Streamlit app.

Pulls 4 years of financial statements from yfinance, computes historical free
cash flow, projects 5 years with growth/margin sliders (defaults from history),
discounts at WACC (CAPM cost of equity + debt cost from interest expense), and
shows intrinsic value vs price, a sensitivity heatmap, and peer comps.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="DCF Valuation Engine", layout="wide")

RISK_FREE = 0.045       # 10Y treasury proxy — adjustable in sidebar
EQUITY_PREMIUM = 0.05   # long-run US equity risk premium

# ----------------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------------
@st.cache_data(ttl=3600)
def load_company(ticker: str) -> dict:
    tk = yf.Ticker(ticker)
    info = tk.info
    cf = tk.cashflow          # annual cash flow statement (cols = years)
    fin = tk.financials       # income statement
    bs = tk.balance_sheet

    def row(df, *names):
        for n in names:
            if n in df.index:
                return df.loc[n].dropna()
        return pd.Series(dtype=float)

    fcf_hist = row(cf, "Free Cash Flow")
    if fcf_hist.empty:
        ocf = row(cf, "Operating Cash Flow", "Total Cash From Operating Activities")
        capex = row(cf, "Capital Expenditure", "Capital Expenditures")
        fcf_hist = (ocf + capex).dropna()  # capex is negative in yfinance
    revenue = row(fin, "Total Revenue")
    interest = row(fin, "Interest Expense", "Interest Expense Non Operating")
    total_debt = row(bs, "Total Debt")
    cash = row(bs, "Cash And Cash Equivalents",
               "Cash Cash Equivalents And Short Term Investments")
    return dict(
        info=info,
        fcf=fcf_hist.sort_index(),
        revenue=revenue.sort_index(),
        interest=float(abs(interest.iloc[0])) if len(interest) else 0.0,
        debt=float(total_debt.iloc[0]) if len(total_debt) else 0.0,
        cash=float(cash.iloc[0]) if len(cash) else 0.0,
    )


def dcf_value(fcf0, growth, terminal_growth, wacc, years=5):
    """Standard 2-stage DCF: project FCF, discount, add discounted terminal value.

    Returns (enterprise_value, list of projected FCFs, terminal value).
    """
    fcfs = [fcf0 * (1 + growth) ** t for t in range(1, years + 1)]
    pv_fcfs = sum(f / (1 + wacc) ** t for t, f in enumerate(fcfs, 1))
    if wacc <= terminal_growth + 0.001:
        return np.nan, fcfs, np.nan  # Gordon growth breaks down
    tv = fcfs[-1] * (1 + terminal_growth) / (wacc - terminal_growth)
    pv_tv = tv / (1 + wacc) ** years
    return pv_fcfs + pv_tv, fcfs, tv


# ----------------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------------
st.title("💰 DCF Valuation Engine")

with st.sidebar:
    st.header("Company")
    ticker = st.text_input("Ticker", "AAPL").strip().upper()
    rf = st.slider("Risk-free rate", 0.02, 0.07, RISK_FREE, 0.0025)
    erp = st.slider("Equity risk premium", 0.03, 0.08, EQUITY_PREMIUM, 0.0025)

try:
    data = load_company(ticker)
except Exception as e:
    st.error(f"Failed to load {ticker}: {e}")
    st.stop()
info = data["info"]
fcf_hist = data["fcf"]
if fcf_hist.empty or len(fcf_hist) < 2:
    st.error(f"Not enough cash-flow history for {ticker} (need 2+ years).")
    st.stop()

price = info.get("currentPrice") or info.get("regularMarketPrice")
shares = info.get("sharesOutstanding")
beta = info.get("beta") or 1.0
mkt_cap = info.get("marketCap", 0)
if not price or not shares:
    st.error("Missing price / share count from Yahoo.")
    st.stop()

# Historical FCF growth (CAGR over available years) as slider default
yrs = len(fcf_hist) - 1
first, last = float(fcf_hist.iloc[0]), float(fcf_hist.iloc[-1])
hist_growth = (abs(last / first)) ** (1 / yrs) - 1 if first != 0 and last > 0 and first > 0 else 0.08
hist_growth = float(np.clip(hist_growth, -0.10, 0.30))

# WACC components
cost_equity = rf + beta * erp                                       # CAPM
cost_debt = data["interest"] / data["debt"] if data["debt"] > 0 else rf + 0.01
cost_debt = float(np.clip(cost_debt, 0.01, 0.15))
tax_rate = 0.21
E, D = mkt_cap, data["debt"]
wacc_default = (E / (E + D)) * cost_equity + (D / (E + D)) * cost_debt * (1 - tax_rate) \
    if (E + D) > 0 else cost_equity

with st.sidebar:
    st.header("Projection (defaults from history)")
    growth = st.slider("FCF growth (yrs 1-5)", -0.10, 0.35, round(hist_growth, 3), 0.005)
    tgrowth = st.slider("Terminal growth", 0.00, 0.04, 0.025, 0.0025)
    wacc = st.slider("WACC", 0.05, 0.15, round(float(np.clip(wacc_default, 0.05, 0.15)), 3), 0.0025)

fcf0 = float(fcf_hist.iloc[-1])
ev, proj_fcfs, tv = dcf_value(fcf0, growth, tgrowth, wacc)
equity_value = ev - data["debt"] + data["cash"] if not np.isnan(ev) else np.nan
intrinsic = equity_value / shares if not np.isnan(equity_value) else np.nan
upside = intrinsic / price - 1.0 if not np.isnan(intrinsic) else np.nan

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Price", f"${price:,.2f}")
c2.metric("Intrinsic value", f"${intrinsic:,.2f}" if not np.isnan(intrinsic) else "n/a",
          f"{upside:+.1%} upside" if not np.isnan(upside) else None)
c3.metric("WACC", f"{wacc:.2%}", f"CAPM Ke {cost_equity:.1%} / Kd {cost_debt:.1%}")
c4.metric("Last FCF", f"${fcf0/1e9:,.1f}B")
c5.metric("Hist FCF CAGR", f"{hist_growth:+.1%}")

with st.expander("How this works"):
    st.markdown(f"""
**DCF** values a company as the present value of all its future free cash flow.

1. **Project FCF** 5 years at your growth rate (default = historical CAGR {hist_growth:+.1%}).
2. **Terminal value** — after year 5, assume FCF grows forever at a GDP-like rate
   (Gordon growth: TV = FCF₆ / (WACC − g)). This is usually 60-80% of the value —
   which is why DCFs are so sensitive to the two rates.
3. **Discount at WACC** — the blended cost of capital.
   Cost of equity from **CAPM**: rf + β·ERP = {rf:.1%} + {beta:.2f}·{erp:.1%} = {cost_equity:.1%}.
   Cost of debt = interest expense / total debt = {cost_debt:.1%}, tax-shielded at 21%.
4. **Equity value** = enterprise value − debt + cash; divide by shares.

**Sensitivity heatmap** — one point of WACC or growth swings the value massively.
Anyone who quotes a single DCF number without a sensitivity table is selling something.
""")

tab1, tab2, tab3 = st.tabs(["📊 Projection", "🌡️ Sensitivity", "🏢 Peer comps"])

with tab1:
    hist_years = [str(pd.to_datetime(i).year) for i in fcf_hist.index]
    proj_years = [f"{int(hist_years[-1]) + t}E" for t in range(1, 6)]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=hist_years, y=fcf_hist.values / 1e9, name="Historical FCF",
                         marker_color="#636efa"))
    fig.add_trace(go.Bar(x=proj_years, y=np.array(proj_fcfs) / 1e9, name="Projected FCF",
                         marker_color="#00cc96"))
    fig.update_layout(template="plotly_dark", height=440,
                      title="Free cash flow: history + 5-year projection ($B)")
    st.plotly_chart(fig, use_container_width=True)
    if not np.isnan(ev):
        pv_tv = tv / (1 + wacc) ** 5
        st.caption(f"Enterprise value ${ev/1e9:,.0f}B = PV of 5yr FCF "
                   f"${(ev - pv_tv)/1e9:,.0f}B + PV of terminal value ${pv_tv/1e9:,.0f}B "
                   f"({pv_tv/ev:.0%} of total — the terminal value dominates, as always).")

with tab2:
    waccs = np.round(np.arange(max(0.05, wacc - 0.03), wacc + 0.031, 0.01), 3)
    growths = np.round(np.arange(growth - 0.06, growth + 0.061, 0.02), 3)
    z = np.full((len(growths), len(waccs)), np.nan)
    for i, g in enumerate(growths):
        for j, w in enumerate(waccs):
            e, _, _ = dcf_value(fcf0, g, tgrowth, w)
            if not np.isnan(e):
                z[i, j] = (e - data["debt"] + data["cash"]) / shares
    fig = go.Figure(go.Heatmap(
        z=z, x=[f"{w:.1%}" for w in waccs], y=[f"{g:+.0%}" for g in growths],
        colorscale="RdYlGn", zmid=float(price),
        text=np.vectorize(lambda v: f"${v:,.0f}" if not np.isnan(v) else "")(z),
        texttemplate="%{text}"))
    fig.update_layout(template="plotly_dark", height=480,
                      title=f"Intrinsic value per share — growth × WACC (green > price ${price:,.0f})",
                      xaxis_title="WACC", yaxis_title="FCF growth")
    st.plotly_chart(fig, use_container_width=True)

with tab3:
    peers_raw = st.text_input("Peers (comma-separated)",
                              {"AAPL": "MSFT,GOOGL,META,NVDA",
                               "MSFT": "AAPL,GOOGL,ORCL,CRM"}.get(ticker, "AAPL,MSFT,GOOGL"))
    peer_list = [ticker] + [p.strip().upper() for p in peers_raw.split(",") if p.strip()]
    rows = []
    for p in dict.fromkeys(peer_list):
        try:
            pi = yf.Ticker(p).info
            rows.append({"ticker": p,
                         "P/E": pi.get("trailingPE"),
                         "Fwd P/E": pi.get("forwardPE"),
                         "EV/EBITDA": pi.get("enterpriseToEbitda"),
                         "P/S": pi.get("priceToSalesTrailing12Months"),
                         "Margin": pi.get("profitMargins"),
                         "Mkt Cap ($B)": (pi.get("marketCap") or 0) / 1e9})
        except Exception:
            continue
    comps = pd.DataFrame(rows).set_index("ticker")
    st.dataframe(comps.style.format({"P/E": "{:.1f}", "Fwd P/E": "{:.1f}",
                                     "EV/EBITDA": "{:.1f}", "P/S": "{:.1f}",
                                     "Margin": "{:.1%}", "Mkt Cap ($B)": "{:,.0f}"},
                                    na_rep="—")
                 .background_gradient(subset=["P/E", "EV/EBITDA"], cmap="RdYlGn_r"),
                 use_container_width=True)
    st.caption("Red = expensive vs peers on that multiple. Multiples are a sanity "
               "check on the DCF — if your DCF says +80% upside but the company "
               "already trades at twice the peer EV/EBITDA, revisit your growth input.")
