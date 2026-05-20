#!/usr/bin/env python3

from __future__ import annotations

import email.utils
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

import translators as ts
from render_image import render as render_image


def _load_dotenv(path: Path | None = None) -> None:
    """从 .env 文件加载环境变量（标准库实现，不依赖 python-dotenv）"""
    env_file = path or Path(__file__).resolve().parent / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("\"'")
        os.environ.setdefault(key, value)


_load_dotenv()

# Telegram 配置（从环境变量读取）
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "")

# Email 配置（Resend API）
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
EMAIL_TO = os.environ.get("EMAIL_TO", "")

CST = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parent


def output_dir(target_date: date | None = None) -> Path:
    """获取指定日期的简报目录 (yyyy-mm/dd/)"""
    d = target_date or datetime.now(CST).date()
    return ROOT / d.strftime("%Y-%m") / d.strftime("%m-%d")


def output_paths(target_date: date | None = None) -> tuple[Path, Path, Path]:
    """返回 (md_path, json_path, png_path)"""
    d = target_date or datetime.now(CST).date()
    prefix = d.isoformat()
    d = output_dir(d)
    return d / f"{prefix}-每日AI科技资讯.md", d / f"{prefix}-每日AI科技资讯.json", d / f"{prefix}-每日AI科技资讯.png"

# 直接从原始源抓取，不通过 aihot.virxact.com
FETCHABLE_SOURCE_MAP = {
    "Anthropic：Newsroom（网页）": {
        "kind": "web",
        "url": "https://www.anthropic.com/news",
        "parser": "anthropic_news",
    },
    "Claude：Blog（网页）": {
        "kind": "web",
        "url": "https://claude.com/blog",
        "parser": "claude_blog",
    },
    "Runway：News（网页）": {
        "kind": "web",
        "url": "https://runwayml.com/news/",
        "parser": "runway_news",
    },
    "The Decoder：AI News（RSS）": {
        "kind": "rss",
        "url": "https://the-decoder.com/feed/",
    },
    "IT之家（RSS）": {
        "kind": "rss",
        "url": "https://www.ithome.com/rss/",
    },
    "Interconnects": {
        "kind": "rss",
        "url": "https://www.interconnects.ai/feed",
    },
    "Cloudflare Blog": {
        "kind": "rss",
        "url": "https://blog.cloudflare.com/rss",
    },
    "Simon Willison": {
        "kind": "rss",
        "url": "https://simonwillison.net/atom/everything/",
    },
    "Apple Machine Learning Research（RSS）": {
        "kind": "rss",
        "url": "https://machinelearning.apple.com/rss.xml",
    },
    "Apple：Newsroom（RSS）": {
        "kind": "rss",
        "url": "https://www.apple.com/newsroom/rss-feed.rss",
    },
    "BAIR：Berkeley AI Research Blog": {
        "kind": "rss",
        "url": "https://bair.berkeley.edu/blog/feed.xml",
    },
    "Claude Code：GitHub Releases（RSS）": {
        "kind": "rss",
        "url": "https://github.com/anthropics/claude-code/releases.atom",
    },
    "Cursor Blog": {
        "kind": "web",
        "url": "https://cursor.com/blog",
        "parser": "cursor_blog",
    },
    "Ethan Mollick：One Useful Thing（RSS）": {
        "kind": "rss",
        "url": "https://www.oneusefulthing.org/feed",
    },
    "Gary Marcus：The Road to AI We Can Trust（RSS）": {
        "kind": "rss",
        "url": "https://garymarcus.substack.com/feed",
    },
    "GitHub Blog": {
        "kind": "rss",
        "url": "https://github.blog/feed/",
    },
    "Google Blog：AI（RSS）": {
        "kind": "rss",
        "url": "https://blog.google/technology/ai/rss/",
    },
    "Google DeepMind：Blog（RSS）": {
        "kind": "rss",
        "url": "https://deepmind.google/blog/rss.xml",
    },
    "Google Developers Blog（RSS）": {
        "kind": "rss",
        "url": "https://developers.googleblog.com/feeds/posts/default",
    },
    "Google Research：Blog（网页）": {
        "kind": "web",
        "url": "https://research.google/blog/",
        "parser": "google_research_blog",
    },
    "Hugging Face：Blog（RSS）": {
        "kind": "rss",
        "url": "https://huggingface.co/blog/feed.xml",
    },
    "LMSYS：Blog（Chatbot Arena 团队）": {
        "kind": "rss",
        "url": "https://www.lmsys.org/blog/rss.xml",
    },
    "Meta Engineering Blog（RSS）": {
        "kind": "rss",
        "url": "https://engineering.fb.com/feed/",
    },
    "Mistral AI：News（网页）": {
        "kind": "web",
        "url": "https://mistral.ai/news/",
        "parser": "mistral_news",
    },
    "Nathan Lambert：Interconnects（RSS）": {
        "kind": "rss",
        "url": "https://www.interconnects.ai/feed",
    },
    "Nature：Machine Learning 主题（RSS）": {
        "kind": "rss",
        "url": "https://www.nature.com/subjects/machine-learning.rss",
    },
    "OpenAI：Alignment 研究博客（RSS）": {
        "kind": "rss",
        "url": "https://alignment.openai.com/feed.xml",
    },
    "OpenAI：官网动态（RSS · 排除企业/客户案例）": {
        "kind": "rss",
        "url": "https://openai.com/news/rss.xml",
    },
    "OpenRouter：Announcements（RSS）": {
        "kind": "rss",
        "url": "https://openrouter.ai/announcements/rss.xml",
    },
    # X (Twitter) sources via nitter.net RSS
    "X：Anthropic (@AnthropicAI)": {"kind": "rss", "url": "https://nitter.net/AnthropicAI/rss"},
    "X：OpenAI (@OpenAI)": {"kind": "rss", "url": "https://nitter.net/OpenAI/rss"},
    "X：Claude Devs (@ClaudeDevs)": {"kind": "rss", "url": "https://nitter.net/ClaudeDevs/rss"},
    "X：Sam Altman (@sama)": {"kind": "rss", "url": "https://nitter.net/sama/rss"},
    "X：Andrej Karpathy (@karpathy)": {"kind": "rss", "url": "https://nitter.net/karpathy/rss"},
    "X：Jim Fan (@DrJimFan)": {"kind": "rss", "url": "https://nitter.net/DrJimFan/rss"},
    "X：Demis Hassabis (@demishassabis)": {"kind": "rss", "url": "https://nitter.net/demishassabis/rss"},
    "X：Google DeepMind (@GoogleDeepMind)": {"kind": "rss", "url": "https://nitter.net/GoogleDeepMind/rss"},
    "X：DeepSeek (@deepseek_ai)": {"kind": "rss", "url": "https://nitter.net/deepseek_ai/rss"},
    "X：Testing Catalog (@testingcatalog)": {"kind": "rss", "url": "https://nitter.net/testingcatalog/rss"},
    "X：歸藏 (@op7418)": {"kind": "rss", "url": "https://nitter.net/op7418/rss"},
    "X：宝玉 (@dotey)": {"kind": "rss", "url": "https://nitter.net/dotey/rss"},
    "X：Berry Xia (@berryxia)": {"kind": "rss", "url": "https://nitter.net/berryxia/rss"},
    "X：邵猛 (@shao__meng)": {"kind": "rss", "url": "https://nitter.net/shao__meng/rss"},
    "X：阿易 AI Notes (@AYi_AInotes)": {"kind": "rss", "url": "https://nitter.net/AYi_AInotes/rss"},
    "X：Rohan Paul (@rohanpaul_ai)": {"kind": "rss", "url": "https://nitter.net/rohanpaul_ai/rss"},
    "X：Ethan Mollick (@emollick)": {"kind": "rss", "url": "https://nitter.net/emollick/rss"},
    "X：OpenAI Developers (@OpenAIDevs)": {"kind": "rss", "url": "https://nitter.net/OpenAIDevs/rss"},
    "X：OpenRouter (@OpenRouter)": {"kind": "rss", "url": "https://nitter.net/OpenRouter/rss"},
    "X：小北 (@frxiaobei)": {"kind": "rss", "url": "https://nitter.net/frxiaobei/rss"},
    "X：servasyy_ai (@servasyy_ai)": {"kind": "rss", "url": "https://nitter.net/servasyy_ai/rss"},
    "X：dingyi (@dingyi)": {"kind": "rss", "url": "https://nitter.net/dingyi/rss"},
}


