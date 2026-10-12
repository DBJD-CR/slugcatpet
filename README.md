# Windows 桌面宠物：让 Rain World 的蛞蝓猫住在你的屏幕上

> exe 见 release 压缩包。

RainWorld 里控制蛞蝓猫各个 bodychunk 拼接和行动的质点系统是 C# 写的，反编译后参考常量和主要函数就能足够相似的模拟。但粒子 shader 等效果难以复现原游戏渲染，又为了提升桌宠性能，所以我做了大量简化。

## 运行要求

- Windows 10 / 11
- Python 3.11+
- 初始化时需要已下载 Rain World，需要包含 Downpour (More Slugcats) DLC。

## 安装与运行

推荐使用 [uv](https://docs.astral.sh/uv/) 安装依赖，速度远快于 pip（pip 首次安装非常慢）。若访问官方源较慢，推荐使用阿里云镜像（清华源可能缺少本项目所需的包，阿里云更齐全且 uv 下网速很快）：

```powershell
# 推荐：uv + 阿里云镜像
uv sync --default-index https://mirrors.aliyun.com/pypi/simple/

.venv\Scripts\Activate.ps1
python run_slugcatpet.py
```

备选：pip（首次安装较慢）

```powershell
pip install PySide6 UnityPy numpy Pillow
python run_slugcatpet.py
```

首次启动会引导你选择本机的 Rain World 安装目录，从中一次性提取精灵图集到 `~/.slugcatpet/assets`，仅存放在你本机、仅供本程序使用。

## 素材与版权说明

- 本仓库不包含任何 Rain World 游戏素材。全部游戏图像在你本机、从你自己的正版安装中提取。
- 此项目为粉丝项目，Rain World 及相关名称、美术均归其权利人所有。
- 本仓库代码以 MIT 许可发布（见 [LICENSE](LICENSE)）；该许可仅覆盖本仓库代码，不授予任何游戏素材相关权利。

---

A Windows desktop pet that puts Rain World's slugcats on your screen. The .exe is in the release zip.

The mass-point system in Rain World that controls the connection and movement of the slugcat's various body chunks is written in C#. After decompiling it, I referred to its constants and main functions, which was enough to create a sufficiently similar simulation. However, effects like particle shaders are hard to replicate to match the original game's rendering, and to boost the desktop pet's performance, I made extensive simplifications.

## Requirements

- Windows 10 / 11
- Python 3.11+
- Rain World installed, including the Downpour (More Slugcats) DLC.

## Install and run

[uv](https://docs.astral.sh/uv/) is recommended for installing dependencies, far faster than pip (a first-time pip install is painfully slow). If the official index is slow, the Aliyun mirror is recommended (the Tsinghua mirror may be missing packages this project needs, while Aliyun is complete and fast under uv):

```powershell
# Recommended: uv + Aliyun mirror
uv sync --default-index https://mirrors.aliyun.com/pypi/simple/

.venv\Scripts\Activate.ps1
python run_slugcatpet.py
```

Alternative: pip (slow on first install)

```powershell
pip install PySide6 UnityPy numpy Pillow
python run_slugcatpet.py
```

On first launch you pick your Rain World install folder. Sprite atlases are extracted once to `~/.slugcatpet/assets`, kept on your machine and used only by this program.

## Assets and copyright

- This repository contains no Rain World assets. All game images are extracted on your machine from your own copy.
- This is a fan project. Rain World and all related names and artwork belong to their respective owners.
- The code is released under the MIT license (see [LICENSE](LICENSE)). It covers this repository's code only and grants no rights to any game assets.
