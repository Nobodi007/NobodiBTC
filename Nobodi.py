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
        min-width: 0;
        max-width: 100%;
        box-sizing: border-box;
        overflow: hidden;
        height: auto;
    }}
    /* แก้ปัญหา Streamlit ตัดตัวเลข/ข้อความด้วย "..." (ellipsis) เมื่อการ์ดแคบ
       และแก้ปัญหาตัวเลขยาวๆ ล้นทะลุกรอบการ์ด: บังคับให้ตัดขึ้นบรรทัดใหม่ภายในกรอบเดิม */
    div[data-testid="stMetricValue"],
    div[data-testid="stMetricValue"] > div,
    div[data-testid="stMetricValue"] > div > div {{
        color: {PRIMARY_COLOR} !important;
        font-weight: 700;
        font-size: clamp(0.95rem, 1.4vw, 1.45rem) !important;
        white-space: normal !important;
        overflow-wrap: anywhere !important;
        word-break: break-word !important;
        text-overflow: unset !important;
        line-height: 1.25 !important;
        max-width: 100%;
    }}
    div[data-testid="stMetricLabel"],
    div[data-testid="stMetricLabel"] > div,
    div[data-testid="stMetricLabel"] p {{
        color: {MUTED_TEXT} !important;
        white-space: normal !important;
        overflow-wrap: anywhere !important;
        word-break: break-word !important;
        text-overflow: unset !important;
        max-width: 100%;
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

st.sidebar.markdown(f"<p style='font-size:12px;color:{MUTED_TEXT};margin-top:6px;'>⚖️ Dealer Risk Controls (โมดูล 4)</p>", unsafe_allow_html=True)
position_limit_btc = st.sidebar.number_input("📐 Position Limit (BTC)", value=0.50, step=0.05, min_value=0.01,
                                              help="เพดานสถานะ (inventory) สูงสุดที่ Dealer ถืออนุญาตให้ถือได้ก่อน flag ว่าเกินลิมิต")
unhedged_pct = st.sidebar.slider("🎯 Unhedged Exposure ต่อรอบ (%)", min_value=0, max_value=100, value=15,
                                  help="สัดส่วนของแต่ละรอบ arbitrage ที่ยังไม่ถูก hedge ทันที (ความเสี่ยงจาก latency ระหว่างขา XSpring กับขาตลาดภายนอก)")

st.sidebar.markdown(f"<p style='font-size:12px;color:{MUTED_TEXT};margin-top:6px;'>💹 XSpring Price Model (โมดูล 4 — ราคาจริง)</p>", unsafe_allow_html=True)
xspring_markup_pct = st.sidebar.slider(
    "Markup ของ XSpring เทียบ Bitkub (%)", min_value=-2.0, max_value=2.0, value=0.0, step=0.05,
    help="XSpring ไม่มี orderbook อิสระของตัวเอง ราคาที่แสดงอ้างอิงจาก Bitkub อยู่แล้ว หากสังเกตราคาจริงต่างจาก Bitkub ให้ปรับค่านี้"
)
xspring_fee_pct = st.sidebar.number_input(
    "ค่าธรรมเนียม XSpring ต่อขา (%)", value=0.15, step=0.01, min_value=0.0
) / 100
external_fee_pct = st.sidebar.number_input(
    "ค่าธรรมเนียมกระดานต่างประเทศต่อขา (%)", value=0.10, step=0.01, min_value=0.0
) / 100
selected_exchanges = st.sidebar.multiselect(
    "กระดานต่างประเทศที่ใช้เทียบราคาจริง",
    ["Binance", "Bybit", "OKX", "Coinbase", "Gate", "Bitget"],
    default=["Binance", "Bybit", "OKX", "Coinbase", "Gate", "Bitget"]
)

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
    data = yf.download(["USDTHB=X", "USDT-USD", "USDC-USD", "THB=X", "BTC-USD", "ETH-USD"],
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


def fmt_thb_compact(value: float) -> str:
    """ย่อตัวเลขบาทให้สั้น กันข้อความล้นกรอบการ์ด (ค่าเต็มดูได้จาก tooltip ตอนชี้เมาส์)"""
    abs_v = abs(value)
    if abs_v >= 1_000_000:
        return f"{value / 1_000_000:.2f}M THB"
    if abs_v >= 1_000:
        return f"{value / 1_000:.1f}K THB"
    return f"{value:,.0f} THB"


# ----------------------------------------------------
# MODULE 4 DATA SOURCES: ราคาจริงจาก Public API ของแต่ละกระดาน
# (XSpring ไม่มี public API/ข้อมูลย้อนหลังสาธารณะ — อ้างอิงจาก Bitkub ที่ตรวจสอบแล้วว่า
#  XSpring ใช้ราคาเดียวกันเป็นฐาน + ค่าธรรมเนียมของตัวเอง)
# ----------------------------------------------------
_REQ_HEADERS = {"User-Agent": "Mozilla/5.0 (XSpringQuantTerminal)"}
_REQ_TIMEOUT = 8


def _safe_get(url, params=None):
    """คืนค่า (json_data, error_reason). error_reason เป็น None ถ้าสำเร็จ
    มิฉะนั้นจะบอกสาเหตุจริง เช่น 'HTTP 451' (โดนบล็อกตามภูมิภาค/เซิร์ฟเวอร์ cloud),
    'Timeout', 'Connection error' ฯลฯ เพื่อ debug ได้ตรงจุดแทนที่จะเดา"""
    try:
        r = requests.get(url, params=params, headers=_REQ_HEADERS, timeout=_REQ_TIMEOUT)
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}"
        return r.json(), None
    except requests.exceptions.Timeout:
        return None, "Timeout"
    except requests.exceptions.ConnectionError:
        return None, "Connection error"
    except Exception as e:
        return None, f"{type(e).__name__}"



# ---------- HISTORICAL (ย้อนหลังจริง ~1 ปี) — คืนค่า (series, error_reason) เสมอ ----------
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_hist_binance(days=365):
    data, err = _safe_get("https://api.binance.com/api/v3/klines",
                           {"symbol": "BTCUSDT", "interval": "1d", "limit": min(days, 1000)})
    if err:
        return None, err
    if not data:
        return None, "ไม่มีข้อมูล"
    idx = [pd.to_datetime(r[0], unit="ms") for r in data]
    close = [float(r[4]) for r in data]
    return pd.Series(close, index=idx), None


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_hist_bybit(days=365):
    data, err = _safe_get("https://api.bybit.com/v5/market/kline",
                           {"category": "spot", "symbol": "BTCUSDT", "interval": "D", "limit": min(days, 1000)})
    if err:
        return None, err
    try:
        rows = sorted(data["result"]["list"], key=lambda r: int(r[0]))
    except Exception:
        return None, "รูปแบบข้อมูลเปลี่ยน (parse error)"
    if not rows:
        return None, "ไม่มีข้อมูล"
    idx = [pd.to_datetime(int(r[0]), unit="ms") for r in rows]
    close = [float(r[4]) for r in rows]
    return pd.Series(close, index=idx), None


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_hist_okx(days=365):
    all_rows, after = [], ""
    last_err = None
    for _ in range(5):
        params = {"instId": "BTC-USDT", "bar": "1D", "limit": "100"}
        if after:
            params["after"] = after
        data, err = _safe_get("https://www.okx.com/api/v5/market/history-candles", params)
        if err:
            last_err = err
            break
        try:
            rows = data["data"]
        except Exception:
            last_err = "รูปแบบข้อมูลเปลี่ยน (parse error)"
            break
        if not rows:
            break
        all_rows.extend(rows)
        after = rows[-1][0]
        if len(all_rows) >= days:
            break
    if not all_rows:
        return None, last_err or "ไม่มีข้อมูล"
    all_rows = sorted(all_rows, key=lambda r: int(r[0]))
    idx = [pd.to_datetime(int(r[0]), unit="ms") for r in all_rows]
    close = [float(r[4]) for r in all_rows]
    return pd.Series(close, index=idx).drop_duplicates(), None


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_hist_coinbase(days=365):
    import datetime as dt
    cursor_end = dt.datetime.utcnow()
    remaining = days
    points = {}
    last_err = None
    for _ in range(3):
        span = min(remaining, 300)
        cursor_start = cursor_end - dt.timedelta(days=span)
        params = {"granularity": 86400, "start": cursor_start.isoformat(), "end": cursor_end.isoformat()}
        data, err = _safe_get("https://api.exchange.coinbase.com/products/BTC-USD/candles", params)
        if err:
            last_err = err
            break
        if not data:
            break
        for row in data:  # [time, low, high, open, close, volume]
            points[int(row[0])] = float(row[4])
        cursor_end = cursor_start
        remaining -= span
        if remaining <= 0:
            break
    if not points:
        return None, last_err or "ไม่มีข้อมูล"
    ts = sorted(points.keys())
    return pd.Series([points[t] for t in ts], index=[pd.to_datetime(t, unit="s") for t in ts]), None


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_hist_gate(days=365):
    data, err = _safe_get("https://api.gateio.ws/api/v4/spot/candlesticks",
                           {"currency_pair": "BTC_USDT", "interval": "1d", "limit": min(days, 1000)})
    if err:
        return None, err
    if not data:
        return None, "ไม่มีข้อมูล"
    try:
        idx = [pd.to_datetime(int(r[0]), unit="s") for r in data]
        close = [float(r[2]) for r in data]  # Gate.io: [t, volume, close, high, low, open]
        return pd.Series(close, index=idx), None
    except Exception:
        return None, "รูปแบบข้อมูลเปลี่ยน (parse error)"


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_hist_bitget(days=365):
    all_rows = []
    end_time = int(time.time() * 1000)
    last_err = None
    for _ in range(3):
        params = {"symbol": "BTCUSDT", "granularity": "1day", "endTime": str(end_time), "limit": "200"}
        data, err = _safe_get("https://api.bitget.com/api/v2/spot/market/candles", params)
        if err:
            last_err = err
            break
        try:
            rows = data["data"]
        except Exception:
            last_err = "รูปแบบข้อมูลเปลี่ยน (parse error)"
            break
        if not rows:
            break
        all_rows.extend(rows)
        end_time = int(rows[0][0]) - 1
        if len(all_rows) >= days:
            break
    if not all_rows:
        return None, last_err or "ไม่มีข้อมูล"
    all_rows = sorted(all_rows, key=lambda r: int(r[0]))
    idx = [pd.to_datetime(int(r[0]), unit="ms") for r in all_rows]
    close = [float(r[4]) for r in all_rows]
    return pd.Series(close, index=idx).drop_duplicates(), None


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_hist_bitkub(days=365):
    now = int(time.time())
    frm = now - days * 86400
    data, err = _safe_get("https://api.bitkub.com/tradingview/history",
                           {"symbol": "THB_BTC", "resolution": "1D", "from": frm, "to": now})
    if err:
        return None, err
    if not data or data.get("s") != "ok" or not data.get("t"):
        return None, "รูปแบบข้อมูลเปลี่ยนหรือไม่มีข้อมูล (parse error)"
    idx = [pd.to_datetime(t, unit="s") for t in data["t"]]
    close = [float(c) for c in data["c"]]
    return pd.Series(close, index=idx), None


HIST_FETCHERS = {
    "Binance": fetch_hist_binance, "Bybit": fetch_hist_bybit, "OKX": fetch_hist_okx,
    "Coinbase": fetch_hist_coinbase, "Gate": fetch_hist_gate, "Bitget": fetch_hist_bitget,
}


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
    col5.metric("Ending Portfolio", fmt_thb_compact(df_thb['Portfolio_Value'].iloc[-1]),
                help=f"{df_thb['Portfolio_Value'].iloc[-1]:,.2f} THB")
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
    st.markdown(f"<span style='color: {MUTED_TEXT};'>เปรียบเทียบความผันผวนย้อนหลัง 30 วัน (30D Annualised RV %) ของ BTC, ETH, USDT, USDC และ THB/USD — เมาส์ชี้บนกราฟ/heatmap/พื้นผิว 3D เพื่อดูค่าจริง</span>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    df_v = pd.DataFrame(index=df_market.index)
    df_v["BTC"] = df_market["BTC-USD"]
    df_v["ETH"] = df_market["ETH-USD"]
    df_v["USDT"] = df_market["USDT-USD"]
    df_v["USDC"] = df_market["USDC-USD"]
    df_v["THB"] = df_market["THB=X"]
    df_v = df_v.dropna()

    ASSET_ORDER = ["BTC", "ETH", "USDT", "USDC", "THB"]
    rv_colors = {
        "BTC": "#00E5FF", "ETH": "#B388FF", "USDT": PRIMARY_COLOR,
        "USDC": ACCENT_ORANGE, "THB": ACCENT_RED,
    }

    log_returns = np.log(df_v / df_v.shift(1))
    realised_vol = (log_returns.rolling(30).std() * np.sqrt(365) * 100).dropna()

    rv_avg = {a: realised_vol[a].mean() for a in ASSET_ORDER}

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("BTC Avg Volatility", f"{rv_avg['BTC']:.1f}%")
    col2.metric("ETH Avg Volatility", f"{rv_avg['ETH']:.1f}%")
    col3.metric("USDT Avg Volatility", f"{rv_avg['USDT']:.2f}%")
    col4.metric("USDC Avg Volatility", f"{rv_avg['USDC']:.2f}%")
    col5.metric("THB/USD Avg Volatility", f"{rv_avg['THB']:.2f}%")
    st.markdown("<br>", unsafe_allow_html=True)

    fig = go.Figure()
    for a in ASSET_ORDER:
        fig.add_trace(go.Scatter(
            x=realised_vol.index, y=realised_vol[a],
            name=f"{a} RV (Avg: {rv_avg[a]:.2f}%)",
            line=dict(color=rv_colors[a], width=1.5),
            hovertemplate="%{x|%d %b %Y}<br>" + a + ": %{y:.2f}%<extra></extra>"
        ))
    fig.update_layout(title=dict(text="30-Day Annualised Realised Volatility Comparison (%)",
                                  font=dict(color=PRIMARY_COLOR, size=16)))
    fig.update_yaxes(title_text="Volatility (%)")
    fig = style_fig(fig, height=480)
    st.plotly_chart(fig, use_container_width=True)

    # ----------------------------------------------------
    # 🌋 3D VOLATILITY LANDSCAPE — เวลา × สินทรัพย์ × ความผันผวน
    # ----------------------------------------------------
    st.markdown("### 🌋 Volatility Landscape (3D) — หมุน/ซูม/เอียงมุมได้ด้วยเมาส์")
    st.markdown(f"<span style='color: {MUTED_TEXT}; font-size: 13px;'>พื้นผิว 3 มิติแสดงความสัมพันธ์ระหว่าง เวลา (แกน X) × สินทรัพย์ (แกน Y) × ระดับความผันผวน (แกน Z สูง = ผันผวนมาก) "
                f"— BTC/ETH จะเห็นเป็นเทือกเขาสูงชัดเจน ต่างจาก stablecoin ที่ราบเรียบ</span>", unsafe_allow_html=True)

    z_matrix = np.array([realised_vol[a].values for a in ASSET_ORDER])
    y_positions = list(range(len(ASSET_ORDER)))

    fig_3d = go.Figure(data=[go.Surface(
        x=realised_vol.index, y=y_positions, z=z_matrix,
        colorscale=[[0, "#0d1117"], [0.35, "#0d3d24"], [0.7, "#0e8a4a"], [1, PRIMARY_COLOR]],
        showscale=True,
        colorbar=dict(title="RV %", tickfont=dict(color=TEXT_COLOR), title_font=dict(color=TEXT_COLOR)),
        hovertemplate="Asset: %{customdata}<br>%{x|%d %b %Y}<br>RV: %{z:.2f}%<extra></extra>",
        customdata=np.array([[a] * len(realised_vol.index) for a in ASSET_ORDER]),
        contours=dict(z=dict(show=True, usecolormap=True, highlightcolor=TEXT_COLOR, project=dict(z=True))),
    )])

    fig_3d.update_layout(
        template="plotly_dark",
        paper_bgcolor=BG_COLOR,
        font=dict(color=TEXT_COLOR, family="Inter, sans-serif"),
        height=650,
        margin=dict(l=0, r=0, t=30, b=0),
        scene=dict(
            xaxis=dict(title="Time", color=TEXT_COLOR, gridcolor=GRID_COLOR,
                       backgroundcolor=PANEL_COLOR, zerolinecolor=GRID_COLOR),
            yaxis=dict(title="Asset", color=TEXT_COLOR, gridcolor=GRID_COLOR,
                       backgroundcolor=PANEL_COLOR, zerolinecolor=GRID_COLOR,
                       tickmode="array", tickvals=y_positions, ticktext=ASSET_ORDER),
            zaxis=dict(title="Volatility (%)", color=TEXT_COLOR, gridcolor=GRID_COLOR,
                       backgroundcolor=PANEL_COLOR, zerolinecolor=GRID_COLOR),
            camera=dict(eye=dict(x=1.6, y=-1.6, z=0.9)),
        ),
    )
    st.plotly_chart(fig_3d, use_container_width=True)

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
    fig_heat = style_fig(fig_heat, height=460, hovermode="closest")
    st.plotly_chart(fig_heat, use_container_width=True)

    show_data_table(realised_vol, "realised_volatility.csv")

# ----------------------------------------------------
# MODULE 4: XSPRING MULTI-EXCHANGE ARBITRAGE BACKTEST — ราคาจริงจาก Public API
# ----------------------------------------------------
elif app_mode == "4. XSpring Multi-Exchange Arbitrage (1Y)":
    st.markdown("# XSpring Multi-Exchange Spread & Arbitrage — Backtest")
    st.markdown(f"<span style='color: {MUTED_TEXT};'>Backtest ย้อนหลังด้วยราคาจริงจากกระดานซื้อขายจริง (ไม่ใช่ข้อมูลจำลอง) — "
                f"ราคา XSpring เองไม่มี public API จึงประมาณจากราคา Bitkub ที่ XSpring อ้างอิงอยู่จริง</span>",
                unsafe_allow_html=True)

    st.info(
        "**หมายเหตุเรื่องราคา XSpring:** XSpring Digital ไม่มี orderbook อิสระของตัวเองและไม่มี public API/ข้อมูลย้อนหลังสาธารณะ "
        "จากข้อมูลที่ตรวจสอบได้ ราคาเหรียญของ XSpring อ้างอิงจาก **Bitkub** อยู่แล้ว (บวกค่าธรรมเนียมของ XSpring เอง) "
        "โมดูลนี้จึงใช้ราคา Bitkub ย้อนหลังจริงเป็นฐานราคา XSpring แล้วให้ปรับ Markup ทางแถบด้านซ้ายได้",
        icon="ℹ️"
    )

    with st.spinner("🔄 กำลังดึงข้อมูลราคาย้อนหลังจริงจากแต่ละกระดาน..."):
        bitkub_hist, bitkub_err = fetch_hist_bitkub(lookback_days)
        hist_data, hist_errors = {}, []
        for ex in selected_exchanges:
            fetch_fn = HIST_FETCHERS.get(ex)
            if fetch_fn is None:
                continue
            s, err = fetch_fn(lookback_days)
            if s is None or s.empty:
                hist_errors.append(f"{ex}: {err or 'ไม่มีข้อมูล'}")
            else:
                hist_data[ex] = s

    if bitkub_hist is None or bitkub_hist.empty:
        st.error(f"⚠️ ดึงราคาย้อนหลังของ Bitkub ไม่ได้ ({bitkub_err}) จึงคำนวณราคา XSpring ย้อนหลังไม่ได้")
        st.stop()
    if not hist_data:
        st.error("⚠️ ดึงราคาย้อนหลังของกระดานต่างประเทศไม่ได้เลยสักกระดาน รายละเอียด:")
        for e in hist_errors:
            st.caption(f"• {e}")
        st.stop()
    if hist_errors:
        with st.expander(f"⚠️ ดึงข้อมูลไม่สำเร็จ {len(hist_errors)} กระดาน (คำนวณเฉพาะกระดานที่ดึงได้)"):
            for e in hist_errors:
                st.caption(f"• {e}")

    fx_hist = df_market_full["THB=X"].reindex(bitkub_hist.index, method="nearest")

    df_bt = pd.DataFrame(index=bitkub_hist.index)
    df_bt["Bitkub_THB"] = bitkub_hist
    df_bt["XSpring"] = df_bt["Bitkub_THB"] * (1 + xspring_markup_pct / 100)

    exchange_list_bt = []
    for ex, s in hist_data.items():
        aligned = s.reindex(df_bt.index, method="nearest")
        df_bt[ex] = aligned * fx_hist
        exchange_list_bt.append(ex)

    df_bt = df_bt.dropna()
    if df_bt.empty or len(exchange_list_bt) == 0:
        st.error("⚠️ ข้อมูลที่ดึงมาไม่พอสำหรับคำนวณ (วันที่ไม่ตรงกันหรือข้อมูลไม่พอ)")
        st.stop()

    for ex in exchange_list_bt:
        df_bt[f"Spread_{ex}"] = df_bt[ex] - df_bt["XSpring"]

    df_bt["Best_External_Buy"] = df_bt[exchange_list_bt].min(axis=1)
    df_bt["Best_External_Sell"] = df_bt[exchange_list_bt].max(axis=1)

    df_bt["Profit_X_Buy"] = df_bt["Best_External_Sell"] * (1 - external_fee_pct) - df_bt["XSpring"] * (1 + xspring_fee_pct)
    df_bt["Profit_X_Sell"] = df_bt["XSpring"] * (1 - xspring_fee_pct) - df_bt["Best_External_Buy"] * (1 + external_fee_pct)

    df_bt["Daily_Net_Profit"] = np.maximum(df_bt["Profit_X_Buy"], df_bt["Profit_X_Sell"])
    df_bt["Daily_Net_Profit"] = np.where(df_bt["Daily_Net_Profit"] > 0, df_bt["Daily_Net_Profit"], 0)

    df_bt["Cumulative_Profit"] = df_bt["Daily_Net_Profit"].cumsum()
    df_bt["Portfolio_Value"] = initial_capital + df_bt["Cumulative_Profit"]
    df_bt["Drawdown"] = df_bt["Portfolio_Value"] / df_bt["Portfolio_Value"].cummax() - 1

    n_days_bt = len(df_bt)
    total_return_bt = (df_bt["Cumulative_Profit"].iloc[-1] / initial_capital) * 100
    max_dd_bt = df_bt["Drawdown"].min() * 100
    opportunity_days_bt = int((df_bt["Daily_Net_Profit"] > 0).sum())
    opportunity_rate_bt = opportunity_days_bt / n_days_bt * 100 if n_days_bt else 0

    # --- Dealer Inventory & Risk ---
    trade_direction = np.sign(df_bt["Profit_X_Buy"] - df_bt["Profit_X_Sell"]) * (df_bt["Daily_Net_Profit"] > 0)
    trade_size_btc = np.where(df_bt["Daily_Net_Profit"] > 0,
                               df_bt["Daily_Net_Profit"] / df_bt["XSpring"] * 50, 0.0)
    unhedged_leg_btc = trade_direction * trade_size_btc * (unhedged_pct / 100)
    inventory = np.zeros(n_days_bt)
    for i in range(n_days_bt):
        prev = inventory[i - 1] if i > 0 else 0.0
        inventory[i] = prev * 0.70 + unhedged_leg_btc.iloc[i]
    df_bt["Net_Inventory_BTC"] = inventory
    df_bt["Inventory_Value_THB"] = df_bt["Net_Inventory_BTC"].abs() * df_bt["XSpring"]

    btc_daily_vol = np.log(df_bt["XSpring"] / df_bt["XSpring"].shift(1)).std()
    df_bt["VaR_95_THB"] = 1.65 * btc_daily_vol * df_bt["Inventory_Value_THB"]

    current_inventory = df_bt["Net_Inventory_BTC"].iloc[-1]
    current_var = df_bt["VaR_95_THB"].iloc[-1]
    capital_utilization = (df_bt["Inventory_Value_THB"].iloc[-1] / initial_capital) * 100
    limit_breach_days = int((df_bt["Net_Inventory_BTC"].abs() > position_limit_btc).sum())
    is_breaching_now = abs(current_inventory) > position_limit_btc

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Arbitrage Total Return", f"{total_return_bt:.2f}%")
    col2.metric("Max Drawdown", f"{max_dd_bt:.2f}%")
    col3.metric("วันที่มีโอกาส Arbitrage", f"{opportunity_rate_bt:.1f}%")
    col4.metric("Ending Portfolio Value", fmt_thb_compact(df_bt['Portfolio_Value'].iloc[-1]),
                help=f"{df_bt['Portfolio_Value'].iloc[-1]:,.2f} THB")
    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown("### ⚖️ Dealer Inventory & Risk Exposure")
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Net Inventory ปัจจุบัน", f"{current_inventory:+.4f} BTC",
              help=f"เทียบกับ Position Limit ที่ตั้งไว้ {position_limit_btc:.2f} BTC")
    r2.metric("1-Day VaR (95%)", fmt_thb_compact(current_var), help=f"{current_var:,.2f} THB")
    r3.metric("Capital Utilization", f"{capital_utilization:.2f}%")
    r4.metric("สถานะ Limit", "🔴 เกินลิมิต" if is_breaching_now else "🟢 ปกติ",
              help=f"เกินลิมิตไปแล้ว {limit_breach_days} วัน จากทั้งหมด {n_days_bt} วัน")
    st.markdown("<br>", unsafe_allow_html=True)

    fig1 = make_subplots(rows=1, cols=1,
                          subplot_titles=("1-Year Price Spread: กระดานจริง vs XSpring (≈Bitkub) (THB)",))
    for ex in exchange_list_bt:
        fig1.add_trace(go.Scatter(
            x=df_bt.index, y=df_bt[f"Spread_{ex}"], name=ex,
            line=dict(color=EXCHANGE_COLORS.get(ex, ACCENT_BLUE), width=1.4),
            hovertemplate=f"{ex}" + ": %{y:,.0f} THB<extra></extra>"
        ))
    fig1.add_hline(y=0, line=dict(color=MUTED_TEXT, dash="dash"))
    fig1.update_yaxes(title_text="Spread vs XSpring (THB)")
    fig1 = style_fig(fig1, height=480)
    st.plotly_chart(fig1, use_container_width=True)

    fig2 = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                          row_heights=[0.34, 0.33, 0.33],
                          subplot_titles=("Daily Net Arbitrage Profit (THB per BTC)",
                                          "1-Year Strategy Equity Curve",
                                          "Drawdown (%)"))
    fig2.add_trace(go.Scatter(x=df_bt.index, y=df_bt["Daily_Net_Profit"], name="Daily Net Profit",
                               line=dict(color="#3fb950", width=1),
                               hovertemplate="%{x|%d %b %Y}<br>Profit: %{y:,.0f} THB<extra></extra>"), row=1, col=1)
    fig2.add_trace(go.Scatter(x=df_bt.index, y=df_bt["Portfolio_Value"], name="Portfolio Value",
                               line=dict(color=ACCENT_BLUE, width=2),
                               hovertemplate="%{x|%d %b %Y}<br>Portfolio: %{y:,.0f} THB<extra></extra>"), row=2, col=1)
    fig2.add_trace(go.Scatter(x=df_bt.index, y=df_bt["Drawdown"] * 100, name="Drawdown",
                               line=dict(color=ACCENT_RED, width=1), fill="tozeroy",
                               fillcolor="rgba(255,77,77,0.25)",
                               hovertemplate="%{x|%d %b %Y}<br>Drawdown: %{y:.2f}%<extra></extra>"), row=3, col=1)
    fig2 = style_fig(fig2, height=750)
    st.plotly_chart(fig2, use_container_width=True)

    st.markdown("### 📊 สรุป Spread เฉลี่ยรายกระดาน (เทียบ XSpring)")
    avg_spread_bt = pd.Series({ex: df_bt[f"Spread_{ex}"].mean() for ex in exchange_list_bt}).sort_values()
    fig3 = go.Figure(go.Bar(
        x=avg_spread_bt.values, y=avg_spread_bt.index, orientation="h",
        marker_color=[EXCHANGE_COLORS.get(ex, ACCENT_BLUE) for ex in avg_spread_bt.index],
        hovertemplate="%{y}<br>Avg Spread: %{x:,.0f} THB<extra></extra>"
    ))
    fig3.add_vline(x=0, line=dict(color=MUTED_TEXT))
    fig3.update_layout(title=dict(text="Average Spread vs XSpring per Exchange (THB)", font=dict(color=PRIMARY_COLOR, size=16)))
    fig3 = style_fig(fig3, height=420, hovermode="closest")
    st.plotly_chart(fig3, use_container_width=True)

    st.caption(
        "⚠️ **ข้อจำกัดที่ควรรู้ก่อนใช้จริง:** สเปรดที่เห็นเป็นราคาจริง แต่การโอนเงินบาท/คริปโตข้ามประเทศเข้า-ออกกระดานไทย "
        "มีเวลาโอน ขั้นตอน KYC/AML และเพดานวงเงินที่ระบบจริงต้องรอ ไม่สามารถปิดสถานะ 2 ขาพร้อมกันได้ทันทีเหมือนเทรดในกระดานเดียว "
        "ตัวเลขกำไรในกราฟจึงเป็น 'กำไรตามราคาที่สังเกตได้' ไม่ใช่กำไรที่รับประกันว่าทำได้จริงเสมอ"
    )

    show_data_table(df_bt, "xspring_arbitrage_real.csv")

st.markdown("---")
st.markdown(
    f"<p style='font-size:11px;color:{MUTED_TEXT};'>⚠️ Disclaimer: เครื่องมือนี้ใช้เพื่อการศึกษาและสาธิตกลยุทธ์เชิงปริมาณเท่านั้น "
    f"ไม่ถือเป็นคำแนะนำการลงทุน ราคาทุกกระดานในโมดูล 4 ดึงจาก public API จริง ยกเว้นราคา XSpring ที่ไม่มี public API สาธารณะ "
    f"จึงประมาณจากราคา Bitkub ที่ตรวจสอบแล้วว่า XSpring อ้างอิงอยู่จริง + markup ที่ปรับได้ ผลตอบแทนจาก backtest ไม่รวมข้อจำกัดการโอนเงิน/สินทรัพย์ข้ามกระดานจริง</p>",
    unsafe_allow_html=True
)
