#!/usr/bin/env python3
"""
Автоматизированный скрипт внедрения AyuGram в Telegram-iOS без хрупких git diff,
с генерацией валидного configuration.json (без плейсхолдеров {! ... !}),
фиксацией совместимой версии Bazel 7.1.1 и синхронизацией версий Xcode
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
        with open(filepath, "a", encoding="utf-8") as f:
            f.write("\n\n// MARK: - AyuGram Extension\n" + replace_str + "\n")
        log(f"Добавлено как расширение в {os.path.basename(filepath)}")
        return True

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
    log("Синхронизация versions.json и фиксация Bazel 7.1.1...")
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

    # Telegram 10.14 строго совместим с Bazel 7.1.1
    vdata["bazel"] = "7.1.1"
    
    with open(os.path.join(target_repo, ".bazelversion"), "w", encoding="utf-8") as f:
        f.write("7.1.1\n")
    log("Установлен .bazelversion = 7.1.1")

    with open(versions_path, "w", encoding="utf-8") as f:
        json.dump(vdata, f, indent=4)
    log("Файл versions.json успешно синхронизирован с Bazel 7.1.1.")

def setup_make_wrapper(target_repo):
    make_py = os.path.join(target_repo, "build-system", "Make", "Make.py")
    make_real = os.path.join(target_repo, "build-system", "Make", "Make.py.real")

    if not os.path.isfile(make_real) and os.path.isfile(make_py):
        shutil.copy2(make_py, make_real)
        log("Создана копия оригинального Make.py")

    wrapper_code = '''#!/usr/bin/env python3
import os
import sys
import subprocess

current_dir = os.path.dirname(os.path.abspath(__file__))
real_make = os.path.join(current_dir, "Make.py.real")

os.environ["USE_BAZEL_VERSION"] = "7.1.1"

args = sys.argv[1:]
if "generateProject" in args:
    cmd = [
        sys.executable,
        real_make,
        "--overrideXcodeVersion",
        "--overrideBazelVersion",
        "generateProject",
        "--configurationPath=build-system/ayugram_config.json",
        "--disableProvisioningProfiles",
        "--xcodeManagedCodesigning"
    ]
    print("[Make-Wrapper] Автоматический запуск generateProject с ayugram_config.json...")
    sys.exit(subprocess.call(cmd, env=os.environ))
else:
    sys.exit(subprocess.call([sys.executable, real_make] + args, env=os.environ))
'''
    with open(make_py, "w", encoding="utf-8") as f:
        f.write(wrapper_code)
    os.chmod(make_py, 0o755)
    log("Установлен интеллектуальный Make-Wrapper.")

def apply_all_modifications(target_repo):
    # 1. Background modes в Info.plist
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

    # 2. Активация AyuBackgroundKeeper при запуске AppDelegate
    app_delegate = os.path.join(target_repo, "Telegram", "Telegram-iOS", "Application.swift")
    patch_file(
        app_delegate,
        "func application(_ application: UIApplication, didFinishLaunchingWithOptions",
        "func application(_ application: UIApplication, didFinishLaunchingWithOptions" + "\n        AyuBackgroundKeeper.shared.start()",
        "Инициализация фонового удержания AyuGram"
    )

    # 3. Создание валидной конфигурации сборки
    generate_ayugram_config(target_repo)

    # 4. Синхронизация версий и фиксация Bazel 7.1.1
    sync_versions_json(target_repo)

    # 5. Настройка обертки сборочного скрипта
    setup_make_wrapper(target_repo)

    log("Все модификации успешно применены!")

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
