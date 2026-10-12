"""启动应用，管理 PetWindow、TabBar、托盘、全局热键。"""

from __future__ import annotations
import sys
import os
import json
import signal
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QPixmap, QAction, QColor, QPainter
from PySide6.QtCore import QTimer

from .cats import default_def
from .window import PetWindow
from .ui.tabbar import TabBar
from .ui.hud import HudPanel
from .ui.settings import SettingsWindow
from .control.hotkey import HotkeyFilter, MOD_CONTROL, MOD_ALT, HK_PLACE_ESC
from .platform import cursorfx
from ._paths import user_dir
from .i18n import t
from . import i18n as _i18n

VK_Q = 0x51
VK_X = 0x58
VK_H = 0x48
HK_ABORT = 1
HK_QUIT = 2
HK_HUD = 3
_APP_PARAMS = user_dir() / "app.json"
SCHEMA_VERSION = 2  # pets[] 分猫存档
AUTOSAVE_MS = 60_000


def _tray_icon() -> QIcon:
    pm = QPixmap(32, 32)
    pm.fill(QColor(0, 0, 0, 0))
    p = QPainter(pm)
    p.setBrush(QColor(*default_def().body_color))
    p.setPen(QColor(40, 80, 20))
    p.drawEllipse(4, 4, 24, 24)
    p.end()
    return QIcon(pm)


def _migrate_params(params: dict) -> dict:
    """旧 schema 迁移为 v2 pets[] 格式。"""
    if params.get("schema_version") == SCHEMA_VERSION and isinstance(
        params.get("pets"), list
    ):
        return params
    from .behavior import tuning

    old_keys = ("energy", "temper", "food", "karma", "cold", "dead")
    if any(k in params for k in old_keys) or not params.get("pets"):
        pet_state = {
            "id": "pet-0",
            "variant": "saint",
            "energy": params.pop("energy", 1.0),
            "temper": params.pop("temper", 0.0),
            "food": params.pop("food", tuning.FOOD_INIT),
            "karma": params.pop("karma", tuning.KARMA_INIT),
            "cold": params.pop("cold", 0.0),
            "dead": params.pop("dead", False),
        }
        params["pets"] = [pet_state]
    params["schema_version"] = SCHEMA_VERSION
    return params


def _load_params(path: Path | None = None) -> dict:
    p = path or _APP_PARAMS
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        raw = {}
    return _migrate_params(raw)


