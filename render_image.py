#!/usr/bin/env python3

"""将 Markdown 资讯渲染为 Bento 风格长图"""

from __future__ import annotations

import argparse
import html
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent

LXGW_FONT_PATH = str(Path.home() / "Library/Fonts/LXGWNeoXiHei.ttf")

LXGW_FONT_FACE = f"""@font-face {{
  font-family: 'LXGWNeoXiHei';
  src: url('file://{LXGW_FONT_PATH}') format('truetype');
  font-weight: normal;
  font-style: normal;
}}
"""

CATEGORY_ICONS = {
    "AI 模型与性能": "🤖",
    "Claude Code 与编程工具": "💻",
    "企业与市场动态": "📈",
    "新产品与平台": "🚀",
    "AI 安全与对齐": "🛡️",
    "AI 趋势与观点": "💡",
    "自动驾驶与机器人": "🚗",
    "芯片与硬件": "⚙️",
    "其他科技动态": "📱",
}

CATEGORY_FA_ICONS = {
    "AI 模型与性能": "fa-solid fa-microchip",
    "Claude Code 与编程工具": "fa-solid fa-code",
    "企业与市场动态": "fa-solid fa-chart-line",
    "新产品与平台": "fa-solid fa-rocket",
    "AI 安全与对齐": "fa-solid fa-shield-halved",
    "AI 趋势与观点": "fa-solid fa-lightbulb",
    "自动驾驶与机器人": "fa-solid fa-robot",
    "芯片与硬件": "fa-solid fa-microchip",
    "其他科技动态": "fa-solid fa-newspaper",
}

CATEGORY_COLORS = {
    "AI 模型与性能": ("#3b82f6", "rgba(59,130,246,0.08)"),
    "Claude Code 与编程工具": ("#8b5cf6", "rgba(139,92,246,0.08)"),
    "企业与市场动态": ("#10b981", "rgba(16,185,129,0.08)"),
    "新产品与平台": ("#f59e0b", "rgba(245,158,11,0.08)"),
    "AI 安全与对齐": ("#ef4444", "rgba(239,68,68,0.08)"),
    "AI 趋势与观点": ("#6366f1", "rgba(99,102,241,0.08)"),
    "自动驾驶与机器人": ("#06b6d4", "rgba(6,182,212,0.08)"),
    "芯片与硬件": ("#64748b", "rgba(100,116,139,0.08)"),
    "其他科技动态": ("#ec4899", "rgba(236,72,153,0.08)"),
}

PAGE_WIDTH = 1200


def parse_markdown(text: str) -> list[dict]:
    items = []
    lines = text.strip().split("\n")

    title_line = lines[0].strip().lstrip("# ") if lines else ""

    quote_lines = []
    for line in lines[1:8]:
        line = line.strip()
        if line.startswith("> "):
            quote_lines.append(line[2:])
    quote = " ".join(quote_lines) if quote_lines else ""

    items.append({"type": "header", "title": title_line, "quote": quote})

    current_category = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("## "):
            current_category = line[3:].strip()
            items.append({"type": "category", "name": current_category})
        elif line.startswith("**") and line.endswith("**"):
            items.append({
                "type": "item",
                "title": line.strip("*").strip(),
                "category": current_category,
            })
        elif line.startswith("[") and "]" in line and ("http" in line or "nitter" in line):
            bracket_end = line.index("]")
            items[-1]["source"] = line[1:bracket_end]
            items[-1]["link"] = line[bracket_end+1:].strip()
        elif re.match(r"^\d{4}-\d{2}-\d{2}", line):
            if items and items[-1]["type"] == "item":
                items[-1]["time"] = line

    return items


def _esc(text: str) -> str:
    return html.escape(text)


