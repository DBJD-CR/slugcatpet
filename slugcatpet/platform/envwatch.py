"""环境守望：他人全屏让位 + 工作区/任务栏适应 + 置顶保持，单定时器 ≤2s 轮询。"""

from __future__ import annotations
import ctypes
from ctypes import wintypes

from PySide6.QtCore import QObject, QTimer
from PySide6.QtGui import QGuiApplication

from ..platform.topmost import TopmostKeeper

_TRUSTED_FULLSCREEN_STATES = {3, 4}  # D3D独占/演示态（SHQueryUserNotificationState）
_SHELL_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Button"}
POLL_MS = 1000  # ≤2000ms
_RECT_TOL = 2  # 矩形匹配容差(px)
_BOTTOM_COVER_FRAC = 0.5  # 底边覆盖：水平重叠须超过任务栏宽度该比例（防仅遮一角误判）


def _taskbar_rect():
    """主任务栏(Shell_TrayWnd)矩形(物理像素)；不可得 None。"""
    try:
        hwnd = ctypes.windll.user32.FindWindowW("Shell_TrayWnd", None)
        if not hwnd:
            return None
        rect = wintypes.RECT()
        if ctypes.windll.user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect)):
            return (rect.left, rect.top, rect.right, rect.bottom)
    except Exception:
        pass
    return None


def _taskbar_hidden() -> bool:
    """主任务栏是否不可见：被全屏应用(含后台全屏)遮挡或用户设为自动隐藏。"""
    try:
        hwnd = ctypes.windll.user32.FindWindowW("Shell_TrayWnd", None)
        if not hwnd:
            return False
        return not ctypes.windll.user32.IsWindowVisible(wintypes.HWND(hwnd))
    except Exception:
        return False


def _default_state_provider() -> int:
    """返回用户通知态；失败退化为 5（ACCEPTS_NOTIFICATIONS）。"""
    try:
        state = ctypes.c_int(0)
        hr = ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(state))
        if hr == 0:
            return state.value
    except Exception:
        pass
    return 5


def _default_foreground_provider():
    """返回前台窗 (hwnd, rect, 类名)；失败 None。"""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        rect = wintypes.RECT()
        if not user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect)):
            return None
        buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(wintypes.HWND(hwnd), buf, 256)
        return int(hwnd), (rect.left, rect.top, rect.right, rect.bottom), buf.value
    except Exception:
        return None