def _save_params(params: dict, path: Path | None = None):
    """原子写盘，失败重试。"""
    p = path or _APP_PARAMS
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".tmp")
        tmp.write_text(
            json.dumps(params, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        for attempt in range(5):
            try:
                os.replace(tmp, p)
                break
            except OSError:
                if attempt == 4:
                    raise
                time.sleep(0.01)
    except Exception as e:
        print("[slugcatpet] save failed:", ascii(e), file=sys.stderr)


def setup_signal_handling(app):
    def _h(sig, frame):
        app.quit()

    signal.signal(signal.SIGINT, _h)
    t = QTimer()
    t.timeout.connect(lambda: None)
    t.start(500)  # 唤醒让 CPython 跑 SIGINT handler
    return t


def _ensure_assets_interactive() -> bool:
    """确保图集就绪，引导用户导入，返回是否成功。"""
    from .gameassets import atlases_present
    from ._paths import assets_dir

    if atlases_present(assets_dir()):
        return True
    from .ui.setup_panel import SetupPanel

    return SetupPanel().run()


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    from .platform.singleton import SingleInstance

    si = SingleInstance()
    if not si.acquire():
        si.notify_primary()
        return
    app._singleton = si  # 保持引用

    _sig = setup_signal_handling(app)  # noqa: F841  # 保持引用

    params = _load_params()

    _saved_lang = params.get("lang")
    if _saved_lang in ("zh", "en"):
        _i18n.set_lang(_saved_lang)  # 应用上次选择的语言

    from .platform.appid import ensure_app_id

    ensure_app_id(t("app_title"))  # 让音量合成器识别为独立应用

    if not _ensure_assets_interactive():
        return

    pet = PetWindow(params=params)
    pet.show()

    hud = HudPanel(pet, params)
    if params.get("hud_visible"):
        hud.toggle_visible()

    tab = TabBar(pet, app, params)
    tab.show()

    def _write_state():
        """序列化状态并写盘。"""
        params["tab_y"] = tab._y
        params["tab_expanded"] = tab.expanded
        params["hud_x"] = hud.x()
        params["hud_y"] = hud.y()
        params["pets"] = [
            {
                "id": p.id,
                "variant": p.variant,
                "energy": p.body.energy,
                "temper": p.body.temper,
                "food": p.body.food,
                "karma": p.body.karma,
                "cold": p.body.cold,
                "name": getattr(p, "name", ""),
                "colors": dict(p.colors),
                "dead": p.behavior is not None and p.behavior.is_truly_dead(),
                "hidden": getattr(p, "hidden", False),
            }
            for p in pet.all_pets()
        ]
        params["global_colors"] = dict(pet.cfg_global_colors)
        params["schema_version"] = SCHEMA_VERSION
        _save_params(params)

    pet._write_state_cb = _write_state  # 语言切换等触发持久化

    def _refresh_top():
        """把所有桌宠窗口无条件重新提到最顶（解被其它程序盖住）。"""
        env = getattr(app, "_envwatch", None)
        if env is not None:
            env.force_top()

    pet._refresh_top_cb = _refresh_top  # 右键菜单/托盘共用刷新置顶

    settings = SettingsWindow(pet, hud, _write_state)
    pet._hud = hud  # 供增删猫后 rebuild_rows
    pet._pets_changed_cb = _write_state  # 增删猫后写盘
    pet._open_settings_cb = settings.open  # 设置入口共用
    app._settings = settings  # 保持引用
    pet._tabbar = tab  # 语言切换重建：侧边栏
    pet._settings = settings  # 语言切换重建：设置窗

    # 音乐播放：内置目录 + 用户目录 + 上次导入的列表
    from .audio import MusicDirector, MusicPlayer
    from .ui.musicpanel import MusicPanel
    from ._paths import bundled_music_dir, user_music_dir

    def _remember_position():
        """把当前曲目与进度写入内存态（随后统一落盘）。"""
        cur = _player.current()
        if cur is None:
            return
        params["music_last_track"] = str(cur.path)
        # 特供/主题曲不记录进度（下次按其自身逻辑起播），普通曲目记进度
        params["music_last_ms"] = 0 if _player.is_special_active else _player.position()

    def _save_music_state():
        params["music_mode"] = _player.mode
        params["music_volume"] = _player.volume
        params["mute_all"] = _player.muted
        params["music_theme_loop"] = _player.theme_loop
        params["music_tracks"] = [str(tr.path) for tr in _player.tracks]
        params["music_hidden"] = _player.hidden
        params["music_sources"] = _player.sources
        _remember_position()
        _save_params(params)

    _player = MusicPlayer(params, on_change=_save_music_state)
    _saved_tracks = params.get("music_tracks")
    if isinstance(_saved_tracks, list):
        # 恢复上次列表（不记来源，避免与 music_sources 重复/污染重扫）
        _player.add_paths([p for p in _saved_tracks if Path(p).is_file()], record=False)
    _player.add_paths([bundled_music_dir(), user_music_dir()])
    # 恢复上次选中曲目与进度（仅选中，不自动播放）
    _player.restore_state(
        params.get("music_last_track"),
        int(params.get("music_last_ms", 0) or 0),
    )

    director = MusicDirector(_player, params)

    # 零重力联动：开关无重力时随机播放/停止主题曲
    _orig_set_zerog = pet.set_zerog

    def _set_zerog_hooked(on):
        _orig_set_zerog(on)
        director.on_zerog(bool(on))

    pet.set_zerog = _set_zerog_hooked

    # 涨水联动：开关涨水时播放/停止主题曲
    _orig_set_water = pet.set_water

    def _set_water_hooked(on):
        _orig_set_water(on)
        director.on_water(bool(on))

    pet.set_water = _set_water_hooked

    music = MusicPanel(_player, _write_state)
    pet._open_music_cb = music.open
    pet._music_panel = music
    pet._music_player = _player
    pet._music_director = director
    app._music_panel = music  # 保持引用

    # 启动序幕曲：延后到事件循环，确保音量与输出就绪
    QTimer.singleShot(300, director.play_intro)

    if params.get("tab_expanded", True):
        tab.toggle()

    tray = QSystemTrayIcon(_tray_icon())
    menu = QMenu()

    def _lang_action():
        """托盘内切换语言项：显示目标语言名，点击即切换并重建。"""
        if _i18n.LANG == "en":
            a = QAction(t("settings_lang_zh"), menu)
            a.triggered.connect(lambda: _i18n.set_lang("zh"))
        else:
            a = QAction(t("settings_lang_en"), menu)
            a.triggered.connect(lambda: _i18n.set_lang("en"))
        a.triggered.connect(pet.refresh_language)
        return a

    def _rebuild_tray_menu():
        tray.setToolTip(t("app_title"))
        menu.clear()
        act_settings = QAction(t("tray_settings"), menu)
        act_settings.triggered.connect(settings.open)
        act_music = QAction(t("tray_music"), menu)
        act_music.triggered.connect(music.open)
        act_hud = QAction(t("tray_hud"), menu)
        act_hud.triggered.connect(hud.toggle_visible)
        act_show = QAction(t("menu_show_all"), menu)
        act_show.setEnabled(pet.has_hidden_pets())
        act_show.triggered.connect(pet.show_all_pets)
        act_refresh = QAction(t("refresh_top"), menu)
        act_refresh.triggered.connect(_refresh_top)
        act_abort = QAction(t("tray_abort"), menu)
        act_abort.triggered.connect(cursorfx.abort_all)
        act_quit = QAction(t("tray_quit"), menu)
        act_quit.triggered.connect(app.quit)
        menu.addAction(act_settings)
        menu.addAction(act_music)
        menu.addAction(act_hud)
        menu.addAction(act_show)
        menu.addAction(act_refresh)
        menu.addAction(act_abort)
        menu.addSeparator()
        menu.addAction(_lang_action())
        menu.addSeparator()
        menu.addAction(act_quit)

    class _TrayBridge:
        def rebuild_ui(self):
            _rebuild_tray_menu()

    pet._tray = _TrayBridge()  # 语言切换重建：托盘菜单
    _rebuild_tray_menu()
    tray.setContextMenu(menu)
    tray.show()
    tray.showMessage(
        t("app_title"), t("tray_started"), QSystemTrayIcon.MessageIcon.Information, 4000
    )

    si.on_secondary_attempt = lambda: tray.showMessage(  # 后启实例触发提示
        t("app_title"),
        t("already_running"),
        QSystemTrayIcon.MessageIcon.Information,
        4000,
    )

    hotkey = HotkeyFilter()
    app.installNativeEventFilter(hotkey)
    hotkey.register(HK_ABORT, MOD_CONTROL | MOD_ALT, VK_Q)
    hotkey.register(HK_QUIT, MOD_CONTROL | MOD_ALT, VK_X)
    hotkey.register(HK_HUD, MOD_CONTROL | MOD_ALT, VK_H)
    pet._hotkey_filter = hotkey  # 放置模式临时挂/摘 Esc

    def _on_hotkey(hk_id):
        if hk_id == HK_QUIT:
            app.quit()
        elif hk_id == HK_HUD:
            hud.toggle_visible()
        elif hk_id == HK_PLACE_ESC:
            pet._exit_place_mode()
        else:
            cursorfx.abort_all()

    hotkey.triggered.connect(_on_hotkey)
    app._hotkey = hotkey  # 保持引用

    autosave = QTimer()
    autosave.timeout.connect(_write_state)
    autosave.start(AUTOSAVE_MS)
    app._autosave = autosave  # 保持引用

    from .platform.envwatch import EnvironmentWatcher

    envwatch = EnvironmentWatcher([pet, tab, hud, settings, music], pet)
    envwatch.start()
    app._envwatch = envwatch  # 保持引用

    def _cleanup():
        try:
            pet.shutdown()  # 先停帧定时器+关更新，防句柄销毁后重绘触发 QBackingStore 警告
        except Exception:
            pass
        app.removeNativeEventFilter(
            hotkey
        )  # 关停期需先摘 filter，防虚方法 dispatch 崩溃
        cursorfx.abort_all()
        try:
            from .control.mouse import set_passthrough

            if pet._hwnd:
                set_passthrough(pet._hwnd, False)
        except Exception:
            pass
        envwatch.stop()
        autosave.stop()
        try:
            _remember_position()  # 先记下当前进度再停
            _player.stop()  # 退出前停音乐
        except Exception:
            pass
        _write_state()
        hotkey.unregister_all()

    app.aboutToQuit.connect(_cleanup)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
