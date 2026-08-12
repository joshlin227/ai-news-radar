import csv
import json
import os
import sys
import time
import re
from difflib import SequenceMatcher
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote

import feedparser
from dotenv import load_dotenv
from openai import OpenAI
from supabase import Client, create_client


# 每個關鍵字抓幾篇新聞
NEWS_LIMIT_PER_KEYWORD = 3

# 需要追蹤的主題
KEYWORDS = [
    "AI",
    "半導體",
    "台積電",
    "NVIDIA",
    "OpenAI",
]


def load_services() -> tuple[OpenAI, Client, str]:
    """讀取環境變數並建立 OpenAI、Supabase 連線。"""
    load_dotenv()

    openai_api_key = os.getenv("OPENAI_API_KEY")
    openai_model = os.getenv("OPENAI_MODEL", "gpt-5-mini")
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    missing_variables = []

    if not openai_api_key:
        missing_variables.append("OPENAI_API_KEY")

    if not supabase_url:
        missing_variables.append("SUPABASE_URL")

    if not supabase_key:
        missing_variables.append("SUPABASE_KEY")

    if missing_variables:
        missing_text = "、".join(missing_variables)
        raise ValueError(f".env 缺少以下設定：{missing_text}")

    openai_client = OpenAI(api_key=openai_api_key)
    supabase_client: Client = create_client(
        supabase_url,
        supabase_key,
    )

    return openai_client, supabase_client, openai_model


def parse_published_at(value: str) -> str | None:
    """將 RSS 日期轉成 Supabase 可接受的 ISO 8601 格式。"""
    if not value:
        return None

    try:
        parsed_date = parsedate_to_datetime(value)

        if parsed_date.tzinfo is None:
            parsed_date = parsed_date.replace(tzinfo=timezone.utc)

        return parsed_date.isoformat()
    except (TypeError, ValueError, OverflowError):
        return None


def fetch_news(keyword: str, limit: int = 5) -> list[dict[str, Any]]:
    """從 Google News RSS 抓取指定關鍵字新聞。"""
    encoded_keyword = quote(keyword)

    rss_url = (
        "https://news.google.com/rss/search"
        f"?q={encoded_keyword}"
        "&hl=zh-TW"
        "&gl=TW"
        "&ceid=TW:zh-Hant"
    )

    feed = feedparser.parse(rss_url)

    if getattr(feed, "bozo", False):
        print(f"⚠️ RSS 可能解析異常：{keyword}")

    news_list: list[dict[str, Any]] = []

    for entry in feed.entries[:limit]:
        published_raw = entry.get("published", "")
        published_at = parse_published_at(published_raw)

        news_item = {
            "title": entry.get("title", "").strip(),
            "source": entry.get("source", {}).get(
                "title",
                "Google News",
            ),
            "url": entry.get("link", "").strip(),
            "published_at": published_at,
            "keyword": keyword,
        }

        if news_item["title"] and news_item["url"]:
            news_list.append(news_item)

    return news_list


def extract_json_object(text: str) -> dict[str, Any]:
    """將 AI 回覆文字轉成 JSON，並處理可能出現的 Markdown 標記。"""
    cleaned_text = text.strip()

    if cleaned_text.startswith("```json"):
        cleaned_text = cleaned_text[7:]

    if cleaned_text.startswith("```"):
        cleaned_text = cleaned_text[3:]

    if cleaned_text.endswith("```"):
        cleaned_text = cleaned_text[:-3]

    cleaned_text = cleaned_text.strip()

    try:
        result = json.loads(cleaned_text)
    except json.JSONDecodeError:
        start_index = cleaned_text.find("{")
        end_index = cleaned_text.rfind("}")

        if start_index == -1 or end_index == -1:
            raise ValueError("AI 回覆中找不到有效 JSON")

        result = json.loads(
            cleaned_text[start_index:end_index + 1]
        )

    if not isinstance(result, dict):
        raise ValueError("AI 回覆不是 JSON 物件")

    return result


def normalize_importance(value: Any) -> str:
    """統一重要程度格式。"""
    text = str(value).strip()

    mapping = {
        "1": "低",
        "2": "低",
        "3": "中",
        "4": "高",
        "5": "高",
        "低": "低",
        "中": "中",
        "高": "高",
    }

    return mapping.get(text, "中")


def normalize_sentiment(value: Any) -> str:
    """統一情緒分類格式。"""
    text = str(value).strip()

    if text in {"正面", "負面", "中性"}:
        return text

    return "中性"


def normalize_impact_level(value: Any) -> str:
    """統一影響程度格式。"""
    text = str(value).strip()

    if text in {"高", "中", "低"}:
        return text

    return "中"


def normalize_keywords(value: Any) -> str:
    """把 AI 回傳的關鍵字統一存成逗號分隔文字。"""
    if isinstance(value, list):
        cleaned_values = [
            str(item).strip()
            for item in value
            if str(item).strip()
        ]

        return ",".join(cleaned_values)

    return str(value or "").strip()


