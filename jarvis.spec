# PyInstaller spec for Jarvis-RU. Сборка на Windows-раннере GitHub Actions.
# ruff: noqa
import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

hidden = []
hidden += collect_submodules("jarvis")
hidden += collect_submodules("vosk")
hidden += collect_submodules("comtypes")
hidden += collect_submodules("pycaw")
hidden += collect_submodules("google.genai")
hidden += collect_submodules("screen_brightness_control")
hidden += [
    "pyttsx3.drivers",
    "pyttsx3.drivers.sapi5",
    "pyttsx3.drivers.dummy",
    "pyttsx3.drivers.nsss",
    "pyttsx3.drivers.espeak",
    "mss.windows",
]

datas = []
datas += collect_data_files("vosk")
datas += collect_data_files("google.genai")

MODEL_DIR = os.environ.get("JARVIS_MODEL_DIR", "models/vosk-model-small-ru-0.22")
if os.path.isdir(MODEL_DIR):
    datas.append((MODEL_DIR, "models/vosk-model-small-ru-0.22"))

# Исключаем тяжёлые/ненужные модули, чтобы .exe был компактнее.
excludes = [
    "tests",
    "test",
    "unittest",
    "pytest",
    "IPython",
    "jupyter",
    "matplotlib",
    "scipy",
    "pandas",
    "tornado",
    "notebook",
    "lib2to3",
    "pydoc_data",
    "sqlite3",
    "xmlrpc",
    "distutils",
    "setuptools",
    "pip",
    "wheel",
]

a = Analysis(
    ["run_jarvis.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="Jarvis",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # UPX-сжатие: даёт ~40% уменьшение размера.
    upx_exclude=[
        # vcruntime / api-ms библиотеки лучше не жать.
        "vcruntime140.dll",
        "vcruntime140_1.dll",
        "python311.dll",
        "python312.dll",
    ],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
