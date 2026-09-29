import Foundation
import Darwin
import EventKit

// The same Apple Calendar store that Things mirrors in Today and Upcoming.
// This read-only mode runs under SUUR Dashboard's privacy identity.
if CommandLine.arguments.count == 4 && CommandLine.arguments[1] == "--calendar-events" {
    let formatter = DateFormatter()
    formatter.locale = Locale(identifier: "en_US_POSIX")
    formatter.timeZone = .current
    formatter.dateFormat = "yyyy-MM-dd"
    guard let first = formatter.date(from: CommandLine.arguments[2]),
          let count = Int(CommandLine.arguments[3]), (3...7).contains(count),
          let last = Calendar.current.date(byAdding: .day, value: count, to: first) else {
        fputs("Invalid calendar date range\n", stderr)
        exit(2)
    }
    let store = EKEventStore()
    let status = EKEventStore.authorizationStatus(for: .event)
    if status == .notDetermined {
        let semaphore = DispatchSemaphore(value: 0)
        if #available(macOS 14.0, *) {
            store.requestFullAccessToEvents { _, _ in semaphore.signal() }
        } else {
            store.requestAccess(to: .event) { _, _ in semaphore.signal() }
        }
        _ = semaphore.wait(timeout: .now() + 25)
    }
    let granted = EKEventStore.authorizationStatus(for: .event)
    let canRead: Bool
    if #available(macOS 14.0, *) { canRead = granted == .fullAccess }
    else { canRead = granted == .authorized }
    guard canRead else {
        fputs("Calendar access is unavailable. Enable SUUR Dashboard in System Settings > Privacy & Security > Calendars.\n", stderr)
        exit(3)
    }
    let predicate = store.predicateForEvents(withStart: first, end: last, calendars: nil)
    let events = store.events(matching: predicate)
    let timeFormatter = DateFormatter()
    timeFormatter.locale = Locale(identifier: "pt_BR")
    timeFormatter.timeZone = .current
    timeFormatter.dateFormat = "HH:mm"
    var days = [[String: Any]]()
    for offset in 0..<count {
        guard let day = Calendar.current.date(byAdding: .day, value: offset, to: first),
              let end = Calendar.current.date(byAdding: .day, value: 1, to: day) else { continue }
        let visible = events.filter { $0.startDate < end && $0.endDate > day }
            .sorted { a, b in
                if a.isAllDay != b.isAllDay { return a.isAllDay }
                if a.startDate != b.startDate { return a.startDate < b.startDate }
                return (a.title ?? "") < (b.title ?? "")
            }
        let entries: [[String: Any]] = visible.map { event in
            let startTime = event.isAllDay || event.startDate < day ? "" : timeFormatter.string(from: event.startDate)
            let endTime = event.isAllDay ? "" : timeFormatter.string(from: event.endDate)
            return ["title": event.title ?? "(sem título)",
                    "calendar": event.calendar.title, "all_day": event.isAllDay,
                    "start_time": startTime, "end_time": endTime]
        }
        days.append(["date": formatter.string(from: day), "events": entries])
    }
    do {
        let data = try JSONSerialization.data(withJSONObject: ["days": days], options: [])
        FileHandle.standardOutput.write(data)
        exit(0)
    } catch {
        fputs("Calendar serialization failed: \(error)\n", stderr)
        exit(4)
    }
}

let app = Bundle.main
guard let configURL = app.url(forResource: "Service", withExtension: "plist"),
      let config = NSDictionary(contentsOf: configURL),
      let python = config["PythonExecutable"] as? String else {
    fputs("SUUR Dashboard: missing Service.plist\n", stderr)
    exit(1)
}

let child = Process()
// The dashboard calls this binary for EventKit reads; no separate app identity
// or Calendar database access is needed from Python.
setenv("SUUR_CALENDAR_HELPER", CommandLine.arguments[0], 1)
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
