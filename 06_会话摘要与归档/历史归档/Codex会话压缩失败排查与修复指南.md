# Codex 会话压缩失败排查与修复指南

## 1. 文档定位

这份文档用于解决以下一类问题：

- Codex 聊天会话上下文过多
- 聊天视图中多智能体分析内容过长
- 点击压缩后失败
- 日志里出现 `remote compact`、`responses/compact`、`stream disconnected before completion` 等报错

这不是业务测试规则文档，也不是研发代码设计文档。  
它属于**本地工具操作手册**，用于你后续自己排查和修复 Codex 会话上下文问题。

## 2. 为什么这样命名

当前建议命名为：

- `Codex会话压缩失败排查与修复指南.md`

这样命名的原因是：

- 和当前工作区 `00` 到 `08` 的文档命名方式保持一致，后续查找成本低
- 标题里直接包含“Codex”“会话”“压缩失败”“排查”“修复”几个关键词，后续一眼就知道用途
- 这份文档的重点是“什么时候压缩失败、为什么失败、怎么修”，不是泛泛而谈的工具介绍

## 3. 为什么放在工作区根目录

当前建议放在：

- 工作区根目录：`D:\AI_workspace\codex`

原因如下：

- 你现在的核心共享文档都在根目录，后续自己查看最顺手
- 这类文档属于“常查手册”，不适合埋到很深的子目录
- 根目录文档适合做稳定入口，脚本则放到 `tools` 目录，职责更清楚

因此当前建议的结构是：

- 文档放根目录
- 执行脚本放 `tools`

## 4. 当前配套脚本位置

当前已经配套落地的脚本有：

- 文档：`D:\AI_workspace\codex\协作文档库\06_会话摘要与归档\历史归档\Codex会话压缩失败排查与修复指南.md`
- 主脚本：`D:\AI_workspace\codex\tools\codex_session_doctor.js`
- 便捷入口：`D:\AI_workspace\codex\tools\codex_session_doctor.cmd`

说明：

- `codex_session_doctor.js` 是实际执行逻辑
- `codex_session_doctor.cmd` 是给你自己更方便调用的入口
- 因为当前机器的 PowerShell 执行策略会拦截 `npm.ps1`，所以后续**优先使用 `.cmd` 或 `node` 直调**，不要优先依赖 `npm run`

## 5. 适用场景

出现以下现象时，优先查看本手册并使用配套脚本：

- 某条 Codex 会话明显特别长
- 会话里出现了大量截图、长日志、长补丁、长工具输出
- 点击压缩后没有成功
- 恢复旧会话时明显卡顿
- 同一条会话反复提示 compact 失败
- 会话路径对应的 `rollout*.jsonl` 文件体积异常大

## 6. 压缩失败的高风险来源

当前已确认最容易把会话压缩搞失败的内容包括：

- 内嵌截图 `data:image/...base64`
- 超长 `apply_patch` 输入内容
- 超长工具输出
- `patch_apply_end.changes` 里带了整段文件内容
- 多轮多智能体分析中持续堆积的大块上下文

要注意：

- 不是“聊天轮次多”本身一定会坏
- 真正高风险的是“大轮次 + 大块二进制图片 + 超长工具输出 + 大补丁文本”叠加

## 7. 使用前检查

正式执行前，先确认以下环境：

- 当前机器能运行 `node`
- 当前机器能运行 `sqlite3`
- Codex 本地数据目录存在：`C:\Users\当前用户名\.codex`

你可以先执行：

```bat
node -v
sqlite3 --version
```

如果 `sqlite3` 不在 PATH 里，需要先把它加到环境变量，或者手工指定会话文件路径执行文件模式。

## 8. 推荐使用方式

后续推荐优先使用下面两种方式：

### 方式一：直接用 `.cmd`

这是最推荐的方式，命令更短，也不容易受 PowerShell 策略影响。

```bat
D:\AI_workspace\codex\tools\codex_session_doctor.cmd list --title "多智能体分析"
```

```bat
D:\AI_workspace\codex\tools\codex_session_doctor.cmd scan --thread-id 线程ID
```

```bat
D:\AI_workspace\codex\tools\codex_session_doctor.cmd repair --thread-id 线程ID
```

### 方式二：直接用 `node`

```bat
node D:\AI_workspace\codex\tools\codex_session_doctor.js list --title "多智能体分析"
```

```bat
node D:\AI_workspace\codex\tools\codex_session_doctor.js scan --thread-id 线程ID
```

```bat
node D:\AI_workspace\codex\tools\codex_session_doctor.js repair --thread-id 线程ID
```

## 9. 标准操作流程

### 第一步：先按标题找线程

```bat
D:\AI_workspace\codex\tools\codex_session_doctor.cmd list --title "多智能体分析"
```

预期结果：

- 返回线程 `id`
- 返回线程标题
- 返回对应 `rolloutPath`
- 返回 `tokensUsed`

如果已经知道线程 ID，可以直接跳到第二步。

### 第二步：扫描会话风险

