"""
难度测试: 让一个"会规划"的电脑玩家玩很多局, 看看各个结局占多少。
改了游戏里的数字以后, 跑一下这个, 看难度有没有变得太离谱。
运行方法: 在游戏文件夹 (wasteland-trail) 里输入 python3 tests/balance.py
想多玩几局: python3 tests/balance.py 5000
换个难度 (1 简单, 2 普通, 3 困难, 不写就是普通): python3 tests/balance.py 1000 3
让第一次玩的新手来玩: python3 tests/balance.py 1000 2 新手

难度的目标 (用户 2026-10-04 定的): 简单 —— 第一次玩的人基本都能到; 普通 —— 第一次玩的人大概一半能到, 玩熟了的人大多能到;
困难 —— 玩熟了的人也常常失败。「会规划的玩家」(planner) 算玩熟了的人, 「新手」(novice) 算第一次玩的人。
"""

import io
import os
import random
import re
import sys
import tempfile
from collections import Counter
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import wasteland_trail as w


# 会规划的玩家在据点遇到愿意加入的人时带不带上 (想测"一个人走完全程"就改成 False)
RECRUIT = True
# 选哪个难度 (见游戏里的 DIFFICULTIES)
DIFFICULTY = 2
# 坐木筏过急流时, 会规划的玩家选错水道的机会 (真人要在几秒内选, 难免手忙脚乱)
RAPID_MISTAKES = 0.2
# 打猎时, 会规划的玩家每一帧最多按几下方向键 (按住不放, 键盘大约每秒重复 20 下), 准星对上了动物有多大机会马上开枪
HUNT_MOVES = 2
HUNT_TRIGGER = 0.5
HUNT_HASTE = 0.05   # 准星还差几格就急着开枪 (多半打空) 的机会, 每一帧
# 新手: 过急流时选错水道的机会、打猎时的手 (每帧按几下方向键, 对上了马上开枪的机会, 急着开枪的机会)
NOVICE_RAPID_MISTAKES = 0.4
NOVICE_HUNT = (1, 0.3, 0.15)


