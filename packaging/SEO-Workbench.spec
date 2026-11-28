# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, copy_metadata

analysis = Analysis(
    [str(Path(SPECPATH) / "desktop_entry.py")],
    datas=collect_data_files("seo_analysis") + copy_metadata("seo-analysis") + copy_metadata("keyring"),
    hiddenimports=[
        "uvicorn.lifespan.on",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols.http.h11_impl",
        "keyring.backends.Windows",
    ],
)

exe = EXE(
    PYZ(analysis.pure),
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="SEO-Workbench",
    console=False,
    upx=False,
)
