# Baseline summary

## Reference

The historical baseline is `GAIA-AI-v1.0-RC6` from `GAIA-AI-v1.0-RC6-final.zip`. Its release report states **RC6 FROZEN / AUTOMATED PASS / PHYSICAL VALIDATION PENDING**.

Known baseline evidence: 202/202 compile checks, 126/126 tests, package/document/security audits PASS; 12 physical controls remained pending. The baseline explicitly forbids inferring Windows, GPU, audio, Ollama, LAN/TLS or Android success from Linux.

## Preserved contracts

- Localhost-first operation and explicit LAN opt-in.
- Authentication, capability checks, ownership, namespaces, Safe Mode and kill switch.
- Action Host as the only system-action boundary.
- No automatic model download or Ollama start.
- Bounded memory, SQLite integrity and backup policies.
- Deterministic release packaging and redacted validation evidence.

## Baseline conclusion

The later package should be repaired by focused diff, not by reverting the entire tree. The post-baseline changes are limited to optional DeepSeek Harness integration, related routing/configuration, installers, Doctor/release tooling and documentation.
