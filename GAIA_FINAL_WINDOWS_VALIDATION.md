# GAIA Final Windows Validation

Status: **PENDING — requires a real Windows PC**.

Install the PC requirements from `lumen-pc/requirements-windows.txt`, configure the Core URL and device token through the existing pairing flow, start the PC Action Host, and verify heartbeat. Test observation first, then a reversible low-risk action with explicit approval, then Kill Switch and Safe Mode. Confirm that the host never executes a pending action for another device. Record OS version, Python version, display/audio device, host logs, and rollback result. No Windows physical validation was possible in the Linux Sandbox.
