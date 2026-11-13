# Group Collaboration System — Final Synthesis

## Base Selection

**Group 3 — yyyunx**, base commit [f36cc8c](https://github.com/yyyunx/groupctl-ai-collaboration/commit/f36cc8c18fac68c5a3aeee05469aaee713b3a267)。
保留 Python groupctl package、原核心 CLI、Git collaboration workflow 與 protocol 0.1。
最終 runtime 修復版本：[2c4c00a](https://github.com/yyyunx/groupctl-ai-collaboration/commit/2c4c00a6e9d85c2ca31c19a93bbf91639bb29b18)。本報告與證據提交不再修改 runtime 功能。

取得來源日期：2026-11-13；比較固定在以下 main snapshots：

| Group | Repository | Commit |
|---|---|---|
| 3 — Base | yyyunx/groupctl-ai-collaboration | f36cc8c18fac68c5a3aeee05469aaee713b3a267 |
| 1 — Reference | ATOMIC-138/group-collaboration-system | 8713dd786b552d6d64f4f7123cb64c9d3b013c2c |
| 2 — Reference | chiahonglin1124-cyber/group-collaboration | 30da54a549fce80cbdbabc24bd355f16d3c68fe4 |

三組完整 clone 均已讀取原始碼、Git 流程、測試與文件；沒有以參考組取代 Base。

## Keep from Group 3

- 保留個人分支、configured canonical branch、PUB 前檢查與 commit/push 的機械操作。
- 保留 SYNC／PUB／INT／REV／TEST／STATUS／FINAL 的語意、核心 CLI 名稱及既有 Python 匯入介面。
- 保留唯一 immutable JSON events、跨分支發現、Git ancestry、conflict detection／abort 與兩階段整合。
- 保留三層驗證：Git incorporation、automated validation、semantic review。Git merge 成功不是語意成功。
- 保留 isolated worktree testing，並延伸到所有 TEST scope、PUB snapshot、整合與 FINAL 驗證。
- 保留 final candidate、精確受測 commit、report hash、未整合工作／review／blocker 檢查及人類確認。
- 原有 15 項測試斷言保留；fixture 明確標為 simulation，不把測試腳本當真人決策。
- 原始八份 spec/ 文件的 Git tree 保持 b498d660f1c49f5c0d4453f06fdfb670ad8bc78c，與 Base 相同。

選擇保留的理由是 Base 已有真實 Git fixture、明確 failure handling 與 semantic/candidate 約束，
比重寫成另一個 root-level CLI 更能保住已驗證的行為。

## Adopt from Group 1

採用設計概念後自行實作，沒有搬移其 package 或原始碼。

| 有價值的概念 | 最終實作 |
|---|---|
| 多種 Agent entry points | AGENTS.md、CLAUDE.md、GEMINI.md 與既有 AGENT_COLLABORATION.md 共用同一份程序 |
| Portable Agent Skill | .agents/skills/group-collaboration/SKILL.md + references/commands.md；格式 validator 通過 |
| 可理解的 STATUS | groupctl/status.py 顯示待整合提案、介面提醒、衝突、未公開事件、pending integration、目前程式碼的測試證據 |
| Recommended Next Action | 依實際衝突、dirty、blocker、缺測試與同步狀態選擇，提供 reason code 與繁體中文 text rendering |
| 15-step end-to-end simulation | scripts/demo.py 逐步產生 acceptance.json、transcript.json、summary.json，另驗證 fresh-session recovery |
| 模組化 | events.py、validation.py、status.py、policy.py、finalization.py、errors.py，保留 groupctl package 與核心介面 |

Group 1 的原始 unit suite 實測 10 tests 通過；這些測試沒有覆蓋其缺少 tests 的整合風險，
因此「參考組測試通過」不等於「可直接移植所有邏輯」。

## Adopt from Group 2

參考 tests/test_event_contract.py 和 CLI usability 測試的想法，
以獨立 protocol fixtures 重新撰寫，避免只檢查 repository 內幾份固定樣本。

- tests/test_event_contract.py：全部十種事件逐欄缺漏、必填型別、合法 verdict/result、
  timestamp 時區、counts、duplicate IDs、missing/self/cyclic/cross-group references。
- 將 graph validation 放進真實讀取與發布路徑，並檢查 matching question/answer、
  resolves_events、final test evidence 的精確 commit 與 pass 狀態。
- tests/test_cli.py：help／無參數、未知命令、缺參數、status format、version、
  非 Git repository 的 structured error 與 exit code。
- 維持 Group 3 的 TEST scope 與 CLI，未採用 Group 2 的特定小組 ID／成員 ID 假設或另一套命令名稱。

Group 2 的原始 event contract 3 tests、CLI 7 tests 均實際通過。
新測試與原有測試涵蓋不同契約及失敗路徑，沒有重複移植等效功能。

## Reject

| 未採用項目 | 原始碼證據與原因 |
|---|---|
| not_available 當作 integration tests pass | Group 1 groupctl_pkg/commands.py:917 明確把 pass、not_available 都映射為 pass；缺測試必須保持 not_available/needs_human |
| 忽略 push 失敗 | 同檔第 70 行 push 使用 check=False；保留 Base 的失敗例外與 NOT published 語意 |
| 無聲略過壞事件 | Group 1 groupctl_pkg/events.py:245 捕捉 Exception 後略過；不可因此讓 blockers 或測試失敗消失 |
| 預設 semantic pass | 不以預設值代替審查；維持 exact reviewed_commit 與明確 assessment |
| 更換 Group 3 架構／CLI | 會增加遷移與 regression 風險，也違反 Base 指定；只抽取可證明有價值的設計概念 |
| 把 Demo confirmation 當真人批准 | Demo 全部標記 simulation；正式非互動 FINAL 需候選綁定的 human attestation |
| 直接複製參考組原始碼 | 兩個參考 snapshot 未找到 LICENSE；採用概念並自行實作，原始作業規格則完整保留 |

## Improvements

### 狀態、證據與測試保護

- STATUS 區分「其他版本的最後一次測試」與「目前程式碼的證據」，不因 metadata commit 就宣稱 exact commit 相同。
- 發布時封存公開事件的原始 Git blob，完整檢查 graph，讓 fresh clone 不依賴私聊或舊快取。
- 已接受 change 的來源分支被刪除後，仍可由 canonical ancestry 與封存紀錄檢查。
- PUB 使用 private Git index snapshot；使用者原始 staged／unstaged 版本不會被測試修改。
- 所有 TEST scope、INT finish、FINAL checks 使用 disposable worktree，測試若修改來源會記為失敗。
- 缺命令／零測試為 not_available；只有 skipped 或缺少環境為 partial；明確失敗仍為 fail。
- 正式 FINAL 綁定候選 ID、受測 commit、報告 hash 與確認者；確認期間群組／程式變更會阻止發布。
- Exit codes 與錯誤 JSON 明確區分操作失敗、用法錯誤及驗證不足，failed push 不回報 published。

### Historical Diff bug

於 40e8d70 的獨立重現中，已納入 canonical 的 change 宣告修改兩個檔案，
但 inspect 的 diff 長度為 0，因 merge-base 等於 change commit。

修復：PUB 的事件新增 optional base_commit，記錄發布時的真正比較基底。
inspect 驗證基底 hash 與 ancestry，之後 canonical 前進仍使用相同基底。
這是 protocol 0.1 的 optional extension；legacy event 沒有基底時採明確標示的 fallback，
不假裝能恢復未記錄的完整 multi-commit 邊界。

Regression：test_historical_diff_preserves_multi_commit_contribution_after_merge
實際發布兩個 commit，驗證合併前後 diff 完全相同，並檢查 legacy warning。

### Merge Commit Event Mutation bug

於 40e8d70 的獨立重現中，只在 merge commit 修改已發布 JSON 事件，原檢查仍讀到被改寫的 summary。

修復：事件歷史檢查使用 git log --full-history -m，對 merge 的每個 parent 檢查修改／刪除，
不再依賴預設會省略 merge diff 的 git log 行為。

Regression：test_event_mutation_introduced_only_in_merge_commit_is_rejected
建立真正的 merge-only 改寫並 push，確認作者 clone 與另一個獨立 clone 都拒絕該歷史。

這兩項修復之後，依使用者指示停止新增功能及擴大測試範圍。

## Validation

### 實際執行結果

| 驗證 | 結果 | 證據 |
|---|---|---|
| Group 3 原始 suite | 15/15 pass | evidence/synthesis/baseline-group3.txt |
| Group 1 原始 unit suite | 10/10 pass | reference-group1.txt |
| Group 2 原始 contract / CLI | 3/3、7/7 pass | reference-group2-contract.txt、reference-group2-cli.txt |
| 指定兩個 bug regression | 2/2 pass，22.249 秒 | two-bug-regressions.txt |
| 修復後完整 suite | 50/50 pass，437.633 秒 | final-tests-50.txt |
| 修復 commit Ubuntu Actions | success | [Actions #43410027587](https://github.com/yyyunx/groupctl-ai-collaboration/actions/runs/43410027587) |
| 修復 commit Windows Actions | success | 同上 |
| 15-step local bare demo | 15/15 pass | local-demo-40e8d70.txt、local-demo-acceptance.json |
| 真實 GitHub HTTPS remote demo | 15/15 pass，58 commands，4 個應用測試 | github-demo-acceptance.json、github-demo-transcript.json、github-demo-summary.json |
| Skill / package | Skill validator valid；package build/install/independent import 成功；修復 commit 的 CI 亦驗證安裝 | .agents/skills/group-collaboration、Actions Installed CLI step |

50 tests 包含原始 15 項，以及 event contract 8、CLI 5、validation 6、synthesis regressions 16。
真實 Git fixtures 涵蓋 dirty protection、failed test/push、missing/zero/skipped tests、
immutability、semantic failure、blockers、candidate invalidation、確認期間變更、conflict recovery 與 fresh session。
未透過改 expected outputs、放寬 assertion 或調整 timeout 來製造 pass。

### Commit 與遠端範圍

- 最終兩項 runtime bug 修復：[2c4c00a](https://github.com/yyyunx/groupctl-ai-collaboration/commit/2c4c00a6e9d85c2ca31c19a93bbf91639bb29b18)。
- [Actions #43410027587](https://github.com/yyyunx/groupctl-ai-collaboration/actions/runs/43410027587) 在上述精確 commit 執行完整 suite、15-step local-remote demo 與 package installation。
- 真實 GitHub HTTPS demo 執行於 40e8d70841ece01dac8892abf447b476cb068020，
  不冒稱它是兩項後續 bug 修復版本的遠端重跑。後續修復由 50 項回歸與精確 commit 的跨平台 CI 驗證。
- GitHub demo 使用獨立 canonical branch synthesis/verification/20261113T085235-766544
  及三位 SYN 成員分支，沒有更新正式 main。驗證 branch 名稱完整記錄於 summary。
- 該示範的受測 canonical commit 是 f49da3a6a8b42cccef9dd490f45a828b0a949c9c；
  decisions／confirmation 的 evidence_mode 始終是 simulation。
- 本次 main 交付使用一般 Git merge；保留 Base 與開發分支歷史，不 force push。
  部署後的精確 merge SHA 由 GitHub history 與最終交付回覆確認。

### 執行環境與失敗紀錄

本機：Windows、Python 3.12.14、Git 2.46.1.windows.1。CI：Ubuntu／Windows、Python 3.12。
沙箱最初阻止 MSYS clone，改在允許 Git 子程序的環境執行；沒有把環境失敗計為 pass。

一次修復後 suite 發生 Git fetch timeout=-4622.437、總耗時 5198.977 秒的環境中斷，
推測為主機暫停／時間跳變。原始失敗紀錄保留在 interrupted-tests-before-rerun.txt。
同一 Fresh-session 測試單獨重跑 18.423 秒通過，之後完整 50 tests 重跑通過，
未修改 timeout 或測試標準。

## Known Limitations

- Protocol 0.1 沒有安全身分認證。成員檔、語意 assessment、human confirmation 都是 attestation，
  不是自然人身分或實際閱讀行為的密碼學證明。
- 工具無法證明自訂 validation commands 足以代表需求；無法自動證明 semantic review 品質。
- Worktree 隔離專案工作檔案，不是 OS security sandbox。測試仍以目前作業系統帳號執行。
- Legacy change event 沒有原始 base_commit 時，只能提供明確提示的最佳可得 diff；完整分組邊界可能無法重建。
- 歷史不可變性檢查依賴完整 Git history；淺 clone 應先取得完整歷史。遭竄改的歷史會 fail closed，不會自動抹去或略過。
- 沒有跨多分支的伺服器 transaction lock；FINAL 在確認後及發布前重新 fetch／核對快照，Git push 防止覆蓋前進的 canonical。
- 真實 GitHub remote驗證的傳輸與 Git 操作是真實的，組員與判斷仍是模擬；沒有冒稱三位真人完成了使用者研究。

## Human Judgment

**工程分析**：Base 選擇、模組化、拒絕不可靠的參考邏輯與兩項 bug 修復理由由原始碼及重現支持。

**實測證據**：test counts、exit codes、Git commits、HTTPS pushes、Actions jobs、
真實 merge conflict、fresh clone 與 Git tree hashes 均來自實際執行或儲存庫資料。

**仍需組員確認的主觀部分**：操作文字是否易懂、分工是否合適、產品需求與衝突政策是否符合課堂期待。
尚未取得這些真人回饋。自動測試中所有 human attestation fixtures 和 Demo confirmation 都只是測試資料，
不能替代正式 group FINAL 所需的真實人類決定。

本次軟體交付的 Commit／Push／main merge 已由使用者明確授權，與替小組捏造產品結案核准不同。
