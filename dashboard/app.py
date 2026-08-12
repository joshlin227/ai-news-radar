import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client


# =========================
# 基本設定
# =========================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

st.set_page_config(
    page_title="AI 產業新聞雷達",
    page_icon="🤖",
    layout="wide",
)


# =========================
# Supabase 連線
# =========================

@st.cache_resource
def get_supabase_client():
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        st.error("找不到 SUPABASE_URL 或 SUPABASE_KEY")
        st.stop()

    return create_client(supabase_url, supabase_key)


@st.cache_data(ttl=300)
def load_news():
    supabase = get_supabase_client()

    response = (
        supabase.table("news")
        .select("*")
        .order("published_at", desc=True)
        .limit(500)
        .execute()
    )

    return pd.DataFrame(response.data or [])


# =========================
# 載入與整理資料
# =========================

try:
    df = load_news()
except Exception as error:
    st.error(f"讀取 Supabase 失敗：{error}")
    st.stop()

if df.empty:
    st.warning("目前沒有新聞資料")
    st.stop()

# 排除測試資料或沒有發布時間的資料
if "published_at" in df.columns:
    df["published_at"] = pd.to_datetime(
        df["published_at"],
        errors="coerce",
        utc=True,
    )

    df = df.dropna(subset=["published_at"]).copy()

    # 轉成台灣時間
    df["published_at"] = df["published_at"].dt.tz_convert("Asia/Taipei")
    df["date"] = df["published_at"].dt.date

if df.empty:
    st.warning("排除測試資料後，目前沒有可顯示的新聞")
    st.stop()


# =========================
# 頁首
# =========================

st.title("🤖 AI 產業新聞雷達與趨勢分析平台")
st.caption("Powered by Python + Supabase + OpenAI + n8n")

# 手動重新載入 Supabase 資料
if st.button("🔄 重新整理資料"):
    st.cache_data.clear()
    st.rerun()


# =========================
# 側邊篩選器
# =========================

st.sidebar.header("🔎 新聞篩選")

sentiment_options = sorted(
    df["sentiment"].dropna().unique().tolist()
)

selected_sentiments = st.sidebar.multiselect(
    "市場情緒",
    options=sentiment_options,
    default=sentiment_options,
)

if "category" in df.columns:
    category_options = sorted(
        df["category"].dropna().unique().tolist()
    )

    selected_categories = st.sidebar.multiselect(
        "新聞分類",
        options=category_options,
        default=category_options,
    )
else:
    selected_categories = []

source_options = sorted(
    df["source"].dropna().unique().tolist()
)

selected_sources = st.sidebar.multiselect(
    "新聞來源",
    options=source_options,
    default=source_options,
)

keyword = st.sidebar.text_input(
    "標題關鍵字",
    placeholder="例如：NVIDIA、OpenAI、台積電",
)

filtered_df = df.copy()

if selected_sentiments:
    filtered_df = filtered_df[
        filtered_df["sentiment"].isin(selected_sentiments)
    ]

if "category" in filtered_df.columns and selected_categories:
    filtered_df = filtered_df[
        filtered_df["category"].isin(selected_categories)
    ]

if selected_sources:
    filtered_df = filtered_df[
        filtered_df["source"].isin(selected_sources)
    ]

if keyword:
    filtered_df = filtered_df[
        filtered_df["title"]
        .fillna("")
        .str.contains(keyword, case=False, na=False)
    ]


# =========================
# KPI 與市場摘要
# =========================

total_news = len(filtered_df)

positive_count = len(
    filtered_df[filtered_df["sentiment"] == "正面"]
)

neutral_count = len(
    filtered_df[filtered_df["sentiment"] == "中性"]
)

negative_count = len(
    filtered_df[filtered_df["sentiment"] == "負面"]
)

high_importance_count = 0

if "importance" in filtered_df.columns:
    high_importance_count = len(
        filtered_df[filtered_df["importance"] == "高"]
    )


def calculate_percent(value: int, total: int) -> int:
    """計算百分比，避免總數為 0。"""
    if total == 0:
        return 0

    return round((value / total) * 100)


positive_percent = calculate_percent(
    positive_count,
    total_news,
)

neutral_percent = calculate_percent(
    neutral_count,
    total_news,
)

negative_percent = calculate_percent(
    negative_count,
    total_news,
)


# 判斷整體市場情緒
if total_news == 0:
    market_status = "暫無資料"
    market_icon = "⚪"
elif negative_percent >= 50:
    market_status = "市場情緒偏負面"
    market_icon = "🔴"
elif positive_percent >= 50:
    market_status = "市場情緒偏正面"
    market_icon = "🟢"
else:
    market_status = "市場情緒中性震盪"
    market_icon = "🟡"


# 建立今日一句話
high_impact_count = 0

if "impact_level" in filtered_df.columns:
    high_impact_count = len(
        filtered_df[
            filtered_df["impact_level"] == "高"
        ]
    )

