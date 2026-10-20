# GAIA-AI v1.0-RC6 Release Decision

## Baseline

RC5 queda como baseline histórico, intacto, con clasificación autoritativa **RC5 NOT FROZEN / ARTIFACT CONSISTENCY FAILURE**. El defecto reproducido fue exclusivamente la inconsistencia entre su ZIP de proyecto y su ZIP documental: cuatro documentos extras en docs y tres Markdown/TXT del proyecto omitidos. RC6 corrige esa política mediante proyección automática exacta.

## Automated decision

El run final de RC6 instaló dependencias únicamente en un venv externo confirmado, reejecutó el runner con el intérprete del venv, superó package gate, preflight, documentación, file/security audit, compile 202/202, suite 126/126, benchmark, extracción limpia, compile limpia 202/202, suite limpia 126/126, benchmark limpio y paridad de 79 documentos sin faltantes, extras ni mismatches. Los builds A/B de proyecto y documentación son byte-identical.

La candidata de cacheo WAL fue medida, clasificada `INCONCLUSIVE` y revertida por empeorar retrieval y ResourceGovernor; no forma parte del runtime RC6. No se aceptan cambios inconclusos.

La decisión exacta autorizada es:

> **RC6 FROZEN / AUTOMATED PASS / PHYSICAL VALIDATION PENDING**

## Límites

Los doce controles físicos permanecen PENDING. Esta decisión no certifica Windows 11, Android/Flutter, audio, SMTC, tres pantallas, GPU/VRAM, batería, térmica, LAN/TLS, signing, Ollama/Qwen ni sesiones prolongadas. No se infiere hardware desde Linux, mocks, imports, APIs locales o existencia de archivos.

La decisión no autoriza producción, no crea una promoción fuera de RC6 y no crea ni declara un artefacto final v1.0.
