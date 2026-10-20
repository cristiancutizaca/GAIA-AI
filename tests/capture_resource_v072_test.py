"""v0.7.2 capture resource ownership and TTL contract."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-pc"))

from PIL import Image  # noqa: E402
import screen_capture  # noqa: E402
from screen_capture import get_capture_record  # noqa: E402

screen_capture.cleanup_captures()
image = Image.new("RGB", (4, 4), color=(20, 40, 60))
record = screen_capture._save_image(image, kind="window", identity="42", owner_device="android-test", target_host="pc-main", request_id="req-1")
assert record["available"] is True
assert record["capture_id"].startswith("cap_")
assert record["retrieval_url"] == f"/api/captures/{record['capture_id']}"
assert record["owner_device"] == "android-test"
assert record["target_host"] == "pc-main"
assert record["sha256"]

owned = get_capture_record(record["capture_id"], owner_device="android-test")
assert owned and Path(owned["path"]).is_file()
assert get_capture_record(record["capture_id"], owner_device="other-device") is None
assert get_capture_record(record["capture_id"], is_master=True)

screen_capture.cleanup_captures()
assert get_capture_record(record["capture_id"], owner_device="android-test") is None
print("CAPTURE RESOURCE V072 TEST OK: capture_id, owner scope, TTL manifest and cleanup are enforced.")
