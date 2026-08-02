"""Indian QoL Concierge package."""

from __future__ import annotations

import warnings

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

# LangGraph's JsonPlusSerializer does `Reviver()` with no args; langchain_core 1.3+
# emits a pending deprecation until allowed_objects is explicit. Default to "core"
# (same behavior as today) before LangGraph imports the serializer.
try:
    from langchain_core.load import load as _lc_load

    _Reviver = _lc_load.Reviver
    if not getattr(_Reviver, "_nexus_allowed_objects_default", False):
        _orig_reviver_init = _Reviver.__init__

        def _reviver_init(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            if not args and "allowed_objects" not in kwargs:
                kwargs["allowed_objects"] = "core"
            return _orig_reviver_init(self, *args, **kwargs)

        _Reviver.__init__ = _reviver_init  # type: ignore[method-assign]
        _Reviver._nexus_allowed_objects_default = True  # type: ignore[attr-defined]
except Exception:
    # Still silence the noise if langchain_core layout changes.
    warnings.filterwarnings(
        "ignore",
        message=r".*allowed_objects.*",
        category=PendingDeprecationWarning,
    )
