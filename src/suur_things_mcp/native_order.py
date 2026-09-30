"""Exact Things task order via the native Move Up/Down shortcuts.

The database remains read-only. Restrict moves to one heading in a project or
Inbox, and verify every move against the order read back from Things.
"""

from __future__ import annotations

import re
import json
import subprocess
import tempfile
import time
from pathlib import Path

from . import reads


_ID = re.compile(r"^[A-Za-z0-9_-]{10,80}$")
_ACCESS_ERROR = "SUUR Order did not confirm Device Control and Data Access permission. Reopen its macOS permission or reinstall the helper."
_HELPER = Path.home() / "Applications/SUUR Order.app/Contents/MacOS/SUUROrder"
_HELPER_APP = _HELPER.parent.parent.parent
_ACCESS_CACHE: tuple[float, bool] | None = None
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
_MOVE_TO_INBOX_SCRIPT = r'''
on run argv
    set taskId to item 1 of argv
    tell application "Things3"
        move (to do id taskId) to list "Inbox"
    end tell
end run
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


def order_writable() -> bool:
    # A direct subprocess inherits the dashboard's TCC attribution. On macOS
    # this can report denied even when SUUR Order itself is enabled in Settings.
    # LaunchServices gives the helper its own app identity. The helper writes a
    # receipt because `open` reports launch success, not the app's exit status.
    global _ACCESS_CACHE
    if _ACCESS_CACHE and time.monotonic() - _ACCESS_CACHE[0] < 5:
        return _ACCESS_CACHE[1]
    if not _HELPER.is_file():
        _ACCESS_CACHE = (time.monotonic(), False)
        return False
    allowed = False
    try:
        with tempfile.TemporaryDirectory(prefix="suur-order-check-") as tmp:
            receipt = Path(tmp) / "access"
            launched = subprocess.run(
                ["/usr/bin/open", "-n", "-a", str(_HELPER_APP),
                 "--args", "--check", str(receipt)],
                capture_output=True, timeout=3, check=False,
            )
            if launched.returncode == 0:
                for _ in range(30):
                    if receipt.exists():
                        allowed = receipt.read_text(encoding="utf-8") == "allowed"
                        break
                    time.sleep(0.1)
    except (OSError, subprocess.TimeoutExpired):
        pass
    _ACCESS_CACHE = (time.monotonic(), allowed)
    return allowed


def move_to_inbox(task_id: str) -> None:
    """Use Things' documented move command, then confirm the task is in Inbox."""
    if not _ID.fullmatch(task_id):
        raise NativeOrderError("Invalid task ID.")
    task = reads.get(task_id)
    if not task or task.get("type") != "to-do" or task.get("status") != "incomplete":
        raise NativeOrderError("Task is no longer available in Things.")
    try:
        result = subprocess.run(
            ["/usr/bin/osascript", "-e", _MOVE_TO_INBOX_SCRIPT, "--", task_id],
            capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise NativeOrderError(f"Could not move task to Inbox: {exc}") from exc
    if result.returncode:
        raise NativeOrderError("Could not move task to Inbox: " + result.stderr.strip()[:300])
    for attempt in range(35):
        if attempt:
            time.sleep(0.1)
        if any(item.get("uuid") == task_id for item in reads.inbox()):
            return
    raise NativeOrderError("Things did not confirm the task in Inbox. Refresh both lists.")


def _check_access() -> None:
    if not order_writable():
        raise NativeOrderError(_ACCESS_ERROR)


def placement_target(list_id: str, target_id: str) -> dict:
    """Validate placement against the read-only DB before creating a task."""
    _check_access()  # Fail before creating a task that cannot be positioned.
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


def _move(task_id: str, direction: str, count: int) -> None:
    try:
        result = subprocess.run(
            ["/usr/bin/open", "-n", "-a", str(_HELPER_APP),
             "--args", task_id, direction, str(count)],
            capture_output=True, text=True, timeout=max(10, count * 0.2 + 5),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise NativeOrderError(f"Things did not move the task: {exc}") from exc
    if result.returncode:
        raise NativeOrderError("Things did not move the task: " + result.stderr.strip()[:300])


def reorder(list_id: str, moved_id: str, target_id: str, before: bool) -> list[str]:
    """Move an open task beside another task in the same native heading.

    Re-read at execution time, so a stale browser never overwrites a whole
    sequence submitted from an older tab. A failed readback is reported rather
    than presented as success.
    """
    _check_access()
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
    destination = order.index(moved_id)
    source = original.index(moved_id)
    steps = abs(source - destination)
    _move(moved_id, "up" if source > destination else "down", steps)
    for attempt in range(max(30, int(steps * 0.7) + 30)):
        if attempt:
            time.sleep(0.1)
        observed = native_ids(list_id)
        if observed == order:
            return order
        if set(observed) != set(original):
            raise NativeOrderError("Things changed while moving the task. Refresh both lists.")
    raise NativeOrderError(
        "Things did not confirm the requested position. Check SUUR Order's Device Control and Data Access permission and the native Things app."
    )
