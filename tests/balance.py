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


def planner(game_box, screen):
    """会规划的玩家: 多买水, 缺吃的就打猎, 有人受伤就用药, 酸雨天休息"""
    plan = ["A", "1", "2",   # 名字、性别、用默认队员名
            "1", "150", "2", "140", "3", "60", "4", "60", "5", "1", "6", "2", "0"]   # 出发前买东西
    shopping = []

    def answer(prompt=""):
        if plan:
            return plan.pop(0)
        game = game_box[0]
        s, party = game["supplies"], game["party"]
        if prompt == "> ":                       # 打猎: 打出屏幕上的词
            return re.findall(r">>> (\w+) <<<", screen.getvalue())[-1]
        if "要进去买东西" in prompt:              # 据点里先买水, 再买食物
            shopping[:] = ["2", "1", "0"]
            return "1"
        if "买什么" in prompt:
            return shopping.pop(0) if shopping else "0"
        if "买多少" in prompt:
            most = int(prompt.split("最多")[1].split(")")[0])
            return str(min(most, game["money"] // 2 + 1))
        if "你怎么办" in prompt:                  # 劫匪就开枪, 雷区就慢慢开过去
            return "2"
        if "换  2" in prompt or "加入" in prompt or "要花 2 天" in prompt:
            return "2"
        if "你要做什么" in prompt:
            if s["药品"] and min(party.values()) < 50:
                return "5"
            if s["食物"] < 40 and s["子弹"] >= 25:
                return "4"
            if s["食物"] and s["水"] and (game["weather"] == "酸雨" or min(party.values()) < 35):
                return "2"
            if s["燃料"] < 2:
                return "3"
            return "1"
        return "1"
    return answer


def play_one(seed):
    """让会规划的玩家玩一局, 返回屏幕上打印的所有文字"""
    random.seed(seed)
    game_box = []
    screen = io.StringIO()
    real_new_game = w.new_game

    def new_game():
        game = real_new_game()
        game_box.append(game)
        return game

    with mock.patch.object(w, "new_game", new_game), \
            mock.patch("builtins.input", planner(game_box, screen)), \
            redirect_stdout(screen):
        w.main()
    return screen.getvalue()


def main(rounds):
    endings = Counter()
    days = []
    # 存档放到临时文件夹, 不碰玩家真正的存档
    with tempfile.TemporaryDirectory() as tmp, \
            mock.patch.object(w, "SAVE_FILE", os.path.join(tmp, "savegame.json")):
        for seed in range(rounds):
            text = play_one(seed)
            endings[re.findall(r"【(.*?结局.*?)】", text)[-1]] += 1
            used = re.search(r"一共用了 (\d+) 天", text)
            if used:
                days.append(int(used[1]))

    print(f"会规划的玩家玩了 {rounds} 局:")
    for ending, count in endings.most_common():
        print(f"  {ending}: {count * 100 / rounds:.1f}%")
    if days:
        print(f"  到达的平均用了 {sum(days) / len(days):.1f} 天, 最多 {max(days)} 天")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 1000)
