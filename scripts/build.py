"""构建脚本：把 content/ 下的 Markdown 与 site.json 构建成 public/ 静态网站。

可安全重复运行：所有产物均为整文件覆盖，生成前清理自己拥有的旧产物。
仅使用 Python 标准库。
"""
import json
import shutil
from datetime import datetime, timezone
from email.utils import formatdate
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape
import re

from common import (
    ASSETS, CONTENT, DATA, PUBLIC, load_site, parse_frontmatter,
    render_markdown, render_page, strip_tags, write_page,
)
import xml.etree.ElementTree as ET


def clean_generated():
    """只清理构建脚本拥有的产物；public/data 下的采集数据保留。"""
    for d in (PUBLIC / "posts", PUBLIC / "wiki"):
        if d.exists():
            shutil.rmtree(d)
    for f in ("feed.xml",):
        p = PUBLIC / f
        if p.exists():
            p.unlink()


def copy_assets():
    PUBLIC.mkdir(parents=True, exist_ok=True)
    for asset in ASSETS.iterdir():
        if asset.is_file():
            shutil.copyfile(asset, PUBLIC / asset.name)


def build_home(site):
    p = site["profile"]
    chips = "".join(
        f'<span class="chip">{html_escape(v)}</span>'
        for v in (p["school"], p["major"])
    )
    cards = "".join(
        f"""<li class="interest-card">
          <h3>{html_escape(it["name"])}</h3>
          <p>{html_escape(it["desc"])}</p>
        </li>"""
        for it in p["interests"]
    )
    body = f"""
    <section class="hero">
      <p class="hero-eyebrow">你好，我是</p>
      <h1 class="hero-name">{html_escape(p["name"])}</h1>
      <p class="hero-chips">{chips}</p>
      <p class="hero-intro">{html_escape(p["intro"])}</p>
      <p class="hero-contact"><a class="btn" href="mailto:{html_escape(site["email"])}">联系我：{html_escape(site["email"])}</a></p>
    </section>
    <section>
      <h2>兴趣方向</h2>
      <ul class="interest-grid">{cards}</ul>
    </section>
"""
    return render_page(site, "home", site["title"], body, depth=0, page="home",
                       description=site.get("description"))


def html_escape(s):
    from html import escape
    return escape(str(s), quote=False)


def build_about(site):
    raw = (CONTENT / "pages" / "about.md").read_text(encoding="utf-8")
    body = render_markdown(raw)
    return render_page(site, "about", "关于我", body, description=f"{site['author']}的个人介绍")


def load_posts():
    posts = []
    for md in sorted((CONTENT / "posts").glob("*.md")):
        meta, body = parse_frontmatter(md.read_text(encoding="utf-8"))
        posts.append({
            "slug": md.stem,
            "title": meta.get("title", md.stem),
            "date": meta.get("date", ""),
            "description": meta.get("description", ""),
            "body": body,
        })
    posts.sort(key=lambda x: x["date"], reverse=True)
    return posts


def build_blog(site, posts):
    items = "".join(
        f"""<article class="list-card">
          <time datetime="{p["date"]}">{p["date"]}</time>
          <h2><a href="posts/{p["slug"]}.html">{html_escape(p["title"])}</a></h2>
          <p>{html_escape(p["description"])}</p>
        </article>"""
        for p in posts
    )
    body = f"""
    <h1>博客</h1>
    <p class="page-lead">用 Markdown 写作，构建时自动生成页面。<a href="feed.xml">订阅 RSS</a>。</p>
    <div class="card-list">{items}</div>
"""
    write_page(PUBLIC / "blog.html",
               render_page(site, "blog", "博客", body, description="郑好的博客文章"))

    for p in posts:
        article = f"""
    <article class="post">
      <header class="post-header">
        <h1>{html_escape(p["title"])}</h1>
        <p class="post-meta"><time datetime="{p["date"]}">{p["date"]}</time> · {html_escape(site["author"])}</p>
      </header>
{render_markdown(p["body"])}
    </article>
    <p class="back-link"><a href="../blog.html">← 返回博客列表</a></p>
"""
        write_page(PUBLIC / "posts" / f"{p['slug']}.html",
                   render_page(site, "blog", p["title"], article, depth=1,
                               description=p["description"]))


