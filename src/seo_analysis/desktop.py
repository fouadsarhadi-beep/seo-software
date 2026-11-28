"""Run the local workbench with a desktop launcher."""

from argparse import ArgumentParser
from contextlib import closing
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import sys
from tempfile import TemporaryDirectory, mkdtemp
from threading import Thread
from time import monotonic
import webbrowser

from platformdirs import PlatformDirs
import uvicorn

from seo_analysis.core.artifacts import write_text
from seo_analysis.core.workspace import Workspace
from seo_analysis.storage.history import History, workspace_access_error as needs_writable_copy
from seo_analysis.ui.server import create_app

HOST = "127.0.0.1"
TITLE = "SEO Workbench"
LOG = logging.getLogger(__name__)
STATE_FOLDER = "SEOAnalysisWorkbench"
WORKSPACE_POINTER = "workspace-config.txt"


def launcher_locations(override: Path | None) -> tuple[Path, ...]:
    if override is not None:
        return (override.expanduser().absolute(),)
    return (
        PlatformDirs(STATE_FOLDER, appauthor=False).user_data_path,
        Path.home() / STATE_FOLDER,
    )


def open_launcher_state(
    locations: tuple[Path, ...], config_file: Path | None,
) -> tuple[Path, RotatingFileHandler, Path | None]:
    """Choose writable launcher storage and resume the most recently recovered workspace."""
    preferred = None
    if config_file is None:
        saved = []
        for location in locations:
            try:
                with (location / WORKSPACE_POINTER).open(encoding="utf-8") as pointer:
                    candidate = Path(pointer.read())
                    modified = os.fstat(pointer.fileno()).st_mtime_ns
            except (FileNotFoundError, NotADirectoryError, PermissionError):
                continue
            saved.append((modified, location, candidate))
        if saved:
            _, preferred, config_file = max(saved, key=lambda item: item[0])

    failures = []
    for location in dict.fromkeys(locations if preferred is None else (preferred, *locations)):
        try:
            location.mkdir(parents=True, exist_ok=True)
            with TemporaryDirectory(prefix=".write-check-", dir=location):
                pass
            log = RotatingFileHandler(location / "launcher.log", maxBytes=1_048_576, backupCount=1, encoding="utf-8")
        except OSError as exc:
            failures.append(f"{location} ({exc.strerror or exc})")
        else:
            return location, log, config_file
    raise OSError("Could not write launcher files. Start the launcher with --state-dir and a writable folder.\n\n"
                  + "\n".join(failures))


def check_workspace(workspace: Workspace) -> None:
    History(workspace).check_writable()


def recover_workspace(workspace: Workspace, state: Path) -> Workspace:
    """Copy the workspace and use SQLite's backup API for a consistent database."""
    source = workspace.data_dir.resolve()
    if state.resolve().is_relative_to(source):
        raise ValueError("Choose a launcher data location outside the existing workspace.")
    recovery = Path(mkdtemp(prefix="recovered-", dir=state))
    data = recovery / "data"
    database = History(workspace).path
    sqlite_files = {database.name + suffix for suffix in ("", "-wal", "-shm", "-journal")}

    def exclude(directory: str, names: list[str]) -> set[str]:
        root = Path(directory)
        return {name for name in names if (root == source and name in sqlite_files)
                or (root / name).is_symlink() or (root / name).is_junction()}

    try:
        if source.exists():
            shutil.copytree(source, data, copy_function=shutil.copyfile, ignore=exclude)
        if database.exists():
            with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as original:
                with closing(sqlite3.connect(data / database.name)) as backup:
                    original.backup(backup)
        config = recovery / "config.toml"
        write_text(config, '[paths]\ndata_dir = "data"\n')
        copied = Workspace.load(config)
        check_workspace(copied)
        write_text(state / WORKSPACE_POINTER, str(config))
    except Exception:
        shutil.rmtree(recovery, ignore_errors=True)
        raise
    return copied


def bind_listener(port: int | None) -> socket.socket:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        # Port zero lets the OS choose a free port and keeps simultaneous launches independent.
        listener.bind((HOST, 0 if port is None else port))
    except OSError:
        listener.close()
        raise
    return listener


