# GitHub Radar

GitHub Daily Trending 情报日报。支持抓取、规则分类、静态 HTML、搜索筛选、历史存档，以及 GitHub Actions 每日生成和 GitHub Pages 发布。

## 开始使用

需要 Python 3.11+ 和 [uv](https://docs.astral.sh/uv/)。在项目目录运行：

```sh
uv sync
uv run github-radar generate
```

打开 `site/index.html` 查看最新日报，无需启动网站服务。每篇报告自带 CSS、交互脚本和数据，断网时仍可阅读、筛选；作者头像需要网络，加载失败显示首字母。`site/archive.html` 是历史索引。

默认采集全领域 Daily Trending 前 20 项，页面优先展示规则识别的 AI 项目。左侧名次始终是原始榜单名次。项目简介保留来源原文，中文解读将在 V2 接入。

## 配置

修改 `config.toml` 中的抓取数量、默认展示顺序和分类关键词。分类使用仓库名称、简介、topics，保留命中依据；规则分类可能有误，可通过调整关键词改善。

GitHub API Token 可选，能够降低匿名 API 限流的影响。只设置环境变量 `GITHUB_TOKEN`，不要写入代码或报告。程序只将它发送到 `api.github.com`；不读取本地 `.env` 文件。

```sh
uv run github-radar generate --no-api
uv run github-radar rebuild
uv run github-radar generate --output /path/to/another-site --data-dir /path/to/data
```

`--no-api` 跳过元数据补充并标记数据提示；`rebuild` 完全使用保存的 JSON，不访问网络、不改变采集时间。配置错误、空榜单、解析失败或渲染失败不会覆盖上一份成功页面。未知 Star 显示“暂无数据”，零显示为零。任务存在数据提示时仍生成可读日报，在页顶查看详细提示；致命失败返回退出码 1。

## 存档

| 路径 | 内容 |
| --- | --- |
| `data/reports/YYYY-MM-DD.json` | 可复现的日报数据，持久保留 |
| `data/sources/YYYY-MM-DD.html` | 同次采集的 Trending 原始响应，用于核对 |
| `site/index.html` | 最新保存的日报 |
| `site/reports/YYYY-MM-DD.html` | 按日期生成的页面 |
| `site/archive.html` | 成功存档的日期索引 |

报告日期按 Asia/Shanghai 的实际采集时间生成。同日重跑更新同一日期，多日运行保留历史；页面显示实际快照日期，不伪装成今天的数据。生成目录带有标识文件，程序拒绝覆盖其他已有目录。写入锁目前使用 macOS / Linux 的文件锁。

每次先校验并渲染全部页面，再替换产物；普通写入错误会恢复旧数据。数据和页面是不同路径，断电或强制杀进程不具备跨目录事务保证，可通过 `rebuild` 从有效存档恢复页面。

## 开发验证

```sh
uv run pytest
node --test tests/filters.test.cjs
uv run ruff check .
uv run ruff format --check .
```

抓取使用网页榜单，REST API 只补充仓库元数据。不能把 Search API 或总 Star 的变化当成官方每日 Trending。

## 每日自动发布

1. 将项目上传到 GitHub 公开仓库，默认分支使用 `main`，保留 `uv.lock`。
2. 在仓库 Settings → Pages → Build and deployment 中选择 **GitHub Actions**。
3. 在 Actions 中打开 **Daily Report**，点击 **Run workflow**，选择默认分支。
4. 首次运行成功后，从任务的 `github-pages` 环境链接打开网站。

默认每天北京时间 **08:17** 执行，工作流使用 UTC `00:17`。GitHub 定时任务可能延迟，高负载时可能跳过；公开仓库连续 60 天无活动会停用定时任务。停用后需要在 Actions 中重新启用。详见 [GitHub 定时任务说明](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)。这不是精确到分钟的调度服务。

无需配置个人 Token 或 OpenAI Key。任务内置的 `GITHUB_TOKEN` 用于补充仓库元数据、保存历史和部署；如果组织策略禁用了写权限或 Pages，需要管理员放行。Pages 环境只允许默认分支部署，其他分支手动触发会跳过生成。

**历史保存方式：**源代码在 `main`，日报 JSON 和原始网页在独立的 `report-data` 分支。每次先取回历史、生成全部页面，再保存新快照和发布。历史不依赖缓存，也不会因 Actions 产物过期而丢失。首次运行使用代码中的现有 JSON 作为种子；同日重跑更新快照，多日运行保留日期。`report-data` 不是网站发布分支，不要修改其结构或删除它。

**失败处理：**远程历史读取失败、数据无效、抓取失败、渲染失败或历史推送冲突都会停止发布，线上保留上一版。Pages 部署失败时，新日报已经保存在 `report-data`，可手动重跑。请在 Actions 查看失败步骤；部分 API 补充失败仍会发布，并在日报内保留数据提示。工作流不会使用强制推送。

**代码检查：**`Checks` 在 `main` 更新和 Pull Request 时验证 Python、交互脚本及静态重建，只有只读权限。`Daily Report` 发布前也执行同样的检查。修改代码不会自动采集，验证通过后可手动运行日报或等待下一次定时任务。

下载远程历史后可离线重建：

```sh
uv run python -m github_radar.history restore \
  --remote https://github.com/OWNER/REPO.git \
  --checkout /tmp/radar-history-new
uv run github-radar rebuild
```

`--checkout` 必须是尚不存在的目录，并且不能与 `data` 重叠。恢复只读操作无需写权限；`save` 仅供发布任务使用，会提交并推送日报快照。历史 JSON 与原始网页均为公开数据，请勿在这些目录存放私密内容。

## 后续版本

V2：读取 README，用 AI 生成中文摘要、应用场景与带证据的价值分析。当前版本无需 OpenAI Key。

设计资料位于 `docs/superpowers/specs/`，交互设计稿位于 `docs/design/`。正式日报不包含演示项目数据。
