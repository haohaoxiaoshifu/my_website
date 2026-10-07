// 原生 JavaScript：加载同域 JSON 数据并渲染。不请求任何外部地址。
(function () {
  "use strict";

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  async function loadJSON(url) {
    var resp = await fetch(url, { cache: "no-store" });
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    return resp.json();
  }

  function showError(el, msg) {
    el.innerHTML = '<p class="error-box">数据加载失败：' + esc(msg) +
      "。如果是在 file:// 下直接打开，请先运行 <code>python -m http.server 8080</code>。</p>";
  }

  // ---------- Research Papers ----------
  async function renderPapers() {
    var el = document.getElementById("papers-list");
    var meta = document.getElementById("papers-meta");
    try {
      var papers = await loadJSON("data/papers.json");
      if (!papers.length) {
        el.innerHTML = '<p class="loading">暂无论文数据。</p>';
        return;
      }
      meta.textContent = "共 " + papers.length + " 篇 · 来源：arXiv（预印本，未经同行评审）";
      el.innerHTML = papers.map(function (p) {
        return '<article class="list-card">' +
          '<time datetime="' + esc(p.published) + '">' + esc(p.published) + "</time>" +
          '<h2><a href="' + esc(p.url) + '" target="_blank" rel="noopener noreferrer">' +
          esc(p.title) + "</a></h2>" +
          '<p class="paper-authors">' + esc(p.authors.slice(0, 4).join(", ")) +
          (p.authors.length > 4 ? " 等" : "") + "</p>" +
          '<p class="paper-summary">' + esc(p.summary) + "</p>" +
          '<p class="card-links">原文：<a href="' + esc(p.url) + '" target="_blank" rel="noopener noreferrer">' +
          esc(p.id) + "</a> · 来源：" + esc(p.source) + "</p>" +
          "</article>";
      }).join("");
    } catch (err) {
      showError(el, err.message);
    }
  }

  // ---------- RSS 聚合 ----------
  async function renderFeed() {
    var el = document.getElementById("rss-list");
    var meta = document.getElementById("rss-meta");
    try {
      var data = await loadJSON("data/rss-items.json");
      var items = data.items || [];
      var sources = (data.sources || []).map(function (s) {
        return '<a href="' + esc(s.url) + '" target="_blank" rel="noopener noreferrer">' +
          esc(s.title) + "</a>";
      }).join("、");
      meta.innerHTML = "采集于 " + esc((data.generated_at || "").replace("T", " ").slice(0, 19)) +
        " · 订阅源：" + sources;
      if (!items.length) {
        el.innerHTML = '<p class="loading">暂无订阅内容。</p>';
        return;
      }
      el.innerHTML = items.map(function (it) {
        return '<article class="list-card">' +
          '<time datetime="' + esc(it.published) + '">' + esc(it.published) + "</time>" +
          '<h2><a href="' + esc(it.link) + '" target="_blank" rel="noopener noreferrer">' +
          esc(it.title) + "</a></h2>" +
          '<p class="paper-authors">来自：' + esc(it.source) + "</p>" +
          (it.summary ? '<p class="paper-summary">' + esc(it.summary) + "</p>" : "") +
          "</article>";
      }).join("");
    } catch (err) {
      showError(el, err.message);
    }
  }

  // ---------- 状态面板 ----------
  async function renderStatus() {
    var el = document.getElementById("status-panel");
    try {
      var s = await loadJSON("data/status.json");
      var c = s.counts || {};
      var stats = [
        [s.pages, "HTML 页面"],
        [c.posts, "博客文章"],
        [c.wiki, "Wiki 页面"],
        [c.papers, "论文"],
        [c.rss_items, "RSS 内容"]
      ].map(function (x) {
        return '<div class="stat-card"><div class="num">' + esc(x[0]) +
          '</div><div class="label">' + esc(x[1]) + "</div></div>";
      }).join("");

      var checks = (s.checks || []).map(function (chk) {
        return '<li class="' + (chk.ok ? "ok" : "fail") + '">' +
          '<span class="check-status">' + (chk.ok ? "✓ 通过" : "✗ 失败") + "</span>" +
          "<strong>" + esc(chk.name) + "</strong>" +
          '<div class="check-detail">' + esc(chk.detail) + "</div></li>";
      }).join("");

      el.innerHTML =
        '<p class="data-meta">最近构建：' + esc(s.generated_at_display) + "</p>" +
        '<div class="status-grid">' + stats + "</div>" +
        '<h2>自动检查</h2><ul class="checks">' + checks + "</ul>";
    } catch (err) {
      showError(el, err.message);
    }
  }

  // ---------- Wiki 检索（RAG 的“检索”步骤，纯前端关键词匹配） ----------
  async function initWikiSearch() {
    var input = document.getElementById("wiki-search-input");
    var list = document.getElementById("wiki-search-results");
    if (!input || !list) return;
    var index = [];
    try {
      index = await loadJSON("../data/wiki-index.json");
    } catch (err) {
      list.className = "wiki-search-results has-query";
      list.innerHTML = '<li><span class="error-box">检索索引加载失败：' + esc(err.message) + "</span></li>";
      return;
    }

    function highlight(text, q) {
      var safe = esc(text);
      if (!q) return safe;
      try {
        var re = new RegExp("(" + q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")", "gi");
        return safe.replace(re, "<mark>$1</mark>");
      } catch (e) {
        return safe;
      }
    }

    input.addEventListener("input", function () {
      var q = input.value.trim().toLowerCase();
      list.className = "wiki-search-results has-query";
      if (!q) {
        list.innerHTML = "<li><small>输入关键词后在此显示证据片段。</small></li>";
        return;
      }
      var hits = index
        .filter(function (p) { return p.slug !== "index"; })
        .map(function (p) {
          var idx = p.text.toLowerCase().indexOf(q);
          var score = (p.title.toLowerCase().indexOf(q) !== -1 ? 2 : 0) + (idx !== -1 ? 1 : 0) +
            (p.tags.join(" ").toLowerCase().indexOf(q) !== -1 ? 1 : 0);
          var snippet = idx !== -1 ? p.text.slice(Math.max(0, idx - 30), idx + 90) : p.excerpt;
          return { p: p, score: score, snippet: snippet };
        })
        .filter(function (x) { return x.score > 0; })
        .sort(function (a, b) { return b.score - a.score; });

      if (!hits.length) {
        list.innerHTML = "<li><small>当前 Wiki 中没有足够依据，请换个关键词或补充新页面。</small></li>";
        return;
      }
      list.innerHTML = hits.map(function (x) {
        return "<li><a href=\"" + esc(x.p.slug) + ".html\">" + highlight(x.p.title, q) + "</a>" +
          "<br><small>更新于 " + esc(x.p.updated) + " · 标签 " + esc(x.p.tags.join(" / ")) +
          "<br>…" + highlight(x.snippet, q) + "…</small></li>";
      }).join("");
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var page = document.body.dataset.page;
    if (page === "papers") renderPapers();
    if (page === "rss") renderFeed();
    if (page === "status") renderStatus();
    if (page === "wiki") initWikiSearch();
  });
})();
