# groupctl：人與 AI 的 Git 協作工具

**Group 3 — yyyunx，protocol 0.1，工具版本 0.3.2。**
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

需要 **Git、Python 3.10 以上**；建議以 pipx 隔離安裝。核心程式沒有第三方
runtime dependency，也不需要 AI API Key。安裝後可在任意目錄執行，不必 clone 工具原始碼。

**v0.3.2 目前是發布準備／Draft，尚未上傳 PyPI；來源與貢獻者權利待確認，沒有新增授權。
以下 GitHub 下載網址需等維護者核准並 Publish Release 後才會公開可用。**
審閱者現在可從 Draft／Actions 下載 wheel，將安裝參數換成本機檔案的完整路徑。
詳見 [來源與授權檢查](docs/LICENSING_REVIEW.md)、[發布狀態與維護者設定](docs/RELEASING.md)。

### Windows（PowerShell）

先安裝 Python 與 Git，確認 `py --version`、`git --version` 可用：

```powershell
py -m pip install --user pipx
py -m pipx ensurepath
# 關閉並重開終端機，讓 PATH 生效
pipx install "https://github.com/yyyunx/groupctl-ai-collaboration/releases/download/v0.3.2/groupctl-0.3.2-py3-none-any.whl"
groupctl --version
```

### Ubuntu / Linux

```bash
sudo apt update
sudo apt install git python3 python3-venv pipx
pipx ensurepath
# 關閉並重開終端機
pipx install "https://github.com/yyyunx/groupctl-ai-collaboration/releases/download/v0.3.2/groupctl-0.3.2-py3-none-any.whl"
groupctl --version
```

### pip / venv 與未來 PyPI

不用 pipx 時，建立虛擬環境後安裝下載的 wheel（不需啟用 PowerShell scripts）：

```powershell
py -m venv .venv-groupctl
.\.venv-groupctl\Scripts\python.exe -m pip install "C:\Downloads\groupctl-0.3.2-py3-none-any.whl"
.\.venv-groupctl\Scripts\groupctl.exe --version
```

Linux 改用 `python3 -m venv .venv-groupctl` 及 `.venv-groupctl/bin/python -m pip install /path/to/wheel`。
要用短指令，可啟用該 venv 或將其執行檔目錄加入 PATH。不要對系統 Python 使用 sudo pip
或繞過 externally-managed-environment 保護。

**只有未來完成授權並正式上傳 PyPI 後**，才可使用 `pipx install groupctl` 或
在 venv 中 `python -m pip install groupctl`。2026-11-15 PyPI 官方 JSON API 對
groupctl 回傳 404；名稱未被保留，正式發布前必須再確認，CLI 名稱始終為 groupctl。

### 更新與解除安裝

- GitHub wheel 安裝：下載並核對新版本 SHA256，執行 `pipx install --force /path/to/new-version.whl`。
- 未來 PyPI 安裝：`pipx upgrade groupctl`；venv 使用 `python -m pip install --upgrade groupctl`。
- pipx 解除安裝：`pipx uninstall groupctl`；venv 使用該環境的 `python -m pip uninstall groupctl`。
- 更新 Python package 不會自動修改各專案的 Agent 設定；重新執行 agent-setup --dry-run 檢查。
- 解除安裝保留專案資料、Agent 指令與備份；請先檢查／合併自己的內容，再自行移除不需要的檔案。

Release 同時提供 wheel、sdist、SHA256SUMS 與 RELEASE-PROVENANCE.json。
Windows 可用 `Get-FileHash .\groupctl-0.3.2-py3-none-any.whl -Algorithm SHA256`，
Linux 可用 `sha256sum -c SHA256SUMS`（先下載清單列出的所有檔案）。
SHA256 用於比對下載完整性；精確來源 commit／驗證 run 另見 provenance 與 Actions。

開發者仍可 clone 後使用 `python -m pip install -e .`、`python -m groupctl` 或 run.ps1；
Windows launcher 支援 GROUPCTL_PYTHON。這不是一般使用者安裝的必要步驟。

## 讓自己的 AI 使用

先將套件內附的指令與 Skill 安裝到**小組專案**（相對路徑以目前目錄為準，不依賴 --repo）：

```text
groupctl agent-setup --target /path/to/team-project --dry-run
groupctl agent-setup --target /path/to/team-project
```

預設支援全部三種 Agent；也可選 `--agent codex`、`--agent claude`、`--agent gemini`
並重複指定。預覽輸出 JSON 含每個檔案的路徑、內容與 create/unchanged/conflict。
相同內容重複安裝不會寫入；任何衝突預設停止全部寫入（exit 2），保留既有設定。
可手動合併所需指令；確實要取代時先檢查預覽，再明確執行：

