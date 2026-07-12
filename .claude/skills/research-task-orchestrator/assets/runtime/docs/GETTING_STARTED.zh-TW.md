# 快速開始：Ubuntu 22.04

這個專案的 common path 只要求使用者理解兩件事：

1. 先用安裝 skill 把本機 runtime 與 Dashboard 準備好。
2. 再用操作 skill 派任務、讓 agent 開會、產出檔案並驗證。

本專案不替使用者指定 Claude、Router、模型或 output token。這些都沿用使用者自己電腦上的設定。

## 1. 安裝

```bash
bash skills/install-multi-agent-runtime/scripts/install.sh
```

安裝流程會：

- 建立 `.env`
- 建立 `agent-runs/`、`results/`、`logs/`
- 準備 Dashboard backend/frontend
- 檢查 operation skill 是否存在
- 執行基本 verification

## 2. 啟動 Dashboard

```bash
bash agent_os_mvp/start-dashboard.sh
```

打開：

```text
http://127.0.0.1:15174/
```

Dashboard 預設採手動 refresh，避免頁面一直跳動，讓使用者可以專心看結果。

## 3. 建立 Role Card

Fab user 不需要設定 skill、MCP、hook、tool 或 capability。只建立 Role Card：

```bash
python3 scripts/create_role_card.py \
  --name Mina \
  --role builder \
  --background "Frontend builder focused on clean, reviewable UI." \
  --style concise
```

產生：

```text
fab_agents/mina/role-card.yaml
```

Role Card 長這樣：

```yaml
name: Mina
role: builder
style: concise
background: |
  Frontend builder focused on clean, reviewable UI.
```

可用角色：

```bash
python3 scripts/list_roles.py
```

驗證 Role Card：

```bash
python3 scripts/validate_role_card.py fab_agents/mina/role-card.yaml
```

解析成 CIM 管控的 effective policy：

```bash
python3 scripts/resolve_role_card.py fab_agents/mina/role-card.yaml --out results/fab_agent_resolved
```

## 4. 使用 operation skill 派任務

安裝完成後，使用者可以對 Claude 說：

```text
Use research-task-orchestrator skill to run:
用 Mina 和 Reviewer 幫我做一個可審查的購物網站 demo。
```

operation skill 會負責：

- 讀取 Role Card / agent 設定
- 依 CIM role preset 套用 capability
- 安排 bounded meeting
- 分派 agent 任務
- 收集 artifacts
- 執行 verifier
- 將結果顯示在 Dashboard

## 5. 跑 deterministic common demo

```bash
bash scripts/run-shopping-site-common-demo.sh mock
```

Mock mode 不證明模型能力；它證明 repo 安裝、結果格式、verifier 與 Dashboard 顯示可以在乾淨機器上穩定完成。

## 6. 跑 live common demo

```bash
bash scripts/run-shopping-site-common-demo.sh live
```

Live mode 會使用使用者電腦既有的 Claude / Router / LLM 設定。購物網站只是 common generated-output demo fixture，不代表系統只支援網站任務。

預期產出：

- `shopping-site/index.html`
- `shopping-site/styles.css`
- `shopping-site/app.js`
- `shopping-site/README.md`

## 7. Dashboard 觀察重點

Dashboard 第一屏只回答五個問題：

- 任務完成了嗎？
- 現在卡在哪？
- 產出在哪？
- 能不能信？
- 下一步是什麼？

技術細節、raw logs、provider diagnostics、audit log 與 verifier JSON 預設收在 Technical details。

## 8. Legacy stress test

PTT Stock micro-gates 仍保留為外部網站壓力測試，但不再是第一次安裝的 common acceptance path。
