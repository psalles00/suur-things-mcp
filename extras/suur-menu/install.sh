#!/bin/zsh
set -euo pipefail

script_dir=${0:A:h}
app_dir="$HOME/Applications/SUUR Menu.app"
agent_path="$HOME/Library/LaunchAgents/com.pedrosalles.suur-menu.plist"
uid=$(id -u)

launchctl bootout "gui/$uid/com.pedrosalles.suur-menu" 2>/dev/null || true
# `open -W` can exit while the status app survives as a launchd child. Reusing
# that process leaves the old binary and old status item running after upgrade.
for app_pid in ${(f)"$(ps -Ao pid=,comm= | awk -v app="$app_dir/Contents/MacOS/SuurMenu" 'index($0, app) > 0 { print $1 }')"}; do
  [[ -n "$app_pid" ]] && kill "$app_pid" 2>/dev/null || true
done

mkdir -p "$app_dir/Contents/MacOS" "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
swiftc -O -parse-as-library -framework AppKit "$script_dir/SuurMenu.swift" -o "$app_dir/Contents/MacOS/SuurMenu"
cp "$script_dir/Info.plist" "$app_dir/Contents/Info.plist"
codesign --force --deep --sign - "$app_dir"

cat > "$agent_path" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>com.pedrosalles.suur-menu</string>
<key>ProgramArguments</key><array>
<string>/usr/bin/open</string><string>-g</string><string>-W</string><string>-a</string><string>$app_dir</string>
</array>
<key>RunAtLoad</key><true/>
<key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
<key>ThrottleInterval</key><integer>10</integer>
<key>LimitLoadToSessionType</key><string>Aqua</string>
<key>StandardOutPath</key><string>$HOME/Library/Logs/suur-menu.log</string>
<key>StandardErrorPath</key><string>$HOME/Library/Logs/suur-menu.log</string>
</dict></plist>
PLIST

launchctl bootstrap "gui/$uid" "$agent_path"
echo "SUUR Menu installed at $app_dir"
