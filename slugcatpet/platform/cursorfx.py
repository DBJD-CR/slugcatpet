"""光标劫持：落体→底边锁定，替换系统光标为"忙"样式。"""

from __future__ import annotations
import sys
import math
import atexit

_IS_WIN = sys.platform == "win32"

# 计时单位为 tick（40Hz）；坐标为 Win32 物理像素
T_FALL_GRAV = 1.6
T_CURSOR_LOCK = 200
WATCHDOG_MAX = 400
# 受击弹开：初速指数衰减 + 轻度重力，飞哪算哪
K_KNOCK = 0.88
K_KNOCK_GRAV = 0.5
K_KNOCK_LAND = 6

_ACTIVE = []  # 活动劫持列表

if _IS_WIN:
    import ctypes
    from ctypes import wintypes

    _user32 = ctypes.windll.user32

    class _RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    def _clip(x, y):
        r = _RECT(int(x), int(y), int(x) + 1, int(y) + 1)
        return bool(_user32.ClipCursor(ctypes.byref(r)))

    def _unclip():
        _user32.ClipCursor(None)

    def _setpos(x, y):
        _user32.SetCursorPos(int(x), int(y))

    _OCR_IDS = (32512, 32513, 32649)  # OCR_NORMAL/IBEAM/HAND
    _IDC_APPSTARTING = 32650  # 系统"忙"光标
    _SPI_SETCURSORS = 0x0057

    _user32.LoadCursorW.restype = ctypes.c_void_p
    _user32.LoadCursorW.argtypes = (ctypes.c_void_p, ctypes.c_void_p)
    _user32.CopyIcon.restype = ctypes.c_void_p
    _user32.CopyIcon.argtypes = (ctypes.c_void_p,)
    _user32.SetSystemCursor.restype = wintypes.BOOL
    _user32.SetSystemCursor.argtypes = (ctypes.c_void_p, wintypes.DWORD)
    _user32.SystemParametersInfoW.restype = wintypes.BOOL
    _user32.SystemParametersInfoW.argtypes = (
        wintypes.UINT,
        wintypes.UINT,
        ctypes.c_void_p,
        wintypes.UINT,
    )

    def _set_busy_cursor():
        """替换系统箭头/文本/链接光标为"忙"样式；需 CopyIcon 因 SetSystemCursor 取走所有权。"""
        src = _user32.LoadCursorW(None, _IDC_APPSTARTING)
        if not src:
            return False
        ok = False
        for ocr in _OCR_IDS:
            h = _user32.CopyIcon(src)
            if h and _user32.SetSystemCursor(h, ocr):
                ok = True
        return ok

    def _restore_cursors():
        """从注册表重载全部系统光标恢复默认（幂等）。"""
        _user32.SystemParametersInfoW(_SPI_SETCURSORS, 0, None, 0)
else:

    def _clip(x, y):
        return False

    def _unclip():
        pass

    def _setpos(x, y):
        pass

    def _set_busy_cursor():
        return False

    def _restore_cursors():
        pass


def restore_cursors():
    """公开：还原系统光标为默认（幂等，非 Win 空操作）。"""
    if _IS_WIN:
        try:
            _restore_cursors()
        except Exception:
            pass


class CursorHijack:
    """光标劫持。坐标 = Win32 物理像素（屏幕全局，已由 window 按 dpr 换算）。"""

    def __init__(
        self,
        dev_x,
        dev_y,
        screen_w,
        screen_h,
        screen_x=0,
        screen_y=0,
        mock=False,
        lock_ticks=T_CURSOR_LOCK,
        mode="fall",
        watchdog_max=WATCHDOG_MAX,
        replace_cursor=True,
        knock_v=(0.0, 0.0),
    ):
        self.mock = mock or not _IS_WIN
        self.x = float(dev_x)
        self.y = float(dev_y)
        self.vy = 0.0
        self.vx = 0.0
        self.W = screen_w
        self.H = screen_h
        self.x0 = screen_x
        self.y0 = screen_y
        self.bottom = screen_y + screen_h - 2
        self.mode = mode
        self.knock_v = (float(knock_v[0]), float(knock_v[1]))
        if mode == "fall" and (knock_v[0] or knock_v[1]):
            self.phase = "knock"  # 受击：先弹开再 fall/lock
            self.vx = self.knock_v[0]  # 初速写入速度，_step_knock 才有位移
            self.vy = self.knock_v[1]
        elif mode == "hold":
            self.phase = "hold"
        else:
            self.phase = "fall"
        self.lock_ticks = int(lock_ticks)
        self.lock_t = 0
        self.watchdog = 0
        self.watchdog_max = int(watchdog_max)
        self.use_setpos = False  # ClipCursor 失败降级标志
        self.replace_cursor = bool(replace_cursor)  # False=不改系统光标样式
        self.active = True
        _ACTIVE.append(self)
        if not self.mock and self.replace_cursor:
            _set_busy_cursor()

    def hold_at(self, dev_x, dev_y):
        self.x = float(dev_x)
        self.y = float(dev_y)

    def update(self) -> bool:
        """推进一帧。返回是否仍活动。"""
        if not self.active:
            return False
        self.watchdog += 1
        if self.watchdog >= self.watchdog_max:
            self.release()
            return False

        if self.phase == "knock":
            self._step_knock()
        elif self.phase == "fall":
            self.vy += T_FALL_GRAV
            self.y += self.vy
            if self.y >= self.bottom:
                self.y = self.bottom
                self.vy = 0.0
                self.phase = "lock"
                self.lock_t = 0
        elif self.phase == "lock":
            self.lock_t += 1
            if self.lock_t >= self.lock_ticks:
                self.release()
                return False

        self._apply()
        return True

    def _step_knock(self):
        """受击弹开：初速指数衰减 + 轻度重力，速度够小即转 lock。"""
        self.vx *= K_KNOCK
        self.vy = self.vy * K_KNOCK + K_KNOCK_GRAV
        self.x += self.vx
        self.y += self.vy
        # 主动 SetCursorPos 推移，ClipCursor 只限范围看不出位移
        self.use_setpos = True
        if math.hypot(self.vx, self.vy) < K_KNOCK_LAND:
            self.phase = "lock"
            self.lock_t = 0

    def _apply(self):
        if self.mock:
            return
        x = min(max(self.x, self.x0), self.x0 + self.W - 1)
        y = min(max(self.y, self.y0), self.y0 + self.H - 1)
        if not self.use_setpos:
            ok = False
            try:
                ok = _clip(x, y)  # 失败则降级 SetCursorPos
            except Exception:
                ok = False
            if not ok:
                try:
                    _unclip()  # 先释放旧 clip
                except Exception:
                    pass
                self.use_setpos = True
        if self.use_setpos:
            try:
                _setpos(x, y)
            except Exception:
                pass

    def release(self):
        """释放 ClipCursor。幂等。"""
        if not self.active:
            return
        self.active = False
        self.phase = "done"
        if not self.mock:
            try:
                _unclip()
            except Exception:
                pass
            if self.replace_cursor:
                try:
                    _restore_cursors()
                except Exception:
                    pass
        try:
            _ACTIVE.remove(self)
        except ValueError:
            pass


def abort_all():
    """释放所有活动劫持。"""
    for h in list(_ACTIVE):
        h.release()
    if _IS_WIN:
        try:
            _unclip()  # 兜底
        except Exception:
            pass
        try:
            _restore_cursors()  # 兜底
        except Exception:
            pass


atexit.register(abort_all)