def _load_x_following_usernames() -> list[str]:
    """从本地文件加载 X 关注列表用户名

    支持两种格式：
    1. x-following.json: ["username1", "username2", ...]
    2. X 数据导出的 following.js: window.YTD.following.part0 = [...]
    """
    base = Path(__file__).resolve().parent

    # 优先读取简单 JSON 格式
    json_path = base / "x-following.json"
    if json_path.is_file():
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [u.strip().lstrip("@") for u in data if isinstance(u, str) and u.strip()]
        except Exception as exc:
            print(f"[WARN] 读取 {json_path}: {exc}", file=sys.stderr)

    # 回退到 X 数据导出格式
    js_path = base / "following.js"
    if js_path.is_file():
        try:
            raw = js_path.read_text(encoding="utf-8")
            # following.js 格式: window.YTD.following.part0 = [{...}, ...]
            match = re.search(r"=\s*(\[.*)", raw, re.DOTALL)
            if match:
                items = json.loads(match.group(1))
                usernames = []
                for item in items:
                    link = item.get("following", {}).get("userLink", "")
                    if link:
                        username = link.rstrip("/").rsplit("/", 1)[-1]
                        if username:
                            usernames.append(username)
                return usernames
        except Exception as exc:
            print(f"[WARN] 读取 {js_path}: {exc}", file=sys.stderr)

    return []


def _build_x_following_sources() -> dict[str, dict]:
    """将关注列表用户名转为 nitter RSS 源条目"""
    usernames = _load_x_following_usernames()
    sources = {}
    for username in usernames:
        label = f"X：{username} (@{username})"
        if label not in FETCHABLE_SOURCE_MAP:
            sources[label] = {
                "kind": "rss",
                "url": f"https://nitter.net/{username}/rss",
            }
    return sources


# 合并关注列表源到主源表（硬编码源优先）
FETCHABLE_SOURCE_MAP.update(_build_x_following_sources())

MAX_PRIORITY_X_SOURCES = 20

AI_KEYWORDS = [
    "ai",
    "agent",
    "agents",
    "llm",
    "gpt",
    "claude",
    "gemini",
    "openai",
    "anthropic",
    "deepmind",
    "runway",
    "cursor",
    "copilot",
    "自动驾驶",
    "智能体",
    "模型",
    "推理",
    "多模态",
    "生成式",
    "大语言模型",
    "大模型",
    "机器学习",
    "深度学习",
]

