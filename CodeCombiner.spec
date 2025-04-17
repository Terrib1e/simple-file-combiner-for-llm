# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['code_combiner.py'],
    pathex=[],
    binaries=[],
    datas=[('C:\\Users\\103168\\Documents\\Personal\\File Combine for LLM\\venv\\Lib\\site-packages\\customtkinter\\assets', 'customtkinter/assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='CodeCombiner',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['checker_icon.ico'],
)
