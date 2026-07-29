# LoRA Training Hardening Execution Sequence

依序執行；前一批完成並通過該批驗證後，才展開下一批的正式 proposal、design、specs 與 tasks。

1. `harden-lora-training-start-contract`
2. `make-lora-training-recipe-explicit`
3. `harden-lora-training-runtime-lifecycle`
4. `complete-lora-training-clients-and-verification`

後續批次的 `confirmed-gaps.md` 僅為 scope guard。除非成為前一批無法完成的 blocker，否則不得把後續缺口提前併入目前批次。
