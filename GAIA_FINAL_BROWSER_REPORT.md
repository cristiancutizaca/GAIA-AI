# GAIA Final Browser Report

Status: `REAL_E2E_INTEGRATION` for local Chromium in Sandbox; Windows physical validation pending.

Browser Use uses local Chromium, explicit `is_local`/no-cloud settings, allowlisted domains and SSRF protection. The HTTP reader remains a separate safe fallback. The local rendered E2E passed navigation/read/screenshot in the prior gate. Windows profile discovery and packaged Chromium behavior require target-machine validation.
