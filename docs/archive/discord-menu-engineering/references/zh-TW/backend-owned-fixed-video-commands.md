> Historical import from `ai-drawing-discord-menu/references/zh-TW/backend-owned-fixed-video-commands.md`.
> The original body below is preserved verbatim. Operational advice, platform limits,
> setup permissions, restart/sync instructions, and implementation claims are historical
> and unverified against the current project. They grant no current execution authority.
> Consult the archive index and current project code/specs before any separately authorized work.

# Backend 擁有的固定影片 Discord 指令

當原生 Discord slash command 要包裝已驗證的本機影片工作流，而且不能讓使用者提交任意 ComfyUI JSON 時，使用此參考。

## 邊界與管線

Discord Bot 保持薄層，Backend 是唯一權威：

```text
Discord 附件＋Prompt＋時間欄位
→ Bot 驗證 Discord metadata 並送 multipart form
→ Backend 驗證實際位元組並以不透明檔名暫存到外接儲存
→ Backend 擁有的固定 workflow builder
→ queue／ComfyUI
→ 原始影片 artifact
→ 精確 FILM 補幀
→ 只持久化最終 artifact
→ `/result` 交付
```

Bot 可以收使用者圖片、Prompt、driver 影片與時間值；不能收 workflow JSON、模型檔名、節點ID、任意檔案路徑或輸出位置。

## 互動式 slash command 與 Modal 邊界

Discord Modal 的文字欄位無法可靠上傳附件，而且一個 Modal 最多只能放五個文字欄位。採兩階段互動：

1. Slash command 只收必要附件（`image`，或 `reference_image`＋`driver_video`），且只做同步metadata驗證，不讀取位元組。
2. 初始interaction response直接呼叫 `send_modal(...)`；不可先 `defer()` 再嘗試開Modal。
3. Modal恰好收五個可編輯欄位：正向動作Prompt、選填負向Prompt、首末幀跨度秒數、原始幀數、精確FILM目標幀數。
4. Modal送出時先解析並驗證全部欄位；非法輸入以ephemeral訊息回覆，不讀附件也不提交。合法輸入立即defer，再讀附件並送Backend multipart request。

短動圖預設值保持可編輯（例如3秒、49原始幀、97 FILM幀）。測試必須證明slash schema只暴露附件、Modal是初始回應、非法值不讀檔，以及AnimeGen與driver-based Wan都保留解析後契約。

## 時間契約

明確定義 `total_seconds` 為首幀到末幀的時間跨度：

- 原始 FPS：`(source_frames - 1) / total_seconds`
- 輸出 FPS：`(target_frames - 1) / total_seconds`
- MP4 容器時長：`target_frames / output_fps`

三者不能混用。metadata 同時保存 `timeline_span_seconds` 與 `container_duration_seconds`；artifact 的 `duration` 欄位應保存實際容器時長。

Wan 家族的原始生成通常要求 `source_frames = 4n+1`。這只限制原始生成；FILM 可以在資源上限內輸出任何精確整數 `target_frames >= source_frames`。

若要任意精確輸出幀數，將輸出索引 `j` 映射到原始位置：

```text
position = j * (source_frames - 1) / (target_frames - 1)
```

整數位置直接複製；小數位置把相鄰來源幀與該小數時間交給 FILM。這會保留首末幀並精確產生要求的總幀數，不必限制為×2／×4。

## 安全附件暫存

驗證兩次：Bot 在讀取位元組前做廉價檢查；Backend 收到後做權威檢查。

Backend 應檢查：

- MIME與副檔名一致
- 檔案大小上限
- magic bytes／容器簽章
- 隨機不透明暫存檔名
- 路徑必須位於暫存根目錄
- 不接受呼叫端指定的檔案系統路徑

Reference 圖片透過 ComfyUI圖片上傳API送入，再把 `LoadImage` 改成回傳的input相對名稱。Driver影片節點若讀ComfyUI input路徑，則把暫存影片hardlink或copy至Backend控制的Comfy input子目錄，只提交相對路徑；所有副本都要納入清理追蹤。

## Queue與artifact不變量

- 後處理是job完成的一部分，不是可忽略的附加步驟。
- FILM失敗時，job必須失敗並刪除原始／部分Gallery輸出；不能把未補幀影片當成功結果。
- 只持久化與交付最後的後處理artifact。
- 成功、失敗及支援的取消路徑都應清除暫存輸入。
- 清理函式在job沒有staged inputs時必須立即返回；否則影片專用清理會破壞一般圖片job的失敗路徑，或破壞刻意不含影片設定欄位的測試fixture。
- 保持API相容：選填媒體metadata（`fps`、`frame_count`、`duration`、`width`、`height`）沒有值時應省略，不能替所有舊artifact response新增`null`欄位。

Wan Animate單段輸出時，`ImageFromBatch.length`必須等於使用者要求的非零原始幀數；不可把沒有continuation時的 `trim_image=0` 直接接成length。

## 驗證矩陣

至少涵蓋：

1. 固定builder保留精確模型／LoRA／sampler資源，只注入允許欄位。
2. Prompt、Negative、原始幀數、FPS、reference、driver、face與pose路徑正確。
3. Wan輸出裁切length非零且等於原始幀數。
4. Multipart endpoint拒絕錯誤類型、簽章、大小、幀契約與路徑逃逸。
5. Queue把暫存檔正確改寫為Comfy可用的input reference。
6. FILM成功只保存一個最終artifact；FILM失敗不保存結果並清除部分檔案。
7. 舊有非影片queue失敗仍維持原錯誤行為。
8. Discord指令註冊、附件限定slash schema、初始回應開Modal、非法輸入不讀檔、兩種固定影片multipart、`/result`及影片交付皆有測試。
9. 用模型安全的小影片做一次真實低負載FILM smoke（此本機FILM金字塔用128×128安全；32×32低於最小尺寸），再用 `ffprobe` 驗證幀數、FPS、尺寸與容器時長。

低負載FILM smoke不等同完整AnimeGen／Wan重型生成；報告時要分開說明。

## 啟用證據

整合後：

- 重啟Backend，從live OpenAPI確認兩個固定route；
- 重啟Bot並確認持續運行；
- 需要Discord command sync完成的證據，不能只看process還活著。

目前原生Bot的 `on_ready()` 先執行 `tree.sync()`，之後才啟動本機operator server。因此operator port開始監聽可作為間接sync完成訊號；只有程式碼仍保持此順序時才能使用這個證據。

若從隔離worktree整合到dirty的本機 `main`，以具名stash保護無關工作、只在本機merge、還原stash、針對整合後樹重跑測試，最後移除完全合併的worktree／branch。回報時分清本機 `main` 已整合與是否已push `origin/main`。
