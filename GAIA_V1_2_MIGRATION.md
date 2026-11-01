# GAIA v1.2 migration

1. Preserve and never modify `CHECKPOINT_00_V1_1_EVOLUTION_FOUNDATION`.
2. Extract v1.2 separately.
3. Start with all `GAIA_FEATURE_*` flags false / `minimal` profile.
4. Run baseline and v1.2 tests.
5. Copy configuration deliberately; never copy plaintext `.env` or tokens into releases.
6. Enable one component at a time. To rollback, restore the v1.1 ZIP/checkpoint and its data backup.
7. No automatic Mem0/Graphiti or database migration is performed.
