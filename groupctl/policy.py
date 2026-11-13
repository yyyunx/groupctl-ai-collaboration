"""Shared finalization and blocker policy; decisions remain explicit events."""

def unresolved_blockers(events):
    resolved = {event_id for e in events for event_id in e.get("resolves_events", [])}
    return [e for e in events if e["event_type"] == "blocker" and e["event_id"] not in resolved]


def final_concerns(r, events, commit):
    incorporated = {e["change_id"] for e in events if e["event_type"] == "change_published"
                    and r.ancestor(e["commit"], commit)}
    resolved = {event_id for e in events for event_id in e.get("resolves_events", [])}
    latest_reviews, latest_integrations = {}, {}
    for event in events:
        if event.get("change_id") not in incorporated:
            continue
        if event["event_type"] == "review":
            latest_reviews[event["change_id"]] = event
        if event["event_type"] == "integration_result" and r.ancestor(event["merge_commit"], commit):
            latest_integrations[event["change_id"]] = event
    concerns = [e for e in latest_reviews.values() if e["verdict"] != "accept"]
    concerns += [e for e in latest_integrations.values() if e["result"] != "success"]
    return [e["event_id"] for e in concerns if e["event_id"] not in resolved]
