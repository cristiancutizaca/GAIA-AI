# Migration from RC6

1. Keep the RC6 archive and `CHECKPOINT_00_RC6_REPAIRED_STABLE` unchanged.
2. Extract v1.1 separately.
3. Copy only `.env` values deliberately; never copy private data into the release.
4. Start with all `GAIA_FEATURE_*` flags false.
5. Run Doctor V2 and regression tests.
6. Enable one optional feature at a time with rollback to RC6 if its validation fails.
No automatic DB or memory migration is performed.