def build_html(items: list[dict]) -> str:
    icon_map = CATEGORY_ICONS
    color_map = CATEGORY_COLORS

    # Parse header
    title = ""
    quote_text = ""
    quote_author = ""
    for item in items:
        if item["type"] == "header":
            title = item["title"]
            if item.get("quote"):
                q = item["quote"]
                if "——" in q:
                    parts = q.split("——", 1)
                    quote_text = parts[0].strip()
                    quote_author = "——" + parts[1].strip()
                else:
                    quote_text = q
            break

    # Collect categories with their items
    categories = []
    current_cat = None
    for item in items:
        if item["type"] == "category":
            current_cat = {"name": item["name"], "items": []}
            categories.append(current_cat)
        elif item["type"] == "item" and current_cat is not None:
            current_cat["items"].append(item)

    # Build hero card
    hero = _build_hero(title, quote_text, quote_author)

    # Build category bento sections
    sections = []
    fa_icon_map = CATEGORY_FA_ICONS
    for cat in categories:
        icon = icon_map.get(cat["name"], "📌")
        fa_icon = fa_icon_map.get(cat["name"], "fa-solid fa-circle")
        colors = color_map.get(cat["name"], ("#6b7280", "rgba(107,114,128,0.08)"))
        accent, bg_light = colors
        sections.append(_build_bento_section(cat["name"], icon, fa_icon, accent, bg_light, cat["items"]))

    return _assemble_page(hero, sections)


def _build_hero(title, quote_text, quote_author) -> str:
    quote_html = ""
    if quote_text:
        quote_html = f"""
      <div class="hero-quote">
        <div class="hero-quote-text">{_esc(quote_text)}</div>
        {'<div class="hero-quote-author">' + _esc(quote_author) + '</div>' if quote_author else ''}
      </div>"""
    return f"""
    <section class="hero-card">
      <h1 class="hero-title">{_esc(title)}</h1>
      {quote_html}
    </section>"""


def _estimate_card_height(item) -> int:
    """粗略估算卡片像素高度，用于最短列分配"""
    title = item.get("title", "")
    h = 80  # base: padding + accent bar
    h += max(1, (len(title) + 25) // 26) * 28  # title lines
    if item.get("source") or item.get("time"):
        h += 24  # meta row
    return h


def _build_bento_section(cat_name, emoji_icon, fa_icon, accent, bg_light, cat_items) -> str:
    if len(cat_items) == 1:
        col_html = _build_bento_card(cat_items[0], accent, bg_light)
        return f"""
  <section class="category-section">
    <header class="category-header">
      <div class="category-icon-block" style="background: {bg_light}; color: {accent};"><i class="{fa_icon}"></i></div>
      <h2 class="category-title">{_esc(cat_name)}</h2>
      <span class="category-count" style="background: {bg_light}; color: {accent};">{len(cat_items)}</span>
    </header>
    <div class="masonry-grid">
      <div class="masonry-col">{col_html}</div>
    </div>
  </section>"""

    # 最短列优先分配
    cols: list[list] = [[], []]
    heights = [0, 0]
    for item in cat_items:
        idx = 0 if heights[0] <= heights[1] else 1
        cols[idx].append(item)
        heights[idx] += _estimate_card_height(item)

    col_blocks = ""
    for col_items in cols:
        if not col_items:
            continue
        cards = "".join(_build_bento_card(it, accent, bg_light) for it in col_items)
        col_blocks += f'      <div class="masonry-col">{cards}</div>\n'

    return f"""
  <section class="category-section">
    <header class="category-header">
      <div class="category-icon-block" style="background: {bg_light}; color: {accent};"><i class="{fa_icon}"></i></div>
      <h2 class="category-title">{_esc(cat_name)}</h2>
      <span class="category-count" style="background: {bg_light}; color: {accent};">{len(cat_items)}</span>
    </header>
    <div class="masonry-grid">
{col_blocks}    </div>
  </section>"""


def _build_bento_card(item, accent, bg_light) -> str:
    source = item.get("source", "")
    link = item.get("link", "")
    time_str = item.get("time", "")
    title = item.get("title", "")

    display_title = title[:120] + "..." if len(title) > 120 else title

    meta_parts = []
    if source:
        meta_parts.append(f'<span class="card-source" style="color: {accent};">{_esc(source)}</span>')
    if time_str:
        t = time_str.strip()
        m = re.search(r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2}:\d{2})', t)
        if m:
            formatted = f"{m.group(2)}-{m.group(3)} {m.group(4)}"
        else:
            formatted = _esc(t)
        meta_parts.append(f'<span class="card-time">{formatted}</span>')

    meta_html = ""
    if meta_parts:
        meta_html = f'<div class="card-meta">{"".join(meta_parts)}</div>'

    return f'''
      <article class="bento-card">
        <div class="card-accent-bar" style="background: {accent};"></div>
        <div class="card-body">
          <h3 class="card-title">{_esc(display_title)}</h3>
          {meta_html}
        </div>
      </article>'''


