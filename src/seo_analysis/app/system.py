"""Local diagnostics available to all interfaces."""
import platform
import sys
from importlib.metadata import version

from seo_analysis import __version__
from seo_analysis.core.tools import DOCTOR
from seo_analysis.core.workspace import Workspace


def doctor(workspace: Workspace) -> dict:
    return {
        "tool_id": DOCTOR.id,
        "schema_version": "1",
        "app_version": __version__,
        "python": platform.python_version(),
        "interpreter": sys.executable,
        "config_file": str(workspace.config_file),
        "config_loaded": workspace.config_file.is_file(),
        "data_dir": str(workspace.data_dir),
        "runs_dir": str(workspace.runs_dir),
        "export_dir": str(workspace.export_dir),
        "dependencies": {name: version(name) for name in ("beautifulsoup4", "requests", "platformdirs")},
    }
