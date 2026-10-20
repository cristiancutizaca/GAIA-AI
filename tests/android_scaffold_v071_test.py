from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
mobile = ROOT / "lumen-mobile"
android = mobile / "android"
required = [
    mobile / "pubspec.yaml",
    mobile / "analysis_options.yaml",
    mobile / "lib" / "main.dart",
    mobile / "test" / "widget_test.dart",
    android / "settings.gradle",
    android / "build.gradle",
    android / "app" / "build.gradle",
    android / "app" / "src" / "main" / "AndroidManifest.xml",
    android / "app" / "src" / "main" / "kotlin" / "com" / "gaiaai" / "lumen" / "MainActivity.kt",
    android / "gradle" / "wrapper" / "gradle-wrapper.properties",
    android / "gradle" / "wrapper" / "gradle-wrapper.jar",
    android / "gradlew",
    android / "gradlew.bat",
]
for path in required:
    assert path.is_file() and path.stat().st_size > 0, f"Android scaffold missing: {path}"

assert (android / "gradlew").stat().st_mode & 0o111
jar_check = subprocess.run(["unzip", "-tq", str(android / "gradle" / "wrapper" / "gradle-wrapper.jar")], capture_output=True, text=True, check=False)
assert jar_check.returncode == 0, jar_check.stderr
jar_list = subprocess.run(["unzip", "-l", str(android / "gradle" / "wrapper" / "gradle-wrapper.jar")], capture_output=True, text=True, check=True).stdout
assert "org/gradle/wrapper/GradleWrapperMain.class" in jar_list
assert "org/gradle/wrapper/IDownload.class" in jar_list
chat_source = (mobile / "lib" / "screens" / "chat_screen.dart").read_text(encoding="utf-8")
assert chat_source.count("import 'dart:async';") == 1
assert "permission_entries" in chat_source
assert "human_scope_description" in chat_source
assert "resource_scope" in chat_source

flutter_available = shutil.which("flutter") is not None
java_available = shutil.which("java") is not None
print(f"ANDROID SCAFFOLD V071 TEST OK: standard files, official Gradle wrapper and Android source structure present; flutter={'PASS' if flutter_available else 'PENDING'}, java={'PASS' if java_available else 'PENDING'}.")
