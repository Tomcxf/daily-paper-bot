"""
AI 相关性打分 + 中文摘要。

对抓到的论文，用 Claude 按你的研究方向打相关性分（0-10）并生成一句话中文总结。
低于阈值的自动过滤掉，其余按分数从高到低排序。

依赖 anthropic SDK；需要环境变量 ANTHROPIC_API_KEY（或在 config 里配 api_key）。
"""

import json
import sys

import anthropic

# 每批送给模型多少篇（控制单次 token 和输出长度）
BATCH_SIZE = 10

# 强制模型按此结构输出，省去解析容错
SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "score": {"type": "integer"},
                    "summary_zh": {"type": "string"},
                },
                "required": ["index", "score", "summary_zh"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["results"],
    "additionalProperties": False,
}


def _system_prompt(focus):
    return (
        "你是一位科研文献助理，帮用户从每日新论文里筛选真正相关的。\n"
        f"用户的研究方向：\n{focus}\n\n"
        "给你一批论文（编号、标题、摘要）。对每一篇：\n"
        "1) 打相关性分 score（0-10 整数）：10=高度契合其主攻方向；"
        "6-9=相关；1-5=沾边但非核心；0=无关。\n"
        "   注意区分‘单细胞/AI 算法方法学论文’(高分) 和‘只是用了单细胞技术的湿实验应用’(低分)。\n"
        "2) 写一句 40 字以内的中文总结 summary_zh，点出这篇做了什么、方法或结论。\n"
        "index 必须与输入编号一致。只依据给定信息，不要编造。"
    )


def _build_user_message(batch):
    lines = []
    for p in batch:
        abstract = (p.get("abstract") or "").strip()
        if len(abstract) > 700:
            abstract = abstract[:700] + "…"
        lines.append(
            f"[{p['_idx']}] 标题: {p['title']}\n摘要: {abstract or '（无摘要）'}"
        )
    return "以下是本批论文：\n\n" + "\n\n".join(lines)


def score_papers(papers, focus, api_key, model, min_score):
    """
    返回过滤+排序后的论文列表，每篇附加 'score' 和 'summary_zh' 字段。
    出错时不阻断流程：打印告警并原样返回（不打分、不过滤）。
    """
    if not papers:
        return papers

    try:
        client = anthropic.Anthropic(api_key=api_key)
    except Exception as e:  # noqa: BLE001
        print(f"  AI 初始化失败，跳过打分: {e}", file=sys.stderr)
        return papers

    # 给每篇一个稳定编号，便于对回
    for i, p in enumerate(papers):
        p["_idx"] = i

    scores = {}
    for start in range(0, len(papers), BATCH_SIZE):
        batch = papers[start : start + BATCH_SIZE]
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=2048,
                system=_system_prompt(focus),
                messages=[{"role": "user", "content": _build_user_message(batch)}],
                output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
            )
            text = next(b.text for b in resp.content if b.type == "text")
            for r in json.loads(text)["results"]:
                scores[r["index"]] = (r["score"], r["summary_zh"])
        except Exception as e:  # noqa: BLE001
            print(f"  AI 打分某批失败，这批不打分: {e}", file=sys.stderr)

    if not scores:
        print("  AI 全部批次失败，按未打分推送。", file=sys.stderr)
        for p in papers:
            p.pop("_idx", None)
        return papers

    # 附加分数与摘要，过滤低分，排序
    kept = []
    for p in papers:
        sc = scores.get(p["_idx"])
        p.pop("_idx", None)
        if sc is None:
            continue
        p["score"], p["summary_zh"] = sc
        if p["score"] >= min_score:
            kept.append(p)

    kept.sort(key=lambda x: x["score"], reverse=True)
    print(f"  AI 打分完成：{len(kept)}/{len(papers)} 篇达到阈值 {min_score}。")
    return kept
