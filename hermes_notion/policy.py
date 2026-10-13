"""Bounded ancestry checks for this plugin's comment tools, not workspace ACLs."""
from . import notion_client


def in_scope(token, target_id, root_ids):
    if not token or not target_id or not root_ids:
        return False
    seen = set()
    for _ in range(32):
        if target_id in root_ids:
            return True
        if target_id in seen:
            return False
        seen.add(target_id)
        try:
            obj = notion_client.get_block(token, target_id)
        except Exception:
            return False
        parent = obj.get("parent", {})
        target_id = parent.get(parent.get("type", ""))
        if not isinstance(target_id, str) or not target_id:
            return False
    return False
