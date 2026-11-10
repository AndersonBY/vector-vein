# 安装、模型配置与升级指南

本指南介绍 VectorVein 桌面版（v1.0.2）的安装步骤、模型与检索服务配置，以及从 0.x 旧版本升级的数据备份与恢复方式。

---

## 1. 下载与安装

### 1.1 获取发布包

前往 [GitHub Releases](https://github.com/AndersonBY/vector-vein/releases) 下载对应操作系统的 ZIP 压缩包：

- **Windows**：`vector-vein-windows-v1.0.2.zip`
- **macOS**：`vector-vein-mac-v1.0.2.zip`（基于 `macos-latest` Apple Silicon 构建；当前发布矩阵不包含独立 Intel macOS 构建）
- **Linux**：`vector-vein-linux-v1.0.2.zip`

解压后直接运行主程序 `VectorVein`（Windows 下为 `VectorVein.exe`）。首次启动时，程序会在运行目录下自动创建 `data/` 文件夹，用于存放本地 SQLite 数据库、知识库索引及静态资源。同时打包目录中还附带命令行工具 `VectorVeinCLI`。

### 1.2 平台运行要求

- **Windows WebView2 运行时**：桌面界面基于 `pywebview` 与 Microsoft Edge WebView2 内核构建。现代 Windows 系统通常已内置；若双击后窗口无法打开，请从微软官方下载并安装 [Microsoft Edge WebView2 Runtime](https://developer.microsoft.com/zh-cn/microsoft-edge/webview2/)。
- **Windows 压缩包解除锁定**：若浏览器下载的 `.zip` 文件被系统标记为来自互联网锁定状态，建议在解压前右键点击 `.zip` 文件 -> **属性** -> 勾选底部 **解除锁定（Unblock）** -> **确定**，再解压运行。

---

## 2. 从 0.x 升级到 1.0 系列

1.0 系列对底层架构进行了重大升级：**任务 Agent（Task Agent）** 正式取代原有的对话（Conversation）Agent，原独立向量数据库升级为**层级知识库（Knowledge Bases）**。

### 2.1 自动全量 ZIP 备份与校验

为保障本地历史数据安全，升级过程遵循“先验证备份，再执行迁移”的原则：

1. **退出旧版进程**：升级前请完全退出正在运行的旧版 VectorVein（包括系统托盘中的驻留进程）。
2. **同级自动备份**：1.0 启动或执行 CLI 初始化时，若检测到未迁移的旧版数据目录（默认 `data/`），会先在同级目录生成完整备份包：
   - 命名格式：`data-backup-before-v1.0.0-<timestamp>-<id>.zip`（自定义数据目录则使用对应目录名并在其父目录生成）。
   - 备份涵盖该数据目录内的完整目录树、存储于数据库中的设置、附件，并对 SQLite 数据库及已提交的 WAL 日志执行在线快照，随后逐项校验压缩包完整性。
3. **失败即中止**：若因磁盘空间不足、权限受限或文件占用导致备份或校验失败，程序会抛出 `UpgradeBackupError` 并中止迁移，保留原有数据目录以便排查重试。

### 2.2 迁移后的数据变化与恢复方式

- **对话历史清理与保留**：备份校验通过后，旧版对话 Agent 及聊天记录会从当前活动数据库中移除，但完整原始数据保留在上述同级 `.zip` 备份包中。
- **关系数据库与知识库**：原有的**关系数据库（Relational Databases）** 与表格完整保留；旧版向量数据集与文档会自动导入为新版**知识库**，已提取的分块可直接用于关键词检索（语义向量检索可在配置好嵌入模型后手动点击重建索引，升级过程不会在后台自动发起付费 Embedding 调用）。
- **如何用旧版查看历史记录**：如需回看旧对话，请先退出所有 VectorVein 进程，保留当前新数据目录，将备份 ZIP 解压回原位置并使用对应的 0.x 旧版本打开（若再次用 1.0 打开会重新触发迁移）。

---

## 3. 模型与 API 端点配置

任务 Agent 与绝大多数 AI 工作流都需要调用大语言模型。打开右上角 **设置（Settings）**，即可统一管理所有云端与本地模型接入。

### 3.1 API 端点管理与在线测试

VectorVein 将 **API 端点（连接地址与凭据）** 与 **模型定义** 解耦，同一个模型可以绑定多个按优先级排序的端点。

- **接入主流云服务与兼容接口**：支持 OpenAI、Anthropic、DeepSeek、Gemini、Qwen（通义千问）、Moonshot、ZhiPuAI（智谱）、MiniMax、Mistral、xAI、Groq、StepFun、Baichuan、Yi、Ernie 以及 AWS Bedrock、Google Vertex AI 等提供商。
- **接入本地推理服务**：兼容 OpenAI 接口的本地服务可作为端点接入（如未开启鉴权可留空 API Key；若服务端配置了访问令牌，请按实际配置填写）：
  - **Ollama**：通常为 `http://localhost:11434/v1`
  - **LM Studio**：通常为 `http://localhost:1234/v1`
  - **vLLM / SGLang**：通常为 `http://localhost:8000/v1`
- **保存前单次实测**：在端点编辑窗口或模型端点绑定弹窗中，点击 **测试（Test）** 即可用当前草稿发送一次真实非流式请求（支持展示正文与 `reasoning_content` 推理内容），无需先保存配置即可排查地址、密钥、代理或请求头问题。详见 [模型端点测试说明](model-endpoint-test.md)。

### 3.2 远程模型与自定义模型系列

在 **远程大语言模型** 标签页中，可以启用所需模型、调整上下文窗口与最大输出上限，或为同一模型配置多个端点的具体部署名称（例如 Azure OpenAI 的自定义 Deployment ID）：

如果使用的是自建私有模型或本地开源权重，可在 **自定义大语言模型** 标签页先新建模型系列，再添加具体模型 ID 并绑定本地端点：

### 3.3 模型预设（Model Presets）

在 **设置 -> 模型预设** 中，你可以为全局配置三档常用组合：

- **默认（Default）**
- **高性能（High performance）**
- **低成本（Low cost）**

每档预设均可保存具体的“提供商 + 模型 + 推理强度（Reasoning Effort）”。配置完成后，无论是在任务 Agent 工作台、运行中的任务详情页，还是工作流的通用 LLM 节点中，都可以通过紧凑的模型选择器快速切换。详见 [模型选择说明](model-selection.md)。

---

## 4. 知识库检索、嵌入与重排序（Vekai 接入）

知识库支持 **关键词检索（SQLite FTS5）**、**语义检索（内置本机 Qdrant 向量索引）** 与 **混合检索（RRF 融合）**，并支持可选的二次 **重排序（Reranking）**。

### 4.1 嵌入模型（Embedding）与重排序模型（Reranking）

- 在 **设置 -> 嵌入模型** 中配置向量化后端（支持 OpenAI Embedding 及各类兼容接口，或通过自定义请求/响应映射接入自建服务）。
- 在 **设置 -> 重排序模型** 中可配置独立的 Rerank 后端，并在知识库检索默认项中开启。开启后无需重建已有文档索引，后续桌面搜索、Agent 检索与工作流检索均会自动对候选片段重排序。
- 两个页面均提供 **测试连接（Test connection）** 按钮，保存前即可验证向量维度或相关性得分。

### 4.2 一键填充本地 Vekai 预设

如果你在本机运行了 [Vekai](https://github.com/AndersonBY/vekai) 本地嵌入或重排序服务，可在嵌入模型和重排序模型设置卡片右上角直接点击 **连接 Vekai（Connect Vekai）** 快速填入默认配置：

- **嵌入服务默认地址**：`http://127.0.0.1:8013`（OpenAI embeddings 协议，默认模型别名 `local-embedding`）
- **重排序服务默认地址**：`http://127.0.0.1:8012`（映射到 `/v1/rerank`，默认模型别名 `local-reranker`）

> 注意：VectorVein 不会自动下载模型或后台启动 Vekai，请先在本机启动 [Vekai](https://github.com/AndersonBY/vekai) 服务，再在设置中测试连接、选择模型并点击 **保存设置**。详见 [知识库与检索架构](knowledge-bases.md)。

---

## 5. 联网搜索、语音与桌面体验设置

- **联网搜索（Network Search）**：支持配置 **DeepSeek Search API**（默认端点 `https://api.deepseek.com/v1/tools/search`）与 **Jina Search**，图片搜索支持 **Pexels**（旧版 Bing 搜索配置已退役）。详见 [联网搜索与嵌入设置](web-search.md)。
- **语音识别（ASR）与语音合成（TTS）**：语音识别统一走 OpenAI 兼容接口（可复用 LLM 端点或接入 Groq Whisper 等服务）。
- **任务风险审批模型**：可在设置中指定独立的轻量模型，用于在任务 Agent 处于 `自动审批（Auto）` 模式时评估命令与工具调用风险。
- **桌面通知与窗口关闭行为**：
  - **桌面通知**：在设置中开启后，普通任务或定时任务完成时会发送系统原生通知（支持点击测试；通知仅包含任务状态，不泄露提示词、输出或文件名）。
  - **窗口与托盘（Windows）**：在 **设置 -> 窗口与托盘** 中可设置点击关闭按钮时的行为（每次询问 / 最小化到系统托盘 / 直接退出）。最小化到托盘后，后台任务 Agent、定时调度器与知识库索引将继续运行。详见 [窗口关闭行为与系统托盘](desktop-window.md)。
- **全局快捷键**：支持自定义呼出任务 Agent 工作台、工作流空间、定时任务或数据空间的快捷键。