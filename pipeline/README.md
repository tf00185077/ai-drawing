# ai-drawing Civitai Recipe Hermes autopilot

- `state.example.json` 是追蹤的 bootstrap；`state.json` 是 ignored runtime truth。
- Sol (`gpt-5.6-sol`) 負責 plan/review；Terra (`gpt-5.6-terra`) 負責 execute。
- dispatcher 是唯一能轉換 state、跑 validators、commit 的控制面。
- validators：contracts、backend tests、MCP tests。
- 無新 transition 時 stdout 必須為空；health watchdog 只監控不派遣。
- exact dirty scope 必須等於 executor `files_changed`。
- 圖片只允許 live-smoke stage 生成；每張結果直接交付 CTY，除非 CTY 要求，不分析圖片。

```bash
python3 pipeline/validate_contracts.py
python3 -m unittest discover -s pipeline/tests -v
python3 pipeline/hermes_cron_wrapper.py
```
