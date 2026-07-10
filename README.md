# 每日文献推送到 Telegram

每天定时从 **PubMed + bioRxiv/medRxiv** 抓取最新论文，按关键词过滤 →（可选）AI 相关性打分+中文摘要 → 推送到你的 Telegram。

```
config.yaml       ← 配置：关键词、来源开关、Telegram 凭证（最常改的文件）
main.py           ← 主程序
sources.py        ← PubMed / bioRxiv 抓取
telegram_push.py  ← Telegram 消息格式化与发送
run.sh            ← 定时任务入口脚本
com.vtmeilab.paperbot.plist ← macOS launchd 定时配置
state.json        ← 自动生成，记录已推送过的论文，避免重复
```

---

## 一次性设置（约 10 分钟）

### 1. 创建 Telegram 机器人拿 token
1. 在 Telegram 里搜索 **@BotFather**，发送 `/newbot`，按提示起名。
2. 它会给你一串 **bot token**，形如 `123456789:AAE...`，记下来。

### 2. 拿到你的 chat_id（消息要发给谁）
1. 先给你刚建的机器人发一句任意消息（比如 `hi`）。
2. 浏览器打开（把 `<TOKEN>` 换成你的 token）：
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. 在返回的 JSON 里找 `"chat":{"id":...}`，那个数字就是你的 **chat_id**。
   （想发到群里：把机器人拉进群，在群里发条消息，再看 getUpdates 里的负数群 id。）

### 3. 装依赖（用虚拟环境，干净）
```bash
cd /Users/tempaccount/VT_project/daily_paper_bot
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 4. 填配置
- 打开 `config.yaml`，把 `topics` 改成你真正关注的方向。
- 打开 `run.sh`，填上你的 token 和 chat_id（AI 打分还需 Anthropic key，见第 6 步）：
  ```bash
  export TELEGRAM_BOT_TOKEN="123456789:AAE..."
  export TELEGRAM_CHAT_ID="你的chat_id"
  ```

### 6.（可选）AI 相关性打分 + 中文摘要
命中关键词的论文再交给 Claude 打相关性分（0-10）并写一句中文总结，低分自动过滤、高分在前。
1. 去 https://console.anthropic.com 申请一个 API key（形如 `sk-ant-...`）。
2. 填进 `run.sh`：`export ANTHROPIC_API_KEY="sk-ant-..."`
3. 在 `config.yaml` 的 `ai:` 段里可调：
   - `enabled`: `true`/`false` 总开关（设 false 就纯关键词，不花钱）
   - `model`: 默认 `claude-opus-4-8`（最强）；想省钱换 `claude-haiku-4-5`（便宜约 5 倍）
   - `min_score`: 推送门槛（0-10），太杂调高、太少调低
   - `focus`: 你的研究方向描述，写得越清楚打分越准
   > 说明：AI 若失败或没配 key，会自动降级为“按关键词结果推送”，不会中断每日任务。

### 5. 先手动跑一次验证
```bash
# 只抓取、打印，不推送（看关键词命中情况）
.venv/bin/python main.py --dry-run

# 真正推送一次，去 Telegram 看有没有收到
TELEGRAM_BOT_TOKEN="123..." TELEGRAM_CHAT_ID="..." .venv/bin/python main.py
```

---

## 设置每天自动运行（二选一）

### 方式 A：cron（简单）
```bash
crontab -e
```
加一行（每天 08:30 运行，路径按你的实际改）：
```
30 8 * * * /Users/tempaccount/VT_project/daily_paper_bot/run.sh
```

### 方式 B：launchd（macOS 原生，推荐，睡眠错过也会补跑）
```bash
cd /Users/tempaccount/VT_project/daily_paper_bot
# 把占位符替换成真实路径
sed "s#__DIR__#$(pwd)#g" com.vtmeilab.paperbot.plist > ~/Library/LaunchAgents/com.vtmeilab.paperbot.plist
launchctl load ~/Library/LaunchAgents/com.vtmeilab.paperbot.plist
```
改时间：编辑 plist 里的 `Hour` / `Minute`，然后 `launchctl unload` 再 `load`。
停止：`launchctl unload ~/Library/LaunchAgents/com.vtmeilab.paperbot.plist`

---

## 日常维护
- **改关注方向**：编辑 `config.yaml` 的 `keywords`，无需重启任何东西，下次运行生效。
- **推送太多/太少**：调 `match_mode`（any/all）、`max_per_source`、`lookback_days`。
- **看日志**：`run.log`（cron/手动）或 `launchd.out.log` / `launchd.err.log`（launchd）。
- **重置去重**：删掉 `state.json` 会重新把近几天的论文都当作“新”推一遍。

## 安全提示
不要把填了真实 token 的 `run.sh` 提交到公开仓库。若要用 git，建议把 `run.sh`、`state.json`、`*.log` 加进 `.gitignore`。
