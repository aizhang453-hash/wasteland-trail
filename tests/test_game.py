"""
废土之旅的自动测试。
运行方法: 在 game 文件夹里输入 python3 -m unittest
"""

import io
import os
import random
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

# 让测试能找到上一层文件夹里的 wasteland_trail.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import wasteland_trail as w


class StopGame(Exception):
    """模拟玩家输入太多次还没玩完, 就强制停下"""


def random_player(rng):
    """一个乱按的玩家: 大部分时候随便选, 偶尔故意输错"""
    count = [0]

    def answer(prompt=""):
        count[0] += 1
        if count[0] > 3000:
            raise StopGame
        if "买多少" in prompt:
            most = int(prompt.split("最多")[1].split(")")[0])
            return str(rng.randint(0, most // 3))
        if "买什么" in prompt:
            return rng.choice(["0", "0", "1", "2", "3", "4", "5", "6"])
        if "你要做什么" in prompt:      # 一半时候往前开, 这样才能走得远、遇到更多事
            return rng.choice(["1", "1", "1", "1", "1", "1", "2", "3", "4", "5", "6", "7", "8"])
        if "退出游戏" in prompt:        # 存档后大多数时候接着玩
            return "2" if rng.random() < 0.05 else "1"
        if rng.random() < 0.1:
            return rng.choice(["", "abc", "²", "99"])
        return str(rng.randint(1, 8))
    return answer


def new_test_game():
    """一局已经准备好的游戏: 4 个满血队员, 物资充足, 晴天"""
    game = w.new_game()
    game["party"] = {"A": 100, "B": 100, "C": 100, "D": 100}
    for item in game["supplies"]:
        game["supplies"][item] = 100
    return game


class GameTest(unittest.TestCase):
    def setUp(self):
        # 测试时把存档放到临时文件夹, 不碰玩家真正的存档
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patcher = mock.patch.object(w, "SAVE_FILE", os.path.join(tmp.name, "savegame.json"))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_random_play_never_crashes(self):
        """乱玩 300 局, 不管怎么按都不能报错"""
        for seed in range(300):
            with self.subTest(seed=seed):
                random.seed(seed)
                with mock.patch("builtins.input", random_player(random.Random(seed))), \
                        redirect_stdout(io.StringIO()):
                    try:
                        w.main()
                    except StopGame:
                        pass

    def test_planner_plays_whole_game(self):
        """会规划的玩家能走完全程, 路上的据点、事件都会遇到, 也不能报错"""
        from tests.balance import play_one
        arrived = 0
        for seed in range(100):
            with self.subTest(seed=seed):
                arrived += "一共用了" in play_one(seed)
        self.assertGreater(arrived, 50)

    def test_ask_number_rejects_bad_input(self):
        answers = iter(["²", "abc", "", "9", "３"])
        with mock.patch("builtins.input", lambda p="": next(answers)), redirect_stdout(io.StringIO()):
            self.assertEqual(w.ask_number("? ", 1, 6), 3)   # 全角的 ３ 也算数

    def test_eat_what_is_left(self):
        """食物不够时有多少吃多少, 缺得越多掉血越多"""
        game = new_test_game()
        game["supplies"]["食物"] = 5        # 4 个人普通口粮要 8 份, 缺 3 份
        with redirect_stdout(io.StringIO()):
            w.pass_day(game)
        self.assertEqual(game["supplies"]["食物"], 0)
        # 普通口粮 +1, 缺 3/8 的食物 -4, 满血 100 封顶后是 97
        self.assertEqual(list(game["party"].values()), [97, 97, 97, 97])

    def test_medicine_not_wasted_on_healthy_party(self):
        game = new_test_game()
        with redirect_stdout(io.StringIO()):
            w.use_medicine(game)
        self.assertEqual(game["supplies"]["药品"], 100)

    def test_last_stretch_only_counts_what_is_left(self):
        game = new_test_game()
        game["distance"] = w.TOTAL_DISTANCE - 10
        game["visited"] = [name for name in w.OUTPOSTS.values()]
        screen = io.StringIO()
        with mock.patch("builtins.input", lambda p="": "1"), redirect_stdout(screen):
            w.travel(game)
        self.assertEqual(game["distance"], w.TOTAL_DISTANCE)
        self.assertIn("开了 10 公里", screen.getvalue())

    def test_hunting(self):
        """打得又快又对: 拿全部的肉; 慢一点: 一半; 太慢或打错: 没有"""
        for typed, seconds, should_get_food in [("bang", 1.0, True), ("bang", 4.0, True),
                                                ("bang", 8.0, False), ("bnag", 1.0, False)]:
            with self.subTest(typed=typed, seconds=seconds):
                game = new_test_game()
                with mock.patch.object(w, "HUNT_WORDS", ["bang"]), \
                        mock.patch.object(w.time, "time", side_effect=[0, seconds]), \
                        mock.patch("builtins.input", lambda p="": typed), \
                        redirect_stdout(io.StringIO()):
                    w.hunt(game)
                eaten = 8   # 打猎花一天, 4 个人吃 8 份
                got_food = game["supplies"]["食物"] + eaten > 100
                self.assertEqual(got_food, should_get_food)
                self.assertEqual(game["supplies"]["子弹"], 95)

    def test_gender_words(self):
        game = w.new_game()
        game["gender"] = "女"
        self.assertEqual(w.pick(game, "大哥", "大姐"), "大姐")
        game["gender"] = "男"
        self.assertEqual(w.pick(game, "大哥", "大姐"), "大哥")

    def test_save_and_load(self):
        game = new_test_game()
        game["day"] = 12
        game["visited"] = ["锈铁镇"]
        game["dead"] = ["E"]
        with redirect_stdout(io.StringIO()):
            w.save_game(game)
            self.assertEqual(w.load_game(), game)

    def test_broken_save_starts_new_game(self):
        with open(w.SAVE_FILE, "w") as f:
            f.write("这不是存档")
        with redirect_stdout(io.StringIO()):
            self.assertIsNone(w.load_game())

    def test_save_is_deleted_when_game_ends(self):
        """读档后队伍饿死, 游戏结束, 存档也要被删掉"""
        game = new_test_game()
        game["party"] = {"A": 1}
        game["supplies"]["食物"] = 0
        game["supplies"]["水"] = 0
        with redirect_stdout(io.StringIO()):
            w.save_game(game)
        answers = iter(["1", "2"])   # 继续上次的游戏, 然后休息一天
        with mock.patch("builtins.input", lambda p="": next(answers)), redirect_stdout(io.StringIO()):
            w.main()
        self.assertFalse(os.path.exists(w.SAVE_FILE))


if __name__ == "__main__":
    unittest.main()
