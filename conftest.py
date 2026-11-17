"""Repository-wide pytest setup.

The SUMO wheel (`eclipse-sumo`) installs a top-level Python module called `sumo`. This
repository also has a `sumo/` folder (a namespace package with the simulation code), and a
regular installed module always wins over a namespace folder, so with SUMO installed
`import sumo.bengaluru_osm...` would fail. Point `sumo` at this repository's folder for the
test session, so one environment can hold both SUMO and the test dependencies.
"""
import sys
import types
from pathlib import Path

_REPO_SUMO = Path(__file__).resolve().parent / "sumo"
_loaded = sys.modules.get("sumo")
if _loaded is None or str(_REPO_SUMO) not in list(getattr(_loaded, "__path__", [])):
    _package = types.ModuleType("sumo")
    _package.__path__ = [str(_REPO_SUMO)]
    sys.modules["sumo"] = _package
