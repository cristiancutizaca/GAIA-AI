# GAIA Final Physical Validation

Status: **PENDING / operator-gated**.

Run on the target PC/Android/device with real credentials and hardware:

```bash
python3 tools/physical_validation.py new --output-dir ./physical-validation
# perform each operator check, attach evidence, then:
python3 tools/physical_validation.py validate --report ./physical-validation/physical_validation_RC6_<stamp>.json
```

Required checks include real Core startup, Kill Switch, Safe Mode, LAN/TLS, browser automation, audio/STT/TTS, Android pairing, backup/restore and clean shutdown. Linux Sandbox evidence cannot set these checks to PASS.


For this final run also validate Browser Use with a local allowlisted page, Pipecat/Silero with a real microphone and interrupt, Mem0 with a private local configuration, Graphiti against a disposable Neo4j database, OpenHands in a copied repo with original hash comparison, and UI-TARS only on a real display. A package import is not physical PASS.
