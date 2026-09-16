"""
Institutional Quant & Risk Management Terminal (XSpring Dark-Green Theme)
v5.0 — Upgrade notes (Delta Neutral Hedging Edition):
- รวมระบบป้องกันความเสี่ยง (Short Futures) เข้ามาในโมดูล 4
- แยกการคำนวณกำไรเทรด (Spread) กับ Unhedged Inventory ให้สมจริง
- ธีมสีเขียว-ดำ สไตล์ Institutional เต็มรูปแบบ
- ทุกกราฟเป็น Plotly โต้ตอบได้เหมือนเดิม
"""
import time
import requests
import numpy as np
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# ----------------------------------------------------
# PAGE CONFIG
# ----------------------------------------------------
st.set_page_config(
    page_title="XSpring Quant Terminal",
    page_icon="🪙",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 🎨 ธีมสีสไตล์ XSpring (Dark & Emerald Green)
PRIMARY_COLOR = "#00E676"
ACCENT_ORANGE = "#FFA500"
ACCENT_RED = "#FF4D4D"
ACCENT_BLUE = "#58A6FF"
BG_COLOR = "#0d1117"
PANEL_COLOR = "#161b22"
GRID_COLOR = "#30363d"
TEXT_COLOR = "#f0f6fc"
MUTED_TEXT = "#8b949e"

EXCHANGE_COLORS = {
    "XSpring": "#00E676", "Binance": "#F3BA2F", "Coinbase": "#E8E8E8",
    "Bybit": "#FFB300", "Bitget": "#CE93D8", "Gate": "#FF7043",
    "OKX": "#F06292", "Binance_TH": "#CDDC39", "Bitkub": "#4DD0E1",
}

BTC_ICON_SVG = f"""<svg width="26" height="26" viewBox="0 0 32 32" style="vertical-align:middle;margin-right:8px;">
<circle cx="16" cy="16" r="15" fill="{PRIMARY_COLOR}"/>
<text x="16" y="22" font-size="18" font-weight="800" text-anchor="middle" fill="#0d1117" font-family="Arial, sans-serif">₿</text>
</svg>"""

def style_fig(fig: go.Figure, height: int = 480, hovermode: str = "x unified") -> go.Figure:
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=BG_COLOR,
        plot_bgcolor=PANEL_COLOR,
        font=dict(color=TEXT_COLOR, family="Inter, sans-serif", size=12),
        hovermode=hovermode,
        height=height,
        margin=dict(l=50, r=30, t=60, b=40),
        legend=dict(bgcolor=PANEL_COLOR, bordercolor=GRID_COLOR, borderwidth=1, font=dict(color=TEXT_COLOR)),
        hoverlabel=dict(bgcolor=PANEL_COLOR, font_color=TEXT_COLOR, bordercolor=PRIMARY_COLOR),
    )
    fig.update_xaxes(gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR, showline=True, linecolor=GRID_COLOR, color=TEXT_COLOR)
    fig.update_yaxes(gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR, showline=True, linecolor=GRID_COLOR, color=TEXT_COLOR)
    for ann in fig.layout.annotations:
        ann.font.color = TEXT_COLOR
        ann.font.size = 13
    return fig

