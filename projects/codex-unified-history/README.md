# Codex Unified History

把 Codex Desktop 在不同认证方式和不同 API provider 下产生的本地对话历史统一到同一个左侧历史列表。

> 适用场景：使用 CC Switch 在 Codex Desktop 中切换 ChatGPT 登录认证、自定义 API provider、不同供应商名称后，历史对话在左侧列表中消失、分散或重复。

## 解决什么问题

Codex Desktop 的本地历史会记录 `model_provider`。当你在 ChatGPT 登录认证和自定义 API provider 之间切换时，同一批本地对话可能因为 provider 不一致而不显示在当前左侧历史列表中。

本项目使用一个本地脚本把历史归属同步到当前 provider，并重建 `session_index.jsonl`，让历史在当前 Codex Desktop 中保持可见。

## 核心原则

- 不使用 provider shadow / 映射复制方案。
- 不复制对话制造重复历史。
- 不把自定义 provider 命名为内置保留 ID `openai`。
- 同步 `.jsonl` 时保留真实 mtime，避免旧对话被错误排到最新。
- 所有操作都在本地完成。
- 任何清理动作都应先备份。

## 文件结构

```text
scripts/codex_unified_history.py          # 核心同步脚本
scripts/codex_unified_history_agent.sh    # launchd 调用入口，带 fingerprint 跳过逻辑
scripts/install.sh                        # 安装 LaunchAgent
scripts/uninstall.sh                      # 卸载 LaunchAgent
scripts/dedupe_codex_history.py           # 可选：清理旧方案造成的重复历史
launchagents/com.example.codex-unified-history.plist
docs/article.md                           # 原理文章
docs/verification.md                      # 校验和排障命令
```

## 安装

```bash
git clone https://github.com/<your-name>/codex-unified-history.git
cd codex-unified-history
bash scripts/install.sh
```

安装后脚本会复制到：

```text
~/.codex/unified-history/
```

LaunchAgent 会写入：

```text
~/Library/LaunchAgents/com.local.codex-unified-history.plist
```

默认每 30 秒运行一次，并监听：

```text
~/.cc-switch/cc-switch.db
~/.codex/config.toml
~/.codex/state_5.sqlite
```

## 手动运行

```bash
~/.codex/unified-history/codex_unified_history_agent.sh
```

查看日志：

```bash
tail -20 ~/.codex/unified-history/unified-history.log
```

## 校验

```bash
sqlite3 ~/.codex/state_5.sqlite \
"select model_provider,count(*) from threads group by model_provider;"

wc -l ~/.codex/session_index.jsonl

launchctl print gui/$(id -u)/com.local.codex-unified-history
```

更多校验命令见 [docs/verification.md](docs/verification.md)。

## 可选：去重

如果你之前使用过 shadow / provider-display 这类复制方案，左侧可能出现大量重复对话。可以先 dry-run：

```bash
python3 scripts/dedupe_codex_history.py --dry-run
```

确认后执行：

```bash
python3 scripts/dedupe_codex_history.py
```

去重脚本会备份数据库、索引和被移出的 JSONL，不会直接销毁原始文件。

## 风险提示

这个项目会修改 Codex 的本地状态文件：

- `~/.codex/state_5.sqlite`
- `~/.codex/session_index.jsonl`
- `~/.codex/sessions/**/*.jsonl`
- `~/.codex/archived_sessions/**/*.jsonl`

请在使用前确认你能接受本地历史被整理。首次使用建议先备份整个 `~/.codex` 目录。

## 卸载

```bash
bash scripts/uninstall.sh
```

卸载只移除 LaunchAgent，不删除你的 Codex 历史。

