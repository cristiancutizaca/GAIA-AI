# GAIA + DeepSeek Harness

Esta edición conserva el Core, memoria, voz, clientes, automatizaciones y permisos de GAIA. DeepSeek Harness actúa como motor de razonamiento sobre Ollama local. GAIA sigue siendo la autoridad para acciones del equipo.

## Arquitectura segura inicial

`GAIA -> DeepSeek Harness SDK -> Ollama -> qwen3.5:4b`

El perfil por defecto es `sdk-minimal` con `deepseek-harness/gaia-safe.patch.yml`, que desactiva el shell persistente. El runtime se obtiene con `deepseek-harness-sdk==0.1.5rc1`; el wheel instala su runtime de la misma versión y no requiere Node.js para el funcionamiento normal.

## Laptop ASUS TUF / RTX 3050 4 GB

Modelo recomendado inicial:

```bash
ollama pull qwen3.5:4b
```

La variante oficial de Ollama ocupa ~3.4 GB. El contexto global recomendado para la laptop es 4096 y la concurrencia 1. Los perfiles `reasoning` y `code` respetan ese techo salvo que se envíe un override explícito.

## Configuración

Copia `.env.example` a `.env` y usa como base:

```env
LUMEN_LLM_BACKEND=deepseek-harness
LUMEN_LLM_MODEL=qwen3.5:4b
OLLAMA_URL=http://localhost:11434
GAIA_DSH_BASE_URL=http://localhost:11434/v1
GAIA_DSH_HOME=
GAIA_DSH_WORKSPACE=
GAIA_DSH_PROFILE=sdk-minimal
GAIA_DSH_PROVIDER=deepseek-official
GAIA_DSH_FALLBACK_TO_OLLAMA=true
GAIA_LLM_CONTEXT=4096
GAIA_MAX_CONCURRENT_LLM_REQUESTS=1
```

`GAIA_DSH_HOME` vacío usa el directorio de datos de GAIA. `GAIA_DSH_WORKSPACE` vacío usa un workspace dedicado dentro de los datos de GAIA; no usa el root del proyecto.

## Instalación

El instalador general ya instala el SDK desde `lumen-core/requirements.txt`. También puede instalarse/validarse de forma independiente:

Windows:

```powershell
.\install-deepseek-harness.ps1
```

Linux:

```bash
./install-deepseek-harness.sh
```

## Fallback

Con `GAIA_DSH_FALLBACK_TO_OLLAMA=true`, si el proceso Harness falla GAIA intenta la misma solicitud directamente contra Ollama. Si Ollama también falla, el error se convierte en `LLMError` y llega al API como fallo controlado, no como un 500 genérico.

Para volver completamente al backend anterior:

```env
LUMEN_LLM_BACKEND=ollama
```

La memoria de GAIA no cambia.

## Prueba real

Con Ollama activo y `qwen3.5:4b` instalado:

```bash
python tools/test_deepseek_harness_e2e.py
```

Debe terminar con `DEEPSEEK HARNESS E2E OK`.

## Seguridad

DeepSeek Harness sigue en Developer Preview. El perfil `sdk-minimal` upstream usa política `danger-full-access`; por eso GAIA desactiva sus shells y ejecuta el runtime en un workspace dedicado. No habilites herramientas completas/subagentes sobre carpetas personales hasta añadir una política de permisos equivalente a la de GAIA.