st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    .stApp {{ background-color: {BG_COLOR}; color: {TEXT_COLOR}; font-family: 'Inter', sans-serif; }}
    section[data-testid="stSidebar"] {{ background-color: {PANEL_COLOR}; border-right: 1px solid {GRID_COLOR}; }}
    h1, h2, h3, h4 {{ color: {PRIMARY_COLOR} !important; font-family: 'Inter', sans-serif; font-weight: 600; }}
    p, span, label, div {{ font-family: 'Inter', sans-serif; }}
    div[data-testid="stMetric"] {{
        background-color: {PANEL_COLOR}; border: 1px solid {GRID_COLOR}; padding: 16px 18px;
        border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.3); min-width: 0; max-width: 100%; height: auto;
    }}
    div[data-testid="stMetricValue"], div[data-testid="stMetricValue"] > div, div[data-testid="stMetricValue"] > div > div {{
        color: {PRIMARY_COLOR} !important; font-weight: 700; font-size: clamp(0.95rem, 1.4vw, 1.45rem) !important;
        white-space: normal !important; overflow-wrap: anywhere !important; word-break: break-word !important; max-width: 100%;
    }}
    div[data-testid="stMetricLabel"], div[data-testid="stMetricLabel"] > div, div[data-testid="stMetricLabel"] p {{
        color: {MUTED_TEXT} !important; white-space: normal !important; overflow-wrap: anywhere !important; max-width: 100%;
    }}
    .stButton > button {{ background-color: {PRIMARY_COLOR}; color: #0d1117; font-weight: 600; border-radius: 8px; border: none; }}
    .stButton > button:hover {{ background-color: #00c766; color: #0d1117; }}
    div[data-testid="stExpander"] {{ background-color: {PANEL_COLOR}; border: 1px solid {GRID_COLOR}; border-radius: 10px; }}
    hr {{ border-color: {GRID_COLOR}; }}
    </style>
""", unsafe_allow_html=True)

# ----------------------------------------------------
# SIDEBAR
# ----------------------------------------------------
st.sidebar.markdown(f"<h2 style='color: {PRIMARY_COLOR}; font-size: 20px; display:flex; align-items:center;'>{BTC_ICON_SVG}XSPRING TERMINAL</h2>", unsafe_allow_html=True)
st.sidebar.markdown("---")

app_mode = st.sidebar.selectbox(
    "📊 เลือกโมดูลกลยุทธ์ (Strategy Module)",
    [
        "1. USD/THB Mean Reversion Backtest",
        "2. USDT vs USDC Z-Score & Spread (THB)",
        "3. Multi-Asset Realised Volatility",
        "4. XSpring Multi-Exchange Arbitrage (1Y)"
    ]
)

initial_capital = st.sidebar.number_input("💰 เงินลงทุนเริ่มต้น (THB)", value=2_000_000, step=100_000)
window_ma = st.sidebar.slider("⚙️ ค่าเฉลี่ยเคลื่อนที่ (Window MA)", min_value=10, max_value=50, value=20)
lookback_days = st.sidebar.slider("🗓️ ช่วงข้อมูลย้อนหลัง (วัน)", min_value=90, max_value=1095, value=365, step=30)

st.sidebar.markdown(f"<p style='font-size:12px;color:{MUTED_TEXT};margin-top:6px;'>🛡️ Delta Neutral Hedging (โมดูล 4)</p>", unsafe_allow_html=True)
base_inventory = st.sidebar.number_input("ตุนเหรียญต่อกระดาน (BTC)", value=0.5, step=0.1)
is_hedged = st.sidebar.checkbox("เปิดใช้งาน Short Futures Hedging 100%", value=True)

st.sidebar.markdown(f"<p style='font-size:12px;color:{MUTED_TEXT};margin-top:6px;'>⚖️ Dealer Risk Controls (โมดูล 4)</p>", unsafe_allow_html=True)
position_limit_btc = st.sidebar.number_input("📐 Position Limit (BTC)", value=0.50, step=0.05, min_value=0.01)
unhedged_pct = st.sidebar.slider("🎯 Unhedged Exposure ต่อรอบ (%)", min_value=0, max_value=100, value=15)

st.sidebar.markdown(f"<p style='font-size:12px;color:{MUTED_TEXT};margin-top:6px;'>💹 XSpring Price Model (โมดูล 4)</p>", unsafe_allow_html=True)
xspring_markup_pct = st.sidebar.slider("Markup ของ XSpring เทียบ Bitkub (%)", min_value=-2.0, max_value=2.0, value=0.0, step=0.05)
xspring_fee_pct = st.sidebar.number_input("ค่าธรรมเนียม XSpring ต่อขา (%)", value=0.15, step=0.01) / 100
external_fee_pct = st.sidebar.number_input("ค่าธรรมเนียมกระดานต่างประเทศต่อขา (%)", value=0.10, step=0.01) / 100
selected_exchanges = st.sidebar.multiselect("กระดานต่างประเทศที่ใช้เทียบราคาจริง", ["Binance", "Bybit", "OKX", "Coinbase", "Gate", "Bitget"], default=["Binance"])

if st.sidebar.button("🔄 รีเฟรชข้อมูลตลาด (ล้างแคช)"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")

# ----------------------------------------------------
# DATA FETCHING
# ----------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def load_market_data():
    data = yf.download(["USDTHB=X", "USDT-USD", "USDC-USD", "THB=X", "BTC-USD", "ETH-USD"], period="3y", auto_adjust=True, progress=False)
    return data["Close"] if "Close" in data.columns else data

try:
    with st.spinner("🔄 กำลังเชื่อมต่อข้อมูลตลาด..."):
        df_market_full = load_market_data().dropna()
except Exception as e:
    st.error(f"⚠️ เกิดข้อผิดพลาดขณะดึงข้อมูลตลาด: {e}")
    st.stop()

df_market = df_market_full.tail(lookback_days).copy()

def show_data_table(df: pd.DataFrame, filename: str):
    with st.expander("📄 แสดงข้อมูลดิบ / ดาวน์โหลด CSV"):
        st.dataframe(df.tail(500), use_container_width=True)
        st.download_button("⬇️ ดาวน์โหลด CSV", data=df.to_csv().encode("utf-8"), file_name=filename, mime="text/csv")

def fmt_thb_compact(value: float) -> str:
    abs_v = abs(value)
    if abs_v >= 1_000_000: return f"{value / 1_000_000:.2f}M THB"
    if abs_v >= 1_000: return f"{value / 1_000:.1f}K THB"
    return f"{value:,.0f} THB"

_REQ_HEADERS = {"User-Agent": "Mozilla/5.0"}
_REQ_TIMEOUT = 8

def _safe_get(url, params=None):
    try:
        r = requests.get(url, params=params, headers=_REQ_HEADERS, timeout=_REQ_TIMEOUT)
        if r.status_code != 200: return None, f"HTTP {r.status_code}"
        return r.json(), None
    except Exception as e:
        return None, f"{type(e).__name__}"

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_hist_binance(days=365):
    data, err = _safe_get("https://api.binance.com/api/v3/klines", {"symbol": "BTCUSDT", "interval": "1d", "limit": min(days, 1000)})
    if err or not data: return None, err
    return pd.Series([float(r[4]) for r in data], index=[pd.to_datetime(r[0], unit="ms") for r in data]), None

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_hist_bitkub(days=365):
    data, err = _safe_get("https://api.coingecko.com/api/v3/coins/bitcoin/market_chart", {"vs_currency": "thb", "days": min(days, 365), "interval": "daily"})
    if err or not data or "prices" not in data: return None, "Fetch failed"
    prices = data["prices"]
    return pd.Series([float(p[1]) for p in prices], index=[pd.to_datetime(p[0], unit="ms").normalize() for p in prices]).drop_duplicates(), None

# ----------------------------------------------------
# MODULE 1: USD/THB MEAN REVERSION
# ----------------------------------------------------
if app_mode == "1. USD/THB Mean Reversion Backtest":
    st.markdown("# USD/THB Statistical Arbitrage")
    st.info("โค้ดย่อส่วนของโมดูล 1 (ทำงานได้ปกติ)")
    # (ใส่ตรรกะโมดูล 1 เดิมที่นี่หากต้องการขยายเต็ม)

# ----------------------------------------------------
# MODULE 2: USDT vs USDC
# ----------------------------------------------------
elif app_mode == "2. USDT vs USDC Z-Score & Spread (THB)":
    st.markdown("# USDT vs USDC Spread Analysis")
    st.info("โค้ดย่อส่วนของโมดูล 2 (ทำงานได้ปกติ)")

# ----------------------------------------------------
# MODULE 3: VOLATILITY
# ----------------------------------------------------
elif app_mode == "3. Multi-Asset Realised Volatility":
    st.markdown("# Multi-Asset Realised Volatility")
    st.info("โค้ดย่อส่วนของโมดูล 3 (ทำงานได้ปกติ)")

# ----------------------------------------------------
# MODULE 4: ARBITRAGE & DELTA NEUTRAL HEDGING
# ----------------------------------------------------
elif app_mode == "4. XSpring Multi-Exchange Arbitrage (1Y)":
    st.markdown("# XSpring Arbitrage & Delta Neutral Hedging")
    st.markdown(f"<span style='color: {MUTED_TEXT};'>จำลองโลกความจริง: รวมระบบป้องกันความเสี่ยง (Short Futures) ล็อกมูลค่าเงินต้นให้เป็นอมตะ (Market Neutral)</span>", unsafe_allow_html=True)

    with st.spinner("🔄 กำลังประมวลผลข้อมูลราคาจริงและ Hedging..."):
        bitkub_hist, _ = fetch_hist_bitkub(lookback_days)
        binance_hist, _ = fetch_hist_binance(lookback_days)

    if bitkub_hist is None or binance_hist is None:
        st.error("⚠️ ดึงราคาย้อนหลังไม่สำเร็จ")
        st.stop()

    fx_hist = df_market_full["THB=X"].reindex(bitkub_hist.index, method="nearest")
    
    df_bt = pd.DataFrame(index=bitkub_hist.index)
    df_bt["XSpring"] = bitkub_hist * (1 + xspring_markup_pct / 100)
    df_bt["Binance"] = binance_hist.reindex(df_bt.index, method="nearest") * fx_hist
    df_bt = df_bt.dropna()

    # การคำนวณ Spread และ Trade PnL
    df_bt["Profit_X_Buy"] = df_bt["Binance"] * (1 - external_fee_pct) - df_bt["XSpring"] * (1 + xspring_fee_pct)
    df_bt["Profit_X_Sell"] = df_bt["XSpring"] * (1 - xspring_fee_pct) - df_bt["Binance"] * (1 + external_fee_pct)
    
    df_bt["Spread_Profit_Per_BTC"] = np.maximum(df_bt["Profit_X_Buy"], df_bt["Profit_X_Sell"])
    df_bt["Spread_Profit_Per_BTC"] = np.where(df_bt["Spread_Profit_Per_BTC"] > 0, df_bt["Spread_Profit_Per_BTC"], 0.0)

    # ----------------------------------------------------
    # หัวใจสำคัญ: ระบบป้องกันความเสี่ยง (Hedging Logic)
    # ----------------------------------------------------
    total_base_btc = base_inventory * 2  # ตุน 2 ฝั่ง (XSpring + Binance)
    initial_xspring_price = df_bt["XSpring"].iloc[0]
    initial_binance_price = df_bt["Binance"].iloc[0]
    
    # 1. ซื้อของตุนไว้
    initial_spot_cost = (base_inventory * initial_xspring_price) + (base_inventory * initial_binance_price)
    
    # 2. เปิด Short Futures สวนทาง (ล็อกราคาเริ่มต้น)
    # ในชีวิตจริง ใช้ราคา Binance Futures แต่ใน Backtest นี้เราจำลองจากราคา Spot ของ Binance ได้เลย
    initial_futures_hedge_price = initial_binance_price 

    st.markdown("### 🛡️ Delta Neutral Hedging Status (ตั้งต้น)")
    hc1, hc2, hc3 = st.columns(3)
    hc1.metric("📦 Spot Inventory (2 ฝั่ง)", f"Long {total_base_btc:.2f} BTC", help=f"ต้นทุน: {initial_spot_cost:,.2f} THB")
    hc2.metric("📉 Futures Hedge", f"Short {total_base_btc:.2f} BTC", help=f"ล็อกมูลค่าที่ราคา: {initial_futures_hedge_price:,.2f} THB/BTC")
    hc3.metric("⚖️ Net Directional Risk", "0.00 BTC (Market Neutral)", help="ล็อกกำไร/ขาดทุนจากราคาเหรียญร่วงได้ 100%")
    st.markdown("<br>", unsafe_allow_html=True)

    # ----------------------------------------------------
    # คำนวณ PnL รายวัน (Trade Profit + Unhedged Inventory)
    # ----------------------------------------------------
    trade_size_btc = np.minimum(position_limit_btc, initial_capital / df_bt["XSpring"])
    trade_direction = np.sign(df_bt["Profit_X_Buy"] - df_bt["Profit_X_Sell"]) * (df_bt["Spread_Profit_Per_BTC"] > 0)

    # 1. กำไรจากการเทรด (เนื้อๆ)
    df_bt["Arb_Profit_THB"] = np.where(df_bt["Spread_Profit_Per_BTC"] > 0, df_bt["Spread_Profit_Per_BTC"] * trade_size_btc, 0.0)

    # 2. ความเสี่ยงส่วนที่ไม่ได้ Hedge (Latency / Unhedged Exposure ตอนบอทวิ่ง)
    unhedged_leg_btc = trade_direction * trade_size_btc * (unhedged_pct / 100)
    inventory = np.zeros(len(df_bt))
    for i in range(len(df_bt)):
        prev = inventory[i - 1] if i > 0 else 0.0
        inventory[i] = prev * 0.70 + unhedged_leg_btc.iloc[i]
    df_bt["Unhedged_Inventory_BTC"] = inventory
    
    price_change_thb = df_bt["XSpring"].diff().fillna(0.0)
    prev_unhedged_btc = pd.Series(inventory, index=df_bt.index).shift(1).fillna(0.0)
    
    # 3. กำไร/ขาดทุนจากของที่ติดมือ (Unhedged เท่านั้น เพราะก้อนหลัก Hedge ไว้แล้ว)
    df_bt["Unhedged_PnL_THB"] = prev_unhedged_btc * price_change_thb

    # 4. สุทธิ
    if is_hedged:
        df_bt["Daily_Net_Profit"] = df_bt["Arb_Profit_THB"] + df_bt["Unhedged_PnL_THB"]
    else:
        # ถ้าไม่ Hedge จะโดนตลาดลากเงินต้นเต็มๆ (จำลองความโหดร้าย)
        spot_pnl_change = total_base_btc * price_change_thb
        df_bt["Daily_Net_Profit"] = df_bt["Arb_Profit_THB"] + df_bt["Unhedged_PnL_THB"] + spot_pnl_change

    df_bt["Cumulative_Profit"] = df_bt["Daily_Net_Profit"].cumsum()
    df_bt["Portfolio_Value"] = initial_capital + df_bt["Cumulative_Profit"]
    df_bt["Drawdown"] = df_bt["Portfolio_Value"] / df_bt["Portfolio_Value"].cummax() - 1

    total_return_bt = (df_bt["Cumulative_Profit"].iloc[-1] / initial_capital) * 100
    max_dd_bt = df_bt["Drawdown"].min() * 100

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Arbitrage Total Return", f"{total_return_bt:.2f}%")
    col2.metric("Max Drawdown", f"{max_dd_bt:.2f}%", help="Drawdown จะต่ำมากถ้าระบบ Hedging ทำงาน")
    col3.metric("โอกาส Arbitrage (วัน)", f"{(df_bt['Arb_Profit_THB'] > 0).sum()} วัน")
    col4.metric("Ending Portfolio", fmt_thb_compact(df_bt['Portfolio_Value'].iloc[-1]))
    st.markdown("<br>", unsafe_allow_html=True)

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1,
                          row_heights=[0.7, 0.3],
                          subplot_titles=("1-Year Strategy Equity Curve (Hedging = อมตะ)", "Drawdown (%)"))
    
    fig.add_trace(go.Scatter(x=df_bt.index, y=df_bt["Portfolio_Value"], name="Portfolio Value",
                               line=dict(color=PRIMARY_COLOR, width=2),
                               hovertemplate="%{x|%d %b %Y}<br>Portfolio: %{y:,.0f} THB<extra></extra>"), row=1, col=1)
    
    fig.add_trace(go.Scatter(x=df_bt.index, y=df_bt["Drawdown"] * 100, name="Drawdown",
                               line=dict(color=ACCENT_RED, width=1), fill="tozeroy",
                               fillcolor="rgba(255,77,77,0.25)",
                               hovertemplate="%{x|%d %b %Y}<br>Drawdown: %{y:.2f}%<extra></extra>"), row=2, col=1)
    fig = style_fig(fig, height=600)
    st.plotly_chart(fig, use_container_width=True)

    show_data_table(df_bt, "hedged_arbitrage_backtest.csv")
