# 快速開始

這個 repo 有兩條路：

1. 我要安裝：使用 `install-multi-agent-runtime` skill，或跑安裝檢查腳本。
2. 我已安裝，要執行任務：使用 `research-task-orchestrator` operation skill。

## 1. 安裝 / 初始化

```bash
bash scripts/doctor.sh
bash scripts/init-runtime.sh
```

第一次 clone 後，建議先跑 mock verification：

```bash
python3 scripts/verify_install.py --strict --json
python3 scripts/run_ai_company_task_harness.py docs/ai_specs/ai-company-release-readiness-strict-demo.json --mode mock
```

Mock path 不需要 Docker、Claude Code、Router、Ollama 或模型。

## 2. 使用 operation skill

安裝完成後，日常任務使用 runtime operation skill：

```text
Use the research-task-orchestrator skill to run: <your task>
```

這個 repo 不會替你選 Claude model、provider 或 output token。Live run 會使用你自己的 Claude Code / Router 設定。

## 3. Live 任務前先小包驗證

複雜 live 任務不要一開始就跑完整大任務。先跑 micro gates：

```bash
powershell -ExecutionPolicy Bypass -File scripts/run-agent-micro-gates.ps1 -SkipGateF
```

Micro-gate task 有 artifact contract 時，`/run-task` final status 必須反映 deterministic verifier 結果。
非 micro-gate 的一般任務，仍以 process result 與 artifacts 一起判讀。
Micro-gate false success 是 hard fail：`[]`、missing artifact、wrong artifact root 都不得被標記為 pass。
Gate D 會使用 Gate C 已 live 驗證的 5 個 PTT Stock URLs 作為 seed；這不是 mock data，也不是 caller-provided crawler，而是 micro-gates 之間的 bounded live handoff。

只有小包 gate 通過後，再跑完整任務。
