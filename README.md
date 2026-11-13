# groupctl：人與 AI 的 Git 協作工具

**Group 3 — yyyunx，protocol 0.1，工具版本 0.3.0。**
每位學生與自己的 AI 在各自電腦上開發，透過同一個 GitHub repository
發布、審查、整合與測試，最後形成一份共同成果。這個工具不會啟動三個 AI，
也不需要 OpenAI／Gemini API。AI 提供判斷，groupctl 執行機械操作並留下證據。

## 先看懂三件事

- **工具 repo**：你現在看的專案，提供 groupctl、Agent Skill、文件與測試。
- **小組專案 repo**：你們真的要共同開發的程式；可以是另一個 repo。
- **Demo**：自動建立三個模擬成員，驗證工具流程；所有審查決定和確認均標為 simulation，
  不能當成真實組員的意見或正式作業核准。

個人分支用 `people/<person_id>/<topic>`；設定的 canonical branch（預設 main）
才是小組正式狀態。PUB 是發布提案，尚未代表接受；REV 通過也不會自動合併。

## 安裝與第一次執行

需要 **Git、Python 3.10 以上**。核心程式沒有第三方 runtime dependency。

```powershell
git clone https://github.com/yyyunx/groupctl-ai-collaboration.git
cd groupctl-ai-collaboration
.\run.ps1 --help
.\run.ps1 demo
```

Windows 啟動器會尋找 Python 或 py launcher；也可指定：

```powershell
$env:GROUPCTL_PYTHON = "C:\你的Python路徑\python.exe"
.\run.ps1 --version
```

跨平台直接執行，或安裝為 CLI：

```text
python -m groupctl --help
python -m pip install -e .
groupctl --help
```

下文的 python 代表實際的 Python 3.10+ 執行檔；有些系統名稱為 python3。
使用 launcher 不需要 pip 安裝。

## 讓自己的 AI 使用

請 AI 讀取 `AGENTS.md` 與 `AGENT_COLLABORATION.md`。
Claude／Gemini 亦有 `CLAUDE.md`、`GEMINI.md` 入口。

例如對能讀檔、執行終端機的 AI 說：

> 請閱讀 AGENT_COLLABORATION.md，依照 groupctl 流程協作。
> 目標專案是「我的專案路徑」。先檢查小組設定和身分；
> 之後收到 SYNC、PUB、INT、REV、TEST、STATUS、FINAL 時照文件執行。

