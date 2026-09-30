"""Move a Things to-do to its recoverable Trash through Things' AppleScript API."""

from __future__ import annotations

import re
import sqlite3
import subprocess
import time

from . import reads


_ID = re.compile(r"^[A-Za-z0-9_-]{10,80}$")
_DELETE_SCRIPT = r'''
on run argv
    set taskId to item 1 of argv
    tell application "Things3"
        delete (to do id taskId)
    end tell
end run
'''


class TaskTrashError(RuntimeError):
    """Things did not confirm a to-do in its Trash."""


def move_to_trash(task_id: str) -> None:
    if not _ID.fullmatch(task_id):
        raise TaskTrashError("ID de tarefa inválido.")
    try:
        state = reads.todo_trashed(task_id)
    except sqlite3.Error as exc:
        raise TaskTrashError("Não foi possível ler a tarefa no banco do Things.") from exc
    if state is None:
        raise TaskTrashError("Tarefa não encontrada no Things.")
    if state:
        raise TaskTrashError("A tarefa já está na Lixeira.")
    try:
        result = subprocess.run(
            ["/usr/bin/osascript", "-e", _DELETE_SCRIPT, "--", task_id],
            capture_output=True, text=True, timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TaskTrashError("O Things não respondeu à exclusão da tarefa.") from exc
    if result.returncode:
        raise TaskTrashError("O Things não moveu a tarefa para a Lixeira: " + result.stderr.strip()[:250])
    for attempt in range(30):
        if attempt:
            time.sleep(0.1)
        try:
            if reads.todo_trashed(task_id) is True:
                return
        except sqlite3.Error as exc:
            raise TaskTrashError("Não foi possível confirmar a Lixeira no Things.") from exc
    raise TaskTrashError("O Things não confirmou a tarefa na Lixeira. Confira no app.")