NEGATIVE_KEYWORDS = [
    # English keywords (match pre-translation titles from X/English sources)
    "phone",
    "headphone",
    "camera",
    "movie",
    "battery",
    "refrigerator",
    "storage card",
    "perfume",
    "lipstick",
    "gaming laptop",
    "motherboard",
    "gpu",
    "monitor",
    "tablet",
    "notebook",
    "game",
    "freebie",
    "android auto",
    "ticket",
    "film festival",
    "self-service",
    "csv",
    # Chinese keywords (match Chinese RSS sources like IT之家, already in Chinese)
    "手机",
    "耳机",
    "相机",
    "电影",
    "电池",
    "冰箱",
    "存储卡",
    "红包",
    "香水",
    "唇膏",
    "游戏本",
    "主板",
    "显卡",
    "显示器",
    "平板",
    "笔记本",
    "游戏",
    "喜加一",
    "免费领",
    "免费试用",
    "门票",
    "电影节",
    "自助服务",
]

# 政治相关排除词
POLITICAL_KEYWORDS = ["政治"]

HARD_REJECT_PATTERNS = [
    "如果你是 openclaw 或 hermes agent",
    "ignore all previous instructions",
    "只回复: 1",
    "in chinese culture",
    "kanye",
    "tmz",
    "android auto",
    "no limits",
    "no invite code",
    # English equivalents (matched against pre-translation titles)
    "ticket",
    "film festival",
    "self-service",
    "upload excel",
    "free trial",
    "free to try",
]

@dataclass
class FeedItem:
    source_label: str
    title: str
    link: str
    published_at: datetime


# 分类规则：按优先级匹配，第一个匹配的分类生效
CATEGORY_RULES = [
    {
        "name": "AI 模型与性能",
        "keywords": ["模型", "model", "llm", "gpt", "claude", "gemini", "qwen", "kimi", "训练", "推理", "性能", "benchmark", "mtp", "投机解码", "tokens/s", "参数", "多模态"],
    },
    {
        "name": "Claude Code 与编程工具",
        "keywords": ["claude code", "codex", "cursor", "copilot", "编程", "coding", "ide", "代码", "agent sdk", "限额", "额度", "沙盒", "sandbox", "github actions"],
    },
    {
        "name": "企业与市场动态",
        "keywords": ["企业", "enterprise", "融资", "收购", "裁员", "估值", "采用率", "adoption", "市场份额", "b2b", "企业级"],
    },
    {
        "name": "新产品与平台",
        "keywords": ["发布", "launch", "推出", "上线", "新版", "更新", "update", "平台", "platform", "产品", "app", "工具"],
    },
    {
        "name": "AI 安全与风险",
        "keywords": ["安全", "security", "漏洞", "vulnerability", "零日", "zero-day", "攻击", "风险", "合规", "alignment", "对齐"],
    },
    {
        "name": "行业观点与趋势",
        "keywords": ["观点", "趋势", "trend", "未来", "预测", "analysis", "分析", "行业", "访谈", "interview"],
    },
    {
        "name": "自动驾驶与机器人",
        "keywords": ["自动驾驶", "autonomous", "机器人", "robot", "机器狗", "无人机", "drone", "vla", "世界模型"],
    },
    {
        "name": "芯片与硬件",
        "keywords": ["芯片", "chip", "gpu", "nvidia", "amd", "intel", "cerbras", "硬件", "hardware", "显卡", "算力"],
    },
    {
        "name": "其他科技动态",
        "keywords": [],  # 默认分类
    },
]


def classify_item(item: FeedItem) -> str:
    """根据标题和来源对消息进行分类"""
    text = f"{item.source_label} {item.title}".lower()
    for rule in CATEGORY_RULES:
        if not rule["keywords"]:  # 默认分类
            return rule["name"]
        for keyword in rule["keywords"]:
            if keyword.lower() in text:
                return rule["name"]
    return "其他科技动态"


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def normalize_link(link: str) -> str:
    link = clean_text(link)
    if not link:
        return ""
    link = link.replace("nitter.net/", "x.com/")
    parsed = urllib.parse.urlsplit(link)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query = [(k, v) for k, v in query if not k.lower().startswith("utm_")]
    return urllib.parse.urlunsplit(parsed._replace(query=urllib.parse.urlencode(query), fragment=""))


def infer_source_kind(source_label: str) -> str:
    if source_label.startswith("X："):
        return "x"
    if "（RSS）" in source_label or "RSS" in source_label:
        return "rss"
    if "GitHub" in source_label and "Releases" in source_label:
        return "rss"
    if "网页" in source_label or "Blog" in source_label or "Newsroom" in source_label or "Changelog" in source_label:
        return "web"
    return "unknown"


