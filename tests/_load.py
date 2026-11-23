"""Load integration modules without importing Home Assistant.

custom_components/tapo_dl100/__init__.py imports homeassistant, so a normal
package import would make the tests need a full Home Assistant install. api.py
and logic.py have no Home Assistant imports, so they are loaded by file path.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

COMPONENT = Path(__file__).resolve().parent.parent / "custom_components" / "tapo_dl100"


def load(name: str) -> ModuleType:
    key = f"tapo_dl100_{name}"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, COMPONENT / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[key] = module
    spec.loader.exec_module(module)
    return module
