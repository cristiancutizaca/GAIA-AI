# Migration from v1.2

1. Keep `CHECKPOINT_00_V1_2_BASELINE` untouched.
2. Extract v1.3 separately and run the test suite.
3. Start with optional flags disabled.
4. Back up data before enabling persistent automation or new providers.
5. Set explicit browser allowlists; never globally allow private hosts.
6. Roll back by extracting the v1.2 archive and restoring its backup.

Database additions: `platform_memory_v13.db`, `automations_v13.db`, `mcp_servers_v13.json`; no automatic migration of existing memory was performed.