def analyze_news_with_ai(
    news_item: dict[str, Any],
    openai_client: OpenAI,
    model: str,
) -> dict[str, Any]:
    """使用 OpenAI 分析單篇新聞。"""
    title = news_item["title"]
    source = news_item["source"]
    keyword = news_item["keyword"]

    prompt = f"""
你是「AI 產業新聞雷達與趨勢分析平台」的新聞分析員。

請根據新聞標題、來源與搜尋主題，完成產業情報分析。

新聞標題：
{title}

新聞來源：
{source}

搜尋主題：
{keyword}

請只輸出一個有效 JSON，不要加入 Markdown、說明文字或程式碼區塊。

JSON 欄位必須如下：
{{
  "category": "新聞分類",
  "summary": "50到100字的繁體中文摘要",
  "sentiment": "正面、負面或中性",
  "importance": "高、中或低",
  "impact_level": "高、中或低",
  "industry_impact": "說明可能影響的產業、市場需求、供應鏈或企業動向",
  "keywords": ["關鍵字1", "關鍵字2", "關鍵字3"],
  "company": "主要相關公司，沒有則填無",
  "technology": "主要相關技術，沒有則填無"
}}

分類可優先使用：
生成式AI、AI晶片、半導體、雲端運算、AI應用、
機器人、資料中心、資安、自動駕駛、其他。

判斷原則：
1. 不要杜撰標題沒有提供的精確數字或事件細節。
2. 資訊不足時，使用保守措辭。
3. 全部使用繁體中文。
""".strip()

    response = openai_client.responses.create(
        model=model,
        input=prompt,
    )

    response_text = response.output_text

    if not response_text:
        raise ValueError("OpenAI 沒有回傳分析內容")

    ai_result = extract_json_object(response_text)

    category = str(
        ai_result.get("category", keyword)
    ).strip() or keyword

    summary = str(
        ai_result.get(
            "summary",
            f"這則新聞與「{category}」相關。",
        )
    ).strip()

    sentiment = normalize_sentiment(
        ai_result.get("sentiment")
    )

    importance = normalize_importance(
        ai_result.get("importance")
    )

    impact_level = normalize_impact_level(
        ai_result.get("impact_level")
    )

    industry_impact = str(
        ai_result.get(
            "industry_impact",
            "需持續觀察後續產業與市場變化。",
        )
    ).strip()

    keywords = normalize_keywords(
        ai_result.get("keywords")
    )

    company = str(
        ai_result.get("company", "無")
    ).strip() or "無"

    technology = str(
        ai_result.get("technology", "無")
    ).strip() or "無"

    push_message = (
        f"【{category}】\n"
        f"{title}\n\n"
        f"摘要：{summary}\n"
        f"情緒：{sentiment}\n"
        f"重要程度：{importance}\n"
        f"影響程度：{impact_level}\n"
        f"產業影響：{industry_impact}\n"
        f"來源：{source}\n"
        f"新聞連結：{news_item['url']}"
    )

    return {
        "published_at": news_item["published_at"],
        "date": (
            news_item["published_at"][:10]
            if news_item["published_at"]
            else datetime.now().date().isoformat()
        ),
        "title": title,
        "source": source,
        "url": news_item["url"],
        "category": category,
        "summary": summary,
        "sentiment": sentiment,
        "importance": importance,
        "impact_level": impact_level,
        "industry_impact": industry_impact,
        "keywords": keywords,
        "company": company,
        "technology": technology,
        "push_message": push_message,
        "fetch_status": "success",
        "ai_status": "success",
    }


def create_fallback_analysis(
    news_item: dict[str, Any],
    error: Exception,
) -> dict[str, Any]:
    """AI 分析失敗時，仍保留新聞與失敗狀態。"""
    title = news_item["title"]
    keyword = news_item["keyword"]

    summary = (
        f"這則新聞與「{keyword}」相關，"
        f"標題重點為：{title}"
    )

    push_message = (
        f"【{keyword}】\n"
        f"{title}\n\n"
        f"摘要：{summary}\n"
        f"AI 分析狀態：失敗\n"
        f"新聞連結：{news_item['url']}"
    )

    print(f"⚠️ AI 分析失敗：{title}")
    print(f"原因：{error}")

    return {
        "published_at": news_item["published_at"],
        "date": (
            news_item["published_at"][:10]
            if news_item["published_at"]
            else datetime.now().date().isoformat()
        ),
        "title": title,
        "source": news_item["source"],
        "url": news_item["url"],
        "category": keyword,
        "summary": summary,
        "sentiment": "中性",
        "importance": "中",
        "impact_level": "中",
        "industry_impact": "AI 分析失敗，需後續人工確認。",
        "keywords": keyword,
        "company": "無",
        "technology": "無",
        "push_message": push_message,
        "fetch_status": "success",
        "ai_status": "failed",
    }


def news_url_exists(
    supabase: Client,
    url: str,
) -> bool:
    """檢查同一網址是否已存在，避免重複寫入。"""
    response = (
        supabase.table("news")
        .select("id")
        .eq("url", url)
        .limit(1)
        .execute()
    )

    return bool(response.data)


