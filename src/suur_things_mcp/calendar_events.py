"""Read Apple Calendar events through the native SUUR Dashboard app.

Things mirrors Apple Calendar locally; its SQLite task store has no calendar
events. This bridge only fetches events and never changes either store.
"""

from __future__ import annotations

import datetime
import json
import os
import plistlib
import subprocess
from pathlib import Path


class CalendarEventsError(Exception):
    """Calendar data is unavailable or permission has not been granted."""


_THINGS_CALENDAR_PREFS = (
    Path.home() / "Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac"
    / "Library/Preferences/JLMPQHK86H.com.culturedcode.ThingsMac.plist"
)


def _disabled_calendar_names() -> tuple[bool, set[str]]:
    """Read Things' own Mac calendar choices; never assume all are selected."""
    try:
        with _THINGS_CALENDAR_PREFS.open("rb") as stream:
            prefs = plistlib.load(stream)
        enabled = prefs["calendarEventsEnabled"]
        hints = prefs.get("disabledCalendarEventsCalendarHints", [])
        if not isinstance(enabled, bool) or not isinstance(hints, list):
            raise ValueError("unexpected Things calendar preference format")
        names = set()
        for hint in hints:
            if not isinstance(hint, dict) or not isinstance(hint.get("calendarName"), str):
                raise ValueError("unexpected Things calendar hint")
            names.add(hint["calendarName"])
        return enabled, names
    except (OSError, plistlib.InvalidFileException, KeyError, ValueError) as exc:
        raise CalendarEventsError("Não foi possível ler as agendas escolhidas no Things.") from exc


def read_days(start: datetime.date, count: int) -> list[dict]:
    enabled, disabled_names = _disabled_calendar_names()
    if not enabled:
        return [{"date": (start + datetime.timedelta(days=i)).isoformat(), "events": []} for i in range(count)]
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
        for day in days:
            day["events"] = [event for event in day["events"] if event["calendar"] not in disabled_names]
        return days
    except (KeyError, TypeError, ValueError) as exc:
        raise CalendarEventsError("Resposta inválida do Calendário.") from exc
