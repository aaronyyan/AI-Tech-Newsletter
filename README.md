# 🤖 AI Tech Newsletter

Automatically aggregates AI and tech news from 40+ sources daily, filters and translates via LLM and keywords, generates Markdown, structured JSON, and Bento-style visual cards, then pushes through Resend email and Telegram.

<p align="center">
  <a href="README.zh-CN.md">中文</a> | English
</p>

------

## ✨ Features

- **Multi-source Concurrent Fetching**: Aggregates 49 quality AI/tech news sources with async RSS and X (Twitter) fetching.
- **Smart Filtering & Classification**: Built-in AI relevance filtering with positive/negative keyword scoring, auto-categorized into 9 core dashboards.
- **Multi-format Output**: Simultaneously produces Markdown archives, structured JSON, and **Bento-style** visual cards based on Apple design language.
- **Auto Fallback**: Cron-guarded with automatic degradation to essential mode on timeout or failure, ensuring uninterrupted delivery.
- **Multi-channel Push**: Integrated **Resend API** for HTML rich-text emails, with optional **Telegram Bot** real-time push.

------

## 🚀 Quick Start

### 1. Install Dependencies

```bash
git clone https://github.com/aaronyyan/AI-Tech-Newsletter.git
cd AI-Tech-Newsletter

pip install -r requirements.txt
playwright install chromium
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env`:

```ini
# Email push (required)
RESEND_API_KEY=re_xxxxxxxx
EMAIL_TO=your-email@example.com

# Telegram push (optional)
TG_BOT_TOKEN=123456:ABC-DEFxxxxxx
TG_CHAT_ID=-100xxxxxxxxx
```

### 3. Run

```bash
# Full version (all sources)
python3 daily.py

# Essential version (fast fallback)
python3 daily.py --essential

# Replay specific date
python3 daily.py --date 2026-05-17
```

------

## 🛠️ Run Mode Comparison

| **Dimension** | **Full (daily.py)** | **Essential (--essential)** |
|---|---|---|
| **Sources** | All **49** sources | Filtered (excludes some, X limited to top 10) |
| **Duration** | ~30-60 seconds | ~10-20 seconds |
| **Purpose** | Daily 09:00 standard push | **Auto fallback** when full version fails |

------

## 📅 Cron Deployment

```bash
# Add to crontab -e
0 9 * * * /bin/bash /path/to/your/project/run.sh >> /path/to/your/project/error.log 2>&1
```

> **💡 Fallback Logic**: `run.sh` runs full version first. On non-zero exit (network/source issues), it logs the error and immediately runs essential version as fallback.

------

## 📂 Project Structure

```
├── daily.py             # Main script: fetch, filter, translate, classify, send
├── render_image.py      # Card rendering: Font Awesome icons + Apple Bento grid
├── run.sh               # Scheduler: full → essential auto fallback
├── source-registry.json # Source registry: 49 channels
├── error.log            # Error log
└── .env                 # Environment variables (local, not committed)
```

### Output Format

- **Markdown**: `YYYY-MM/MM-DD/YYYY-MM-DD-daily-ai-tech-news.md`
- **JSON**: `YYYY-MM/MM-DD/YYYY-MM-DD-daily-ai-tech-news.json`
- **Bento Card**: `YYYY-MM/MM-DD/YYYY-MM-DD-daily-ai-tech-news.png`

------

## 🎨 Preview

| **Bento-style Dashboard Card** |
|---|
| [![Preview](https://i.postimg.cc/76d7bgxX/i-Shot-2026-05-22-11-38-45.png)](https://postimg.cc/5Y5jRQQF) |

------

## 📄 License

[MIT License](LICENSE)
