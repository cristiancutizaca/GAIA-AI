# GAIA v1.2 performance report

The default path remains lightweight: feature flags are false, external SDKs are not imported, and v1.2 tests use standard library components. The platform adds no resident process. SQLite, JSONL and in-memory scheduler work are bounded by caller limits.

Physical startup/RAM/CPU/latency measurements on the ASUS TUF are pending. Measure minimal, standard and full profiles separately; do not enable voice/browser/OpenHands/Computer Use merely to measure them.