```text
groupctl agent-setup --target /path/to/team-project --overwrite --confirm
```

每份被取代的原檔會以 `.groupctl-backup-唯一ID` 保留；不跟隨符號連結／Windows junction。
不要將可能含私人內容的備份直接提交 Git。目標可以尚未建立，也不必已是 Git repo。
安裝只寫指令檔，不安裝／登入 AI、不變更 Git，也不產生小組身分。

產物包含 AGENT_COLLABORATION.md 及所選 Agent 的 AGENTS.md／CLAUDE.md／GEMINI.md。
Codex 使用 `.agents/skills/group-collaboration/`；Claude 使用 `.claude/skills/group-collaboration/`；
Gemini 使用 `.gemini/skills/group-collaboration/`，各含完整 references。
共用 `.agents` 路徑也會保留，所有資料直接來自已安裝 Python package。
重新開啟 Agent 對話，讓它讀取新設定；舊版 Agent 可明確讀取 AGENT_COLLABORATION.md。

例如對能讀檔、執行終端機的 AI 說：

> 請閱讀 AGENT_COLLABORATION.md，依照 groupctl 流程協作。
> 目標專案是「我的專案路徑」。先檢查小組設定和身分；
> 之後收到 SYNC、PUB、INT、REV、TEST、STATUS、FINAL 時照文件執行。

