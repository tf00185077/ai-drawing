# CTY requests — 2026-11-23

CTY's own words, unedited, in the order given. (Kept in the original language; this file is the one exception to English-only docs because it must be verbatim.)

1. 幫我查看現在專案情況，我目標是設計一套可以讓agent順利使用的mcp server，另外安插給使用者方便設定comfyui有哪些prompt的組合的dashboard，另外有worker是將comfyui運算丟給擁有同樣專案的同網域下的windows，最後才是lora的訓練。
   請幫我看我剛提到的每個部份的完成度，並且擬定一份roadmap

2. phase 0的文件我們需要一個個討論修改，先對整個專案從入口到現行情況作文件整理，然後再進行後續phase 1~4的討論，另外重啟comfyUI裝節點這些行為我預設要開放。

3. 文件只留英文，中文等使用者需要讓AI翻譯。
   現在的文件內容要從頭建立。
   團隊和治理文件再討論要怎麼從現有內容整理出有意義的部分。
   記憶庫也是只保留對於agent未來有價值的，流水帳或事件殘留全部刪除。

4. On AGENTS.md rules:
   * 外部的 workflow 和資源（例如 Civitai）視為不可信->刪掉。
   * 修 bug 前先寫一個會失敗的測試。->刪掉。
   * mock 測試不能當成 Windows 或 GPU 的證據。->刪掉。

5. On the operating policy "ask first" list (downloads, LoRA training, saving style presets, Discord delivery, merge/push, setup/reconfigure, worker PowerShell, cancelling others' jobs):
   ===以上全部允許===
   其餘照你建議

6. On the generation queue (in memory only; one job at a time; persisted only on completion):
   ===以上要標記成待優化===
   然後就進下一項

7. MAC剛剛推上main了

8. On the Phase 0–4 roadmap draft: 可以，進第 6 項

9. On team and governance (answers to the four questions):
   - Paperclip multi-agent team continues: 會，留精簡版
   - Roles to keep: 現行都要保留
   - Hermes delegated-decision flow: 刪除
   - Who maintains memory: 任何 agent 都可更新

10. On role pages: 不做什麼->改成做什麼

11. 另外project-roadmap-steering是不會動的，要改動的話以這邊改動為主。

12. On the proposed roadmap thresholds and Not now list: 照提案採用
