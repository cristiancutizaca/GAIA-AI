# GAIA-AI v1.0-RC6 Security Model

RC6 conserva la frontera de autoridad de RC5: los eventos son datos, los permisos son explícitos, ownership y namespace no se mezclan, provenance se conserva y el ResourceGovernor permanece read-only respecto al hardware. Las acciones requieren preflight y no se duplican.

El runner usa subprocessos en forma de lista, `shell=False`, timeouts y redacción. No usa `os.system`, `eval`, `exec`, `Invoke-Expression`, shell dinámico, descarga automática de modelos ni arranque automático de Ollama. No muta BIOS, GPU, ventiladores, energía, firewall ni hardware.

Las cachés y colas deben tener límite, TTL o invalidación explícita, sin almacenar secretos, conversaciones completas o autorizaciones positivas de modo peligroso. SQLite conserva integridad, ownership, provenance y transacciones seguras; no se usa `synchronous=OFF` ni conexiones compartidas inseguramente entre threads.