def planner(game_box, screen, month):
    """会规划的玩家: 多买水 (夏天出发再多买一半), 每人一套冬衣, 留一支排辐剂备用, 到据点就补货、带上愿意加入的人,
    缺吃的就打猎, 有人生病或受伤就用药, 辐射严重了就打排辐剂, 酸雨和辐射风暴天躲在车里休息。
    留着坐渡船的钱; 过河时水浅就开过去, 有渡船就坐渡船, 水只深一点就等两天看水退不退, 不然就浮过去。
    到了达尔斯, 钱够就交过路费走巴洛路, 不够就坐木筏, 急流里每次都选对水道"""
    thirst = 1.5 if month >= 6 else 1   # 夏天天热, 水要多带
    plan = ["A", "1", str(month)]   # 名字、性别、出发月份 (难度在「设置」里, 见 play_one)
    menu_visits = [0]
    # 出发前要买的东西 (一个人出发), 按顺序买, 钱不够了后面的就少买
    shopping = [("1", 60), ("2", round(60 * thirst)), ("3", 70), ("4", 40), ("6", 1), ("7", 1), ("8", 1)]
    buying = []
    medicine = []   # 决定用药以后: [用哪一种 ("1" 药品, "2" 排辐剂), 给谁]
    waited = Counter()   # 在每条河边等了几天
    count = [0]

    def answer(prompt=""):
        count[0] += 1
        if count[0] > 20000:   # 一局正常几百次就玩完了, 太多说明电脑玩家卡在哪里转圈
            raise RuntimeError(f"电脑玩家卡住了, 最后一个问题: {prompt}")
        if "选哪一项" in prompt:                  # 主菜单: 第一次开新游戏, 玩完一局回来就退出
            menu_visits[0] += 1
            return "1" if menu_visits[0] == 1 else "6"
        if "确定, 开始新游戏" in prompt:          # 有旧存档也开新游戏
            return "1"
        if plan:
            return plan.pop(0)
        game = game_box[0]
        s, party = game["supplies"], game["party"]
        if prompt == "快打: ":                    # 打猎: 打出屏幕上的词
            return re.findall(r">>> (\w+) <<<", screen.getvalue())[-1]
        if "要进去买卖东西" in prompt:              # 据点里把冬衣、排辐剂、燃料、水、食物补到够用 (人越多要得越多)
            n = len(party)
            # 排辐剂: 手上留 1 支备用, 辐射已经比较高的人再每人 1 支
            anti_rad = 1 + sum(game["rads"].get(name, 0) >= 40 for name in party)
            medicine_want = 2 if n > 1 else 1
            shopping[:] = [(choice, want - s[item]) for choice, item, want
                           in [("7", "冬衣", n), ("6", "药品", medicine_want), ("8", "排辐剂", anti_rad), ("3", "燃料", 45),
                               ("2", "水", round((22 * n + 10) * thirst)), ("1", "食物", 28 * n + 10)]
                           if s[item] < want]
            return "1" if shopping else "2"
        if "买什么" in prompt:
            if shopping:
                buying[:] = [shopping.pop(0)]
                return buying[0][0]
            return "0"
        if "买多少" in prompt:                    # 留够前面坐渡船的钱
            most = int(prompt.split("最多")[1].split(")")[0])
            item = list(w.PRICES)[int(buying[0][0]) - 1]
            spare = w.most_affordable(game, item, max(0, game["money"] - ferry_money(game)))
            return str(min(most, spare, buying[0][1]))
        if "怎么过河" in prompt:
            place = game["visited"][-1]
            depth = float(re.findall(r"今天水深 ([\d.]+) 米", screen.getvalue())[-1])
            fare = w.RIVERS[place][3]
            if depth <= w.wade_depth(game):
                return "1"
            if fare and game["money"] >= fare:
                return "4"
            waited[place] += 1   # 水只比能开过的深一点, 就等两天看水退不退; 深得多就直接浮过去
            if waited[place] <= 2 and depth <= round(w.wade_depth(game) + w.SOAK_DEPTH, 1):
                return "3"
            return "2"
        if "走哪条路" in prompt:                  # 达尔斯: 钱够交过路费就走巴洛路, 不够就坐木筏
            return "2" if game["money"] >= w.BARLOW_TOLL else "1"
        if "怎么过这一带" in prompt:              # 辐射热点: 有人辐射已经不低了、燃料又够多开两天, 就绕过去
            most = max(game["rads"].get(name, 0) for name in party)
            fuel_ok = s["燃料"] >= w.next_supply_stop(game)[3] + 2 * w.PACES[game["pace"]][2]
            return "2" if most >= 35 and fuel_ok else "1"
        if "走大路还是走捷径" in prompt:          # 南山口: 车上坐满了 (不用去布里杰堡招人)、水也够, 就走捷径
            return "2" if len(party) >= w.MAX_PARTY and s["水"] >= 10 * len(party) else "1"
        if "往哪边划" in prompt:                  # 急流: 看清楚哪边是水道 (可人手忙脚乱时也会选错, 按 20% 算)
            lanes = re.findall(r"左边(礁石|水道)  中间(礁石|水道)  右边(礁石|水道)", screen.getvalue())[-1]
            want = "礁石" if random.random() < RAPID_MISTAKES and "礁石" in lanes else "水道"
            return str(lanes.index(want) + 1)
        if "你怎么办" in prompt:                  # 劫匪就开枪, 雷区就慢慢开过去
            return "2"
        if "先丢掉一些东西" in prompt:             # 车太重, 想上车的人坐不下: 不丢东西 (就让他留下)
            return "2"
        if "不用了" in prompt:                    # 据点里愿意跟着走的人: 带上
            return "1" if RECRUIT else "2"
        if "换  2" in prompt or "加入" in prompt or "要花 2 天" in prompt:
            return "2"
        if "用哪种药" in prompt:
            return medicine[0]
        if "给谁用" in prompt:
            return str(list(party).index(medicine[1]) + 1)
        if "你要做什么" in prompt:
            sick = [name for name in party if name in game["sick"]]
            if s["药品"] and (sick or min(party.values()) < 50):   # 先治生病受伤的人里最虚弱的
                medicine[:] = ["1", min(sick or party, key=party.get)]
                return "6"
            most_rads = max(party, key=lambda name: game["rads"].get(name, 0))
            if s["排辐剂"] and game["rads"].get(most_rads, 0) >= 50:
                medicine[:] = ["2", most_rads]
                return "6"
            if s["食物"] < 40 and s["子弹"] >= 25:
                return "4"
            if s["食物"] and s["水"] and (game["weather"] in ["酸雨", "辐射风暴"] or min(party.values()) < 35):
                return "2"
            if s["燃料"] < w.PACES[game["pace"]][2]:   # 燃料不够今天开的, 就去搜刮
                return "3"
            return "1"
        return "1"
    return answer


