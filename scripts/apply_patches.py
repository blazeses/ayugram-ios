#!/usr/bin/env python3
"""
Автоматизированный скрипт внедрения AyuGram в Telegram-iOS без хрупких git diff,
с генерацией валидного configuration.json, настройкой флагов сборки под TrollStore,
фиксацией совместимой версии Bazel 7.4.1 (с исправлением dyld LC_UUID на macOS 15)
и интеллектуальным Make-Wrapper для компиляции без сторонних Xcode-генераторов.
"""

import os
import sys
import shutil
import json
import subprocess

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AYU_CORE_DIR = os.path.join(BASE_DIR, "AyuCore", "Sources")

def log(msg):
    print(f"[AyuGram-iOS] {msg}")

def inject_ayu_core(target_repo):
    log("Внедрение исходников AyuCore в TelegramCore...")
    dest_dir = os.path.join(target_repo, "submodules", "TelegramCore", "Sources", "AyuGram")
    os.makedirs(dest_dir, exist_ok=True)
    
    for filename in os.listdir(AYU_CORE_DIR):
        src_file = os.path.join(AYU_CORE_DIR, filename)
        dst_file = os.path.join(dest_dir, filename)
        if os.path.isfile(src_file):
            shutil.copy2(src_file, dst_file)
            log(f"Скопирован модуль: {filename}")

def patch_file(filepath, search_str, replace_str, description):
    if not os.path.isfile(filepath):
        log(f"ПРЕДУПРЕЖДЕНИЕ: Файл {filepath} не найден, пропускаем ({description})")
        return False
    
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    if replace_str.strip() in content:
        log(f"Уже внедрено: {description}")
        return True

    if search_str not in content:
        log(f"ПРЕДУПРЕЖДЕНИЕ: Сигнатура не найдена в {os.path.basename(filepath)} ({description})")
        return False

    new_content = content.replace(search_str, replace_str, 1)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)
    log(f"Успешно модифицирован {os.path.basename(filepath)} ({description})")
    return True

def generate_ayugram_config(target_repo):
    log("Генерация валидной конфигурации сборки AyuGram...")
    config_path = os.path.join(target_repo, "build-system", "ayugram_config.json")
    config_data = {
        "bundle_id": "org.telegram.ayugram",
        "api_id": "2040",
        "api_hash": "b18441a1ff607e10a989891a5462e627",
        "team_id": "AYUGRAM123",
        "app_center_id": "0",
        "is_internal_build": "true",
        "is_appstore_build": "false",
        "appstore_id": "0",
        "app_specific_url_scheme": "tg",
        "premium_iap_product_id": "",
        "enable_siri": False,
        "enable_icloud": False
    }
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=4)
    log(f"Создан конфигурационный файл: {config_path}")

def sync_versions_json(target_repo):
    log("Синхронизация versions.json и фиксация Bazel 7.4.1...")
    versions_path = os.path.join(target_repo, "versions.json")
    if not os.path.isfile(versions_path):
        return

    with open(versions_path, "r", encoding="utf-8") as f:
        vdata = json.load(f)

    # Реальная версия Xcode
    try:
        xcode_path = subprocess.check_output(["xcode-select", "-p"], text=True).strip()
        plist_path = os.path.normpath(os.path.join(xcode_path, "..", "Info.plist"))
        xcode_ver = subprocess.check_output(
            ["plutil", "-extract", "CFBundleShortVersionString", "raw", plist_path],
            text=True
        ).strip()
        vdata["xcode"] = xcode_ver
        log(f"Версия Xcode обновлена на: {xcode_ver}")
    except Exception as e:
        log(f"Не удалось извлечь точную версию Xcode ({e}), fallback: 26.6")
        vdata["xcode"] = "26.6"

    # Bazel 7.4.1 исправляет dyld missing LC_UUID load command на macOS 15+
    vdata["bazel"] = "7.4.1"
    
    with open(os.path.join(target_repo, ".bazelversion"), "w", encoding="utf-8") as f:
        f.write("7.4.1\n")
    log("Установлен .bazelversion = 7.4.1")

    with open(versions_path, "w", encoding="utf-8") as f:
        json.dump(vdata, f, indent=4)
    log("Файл versions.json успешно синхронизирован с Bazel 7.4.1.")

