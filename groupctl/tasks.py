"""Attention suggestions from facts, never a dispatcher or automatic assignment."""
from .presentation import summary, safe
from .policy import unresolved_blockers


def review_candidates(r, events):
    latest = {}
    for e in events:
        if e["event_type"] == "review":
            latest[e["change_id"]] = e
    return [(e, latest.get(e["change_id"])) for e in events if e["event_type"] == "change_published"
            and e["proposed_for_integration"] and not r.ancestor(e["commit"], r.canonical)]


def attention(r, events, view):
    person = view["person_id"]
    resolved = {ref for e in events for ref in e.get("resolves_events", [])}
    answered = {ref for e in events if e["event_type"] == "answer" for ref in e["related_events"]}
    tasks = []
    def add(kind, event, title, command, requires_input=False, shared=False):
        tasks.append({"kind": kind, "event_id": event.get("event_id"), "change_id": event.get("change_id"),
            "from_person": event.get("person_id"), "title": title, "command": command,
            "requires_input": requires_input, "responsibility": "shared_suggestion_not_assignment" if shared else "current_member_context"})
    for change, review in review_candidates(r, events):
        if change["person_id"] != person:
            if not review or (review["verdict"] != "accept" and review["person_id"] != person):
                add("review_change", change, "可協助審查隊友修改（未指派）：先檢查精確 diff。", ["inspect", change["change_id"]], shared=True)
        elif review and review["verdict"] != "accept" and review["event_id"] not in resolved:
            add("respond_review", review, "你的修改收到審查意見：檢查問題、回覆或修正後重新發布。", ["trace", change["change_id"]])
        elif r.ancestor(change["commit"]):
            add("canonical_pending", change, "你的修改尚未納入正式歷史；先檢查 Review、INT 與測試證據。", ["trace", change["change_id"]])
    for event in events:
        if event["event_type"] == "question" and event["event_id"] not in answered | resolved:
            if event["person_id"] == person:
                add("waiting_for_answer", event, "你的問題尚待隊友回答。", ["inbox", "--type", "answer", "--relevant"])
            else:
                add("answer_question", event, "可回覆小組公開問題（未指定答覆者）。",
                    ["answer", event["question_id"], "--text", "<實際回覆>"], requires_input=True, shared=True)
    for event in unresolved_blockers(events):
        add("blocker", event, event["requested_action"], ["resolve", event["event_id"], "--reason", "<實際解決理由與證據>"],
            requires_input=True, shared=True)
    integrations = {}
    for event in events:
        if event["event_type"] == "integration_result":
            integrations[(event["change_id"], event["target_branch"])] = event
    for event in integrations.values():
        if event["result"] != "success" and event["event_id"] not in resolved and (
                event["person_id"] == person or event["target_branch"] == view["branch"]):
            add("failed_integration", event, "整合驗證尚未通過：先讀失敗證據，修正後重新 INT 與 assessment。", ["trace", event["change_id"]])
    if view["pending_integration"]:
        add("finish_integration", view["pending_integration"], "整合尚未完成：實際檢查語意，再提交精確 HEAD 的 assessment。", ["template", "semantic"])
    if view["unpublished_events"]:
        add("recover_publication", {}, "有本機事件尚未公開；先診斷，不要重複 PUB。", ["recover"])
    return safe(tasks)


def unreviewed(r, events):
    return [summary(change) | {"attention": "not_reviewed"} for change, review in review_candidates(r, events) if review is None]
