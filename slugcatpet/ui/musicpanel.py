"""音乐播放面板：导入列表、播放/暂停、顺序/随机/单曲循环、音量与进度。"""

from __future__ import annotations
import os

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QListWidget,
    QListWidgetItem,
    QSlider,
    QFileDialog,
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices

from ..i18n import t
from ..audio.player import MODE_ORDER, MODE_SHUFFLE, MODE_ONE, fmt_time
from .tips import install as install_tip

_QSS = (
    "QWidget{background:rgba(30,34,40,245);color:#e8f5d8;font-size:12px;}"
    "QLabel{color:#e8f5d8;}"
    "#secHeader{color:#aef156;font-size:13px;font-weight:bold;}"
    "#dim{color:#9fc080;}"
    "#nowPlaying{color:#aef156;font-weight:bold;}"
    "QPushButton{color:#e8f5d8;background:rgba(60,70,55,255);border:1px solid #4a5a3a;"
    "border-radius:5px;padding:4px 12px;}"
    "QPushButton:enabled:hover{background:rgba(80,100,70,255);}"
    "QPushButton:disabled{color:#777;background:rgba(45,48,52,255);}"
    "QListWidget{background:rgba(24,27,31,255);border:1px solid #4a5a3a;border-radius:6px;"
    "color:#e8f5d8;padding:2px;}"
    "QListWidget::item{padding:4px 6px;border-radius:4px;}"
    "QListWidget::item:selected{background:rgba(80,100,70,255);}"
    "QListWidget::item:hover{background:rgba(60,72,55,180);}"
    "QSlider::groove:horizontal{height:6px;background:rgba(45,48,52,255);border-radius:3px;}"
    "QSlider::sub-page:horizontal{background:#6aa34a;border-radius:3px;}"
    "QSlider::handle:horizontal{width:12px;height:12px;margin:-4px 0;border-radius:6px;"
    "background:#aef156;}"
)

_MODE_KEYS = {
    MODE_ORDER: "music_mode_order",
    MODE_SHUFFLE: "music_mode_shuffle",
    MODE_ONE: "music_mode_one",
}


