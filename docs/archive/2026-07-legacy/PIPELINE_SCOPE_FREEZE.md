# Pipeline Stage Scope Freeze Contract

## Goal

讓 CIV-B～CIV-G 以可收斂、可二元驗收的 stage contract 執行，避免 reviewer 在執行中新增 acceptance criteria。

## Required stage fields

每個新 stage 必須由 planner 一次寫定：

- `contract_version`
- `inputs`
- `outputs`
- `in_scope`
- `out_of_scope`
- `acceptance`: 非空陣列，每項 `{id, text}`，ID 唯一
- `required_tests`
- `allowed_files`
- `executor_brief`

缺任何欄位、使用字串 acceptance、重複 criterion ID，plan decision 都視為 invalid，不建立 stage。

## Review rules

1. `reject`／`accept_with_fixes` 必須提供 `blocking_criterion_ids`，且每個 ID 必須存在於 frozen acceptance。
2. 每個 fix 必須是 `{criterion_id, instruction}`。
3. 未列入 acceptance 的 correctness、hardening、future integration 發現只能寫入 `deferred_findings`，不得阻擋本 stage。
4. Frozen acceptance 全部通過時必須 accept。
5. Reviewer 引用未知 criterion ID 時，pipeline 以 `SCOPE_VIOLATION` 暫停，不把新要求交給 executor。

## Convergence limit

- 每 stage 最多三次 review rejection。
- 第三次 rejection 後 stage/goal 自動暫停，由 Hermes／owner 判定原 contract 是否真的無法完成。
- 不允許自動開第四輪、也不允許 reviewer 在第三輪新增 criterion。

## Executor rules

- 只修改 `allowed_files` 覆蓋的產品路徑。
- 只完成 `in_scope` 與 acceptance。
- `out_of_scope` 發現寫入 `notes_for_review`，不可擴大 dirty scope。
- 遵守 TDD；執行 `required_tests`。

## Deferred findings

`deferred_findings` 會保存在 stage state，供後續 planner 對應 CIV-C～G 時取用；它不是當前 stage blocker。

## Verification

```bash
python3 pipeline/validate_contracts.py
python3 -m unittest discover -s pipeline/tests -v
```

必測行為：

- 缺 frozen contract 的 plan 被拒絕。
- 未知 criterion 的 review 觸發 scope violation／pause。
- 第三次 reject 後 pause，不派第四個 executor。
- 既有 rate-limit、dirty-scope、validator、commit gate 測試仍通過。
