"""界面文案中英两套 + 运行期取串。语言由 env / exe 名初定，可在设置中运行期切换。"""

from __future__ import annotations
import os
import sys
from pathlib import Path


def _detect_lang() -> str:
    env = os.environ.get("SLUGCATPET_LANG", "").strip().lower()
    if env in ("zh", "en"):
        return env
    if getattr(sys, "frozen", False) and Path(sys.executable).stem.lower().endswith(
        "-en"
    ):
        return "en"
    return "zh"


LANG = _detect_lang()


def set_lang(lang: str) -> None:
    """运行期切换语言（'zh'/'en'）；调用方需重建界面以刷新文案。"""
    global LANG
    if lang in ("zh", "en"):
        LANG = lang


_STR = {
    # —— 通用 / 产品名 ——
    "app_title": {"zh": "蛞蝓猫桌宠", "en": "Slugcat Pet"},
    # —— setup_panel：首次导入面板 ——
    "setup_importing": {"zh": "正在导入素材…", "en": "Importing assets…"},
    "setup_hint_init": {
        "zh": "首次启动需从你的游戏读取画面，请稍候",
        "en": "First launch needs to read the picture from your game, please wait",
    },
    "setup_hint_busy": {
        "zh": "首次启动需从你的游戏读取素材，请稍候。未来不再需要读取",
        "en": "First launch needs to read assets from your game, please wait. Won't be needed again in the future",
    },
    "setup_hint_error": {
        "zh": "点【选择 RainWorld 文件夹】手动指定：选中的文件夹里应能看到 RainWorld.exe 和 RainWorld_Data 文件夹",
        "en": "Click [Select RainWorld folder] to specify manually: the chosen folder should contain RainWorld.exe and the RainWorld_Data folder",
    },
    "setup_quit": {"zh": "退出", "en": "Quit"},
    "setup_pick": {"zh": "选择 RainWorld 文件夹", "en": "Select RainWorld folder"},
    "setup_unexpected": {
        "zh": "导入时发生意外错误：{e}",
        "en": "Unexpected error during import: {e}",
    },
    # —— tabbar：图标盘 tooltip ——
    "tip_vpole": {"zh": "放竖杆", "en": "Place vertical pole"},
    "tip_hpole": {"zh": "放横杆", "en": "Place horizontal pole"},
    "tip_fruit": {"zh": "放果子", "en": "Place fruit"},
    "tip_stone": {"zh": "放石头", "en": "Place stone"},
    "tip_lamp": {"zh": "放灯笼", "en": "Place lantern"},
    "tip_slimemold": {"zh": "放黏菌", "en": "Place slime mold"},
    "tip_batfly": {"zh": "放蝠蝇", "en": "Place batfly"},
    "tip_remove": {"zh": "移除单个物品", "en": "Remove single item"},
    "tip_clear": {"zh": "清除所有可交互实体", "en": "Clear All placed items"},
    # —— tabbar：toast ——
    "toast_max_fruit": {
        "zh": "场上最多 12 个果子",
        "en": "At most 12 fruits on the field",
    },
    "toast_max_stone": {
        "zh": "场上最多 12 个石头",
        "en": "At most 12 stones on the field",
    },
    "toast_max_slimemold": {
        "zh": "场上最多 12 个黏菌",
        "en": "At most 12 slime molds on the field",
    },
    "toast_max_batfly": {
        "zh": "场上最多 12 只蝠蝇",
        "en": "At most 12 batflies on the field",
    },
    "toast_max_vpole": {
        "zh": "场上最多 6 根竖杆",
        "en": "At most 6 vertical poles on the field",
    },
    "toast_max_hpole": {
        "zh": "场上最多 6 根横杆",
        "en": "At most 6 horizontal poles on the field",
    },
    "toast_no_object": {"zh": "场上没有物体", "en": "No objects on the field"},
    # —— 放置模式：操作提示（左键连续放置，右键/Esc 退出）——
    "place_hint_cont": {
        "zh": "左键连续放置　·　右键 / Esc 退出",
        "en": "Left-click to place repeatedly  ·  Right-click / Esc to exit",
    },
    "place_hint_remove": {
        "zh": "左键移除选中的物品　·　右键 / Esc 退出",
        "en": "Left-click to remove the item under cursor  ·  Right-click / Esc to exit",
    },
    # —— tabbar：动作按钮 ——
    "btn_quit_app": {"zh": "退出程序", "en": "Quit program"},
    # —— 杀死确认弹窗（猫菜单「杀死该猫」复用）——
    "dlg_confirm_title": {"zh": "确认", "en": "Confirm"},
    "dlg_kill_text": {
        "zh": "确定要杀死 {name} 吗？",
        "en": "Are you sure you want to kill {name}?",
    },
    "dlg_kill_yes": {"zh": "杀死", "en": "Kill"},
    "dlg_kill_no": {"zh": "取消", "en": "Cancel"},
    # —— hud：状态面板字段名 ——
    "hud_karma": {"zh": "业力", "en": "Karma"},
    "hud_stamina": {"zh": "体力", "en": "Stamina"},
    "hud_satiety": {"zh": "饱食", "en": "Satiety"},
    "hud_affection": {"zh": "好感", "en": "Affection"},
    "hud_cold": {"zh": "寒冷", "en": "Cold"},
    "hud_air": {"zh": "氧气", "en": "Oxygen"},
    "hud_op_hint": {
        "zh": "右键蛞蝓猫或点击此行可操作",
        "en": "Right-click the slugcat or click this row to operate",
    },
    # —— 皮名（variant 显示名） ——
    "variant_saint": {"zh": "圣徒", "en": "Saint"},
    "variant_rivulet": {"zh": "溪流", "en": "Rivulet"},
    "variant_survivor": {"zh": "白猫", "en": "Survivor"},
    "variant_monk": {"zh": "黄猫", "en": "Monk"},
    "variant_hunter": {"zh": "猎手", "en": "Hunter"},
    "variant_artificer": {"zh": "工匠", "en": "Artificer"},
    "variant_wip_note": {
        "zh": "（外观差异待后续）",
        "en": "(appearance differences TBD)",
    },
    # —— 猫菜单 ——
    "menu_kill_pet": {"zh": "杀掉该猫", "en": "Kill this cat"},
    "menu_reset_pet": {"zh": "重置该猫", "en": "Reset this cat"},
    "menu_reincarnating": {"zh": "转世中…", "en": "Reincarnating…"},
    "menu_open_settings": {"zh": "打开设置", "en": "Open settings"},
    "menu_control_pet": {"zh": "控制该猫", "en": "Control this cat"},
    "menu_exit_control": {"zh": "退出控制", "en": "Exit control"},
    "menu_hide_pet": {"zh": "隐藏该猫", "en": "Hide this cat"},
    "menu_show_pet": {"zh": "显示该猫", "en": "Show this cat"},
    "menu_show_all": {"zh": "显示全部隐藏的猫", "en": "Show all hidden cats"},
    "refresh_top": {"zh": "刷新置顶", "en": "Refresh topmost"},
    # —— 控制 HUD ——
    "ctrlhud_title": {"zh": "控制中：{name}", "en": "Controlling: {name}"},
    "ctrlhud_paused": {"zh": "已暂停 · 点击继续", "en": "Paused · click to resume"},
    "ctrlhud_exit": {"zh": "退出控制 (Esc)", "en": "Exit control (Esc)"},
    "ctrlhud_keys": {
        "zh": "{move} 移动，{jump} 跳跃",
        "en": "{move} to move, {jump} to jump",
    },
    # —— 设置窗 ——
    "settings_title": {"zh": "蛞蝓猫桌宠设置", "en": "Slugcatpet Settings"},
    "settings_cats_section": {"zh": "蛞蝓猫", "en": "Slugcats"},
    "settings_add": {"zh": "添加", "en": "Add"},
    "settings_remove": {"zh": "移除", "en": "Remove"},
    "settings_hide": {"zh": "隐藏", "en": "Hide"},
    "settings_show": {"zh": "显示", "en": "Show"},
    "settings_max_pets": {"zh": "最多 {n} 只", "en": "At most {n} cats"},
    "settings_max_pets_cap": {"zh": "蛞蝓猫数量上限", "en": "Max slugcats"},
    "settings_min_pets": {"zh": "至少保留 1 只", "en": "Keep at least 1 cat"},
    "settings_name": {"zh": "改名", "en": "Rename"},
    "hud_hidden_suffix": {"zh": "（已隐藏）", "en": " (hidden)"},
    "settings_name_title": {"zh": "自定义名字", "en": "Custom name"},
    "settings_name_placeholder": {
        "zh": "留空使用默认名",
        "en": "Leave empty for default name",
    },
    "settings_color": {"zh": "配色", "en": "Colors"},
    "settings_color_section": {"zh": "配色", "en": "Colors"},
    "settings_color_global": {"zh": "全局配色", "en": "Global colors"},
    "settings_color_title": {"zh": "自定义颜色", "en": "Custom colors"},
    "settings_color_body": {"zh": "身体颜色", "en": "Body color"},
    "settings_color_eye": {"zh": "脸部/眼睛", "en": "Face / eye"},
    "settings_color_scar": {"zh": "疤痕颜色", "en": "Scar color"},
    "settings_color_gills": {"zh": "鳃颜色", "en": "Gill color"},
    "settings_color_reset": {"zh": "恢复默认", "en": "Reset to default"},
    "settings_color_pick": {"zh": "选择颜色", "en": "Pick a color"},
    "settings_remove_confirm": {"zh": "确定移除 {name}？", "en": "Remove {name}?"},
    "settings_env_section": {"zh": "环境", "en": "Environment"},
    "settings_env_none": {"zh": "无", "en": "None"},
    "settings_snow": {"zh": "暴风雪", "en": "Blizzard"},
    "settings_zerog": {"zh": "无重力", "en": "Zero gravity"},
    "settings_water": {"zh": "涨水", "en": "Flood"},
    "settings_water_depth": {"zh": "涨水高度", "en": "Flood height"},
    "settings_water_depth_note": {
        "zh": "水面深度占窗口高度的比例，越大水越深",
        "en": "Water depth as a fraction of the window height; larger means deeper",
    },
    "settings_show_hud": {"zh": "显示状态面板", "en": "Show status panel"},
    "settings_pick_title": {"zh": "选择皮", "en": "Pick a variant"},
    "settings_pick_cat": {"zh": "选择要添加的蛞蝓猫", "en": "Choose a slugcat to add"},
    "settings_ok": {"zh": "确定", "en": "OK"},
    "settings_cancel": {"zh": "取消", "en": "Cancel"},
    "settings_lang_section": {"zh": "语言", "en": "Language"},
    "settings_lang": {"zh": "界面语言", "en": "Interface language"},
    "settings_lang_zh": {"zh": "简体中文", "en": "简体中文"},
    "settings_lang_en": {"zh": "English", "en": "English"},
    "settings_perf_section": {"zh": "性能", "en": "Performance"},
    "settings_fps_label": {"zh": "渲染帧率", "en": "Render FPS"},
    "settings_fps_auto": {"zh": "自动（{hz} Hz）", "en": "Auto ({hz} Hz)"},
    "settings_power_save": {
        "zh": "省电模式（发呆时降至 15 FPS）",
        "en": "Power-save mode (drop to 15 FPS when idle)",
    },
    "settings_interaction_section": {"zh": "交互", "en": "Interaction"},
    "settings_cursor_hijack": {"zh": "允许光标抢夺", "en": "Allow cursor hijack"},
    "settings_cursor_hijack_note": {
        "zh": "关闭后猫不再抢夺/锁定鼠标光标",
        "en": "When off, cats won't hijack/lock the cursor",
    },
    "settings_cursor_hijack_cursor": {
        "zh": "抢夺时替换光标样式",
        "en": "Replace cursor shape when hijacking",
    },
    "settings_cursor_hijack_cursor_note": {
        "zh": "关闭后劫持期间保持正常箭头（不改系统光标）",
        "en": "When off, keep the normal arrow while hijacked (no system cursor change)",
    },
    "settings_startup_section": {"zh": "启动", "en": "Startup"},
    "settings_autostart": {"zh": "开机自启动", "en": "Launch at startup"},
    "settings_autostart_note": {
        "zh": "开机后自动启动桌宠",
        "en": "Start the pet automatically after startup",
    },
    # —— tabbar：打开设置 ——
    "btn_open_settings": {"zh": "打开设置", "en": "Open settings"},
    # —— 音乐播放 ——
    "btn_music": {"zh": "音乐", "en": "Music"},
    "tray_music": {"zh": "音乐播放", "en": "Music player"},
    "music_title": {"zh": "音乐播放", "en": "Music Player"},
    "music_empty": {
        "zh": "列表为空，点【导入音乐】添加曲目",
        "en": "List is empty, click Import to add tracks",
    },
    "music_import_files": {"zh": "导入音乐", "en": "Import"},
    "music_import_dir": {"zh": "导入文件夹", "en": "Import folder"},
    "music_open_folder": {"zh": "打开音乐目录", "en": "Open music folder"},
    "music_rescan": {"zh": "重新扫描", "en": "Rescan"},
    "music_back5": {"zh": "快退 5 秒", "en": "Back 5s"},
    "music_forward5": {"zh": "快进 5 秒", "en": "Forward 5s"},
    "music_theme_label": {"zh": "主题曲行为", "en": "Theme behavior"},
    "music_theme_loop": {"zh": "循环播放", "en": "Loop"},
    "music_theme_once": {"zh": "播完即停", "en": "Play once"},
    "music_clear": {"zh": "清空", "en": "Clear"},
    "music_play": {"zh": "播放", "en": "Play"},
    "music_pause": {"zh": "暂停", "en": "Pause"},
    "music_prev": {"zh": "上一首", "en": "Previous"},
    "music_next": {"zh": "下一首", "en": "Next"},
    "music_remove": {"zh": "移除", "en": "Remove"},
    "music_mode_order": {"zh": "顺序播放", "en": "In order"},
    "music_mode_shuffle": {"zh": "随机播放", "en": "Shuffle"},
    "music_mode_one": {"zh": "单曲循环", "en": "Repeat one"},
    "music_volume": {"zh": "音量", "en": "Volume"},
    "music_imported": {"zh": "已导入 {n} 首", "en": "Imported {n} track(s)"},
    "music_import_none": {"zh": "未找到音频文件", "en": "No audio files found"},
    "music_no_qt": {
        "zh": "缺少 QtMultimedia，无法播放音乐",
        "en": "QtMultimedia missing, cannot play music",
    },
    "music_pick_files": {"zh": "选择音乐文件", "en": "Select music files"},
    "music_pick_dir": {"zh": "选择音乐文件夹", "en": "Select music folder"},
    "music_dirs_hint": {
        "zh": "也可把音乐放进内置目录或 ~/.slugcatpet/music",
        "en": "You can also drop music into the built-in folder or ~/.slugcatpet/music",
    },
    "music_no_selection": {"zh": "未选中曲目", "en": "No track selected"},
    # —— 设置窗：声音 ——
    "settings_sound_section": {"zh": "声音", "en": "Sound"},
    "settings_mute_all": {"zh": "静音运行", "en": "Mute all audio"},
    "settings_mute_all_note": {
        "zh": "开启后屏蔽所有音效",
        "en": "When on, mute all audio",
    },
    "settings_zerog_music": {
        "zh": "零重力时播放主题曲",
        "en": "Play a theme during zero gravity",
    },
    "settings_zerog_music_note": {
        "zh": "开启后会随机选一首内置主题曲循环播放",
        "en": "When on, loop a random built-in theme",
    },
    "settings_water_music": {
        "zh": "涨水时播放主题曲",
        "en": "Play a theme during flood",
    },
    "settings_water_music_note": {
        "zh": "开启涨水后会循环播放内置主题曲",
        "en": "When on, loop a built-in theme while flooded",
    },
    "settings_passages_music": {
        "zh": "聚焦设置窗时播放氛围乐",
        "en": "Play ambient music while focused on settings",
    },
    "settings_passages_music_note": {
        "zh": "点到设置窗口时播放，移开焦点后停止",
        "en": "Plays while the settings window is focused, stops on blur",
    },
    "settings_hud_music": {
        "zh": "聚焦状态面板时播放氛围乐",
        "en": "Play ambient music while focused on the panel",
    },
    "settings_hud_music_note": {
        "zh": "点到状态面板时播放，移开焦点后停止",
        "en": "Plays while the status panel is focused, stops on blur",
    },
    # —— main：单实例 ——
    "already_running": {
        "zh": "蛞蝓猫桌宠已在运行",
        "en": "Slugcat Pet is already running",
    },
    # —— main：托盘菜单 / 通知 ——
    "tray_settings": {"zh": "设置", "en": "Settings"},
    "tray_hud": {
        "zh": "显示/隐藏状态面板 (Ctrl+Alt+H)",
        "en": "Show/Hide status panel (Ctrl+Alt+H)",
    },
    "tray_quit": {"zh": "退出程序", "en": "Quit program"},
    "tray_abort": {
        "zh": "中止光标劫持 (Ctrl+Alt+Q)",
        "en": "Abort cursor hijack (Ctrl+Alt+Q)",
    },
    "tray_started": {
        "zh": "已启动。被超度的光标按 Ctrl+Alt+Q 解除；Ctrl+Alt+X 退出程序。",
        "en": "Launched. Press Ctrl+Alt+Q to release a salvaged cursor; Ctrl+Alt+X to quit the program.",
    },
    # —— gameassets：导入报错（显示在 setup 面板） ——
    "err_atlas_missing": {
        "zh": "未找到游戏图集文件：{res}\n请选择 RainWorld 文件夹（其中应有 RainWorld.exe 和 RainWorld_Data 文件夹）。",
        "en": "Game atlas file not found: {res}\nPlease select the RainWorld folder (which should contain RainWorld.exe and the RainWorld_Data folder).",
    },
    "err_no_unitypy": {
        "zh": "缺少依赖 UnityPy，请先运行：pip install UnityPy",
        "en": "Missing dependency UnityPy, please run first: pip install UnityPy",
    },
    "err_base_fail": {
        "zh": "基础图集 rainWorld 提取失败，游戏文件可能损坏或版本不兼容。",
        "en": "Base atlas rainWorld extraction failed; game files may be corrupted or the version incompatible.",
    },
    "err_msc_missing": {
        "zh": "未找到 rainworldmsc 图集——Saint 属于 Downpour(More Slugcats) DLC，需要在 Steam 拥有该 DLC 才能导入。",
        "en": "rainworldmsc atlas not found — Saint belongs to the Downpour (More Slugcats) DLC; you need to own that DLC on Steam to import.",
    },
    "err_ui_fail": {
        "zh": "UI 图集 uiSprites 提取失败，游戏文件可能损坏或版本不兼容。",
        "en": "UI atlas uiSprites extraction failed; game files may be corrupted or the version incompatible.",
    },
    "err_uimsc_missing": {
        "zh": "未找到 uispritesmsc 图集——业力图标需 Downpour(More Slugcats) DLC。",
        "en": "uispritesmsc atlas not found — the karma icons need the Downpour (More Slugcats) DLC.",
    },
    "err_no_install": {
        "zh": "未能自动定位 Rain World 安装。\n请点下方按钮，手动选择你的 RainWorld 文件夹。",
        "en": "Could not automatically locate the Rain World installation.\nPlease click the button below to manually select your RainWorld folder.",
    },
}


def t(key: str, **kw) -> str:
    e = _STR.get(key)
    if e is None:
        return key
    s = e.get(LANG) or e.get("zh") or key
    return s.format(**kw) if kw else s
