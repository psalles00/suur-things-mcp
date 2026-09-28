import AppKit
import Foundation

private enum SUUR {
    static let address = "http://127.0.0.1:8765/"
    static let healthURL = URL(string: address + "api/health")!
    static let serviceLabel = "io.suur.things-dashboard"
}

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    private let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
    private let menu = NSMenu()
    private let stateItem = NSMenuItem(title: "Verificando SUUR…", action: nil, keyEquivalent: "")
    private let startItem = NSMenuItem(title: "Tentar iniciar serviço", action: #selector(startService), keyEquivalent: "")
    private var timer: Timer?
    private var lastHealthy = false

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        configureMenu()
        updateState(healthy: false, version: nil, checking: true)
        checkHealth()
        timer = Timer.scheduledTimer(timeInterval: 5, target: self, selector: #selector(checkHealth), userInfo: nil, repeats: true)
    }

    func applicationWillTerminate(_ notification: Notification) {
        timer?.invalidate()
    }

    private func configureMenu() {
        item.autosaveName = "com.pedrosalles.suur-menu.status"
        item.isVisible = true
        stateItem.isEnabled = false
        menu.addItem(stateItem)
        menu.addItem(.separator())
        menu.addItem(NSMenuItem(title: "Abrir painel", action: #selector(openDashboard), keyEquivalent: ""))
        menu.addItem(NSMenuItem(title: "Copiar endereço", action: #selector(copyAddress), keyEquivalent: ""))
        menu.addItem(.separator())
        menu.addItem(NSMenuItem(title: "Verificar agora", action: #selector(checkHealth), keyEquivalent: ""))
        menu.addItem(startItem)
        menu.addItem(.separator())
        menu.addItem(NSMenuItem(title: "Sair do utilitário", action: #selector(quit), keyEquivalent: ""))
        for menuItem in menu.items where menuItem.action != nil {
            menuItem.target = self
        }
        item.menu = menu
        // A compact item stays discoverable when the menu bar is crowded.
        item.button?.title = "S"
        item.button?.toolTip = "SUUR Things"
    }

    private func updateState(healthy: Bool, version: String?, checking: Bool = false) {
        lastHealthy = healthy
        item.button?.image = nil
        item.button?.contentTintColor = checking ? .secondaryLabelColor : (healthy ? .systemGreen : .systemOrange)
        item.button?.toolTip = checking ? "Verificando SUUR" : (healthy ? "SUUR rodando" : "SUUR parado")
        stateItem.title = checking ? "Verificando SUUR…" : (healthy ? "SUUR rodando\(version.map { " (\($0))" } ?? "")" : "SUUR parado")
        startItem.isHidden = healthy || checking
    }

    @objc private func checkHealth() {
        var request = URLRequest(url: SUUR.healthURL)
        request.cachePolicy = .reloadIgnoringLocalCacheData
        request.timeoutInterval = 1.5
        URLSession.shared.dataTask(with: request) { [weak self] data, response, _ in
            let httpOK = (response as? HTTPURLResponse)?.statusCode == 200
            let payload = data.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] }
            let healthy = httpOK && (payload?["ok"] as? Bool == true)
                && (payload?["database"] as? Bool == true)
                && (payload?["version"] as? String != nil)
            let version = payload?["version"] as? String
            DispatchQueue.main.async {
                self?.updateState(healthy: healthy, version: version)
            }
        }.resume()
    }

    @objc private func openDashboard() {
        guard let url = URL(string: SUUR.address) else { return }
        NSWorkspace.shared.open(url)
    }

    @objc private func copyAddress() {
        let pasteboard = NSPasteboard.general
        pasteboard.clearContents()
        pasteboard.setString(SUUR.address, forType: .string)
    }

    @objc private func startService() {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/bin/launchctl")
        process.arguments = ["kickstart", "-k", "gui/\(getuid())/\(SUUR.serviceLabel)"]
        do {
            try process.run()
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) { [weak self] in self?.checkHealth() }
        } catch {
            updateState(healthy: false, version: nil)
        }
    }

    @objc private func quit() {
        NSApp.terminate(nil)
    }
}

@main
struct SUURMenu {
    static func main() {
        let app = NSApplication.shared
        let delegate = AppDelegate()
        app.delegate = delegate
        app.run()
    }
}
