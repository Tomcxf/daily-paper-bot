"""
文献抓取模块：PubMed + bioRxiv/medRxiv。

每个抓取函数返回统一结构的 dict 列表，字段：
    id       去重用的唯一标识（PMID 或 DOI）
    title    标题
    authors  作者字符串
    abstract 摘要（可能为空）
    source   来源标签，如 "PubMed" / "bioRxiv"
    url      链接
    date     发布/收录日期字符串
"""

import datetime as dt
import time
import xml.etree.ElementTree as ET

import requests

# 出于礼貌给 NCBI/bioRxiv 一个可识别的 UA
HEADERS = {"User-Agent": "daily-paper-bot/1.0 (mailto:vtmeilab@gmail.com)"}
TIMEOUT = 30


def _get(url, **kwargs):
    """带简单重试的 GET。"""
    last_err = None
    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, **kwargs)
            r.raise_for_status()
            return r
        except requests.RequestException as e:  # noqa: PERF203
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise last_err


# ----------------------------------------------------------------------
# PubMed (NCBI E-utilities)
# ----------------------------------------------------------------------
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def build_query(topics):
    """把主题组转成 PubMed 检索式：组内 AND，组间 OR，均限定 Title/Abstract。"""
    groups = []
    for group in topics:
        terms = " AND ".join(f'"{t}"[Title/Abstract]' for t in group)
        groups.append(f"({terms})")
    return "(" + " OR ".join(groups) + ")"


def topic_hit(haystack, topics):
    """本地过滤：haystack 命中任意一个主题组（组内所有词都在）即为真。"""
    for group in topics:
        if all(t.lower() in haystack for t in group):
            return True
    return False


def fetch_pubmed(topics, lookback_days, max_results):
    """用主题组构造 PubMed 检索式，抓最近几天的论文。"""
    query = build_query(topics)

    esearch = (
        f"{EUTILS}/esearch.fcgi?db=pubmed&term={requests.utils.quote(query)}"
        f"&datetype=pdat&reldate={lookback_days}&retmax={max_results}"
        f"&sort=date&retmode=json"
    )
    ids = _get(esearch).json().get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []

    # efetch 拿标题、作者、摘要
    efetch = (
        f"{EUTILS}/efetch.fcgi?db=pubmed&id={','.join(ids)}"
        f"&retmode=xml&rettype=abstract"
    )
    root = ET.fromstring(_get(efetch).content)

    papers = []
    for art in root.findall(".//PubmedArticle"):
        pmid = art.findtext(".//PMID") or ""
        title = (art.findtext(".//ArticleTitle") or "").strip()
        if not title:
            continue

        # 摘要可能分多段
        abstract = " ".join(
            (node.text or "").strip()
            for node in art.findall(".//Abstract/AbstractText")
        ).strip()

        authors = []
        for a in art.findall(".//Author"):
            last = a.findtext("LastName")
            initials = a.findtext("Initials")
            if last:
                authors.append(f"{last} {initials}" if initials else last)
        author_str = ", ".join(authors[:3])
        if len(authors) > 3:
            author_str += " et al."

        journal = art.findtext(".//Journal/Title") or ""

        papers.append(
            {
                "id": f"pmid:{pmid}",
                "title": title,
                "authors": author_str,
                "abstract": abstract,
                "source": f"PubMed · {journal}" if journal else "PubMed",
                "journal": journal,  # 干净的期刊名，用于查影响因子
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "date": _pubmed_date(art),
            }
        )
    return papers


def _pubmed_date(art):
    pd = art.find(".//PubDate")
    if pd is None:
        return ""
    y = pd.findtext("Year") or ""
    m = pd.findtext("Month") or ""
    d = pd.findtext("Day") or ""
    return " ".join(x for x in (y, m, d) if x)


# ----------------------------------------------------------------------
# bioRxiv / medRxiv
# ----------------------------------------------------------------------
def fetch_biorxiv(server, topics, lookback_days, max_results):
    """
    bioRxiv API 不支持关键词检索，只能按日期区间取回全部新论文，
    再在本地对 标题+摘要 做主题组过滤。
    API: https://api.biorxiv.org/details/{server}/{from}/{to}/{cursor}
    """
    today = dt.date.today()
    start = today - dt.timedelta(days=lookback_days)

    collected = []
    cursor = 0
    while True:
        url = (
            f"https://api.biorxiv.org/details/{server}/"
            f"{start.isoformat()}/{today.isoformat()}/{cursor}"
        )
        data = _get(url).json()
        batch = data.get("collection", [])
        if not batch:
            break

        for item in batch:
            title = (item.get("title") or "").strip()
            abstract = (item.get("abstract") or "").strip()
            haystack = f"{title} {abstract}".lower()

            if not topic_hit(haystack, topics):
                continue

            doi = item.get("doi", "")
            collected.append(
                {
                    "id": f"doi:{doi}",
                    "title": title,
                    "authors": _biorxiv_authors(item.get("authors", "")),
                    "abstract": abstract,
                    "source": server,
                    "url": f"https://doi.org/{doi}" if doi else "",
                    "date": item.get("date", ""),
                }
            )

        # 分页：messages 里有 total，一批通常 100 条
        total = int(data.get("messages", [{}])[0].get("total", 0))
        cursor += len(batch)
        if cursor >= total or len(collected) >= max_results * 3:
            break

    # 去重（同一篇可能有多个版本）并截断
    seen, unique = set(), []
    for p in collected:
        if p["id"] in seen:
            continue
        seen.add(p["id"])
        unique.append(p)
    return unique[:max_results]


def _biorxiv_authors(raw):
    parts = [a.strip() for a in raw.split(";") if a.strip()]
    s = ", ".join(parts[:3])
    if len(parts) > 3:
        s += " et al."
    return s
