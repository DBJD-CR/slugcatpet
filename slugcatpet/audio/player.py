"""音乐播放核心：目录扫描 + QMediaPlayer 封装 + 顺序/随机/单曲循环。"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl, Signal

# 支持导入的音频扩展名（小写，含点）
AUDIO_EXTS = (
    ".mp3",
    ".wav",
    ".flac",
    ".ogg",
    ".m4a",
    ".aac",
    ".wma",
    ".opus",
    ".aiff",
    ".aif",
)

# 播放模式
MODE_ORDER = "order"  # 顺序播放
MODE_SHUFFLE = "shuffle"  # 随机播放
MODE_ONE = "one"  # 单曲循环

_MODES = (MODE_ORDER, MODE_SHUFFLE, MODE_ONE)

_FADE_MS = 350  # 曲目切换时的淡入/淡出时长
_FADE_TICK_MS = 20  # 渐变步进间隔


@dataclass(slots=True)
class Track:
    """一首曲目。"""

    path: Path

    @property
    def name(self) -> str:
        return self.path.stem

    @property
    def folder(self) -> str:
        return self.path.parent.name


def _norm(path) -> str:
    """归一化路径键：小写，用于去重与隐藏集合比对。"""
    try:
        return str(Path(path).resolve()).lower()
    except (TypeError, OSError):
        return str(path).lower()


def scan_tracks(dirs, recursive: bool = True) -> list[Track]:
    """扫描若干目录下的音频文件，按路径排序返回。"""
    found: dict[str, Path] = {}
    for d in dirs:
        try:
            root = Path(d)
        except TypeError:
            continue
        if not root.is_dir():
            continue
        it = root.rglob("*") if recursive else root.glob("*")
        for p in it:
            try:
                if p.is_file() and p.suffix.lower() in AUDIO_EXTS:
                    found[_norm(p)] = p
            except OSError:
                continue
    tracks = [Track(p) for p in found.values()]
    tracks.sort(key=lambda t: (str(t.path.parent).lower(), t.path.name.lower()))
    return tracks


def fmt_time(ms: int) -> str:
    """毫秒转 mm:ss。"""
    ms = max(0, int(ms))
    sec = ms // 1000
    return f"{sec // 60:02d}:{sec % 60:02d}"


def _load_media_classes():
    """延迟导入 QtMultimedia，缺失时给出可读提示。"""
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

    return QMediaPlayer, QAudioOutput


class MusicPlayer(QObject):
    """音乐播放器：管理曲目列表与播放状态，供 UI 绑定。

    音量分两层：volume（程序音量 0..100，用户可调）与 gain（每曲乘数 0..1，
    用于把特供曲目按比例压低）。实际输出 = 静音 ? 0 : volume/100 * gain。
    """

    track_changed = Signal(object)  # 当前曲目（Track 或 None）
    playing_changed = Signal(bool)  # 播放/暂停
    mode_changed = Signal(str)  # 播放模式
    volume_changed = Signal(int)  # 音量 0..100
    mute_changed = Signal(bool)  # 静音开关
    list_changed = Signal()  # 曲目列表变化
    position_changed = Signal(int, int)  # 当前位置/总长（毫秒）
    failed = Signal(str)  # 播放出错（曲目路径）
    played_once = Signal()  # play_once 曲目播放完毕
    theme_changed = Signal(bool)  # 主题曲行为（True=循环，False=播完即停）

    def __init__(self, params: dict | None = None, on_change=None, parent=None):
        super().__init__(parent)
        self._params = params if params is not None else {}
        self._on_change = on_change
        self._tracks: list[Track] = []
        # 被用户移除的曲目归一化键：扫描时跳过，持久化后不再自动加回
        self._hidden: set[str] = {
            p for p in (self._params.get("music_hidden") or []) if isinstance(p, str)
        }
        # 用户显式导入的曲目路径：重新扫描时据此还原
        self._sources: list[Path] = [
            Path(p)
            for p in (self._params.get("music_sources") or [])
            if isinstance(p, str)
        ]
        self._index = -1
        self._mode = self._params.get("music_mode", MODE_ORDER)
        if self._mode not in _MODES:
            self._mode = MODE_ORDER
        self._volume = int(self._params.get("music_volume", 70))
        self._volume = max(0, min(100, self._volume))
        self._gain = 1.0  # 当前曲目音量乘数（特供曲目用）
        self._mute = bool(self._params.get("mute_all", False))
        self._order: list[int] = []  # 随机模式下的播放次序（存索引）
        self._available = True
        # 特供曲目行为：放完即停 / 循环当前曲
        self._stop_after_end = False
        self._loop_current = False
        self._special_track: Track | None = None  # 当前特供曲（可不在列表中）
        self._theme_loop = bool(self._params.get("music_theme_loop", True))
        self._resume_ms = 0  # 恢复的播放位置，play 时应用一次
        self._pending_seek = None  # 待应用的目标播放位置（毫秒）
        # 音量渐变：切换曲目时渐弱/渐强
        self._fade = 1.0
        self._fade_target = 1.0
        self._fade_done = None
        self._fade_timer = QTimer(self)
        self._fade_timer.setInterval(_FADE_TICK_MS)
        self._fade_timer.timeout.connect(self._fade_step)
        try:
            QMediaPlayer, QAudioOutput = _load_media_classes()
            self._out = QAudioOutput()
            self._player = QMediaPlayer()
            self._player.setAudioOutput(self._out)
        except Exception:
            self._available = False
            self._out = None
            self._player = None
        self._apply_output_volume()
        if self._player is not None:
            self._player.mediaStatusChanged.connect(self._on_status)
            self._player.playbackStateChanged.connect(self._on_playback_state)
            self._player.positionChanged.connect(self._on_position)
            self._player.durationChanged.connect(self._on_duration)
            self._player.errorOccurred.connect(self._on_error)
        self._last_duration = 0

    # ── 属性 ──
    @property
    def available(self) -> bool:
        """QtMultimedia 是否可用。"""
        return self._available

    @property
    def tracks(self) -> list[Track]:
        return self._tracks

    @property
    def index(self) -> int:
        return self._index

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def volume(self) -> int:
        return self._volume

    @property
    def gain(self) -> float:
        return self._gain

    @property
    def muted(self) -> bool:
        return self._mute

    @property
    def looping(self) -> bool:
        """当前是否处于循环当前曲（特供曲目）状态。"""
        return self._loop_current

    @property
    def theme_loop(self) -> bool:
        """主题曲行为：True 循环播放，False 播完即停。"""
        return self._theme_loop

    @property
    def is_special_active(self) -> bool:
        """当前是否有特供/主题曲处于激活态（含播完即停尚未收尾）。"""
        return (
            self._special_track is not None
            or self._loop_current
            or self._stop_after_end
        )

    @property
    def playing_user(self) -> bool:
        """是否在播放用户自选的普通曲目（非特供/氛围曲）。"""
        return self.is_playing() and not self._loop_current and not self._stop_after_end

    def current(self) -> Track | None:
        if self._special_track is not None:
            return self._special_track  # 特供曲优先，独立于列表选中
        if 0 <= self._index < len(self._tracks):
            return self._tracks[self._index]
        return None

    def is_playing(self) -> bool:
        if self._player is None:
            return False
        from PySide6.QtMultimedia import QMediaPlayer

        return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def position(self) -> int:
        """当前播放位置（毫秒）。"""
        if self._player is None:
            return 0
        return int(self._player.position())

    def find(self, filename: str) -> int | None:
        """按文件名（不区分大小写）查找列表曲目索引；无则 None。"""
        target = Path(filename).name.lower()
        for i, t in enumerate(self._tracks):
            if t.path.name.lower() == target:
                return i
        return None

    def resolve_track(self, filename: str) -> Track | None:
        """按文件名解析特供曲目，独立于播放列表。

        先从列表命中，再回退到内置目录、用户目录与历史导入来源，
        因此即便曲目被移出列表，主题曲仍能正常解析播放。
        """
        name = Path(filename).name.lower()
        for t in self._tracks:
            if t.path.name.lower() == name:
                return t
        from .._paths import bundled_music_dir, user_music_dir

        seen: set[str] = set()
        for root in [*self._sources, bundled_music_dir(), user_music_dir()]:
            key = _norm(root)
            if key in seen:
                continue
            seen.add(key)
            try:
                rp = Path(root)
                if rp.is_file():
                    if rp.name.lower() == name:
                        return Track(rp)
                elif rp.is_dir():
                    for f in rp.glob("*"):
                        try:
                            if f.is_file() and f.name.lower() == name:
                                return Track(f)
                        except OSError:
                            continue
            except OSError:
                continue
        return None

    def restore_state(self, path, position_ms: int = 0):
        """恢复上次的选中曲目与进度（仅选中，不自动播放）。"""
        if not path:
            return
        key = _norm(path)
        for i, t in enumerate(self._tracks):
            if _norm(t.path) == key:
                self._index = i
                self._resume_ms = max(0, int(position_ms))
                self._select(i)
                return

    # ── 属性：隐藏与来源 ──
    @property
    def hidden(self) -> list[str]:
        """被用户移除的曲目路径列表（归一化键）。"""
        return sorted(self._hidden)

    @property
    def sources(self) -> list[str]:
        """用户显式导入的来源路径列表。"""
        return [str(p) for p in self._sources]

    # ── 列表管理 ──
    def add_paths(self, paths, record: bool = True) -> int:
        """加入若干文件/目录，返回新增曲目数。record 为真时记录来源以便重扫。"""
        files: list[Path] = []
        dirs: list[Path] = []
        for p in paths:
            try:
                pp = Path(p)
            except TypeError:
                continue
            if pp.is_dir():
                dirs.append(pp)
            elif pp.is_file():
                files.append(pp)
        if record:
            known = {_norm(p) for p in self._sources}
            for d in dirs + files:
                if _norm(d) not in known:
                    known.add(_norm(d))
                    self._sources.append(d)
        existing = {_norm(t.path) for t in self._tracks}
        added = 0
        for t in scan_tracks(dirs):
            key = _norm(t.path)
            if key not in existing and key not in self._hidden:
                existing.add(key)
                self._tracks.append(t)
                added += 1
        for f in files:
            if f.suffix.lower() not in AUDIO_EXTS:
                continue
            key = _norm(f)
            if key not in existing and key not in self._hidden:
                existing.add(key)
                self._tracks.append(Track(f))
                added += 1
        if added:
            self._tracks.sort(
                key=lambda t: (str(t.path.parent).lower(), t.path.name.lower())
            )
            self._index = self._reindex_after_sort()
            self._rebuild_order()
            self.list_changed.emit()
            self._changed()
        return added

    def load_dirs(self, dirs) -> int:
        """用若干目录的内容替换整个列表；返回曲目数。"""
        self._tracks = scan_tracks(dirs)
        self._index = 0 if self._tracks else -1
        self._rebuild_order()
        self.list_changed.emit()
        self.track_changed.emit(self.current())
        self._changed()
        return len(self._tracks)

    def remove_index(self, i: int):
        """移除第 i 首（仅移出列表，文件保持不动）；若正播放该曲则停止。"""
        if not (0 <= i < len(self._tracks)):
            return
        cur = self.current()
        removed = self._tracks.pop(i)
        self._hidden.add(_norm(removed.path))  # 记住移除，重扫不再加回
        if removed is cur:
            self.stop()
            self._special_track = None
        elif i < self._index:
            self._index -= 1
        self._index = min(self._index, len(self._tracks) - 1)
        self._rebuild_order()
        self.list_changed.emit()
        self.track_changed.emit(self.current())
        self._changed()

    def rescan(self) -> int:
        """重新扫描已记录的来源与内置目录，恢复被移除之外的新增曲目。

        已移除的曲目不会因扫描而复活（其余都在隐藏集合中），
        真正从磁盘删除的文件会随扫描结果一并剔除。
        """
        from .._paths import bundled_music_dir, user_music_dir

        dirs: list[Path] = []
        files: list[Path] = []
        seen: set[str] = set()
        for p in [*self._sources, bundled_music_dir(), user_music_dir()]:
            key = _norm(p)
            if key in seen:
                continue
            seen.add(key)
            try:
                if p.is_dir():
                    dirs.append(p)
                elif p.is_file():
                    files.append(p)
            except OSError:
                continue
        found = scan_tracks(dirs)
        for f in files:
            if f.suffix.lower() in AUDIO_EXTS:
                found.append(Track(f))
        kept = [t for t in found if _norm(t.path) not in self._hidden]
        kept.sort(key=lambda t: (str(t.path.parent).lower(), t.path.name.lower()))
        cur = self.current()
        cur_key = _norm(cur.path) if cur is not None else None
        self._tracks = kept
        if cur_key is not None:
            self._index = next(
                (i for i, t in enumerate(kept) if _norm(t.path) == cur_key),
                -1,
            )
        else:
            self._index = -1
        if self._player is not None and cur_key is not None and self._index < 0:
            self.stop()  # 当前曲目已不在列表中
        self._rebuild_order()
        self.list_changed.emit()
        self._changed()
        return len(kept)

    def clear(self):
        """清空列表并停止；同时清空隐藏记录与导入来源。"""
        self.stop()
        self._tracks = []
        self._index = -1
        self._order = []
        self._hidden.clear()
        self._sources = []
        self.list_changed.emit()
        self.track_changed.emit(None)
        self._changed()

    # ── 播放控制 ──
    def set_index(self, i: int, autoplay: bool = True):
        """定位到第 i 首并（可选）播放；视为用户操作，清除特供曲目设置。"""
        if not (0 <= i < len(self._tracks)):
            return
        self._clear_special()
        if autoplay:
            self._start_track(self._tracks[i], 1.0, False, False, list_index=i)
        else:
            self._select(i)

    def play(self):
        """播放当前曲目；无选中则从首曲开始。"""
        if not self._tracks:
            return
        if self._index < 0:
            self._index = self._shuffle_first() if self._mode == MODE_SHUFFLE else 0
        if self._player is None:
            return
        if self._player.source().isEmpty():
            self._select(self._index)
        if self._resume_ms:
            pos = self._resume_ms
            self._resume_ms = 0
            self._player.setPosition(pos)  # 已就绪直接定位
            self._pending_seek = pos  # 未就绪则媒体载入后补定位
        self._player.play()
        self._start_fade(1.0)  # 恢复播放时渐强

    def pause(self):
        if self._player is None:
            return
        if self.is_playing():
            self._start_fade(0.0, self._player.pause)  # 先渐弱再暂停
        else:
            self._player.pause()

    def toggle(self):
        """播放/暂停切换。"""
        if self.is_playing():
            self.pause()
        else:
            self.play()

    def stop(self):
        if self._player is None:
            return
        if self.is_playing():
            self._start_fade(0.0, self._player.stop)  # 先渐弱再停
        else:
            self._player.stop()

    def next(self, user: bool = True):
        """下一首。"""
        if not self._tracks:
            return
        self._clear_special()
        self._advance(1, user=user)

    def prev(self):
        """上一首。"""
        if not self._tracks:
            return
        self._clear_special()
        if self._player is not None and self._player.position() > 3000:
            self._player.setPosition(0)  # 播放超过 3s 先回到开头
            return
        self._advance(-1, user=True)

    def seek(self, ms: int):
        if self._player is not None:
            self._player.setPosition(max(0, int(ms)))

    def relative_seek(self, delta_ms: int):
        """在当前进度上偏移 delta_ms 毫秒（钳制在 0..总时长之间）。"""
        if self._player is None:
            return
        target = self._player.position() + int(delta_ms)
        target = max(0, target)
        if self._last_duration > 0:
            target = min(target, self._last_duration)
        self._player.setPosition(target)

    def set_mode(self, mode: str):
        """设置播放模式。"""
        if mode not in _MODES or mode == self._mode:
            return
        self._mode = mode
        self._rebuild_order()
        self.mode_changed.emit(mode)
        self._changed()

    def cycle_mode(self) -> str:
        """顺序切换模式并返回新模式。"""
        order = (MODE_ORDER, MODE_SHUFFLE, MODE_ONE)
        cur = order.index(self._mode) if self._mode in order else 0
        nxt = order[(cur + 1) % len(order)]
        self.set_mode(nxt)
        return nxt

    def set_volume(self, v: int):
        """设置音量 0..100。"""
        v = max(0, min(100, int(v)))
        if v == self._volume:
            return
        self._volume = v
        self._apply_output_volume()
        self.volume_changed.emit(v)
        self._changed()

    def set_gain(self, g: float):
        """设置当前曲目音量乘数 0..1（不写盘，随曲目切换复原）。"""
        g = max(0.0, min(1.0, float(g)))
        if abs(g - self._gain) < 1e-6:
            return
        self._rescale_fade(self._gain, g)  # 换算渐变系数，保持输出连续
        self._gain = g
        self._apply_output_volume()

    def set_mute(self, on: bool):
        """全局静音：屏蔽所有音效（实际输出置 0）。"""
        on = bool(on)
        if on == self._mute:
            return
        self._mute = on
        self._apply_output_volume()
        self.mute_changed.emit(on)
        self._changed()

    # ── 特供曲目（启动曲 / 环境主题）──
    def play_special_track(
        self,
        track,
        gain: float = 1.0,
        loop: bool = True,
        stop_after_end: bool = False,
        start_ms: int = 0,
    ):
        """按路径/曲目播放特供曲，独立于播放列表（含被移除的曲目）。

        不改变列表选中索引，用 _special_track 承载当前特供曲。
        """
        if not isinstance(track, Track):
            track = Track(Path(track))
        self._start_track(track, gain, loop, stop_after_end, start_ms)
        return track

    def set_theme_loop(self, on: bool):
        """设置主题曲行为：True 循环播放，False 播完即停。"""
        on = bool(on)
        if on == self._theme_loop:
            return
        self._theme_loop = on
        self.theme_changed.emit(on)
        self._changed()

    def stop_ambient(self):
        """停止氛围曲并复原音量乘数。"""
        self._clear_special()
        self.stop()

    # ── 内部 ──
    def _start_track(
        self,
        track: Track,
        gain: float,
        loop_current: bool,
        stop_after_end: bool,
        start_ms=0,
        list_index: int | None = None,
    ):
        """切换曲目并播放：先渐弱，切源后渐强。

        list_index 非 None 表示普通列表曲目（更新选中索引）；
        为 None 表示特供曲（写入 _special_track，不动选中索引）。
        """
        if track is None:
            return
        self._loop_current = loop_current
        self._stop_after_end = stop_after_end
        was_playing = self.is_playing()

        def do_switch():
            if list_index is None:
                self._special_track = track
            else:
                self._special_track = None
                self._index = list_index
            new_gain = max(0.0, min(1.0, float(gain)))
            self._rescale_fade(self._gain, new_gain)
            self._gain = new_gain
            if self._player is not None:
                url = QUrl.fromLocalFile(str(track.path))
                same = self._player.source() == url
                if same:
                    # 同曲重播：音源未变，载入事件不触发，直接定位
                    self._pending_seek = None
                    self._player.setPosition(int(start_ms) if start_ms else 0)
                    self._player.play()
                else:
                    # 异曲：等媒体就绪后再定位，否则会被忽略
                    self._pending_seek = int(start_ms) if start_ms else None
                    self._player.setSource(url)
                    if not start_ms:
                        self._player.setPosition(0)
                    self._player.play()
            self.track_changed.emit(self.current())
            self._apply_output_volume()
            self._start_fade(1.0)

        if self._player is not None and was_playing:
            self._start_fade(0.0, do_switch)  # 现有声渐弱后再切换
        else:
            self._fade = 0.0
            self._apply_output_volume()
            do_switch()  # 直接切换，从 0 渐强

    def _start_fade(self, target: float, done=None):
        """启动向 target 的音量渐变，到达后调用 done。"""
        self._fade_target = max(0.0, min(1.0, target))
        self._fade_done = done
        if abs(self._fade - self._fade_target) < 1e-3:
            self._fade = self._fade_target
            self._fade_done = None
            self._apply_output_volume()
            if done is not None:
                done()
            return
        self._fade_timer.start(_FADE_TICK_MS)

    def _fade_step(self):
        """定时器步进：逼近目标音量，到达即回调。"""
        target = self._fade_target
        step = _FADE_TICK_MS / float(_FADE_MS)
        if self._fade < target:
            self._fade = min(target, self._fade + step)
        elif self._fade > target:
            self._fade = max(target, self._fade - step)
        if abs(self._fade - target) < 1e-3:
            self._fade = target
            self._fade_timer.stop()
            done = self._fade_done
            self._fade_done = None
            self._apply_output_volume()
            if done is not None:
                done()
        else:
            self._apply_output_volume()

    def _select(self, i: int):
        """仅切换音源与当前索引并广播（不改播放态、清除特供态）。"""
        self._index = i
        self._special_track = None
        track = self.current()
        if self._player is not None and track is not None:
            self._player.setSource(QUrl.fromLocalFile(str(track.path)))
        self.track_changed.emit(track)

    def _clear_special(self):
        """清除特供曲目行为并复原音量乘数。"""
        self._stop_after_end = False
        self._loop_current = False
        self._special_track = None
        if self._gain != 1.0:
            # 先换算渐变系数再复原增益，避免输出音量瞬间突增造成爆音
            self._rescale_fade(self._gain, 1.0)
            self._gain = 1.0
            self._apply_output_volume()

    def _rescale_fade(self, old_gain: float, new_gain: float):
        """增益变化时换算渐变系数，使实际输出保持连续。

        输出 = volume * gain * fade；令新旧输出相等可得
        fade' = fade * old_gain / new_gain。fade 已到 0 则无需换算。
        """
        if self._fade > 1e-3 and old_gain > 0 and new_gain > 0:
            self._fade = min(1.0, self._fade * old_gain / new_gain)

    def _apply_output_volume(self):
        """按静音/音量/乘数计算并应用实际输出音量。"""
        if self._out is None:
            return
        if self._mute:
            v = 0.0
        else:
            v = (self._volume / 100.0) * self._gain * self._fade
        self._out.setVolume(max(0.0, min(1.0, v)))

    def _rebuild_order(self):
        """重建随机播放次序，保留当前曲目为起点。"""
        n = len(self._tracks)
        idx = list(range(n))
        random.shuffle(idx)
        if 0 <= self._index < n:
            idx.remove(self._index)
            idx.insert(0, self._index)
        self._order = idx

    def _shuffle_first(self) -> int:
        if self._order:
            return self._order[0]
        return 0

    def _advance(self, step: int, user: bool = False):
        """按模式推进 step 首并播放。"""
        n = len(self._tracks)
        if n == 0:
            return
        if self._mode == MODE_ONE and not user:
            self.set_index(self._index, autoplay=True)
            return
        if self._mode == MODE_SHUFFLE:
            if not self._order:
                self._rebuild_order()
            try:
                pos = self._order.index(self._index)
            except ValueError:
                pos = 0
            pos = (pos + step) % n
            self.set_index(self._order[pos], autoplay=True)
            return
        # 顺序播放
        nxt = self._index + step
        if nxt >= n or nxt < 0:
            if user:  # 用户操作时环绕
                nxt %= n
            else:  # 自动播放到末尾则停下
                self.stop()
                self.playing_changed.emit(False)
                return
        self.set_index(nxt, autoplay=True)

    def _reindex_after_sort(self) -> int:
        """排序后按当前曲目路径找回索引。"""
        cur = self.current()
        if cur is None:
            return -1
        for i, t in enumerate(self._tracks):
            if t.path == cur.path:
                return i
        return min(self._index, len(self._tracks) - 1)

    def _apply_seek(self, ms: int):
        """安全定位到指定毫秒（媒体就绪后调用）。"""
        if self._player is None:
            return
        self._player.setPosition(max(0, int(ms)))

    def _changed(self):
        if self._on_change is not None:
            try:
                self._on_change()
            except Exception:
                pass

    # ── QtMultimedia 回调 ──
    def _on_status(self, status):
        from PySide6.QtMultimedia import QMediaPlayer

        if status in (
            QMediaPlayer.MediaStatus.LoadedMedia,
            QMediaPlayer.MediaStatus.BufferedMedia,
        ):
            if self._pending_seek is not None:
                # 媒体就绪后再定位，否则会被忽略；延后一拍确保生效
                pos = self._pending_seek
                self._pending_seek = None
                QTimer.singleShot(60, lambda p=pos: self._apply_seek(p))
            return
        if status != QMediaPlayer.MediaStatus.EndOfMedia:
            return
        if self._loop_current:
            self._player.setPosition(0)
            self._player.play()
        elif self._stop_after_end:
            self.stop()
            self._clear_special()  # 复原增益、清除特供态，回到列表选中曲
            self.playing_changed.emit(False)
            self.played_once.emit()
        elif self._mode == MODE_ONE:
            self._player.setPosition(0)
            self._player.play()
        else:
            self._advance(1, user=False)

    def _on_playback_state(self, state):
        from PySide6.QtMultimedia import QMediaPlayer

        self.playing_changed.emit(state == QMediaPlayer.PlaybackState.PlayingState)

    def _on_position(self, pos):
        self.position_changed.emit(int(pos), int(self._last_duration))

    def _on_duration(self, dur):
        self._last_duration = dur
        self.position_changed.emit(int(self._player.position()), int(dur))

    def _on_error(self, *_args):
        track = self.current()
        if track is not None:
            self.failed.emit(str(track.path))
