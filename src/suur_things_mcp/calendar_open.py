"""Reveal a displayed Calendar event using Apple's documented `show` command."""

from __future__ import annotations

import subprocess


class CalendarOpenError(Exception):
    """The event could not be located or shown without ambiguity."""


_REVEAL_SCRIPT = r'''
function run(argv) {
    var calendarName = argv[0], title = argv[1], iso = argv[2],
        startTime = argv[3], endTime = argv[4];
    var parts = iso.split("-").map(Number);
    var day = new Date(parts[0], parts[1] - 1, parts[2]);
    var next = new Date(parts[0], parts[1] - 1, parts[2] + 1);
    var app = Application("Calendar");
    var calendars = app.calendars.whose({name: calendarName})();
    if (calendars.length !== 1) throw new Error("Calendar name is ambiguous or unavailable");
    var events = calendars[0].events.whose({summary: title})();
    function hhmm(date) {
        return ("0" + date.getHours()).slice(-2) + ":" + ("0" + date.getMinutes()).slice(-2);
    }
    var matches = events.filter(function(event) {
        var start = event.startDate(), end = event.endDate();
        if (!(start < next && end > day)) return false;
        if (startTime && hhmm(start) !== startTime) return false;
        if (endTime && hhmm(end) !== endTime) return false;
        return true;
    });
    if (matches.length !== 1) throw new Error("Event is unavailable or ambiguous");
    matches[0].show();
    return "ok";
}
'''


def reveal(event: dict, date: str) -> None:
    try:
        result = subprocess.run(
            ["/usr/bin/osascript", "-l", "JavaScript", "-e", _REVEAL_SCRIPT, "--",
             event["calendar"], event["title"], date,
             event.get("start_time") or "", event.get("end_time") or ""],
            capture_output=True, text=True, timeout=20, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CalendarOpenError("Não foi possível abrir o Calendário.") from exc
    if result.returncode:
        detail = result.stderr.strip().splitlines()
        raise CalendarOpenError(detail[-1] if detail else "O evento não foi encontrado no Calendário.")
