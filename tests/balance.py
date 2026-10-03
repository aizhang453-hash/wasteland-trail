"""
难度测试: 让一个"会规划"的电脑玩家玩很多局, 看看各个结局占多少。
改了游戏里的数字以后, 跑一下这个, 看难度有没有变得太离谱。
运行方法: 在 game 文件夹里输入 python3 tests/balance.py
想多玩几局: python3 tests/balance.py 5000
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


def planner(game_box, screen, month):
    """会规划的玩家: 多买水 (夏天出发再多买一半), 每人一套冬衣, 留一支排辐剂备用, 到据点就补货、带上愿意加入的人,
    缺吃的就打猎, 有人生病或受伤就用药, 辐射严重了就打排辐剂, 酸雨和辐射风暴天躲在车里休息"""
    thirst = 1.5 if month >= 6 else 1   # 夏天天热, 水要多带
    plan = ["1", "A", "1", str(month)]   # 单位、名字、性别、出发月份
    menu_visits = [0]
    # 出发前要买的东西 (一个人出发), 按顺序买, 钱不够了后面的就少买
    shopping = [("1", 60), ("2", round(60 * thirst)), ("3", 70), ("4", 40), ("6", 1), ("7", 1), ("8", 1)]
    buying = []
    medicine = []   # 决定用药以后: [用哪一种 ("1" 药品, "2" 排辐剂), 给谁]
    count = [0]

    def answer(prompt=""):
        count[0] += 1
        if count[0] > 20000:   # 一局正常几百次就玩完了, 太多说明电脑玩家卡在哪里转圈
            raise RuntimeError(f"电脑玩家卡住了, 最后一个问题: {prompt}")
        if "选哪一项" in prompt:                  # 主菜单: 第一次开新游戏, 玩完一局回来就退出
            menu_visits[0] += 1
            return "1" if menu_visits[0] == 1 else "4"
        if "确定, 开始新游戏" in prompt:          # 有旧存档也开新游戏
            return "1"
        if plan:
            return plan.pop(0)
        game = game_box[0]
        s, party = game["supplies"], game["party"]
        if prompt == "快打: ":                    # 打猎: 打出屏幕上的词
            return re.findall(r">>> (\w+) <<<", screen.getvalue())[-1]
        if "要进去买东西" in prompt:              # 据点里把冬衣、排辐剂、燃料、水、食物补到够用 (人越多要得越多)
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
        if "买多少" in prompt:
            most = int(prompt.split("最多")[1].split(")")[0])
            return str(min(most, buying[0][1]))
        if "你怎么办" in prompt:                  # 劫匪就开枪, 雷区就慢慢开过去
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
                return "5"
            most_rads = max(party, key=lambda name: game["rads"].get(name, 0))
            if s["排辐剂"] and game["rads"].get(most_rads, 0) >= 50:
                medicine[:] = ["2", most_rads]
                return "5"
            if s["食物"] < 40 and s["子弹"] >= 25:
                return "4"
            if s["食物"] and s["水"] and (game["weather"] in ["酸雨", "辐射风暴"] or min(party.values()) < 35):
                return "2"
            if s["燃料"] < w.PACES[game["pace"]][2]:   # 燃料不够今天开的, 就去搜刮
                return "3"
            return "1"
        return "1"
    return answer


def month_for(seed):
    """每一局按顺序轮流选 3 月到 7 月出发"""
    months = range(w.FIRST_MONTH, w.LAST_MONTH + 1)
    return months[seed % len(months)]


def play_one(seed, month=None):
    """让会规划的玩家玩一局, 返回屏幕上打印的所有文字。month 不填就按 seed 轮流选出发月份"""
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
            mock.patch("builtins.input", planner(game_box, screen, month)), \
            redirect_stdout(screen):
        w.main()
    return screen.getvalue()


def main(rounds):
    endings = Counter()
    days = []
    games_by_month = Counter()     # 每个出发月份玩了几局
    arrived_by_month = Counter()   # 其中到达了几局
    # 存档放到临时文件夹, 不碰玩家真正的存档
    with tempfile.TemporaryDirectory() as tmp, \
            mock.patch.object(w, "SAVE_FILE", os.path.join(tmp, "savegame.json")):
        for seed in range(rounds):
            text = play_one(seed)
            endings[re.findall(r"【(.*?结局.*?)】", text)[-1]] += 1
            month = month_for(seed)
            games_by_month[month] += 1
            used = re.search(r"一共用了 (\d+) 天", text)
            if used:
                days.append(int(used[1]))
                arrived_by_month[month] += 1

    print(f"会规划的玩家玩了 {rounds} 局:")
    for ending, count in endings.most_common():
        print(f"  {ending}: {count * 100 / rounds:.1f}%")
    if days:
        print(f"  到达的平均用了 {sum(days) / len(days):.1f} 天, 最多 {max(days)} 天")
    print("  按出发月份, 到达的比例:")
    for month in sorted(games_by_month):
        print(f"    {month} 月: {arrived_by_month[month] * 100 / games_by_month[month]:.1f}%")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 1000)
