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
        game["visited"] = [name for name, _ in w.OUTPOSTS.values()]
        screen = io.StringIO()
        with mock.patch("builtins.input", lambda p="": "1"), redirect_stdout(screen):
            w.travel(game)
        self.assertEqual(game["distance"], w.TOTAL_DISTANCE)
        self.assertIn("开了 10 公里", screen.getvalue())

    def test_distance_units(self):
        """选了英里, 路程就按英里显示; 游戏里面还是按公里算"""
        game = new_test_game()
        self.assertEqual(w.show_distance(game, 1000), "1000 公里")
        game["unit"] = "英里"
        self.assertEqual(w.show_distance(game, 1000), "621 英里")
        game["distance"] = w.TOTAL_DISTANCE - 10
        game["visited"] = [name for name, _ in w.OUTPOSTS.values()]
        screen = io.StringIO()
        with mock.patch("builtins.input", lambda p="": "1"), redirect_stdout(screen):
            w.travel(game)
        self.assertEqual(game["distance"], w.TOTAL_DISTANCE)
        self.assertIn("开了 6 英里", screen.getvalue())

    def test_places_in_order(self):
        """一路开过去, 每个地标和据点都只经过一次, 而且顺序跟真实的俄勒冈小道一样"""
        game = new_test_game()
        all_places = sorted([(km, name) for km, (name, _) in w.LANDMARKS.items()] +
                            [(km, name) for km, (name, _) in w.OUTPOSTS.items()])
        with mock.patch("builtins.input", lambda p="": "2"), redirect_stdout(io.StringIO()):
            for km in range(0, w.TOTAL_DISTANCE + 1, 50):
                game["distance"] = km
                w.check_places(game)
        self.assertEqual(game["visited"], [name for _, name in all_places])

    def test_next_place(self):
        game = new_test_game()
        self.assertEqual(w.next_place(game), ("堪萨斯河渡口", 130))
        game["distance"] = 2900
        self.assertEqual(w.next_place(game), (w.DESTINATION, w.TOTAL_DISTANCE))

    def test_start_alone(self):
        """开局只有主角一个人"""
        answers = iter(["1", "小明", "2", "0"])   # 公里、名字、女、不买东西
        game = w.new_game()
        with mock.patch("builtins.input", lambda p="": next(answers)), redirect_stdout(io.StringIO()):
            w.setup(game)
        self.assertEqual(game["party"], {"小明": 100})
        self.assertEqual(game["leader"], "小明")
        self.assertEqual(game["gender"], "女")

    def test_recruit_at_outpost(self):
        """到了据点, 愿意跟着走的人可以带上, 也可以不带; 每个据点只问一次"""
        for answer, should_join in [("1", True), ("2", False)]:
            game = new_test_game()
            game["party"] = {"小明": 100}
            game["distance"] = 510   # 卡尼堡
            game["visited"] = [name for km, (name, _) in w.LANDMARKS.items() if km < 510]
            with mock.patch("builtins.input", lambda p="", a=answer: a if "加入" in p else "2"), \
                    redirect_stdout(io.StringIO()):
                w.check_places(game)
                w.check_places(game)
            self.assertEqual("杰克" in game["party"], should_join)
            self.assertEqual(len(game["party"]), 2 if should_join else 1)

    def test_no_recruit_when_party_is_full(self):
        game = new_test_game()   # 已经 4 个人了
        screen = io.StringIO()
        with mock.patch("builtins.input", lambda p="": "1"), redirect_stdout(screen):
            w.offer_recruit(game, "卡尼堡")
            random.seed(0)
            w.stranger(game)
        self.assertEqual(len(game["party"]), w.MAX_PARTY)
        self.assertIn("坐满了", screen.getvalue())

    def test_endings_for_solo_and_lost_leader(self):
        game = new_test_game()
        game["party"] = {"小明": 80}
        game["distance"] = w.TOTAL_DISTANCE
        screen = io.StringIO()
        with redirect_stdout(screen):
            w.arrive(game)
        self.assertIn("独行结局", screen.getvalue())

        game["leader"] = "小明"
        game["party"] = {"杰克": 80, "玛莎": 70}
        game["dead"] = ["小明"]
        screen = io.StringIO()
        with redirect_stdout(screen):
            w.arrive(game)
        self.assertIn("同伴们替小明走完了这条路", screen.getvalue())
        self.assertIn("普通结局", screen.getvalue())

    def with_job(self, job):
        """一局 4 人的游戏, 其中 B 是这个职业"""
        game = new_test_game()
        game["jobs"] = {"B": job}
        return game

    def test_recruit_brings_job(self):
        game = new_test_game()
        game["party"] = {"小明": 100}
        with mock.patch("builtins.input", lambda p="": "1"), redirect_stdout(io.StringIO()):
            w.offer_recruit(game, "布里杰堡")
        self.assertEqual(game["jobs"], {"埃迪": "机械师"})

    def test_job_only_works_while_alive(self):
        game = self.with_job("医生")
        self.assertEqual(w.skilled(game, "医生"), "B")
        del game["party"]["B"]
        self.assertIsNone(w.skilled(game, "医生"))

    def test_veteran(self):
        game = self.with_job("老兵")
        with mock.patch("builtins.input", lambda p="": "2"), redirect_stdout(io.StringIO()):
            for seed in range(30):   # 打 30 次劫匪, 一次都不能有人受伤
                random.seed(seed)
                w.raiders(game)
                game["supplies"]["子弹"] = 100
        self.assertEqual(list(game["party"].values()), [100, 100, 100, 100])
        with redirect_stdout(io.StringIO()):
            w.mutant_attack(game)
        self.assertEqual(game["supplies"]["子弹"], 95)

    def test_doctor(self):
        game = self.with_job("医生")
        game["party"]["A"] = 20
        with redirect_stdout(io.StringIO()):
            w.use_medicine(game)
        self.assertEqual(game["party"]["A"], 80)

    def test_mechanic(self):
        game = self.with_job("机械师")
        with redirect_stdout(io.StringIO()):
            w.breakdown(game)
        self.assertEqual(game["supplies"]["零件"], 100)   # 没用零件
        self.assertEqual(game["day"], 1)                  # 也没耽误时间

    def test_hunter(self):
        for job, expected in [(None, 20), ("猎人", 30)]:
            game = self.with_job(job) if job else new_test_game()
            with mock.patch.object(w, "HUNT_WORDS", ["bang"]), \
                    mock.patch.object(w, "ANIMALS", {"测试兔": (20, 20)}), \
                    mock.patch.object(w.time, "time", side_effect=[0, 1.0]), \
                    mock.patch("builtins.input", lambda p="": "bang"), redirect_stdout(io.StringIO()):
                w.hunt(game)
            self.assertEqual(game["supplies"]["食物"], 100 + expected - 8)

    def test_merchant(self):
        game = self.with_job("商人")
        game["money"] = 100
        answers = iter(["1", "100", "0"])   # 买 100 份食物
        with mock.patch("builtins.input", lambda p="": next(answers)), redirect_stdout(io.StringIO()):
            w.shop(game)
        self.assertEqual(game["money"], 20)   # 打八折, 只花了 80
        self.assertEqual(w.cost_of(game, "零件", 1), 16)
        self.assertEqual(w.cost_of(game, "食物", 1), 1)   # 有零头往上算

    def test_scavenger(self):
        """有拾荒者时, 搜刮废墟不会空手而归; 没遇到野狗就一次找到两样"""
        for job, empty_allowed in [(None, True), ("拾荒者", False)]:
            game = self.with_job(job) if job else new_test_game()
            empty = 0
            for seed in range(50):
                random.seed(seed)
                screen = io.StringIO()
                with redirect_stdout(screen):
                    w.scavenge(game)
                text = screen.getvalue()
                empty += "什么有用的都没找到" in text
                if job and "变异野兽" not in text:
                    self.assertEqual(text.count("找到了"), 2)
            self.assertEqual(empty > 0, empty_allowed)

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