def fetch_text(url: str, max_retries: int = 3) -> str:
    """抓取网页内容，支持重试"""
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except Exception as e:
            if attempt < max_retries - 1:
                import time
                time.sleep(2 ** attempt)  # 指数退避：1s, 2s, 4s
                continue
            # 最后一次尝试用 curl
            try:
                out = subprocess.run(
                    [
                        "curl",
                        "--http1.1",
                        "-L",
                        "-A",
                        "Mozilla/5.0",
                        "-H",
                        "Cache-Control: no-cache",
                        "-H",
                        "Pragma: no-cache",
                        url,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
                if out.returncode == 0 and out.stdout.strip():
                    return out.stdout
            except Exception:
                pass
            raise RuntimeError(f"failed to fetch {url} after {max_retries} attempts")


def parse_dt(value: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = email.utils.parsedate_to_datetime(value)
        return dt.astimezone(CST)
    except Exception:
        pass
    for fmt in [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%B %d, %Y",
    ]:
        try:
            dt = datetime.strptime(value, fmt)
            return dt.replace(tzinfo=CST) if dt.tzinfo is None else dt.astimezone(CST)
        except Exception:
            continue
    return None


def parse_rss_items(xml_text: str, source_label: str) -> list[FeedItem]:
    root = ET.fromstring(xml_text)
    items: list[FeedItem] = []
    for node in root.findall(".//item"):
        title = clean_text(node.findtext("title") or "")
        link = normalize_link(clean_text(node.findtext("link") or ""))
        pub = parse_dt(clean_text(node.findtext("pubDate") or ""))
        if title and link and pub:
            items.append(FeedItem(source_label, title, link, pub))
    for node in root.findall(".//{http://www.w3.org/2005/Atom}entry"):
        title = clean_text(node.findtext("{http://www.w3.org/2005/Atom}title") or "")
        link = ""
        for link_node in node.findall("{http://www.w3.org/2005/Atom}link"):
            href = link_node.attrib.get("href", "")
            if href:
                link = normalize_link(href)
                break
        pub = parse_dt(
            clean_text(
                node.findtext("{http://www.w3.org/2005/Atom}updated")
                or node.findtext("{http://www.w3.org/2005/Atom}published")
                or ""
            )
        )
        if title and link and pub:
            items.append(FeedItem(source_label, title, link, pub))
    return items


# ============================================================
# 通用 HTML 解析引擎（基于 HTMLParser 构建 DOM 树 + CSS 选择器）
# ============================================================

class _DOMNode:
    """轻量 DOM 节点"""
    __slots__ = ("tag", "attrs", "children", "parent", "text_parts")

    def __init__(self, tag: str, attrs: dict[str, str], parent: "_DOMNode | None"):
        self.tag = tag
        self.attrs = attrs
        self.children: list[_DOMNode] = []
        self.parent = parent
        self.text_parts: list[str] = []

    @property
    def text(self) -> str:
        return clean_text(" ".join(self.text_parts))

    @property
    def inner_text(self) -> str:
        """递归获取所有后代文本"""
        parts: list[str] = []
        self._collect_text(parts)
        return clean_text(" ".join(parts))

    def _collect_text(self, parts: list[str]) -> None:
        if self.text_parts:
            parts.extend(self.text_parts)
        for child in self.children:
            child._collect_text(parts)

    def get(self, attr: str) -> str:
        return self.attrs.get(attr, "")

    def _match_simple(self, selector: str) -> bool:
        """匹配 tag / tag.class / tag#id / tag[attr] / tag[attr=value] / tag[attr*=value]"""
        sel = selector.strip()
        # tag[attr*="value"]  (contains)
        m = re.match(r'^(\w+)\[(\w+)\*="([^"]+)"\]$', sel)
        if m:
            return self.tag == m.group(1) and m.group(3) in self.attrs.get(m.group(2), "")
        # tag[attr="value"]  (exact)
        m = re.match(r'^(\w+)\[(\w+)="([^"]+)"\]$', sel)
        if m:
            return self.tag == m.group(1) and self.attrs.get(m.group(2)) == m.group(3)
        # tag[attr]
        m = re.match(r'^(\w+)\[(\w+)\]$', sel)
        if m:
            return self.tag == m.group(1) and m.group(2) in self.attrs
        # tag#id
        m = re.match(r'^(\w+)#(\w+)$', sel)
        if m:
            return self.tag == m.group(1) and self.attrs.get("id") == m.group(2)
        # tag.class
        m = re.match(r'^(\w+)\.([\w-]+)$', sel)
        if m:
            classes = self.attrs.get("class", "").split()
            return self.tag == m.group(1) and m.group(2) in classes
        # tag only
        return self.tag == sel

    def query(self, selector: str) -> "_DOMNode | None":
        """CSS 选择器查询，返回第一个匹配的后代节点"""
        parts = [s.strip() for s in selector.split() if s.strip()]
        if not parts:
            return None
        return self._query_recursive(parts, 0)

    def query_all(self, selector: str) -> "list[_DOMNode]":
        """CSS 选择器查询，返回所有匹配的后代节点"""
        parts = [s.strip() for s in selector.split() if s.strip()]
        if not parts:
            return []
        results: list[_DOMNode] = []
        self._query_all_recursive(parts, 0, results)
        return results

    def _query_recursive(self, parts: list[str], idx: int) -> "_DOMNode | None":
        if idx >= len(parts):
            return self
        # 搜索所有后代（CSS 后代选择器语义）
        return self._desc_query(parts, idx)

    def _desc_query(self, parts: list[str], idx: int) -> "_DOMNode | None":
        for child in self.children:
            if child._match_simple(parts[idx]):
                result = child._query_recursive(parts, idx + 1)
                if result is not None:
                    return result
            result = child._desc_query(parts, idx)
            if result is not None:
                return result
        return None

    def _query_all_recursive(self, parts: list[str], idx: int, results: list["_DOMNode"]) -> None:
        if idx >= len(parts):
            results.append(self)
            return
        for child in self.children:
            if child._match_simple(parts[idx]):
                child._query_all_recursive(parts, idx + 1, results)
            child._query_all_recursive(parts, idx, results)



class _DOMBuilder(HTMLParser):
    """HTMLParser → DOM 树"""

    def __init__(self):
        super().__init__()
        self.root = _DOMNode("root", {}, None)
        self._current = self.root

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        attr_dict = {k: (v or "") for k, v in attrs}
        node = _DOMNode(tag, attr_dict, self._current)
        self._current.children.append(node)
        # 自闭合标签不入栈
        if tag not in ("br", "hr", "img", "input", "meta", "link"):
            self._current = node

    def handle_endtag(self, tag: str):
        if self._current.parent and self._current.tag == tag:
            self._current = self._current.parent

    def handle_data(self, data: str):
        self._current.text_parts.append(data)


@dataclass
class _FeedSelectorConfig:
    """HTML 解析选择器配置"""
    container: str  # 文章卡片选择器
    link: str       # 链接选择器（相对于 container）
    title: str      # 标题选择器（相对于 container）
    date: str       # 日期选择器（相对于 container）
    link_pattern: str = r""  # 链接 URL 正则过滤


def _extract_date_text(node: _DOMNode) -> str:
    """从节点提取日期文本：优先 datetime 属性，其次文本内容"""
    dt_attr = node.get("datetime") or node.get("dateTime")
    if dt_attr:
        return clean_text(dt_attr)
    return node.inner_text


def _find_link_href(card: _DOMNode, link_selector: str) -> str:
    """提取链接 href：优先子节点匹配，其次 container 自身（如 <a> 作为 container）"""
    link_el = card.query(link_selector)
    if link_el:
        href = link_el.get("href")
        if href:
            return href
    # container 自身就是链接元素
    return card.get("href") if card.tag == "a" else ""


def parse_html_feed(html: str, source_label: str, parser_name: str, url: str) -> list[FeedItem]:
    builder = _DOMBuilder()
    builder.feed(html)

    if parser_name == "anthropic_news":
        return _parse_anthropic(builder.root, source_label, url)
    if parser_name == "runway_news":
        return _parse_runway_json(html, source_label, url)

    config = _SELECTOR_CONFIGS.get(parser_name)
    if not config:
        print(f"[WARN] unknown parser: {parser_name}", file=sys.stderr)
        return []

    link_re = re.compile(config.link_pattern) if config.link_pattern else None
    items: list[FeedItem] = []

    for card in builder.root.query_all(config.container):
        href = _find_link_href(card, config.link)
        if not href:
            continue

        title_el = card.query(config.title)
        if not title_el:
            continue
        title = title_el.inner_text
        if not title:
            continue

        date_el = card.query(config.date)
        if not date_el:
            continue
        pub = parse_dt(_extract_date_text(date_el))
        if not pub:
            continue

        full_link = normalize_link(urllib.parse.urljoin(url, href))
        if link_re and not link_re.search(full_link):
            continue

        if title and full_link:
            items.append(FeedItem(source_label, title, full_link, pub))

    return items


def _parse_anthropic(root: _DOMNode, source_label: str, url: str) -> list[FeedItem]:
    """Anthropic Newsroom 专用解析：遍历 <li>，跳过 customers 分类"""
    items: list[FeedItem] = []
    for li in root.query_all("li"):
        link_el = li.query("a[href]")
        if not link_el:
            continue
        href = link_el.get("href")
        if not href or "/news/" not in href:
            continue

        time_el = li.query("time")
        if not time_el:
            continue
        pub = parse_dt(_extract_date_text(time_el))
        if not pub:
            continue

        # 收集 <a> 内所有 span，按文档顺序
        spans = link_el.query_all("span")
        if len(spans) < 2:
            continue
        # 第一个 span 是分类，第二个是标题
        if spans[0].inner_text.lower() == "customers":
            continue
        title = spans[1].inner_text
        if not title:
            continue

        full_link = normalize_link(urllib.parse.urljoin(url, href))
        if title and full_link:
            items.append(FeedItem(source_label, title, full_link, pub))

    return items


def _parse_runway_json(html: str, source_label: str, url: str) -> list[FeedItem]:
    """Runway 页面内嵌 JSON 数据，用正则提取 JSON 后解析"""
    items: list[FeedItem] = []
    for match in re.finditer(r'\{"title":"([^"]+)","date":"([^"]+)".*?"href":"(/[^"]+)"', html):
        title = clean_text(match.group(1))
        link = normalize_link(urllib.parse.urljoin(url, clean_text(match.group(3))))
        pub = parse_dt(clean_text(match.group(2)))
        if title and link and pub:
            items.append(FeedItem(source_label, title, link, pub))
    return items


# 各源选择器配置
_SELECTOR_CONFIGS: dict[str, _FeedSelectorConfig] = {
    "claude_blog": _FeedSelectorConfig(
        container='div[role="listitem"]',
        link="a[href]",
        title="h2",
        date="div",
        link_pattern=r"/blog/",
    ),
    "cursor_blog": _FeedSelectorConfig(
        container='a[class*="blog-directory__row"]',
        link="a",
        title="p",
        date="time",
        link_pattern=r"/blog/",
    ),
    "google_research_blog": _FeedSelectorConfig(
        container='a[href*="/blog/"]',
        link="a",
        title="div",
        date="time",
        link_pattern=r"/blog/",
    ),
    "mistral_news": _FeedSelectorConfig(
        container='a[href*="/news/"]',
        link="a",
        title="div",
        date="time",
        link_pattern=r"/news/",
    ),
}


def select_priority_x_sources(registry: dict[str, dict]) -> list[str]:
    """从 registry 中选择优先的 X 来源"""
    scored: list[tuple[int, str]] = []
    for source_label, meta in registry.items():
        if meta.get("source_kind") != "x":
            continue
        score = 0
        pages = set(meta.get("evidence_pages", []))
        if "daily-latest" in pages:
            score += 5
        score += len(pages)
        score += len(meta.get("sample_links", []))
        if meta.get("origin_type") == "官方·X":
            score += 3
        elif meta.get("origin_type") == "X·KOL":
            score += 1
        if extract_x_handle(source_label):
            scored.append((score, source_label))
    scored.sort(reverse=True)
    return [source_label for _, source_label in scored[:MAX_PRIORITY_X_SOURCES]]


def extract_x_handle(source_label: str) -> str:
    match = re.search(r'@([A-Za-z0-9_]+)\)', source_label)
    return match.group(1) if match else ""


def is_ai_relevant(item: FeedItem) -> bool:
    hay = f"{item.source_label} {item.title}".lower()
    if item.title.startswith("RT by @") or item.title.startswith("R to @"):
        return False
    # 标题太短，无实际内容
    if len(item.title.strip()) < 15:
        return False
    if item.link.endswith("#m"):
        item.link = item.link[:-2]
    for pattern in HARD_REJECT_PATTERNS:
        if pattern in hay:
            return False
    if len(item.title) > 500:
        return False

    # 排除政治相关内容
    for word in POLITICAL_KEYWORDS:
        if word.lower() in hay:
            return False

    score = 0
    matched_keywords = 0
    for word in AI_KEYWORDS:
        if word.lower() in hay:
            score += 2
            matched_keywords += 1
    for word in NEGATIVE_KEYWORDS:
        if word.lower() in hay:
            score -= 5
    if item.source_label == "IT之家（RSS）":
        return score >= 2 and matched_keywords >= 2
    if item.source_label == "The Decoder：AI News（RSS）":
        return True
    if item.source_label.startswith("X："):
        # X 来源需要匹配 2 个以上 AI 关键词，且不能被负面关键词抵消
        return matched_keywords >= 2 and score > 0
    return score > 0 and matched_keywords >= 2


def _fetch_source(source_label: str, spec: dict, target_date: date,
                   min_x_date: date) -> list[FeedItem]:
    """抓取单个源（供线程池调用）"""
    items: list[FeedItem] = []
    try:
        body = fetch_text(spec["url"])
        parsed = (
            parse_rss_items(body, source_label)
            if spec["kind"] == "rss"
            else parse_html_feed(body, source_label, spec["parser"], spec["url"])
        )
    except Exception as exc:
        _log_error(target_date, source_label, "fetch_error", str(exc))
        print(f"[WARN] fetch {source_label}: {exc}", file=sys.stderr)
        return items
    for item in parsed:
        item_date = item.published_at.date()
        if item_date < min_x_date or item_date > target_date:
            continue
        if is_ai_relevant(item):
            items.append(item)
    return items


_ERROR_LOG_PATH = ROOT / "error.log"


def _log_error(target_date: date, source_label: str, error_type: str, detail: str) -> None:
    """记录抓取错误到 error.log"""
    ts = datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{error_type}] [{target_date}] {source_label}: {detail}\n"
    try:
        with open(_ERROR_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass


def collect_today_items(target_date: date | None = None, max_workers: int = 10) -> list[FeedItem]:
    """从原始源并发抓取指定日期的 AI 相关内容

    X 来源如果今天没有内容，会自动往前找最多 3 天。
    """
    if target_date is None:
        target_date = datetime.now(CST).date()
    min_x_date = target_date - timedelta(days=3)

    all_items: list[FeedItem] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_fetch_source, label, spec, target_date, min_x_date): label
            for label, spec in FETCHABLE_SOURCE_MAP.items()
        }
        for future in as_completed(futures):
            label = futures[future]
            try:
                result = future.result()
                if not result:
                    _log_error(target_date, label, "zero_items", "no items matched date/AI filter")
                all_items.extend(result)
            except Exception as exc:
                print(f"[WARN] fetch {label}: {exc}", file=sys.stderr)

    all_items.sort(key=lambda item: (item.published_at, item.source_label), reverse=True)
    deduped: list[FeedItem] = []
    seen_links: set[str] = set()
    for item in all_items:
        if item.link in seen_links:
            continue
        seen_links.add(item.link)
        deduped.append(item)
    return deduped


# 精选源：保留 X/Twitter（最重要的 AI 资讯来源）+ 官方博客，跳过 IT之家（噪音多）
ESSENTIAL_SOURCES: dict[str, dict] = {
    k: v for k, v in FETCHABLE_SOURCE_MAP.items()
    if k != "IT之家（RSS）"
}

MAX_ESSENTIAL_X = 10  # 精选模式下限制 X 源数量


def collect_essential_items(target_date: date | None = None) -> list[FeedItem]:
    """精选版：保留 X/Twitter（限数量）+ 官方博客，跳过 IT之家，保证快速完成"""
    if target_date is None:
        target_date = datetime.now(CST).date()
    min_x_date = target_date - timedelta(days=3)
    items: list[FeedItem] = []

    # 限制 X 源数量
    x_count = 0
    filtered_sources: dict[str, dict] = {}
    for label, spec in ESSENTIAL_SOURCES.items():
        if label.startswith("X："):
            x_count += 1
            if x_count > MAX_ESSENTIAL_X:
                continue
        filtered_sources[label] = spec

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {
            pool.submit(_fetch_source, label, spec, target_date, min_x_date): label
            for label, spec in filtered_sources.items()
        }
        for future in as_completed(futures):
            try:
                result = future.result()
                if not result:
                    label = futures[future]
                    _log_error(target_date, label, "zero_items", "no items matched date/AI filter")
                items.extend(result)
            except Exception as exc:
                print(f"[WARN] fetch essential: {exc}", file=sys.stderr)

    items.sort(key=lambda item: (item.published_at, item.source_label), reverse=True)
    deduped: list[FeedItem] = []
    seen_links: set[str] = set()
    for item in items:
        if item.link in seen_links:
            continue
        seen_links.add(item.link)
        deduped.append(item)
    return deduped


def needs_translation(text: str) -> bool:
    letters = re.findall(r"[A-Za-z]", text)
    cjk = re.findall(r"[一-鿿]", text)
    return len(letters) >= 12 and len(letters) > len(cjk)


def translate_text(text: str) -> str:
    try:
        result = ts.translate_text(text, translator='google', to_language='zh')
        return result
    except Exception as e:
        print(f"[WARN] translate failed: {e}", file=sys.stderr)
        return text


def translate_today_items(items: list[FeedItem]) -> None:
    for item in items:
        if needs_translation(item.title):
            try:
                item.title = translate_text(item.title)
            except Exception as exc:
                print(f"[WARN] translate {item.link}: {exc}", file=sys.stderr)


def write_today_outputs(items: list[FeedItem]) -> None:
    md_path, json_path, png_path = output_paths()
    output_dir().mkdir(parents=True, exist_ok=True)

    payload = [
        {
            "source_label": item.source_label,
            "title": item.title,
            "link": item.link,
            "published_at": item.published_at.isoformat(),
        }
        for item in items
    ]
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    md_path.write_text(render_today_markdown(items))


def write_date_outputs(items: list[FeedItem], target_date: date) -> None:
    """生成指定日期的资讯文件"""
    output_dir(target_date).mkdir(parents=True, exist_ok=True)
    md_path, json_path, _ = output_paths(target_date)
    date_str = target_date.isoformat()

    payload = [
        {
            "source_label": item.source_label,
            "title": item.title,
            "link": item.link,
            "published_at": item.published_at.isoformat(),
        }
        for item in items
    ]
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")

    # 渲染指定日期的 markdown
    today = datetime.now(CST).date()
    if target_date == today:
        title = f"# 今日AI科技资讯 {date_str}"
    else:
        title = f"# {date_str} 消息汇总"
    lines = [title, ""]
    q = get_daily_quote()
    if q:
        quote_en, quote_cn, quote_author = q
        if quote_cn:
            lines.append(f"> 💬 {quote_cn}")
        lines.append(f"> *{quote_en}* —— {quote_author}")
        lines.append("")

    # 按分类分组
    categorized: dict[str, list[FeedItem]] = {}
    for item in items:
        category = classify_item(item)
        if category not in categorized:
            categorized[category] = []
        categorized[category].append(item)

    # 按分类顺序输出
    for rule in CATEGORY_RULES: 
        category_name = rule["name"]
        if category_name not in categorized:
            continue
        category_items = categorized[category_name]
        lines.append(f"## {category_name}")
        lines.append("")
        for item in category_items:
            lines.append(f"**{item.title}**")
            lines.append(f"[{item.source_label}] {item.link}")
            lines.append(f"{item.published_at.strftime('%Y-%m-%d %H:%M')}")
            lines.append("")

    md_path.write_text("\n".join(lines).strip() + "\n")
    print(f"Generated {md_path}")


def google_translate(text: str, sl: str = "en", tl: str = "zh-CN") -> str:
    """用 Google Translate 免费接口翻译文本"""
    encoded = urllib.parse.quote(text)
    url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={sl}&tl={tl}&dt=t&q={encoded}"
    try:
        body = fetch_text(url, max_retries=1)
        data = json.loads(body)
        # 返回格式: [[["翻译结果","原文",null,null,10]],null,"en",...]
        if data and isinstance(data, list) and data[0]:
            return "".join(seg[0] for seg in data[0] if seg and seg[0])
    except Exception:
        pass
    return ""


def get_daily_quote() -> tuple[str, str, str] | None:
    """从 zenquotes.io API 获取随机名言，Google 翻译为中文。返回 (英文, 中文, 作者)；获取不到返回 None"""
    try:
        body = fetch_text("https://zenquotes.io/api/random", max_retries=1)
        data = json.loads(body)
        if data and isinstance(data, list) and "q" in data[0]:
            en = data[0]["q"]
            author = data[0].get("a", "Unknown")
            cn = google_translate(en)
            return (en, cn, author) if cn else (en, "", author)
    except Exception:
        pass
    return None


def render_today_markdown(items: list[FeedItem]) -> str:
    today = datetime.now(CST).date().isoformat()
    quote_en, quote_cn, quote_author = get_daily_quote()

    q = get_daily_quote()
    lines = [f"# 今日AI科技资讯 {today}", ""]
    if q:
        quote_en, quote_cn, quote_author = q
        if quote_cn:
            lines.append(f"> 💬 {quote_cn}")
        lines.append(f"> *{quote_en}* —— {quote_author}")
        lines.append("")

    # 按分类分组
    categorized: dict[str, list[FeedItem]] = {}
    for item in items:
        category = classify_item(item)
        if category not in categorized:
            categorized[category] = []
        categorized[category].append(item)

    # 按分类顺序输出
    for rule in CATEGORY_RULES:
        category_name = rule["name"]
        if category_name not in categorized:
            continue
        category_items = categorized[category_name]
        lines.append(f"## {category_name}")
        lines.append("")
        for item in category_items:
            lines.append(f"**{item.title}**")
            lines.append(f"[{item.source_label}] {item.link}")
            lines.append(f"{item.published_at.strftime('%Y-%m-%d %H:%M')}")
            lines.append("")

    return "\n".join(lines).strip() + "\n"


def send_image_to_telegram():
    """发送今日简报长图到 Telegram"""
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("[WARN] TG_BOT_TOKEN or TG_CHAT_ID not set, skipping Telegram send", file=sys.stderr)
        return
    _, _, png_path = output_paths()
    img_path = str(png_path)
    today = datetime.now(CST).date().isoformat()
    caption = f"今日AI科技资讯 {today}"

    result = subprocess.run(
        [
            "curl", "-s", "-X", "POST",
            f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendDocument",
            "-F", f"chat_id={TG_CHAT_ID}",
            "-F", f"caption={caption}",
            "-F", f"document=@{img_path}",
        ],
        capture_output=True, text=True, timeout=30,
    )
    try:
        data = json.loads(result.stdout)
        if data.get("ok"):
            print("[INFO] image sent to Telegram OK")
        else:
            print(f"[WARN] telegram send failed: {data}", file=sys.stderr)
    except Exception as e:
        print(f"[WARN] telegram send error: {e}", file=sys.stderr)


def send_email(items: list[FeedItem], essential: bool = False, target_date: date | None = None) -> None:
    """发送简报 HTML 邮件（通过 Resend API + curl）"""
    if not RESEND_API_KEY or not EMAIL_TO:
        print("[WARN] RESEND_API_KEY or EMAIL_TO not set, skipping email send", file=sys.stderr)
        return

    from render_image import build_email_html, parse_markdown

    now = datetime.now(CST)
    d = target_date or now.date()
    date_str = d.isoformat()
    prefix = "【精选版】" if essential else ""
    # 零宽字符 (U+200B) 追加到主题末尾，让 Gmail 视为不同邮件，肉眼不可见
    import random
    zwsp = "​"
    hidden = zwsp * random.randint(1, 8)
    subject = f"{prefix}AI科技资讯 {date_str}{hidden}"

    md_path, _, _ = output_paths(target_date)
    md_text = md_path.read_text(encoding="utf-8")
    parsed = parse_markdown(md_text)
    html_body = build_email_html(parsed)

    payload = json.dumps({
        "from": "AI 科技快讯 <onboarding@resend.dev>",
        "to": [EMAIL_TO],
        "subject": subject,
        "html": html_body,
    }, ensure_ascii=False)

    result = subprocess.run(
        [
            "curl", "-s", "-X", "POST",
            "https://api.resend.com/emails",
            "-H", f"Authorization: Bearer {RESEND_API_KEY}",
            "-H", "Content-Type: application/json",
            "-d", payload,
        ],
        capture_output=True, text=True, timeout=30,
    )
    try:
        data = json.loads(result.stdout)
        if data.get("id"):
            print(f"[INFO] email sent to {EMAIL_TO} OK, id={data['id']}")
        else:
            print(f"[WARN] resend send failed: {data}", file=sys.stderr)
    except Exception as e:
        print(f"[WARN] email send error: {e}", file=sys.stderr)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="AI RSS Briefing Generator")
    parser.add_argument(
        "--date",
        type=str,
        help="Generate for specific date (YYYY-MM-DD format). Default is today.",
    )
    parser.add_argument(
        "--essential",
        action="store_true",
        help="Use essential sources only (X limited to top 10, skip IT之家).",
    )
    args = parser.parse_args()

    if args.date:
        try:
            target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print(f"Error: Invalid date format '{args.date}'. Use YYYY-MM-DD.", file=sys.stderr)
            sys.exit(1)
        items = collect_today_items(target_date)
        translate_today_items(items)
        write_date_outputs(items, target_date)
        md_path, json_path, png_path = output_paths(target_date)
        render_image(md_path=str(md_path), out_path=str(png_path))
        send_email(items, target_date=target_date)
        print(f"{target_date} AI科技资讯已生成并发送邮件，共 {len(items)} 条")
    else:
        essential = args.essential
        if essential:
            today_items = collect_essential_items()
        else:
            today_items = collect_today_items()

        translate_today_items(today_items)
        write_today_outputs(today_items)
        md_path, _, png_path = output_paths()
        render_image(md_path=str(md_path), out_path=str(png_path))
        send_email(today_items, essential=essential)
        item_count = len(today_items)
        mode = "精选版" if essential else "完整版"
        print(f"今日AI科技资讯 ({mode}) 已生成并发送邮件，共 {item_count} 条")


if __name__ == "__main__":
    main()