def serve_desktop(
    listener: socket.socket,
    workspace: Workspace,
    root=None,
) -> int:
    port = listener.getsockname()[1]
    url = f"http://{HOST}:{port}"
    config = uvicorn.Config(
        create_app(workspace, port), host=HOST, port=port,
        loop="asyncio", http="h11", ws="none", lifespan="on",
        log_config=None, access_log=False,
    )
    server = uvicorn.Server(config)
    if root is None:
        server.run(sockets=[listener])
        return int(not server.started)

    import tkinter as tk
    from tkinter import messagebox, ttk

    status = tk.StringVar(master=root, value="Starting the workbench…")
    frame = ttk.Frame(root, padding=20)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, textvariable=status).pack(anchor="w")
    address = tk.StringVar(master=root, value=url)
    ttk.Entry(frame, textvariable=address, width=35, state="readonly").pack(fill="x", pady=(8, 16))
    buttons = ttk.Frame(frame)
    buttons.pack(fill="x")

    def open_browser() -> None:
        try:
            if webbrowser.open(url):
                return
        except (OSError, webbrowser.Error):
            LOG.exception("Could not open the default browser")
        status.set("Open the address below in your browser.")

    open_button = ttk.Button(buttons, text="Open Workbench", command=open_browser, state="disabled")
    open_button.pack(side="left")
    exit_button = ttk.Button(buttons, text="Exit", command=lambda: stop())
    exit_button.pack(side="right")

    def run_server() -> None:
        try:
            server.run(sockets=[listener])
        except Exception:
            LOG.exception("Local server stopped unexpectedly")

    thread = Thread(target=run_server, name="workbench-server")
    started = False
    stopping = False
    deadline = monotonic() + 30

    def stop() -> None:
        nonlocal stopping
        stopping = True
        server.should_exit = True
        status.set("Stopping the workbench…")
        open_button.state(["disabled"])
        exit_button.state(["disabled"])

    def poll() -> None:
        nonlocal started
        if not thread.is_alive():
            if not stopping:
                messagebox.showerror(TITLE, "The workbench stopped. See launcher.log for details.", parent=root)
            root.quit()
            return
        if not stopping and not started:
            if server.started:
                started = True
                status.set("The workbench is running.")
                open_button.state(["!disabled"])
                open_browser()
            elif monotonic() >= deadline:
                stop()
                messagebox.showerror(TITLE, "The workbench took too long to start.", parent=root)
        root.after(100, poll)

    root.protocol("WM_DELETE_WINDOW", stop)
    root.deiconify()
    thread.start()
    root.after(100, poll)
    try:
        root.mainloop()
    finally:
        server.should_exit = True
        thread.join()
    return int(not (started and stopping))


def main() -> int:
    parser = ArgumentParser(prog="SEO-Workbench", description="Start the local SEO workbench.")
    parser.add_argument("--config-file", type=Path, help="Use a specific workspace configuration.")
    parser.add_argument("--state-dir", type=Path, help="Set the folder for launcher logs and recovered workspaces.")
    parser.add_argument("--no-window", action="store_true", help="Serve without opening the launcher or browser.")
    parser.add_argument("--port", type=int, help="Use a specific local port.")
    args = parser.parse_args()
    if args.port is not None and not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")

    from tkinter import Tk, messagebox

    root = None if args.no_window else Tk()
    if root is not None:
        root.title(TITLE)
        root.resizable(False, False)
        root.withdraw()
    log_path = None
    try:
        state, handler, config_file = open_launcher_state(launcher_locations(args.state_dir), args.config_file)
        log_path = state / "launcher.log"
        logging.basicConfig(handlers=[handler], level=logging.INFO)
        workspace = Workspace.load(config_file)
        try:
            check_workspace(workspace)
        except (PermissionError, sqlite3.OperationalError) as exc:
            if root is None or not needs_writable_copy(exc):
                raise
            if not messagebox.askyesno(
                TITLE, f"The workbench cannot write to this workspace:\n{workspace.data_dir}\n\n"
                "Create a writable copy of your projects, run history and saved files? "
                "The original folder will stay intact. Connected accounts may need to be set up again.",
                parent=root,
            ):
                return 1
            workspace = recover_workspace(workspace, state)
            messagebox.showinfo(TITLE, f"The workbench will use this copy:\n{workspace.data_dir}", parent=root)
        with bind_listener(args.port) as listener:
            return serve_desktop(listener, workspace, root)
    except (OSError, ValueError, sqlite3.Error) as exc:
        message = f"Could not start the workbench.\n\n{exc}"
        if log_path is not None:
            LOG.exception("Could not start the workbench")
            message += f"\n\nLog: {log_path}"
        if root is not None:
            messagebox.showerror(TITLE, message, parent=root)
        else:
            print(message, file=sys.stderr)
        return 1
    finally:
        if root is not None:
            root.destroy()


if __name__ == "__main__":
    raise SystemExit(main())
