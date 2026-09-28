"""Exact Things task order via its undocumented AppleScript reorder command.

The database remains read-only. Restrict writes to one project or Inbox, keep
the complete open-task sequence, and verify the result from Things afterwards.
"""

from __future__ import annotations

import re
import json
import subprocess
import time

from . import reads


_ID = re.compile(r"^[A-Za-z0-9_-]{10,80}$")
_SCRIPT = r'''
on run argv
    set containerKind to item 1 of argv
    set containerID to item 2 of argv
    set orderedIDs to item 3 of argv
    tell application "Things3"
        if containerKind is "inbox" then
            set destinationContainer to list id "TMInboxListSource"
        else
            set destinationContainer to project id containerID
        end if
        _private_experimental_ reorder to dos in destinationContainer with ids orderedIDs
    end tell
end run
'''
_READ_SCRIPT = r'''
function run(argv) {
    var things = Application('Things3');
    var kind = argv[0], id = argv[1];
    var container = kind === 'inbox'
        ? things.lists.byId('TMInboxListSource')
        : things.projects.byId(id);
    if (!container.exists()) throw new Error('Things list not found');
    return JSON.stringify(container.toDos().map(function(x) { return String(x.id()); }));
}
'''


class NativeOrderError(RuntimeError):
    pass


def native_ids(list_id: str) -> list[str]:
    if list_id != "inbox" and not _ID.fullmatch(list_id):
        raise NativeOrderError("Exact ordering is available only in Inbox and projects.")
    try:
        result = subprocess.run(
            ["/usr/bin/osascript", "-l", "JavaScript", "-e", _READ_SCRIPT, "--",
             "inbox" if list_id == "inbox" else "project", list_id],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode:
            raise NativeOrderError("Could not read the native order from Things: " + result.stderr.strip()[:300])
        ids = json.loads(result.stdout)
        if not isinstance(ids, list) or any(not isinstance(i, str) or not _ID.fullmatch(i) for i in ids):
            raise ValueError("invalid task IDs")
        return ids
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        raise NativeOrderError(f"Could not read the native order from Things: {exc}") from exc


def placement_target(list_id: str, target_id: str) -> dict:
    """Validate placement against the read-only DB before creating a task."""
    if list_id == "inbox":
        tasks = reads.inbox()
    elif _ID.fullmatch(list_id):
        project = reads.get(list_id)
        if not project or project.get("type") != "project":
            raise NativeOrderError("Exact ordering is available only in Inbox and projects.")
        tasks = reads.todos(project_uuid=list_id, status="incomplete")
    else:
        raise NativeOrderError("Exact ordering is available only in Inbox and projects.")
    target = next((t for t in tasks if t.get("uuid") == target_id
                   and t.get("type") == "to-do" and t.get("status") == "incomplete"), None)
    if target is None:
        raise NativeOrderError("Target task is no longer in Things. Refresh the list.")
    return target


def _tasks_and_order(list_id: str) -> tuple[list[dict], list[str]]:
    if list_id == "inbox":
        tasks = reads.inbox()
    elif _ID.fullmatch(list_id):
        obj = reads.get(list_id)
        if not obj or obj.get("type") != "project":
            raise NativeOrderError("Exact ordering is available only in Inbox and projects.")
        tasks = reads.todos(project_uuid=list_id, status="incomplete")
    else:
        raise NativeOrderError("Exact ordering is available only in Inbox and projects.")
    by_id = {t["uuid"]: t for t in tasks if t.get("type") == "to-do" and t.get("status") == "incomplete"}
    order = native_ids(list_id)
    if not set(by_id).issubset(order):
        raise NativeOrderError("Things order and database disagree. Refresh after Things finishes syncing.")
    return [by_id[i] for i in order if i in by_id], order


def _tasks(list_id: str) -> list[dict]:
    return _tasks_and_order(list_id)[0]


def _write(list_id: str, ids: list[str]) -> None:
    if not ids or any(not _ID.fullmatch(i) for i in ids) or len(ids) != len(set(ids)):
        raise NativeOrderError("Invalid Things task order.")
    kind = "inbox" if list_id == "inbox" else "project"
    try:
        result = subprocess.run(
            ["/usr/bin/osascript", "-e", _SCRIPT, "--", kind, list_id, ",".join(ids)],
            capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise NativeOrderError(f"Things did not accept the order: {exc}") from exc
    if result.returncode:
        raise NativeOrderError("Things did not accept the order: " + result.stderr.strip()[:300])


def reorder(list_id: str, moved_id: str, target_id: str, before: bool) -> list[str]:
    """Move an open task beside another task in the same native heading.

    Re-read at execution time, so a stale browser never overwrites a whole
    sequence submitted from an older tab. A failed readback is reported rather
    than presented as success.
    """
    if not _ID.fullmatch(moved_id) or not _ID.fullmatch(target_id):
        raise NativeOrderError("Invalid task ID.")
    tasks, original = _tasks_and_order(list_id)
    by_id = {t["uuid"]: t for t in tasks}
    if moved_id not in by_id or target_id not in by_id:
        raise NativeOrderError("Task moved or disappeared in Things. Refresh the list.")
    if moved_id == target_id:
        return native_ids(list_id)
    if (by_id[moved_id].get("heading") or "") != (by_id[target_id].get("heading") or ""):
        raise NativeOrderError("Move tasks within the same heading to keep the Things order exact.")
    order = [i for i in original if i != moved_id]
    idx = order.index(target_id) + (0 if before else 1)
    order.insert(idx, moved_id)
    if order == original:
        return order
    _write(list_id, order)
    for _ in range(12):
        time.sleep(0.1)
        try:
            current_ids = native_ids(list_id)
        except NativeOrderError:
            continue  # Things can briefly stop answering Apple Events while syncing.
        if current_ids == order:
            return order
        if set(current_ids) != set(original):
            raise NativeOrderError("Things changed while reordering. Refresh both lists.")
    raise NativeOrderError("Things did not confirm the new order. Check the native app.")
