"""自绘卡片弹窗：show()=非模态，open()=WindowModal，不走 exec。"""

from __future__ import annotations
from PySide6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QButtonGroup,
    QColorDialog,
    QLineEdit,
)
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QGuiApplication, QColor

from ..i18n import t
from ..rendering.graphics_draw import DEFAULT_SCAR, DEFAULT_GILL
from .tips import install as install_tip

# 壳级 QSS：防父窗样式渗透
_CARD_QSS = (
    "#cardShell{background:transparent;}"
    "#cardRoot{background:rgba(28,32,38,238);border-radius:14px;border:1px solid #4a5a3a;}"
    "#cardTitle{color:#cfe8b8;font-size:15px;font-weight:600;background:transparent;}"
    "#cardText{color:#e8f5d8;font-size:13px;background:transparent;}"
    "QLabel{background:transparent;}"
    "QPushButton{font-size:12px;padding:6px 14px;border-radius:8px;}"
    "#btnPrimary{background:#6aa34a;color:#0f1a08;font-weight:600;border:none;}"
    "#btnPrimary:hover{background:#7cb45a;}"
    "#btnGhost{background:transparent;color:#9fc080;border:1px solid #4a5a3a;}"
    "#btnGhost:hover{background:rgba(120,150,100,40);}"
    "#btnDanger{background:#8c3b3b;color:#f5ded8;font-weight:600;border:none;}"
    "#btnDanger:hover{background:#a34848;}"
    "QRadioButton{color:#e8f5d8;font-size:12px;spacing:8px;background:transparent;}"
    "QRadioButton::indicator{width:13px;height:13px;border-radius:7px;"
    "border:1px solid #4a5a3a;background:#2d3428;}"
    "QRadioButton::indicator:checked{background:#7cb45a;border-color:#7cb45a;}"
    "QLineEdit{color:#e8f5d8;background:rgba(45,48,52,255);border:1px solid #4a5a3a;"
    "border-radius:6px;padding:6px 8px;font-size:13px;}"
)

_BTN_KIND = {"primary": "btnPrimary", "ghost": "btnGhost", "danger": "btnDanger"}


