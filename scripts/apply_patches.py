#!/usr/bin/env python3
"""
Автоматизированный скрипт внедрения AyuGram в Telegram-iOS без хрупких git diff
и с авто-настройкой параметров сборки для Make.py
"""

import os
import sys
import shutil

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

args = sys.argv[1:]
if "generateProject" in args:
    cmd = [
        sys.executable,
        real_make,
        "generateProject",
        "--configurationPath=build-system/template_minimal_development_configuration.json",
        "--disableProvisioningProfiles",
        "--xcodeManagedCodesigning"
    ]
    print("[Make-Wrapper] Автоматический запуск generateProject с корректной конфигурацией и xcodeManagedCodesigning...")
    sys.exit(subprocess.call(cmd))
else:
    sys.exit(subprocess.call([sys.executable, real_make] + args))
'''
    with open(make_py, "w", encoding="utf-8") as f:
        f.write(wrapper_code)
    os.chmod(make_py, 0o755)
    log("Установлен интеллектуальный Make-Wrapper для автоматической сборки.")

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

    # 3. Настройка обертки сборочного скрипта
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
