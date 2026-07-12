# 進階：Claude Code / Router

Common path 不要求你修改 Claude Code、Claude Code Router、provider、model 或 output token。

Live 任務會沿用你機器上已經可用的 Claude/Router 設定。若你要自訂模型或 provider，請在自己的 Claude/Router 環境設定中處理，而不是在本 repo 的 common config 中處理。

本 repo 只做兩件事：

1. 送任務給既有 agent/runtime。
2. 驗證 artifact 是否真的產生且符合 contract。
