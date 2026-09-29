# SUUR Dashboard login app

This native, background macOS app starts the installed `suur-things-mcp` Python package at login. It gives macOS a dedicated app identity for its privacy controls. Build and install with `zsh extras/suur-dashboard/install.sh` after installing the package with `uv tool install`.

The Things database is inside a protected Group Container. On this Mac, a plain launchd Python process was denied access (`Operation not permitted`), even though the same Python command worked in Terminal. Open **System Settings → Privacy & Security → Full Disk Access**, add `~/Applications/SUUR Dashboard.app`, enable it, then restart the `io.suur.things-dashboard` LaunchAgent. This permission is a manual macOS choice. Check `http://127.0.0.1:8765/api/health`: `database: true` confirms it worked. If the app still cannot read the database, the permission did not cover the Python child process; do not grant Full Disk Access to the shared Homebrew Python as a blind workaround.

## Calendar events in Teux Deux

Things mirrors Apple Calendar events locally. Teux Deux reads the same Apple Calendar store through EventKit and displays events above Things tasks in each date column, with a calendar icon instead of a checkbox. Clicking an event asks Calendar to reveal that specific occurrence; macOS may request Automation permission on the first click. SUUR never edits calendar events. On first use, grant **SUUR Dashboard** Calendar access when macOS asks. If you declined, enable it in **System Settings → Privacy & Security → Calendars**. SUUR reads Things' local `calendarEventsEnabled` and `disabledCalendarEventsCalendarHints` preferences and hides events from calendars deselected in Things → Settings → Calendar Events. These are undocumented Things keys; if the preferences cannot be read, SUUR shows an error rather than exposing every calendar. The native bridge currently reports calendar names, so calendars with the same name in different accounts cannot be distinguished; opening an ambiguous event fails instead of selecting the wrong one.

## Editing existing Things tasks

In **Things → Settings → General**, enable **Things URLs**, then select **Manage** and copy its auth token. In a Terminal opened at the repository root, run `python3 extras/suur-dashboard/configure_token.py` and paste it when prompted. Input is hidden. The token is saved to `~/.config/suur-things-mcp/token` with mode `0600`, outside Git and the LaunchAgent. Refresh the dashboard. `/api/health` reports `auth: true` when the service can read it; the token itself is never returned.

The token permits edits to existing Things items through the URL Scheme. Keep it private. Creating new tasks does not need it.
