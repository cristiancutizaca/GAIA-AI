# Migration and rollback from v1.5

1. Back up Core SQLite and configuration.
2. Copy the v1.5 release tree to a new directory; do not overwrite the live tree.
3. Install Core requirements, then optional groups in isolated environments.
4. Start with all new feature flags false and verify `/api/health` and diagnostics.
5. Enable one provider at a time and run its checklist.
6. Roll back by stopping Core and restoring the immutable v1.5 archive/checkpoint; restore the SQLite backup if the operator approved any test writes.

No migration deletes existing memory or tokens.
