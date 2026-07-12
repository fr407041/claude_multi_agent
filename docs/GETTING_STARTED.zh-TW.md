# Getting Started（Ubuntu 22.04）

這個 repo 的 common path 很簡單：

1. 用安裝 skill 準備本機 runtime 與 Dashboard。
2. 用操作 skill 執行 agent 任務。
3. 用 Dashboard 看結果、產出、驗證與下一步。

本專案不替你指定 Claude、Router、model 或 output token；那些設定以你的電腦既有環境為準。

## 1. 安裝

```bash
bash skills/install-multi-agent-runtime/scripts/install.sh
```

安裝流程會：

- 建立 `.env`
- 建立 `agent-runs/`、`results/`、`logs/`
- 準備 Dashboard backend/frontend dependencies
- 檢查 `research-task-orchestrator` operation skill 是否存在

## 2. 啟動 Dashboard

```bash
bash agent_os_mvp/start-dashboard.sh
```

打開：

```text
http://127.0.0.1:15174/
```

Dashboard 採手動 refresh，避免你正在看結果時畫面跳來跳去。

## 3. 先跑 deterministic common demo

```bash
bash scripts/run-shopping-site-common-demo.sh mock
```

mock demo 不證明模型能力；它證明安裝、verifier、result format 與 Dashboard display 可以在乾淨環境穩定完成。

## 4. 再跑 live common demo

```bash
bash scripts/run-shopping-site-common-demo.sh live
```

這會用你的既有 Claude/Router/LLM 設定，讓 agent 先進行 bounded meeting，再產生一組可人工審查的 generated outputs，最後由 deterministic verifier 驗證。

目前預設 demo 會產生：

- `shopping-site/index.html`
- `shopping-site/styles.css`
- `shopping-site/app.js`
- `shopping-site/README.md`

購物網站只是容易人工檢查的 common 生成任務範例；Dashboard 和 runtime 不綁定這個情境。

## 5. Dashboard 讀哪裡

預設 watched roots：

- `AI_COMPANY_RESULTS_ROOT=./results/ai_company_task_harness`
- `MICRO_GATES_RUNS_ROOT=./agent-test-runs`

可用健康檢查確認：

```text
http://127.0.0.1:18010/health
```

## 6. Legacy stress test

PTT Stock micro-gates 是 external-site stress test。它可以測模型與外部網站處理能力，但不再作為 common install/live demo 的唯一通過條件。
