# GAIA Final Graph Report

Status: `FUNCTIONAL_OPTIONAL_BACKEND`.

Graphiti uses deterministic owner/project/namespace group IDs and filters search by the same group. It requires explicit Neo4j URI, user and password and reports `CONFIG_REQUIRED` otherwise. The temporal SQLite graph fallback remains available. Live Neo4j execution requires deployment credentials.