```bat
D:\AI_workspace\codex\tools\codex_session_doctor.cmd scan --thread-id 019db140-5534-7353-b39d-d93ea62219b5
```

重点看以下字段：

- `bytes`
- `dataImageCount`
- `longApplyPatchInputs`
- `longFunctionOutputs`
- `longExecOutputs`
- `longPatchChangeContents`
- `topLargeLines`

### 第三步：判断是否需要修复

满足以下任一条件，通常就建议修复：

- `dataImageCount > 0`
- `longApplyPatchInputs > 0`
- `longFunctionOutputs > 0`
- `longExecOutputs > 0`
- `longPatchChangeContents > 0`
- `bytes` 明显偏大，而且会话已经发生压缩失败

### 第四步：执行修复

```bat
D:\AI_workspace\codex\tools\codex_session_doctor.cmd repair --thread-id 019db140-5534-7353-b39d-d93ea62219b5
```

脚本会自动执行：

1. 备份原始会话文件
2. 生成修复版文件
3. 尝试直接回写原始会话文件

### 第五步：回到 Codex 验证

修复后建议这样验证：

1. 先切换到别的聊天线程
2. 再切回目标线程
3. 重新尝试压缩
4. 如果界面没刷新，重启 Codex 后再试

## 10. 各命令说明

### `list`

用途：

- 按标题查找最近线程

示例：

```bat
D:\AI_workspace\codex\tools\codex_session_doctor.cmd list --title "压缩失败" --limit 10
```

### `scan`

用途：

- 扫描某条会话的风险项

线程模式：

```bat
D:\AI_workspace\codex\tools\codex_session_doctor.cmd scan --thread-id 线程ID
```

文件模式：

```bat
D:\AI_workspace\codex\tools\codex_session_doctor.cmd scan --file "C:\Users\qishi\.codex\sessions\...\rollout-xxx.jsonl"
```

### `repair`

用途：

- 自动备份并修复高风险上下文内容

线程模式：

```bat
D:\AI_workspace\codex\tools\codex_session_doctor.cmd repair --thread-id 线程ID
```

文件模式：

```bat
D:\AI_workspace\codex\tools\codex_session_doctor.cmd repair --file "C:\Users\qishi\.codex\sessions\...\rollout-xxx.jsonl"
```

## 11. 修复后预期结果

正常情况下，修复后会看到以下结果：

- 会话文件体积下降
- `dataImageCount` 归零
- 长工具输出数量下降或归零
- 长补丁输入数量下降或归零
- 原始文件旁边出现 `.bak-时间戳` 备份
- 原始文件可以继续被 Codex 正常读取

## 12. 回滚方式

如果修复后你想回滚，直接把备份文件拷回原始文件即可。

典型文件形式如下：

- 原始文件：`rollout-xxxx.jsonl`
- 备份文件：`rollout-xxxx.jsonl.bak-20260423-070325`

回滚示例：

```bat
copy /Y "原始备份文件路径" "原始 rollout 文件路径"
```

## 13. 常见异常与处理

### 异常一：`npm run` 无法执行

现象：

- PowerShell 提示 `npm.ps1 cannot be loaded because running scripts is disabled`

处理：

- 不用 `npm run`
- 改用 `.cmd` 或 `node` 直调

### 异常二：提示找不到 `sqlite3`

现象：

- 执行时报 `sqlite3` 不存在

处理：

- 先把 `sqlite3` 加到 PATH
- 或者直接改用 `--file` 模式，绕开线程 ID 查询

### 异常三：修复时原始文件无法覆盖

现象：

- 输出里 `replacedOriginal` 为 `false`

处理：

1. 先关闭或切出目标会话
2. 必要时重启 Codex
3. 再重新执行 `repair`
4. 如果仍失败，可手工把 `.repaired-*` 文件覆盖回原始 `rollout`

### 异常四：修复后线程又读回原始路径

说明：

- 这是正常现象，只要原始文件本体已经被成功覆盖，线程继续指向原始路径没有问题
- 真正关键的是“原始文件内容是否已修复”，不是“数据库路径是否切到新文件名”

## 14. 日常预防建议

为了减少后续再次出现压缩失败，建议平时这样做：

- 不把大截图的 `base64` 直接长期堆在同一条会话里
- 超长日志尽量落地为文件，不整段灌进聊天
- 大补丁尽量分阶段提交，不要一次性塞很长
- 多智能体分析做到一个阶段后，开新线程并带摘要续聊
- 对超长历史线程，先 `scan` 再继续工作

## 15. 当前推荐口径

以后你自己快速判断时，可以直接按下面的口径执行：

- 先 `list`
- 再 `scan`
- 有风险项就 `repair`
- 修完回 Codex 重试压缩
- 有备份就不怕误修

## 16. 当前结论

对于这类“会话上下文很多，压缩失败”的问题，后续最合适的长期放置方式是：

- 手册放根目录
- 脚本放 `tools`
- 自己使用时优先走 `.cmd`

这套放置方式兼顾了：

- 易找
- 易用
- 易维护
- 易回滚
