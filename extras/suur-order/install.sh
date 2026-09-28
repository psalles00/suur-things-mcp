#!/bin/zsh
set -euo pipefail

script_dir=${0:A:h}
app_dir="$HOME/Applications/SUUR Order.app"
mkdir -p "$app_dir/Contents/MacOS"
swiftc -O "$script_dir/SUUROrder.swift" -o "$app_dir/Contents/MacOS/SUUROrder"
cp "$script_dir/Info.plist" "$app_dir/Contents/Info.plist"

# A stable Development signature keeps macOS permission across rebuilds.
identity=$(/usr/bin/security find-identity -v -p codesigning | /usr/bin/sed -n 's/^ *1) \([0-9A-F]*\) "Apple Development:.*$/\1/p')
if [[ -n "$identity" ]]; then
  /usr/bin/codesign --force --sign "$identity" "$app_dir"
else
  /usr/bin/codesign --force --sign - "$app_dir"
fi
echo "SUUR Order installed at $app_dir"
