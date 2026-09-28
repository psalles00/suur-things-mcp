# SUUR Menu

Small native macOS menu bar utility. It checks `http://127.0.0.1:8765/api/health` every five seconds, shows whether the dashboard can read Things, and offers shortcuts to open or copy its address. When the dashboard is unavailable, it can ask launchd to restart the `io.suur.things-dashboard` service.

Install the dashboard first with `suur-things-mcp dashboard --install-service`. Then run `zsh extras/suur-menu/install.sh` from the repository root. The installer compiles the Swift source locally, puts the app in `~/Applications`, and adds a login LaunchAgent. Xcode Command Line Tools are required. No Docker or VM is needed.

The menu utility has a fixed local address and requires the dashboard service label above. It does not access the Things database or any account.