if total_news == 0:
    daily_summary = "目前沒有符合篩選條件的新聞。"

elif negative_percent >= 50:
    daily_summary = (
        f"今日負面新聞占 {negative_percent}%，"
        f"高影響事件共 {high_impact_count} 則，"
        "市場風險與波動值得持續觀察。"
    )

elif positive_percent >= 50:
    daily_summary = (
        f"今日正面新聞占 {positive_percent}%，"
        f"高重要性事件共 {high_importance_count} 則，"
        "產業發展氣氛相對正向。"
    )

else:
    daily_summary = (
        f"今日市場消息多空交錯，"
        f"正面占 {positive_percent}%、"
        f"負面占 {negative_percent}%，"
        "整體情緒維持中性。"
    )


# 市場摘要區
st.subheader(f"{market_icon} AI 今日市場摘要")

with st.container(border=True):
    st.markdown(f"### {market_status}")
    st.write(daily_summary)

    st.caption(
        f"目前根據篩選後的 {total_news} 則新聞自動統計"
    )


# KPI 指標卡
c1, c2, c3, c4, c5 = st.columns(
    5,
    gap="medium",
)

with c1:
    st.metric(
        label="📰 新聞數量",
        value=total_news,
        border=True,
    )

with c2:
    st.metric(
        label="😊 正面",
        value=f"{positive_percent}%",
        delta=f"{positive_count} 則",
        border=True,
    )

with c3:
    st.metric(
        label="😐 中性",
        value=f"{neutral_percent}%",
        delta=f"{neutral_count} 則",
        border=True,
    )

with c4:
    st.metric(
        label="😟 負面",
        value=f"{negative_percent}%",
        delta=f"{negative_count} 則",
        border=True,
    )

with c5:
    st.metric(
        label="🔥 高重要性",
        value=high_importance_count,
        delta=f"共 {total_news} 則",
        border=True,
    )

st.divider()


# =========================
# 圖表區
# =========================

left_chart, right_chart = st.columns(2)

with left_chart:
    st.subheader("📊 市場情緒分布")

    sentiment_data = (
        filtered_df["sentiment"]
        .fillna("未分類")
        .value_counts()
        .reset_index()
    )

    sentiment_data.columns = ["情緒", "新聞數"]

    sentiment_chart = px.pie(
        sentiment_data,
        names="情緒",
        values="新聞數",
        hole=0.55,
    )

    sentiment_chart.update_layout(
        margin=dict(l=10, r=10, t=20, b=10),
        legend_title_text="",
    )

    st.plotly_chart(
        sentiment_chart,
        width="stretch",
    )

with right_chart:
    st.subheader("🏢 新聞來源排行")

    source_data = (
        filtered_df["source"]
        .fillna("未知來源")
        .value_counts()
        .head(10)
        .sort_values()
        .reset_index()
    )

    source_data.columns = ["來源", "新聞數"]

    source_chart = px.bar(
        source_data,
        x="新聞數",
        y="來源",
        orientation="h",
    )

    source_chart.update_layout(
        margin=dict(l=10, r=10, t=20, b=10),
        yaxis_title="",
        xaxis_title="新聞數",
    )

    st.plotly_chart(
        source_chart,
        width="stretch",
    )


# =========================
# 每日新聞趨勢
# =========================

st.subheader("📈 每日新聞趨勢")

daily_data = (
    filtered_df.groupby("date")
    .size()
    .reset_index(name="新聞數")
    .sort_values("date")
)

trend_chart = px.line(
    daily_data,
    x="date",
    y="新聞數",
    markers=True,
)

trend_chart.update_layout(
    margin=dict(l=10, r=10, t=20, b=10),
    xaxis_title="日期",
    yaxis_title="新聞數",
)

st.plotly_chart(
    trend_chart,
    width="stretch",
)

st.divider()


# =========================
# 最新新聞表格
# =========================

st.subheader("📰 最新新聞")

display_columns = [
    column
    for column in [
        "title",
        "source",
        "category",
        "sentiment",
        "importance",
        "impact_level",
        "published_at",
        "url",
    ]
    if column in filtered_df.columns
]

display_df = filtered_df[display_columns].copy()

if "published_at" in display_df.columns:
    display_df["published_at"] = (
        display_df["published_at"]
        .dt.strftime("%Y-%m-%d %H:%M")
    )

display_df = display_df.rename(
    columns={
        "title": "新聞標題",
        "source": "來源",
        "category": "分類",
        "sentiment": "情緒",
        "importance": "重要程度",
        "impact_level": "影響程度",
        "published_at": "發布時間",
        "url": "新聞連結",
    }
)

st.dataframe(
    display_df,
    width="stretch",
    hide_index=True,
    column_config={
        "新聞連結": st.column_config.LinkColumn(
            "新聞連結",
            display_text="閱讀全文",
        )
    },
)

st.caption(
    f"目前顯示 {len(filtered_df)} 則，資料每 5 分鐘重新讀取一次。"
)