# SUUR Order helper

The dashboard Python process cannot inherit macOS Accessibility access from
SUUR Dashboard.app. This small native app selects one Things task and sends
Things' built-in Move Up/Down shortcut. It never writes to the Things database.

Install with `zsh extras/suur-order/install.sh`. Then allow **SUUR Order.app**
in System Settings > Privacy & Security > Device Control and Data Access
(Accessibility on older macOS versions). The first move may also ask whether
SUUR Order can automate Things. Allow it for this feature. Reload the dashboard
after granting access.

The helper accepts only a Things task ID, `up` or `down`, and a bounded number
of steps. The dashboard reads the native order back and reports an error unless
Things confirms the requested position. It targets the running Things process
without changing the foreground app.

The dashboard starts the app through LaunchServices. Executing the helper as a
direct child of the dashboard can make macOS attribute its Accessibility check
to the dashboard, even when SUUR Order is enabled in System Settings.
