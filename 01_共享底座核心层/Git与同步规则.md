# Git与同步规则

## 1. 当前同步原则

当前 [协作文档库](D:/AI_workspace/codex/协作文档库) 采用的是：

- 整个文档库默认纳入 Git 管理
- 只有 `.gitignore` 中明确排除的内容不会同步
- 普通 Markdown 文档、普通文件夹、图片附件目录 `assets/`、后续新建的业务子目录，默认都会同步

也就是说，后续你在文档库里新增：

- 模块目录
- 规则目录
- 需求目录
- 新笔记
- 附件图片

只要没有命中 `.gitignore`，都会进入 Git。

---

## 2. 当前不会同步的内容

当前仓库 [`.gitignore`](D:/AI_workspace/codex/协作文档库/.gitignore) 已明确排除这些内容：

- `Thumbs.db`
- `.DS_Store`
- `.claude/`
- `.claudian/`
- `.obsidian/workspace.json`
- `.obsidian/workspace-mobile.json`
- `.obsidian/cache`
- `.obsidian/workspace`
- `.obsidian/plugins/**/main.js`
- `.obsidian/plugins/**/manifest.json`
- `.obsidian/plugins/**/styles.css`
- `.obsidian/plugins/**/obsidian_askpass.sh`
- `*.log`
- `*.tmp`
- `*.temp`

这些内容不建议作为文档库协作内容进入 Git。

---

## 3. Obsidian 相关规则

### 3.1 会同步的 Obsidian 内容

当前会同步的 Obsidian 内容主要是：

- `.obsidian/app.json`
- `.obsidian/appearance.json`
- `.obsidian/community-plugins.json`
- `.obsidian/core-plugins.json`
- `.obsidian/hotkeys.json`
- 各插件的 `data.json` 这类配置文件

这类内容的价值是：

- 保留 Vault 的基础配置
- 保留插件启用状态
- 保留插件行为配置

### 3.2 不会同步的 Obsidian 内容

当前不会同步的 Obsidian 内容主要是：

- 当前窗口布局
- 当前工作区状态
- 社区插件安装包本体

这意味着：

- 换一台机器时，窗口布局不一定完全一致
- 社区插件可能仍需要本机安装
- 但插件配置本身仍然可以跟仓库走

---

## 4. 图片与附件规则

当前附件插件配置为：

- 附件目录：`./assets/${noteFileName}`

因此后续如果你在笔记里插图，通常会生成：

- 文档同级或近邻的 `assets/`
- `assets/<笔记文件名>/`

当前仓库 **没有忽略 `assets/`**，所以：

- 图片附件默认会同步
- 只要图片实际存在于文档库中，就会进入 Git

---

## 5. 新建文件夹时要注意的事

### 5.1 普通新目录

普通新目录只要里面有真实文件，就会同步。

例如：

- 新建一个模块目录
- 里面放一篇 `.md`
- 这个目录和文档就都会进入 Git

### 5.2 空目录

Git 不跟踪纯空目录。

如果你新建了一个文件夹，但里面什么都没有，它不会被同步到远端。

如果你希望保留空目录结构，可以：

- 放一个真实文档进去
- 或放一个 `.gitkeep`

---

## 6. 未来新增目录的处理原则

后续如果你自己创建新的业务目录，默认按下面规则判断：

- 目录里有正常文档或附件：会同步
- 目录名没有命中 `.gitignore`：会同步
- 只是空目录：不会同步
- 属于本地缓存、日志、会话侧车、插件程序本体：不建议同步

也就是说，当前并不是“只同步现在这几个目录”，而是：

**文档库内的大多数正常内容，默认都会同步。**

---

## 7. 如果后续有新目录不想同步

如果后续某类目录你明确不希望进入 Git，例如：

- 临时草稿
- 大量缓存图
- 本地测试输出
- 某类插件生成物

处理方式是：

1. 在 [`.gitignore`](D:/AI_workspace/codex/协作文档库/.gitignore) 里补规则
2. 再决定是否把已经追踪的旧文件移出版本管理

不要直接假设“新目录天然不会同步”。

---

## 8. 当前适合你的使用结论

你后续可以直接按下面方式理解当前仓库：

- 正常写文档：会同步
- 正常建目录：大概率会同步
- 插图和 `assets/`：会同步
- 空目录：不会同步
- Obsidian 窗口状态：不会同步
- 社区插件安装包本体：不会同步
- 插件配置文件：大部分会同步

如果后续你新增了某类目录，想先判断它会不会进 Git，先看：

- 这个目录里有没有真实文件
- 它有没有命中 [`.gitignore`](D:/AI_workspace/codex/协作文档库/.gitignore)

这两个判断就够用了。
