"""Small, explicit shortcuts around the existing initialization and Git workflow."""
import json
import sys

from .core import Repository, GroupError, execute, identifier
from .collaboration import ObservedRepository
from . import localstate
from .presentation import safe, reject_secrets, safe_commands
from .validation import validate_commands


CHECK_PRESETS = {
    "unittest": [["{python}", "-m", "unittest", "discover", "-s", "tests", "-v"]],
    "pytest": [["{python}", "-m", "pytest", "-v"]],
}


def exists(r, ref):
    return r.git("show-ref", "--verify", "--quiet", ref, ok=(0, 1)).returncode == 0


def prepare_init(r, args, assignment, checks):
    """All fallible prerequisites precede creating .group or changing a branch."""
    if not getattr(args, "publish", False):
        return
    r.clean()
    if r.branch != args.canonical:
        raise GroupError("初始化發布必須在 canonical branch 執行。", hint=f"先切換到 {args.canonical}，整理工作後重試。")
    r.git("rev-parse", "--verify", "HEAD")
    r.git("var", "GIT_AUTHOR_IDENT")
    reject_secrets(assignment)
    if safe_commands(checks) != checks:
        raise GroupError("驗證命令可能含憑證；不要把 Secrets 寫入共享設定。")
    topic = identifier(getattr(args, "topic", "work"))
    r.fetch()
    canonical = f"refs/remotes/{r.remote}/{args.canonical}"
    if exists(r, canonical) and r.head != r.output("rev-parse", canonical):
        raise GroupError("本機 canonical 與遠端不同，尚未初始化。", hint="先檢查並同步正式分支，再執行 init --publish。")
    branch = f"people/{args.person}/{topic}"
    if exists(r, "refs/heads/" + branch) or exists(r, f"refs/remotes/{r.remote}/{branch}"):
        raise GroupError("個人分支已存在；尚未初始化。", hint="先確認是否應加入既有小組或選擇不同 topic。")


def publish_init(args):
    r = Repository(args.repo)
    r.git("add", "--", ".group")
    r.git("commit", "-m", f"group: initialize {args.group}", "--", ".group")
    r.clean()
    try:
        r.git("push", "-u", r.remote, f"HEAD:refs/heads/{args.canonical}")
    except GroupError as exc:
        localstate.push_failure(r, "setup_push")
        raise GroupError("設定已提交，但尚未確認發布；不要重做 init。",
                         hint="檢查網路／權限後 recover --retry-push，再 join --resume --person " + args.person) from exc
    r.fetch()
    branch = f"people/{args.person}/{getattr(args, 'topic', 'work')}"
    r.git("switch", "-c", branch)
    return {"group_id": args.group, "person_id": args.person, "branch": branch, "published": True,
            "validation_configured": bool(r.config["validation_commands"]), "tests_executed": False,
            "next": "已建立個人分支。用 context 開始 AI 對話、inbox 看待辦；完成程式修改後 pub --dry-run。"}


def member_at(r, ref, person, foreign_ok=False):
    """Inspect exact blobs, including scope, before switching to a returning branch."""
    def blob(path):
        entry = r.output("ls-tree", ref, "--", path)
        return json.loads(r.git("cat-file", "blob", entry.split()[2], binary=True).stdout) if entry else None
    scope = blob(".group/group.json")
    if foreign_ok and isinstance(scope, dict) and scope.get("group_id") != r.config["group_id"]:
        return None
    if not isinstance(scope, dict) or any(scope.get(k) != r.config[k] for k in ("group_id", "protocol_version")):
        raise GroupError("既有分支不屬於目前小組；不會切換或覆寫。")
    member = blob(f".group/members/{person}.json")
    if member is not None and (not isinstance(member, dict) or member.get("person_id") != person or
                               member.get("protocol_version") != "0.1"):
        raise GroupError("既有成員描述無效；不會替換身分。")
    return member


def member_branches(r, person):
    refs = r.output("for-each-ref", "--format=%(refname)", f"refs/remotes/{r.remote}/people/{person}/").splitlines()
    return [ref for ref in refs if member_at(r, ref, person, foreign_ok=True)]


