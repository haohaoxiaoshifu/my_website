"""校验 public/data/papers.json 的字段完整性、id 唯一性与链接安全性。"""
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

PAPERS = Path(__file__).resolve().parent.parent / "public" / "data" / "papers.json"

try:
    papers = json.loads(PAPERS.read_text(encoding="utf-8"))
except FileNotFoundError:
    print("papers.json 不存在，请先运行 collect_papers.py", file=sys.stderr)
    sys.exit(1)

required = {"id", "title", "authors", "published", "summary", "url", "source"}
ids = set()

for index, paper in enumerate(papers):
    missing = required - paper.keys()
    assert not missing, f"第 {index} 篇论文缺字段: {sorted(missing)}"
    assert paper["id"] not in ids, f"重复 id: {paper['id']}"
    assert urlparse(paper["url"]).scheme == "https", f"链接非 HTTPS: {paper['url']}"
    ids.add(paper["id"])

print(f"PAPER CHECK PASSED: {len(papers)} papers")
