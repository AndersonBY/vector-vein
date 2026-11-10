# Setup, Model Configuration & Upgrade Guide

This guide covers downloading and installing VectorVein Desktop (`v1.0.2`), configuring cloud and local models, setting up retrieval services, and upgrading safely from legacy `0.x` releases.

---

## 1. Download & Installation

### 1.1 Release Packages

Download the ZIP archive for your platform from [GitHub Releases](https://github.com/AndersonBY/vector-vein/releases):

- **Windows**: `vector-vein-windows-v1.0.2.zip`
- **macOS**: `vector-vein-mac-v1.0.2.zip` (built on `macos-latest` for Apple Silicon; there is no separate Intel macOS build in the current release matrix)
- **Linux**: `vector-vein-linux-v1.0.2.zip`

Extract the archive and run `VectorVein` (`VectorVein.exe` on Windows). On first launch, VectorVein creates a `data/` folder in the application directory to store local SQLite databases, knowledge-base indexes, and static assets. The archive also includes the headless CLI executable `VectorVeinCLI`.

### 1.2 Platform Prerequisites

- **Windows WebView2 Runtime**: VectorVein uses `pywebview` backed by Microsoft Edge WebView2. Most modern Windows installations already include it; if the window fails to open, install the [Microsoft Edge WebView2 Runtime](https://developer.microsoft.com/en-us/microsoft-edge/webview2/).
- **Unblocking Downloaded Archives on Windows**: If Windows marks the downloaded `.zip` as blocked from the internet, right-click the `.zip` file before extracting -> **Properties** -> check **Unblock** -> **OK**.

---

## 2. Upgrading from 0.x to 1.0

VectorVein 1.0 introduces major architectural changes: **Task Agent** replaces the retired conversation Agent module, and standalone vector databases are replaced by hierarchical **Knowledge Bases**.

### 2.1 Automatic Verified ZIP Backup

Before migrating an existing pre-1.0 data directory, VectorVein enforces an automatic backup-and-verify step:

1. **Exit Old Processes First**: Completely close any running `0.x` VectorVein application (including its system tray process) before starting `1.0`.
2. **Sibling ZIP Snapshot**: When `1.0` starts (or when `VectorVeinCLI` initializes the workspace) and detects a pre-1.0 `data/` directory, it creates a complete sibling archive before changing your data:
   - Archive name: `data-backup-before-v1.0.0-<timestamp>-<id>.zip` (custom data directory names use their own directory name inside the same parent directory).
   - The archive preserves the full data directory tree, database-stored settings, attachments, and online snapshots of SQLite databases (including committed WAL records) within that data directory, and verifies archive readability.
3. **Abort on Backup Failure**: If insufficient disk space, permission issues, or file changes cause backup creation or verification to fail, VectorVein raises `UpgradeBackupError` and stops the migration so you can resolve the issue and retry.

### 2.2 What Changes After Migration & How to Restore

- **Legacy Conversation History**: Once the backup is verified, retired conversation Agent tables and chat history are removed from the active database, while the original records remain preserved in the backup `.zip`.
- **Relational Databases & Knowledge Bases**: Existing **Relational Databases** and tables are kept intact. Legacy vector datasets and documents are imported idempotently into **Knowledge Bases**; recovered text chunks are immediately searchable via keyword search, while semantic retrieval stays unindexed until you explicitly rebuild the index (migration never makes automatic paid embedding requests).
- **Inspecting Old Data with 0.x**: If you need to open your old conversation history in a `0.x` release, exit all VectorVein processes, keep your current `data` folder aside, extract the backup ZIP into the original parent directory, and open it with the corresponding `0.x` build.

---

## 3. Model & API Endpoint Configuration

Open **Settings** in the top-right corner to configure cloud providers, local model servers, and model presets.

### 3.1 API Endpoints & Live Testing

VectorVein separates **API Endpoints** (URLs, credentials, headers, proxy settings) from **Model Definitions**, allowing a single model to bind multiple prioritized endpoints.

- **Cloud & Compatible Providers**: Configure OpenAI, Anthropic, DeepSeek, Gemini, Qwen, Moonshot, ZhiPuAI, MiniMax, Mistral, xAI, Groq, StepFun, Baichuan, Yi, Ernie, AWS Bedrock, Google Vertex AI, or any OpenAI-compatible endpoint.
- **Local Model Servers**: Connect local OpenAI-compatible inference servers (leave the API Key empty if authentication is disabled on your local server, or provide your configured token if authentication is enabled):
  - **Ollama**: typically `http://localhost:11434/v1`
  - **LM Studio**: typically `http://localhost:1234/v1`
  - **vLLM / SGLang**: typically `http://localhost:8000/v1`
- **Test Before Saving**: In the endpoint editor or model-binding dialog, click **Test** to send a single non-streaming request using your current draft (displaying both the reply text and optional `reasoning_content`). See [Model Endpoint Testing](model-endpoint-test.md).

### 3.2 Remote Models & Custom Model Families

Under **Remote LLMs**, enable the models you use, adjust context window or output limits, or override the deployment `Model ID` per endpoint (such as custom Azure OpenAI deployment names):

For self-hosted or local open-weight models, open **Custom LLMs**, create a model family, add your model IDs, and bind them to your local endpoint:

### 3.3 Model Presets

Under **Settings -> Model presets**, configure three quick-access slots:

- **Default**
- **High performance**
- **Low cost**

Each preset stores a provider, model, and optional reasoning effort, making it easy to switch models across the Task Agent Workbench, active tasks, and Universal LLM workflow nodes. See [Model Selection](model-selection.md).

---

## 4. Knowledge Base Retrieval, Embeddings & Reranking (Vekai)

Knowledge bases support **keyword search (SQLite FTS5)**, **semantic search (embedded local Qdrant)**, and **hybrid search (Reciprocal Rank Fusion)**, plus optional **reranking**.

### 4.1 Embedding & Reranking Models

- Configure embedding models under **Settings -> Embedding models** (OpenAI Embeddings, compatible endpoints, or custom request/response mappings).
- Configure reranking backends under **Settings -> Reranking models** and select a default reranker for knowledge retrieval. Enabling or changing reranking takes effect immediately on subsequent searches without reindexing documents.
- Use **Test connection** in both sections to verify vector dimensions or relevance scores before saving.

### 4.2 One-Click Local Vekai Presets

If you run [Vekai](https://github.com/AndersonBY/vekai) locally for embeddings or reranking, click **Connect Vekai** in the Embedding or Reranking settings header to populate the default endpoints:

- **Embedding default**: `http://127.0.0.1:8013` (OpenAI embeddings protocol, default alias `local-embedding`)
- **Reranking default**: `http://127.0.0.1:8012` (mapped to `/v1/rerank`, default alias `local-reranker`)

> Note: Start your local [Vekai](https://github.com/AndersonBY/vekai) service before testing the connection, then select the model and click **Save settings**. See [Knowledge Bases](knowledge-bases.md).

---

## 5. Web Search, Speech & Desktop Window Settings

- **Network Search**: Configure **DeepSeek Search** (`https://api.deepseek.com/v1/tools/search`) and **Jina** for text search, and **Pexels** for image search. See [Web Search and Embedding Settings](web-search.md).
- **Speech Recognition (ASR) & TTS**: ASR uses OpenAI-compatible audio endpoints (reuse an existing LLM endpoint or connect services such as Groq).
- **Task Agent Risk Review Model**: Configure a dedicated model used to evaluate command and tool risks when an Agent task runs in `Auto` approval mode.
- **Desktop Notifications & Window Close Behavior**:
  - **Desktop Notifications**: Enable global completion notifications in Settings (includes a test button; notifications show generic task status only).
  - **Window & Tray (Windows)**: Under **Settings -> Window & tray**, choose whether closing the window asks every time, minimizes to the system tray, or exits. Minimizing keeps active Agents, schedulers, and indexing running in the background. See [Window Close Behavior and System Tray](desktop-window.md).
- **Global Shortcuts**: Assign keyboard shortcuts to jump directly to the Task Agent Workbench, Workflows, Schedules, or Data space.