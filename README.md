# 🤖 AI 產業新聞雷達系統（AI News Radar）

一套結合 **Python、OpenAI、Supabase、n8n、GitHub Actions 與 LINE Official Account** 的 AI 新聞自動化分析與推播系統。

系統每日自動取得 AI 產業相關新聞，經過資料清洗與去重後，使用 AI 進行新聞摘要、分類、情緒與重要度分析，將結果儲存至資料庫，並透過 LINE 與 Dashboard 提供每日產業資訊。

---

## 📌 專案目標

AI 相關新聞每天大量產生，若透過人工搜尋、閱讀與整理，需要花費大量時間。

本專案希望建立一套自動化流程，完成：

**新聞蒐集 → 資料清洗 → AI 分析 → 資料儲存 → Dashboard → LINE 推播**

降低人工整理新聞所需的時間，並讓使用者快速掌握每日重要 AI 產業資訊。

---

## ⚙️ 系統流程

```text
Google News RSS
       ↓
Python
       ↓
資料清洗與新聞去重
       ↓
OpenAI
       ↓
新聞摘要 / 分類 / 情緒 / 重要度分析
       ↓
Supabase
       ↓
Dashboard
       ↓
n8n
       ↓
LINE Official Account
```

GitHub Actions 負責每日定時執行新聞抓取與資料處理流程。

---

## ✨ 主要功能

### 📰 自動取得 AI 新聞

* 使用 Google News RSS 取得 AI 產業相關新聞
* 每日自動執行新聞蒐集流程

### 🧹 資料清洗與去重

* 清理新聞資料
* 避免重複新聞重複寫入資料庫
* 提升每日新聞內容品質

### 🤖 AI 新聞分析

透過 OpenAI 對新聞進行：

* 新聞摘要
* 新聞分類
* 情緒分析
* 重要度判斷
* 影響分析

### 🗄️ 資料儲存

使用 Supabase 儲存結構化新聞分析結果，提供 Dashboard 與自動化流程使用。

### 📊 Dashboard

將新聞資料進行視覺化呈現，協助使用者快速查看：

* AI 新聞內容
* 新聞分類
* 情緒分布
* 重要新聞
* 新聞趨勢

### 💬 LINE 自動推播

透過 n8n 串接 LINE Official Account，將每日 AI 新聞分析結果自動推播給使用者。

### ⏰ 自動排程

使用 GitHub Actions 定時執行 Python 程式，使新聞蒐集與分析流程可以每日自動運作。

---

## 🛠️ 使用技術

| 技術                    | 用途              |
| --------------------- | --------------- |
| Python                | 新聞取得、資料清洗、資料處理  |
| Pandas                | 結構化資料處理         |
| Google News RSS       | AI 新聞資料來源       |
| OpenAI API            | 新聞摘要與 AI 分析     |
| Supabase              | 新聞資料儲存          |
| n8n                   | 自動化工作流程         |
| GitHub Actions        | 每日自動排程          |
| LINE Official Account | 新聞推播            |
| Streamlit             | Dashboard 資料視覺化 |

---

## 📂 專案結構

```text
ai-news-radar/
│
├── .github/
│   └── workflows/
│       └── news_fetch.yml
│
├── dashboard/
│   └── Dashboard 相關程式
│
├── news_fetch.py
├── requirements.txt
└── README.md
```

---

## 🎯 專案成果

目前系統已完成自動化流程：

**每日自動取得新聞 → 清洗與去重 → AI 分析 → Supabase 儲存 → Dashboard 顯示 → LINE 自動推播**

透過 GitHub Actions 執行每日排程，使系統能持續自動取得最新新聞資料，不需要每天人工執行程式。

---


## 👨‍💻 專案定位

本專案主要練習並整合：

**Python 資料處理、API 串接、AI 應用、資料庫、自動化流程、Dashboard 與第三方服務整合。**

透過完整專案實作，建立從資料取得、分析、儲存到自動推播的完整資料處理流程。
