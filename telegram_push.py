"""Telegram 推送：把论文列表格式化成消息发出去。"""

import html
import time

import requests

TG_LIMIT = 4096  # Telegram 单条消息字符上限


def _escape(text):
    return html.escape(text or "")


def format_paper(p, index):
    """把一篇论文格式化成一段 HTML。"""
    # 有 AI 分数就在标题前标出来
    prefix = f"⭐{p['score']} " if "score" in p else ""
    # 有中文标题就用中文作主标题，英文原标题放下一行小字
    if p.get("title_zh"):
        lines = [f"<b>{index}. {prefix}{_escape(p['title_zh'])}</b>"]
        lines.append(f"<i>{_escape(p['title'])}</i>")
    else:
        lines = [f"<b>{index}. {prefix}{_escape(p['title'])}</b>"]

    meta = []
    if p.get("impact_factor"):
        meta.append(f"IF {_escape(str(p['impact_factor']))}")
    if p.get("authors"):
        meta.append(_escape(p["authors"]))
    if p.get("source"):
        meta.append(_escape(p["source"]))
    if p.get("date"):
        meta.append(_escape(p["date"]))
    if meta:
        lines.append("<i>" + " · ".join(meta) + "</i>")

    # 摘要优先级：AI 中文总结 > 翻译的中文摘要 > 英文原摘要
    if p.get("summary_zh"):
        lines.append("💡 " + _escape(p["summary_zh"]))
    elif p.get("abstract_zh"):
        lines.append("💡 " + _escape(p["abstract_zh"]))
    else:
        abstract = (p.get("abstract") or "").strip()
        if abstract:
            if len(abstract) > 400:
                abstract = abstract[:400].rstrip() + "…"
            lines.append(_escape(abstract))

    if p.get("url"):
        lines.append(f'🔗 <a href="{_escape(p["url"])}">{_escape(p["url"])}</a>')

    return "\n".join(lines)


def _chunk_messages(header, blocks):
    """把 header + 各论文块拼成若干条不超长的消息。"""
    messages, current = [], header
    for block in blocks:
        candidate = current + "\n\n" + block if current else block
        if len(candidate) > TG_LIMIT:
            if current:
                messages.append(current)
            current = block
        else:
            current = candidate
    if current:
        messages.append(current)
    return messages


def send(bot_token, chat_id, papers):
    """推送论文。无论文时发一条“今日无匹配”提示。"""
    api = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    if not papers:
        _post(
            api,
            chat_id,
            "📭 <b>今日文献推送</b>\n\n今天没有匹配到新的论文。",
        )
        return

    header = f"📚 <b>今日文献推送</b> · 共 {len(papers)} 篇"
    blocks = [format_paper(p, i + 1) for i, p in enumerate(papers)]
    for msg in _chunk_messages(header, blocks):
        _post(api, chat_id, msg)
        time.sleep(0.5)  # 避免触发限流


def _post(api, chat_id, text):
    resp = requests.post(
        api,
        data={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        },
        timeout=30,
    )
    if not resp.ok:
        raise RuntimeError(f"Telegram 发送失败: {resp.status_code} {resp.text}")
