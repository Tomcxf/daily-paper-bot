# 部署到 GitHub Actions（云端定时，不依赖你的电脑）

本机的 git 已经初始化并提交好了。你只需三步：建仓库 → 填 Secrets → 推上去。

## 前提说明
- `run.sh` 里有明文 token，已被 `.gitignore` 排除，**不会上传**。GitHub 上改用 Secrets。
- `state.json`（去重记录）会被提交，且每次运行后自动更新回仓库——这是云端去重的关键。
- `config.yaml` 里只有 `ENV:` 占位符，没有密钥，可安全公开。

## 第 1 步：在 GitHub 建一个空仓库
1. 打开 https://github.com/new
2. 起个名字（如 `daily-paper-bot`），**不要**勾选 "Add a README"（保持空仓库）。
3. 建好后复制它的地址，形如 `https://github.com/你的用户名/daily-paper-bot.git`。

## 第 2 步：填 Secrets（密钥）
在你新建的仓库页面：**Settings → Secrets and variables → Actions → New repository secret**，加这几个：

| Name | Value（从本机 `run.sh` 里复制，别写进任何会上传的文件）|
|------|-------|
| `TELEGRAM_BOT_TOKEN` | 你的 bot token（`run.sh` 里 `TELEGRAM_BOT_TOKEN` 那行）|
| `TELEGRAM_CHAT_ID` | 你的 chat_id（`run.sh` 里 `TELEGRAM_CHAT_ID` 那行）|
| `ANTHROPIC_API_KEY` | （可选，只有想开 AI 时才填）|

> ⚠️ 密钥只填进 GitHub 网页的 Secrets 输入框，**永远不要**写进 `config.yaml`、`DEPLOY_GITHUB.md` 等会被提交的文件。

## 第 3 步：把代码推上去
在终端里（把 URL 换成你自己的）：
```bash
cd /Users/tempaccount/VT_project/daily_paper_bot
git remote add origin https://github.com/你的用户名/daily-paper-bot.git
git branch -M main
git push -u origin main
```
> 推送时会让你登录 GitHub（浏览器授权或输入 Personal Access Token）。

## 第 4 步：验证
1. 仓库页面 → **Actions** 标签，能看到 "每日文献推送" 工作流。
2. 点进去 → **Run workflow**（手动触发一次测试），看是否成功、Telegram 是否收到。
3. 以后每天 13:00 UTC（≈美东 9 点）自动跑。

## 日常
- **改研究方向 / 参数**：改 `config.yaml`，`git commit` 后 `git push`，下次自动生效。
- **改推送时间**：改 `.github/workflows/daily.yml` 里的 `cron`（UTC 时间）。
- **看运行记录**：仓库 Actions 标签，每次运行的日志都在。
- **开 AI**：把 `config.yaml` 的 `ai.enabled` 改成 `true`，并在 Secrets 里加 `ANTHROPIC_API_KEY`。

## 仓库公开还是私有？
- **私有**（推荐）：只有你能看到。免费额度每月 2000 分钟 Actions，够用。
- **公开**：Actions 完全免费无限，但你的 `state.json`、config 谁都能看到（没有密钥，问题不大）。