可攜 Skill 位於 `.agents/skills/group-collaboration/`，包含 SKILL.md 與內部 references。
可供支援 Agent Skills 的工具載入，也可讓 AI 明確讀取 SKILL.md。
安裝 Skill 不會自動安裝 Python package；兩者都要可用。
Skill 格式及 Codex discovery 見 [官方說明](https://learn.chatgpt.com/docs/build-skills)。

## 建立小組：第一位成員

以下假設另一個 team-project 已有 main、應用程式與真正的 tests，且已設定 origin。
先在工具目錄執行。把 assignment.md 換成真實需求；examples 只作為格式範例。

```powershell
.\run.ps1 --repo ..\team-project init --group G01 --person P17 --name "同學 A" --assignment .\examples\assignment.md --checks-file .\examples\checks.json
git -C ..\team-project add .group
git -C ..\team-project commit -m "Initialize group collaboration"
git -C ..\team-project push origin main
git -C ..\team-project switch -c people/P17/work
.\run.ps1 --repo ..\team-project status --format text
```

`init` 建立 .group 設定，不會偷偷提交其他檔案。空 Git repo 也可先初始化，
但發布與結案前必須加入有意義的驗證命令／測試。

`.group/group.json` 的可選 validation_commands 使用 argv 陣列：

```json
{
  "validation_commands": [
    ["{python}", "-m", "unittest", "discover", "-s", "tests", "-v"]
  ]
}
```

`{python}` 只在命令第一個引數展開為目前執行工具的 Python。
不經 shell，不使用 `&&` 串指令。可以列出 build、lint、unit 等多個命令。
缺少命令、零個測試、全部 skipped 或執行環境缺失都不會假裝通過。
任意自訂命令的品質仍由小組負責，工具無法證明它真的測了需求。

## 加入小組：其他成員

每位成員各自 clone 同一個 team repo，並具有 push 權限。在自己的 team clone 中，
使用已安裝的 groupctl：

```text
groupctl join --person P22 --name "同學 B" --topic renderer
groupctl status --format text
```

第三位使用不同身分，例如 P31。join 從遠端 canonical 建立個人分支，
提交成員描述並推送。既有成員重新 clone，使用 `identity --person P17`，
再建立自己的個人分支。重要進度來自 Git／公開事件，不需複製舊聊天紀錄。

## 七大協作指令

日常協作也可直接使用新的便利入口（先在目標 team repo 執行，或於 subcommand 前加 --repo PATH）：

```text
groupctl context --format markdown --max-chars 12000
groupctl context --format json
groupctl inbox
groupctl inbox --format json --type question --person P22
groupctl inbox --mark-read E-事件ID
groupctl ask --text "API 格式要統一嗎？"
groupctl answer Q-問題ID --text "統一使用 JSON"
groupctl block --summary "資料格式衝突" --action "請確認 schema"
groupctl resolve E-阻礙事件ID --reason "已更新並驗證"
groupctl template review C-修改ID --output .group/local/review.json
groupctl template semantic --output .group/local/semantic.json
```

Context 只輸出精簡摘要、精確 commit 與證據，不輸出測試原始 logs／設定命令；常見 token、密碼與私鑰會遮罩。
內容縮減時保留 totals 與 truncated，不能把省略誤認為沒有問題。Inbox 以 --limit 控制每類顯示數量；
已讀紀錄只保存在 .group/local/inbox.json，與 SYNC 快取不同，也不代表已解決或接受工作。
快捷溝通需要乾淨的工作目錄並 commit/push；群組層級 blocker 使用 blocking_change_id=GROUP，
可用 --change C-ID 關聯特定提案。resolve 新增 finding／resolves_events，原事件與 verdict 保持不變。
Template 建立 UTF-8 JSON 並拒絕覆寫既有檔案；仍需實際審查，不能直接當成通過或人類批准。

提交／整合前可先看只讀預覽，網路中斷後可先診斷再明確重試：

```text
groupctl pub --dry-run
groupctl integrate C-修改ID --preview
groupctl recover
groupctl recover --format json --offline
groupctl recover --retry-push
groupctl recover --resume-integration C-修改ID
```

預覽不 fetch、不執行測試、不建立 worktree，也不寫入工作檔案、Git index、objects、refs 或遠端。
它會列出修改檔案、配置的測試、目標 commit 與潛在檔案重疊；這些風險不等於已證實的 Git conflict。
Recover 預設只診斷，斷線時會使用標示為可能過期的本機資料。--retry-push 要求 fresh fetch 與乾淨工作目錄，
只用一般 fast-forward push 推送現有 HEAD，重用原 event ID；若遠端分歧會拒絕，不 force push 或 reset。
只有程式碼缺少發布說明時，會要求你先檢查再 PUB，不自行捏造 summary。
--resume-integration 只在 MERGE_HEAD 或目前 merge commit 的 parent 精確符合 change 時重建遺失的 .group/local 記錄；
不解衝突、不改 index／branch。原衝突清單可能不完整，後續 integration_result 會註明 recovered state，仍須實際語意審查。

這些大寫詞是**對 AI 說的提示指令**；下表是它背後使用的 CLI。
核心協作 CLI 預設回傳 JSON；context 預設 Markdown，inbox／recover／trace 預設中文 Text，
均可指定 --format json。`--repo PATH` 要放在 subcommand 前。

### 追蹤修改與離線工作

```text
groupctl trace C-修改ID
groupctl trace C-修改ID --format json --offline
groupctl status --offline --format text
```

trace 根據公開事件、精確 commit 與 Git ancestry 串起 PUB、REV、INT、TEST、blocker 與 canonical 歷程。
它保留歷次 verdict，不會把「曾經合併」視為目前語意正確或真人批准；修改可能已被後續 revert。
status --offline 完全不連線，明示資料可能過期；根據隊友宣告的 files_changed／interface_changes
與本機已提交及未提交修改提示潛在風險，並不證實會有 Git conflict，也不自動分工。

Context／Inbox／Trace 採用允許欄位與常見憑證格式遮罩；不讀取 .env，也不匯出測試原始 log。
遮罩無法識別任意未知格式的敏感資訊，分享前仍須檢查作業內容與自由文字。不要將秘密寫入公開事件。

| 對 AI 說 | 工具操作與重點 |
|---|---|
| SYNC | `sync` 探索所有相關遠端分支事件；確認安全後 `sync --update` 只合併 canonical，並驗證 |
| PUB | `pub --summary "完成內容"`；可重複提供 --interface-change、--known-issue |
| REV C-… | 先 `inspect C-…`，實際讀 diff／程式後 `review C-… --file review.json` |
| INT C-… | `integrate C-…`，處理衝突及語意，再 `integrate-finish --file semantic.json` |
| TEST | `test`、`test main` 或 `test C-…`；每個 scope 都用 isolated worktree |
| STATUS | `status` 或 `status --format text`；顯示 dirty、pending changes、Tests、Blockers 與下一步 |
| FINAL | `final-prepare --result "完成內容"`，展示草稿，再經真正的人類確認發布 |

審查 JSON 範例在 examples/review.json；inspected_commit 必須是實際讀過的完整 hash，
diff_inspected 必須為 JSON boolean true。四種 verdict：
accept、accept_with_changes、reject、needs_more_evidence。

語意審查範例在 examples/semantic-review.json；reviewed_commit 必須等於整合後 HEAD。
自動合併不會預設語意成功。沒有 tests 的整合最多是 needs_human。

PUB 會記錄 optional base_commit，讓已合併 change 的歷史 diff 仍可重建；舊事件缺少基底時會顯示 legacy warning，可能只能呈現最後一個 commit，需進一步閱讀 Git history。
事件不可變性亦檢查 merge commit 的每個 parent，不能藉由只在 merge 時改寫 JSON 來避過檢查。

一般 finding／question／answer／blocker 用
`event --type finding --file payload.json --related E-…` 發布。
關聯必須存在、屬於同組且不能形成 cycle；更正資訊要新增事件。
解決 blocker 或審查問題可附 resolves_events，並在 related_events 指向原事件、提供理由／證據。

## 最終成果與真人確認

1. 用一般 Git merge 將已審查、整合和驗證的工作納入 canonical，再推送。
2. 在 clean 且與遠端一致的 canonical 執行 final-prepare。
3. 工具檢查 pending changes、review／integration concerns、blockers，執行隔離驗證，
   產生 .group/final/candidate.md 及候選事件。
4. **把實際候選報告給真人看。** 正式互動終端執行
   `final-publish E-候選ID --confirm` 後，真人須鍵入指定候選 ID 和報告 hash。
5. 非互動情境需真人提供 `--confirmation-file`，並同時指定 --confirm。
   JSON 必須包含 candidate_id、canonical_commit、report_sha256、confirmed_by、
   confirmed_at（具時區且不早於候選建立）、statement。
   AI 不得替真人編造同意內容。輸入檔放在 .group/local 或專案外。
6. 候選報告／程式／設定改變、出現新提案、失敗證據或未解 blocker 時，停止並重新確認。
7. 成功後推送 final_report.md、final.json、final_result，記錄精確受測 canonical commit。

有意拒絕／淘汰尚未合併提案時，準備 change ID 到理由的 JSON map，
提供給 final-prepare --dispositions。重要但未知的工作不可直接忽略。
有已知限制可使用 --limitation，記錄為 completed_with_known_limitations。

`init --simulation` 只用於生成的測試情境，報告／事件／envelope 明確標示 simulation；
它不提供真實人類確認，也不應用於正式小組設定。

## 測試與 15-step Demo

```powershell
.\run.ps1 test-suite
.\run.ps1 demo
```

或使用 `python -m unittest discover -s tests -v`、
`python scripts/demo.py`。Demo 建立三個獨立 clone 及 bare remote，實際執行
PUB → SYNC → REV → INT → TEST → FINAL、真正的 Git 衝突與已知案例解決，
最後另開全新 clone 檢查恢復。輸出 acceptance.json、transcript.json、summary.json。

另有**明確會推送新驗證分支**的遠端模式：

```text
python scripts/demo.py --remote https://github.com/OWNER/REPO.git --base-ref origin/synthesis/groupctl-final
```

需寫入權限與不含真實 .group 的基底。它建立具唯一 ID 的驗證 canonical 與三位模擬成員分支，
不更新遠端 main；summary 記錄所有分支。所有人工判斷仍為 simulation。
一般本機 demo 不會連到 GitHub。

CI 在 Ubuntu／Windows 執行完整 suite、Demo、package 安裝 smoke。
是否真的通過，以 Actions 結果與 evidence/synthesis 為準，不以有 workflow 檔案當成功證據。

## 常見錯誤與恢復

| 情況 | 做法 |
|---|---|
| 找不到 Python | 安裝 3.10+，或設定 GROUPCTL_PYTHON；不需安裝 AI API SDK |
| not a git repository／沒有 .group | 指向正確 team clone；第一位 init，其他成員先 clone |
| working tree is not clean | 先保護並整理未完成修改；工具不會自動丟棄 dirty work |
| push 被拒絕／NOT published | 檢查權限與網路、fetch 並處理分歧後重試 push；不可 force push |
| not_available／partial | 補上有意義的測試、依賴或人工檢查；不能當 pass |
| Git conflict | 檢查雙方意圖、修改並提交，再 integrate-finish；不清楚時問真人 |
| 放棄未完成整合 | integrate-abort；已提交的 merge 不會被偷偷 reset，需刻意 revert |
| Broken related_events／immutable event 變更 | 找回原事件與正確分支；不要修改已公開檔案或無聲略過錯誤 |
| stale candidate／report changed | 對新的 canonical 狀態重新驗證、產生候選，再請真人確認 |
| 正式非互動 --confirm 被拒絕 | 取得候選綁定的真人確認檔；不要讓 AI 使用 Demo 的模擬批准 |

Exit code：0 成功；1 操作／前置條件錯誤；2 CLI 用法錯誤或驗證失敗／不足／尚有衝突。
有些失敗的 TEST 會成功發布「失敗證據」，但仍回傳非零 exit code。

## 架構與證據

- groupctl/core.py：Git、身分、不可變事件存取／封存、worktree、private-index snapshot。
- groupctl/events.py：十種事件 schema、型別、enum 與關聯 graph。
- groupctl/validation.py：無 shell 的檢查執行、零測試／skip／環境／failure 分類。
- groupctl/commands.py：既有核心 CLI 操作；模組匯入相容保留。
- groupctl/status.py／policy.py：狀態投影、建議與 blocker／final concerns。
- groupctl/finalization.py：candidate、時效、證據與真人確認。
- groupctl/collaboration.py／presentation.py：有長度限制的 Agent Context、Inbox、Trace、風險投影與遮罩。
- groupctl/communication.py：快速提問／回答／blocker／解決事件與未批准的 assessment templates。
- groupctl/preview.py／recovery.py／localstate.py：只讀預覽、明確重試與只存在本機的已讀／恢復紀錄。
- .group/local：可丟棄的本機支援資料；公開事件會封存在推送歷史中。
- spec/：原始八份作業規格，保留不改。
- [整合報告](docs/SYNTHESIS_REPORT.md)、[實作差異](docs/IMPLEMENTATION_SUMMARY.md)。
- evidence/ 下舊紀錄是原版歷史；本次結果在 evidence/synthesis/。

Protocol 0.1 的成員與確認屬 attestation，沒有安全身分認證；工具無法驗證自然人身分、
AI 語意判斷品質或任意自訂測試的充分性。測試 worktree 可隔離專案檔案修改，
不是不可信程式的安全沙箱：驗證命令仍以你的作業系統帳號權限執行。
