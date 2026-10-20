"""Canonical GAIA product identity. Protocol/schema remain independently compatible."""
PRODUCT = "GAIA-AI"
PRODUCT_VERSION = "2.0.0"
RELEASE = "2.0-RESIDENT-DESKTOP-ASSISTANT"
PROTOCOL_VERSION = "1.0-RC6"  # wire compatibility; not the product release
SCHEMA_MIN = 8
SCHEMA_MAX = 9
ANDROID_VERSION = "2.0.0+1"

def identity() -> dict[str, object]:
    return {"product": PRODUCT, "product_version": PRODUCT_VERSION, "release": RELEASE, "protocol": PROTOCOL_VERSION, "schema_min": SCHEMA_MIN, "schema_max": SCHEMA_MAX, "android": ANDROID_VERSION}
