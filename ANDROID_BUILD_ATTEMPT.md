HISTORICAL DOCUMENT — DO NOT USE FOR RC6 OPERATIONS

This document is preserved for historical traceability only. For current RC6 operations use WINDOWS_RC6_VALIDATION_CHECKLIST.md, UPDATE_ROLLBACK_GUIDE.md and PHYSICAL_VALIDATION_RC6.md.

# Android / Flutter build attempt — RC2

The Android companion remains a separate physical-readiness item. The RC2 release source contains the version and protocol bump, but this sandbox does not claim an Android build, APK, signing result, emulator result, or device test unless the actual Flutter and Android toolchains are present and the build completes.

The required operator sequence is to run `flutter --version`, inspect the Android SDK/toolchain, run the project dependency resolution, and attempt the configured debug build. If Flutter, Gradle, Android SDK, signing material, or a physical device is unavailable, the corresponding result is **PENDING / NOT MEASURED**. No placeholder APK is created and no signing PASS is inferred from source inspection.

| Item | RC2 status |
|---|---|
| Flutter toolchain detected in sandbox | PENDING until measured |
| Android SDK and platform tools | PENDING until measured |
| Dependency resolution | PENDING until measured |
| Debug APK build | PENDING / NOT MEASURED |
| Release signing | PENDING / NOT MEASURED |
| Physical Android onboarding and token flow | PENDING / NOT MEASURED |
| Audio/voice behavior | PENDING / NOT MEASURED |

Any resulting APK, Gradle build directory, signing key, device log, or audio artifact is runtime/physical evidence and is excluded from the project and documentation release ZIPs.
