"""读取 config/feeds.json 中订阅的 RSS/Atom，规范化为 public/data/rss-items.json。

信任边界：外部 Feed 的标题、摘要、链接全部是不可信数据：
- 强制 HTTPS、限制超时(15s)与体积(2MB)；
- 摘要去除 HTML 标签并截断到 300 字，只作为文本展示；
- 单个订阅源失败不影响其他源；全部失败且存在旧数据时保留旧数据。
仅使用 Python 标准库。
"""
import json
import re
import sys
import html as html_mod
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "feeds.json"
OUTPUT = ROOT / "public" / "data" / "rss-items.json"

MAX_BYTES = 2 * 1024 * 1024
TIMEOUT = 15
SUMMARY_LIMIT = 300
ATOM = {"atom": "http://www.w3.org/2005/Atom"}


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def html_to_text(value):
    parser = _TextExtractor()
    try:
        parser.feed(value or "")
    except Exception:  # noqa: BLE001 - 外部 HTML 可能畸形，退化为正则去标签
        return re.sub(r"<[^>]+>", "", value or "")
    text = html_mod.unescape("".join(parser.parts))
    return re.sub(r"\s+", " ", text).strip()


def normalize_date(value):
    """尽力把 RFC822 / ISO 时间统一为 YYYY-MM-DD；无法解析返回空串。"""
    value = (value or "").strip()
    if not value:
        return ""
    try:
        return parsedate_to_datetime(value).date().isoformat()
    except (TypeError, ValueError):
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(value[:19] if "%z" in fmt or "Z" in fmt else value[:10],
                                     fmt).date().isoformat()
        except ValueError:
            continue
    return value[:10]


def fetch_raw(url):
    if not url.startswith("https://"):
        raise ValueError("只允许 HTTPS 订阅地址")
    request = Request(url, headers={"User-Agent": "zheng-hao-rss-reader/1.0"})
    with urlopen(request, timeout=TIMEOUT) as resp:
        data = resp.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("Feed 体积超过 2MB 限制")
    return data


def parse_rss(root, source):
    channel = root.find("channel")
    if channel is None:
        return []
    items = []
    for node in channel.findall("item"):
        link = (node.findtext("link") or "").strip()
        guid = (node.findtext("guid") or link).strip()
        items.append({
            "id": guid or link,
            "title": html_to_text(node.findtext("title")),
            "link": link,
            "published": normalize_date(node.findtext("pubDate")),
            "summary": html_to_text(node.findtext("description"))[:SUMMARY_LIMIT],
            "source": source["title"],
            "source_url": source["url"],
        })
    return items


def atom_link(entry):
    for link in entry.findall("atom:link", ATOM):
        if link.get("href") and (link.get("rel") in (None, "alternate")):
            return link.get("href")
    first = entry.find("atom:link", ATOM)
    return first.get("href") if first is not None else ""


def parse_atom(root, source):
    items = []
    for entry in root.findall("atom:entry", ATOM):
        link = atom_link(entry)
        raw_id = (entry.findtext("atom:id", namespaces=ATOM) or link).strip()
        date = entry.findtext("atom:published", namespaces=ATOM) or \
            entry.findtext("atom:updated", namespaces=ATOM)
        summary = entry.findtext("atom:summary", namespaces=ATOM) or \
            entry.findtext("atom:content", namespaces=ATOM) or ""
        items.append({
            "id": raw_id or link,
            "title": html_to_text(entry.findtext("atom:title", namespaces=ATOM)),
            "link": (link or "").strip(),
            "published": normalize_date(date),
            "summary": html_to_text(summary)[:SUMMARY_LIMIT],
            "source": source["title"],
            "source_url": source["url"],
        })
    return items


def parse_feed(raw, source):
    root = ET.fromstring(raw)
    tag = root.tag.lower()
    if tag.endswith("rss") or root.find("channel") is not None:
        return parse_rss(root, source)
    if tag.endswith("feed"):
        return parse_atom(root, source)
    raise ValueError("无法识别的 Feed 格式（非 RSS 2.0 / Atom 1.0）")


def main():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    sources, items, errors = [], [], []

    for source in config.get("feeds", []):
        try:
            raw = fetch_raw(source["url"])
            parsed = parse_feed(raw, source)
            sources.append({"title": source["title"], "url": source["url"], "items": len(parsed)})
            items.extend(parsed)
            print(f"OK  {source['title']}: {len(parsed)} items")
        except Exception as exc:  # noqa: BLE001 - 单源失败隔离
            errors.append({"source": source["title"], "error": str(exc)})
            print(f"ERR {source['title']}: {exc}", file=sys.stderr)

    # 按 id/link 去重，日期倒序
    deduped = {}
    for item in items:
        key = item["id"] or item["link"]
        if key and key not in deduped:
            deduped[key] = item
    result = sorted(deduped.values(), key=lambda x: x["published"], reverse=True)

    if not result and errors and OUTPUT.exists():
        old = json.loads(OUTPUT.read_text(encoding="utf-8"))
        old["errors"] = errors
        OUTPUT.write_text(json.dumps(old, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("ALL SOURCES FAILED, KEPT OLD DATA", file=sys.stderr)
        return 0

    payload = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "sources": sources,
        "items": result,
        "errors": errors,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"sources": len(sources), "items": len(result),
                      "errors": len(errors)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
