# Group Collaboration System — Evidence-based Synthesis

## Base Selection

**Group 3 — yyyunx**, base `f36cc8c18fac68c5a3aeee05469aaee713b3a267`.
保留 Python `groupctl` package、既有 CLI 名稱、Git branch 與 `.group` protocol 0.1。

## Reference snapshots

| Repository | 本次取得的 main commit |
|---|---|
| Group 1 — ATOMIC-138/group-collaboration-system | `8713dd786b552d6d64f4f7123cb64c9d3b013c2c` |
| Group 2 — chiahonglin1124-cyber/group-collaboration | `30da54a549fce80cbdbabc24bd355f16d3c68fe4` |
| Group 3 — yyyunx/groupctl-ai-collaboration | `f36cc8c18fac68c5a3aeee05469aaee713b3a267` |

## Keep from Group 3

- 獨立且 immutable 的事件檔案，跨所有遠端分支探索事件。
- 分離 Git merge、automated validation、semantic review，三者不能互相替代。
- 語意審查綁定精確 commit；結案使用 canonical commit、候選報告雜湊與人類確認。
- 既有失敗處理、push 成功才算公開、Git conflict 與兩階段整合。
- 原始 `spec/` 八份文件及所有既有測試斷言。

## Adopt from Group 1

重新實作 STATUS 的待整合清單、介面提醒、測試關聯與依狀態選擇的下一步建議，位於 `groupctl/status.py`。
採用依責任拆分模組的概念，新增 `events.py`、`validation.py`、`policy.py`、`finalization.py`、`errors.py`；保留 Group 3 package 與公開匯入介面。
可攜 Skill、多 agent 指引及 15-step 對照將於後續提交補齊。

## Adopt from Group 2

依規格自行撰寫 `tests/test_event_contract.py`，涵蓋全部十種事件、逐欄缺漏、enum、欄位型別、時區、重複 ID、事件關聯、環狀關聯、精確 commit 的最終測試證據。
Group 2 的靜態事件檢查被延伸為正式執行路徑中的 `validate_event_graph`，並非只對範例 JSON 執行測試。

## Reject

- Group 1 `groupctl_pkg/commands.py:917` 把 `not_available` 視為 pass；不採用。原始碼的判斷式與其回傳狀態可直接驗證此風險。
- Group 1 `_commit_and_push_paths` 使用 `push ... check=False`，可能忽略 push 失敗；保留 Group 3 對 push 結果的檢查。
- Group 1 `load_all_events` 捕捉所有例外後跳過無效事件；改為明確拒絕不合法資料，避免 blockers 無聲消失。
- 不採用 Group 1/2 的 root-level CLI／另套 package 架構；不直接複製參考組的程式或 Skill 內容。未在參考 checkout 找到 LICENSE 檔案，採用的是設計概念。
- 不將模擬決策或自動化 demo 當作真人確認。正式非互動結案需候選綁定的 human attestation，互動結案需鍵入候選 ID 與報告雜湊。

## Improvements — first increment

- TEST 所有 scope、整合驗證及 FINAL 驗證在 disposable worktree 執行。
- PUB 使用 private Git index 建立待驗證 snapshot，不改動使用者 index；測試也無法修改原工作檔案。
- unittest 的零測試不再是 pass；未安裝命令、timeout、測試失敗保留不同結果。
- 事件關聯驗證與公開事件封存，讓全新 clone 能恢復證據，無須舊對話紀錄。
- STATUS 預設 JSON 相容，另有 `status --format text`。
- 正式與 `init --simulation` 的結案紀錄明確區隔；正式自動化不能只靠 `--confirm` 自行宣稱真人同意。

## Validation — progress, not final acceptance

已實際執行：

- Group 3 原始版本：15 tests，全部通過（101.496 秒）。第一次沙箱執行因 Windows MSYS 權限造成全部無法 clone；此環境失敗未計為產品成功，沙箱外重跑通過。
- Group 1 原始 unit suite：10 tests 全數通過。這個 suite 並未驗證缺少測試的整合風險。
- Group 2 原始 event contract：3 tests 全數通過；原始 CLI suite：7 tests 全數通過。
- 第一批新 event contract：8 tests 全數通過，包含多組 subtests。
- 第一輪三人 smoke 找到模組拆分後漏掉 `json` 匯入，已修正並重跑；後續結果將記錄於證據目錄。

完整 regression、15-step demo、GitHub remote 驗證與最終 main 整合尚在進行中。這份進度報告不宣稱已完成最終驗收。

## Known Limitations

- Protocol 0.1 沒有安全身分認證；成員檔和確認檔是 attestation，不是自然人身分的密碼學證明。
- 自動工具無法證明語意審查者真正理解程式，仍須 AI／學生檢查介面與行為。
- 真實 GitHub 遠端驗證與完整 E2E 的最新結果待後續提交補齊。

## Human Judgment

本報告的架構取捨是工程分析；測試數是實際程序輸出。尚未取得組員對易用性、衝突處理政策或最終作業品質的主觀回饋，沒有虛構真人意見。Demo 的固定語意判斷與確認只屬測試 fixture。
