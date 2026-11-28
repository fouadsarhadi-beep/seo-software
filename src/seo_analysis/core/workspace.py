"""Resolve application paths without creating files or selecting a website."""
from dataclasses import dataclass
from pathlib import Path
import tomllib
from uuid import uuid4

from platformdirs import PlatformDirs


class ConfigurationError(ValueError):
    """An invalid setting that the operator can correct."""


@dataclass(frozen=True)
class Workspace:
    config_file: Path
    data_dir: Path
    export_dir: Path

    @property
    def runs_dir(self) -> Path:
        return self.data_dir / "runs"

    def create_run_directory(self) -> Path:
        directory = self.runs_dir / uuid4().hex
        directory.mkdir(parents=True, exist_ok=False)
        return directory

    @classmethod
    def load(cls, config_file: Path | None = None) -> "Workspace":
        path = config_file or PlatformDirs("SEOAnalysisSoftware", appauthor=False).user_config_path / "config.toml"
        path = path.expanduser().absolute()
        try:
            with path.open("rb") as fh:
                settings = tomllib.load(fh)
        except FileNotFoundError as exc:
            if config_file is not None:
                raise ConfigurationError(f"Configuration file does not exist: {path}") from exc
            settings = {}
        except tomllib.TOMLDecodeError as exc:
            raise ConfigurationError(f"Invalid TOML in {path}") from exc

        if settings.keys() - {"paths"}:
            raise ConfigurationError("Unknown configuration section. Expected [paths].")
        paths = settings.get("paths", {})
        if not isinstance(paths, dict) or paths.keys() - {"data_dir", "export_dir"}:
            raise ConfigurationError("Use data_dir and export_dir under [paths].")

        def directory(name: str) -> Path:
            value = paths[name]
            if not isinstance(value, str) or not value.strip():
                raise ConfigurationError(f"paths.{name} must be a nonempty directory path.")
            result = (path.parent / Path(value).expanduser()).resolve()
            if result.exists() and not result.is_dir():
                raise ConfigurationError(f"paths.{name} points to a file.")
            return result

        data = (directory("data_dir") if "data_dir" in paths
                else PlatformDirs("SEOAnalysisSoftware", appauthor=False).user_data_path)
        exports = directory("export_dir") if "export_dir" in paths else data / "exports"
        return cls(path, data, exports)
