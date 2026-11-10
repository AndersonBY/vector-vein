# 开发、测试与构建发布指南 (Development Guide)

本文档介绍 VectorVein 桌面版（v1.0.2）的本地源码开发环境搭建、前后端联调、质量门禁、数据库迁移以及跨平台打包发布流程。

---

## 1. 环境要求

请确保本地开发环境满足以下版本约束（与 GitHub Actions CI/Release 基线一致）：

- **后端环境**
  - **Python**：`>=3.12, <3.13`（固定使用 Python 3.12）
  - **包管理器**：[PDM](https://pdm.fming.dev/latest/#installation)
  - 核心运行时依赖基线：`vv-agent==0.33.1`、`vv-llm==0.9.0`、`mcp==2.3.0`、`pywebview>=6.2.1`、`qdrant-client>=1.20.0`
- **前端环境**
  - **Node.js**：`22.x`
  - **包管理器**：`pnpm 10`
  - 技术栈：Vue 3.5 + Vite 8 + Pinia + Ant Design Vue 4 + Vue Flow

### 系统级依赖（macOS / Linux）

- **macOS**：安装 PortAudio（用于音频相关依赖编译）
  ```bash
  brew install portaudio
  ```
- **Linux (Ubuntu/Debian)**：安装 Qt/WebView 与音频构建依赖
  ```bash
  sudo apt-get update
  sudo apt-get install -y \
    build-essential patchelf portaudio19-dev \
    libdbus-1-3 libegl1 libgl1 libnss3 \
    libxcb-cursor0 libxkbcommon-x11-0
  ```

---

## 2. 安装依赖与本地启动

### 2.1 准备环境变量文件

将 `backend/.env.example` 复制为 `backend/.env`：

```bash
cp backend/.env.example backend/.env
```

### 2.2 安装前后端依赖

1. **安装前端依赖**（位于 `frontend/` 目录）：
   ```bash
   cd frontend
   pnpm install
   ```
2. **安装后端依赖**（位于 `backend/` 目录）：
   ```bash
   cd ../backend
   # Windows / Linux
   pdm install

   # macOS（包含 pyobjc 可选依赖组）
   pdm install -G mac
   ```

### 2.3 构建前端静态资源并启动桌面端

桌面主程序默认加载 `backend/web` 下的前端构建产物（除非处于 `DEBUG` 模式且本地 Vite 开发服务器正在运行）：

```bash
cd backend
# 编译 frontend 并同步拷贝到 backend/web
pdm run build-front

# 启动桌面应用
pdm run dev
```

如果需要前后端热更新联调，也可以在 `frontend/` 下启动 `pnpm run dev`，或使用 `backend/` 下的全栈开发脚本：

```bash
cd backend
pdm run fullstack-dev
```

---

## 3. 代码质量检查与自动化测试

在提交代码或发起构建前，请在各自目录运行以下检查：

### 3.1 后端测试、Lint 与类型检查

```bash
cd backend
# 运行 pytest 测试套件
pdm run test

# 运行 Ruff 代码检查（保持与 CI 一致的 E4,E7,E9,F 规则集）
pdm run lint

# 运行 ty 静态类型检查（Python 3.12）
pdm run typecheck
```

### 3.2 前端单元测试、Lint 与打包检查

```bash
cd frontend
# 运行前端单元测试（node --test）
pnpm test

# 运行 ESLint 检查
pnpm run lint

# 验证生产构建
pnpm exec vite build
```

---

## 4. 命令行工具（CLI）调试

源码环境下可直接通过 `pdm run cli` 调用工作流命令行与 Task Agent App Server（无需启动桌面 GUI 或单独启动 Celery Worker）：

```bash
cd backend
pdm run cli --workspace ./workspace init
pdm run cli --workspace ./workspace workflow list
```

完整 CLI 参数、退出码与自动化集成方式见 [Workflow CLI 文档](cli.md)。

---

## 5. 数据库结构变更（Migrations）

> [!WARNING]
> 修改数据库模型并生成迁移前，请先备份配置数据目录下的 `my_database.db` 及 `task-agent/`、`knowledge-base/` 目录。

若修改了 `backend/models/` 下的 Peewee 模型结构，请在 `backend/` 目录进入 PDM Python 环境生成迁移脚本：

```bash
cd backend
pdm run python
```

```python
from models import create_migrations
create_migrations("your_migration_name")
```

执行后会在 `backend/migrations/` 下生成形如 `xxx_your_migration_name.py` 的迁移文件。请先人工检查生成的迁移内容是否符合预期，随后重新启动主程序，启动流程会自动执行未应用的迁移。

（注：Task Agent 的业务库 `data/task-agent/tasks.db` 与知识库元数据 `data/knowledge-base/metadata.sqlite3` 分别由各自模块内建的版本迁移逻辑管理，详见 [Task Agent Runtime](task-agent-runtime.md) 与 [Knowledge Bases](knowledge-bases.md)。）

---

## 6. 桌面安装包构建与自动发布

### 6.1 本地 PyInstaller 打包

项目使用 PyInstaller 将主程序 `VectorVein` 与命令行工具 `VectorVeinCLI` 一并打包：

```bash
cd backend
# 1. 先确保前端产物已最新编译到 backend/web
pdm run build-front

# 2. 执行生产打包（输出到 backend/dist/）
pdm run build
```

打包完成后，可执行以下命令对产出的 `VectorVeinCLI` 及内嵌 Task Agent 运行时做冒烟验证：

```bash
cd backend
python tests/task_agent_package_smoke.py ./dist/vector-vein/VectorVeinCLI 1.0.2
```

### 6.2 GitHub Actions 自动发布流程

仓库配置了 `.github/workflows/release.yml` 跨平台发布流水线：

1. 更新 `backend/pyproject.toml` 中的 `project.version`（例如 `"1.0.2"`）。
2. 在 `docs/releases/<version>.md` 准备对应版本的发布说明。
3. 提交修改并推送形如 `v1.0.2` 的 Git Tag（Tag 版本号必须与 `backend/pyproject.toml` 中的 `project.version` 完全一致，否则流水线会在构建前直接中止）。
4. GitHub Actions 会自动在 Windows、macOS（`macos-latest`）、Linux 三个平台执行后端测试、Ruff 检查、前端构建、PyInstaller 打包与 `task_agent_package_smoke.py` 冒烟测试，最终生成平台 ZIP 包并发布到同名 GitHub Release。