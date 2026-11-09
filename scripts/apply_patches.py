#!/usr/bin/env python3
"""
Автоматизированный скрипт внедрения AyuGram в Telegram-iOS без хрупких git diff,
с генерацией валидного build_configuration repository, исправлением -Wl,-no_uuid в apple_support
(устранение dyld missing LC_UUID на macOS 15), настройкой флагов сборки под TrollStore,
фиксацией совместимой версии Bazel 7.4.1 и интеллектуальным Make-Wrapper.
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

def fix_apple_support_uuid(target_repo):
    log("Устранение флагов -Wl,-no_uuid в apple_support (фикс dyld missing LC_UUID на macOS 15)...")
    # Ищем все файлы universal_exec_tool.bzl в репозитории
    count = 0
    for root, dirs, files in os.walk(target_repo):
        for file in files:
            if file.endswith(".bzl"):
                bzl_path = os.path.join(root, file)
                try:
                    with open(bzl_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    if "-Wl,-no_uuid" in content or "-no_uuid" in content:
                        new_content = content.replace("-Wl,-no_uuid \\\n", "").replace("-Wl,-no_uuid\n", "")
                        new_content = new_content.replace("-Wl,-no_adhoc_codesign \\\n", "").replace("-Wl,-no_adhoc_codesign\n", "")
                        new_content = new_content.replace("-Wl,-no_uuid", "").replace("-Wl,-no_adhoc_codesign", "")
                        with open(bzl_path, "w", encoding="utf-8") as f:
                            f.write(new_content)
                        log(f"Удален флаг -no_uuid из {os.path.relpath(bzl_path, target_repo)}")
                        count += 1
                except Exception as e:
                    pass
    log(f"Патч LC_UUID применен к {count} файлам правил тулчейна.")

def setup_configuration_repository(target_repo):
    log("Создание и настройка configuration-repository для Bazel...")
    config_repo = os.path.join(target_repo, "build-input", "configuration-repository")
    os.makedirs(config_repo, exist_ok=True)
    
    # 1. WORKSPACE
    with open(os.path.join(config_repo, "WORKSPACE"), "w", encoding="utf-8") as f:
        f.write("# build_configuration repository\n")
        
    # 2. BUILD
    with open(os.path.join(config_repo, "BUILD"), "w", encoding="utf-8") as f:
        f.write('exports_files(["variables.bzl"])\n')
        
    # 3. variables.bzl
    variables_bzl = """telegram_bazel_path = ""
telegram_use_xcode_managed_codesigning = True
telegram_bundle_id = "org.telegram.ayugram"
telegram_api_id = "2040"
telegram_api_hash = "b18441a1ff607e10a989891a5462e627"
telegram_team_id = "AYUGRAM123"
telegram_app_center_id = "0"
telegram_is_internal_build = "true"
telegram_is_appstore_build = "false"
telegram_appstore_id = "0"
telegram_app_specific_url_scheme = "tg"
telegram_premium_iap_product_id = ""
telegram_aps_environment = ""
telegram_enable_siri = False
telegram_enable_icloud = False
telegram_enable_watch = False
"""
    with open(os.path.join(config_repo, "variables.bzl"), "w", encoding="utf-8") as f:
        f.write(variables_bzl)

    # 4. provisioning directory
    prov_dir = os.path.join(config_repo, "provisioning")
    os.makedirs(prov_dir, exist_ok=True)
    with open(os.path.join(prov_dir, "BUILD"), "w", encoding="utf-8") as f:
        f.write("exports_files([])\n")

    # 5. Добавляем local_repository в корневой WORKSPACE
    root_workspace = os.path.join(target_repo, "WORKSPACE")
    if os.path.isfile(root_workspace):
        with open(root_workspace, "r", encoding="utf-8", errors="ignore") as f:
            ws_content = f.read()
        if 'name = "build_configuration"' not in ws_content:
            repo_decl = '\nlocal_repository(\n    name = "build_configuration",\n    path = "build-input/configuration-repository",\n)\n'
            with open(root_workspace, "a", encoding="utf-8") as f:
                f.write(repo_decl)
            log("Добавлен local_repository build_configuration в корневой WORKSPACE.")

    log("Файлы configuration-repository успешно сгенерированы.")

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

    # Bazel 7.4.1
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
        "build --override_repository=build_configuration=build-input/configuration-repository",
        "build --define=buildNumber=1000",
        "build --define=telegramVersion=10.14",
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

args = sys.argv[1:]
print(f"[Make-Wrapper] Получен вызов: {args}")

# generateProject в CI не нужен, так как прямая компиляция идет через Bazel
if "generateProject" in args:
    print("[Make-Wrapper] generateProject перехвачен: configuration-repository уже настроен, Xcode-проект пропущен.")
    sys.exit(0)

current_dir = os.path.dirname(os.path.abspath(__file__))
real_make = os.path.join(current_dir, "Make.py.real")
import subprocess
sys.exit(subprocess.call([sys.executable, real_make] + args, env=os.environ))
'''
    with open(make_py, "w", encoding="utf-8") as f:
        f.write(wrapper_code)
    os.chmod(make_py, 0o755)
    log("Установлен Make-Wrapper.")

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

    # 4. Удаление флагов -no_uuid в apple_support (фикс dyld missing LC_UUID)
    fix_apple_support_uuid(target_repo)

    # 5. Создание и настройка configuration-repository для Bazel
    setup_configuration_repository(target_repo)

    # 6. Валидный конфигурационный файл сборки без плейсхолдеров
    generate_ayugram_config(target_repo)

    # 7. Синхронизация версий и фиксация Bazel 7.4.1
    sync_versions_json(target_repo)

    # 8. Настройка .bazelrc под TrollStore
    configure_bazelrc(target_repo)

    # 9. Установка перехватчика сборочной системы Make.py
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