def _assemble_page(hero_html, sections_html) -> str:
    sections_joined = "\n".join(sections_html)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
<style>
{LXGW_FONT_FACE}
* {{
  margin: 0; padding: 0; box-sizing: border-box;
}}
body {{
  width: {PAGE_WIDTH}px;
  font-family: 'LXGWNeoXiHei', -apple-system, BlinkMacSystemFont, "SF Pro Display", "PingFang SC", sans-serif;
  background: #edf1f8;
  padding: 0;
  -webkit-font-smoothing: antialiased;
}}
.page {{
  padding: 36px 44px;
  display: flex;
  flex-direction: column;
  gap: clamp(22px, 2.2vw, 30px);
}}

/* ── Hero Card ────────────────────────────── */
.hero-card {{
  background: linear-gradient(135deg, #ffffff 0%, #f8faff 100%);
  border-radius: 24px;
  padding: clamp(32px, 4vw, 48px);
  box-shadow: 0 2px 20px rgba(0,0,0,0.04), 0 0 0 1px rgba(0,0,0,0.03);
  backdrop-filter: blur(20px);
  position: relative;
  overflow: hidden;
}}
.hero-card::before {{
  content: '';
  position: absolute;
  top: -60px; right: -60px;
  width: 200px; height: 200px;
  background: radial-gradient(circle, rgba(59,130,246,0.06) 0%, transparent 70%);
  border-radius: 50%;
}}
.hero-title {{
  font-size: clamp(28px, 4vw, 40px);
  font-weight: 800;
  color: #1a1a2e;
  line-height: 1.25;
  letter-spacing: -0.5px;
  margin-bottom: 28px;
}}
.hero-quote {{
  background: rgba(59,130,246,0.04);
  border-left: 3px solid #3b82f6;
  border-radius: 0 12px 12px 0;
  padding: 16px 20px;
  margin-bottom: 8px;
}}
.hero-quote-text {{
  font-size: clamp(15px, 1.6vw, 18px);
  color: #374151;
  line-height: 1.6;
  font-style: italic;
}}
.hero-quote-author {{
  font-size: 13px;
  color: #9ca3af;
  margin-top: 8px;
}}
/* ── Category Section ─────────────────────── */
.category-section {{
  display: flex;
  flex-direction: column;
  gap: 16px;
}}
.category-header {{
  display: flex;
  align-items: center;
  gap: 12px;
}}
.category-icon-block {{
  width: 36px; height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
}}
.category-title {{
  font-size: clamp(16px, 1.8vw, 20px);
  font-weight: 700;
  color: #1a1a2e;
  flex: 1;
}}
.category-count {{
  font-size: 12px;
  font-weight: 700;
  padding: 4px 10px;
  border-radius: 12px;
  flex-shrink: 0;
}}

/* ── Masonry / Waterfall ──────────────────── */
.masonry-grid {{
  display: flex;
  gap: 20px;
}}
.masonry-col {{
  flex: 1;
  display: flex;
  flex-direction: column;
}}
.bento-card {{
  background: #ffffff;
  border-radius: 22px;
  box-shadow: 0 1px 8px rgba(0,0,0,0.03), 0 0 0 1px rgba(0,0,0,0.04);
  overflow: hidden;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  position: relative;
  margin-bottom: 20px;
  min-height: 280px;
  display: flex;
  flex-direction: column;
}}
.bento-card:hover {{
  transform: translateY(-2px);
  box-shadow: 0 4px 20px rgba(0,0,0,0.06), 0 0 0 1px rgba(0,0,0,0.04);
}}
.card-accent-bar {{
  height: 3px;
  width: 100%;
}}
.card-body {{
  padding: clamp(24px, 3vw, 34px);
  flex: 1;
}}
.card-title {{
  font-size: clamp(18px, 2vw, 22px);
  font-weight: 600;
  color: #1a1a2e;
  line-height: 1.55;
  margin-bottom: 16px;
}}
.card-meta {{
  display: flex;
  align-items: center;
  gap: 10px;
}}
.card-source {{
  font-size: 14px;
  font-weight: 600;
}}
.card-time {{
  font-size: 14px;
  color: #9ca3af;
  font-weight: 500;
}}

/* ── Size variants ────────────────────────── */
.card-sm .card-title {{ margin-bottom: 10px; }}
.card-sm .card-body {{ padding: clamp(18px, 2vw, 24px); }}
.card-lg .card-title {{ font-size: clamp(16px, 1.7vw, 19px); }}

/* ── Responsive ───────────────────────────── */
@media (max-width: 1024px) {{
  body {{ width: 100%; }}
  .page {{ padding: 20px; }}
}}
@media (max-width: 600px) {{
  .masonry-grid {{ flex-direction: column; }}
}}
</style>
</head>
<body>
<main class="page">
{hero_html}
{sections_joined}
</main>
</body>
</html>"""


def build_email_html(items: list[dict]) -> str:
    # Parse header
    title = ""
    quote_text = ""
    quote_author = ""
    for item in items:
        if item["type"] == "header":
            title = item["title"]
            if item.get("quote"):
                q = item["quote"]
                if "——" in q:
                    parts = q.split("——", 1)
                    quote_text = parts[0].strip()
                    quote_author = "——" + parts[1].strip()
                else:
                    quote_text = q
            break

    # Hero section
    quote_html = ""
    if quote_text:
        quote_author_html = f'<tr><td style="padding:0 18px 10px;font-size:13px;color:#9ca3af;font-family:-apple-system,BlinkMacSystemFont,\'PingFang SC\',sans-serif;">{_esc(quote_author)}</td></tr>' if quote_author else ''
        quote_html = f'''<tr><td style="padding:0 0 20px 0;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f0f4ff;border-left:3px solid #3b82f6;border-radius:0 8px 8px 0;">
        <tr><td style="padding:14px 18px;font-size:15px;color:#374151;line-height:1.6;font-style:italic;font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;">{_esc(quote_text)}</td></tr>
        {quote_author_html}
      </table>
    </td></tr>'''

    # Collect categories
    categories = []
    current_cat = None
    for item in items:
        if item["type"] == "category":
            current_cat = {"name": item["name"], "items": []}
            categories.append(current_cat)
        elif item["type"] == "item" and current_cat is not None:
            current_cat["items"].append(item)

    # Build category sections
    sections_html = ""
    for cat in categories:
        icon = CATEGORY_ICONS.get(cat["name"], "📌")
        colors = CATEGORY_COLORS.get(cat["name"], ("#6b7280", "rgba(107,114,128,0.08)"))
        accent = colors[0]

        def _email_card(item):
            title_text = item.get("title", "")
            display = title_text[:120] + "..." if len(title_text) > 120 else title_text
            source = item.get("source", "")
            time_str = item.get("time", "")
            link = item.get("link", "")
            meta = ""
            if source or time_str or link:
                line1_parts = []
                if source:
                    line1_parts.append(f'<span style="font-size:11px;font-weight:600;color:{accent};font-family:-apple-system,BlinkMacSystemFont,\'PingFang SC\',sans-serif;">{_esc(source)}</span>')
                if time_str:
                    m = re.search(r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2}:\d{2})', time_str.strip())
                    if m:
                        t = f"{m.group(2)}-{m.group(3)} {m.group(4)}"
                    else:
                        t = _esc(time_str.strip())
                    line1_parts.append(f'<span style="font-size:11px;color:#9ca3af;font-family:-apple-system,BlinkMacSystemFont,\'PingFang SC\',sans-serif;">{t}</span>')
                line1 = f'{line1_parts[0]}<span style="display:inline-block;width:10px;"></span>{line1_parts[1]}' if len(line1_parts) == 2 else (line1_parts[0] if line1_parts else "")
                line2 = ""
                if link:
                    short = link if len(link) <= 50 else link[:47] + "..."
                    line2 = f'<tr><td style="padding:4px 14px 0 14px;"><a href="{_esc(link)}" style="font-size:10px;color:#9ca3af;text-decoration:none;font-family:-apple-system,BlinkMacSystemFont,\'PingFang SC\',sans-serif;">{_esc(short)}</a></td></tr>'
                meta = f'<tr><td style="padding:6px 14px 0 14px;">{line1}</td></tr>{line2}'

            return f'''<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#ffffff;border:1px solid #e5e7eb;border-radius:12px;margin-bottom:10px;">
              <tr><td style="height:3px;background:{accent};border-radius:12px 12px 0 0;"></td></tr>
              <tr><td style="padding:14px 14px 6px 14px;font-size:14px;font-weight:600;color:#1a1a2e;line-height:1.5;font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;">{_esc(display)}</td></tr>
              {meta}
              <tr><td style="padding:0 14px 10px 14px;"></td></tr>
            </table>'''

        # Split items into two columns
        left_items = cat["items"][0::2]
        right_items = cat["items"][1::2]

        left_html = "".join(_email_card(item) for item in left_items)
        right_html = "".join(_email_card(item) for item in right_items)

        sections_html += f'''<tr><td style="padding:20px 0 0 0;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr><td style="padding:0 0 12px 0;font-size:16px;font-weight:700;color:#1a1a2e;font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;">
            <span style="display:inline-block;width:28px;height:28px;line-height:28px;text-align:center;background:{accent}15;border-radius:7px;font-size:14px;">{icon}</span>&nbsp;&nbsp;{_esc(cat["name"])}
            <span style="display:inline-block;margin-left:6px;padding:2px 8px;background:{accent}15;color:{accent};font-size:11px;font-weight:700;border-radius:8px;">{len(cat["items"])}</span>
          </td></tr>
      </table>
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td width="50%" valign="top" style="padding:0 6px 0 0;">{left_html}</td>
          <td width="50%" valign="top" style="padding:0 0 0 6px;">{right_html}</td>
        </tr>
      </table>
    </td></tr>'''

    return f'''<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#edf1f8;">
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#edf1f8;">
  <tr><td align="center" style="padding:20px 10px;">
    <table width="640" cellpadding="0" cellspacing="0" border="0" style="max-width:640px;width:100%;">
      <!-- Hero -->
      <tr><td style="background:#ffffff;border-radius:16px;padding:28px 32px;border:1px solid #e5e7eb;margin-bottom:20px;">
        <table width="100%" cellpadding="0" cellspacing="0" border="0">
          <tr><td style="font-size:26px;font-weight:800;color:#1a1a2e;line-height:1.3;padding:0 0 24px 0;font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;">{_esc(title)}</td></tr>
          {quote_html}
        </table>
      </td></tr>
      <!-- Spacer -->
      <tr><td style="height:8px;"></td></tr>
      <!-- Sections -->
      {sections_html}
      <!-- Footer -->
      <tr><td style="padding:32px 0;text-align:center;font-size:12px;color:#9ca3af;font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;">
        AI RSS Briefing
      </td></tr>
    </table>
  </td></tr>
</table>
</body>
</html>'''


def render(md_path: str | None = None, out_path: str | None = None):
    if md_path is None:
        md_path = str(ROOT / "today-每日AI科技资讯.md")
    if out_path is None:
        out_path = str(ROOT / "today-每日AI科技资讯.png")

    text = Path(md_path).read_text(encoding="utf-8")
    items = parse_markdown(text)
    html_content = build_html(items)

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, dir=str(ROOT)) as f:
        f.write(html_content.encode("utf-8"))
        html_path = f.name

    try:
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page(viewport={"width": PAGE_WIDTH, "height": 800}, device_scale_factor=2)
                page.goto(f"file://{html_path}")
                page.wait_for_timeout(500)
                height = page.evaluate("document.querySelector('.page').scrollHeight")
                page.set_viewport_size({"width": PAGE_WIDTH, "height": height + 80})
                page.locator(".page").screenshot(path=out_path)
                browser.close()
            print(f"Saved to {out_path}")
            return
        except ImportError:
            pass

        try:
            subprocess.run(
                ["wkhtmltoimage", "--width", str(PAGE_WIDTH), "--quality", "95", html_path, out_path],
                check=True, capture_output=True
            )
            print(f"Saved to {out_path}")
            return
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass

        try:
            import weasyprint
            weasyprint.HTML(filename=html_path).write_pdf(out_path.replace(".png", ".pdf"))
            print(f"Saved PDF to {out_path.replace('.png', '.pdf')}")
            return
        except ImportError:
            pass

        print("Error: No rendering engine found. Install playwright or weasyprint.")
    finally:
        Path(html_path).unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--md", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    render(md_path=args.md, out_path=args.out)
