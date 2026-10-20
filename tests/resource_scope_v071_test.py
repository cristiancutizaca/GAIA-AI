from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "lumen-core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

from resource_scope import RESOURCE_SCOPE_VERSION, resolve_resource_scope


def main() -> None:
    source = ROOT / "tests" / "fixtures" / "source.txt"
    destination_a = ROOT / "tests" / "fixtures" / "project-a" / "copy.txt"
    destination_b = ROOT / "tests" / "fixtures" / "project-b" / "copy.txt"
    copy_a = resolve_resource_scope("files.copy", {"source": str(source), "destination": str(destination_a)})
    copy_b = resolve_resource_scope("files.copy", {"source": str(source), "destination": str(destination_b)})
    assert copy_a["resource_scope"].startswith("files.copy:from=folder:")
    assert "->to=folder:" in copy_a["resource_scope"]
    assert copy_a["resource_scope"] != copy_b["resource_scope"]
    assert copy_a["persistent_grant_allowed"] is True
    assert copy_a["resource_scope_version"] == RESOURCE_SCOPE_VERSION

    vscode = resolve_resource_scope("uia.invoke_control", {
        "trusted_app_id": "safe:vscode",
        "expected_target": {"window_id": 10, "pid": 20, "executable": "Code.exe"},
        "control_id": "uia:continue-1",
    })
    discord = resolve_resource_scope("uia.invoke_control", {
        "trusted_app_id": "trusted:discord",
        "expected_target": {"window_id": 10, "pid": 20, "executable": "Discord.exe"},
        "control_id": "uia:delete-account",
    })
    assert vscode["resource_scope"] != discord["resource_scope"]
    assert "safe:vscode" in vscode["resource_scope"]
    assert "trusted:discord" in discord["resource_scope"]
    assert vscode["persistent_grant_allowed"] is False
    assert discord["persistent_grant_allowed"] is False

    unresolved = resolve_resource_scope("screen.capture_window", {})
    assert "unresolved" in unresolved["resource_scope"]
    assert unresolved["persistent_grant_allowed"] is False

    display = resolve_resource_scope("screen.capture_display", {"display_id": "display-2"})
    assert display["resource_scope"] == "display:display-2"
    assert display["persistent_grant_allowed"] is False

    media = resolve_resource_scope("media.play_pause", {})
    assert media["resource_scope"] == "media:active_media_session"
    assert media["persistent_grant_allowed"] is True

    print("RESOURCE SCOPE V071 TEST OK: Core-owned compound scopes, UIA isolation, stale-safe identities, non-empty media scope and no empty persistent grants.")


if __name__ == "__main__":
    main()
