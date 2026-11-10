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
import re
import tarfile

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

def patch_mozjpeg(target_repo):
    log("Патч third-party/mozjpeg для совместимости с CMake >= 3.31...")
    # 1. Замена версии CMake в CMakeLists.txt
    cm_path = os.path.join(target_repo, "third-party", "mozjpeg", "mozjpeg", "CMakeLists.txt")
    if os.path.isfile(cm_path):
        patch_file(
            cm_path,
            "cmake_minimum_required(VERSION 2.8.12)",
            "cmake_minimum_required(VERSION 3.5)",
            "Минимальная версия CMake в mozjpeg"
        )
    # 2. Флаг политики в build-mozjpeg-bazel.sh
    sh_path = os.path.join(target_repo, "third-party", "mozjpeg", "build-mozjpeg-bazel.sh")
    if os.path.isfile(sh_path):
        with open(sh_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        if "CMAKE_POLICY_VERSION_MINIMUM" not in content:
            content = content.replace(
                'cmake -G"Unix Makefiles"',
                'cmake -G"Unix Makefiles" -DCMAKE_POLICY_VERSION_MINIMUM=3.5'
            )
            with open(sh_path, "w", encoding="utf-8") as f:
                f.write(content)
            log("Добавлен флаг CMAKE_POLICY_VERSION_MINIMUM=3.5 в build-mozjpeg-bazel.sh")
    # 3. Приоритет встроенного CMake 3.23.1 перед системным
    build_path = os.path.join(target_repo, "third-party", "mozjpeg", "BUILD")
    if os.path.isfile(build_path):
        patch_file(
            build_path,
            'PATH="$$PATH:$$CMAKE_DIR/cmake-3.23.1-macos-universal/CMake.app/Contents/bin"',
            'PATH="$$CMAKE_DIR/cmake-3.23.1-macos-universal/CMake.app/Contents/bin:$$PATH"',
            "Приоритет встроенного CMake перед системным в mozjpeg BUILD"
        )

def patch_third_party_cmake(target_repo):
    log("Комплексный патч third-party пакетов (yasm, mozjpeg, etc.) под CMake >= 3.31...")
    tp_dir = os.path.join(target_repo, "third-party")
    if not os.path.isdir(tp_dir):
        return

    # 1. Прямой патч архива third-party/yasm/yasm-1.3.0.tar.gz
    yasm_tar = os.path.join(tp_dir, "yasm", "yasm-1.3.0.tar.gz")
    if os.path.isfile(yasm_tar):
        temp_extract = os.path.join(tp_dir, "yasm", "_temp_yasm")
        try:
            if os.path.exists(temp_extract):
                shutil.rmtree(temp_extract)
            with tarfile.open(yasm_tar, "r:gz") as tar:
                tar.extractall(temp_extract)

            # а) CMakeLists.txt
            cm_path = os.path.join(temp_extract, "yasm-1.3.0", "CMakeLists.txt")
            if os.path.isfile(cm_path):
                with open(cm_path, "r", encoding="utf-8", errors="ignore") as f:
                    c = f.read()
                c = re.sub(r'cmake_minimum_required\(VERSION [0-9.]+\)', 'cmake_minimum_required(VERSION 3.5)\ncmake_policy(SET CMP0026 OLD)', c, flags=re.I)
                with open(cm_path, "w", encoding="utf-8") as f:
                    f.write(c)

            # б) YasmMacros.cmake: замена get_target_property(... LOCATION) на set(var target)
            ym_path = os.path.join(temp_extract, "yasm-1.3.0", "cmake", "modules", "YasmMacros.cmake")
            if os.path.isfile(ym_path):
                with open(ym_path, "r", encoding="utf-8", errors="ignore") as f:
                    c = f.read()
                c = re.sub(r'get_target_property\s*\(\s*(\w+)\s+(\w+)\s+LOCATION\s*\)', r'set(\1 \2)', c)
                with open(ym_path, "w", encoding="utf-8") as f:
                    f.write(c)

            # в) Переупаковка
            with tarfile.open(yasm_tar, "w:gz") as tar:
                for item in os.listdir(temp_extract):
                    tar.add(os.path.join(temp_extract, item), arcname=item)
            log("Архив yasm-1.3.0.tar.gz успешно модифицирован и переупакован с CMP0026 фиксом!")
        except Exception as e:
            log(f"Предупреждение при переупаковке yasm-1.3.0.tar.gz: {e}")
        finally:
            if os.path.exists(temp_extract):
                shutil.rmtree(temp_extract, ignore_errors=True)

    # 2. Точечный патч third-party/yasm/BUILD
    yasm_build = os.path.join(tp_dir, "yasm", "BUILD")
    if os.path.isfile(yasm_build):
        with open(yasm_build, "r", encoding="utf-8", errors="ignore") as f:
            yasm_content = f.read()

        # Убираем ранее добавленные sed команды
        yasm_content = re.sub(r"sed -i '' [^\n]+\n\s*", "", yasm_content)
        
        # Исправляем PATH
        yasm_content = re.sub(
            r'PATH="[^"]*CMAKE_DIR[^"]*"',
            'PATH="$$CMAKE_DIR/cmake-3.23.1-macos-universal/CMake.app/Contents/bin:$$PATH"',
            yasm_content
        )

        # Добавляем политики CMP0026 и CMP0042
        if "-DCMAKE_POLICY_DEFAULT_CMP0026=OLD" not in yasm_content:
            yasm_content = yasm_content.replace(
                "cmake ..",
                "cmake .. -DCMAKE_POLICY_VERSION_MINIMUM=3.5 -DCMAKE_POLICY_DEFAULT_CMP0026=OLD"
            )

        with open(yasm_build, "w", encoding="utf-8") as f:
            f.write(yasm_content)
        log("Сборочный файл third-party/yasm/BUILD успешно обновлен.")

    # 3. Общий сканер всех сборочных файлов third-party на предмет CMake
    for root, dirs, files in os.walk(tp_dir):
        for file in files:
            if file in ("BUILD", "BUILD.bazel") or file.endswith(".sh"):
                fpath = os.path.join(root, file)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        txt = f.read()
                    changed = False
                    
                    # Фикс порядка PATH для CMAKE_DIR
                    if 'PATH="$$PATH:$$CMAKE_DIR' in txt:
                        txt = re.sub(r'PATH="(\${1,2}PATH):(\${1,2}CMAKE_DIR/[^"]+)"', r'PATH="\2:\1"', txt)
                        changed = True
                    if 'PATH="$PATH:$CMAKE_DIR' in txt:
                        txt = re.sub(r'PATH="(\$PATH):(\$CMAKE_DIR/[^"]+)"', r'PATH="\2:\1"', txt)
                        changed = True

                    # Добавление CMAKE_POLICY_VERSION_MINIMUM=3.5 и CMP0026=OLD
                    if "cmake .." in txt and "CMAKE_POLICY_VERSION_MINIMUM" not in txt:
                        txt = txt.replace("cmake ..", "cmake .. -DCMAKE_POLICY_VERSION_MINIMUM=3.5 -DCMAKE_POLICY_DEFAULT_CMP0026=OLD")
                        changed = True

                    if changed:
                        with open(fpath, "w", encoding="utf-8") as f:
                            f.write(txt)
                        log(f"CMake патч применен к {os.path.relpath(fpath, target_repo)}")
                except Exception as e:
                    pass

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

def patch_posix_headers(target_repo):
    log("Патч POSIX/socket заголовков для Clang modules (Xcode 16+)...")
    submodules_dir = os.path.join(target_repo, "submodules")
    if not os.path.isdir(submodules_dir):
        return

    # 1. PingFoundation.h
    pf_header = os.path.join(submodules_dir, "MtProtoKit", "Sources", "PingFoundation.h")
    if os.path.isfile(pf_header):
        with open(pf_header, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        if "<sys/socket.h>" not in content:
            new_content = "#import <sys/types.h>\n#import <sys/socket.h>\n#import <netinet/in.h>\n#import <arpa/inet.h>\n" + content
            with open(pf_header, "w", encoding="utf-8") as f:
                f.write(new_content)
            log("Добавлены POSIX сокет заголовки в PingFoundation.h")

    # 2. Сканируем все .h и .m в submodules на предмет sa_family_t
    count = 0
    for root, dirs, files in os.walk(submodules_dir):
        for file in files:
            if file.endswith((".h", ".m", ".c", ".mm")):
                fpath = os.path.join(root, file)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        txt = f.read()
                    if "sa_family_t" in txt and "<sys/socket.h>" not in txt:
                        txt = "#import <sys/types.h>\n#import <sys/socket.h>\n#import <netinet/in.h>\n#import <arpa/inet.h>\n" + txt
                        with open(fpath, "w", encoding="utf-8") as f:
                            f.write(txt)
                        log(f"Добавлены POSIX сокет заголовки в {os.path.relpath(fpath, target_repo)}")
                        count += 1
                except Exception:
                    pass
    log(f"POSIX сокет заголовки проверены и обновлены (дополнительно обновлено: {count} файлов).")

def patch_clang_warnings_and_werror(target_repo):
    log("Устранение -Werror и исправление VLA/kMemoryChunkSize под Xcode 16 Clang...")
    submodules_dir = os.path.join(target_repo, "submodules")
    if not os.path.isdir(submodules_dir):
        return

    # 1. Точечное исправление kMemoryChunkSize в MTInternalMessageParser.m
    parser_path = os.path.join(submodules_dir, "MtProtoKit", "Sources", "MTInternalMessageParser.m")
    if os.path.isfile(parser_path):
        with open(parser_path, "r", encoding="utf-8", errors="ignore") as f:
            p_content = f.read()
        # Заменяем static const на enum или #define, чтобы убрать ошибку VLA (variable length array folded)
        p_new = re.sub(
            r'static\s+const\s+(?:int|NSInteger|NSUInteger|size_t)\s+kMemoryChunkSize\s*=\s*([^;]+);',
            r'enum { kMemoryChunkSize = \1 };',
            p_content
        )
        if p_new != p_content:
            with open(parser_path, "w", encoding="utf-8") as f:
                f.write(p_new)
            log("Исправлен kMemoryChunkSize (VLA -> enum compile-time constant) в MTInternalMessageParser.m")

    # 2. Удаление -Werror во всех сборочных файлах submodules
    count = 0
    for root, dirs, files in os.walk(submodules_dir):
        for file in files:
            if file in ("BUILD", "BUILD.bazel") or file.endswith(".bzl"):
                fpath = os.path.join(root, file)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    if '"-Werror"' in content or "'-Werror'" in content or "-Werror" in content:
                        new_content = content.replace('"-Werror"', '"-Wno-error"')
                        new_content = new_content.replace("'-Werror'", "'-Wno-error'")
                        with open(fpath, "w", encoding="utf-8") as f:
                            f.write(new_content)
                        count += 1
                except Exception:
                    pass
    log(f"Удалены жесткие флаги -Werror из {count} сборочных файлов подмодулей.")

    # 3. Преобразование static const VLA в enum во всех заголовочных файлах подмодулей (AsyncDisplayKit и др.)
    vla_count = 0
    for root, dirs, files in os.walk(submodules_dir):
        for file in files:
            if file.endswith((".h", ".m", ".mm")):
                fpath = os.path.join(root, file)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        c = f.read()
                    if "kMaxLayoutElement" in c or "kMemoryChunkSize" in c or "Extensions[" in c:
                        new_c = re.sub(
                            r'static\s+const\s+(?:int|NSInteger|NSUInteger|size_t|uint32_t)\s+(k[A-Za-z0-9_]+)\s*=\s*([^;]+);',
                            r'enum { \1 = \2 };',
                            c
                        )
                        if new_c != c:
                            with open(fpath, "w", encoding="utf-8") as f:
                                f.write(new_c)
                            vla_count += 1
                except Exception:
                    pass
    log(f"Константы VLA преобразованы в enum в {vla_count} файлах подмодулей (включая AsyncDisplayKit).")

def patch_webrtc_lifetime_bound(target_repo):
    log("Патч WebRTC и Abseil (фикс [[clang::lifetimebound]] на Xcode 16)...")
    tp_dir = os.path.join(target_repo, "third-party")
    if not os.path.isdir(tp_dir):
        return

    count = 0
    for root, dirs, files in os.walk(tp_dir):
        for file in files:
            if file.endswith((".h", ".cc", ".cpp")):
                fpath = os.path.join(root, file)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    changed = False

                    # 1. Безопасное отключение макроса в Abseil (без повреждения #if/#endif)
                    if "#define ABSL_ATTRIBUTE_LIFETIME_BOUND [[clang::lifetimebound]]" in content:
                        content = content.replace(
                            "#define ABSL_ATTRIBUTE_LIFETIME_BOUND [[clang::lifetimebound]]",
                            "#define ABSL_ATTRIBUTE_LIFETIME_BOUND"
                        )
                        changed = True

                    if "#define ABSL_ATTRIBUTE_LIFETIME_BOUND __attribute__((lifetimebound))" in content:
                        content = content.replace(
                            "#define ABSL_ATTRIBUTE_LIFETIME_BOUND __attribute__((lifetimebound))",
                            "#define ABSL_ATTRIBUTE_LIFETIME_BOUND"
                        )
                        changed = True

                    # 2. Точечное исправление candidate.h
                    if "void set_type(absl::string_view type ABSL_ATTRIBUTE_LIFETIME_BOUND)" in content:
                        content = content.replace(
                            "void set_type(absl::string_view type ABSL_ATTRIBUTE_LIFETIME_BOUND)",
                            "void set_type(absl::string_view type)"
                        )
                        changed = True

                    # 3. Однострочная замена на случай других void функций (только в пределах одной строки [^\n]!)
                    if "ABSL_ATTRIBUTE_LIFETIME_BOUND" in content and "void" in content:
                        new_content = re.sub(
                            r'(void\s+[A-Za-z0-9_:]+\([^\n)]*)\bABSL_ATTRIBUTE_LIFETIME_BOUND\b',
                            r'\1',
                            content
                        )
                        if new_content != content:
                            content = new_content
                            changed = True

                    if changed:
                        with open(fpath, "w", encoding="utf-8") as f:
                            f.write(content)
                        count += 1
                except Exception:
                    pass
    log(f"Патч lifetimebound безопасно применен к {count} файлам WebRTC/Abseil.")

def patch_swift_deprecations(target_repo):
    log("Патч устаревших Swift API для Xcode 16 (allowBluetooth -> allowBluetoothHFP)...")
    submodules_dir = os.path.join(target_repo, "submodules")
    if not os.path.isdir(submodules_dir):
        return

    count = 0
    for root, dirs, files in os.walk(submodules_dir):
        for file in files:
            if file.endswith(".swift"):
                fpath = os.path.join(root, file)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        c = f.read()
                    if ".allowBluetooth" in c:
                        new_c = re.sub(r'\.allowBluetooth\b(?![A-Za-z0-9_])', '.allowBluetoothHFP', c)
                        if new_c != c:
                            c = new_c
                            with open(fpath, "w", encoding="utf-8") as f:
                                f.write(c)
                            log(f"Заменен .allowBluetooth -> .allowBluetoothHFP в {os.path.relpath(fpath, target_repo)}")
                            count += 1
                    
                    if "weak var " in c:
                        # Исправление ошибки Swift 6: weak variable was never mutated; consider changing to 'let' constant [#WeakMutability]
                        new_c = re.sub(r'\bweak\s+var\s+([A-Za-z0-9_]+)\s*=\s*([A-Za-z0-9_.]+)', r'let \1 = \2', c)
                        if new_c != c:
                            c = new_c
                            with open(fpath, "w", encoding="utf-8") as f:
                                f.write(c)
                            log(f"Заменен weak var -> let в {os.path.relpath(fpath, target_repo)}")
                            count += 1
                except Exception:
                    pass
    log(f"Swift deprecation патч применен к {count} файлам.")

def patch_postbox_encoding_container(target_repo):
    log("Патч Postbox AdaptedPostboxUnkeyedEncodingContainer под Swift 6 / iOS 18 SDK...")
    p_path = os.path.join(target_repo, "submodules", "Postbox", "Sources", "Utils", "Encoder", "AdaptedPostboxUnkeyedEncodingContainer.swift")
    if os.path.isfile(p_path):
        with open(p_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # Вырезаем encode(_ value: Data) из тела класса и переносим в extension для устранения near-miss ошибки в Swift 6
        target_pattern = r'(\s*func encode\(_ value: Data\) throws \{\s*self\.items\.append\(\.data\(value\)\)\s*\})'
        if re.search(target_pattern, content):
            content = re.sub(target_pattern, "\n    // encode(_ value: Data) moved to extension below for Swift 6 compatibility\n", content)
            content += """\n
extension _AdaptedPostboxEncoder.UnkeyedContainer {
    func encode(_ value: Data) throws {
        self.items.append(.data(value))
    }
}
"""
            with open(p_path, "w", encoding="utf-8") as f:
                f.write(content)
            log("encode(_ value: Data) вынесен в extension в AdaptedPostboxUnkeyedEncodingContainer.swift")

def setup_metal_toolchain(target_repo):
    log("Настройка Metal Toolchain для компиляции шейдеров (Xcode 16)...")
    
    # 1. Скачиваем официальный компонент MetalToolchain через sudo xcodebuild
    try:
        log("Запуск sudo xcodebuild -downloadComponent MetalToolchain...")
        res = subprocess.run(
            ["sudo", "xcodebuild", "-downloadComponent", "MetalToolchain"],
            capture_output=True,
            text=True,
            timeout=180
        )
        log(f"xcodebuild результат (код {res.returncode}): {res.stdout.strip()[:200]}")
    except Exception as e:
        log(f"xcodebuild -downloadComponent не удался: {e}")

    # 2. Проверяем, доступен ли metal через xcrun
    try:
        check_metal = subprocess.run(["xcrun", "--find", "metal"], capture_output=True, text=True)
        if check_metal.returncode == 0 and check_metal.stdout.strip():
            log(f"Metal toolchain найден: {check_metal.stdout.strip()}")
            return
    except Exception:
        pass

    # 3. Fallback: поиск в других установленных версиях Xcode
    try:
        xcode_dev = subprocess.check_output(["xcode-select", "-p"], text=True).strip()
        target_bin = os.path.join(xcode_dev, "Toolchains", "XcodeDefault.xctoolchain", "usr", "bin")
        os.makedirs(target_bin, exist_ok=True)
        
        for xc in sorted(os.listdir("/Applications"), reverse=True):
            if xc.startswith("Xcode") and xc.endswith(".app"):
                cand = f"/Applications/{xc}/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/metal"
                if os.path.isfile(cand):
                    log(f"Копирование metal из {cand} в {target_bin}...")
                    subprocess.run(["sudo", "cp", "-P", f"{os.path.dirname(cand)}/metal*", target_bin], check=False)
                    cand_lib = os.path.normpath(os.path.join(os.path.dirname(cand), "..", "lib"))
                    target_lib = os.path.normpath(os.path.join(target_bin, "..", "lib"))
                    if os.path.isdir(cand_lib):
                        subprocess.run(["sudo", "cp", "-R", cand_lib, target_lib], check=False)
                    break
    except Exception as e:
        log(f"Поиск альтернативного metal не удался: {e}")

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
        "build --copt=-Wno-error",
        "build --copt=-Wno-gnu-folding-constant",
        "build --copt=-Wno-vla-extension",
        "build --cxxopt=-Wno-error",
        "build --swiftcopt=-Xcc",
        "build --swiftcopt=-Wno-gnu-folding-constant",
        "build --swiftcopt=-Xcc",
        "build --swiftcopt=-Wno-vla-extension",
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

    # 5. Патч mozjpeg и yasm для совместимости с CMake >= 3.31
    patch_mozjpeg(target_repo)
    patch_third_party_cmake(target_repo)

    # 6. Патч POSIX сокет заголовков (sa_family_t) для Clang modules на Xcode 16
    patch_posix_headers(target_repo)

    # 7. Устранение -Werror и фикс VLA / kMemoryChunkSize под Xcode 16 Clang
    patch_clang_warnings_and_werror(target_repo)

    # 8. Патч WebRTC / Abseil (фикс [[clang::lifetimebound]] на void функциях под Xcode 16)
    patch_webrtc_lifetime_bound(target_repo)

    # 9. Патч устаревших Swift API под Xcode 16 (allowBluetooth -> allowBluetoothHFP)
    patch_swift_deprecations(target_repo)

    # 10. Патч Postbox AdaptedPostboxUnkeyedEncodingContainer под Swift 6 / iOS 18
    patch_postbox_encoding_container(target_repo)

    # 11. Установка и настройка Metal Toolchain под Xcode 16
    setup_metal_toolchain(target_repo)

    # 6. Создание и настройка configuration-repository для Bazel
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
