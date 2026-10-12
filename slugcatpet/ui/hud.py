"""状态面板 HUD：每猫一行体征，可拖动可隐藏；猫多时内部滚动防溢出屏幕。"""

from __future__ import annotations
from PySide6.QtWidgets import QWidget, QVBoxLayout, QFrame, QScrollArea
from PySide6.QtCore import Qt, QTimer, QEvent
from PySide6.QtGui import QGuiApplication

from .hudrow import PetRow

REFRESH_MS = 200
SCREEN_PAD = 24  # 面板距屏幕边缘余量
SCROLLBAR_W = 10  # 预留滚动条宽度

_PANEL_QSS = (
    "#hudPanel{background:rgba(30,34,40,235);border-radius:10px;border:1px solid #4a5a3a;}"
    "QLabel{color:#e8f5d8;font-size:12px;}"
    "#hudName{color:#9fc080;font-size:12px;}"
    "#hudVal{color:#cfe8b8;font-size:11px;}"
    "#hudRowName{color:#aef156;font-size:13px;font-weight:bold;}"
)


class HudPanel(QWidget):
    def __init__(self, pet, params=None):
        super().__init__()
        self.pet = pet  # PetWindow
        self.params = params if params is not None else {}
        self._drag = None
        self._focused = False  # 当前是否聚焦（用于状态面板氛围乐）
        self.installEventFilter(self)  # 聚焦时播放氛围乐

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self._build()
        self._place()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        # 定时器由 toggle_visible 控制启停

        self.hide()

    def _pets(self):
        ap = getattr(self.pet, "all_pets", None)
        if ap is not None:
            return ap()  # 含隐藏猫，隐藏态加标注
        return getattr(self.pet, "pets", None) or [self.pet]

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        # 滚动容器：内容超高时内部滚动，避免面板溢出屏幕
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        # 勿用无选择器 QSS：会被当 * 规则泄漏到子控件
        vp = self._scroll.viewport()
        vp.setObjectName("hudViewport")
        vp.setStyleSheet("#hudViewport{background:transparent;}")
        self._panel = QWidget()
        self._panel.setObjectName("hudPanel")
        self._vbox = QVBoxLayout(self._panel)
        self._vbox.setContentsMargins(10, 8, 10, 8)
        self._vbox.setSpacing(6)
        self._panel.setStyleSheet(_PANEL_QSS)
        self._scroll.setWidget(self._panel)
        outer.addWidget(self._scroll)
        self._rows = []
        self._build_rows()

    def _build_rows(self):
        for i, pet_unit in enumerate(self._pets()):
            if i > 0:
                self._vbox.addWidget(self._divider())
            row = PetRow(pet_unit, self)
            self._vbox.addWidget(row)
            self._rows.append(row)

    @staticmethod
    def _divider():
        f = QFrame()
        f.setFixedHeight(1)
        f.setStyleSheet("background:rgba(120,150,100,90);border:none;")
        return f

    def rebuild_rows(self):
        """增删猫后重排行。"""
        while self._vbox.count():
            item = self._vbox.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._rows = []
        self._build_rows()
        self._refresh()
        self._place()

    def rebuild_ui(self):
        """语言切换：重建所有体征行以刷新文案。"""
        self.rebuild_rows()

    def _place(self):
        # 面板尺寸自适应内容高度，但不超过屏幕可用高度（超出则内部滚动）
        self._panel.layout().activate()
        hint = self._panel.sizeHint()
        screen = QGuiApplication.primaryScreen().availableGeometry()
        max_h = max(120, screen.height() - SCREEN_PAD * 2)
        w = hint.width() + SCROLLBAR_W
        h = min(hint.height(), max_h)
        self.resize(w, h)
        x = self.params.get("hud_x")
        y = self.params.get("hud_y")
        if x is None or y is None:
            x = screen.x() + SCREEN_PAD
            y = screen.y() + SCREEN_PAD
        x = max(screen.x(), min(screen.x() + screen.width() - self.width(), int(x)))
        y = max(screen.y(), min(screen.y() + screen.height() - self.height(), int(y)))
        self.move(x, y)
        self.params["hud_x"] = x
        self.params["hud_y"] = y

    def toggle_visible(self):
        # 实时记显隐（退出时查不到）
        if self.isVisible():
            if self._focused:  # 隐藏前先结算氛围乐进度
                self._on_focus(False)
            self.hide()
            self._timer.stop()  # 隐藏期不空转
            self.params["hud_visible"] = False
        else:
            self.show()
            self.raise_()
            self._refresh()
            self._timer.start(REFRESH_MS)
            self.params["hud_visible"] = True

    def eventFilter(self, obj, ev):
        if obj is self:
            et = ev.type()
            if et == QEvent.Type.WindowActivate:
                self._on_focus(True)
            elif et == QEvent.Type.WindowDeactivate:
                self._on_focus(False)
        return super().eventFilter(obj, ev)

    def _on_focus(self, focused):
        """聚焦/失焦：联动状态面板氛围乐（Passages）。"""
        focused = bool(focused)
        if focused == self._focused:
            return
        self._focused = focused
        director = getattr(self.pet, "_music_director", None)
        if director is not None:
            try:
                director.on_hud_focus(focused)
            except Exception:
                pass

    def _refresh(self):
        if not self.isVisible():
            return
        replot = False
        for row in self._rows:
            replot = row.refresh() or replot
        if replot:
            self._place()

    # 面板背景拖动整窗，行内由 PetRow 自理
    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._drag = ev.globalPosition().toPoint() - self.frameGeometry().topLeft()
            ev.accept()

    def mouseMoveEvent(self, ev):
        if self._drag is not None and ev.buttons() & Qt.MouseButton.LeftButton:
            screen = QGuiApplication.primaryScreen().availableGeometry()
            p = ev.globalPosition().toPoint() - self._drag
            x = max(screen.x(), min(screen.x() + screen.width() - self.width(), p.x()))
            y = max(
                screen.y(), min(screen.y() + screen.height() - self.height(), p.y())
            )
            self.move(x, y)
            self.params["hud_x"] = x
            self.params["hud_y"] = y
            ev.accept()

    def mouseReleaseEvent(self, ev):
        self._drag = None
        ev.accept()
