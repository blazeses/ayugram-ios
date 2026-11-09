import Foundation
import AVFoundation
import UIKit
import UserNotifications

/// Сервис фонового удержания соединения (Keep-Alive) для TrollStore на iOS 15+.
/// Предотвращает выгрузку приложения системой Jetsam и держит постоянное соединение
/// с MTProto для мгновенной доставки сообщений и локальных пуш-уведомлений.
public final class AyuBackgroundKeeper {
    public static let shared = AyuBackgroundKeeper()

    private var audioPlayer: AVAudioPlayer?
    private var bgTask: UIBackgroundTaskIdentifier = .invalid
    private var isRunning = false

    private init() {}

    /// Активация непрерывного фонового режима
    public func start() {
        guard !isRunning else { return }
        isRunning = true

        NotificationCenter.default.addObserver(self, selector: #selector(appDidEnterBackground), name: UIApplication.didEnterBackgroundNotification, object: nil)
        NotificationCenter.default.addObserver(self, selector: #selector(appWillEnterForeground), name: UIApplication.willEnterForegroundNotification, object: nil)

        setupSilentAudio()
        requestNotificationPermissions()
    }

    private func setupSilentAudio() {
        do {
            try AVAudioSession.sharedInstance().setCategory(.playback, mode: .default, options: [.mixWithOthers])
            try AVAudioSession.sharedInstance().setActive(true)

            // Генерируем 1 секунду тишины в WAV-формате прямо в памяти
            let silentWavData = createSilentWavData()
            audioPlayer = try AVAudioPlayer(data: silentWavData)
            audioPlayer?.numberOfLoops = -1 // Бесконечный цикл
            audioPlayer?.volume = 0.01 // Бесшумно
        } catch {
            print("[AyuGram] Не удалось инициализировать фоновый аудио-сеанс: \(error)")
        }
    }

    @objc private func appDidEnterBackground() {
        bgTask = UIApplication.shared.beginBackgroundTask(withName: "AyuGramKeepAlive") { [weak self] in
            self?.endBgTask()
        }

        // Запуск бесшумного воспроизведения предотвращает засыпание процесса на iOS
        audioPlayer?.play()
    }

    @objc private func appWillEnterForeground() {
        audioPlayer?.pause()
        endBgTask()
    }

    private func endBgTask() {
        if bgTask != .invalid {
            UIApplication.shared.endBackgroundTask(bgTask)
            bgTask = .invalid
        }
    }

    /// Запрос прав на показ локальных уведомлений на экране блокировки
    public func requestNotificationPermissions() {
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .badge, .sound]) { granted, error in
            if let error = error {
                print("[AyuGram] Ошибка запроса прав на уведомления: \(error)")
            }
        }
    }

    /// Показ мгновенного локального уведомления при получении сообщения в фоне
    public func triggerLocalNotification(senderName: String, messageText: String, chatPeerId: Int64) {
        let content = UNMutableNotificationContent()
        content.title = senderName
        content.body = messageText
        content.sound = .default
        content.userInfo = ["peerId": chatPeerId]

        let request = UNNotificationRequest(
            identifier: UUID().uuidString,
            content: content,
            trigger: nil // Немедленный показ
        )

        UNUserNotificationCenter.current().add(request, withCompletionHandler: nil)
    }

    /// Генерация минимального WAV-файла тишины (44 байта заголовка + тишина)
    private func createSilentWavData() -> Data {
        var data = Data()
        data.append(contentsOf: "RIFF".utf8)
        var fileSize: UInt32 = 44 + 800 - 8
        data.append(Data(bytes: &fileSize, count: 4))
        data.append(contentsOf: "WAVEfmt ".utf8)
        var fmtChunkSize: UInt32 = 16
        data.append(Data(bytes: &fmtChunkSize, count: 4))
        var audioFormat: UInt16 = 1 // PCM
        data.append(Data(bytes: &audioFormat, count: 2))
        var numChannels: UInt16 = 1
        data.append(Data(bytes: &numChannels, count: 2))
        var sampleRate: UInt32 = 8000
        data.append(Data(bytes: &sampleRate, count: 4))
        var byteRate: UInt32 = 8000 * 2
        data.append(Data(bytes: &byteRate, count: 4))
        var blockAlign: UInt16 = 2
        data.append(Data(bytes: &blockAlign, count: 2))
        var bitsPerSample: UInt16 = 16
        data.append(Data(bytes: &bitsPerSample, count: 2))
        data.append(contentsOf: "data".utf8)
        var dataChunkSize: UInt32 = 800
        data.append(Data(bytes: &dataChunkSize, count: 4))
        data.append(Data(count: 800)) // 800 байт нулей (тишина)
        return data
    }
}
