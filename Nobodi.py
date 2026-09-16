"""
Institutional Quant & Risk Management Terminal (XSpring Dark-Green Theme)
=======================================================================
รวมศูนย์กลยุทธ์ Quant ทั้งหมด:
1. USD/THB Mean Reversion
2. USDT vs USDC Z-Score & Spread (THB)
3. Multi-Asset Realised Volatility
4. XSpring Multi-Exchange Spread & Arbitrage Analysis

v4.0 — Upgrade notes:
- เปลี่ยนกราฟทั้งหมดจาก matplotlib (รูปนิ่ง) เป็น Plotly (โต้ตอบได้: เมาส์ชี้ดูค่าตัวเลข/วันที่จริง,
  ซูม, แพน, ซ่อน/แสดงเส้นจาก legend, unified hover ทุกซีรีส์พร้อมกัน)
- ธีมกราฟมืดเข้าธีม XSpring (เขียว/ดำ) ทุกจุด ตัวอักษรอ่านชัดไม่กลืนพื้นหลัง
- แก้ st.metric ให้มีการ์ดพื้นหลังจริง
- error handling ตอนโหลดข้อมูล + ปุ่มรีเฟรชแคช
- ตัวกรองช่วงวันที่ย้อนหลังในไซด์บาร์
- ตัวชี้วัดเพิ่ม: Sharpe Ratio, Win Rate, Correlation, Drawdown ทุกโมดูล
- ทุกโมดูลมีตารางข้อมูลดิบ + ปุ่มดาวน์โหลด CSV
"""
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

# ไอคอน BTC แบบ inline SVG (ไม่พึ่งพาโหลดรูปจากเน็ต) — วงกลมเขียวธีม XSpring + สัญลักษณ์ ₿
BTC_ICON_SVG = f"""<svg width="26" height="26" viewBox="0 0 32 32" style="vertical-align:middle;margin-right:8px;">
<circle cx="16" cy="16" r="15" fill="{PRIMARY_COLOR}"/>
<text x="16" y="22" font-size="18" font-weight="800" text-anchor="middle" fill="#0d1117" font-family="Arial, sans-serif">₿</text>
</svg>"""


def style_fig(fig: go.Figure, height: int = 480, hovermode: str = "x unified") -> go.Figure:
    """ตั้งค่าธีมมืด XSpring ให้กราฟ Plotly ทุกใบแบบ consistent"""
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=BG_COLOR,
        plot_bgcolor=PANEL_COLOR,
        font=dict(color=TEXT_COLOR, family="Inter, sans-serif", size=12),
        hovermode=hovermode,
        height=height,
        margin=dict(l=50, r=30, t=60, b=40),
        legend=dict(bgcolor=PANEL_COLOR, bordercolor=GRID_COLOR, borderwidth=1,
                    font=dict(color=TEXT_COLOR)),
        hoverlabel=dict(bgcolor=PANEL_COLOR, font_color=TEXT_COLOR, bordercolor=PRIMARY_COLOR),
    )
    fig.update_xaxes(gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR, showline=True,
                      linecolor=GRID_COLOR, color=TEXT_COLOR)
    fig.update_yaxes(gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR, showline=True,
                      linecolor=GRID_COLOR, color=TEXT_COLOR)
    for ann in fig.layout.annotations:
        ann.font.color = TEXT_COLOR
        ann.font.size = 13
    return fig


