# shuchengcaoxin.github.io

Shucheng Cao（Bangli Cao）的个人研究主页，由 GitHub Pages 直接托管。

网站是纯静态 HTML/CSS，没有 Jekyll、Node 或编译步骤。主页的信息顺序固定为：

```text
Summary → News → Selected Work → Publications → Blog → Contact
```

## 主要文件

- `index.html`：主页内容
- `assets/css/site.css`：主页与 Blog 列表的共享视觉样式
- `blog/index.html`：Blog 列表
- `blog/<slug>/index.html`：各篇 Blog 正文
- `sitemap.xml`：搜索引擎页面清单
- `scripts/check_blog_news_sync.py`：检查每篇 Blog 是否同时出现在 News 和 sitemap
- `如何更新我的网站.md`：面向站点维护者的完整中文说明

## 本地预览

在 Windows PowerShell 中：

```powershell
cd D:\Work_Destiny\Internship_CABS\shuchengcaoxin.github.io
python -m http.server 8000 --bind 127.0.0.1
```

打开 <http://127.0.0.1:8000/>。结束预览时在 PowerShell 按 `Ctrl+C`。

## 发布前检查

```powershell
python scripts\check_blog_news_sync.py
git diff --check
git status -sb
```

Blog 发布规则：文章进入 `blog/index.html` 的同时，必须在主页 `#news` 中新增一条指向该文章的链接，并加入 `sitemap.xml`。