def load_wiki_pages():
    pages = []
    for md in sorted((CONTENT / "wiki").glob("*.md")):
        meta, body = parse_frontmatter(md.read_text(encoding="utf-8"))
        pages.append({
            "slug": md.stem,
            "title": meta.get("title", md.stem),
            "updated": meta.get("updated", ""),
            "tags": meta.get("tags", []) if isinstance(meta.get("tags", []), list) else [meta.get("tags")],
            "body": body,
        })
    return pages


def build_wiki(site, pages):
    wiki_map = {p["slug"]: p["title"] for p in pages}
    dead_links = set()
    index_entries = []

    for p in pages:
        rendered = render_markdown(p["body"], wiki_map=wiki_map)
        # 基于原文收集 [[slug]] 并检查死链
        for raw in re.findall(r"\[\[([^\[\]|]+)(?:\|[^\[\]]+)?\]\]", p["body"]):
            if raw.strip() not in wiki_map:
                dead_links.add((p["slug"], raw.strip()))
        tags = "".join(f'<span class="tag">{html_escape(t)}</span>' for t in p["tags"])
        is_index = p["slug"] == "index"
        search_box = """
    <div class="wiki-search">
      <label for="wiki-search-input">检索 Wiki（RAG 第一步：先找证据）</label>
      <input id="wiki-search-input" type="search" placeholder="输入关键词，例如：Agent、回滚、RSS">
      <ul id="wiki-search-results" class="wiki-search-results"></ul>
    </div>
""" if is_index else ""
        body = f"""
{search_box}
    <article class="post wiki-page" data-slug="{p["slug"]}">
      <header class="post-header">
        <h1>{html_escape(p["title"])}</h1>
        <p class="post-meta">更新于 {p["updated"]} · {tags}</p>
      </header>
{rendered}
    </article>
"""
        write_page(PUBLIC / "wiki" / f"{p['slug']}.html",
                   render_page(site, "wiki", p["title"], body, depth=1, page="wiki",
                               description=f"Wiki：{p['title']}"))
        plain = strip_tags(rendered)
        index_entries.append({
            "slug": p["slug"],
            "title": p["title"],
            "updated": p["updated"],
            "tags": p["tags"],
            "excerpt": plain[:120],
            "text": plain,
        })

    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "wiki-index.json").write_text(
        json.dumps(index_entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return dead_links


def build_feed(site, posts):
    base = site["url"].rstrip("/")
    items_xml = []
    for p in posts:
        link = f"{base}/posts/{p['slug']}.html"
        desc = p["description"] or strip_tags(render_markdown(p["body"]))[:120]
        try:
            dt = datetime.strptime(p["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            pub = formatdate(dt.timestamp(), usegmt=True)
        except ValueError:
            pub = formatdate(usegmt=True)
        items_xml.append(f"""    <item>
      <title>{xml_escape(p["title"])}</title>
      <link>{xml_escape(link)}</link>
      <guid isPermaLink="true">{xml_escape(link)}</guid>
      <pubDate>{pub}</pubDate>
      <description>{xml_escape(desc)}</description>
    </item>""")

    now_rfc = formatdate(usegmt=True)
    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>{xml_escape(site["title"])}</title>
    <link>{xml_escape(base)}/</link>
    <description>{xml_escape(site.get("description", ""))}</description>
    <language>zh-CN</language>
    <lastBuildDate>{now_rfc}</lastBuildDate>
{chr(10).join(items_xml)}
  </channel>
</rss>
"""
    write_page(PUBLIC / "feed.xml", feed)
    ET.fromstring(feed)  # 解析失败会直接抛异常，阻止“成功构建”
    return len(posts)


def skeleton(site, key, title, lead, inner, page, description=None):
    body = f"""
    <h1>{title}</h1>
    <p class="page-lead">{lead}</p>
{inner}
"""
    write_page(PUBLIC / {"papers": "papers.html", "rss": "rss.html", "status": "status.html"}[key],
               render_page(site, key, title, body, page=page, description=description))


def build_data_pages(site):
    skeleton(
        site, "papers", "Research Papers",
        "构建时自动收集 arXiv 最新论文，以原始摘要展示，不猜测结论。",
        """
    <p id="papers-meta" class="data-meta"></p>
    <div id="papers-list" class="card-list"><p class="loading">正在加载论文数据…</p></div>
""", "papers", "arXiv 最新论文收集")

    skeleton(
        site, "rss", "RSS 订阅",
        "聚合我关注的外部内容。外部内容只作文本展示，不会被当作指令执行。",
        """
    <p id="rss-meta" class="data-meta"></p>
    <div id="rss-list" class="card-list"><p class="loading">正在加载订阅内容…</p></div>
""", "rss", "RSS/Atom 订阅聚合")

    skeleton(
        site, "status", "网站状态",
        "可观测性面板：最近一次构建的时间、内容数量与自动检查结果。",
        """
    <div id="status-panel"><p class="loading">正在加载状态数据…</p></div>
""", "status", "网站构建状态与检查结果")


def build_status(site, posts, wiki_pages, dead_links, feed_ok):
    checks = []

    # feed.xml 校验
    checks.append({"name": "feed.xml XML 解析", "ok": feed_ok,
                   "detail": "RSS 2.0 可被 XML 解析器解析" if feed_ok else "解析失败"})

    # Wiki 死链
    checks.append({
        "name": "Wiki 双向链接检查",
        "ok": len(dead_links) == 0,
        "detail": "无死链" if not dead_links else "死链：" + ", ".join(f"{a}→{b}" for a, b in dead_links),
    })

    # 论文数据校验
    paper_count = 0
    papers_file = DATA / "papers.json"
    papers_ok = True
    papers_detail = "暂无数据，采集脚本尚未运行"
    required = {"id", "title", "authors", "published", "summary", "url", "source"}
    if papers_file.exists():
        try:
            papers = json.loads(papers_file.read_text(encoding="utf-8"))
            paper_count = len(papers)
            ids = set()
            for i, paper in enumerate(papers):
                missing = required - paper.keys()
                assert not missing, f"第 {i} 篇缺字段 {sorted(missing)}"
                assert paper["id"] not in ids, f"重复 id：{paper['id']}"
                ids.add(paper["id"])
            papers_ok = True
            papers_detail = f"{paper_count} 篇论文字段完整、id 无重复"
        except Exception as exc:  # noqa: BLE001 - 检查结果需要写入状态面板
            papers_ok = False
            papers_detail = str(exc)
    checks.append({"name": "论文数据结构检查", "ok": papers_ok, "detail": papers_detail})

    # RSS 聚合数据校验
    rss_count = 0
    rss_sources = 0
    rss_ok = True
    rss_detail = "暂无数据，采集脚本尚未运行"
    rss_file = DATA / "rss-items.json"
    if rss_file.exists():
        try:
            data = json.loads(rss_file.read_text(encoding="utf-8"))
            rss_sources = len(data.get("sources", []))
            rss_count = len(data.get("items", []))
            for item in data.get("items", []):
                assert item.get("title") and item.get("link"), "条目缺 title/link"
            rss_ok = True
            rss_detail = f"{rss_sources} 个订阅源，{rss_count} 条内容"
        except Exception as exc:  # noqa: BLE001
            rss_ok = False
            rss_detail = str(exc)
    checks.append({"name": "RSS 聚合数据检查", "ok": rss_ok, "detail": rss_detail})

    generated_at = datetime.now().astimezone()
    html_count = len(list(PUBLIC.rglob("*.html")))
    status = {
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "generated_at_display": generated_at.strftime("%Y-%m-%d %H:%M:%S %z"),
        "pages": html_count,
        "counts": {
            "posts": len(posts),
            "wiki": len(wiki_pages),
            "papers": paper_count,
            "rss_items": rss_count,
            "rss_sources": rss_sources,
        },
        "checks": checks,
    }
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return status


def main():
    clean_generated()
    copy_assets()

    site = load_site()
    write_page(PUBLIC / "index.html", build_home(site))
    write_page(PUBLIC / "about.html", build_about(site))

    posts = load_posts()
    build_blog(site, posts)

    wiki_pages = load_wiki_pages()
    dead_links = build_wiki(site, wiki_pages)

    feed_ok = True
    try:
        build_feed(site, posts)
    except ET.ParseError:
        feed_ok = False
        raise

    build_data_pages(site)
    status = build_status(site, posts, wiki_pages, dead_links, feed_ok)

    print("BUILD OK")
    print(json.dumps({
        "pages": status["pages"],
        "posts": len(posts),
        "wiki": len(wiki_pages),
        "papers": status["counts"]["papers"],
        "rss_items": status["counts"]["rss_items"],
        "checks_failed": [c["name"] for c in status["checks"] if not c["ok"]],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