def configure_bazelrc(target_repo):
    log("Настройка .bazelrc с опциями сборки без профилей под TrollStore...")
    bazelrc_path = os.path.join(target_repo, ".bazelrc")
    options = [
        "",
        "# AyuGram TrollStore Build Options",
        "build --//Telegram:disableProvisioningProfiles",
        "build --//Telegram:disableExtensions",
        "build --//Telegram:disableStripping",
        "build --announce_rc",
        "build --verbose_failures",
        ""
    ]
    with open(bazelrc_path, "a", encoding="utf-8") as f:
        f.write("\n".join(options))
    log("Файл .bazelrc успешно обновлен с флагами для TrollStore.")

def setup_make_wrapper(target_repo):
    make_py = os.path.join(target_repo, "build-system", "Make", "Make.py")
    make_real = os.path.join(target_repo, "build-system", "Make", "Make.py.real")

    if not os.path.isfile(make_real) and os.path.isfile(make_py):
        shutil.copy2(make_py, make_real)
        log("Создана копия оригинального Make.py")

    wrapper_code = '''#!/usr/bin/env python3
import os
import sys
import shutil
import glob
import subprocess

current_dir = os.path.dirname(os.path.abspath(__file__))
real_make = os.path.join(current_dir, "Make.py.real")

os.environ["USE_BAZEL_VERSION"] = "7.4.1"

args = sys.argv[1:]
print(f"[Make-Wrapper] Получен вызов: {args}")

if "generateProject" in args:
    print("[Make-Wrapper] generateProject пропущен (генерация Xcode-проекта не требуется для сборки IPA через Bazel в CI).")
    sys.exit(0)

if "build" in args:
    print("[Make-Wrapper] Подготовка параметров для компиляции AyuGram...")
    output_dir = None
    cleaned_args = []
    skip_next = False

    for i, a in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if a.startswith("--outputDirectory="):
            output_dir = a.split("=", 1)[1]
        elif a == "--outputDirectory":
            if i + 1 < len(args):
                output_dir = args[i + 1]
                skip_next = True
        elif a.startswith("--configurationPath="):
            cleaned_args.append("--configurationPath=build-system/ayugram_config.json")
        elif a == "--configurationPath":
            cleaned_args.append("--configurationPath=build-system/ayugram_config.json")
            skip_next = True
        else:
            cleaned_args.append(a)

    if not any("--xcodeManagedCodesigning" in a for a in cleaned_args):
        cleaned_args.append("--xcodeManagedCodesigning")

    final_cmd = [
        sys.executable,
        real_make,
        "--overrideXcodeVersion",
        "--overrideBazelVersion"
    ] + cleaned_args

    print(f"[Make-Wrapper] Запуск оригинального Make.py: {' '.join(final_cmd)}")
    ret = subprocess.call(final_cmd, env=os.environ)
    if ret != 0:
        print(f"[Make-Wrapper] Ошибка компиляции Make.py (код {ret})")
        sys.exit(ret)

    print("[Make-Wrapper] Сборка Bazel завершена. Маршрутизация выходных артефактов...")
    workspace = os.environ.get("GITHUB_WORKSPACE", os.getcwd())
    if not output_dir:
        output_dir = os.path.join(workspace, "output")
    os.makedirs(output_dir, exist_ok=True)

    # 1. Поиск скомпилированного .app
    app_found = None
    for root, dirs, files in os.walk("."):
        for d in dirs:
            if d.endswith(".app"):
                candidate = os.path.join(root, d)
                if "bazel-bin" in candidate or "bazel-out" in candidate:
                    app_found = candidate
                    break
        if app_found:
            break

    if app_found:
        dest_app = os.path.join(output_dir, os.path.basename(app_found))
        print(f"[Make-Wrapper] Найдено приложение: {app_found} -> {dest_app}")
        if os.path.exists(dest_app):
            shutil.rmtree(dest_app)
        shutil.copytree(app_found, dest_app)

    # 2. Поиск сгенерированного .ipa
    ipa_candidates = glob.glob("bazel-bin/**/*.ipa", recursive=True) + glob.glob("bazel-out/**/*.ipa", recursive=True)
    if ipa_candidates:
        src_ipa = ipa_candidates[0]
        dest_ipa_out = os.path.join(output_dir, "AyuGram-iOS.ipa")
        dest_ipa_root = os.path.join(workspace, "AyuGram-iOS.ipa")
        print(f"[Make-Wrapper] Найден IPA файл: {src_ipa} -> сохранение в {dest_ipa_out} и {dest_ipa_root}")
        shutil.copy2(src_ipa, dest_ipa_out)
        shutil.copy2(src_ipa, dest_ipa_root)

    print("[Make-Wrapper] Готово! Артефакты подготовлены для TrollStore packaging.")
    sys.exit(0)

# Для всех остальных команд
final_cmd = [sys.executable, real_make, "--overrideXcodeVersion", "--overrideBazelVersion"] + args
sys.exit(subprocess.call(final_cmd, env=os.environ))
'''
    with open(make_py, "w", encoding="utf-8") as f:
        f.write(wrapper_code)
    os.chmod(make_py, 0o755)
    log("Установлен интеллектуальный Make-Wrapper.")

