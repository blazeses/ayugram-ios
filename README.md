# AyuGram для iOS 15+ (TrollStore / Sideloading)

Форк и набор патчей для официального клиента **Telegram-iOS**, добавляющий ключевой функционал **AyuGram**:
- **Anti-Delete (Анти-удаление сообщений):** сообщения не удаляются из локальной базы Postbox и помечаются специальным бейджем `[Удалено]`.
- **Edit History (История правок):** сохранение предыдущих редакций сообщений с возможностью просмотра через контекстное меню.
- **Ghost Mode (Режим призрака):** отключение отчетов о прочтении сообщений (`messages.readHistory`) и скрытие статуса набора текста (`messages.setTyping`).

---

## Структура проекта на `D:\AyuGram-iOS`

- `AyuCore/Sources/`
  - `AyuSettings.swift` — управление переключателями приватности и режимами работы.
  - `AyuDeletedMessageAttribute.swift` — кастомный атрибут Postbox для хранения удаленных сообщений.
  - `AyuEditHistoryStorage.swift` — хранилище истории редакций сообщений.
- `patches/`
  - `01_postbox_anti_delete.patch` — перехват операций удаления сообщений в ядре Postbox.
  - `02_telegramcore_ghost_mode.patch` — блокировка исходящих пакетов прочтения/набора текста и сохранение правок.
  - `03_telegramui_indicators.patch` — отображение бейджа `🗑 [Удалено]` и меню истории правок в чате.
- `scripts/apply_patches.py` — автоматический скрипт внедрения AyuCore и патчей в репозиторий Telegram-iOS.
- `.github/workflows/build.yml` — пайплайн облачной сборки в `.ipa` через GitHub Actions на macOS 14.

---

## Пошаговая инструкция по сборке `.ipa` без наличия Mac

Сборка Telegram под iOS требует macOS и Xcode. Для сборки на твоем ПК под Windows используется бесплатный раннер GitHub Actions:

### Шаг 1. Создание репозитория на GitHub
1. Перейди на [github.com/new](https://github.com/new) и создай новый приватный репозиторий (например, `AyuGram-iOS`).
2. В терминале PowerShell на компьютере перейди в папку проекта и отправь файлы в репозиторий:
```powershell
cd D:\AyuGram-iOS
git init
git add .
git commit -m "feat: initial AyuGram iOS patches and workflow"
git branch -M main
git remote add origin https://github.com/<ТВОЙ_ЛОГИН>/AyuGram-iOS.git
git push -u origin main
```

### Шаг 2. Запуск облачной сборки
1. Открой свой репозиторий на GitHub в браузере.
2. Перейди во вкладку **Actions**.
3. В левой колонке выбери воркфлоу **Build AyuGram-iOS**.
4. Нажми кнопку **Run workflow** справа.
5. GitHub запустит виртуальную машину `macos-14`, установит Bazel, применит наши патчи и соберет проект (сборка занимает около 40–50 минут).

### Шаг 3. Скачивание и установка на iOS 15
1. По завершении сборки внизу страницы выполнения (Artifacts) появится файл `AyuGram-iOS-TrollStore.zip`.
2. Скачай архив, распакуй `AyuGram-iOS.ipa`.
3. Передай файл на iPhone через AirDrop, iCloud Drive или Telegram Сохраненные.
4. Открой файл через **TrollStore** и нажми **Install**. Приложение установится навсегда без необходимости еженедельной переподписи.
