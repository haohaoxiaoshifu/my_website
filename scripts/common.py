"""公共工具：路径、站点配置、Markdown 渲染、HTML 页面骨架。仅使用 Python 标准库。"""
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
PUBLIC = ROOT / "public"
DATA = PUBLIC / "data"
ASSETS = ROOT / "assets"


def load_site():
    return json.loads((CONTENT / "site.json").read_text(encoding="utf-8"))


def parse_frontmatter(text):
    """返回 (meta_dict, body_str)。meta 使用极简 key: value 与 [a, b] 解析，够用即可。"""
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text
    meta = {}
    for line in lines[1:end]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            value = [v.strip().strip("'\"") for v in value[1:-1].split(",") if v.strip()]
            meta[key] = value
        else:
            meta[key] = value.strip("'\"")
    return meta, "\n".join(lines[end + 1:]).lstrip("\n")


def _inline(text, wiki_map=None):
    """先转义，再替换行内代码、Wiki 双链、链接、粗体。"""
    text = html.escape(text, quote=False)
    placeholders = {}

    def stash(kind, inner):
        key = f"\x00{kind}{len(placeholders)}\x00"
        placeholders[key] = inner
        return key

    # 行内代码
    def code_repl(m):
        return stash("C", f"<code>{m.group(1)}</code>")

    text = re.sub(r"`([^`]+)`", code_repl, text)

    # Wiki 双向链接 [[slug]] 或 [[slug|显示文本]]
    if wiki_map is not None:
        def wiki_repl(m):
            inner = m.group(1)
            if "|" in inner:
                slug, label = inner.split("|", 1)
            else:
                slug = inner
                label = None
            slug = slug.strip()
            label = html.escape((label or wiki_map.get(slug, slug)).strip())
            cls = "wikilink" if slug in wiki_map else "wikilink wikilink-missing"
            return stash("C", f'<a class="{cls}" href="{slug}.html">{label}</a>')

        text = re.sub(r"\[\[([^\[\]]+)\]\]", wiki_repl, text)

    # 普通链接 [text](url)
    def link_repl(m):
        label, url = m.group(1), m.group(2)
        if not re.match(r"^(https?|mailto):/\?/?[^\s]+$", url) and not url.startswith("mailto:"):
            if not re.match(r"^[A-Za-z0-9_./#-]+$", url):
                return m.group(0)
        return stash("C", f'<a href="{url}">{label}</a>')

    text = re.sub(r"\[([^\[\]]+)\]\(([^)\s]+)\)", link_repl, text)

    # 粗体
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)

    for key, value in placeholders.items():
        text = text.replace(key, value)
    return text


def render_markdown(md, wiki_map=None):
    """把 Markdown 渲染为 HTML 片段。支持：围栏代码块、标题、hr、引用、有序/无序列表、段落。"""
    lines = md.splitlines()
    out = []
    i = 0
    n = len(lines)

    def is_list_item(s):
        return re.match(r"^\s*([-*+]|\d+\.)\s+", s)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # 围栏代码块
        fence = re.match(r"^```(\w*)\s*$", stripped)
        if fence:
            lang = fence.group(1)
            code = []
            i += 1
            while i < n and not re.match(r"^```\s*$", lines[i].strip()):
                code.append(html.escape(lines[i], quote=False))
                i += 1
            i += 1  # 跳过结束围栏
            cls = f' class="language-{lang}"' if lang else ""
            out.append(f"<pre><code{cls}>{chr(10).join(code)}</code></pre>")
            continue

        # 标题
        h = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if h:
            level = len(h.group(1))
            out.append(f"<h{level}>{_inline(h.group(2), wiki_map)}</h{level}>")
            i += 1
            continue

        # 分隔线
        if re.match(r"^(-{3,}|\*{3,})\s*$", stripped):
            out.append("<hr>")
            i += 1
            continue

        # 引用块
        if stripped.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            out.append("<blockquote>" + _inline("\n".join(buf), wiki_map).replace("\n", "<br>") + "</blockquote>")
            continue

        # 列表（有序/无序）
        if is_list_item(stripped):
            ordered = bool(re.match(r"^\s*\d+\.", stripped))
            tag = "ol" if ordered else "ul"
            items = []
            while i < n and is_list_item(lines[i].strip()):
                item = re.sub(r"^\s*([-*+]|\d+\.)\s+", "", lines[i].strip())
                items.append(f"<li>{_inline(item, wiki_map)}</li>")
                i += 1
            out.append(f"<{tag}>" + "".join(items) + f"</{tag}>")
            continue

        # 普通段落（连续非空行合并）
        buf = [stripped]
        i += 1
        while i < n and lines[i].strip() and not re.match(r"^(#{1,6}\s|```|>|\s*([-*+]|\d+\.)\s|-{3,}\s*$)", lines[i].strip()):
            buf.append(lines[i].strip())
            i += 1
        out.append("<p>" + _inline(" ".join(buf), wiki_map) + "</p>")

    return "\n".join(out)


def strip_tags(fragment):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", fragment)).strip()


def render_page(site, nav_key, title, body, depth=0, page="", description=None):
    """生成完整 HTML 页面。depth 为页面对 public 根目录的层级深度。"""
    prefix = "../" * depth
    nav_links = []
    for item in site["nav"]:
        href = prefix + item["href"]
        if item["key"] == nav_key:
            nav_links.append(
                f'<a class="nav-link" href="{href}" aria-current="page">{item["label"]}</a>'
            )
        else:
            nav_links.append(f'<a class="nav-link" href="{href}">{item["label"]}</a>')

    desc = description or site.get("description", "")
    email = site["email"]
    full_title = title if nav_key == "home" else f"{title} - {site['title']}"
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(full_title)}</title>
  <meta name="description" content="{html.escape(desc)}">
  <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ctext y='.9em' font-size='90'%3E%F0%9F%9B%A1%EF%B8%8F%3C/text%3E%3C/svg%3E">
  <link rel="alternate" type="application/rss+xml" title="{html.escape(site['title'])} RSS" href="{prefix}feed.xml">
  <link rel="stylesheet" href="{prefix}styles.css">
</head>
<body data-page="{page}">
  <header class="site-header">
    <div class="container nav-bar">
      <a class="brand" href="{prefix}index.html">{html.escape(site["author"])}<span class="brand-dot">.dev</span></a>
      <nav class="site-nav" aria-label="主导航">
        {"".join(nav_links)}
      </nav>
    </div>
  </header>
  <main class="container">
{body}
  </main>
  <footer class="site-footer">
    <div class="container">
      <p>&copy; 2026 {html.escape(site["author"])} · <a href="mailto:{html.escape(email)}">{html.escape(email)}</a></p>
      <p class="footer-sub">由 AI Agent 协作构建 · 托管于腾讯云 CloudBase</p>
    </div>
  </footer>
  <script src="{prefix}app.js" defer></script>
</body>
</html>
"""


def write_page(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
