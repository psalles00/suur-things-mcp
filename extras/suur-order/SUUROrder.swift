import AppKit
import ApplicationServices
import Foundation

let args = CommandLine.arguments
let checkReceipt = args.count == 3 && args[1] == "--check" ? args[2] : nil
let accessibilityGranted = AXIsProcessTrusted()
if let checkReceipt {
    try? (accessibilityGranted ? "allowed" : "denied").write(
        toFile: checkReceipt, atomically: true, encoding: .utf8
    )
}
guard accessibilityGranted else {
    fputs("SUUR Order needs macOS Accessibility access.\n", stderr)
    exit(2)
}
if (args.count == 2 || checkReceipt != nil) && args[1] == "--check" {
    exit(0)
}
guard args.count == 4,
      args[1].range(of: "^[A-Za-z0-9_-]{10,80}$", options: .regularExpression) != nil,
      ["up", "down"].contains(args[2]),
      let count = Int(args[3]), (1...500).contains(count) else {
    fputs("Invalid SUUR Order request.\n", stderr)
    exit(64)
}

let taskID = args[1]
let script = NSAppleScript(source: "tell application \"Things3\" to show (to do id \"\(taskID)\")")!
var appleError: NSDictionary?
_ = script.executeAndReturnError(&appleError)
if let appleError {
    fputs("Could not select task in Things: \(appleError)\n", stderr)
    exit(3)
}
guard let things = NSRunningApplication.runningApplications(withBundleIdentifier: "com.culturedcode.ThingsMac").first else {
    fputs("Things is not running.\n", stderr)
    exit(4)
}

usleep(120_000)
let key: CGKeyCode = args[2] == "up" ? 126 : 125
for _ in 0..<count {
    guard let down = CGEvent(keyboardEventSource: nil, virtualKey: key, keyDown: true),
          let up = CGEvent(keyboardEventSource: nil, virtualKey: key, keyDown: false) else {
        fputs("Could not create keyboard event.\n", stderr)
        exit(5)
    }
    down.flags = .maskCommand
    up.flags = .maskCommand
    down.postToPid(things.processIdentifier)
    up.postToPid(things.processIdentifier)
    usleep(60_000)
}
