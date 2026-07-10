#!/usr/bin/env python3
"""
每日文献推送主程序。

流程：读配置 → 抓 PubMed / bioRxiv → 关键词过滤 → 去掉已推送过的 → 推 Telegram。
用法：
    python main.py            正常运行并推送
    python main.py --dry-run  只抓取和打印，不推送、不记录状态（调试用）
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import yaml

import ai_filter
import journal_metrics
import sources
import telegram_push
import translate

BASE = Path(__file__).resolve().parent
CONFIG_PATH = BASE / "config.yaml"
STATE_PATH = BASE / "state.json"


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_secret(value, required=True):
    """支持 "ENV:VAR" 形式，从环境变量读取。
    required=False 时缺失返回 None 而不退出。"""
    if isinstance(value, str) and value.startswith("ENV:"):
        var = value[4:]
        got = os.environ.get(var)
        if not got:
            if required:
                sys.exit(f"错误：环境变量 {var} 未设置。请先 export {var}=...")
            return None
        return got
    return value


def load_state():
    if STATE_PATH.exists():
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"seen_ids": []}


def save_state(state):
    # 只保留最近 5000 条，防止无限增长
    state["seen_ids"] = state["seen_ids"][-5000:]
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def collect_papers(cfg):
    topics = cfg["topics"]
    lookback = cfg.get("lookback_days", 2)
    max_per = cfg.get("max_per_source", 10)
    srcs = cfg.get("sources", {})

    papers = []
    attempted = succeeded = 0  # 用于区分“真的没论文”和“断网抓取失败”

    if srcs.get("pubmed", {}).get("enabled"):
        attempted += 1
        try:
            got = sources.fetch_pubmed(topics, lookback, max_per)
            print(f"  PubMed: {len(got)} 篇")
            papers += got
            succeeded += 1
        except Exception as e:  # noqa: BLE001
            print(f"  PubMed 抓取失败: {e}", file=sys.stderr)

    bio = srcs.get("biorxiv", {})
    if bio.get("enabled"):
        for server in bio.get("servers", ["biorxiv"]):
            attempted += 1
            try:
                got = sources.fetch_biorxiv(server, topics, lookback, max_per)
                print(f"  {server}: {len(got)} 篇")
                papers += got
                succeeded += 1
            except Exception as e:  # noqa: BLE001
                print(f"  {server} 抓取失败: {e}", file=sys.stderr)

    return papers, attempted, succeeded


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只抓取打印，不推送")
    args = ap.parse_args()

    cfg = load_config()

    # 抓取；若所有数据源都失败（多半是运行时无网络，如刚开机/唤醒），
    # 隔一会儿重试几次，覆盖网络还没起来的情况。
    net_retries = 3
    retry_delay = 120  # 秒
    for attempt in range(net_retries):
        print("开始抓取文献…")
        papers, attempted, succeeded = collect_papers(cfg)
        if attempted == 0 or succeeded > 0:
            break
        if attempt < net_retries - 1:
            print(f"所有数据源抓取失败（可能暂时无网络），{retry_delay}s 后重试…",
                  file=sys.stderr)
            time.sleep(retry_delay)
    else:
        # 多次仍全失败：不推送、不改状态、干净退出（明天照常再跑）
        sys.exit("多次重试后仍无法抓取任何数据源，判断为无网络，本次跳过。")

    # 去重（本次内部）
    seen_now, deduped = set(), []
    for p in papers:
        if p["id"] in seen_now:
            continue
        seen_now.add(p["id"])
        deduped.append(p)

    # 过滤掉历史已推送过的
    state = load_state()
    already = set(state["seen_ids"])
    fresh = [p for p in deduped if p["id"] not in already]

    print(f"抓到 {len(deduped)} 篇，去掉历史已推 {len(deduped) - len(fresh)} 篇，"
          f"关键词命中 {len(fresh)} 篇。")

    # AI 相关性打分 + 中文摘要（可选）
    ai_cfg = cfg.get("ai", {})
    if ai_cfg.get("enabled") and fresh:
        api_key = resolve_secret(ai_cfg.get("api_key"), required=False)
        if api_key:
            print("AI 打分中…")
            fresh = ai_filter.score_papers(
                fresh,
                focus=ai_cfg.get("focus", ""),
                api_key=api_key,
                model=ai_cfg.get("model", "claude-opus-4-8"),
                min_score=ai_cfg.get("min_score", 6),
            )
        else:
            print("未设置 ANTHROPIC_API_KEY，跳过 AI 打分，按关键词结果推送。",
                  file=sys.stderr)

    # 影响因子标注（离线，只对有期刊名的 PubMed 论文）
    if cfg.get("impact_factor", {}).get("enabled") and fresh:
        print("查影响因子中…")
        try:
            journal_metrics.annotate(fresh)
        except Exception as e:  # noqa: BLE001
            print(f"  影响因子模块不可用，跳过: {e}", file=sys.stderr)

    # 中文翻译（免费，翻译最终要推送的这批）
    tr_cfg = cfg.get("translate", {})
    if tr_cfg.get("enabled") and fresh:
        print("翻译中…")
        translate.translate_papers(fresh, do_abstract=tr_cfg.get("abstract", True))

    print(f"最终推送 {len(fresh)} 篇。")

    if args.dry_run:
        for i, p in enumerate(fresh, 1):
            tag = f"[{p['score']}分] " if "score" in p else ""
            print(f"\n[{i}] {tag}{p['title']}\n    {p['source']} | {p['url']}")
            if p.get("summary_zh"):
                print(f"    摘要: {p['summary_zh']}")
        print("\n(dry-run：未推送，未更新状态)")
        return

    tg = cfg["telegram"]
    bot_token = resolve_secret(tg["bot_token"])
    chat_id = resolve_secret(tg["chat_id"])

    try:
        telegram_push.send(bot_token, chat_id, fresh)
    except Exception as e:  # noqa: BLE001
        # 网络问题导致发送失败：干净退出（不记录状态，下次会重发），不抛 traceback
        sys.exit(f"Telegram 推送失败（可能无网络），本次未记录状态，下次会重试：{e}")
    print("已推送到 Telegram。")

    # 记录已推送的 ID（仅在推送成功后）
    state["seen_ids"].extend(p["id"] for p in fresh)
    save_state(state)


if __name__ == "__main__":
    main()