def hunter_bot(game_box, moves=None, trigger=None, haste=None):
    """会规划的玩家打猎: 准星一下一下地挪向最近的那只动物 (跟真人在终端里按方向键一样), 对上了就开枪 (手不总是那么快);
    肉已经多得扛不动了就回去。moves、trigger、haste 不填就用上面的 HUNT_MOVES、HUNT_TRIGGER、HUNT_HASTE (新手的手慢一些)"""
    moves = HUNT_MOVES if moves is None else moves
    trigger = HUNT_TRIGGER if trigger is None else trigger
    haste = HUNT_HASTE if haste is None else haste

    def keys(hunting):
        game = game_box[0]
        most = len(game["party"]) * w.CARRY_PER_PERSON // w.WEIGHTS["食物"]
        if sum(meat for _, meat in hunting["bag"]) >= most:
            return [("走",)]
        alive = [animal for animal in hunting["animals"] if animal["dead"] is None]
        if not alive:
            return []
        row, col = hunting["aim"]

        def middle(animal):
            top, left, height, width = w.animal_box(animal)
            return top + height // 2, left + width // 2

        target = min(alive, key=lambda animal: abs(middle(animal)[0] - row) * 2 + abs(middle(animal)[1] - col))
        top, left, height, width = w.animal_box(target)
        events = []
        for _ in range(moves):
            want_row, want_col = middle(target)
            if top <= row < top + height and left <= col < left + width:
                break
            if row != want_row:
                events.append(("下",) if row < want_row else ("上",))
                row += 1 if row < want_row else -1
            elif col != want_col:
                step = w.HUNT_STEP if col < want_col else -w.HUNT_STEP
                events.append(("右",) if step > 0 else ("左",))
                col += step
        on_target = top <= row < top + height and left <= col < left + width
        near = abs(middle(target)[1] - col) <= 6 and abs(middle(target)[0] - row) <= 2
        if on_target and random.random() < trigger or not on_target and near and random.random() < haste:
            events.append(("开枪",))
        return events
    return keys


