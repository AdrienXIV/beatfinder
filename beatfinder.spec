# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec pour Beatfinder desktop.

Inclut :
 - tout backend (FastAPI + analyzers librosa/numba/madmom)
 - frontend/build/ (SPA SvelteKit static)
 - hooks pour librosa/numba/llvmlite/sklearn (déjà dans hooks-contrib)
 - madmom modèles pré-entraînés

Build : pyinstaller beatfinder.spec
Output: dist/beatfinder/beatfinder (binaire + dossier libs)
"""
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None


# Collect everything pour les libs sensibles (modèles, plugins, lazy imports)
librosa_collected = collect_all('librosa')
numba_collected = collect_all('numba')
llvmlite_collected = collect_all('llvmlite')
madmom_collected = collect_all('madmom')
sklearn_collected = collect_all('sklearn')
soundfile_collected = collect_all('soundfile')
soxr_collected = collect_all('soxr')
spotipy_collected = collect_all('spotipy')
audioread_collected = collect_all('audioread')
scipy_collected = collect_all('scipy')

# Aggregate
datas = (
    librosa_collected[0]
    + numba_collected[0]
    + llvmlite_collected[0]
    + madmom_collected[0]
    + sklearn_collected[0]
    + soundfile_collected[0]
    + soxr_collected[0]
    + spotipy_collected[0]
    + audioread_collected[0]
    + scipy_collected[0]
)
binaries = (
    librosa_collected[1]
    + numba_collected[1]
    + llvmlite_collected[1]
    + madmom_collected[1]
    + sklearn_collected[1]
    + soundfile_collected[1]
    + soxr_collected[1]
    + audioread_collected[1]
    + scipy_collected[1]
)
hiddenimports = (
    librosa_collected[2]
    + numba_collected[2]
    + llvmlite_collected[2]
    + madmom_collected[2]
    + sklearn_collected[2]
    + soundfile_collected[2]
    + soxr_collected[2]
    + spotipy_collected[2]
    + audioread_collected[2]
    + scipy_collected[2]
)

# Backend modules chargés dynamiquement
hiddenimports += collect_submodules('backend')

# FastAPI / uvicorn extras
hiddenimports += [
    'uvicorn.loops.auto',
    'uvicorn.loops.asyncio',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.http.h11_impl',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.protocols.websockets.websockets_impl',
    'uvicorn.lifespan.on',
    'uvicorn.lifespan.off',
    'uvicorn.logging',
    'email.mime.multipart',
    'email.mime.text',
    'fastapi.applications',
    'pydantic.deprecated.decorator',
]

# Frontend static
datas += [
    ('frontend/build', 'frontend/build'),
]


a = Analysis(
    ['run_app.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pytest',
        'pytest_asyncio',
        'ruff',
        'IPython',
        'jupyter',
        'matplotlib',
        'notebook',
        'tkinter',
        # Tests embarqués dans les libs scientifiques (data + fixtures inutiles)
        'numpy.tests',
        'scipy.tests',
        'sklearn.tests',
        'librosa.tests',
        'numba.tests',
        # scipy I/O backends pour formats qu'on n'utilise pas (audio passe par
        # soundfile/audioread). Garder scipy.io.wavfile ? madmom utilise
        # scipy.io.wavfile pour ses tests internes, donc on ne touche pas scipy.io.
    ],
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
    name='beatfinder',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=True,
    upx=False,
    name='beatfinder',
)
