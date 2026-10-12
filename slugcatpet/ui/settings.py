"""设置窗：猫增删/环境单选/HUD 开关，关窗即写盘。"""

from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QCheckBox,
    QRadioButton,
    QButtonGroup,
    QFrame,
    QDialog,
    QComboBox,
    QSpinBox,
    QScrollArea,
)
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QGuiApplication

from ..cats import REGISTRY
from ..i18n import t
from .._paths import resource_dir
from .. import i18n as _i18n
from ..window import MIN_PETS, MAX_PETS
from .catmenu import variant_label, pet_label
from .dialogs import ConfirmDialog, PickDialog, ColorDialog, RenameDialog
from .tips import install as install_tip
from ..platform import autostart as _autostart

_VARIANTS = tuple(REGISTRY)

_CHECK = (resource_dir() / "icons" / "check.svg").as_posix()  # 缺 QtSvg 时退化为高亮块

_QSS = (
    "QWidget{background:rgba(30,34,40,245);color:#e8f5d8;font-size:12px;}"
    "QLabel{color:#e8f5d8;}"
    "#secHeader{color:#aef156;font-size:13px;font-weight:bold;}"
    "#dim{color:#9fc080;}"
    "QPushButton{color:#e8f5d8;background:rgba(60,70,55,255);border:1px solid #4a5a3a;"
    "border-radius:5px;padding:4px 12px;}"
    "QPushButton:enabled:hover{background:rgba(80,100,70,255);}"
    "QPushButton:disabled{color:#777;background:rgba(45,48,52,255);}"
    "QCheckBox{color:#e8f5d8;}"
    "QRadioButton{color:#e8f5d8;spacing:8px;}"
    "QRadioButton::indicator{width:16px;height:16px;border-radius:8px;"
    "border:1px solid #52633f;background:#262b22;}"
    "QRadioButton::indicator:hover{border-color:#7c9a52;}"
    f"QRadioButton::indicator:checked{{border:2px solid #aef156;background:#aef156;"
    f"image:url({_CHECK});}}"
    "QComboBox{color:#e8f5d8;background:rgba(45,48,52,255);border:1px solid #4a5a3a;"
    "border-radius:5px;padding:2px 8px;min-width:96px;}"
    "QComboBox QAbstractItemView{background:rgba(30,34,40,255);color:#e8f5d8;"
    "selection-background-color:#5a7a3a;}"
    "QSpinBox{color:#e8f5d8;background:rgba(45,48,52,255);border:1px solid #4a5a3a;"
    "border-radius:5px;padding:2px 8px;min-width:64px;}"
    "QScrollArea{background:transparent;border:none;}"
    "QScrollBar:vertical{background:transparent;width:10px;margin:0;}"
    "QScrollBar::handle:vertical{background:rgba(120,150,100,140);border-radius:5px;"
    "min-height:28px;}"
    "QScrollBar::handle:vertical:hover{background:rgba(150,180,120,200);}"
    "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}"
    "QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical{background:transparent;}"
)