def apply_all_modifications(target_repo):
    # 1. Фоновые режимы (Keep-Alive аудио / voip) в Info.plist
    info_plist_paths = [
        os.path.join(target_repo, "Telegram", "Telegram-iOS", "Info.plist"),
        os.path.join(target_repo, "submodules", "TelegramUI", "Info.plist")
    ]
    for plist_path in info_plist_paths:
        if os.path.isfile(plist_path):
            with open(plist_path, "r", encoding="utf-8", errors="ignore") as f:
                p_content = f.read()
            if "<string>voip</string>" not in p_content and "<key>UIBackgroundModes</key>" in p_content:
                p_content = p_content.replace(
                    "<key>UIBackgroundModes</key>\n\t<array>",
                    "<key>UIBackgroundModes</key>\n\t<array>\n\t\t<string>audio</string>\n\t\t<string>voip</string>\n\t\t<string>fetch</string>"
                )
                with open(plist_path, "w", encoding="utf-8") as f:
                    f.write(p_content)
                log(f"Добавлены фоновые права в {plist_path}")

    # 2. Инициализация AyuBackgroundKeeper в AppDelegate
    app_delegate = os.path.join(target_repo, "submodules", "TelegramUI", "Sources", "AppDelegate.swift")
    patch_file(
        app_delegate,
        "func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {",
        "func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {\n        AyuBackgroundKeeper.shared.start()",
        "Инициализация фонового удержания AyuBackgroundKeeper в AppDelegate"
    )

    # 3. Инъекция No-Read режима (призрак прочитанности)
    read_history = os.path.join(target_repo, "submodules", "TelegramCore", "Sources", "TelegramEngine", "Messages", "ApplyMaxReadIndexInteractively.swift")
    patch_file(
        read_history,
        "func _internal_applyMaxReadIndexInteractively(postbox: Postbox, stateManager: AccountStateManager, index: MessageIndex) -> Signal<Void, NoError> {",
        "func _internal_applyMaxReadIndexInteractively(postbox: Postbox, stateManager: AccountStateManager, index: MessageIndex) -> Signal<Void, NoError> {\n    if AyuSettings.shared.isNoReadHistoryEnabled {\n        return .single(Void())\n    }",
        "Режим призрака: блокировка отправки отчетов о прочтении"
    )

    # 4. Валидный конфигурационный файл сборки без плейсхолдеров
    generate_ayugram_config(target_repo)

    # 5. Синхронизация версий и фиксация Bazel 7.4.1
    sync_versions_json(target_repo)

    # 6. Настройка .bazelrc под TrollStore (без профилей, без расширений)
    configure_bazelrc(target_repo)

    # 7. Установка перехватчика сборочной системы Make.py
    setup_make_wrapper(target_repo)

    log("Все модификации AyuGram успешно применены!")

def main():
    if len(sys.argv) < 2:
        print("Использование: python apply_patches.py <путь_к_репозиторию_Telegram-iOS>")
        sys.exit(1)

    target_repo = os.path.abspath(sys.argv[1])
    log(f"Целевой репозиторий: {target_repo}")

    inject_ayu_core(target_repo)
    apply_all_modifications(target_repo)

if __name__ == "__main__":
    main()