def novice(game_box, screen, month):
    """第一次玩的新手: 不知道什么最要紧, 东西凭感觉买 (有时忘了买冬衣、排辐剂、零件), 不留坐渡船的钱;
    坏天气多半照样赶路, 有人生病了不一定马上用药, 辐射很高了才打排辐剂, 吃的快没了才去打猎 (枪法一般), 水快没了有时去搜刮;
    到了据点先补快用完的东西; 过河、路上出事、急流都凭感觉选; 据点里愿意跟着走的人都带上, 碰到要换东西的、要搭车的一半会答应"""
    rng = random.Random(month * 1000 + random.randrange(1000))   # 新手自己拿主意用的随机数 (不打乱游戏的随机数)
    plan = ["A", "1", str(month)]   # 名字、性别、出发月份 (难度在「设置」里, 见 play_one)
    menu_visits = [0]
    # 出发前买东西: 每样花掉一开始的钱的几成 (凭感觉, 每局不一样); 冬衣、排辐剂、零件一半会忘了买
    shares = {"1": rng.uniform(0.15, 0.3), "2": rng.uniform(0.1, 0.25), "3": rng.uniform(0.25, 0.45),
              "4": rng.uniform(0.05, 0.1), "6": rng.uniform(0, 0.08)}
    for choice in ["5", "7", "8"]:
        if rng.random() < 0.5:
            shares[choice] = 0.05
    shopping = list(shares)
    buying = []
    medicine = []
    budget = [None]   # 这一次进商店时有多少钱 (每样按它的几成买)
    count = [0]

    def answer(prompt=""):
        count[0] += 1
        if count[0] > 20000:
            raise RuntimeError(f"新手卡住了, 最后一个问题: {prompt}")
        if "选哪一项" in prompt:
            menu_visits[0] += 1
            return "1" if menu_visits[0] == 1 else "6"
        if "确定, 开始新游戏" in prompt:
            return "1"
        if plan:
            return plan.pop(0)
        game = game_box[0]
        s, party = game["supplies"], game["party"]
        if "要进去买卖东西" in prompt:             # 据点: 有钱的话进去, 先补快用完的 (状态栏写着够几天), 再随便买点别的
            short = [choice for choice, item in [("2", "水"), ("1", "食物"), ("3", "燃料")] if w.days_left(game, item) < 10]
            if w.fuel_short(game) and "3" in short:   # 状态栏写着「燃料不够开到下一个据点」: 先买燃料
                short.remove("3")
                short.insert(0, "3")
            shopping[:] = short + [choice for choice in ["3", "1", "2"] if choice not in short and rng.random() < 0.5]
            budget[0] = None
            return "1" if shopping and game["money"] >= 10 else "2"
        if "买什么" in prompt:
            if budget[0] is None:
                budget[0] = game["money"]
            if shopping:
                buying[:] = [shopping.pop(0)]
                return buying[0]
            return "0"
        if "买多少" in prompt:
            most = int(prompt.split("最多")[1].split(")")[0])
            item = list(w.PRICES)[int(buying[0]) - 1]
            share = shares.get(buying[0], 0.3)
            want = w.most_affordable(game, item, int(budget[0] * share))
            return str(min(most, want))
        if "卖什么" in prompt or "丢什么" in prompt:
            return "0"
        if "怎么过河" in prompt:                  # 凭感觉: 多半直接开或者浮过去, 有时坐渡船、等一天
            return rng.choice(["1", "1", "2", "2", "3", "4"])
        if "走哪条路" in prompt or "怎么过这一带" in prompt or "走大路还是走捷径" in prompt:   # 最后一段路、辐射热点、捷径: 凭感觉选
            return rng.choice(["1", "2"])
        if "往哪边划" in prompt:
            lanes = re.findall(r"左边(礁石|水道)  中间(礁石|水道)  右边(礁石|水道)", screen.getvalue())[-1]
            want = "礁石" if rng.random() < NOVICE_RAPID_MISTAKES and "礁石" in lanes else "水道"
            return str(lanes.index(want) + 1)
        if "你怎么办" in prompt or "冲过去" in prompt:   # 劫匪、雷区、烂路: 凭感觉选
            return rng.choice(["1", "2"])
        if "先丢掉一些东西" in prompt:
            return "2"
        if "不用了" in prompt:                    # 据点里愿意跟着走的人: 带上
            return "1"
        if "换  2" in prompt or "加入" in prompt or "要花 2 天" in prompt:
            return rng.choice(["1", "2"])
        if "用哪种药" in prompt:
            return medicine[0]
        if "给谁用" in prompt:
            return str(list(party).index(medicine[1]) + 1)
        if "休息几天" in prompt:
            return "2"
        if "你要做什么" in prompt:
            weakest = min(party, key=party.get)
            sick = [name for name in party if name in game["sick"]]
            if s["药品"] and (party[weakest] < 30 or sick and rng.random() < 0.3):   # 病得很重了才想起用药, 有时生病了马上用
                medicine[:] = ["1", weakest if party[weakest] < 30 else sick[0]]
                return "6"
            most_rads = max(party, key=lambda name: game["rads"].get(name, 0))
            if s["排辐剂"] and game["rads"].get(most_rads, 0) >= 70:
                medicine[:] = ["2", most_rads]
                return "6"
            if s["食物"] < 10 and s["子弹"] >= 5:
                return "4"
            if s["燃料"] < w.PACES[game["pace"]][2] or w.days_left(game, "水") < 2 and rng.random() < 0.5:
                return "3"
            if s["食物"] and s["水"] and game["weather"] in ["酸雨", "辐射风暴"] and rng.random() < 0.3:
                return "2"
            if s["食物"] and s["水"] and party[weakest] < 20 and rng.random() < 0.5:
                return "2"
            return "1"
        return "1"
    return answer