# Custom CSS
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    .stApp {{
        background-color: {BG_COLOR};
        color: {TEXT_COLOR};
        font-family: 'Inter', sans-serif;
    }}
    section[data-testid="stSidebar"] {{
        background-color: {PANEL_COLOR};
        border-right: 1px solid {GRID_COLOR};
    }}
    h1, h2, h3, h4 {{
        color: {PRIMARY_COLOR} !important;
        font-family: 'Inter', sans-serif;
        font-weight: 600;
    }}
    p, span, label, div {{
        font-family: 'Inter', sans-serif;
    }}

    div[data-testid="stMetric"] {{
        background-color: {PANEL_COLOR};
        border: 1px solid {GRID_COLOR};
        padding: 16px 18px;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    }}
    div[data-testid="stMetricValue"] {{
        color: {PRIMARY_COLOR} !important;
        font-weight: 700;
    }}
    div[data-testid="stMetricLabel"] {{
        color: {MUTED_TEXT} !important;
    }}

    .stButton > button {{
        background-color: {PRIMARY_COLOR};
        color: #0d1117;
        font-weight: 600;
        border-radius: 8px;
        border: none;
    }}
    .stButton > button:hover {{
        background-color: #00c766;
        color: #0d1117;
    }}
    div[data-testid="stExpander"] {{
        background-color: {PANEL_COLOR};
        border: 1px solid {GRID_COLOR};
        border-radius: 10px;
    }}
    hr {{ border-color: {GRID_COLOR}; }}
    </style>