class EnvironmentWatcher(QObject):
    """单定时器轮询全屏与工作区变化。"""

    def __init__(
        self,
        windows,
        pet,
        state_provider=None,
        foreground_provider=None,
        interval_ms: int = POLL_MS,
        parent=None,
        topmost=None,
    ):
        super().__init__(parent)
        self._windows = list(windows)
        self._pet = pet
        self._state_provider = state_provider or _default_state_provider
        self._foreground_provider = foreground_provider or _default_foreground_provider
        self._fullscreen = False
        self._topmost = topmost or TopmostKeeper(
            self._windows, is_suspended=lambda: self._fullscreen
        )
        self._vis_snapshot: list[bool] | None = None
        self._area = None
        self._geo = None
        self._connected_screen = None
        self._timer = QTimer(self)
        self._timer.setInterval(min(interval_ms, 2000))
        self._timer.timeout.connect(self._on_poll)

    def start(self):
        """初始化工作区缓存、接信号、启动轮询。"""
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            self._area = screen.availableGeometry()
            self._geo = screen.geometry()
        self._connect_screen(screen)
        app = QGuiApplication.instance()
        if app is not None:
            try:
                app.primaryScreenChanged.connect(self._on_primary_changed)
            except Exception:
                pass
        self._timer.start()
        self._topmost.start()

    def stop(self):
        """停轮询与置顶钩子，并断开屏幕信号，防退出期回调已销毁窗口。"""
        self._timer.stop()
        self._topmost.stop()
        app = QGuiApplication.instance()
        if app is not None:
            try:
                app.primaryScreenChanged.disconnect(self._on_primary_changed)
            except Exception:
                pass
        if self._connected_screen is not None:
            try:
                self._connected_screen.availableGeometryChanged.disconnect(
                    self._on_screen_signal
                )
            except Exception:
                pass
            self._connected_screen = None

    def force_top(self):
        """手动刷新置顶：把全部窗口无条件提到最顶（解被其它程序盖住）。"""
        try:
            self._topmost.force_top()
        except Exception:
            pass

    # ── 轮询入口 ──
    def _on_poll(self):
        self._check_fullscreen()
        self._check_cover()
        self._check_workspace()
        self._topmost.reassert()

    # ── 底边覆盖适应 ──
    def _check_cover(self):
        """工作区底边是否被其它应用覆盖（最大化/域应用挡任务栏）→ 通知窗口沉到整屏底。"""
        pet = self._pet
        if not hasattr(pet, "set_env_top"):
            return
        if self._fullscreen:
            pet.set_env_top(False)  # 全屏时窗口隐藏，无需沉底
            return
        pet.set_env_top(self._detect_bottom_cover())

    def _detect_bottom_cover(self) -> bool:
        """工作区底边是否被覆盖 → 地板应下延到整屏底。
        判据一：任务栏不可见(自动隐藏)。
        判据二：前台窗矩形纵向盖住任务栏矩形，且横向覆盖足够。"""
        if _taskbar_hidden():
            return True
        fg = self._foreground_provider()
        if fg is None:
            return False
        hwnd, rect, cls = fg
        if hwnd in self._own_hwnds() or cls in _SHELL_CLASSES:
            return False
        tray = _taskbar_rect()
        if tray is None:
            return False
        tl, tt, tr, tb = tray
        tw = tr - tl
        if tb - tt <= 0 or tw <= 0:
            return False
        fl, ft, frr, fb = rect
        if not (ft <= tt + _RECT_TOL and fb >= tb - _RECT_TOL):
            return False  # 纵向未盖住整条任务栏
        covers_lr = fl <= tl + _RECT_TOL and frr >= tr - _RECT_TOL  # 左右两端都覆盖
        overlap = min(frr, tr) - max(fl, tl)  # 与任务栏水平重叠宽度
        return covers_lr or overlap >= tw * _BOTTOM_COVER_FRAC

    # ── 全屏让位 ──
    def _check_fullscreen(self):
        now_full = self._detect_fullscreen()
        if now_full and not self._fullscreen:
            self._enter_fullscreen()
        elif not now_full and self._fullscreen:
            self._exit_fullscreen()

    def _detect_fullscreen(self) -> bool:
        try:
            if self._state_provider() in _TRUSTED_FULLSCREEN_STATES:
                return True
        except Exception:
            pass
        return self._foreground_is_fullscreen()

    def _foreground_is_fullscreen(self) -> bool:
        """前台窗非自身、非桌面壳且铺满主屏 → 判定他人全屏。"""
        fg = self._foreground_provider()
        if fg is None:
            return False
        hwnd, rect, cls = fg
        if hwnd in self._own_hwnds():  # 排除自身窗（防御性）
            return False
        if cls in _SHELL_CLASSES:  # 排除桌面/任务栏
            return False
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return False
        g = screen.geometry()
        left, top, right, bottom = rect
        return (
            abs(left - g.x()) <= _RECT_TOL
            and abs(top - g.y()) <= _RECT_TOL
            and abs((right - left) - g.width()) <= _RECT_TOL
            and abs((bottom - top) - g.height()) <= _RECT_TOL
        )

    def _own_hwnds(self) -> set[int]:
        hwnds = set()
        for w in self._windows:
            try:
                hwnds.add(int(w.winId()))
            except Exception:
                pass
        return hwnds

    def _enter_fullscreen(self):
        """进入全屏：隐藏窗口并冻结 tick。"""
        self._fullscreen = True
        self._vis_snapshot = [self._is_visible(w) for w in self._windows]
        for w in self._windows:
            try:
                w.hide()
            except Exception:
                pass
        try:
            self._pet.freeze_tick()
        except Exception:
            pass

    def _exit_fullscreen(self):
        """解除全屏：恢复窗口可见态并解冻 tick。"""
        self._fullscreen = False
        try:
            self._pet.resume_tick()
        except Exception:
            pass
        snap = (
            self._vis_snapshot
            if self._vis_snapshot is not None
            else [True] * len(self._windows)
        )
        for w, vis in zip(self._windows, snap):
            if not vis:
                continue
            try:
                w.show()
            except Exception:
                pass
        self._vis_snapshot = None

    @staticmethod
    def _is_visible(w) -> bool:
        try:
            return bool(w.isVisible())
        except Exception:
            return True

    # ── 工作区/任务栏适应 ──
    def _check_workspace(self):
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        geo = screen.geometry()
        if self._area is not None and area == self._area and geo == self._geo:
            return
        self._area = area
        self._geo = geo
        try:
            self._pet.apply_workspace(area, geo)
        except Exception:
            pass

    def _connect_screen(self, screen):
        """接主屏信号，换屏时重接。"""
        if self._connected_screen is not None:
            try:
                self._connected_screen.availableGeometryChanged.disconnect(
                    self._on_screen_signal
                )
            except Exception:
                pass
        self._connected_screen = screen
        if screen is not None:
            try:
                screen.availableGeometryChanged.connect(self._on_screen_signal)
            except Exception:
                pass

    def _on_screen_signal(self, *args):
        self._check_workspace()

    def _on_primary_changed(self, screen):
        self._connect_screen(screen)
        self._check_workspace()
