"""
免费中文翻译（Google 翻译公开接口，无需 API key）。

用于把英文标题翻成中文。注意：这是免费非官方接口，偶尔可能限流或失败，
失败时不影响推送（保留英文原文）。想要更高质量的中文，用 config 里的 AI 打分功能。
"""

import time

import requests

ENDPOINT = "https://translate.googleapis.com/translate_a/single"
HEADERS = {"User-Agent": "Mozilla/5.0 daily-paper-bot"}


def to_zh(text):
    """英文 → 简体中文。失败返回空字符串。"""
    text = (text or "").strip()
    if not text:
        return ""
    params = {"client": "gtx", "sl": "en", "tl": "zh-CN", "dt": "t", "q": text}
    for attempt in range(2):
        try:
            r = requests.get(ENDPOINT, params=params, headers=HEADERS, timeout=15)
            r.raise_for_status()
            data = r.json()
            return "".join(seg[0] for seg in data[0] if seg[0])
        except Exception:  # noqa: BLE001
            time.sleep(1.0 * (attempt + 1))
    return ""


def translate_papers(papers, do_abstract=True):
    """给每篇论文加 title_zh（和可选 abstract_zh）字段。就地修改并返回。"""
    ok_t = ok_a = 0
    for p in papers:
        zh = to_zh(p.get("title", ""))
        if zh:
            p["title_zh"] = zh
            ok_t += 1
        time.sleep(0.2)  # 轻微限速，友好使用免费接口

        if do_abstract:
            ab = (p.get("abstract") or "").strip()
            if ab:
                zh_ab = to_zh(ab[:600])  # 截断，控制长度与速度
                if zh_ab:
                    p["abstract_zh"] = zh_ab
                    ok_a += 1
                time.sleep(0.2)

    msg = f"  翻译完成：标题 {ok_t}/{len(papers)}"
    if do_abstract:
        msg += f"，摘要 {ok_a}/{len(papers)}"
    print(msg + " 篇。")
    return papers