def ferry_money(game):
    """前面还没过的河里, 坐渡船一共要多少钱"""
    total = 0
    for km, (place, _) in w.LANDMARKS.items():
        if place in w.RIVERS and km > game["distance"] and w.RIVERS[place][3]:
            total += w.RIVERS[place][3]
    return total


def month_for(seed):
    """每一局按顺序轮流选 3 月到 7 月出发"""
    months = range(w.FIRST_MONTH, w.LAST_MONTH + 1)
    return months[seed % len(months)]


def play_one(seed, month=None, who="planner"):
    """让会规划的玩家 (who="novice" 就是新手) 玩一局, 返回屏幕上打印的所有文字。month 不填就按 seed 轮流选出发月份"""
    month = month or month_for(seed)
    random.seed(seed)
    game_box = []
    screen = io.StringIO()
    real_new_game = w.new_game

    def new_game():
        game = real_new_game()
        game_box.append(game)
        return game

    with mock.patch.object(w, "new_game", new_game), \
            mock.patch.dict(w.settings, {"difficulty": DIFFICULTY, "unit": "公里"}), \
            mock.patch("builtins.input", (novice if who == "novice" else planner)(game_box, screen, month)), \
            mock.patch.multiple(w, can_aim=lambda: True,
                                hunt_keys=hunter_bot(game_box, *NOVICE_HUNT) if who == "novice" else hunter_bot(game_box),
                                load_settings=lambda: None, save_settings=lambda: None), \
            redirect_stdout(screen):
        w.main()
    return screen.getvalue()


def main(rounds, who="planner"):
    endings = Counter()
    days = []
    games_by_month = Counter()     # 每个出发月份玩了几局
    arrived_by_month = Counter()   # 其中到达了几局
    # 存档、最高分榜、成就放到临时文件夹, 不碰玩家真正的存档、最高分和成就
    with tempfile.TemporaryDirectory() as tmp, \
            mock.patch.object(w, "SAVE_FILE", os.path.join(tmp, "savegame.json")), \
            mock.patch.object(w, "HIGH_SCORE_FILE", os.path.join(tmp, "highscores.json")), \
            mock.patch.object(w, "ACHIEVEMENT_FILE", os.path.join(tmp, "achievements.json")), \
            mock.patch.object(w, "SETTINGS_FILE", os.path.join(tmp, "settings.json")):
        for seed in range(rounds):
            text = play_one(seed, who=who)
            endings[re.findall(r"【(.*?结局.*?)】", text)[-1]] += 1
            month = month_for(seed)
            games_by_month[month] += 1
            used = re.search(r"一共用了 (\d+) 天", text)
            if used:
                days.append(int(used[1]))
                arrived_by_month[month] += 1

    print(f"{'新手' if who == 'novice' else '会规划的玩家'}玩了 {rounds} 局 ({w.DIFFICULTIES[DIFFICULTY][0]}难度):")
    for ending, count in endings.most_common():
        print(f"  {ending}: {count * 100 / rounds:.1f}%")
    if days:
        print(f"  到达的平均用了 {sum(days) / len(days):.1f} 天, 最多 {max(days)} 天")
    print("  按出发月份, 到达的比例:")
    for month in sorted(games_by_month):
        print(f"    {month} 月: {arrived_by_month[month] * 100 / games_by_month[month]:.1f}%")


if __name__ == "__main__":
    if len(sys.argv) > 2:
        DIFFICULTY = int(sys.argv[2])
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 1000, "novice" if "新手" in sys.argv[3:] else "planner")
