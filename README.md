# Multi-Agent Claude Code

這個 repo 提供一套 bounded multi-agent workflow、runtime operation skill、mock/live verification，以及 dashboard。

設計原則很簡單：

- 安裝 repo 是一件事。
- 使用 agent 執行任務是另一件事。
- 使用者自己的 Claude Code / Router / model / output token 設定是權威來源；本 repo common path 不覆蓋它。

## Quick Start

### 1. 安裝 / 檢查

```bash
bash scripts/doctor.sh
bash scripts/init-runtime.sh
```

第一次 clone 後先跑 mock verification：

```bash
python3 scripts/verify_install.py --strict --json
python3 scripts/run_ai_company_task_harness.py docs/ai_specs/ai-company-release-readiness-strict-demo.json --mode mock
```

Mock verification 不需要 Docker、Claude Code、Router、Ollama 或模型。

### 2. 使用 operation skill

安裝完成後，用 runtime operation skill 執行任務：

```text
Use the research-task-orchestrator skill to run: <your task>
```

Operation skill 位於：

```text
.claude/skills/research-task-orchestrator/
```

它用於 backend/runtime agent 任務，不是 repo 安裝工具。

## Skill 分層

- `skills/install-multi-agent-runtime/`
  - 安裝、doctor、初始化 folder、mock verification 引導。
  - 不修改 Claude/Router/model/provider/output-token 設定。
- `.claude/skills/research-task-orchestrator/`
  - 日常任務與 backend agent 使用的 operation skill。
  - 不負責 repo 安裝或 global Claude 設定。

詳細說明見 [docs/SKILL_SEPARATION.zh-TW.md](docs/SKILL_SEPARATION.zh-TW.md)。

## Configuration

Common config 只管理本專案自己的路徑與 dashboard port：

```bash
cp .env.example .env
```

```env
RUNS_DIR=./agent-runs
RESULTS_DIR=./results
LOGS_DIR=./logs
DASHBOARD_BACKEND_PORT=8010
DASHBOARD_FRONTEND_PORT=5174
SKILLS_DIR=./skills
TASK_TIMEOUT_SECONDS=1800
```

本 repo 不在 common path 中設定 Claude model、provider、Router profile 或 output token。那些由使用者自己的 Claude/Router 環境決定。

## Live 驗證

複雜 live 任務先跑 micro gates，不直接跑完整大任務：

```bash
powershell -ExecutionPolicy Bypass -File scripts/run-agent-micro-gates.ps1 -SkipGateF
```

Micro-gate task 有 artifact contract 時，`/run-task` final status 必須反映 deterministic verifier 結果。
非 micro-gate 的一般任務，仍以 process result 與 artifacts 一起判讀。
Micro-gate false success 是 hard fail：`[]`、missing artifact、wrong artifact root 都不得被標記為 pass。
Gate D 會使用 Gate C 已 live 驗證的 5 個 PTT Stock URLs 作為 seed；這不是 mock data，也不是 caller-provided crawler，而是 micro-gates 之間的 bounded live handoff。

## Dashboard

```bash
bash .claude/skills/research-task-orchestrator/scripts/install_dashboard.sh
bash .claude/skills/research-task-orchestrator/scripts/start_dashboard.sh
```

預設：

```text
Backend health: http://127.0.0.1:8010/health
Frontend:       http://127.0.0.1:5174
```

更多： [docs/DASHBOARD.zh-TW.md](docs/DASHBOARD.zh-TW.md)

## Docs

- [快速開始](docs/GETTING_STARTED.zh-TW.md)
- [Skill 分層](docs/SKILL_SEPARATION.zh-TW.md)
- [設定](docs/CONFIGURATION.zh-TW.md)
- [Dashboard](docs/DASHBOARD.zh-TW.md)
- [進階 Claude/Router](docs/ADVANCED_CLAUDE_ROUTER.zh-TW.md)

## Repository Contents

- `.claude/skills/research-task-orchestrator/`: runtime operation skill
- `skills/install-multi-agent-runtime/`: install/doctor skill
- `scripts/verify_install.py`: checkout validation
- `scripts/run_ai_company_task_harness.py`: mock/live harness entrypoint
- `scripts/run-agent-micro-gates.ps1`: live micro-gate runner
- `scripts/verify-agent-micro-gate.ps1`: deterministic gate verifier
- `agent_os_mvp/`: dashboard package

## Safety

Do not commit API keys, passwords, Docker images, model weights, result caches, `.venv`, `node_modules`, SQLite runtime DBs, or logs.
