# HW2：groupctl 小組協作工具

這份作業做的是「多位學生各自搭配 AI，透過同一個 GitHub repository 合作」的協作層。`groupctl` 是本機命令列工具，不需要 OpenAI/Gemini API，也不需要額外伺服器。

## 功能與實際用途

假設 A 改解析器，B 改畫面，C 寫測試：A 完成後可以發布一筆有 commit、介面變動及測試資訊的修改；B 的 AI 能從遠端分支找到它，檢查實際 diff，整合後再次測試。重新開啟 AI 對話時，也能從 Git 恢復小組資訊。

| 功能 | 你實際得到什麼 |
|---|---|
| 小組設定與身分 | `.group/group.json`、成員名單、本機身分與個人分支 |
| SYNC / STATUS | 查詢所有遠端分支的公開事件，知道新進度及與 main 的差異 |
| PUB | 測試、提交、推送程式，產生唯一 change ID 與修改說明 |
| REV | 記錄審查結論與證據，不會自動合併 |
| INT | 合併特定修改，列出衝突，另行執行測試與語意檢查 |
| TEST | 記錄實際受測 commit、命令、輸出及結果；指定其他版本時使用隔離 worktree |
| FINAL | 檢查 main、未整合提案與阻礙，產生報告草稿，經人確認後發布成果 |

`PUB` 是「讓大家看到」，進入 `main` 才是小組接受。事件是獨立且不可修改的 JSON；更正資訊要新增事件。只有 commit **並且 push 成功**的事件才算公開。

## 先執行看看

需要 Git 與 Python 3.10 以上，核心程式只使用 Python 標準函式庫。Windows 啟動器也會尋找目前 Codex 隨附的 Python；換電腦可安裝 Python，或設定 `$env:GROUPCTL_PYTHON`。

在這份資料夾開啟 PowerShell：

```powershell
.\run.ps1 --help
.\run.ps1 test-suite
.\run.ps1 demo
```

`demo` 會建立新的本機 bare Git remote 與 A/B/C 三個獨立 clone，實際執行發布、同步、審查、正常整合、衝突與解決、測試及模擬結案，最後印出成果位置。每次建立新目錄，不覆寫上次結果。這是離線驗證，不會推送到你的 GitHub。

也可以直接執行：

```text
python -m groupctl --help
python -m unittest discover -s tests -v
python scripts/demo.py
```

## 用在真正的小組 GitHub repository

先建立空的 GitHub repository，以下指令中的網址請換成自己的。先在本工具資料夾執行；`--repo` 指向你們的專案 clone。

```powershell
git clone https://github.com/YOUR-GROUP/YOUR-REPO.git ..\group-project
git -C ..\group-project switch -c main
git -C ..\group-project config user.name "Your Name"
git -C ..\group-project config user.email "your-email@example.com"
.\run.ps1 --repo ..\group-project init --group G-12 --person P17 --name "同學 A" --assignment .\examples\assignment.md --checks-file .\examples\checks.json
```

`examples/checks.json` 是 Python unittest 範例，請先把它改成專案真正的測試命令，並加入有意義的測試。命令以 JSON 引數陣列儲存，不經 shell 解譯。例如 `[["python", "-m", "unittest", "discover", "-s", "tests", "-v"]]`。

如果系統沒有 PATH 中的 `python`，請將範例 JSON 的第一個元素改為你實際使用的 Python 完整路徑。`demo` 會自動使用啟動器找到的執行檔，不需調整。

`init` 建立 `.group`，不會偷偷提交其他檔案。確認內容後：

```powershell
git -C ..\group-project add .group
git -C ..\group-project commit -m "Initialize group collaboration"
git -C ..\group-project push -u origin main
git -C ..\group-project switch -c people/P17/work
.\run.ps1 --repo ..\group-project status
```

其他成員各自 clone，使用 `join --person P22 --name "同學 B" --topic renderer`。它會從遠端 main 建立 `people/P22/renderer`、提交成員資料並推送。既有成員重新 clone，可用 `identity --person P17` 選擇本機身分，再建立自己的工作分支。

## 你對 AI 說的指令，和工具指令不同

將 [AGENT_COLLABORATION.md](AGENT_COLLABORATION.md) 提供給各自的 AI。你說 `INT C-...`，AI 依規格先查 diff、判斷影響，再呼叫工具；工具不會假裝自己能理解所有程式行為。

| 對 AI 說 | AI 主要使用的工具命令 |
|---|---|
| `SYNC` | `sync` 先看紀錄；確認安全後 `sync --update` 合併 main |
| `PUB` | `pub --summary "完成的功能" --interface-change "介面變更"` |
| `REV C-...` | `inspect C-...`，實際審查後 `review C-... --file 審查.json` |
| `INT C-...` | `inspect C-...`、`integrate C-...`，再 `integrate-finish --file 語意檢查.json` |
| `TEST` | `test`；亦可 `test main` 或 `test C-...` |
| `STATUS` | `status` |
| `FINAL` | `final-prepare --result "完成內容"`，展示報告，再由人確認 `final-publish E-... --confirm` |

指令一律回傳 JSON。exit code：0 成功；1 操作錯誤或前置條件不符；2 驗證未通過、證據不足或仍有合併衝突。`integrate` 即使 Git 成功，也只完成第一階段。

審查與語意檢查範例在 `examples/`。檔案中的 commit 必須替換成實際檢查過的完整 hash。把這些輸入檔放在專案外或 `.group/local/`，以免成為未提交檔案阻擋操作。

驗證過的個人分支納入 main，使用普通 Git：先同步、檢查，再合併指定的已驗證分支，重新測試並推送。任何成員均可執行；不需要永久整合者。main 有新修改時 Git push 會拒絕過期提交，必須先同步處理，不使用 force push。

## 檔案位置

```text
groupctl/                 Python 命令列實作
tests/                    使用真實 Git 的整合與失敗路徑測試
scripts/demo.py           三成員完整離線示範
AGENT_COLLABORATION.md     可給不同 AI 使用的操作指引
examples/                 設定、審查與語意檢查範例
spec/                     原始 8 份作業規格，保留不改
evidence/                 實際執行結果與規格對照
```

受管理的專案會建立規格要求的 `.group/assignment/`、`.group/members/`、`.group/events/`、`.group/final/` 與 `.group/local/`。本機快取不作為唯一的小組紀錄。

## 範圍與限制

- 實作協作層，沒有 Dispatcher、自動任務分派或 AI API 呼叫。
- 0.1 的成員檔案是身分描述，沒有安全認證功能，與原規格一致。
- 語意審查由 AI／人提供，工具會記錄與要求具體 commit，但無法證明審查者真的理解了程式。
- 秘密檔案檢查涵蓋常見私鑰、token 與敏感檔名，發布前仍需要 AI 檢查 diff。
- `TEST` 支援任意驗證命令；不能可靠解析的測試數量記為 null，不會編造通過數。
- GitHub 遠端使用同一套 Git fetch/push；目前附帶的驗證使用本機 remote。實際 GitHub 展示仍需要小組的 repository 與登入權限。
