import Foundation
import Darwin

let app = Bundle.main
guard let configURL = app.url(forResource: "Service", withExtension: "plist"),
      let config = NSDictionary(contentsOf: configURL),
      let python = config["PythonExecutable"] as? String else {
    fputs("SUUR Dashboard: missing Service.plist\n", stderr)
    exit(1)
}

let child = Process()
child.executableURL = URL(fileURLWithPath: python)
child.arguments = ["-m", "suur_things_mcp", "dashboard", "--no-open"]
child.standardOutput = FileHandle.standardOutput
child.standardError = FileHandle.standardError

signal(SIGTERM, SIG_IGN)
signal(SIGINT, SIG_IGN)
let signals = [SIGTERM, SIGINT].map { number in
    let source = DispatchSource.makeSignalSource(signal: number, queue: .main)
    source.setEventHandler {
        if child.isRunning { child.terminate() }
    }
    source.resume()
    return source
}

do {
    try child.run()
    while child.isRunning {
        RunLoop.main.run(until: Date(timeIntervalSinceNow: 0.2))
    }
    _ = signals
    exit(child.terminationStatus)
} catch {
    fputs("SUUR Dashboard: could not start Python: \(error)\n", stderr)
    exit(1)
}
