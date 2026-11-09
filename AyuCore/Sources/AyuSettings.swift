import Foundation

/// Глобальные настройки AyuGram для iOS
public final class AyuSettings {
    public static let shared = AyuSettings()

    private let defaults = UserDefaults(suiteName: "group.org.telegram.ayugram") ?? UserDefaults.standard

    private enum Keys {
        static let ghostMode = "ayugram_ghost_mode"
        static let noReadHistory = "ayugram_no_read_history"
        static let noTyping = "ayugram_no_typing"
        static let antiDelete = "ayugram_anti_delete"
        static let editHistory = "ayugram_edit_history"
        static let markDeletedMessages = "ayugram_mark_deleted"
        static let stealthSecretChats = "ayugram_stealth_secret_chats"
    }

    private init() {
        registerDefaults()
    }

    private func registerDefaults() {
        defaults.register(defaults: [
            Keys.ghostMode: true,
            Keys.noReadHistory: true,
            Keys.noTyping: true,
            Keys.antiDelete: true,
            Keys.editHistory: true,
            Keys.markDeletedMessages: true,
            Keys.stealthSecretChats: false
        ])
    }

    /// Режим призрака: не отправлять статус присутствия онлайн
    public var isGhostModeEnabled: Bool {
        get { return defaults.bool(forKey: Keys.ghostMode) }
        set { defaults.set(newValue, forKey: Keys.ghostMode) }
    }

    /// Запрет отправки отчета о прочтении сообщений
    public var isNoReadHistoryEnabled: Bool {
        get { return defaults.bool(forKey: Keys.noReadHistory) }
        set { defaults.set(newValue, forKey: Keys.noReadHistory) }
    }

    /// Запрет отправки статуса «печатает / записывает аудио»
    public var isNoTypingEnabled: Bool {
        get { return defaults.bool(forKey: Keys.noTyping) }
        set { defaults.set(newValue, forKey: Keys.noTyping) }
    }

    /// Анти-удаление сообщений: предотвращает удаление из локального хранилища Postbox
    public var isAntiDeleteEnabled: Bool {
        get { return defaults.bool(forKey: Keys.antiDelete) }
        set { defaults.set(newValue, forKey: Keys.antiDelete) }
    }

    /// Сохранение истории редактирования сообщений
    public var isEditHistoryEnabled: Bool {
        get { return defaults.bool(forKey: Keys.editHistory) }
        set { defaults.set(newValue, forKey: Keys.editHistory) }
    }

    /// Показывать визуальный бейдж [Удалено] в интерфейсе пузыря сообщения
    public var shouldMarkDeletedMessages: Bool {
        get { return defaults.bool(forKey: Keys.markDeletedMessages) }
        set { defaults.set(newValue, forKey: Keys.markDeletedMessages) }
    }
}