class CardDialog(QDialog):
    """透明壳+卡片弹窗基类，空白区可拖动。"""

    def __init__(self, title: str, parent=None, width: int = 300):
        super().__init__(parent)
        self.setObjectName("cardShell")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Dialog
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._drag_off = None
        self._finished = False
        self._card = QWidget(self)
        self._card.setObjectName("cardRoot")
        self._card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._card.setFixedWidth(width)
        col = QVBoxLayout(self._card)
        col.setContentsMargins(24, 20, 24, 18)
        col.setSpacing(12)
        lbl = QLabel(title)
        lbl.setObjectName("cardTitle")
        col.addWidget(lbl)
        self.body = QVBoxLayout()
        self.body.setSpacing(10)
        col.addLayout(self.body)
        self._btn_row = QHBoxLayout()
        self._btn_row.setSpacing(10)
        self._btn_row.addStretch(1)
        col.addLayout(self._btn_row)
        self.setStyleSheet(_CARD_QSS)

    def done(self, result):
        if self._finished:  # 防二次发射 finished
            return
        self._finished = True
        super().done(result)

    def add_button(self, text: str, kind: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName(_BTN_KIND[kind])
        self._btn_row.addWidget(btn)
        return btn

    def place_center(self, host=None, offset: QPoint | None = None):
        """居中于 host（无则主屏），钳入屏内。"""
        self._card.adjustSize()
        size = self._card.size()
        self.resize(size)
        self._card.setGeometry(0, 0, size.width(), size.height())
        if host is not None:
            g = host.frameGeometry()
            x = g.x() + (g.width() - size.width()) // 2
            y = g.y() + (g.height() - size.height()) // 2
        else:
            scr = QGuiApplication.primaryScreen().availableGeometry()
            x = scr.x() + (scr.width() - size.width()) // 2
            y = scr.y() + (scr.height() - size.height()) // 3
        if offset is not None:
            x += offset.x()
            y += offset.y()
        self.move(self._clamped(QPoint(x, y)))

    def _clamped(self, pos: QPoint) -> QPoint:
        scr = QGuiApplication.primaryScreen().availableGeometry()
        x = max(scr.x(), min(pos.x(), scr.x() + scr.width() - self.width()))
        y = max(scr.y(), min(pos.y(), scr.y() + scr.height() - self.height()))
        return QPoint(x, y)

    # 卡片空白区拖动
    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._drag_off = (
                ev.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if self._drag_off is not None and (ev.buttons() & Qt.MouseButton.LeftButton):
            self.move(self._clamped(ev.globalPosition().toPoint() - self._drag_off))
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        self._drag_off = None
        super().mouseReleaseEvent(ev)


class ConfirmDialog(CardDialog):
    """确认弹窗（Accepted=确认）；cancel_btn 供外部程序化点击。"""

    def __init__(
        self,
        title: str,
        text: str,
        confirm_text: str,
        cancel_text: str,
        parent=None,
        width: int = 300,
    ):
        super().__init__(title, parent, width)
        lbl = QLabel(text)
        lbl.setObjectName("cardText")
        lbl.setWordWrap(True)
        self.body.addWidget(lbl)
        self.confirm_btn = self.add_button(confirm_text, "danger")
        self.confirm_btn.clicked.connect(self.accept)
        self.cancel_btn = self.add_button(cancel_text, "primary")
        self.cancel_btn.setDefault(True)
        self.cancel_btn.clicked.connect(self.reject)

    def showEvent(self, ev):
        super().showEvent(ev)
        self.cancel_btn.setFocus()  # 默认焦点在取消上


class PickDialog(CardDialog):
    """选择弹窗；Accepted 后读 selected_index()。"""

    def __init__(
        self,
        title: str,
        label: str,
        items: list,
        ok_text: str,
        cancel_text: str,
        parent=None,
        current: int = 0,
        width: int = 320,
    ):
        super().__init__(title, parent, width)
        lbl = QLabel(label)
        lbl.setObjectName("cardText")
        lbl.setWordWrap(True)
        self.body.addWidget(lbl)
        self._group = QButtonGroup(self)
        for i, item in enumerate(items):
            rb = QRadioButton(item)
            rb.setChecked(i == current)
            self._group.addButton(rb, i)
            self.body.addWidget(rb)
        self.cancel_btn = self.add_button(cancel_text, "ghost")
        self.cancel_btn.clicked.connect(self.reject)
        self.ok_btn = self.add_button(ok_text, "primary")
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self.accept)

    def selected_index(self) -> int:
        return max(0, self._group.checkedId())


def _hex(c) -> str:
    return "#%02x%02x%02x" % (int(c[0]), int(c[1]), int(c[2]))


class ColorDialog(CardDialog):
    """单只猫自定义配色：身体/脸部/疤痕，各自取色或恢复默认。"""

    def __init__(
        self,
        title: str,
        initial: dict,
        base_colors: dict | None,
        racials: dict | None,
        scar_ok: bool,
        gills_ok: bool,
        parent=None,
        width: int = 340,
    ):
        super().__init__(title, parent, width)
        self._base = base_colors or {}  # 未覆盖项的回退基线（全局配色）
        self._racials = racials or {}  # 种族默认色（body/eye）
        self._working = dict(initial)  # 确认才回落，取消丢弃
        self._rows = {}
        for key, label_key in (
            ("body", "settings_color_body"),
            ("eye", "settings_color_eye"),
            ("scar", "settings_color_scar"),
            ("gills", "settings_color_gills"),
        ):
            if key == "scar" and not scar_ok:
                continue  # 无疤不展示该行
            if key == "gills" and not gills_ok:
                continue  # 无鳃不展示该行
            row = QHBoxLayout()
            row.addWidget(QLabel(t(label_key)))
            row.addStretch(1)
            btn = QPushButton()
            btn.setFixedWidth(64)
            btn.setFixedHeight(24)
            btn.clicked.connect(lambda _c, k=key: self._pick(k))
            row.addWidget(btn)
            rst = QPushButton(t("settings_color_reset"))
            rst.clicked.connect(lambda _c, k=key: self._reset(k))
            row.addWidget(rst)
            self.body.addLayout(row)
            self._rows[key] = btn
        self.cancel_btn = self.add_button(t("settings_cancel"), "ghost")
        self.cancel_btn.clicked.connect(self.reject)
        self.ok_btn = self.add_button(t("settings_ok"), "primary")
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self.accept)
        self._refresh()

    def _effective(self, key):
        """当前展示色：暂存 > 全局基线 > 种族默认 > 固有色。"""
        if self._working.get(key):
            return self._working[key]
        if self._base.get(key):
            return self._base[key]
        if self._racials.get(key):
            return self._racials[key]
        return DEFAULT_GILL if key == "gills" else DEFAULT_SCAR

    def _refresh(self):
        for key, btn in self._rows.items():
            c = self._effective(key)
            btn.setText("")  # 只留纯色块，色号移到悬停提示
            install_tip(btn, _hex(c))
            btn.setStyleSheet(
                f"QPushButton{{background:rgb({int(c[0])},{int(c[1])},{int(c[2])});"
                "border:1px solid #4a5a3a;border-radius:5px;padding:2px 6px;}"
            )

    def _pick(self, key):
        cur = QColor(*self._effective(key))
        col = QColorDialog.getColor(cur, self, t("settings_color_pick"))
        if col.isValid():
            self._working[key] = (col.red(), col.green(), col.blue())
            self._refresh()

    def _reset(self, key):
        self._working.pop(key, None)
        self._refresh()

    def result_colors(self) -> dict:
        return dict(self._working)


class RenameDialog(CardDialog):
    """自定义名字输入：空值回落默认名。"""

    def __init__(
        self,
        title: str,
        initial: str,
        placeholder: str,
        ok_text: str,
        cancel_text: str,
        parent=None,
        width: int = 340,
    ):
        super().__init__(title, parent, width)
        self.edit = QLineEdit(initial)
        self.edit.setPlaceholderText(placeholder)
        self.edit.setMaxLength(24)
        self.edit.returnPressed.connect(self.accept)
        self.body.addWidget(self.edit)
        self.cancel_btn = self.add_button(cancel_text, "ghost")
        self.cancel_btn.clicked.connect(self.reject)
        self.ok_btn = self.add_button(ok_text, "primary")
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self.accept)

    def name(self) -> str:
        return self.edit.text().strip()
