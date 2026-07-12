# Dashboard 使用說明

Dashboard 是 common agent task observer。它只讀目前專案內的 artifacts，不負責啟動模型、不修改 Claude/Router，也不替使用者選 model。

## Ubuntu 22.04 common path

第一次安裝請使用 install skill，或直接執行：

```bash
bash skills/install-multi-agent-runtime/scripts/install.sh
```

啟動：

```bash
bash agent_os_mvp/start-dashboard.sh
```

打開：

```text
http://127.0.0.1:15174/
```

健康檢查：

```text
http://127.0.0.1:18010/health
```

停止：

```bash
bash agent_os_mvp/stop-dashboard.sh
```

## Dashboard 讀哪些資料

預設 watched roots：

- `AI_COMPANY_RESULTS_ROOT=./results/ai_company_task_harness`
- `MICRO_GATES_RUNS_ROOT=./agent-test-runs`

`/health` 會回傳實際 roots。若舊 run summary 內含 Windows host path，Dashboard 會先轉成目前 mounted project root 再檢查 artifact 是否存在。

## 使用者體驗原則

- 預設手動 refresh，避免你正在看結果時畫面跳動。
- 首頁只回答：完成了嗎、卡在哪、產出在哪、能不能信、下一步是什麼。
- `Generated outputs` 顯示檔案、大小、修改時間與安全預覽。
- meeting、raw logs、verifier JSON、internal error code 放在 technical details。

## Common demo

Deterministic demo：

```bash
bash scripts/run-shopping-site-common-demo.sh mock
```

它不證明模型能力；它證明安裝、verifier、result format 與 Dashboard 顯示可以穩定完成。

Live demo：

```bash
bash scripts/run-shopping-site-common-demo.sh live
```

它會使用使用者自己的 Claude/Router/LLM 設定。若 live agent 沒產出檔案，Dashboard 應顯示 `Agent did not create the expected file.`，不得顯示為完成。

## Advanced: Docker Compose

Docker Compose 只給 CI、開發或維護者使用，不是 common install path。

```bash
cd agent_os_mvp
docker compose up -d --build
```
