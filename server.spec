# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# EXCLUSIONS: Heavily prune unnecessary modules that often cause issues
# EXCLUSIONS: None (Rely on clean venv)
excluded_modules = []



from PyInstaller.utils.hooks import collect_all

# AUTOMATIC COLLECTION: Robustly collect everything for complex packages
packages_to_collect = [
    'uvicorn', 'fastapi', 'agno', 'pydantic', 
    'lancedb', 'pyarrow', 'tantivy', 'pandas', 'sqlalchemy', 'aiosqlite',
    'watchdog', 'pathspec',
    'langchain_core', 'langchain_text_splitters',
    'sentence_transformers', 'torch', 'numpy',
    'openai', 'anthropic', 'ollama', 'google_genai', 'google.generativeai',
    'pylance'
]

# DATA: Public assets
datas = [
    ('src/prompts', 'src/prompts'),
    ('src/templates', 'src/templates'),
]
binaries = []
hiddenimports = []

tmp_ret = []
for pkg in packages_to_collect:
    try:
        tmp = collect_all(pkg)
        datas += tmp[0]
        binaries += tmp[1]
        hiddenimports += tmp[2]
    except Exception as e:
        print(f"WARNING: Could not collect {pkg}: {e}")

a = Analysis(
    ['server.py'],
    pathex=[os.getcwd()],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excluded_modules,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True, # Set to False for production if you want to hide window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='server',
)