可攜 Skill 位於 `.agents/skills/group-collaboration/`，包含 SKILL.md 與內部 references。
可供支援 Agent Skills 的工具載入，也可讓 AI 明確讀取 SKILL.md。
安裝 Skill 不會自動安裝 Python package；兩者都要可用。
Skill discovery 見 [Codex 官方說明](https://learn.chatgpt.com/docs/build-skills)、
[Claude Code 官方說明](https://code.claude.com/docs/en/skills)、
[Gemini CLI 官方說明](https://geminicli.com/docs/cli/skills/)。

已設定好目標專案後，每次開新 Codex／Gemini／Claude 對話，可把
`groupctl context --format markdown` 的實際輸出交給 AI，請它先讀 tasks 與 inbox。
Context 現在附目標路徑、command_prefix、dirty 檔案、精簡操作規則和真人確認界線；不依賴舊聊天紀錄。
若未安裝 groupctl，仍可從工具目錄用 run.ps1／python -m groupctl，並指定 --repo 到同一個目標。

## 建立小組：第一位成員

以下假設另一個 team-project 已有 main、應用程式與真正的 tests，且已設定 origin。
在小組專案目錄執行。先將真實需求寫入並提交 assignment.md；不需要工具 repo 的 examples。
目標專案要有 initial commit、origin，且工作目錄乾淨；既有遠端 main 必須已同步。

```text
git clone https://github.com/YOUR-TEAM/team-project.git
cd team-project
groupctl doctor
groupctl init --group G01 --person P17 --name "同學 A" --assignment assignment.md --checks unittest --publish
groupctl agent-setup --target . --dry-run
groupctl agent-setup --target .
groupctl context --format markdown
groupctl inbox
```

初始化前 doctor 缺少小組設定時回傳 2 是預期診斷。建立 Agent 指令後，請檢查並明確提交
產生的設定檔到小組的個人分支，依原協作流程發布；不要為了 clean tree 丟掉自己的設定。
其他成員若已 clone 到共享指令，不必重新安裝；需要時 agent-setup 可安全重複執行。
從其他目錄操作時，在 subcommand 前加 `groupctl --repo /path/to/team-project ...`。

`init --publish` 只提交 .group、推送 canonical，然後建立 people/P17/work，一個指令取代手動 Git 步驟。
失敗時不要重做 init：用 recover 查看已提交內容，必要時 recover --retry-push。
不加 --publish 的 `init` 保留原本只建立設定的操作；不提交其他檔案。空 Git repo 也可先初始化，
但發布與結案前必須加入有意義的驗證命令／測試。
`--checks unittest` 使用 tests/；`--checks pytest` 使用目前 Python 的 pytest（需自行安裝）。
兩者都只是設定命令，尚未執行測試。自訂專案仍可使用 --checks-file，不可與 --checks 同時使用。
`--name` 預設為 person ID，`--topic` 預設為 work；doctor 不連網、不修改 Git，缺少設定時 exit code 2 並給修復提示。

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
提交成員描述並推送。既有成員換電腦或重新 clone 後，用一個指令恢復原本分支和本機身分：

```text
groupctl join --resume --person P22 --topic renderer
groupctl context --format markdown
groupctl inbox
```

resume 不重複註冊或 Push；只在安全時 fast-forward，分歧或未提交工作會停止並保留現場。
若從未發布個人分支，但 canonical 已有你的成員描述，會建立對應個人分支。
`identity` 仍可用於目前 checkout 已認識的成員。重要進度來自 Git／公開事件，不需複製舊聊天紀錄。

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
Inbox 的 tasks 區分可協助審查、你的修改收到意見、公開問題待回答、自己的問題待回覆與 blocker；
提供精確 ID 與下一步 argv。shared suggestion 只是可協助事項，不會自動指派工作。
未讀數可歸零，但未完成的 Review 仍保留。canonical_incorporated 表示納入 Git 歷史，不能保證沒有後續 revert。
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
groupctl recover --update
groupctl recover --resume-integration C-修改ID
```

預覽不 fetch、不執行測試、不建立 worktree，也不寫入工作檔案、Git index、objects、refs 或遠端。
它會列出修改檔案、配置的測試、目標 commit 與潛在檔案重疊；這些風險不等於已證實的 Git conflict。
Recover 預設只診斷，斷線時會使用標示為可能過期的本機資料。--retry-push 要求 fresh fetch 與乾淨工作目錄，
只用一般 fast-forward push 推送現有 HEAD，重用原 event ID；若遠端分歧會拒絕，不 force push 或 reset。
診斷會區分 missing／ahead／behind／diverged／synced；純落後時可用 --update 將目前分支 fast-forward
到剛 fetch 的遠端版本，不會合併其他 feature branch。Dirty、分歧、未完成 integration、離線均拒絕更新。
--update 不 Push、不執行測試、不預設語意成功；更新後依 context／TEST 檢查最新工作。
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

不想手動建立 JSON 時，也可明確提供實際判斷（以下 SHA、文字都要換成你真正檢查的內容）：

```text
groupctl inspect C-修改ID
groupctl review C-修改ID --verdict accept --inspected-commit 完整來源SHA --diff-inspected --summary "實際審查結果" --evidence "檢查過的行為或證據"
groupctl integrate C-修改ID
groupctl integrate-finish --semantic-review pass --reviewed-commit 完整整合後HEAD --build not_applicable --summary "實際相容性判斷" --resolution "沒有文字衝突；已檢查雙方行為"
```

--verdict、--semantic-review 沒有預設 Pass。工具仍驗證精確 commit，INT 仍執行隔離測試；
build 不可用、語意失敗或缺少測試仍不會通過。`--file` 仍相容，不能與 inline assessment 混用。

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
| 找不到 groupctl | pipx ensurepath 後重開終端機；pipx list 檢查，或使用 venv 中的完整執行檔路徑 |
| PyPI 找不到 groupctl／GitHub wheel 404 | 目前尚未正式發布；審閱者下載 Draft／Actions artifact，不要把同名第三方套件當成本工具 |
| externally-managed-environment | 使用 pipx 或 venv，避免 sudo pip 與 --break-system-packages |
| agent-setup 有 conflicts（exit 2） | 沒有寫入任何檔案；讀 dry-run 內容並手動合併，或明確 --overwrite --confirm 並保留備份 |
| Agent 沒看到新 Skill | 在 target 專案重新開啟 Agent；確認所選 Agent 目錄，或直接請它讀 AGENT_COLLABORATION.md |
| not a git repository／沒有 .group | 指向正確 team clone；第一位 init，其他成員先 clone |
| working tree is not clean | 先保護並整理未完成修改；工具不會自動丟棄 dirty work |
| push 被拒絕／NOT published | 檢查權限與網路、fetch 並處理分歧後重試 push；不可 force push |
| 設定或身分不明 | doctor；既有成員換電腦用 join --resume --person ID --topic 原topic |
| 同一個人分支在別台電腦有新提交 | recover 確認 behind，再 recover --update；有分歧時先刻意整合兩邊歷史 |
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
- groupctl/onboarding.py／tasks.py：一鍵設定、身分恢復、只讀診斷與根據實際證據的待辦建議。
- .group/local：可丟棄的本機支援資料；公開事件會封存在推送歷史中。
- spec/：原始八份作業規格，保留不改。
- [整合報告](docs/SYNTHESIS_REPORT.md)、[實作差異](docs/IMPLEMENTATION_SUMMARY.md)。
- evidence/ 下舊紀錄是原版歷史；本次結果在 evidence/synthesis/。

Protocol 0.1 的成員與確認屬 attestation，沒有安全身分認證；工具無法驗證自然人身分、
AI 語意判斷品質或任意自訂測試的充分性。測試 worktree 可隔離專案檔案修改，
不是不可信程式的安全沙箱：驗證命令仍以你的作業系統帳號權限執行。
