# 🤖 AI 科技快讯 (AI Tech Newsletter)

每日自动聚合个人关注订阅的 40+ 渠道的 AI 与科技资讯，通过大模型及关键词进行智能过滤、翻译与分类，最终生成 Markdown、结构化 JSON 以及 Bento 风格的长图，并自动通过 Resend 邮件和 Telegram 进行多渠道推送。

------

## ✨ 核心特性

- **多源并发抓取**：聚合 49 个优质 AI/科技资讯源，支持 RSS 与 X (Twitter) 账号异步并发抓取。
- **智能过滤分类**：内置 AI 相关性过滤与正负关键词打分系统，精选内容并自动归类至 9 大核心看板。
- **多格式输出**：同时产出 Markdown 归档、结构化 JSON 数据以及基于 Apple 设计语言的 **Bento 风格** 视觉长图。
- **自动降级容灾**：Cron 脚本守护，完整版运行超时或失败时，自动降级至精选版兜底，确保推送不中断。
- **多渠道推送**：集成 **Resend API** 发送 HTML 富文本邮件，并可选支持 **Telegram Bot** 实时渠道推送。

------

## 🚀 快速开始

### 1. 安装依赖

项目使用 `translators` 进行文本翻译，并依赖 `Playwright` 渲染长图。

Bash

```
# 克隆项目
git clone https://github.com/aaronyyan/AI-Tech-Newsletter.git
cd AI-Tech-Newsletter

# 安装 Python 依赖
pip install -r requirements.txt # 或 pip install translators playwright

# 安装 Playwright 浏览器核心
playwright install chromium
```

### 2. 配置环境变量

复制环境模板并配置你的密钥与收件信息：

Bash

```
cp .env.example .env
```

打开 `.env` 配置文件：

Ini, TOML

```
# 邮件推送配置（必填）
RESEND_API_KEY=re_xxxxxxxx
EMAIL_TO=your-email@example.com

# Telegram 推送配置（可选）
TG_BOT_TOKEN=123456:ABC-DEFxxxxxx
TG_CHAT_ID=-100xxxxxxxxx
```

### 3. 运行脚本

Bash

```
# 运行今日完整版（全渠道抓取）
python3 daily.py

# 运行今日精选版（快速构建兜底简报）
python3 daily.py --essential

# 补充/重现指定日期的历史快讯
python3 daily.py --date 2026-05-17
```

------

## 🛠️ 运行模式对比

| **维度**       | **完整版 (daily.py)**     | **精选版 (--essential)**                      |
| -------------- | ------------------------- | --------------------------------------------- |
| **数据源数量** | 覆盖全部 **49** 个订阅源  | 过滤精简源（排除 IT之家等，X 源限制前 10 个） |
| **运行耗时**   | 约 30 - 60 秒             | 约 10 - 20 秒                                 |
| **主要用途**   | 每日 09:00 的日常标准推送 | 完整版因网络/超时失败时的**自动降级兜底**     |

------

## 📅 定时任务部署

通过 `run.sh` 脚本包裹主程序，可在 Cron 中配置每天早上 **09:00 (CST)** 自动运行。

Plaintext

```
# 使用 crontab -e 添加以下定时任务
0 9 * * * /bin/bash /path/to/your/project/run.sh >> /path/to/your/project/error.log 2>&1
```

> **💡 容灾逻辑**：`run.sh` 优先跑完整版，若遇到网络波动或源站崩溃触发非 0 状态码，会自动追加错误到 `error.log` 并立即拉起精选版进行降级发送。

------

## 📂 项目结构与输出规范

### 目录结构

Plaintext

```
├── daily.py             # 主脚本：负责抓取、过滤、翻译、分类与邮件发送
├── render_image.py      # 长图渲染：基于 Font Awesome 图标与 Apple Bento 栅格设计
├── run.sh               # 调度外壳：实现完整版失败自动降级精选版
├── source-registry.json # 数据源注册表：维护 49 个抓取渠道
├── error.log            # 异常日志：自动追加运行时错误
└── .env                 # 环境变量（本地私密配置，不提交）
```

### 归档输出格式

脚本运行成功后，会在相应年份和日期目录下自动生成以下三种格式的文件：

- **Markdown 归档**：`YYYY-MM/MM-DD/YYYY-MM-DD-每日AI科技资讯.md`
- **结构化 JSON**：`YYYY-MM/MM-DD/YYYY-MM-DD-每日AI科技资讯.json`
- **Bento 视觉长图**：`YYYY-MM/MM-DD/YYYY-MM-DD-每日AI科技资讯.png`

------

## 🎨 视觉预览

| **Bento 风格看板长图预览**                                   |
| ------------------------------------------------------------ |
| [![i-Shot-2026-05-22-11-38-45.png](https://i.postimg.cc/76d7bgxX/i-Shot-2026-05-22-11-38-45.png)](https://postimg.cc/5Y5jRQQF) |

------

## 📄 开源协议

本项目基于 [MIT License](https://gemini.google.com/app/11be423d2a3a5b0b) 协议开源。
