"""Indian QoL Concierge package."""

# Compat shim: langchain_core.get_debug() expects langchain.debug on older installs
try:
    import langchain as _lc

    if not hasattr(_lc, "debug"):
        _lc.debug = False  # type: ignore[attr-defined]
    if not hasattr(_lc, "verbose"):
        _lc.verbose = False  # type: ignore[attr-defined]
    if not hasattr(_lc, "llm_cache"):
        _lc.llm_cache = None  # type: ignore[attr-defined]
except Exception:
    pass
