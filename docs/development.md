# Development, Testing & Build Guide

This guide covers setting up a local development environment for VectorVein Desktop (`v1.0.2`), running frontend and backend quality checks, creating database migrations, and building cross-platform release packages.

---

## 1. Prerequisites

Match the versions verified in the GitHub Actions CI and Release workflows:

- **Backend**
  - **Python**: `>=3.12, <3.13` (Python 3.12)
  - **Package Manager**: [PDM](https://pdm.fming.dev/latest/#installation)
  - Core runtime baseline: `vv-agent==0.33.1`, `vv-llm==0.9.0`, `mcp==2.3.0`, `pywebview>=6.2.1`, `qdrant-client>=1.20.0`
- **Frontend**
  - **Node.js**: `22.x`
  - **Package Manager**: `pnpm 10`
  - Stack: Vue 3.5 + Vite 8 + Pinia + Ant Design Vue 4 + Vue Flow

### System Libraries (macOS / Linux)

- **macOS**: Install PortAudio before installing Python dependencies:
  ```bash
  brew install portaudio
  ```
- **Linux (Ubuntu/Debian)**: Install build, audio, and Qt/WebView runtime dependencies:
  ```bash
  sudo apt-get update
  sudo apt-get install -y \
    build-essential patchelf portaudio19-dev \
    libdbus-1-3 libegl1 libgl1 libnss3 \
    libxcb-cursor0 libxkbcommon-x11-0
  ```

---

## 2. Installing Dependencies & Running Locally

### 2.1 Environment File

Copy `backend/.env.example` to `backend/.env`:

```bash
cp backend/.env.example backend/.env
```

### 2.2 Install Frontend & Backend Dependencies

1. **Frontend** (`frontend/`):
   ```bash
   cd frontend
   pnpm install
   ```
2. **Backend** (`backend/`):
   ```bash
   cd ../backend
   # Windows / Linux
   pdm install

   # macOS (includes pyobjc optional dependency group)
   pdm install -G mac
   ```

### 2.3 Build Frontend Assets & Start the Desktop App

By default, the desktop application serves static assets from `backend/web` (unless running in `DEBUG` mode with an active Vite dev server):

```bash
cd backend
# Build frontend and copy assets to backend/web
pdm run build-front

# Launch the desktop app
pdm run dev
```

For full-stack hot-reload development, you can also run `pnpm run dev` in `frontend/` or run:

```bash
cd backend
pdm run fullstack-dev
```

---

## 3. Quality Checks & Automated Tests

Run these checks before submitting changes:

### 3.1 Backend Tests, Lint & Typecheck

```bash
cd backend
# Run pytest suite
pdm run test

# Run Ruff lint checks (E4, E7, E9, F)
pdm run lint

# Run ty static type checking (Python 3.12)
pdm run typecheck
```

### 3.2 Frontend Unit Tests, Lint & Production Build

```bash
cd frontend
# Run frontend unit tests (node --test)
pnpm test

# Run ESLint
pnpm run lint

# Verify Vite production bundle
pnpm exec vite build
```

---

## 4. Headless CLI Debugging

During development, invoke the workflow CLI or Task Agent App Server directly via `pdm run cli`:

```bash
cd backend
pdm run cli --workspace ./workspace init
pdm run cli --workspace ./workspace workflow list
```

See [Workflow CLI](cli.md) for full command syntax and exit codes.

---

## 5. Database Schema Migrations

> [!WARNING]
> Back up `my_database.db`, `task-agent/`, and `knowledge-base/` inside your configured `data` directory before modifying models or running migrations.

When updating Peewee models under `backend/models/`, generate a migration script from `backend/`:

```bash
cd backend
pdm run python
```

```python
from models import create_migrations
create_migrations("your_migration_name")
```

This creates `backend/migrations/xxx_your_migration_name.py`. Review the generated file before restarting the main application, which applies pending migrations automatically on startup.

(Note: `data/task-agent/tasks.db` and `data/knowledge-base/metadata.sqlite3` manage their own internal schema versions; see [Task Agent Runtime](task-agent-runtime.md) and [Knowledge Bases](knowledge-bases.md).)

---

## 6. Packaging & Automated Releases

### 6.1 Local PyInstaller Build

VectorVein packages both the desktop app (`VectorVein`) and the console runner (`VectorVeinCLI`) with PyInstaller:

```bash
cd backend
# 1. Rebuild frontend assets into backend/web
pdm run build-front

# 2. Build packaged executables under backend/dist/
pdm run build
```

Verify the packaged CLI and Task Agent runtime with the smoke test:

```bash
cd backend
python tests/task_agent_package_smoke.py ./dist/vector-vein/VectorVeinCLI 1.0.2
```

### 6.2 GitHub Actions Release Workflow

`.github/workflows/release.yml` builds and publishes release archives when a version tag is pushed:

1. Update `project.version` in `backend/pyproject.toml` (for example, `"1.0.2"`).
2. Add release notes under `docs/releases/<version>.md`.
3. Commit and push a matching tag such as `v1.0.2` (the workflow fails before packaging if the tag does not match `backend/pyproject.toml`).
4. GitHub Actions runs backend tests, Ruff checks, frontend builds, PyInstaller packaging, and `task_agent_package_smoke.py` across Windows, macOS (`macos-latest`), and Linux, then uploads `vector-vein-windows-v<version>.zip`, `vector-vein-mac-v<version>.zip`, and `vector-vein-linux-v<version>.zip` to the GitHub Release.