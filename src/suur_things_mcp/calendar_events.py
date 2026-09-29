"""Read Apple Calendar events through the native SUUR Dashboard app.

Things mirrors Apple Calendar locally; its SQLite task store has no calendar
events. This bridge only fetches events and never changes either store.
"""

from __future__ import annotations

import datetime
import json
import os
import subprocess


class CalendarEventsError(Exception):
    """Calendar data is unavailable or permission has not been granted."""


def read_days(start: datetime.date, count: int) -> list[dict]:
    helper = os.environ.get("SUUR_CALENDAR_HELPER", "")
    if not helper or not os.path.isfile(helper) or not os.access(helper, os.X_OK):
        raise CalendarEventsError("Instale o app SUUR Dashboard para mostrar eventos do Calendário.")
    try:
        result = subprocess.run(
            [helper, "--calendar-events", start.isoformat(), str(count)],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CalendarEventsError("Não foi possível ler os eventos do Calendário.") from exc
    if result.returncode:
        detail = result.stderr.strip().splitlines()
        raise CalendarEventsError(detail[-1] if detail else "Acesso ao Calendário indisponível.")
    try:
        data = json.loads(result.stdout)
        days = data["days"]
        if not isinstance(days, list):
            raise ValueError("bad calendar response")
        return days
    except (KeyError, TypeError, ValueError) as exc:
        raise CalendarEventsError("Resposta inválida do Calendário.") from exc