def resume_join(r, args):
    branch = f"people/{args.person}/{args.topic}"
    local = "refs/heads/" + branch
    remote = f"refs/remotes/{r.remote}/{branch}"
    has_local, has_remote = exists(r, local), exists(r, remote)
    source = local if has_local else remote if has_remote else r.canonical
    if not member_at(r, source, args.person):
        available = member_branches(r, args.person)
        raise GroupError("找不到這個既有身分／topic，尚未切換分支。",
                         hint="指定原本的 --person 與 --topic。已知分支：" + ", ".join(available) + "。新成員請 join，不加 --resume。")
    if has_remote and not member_at(r, remote, args.person):
        raise GroupError("遠端個人分支缺少對應的成員描述。")
    if has_local and has_remote and not (r.ancestor(local, remote) or r.ancestor(remote, local)):
        raise GroupError("本機與遠端個人分支已分歧；不會切換或重設。",
                         hint="保留兩邊歷史，先檢查 git log 與 diff，再刻意整合。")
    if has_local:
        r.git("switch", branch)
        if has_remote:
            if r.ancestor(local, remote):
                r.git("merge", "--ff-only", remote)
            r.git("branch", "--set-upstream-to", remote, branch)
    elif has_remote:
        r.git("switch", "-c", branch, "--track", remote)
    else:
        r.git("switch", "-c", branch, r.canonical)
    localstate.save(r, "identity.json", {"person_id": args.person})
    return {"person_id": r.identity(), "branch": branch, "resumed": True, "new_membership": False,
            "local_ahead": int(r.output("rev-list", "--count", f"{remote}..HEAD")) if has_remote else None,
            "next": "context --format markdown；inbox。既有提交保留，沒有產生新的成員紀錄或 Push。"}


def doctor(args):
    checks = []
    def add(name, ok, message, action=None, warning=False):
        checks.append({"check": name, "ok": ok, "level": "warning" if warning else "required",
                       "message": message, "action": action})
    add("python", sys.version_info >= (3, 10), "Python " + sys.version.split()[0], "安裝 Python 3.10+。")
    try:
        execute(["git", "--version"], args.repo)
        add("git", True, "Git 可執行。")
        r = ObservedRepository(args.repo, configured=False)
    except GroupError:
        add("repository", False, "找不到可用的 Git Repository。", "先 git clone 小組專案；或使用 --repo 指向正確 clone。")
        return {"ready": False, "checks": checks, "network_used": False}
    author = r.git("var", "GIT_AUTHOR_IDENT", ok=(0, 128)).returncode == 0
    add("git_identity", author, "Git 提交身分已設定。" if author else "尚無 Git 提交身分。",
        'git config user.name "你的名字"；git config user.email "你的信箱"')
    remote = bool(r.git("remote", "get-url", "origin", ok=(0, 2, 128)).stdout.strip())
    add("remote", remote, "origin 已設定。" if remote else "沒有 origin。", "git remote add origin <小組 GitHub URL>")
    if not (r.meta / "group.json").exists():
        tool = (r.root / "groupctl/__main__.py").exists()
        add("group", False, "這是工具原始碼目錄，尚未指向小組專案。" if tool else "尚未建立 .group 設定。",
            "使用 --repo <小組專案>；第一位 init --help，其他人先 clone 小組 repo。")
        return safe({"ready": False, "checks": checks, "network_used": False})
    try:
        r = ObservedRepository(args.repo)
        add("group", True, "小組設定有效。")
        validate_commands(r.config.get("validation_commands", []))
        validation = bool(r.config.get("validation_commands"))
        add("validation", validation, "已設定驗證命令；尚未執行。" if validation else "尚未設定 Tests；不能算 Pass。",
            "在 .group/group.json 設定 validation_commands；不會自動假設測試通過。")
        try:
            person = r.identity()
            add("member", True, "目前身分：" + person)
        except GroupError:
            add("member", False, "此 clone 尚未選擇有效的成員身分。", "join --resume --person <既有ID> --topic <原topic>；新成員用 join。")
        canonical = exists(r, r.canonical)
        add("canonical", canonical, "本機有 canonical ref。" if canonical else "尚無 canonical ref。", "確認網路後 sync；未發布的初始化請 recover。")
        named = r.git("symbolic-ref", "--quiet", "--short", "HEAD", ok=(0, 1)).returncode == 0
        add("branch", named, "目前在具名分支。" if named else "目前是 detached HEAD，協作操作需要具名分支。",
            "保護目前工作後，用 join --resume 恢復原個人分支。")
        dirty = bool(r.git("status", "--porcelain").stdout)
        add("working_tree", not dirty, "有未提交工作；先保護修改再執行需要 clean tree 的操作。" if dirty else "工作目錄乾淨。", warning=True)
    except GroupError as exc:
        add("configuration", False, str(exc), "檢查 .group/group.json；不要修改 immutable events。")
    return safe({"ready": all(c["ok"] for c in checks if c["level"] == "required"), "checks": checks,
                 "network_used": False, "note": "Doctor 是本機設定檢查；不執行測試、不驗證 GitHub 寫入權限。"})


def render_doctor(value):
    lines = ["groupctl 設定檢查（離線、只讀）"]
    for c in value["checks"]:
        lines.append(("✓ " if c["ok"] else "! ") + c["message"])
        if not c["ok"] and c["action"]:
            lines.append("  下一步：" + c["action"])
    return "\n".join(lines)
