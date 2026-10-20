# Quick start

```bash
export PYTHONPATH=lumen-core:lumen-pc
python3 tests/v13_core_e2e_test.py
python3 -m uvicorn main:app --host 127.0.0.1 --port 8090
```

Use `Authorization: Bearer <LUMEN_SECRET>`. Keep optional flags disabled until physical validation.
