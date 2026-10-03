# Build from the project root with: pyinstaller packaging/sample-organizer.spec
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

root = Path.cwd()
analysis = Analysis(
    [str(root / "src" / "launcher.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=[(str(root / "config" / "categories.json"), "config")],
    hiddenimports=collect_submodules("sample_organizer"),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(analysis.pure)
executable = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="Sample Organizer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
app = BUNDLE(
    executable,
    name="Sample Organizer.app",
    icon=None,
    bundle_identifier="com.sampleorganizer.desktop",
    version="0.1.0",
)