def insert_news(
    supabase: Client,
    news_item: dict[str, Any],
) -> bool:
    """將新聞寫入 Supabase；重複資料會跳過。"""
    if news_url_exists(supabase, news_item["url"]):
        print(f"⏭️ 已存在，跳過：{news_item['title']}")
        return False

    response = (
        supabase.table("news")
        .insert(news_item)
        .execute()
    )

    if not response.data:
        raise RuntimeError("Supabase 沒有回傳新增資料")

    print(f"✅ 已寫入：{news_item['title']}")
    return True


def normalize_title(title: str) -> str:
    """清洗新聞標題，方便進行相似度比較。"""
    title = title.lower().strip()

    # 移除空白與常見標點符號
    title = re.sub(r"[\s｜|\-–—_：:，,。.!！?？「」『』【】\[\]()（）]", "", title)

    return title


def title_similarity(title1: str, title2: str) -> float:
    """計算兩個新聞標題的相似程度，範圍 0～1。"""
    clean_title1 = normalize_title(title1)
    clean_title2 = normalize_title(title2)

    return SequenceMatcher(
        None,
        clean_title1,
        clean_title2,
    ).ratio()


def remove_duplicate_news(
    news_items: list[dict[str, Any]],
    similarity_threshold: float = 0.75,
) -> list[dict[str, Any]]:
    """移除相同網址以及標題高度相似的新聞。"""
    seen_urls: set[str] = set()
    unique_news: list[dict[str, Any]] = []

    for item in news_items:
        url = item["url"]
        title = item["title"]

        # 第一層：網址完全相同
        if url in seen_urls:
            print(f"⏭️ URL 重複，跳過：{title}")
            continue

        # 第二層：標題相似度
        is_duplicate = False

        for existing_item in unique_news:
            similarity = title_similarity(
                title,
                existing_item["title"],
            )

            if similarity >= similarity_threshold:
                print(
                    f"⏭️ 標題相似，跳過：{title}\n"
                    f"   ↳ 已有：{existing_item['title']}\n"
                    f"   ↳ 相似度：{similarity:.0%}"
                )
                is_duplicate = True
                break

        if is_duplicate:
            continue

        seen_urls.add(url)
        unique_news.append(item)

    return unique_news


def save_json(
    news_items: list[dict[str, Any]],
) -> None:
    """輸出 JSON 備份。"""
    with open(
        "news_output.json",
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            news_items,
            file,
            ensure_ascii=False,
            indent=4,
        )


def save_csv(
    news_items: list[dict[str, Any]],
) -> None:
    """輸出 CSV 備份。"""
    fieldnames = [
        "published_at",
        "date",
        "title",
        "source",
        "url",
        "category",
        "summary",
        "sentiment",
        "importance",
        "impact_level",
        "industry_impact",
        "keywords",
        "company",
        "technology",
        "push_message",
        "fetch_status",
        "ai_status",
    ]

    with open(
        "news_output.csv",
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(news_items)


def main() -> None:
    """執行完整新聞蒐集與分析流程。"""
    openai_client, supabase, model = load_services()

    print("開始抓取新聞……")

    fetched_news: list[dict[str, Any]] = []

    for keyword in KEYWORDS:
        print(f"正在抓取：{keyword}")

        try:
            keyword_news = fetch_news(
                keyword,
                limit=NEWS_LIMIT_PER_KEYWORD,
            )

            fetched_news.extend(keyword_news)
        except Exception as error:
            print(f"❌ 抓取 {keyword} 失敗：{error}")

    unique_news = remove_duplicate_news(fetched_news)

    print(f"共取得 {len(unique_news)} 則不重複新聞。")

    analyzed_news: list[dict[str, Any]] = []
    inserted_count = 0
    skipped_count = 0

    for index, item in enumerate(unique_news, start=1):
        print()
        print(
            f"正在處理第 {index}/{len(unique_news)} 則："
            f"{item['title']}"
        )

        try:
            # 已經存在的資料不再花 OpenAI 費用分析
            if news_url_exists(supabase, item["url"]):
                print("⏭️ Supabase 已存在，跳過 AI 分析。")
                skipped_count += 1
                continue

            try:
                analyzed_item = analyze_news_with_ai(
                    item,
                    openai_client,
                    model,
                )
            except Exception as ai_error:
                analyzed_item = create_fallback_analysis(
                    item,
                    ai_error,
                )

            analyzed_news.append(analyzed_item)

            if insert_news(supabase, analyzed_item):
                inserted_count += 1

            # 避免短時間大量呼叫 API
            time.sleep(1)

        except Exception as error:
            print(f"❌ 新聞處理失敗：{error}")

    save_json(analyzed_news)
    save_csv(analyzed_news)

    print()
    print("=" * 60)
    print("新聞處理完成")
    print(f"抓取不重複新聞：{len(unique_news)}")
    print(f"成功寫入 Supabase：{inserted_count}")
    print(f"已存在而跳過：{skipped_count}")
    print(f"本次輸出備份：{len(analyzed_news)}")
    print("已產生 news_output.json 與 news_output.csv")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n使用者已中止程式。")
        sys.exit(1)
    except Exception as error:
        print(f"\n程式執行失敗：{error}")
        sys.exit(1)