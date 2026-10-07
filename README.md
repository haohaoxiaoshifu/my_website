# 郑好的个人网站

纯静态个人网站，由 AI Agent 按课程迭代构建：原生 HTML/CSS/JavaScript + Python 标准库构建脚本，
通过 GitHub / 极狐 GitLab 的 CI 自动部署到腾讯云 CloudBase 静态网站托管。

## 功能

- 个人首页：姓名、学校、专业、自我介绍、兴趣方向、邮箱；
- 关于我；
- Markdown 博客（自动生成列表页、文章页）；
- RSS 2.0 订阅源 `feed.xml`；
- RSS/Atom 聚合阅读器（订阅腾讯安全应急响应中心等）；
- Research Papers：自动收集 arXiv 最新论文；
- 个人 Wiki：Markdown + `[[双向链接]]` + 页面内关键词检索；
- 网站状态面板：构建时间、内容数量、自动检查结果。

## 目录结构

```
my_website/
├── .github/workflows/   # GitHub Actions 自动部署
├── .gitlab-ci.yml       # 极狐 GitLab CI 自动部署
├── .opencode/skills/    # 自定义 Skill：research-paper-collector
├── AGENTS.md            # 项目长期约束
├── assets/              # styles.css、app.js（构建时复制到 public/）
├── config/feeds.json    # RSS 订阅源配置
├── content/
│   ├── site.json        # 个人信息与导航（改信息从这里开始）
│   ├── pages/about.md   # 关于我
│   ├── posts/           # 博客 Markdown
│   └── wiki/            # Wiki Markdown
├── scripts/             # 构建与采集脚本（仅 Python 标准库）
└── public/              # 唯一被部署的目录
    ├── index.html
    ├── posts/  wiki/
    ├── feed.xml
    └── data/            # papers.json、rss-items.json、status.json 等
```

## 本地预览

```bash
# 1. （可选）重新采集论文和 RSS
python scripts/collect_papers.py --limit 10
python scripts/fetch_feeds.py

# 2. 构建站点（可重复执行，不会重复追加内容）
python scripts/build.py

# 3. 在 public 目录启动本地服务器
cd public
python -m http.server 8080
# 浏览器访问 http://localhost:8080
```

## 更新内容

- 改个人信息：编辑 `content/site.json`；
- 写博客：在 `content/posts/` 新增 md（含 title/date/description frontmatter）；
- 写 Wiki：在 `content/wiki/` 新增 md，用 `[[页面名]]` 建立双链；
- 加 RSS 订阅：在 `config/feeds.json` 增加 HTTPS 的 RSS/Atom 地址；
- 改论文方向：`python scripts/collect_papers.py --query 'all:"your topic"'`；
- 改完运行 `python scripts/build.py`，提交并 push，CI 会自动重新部署。

## 部署：腾讯云 CloudBase

1. 注册腾讯云并实名认证，开通 CloudBase，创建**免费体验**环境，记下环境 ID `TCB_ENV_ID`；
2. 在 [API 密钥管理](https://console.cloud.tencent.com/cam/capi) 创建 `TCB_SECRET_ID` / `TCB_SECRET_KEY`；
3. 把本仓库 push 到 GitHub 或极狐 GitLab；
4. 在平台的密钥/变量中填入上述三个值：
   - GitHub：Settings → Secrets and variables → Actions；
   - 极狐 GitLab：设置 → CI/CD → 变量；
5. push 到 `main` 分支即自动构建部署；CloudBase 控制台「静态网站托管」中可看到访问域名；
6. 拿到域名后，把 `content/site.json` 里的 `url` 改成 `https://你的域名`，重新提交，
   `feed.xml` 中的文章链接即为正式绝对地址。
