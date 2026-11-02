# GitHub 与网页发布说明

项目代码和网页可放在同一 GitHub 仓库。网页由已生成的 HTML、CSV 和 Excel 构成，不需要服务器数据库或访问者安装 Python。

## 发布内容

执行 `python tools/prepare_publication.py` 后得到：

- `publication/repository/`：可审阅的完整仓库副本。
- `publication/repository/docs/`：GitHub Pages 静态网站，首页为 `index.html`。
- `publication/github_release.zip`：相同内容的压缩包。
- 副本内的 `PUBLICATION_MANIFEST.json`：逐文件 SHA-256 与大小。

脚本先验证输出一致性，再按明确文件清单复制。它不创建 Git 提交、不连接远端、不部署网站。发布范围仅为本项目代码、公开原始数据、方法说明和已验证的输出；不包含上级工作区内容、环境文件、运行库或历史打包文件。

## GitHub Pages 配置

将仓库副本提交到获准发布的公开仓库后，在 **Settings → Pages** 选择 **Deploy from a branch**，分支选择 `main`，目录选择 `/docs`，保存并等待部署完成。以 GitHub 实际返回的地址为准，确认首页、项目说明、报告和下载入口可访问后，再将地址写入 README 和求职材料。

官方说明：[配置 GitHub Pages 发布来源](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)。

## 更新方式

调整分析参数后需重新运行分析并导出同批 Excel；只调整展示用语时可执行 `python run_project.py --presentation-only`。随后重新生成发布副本，检查差异并更新仓库。浏览器内切换场景或筛选品种不会修改原始数据。

完成本地打包不代表已经上线。公开部署和 Git 提交应遵循仓库所有者的授权。
