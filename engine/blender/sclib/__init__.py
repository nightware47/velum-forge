"""Backward-compatible `sclib` alias forwarding cleanly to `vflib`."""
import sys
import vflib
from vflib import core, export, gameready, geo, mats, palette, render

for _sub in ("core", "export", "gameready", "geo", "mats", "palette", "render"):
    sys.modules[f"sclib.{_sub}"] = getattr(vflib, _sub)

__version__ = vflib.__version__
__all__ = vflib.__all__

