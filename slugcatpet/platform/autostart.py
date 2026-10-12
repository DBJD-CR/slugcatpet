"""Windows 开机自启动：读写 HKCU Run 注册表项。"""

from __future__ import annotations
import sys
from pathlib import Path

from .._paths import base_dir

_APP_NAME = "SlugcatPet"
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _launch_command() -> str:
    """自启动命令行：冻结时用 exe，开发时用 pythonw + 入口脚本。"""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    script = base_dir() / "run_slugcatpet.py"
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe")
    if pyw.exists():
        exe = pyw
    return f'"{exe}" "{script}"'


def is_enabled() -> bool:
    """HKCU Run 中是否已登记本程序。"""
    if sys.platform != "win32":
        return False
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as k:
            winreg.QueryValueEx(k, _APP_NAME)
        return True
    except Exception:
        return False


def enable() -> bool:
    """登记开机自启动，成功返回 True。"""
    if sys.platform != "win32":
        return False
    try:
        import winreg

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as k:
            winreg.SetValueEx(k, _APP_NAME, 0, winreg.REG_SZ, _launch_command())
        return True
    except Exception:
        return False


def disable() -> bool:
    """移除开机自启动，成功返回 True。"""
    if sys.platform != "win32":
        return False
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as k:
            winreg.DeleteValue(k, _APP_NAME)
        return True
    except FileNotFoundError:
        return True
    except Exception:
        return False


def set_enabled(on: bool) -> bool:
    """按需启用/禁用，返回操作是否成功。"""
    return enable() if on else disable()
