"""音乐编排：把内置曲目与程序启动/环境状态联动。"""

from __future__ import annotations

import random
import time

# 内置曲目文件名（需与 resources/music 下的文件同名）
INTRO_TRACK = "RW_8+TitleRollRain_-_Sundown_(Theme_I).mp3"
INTRO_START_MS = 20000  # 序幕曲起始位置：跳过前 20s 前奏
ZEROG_TRACKS = (
    "NA_41_-_Random_Gods_(Theme_III).mp3",
    "VS_E_DEEP_GHOSTS+VS_F_THE_CORE_-_Deep_Light_(Theme_IV).mp3",
)
WATER_TRACK = "TH_SL_-_Threat_-_Shoreline.mp3"
# 聚焦氛围曲：设置窗 / 状态面板各一首，聚焦时播放、失焦停止
SETTINGS_AMBIENT_TRACK = "Rain Meadow.MP3"
HUD_AMBIENT_TRACK = "Passages.mp3"
# 聚焦氛围源：key -> (曲目文件, 启用开关配置键)
FOCUS_SOURCES = {
    "settings": (SETTINGS_AMBIENT_TRACK, "music_passages_enabled"),
    "hud": (HUD_AMBIENT_TRACK, "music_hud_enabled"),
}
ZEROG_GAIN = 0.4  # 零重力主题音量乘数（区别于程序音量，加载即先乘）
DEFAULT_GAIN = 1.0
FOCUS_MEM_TTL = 120  # 聚焦氛围曲进度记忆有效期（秒），超过则从头播


class MusicDirector:
    """按程序/环境状态调度特供曲目。"""

    def __init__(self, player, params):
        self._player = player
        self._params = params if params is not None else {}
        self._zerog_path = None  # 当前零重力主题曲路径
        self._water_path = None  # 当前涨水主题曲路径
        self._focus_path = None  # 当前聚焦氛围曲路径
        self._focus_source = None  # 当前聚焦氛围源：'settings' | 'hud'

    def play_intro(self):
        """程序启动：从 INTRO_START_MS 起播放序幕曲一次，放完即停（不受列表影响）。"""
        if self._player.muted:
            return
        track = self._player.resolve_track(INTRO_TRACK)
        if track is None:
            return
        self._player.play_special_track(
            track,
            gain=DEFAULT_GAIN,
            loop=False,
            stop_after_end=True,
            start_ms=INTRO_START_MS,
        )

    def on_zerog(self, on: bool):
        """零重力开关联动：进入随机播放主题曲，退出停止。"""
        if on:
            if not self._enabled("music_zerog_enabled"):
                return
            names = [
                n for n in ZEROG_TRACKS if self._player.resolve_track(n) is not None
            ]
            self._zerog_path = (
                self._play(random.choice(names), ZEROG_GAIN) if names else None
            )
        else:
            self._stop_if(self._zerog_path)
            self._zerog_path = None

    def on_water(self, on: bool):
        """涨水开关联动：进入播放主题曲，退出停止。"""
        if on:
            if self._enabled("music_water_enabled"):
                self._water_path = self._play(WATER_TRACK, DEFAULT_GAIN)
        else:
            self._stop_if(self._water_path)
            self._water_path = None

    def on_settings_focus(self, focused: bool):
        """设置窗聚焦联动：聚焦时续播氛围曲，失焦停止并记忆进度。"""
        self._on_focus("settings", focused)

    def on_hud_focus(self, focused: bool):
        """状态面板聚焦联动：同上，与设置窗可互相打断/续播。"""
        self._on_focus("hud", focused)

    def _on_focus(self, key: str, focused: bool):
        """聚焦氛围源统一入口：聚焦起播，失焦停播。"""
        if focused:
            self._start_focus(key)
        else:
            self._stop_focus(key)

    def _start_focus(self, key: str):
        """聚焦源进入：低优先级；可打断另一聚焦源，但不打断用户曲/环境主题曲。"""
        filename, enabled_key = FOCUS_SOURCES[key]
        if not self._enabled(enabled_key):
            return
        if self._other_playing():
            return  # 用户曲/环境主题曲占用，不打断
        # 若另一聚焦源正在播，先记住其进度再切换过去
        self._remember_focus()
        self._focus_path = self._play(filename, DEFAULT_GAIN, self._saved_ms(key))
        self._focus_source = key if self._focus_path else None

    def _stop_focus(self, key: str):
        """聚焦源退出：仅当当前氛围曲归属该源时，记忆进度并停止。"""
        if self._focus_source != key:
            return  # 已被另一聚焦源打断，勿误停
        if self._focus_path is not None:
            cur = self._player.current()
            if cur is not None and cur.path == self._focus_path:
                # 记住播放进度与时刻，2 分钟内再聚焦可续播
                self._params[f"music_{key}_ambient_ms"] = self._player.position()
                self._params[f"music_{key}_ambient_ts"] = int(time.time())
        self._stop_if(self._focus_path)
        self._focus_path = None
        self._focus_source = None

    def _remember_focus(self):
        """记住当前聚焦氛围曲的播放进度与时刻（供被打断后续播）。"""
        key = self._focus_source
        if key is None or self._focus_path is None:
            return
        cur = self._player.current()
        if cur is not None and cur.path == self._focus_path:
            self._params[f"music_{key}_ambient_ms"] = self._player.position()
            self._params[f"music_{key}_ambient_ts"] = int(time.time())

    def _saved_ms(self, key: str) -> int:
        """取某聚焦源记忆的播放位置；超过有效期则从头播。"""
        ts = int(self._params.get(f"music_{key}_ambient_ts", 0) or 0)
        if ts and (time.time() - ts) <= FOCUS_MEM_TTL:
            return max(0, int(self._params.get(f"music_{key}_ambient_ms", 0) or 0))
        return 0  # 记忆过期，从头播放

    # ── 内部 ──
    def _other_playing(self) -> bool:
        """是否有其它持续音乐在播：用户自选曲，或循环中的零重力/涨水主题曲。

        一次性特供曲（序幕曲、播完即停主题）不算占用，允许氛围曲打断。
        """
        if self._player.playing_user:
            return True
        cur = self._player.current()
        if cur is None or not self._player.looping:
            return False
        return cur.path in (self._zerog_path, self._water_path)

    def _enabled(self, key: str) -> bool:
        return bool(self._params.get(key, True)) and not self._player.muted

    def _play(self, filename: str, gain: float, start_ms: int = 0):
        """播放主题曲（独立于列表，按 theme_loop 决定循环/播完即停），返回路径。"""
        track = self._player.resolve_track(filename)
        if track is None:
            return None
        loop = self._player.theme_loop
        self._player.play_special_track(
            track,
            gain=gain,
            loop=loop,
            stop_after_end=not loop,
            start_ms=start_ms,
        )
        return track.path

    def _stop_if(self, path):
        """仅当当前氛围曲正是该曲目时才停止。"""
        if path is None:
            return
        cur = self._player.current()
        if cur is not None and cur.path == path and self._player.is_special_active:
            self._player.stop_ambient()
