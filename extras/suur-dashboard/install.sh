#!/bin/zsh
set -euo pipefail

script_dir=${0:A:h}
app_dir="$HOME/Applications/SUUR Dashboard.app"
agent_path="$HOME/Library/LaunchAgents/io.suur.things-dashboard.plist"
python_bin="$HOME/.local/share/uv/tools/suur-things-mcp/bin/python"
uid=$(id -u)

if [[ ! -x "$python_bin" ]]; then
  print -u2 "SUUR Python installation not found at $python_bin"
  exit 1
fi

mkdir -p "$app_dir/Contents/MacOS" "$app_dir/Contents/Resources" "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
swiftc -O "$script_dir/SUURDashboard.swift" -o "$app_dir/Contents/MacOS/SUURDashboard"
cp "$script_dir/Info.plist" "$app_dir/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Clear dict" "$app_dir/Contents/Resources/Service.plist" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Add :PythonExecutable string $python_bin" "$app_dir/Contents/Resources/Service.plist"
codesign --force --deep --sign - "$app_dir"

cat > "$agent_path" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>io.suur.things-dashboard</string>
<key>ProgramArguments</key><array><string>$app_dir/Contents/MacOS/SUURDashboard</string></array>
<key>RunAtLoad</key><true/>
<key>KeepAlive</key><true/>
<key>StandardOutPath</key><string>$HOME/Library/Logs/suur-things-dashboard.log</string>
<key>StandardErrorPath</key><string>$HOME/Library/Logs/suur-things-dashboard.log</string>
</dict></plist>
PLIST

launchctl bootout "gui/$uid/io.suur.things-dashboard" 2>/dev/null || true
if ! launchctl bootstrap "gui/$uid" "$agent_path"; then
  # launchd can briefly retain the old label after bootout.
  sleep 1
  launchctl bootstrap "gui/$uid" "$agent_path"
fi
echo "SUUR Dashboard installed at $app_dir"
