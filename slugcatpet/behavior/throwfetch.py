"""生气期捡石/投石控制器 StoneThrower；四态机 select→approach→hold→throw，update() 返回路由串。"""

from __future__ import annotations
import math

from ..world.stone import GRAVITY as STONE_GRAVITY

# 捡石/投石参数
GRAB_REACH = 18.0
REACH_GATE_K = 2.0
APPROACH_TIMEOUT = 240
MAX_FAILS = 5
ABANDON_FAILS = 3
THROW_FRAMES = 5
# 先盯着光标看满这么久（tick，40Hz → 80≈2s）才允许投石
HOLD_AIM_TICKS = 80
# 打击范围：saint→光标角度门（度）
THROW_BAND_LO = -28.0
THROW_BAND_HI = 18.0
# 盯满 2s 后仍无可乘之机，最多再等这么久（10~15s）就泄气退出
ABANDON_MIN = 400
ABANDON_MAX = 600

THROW_SPEED_FRAC = 0.06
THROW_SPEED_MIN = 30.0
THROW_RECOIL = 0.35


class StoneThrower:
    def __init__(self, win, rng, fsm):
        self.win = win
        self.body = win.body
        self.gfx = win.gfx
        self.rng = rng
        self.fsm = fsm

        self.target = None
        self.phase = "select"
        self.grab_side = "r"
        self.timer = 0
        self.fails = 0
        self.throw_dir = 0
        self.throw_t = 0
        self.abandon_at = ABANDON_MAX
        self._thrown = None

    def _chunk0(self):
        return self.body.chunk0

    def _grab_dist(self):
        s = self.target
        c0 = self._chunk0()
        d = math.hypot(c0.x - s.x, c0.y - s.y)
        hx, hy = self.body._carry_pos(self.grab_side)
        return min(d, math.hypot(hx - s.x, hy - s.y))

    def _pick_side(self):
        return "r" if self.target.x >= self._chunk0().x else "l"

    def _avail(self, s):
        """可作目标：free 态 + 地面静止 + 未判 unfetchable。"""
        return (
            s.state == "free"
            and not s.unfetchable
            and s.at_rest_on_ground(self.win._HL)
        )

    def _in_band(self, cursor):
        """光标是否在可打击范围内（横向角度门）。"""
        c0 = self._chunk0()
        horiz = abs(cursor[0] - c0.x)
        above = c0.y - cursor[1]  # y↓：>0 光标在上方
        if horiz < 1e-6:
            return False
        ang = math.degrees(math.atan2(above, horiz))
        return THROW_BAND_LO <= ang <= THROW_BAND_HI

    def _solve_vy(self, base):
        """按重力反解垂直初速，使石头水平飞行后命中光标高度。"""
        cursor = self.fsm.cursor
        if cursor is None:
            return None
        side = self.body.carry_hand or self.grab_side
        sx, sy = self.body._carry_pos(side)
        rx = sx + self.throw_dir * 10.0
        ry = sy - 4.0
        dx = abs(cursor[0] - rx)
        dy = cursor[1] - ry  # y↓：>0 光标在下方
        if dx < 1.0:
            return None
        vx = self.body.chunk0.vx * 0.2 + self.throw_dir * base
        if abs(vx) < 1e-3:
            return None
        t = dx / abs(vx)
        return dy / t - 0.5 * STONE_GRAVITY * self.body.room_gravity * t

    def update(self, still_angry) -> str:
        self.timer += 1
        m = getattr(self, "_phase_" + self.phase, None)
        if m is None:
            return "idle"
        return m(still_angry)

    def _phase_select(self, still_angry):
        if not still_angry:
            return "idle"
        stones = [s for s in self.win.stones if self._avail(s)]
        if not stones:
            return "revert_wander"
        c0 = self._chunk0()
        self.target = min(stones, key=lambda s: math.hypot(c0.x - s.x, c0.y - s.y))
        self.grab_side = self._pick_side()
        self.fails = 0
        self.timer = 0
        self.phase = "approach"
        return "running"

    def _phase_approach(self, still_angry):
        s = self.target
        if s is None or not self._avail(s):
            return "revert_wander" if still_angry else "idle"
        if not still_angry:
            return "idle"
        self.grab_side = self._pick_side()
        self.body.walk_to(s.x)
        if self._grab_dist() < self.body.arm_full_reach * REACH_GATE_K:
            self.body.reach_for(s, self.grab_side)
        if self._grab_dist() < GRAB_REACH:
            self.body.stop_walk()
            self.body.grab_stone(s, self.grab_side)
            self.phase = "hold"
            self.timer = 0
            self.abandon_at = self.rng.randint(ABANDON_MIN, ABANDON_MAX)
            return "running"
        # 久够不到 → fail，超阈 unfetchable
        if abs(self._chunk0().x - s.x) < GRAB_REACH and self.timer > APPROACH_TIMEOUT:
            self.timer = 0
            self.fails += 1
            if self.fails >= MAX_FAILS:
                s.fetch_fails += 1
                if s.fetch_fails >= ABANDON_FAILS:
                    s.unfetchable = True
                return "revert_wander" if still_angry else "idle"
        return "running"

    def _phase_hold(self, still_angry):
        if self.body.carried_stone is None:
            return "revert_wander" if still_angry else "idle"
        self.body.stop_walk()
        cursor = self.fsm.cursor
        self.gfx.look_at = cursor  # 持石手由 _apply_carry_stone 管，不抢 hand_aim
        if still_angry:
            if self.timer >= self.abandon_at:
                # 盯太久仍无可乘之机 → 泄气，不再持有攻击性
                self.fsm.anger = 0
                return "revert_wander"
            if cursor is None:
                return "running"
            self.throw_dir = 1 if cursor[0] >= self._chunk0().x else -1
            # 先盯满 2s，其后光标一进入打击范围立刻砸
            if self.timer >= HOLD_AIM_TICKS and self._in_band(cursor):
                self.phase = "throw"
                self.throw_t = 0
        else:
            self.throw_dir = 1 if self.rng.random() < 0.5 else -1
            self.phase = "throw"
            self.throw_t = 0
        return "running"

    def _phase_throw(self, still_angry):
        if self.throw_t == 0:
            base = max(THROW_SPEED_MIN, self.win._WL * THROW_SPEED_FRAC)
            vy = self._solve_vy(base)
            self._thrown = self.body.throw_stone(
                self.throw_dir, base, up=3.0, recoil=THROW_RECOIL, vy=vy
            )
            self.gfx.blink = 15
        # follow-through：手伸向投掷方向
        side = self.grab_side
        c0 = self._chunk0()
        self.gfx.hand_aim[side] = (c0.x + self.throw_dir * 30.0, c0.y)
        self.gfx.hand_aim["l" if side == "r" else "r"] = None
        if self._thrown is not None:
            self.gfx.look_at = (self._thrown.x, self._thrown.y)
        self.throw_t += 1
        if self.throw_t >= THROW_FRAMES:
            self.fsm._clear_hands()
            return "thrown"
        return "running"
