# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 설정 파일 - Standalone tray_launcher
외부 리소스는 포함하지 않고 경로만 올바르게 참조
"""

import sys
from pathlib import Path

block_cipher = None

# 프로젝트 루트 경로
project_root = Path('.')

# 최소한의 데이터 파일만 포함 (config는 외부에서 읽음)
added_files = []

# Hidden imports (런타임에 필요한 모듈들)
hidden_imports = [
    # GUI/Tray related
    'pystray',
    'PIL',
    'PIL._tkinter_finder',
    'PIL.Image',
    'PIL.ImageDraw',
    'PIL.ImageFont',
    
    # System utilities
    'psutil',
    'subprocess',
    'multiprocessing',
    'threading',
    'socket',
    'time',
    'os',
    'sys',
    'shutil',
    'msvcrt',
    
    # Data handling
    'json',
    'pathlib',
    'gzip',
    
    # Logging
    'logging.handlers',
    'concurrent.futures',
    
    # Project modules
    'process_manager',
    'log_manager',
]

# 분석 설정
a = Analysis(
    ['tray_launcher.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=added_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 불필요한 모듈들 제외
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'jupyter',
        'IPython',
        'pytest',
        'unittest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# PYZ (Python zip archive) 설정
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# EXE 설정 - 단일 파일 모드
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='tray_launcher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # UPX 압축 사용
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # 디버깅을 위해 콘솔 표시
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/app_icon.ico' if Path('assets/app_icon.ico').exists() else None,
)