class SettingsWindow(QWidget):
    def __init__(self, window, hud, write_state):
        super().__init__()
        self._window = window
        self._hud = hud
        self._write_state = write_state
        window._settings_panel = self  # 供 window 反向同步世界态
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle(t("settings_title"))
        self.setStyleSheet(_QSS)
        self.setMinimumWidth(380)
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)
        self._outer.setSpacing(0)
        # 内容超屏时滚动，避免窗口过高
        self._area = QScrollArea()
        self._area.setWidgetResizable(True)
        self._area.setFrameShape(QFrame.Shape.NoFrame)
        self._area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._area.viewport().setAutoFillBackground(False)
        # 勿用无选择器 QSS：会被当 * 规则泄漏到子控件，抹掉按钮底色
        self._area.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        self._scroll = QWidget()
        self._scroll.setObjectName("settingsScroll")
        self._scroll.setStyleSheet("#settingsScroll{background:transparent;}")
        self._sv = QVBoxLayout(self._scroll)
        self._sv.setContentsMargins(16, 14, 16, 14)
        self._sv.setSpacing(3)
        self._area.setWidget(self._scroll)
        self._outer.addWidget(self._area)
        self._body = None
        self._dlg = None  # 弹窗单例守卫
        self._focused = False  # 当前是否聚焦（用于记忆氛围乐进度）
        self.installEventFilter(self)  # 聚焦时播放氛围乐
        self._rebuild()

    def open(self):
        self._rebuild()  # 重建以反映最新宠物/环境状态
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, ev):
        if self._focused:  # 关窗前先结算一次氛围乐进度
            self._on_focus(False)
        self._write_state()
        super().closeEvent(ev)

    def eventFilter(self, obj, ev):
        if obj is self:
            et = ev.type()
            if et == QEvent.Type.WindowActivate:
                self._on_focus(True)
            elif et == QEvent.Type.WindowDeactivate:
                self._on_focus(False)
        return super().eventFilter(obj, ev)

    def _on_focus(self, focused):
        """聚焦/失焦：联动播放/停止设置窗氛围乐。"""
        focused = bool(focused)
        if focused == self._focused:
            return
        self._focused = focused
        director = getattr(self._window, "_music_director", None)
        if director is not None:
            try:
                director.on_settings_focus(focused)
            except Exception:
                pass
        if not focused:
            self._write_state()  # 存下氛围乐进度

    def _sync_size(self):
        """按内容与屏幕高度定窗口尺寸，超出则启用滚动。"""
        self._scroll.adjustSize()
        hint = self._scroll.sizeHint()
        w = max(380, min(self.width(), 460) if self.width() > 1 else 400)
        screen = QGuiApplication.primaryScreen()
        avail_h = (
            screen.availableGeometry().height() if screen is not None else 800
        ) - 80
        h = min(hint.height(), avail_h)
        self.resize(w, max(h, 240))

    # 内容重建
    def _rebuild(self):
        self.setWindowTitle(t("settings_title"))
        if self._body is not None:
            self._sv.removeWidget(self._body)
            self._body.setParent(None)
            self._body.deleteLater()
        self._body = QWidget()
        v = QVBoxLayout(self._body)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        self._section_lang(v)
        v.addWidget(self._divider())
        self._section_cats(v)
        v.addWidget(self._divider())
        self._section_color(v)
        v.addWidget(self._divider())
        self._section_env(v)
        v.addWidget(self._divider())
        self._section_perf(v)
        v.addWidget(self._divider())
        self._section_interaction(v)
        v.addWidget(self._divider())
        self._section_sound(v)
        v.addWidget(self._divider())
        self._section_startup(v)
        v.addWidget(self._divider())
        self._section_hud(v)
        self._sv.addWidget(self._body)
        self._sv.addStretch(1)
        self._sync_size()

    @staticmethod
    def _header(text):
        lbl = QLabel(text)
        lbl.setObjectName("secHeader")
        return lbl

    @staticmethod
    def _divider():
        f = QFrame()
        f.setFixedHeight(1)
        f.setStyleSheet("background:rgba(120,150,100,90);border:none;")
        return f

    def _section_cats(self, v):
        v.addWidget(self._header(t("settings_cats_section")))
        pets = list(self._window.all_pets())
        can_remove = len(self._window.pets) > 1  # 至少保留一只可见
        for pet in pets:
            hidden = getattr(pet, "hidden", False)
            row = QHBoxLayout()
            row.setSpacing(8)
            name = QLabel(pet_label(pet, pets))
            if hidden:
                name.setText(name.text() + t("hud_hidden_suffix"))
            row.addWidget(name)
            row.addStretch(1)
            rn = QPushButton(t("settings_name"))
            rn.clicked.connect(lambda _c, p=pet: self._open_name_dialog(p))
            row.addWidget(rn)
            clr = QPushButton(t("settings_color"))
            clr.clicked.connect(lambda _c, p=pet: self._open_color_dialog(p))
            row.addWidget(clr)
            hid = QPushButton(t("settings_show") if hidden else t("settings_hide"))
            if hidden:
                if len(self._window.pets) >= self._window.cfg_max_pets:
                    hid.setEnabled(False)  # 满员，放回不下
                    install_tip(
                        hid, t("settings_max_pets", n=self._window.cfg_max_pets)
                    )
            elif len(self._window.pets) <= 1:
                hid.setEnabled(False)  # 至少保留一只可见
                install_tip(hid, t("settings_min_pets"))
            hid.clicked.connect(lambda _c, p=pet: self._toggle_hidden(p))
            row.addWidget(hid)
            rm = QPushButton(t("settings_remove"))
            rm.setEnabled(can_remove)
            if not can_remove:
                install_tip(rm, t("settings_min_pets"))
            rm.clicked.connect(lambda _c, p=pet: self._on_remove(p))
            row.addWidget(rm)
            v.addLayout(row)
        add = QPushButton(t("settings_add"))
        self._add_btn = add
        add.clicked.connect(self._on_add)
        self._sync_add_button()  # 按当前上限设可用态与 tooltip
        v.addWidget(add)
        cap = self._window.cfg_max_pets
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(QLabel(t("settings_max_pets_cap")))
        row.addStretch(1)
        spin = QSpinBox()
        spin.setRange(MIN_PETS, MAX_PETS)
        spin.setValue(cap)
        spin.setKeyboardTracking(False)  # 编辑完成才发信号，避免逐字符重建
        spin.valueChanged.connect(self._on_max_pets_changed)
        row.addWidget(spin)
        v.addLayout(row)

    def _section_color(self, v):
        v.addWidget(self._header(t("settings_color_section")))
        row = QHBoxLayout()
        row.addWidget(QLabel(t("settings_color_global")))
        row.addStretch(1)
        btn = QPushButton(t("settings_color"))
        btn.clicked.connect(self._open_global_color_dialog)
        row.addWidget(btn)
        v.addLayout(row)

    def _section_env(self, v):
        v.addWidget(self._header(t("settings_env_section")))
        grp = QButtonGroup(self._body)
        self._env_group = grp
        self._env_radios = {}
        current = self._current_env()
        for key, label_key in (
            ("none", "settings_env_none"),
            ("blizzard", "settings_snow"),
            ("zerog", "settings_zerog"),
            ("water", "settings_water"),
        ):
            rb = QRadioButton(t(label_key))
            rb.setChecked(key == current)
            rb.toggled.connect(
                lambda checked, k=key: checked and self._on_env_selected(k)
            )
            grp.addButton(rb)
            v.addWidget(rb)
            self._env_radios[key] = rb
        # 涨水高度（占窗口比例%）
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(QLabel(t("settings_water_depth")))
        row.addStretch(1)
        dspin = QSpinBox()
        dspin.setRange(5, 95)
        dspin.setValue(int(round(self._window.cfg_water_depth * 100)))
        dspin.setSuffix("%")
        dspin.setKeyboardTracking(False)  # 编辑完成才发信号
        install_tip(dspin, t("settings_water_depth_note"))
        dspin.valueChanged.connect(self._on_water_depth_changed)
        row.addWidget(dspin)
        v.addLayout(row)

    def _on_water_depth_changed(self, val):
        self._window.set_water_depth(val / 100.0)
        self._write_state()

    def _current_env(self):
        """从 window 环境态推导当前单选项。"""
        w = self._window
        if getattr(w, "blizzard_on", False):
            return "blizzard"
        if getattr(w, "zerog_on", False):
            return "zerog"
        if getattr(w, "water_on", False):
            return "water"
        return "none"

    def _on_env_selected(self, key):
        """选中 key 对应环境，互斥关其余（none=全关）。"""
        w = self._window
        if key != "blizzard" and getattr(w, "blizzard_on", False):
            w.blizzard_on = False
            w.blizzard_timer = 0
        if key != "zerog" and getattr(w, "zerog_on", False):
            w.set_zerog(False)
        if key != "water" and getattr(w, "water_on", False):
            w.set_water(False)
        if key == "blizzard" and not w.blizzard_on:
            w.blizzard_on = True
            w.blizzard_timer = 0
        elif key == "zerog" and not w.zerog_on:
            w.set_zerog(True)
        elif key == "water" and not w.water_on:
            w.set_water(True)

    def _section_hud(self, v):
        chk = QCheckBox(t("settings_show_hud"))
        chk.setChecked(self._hud.isVisible())
        chk.toggled.connect(self._on_hud_toggled)
        v.addWidget(chk)

    # 增删走卡片弹窗（open()=WindowModal，不 exec）
    def _on_add(self):
        if self._dlg is not None:
            return
        labels = []
        for variant in _VARIANTS:
            lbl = variant_label(variant)
            if REGISTRY[variant].wip:
                lbl += t("variant_wip_note")  # 占位种族挂提示
            labels.append(lbl)
        dlg = PickDialog(
            t("settings_pick_title"),
            t("settings_pick_cat"),
            labels,
            t("settings_ok"),
            t("settings_cancel"),
            parent=self,
        )
        dlg.finished.connect(lambda r, d=dlg: self._add_finished(d, r))
        self._dlg = dlg
        dlg.place_center(self)
        dlg.open()

    def _add_finished(self, dlg, result):
        self._dlg = None
        dlg.deleteLater()
        if result == QDialog.DialogCode.Accepted:
            self._window.add_pet(_VARIANTS[dlg.selected_index()])  # 内部刷 HUD+写盘
            self._rebuild()

    def _sync_add_button(self):
        """按当前猫咪上限与数量，更新添加按钮可用态与 tooltip。"""
        btn = getattr(self, "_add_btn", None)
        if btn is None:
            return
        cap = self._window.cfg_max_pets
        full = len(self._window.pets) >= cap
        btn.setEnabled(not full)
        install_tip(
            btn,
            lambda: t("settings_max_pets", n=self._window.cfg_max_pets)
            if len(self._window.pets) >= self._window.cfg_max_pets
            else "",
        )

    def _on_max_pets_changed(self, n):
        if n is None:
            return
        self._window.set_max_pets(n)
        self._write_state()
        self._sync_add_button()  # 仅更新添加按钮，避免整面板重建闪烁

    def _toggle_hidden(self, pet):
        w = self._window
        if getattr(pet, "hidden", False):
            changed = w.unhide_pet(pet)
        else:
            changed = w.hide_pet(pet)
        if changed:
            self._rebuild()

    def _on_remove(self, pet):
        if self._dlg is not None:
            return
        name = pet_label(pet, list(self._window.pets))
        dlg = ConfirmDialog(
            t("settings_remove"),
            t("settings_remove_confirm", name=name),
            t("settings_remove"),
            t("settings_cancel"),
            parent=self,
        )
        dlg.finished.connect(lambda r, p=pet, d=dlg: self._remove_finished(p, d, r))
        self._dlg = dlg
        dlg.place_center(self)
        dlg.open()

    def _remove_finished(self, pet, dlg, result):
        self._dlg = None
        dlg.deleteLater()
        if result == QDialog.DialogCode.Accepted and self._window.remove_pet(pet):
            self._rebuild()

    # 每猫自定义名字
    def _open_name_dialog(self, pet):
        if self._dlg is not None:
            return
        title = (
            f"{t('settings_name_title')} · {pet_label(pet, list(self._window.pets))}"
        )
        dlg = RenameDialog(
            title,
            pet.name,
            t("settings_name_placeholder"),
            t("settings_ok"),
            t("settings_cancel"),
            parent=self,
        )
        dlg.finished.connect(lambda r, p=pet, d=dlg: self._name_finished(p, d, r))
        self._dlg = dlg
        dlg.place_center(self)
        dlg.open()

    def _name_finished(self, pet, dlg, result):
        self._dlg = None
        if result == QDialog.DialogCode.Accepted:
            pet.name = dlg.name()  # 空=回落默认名
        dlg.deleteLater()
        self._write_state()
        self._rebuild()  # 刷新本页名字列

    # 每猫自定义配色
    def _open_color_dialog(self, pet):
        if self._dlg is not None:
            return
        scar_ok = bool(getattr(pet.gfx, "_face_scar_frame", None))
        racials = {"body": pet.cat.body_color, "eye": pet.cat.eye_color}
        title = (
            f"{t('settings_color_title')} · {pet_label(pet, list(self._window.pets))}"
        )
        dlg = ColorDialog(
            title,
            pet.colors,
            self._window.cfg_global_colors,
            racials,
            scar_ok,
            pet.cat.caps.gills,
            parent=self,
        )
        dlg.finished.connect(lambda r, p=pet, d=dlg: self._colors_finished(p, d, r))
        self._dlg = dlg
        dlg.place_center(self)
        dlg.open()

    def _colors_finished(self, pet, dlg, result):
        self._dlg = None
        if result == QDialog.DialogCode.Accepted:
            pet.colors = dlg.result_colors()
            pet.gfx.set_colors(pet._effective_colors())  # 合并全局后即时生效
        dlg.deleteLater()
        self._write_state()

    # 全局配色（作为各猫未覆盖项的基线）
    def _open_global_color_dialog(self):
        if self._dlg is not None:
            return
        scar_ok = any(
            getattr(p.gfx, "_face_scar_frame", None) for p in self._window.pets
        )
        gills_ok = any(p.cat.caps.gills for p in self._window.pets)
        dlg = ColorDialog(
            t("settings_color_global"),
            self._window.cfg_global_colors,
            None,
            None,
            scar_ok,
            gills_ok,
            parent=self,
        )
        dlg.finished.connect(lambda r, d=dlg: self._global_colors_finished(d, r))
        self._dlg = dlg
        dlg.place_center(self)
        dlg.open()

    def _global_colors_finished(self, dlg, result):
        self._dlg = None
        if result == QDialog.DialogCode.Accepted:
            self._window.set_global_colors(dlg.result_colors())  # 即时套用+写盘
        dlg.deleteLater()
        self._write_state()

    def _on_hud_toggled(self, checked):
        if checked != self._hud.isVisible():
            self._hud.toggle_visible()

    def _section_perf(self, v):
        v.addWidget(self._header(t("settings_perf_section")))
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(QLabel(t("settings_fps_label")))
        row.addStretch(1)
        combo = QComboBox()
        combo.addItem(t("settings_fps_auto", hz=self._refresh_hz()), "auto")
        for fps in (30, 60, 90, 120, 144, 165, 240):
            combo.addItem(f"{fps} FPS", fps)
        idx = combo.findData(self._window.cfg_fps_mode)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        combo.currentIndexChanged.connect(
            lambda _i, c=combo: self._on_fps_changed(c.currentData())
        )
        row.addWidget(combo)
        v.addLayout(row)
        chk = QCheckBox(t("settings_power_save"))
        chk.setChecked(self._window.cfg_power_save)
        chk.toggled.connect(self._on_power_save)
        v.addWidget(chk)

    def _refresh_hz(self):
        """取显示器刷新率取整；取不到回退 60。"""
        try:
            scr = QGuiApplication.primaryScreen()
            hz = int(round(scr.refreshRate())) if scr is not None else 0
        except Exception:
            hz = 0
        return hz if hz > 0 else 60

    def _on_fps_changed(self, mode):
        self._window.set_fps_mode(mode)
        self._write_state()

    def _on_power_save(self, checked):
        self._window.set_power_save(checked)
        self._write_state()

    def _section_interaction(self, v):
        v.addWidget(self._header(t("settings_interaction_section")))
        chk = QCheckBox(t("settings_cursor_hijack"))
        chk.setChecked(self._window.cfg_cursor_hijack)
        install_tip(chk, t("settings_cursor_hijack_note"))
        chk.toggled.connect(self._on_cursor_hijack)
        v.addWidget(chk)
        chk2 = QCheckBox(t("settings_cursor_hijack_cursor"))
        chk2.setChecked(self._window.cfg_cursor_hijack_cursor)
        install_tip(chk2, t("settings_cursor_hijack_cursor_note"))
        chk2.toggled.connect(self._on_cursor_hijack_cursor)
        v.addWidget(chk2)

    def _on_cursor_hijack(self, checked):
        self._window.set_cursor_hijack(checked)
        self._write_state()

    def _on_cursor_hijack_cursor(self, checked):
        self._window.set_cursor_hijack_cursor(checked)
        self._write_state()

    def _section_sound(self, v):
        v.addWidget(self._header(t("settings_sound_section")))
        player = getattr(self._window, "_music_player", None)
        chk = QCheckBox(t("settings_mute_all"))
        install_tip(chk, t("settings_mute_all_note"))
        saved_mute = bool(self._window._params.get("mute_all", False))
        chk.setChecked(bool(player.muted) if player is not None else saved_mute)
        chk.setEnabled(player is not None)
        chk.toggled.connect(self._on_mute_all)
        v.addWidget(chk)
        chk2 = QCheckBox(t("settings_zerog_music"))
        install_tip(chk2, t("settings_zerog_music_note"))
        chk2.setChecked(bool(self._window._params.get("music_zerog_enabled", True)))
        chk2.setEnabled(player is not None)
        chk2.toggled.connect(self._on_zerog_music)
        v.addWidget(chk2)
        chk3 = QCheckBox(t("settings_water_music"))
        install_tip(chk3, t("settings_water_music_note"))
        chk3.setChecked(bool(self._window._params.get("music_water_enabled", True)))
        chk3.setEnabled(player is not None)
        chk3.toggled.connect(self._on_water_music)
        v.addWidget(chk3)
        chk4 = QCheckBox(t("settings_passages_music"))
        install_tip(chk4, t("settings_passages_music_note"))
        chk4.setChecked(bool(self._window._params.get("music_passages_enabled", True)))
        chk4.setEnabled(player is not None)
        chk4.toggled.connect(self._on_passages_music)
        v.addWidget(chk4)
        chk5 = QCheckBox(t("settings_hud_music"))
        install_tip(chk5, t("settings_hud_music_note"))
        chk5.setChecked(bool(self._window._params.get("music_hud_enabled", True)))
        chk5.setEnabled(player is not None)
        chk5.toggled.connect(self._on_hud_music)
        v.addWidget(chk5)
        # 主题曲行为：播完即停 / 循环播放（互斥单选）
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(QLabel(t("music_theme_label")))
        row.addStretch(1)
        theme_grp = QButtonGroup(self._body)
        loop_on = bool(player.theme_loop) if player is not None else True
        rb_loop = QRadioButton(t("music_theme_loop"))
        rb_loop.setChecked(loop_on)
        rb_loop.setEnabled(player is not None)
        rb_loop.toggled.connect(lambda chk, v=True: chk and self._on_theme_behavior(v))
        theme_grp.addButton(rb_loop)
        row.addWidget(rb_loop)
        rb_once = QRadioButton(t("music_theme_once"))
        rb_once.setChecked(not loop_on)
        rb_once.setEnabled(player is not None)
        rb_once.toggled.connect(lambda chk, v=False: chk and self._on_theme_behavior(v))
        theme_grp.addButton(rb_once)
        row.addWidget(rb_once)
        v.addLayout(row)

    def _on_mute_all(self, checked):
        player = getattr(self._window, "_music_player", None)
        if player is not None:
            player.set_mute(checked)
        self._write_state()

    def _on_zerog_music(self, checked):
        self._window._params["music_zerog_enabled"] = bool(checked)
        self._write_state()

    def _on_water_music(self, checked):
        self._window._params["music_water_enabled"] = bool(checked)
        self._write_state()

    def _on_passages_music(self, checked):
        self._window._params["music_passages_enabled"] = bool(checked)
        self._write_state()

    def _on_hud_music(self, checked):
        self._window._params["music_hud_enabled"] = bool(checked)
        self._write_state()

    def _on_theme_behavior(self, loop):
        """设置主题曲行为：True 循环播放，False 播完即停。"""
        player = getattr(self._window, "_music_player", None)
        if player is not None:
            player.set_theme_loop(bool(loop))
        self._write_state()

    def _section_startup(self, v):
        v.addWidget(self._header(t("settings_startup_section")))
        chk = QCheckBox(t("settings_autostart"))
        chk.setChecked(_autostart.is_enabled())
        install_tip(chk, t("settings_autostart_note"))
        chk.toggled.connect(self._on_autostart)
        v.addWidget(chk)

    def _on_autostart(self, checked):
        _autostart.set_enabled(checked)
        actual = _autostart.is_enabled()
        if actual != checked:  # 写注册表失败 → 回填真实状态
            chk = self.sender()
            if chk is not None:
                chk.blockSignals(True)
                chk.setChecked(actual)
                chk.blockSignals(False)
        self._write_state()

    def _section_lang(self, v):
        v.addWidget(self._header(t("settings_lang_section")))
        row = QHBoxLayout()
        row.addWidget(QLabel(t("settings_lang")))
        row.addStretch(1)
        combo = QComboBox()
        combo.addItem(t("settings_lang_zh"), "zh")
        combo.addItem(t("settings_lang_en"), "en")
        idx = combo.findData(_i18n.LANG)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        combo.currentIndexChanged.connect(
            lambda _i, c=combo: self._on_lang_changed(c.currentData())
        )
        row.addWidget(combo)
        v.addLayout(row)

    def _on_lang_changed(self, lang):
        if lang is None or lang == _i18n.LANG:
            return
        _i18n.set_lang(lang)
        self._window.refresh_language()  # 重建 tabbar/hud/托盘/设置自身

    def rebuild_ui(self):
        """语言切换：整面板按新语言重建。"""
        self._rebuild()

    def refresh_env(self):
        """同步单选钮到真实环境态（未开窗跳过）。"""
        if not self.isVisible():
            return
        radios = getattr(self, "_env_radios", None)
        if not radios:
            return
        rb = radios.get(self._current_env())
        if rb is not None and not rb.isChecked():
            rb.setChecked(True)  # 互斥自动清其余，幂等
