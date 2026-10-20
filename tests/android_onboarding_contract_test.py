from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
service = (ROOT / "lumen-mobile/lib/services/lumen_service.dart").read_text(encoding="utf-8")
pairing = (ROOT / "lumen-mobile/lib/screens/pairing_screen.dart").read_text(encoding="utf-8")
main = (ROOT / "lumen-mobile/lib/main.dart").read_text(encoding="utf-8")
chat = (ROOT / "lumen-mobile/lib/screens/chat_screen.dart").read_text(encoding="utf-8")
settings = (ROOT / "lumen-mobile/lib/screens/settings_screen.dart").read_text(encoding="utf-8")
automation_screen = (ROOT / "lumen-mobile/lib/screens/automation_screen.dart").read_text(encoding="utf-8")
pubspec = (ROOT / "lumen-mobile/pubspec.yaml").read_text(encoding="utf-8")
assert "FlutterSecureStorage" in service and "gaia_device_token" in service
assert "gaia_device_id" in service and "completePairing" in service and "clearSavedConfig" in service and "saveConfig(url: baseUrl, token: pairedToken" in service
assert "pairing/complete" in service and "parsePairingUri" in service and "gaia://pair" in pairing and "Pairing ID" in pairing and "Completar pairing" in pairing
assert "mobile_scanner" in pairing and "MobileScanner" in pairing and "Escanear QR" in pairing and "Pegar URI manualmente" in pairing
assert "BootstrapScreen" in main and "PairingScreen" in main and "_lumen.secret.trim().isEmpty" in main
assert "token expiró o fue revocado" in chat and "clearSavedConfig" in service
assert "ALLOW_ONCE" in chat and "ALWAYS_ALLOW" in chat and "CANCEL" in chat
assert "PC Action Host" in settings and "getRemoteHostStatus" in service
assert "AutomationScreen" in settings and "getAutomationStatus" in service and "Kill switch" in automation_screen
assert "_tokenController" not in settings and "Token de dispositivo', _tokenController" not in settings
assert "guardado de forma segura" in settings
assert "AudioRecorder" in chat and "Permission.microphone.request" in chat and "sendVoice" in chat and "File(path).delete" in chat
assert "onLongPressStart" in chat and "onLongPressEnd" in chat and "wake word" not in chat.casefold()
assert "version: 1.0.0-rc6+1" in pubspec
android_manifest = (ROOT / "lumen-mobile/android/app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
android_build = (ROOT / "lumen-mobile/android/app/build.gradle").read_text(encoding="utf-8")
assert "android.permission.CAMERA" in android_manifest and "android.permission.RECORD_AUDIO" in android_manifest
assert "dev.flutter.flutter-gradle-plugin" in android_build and "applicationId \"com.gaiaai.lumen\"" in android_build
print("ANDROID ONBOARDING CONTRACT TEST OK: secure token, device identity, pairing gate, QR URI parser, remote permission UX and host status.")
