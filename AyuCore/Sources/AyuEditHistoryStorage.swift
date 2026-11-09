import Foundation

public struct AyuEditEntry: Codable {
    public let timestamp: Int32
    public let text: String

    public init(timestamp: Int32, text: String) {
        self.timestamp = timestamp
        self.text = text
    }
}

/// Потокобезопасное хранилище истории правок сообщений
public final class AyuEditHistoryStorage {
    public static let shared = AyuEditHistoryStorage()

    private let lock = NSLock()
    private let storagePath: URL

    private var inMemoryEdits: [String: [AyuEditEntry]] = [:]

    private init() {
        let fileManager = FileManager.default
        let appSupport = fileManager.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        let dir = appSupport.appendingPathComponent("AyuGram", isDirectory: true)

        try? fileManager.createDirectory(at: dir, withIntermediateDirectories: true, attributes: nil)
        self.storagePath = dir.appendingPathComponent("edits_history.json")

        loadFromDisk()
    }

    private func keyFor(peerId: Int64, messageId: Int32) -> String {
        return "\(peerId)_\(messageId)"
    }

    /// Сохранение старой версии сообщения перед обновлением
    public func recordEdit(peerId: Int64, messageId: Int32, previousText: String, editTimestamp: Int32) {
        guard !previousText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }

        lock.lock()
        defer { lock.unlock() }

        let key = keyFor(peerId: peerId, messageId: messageId)
        var list = inMemoryEdits[key] ?? []

        // Избегаем дублирования идентичного текста
        if let last = list.last, last.text == previousText {
            return
        }

        list.append(AyuEditEntry(timestamp: editTimestamp, text: previousText))
        inMemoryEdits[key] = list

        persistToDisk()
    }

    /// Получение всех сохраненных предыдущих версий сообщения
    public func editsFor(peerId: Int64, messageId: Int32) -> [AyuEditEntry] {
        lock.lock()
        defer { lock.unlock() }

        let key = keyFor(peerId: peerId, messageId: messageId)
        return inMemoryEdits[key] ?? []
    }

    private func loadFromDisk() {
        guard let data = try? Data(contentsOf: storagePath),
              let decoded = try? JSONDecoder().decode([String: [AyuEditEntry]].self, from: data) else {
            return
        }
        self.inMemoryEdits = decoded
    }

    private func persistToDisk() {
        guard let data = try? JSONEncoder().encode(inMemoryEdits) else { return }
        try? data.write(to: storagePath, options: [.atomic])
    }
}
