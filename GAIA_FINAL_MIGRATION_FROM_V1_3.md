# Migration from GAIA v1.3

1. Stop the v1.3 service cleanly.
2. Back up Core data with the existing BackupManager.
3. Extract v1.5 to a new directory; do not overwrite the v1.3 tree.
4. Copy only approved `.env` values; never copy credentials into the archive.
5. Keep feature flags disabled until each backend is installed and validated.
6. Start Core and inspect `/api/platform/status`.
7. Run the physical validation ledger.
8. Roll back by stopping v1.5 and restoring the v1.3 archive plus its data backup.

The immutable v1.3 source checkpoint remains at `CHECKPOINT_01_GLOBAL_AUTHORITY_FIXED` outside the release package.
