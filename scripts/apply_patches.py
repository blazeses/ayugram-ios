#!/usr/bin/env python3
"""
Скрипт применения модификаций AyuGram к исходникам Telegram-iOS
"""

import os
import sys
import shutil
import subprocess

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATCHES_DIR = os.path.join(BASE_DIR, "patches")
AYU_CORE_DIR = os.path.join(BASE_DIR, "AyuCore", "Sources")

def log(msg):
    print(f"[AyuGram-iOS] {msg}")

def apply_patch_file(target_repo, patch_path):
    patch_name = os.path.basename(patch_path)
    log(f"Применение патча {patch_name}...")
    cmd = ["git", "apply", "--ignore-whitespace", patch_path]
    result = subprocess.run(cmd, cwd=target_repo, capture_output=True, text=True)
    if result.returncode != 0:
        log(f"Ошибка применения {patch_name}: {result.stderr}")
        return False
    log(f"Патч {patch_name} успешно применен.")
    return True

def inject_ayu_core(target_repo):
    log("Внедрение файлов AyuCore в структуру Telegram-iOS...")
    dest_dir = os.path.join(target_repo, "submodules", "TelegramCore", "Sources", "AyuGram")
    os.makedirs(dest_dir, exist_ok=True)
    
    for filename in os.listdir(AYU_CORE_DIR):
        src_file = os.path.join(AYU_CORE_DIR, filename)
        dst_file = os.path.join(dest_dir, filename)
        if os.path.isfile(src_file):
            shutil.copy2(src_file, dst_file)
            log(f"Скопирован: {filename} -> {dst_file}")

def main():
    if len(sys.argv) < 2:
        print("Использование: python apply_patches.py <путь_к_репозиторию_Telegram-iOS>")
        sys.exit(1)

    target_repo = os.path.abspath(sys.argv[1])
    if not os.path.isdir(target_repo):
        print(f"Ошибка: каталог {target_repo} не найден.")
        sys.exit(1)

    log(f"Целевой репозиторий: {target_repo}")
    inject_ayu_core(target_repo)

    patches = sorted([os.path.join(PATCHES_DIR, f) for f in os.listdir(PATCHES_DIR) if f.endswith(".patch")])
    for p in patches:
        if not apply_patch_file(target_repo, p):
            sys.exit(1)

    log("Все модификации AyuGram успешно внедрены!")

if __name__ == "__main__":
    main()
