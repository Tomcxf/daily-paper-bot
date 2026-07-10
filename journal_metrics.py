"""
期刊影响因子查询（离线，基于开源 impact_factor 包内置的 JCR 数据集）。

说明：这是内置数据集（约 2023 年 JCR），非实时官方数据；查不到的期刊返回 None。
为避免张冠李戴，只在期刊名精确匹配（或唯一命中）时才返回 IF。
"""

import sys

_factor = None


def _get_factor():
    global _factor
    if _factor is None:
        from impact_factor.core import Factor  # 延迟导入，未装也不影响其它功能
        _factor = Factor()
    return _factor


def get_if(journal):
    """返回该期刊的影响因子（字符串/数值），查不到返回 None。"""
    journal = (journal or "").strip().rstrip(".")
    if not journal:
        return None
    try:
        results = _get_factor().search(journal)
    except Exception as e:  # noqa: BLE001
        print(f"  影响因子查询出错: {e}", file=sys.stderr)
        return None
    if not results:
        return None

    target = journal.upper()
    for r in results:
        if (r.get("journal") or "").upper() == target:
            return r.get("factor")
    # 只有一个候选时也接受，否则宁可不显示（避免匹配错期刊）
    if len(results) == 1:
        return results[0].get("factor")
    return None


def annotate(papers):
    """给有期刊名的论文加 impact_factor 字段。就地修改并返回。"""
    ok = 0
    for p in papers:
        jf = get_if(p.get("journal"))
        if jf:
            p["impact_factor"] = jf
            ok += 1
    print(f"  影响因子：{ok} 篇查到。")
    return papers