""", unsafe_allow_html=True)

# ----------------------------------------------------
# SIDEBAR: CONTROLS & NAVIGATION
# ----------------------------------------------------
st.sidebar.markdown(
    f"<h2 style='color: {PRIMARY_COLOR}; font-size: 20px; display:flex; align-items:center;'>"
    f"{BTC_ICON_SVG}XSPRING TERMINAL</h2>",
    unsafe_allow_html=True
)
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

initial_capital = st.sidebar.number_input("💰 เงินลงทุนเริ่มต้น (THB)", value=1_000_000, step=100_000)
window_ma = st.sidebar.slider("⚙️ ค่าเฉลี่ยเคลื่อนที่ (Window MA)", min_value=10, max_value=50, value=20)

lookback_days = st.sidebar.slider("🗓️ ช่วงข้อมูลย้อนหลัง (วัน)", min_value=90, max_value=1095, value=1095, step=30,
                                   help="กรองข้อมูลจากทั้งหมด 3 ปี ให้แสดงเฉพาะ N วันล่าสุด")

if st.sidebar.button("🔄 รีเฟรชข้อมูลตลาด (ล้างแคช)"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown(f"<p style='font-size: 11px; color: {MUTED_TEXT};'>Institutional Quantitative Finance Engine v4.0 · Interactive Charts</p>", unsafe_allow_html=True)

# ----------------------------------------------------
# DATA FETCHING CACHE (พร้อม error handling)
# ----------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def load_market_data():
    data = yf.download(["USDTHB=X", "USDT-USD", "USDC-USD", "THB=X", "BTC-USD"],
                        period="3y", auto_adjust=True, progress=False)
    if "Close" in data.columns:
        close_data = data["Close"]
    else:
        close_data = data
    return close_data.dropna()


try:
    with st.spinner("🔄 กำลังเชื่อมต่อข้อมูลตลาดแบบเรียลไทม์..."):
        df_market_full = load_market_data()
    if df_market_full.empty:
        st.error("⚠️ ไม่พบข้อมูลตลาดที่ดาวน์โหลดมา กรุณาลองรีเฟรชอีกครั้ง")
        st.stop()
except Exception as e:
    st.error(f"⚠️ เกิดข้อผิดพลาดขณะดึงข้อมูลตลาด: {e}")
    st.stop()

df_market = df_market_full.tail(lookback_days).copy()


def show_data_table(df: pd.DataFrame, filename: str, label: str = "📄 แสดงข้อมูลดิบ / ดาวน์โหลด CSV"):
    with st.expander(label):
        st.dataframe(df.tail(500), use_container_width=True)
        st.download_button(
            "⬇️ ดาวน์โหลด CSV",
            data=df.to_csv().encode("utf-8"),
            file_name=filename,
            mime="text/csv",
        )


def sharpe_ratio(returns: pd.Series, periods_per_year: int = 365) -> float:
    r = returns.dropna()
    if r.std() == 0 or len(r) == 0:
        return 0.0
    return (r.mean() / r.std()) * np.sqrt(periods_per_year)


# ----------------------------------------------------
# MODULE 1: USD/THB MEAN REVERSION
# ----------------------------------------------------
if app_mode == "1. USD/THB Mean Reversion Backtest":
    st.markdown("# USD/THB Statistical Arbitrage & Mean Reversion")
    st.markdown(f"<span style='color: {MUTED_TEXT};'>ระบบจำลองกลยุทธ์เทรดอัตราแลกเปลี่ยนด้วยหลักการ Z-Score Deviation — เมาส์ชี้บนกราฟเพื่อดูค่าตัวเลขจริง</span>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    df_thb = pd.DataFrame(index=df_market.index)
    df_thb["USDTHB"] = df_market["USDTHB=X"]
    df_thb = df_thb.dropna()

    df_thb["MA"] = df_thb["USDTHB"].rolling(window_ma).mean()
    df_thb["STD"] = df_thb["USDTHB"].rolling(window_ma).std()
    df_thb["Z_Score"] = (df_thb["USDTHB"] - df_thb["MA"]) / df_thb["STD"]

    df_thb["Signal"] = 0
    df_thb.loc[df_thb["Z_Score"] < -2, "Signal"] = 1
    df_thb.loc[df_thb["Z_Score"] > 2, "Signal"] = -1
    df_thb["Position"] = df_thb["Signal"].shift(1).fillna(0)

    df_thb["USDTHB_Ret"] = df_thb["USDTHB"].pct_change()
    df_thb["Strategy_Returns"] = df_thb["Position"] * df_thb["USDTHB_Ret"]
    df_thb["Portfolio_Value"] = initial_capital * (1 + df_thb["Strategy_Returns"].fillna(0)).cumprod()

    total_return = (df_thb["Portfolio_Value"].iloc[-1] / initial_capital - 1) * 100
    drawdown = df_thb["Portfolio_Value"] / df_thb["Portfolio_Value"].cummax() - 1
    max_dd = drawdown.min() * 100
    sharpe = sharpe_ratio(df_thb["Strategy_Returns"])

    trades = df_thb["Position"].diff().fillna(0) != 0
    n_trades = int(trades.sum())
    win_rate = (df_thb.loc[df_thb["Strategy_Returns"] != 0, "Strategy_Returns"] > 0).mean() * 100 if n_trades > 0 else 0.0

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Return", f"{total_return:.2f}%")
    col2.metric("Max Drawdown", f"{max_dd:.2f}%")
    col3.metric("Sharpe Ratio", f"{sharpe:.2f}")
    col4.metric("Win Rate", f"{win_rate:.1f}%")
    col5.metric("Ending Portfolio", f"{df_thb['Portfolio_Value'].iloc[-1]:,.0f} THB")
    st.markdown("<br>", unsafe_allow_html=True)

    fig1 = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1,
                          row_heights=[0.7, 0.3],
                          subplot_titles=("Portfolio Value (THB)", "Drawdown (%)"))

    fig1.add_trace(go.Scatter(
        x=df_thb.index, y=df_thb["Portfolio_Value"], name="Equity Curve",
        line=dict(color=PRIMARY_COLOR, width=2),
        hovertemplate="%{x|%d %b %Y}<br>Portfolio: %{y:,.0f} THB<extra></extra>"
    ), row=1, col=1)

    fig1.add_trace(go.Scatter(
        x=drawdown.index, y=drawdown.values * 100, name="Drawdown",
        line=dict(color=ACCENT_RED, width=1), fill="tozeroy",
        fillcolor="rgba(255,77,77,0.25)",
        hovertemplate="%{x|%d %b %Y}<br>Drawdown: %{y:.2f}%<extra></extra>"
    ), row=2, col=1)

    fig1.update_yaxes(title_text="THB", row=1, col=1)
    fig1.update_yaxes(title_text="%", row=2, col=1)
    fig1 = style_fig(fig1, height=650)
    fig1.update_layout(title=dict(text="USD/THB Mean Reversion Strategy", font=dict(color=PRIMARY_COLOR, size=16)))
    st.plotly_chart(fig1, use_container_width=True)

    # กราฟ USD/THB + Z-Score พร้อมจุดสัญญาณซื้อ/ขาย
    fig2 = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1,
                          row_heights=[0.6, 0.4],
                          subplot_titles=("USD/THB & Moving Average", "Z-Score & Trade Signals"))

    fig2.add_trace(go.Scatter(x=df_thb.index, y=df_thb["USDTHB"], name="USD/THB",
                               line=dict(color=TEXT_COLOR, width=1.3),
                               hovertemplate="%{x|%d %b %Y}<br>USD/THB: %{y:.3f}<extra></extra>"), row=1, col=1)
    fig2.add_trace(go.Scatter(x=df_thb.index, y=df_thb["MA"], name=f"MA({window_ma})",
                               line=dict(color=ACCENT_ORANGE, width=1.3, dash="dash"),
                               hovertemplate="%{x|%d %b %Y}<br>MA: %{y:.3f}<extra></extra>"), row=1, col=1)

    buys = df_thb[df_thb["Signal"] == 1]
    sells = df_thb[df_thb["Signal"] == -1]
    fig2.add_trace(go.Scatter(x=buys.index, y=buys["USDTHB"], name="Buy Signal", mode="markers",
                               marker=dict(color=PRIMARY_COLOR, size=8, symbol="triangle-up"),
                               hovertemplate="%{x|%d %b %Y}<br>Buy @ %{y:.3f}<extra></extra>"), row=1, col=1)
    fig2.add_trace(go.Scatter(x=sells.index, y=sells["USDTHB"], name="Sell Signal", mode="markers",
                               marker=dict(color=ACCENT_RED, size=8, symbol="triangle-down"),
                               hovertemplate="%{x|%d %b %Y}<br>Sell @ %{y:.3f}<extra></extra>"), row=1, col=1)

    fig2.add_trace(go.Scatter(x=df_thb.index, y=df_thb["Z_Score"], name="Z-Score",
                               line=dict(color=ACCENT_BLUE, width=1.3),
                               hovertemplate="%{x|%d %b %Y}<br>Z-Score: %{y:.2f}<extra></extra>"), row=2, col=1)
    fig2.add_hline(y=2, line=dict(color=ACCENT_RED, dash="dot"), row=2, col=1)
    fig2.add_hline(y=-2, line=dict(color=PRIMARY_COLOR, dash="dot"), row=2, col=1)
    fig2.add_hline(y=0, line=dict(color=MUTED_TEXT, dash="dash"), row=2, col=1)

    fig2 = style_fig(fig2, height=650)
    st.plotly_chart(fig2, use_container_width=True)

    show_data_table(df_thb, "usdthb_mean_reversion.csv")

# ----------------------------------------------------
# MODULE 2: STABLECOIN Z-SCORE & SPREAD (THB)
# ----------------------------------------------------
elif app_mode == "2. USDT vs USDC Z-Score & Spread (THB)":
    st.markdown("# USDT vs USDC Spread & Z-Score Analysis")
    st.markdown(f"<span style='color: {MUTED_TEXT};'>วิเคราะห์ส่วนต่างราคาระหว่างเหรียญเสถียร (USDT/USDC) แปลงเป็นมูลค่าบาทไทย (THB) — เมาส์ชี้บนกราฟเพื่อดูค่าจริง</span>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    df_s = pd.DataFrame(index=df_market.index)
    df_s["USDT"] = df_market["USDT-USD"]
    df_s["USDC"] = df_market["USDC-USD"]
    df_s["USDTHB"] = df_market["USDTHB=X"]
    df_s = df_s.dropna()

    usd_spread = df_s["USDT"] - df_s["USDC"]
    df_s["Spread_THB"] = usd_spread * df_s["USDTHB"]

    df_s["MA"] = df_s["Spread_THB"].rolling(window_ma).mean()
    df_s["STD"] = df_s["Spread_THB"].rolling(window_ma).std()
    df_s["Z_Score"] = (df_s["Spread_THB"] - df_s["MA"]) / df_s["STD"]
    df_s = df_s.dropna()

    latest_z = df_s["Z_Score"].iloc[-1]
    latest_spread = df_s["Spread_THB"].iloc[-1]
    corr = df_s["USDT"].corr(df_s["USDC"])
    signal_txt = "Overbought ⚠️" if latest_z > 2 else ("Oversold ⚠️" if latest_z < -2 else "Neutral ✅")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Latest Spread (THB)", f"{latest_spread:,.2f}")
    col2.metric("Latest Z-Score", f"{latest_z:.2f}")
    col3.metric("USDT–USDC Correlation", f"{corr:.3f}")
    col4.metric("Signal", signal_txt)
    st.markdown("<br>", unsafe_allow_html=True)

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1,
                         row_heights=[0.55, 0.45],
                         subplot_titles=("USDT vs USDC Spread (THB) & Moving Average", "Z-Score Indicator & Trigger Boundaries"))

    fig.add_trace(go.Scatter(x=df_s.index, y=df_s["Spread_THB"], name="Spread (THB)",
                              line=dict(color=PRIMARY_COLOR, width=1.3),
                              hovertemplate="%{x|%d %b %Y}<br>Spread: %{y:,.2f} THB<extra></extra>"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_s.index, y=df_s["MA"], name=f"MA({window_ma})",
                              line=dict(color=ACCENT_ORANGE, width=1.3, dash="dash"),
                              hovertemplate="%{x|%d %b %Y}<br>MA: %{y:,.2f} THB<extra></extra>"), row=1, col=1)

    fig.add_trace(go.Scatter(x=df_s.index, y=df_s["Z_Score"], name="Z-Score",
                              line=dict(color=ACCENT_RED, width=1.3),
                              hovertemplate="%{x|%d %b %Y}<br>Z-Score: %{y:.2f}<extra></extra>"), row=2, col=1)
    fig.add_hline(y=2, line=dict(color=ACCENT_RED, dash="dot"), annotation_text="Overbought (+2)",
                  annotation_font_color=ACCENT_RED, row=2, col=1)
    fig.add_hline(y=-2, line=dict(color=PRIMARY_COLOR, dash="dot"), annotation_text="Oversold (-2)",
                  annotation_font_color=PRIMARY_COLOR, row=2, col=1)
    fig.add_hline(y=0, line=dict(color=MUTED_TEXT, dash="dash"), row=2, col=1)

    fig.update_yaxes(title_text="THB", row=1, col=1)
    fig.update_yaxes(title_text="Z-Score", row=2, col=1)
    fig = style_fig(fig, height=650)
    st.plotly_chart(fig, use_container_width=True)

    # ราคา USDT vs USDC ดิบ
    fig_raw = go.Figure()
    fig_raw.add_trace(go.Scatter(x=df_s.index, y=df_s["USDT"], name="USDT/USD",
                                  line=dict(color=PRIMARY_COLOR, width=1.3),
                                  hovertemplate="%{x|%d %b %Y}<br>USDT: $%{y:.4f}<extra></extra>"))
    fig_raw.add_trace(go.Scatter(x=df_s.index, y=df_s["USDC"], name="USDC/USD",
                                  line=dict(color=ACCENT_BLUE, width=1.3),
                                  hovertemplate="%{x|%d %b %Y}<br>USDC: $%{y:.4f}<extra></extra>"))
    fig_raw.update_layout(title=dict(text="USDT vs USDC — Raw Price (USD)", font=dict(color=PRIMARY_COLOR, size=16)))
    fig_raw.update_yaxes(title_text="USD")
    fig_raw = style_fig(fig_raw, height=380)
    st.plotly_chart(fig_raw, use_container_width=True)

    show_data_table(df_s, "usdt_usdc_spread.csv")

# ----------------------------------------------------
# MODULE 3: MULTI-ASSET REALISED VOLATILITY
# ----------------------------------------------------
elif app_mode == "3. Multi-Asset Realised Volatility":
    st.markdown("# Multi-Asset Realised Volatility")
    st.markdown(f"<span style='color: {MUTED_TEXT};'>เปรียบเทียบความผันผวนย้อนหลัง 30 วัน (30D Annualised RV %) ของ USDT, USDC และ THB/USD — เมาส์ชี้บนกราฟและ heatmap เพื่อดูค่าจริง</span>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    df_v = pd.DataFrame(index=df_market.index)
    df_v["USDT"] = df_market["USDT-USD"]
    df_v["USDC"] = df_market["USDC-USD"]
    df_v["THB"] = df_market["THB=X"]
    df_v = df_v.dropna()

    log_returns = np.log(df_v / df_v.shift(1))
    realised_vol = (log_returns.rolling(30).std() * np.sqrt(365) * 100).dropna()

    avg_usdt_rv = realised_vol["USDT"].mean()
    avg_usdc_rv = realised_vol["USDC"].mean()
    avg_thb_rv = realised_vol["THB"].mean()

    col1, col2, col3 = st.columns(3)
    col1.metric("USDT Avg Volatility", f"{avg_usdt_rv:.2f}%")
    col2.metric("USDC Avg Volatility", f"{avg_usdc_rv:.2f}%")
    col3.metric("THB/USD Avg Volatility", f"{avg_thb_rv:.2f}%")
    st.markdown("<br>", unsafe_allow_html=True)

    fig = go.Figure()
    rv_colors = {"USDT": PRIMARY_COLOR, "USDC": ACCENT_ORANGE, "THB": ACCENT_RED}
    rv_avg = {"USDT": avg_usdt_rv, "USDC": avg_usdc_rv, "THB": avg_thb_rv}
    for col in ["USDT", "USDC", "THB"]:
        fig.add_trace(go.Scatter(
            x=realised_vol.index, y=realised_vol[col],
            name=f"{col} RV (Avg: {rv_avg[col]:.2f}%)",
            line=dict(color=rv_colors[col], width=1.5),
            hovertemplate="%{x|%d %b %Y}<br>" + col + ": %{y:.2f}%<extra></extra>"
        ))
    fig.update_layout(title=dict(text="30-Day Annualised Realised Volatility Comparison (%)",
                                  font=dict(color=PRIMARY_COLOR, size=16)))
    fig.update_yaxes(title_text="Volatility (%)")
    fig = style_fig(fig, height=480)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### 🔗 Correlation Matrix (Log Returns)")
    corr_matrix = log_returns.corr().round(3)

    fig_heat = go.Figure(data=go.Heatmap(
        z=corr_matrix.values,
        x=list(corr_matrix.columns),
        y=list(corr_matrix.columns),
        colorscale=[[0, "#0d1117"], [0.5, "#134e2e"], [1, PRIMARY_COLOR]],
        zmin=-1, zmax=1,
        text=corr_matrix.values,
        texttemplate="%{text}",
        textfont=dict(color=TEXT_COLOR, size=13),
        hovertemplate="%{y} vs %{x}<br>Correlation: %{z:.3f}<extra></extra>",
        colorbar=dict(title="ρ", tickfont=dict(color=TEXT_COLOR), title_font=dict(color=TEXT_COLOR)),
    ))
    fig_heat.update_layout(title=dict(text="Return Correlation", font=dict(color=PRIMARY_COLOR, size=16)))
    fig_heat = style_fig(fig_heat, height=420, hovermode="closest")
    st.plotly_chart(fig_heat, use_container_width=True)

    show_data_table(realised_vol, "realised_volatility.csv")

# ----------------------------------------------------
# MODULE 4: XSPRING MULTI-EXCHANGE ARBITRAGE (1Y)
# ----------------------------------------------------
elif app_mode == "4. XSpring Multi-Exchange Arbitrage (1Y)":
    st.markdown("# XSpring Multi-Exchange Spread & Arbitrage")
    st.markdown(f"<span style='color: {MUTED_TEXT};'>จำลองส่วนต่างราคาและการทำกำไร Arbitrage ระหว่าง XSpring และกระดานซื้อขายชั้นนำระดับโลก "
                f"(ราคาของกระดานอื่นเป็นการจำลองด้วย random noise เพื่อสาธิตกลยุทธ์เท่านั้น ไม่ใช่ข้อมูลจริง) — เมาส์ชี้บนกราฟเพื่อดูค่าจริง</span>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    @st.cache_data(ttl=3600, show_spinner=False)
    def load_arb_data():
        data_arb = yf.download(["BTC-USD", "THB=X"], period="1y", auto_adjust=True, progress=False)["Close"]
        df_a = pd.DataFrame(index=data_arb.index)
        df_a["BTC_USD"] = data_arb["BTC-USD"]
        df_a["FX_THB"] = data_arb["THB=X"]
        df_a["Global_THB"] = df_a["BTC_USD"] * df_a["FX_THB"]
        return df_a.dropna()

    try:
        df_arb = load_arb_data()
        if df_arb.empty:
            st.error("⚠️ ไม่พบข้อมูล BTC/THB สำหรับโมดูล Arbitrage")
            st.stop()
    except Exception as e:
        st.error(f"⚠️ เกิดข้อผิดพลาดขณะดึงข้อมูล: {e}")
        st.stop()

    np.random.seed(42)
    n_days = len(df_arb)

    exchanges = {
        "XSpring": df_arb["Global_THB"] + (np.random.randn(n_days) * 2000) + 1500,
        "Binance": df_arb["Global_THB"] + np.random.randn(n_days) * 800,
        "Coinbase": df_arb["Global_THB"] + np.random.randn(n_days) * 1000,
        "Bybit": df_arb["Global_THB"] + np.random.randn(n_days) * 900,
        "Bitget": df_arb["Global_THB"] + np.random.randn(n_days) * 1200,
        "Gate": df_arb["Global_THB"] + np.random.randn(n_days) * 1300,
        "OKX": df_arb["Global_THB"] + np.random.randn(n_days) * 850,
        "Binance_TH": df_arb["Global_THB"] + np.random.randn(n_days) * 950,
        "Bitkub": df_arb["Global_THB"] + (np.random.randn(n_days) * 1500) - 1000,
    }

    exchange_list = list(exchanges.keys())
    for ex, price in exchanges.items():
        df_arb[ex] = price
        df_arb[f"Spread_{ex}"] = df_arb[ex] - df_arb["Global_THB"]

    fee_pct = 0.0005
    df_arb["Best_External_Buy"] = df_arb[exchange_list].min(axis=1)
    df_arb["Best_External_Sell"] = df_arb[exchange_list].max(axis=1)

    df_arb["Profit_X_Buy"] = df_arb["Best_External_Sell"] * (1 - fee_pct) - df_arb["XSpring"] * (1 + fee_pct)
    df_arb["Profit_X_Sell"] = df_arb["XSpring"] * (1 - fee_pct) - df_arb["Best_External_Buy"] * (1 + fee_pct)

    df_arb["Daily_Net_Profit"] = np.maximum(df_arb["Profit_X_Buy"], df_arb["Profit_X_Sell"])
    df_arb["Daily_Net_Profit"] = np.where(df_arb["Daily_Net_Profit"] > 0, df_arb["Daily_Net_Profit"], 0)

    df_arb["Cumulative_Profit"] = df_arb["Daily_Net_Profit"].cumsum()
    df_arb["Portfolio_Value"] = initial_capital + df_arb["Cumulative_Profit"]
    df_arb["Drawdown"] = df_arb["Portfolio_Value"] / df_arb["Portfolio_Value"].cummax() - 1

    total_return_arb = (df_arb["Cumulative_Profit"].iloc[-1] / initial_capital) * 100
    max_dd_arb = df_arb["Drawdown"].min() * 100
    opportunity_days = int((df_arb["Daily_Net_Profit"] > 0).sum())
    opportunity_rate = opportunity_days / n_days * 100

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Arbitrage Total Return", f"{total_return_arb:.2f}%")
    col2.metric("Max Drawdown", f"{max_dd_arb:.2f}%")
    col3.metric("วันที่มีโอกาส Arbitrage", f"{opportunity_rate:.1f}%")
    col4.metric("Ending Portfolio Value", f"{df_arb['Portfolio_Value'].iloc[-1]:,.0f} THB")
    st.markdown("<br>", unsafe_allow_html=True)

    fig1 = make_subplots(rows=1, cols=1,
                          subplot_titles=("1-Year Price Spread Breakdown: All Exchanges vs Global Benchmark (THB)",))
    for ex in exchange_list:
        is_xspring = ex == "XSpring"
        fig1.add_trace(go.Scatter(
            x=df_arb.index, y=df_arb[f"Spread_{ex}"], name=ex,
            line=dict(color=EXCHANGE_COLORS[ex], width=2.2 if is_xspring else 1),
            opacity=1.0 if is_xspring else 0.55,
            hovertemplate=f"{ex}" + ": %{y:,.0f} THB<extra></extra>"
        ))
    fig1.add_hline(y=0, line=dict(color=MUTED_TEXT, dash="dash"))
    fig1.update_yaxes(title_text="Spread (THB)")
    fig1 = style_fig(fig1, height=480)
    st.plotly_chart(fig1, use_container_width=True)

    fig2 = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                          row_heights=[0.34, 0.33, 0.33],
                          subplot_titles=("Daily Net Arbitrage Profit (THB per BTC)",
                                          "1-Year Strategy Equity Curve",
                                          "Drawdown (%)"))

    fig2.add_trace(go.Scatter(x=df_arb.index, y=df_arb["Daily_Net_Profit"], name="Daily Net Profit",
                               line=dict(color="#3fb950", width=1),
                               hovertemplate="%{x|%d %b %Y}<br>Profit: %{y:,.0f} THB<extra></extra>"), row=1, col=1)

    fig2.add_trace(go.Scatter(x=df_arb.index, y=df_arb["Portfolio_Value"], name="Portfolio Value",
                               line=dict(color=ACCENT_BLUE, width=2),
                               hovertemplate="%{x|%d %b %Y}<br>Portfolio: %{y:,.0f} THB<extra></extra>"), row=2, col=1)

    fig2.add_trace(go.Scatter(x=df_arb.index, y=df_arb["Drawdown"] * 100, name="Drawdown",
                               line=dict(color=ACCENT_RED, width=1), fill="tozeroy",
                               fillcolor="rgba(255,77,77,0.25)",
                               hovertemplate="%{x|%d %b %Y}<br>Drawdown: %{y:.2f}%<extra></extra>"), row=3, col=1)

    fig2 = style_fig(fig2, height=750)
    st.plotly_chart(fig2, use_container_width=True)

    st.markdown("### 📊 สรุป Spread เฉลี่ยรายกระดาน (เทียบ Global Benchmark)")
    avg_spread = pd.Series({ex: df_arb[f"Spread_{ex}"].mean() for ex in exchange_list}).sort_values()

    fig3 = go.Figure(go.Bar(
        x=avg_spread.values, y=avg_spread.index, orientation="h",
        marker_color=[EXCHANGE_COLORS[ex] for ex in avg_spread.index],
        hovertemplate="%{y}<br>Avg Spread: %{x:,.0f} THB<extra></extra>"
    ))
    fig3.add_vline(x=0, line=dict(color=MUTED_TEXT))
    fig3.update_layout(title=dict(text="Average Spread per Exchange (THB)", font=dict(color=PRIMARY_COLOR, size=16)))
    fig3 = style_fig(fig3, height=420, hovermode="closest")
    st.plotly_chart(fig3, use_container_width=True)

    show_data_table(df_arb, "xspring_arbitrage.csv")

st.markdown("---")
st.markdown(
    f"<p style='font-size:11px;color:{MUTED_TEXT};'>⚠️ Disclaimer: เครื่องมือนี้ใช้เพื่อการศึกษาและสาธิตกลยุทธ์เชิงปริมาณเท่านั้น "
    f"ไม่ถือเป็นคำแนะนำการลงทุน ข้อมูลราคาบางส่วน (โมดูล 4) เป็นการจำลองด้วย random noise</p>",
    unsafe_allow_html=True
)