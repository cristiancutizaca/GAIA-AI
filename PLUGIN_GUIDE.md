# Plugin guide

Implement a provider under `lumen-core/gaia_platform` or `gaia_ext`, declare health/capabilities, use deny-by-default permissions, register it lazily and add failure-injection tests. Do not import external SDKs at Core startup.
