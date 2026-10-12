"""Windows AppUserModelID：让音量合成器把本程序识别为独立应用。

不设置时，音频会话按可执行文件名隐式分组，且在开发态会挂到 python.exe 名下；
设置显式 ID 并登记显示名后，音量合成器会显示独立条目、可单独调音量。
"""

from __future__ import annotations

import sys
from pathlib import Path

_IS_WIN = sys.platform == "win32"

# 稳定且唯一的 AppUserModelID
APP_USER_MODEL_ID = "SlugcatPet"

_APPID_KEY = r"Software\Classes\AppUserModelId"
_EXE_NAME = "slugcatpet.exe"
_APP_REL_KEY = rf"Software\Classes\Applications\{_EXE_NAME}"


def _set_current_process_app_id() -> bool:
    """设置本进程显式 AppUserModelID。"""
    try:
        import ctypes

        fn = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
        fn.argtypes = [ctypes.c_wchar_p]
        fn.restype = ctypes.c_long
        return fn(APP_USER_MODEL_ID) == 0  # S_OK=0
    except Exception:
        return False


def _relaunch_command() -> str:
    """重续命令行：冻结时用 exe，开发时用 pythonw + 入口脚本。"""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    from .._paths import base_dir

    script = base_dir() / "run_slugcatpet.py"
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe")
    if pyw.exists():
        exe = pyw
    return f'"{exe}" "{script}"'


def _register_display_name(display_name: str, icon_path: str | None) -> None:
    """登记 ID 的友好名与图标，供音量合成器/任务栏展示。"""
    import winreg

    with winreg.CreateKey(
        winreg.HKEY_CURRENT_USER, rf"{_APPID_KEY}\{APP_USER_MODEL_ID}"
    ) as k:
        winreg.SetValueEx(k, "DisplayName", 0, winreg.REG_SZ, display_name)
        if icon_path:
            winreg.SetValueEx(k, "IconUri", 0, winreg.REG_SZ, icon_path)
            winreg.SetValueEx(k, "IconBackgroundColor", 0, winreg.REG_DWORD, 0)


def _register_relaunch(display_name: str) -> None:
    """按 exe 名登记重续命令，使隐式会话也归入本 ID。"""
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _APP_REL_KEY) as k:
        winreg.SetValueEx(k, "FriendlyAppName", 0, winreg.REG_SZ, display_name)
    with winreg.CreateKey(
        winreg.HKEY_CURRENT_USER, rf"{_APP_REL_KEY}\shell\open\command"
    ) as k:
        winreg.SetValueEx(k, "", 0, winreg.REG_SZ, _relaunch_command())


def ensure_app_id(display_name: str | None = None) -> None:
    """设置并登记 AppUserModelID；非 Windows 或失败时静默跳过。"""
    if not _IS_WIN:
        return
    _set_current_process_app_id()
    name = display_name or "Slugcat Pet"
    icon = sys.executable if getattr(sys, "frozen", False) else None
    try:
        _register_display_name(name, icon)
    except Exception:
        pass
    try:
        _register_relaunch(name)
    except Exception:
        pass