class MusicPanel(QWidget):
    """音乐播放面板窗口。"""

    def __init__(self, player, write_state=None, on_close=None):
        super().__init__()
        self._player = player
        self._write_state = write_state
        self._on_close = on_close
        self._syncing = False  # 程序改列表/滑块时抑制回调
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle(t("music_title"))
        self.setStyleSheet(_QSS)
        self.setMinimumWidth(420)
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(16, 14, 16, 14)
        self._outer.setSpacing(10)
        self._body = None
        self._connected = False
        self._rebuild()

    def open(self):
        if not self._connected:
            self._connect()
        self._refresh_list()
        self._refresh_now()
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, ev):
        self._save()
        super().closeEvent(ev)

    def _save(self):
        if self._write_state is not None:
            self._write_state()

    def _connect(self):
        """一次性连接播放器信号。"""
        self._player.track_changed.connect(lambda _t: self._refresh_now())
        self._player.playing_changed.connect(self._refresh_play_button)
        self._player.mode_changed.connect(lambda _m: self._refresh_mode())
        self._player.volume_changed.connect(self._refresh_volume)
        self._player.list_changed.connect(self._refresh_list)
        self._player.position_changed.connect(self._on_position)
        self._player.mute_changed.connect(lambda _m: self._refresh_now())
        self._player.failed.connect(self._on_failed)
        self._connected = True

    # ── 界面构建 ──
    def _rebuild(self):
        self.setWindowTitle(t("music_title"))
        if self._body is not None:
            self._outer.removeWidget(self._body)
            self._body.setParent(None)
            self._body.deleteLater()
        self._body = QWidget()
        v = QVBoxLayout(self._body)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)

        self._build_header(v)
        v.addWidget(self._divider())
        self._build_list(v)
        v.addWidget(self._divider())
        self._build_controls(v)
        self._build_progress(v)

        self._outer.addWidget(self._body)
        self._refresh_list()
        self._refresh_now()
        self._refresh_mode()
        self._refresh_volume(self._player.volume)
        self.adjustSize()

    @staticmethod
    def _divider():
        f = QFrame()
        f.setFixedHeight(1)
        f.setStyleSheet("background:rgba(120,150,100,90);border:none;")
        return f

    def _build_header(self, v):
        header = QLabel(t("music_title"))
        header.setObjectName("secHeader")
        v.addWidget(header)
        self._now_lbl = QLabel(t("music_empty"))
        self._now_lbl.setObjectName("nowPlaying")
        self._now_lbl.setWordWrap(True)
        v.addWidget(self._now_lbl)
        hint = QLabel(t("music_dirs_hint"))
        hint.setObjectName("dim")
        hint.setWordWrap(True)
        v.addWidget(hint)

    def _build_list(self, v):
        self._list = QListWidget()
        self._list.setMinimumHeight(150)
        self._list.itemDoubleClicked.connect(self._on_item_activated)
        self._list.currentRowChanged.connect(self._on_row_changed)
        v.addWidget(self._list)

    def _build_controls(self, v):
        # 导入行
        row = QHBoxLayout()
        row.setSpacing(6)
        b_files = QPushButton(t("music_import_files"))
        b_files.clicked.connect(self._import_files)
        row.addWidget(b_files)
        b_dir = QPushButton(t("music_import_dir"))
        b_dir.clicked.connect(self._import_dir)
        row.addWidget(b_dir)
        b_open = QPushButton(t("music_open_folder"))
        b_open.clicked.connect(self._open_folder)
        row.addWidget(b_open)
        b_rescan = QPushButton(t("music_rescan"))
        b_rescan.clicked.connect(self._rescan)
        row.addWidget(b_rescan)
        row.addStretch(1)
        b_remove = QPushButton(t("music_remove"))
        b_remove.clicked.connect(self._remove_selected)
        row.addWidget(b_remove)
        b_clear = QPushButton(t("music_clear"))
        b_clear.clicked.connect(self._player.clear)
        row.addWidget(b_clear)
        v.addLayout(row)

        # 播放控制行
        row2 = QHBoxLayout()
        row2.setSpacing(6)
        # 注意：clicked 会附带 checked=False，故用 lambda 屏蔽。
        self._prev_btn = QPushButton("⏮")
        install_tip(self._prev_btn, t("music_prev"))
        self._prev_btn.clicked.connect(lambda: self._player.prev())
        row2.addWidget(self._prev_btn)
        self._play_btn = QPushButton("▶")
        install_tip(self._play_btn, t("music_play"))
        self._play_btn.clicked.connect(lambda: self._player.toggle())
        row2.addWidget(self._play_btn)
        self._next_btn = QPushButton("⏭")
        install_tip(self._next_btn, t("music_next"))
        self._next_btn.clicked.connect(lambda: self._player.next())
        row2.addWidget(self._next_btn)
        self._mode_btn = QPushButton(t("music_mode_order"))
        install_tip(self._mode_btn, t("music_mode_order"))
        self._mode_btn.clicked.connect(self._player.cycle_mode)
        row2.addWidget(self._mode_btn)
        row2.addStretch(1)
        row2.addWidget(QLabel(t("music_volume")))
        self._vol = QSlider(Qt.Orientation.Horizontal)
        self._vol.setRange(0, 100)
        self._vol.setFixedWidth(120)
        self._vol.valueChanged.connect(self._on_volume)
        row2.addWidget(self._vol)
        v.addLayout(row2)

    def _build_progress(self, v):
        row = QHBoxLayout()
        row.setSpacing(6)
        self._pos_lbl = QLabel("00:00")
        row.addWidget(self._pos_lbl)
        # 快退 5 秒
        b_back = QPushButton("-5s")
        install_tip(b_back, t("music_back5"))
        b_back.clicked.connect(lambda: self._player.relative_seek(-5000))
        row.addWidget(b_back)
        self._seek = QSlider(Qt.Orientation.Horizontal)
        self._seek.setRange(0, 0)
        self._seek.sliderReleased.connect(self._on_seek_released)
        row.addWidget(self._seek, 1)
        # 快进 5 秒
        b_fwd = QPushButton("+5s")
        install_tip(b_fwd, t("music_forward5"))
        b_fwd.clicked.connect(lambda: self._player.relative_seek(5000))
        row.addWidget(b_fwd)
        self._dur_lbl = QLabel("00:00")
        row.addWidget(self._dur_lbl)
        v.addLayout(row)

    # ── 刷新 ──
    def _refresh_list(self):
        if not hasattr(self, "_list"):
            return
        self._syncing = True
        self._list.clear()
        for i, tr in enumerate(self._player.tracks):
            item = QListWidgetItem(f"{i + 1}. {tr.name}")
            self._list.addItem(item)
        if 0 <= self._player.index < self._list.count():
            self._list.setCurrentRow(self._player.index)
        self._syncing = False

    def _refresh_now(self):
        if not hasattr(self, "_now_lbl"):
            return
        cur = self._player.current()
        if cur is None:
            self._now_lbl.setText(t("music_empty"))
        else:
            idx = self._player.index + 1
            n = len(self._player.tracks)
            tags = ""
            if self._player.muted:
                tags += " 🔇"
            if self._player.looping:
                tags += " 🔁"
            self._now_lbl.setText(f"♪ {cur.name}  ({idx}/{n}){tags}")
        self._refresh_play_button(self._player.is_playing())
        self._refresh_selection()

    def _refresh_selection(self):
        if not hasattr(self, "_list"):
            return
        self._syncing = True
        if 0 <= self._player.index < self._list.count():
            self._list.setCurrentRow(self._player.index)
        self._syncing = False

    def _refresh_play_button(self, playing):
        if not hasattr(self, "_play_btn"):
            return
        self._play_btn.setText("⏸" if playing else "▶")

    def _refresh_mode(self):
        if not hasattr(self, "_mode_btn"):
            return
        key = _MODE_KEYS.get(self._player.mode, "music_mode_order")
        self._mode_btn.setText(t(key))
        install_tip(self._mode_btn, t(key))

    def _refresh_volume(self, v):
        if not hasattr(self, "_vol"):
            return
        self._syncing = True
        self._vol.setValue(int(v))
        self._syncing = False

    def _on_position(self, pos, dur):
        if not hasattr(self, "_seek"):
            return
        self._syncing = True
        self._seek.setRange(0, max(0, dur))
        if not self._seek.isSliderDown():
            self._seek.setValue(pos)
        self._pos_lbl.setText(fmt_time(pos))
        self._dur_lbl.setText(fmt_time(dur))
        self._syncing = False

    def _on_failed(self, path):
        name = os.path.basename(path)
        self._now_lbl.setText(f"⚠ {name}")

    # ── 交互 ──
    def _remove_selected(self):
        """移除当前选中曲目（仅移出列表，本地文件保持不动）。"""
        row = self._list.currentRow()
        if row < 0:
            self._now_lbl.setText(t("music_no_selection"))
            return
        self._player.remove_index(row)
        self._save()

    def _rescan(self):
        """重新扫描来源目录，找回新加入/已删除的文件。"""
        n = self._player.rescan()
        self._refresh_list()
        if n == 0:
            self._now_lbl.setText(t("music_empty"))
        self._save()

    def _on_item_activated(self, item):
        row = self._list.row(item)
        if row >= 0:
            self._player.set_index(row, autoplay=True)

    def _on_row_changed(self, row):
        if self._syncing or row < 0:
            return
        self._player.set_index(row, autoplay=self._player.is_playing())

    def _on_volume(self, v):
        if self._syncing:
            return
        self._player.set_volume(v)
        self._save()

    def _on_seek_released(self):
        self._player.seek(self._seek.value())

    def _import_files(self):
        exts = " ".join(f"*{e}" for e in _audio_exts())
        files, _ = QFileDialog.getOpenFileNames(
            self, t("music_pick_files"), "", f"Audio ({exts})"
        )
        if files:
            n = self._player.add_paths(files)
            self._notify(n)
            self._save()

    def _import_dir(self):
        d = QFileDialog.getExistingDirectory(self, t("music_pick_dir"), "")
        if d:
            n = self._player.add_paths([d])
            self._notify(n)
            self._save()

    def _open_folder(self):
        from .._paths import user_music_dir

        path = user_music_dir()
        try:
            os.startfile(str(path))  # Windows 资源管理器
        except (AttributeError, OSError):
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _notify(self, n):
        if n > 0:
            self._now_lbl.setText(t("music_imported", n=n))
        else:
            self._now_lbl.setText(t("music_import_none"))

    def rebuild_ui(self):
        """语言切换：整体重建。"""
        self._rebuild()

    def refresh_selection(self):
        """外部状态变化时同步选中行（未开窗跳过）。"""
        if self.isVisible():
            self._refresh_selection()


def _audio_exts():
    from ..audio.player import AUDIO_EXTS

    return AUDIO_EXTS
