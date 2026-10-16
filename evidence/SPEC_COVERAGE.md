# 作業規格與實作對照

## 實作交付

| 原規格 | 實作位置與行為 |
|---|---|
| 00：local collaboration tool | `groupctl/`，Python 標準函式庫 CLI；`python -m groupctl` |
| 01：工具與 AI 的責任分工 | 工具查 Git 事實；`AGENT_COLLABORATION.md` 要求 AI 檢查實際 diff、介面及語意 |
| 01：個人分支與 canonical | `people/<person_id>/<topic>`，canonical_branch 可設定；不把所有遠端分支自動合併 |
| 01：重新開始仍能恢復 | 從所有遠端分支讀取不可變事件，不依賴私人聊天或唯一的本機快取 |
| 02：repository contract | `init` 建立 `.group/group.json`、assignment、members、events、final、local |
| 02：事件不可變、公開條件 | 唯一事件檔，禁止覆寫；檢查遠端事件歷史修改；commit+push 才回傳 published |
| 03：event envelope / types | `core.EVENT_FIELDS`、`validate_event`；完整 10 種事件與規定 enum |
| 04/05：SYNC | 先保留 dirty/branch/commit 資訊，fetch 所有遠端分支；`--update` 只合併 canonical 並驗證 |
| 04/05：PUB | 快速檢查、來源提交、推送、唯一 change ID、change_published 事件 |
| 04/05：INT | 檢查 exact commit、實際 diff、merge、衝突列舉；finish 驗證 ancestry/markers/checks/semantic assessment |
| 04/05：REV | 審查需要 exact inspected_commit，發布四種合法 verdict，不執行合併 |
| 04/05：TEST | current / main / change ID；不同版本在隔離 worktree 驗證並發布 exact commit evidence |
| 04/05：STATUS | 新鮮遠端資訊、身分、分支、commit、dirty、ahead/behind、事件、測試、blockers |
| 04/05：FINAL | canonical-only、待整合處置、未解 review/integration/blocker、最後驗證、candidate、人確認、final records |
| 06：可攜 AI 指引 | `AGENT_COLLABORATION.md`，不依賴某家 API 或私人對話格式 |
| 07：final report / envelope | 規定報告段落與 final.json 欄位；指向受測 canonical commit，保留已知限制 |

## 示範驗收項目

`scripts/demo.py` 會建立獨立 A/B/C 三個 clone 及 bare Git remote，執行：

1. 三個成員、三條各自的個人工作分支。
2. A 完成姓名去空白；B 完成加法功能；分別 PUB。
3. B SYNC 發現 A 的 change_published，讀取實際 diff 並 REV。
4. B INT A，Git 自動合併後，另做測試及明確的語意檢查。
5. C 修改相同問候語一行，PUB 後讓 B INT，實際產生 Git conflict。
6. 示範腳本對這個已知案例採用明確的合併決定：保留 Welcome 與去空白兩個意圖；再次驗證。
7. B TEST 並發布結果，將組合版本納入 main；C 再獨立 TEST main。
8. B 以被認可成員身分產生 final candidate，再以「示範中的模擬人類確認」發布 final report / final.json / final_result。
9. C 再 SYNC，讀到同一份最後成果。

## 證據與尚待實際環境驗收

- `test-results.txt`：自動化測試的真實輸出。
- `demo-summary.json`：完整示範的摘要、commit、事件與測試結果。
- `demo-transcript.json`：實際 Git 與 groupctl 指令、exit code、stdout/stderr。
- `sample-final-report.md` / `sample-final.json`：示範產生的共同成果紀錄。

本次測試使用**本機 Git remote**，沒有登入或推送到真正 GitHub。規格要求的 GitHub-hosted 展示，仍需用你們自己的 repository 和帳號權限再執行同一流程。工具使用普通 Git fetch/push，不依賴本機 remote 特有功能。

示範中的衝突決策及最後確認是已知測試案例的模擬；任意真實專案仍需要 AI／學生實際審查，不能以腳本中的固定內容取代判斷。
