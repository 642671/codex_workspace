# Codex Desktop 本地历史统一方案：让 API 和认证模式下的对话都显示在左侧

## 背景

在 Codex Desktop 中，如果通过 CC Switch 在 ChatGPT 登录认证和自定义 API provider 之间切换，可能会遇到一个现象：原来能看到的历史对话，在切换 provider 后不再出现在左侧。

这并不一定是对话丢了。更多时候，它们仍然保存在本地，只是当前视图按 provider 或索引读取时没有把它们展示出来。

## 问题根因

Codex 本地历史主要涉及几类文件：

```text
~/.codex/config.toml
~/.codex/state_5.sqlite
~/.codex/session_index.jsonl
~/.codex/sessions/**/*.jsonl
~/.codex/archived_sessions/**/*.jsonl
```

其中 `state_5.sqlite` 的 `threads` 表里有 `model_provider` 字段。切换 provider 后，如果历史记录仍属于旧 provider，就可能在当前左侧列表中不可见。

直接复制历史到另一个 provider 看似可以解决显示问题，但会制造重复 thread、重复 JSONL、重复索引，最后左侧会变得混乱。

## 当前方案

本方案不复制历史，而是把所有本地历史统一到当前 provider：

1. 从 `~/.codex/config.toml` 读取当前 Codex provider。
2. 如果当前是 ChatGPT 登录认证，使用内置 `openai`。
3. 如果当前是自定义 API provider，使用 CC Switch 显示名生成合法 provider ID。
4. 避免使用保留 ID `[model_providers.openai]`，防止 Codex 报错。
5. 更新 `state_5.sqlite` 中 `threads.model_provider`。
6. 更新 JSONL 中 `session_meta.model_provider`。
7. 从 JSONL 真实时间修复数据库时间。
8. 写回 JSONL 后恢复文件 mtime，避免左侧排序被污染。
9. 重建 `session_index.jsonl`。

## 为什么不能把自定义 provider 叫 openai

`openai` 是 Codex 内置保留 provider ID。自定义配置不能覆盖：

```toml
[model_providers.openai]
```

如果这样写，Codex 可能报错：

```text
model_providers contains reserved built-in provider IDs: openai
```

所以自定义 API provider 应该使用自己的名字，例如：

```toml
model_provider = "my_api"

[model_providers.my_api]
name = "my_api"
base_url = "https://example.com"
```

## 为什么要保留 JSONL mtime

Codex 在重建或展示历史时，可能会参考文件修改时间。如果脚本批量修改旧 JSONL，却不恢复 mtime，旧对话会被误认为刚刚更新，左侧排序就会乱。

所以脚本会先读取 JSONL 内部 timestamp，写回 provider 后再把文件 mtime 调回真实更新时间。

## 自动同步

项目通过 macOS LaunchAgent 自动触发：

```text
~/Library/LaunchAgents/com.local.codex-unified-history.plist
```

默认每 30 秒运行一次，并监听：

```text
~/.cc-switch/cc-switch.db
~/.codex/config.toml
~/.codex/state_5.sqlite
```

为了减少无意义写入，agent 会记录 fingerprint。相关文件没有变化时直接跳过。

## 去重策略

如果之前用过复制型方案，可能已经产生重复 thread。去重脚本使用保守规则：

- 以 `title + first_user_message + created_at` 判断同一批重复对话。
- 每组保留 JSONL 行数最多、文件最大、更新时间最新的一条。
- 其余记录从数据库和索引中移除。
- 被移出的 JSONL 移动到备份目录，不直接删除。
- 孤儿 JSONL 也移动到备份目录，避免未来重建索引时重新出现。

## 适用边界

这个方案适合本地 Codex Desktop 历史整理，不是云同步工具。换电脑使用时，应重新安装脚本和 LaunchAgent，不建议直接复制整份 `.codex`。

## 结论

核心思路很简单：不要复制历史，不要映射出第二份历史，而是让本地历史始终归属当前 provider，并保持索引、数据库、JSONL 和文件时间一致。

