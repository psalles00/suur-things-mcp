#!/bin/zsh
set -euo pipefail

script_dir=${0:A:h}
app_dir="$HOME/Applications/SUUR Menu.app"
agent_path="$HOME/Library/LaunchAgents/com.pedrosalles.suur-menu.plist"
uid=$(id -u)

mkdir -p "$app_dir/Contents/MacOS" "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
swiftc -O -parse-as-library -framework AppKit "$script_dir/SuurMenu.swift" -o "$app_dir/Contents/MacOS/SuurMenu"
cp "$script_dir/Info.plist" "$app_dir/Contents/Info.plist"
codesign --force --deep --sign - "$app_dir"

cat > "$agent_path" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>com.pedrosalles.suur-menu</string>
<key>ProgramArguments</key><array><string>$app_dir/Contents/MacOS/SuurMenu</string></array>
<key>RunAtLoad</key><true/>
<key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
<key>ThrottleInterval</key><integer>10</integer>
<key>LimitLoadToSessionType</key><string>Aqua</string>
<key>StandardOutPath</key><string>$HOME/Library/Logs/suur-menu.log</string>
<key>StandardErrorPath</key><string>$HOME/Library/Logs/suur-menu.log</string>
</dict></plist>
PLIST

launchctl bootout "gui/$uid" "$agent_path" 2>/dev/null || true
launchctl bootstrap "gui/$uid" "$agent_path"
echo "SUUR Menu installed at $app_dir"
