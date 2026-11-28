"""Check that the built executable can start with an empty workspace."""

import os
from pathlib import Path
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import monotonic, sleep
from urllib.error import URLError
from urllib.request import urlopen


def main(executable: Path) -> None:
    with TemporaryDirectory(prefix="SEO محیط ") as directory:
        root = Path(directory)
        config = root / "config.toml"
        config.write_text('[paths]\ndata_dir = "data"\n', encoding="utf-8")
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        # Keep launcher state and logs inside the disposable workspace.
        env = os.environ | {"LOCALAPPDATA": directory, "XDG_DATA_HOME": directory}
        command = [str(executable.resolve(strict=True)), "--no-window", "--config-file", str(config),
                   "--port", str(port)]
        process = subprocess.Popen(command, cwd=root, env=env)
        try:
            deadline = monotonic() + 90
            while process.poll() is None and monotonic() < deadline:
                try:
                    with urlopen(f"http://127.0.0.1:{port}/", timeout=2) as response:
                        assert b"Run audit" in response.read(), "Home page did not render the audit form."
                    assert (root / "data" / "history.sqlite3").is_file(), "History was not initialized."
                    return
                except (URLError, TimeoutError):
                    sleep(0.5)
            raise RuntimeError("The packaged workbench did not start.")
        except Exception:
            log = root / "SEOAnalysisWorkbench" / "launcher.log"
            if log.is_file():
                print(log.read_text(encoding="utf-8"), file=sys.stderr)
            raise
        finally:
            if process.poll() is None:
                if os.name == "nt":
                    # PyInstaller's single-file launcher runs the app in a child process.
                    subprocess.run(["taskkill", "/T", "/F", "/PID", str(process.pid)], check=True)
                else:
                    process.terminate()
                process.wait(timeout=20)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
