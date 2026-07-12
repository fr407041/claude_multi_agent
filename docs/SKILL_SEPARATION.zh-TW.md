# Skill 分層：安裝 Skill vs 操作 Skill

Issue #30 的核心是：不要把「build/install 這個 repo」和「backend agent 執行多代理任務」混在同一個 skill。

## 安裝 skill

位置：

```text
skills/install-multi-agent-runtime/
```

用途：

- 初始化 `.env`
- 建立 runs/results/logs 目錄
- 執行 doctor checks
- 執行 mock verification
- 確認 operation skill 存在
- 引導 dashboard/backend 啟動方式

禁止：

- 不修改 Claude Code 設定
- 不修改 Claude Code Router 設定
- 不指定 model/provider/output token
- 不執行使用者的實際研究任務

## 操作 skill

位置：

```text
.claude/skills/research-task-orchestrator/
```

用途：

- 接受使用者任務
- 使用既有 Claude/Router/runtime
- 執行 bounded multi-agent workflow
- 產生 artifacts
- 支援 dashboard 與 verification

禁止：

- 不負責 repo 安裝
- 不負責教使用者 build repo
- 不修改 global Claude/Router/model 設定

## 使用者心智模型

- 第一次：用 install skill。
- 日常任務：用 operation skill。
- Live 設定：沿用使用者自己的 Claude Code / Router 預設。
