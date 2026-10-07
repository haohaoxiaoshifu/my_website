"""收集 arXiv 最新论文并合并到 public/data/papers.json。

- 仅使用 Python 标准库；
- 以 arXiv id 去重，保留最多 50 篇，按发布日期倒序；
- 网络失败时保留已有数据；首次运行无旧数据则以非零码退出。
"""
import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "public" / "data" / "papers.json"
API = "https://export.arxiv.org/api/query"
ATOM = {"atom": "http://www.w3.org/2005/Atom"}


def clean(text):
    return " ".join((text or "").split())


def fetch(query, limit):
    params = urlencode({
        "search_query": query,
        "start": 0,
        "max_results": limit,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    })
    request = Request(f"{API}?{params}", headers={"User-Agent": "zheng-hao-personal-site/1.0"})
    with urlopen(request, timeout=25) as response:
        root = ET.fromstring(response.read())

    papers = []
    for entry in root.findall("atom:entry", ATOM):
        raw_id = clean(entry.findtext("atom:id", namespaces=ATOM))
        paper_id = raw_id.rsplit("/", 1)[-1]
        papers.append({
            "id": paper_id,
            "title": clean(entry.findtext("atom:title", namespaces=ATOM)),
            "authors": [clean(a.findtext("atom:name", namespaces=ATOM))
                        for a in entry.findall("atom:author", ATOM)],
            "published": clean(entry.findtext("atom:published", namespaces=ATOM))[:10],
            "summary": clean(entry.findtext("atom:summary", namespaces=ATOM)),
            "url": raw_id.replace("http://", "https://"),
            "source": "arXiv",
        })
    return papers


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", default='all:"AI agent" OR all:"LLM agent"')
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    old = []
    if OUTPUT.exists():
        old = json.loads(OUTPUT.read_text(encoding="utf-8"))

    try:
        fetched = fetch(args.query, args.limit)
    except Exception as exc:  # noqa: BLE001 - 网络失败保留旧数据
        if old:
            print(json.dumps({"fetched": 0, "new": 0, "saved": len(old),
                              "query": args.query, "error": str(exc)}, ensure_ascii=False))
            return 0
        print(f"FETCH FAILED AND NO OLD DATA: {exc}", file=sys.stderr)
        return 1

    by_id = {paper["id"]: paper for paper in old}
    before = len(by_id)
    for paper in fetched:
        by_id[paper["id"]] = paper

    result = sorted(by_id.values(), key=lambda p: p["published"], reverse=True)[:50]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"fetched": len(fetched), "new": len(by_id) - before,
                      "saved": len(result), "query": args.query}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
