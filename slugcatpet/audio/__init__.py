"""音频播放子系统：音乐播放器、曲目扫描与编排。"""

from __future__ import annotations

from PySide6.QtCore import QLoggingCategory

from .director import MusicDirector
from .player import (
    AUDIO_EXTS,
    MODE_ONE,
    MODE_ORDER,
    MODE_SHUFFLE,
    MusicPlayer,
    scan_tracks,
)

# FFmpeg 后端会把媒体元数据 / 设备探测信息打到控制台，这里统一静音。
# 残留的少量 [av1_mf]/[h264_mf] 行由 FFmpeg 直写 stderr，不经过 Qt 日志，无法从 Python 拦截。
QLoggingCategory.setFilterRules("qt.multimedia.*=false")

__all__ = [
    "MusicPlayer",
    "MusicDirector",
    "scan_tracks",
    "AUDIO_EXTS",
    "MODE_ORDER",
    "MODE_SHUFFLE",
    "MODE_ONE",
]
