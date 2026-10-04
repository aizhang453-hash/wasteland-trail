"""
废土之旅的自动测试。
运行方法: 在游戏文件夹 (wasteland-trail) 里输入 python3 -m unittest
"""

import io
import json
import os
import random
import re
import sys
import tempfile
import time
import unittest
from collections import Counter
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
    played = [False]   # 有没有真的开始玩

    def answer(prompt=""):
        count[0] += 1
        if count[0] > 3000:
            raise StopGame
        if "选哪一项" in prompt:        # 主菜单: 还没玩过就大多开新游戏, 玩过一局回来就退出
            return "5" if played[0] else rng.choice(["1", "1", "1", "2", "3", "4"])
        if "买多少" in prompt:
            most = int(prompt.split("最多")[1].split(")")[0])
            return str(rng.randint(0, most // 3))
        if "买什么" in prompt:
            return rng.choice(["0", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"])
        if "卖多少" in prompt:
            most = int(prompt.split("最多")[1].split(")")[0])
            return str(rng.randint(0, most))
        if "丢什么" in prompt:          # 丢一两样就不丢了 (不然一直在丢东西的画面里出不来)
            return rng.choice(["0", "0", str(rng.randint(1, 8))])
        if "丢多少" in prompt:          # 丢东西大多只丢一点
            most = int(prompt.split("最多")[1].split(")")[0])
            return str(rng.randint(0, most // 4))
        if "你要做什么" in prompt:      # 一半时候往前开, 这样才能走得远、遇到更多事
            played[0] = True
            return rng.choice(["1", "1", "1", "1", "1", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13"])
        if "继续玩" in prompt:          # 存档后大多数时候接着玩
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


REAL_CAPACITY = w.CAR_CAPACITY


def real_car():
    """用真的车载重。一般的测试为了方便把车当成无限大 (见 setUp), 测重量和完整玩游戏的测试要用真的"""
    return mock.patch.object(w, "CAR_CAPACITY", REAL_CAPACITY)


def no_new_diseases():
    """过一天时不让人突然病倒。要算准每个人剩多少健康的测试用它, 不然偶尔有人随机生病, 测试就时好时坏"""
    return mock.patch.multiple(w, catch_diseases=lambda *args: None, DIRTY_WATER_CHANCE=0)


class GameTest(unittest.TestCase):
    def setUp(self):
        # 测试时用整行读的方式输入数字 (测试替玩家"打字"时用的是假的 input)
        patcher = mock.patch.object(w, "can_read_keys", lambda: False)
        patcher.start()
        self.addCleanup(patcher.stop)
        # 测试时把存档放到临时文件夹, 不碰玩家真正的存档
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patcher = mock.patch.object(w, "SAVE_FILE", os.path.join(tmp.name, "savegame.json"))
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(w, "HIGH_SCORE_FILE", os.path.join(tmp.name, "highscores.json"))
        patcher.start()
        self.addCleanup(patcher.stop)
        # 测试队伍的物资给得很足 (每样 100 个, 好几吨), 一般的测试就把车当成无限大
        patcher = mock.patch.object(w, "CAR_CAPACITY", 10 ** 12)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_random_play_never_crashes(self):
        """乱玩 300 局, 不管怎么按都不能报错"""
        for seed in range(300):
            with self.subTest(seed=seed):
                random.seed(seed)
                with real_car(), mock.patch("builtins.input", random_player(random.Random(seed))), \
                        redirect_stdout(io.StringIO()):
                    try:
                        w.main()
                    except StopGame:
                        pass

    def test_novice_plays_whole_game(self):
        """难度测试里的「新手」也能玩完一局, 不会卡在哪个问题上转圈, 有到达的也有没到的"""
        from tests.balance import play_one
        results = []
        with real_car():
            for seed in range(40):
                with self.subTest(seed=seed):
                    results.append("一共用了" in play_one(seed, who="novice"))
        self.assertTrue(any(results) and not all(results))

    def test_planner_plays_whole_game(self):
        """会规划的玩家能走完全程, 路上的据点、事件都会遇到, 也不能报错"""
        from tests.balance import play_one
        arrived = 0
        with real_car():
            for seed in range(100):
                with self.subTest(seed=seed):
                    arrived += "一共用了" in play_one(seed)
        self.assertGreater(arrived, 50)

    def test_ask_number_rejects_bad_input(self):
        answers = iter(["²", "abc", "", "9", "３"])
        with mock.patch("builtins.input", lambda p="": next(answers)), redirect_stdout(io.StringIO()):
            self.assertEqual(w.ask_number("? ", 1, 6), 3)   # 全角的 ３ 也算数

    def fake_keyboard(self, keys):
        """假装玩家在终端里一个键一个键地按 keys 里的键"""
        return mock.patch.multiple(w, read_keys=lambda: next(keys),
                                   start_reading_keys=lambda: None, stop_reading_keys=lambda old: None)

    def test_ask_number_ignores_other_keys(self):
        """在终端里选数字: 空格、字母、超出范围的数字、没输数字就按回车, 都不会有任何反应"""
        keys = iter([" ", "\r", "a", "3", "\r", "1", "\x7f", "2", "\r"])   # 范围是 1~2
        screen = io.StringIO()
        with mock.patch.object(w, "can_read_keys", lambda: True), \
                self.fake_keyboard(keys), redirect_stdout(screen):
            self.assertEqual(w.ask_number("选哪个? ", 1, 2), 2)
        self.assertEqual(screen.getvalue(), "选哪个? 1\b \b2\n")

    def test_ask_number_two_digits(self):
        """菜单有 10 项时, 能输 10; 不能输 11, 也不能在 0 后面接着打"""
        keys = iter(["1", "1", "0", "\r"])
        with mock.patch.object(w, "can_read_keys", lambda: True), \
                self.fake_keyboard(keys), redirect_stdout(io.StringIO()):
            self.assertEqual(w.ask_number("? ", 1, 10), 10)
        keys = iter(["0", "5", "\r"])
        with mock.patch.object(w, "can_read_keys", lambda: True), \
                self.fake_keyboard(keys), redirect_stdout(io.StringIO()):
            self.assertEqual(w.ask_number("? ", 0, 6), 0)

    def test_eat_what_is_left(self):
        """食物不够时有多少吃多少, 缺得越多掉血越多"""
        game = new_test_game()
        game["supplies"]["食物"] = 5        # 4 个人普通口粮要 8 份, 缺 3 份
        with no_new_diseases(), redirect_stdout(io.StringIO()):
            w.pass_day(game)
        self.assertEqual(game["supplies"]["食物"], 0)
        # 普通口粮 +1, 缺 3/8 的食物 -4, 满血 100 封顶后是 97
        self.assertEqual(list(game["party"].values()), [97, 97, 97, 97])

    def test_medicine_not_wasted_on_healthy_party(self):
        game = new_test_game()
        with redirect_stdout(io.StringIO()):
            w.use_medicine(game, "A")   # A 没病没伤
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
        """一路开过去, 每个地标、据点和辐射热点都只经过一次, 而且顺序跟真实的俄勒冈小道一样"""
        game = new_test_game()
        all_places = sorted([(km, name) for km, (name, _) in w.LANDMARKS.items()] +
                            [(km, name) for km, (name, _) in w.OUTPOSTS.items()] +
                            [(spot[0], spot[2]) for spot in w.HOTSPOTS])
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
        answers = iter(["2", "1", "小明", "2", "6", "0"])   # 普通难度、公里、名字、女、6 月出发、不买东西
        game = w.new_game()
        with mock.patch("builtins.input", lambda p="": next(answers)), redirect_stdout(io.StringIO()):
            w.setup(game)
        self.assertEqual(game["party"], {"小明": 100})
        self.assertEqual(game["leader"], "小明")
        self.assertEqual(game["gender"], "女")
        self.assertEqual(game["start_month"], 6)
        self.assertEqual(w.date_text(game), "6月1日")

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
            w.use_medicine(game, "A")
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

    def test_prices_rise_to_the_west(self):
        """越往西越贵: 卡尼堡是独立城的 115%, 达尔斯 190%; 有零头往上算; 商人再打八折; 钱够买几个也跟着算"""
        game = new_test_game()
        self.assertEqual(w.cost_of(game, "食物", 10), 10)   # 出发的独立城: 原价
        game["here"] = "卡尼堡"
        self.assertEqual(w.cost_of(game, "食物", 10), 12)   # 11.5 块, 零头往上算
        self.assertEqual(w.unit_price(game, "燃料"), "4.6")
        game["money"] = 46
        self.assertEqual(w.most_affordable(game, "燃料"), 10)
        game["here"] = "达尔斯"
        self.assertEqual(w.cost_of(game, "零件", 1), 38)
        merchant = self.with_job("商人")
        merchant["here"] = "达尔斯"
        self.assertEqual(w.cost_of(merchant, "零件", 1), 31)   # 38 x 0.8 = 30.4
        game["here"] = "灰洞"   # 不是据点 (在路上碰到的人换东西不算这个), 按原价
        self.assertEqual(w.price_level(game), 100)

        game = new_test_game()
        game["here"], game["money"] = "拉勒米堡", 100
        answers = iter(["1", "10", "0"])   # 买 10 份食物
        with mock.patch("builtins.input", lambda p="": next(answers)), redirect_stdout(io.StringIO()) as screen:
            w.shop(game, can_sell=True)
        self.assertEqual(game["money"], 87)
        self.assertIn("东西都比那里贵 30%", screen.getvalue())
        self.assertIn("1. 食物  1.3 块一份", screen.getvalue())

    def test_no_profit_from_buying_east_selling_west(self):
        """卖东西不跟着越往西越贵: 不管在哪儿买、有没有商人帮着讲价, 买了再卖都会亏"""
        for place in [w.START_PLACE] + list(w.OUTPOST_PRICES):
            for job in [None, "商人"]:
                game = self.with_job(job) if job else new_test_game()
                game["here"] = place
                for item in w.PRICES:
                    with self.subTest(place=place, job=job, item=item):
                        self.assertLess(w.sale_price(self.with_job("商人"), item, 10), w.cost_of(game, item, 10))

    def test_sell_at_outpost(self):
        """在据点能卖东西, 只给一半的价钱; 有商人能卖到六成。出发前的营地不能卖"""
        game = new_test_game()
        game["money"] = 0
        answers = iter(["9", "4", "50", "9", "5", "1", "0"])   # 卖 50 发子弹, 再卖 1 个零件, 离开
        screen = io.StringIO()
        with mock.patch("builtins.input", lambda p="": next(answers)), redirect_stdout(screen):
            w.shop(game, can_sell=True)
        self.assertEqual(game["supplies"]["子弹"], 50)
        self.assertEqual(game["supplies"]["零件"], 99)
        self.assertEqual(game["money"], 25 + 10)   # 子弹 1 块一发卖一半 (25), 零件 20 块卖 10
        self.assertIn("拿到 25 块钱", screen.getvalue())

        merchant = self.with_job("商人")
        self.assertEqual(w.sale_price(merchant, "零件", 1), 12)
        self.assertEqual(w.sale_price(merchant, "食物", 5), 3)   # 零头不算
        # 有商人时买 1 个零件 16 块, 卖掉只能拿回 12 块, 不能低买高卖赚钱
        self.assertLess(w.sale_price(merchant, "零件", 1), w.cost_of(merchant, "零件", 1))

        game = new_test_game()   # 出发前的营地: 没有「卖东西」, 选 9 不算数
        answers = iter(["9", "0"])
        screen = io.StringIO()
        with mock.patch("builtins.input", lambda p="": next(answers)), redirect_stdout(screen):
            w.shop(game)
        self.assertNotIn("卖东西", screen.getvalue())
        self.assertIn("请输入 0 到 8 之间的数字", screen.getvalue())

    def test_scavenger(self):
        """有拾荒者时, 搜刮废墟不会空手而归; 没遇到野狗就一次找到两样"""
        for job, empty_allowed in [(None, True), ("拾荒者", False)]:
            empty = 0
            for seed in range(50):
                game = self.with_job(job) if job else new_test_game()   # 每次都是一局新游戏, 大家都满血
                random.seed(seed)
                screen = io.StringIO()
                with redirect_stdout(screen):
                    w.scavenge(game)
                text = screen.getvalue()
                empty += "什么有用的都没找到" in text
                if job and "变异野兽" not in text:
                    self.assertEqual(text.count("找到了"), 2)
            self.assertEqual(empty > 0, empty_allowed)

    def test_show_party(self):
        """查看队伍: 能看到每个人、主角、职业和特长、物资能撑几天, 而且不花时间"""
        game = new_test_game()
        game["leader"] = "A"
        game["jobs"] = {"B": "医生"}
        game["dead"] = ["E"]
        game["supplies"]["食物"] = 120   # 4 个人普通口粮每天 8 份 -> 15 天
        game["supplies"]["燃料"] = 30    # 中速每天 2 份 -> 15 天, 每天 105 公里
        screen = io.StringIO()
        with redirect_stdout(screen):
            w.show_party(game)
        text = screen.getvalue()
        for words in ["A (主角)", "B (医生)", w.SKILLS["医生"], "路上失去的人: E",
                      "还够吃 15 天", "还够开 15 天, 大约 1575 公里"]:
            self.assertIn(words, text)
        self.assertEqual(game["day"], 1)

    def test_diary(self):
        """旅行日记会记下出发、经过的地方、谁加入了、谁去世了, 而且带着天数和路程"""
        answers = iter(["2", "1", "小明", "1", "5", "0"])   # 普通难度、公里、名字、男、5 月出发、不买东西
        game = w.new_game()
        with mock.patch("builtins.input", lambda p="": next(answers)), redirect_stdout(io.StringIO()):
            w.setup(game)
        game["distance"] = 510   # 一路开到卡尼堡 (河都绑上油桶浮过去), 带上杰克, 不买东西
        with mock.patch("builtins.input", lambda p="": "1" if "加入" in p else "2"), \
                mock.patch.object(w, "FLOAT_RISK", 0), redirect_stdout(io.StringIO()):
            w.check_places(game)
            w.hurt(game, "杰克", 100)
        diary = "\n".join(game["diary"])
        for words in ["小明被赶出了独立城地下的避难所", "把车浮过了堪萨斯河", "把车浮过了大蓝河", "到了卡尼堡",
                      "老兵杰克在卡尼堡加入了队伍", "杰克 去世了", "5月1日 (第 1 天), 已走 510 公里"]:
            self.assertIn(words, diary)
        screen = io.StringIO()
        with redirect_stdout(screen):
            w.show_diary(game)
        self.assertIn("到了卡尼堡", screen.getvalue())

    def test_recruit_with_same_name_as_leader(self):
        """主角也叫杰克时, 卡尼堡的杰克还是能加入 (改名叫杰克2)"""
        game = new_test_game()
        game["party"] = {"杰克": 100}
        with mock.patch("builtins.input", lambda p="": "1"), redirect_stdout(io.StringIO()):
            w.offer_recruit(game, "卡尼堡")
        self.assertEqual(game["party"], {"杰克": 100, "杰克2": 100})
        self.assertEqual(game["jobs"], {"杰克2": "老兵"})

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

    # ---------- 日期和天气 ----------

    def test_dates(self):
        """第几天是几月几号: 跨月、跨年都要算对"""
        game = w.new_game()
        game["start_month"] = 4
        self.assertEqual(w.date_text(game, 1), "4月1日")
        self.assertEqual(w.date_text(game, 30), "4月30日")
        self.assertEqual(w.date_text(game, 31), "5月1日")
        self.assertEqual(w.date_text(game, 62), "6月1日")
        game["start_month"] = 12
        self.assertEqual(w.date_text(game, 32), "1月1日")

    def test_climate_table(self):
        """气候表: 地区按路线排好, 每个地区都有 12 个月的数字"""
        self.assertEqual(min(w.CLIMATE), 0)
        self.assertLess(max(w.CLIMATE), w.TOTAL_DISTANCE)
        for region, highs, wet_days, snow_days in w.CLIMATE.values():
            with self.subTest(region=region):
                self.assertEqual([len(highs), len(wet_days), len(snow_days)], [12, 12, 12])
                for month in range(12):
                    self.assertGreater(wet_days[month], 0)   # 算下雪的比例时要除以它, 不能是 0
                    self.assertLessEqual(wet_days[month], w.MONTH_DAYS[month])
        regions = [region for region, *_ in w.CLIMATE.values()]
        for region in w.DUSTY_REGIONS:
            self.assertIn(region, regions)

    def roll_many(self, km, month, days=5000):
        """在某个地方、某个月, 连着过很多天, 返回每天的 (天气, 气温)"""
        game = w.new_game()
        game["distance"] = km
        game["start_month"] = month
        game["day"] = 15   # 一直是这个月的 15 号
        random.seed(1)
        results = []
        for _ in range(days):
            w.roll_weather(game)
            results.append((game["weather"], game["temperature"]))
        return results

    def test_rain_days_match_real_data(self):
        """连着下雨的日子多了, 但长期算下来, 下雨下雪的天数还是跟气象站的平均差不多"""
        for km, month in [(0, 5), (2900, 1), (2900, 7), (1270, 4)]:
            with self.subTest(km=km, month=month):
                days = self.roll_many(km, month)
                wet = [weather in w.WET_WEATHER for weather, _ in days]
                expected = w.CLIMATE[km][2][month - 1] / w.MONTH_DAYS[month - 1]
                self.assertAlmostEqual(sum(wet) / len(wet), expected, delta=0.04)
                # 昨天下了雨, 今天接着下的机会比昨天没下时大
                after_wet = [today for yesterday, today in zip(wet, wet[1:]) if yesterday]
                after_dry = [today for yesterday, today in zip(wet, wet[1:]) if not yesterday]
                self.assertGreater(sum(after_wet) / len(after_wet), sum(after_dry) / len(after_dry))

    def test_weather_follows_place_and_season(self):
        """7 月的大平原很热、不下雪, 会有辐射风暴; 1 月的胡德山很冷, 常下雪, 还会有暴风雪"""
        summer = self.roll_many(0, 7)
        winter = self.roll_many(2900, 1)
        summer_weather = [weather for weather, _ in summer]
        winter_weather = [weather for weather, _ in winter]
        self.assertNotIn("灰雪", summer_weather)
        self.assertNotIn("灰色暴风雪", summer_weather)
        self.assertIn("辐射风暴", summer_weather)
        self.assertIn("灰雪", winter_weather)
        self.assertIn("灰色暴风雪", winter_weather)
        self.assertNotIn("辐射风暴", winter_weather)   # 辐射风暴要天热才有 (就像雷暴)
        self.assertGreater(sum(t for _, t in summer) / len(summer), 25)
        self.assertLess(sum(t for _, t in winter) / len(winter), 3)
        # 沙尘暴只在又干又多风的地方刮
        self.assertIn("辐射沙尘暴", [weather for weather, _ in self.roll_many(1900, 6)])
        self.assertNotIn("辐射沙尘暴", [weather for weather, _ in self.roll_many(0, 6)])

    def test_every_weather_can_happen(self):
        """每一种天气都会在路上的某个地方、某个月出现"""
        seen = set()
        for km in w.CLIMATE:
            for month in [1, 4, 7]:
                seen.update(weather for weather, _ in self.roll_many(km, month, days=2000))
        self.assertEqual(seen, set(w.WEATHER))

    def test_storm_goes_into_diary(self):
        """碰上辐射风暴要记进旅行日记, 连着几天的风暴只记一次"""
        game = new_test_game()
        game["start_month"] = 7   # 7 月的大平原
        storm_days = 0
        random.seed(1)
        with mock.patch.object(w, "STORM_CHANCE", 1):   # 天热时下雨一定是辐射风暴
            for _ in range(200):
                game["warmth"] = 10   # 一直很热
                w.roll_weather(game)
                storm_days += game["weather"] == "辐射风暴"
        written = [line for line in game["diary"] if "遇到了辐射风暴" in line]
        self.assertGreater(len(written), 0)
        self.assertLess(len(written), storm_days)

    def test_snow_is_cold(self):
        """下雪的日子气温不会超过 2 度"""
        for weather, temperature in self.roll_many(1270, 4):
            if weather in ["灰雪", "灰色暴风雪"]:
                self.assertLessEqual(temperature, 2)

    def test_cold_without_clothes(self):
        """天冷时冬衣只够一个人穿: 排在前面的穿上, 没穿上的人冻伤。躲在车里也会冻着"""
        game = new_test_game()
        game["party"] = {"A": 50, "B": 50}
        game["supplies"]["冬衣"] = 1
        game["temperature"] = 5   # 寒冷
        screen = io.StringIO()
        with no_new_diseases(), redirect_stdout(screen):
            w.pass_day(game, indoors=True)
        self.assertEqual(game["party"], {"A": 51, "B": 48})   # 普通口粮 +1, 没冬衣 -3
        self.assertIn("B没有冬衣穿", screen.getvalue())
        self.assertEqual(game["supplies"]["食物"], 100 - 2 * 3)   # 天冷每人多吃 1 份

        game["party"] = {"A": 50, "B": 50}
        game["weather"] = "晴"      # 过了一天天气变了, 换回晴天, 只看冷的影响
        game["temperature"] = -5   # 严寒, 在外面
        with no_new_diseases(), redirect_stdout(io.StringIO()):
            w.pass_day(game)
        self.assertEqual(game["party"], {"A": 50, "B": 42})   # 口粮 +1, 严寒在外面 -1, 没冬衣再 -8

    def test_heat_needs_more_water(self):
        """酷热天每人多喝 2 份水, 在外面还会中暑"""
        game = new_test_game()
        game["temperature"] = 38
        with no_new_diseases(), redirect_stdout(io.StringIO()):
            w.pass_day(game)
        self.assertEqual(game["supplies"]["水"], 100 - 4 * 3)
        self.assertEqual(list(game["party"].values()), [99, 99, 99, 99])   # 口粮 +1, 中暑 -2

    def test_blizzard_stops_the_car(self):
        """暴风雪里车开不动: 不往前走、不用燃料, 但是过了一天"""
        game = new_test_game()
        game["weather"] = "灰色暴风雪"
        game["temperature"] = 0
        screen = io.StringIO()
        with redirect_stdout(screen):
            w.travel(game)
        self.assertEqual(game["distance"], 0)
        self.assertEqual(game["supplies"]["燃料"], 100)
        self.assertEqual(game["day"], 2)
        self.assertIn("开不动", screen.getvalue())

    def test_temperature_units(self):
        """选公里就用摄氏度, 选英里就用华氏度"""
        game = new_test_game()
        self.assertEqual(w.show_temperature(game, 30), "30°C")
        game["unit"] = "英里"
        self.assertEqual(w.show_temperature(game, 30), "86°F")
        self.assertEqual(w.show_temperature(game, -5), "23°F")

    def test_status_shows_date_and_weather(self):
        game = new_test_game()
        game["start_month"] = 6
        game["day"] = 3
        game["distance"] = 1450   # 南山口
        game["weather"] = "黑雨"
        game["temperature"] = 33
        screen = io.StringIO()
        with redirect_stdout(screen):
            w.show_status(game)
        for words in ["6月3日 (第 3 天)", "地区: 落基山区", "天气: 黑雨", "33°C 炎热",
                      "路上泥泞", "每人要多喝 1 份水", "冬衣 100"]:
            self.assertIn(words, screen.getvalue())

    def test_old_save_still_loads(self):
        """以前版本的存档 (没有冬衣、出发月份, 天气还叫"酷热") 也能接着玩"""
        old = w.new_game()
        old["party"] = {"A": 80}
        old["leader"] = "A"
        old["weather"] = "酷热"
        del old["supplies"]["冬衣"]
        del old["supplies"]["排辐剂"]
        for key in ["start_month", "temperature", "warmth", "rads", "sick", "rain", "difficulty"]:
            del old[key]
        with open(w.SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(old, f, ensure_ascii=False)
        with redirect_stdout(io.StringIO()):
            game = w.load_game()
            w.show_status(game)
            w.show_party(game)
            w.pass_day(game)
        self.assertEqual(game["supplies"]["冬衣"], 0)
        self.assertEqual(game["supplies"]["排辐剂"], 0)
        self.assertIn(game["weather"], w.WEATHER)
        self.assertEqual(game["difficulty"], 2)   # 以前没有难度选择, 算普通

    # ---------- 辐射 ----------

    def test_storm_radiation_even_in_the_car(self):
        """辐射风暴: 在外面每天受 15 点辐射, 躲在车里也有 5 点"""
        for indoors, expected in [(False, 15), (True, 5)]:
            game = new_test_game()
            game["weather"] = "辐射风暴"
            with redirect_stdout(io.StringIO()):
                w.pass_day(game, indoors=indoors)
            self.assertEqual(game["rads"], {"A": expected, "B": expected, "C": expected, "D": expected})

    def test_radiation_hurts_every_day(self):
        """辐射值高的人每天掉血, 越高掉得越多; 辐射不会自己降下来"""
        game = new_test_game()
        game["rads"] = {"A": 10, "B": 30, "C": 60, "D": 90}
        screen = io.StringIO()
        with no_new_diseases(), redirect_stdout(screen):
            w.pass_day(game, indoors=True)
        # 普通口粮 +1 (满血 100 封顶), 再按辐射: 轻度 -1, 严重 -3, 致命 -6
        self.assertEqual(game["party"], {"A": 100, "B": 99, "C": 97, "D": 94})
        self.assertEqual(game["rads"], {"A": 10, "B": 30, "C": 60, "D": 90})
        self.assertIn("辐射在B、C、D的身体里作怪", screen.getvalue())

    def test_anti_rad(self):
        """一支排辐剂排掉 50 点辐射; 身上没辐射的人用了不浪费"""
        game = new_test_game()
        with redirect_stdout(io.StringIO()):
            w.use_anti_rad(game, "A")
        self.assertEqual(game["supplies"]["排辐剂"], 100)
        game["rads"] = {"A": 30, "B": 70}
        with redirect_stdout(io.StringIO()):
            w.use_anti_rad(game, "B")
            w.use_anti_rad(game, "A")
        self.assertEqual(game["rads"], {"A": 0, "B": 20})
        self.assertEqual(game["supplies"]["排辐剂"], 98)

    def test_medicine_menu(self):
        """每天的菜单里的「用药」: 先选哪种药, 再选给谁; 哪一步选 0 都是不用"""
        for answers, used, who in [(["1", "1"], "药品", "A"), (["2", "2"], "排辐剂", "B"),
                                   (["0"], None, None), (["1", "0"], None, None)]:
            with self.subTest(answers=answers):
                game = new_test_game()
                game["party"]["A"] = 50
                game["rads"] = {"B": 60}
                keys = iter(answers)
                with mock.patch("builtins.input", lambda p="": next(keys)), redirect_stdout(io.StringIO()):
                    w.take_medicine(game)
                for item in ["药品", "排辐剂"]:
                    self.assertEqual(game["supplies"][item], 99 if item == used else 100)
                if who == "A":
                    self.assertEqual(game["party"]["A"], 85)
                if who == "B":
                    self.assertEqual(game["rads"]["B"], 10)

    def test_solo_does_not_choose(self):
        """只有一个人时用药不用选给谁"""
        game = new_test_game()
        game["party"] = {"小明": 50}
        game["leader"] = "小明"
        keys = iter(["1"])   # 只回答用哪种药
        screen = io.StringIO()
        with mock.patch("builtins.input", lambda p="": next(keys)), redirect_stdout(screen):
            w.take_medicine(game)
        self.assertEqual(game["party"], {"小明": 85})
        self.assertIn("你给自己用了药", screen.getvalue())

    def test_radiation_sickness_event(self):
        """辐射病不直接掉血, 而是辐射一下子升高"""
        game = new_test_game()
        game["party"] = {"A": 100}
        with redirect_stdout(io.StringIO()):
            w.radiation_sickness(game)
        self.assertEqual(game["rads"], {"A": w.SICKNESS_RADS})
        self.assertEqual(game["party"], {"A": 100})

    def test_radiation_is_capped_and_cleared(self):
        """辐射值最多 100; 人去世以后就不再记他的辐射"""
        game = new_test_game()
        w.irradiate(game, "A", 500)
        self.assertEqual(game["rads"], {"A": 100})
        with redirect_stdout(io.StringIO()):
            w.hurt(game, "A", 100)
        self.assertEqual(game["rads"], {})

    def test_radiation_shown(self):
        """状态栏和查看队伍都能看到辐射"""
        game = new_test_game()
        game["rads"] = {"B": 60}
        screen = io.StringIO()
        with redirect_stdout(screen):
            w.show_status(game)
            w.show_party(game)
        self.assertIn("B 良好(100) 辐射60", screen.getvalue())
        self.assertIn("辐射 60 严重, 每天掉 3 点健康", screen.getvalue())
        self.assertIn("排辐剂 100", screen.getvalue())

    def test_hotspots_on_route(self):
        """辐射热点按路程排好、不重叠, 都在路上; 每一段都比车一天最多能开的路长, 不会一天就整段开过去"""
        longest_day = max(km for _, km, _, _ in w.PACES.values()) + 10
        self.assertEqual(w.HOTSPOTS, sorted(w.HOTSPOTS))
        for start, end, name, outdoor, indoor, intro in w.HOTSPOTS:
            self.assertLess(0, start)
            self.assertLessEqual(end, w.TOTAL_DISTANCE)
            self.assertGreater(end - start, longest_day)
            self.assertGreater(outdoor, indoor)
        for before, after in zip(w.HOTSPOTS, w.HOTSPOTS[1:]):
            self.assertLessEqual(before[1], after[0])

    def test_hotspot_radiation(self):
        """在辐射热点里, 晴天也要受辐射: 在外面多, 躲在车里少; 没开进去或者开出来了就没有"""
        start, end, name, outdoor, indoor, _ = w.HOTSPOTS[0]
        for distance, indoors, expected in [(start, False, outdoor), (end - 1, True, indoor),
                                            (start - 1, False, 0), (end, False, 0)]:
            with self.subTest(distance=distance, indoors=indoors):
                game = new_test_game()
                game["distance"] = distance
                screen = io.StringIO()
                with no_new_diseases(), redirect_stdout(screen):
                    w.pass_day(game, indoors=indoors)
                self.assertEqual(game["rads"], {"A": expected, "B": expected, "C": expected, "D": expected})
                self.assertEqual(f"{name}辐射偏高, 大家又受了" in screen.getvalue(), bool(expected))

    def test_enter_hotspot(self):
        """开进辐射热点时提醒一次, 记进日记 (按热点开始的地方记)"""
        start, _, name, _, _, intro = w.HOTSPOTS[0]
        game = new_test_game()
        game["distance"] = start + 10
        game["visited"] = [place for km, (place, _) in list(w.LANDMARKS.items()) + list(w.OUTPOSTS.items())
                           if km <= game["distance"]]
        screen = io.StringIO()
        with redirect_stdout(screen):
            w.check_places(game)
            w.check_places(game)
        self.assertEqual(screen.getvalue().count(f"开进了【{name}】"), 1)
        self.assertIn(intro, screen.getvalue())
        self.assertIn(f"已走 {start} 公里: 开进了{name}, 这一带辐射偏高。", game["diary"][-1])

    def test_status_shows_hotspot(self):
        """状态栏: 快到辐射热点时提前提醒; 在热点里写着每天受多少辐射、还要开多远才能出去"""
        start, end, name, outdoor, indoor, _ = w.HOTSPOTS[0]
        inside = (f"正在{name}, 还要开 {end - start - 40} 公里才能离开\n"
                  f"          在外面每天受 {outdoor} 点辐射, 躲在车里 {indoor} 点")
        for distance, words in [(start - 100, f"再开 100 公里就到{name}, 那一带辐射偏高"),
                                (start + 40, inside), (start - w.HOTSPOT_WARNING - 1, None)]:
            with self.subTest(distance=distance):
                game = new_test_game()
                game["distance"] = distance
                screen = io.StringIO()
                with redirect_stdout(screen):
                    w.show_status(game)
                if words:
                    self.assertIn(words, screen.getvalue())
                else:
                    self.assertNotIn("辐射热点", screen.getvalue())

    def test_status_fits_small_terminal(self):
        """状态栏每一行都放得下 80 列宽的终端 (东西很多、四个人都病了、在辐射热点里、选英里也一样), 不会折行把画面挤乱"""
        for unit in ["公里", "英里"]:
            for distance in [0, 510, 950, 1950, 2861]:
                with self.subTest(unit=unit, distance=distance):
                    game = new_test_game()
                    game.update(unit=unit, distance=distance, day=199, money=9999, seeds=True, weather="灰色暴风雪")
                    game["party"] = {"小明": 100, "杰克": 40, "玛莎": 10, "埃迪2": 5}
                    game["jobs"] = {"杰克": "老兵", "玛莎": "医生", "埃迪2": "机械师"}
                    game["sick"] = {"埃迪2": ["伤口感染", 3], "杰克": ["过度劳累", 2]}
                    game["rads"] = {name: 100 for name in game["party"]}
                    for item in game["supplies"]:
                        game["supplies"][item] = 9999
                    with redirect_stdout(io.StringIO()) as screen:
                        w.show_status(game)
                    for line in re.sub(r"\x1b\[[\d;]*m", "", screen.getvalue()).split("\n"):
                        self.assertLess(w.text_width(line), 80, line)

    def test_old_save_does_not_warn_about_passed_hotspots(self):
        """以前版本的存档里没记辐射热点: 读档以后, 已经开进去或者开过去的热点不会再提醒一遍"""
        old = new_test_game()
        old["distance"] = w.HOTSPOTS[1][0] + 50   # 过了第一个热点, 正在第二个里面
        old["visited"] = [place for km, (place, _) in list(w.LANDMARKS.items()) + list(w.OUTPOSTS.items())
                          if km <= old["distance"]]
        with open(w.SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(old, f, ensure_ascii=False)
        screen = io.StringIO()
        with redirect_stdout(screen):
            game = w.load_game()
            w.check_places(game)
        self.assertNotIn("开进了", screen.getvalue())

    # ---------- 生病和受伤 ----------

    def test_disease_lasts_days_then_heals(self):
        """痢疾每天掉 3 点健康, 5 天后自己好"""
        game = new_test_game()
        screen = io.StringIO()
        with no_new_diseases(), redirect_stdout(screen):
            w.get_sick(game, "A", "痢疾")
            self.assertEqual(game["sick"], {"A": ["痢疾", 5]})
            for day in range(5):
                game["weather"] = "晴"      # 每天都换回晴天、20 度, 只看生病的影响
                game["temperature"] = 20
                w.pass_day(game)
                if day == 0:
                    self.assertEqual(game["party"]["A"], 97)   # 口粮 +1 (满血封顶), 痢疾 -3
                    self.assertEqual(game["sick"], {"A": ["痢疾", 4]})
        self.assertEqual(game["sick"], {})
        self.assertIn("A的痢疾好了", screen.getvalue())

    def test_only_one_disease_at_a_time(self):
        game = new_test_game()
        with redirect_stdout(io.StringIO()):
            w.get_sick(game, "A", "痢疾")
            w.get_sick(game, "A", "霍乱")
        self.assertEqual(game["sick"], {"A": ["痢疾", 5]})

    def test_rest_and_doctor_heal_faster(self):
        """躲在车里休养, 病好得快一倍; 有医生照顾 (医生自己生病不算), 每天再多好一天"""
        for job, indoors, days_left in [(None, False, 7), (None, True, 6), ("医生", False, 6), ("医生", True, 5)]:
            with self.subTest(job=job, indoors=indoors):
                game = self.with_job(job) if job else new_test_game()
                with no_new_diseases(), redirect_stdout(io.StringIO()):
                    w.get_sick(game, "A", "伤寒")   # 8 天
                    w.pass_day(game, indoors=indoors)
                self.assertEqual(game["sick"]["A"][1], days_left)

    def test_sick_alone_is_worse(self):
        """一个人生病没人照顾, 每天多掉 2 点"""
        for party, expected in [({"小明": 50}, 46), ({"小明": 50, "杰克": 50}, 48)]:
            game = new_test_game()
            game["party"] = dict(party)
            with no_new_diseases(), redirect_stdout(io.StringIO()):
                w.get_sick(game, "小明", "痢疾")
                w.pass_day(game, indoors=True)
            self.assertEqual(game["party"]["小明"], expected)   # 口粮 +1, 痢疾 -3, 一个人再 -2

    def test_medicine_cures_disease(self):
        game = new_test_game()
        game["party"]["A"] = 40
        with redirect_stdout(io.StringIO()):
            w.get_sick(game, "A", "肺炎")
            w.use_medicine(game, "A")
        self.assertEqual(game["sick"], {})
        self.assertEqual(game["party"]["A"], 75)
        self.assertEqual(game["supplies"]["药品"], 99)
        # 满血但是生病的人, 用药也有用 (治病)
        with redirect_stdout(io.StringIO()):
            w.get_sick(game, "B", "骨折")
            w.use_medicine(game, "B")
        self.assertEqual(game["sick"], {})
        self.assertEqual(game["supplies"]["药品"], 98)

    def test_died_of_dysentery(self):
        """病死的人会写「死于痢疾」"""
        game = new_test_game()
        game["party"]["A"] = 2
        screen = io.StringIO()
        with no_new_diseases(), redirect_stdout(screen):
            w.get_sick(game, "A", "痢疾")
            w.pass_day(game)
        self.assertIn("A 死于痢疾", screen.getvalue())
        self.assertIn("A 死于痢疾", "\n".join(game["diary"]))
        self.assertEqual(game["sick"], {})

    def test_cholera_needs_more_water(self):
        game = new_test_game()
        with no_new_diseases(), redirect_stdout(io.StringIO()):
            w.get_sick(game, "A", "霍乱")
            w.pass_day(game)
        self.assertEqual(game["supplies"]["水"], 100 - 4 - w.CHOLERA_WATER)

    def test_dirty_water_makes_people_sick(self):
        """没有干净的水, 只能喝脏水, 会得霍乱或痢疾"""
        game = new_test_game()
        game["supplies"]["水"] = 0
        with mock.patch.multiple(w, catch_diseases=lambda *args: None, DIRTY_WATER_CHANCE=1), \
                redirect_stdout(io.StringIO()):
            w.pass_day(game)
        self.assertEqual(set(game["sick"]), {"A", "B", "C", "D"})
        for disease, _ in game["sick"].values():
            self.assertIn(disease, ["霍乱", "痢疾"])

    def test_what_makes_people_sick(self):
        """健康满分、什么事都没有的人很少生病; 受冻的人更容易病, 而且多半是肺炎"""
        def sick_count(cold):
            diseases = Counter()
            random.seed(1)
            for _ in range(3000):
                game = new_test_game()
                with redirect_stdout(io.StringIO()):
                    w.catch_diseases(game, False, ["A"] if cold else [], False)
                if "A" in game["sick"]:
                    diseases[game["sick"]["A"][0]] += 1
            return diseases
        normal = sick_count(cold=False)
        cold = sick_count(cold=True)
        self.assertAlmostEqual(sum(normal.values()) / 3000, w.SICK_CHANCE, delta=0.006)
        self.assertGreater(sum(cold.values()), sum(normal.values()) * 2)
        self.assertEqual(cold.most_common(1)[0][0], "肺炎")
        self.assertNotIn("肺炎", normal)

    def test_injuries_from_events(self):
        """踩雷会骨折; 被野狗咬、中枪可能伤口感染"""
        game = new_test_game()
        with mock.patch.object(w.random, "random", lambda: 0), \
                mock.patch("builtins.input", lambda p="": "2"), redirect_stdout(io.StringIO()):
            w.minefield(game)   # 慢慢开过去, 一定压到地雷
        self.assertEqual([d for d, _ in game["sick"].values()], ["骨折"])
        game = new_test_game()
        game["supplies"]["子弹"] = 0
        with mock.patch.object(w.random, "random", lambda: 0), redirect_stdout(io.StringIO()):
            w.mutant_attack(game)   # 没子弹, 一定被咬
        self.assertEqual([d for d, _ in game["sick"].values()], ["伤口感染"])

    def test_sickness_shown(self):
        """状态栏和查看队伍都能看到谁病了"""
        game = new_test_game()
        with redirect_stdout(io.StringIO()):
            w.get_sick(game, "B", "痢疾")
        screen = io.StringIO()
        with redirect_stdout(screen):
            w.show_status(game)
            w.show_party(game)
        self.assertIn("B 良好(100) 痢疾", screen.getvalue())
        self.assertIn("痢疾: 拉肚子拉得站不起来, 每天掉 3 点健康, 大约还要 5 天才好", screen.getvalue())

    # ---------- 重量 ----------

    def test_show_weight(self):
        """选公里用公斤, 选英里用磅; 很轻的东西留两位小数"""
        game = w.new_game()
        self.assertEqual(w.show_weight(game, 8000), "8 公斤")
        self.assertEqual(w.show_weight(game, 500), "0.5 公斤")
        self.assertEqual(w.show_weight(game, 20), "0.02 公斤")
        self.assertEqual(w.show_weight(game, 1000000), "1000 公斤")
        game["unit"] = "英里"
        self.assertEqual(w.show_weight(game, 1000000), "2205 磅")
        self.assertEqual(w.show_weight(game, 2000), "4.41 磅")

    def test_load_counts_people_and_supplies(self):
        game = w.new_game()
        game["party"] = {"A": 100, "B": 100}
        game["supplies"]["燃料"] = 10   # 80 公斤
        game["supplies"]["子弹"] = 50   # 1 公斤
        self.assertEqual(w.load_of(game), 2 * 70000 + 80000 + 1000)

    def test_shop_counts_room(self):
        """商店里最多能买几个, 要看钱, 也要看车上还装得下几个"""
        game = w.new_game()
        game["party"] = {"A": 100}
        game["money"] = 1000
        game["supplies"]["燃料"] = 100   # 800 公斤, 加上人一共 870, 还能装 130 公斤 = 16 份燃料
        prompts = []
        answers = iter(["3", "16", "0"])

        def answer(prompt=""):
            prompts.append(prompt)
            return next(answers)
        with real_car(), mock.patch("builtins.input", answer), redirect_stdout(io.StringIO()):
            w.shop(game)
        self.assertIn("买多少燃料? (最多 16) ", prompts)
        self.assertEqual(game["supplies"]["燃料"], 116)

    def test_loot_left_behind_when_full(self):
        game = w.new_game()
        game["party"] = {"A": 100}
        game["supplies"]["燃料"] = 116   # 928 + 70 = 998 公斤, 只剩 2 公斤
        screen = io.StringIO()
        with real_car(), mock.patch.dict(w.LOOT, {"水": (10, 10)}, clear=True), redirect_stdout(screen):
            w.find_supplies(game)
        self.assertEqual(game["supplies"]["水"], 1)   # 2 公斤只装得下 1 份水
        self.assertIn("有 9 份水只能丢下", screen.getvalue())

    def test_hunting_carry_limit(self):
        """打到 100 份肉: 一个人只扛得动 40 份 (20 公斤), 4 个人能扛 160 份, 就能全带回来"""
        for party, brought in [({"A": 100}, 40), ({"A": 100, "B": 100, "C": 100, "D": 100}, 100)]:
            game = w.new_game()
            game["party"] = dict(party)
            game["supplies"]["子弹"] = 5
            with real_car(), no_new_diseases(), mock.patch.object(w, "HUNT_WORDS", ["bang"]), \
                    mock.patch.object(w, "ANIMALS", {"测试猪": (100, 100)}), \
                    mock.patch.object(w.time, "time", side_effect=[0, 1.0]), \
                    mock.patch("builtins.input", lambda p="": "bang"), redirect_stdout(io.StringIO()):
                w.hunt(game)
            eaten = 2 * len(party)   # 打猎花了一天, 每人吃 2 份
            self.assertEqual(game["supplies"]["食物"], brought - eaten)

    def test_no_seat_when_too_heavy(self):
        """车上东西太重, 据点里的人坐不上来"""
        game = w.new_game()
        game["party"] = {"小明": 100}
        game["supplies"]["燃料"] = 115   # 920 + 70 = 990 公斤, 再坐一个人就超载
        screen = io.StringIO()
        with real_car(), mock.patch("builtins.input", lambda p="": "2"), redirect_stdout(screen):
            w.offer_recruit(game, "卡尼堡")   # 不丢东西
        self.assertEqual(list(game["party"]), ["小明"])
        self.assertIn("超载", screen.getvalue())
        # 先丢 5 份燃料 (40 公斤) 还不够, 再丢 3 份: 车上 926 公斤, 杰克 (70 公斤) 就坐得下了
        answers = iter(["1", "3", "5", "0", "1", "3", "3", "0", "1"])   # 丢东西: 燃料 5 份, 不丢了; 还是坐不下, 再丢 3 份; 让杰克加入
        with real_car(), mock.patch("builtins.input", lambda p="": next(answers)), redirect_stdout(io.StringIO()):
            w.offer_recruit(game, "卡尼堡")
        self.assertEqual(list(game["party"]), ["小明", "杰克"])
        self.assertEqual(game["supplies"]["燃料"], 107)
        self.assertEqual(game["supplies"]["食物"], 8)   # 他带的 60 份口粮只装得下 4 公斤

    def test_recruit_brings_only_what_fits(self):
        game = w.new_game()
        game["party"] = {"小明": 100}
        game["supplies"]["燃料"] = 100   # 800 + 70 = 870, 杰克坐上来 940, 还剩 60 公斤
        with real_car(), mock.patch("builtins.input", lambda p="": "1"), redirect_stdout(io.StringIO()):
            w.offer_recruit(game, "卡尼堡")
        self.assertIn("杰克", game["party"])
        self.assertEqual(game["supplies"]["食物"], 100)   # 50 公斤, 装得下
        self.assertEqual(game["supplies"]["水"], 5)       # 只剩 10 公斤, 只装得下 5 份水

    # ---------- 交易 ----------

    def fuel_offer(self):
        """交易时对方一定拿出 8 份燃料, 按商店的价钱要回一样多 (值 32 块)"""
        return mock.patch.multiple(w, TRADE_LOTS={"燃料": (8, 8)}, TRADE_ASK=(100, 100))

    def only(self, game, **supplies):
        """车上只有这几样东西, 别的都是 0 (对方只能要车上有的东西)"""
        for item in game["supplies"]:
            game["supplies"][item] = supplies.get(item, 0)

    def test_trade(self):
        """对方拿出 8 份燃料, 要值一样多的食物 (32 份): 不换什么都不变; 换了就换了, 记进日记"""
        game = new_test_game()
        self.only(game, 食物=100)
        with self.fuel_offer(), mock.patch("builtins.input", lambda p="": "2"), redirect_stdout(io.StringIO()):
            w.offer_trade(game, "一个独眼的老猎人")
        self.assertEqual((game["supplies"]["食物"], game["supplies"]["燃料"]), (100, 0))
        screen = io.StringIO()
        with self.fuel_offer(), mock.patch("builtins.input", lambda p="": "1"), redirect_stdout(screen):
            w.offer_trade(game, "一个独眼的老猎人")
        self.assertIn("我这 8 份燃料换你 32 份食物, 换不换?", screen.getvalue())
        self.assertEqual((game["supplies"]["食物"], game["supplies"]["燃料"]), (68, 8))
        self.assertIn("跟一个独眼的老猎人用 32 份食物换了 8 份燃料。", game["diary"][-1])

    def test_merchant_trades_cheaper(self):
        """有商人帮着讲价, 对方少要两成: 32 份食物变成 26 份"""
        game = self.with_job("商人")
        self.only(game, 食物=100)
        screen = io.StringIO()
        with self.fuel_offer(), mock.patch("builtins.input", lambda p="": "1"), redirect_stdout(screen):
            w.offer_trade(game, "一个独眼的老猎人")
        self.assertIn("商人B帮你讲价", screen.getvalue())
        self.assertEqual((game["supplies"]["食物"], game["supplies"]["燃料"]), (74, 8))

    def test_trade_needs_what_they_want(self):
        """车上的东西不够对方要的, 就换不成"""
        game = new_test_game()
        self.only(game, 食物=31)
        screen = io.StringIO()
        with self.fuel_offer(), mock.patch("builtins.input", lambda p="": "1"), redirect_stdout(screen):
            w.offer_trade(game, "一个独眼的老猎人")
        self.assertIn("没有对方想要的东西", screen.getvalue())
        self.assertEqual((game["supplies"]["食物"], game["supplies"]["燃料"]), (31, 0))

    def test_trade_needs_room(self):
        game = w.new_game()
        game["party"] = {"A": 100}
        self.only(game, 食物=40, 燃料=110)   # 70 + 20 + 880 = 970 公斤, 换掉 16 公斤食物也装不下 64 公斤燃料
        screen = io.StringIO()
        with real_car(), self.fuel_offer(), mock.patch("builtins.input", lambda p="": "1"), redirect_stdout(screen):
            w.trader(game)
        self.assertIn("【流浪商人】", screen.getvalue())
        self.assertIn("装不下 8 份燃料", screen.getvalue())
        self.assertEqual(game["supplies"]["燃料"], 110)

    def test_trades_always_add_up(self):
        """乱换 2000 次 (车上的东西也是乱的): 换完不会有负数, 车也不会超重; 流浪商人不花时间"""
        rng = random.Random(1)
        for seed in range(2000):
            random.seed(seed)
            game = w.new_game()
            game["party"] = {name: 100 for name in "ABCD"[:rng.randint(1, 4)]}
            for item in game["supplies"]:
                game["supplies"][item] = rng.choice([0, 0, 1, 2, 5, 30, 100])
            if w.load_of(game) > REAL_CAPACITY:
                continue
            with real_car(), mock.patch("builtins.input", lambda p="": "1"), redirect_stdout(io.StringIO()):
                w.trader(game)
            with self.subTest(seed=seed):
                self.assertTrue(all(amount >= 0 for amount in game["supplies"].values()))
                self.assertLessEqual(w.load_of(game), REAL_CAPACITY)
                self.assertEqual(game["day"], 1)

    def test_trade_takes_a_day(self):
        """每天的菜单里的「交易」花一天: 在路上可能碰不到人, 停在据点里一定碰得到"""
        game = new_test_game()
        game["here"] = None
        with mock.patch.object(w, "TRADE_CHANCE", 0), redirect_stdout(io.StringIO()) as screen:
            w.trade(game)
        self.assertEqual(game["day"], 2)
        self.assertIn("连个人影都没看到", screen.getvalue())
        game["here"] = "卡尼堡"
        with mock.patch.object(w, "TRADE_CHANCE", 0), mock.patch("builtins.input", lambda p="": "2"), \
                redirect_stdout(io.StringIO()) as screen:
            w.trade(game)
        self.assertEqual(game["day"], 3)
        self.assertIn("在卡尼堡里转了一天", screen.getvalue())
        self.assertIn("凑了过来", screen.getvalue())

    def test_menu_trade(self):
        """每天的菜单里选 5 是交易"""
        game = new_test_game()
        answers = iter(["5", "13", "2"])   # 交易, 存档, 回到主菜单
        with mock.patch.object(w, "TRADE_CHANCE", 0), mock.patch("builtins.input", lambda p="": next(answers)), \
                redirect_stdout(io.StringIO()) as screen:
            w.play(game)
        self.assertIn("5. 交易", screen.getvalue())
        self.assertIn("连个人影都没看到", screen.getvalue())

    # ---------- 打猎小游戏 ----------

    def test_typing_hunt_when_cannot_aim(self):
        """跑测试、网页还是旧版的时候不能实时读键盘, 打猎还是以前打字的样子; 设置里关掉了也是"""
        self.assertFalse(w.can_aim())
        with mock.patch.object(w, "can_clear_screen", lambda: True), mock.patch.object(w, "HUNT_IN_BROWSER", True):
            self.assertTrue(w.can_aim())
            with mock.patch.object(w, "HUNT_GAME", False):
                self.assertFalse(w.can_aim())

    def test_aim_hunt(self):
        """会瞄准的电脑玩家打猎: 打得到动物, 开一枪用一发子弹, 肉记进日记, 花一天"""
        from tests.balance import hunter_bot
        game = new_test_game()
        game["supplies"]["食物"] = 0
        game["supplies"]["子弹"] = 50
        with mock.patch.multiple(w, can_aim=lambda: True, hunt_keys=hunter_bot([game])), \
                mock.patch("builtins.input", lambda p="": ""), redirect_stdout(io.StringIO()) as screen:
            w.hunt(game)
        text = screen.getvalue()
        shots = int(re.search(r"这次开了 (\d+) 枪", text)[1])
        self.assertIn("打到了", text)
        self.assertEqual(game["supplies"]["子弹"], 50 - shots)
        self.assertEqual(game["day"], 2)
        self.assertIn("打猎打到", game["diary"][-1])
        self.assertLessEqual(game["supplies"]["食物"], 4 * 40)   # 4 个人最多扛 160 份 (过了一天还吃掉一些)

    def hunting_with_deer(self, game, x=20, y=5):
        """一场打猎, 原野上只有一只往左跑的双头鹿, 在第 y 行第 x 格 (11 格宽、4 行高)"""
        hunting = w.new_hunt(game)
        hunting["animals"].append({"name": "双头鹿", "x": x, "y": y, "speed": -0.6, "scared": False, "dead": None})
        return hunting

    def test_shoot(self):
        """准星在动物身上就打中; 没打中会吓得旁边的动物跑快; 网页上点在动物旁边一格也算; 子弹打光就结束"""
        game = new_test_game()
        game["supplies"]["子弹"] = 3
        hunting = self.hunting_with_deer(game)
        hunting["aim"] = [6, 25]
        w.hunt_event(game, hunting, ("开枪",))
        self.assertEqual([name for name, _ in hunting["bag"]], ["双头鹿"])
        self.assertEqual((game["supplies"]["子弹"], hunting["shots"]), (2, 1))
        self.assertIn("打中了一只双头鹿", hunting["message"])

        hunting = self.hunting_with_deer(game)
        hunting["aim"] = [6, 34]   # 鹿在 20~30 格, 准星在旁边
        w.hunt_event(game, hunting, ("开枪",))
        self.assertEqual(hunting["bag"], [])
        self.assertEqual(hunting["animals"][0]["speed"], -0.6 * w.HUNT_SCARE_SPEED)
        self.assertEqual(game["supplies"]["子弹"], 1)

        hunting = self.hunting_with_deer(game)
        w.hunt_event(game, hunting, ("打", 1 + 9, 31))   # 网页: 点在屏幕第 10 行 (原野第 9 行, 鹿的下面一行), 鹿右边一格
        self.assertEqual(len(hunting["bag"]), 1)
        self.assertEqual(hunting["aim"], [9, 31])
        self.assertEqual(game["supplies"]["子弹"], 0)

        w.hunt_event(game, hunting, ("开枪",))
        self.assertTrue(hunting["over"])
        self.assertIn("没子弹了", hunting["message"])

    def test_aim_moves(self):
        """方向键移动准星 (左右一次 2 格), 不会移出原野; 网页上鼠标移到哪准星就在哪; 回车结束"""
        game = new_test_game()
        hunting = w.new_hunt(game)
        hunting["aim"] = [0, 1]
        for key in ["上", "左", "右", "右", "下"]:
            w.hunt_event(game, hunting, (key,))
        self.assertEqual(hunting["aim"], [1, 4])
        w.hunt_event(game, hunting, ("瞄", 3, 50))
        self.assertEqual(hunting["aim"], [2, 50])
        w.hunt_event(game, hunting, ("瞄", 40, 50))   # 点在原野外面不算
        self.assertEqual(hunting["aim"], [2, 50])
        self.assertEqual(game["supplies"]["子弹"], 100)
        w.hunt_event(game, hunting, ("走",))
        self.assertTrue(hunting["over"])

    def test_terminal_hunt_keys(self):
        """终端里: 方向键是 ESC [ A 这样三个字; W A S D 也能移动, 空格开枪, 回车或 Q 结束"""
        self.assertEqual(w.split_keys("\x1b[A \x1b[Dq\x1bOC"), ["上", " ", "左", "q", "右"])
        events = [w.HUNT_KEYS.get(key.lower()) for key in "wasd \rQ"]
        self.assertEqual(events, ["上", "左", "下", "右", "开枪", "走", "走"])

    def test_animals_and_hunt_screen(self):
        """动物往右跑时左右翻过来, 两帧一样大; 画面一共 15 行, 原野只用英文字符, 不超过画面宽"""
        for name, frames in w.ANIMAL_ART.items():
            with self.subTest(name=name):
                self.assertEqual({len(frame) for frame in frames}, {len(frames[0])})
                self.assertTrue(all(line.isascii() for frame in frames for line in frame))
                left = {"name": name, "speed": -1, "x": 0, "y": 2}
                right = {"name": name, "speed": 1, "x": 0, "y": 2}
                self.assertEqual(w.animal_box(left), w.animal_box(right))
        right = {"name": "辐射野猪", "speed": 1}
        self.assertEqual(w.animal_art(right)[1], "~(       o)>")
        game = new_test_game()
        hunting = self.hunting_with_deer(game)
        rows = [re.sub(r"\x1b\[[\d;]*m", "", row) for row in w.hunt_rows(game, hunting)]
        self.assertEqual(len(rows), 1 + w.HUNT_HEIGHT + 2)
        field = rows[1:1 + w.HUNT_HEIGHT]
        self.assertTrue(all(row.isascii() and len(row) == w.SCENE_WIDTH for row in field))
        self.assertIn("<o><o>", field[6])
        self.assertTrue(all(w.text_width(row) <= w.SCENE_WIDTH for row in rows))

    def test_hunt_ends_in_time(self):
        """没人按键, 打猎到时间就结束; 动物会跑进来, 也会跑出去"""
        game = new_test_game()
        seen = set()

        def nobody(hunting):
            seen.update(animal["name"] for animal in hunting["animals"])
            return []
        random.seed(1)
        with mock.patch.object(w, "hunt_keys", nobody), redirect_stdout(io.StringIO()):
            hunting = w.hunt_game(game)
        self.assertEqual(hunting["left"], 0)
        self.assertEqual(hunting["bag"], [])
        self.assertIn("时间到了", hunting["message"])
        self.assertTrue(seen)

    # ---------- 路上的小事 ----------

    def test_small_events(self):
        """新的路上的事 (小事): 每一件都能发生, 不会出错; 有的东西变多, 有的变少"""
        for event in w.SMALL_EVENTS:
            for seed in range(20):
                with self.subTest(event=event.__name__, seed=seed):
                    random.seed(seed)
                    game = new_test_game()
                    with mock.patch("builtins.input", lambda p="": str(seed % 2 + 1)), redirect_stdout(io.StringIO()):
                        event(game)
                    self.assertTrue(all(amount >= 0 for amount in game["supplies"].values()))
                    self.assertTrue(all(0 <= health <= 100 for health in game["party"].values()))

    def test_small_events_effects(self):
        game = new_test_game()
        with no_new_diseases(), redirect_stdout(io.StringIO()):
            w.lost_way(game)
        self.assertIn(game["day"], [2, 3])
        hunter = self.with_job("猎人")
        with no_new_diseases(), redirect_stdout(io.StringIO()):
            w.lost_way(hunter)
        self.assertEqual(hunter["day"], 2)   # 猎人认得路, 只耽误一天

        game = new_test_game()
        with redirect_stdout(io.StringIO()):
            w.wild_food(game)
            w.clean_spring(game)
        self.assertTrue(110 <= game["supplies"]["食物"] <= 130 and 120 <= game["supplies"]["水"] <= 140)

        game = new_test_game()
        with redirect_stdout(io.StringIO()):
            w.car_fire(game)
        self.assertEqual(sorted(game["supplies"].values())[0] in range(70, 91), True)   # 一样东西烧掉 10%~30%

        veteran = self.with_job("老兵")
        with redirect_stdout(io.StringIO()) as screen:
            w.thief(veteran)
        self.assertEqual(set(veteran["supplies"].values()), {100})
        self.assertIn("吓得", screen.getvalue())

        game = new_test_game()
        with mock.patch.object(w, "ROUGH_ROAD_BREAK", 1), mock.patch("builtins.input", lambda p="": "2"), \
                redirect_stdout(io.StringIO()):
            w.rough_road(game)   # 冲过去, 车颠坏了, 用掉一个零件
        self.assertEqual(game["supplies"]["零件"], 99)

        doctor = self.with_job("医生")
        with mock.patch.object(w, "random_member", lambda game: "A"), mock.patch.object(w, "INFECTION_CHANCE", 1), \
                redirect_stdout(io.StringIO()):
            w.snake_bite(doctor)
        self.assertLess(doctor["party"]["A"], 100)
        self.assertNotIn("A", doctor["sick"])   # 医生处理过的伤口不会感染

    def test_small_events_on_the_road(self):
        """没遇到大事的话, 还可能遇到小事"""
        game = new_test_game()
        happened = []
        with mock.patch.multiple(w, EVENTS=[lambda game: happened.append("大")], SMALL_EVENTS=[lambda game: happened.append("小")]), \
                mock.patch.object(w.random, "random", lambda: 0.1):
            w.random_event(game, 10)   # 开 10 公里: 大事 3.5%, 小事 1.5%, 都没碰上
            w.random_event(game, 100)  # 开 100 公里: 大事 35% 没碰上 (0.1 < 0.35 碰上了)
        self.assertEqual(happened, ["大"])
        with mock.patch.multiple(w, EVENTS=[lambda game: happened.append("大")], SMALL_EVENTS=[lambda game: happened.append("小")]), \
                mock.patch.object(w.random, "random", lambda: 0.1), mock.patch.object(w, "EVENT_CHANCE_PER_100KM", 0):
            w.random_event(game, 100)  # 没有大事, 小事 15% 碰上了
        self.assertEqual(happened, ["大", "小"])

    # ---------- 和人说话 ----------

    def test_talk(self):
        """停在一个地方才有人说话; 每次换一个人、说一件事 (前面的河多深、天气、下一个据点、辐射热点、最后一段路、提醒)"""
        game = new_test_game()
        game["here"] = None
        with redirect_stdout(io.StringIO()) as screen:
            w.talk(game)
        self.assertIn("一个人影都没有", screen.getvalue())

        game["here"], game["distance"] = "卡尼堡", 510
        with redirect_stdout(io.StringIO()) as screen:
            for _ in range(8):
                w.talk(game)
        text = screen.getvalue()
        for words in ["就是北普拉特河", "收 10 块钱", "再往西到了高平原一带", "下一个能买东西的地方是拉勒米堡",
                      "就到导弹发射井一带了", "到了达尔斯", "一个在据点门口晒太阳的老人说", "据点里修车的师傅说"]:
            self.assertIn(words, text)
        self.assertEqual(text.count("都跟你们说过了"), 1)   # 一共 7 件事, 第 7 次说完提醒一下
        self.assertEqual(game["talk"], ["卡尼堡", 8])

        game["here"], game["distance"] = "达尔斯", 2861   # 过了达尔斯: 没有据点、没有河, 也不用再说最后一段路
        with redirect_stdout(io.StringIO()) as screen:
            for _ in range(4):
                w.talk(game)
        text = screen.getvalue()
        self.assertIn("再也没有能买东西的地方", text)
        self.assertNotIn("扎木筏", text)
        self.assertEqual(game["talk"], ["达尔斯", 4])   # 换了地方, 从头说起

    def test_talk_on_menu(self):
        game = new_test_game()
        answers = iter(["10", "13", "2"])   # 和人说话, 存档, 回到主菜单
        with mock.patch("builtins.input", lambda p="": next(answers)), redirect_stdout(io.StringIO()) as screen:
            w.play(game)
        self.assertIn("10. 和人说话", screen.getvalue())
        self.assertIn("在这里歇脚的一个旅人说", screen.getvalue())   # 刚出发, 停在独立城

    # ---------- 休息几天、丢东西 ----------

    def test_rest_days(self):
        """问休息几天: 选 3 就过 3 天, 每天多恢复 8 点健康; 选 0 就不休息"""
        game = new_test_game()
        game["party"] = {"A": 50, "B": 50}
        with no_new_diseases(), mock.patch.multiple(w, roll_weather=lambda g: None), \
                mock.patch("builtins.input", lambda p="": "3"), redirect_stdout(io.StringIO()) as screen:
            w.rest(game)
        self.assertEqual(game["day"], 4)
        self.assertEqual(game["party"], {"A": 50 + 3 * (8 + 1), "B": 50 + 3 * (8 + 1)})   # 普通口粮每天还有 1 点
        self.assertIn("4月3日 晴, 休息了一天。", screen.getvalue())
        self.assertIn("休息了 3 天", screen.getvalue())
        with mock.patch("builtins.input", lambda p="": "0"), redirect_stdout(io.StringIO()):
            w.rest(game)
        self.assertEqual(game["day"], 4)

    def test_rest_stops_when_something_happens(self):
        """休息到一半有人病倒、有人去世, 或者吃的头一回不够了, 就不接着休息了"""
        game = new_test_game()
        sick_on_day_2 = lambda g, *args: g["day"] == 2 and w.get_sick(g, "A", "痢疾")
        with mock.patch.object(w, "catch_diseases", sick_on_day_2), redirect_stdout(io.StringIO()) as screen:
            w.rest_days(game, 9)
        self.assertEqual(game["day"], 3)
        self.assertIn("先不休息了 (休息了 2 天)", screen.getvalue())

        game = new_test_game()
        game["supplies"]["食物"] = 8 * 2 + 3   # 4 个人每天吃 8 份, 第 3 天就不够了
        with no_new_diseases(), mock.patch.object(w, "roll_weather", lambda g: None), redirect_stdout(io.StringIO()):
            w.rest_days(game, 9)
        self.assertEqual(game["day"], 4)

        game = new_test_game()
        game["party"]["D"] = 1
        game["supplies"]["食物"] = 0   # D 第一天就饿死了
        with no_new_diseases(), redirect_stdout(io.StringIO()) as screen:
            w.rest_days(game, 9)
        self.assertNotIn("D", game["party"])
        self.assertEqual(game["day"], 2)

        game = new_test_game()
        game["supplies"]["食物"] = 0   # 一开始就在挨饿: 不算新出的事, 照样休息完
        game["short"] = ["食物"]
        with no_new_diseases(), redirect_stdout(io.StringIO()):
            w.rest_days(game, 3)
        self.assertEqual(game["day"], 4)

    def test_drop(self):
        """丢东西: 不花时间, 车变轻了, 记进日记; 没有的东西丢不了"""
        game = w.new_game()
        game["party"] = {"A": 100}
        game["supplies"]["燃料"] = 50
        answers = iter(["3", "20", "6", "0"])   # 丢 20 份燃料, 再选药品 (没有), 不丢了
        with real_car(), mock.patch("builtins.input", lambda p="": next(answers)), redirect_stdout(io.StringIO()) as screen:
            w.drop(game)
        self.assertEqual(game["supplies"]["燃料"], 30)
        self.assertEqual(w.load_of(game), 70000 + 30 * 8000)
        self.assertEqual(game["day"], 1)
        self.assertIn("扔掉了 20 份燃料, 车轻了 160 公斤", screen.getvalue())
        self.assertIn("车上没有药品", screen.getvalue())
        self.assertIn("扔掉了 20 份燃料。", game["diary"][-1])

    def test_full_car_suggests_dropping(self):
        game = w.new_game()
        game["party"] = {"A": 100}
        game["supplies"]["燃料"] = 116   # 70 + 928 = 998 公斤, 只装得下 4 份食物
        with real_car(), redirect_stdout(io.StringIO()) as screen:
            w.add_supplies(game, "食物", 10)
        self.assertIn("可以把用不上的东西丢掉", screen.getvalue())

    def test_status_shows_load(self):
        game = w.new_game()
        game["party"] = {"A": 100}
        game["supplies"]["燃料"] = 10
        screen = io.StringIO()
        with real_car(), redirect_stdout(screen):
            w.show_status(game)
            w.show_party(game)
        self.assertIn("载重: 150 公斤 / 1000 公斤", screen.getvalue())
        self.assertIn("人 70 公斤  物资 80 公斤", screen.getvalue())
        self.assertIn("最重的是燃料", screen.getvalue())

    def test_save_and_load(self):
        game = new_test_game()
        game["day"] = 12
        game["visited"] = ["锈铁镇"]
        game["dead"] = ["E"]
        with redirect_stdout(io.StringIO()):
            w.save_game(game)
            self.assertEqual(w.load_game(), game)

    def test_broken_save_starts_new_game(self):
        with open(w.SAVE_FILE, "w", encoding="utf-8") as f:
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
        # 主菜单选继续游戏, 休息一天 (饿死了), 按回车回到主菜单, 退出
        answers = iter(["2", "2", "1", "", "5"])
        with mock.patch("builtins.input", lambda p="": next(answers)), redirect_stdout(io.StringIO()):
            w.main()
        self.assertFalse(os.path.exists(w.SAVE_FILE))

    # ---------- 过河 ----------

    def cross(self, game, place, answers, depth):
        """在 place 这条河边, 按顺序回答 answers 过河; 河水深度固定是 depth (一个数, 或者每天一个的列表)。
        返回屏幕上的字"""
        depths = iter(depth if isinstance(depth, list) else [depth] * 100)
        keys = iter(answers)
        screen = io.StringIO()
        with mock.patch("builtins.input", lambda p="": next(keys)), \
                mock.patch.object(w, "river_depth", lambda game, place: next(depths)), \
                no_new_diseases(), redirect_stdout(screen):
            w.cross_river(game, place)
        return screen.getvalue()

    def test_rivers_are_landmarks(self):
        """要过的河都是路上的地标, 渡船的钱是正数 (没有渡船就是 None)"""
        landmarks = [name for name, _ in w.LANDMARKS.values()]
        for place, (river, width, depth, fare) in w.RIVERS.items():
            self.assertIn(place, landmarks)
            self.assertGreater(width, 0)
            self.assertGreater(depth, 0)
            self.assertTrue(fare is None or fare > 0)
        self.assertEqual(len(w.RIVER_SEASON), 12)

    def test_status_shows_river_ahead(self):
        game = new_test_game()
        screen = io.StringIO()
        with redirect_stdout(screen):
            w.show_status(game)
        self.assertIn("下一站: 堪萨斯河渡口 (要过河)", screen.getvalue())

    def test_drive_through_shallow_water(self):
        """水不比车能开过的深, 直接开过去什么事都没有, 也不花时间"""
        game = new_test_game()
        text = self.cross(game, "大蓝河", ["1"], w.CAR_WADE_DEPTH)
        self.assertIn("车稳稳地蹚过了大蓝河", text)
        self.assertEqual(game["supplies"]["食物"], 100)
        self.assertEqual(game["day"], 1)
        self.assertIn("直接开车过了大蓝河", game["diary"][-1])

    def test_engine_gets_wet(self):
        """水比车能开过的深一点: 发动机进水, 泡了水的食物要扔掉四分之一, 还要花一天晾干"""
        game = new_test_game()
        text = self.cross(game, "大蓝河", ["1"], 0.9)
        self.assertIn("发动机进水熄火了", text)
        self.assertEqual(game["day"], 2)
        self.assertEqual(game["supplies"]["食物"], 100 - 25 - 8)   # 扔掉 25 份, 晾车那天 4 个人又吃了 8 份

    def test_car_tips_over_in_deep_water(self):
        """水太深还硬开过去, 车会被冲翻: 东西被冲走, 掉进河里的人受辐射, 还可能有人被冲走"""
        game = new_test_game()
        with mock.patch.object(w.random, "random", lambda: 0), \
                mock.patch.object(w.random, "randint", lambda low, high: low):
            text = self.cross(game, "大蓝河", ["1"], 1.0)
        self.assertIn("【翻车】", text)
        for item in game["supplies"]:
            self.assertEqual(game["supplies"][item], 80)   # 每样东西都冲走了 20%
        self.assertEqual(len(game["party"]), 3)
        self.assertEqual(len(game["dead"]), 1)
        self.assertIn("被大蓝河的急流冲走了", text)
        for name in game["party"]:
            self.assertEqual(game["rads"][name], w.RIVER_RADS)
        self.assertIn("好不容易把车拖上了对岸", text)

    def test_float_across(self):
        """绑上空油桶浮过去: 水再深也能过, 可是有机会翻车, 水越深越容易翻"""
        game = new_test_game()
        with mock.patch.object(w.random, "random", lambda: 0.99):
            text = self.cross(game, "格林河", ["2"], 2.5)
        self.assertIn("车平平安安地漂到了对岸", text)
        self.assertEqual(game["supplies"]["食物"], 100)
        # 翻车的机会: 0.8 米深是 10%, 2 米深是 20%
        with mock.patch.object(w.random, "random", lambda: 0.15):
            self.assertNotIn("【翻车】", self.cross(new_test_game(), "格林河", ["2"], 0.8))
            self.assertIn("【翻车】", self.cross(new_test_game(), "格林河", ["2"], 2.0))

    def test_ferry(self):
        """坐渡船要花钱, 钱不够坐不了; 没有渡船的河不能选渡船"""
        game = new_test_game()
        game["money"] = 100
        with mock.patch.object(w, "FERRY_WAIT", 0):
            text = self.cross(game, "格林河", ["4"], 2.5)
        fare = w.RIVERS["格林河"][3]
        self.assertEqual(game["money"], 100 - fare)
        self.assertIn(f"花 {fare} 块钱坐渡船过了格林河", game["diary"][-1])
        self.assertIn("坐渡船", text)

        game = new_test_game()
        game["money"] = fare - 1
        with mock.patch.object(w.random, "random", lambda: 0.99):
            text = self.cross(game, "格林河", ["4", "2"], 2.5)   # 钱不够, 只好浮过去
        self.assertIn("你的钱不够", text)
        self.assertEqual(game["money"], fare - 1)

        game = new_test_game()
        text = self.cross(game, "大蓝河", ["4", "1"], 0.5)   # 大蓝河没有渡船, 只能选 1~3
        self.assertNotIn("坐渡船", text)
        self.assertIn("请输入 1 到 3 之间的数字", text)

    def test_ferry_queue_takes_days(self):
        game = new_test_game()
        with mock.patch.object(w.random, "randint", lambda low, high: high):
            text = self.cross(game, "堪萨斯河渡口", ["4"], 2.0)
        self.assertIn(f"等了 {w.FERRY_WAIT} 天才轮到", text)
        self.assertEqual(game["day"], 1 + w.FERRY_WAIT)

    def test_wait_for_water_to_go_down(self):
        """在河边等一天, 第二天水深会变"""
        game = new_test_game()
        text = self.cross(game, "大蓝河", ["3", "1"], [1.0, 0.5])
        self.assertIn("等了一天", text)
        self.assertIn("河水退了一些", text)
        self.assertIn("今天水深 0.5 米", text)
        self.assertEqual(game["day"], 2)
        self.assertIn("直接开车过了大蓝河", game["diary"][-1])

    def test_mechanic_snorkel(self):
        """有机械师的话, 车能开过更深的水"""
        self.assertEqual(w.wade_depth(new_test_game()), w.CAR_WADE_DEPTH)
        game = self.with_job("机械师")
        self.assertEqual(w.wade_depth(game), 0.9)
        text = self.cross(game, "蛇河渡口", ["1"], 0.9)
        self.assertIn("通气管", text)
        self.assertIn("车稳稳地蹚过了蛇河", text)

    def test_river_depth_follows_season_and_rain(self):
        """河水 5、6 月最深, 秋天浅; 这几天下了雨雪, 河水会涨"""
        game = new_test_game()
        with mock.patch.object(w.random, "uniform", lambda low, high: 1):
            game["start_month"] = 6
            self.assertEqual(w.river_depth(game, "格林河"), 2.2)   # 1.6 米 x 1.4
            game["start_month"] = 9
            self.assertEqual(w.river_depth(game, "格林河"), 1.1)   # 1.6 米 x 0.7
            game["start_month"] = 6
            game["rain"] = 3
            self.assertEqual(w.river_depth(game, "格林河"), 2.9)   # 再涨三成
        # 每天的天气会记下这几天下了多少雨雪
        game["rain"] = 2
        with redirect_stdout(io.StringIO()):
            w.roll_weather(game)
        wet = 1 if game["weather"] in w.WET_WEATHER else 0
        self.assertEqual(game["rain"], round(2 * w.RAIN_FADE + wet, 2))

    def test_river_lengths_in_feet(self):
        game = new_test_game()
        self.assertEqual(w.show_length(game, 1.2), "1.2 米")
        self.assertEqual(w.show_length(game, 190), "190 米")
        game["unit"] = "英里"
        self.assertEqual(w.show_length(game, 1.2), "3.9 英尺")
        self.assertEqual(w.show_length(game, 190), "623 英尺")

    def test_drive_to_river_then_cross(self):
        """赶路时开过河的位置, 就要过河; 过了以后不会再问"""
        game = new_test_game()
        game["distance"] = 100
        game["money"] = 100
        screen = io.StringIO()
        with mock.patch("builtins.input", lambda p="": "4" if "怎么过河" in p else "2"), \
                mock.patch.multiple(w, FERRY_WAIT=0, EVENT_CHANCE_PER_100KM=0, SMALL_EVENT_CHANCE_PER_100KM=0), redirect_stdout(screen):
            w.travel(game)
            w.check_places(game)
        self.assertEqual(screen.getvalue().count("来到了【堪萨斯河渡口】"), 1)
        self.assertEqual(screen.getvalue().count("交了"), 1)
        self.assertEqual(game["money"], 100 - w.RIVERS["堪萨斯河渡口"][3])
        self.assertGreater(game["distance"], 130)   # 过了河接着开完今天的路
        crossed = [line for line in game["diary"] if "坐渡船过了堪萨斯河" in line]
        self.assertIn("已走 130 公里", crossed[0])  # 日记里记的是河的位置

    # ---------- 最后一段路: 漂流还是走巴洛路 ----------

    def last_road(self, game, choice, lane="水道"):
        """在达尔斯选最后一段路 (choice 是 "1" 木筏 或 "2" 巴洛路)。过急流时选 lane ("水道" 或 "礁石") 那一边。
        返回屏幕上的字"""
        screen = io.StringIO()

        def answer(prompt=""):
            if "走哪条路" in prompt:
                return choice
            lanes = re.findall(r"左边(礁石|水道)  中间(礁石|水道)  右边(礁石|水道)", screen.getvalue())[-1]
            if lane not in lanes:   # 三条都是水道时, 想撞礁石也撞不上
                return "1"
            return str(lanes.index(lane) + 1)
        with mock.patch("builtins.input", answer), no_new_diseases(), redirect_stdout(screen):
            w.choose_last_road(game, 2861)
        return screen.getvalue()

    def test_barlow_road(self):
        """走巴洛路: 交过路费, 接着开车; 钱不够就只能坐木筏"""
        game = new_test_game()
        game["distance"] = 2900
        game["money"] = 50
        self.last_road(game, "2")
        self.assertEqual(game["money"], 50 - w.BARLOW_TOLL)
        self.assertEqual(game["distance"], 2900)
        self.assertEqual(game["day"], 1)
        self.assertIn("走巴洛路", game["diary"][-1])

        game = new_test_game()
        game["money"] = w.BARLOW_TOLL - 1
        text = self.last_road(game, "2")
        self.assertIn("钱不够交过路费", text)
        self.assertEqual(game["money"], w.BARLOW_TOLL - 1)
        self.assertEqual(game["distance"], w.TOTAL_DISTANCE)

    def test_raft_trip(self):
        """坐木筏: 不要钱、不用燃料, 扎木筏一天、漂一夜, 急流都躲开就什么都不丢, 直接到终点"""
        game = new_test_game()
        game["distance"] = 2900
        text = self.last_road(game, "1")
        self.assertEqual(text.count("【急流】"), w.RAPIDS)
        self.assertNotIn("撞上了礁石", text)
        self.assertEqual(game["distance"], w.TOTAL_DISTANCE)
        self.assertEqual(game["day"], 3)                         # 扎木筏 1 天, 晚上靠岸 1 夜
        self.assertEqual(game["supplies"]["燃料"], 100)
        self.assertEqual(game["supplies"]["零件"], 100)
        self.assertIn("已走 2861 公里: 在达尔斯扎了一个木筏", game["diary"][0])
        self.assertIn("坐木筏顺着哥伦比亚河漂到了俄勒冈城", game["diary"][-1])

    def test_rapids_hit_rocks(self):
        """急流里选了有礁石的那边: 东西掉进河里, 有人撞伤 (或者被冲走)"""
        game = new_test_game()
        with mock.patch.object(w, "RAPID_HIT_DROWN", 0):
            text = self.last_road(game, "1", lane="礁石")
        self.assertIn("撞上了礁石", text)
        self.assertIn("掉进河里冲走了", text)
        self.assertEqual(len(game["party"]), 4)
        self.assertLess(sum(game["supplies"].values()), 800)
        self.assertTrue(any(game["rads"].get(name, 0) >= w.RIVER_RADS for name in game["party"]))

        game = new_test_game()
        with mock.patch.object(w, "RAPID_HIT_DROWN", 1), redirect_stdout(io.StringIO()):
            w.hit_rock(game)
        self.assertEqual(len(game["party"]), 3)
        self.assertIn("被急流冲走了", game["diary"][-2])

    def test_rapids_too_slow(self):
        """选对了水道但太慢: 一半机会还是撞上礁石"""
        for luck, crashed in [(0.1, True), (0.9, False)]:
            game = new_test_game()
            screen = io.StringIO()
            with mock.patch.object(w.time, "time", side_effect=[0, w.RAPID_SECONDS + 1]), \
                    mock.patch.object(w.random, "random", lambda: luck), \
                    mock.patch.object(w.random, "randint", lambda low, high: low), \
                    mock.patch.object(w.random, "sample", lambda items, n: list(items)[:n]), \
                    mock.patch("builtins.input", lambda p="": "1"), redirect_stdout(screen):
                w.shoot_rapid(game, 1)   # 左边一定是水道 (sample 取前几个)
            self.assertIn("太慢了" if crashed else "有点慢", screen.getvalue())
            self.assertEqual("撞了上去" in screen.getvalue(), crashed)

    def test_rapid_picture_lines_up(self):
        for art in w.ROCK_ART + w.WATER_ART:
            self.assertEqual(len(art), 8)

    def test_no_events_after_arriving(self):
        """开到终点那天, 不会再遇到路上的事件"""
        game = new_test_game()
        game["distance"] = w.TOTAL_DISTANCE - 10
        game["visited"] = [name for name, _ in list(w.OUTPOSTS.values()) + list(w.LANDMARKS.values())] + \
                          [spot[2] for spot in w.HOTSPOTS]
        screen = io.StringIO()
        with mock.patch.object(w, "EVENT_CHANCE_PER_100KM", 1000), redirect_stdout(screen):
            w.travel(game)
        self.assertEqual(game["distance"], w.TOTAL_DISTANCE)
        self.assertNotIn("【", screen.getvalue())

    # ---------- 得分和最高分 ----------

    def test_score(self):
        """活下来的人按健康给分, 剩下的物资和钱也换成分"""
        game = w.new_game()
        game["party"] = {"A": 100, "B": 50, "C": 10}   # 良好 500、一般 400、危险 200
        game["supplies"].update({"食物": 60, "燃料": 12, "子弹": 30, "零件": 1, "药品": 2})
        game["money"] = 23
        total, lines = w.score_of(game)
        # 人 1100 + 食物 2 + 燃料 2 + 子弹 0 + 零件 2 + 药品 4 + 钱 4
        self.assertEqual(total, 1100 + 2 + 2 + 2 + 4 + 4)
        self.assertIn("B 健康一般: 400 分", lines)
        self.assertIn("剩下 23 块钱: 4 分", lines)
        self.assertFalse(any("子弹" in line for line in lines))   # 不够 1 分的不写
        game["seeds"] = True
        self.assertEqual(w.score_of(game)[0], total + w.SCORE_SEEDS)

    def finish(self, score, name="A"):
        """假装一局到达终点得了 score 分, 返回屏幕上的字"""
        game = w.new_game()
        game["leader"] = name
        game["party"] = {name: 100}
        game["day"] = 41
        screen = io.StringIO()
        with mock.patch.object(w, "score_of", lambda game: (score, [])), redirect_stdout(screen):
            w.record_score(game, "独行结局")
        return screen.getvalue()

    def test_high_scores(self):
        """最高分榜只记前 10 名, 从高到低; 分数一样时先得到的在前面"""
        self.assertIn("进了最高分榜, 第 1 名", self.finish(500, "第一局"))
        for i in range(10):
            self.finish(1000 + i * 100, f"玩家{i}")
        self.assertIn("第 1 名", self.finish(5000, "高手"))
        text = self.finish(100, "新手")
        self.assertIn("没能进前 10 名", text)
        self.assertIn("第 4 名", self.finish(1800, "后来的"))   # 前面有 5000、1900, 还有先得到 1800 分的玩家8
        scores = w.load_high_scores()
        self.assertEqual(len(scores), w.HIGH_SCORES)
        self.assertEqual([e["score"] for e in scores], sorted([e["score"] for e in scores], reverse=True))
        self.assertEqual(scores[0], {"name": "高手", "score": 5000, "ending": "独行结局", "days": 40, "survivors": 1,
                                     "difficulty": "普通"})
        self.assertEqual([e["name"] for e in scores[2:4]], ["玩家8", "后来的"])
        self.assertNotIn("第一局", [e["name"] for e in scores])

        screen = io.StringIO()
        with redirect_stdout(screen):
            w.show_high_scores()
        self.assertIn(" 1.  5000 分  高手  普通  独行结局, 用了 40 天, 1 个人到达", screen.getvalue())

    def test_broken_high_score_file(self):
        """最高分文件坏了 (或者是别的东西), 当成空的, 不能报错"""
        for content in ["坏掉的文件", "{}", '[1, {"name": "x"}]']:
            with open(w.HIGH_SCORE_FILE, "w", encoding="utf-8") as f:
                f.write(content)
            self.assertEqual(w.load_high_scores(), [])
            self.assertIn("第 1 名", self.finish(300))

    def test_score_after_arriving(self):
        """一局走到终点, 回顾完日记就算分、记进最高分榜; 全军覆没不算分"""
        game = new_test_game()
        game["leader"] = "A"
        game["distance"] = w.TOTAL_DISTANCE
        game["day"] = 30
        screen = io.StringIO()
        with mock.patch("builtins.input", lambda p="": ""), redirect_stdout(screen):
            w.play(game)
        text = screen.getvalue()
        self.assertLess(text.index("旅行日记"), text.index("========== 得分"))
        self.assertIn("完美结局", w.load_high_scores()[0]["ending"])
        self.assertEqual(w.load_high_scores()[0]["days"], 29)

        game = new_test_game()
        game["party"] = {}
        screen = io.StringIO()
        with mock.patch("builtins.input", lambda p="": ""), redirect_stdout(screen):
            w.play(game)
        self.assertNotIn("得分", screen.getvalue())
        self.assertEqual(len(w.load_high_scores()), 1)

    # ---------- 难度 ----------

    def test_choose_difficulty(self):
        """开局先选难度, 一开始的钱跟着难度变: 越难钱越少"""
        for choice in [1, 2, 3]:
            with self.subTest(choice=choice):
                answers = iter([str(choice), "1", "小明", "1", "5", "0"])   # 难度、公里、名字、男、5 月出发、不买东西
                game = w.new_game()
                screen = io.StringIO()
                with mock.patch("builtins.input", lambda p="": next(answers)), redirect_stdout(screen):
                    w.setup(game)
                self.assertEqual(game["difficulty"], choice)
                self.assertEqual(game["money"], w.DIFFICULTIES[choice][1])
                self.assertIn("3. 困难: 一开始有 370 块钱", screen.getvalue())
        self.assertGreater(w.DIFFICULTIES[1][1], w.DIFFICULTIES[2][1])
        self.assertGreater(w.DIFFICULTIES[2][1], w.DIFFICULTIES[3][1])
        self.assertEqual(w.DIFFICULTIES[2][1:5], (500, 100, 100, 100))   # 普通就是没有难度选择以前的样子

    def test_difficulty_changes_luck(self):
        """难度越高, 路上越容易出事, 也越容易生病"""
        def events_and_sickness(difficulty, event_roll, sick_roll):
            game = new_test_game()
            game["difficulty"] = difficulty
            events, sick = [], []
            with mock.patch.object(w, "EVENTS", [lambda game: events.append(1)]), \
                    mock.patch.object(w.random, "random", lambda: event_roll):
                w.random_event(game, 100)   # 普通难度: 开 100 公里有 35% 的机会出事
            with mock.patch.object(w, "get_sick", lambda game, name, disease: sick.append(name)), \
                    mock.patch.object(w.random, "random", lambda: sick_roll):
                w.catch_diseases(game, False, [], False)   # 普通难度: 满血的人每天有 1% 的机会生病
            return bool(events), len(sick)
        self.assertEqual([events_and_sickness(d, 0.3, 0.009) for d in [1, 2, 3]], [(False, 0), (True, 4), (True, 4)])
        self.assertEqual([events_and_sickness(d, 0.4, 0.012) for d in [1, 2, 3]], [(False, 0), (False, 0), (True, 4)])

    def test_score_by_difficulty(self):
        """得分最后按难度乘: 简单 ×0.5, 普通不变, 困难 ×1.5"""
        game = w.new_game()
        game["party"] = {"A": 100}   # 良好 500 分, 没有别的东西
        game["money"] = 0
        results = []
        for difficulty in [1, 2, 3]:
            game["difficulty"] = difficulty
            results.append(w.score_of(game))
        self.assertEqual([total for total, _ in results], [250, 500, 750])
        self.assertIn("困难难度: 得分 ×1.5", results[2][1])
        self.assertFalse(any("难度" in line for line in results[1][1]))

    def test_high_scores_show_difficulty(self):
        """最高分榜记着难度; 以前没有难度时的成绩算普通"""
        with open(w.HIGH_SCORE_FILE, "w", encoding="utf-8") as f:
            json.dump([{"name": "老玩家", "score": 1800, "ending": "完美结局", "days": 40, "survivors": 4}],
                      f, ensure_ascii=False)
        game = w.new_game()
        game["leader"] = "新玩家"
        game["party"] = {"新玩家": 100}
        game["difficulty"] = 3
        game["money"] = 0
        game["day"] = 41
        screen = io.StringIO()
        with redirect_stdout(screen):
            w.record_score(game, "独行结局")
        self.assertIn("1800 分  老玩家  普通  完美结局", screen.getvalue())
        self.assertIn("750 分  新玩家  困难  独行结局", screen.getvalue())
        self.assertEqual(w.load_high_scores()[1]["difficulty"], "困难")

    # ---------- 颜色和进度条 ----------

    def test_colored(self):
        """在终端和网页版里上色, 跑测试 (不是终端) 或者设置里关掉了就不上色"""
        self.assertEqual(w.colored("危险", "红"), "危险")
        with mock.patch.object(w, "IN_BROWSER", True):
            self.assertEqual(w.colored("危险", "红"), "\x1b[31m危险\x1b[0m")
            self.assertEqual(w.colored("总分", "黄", bold=True), "\x1b[33;1m总分\x1b[0m")
            self.assertEqual(w.colored("晴", None), "晴")
            with mock.patch.object(w, "COLOR", False):
                self.assertEqual(w.colored("危险", "红"), "危险")

    def test_colors_do_not_change_the_words(self):
        """开了颜色, 去掉颜色的控制字符以后, 屏幕上的字跟没颜色时一模一样"""
        def screen_text():
            game = new_test_game()
            game["rads"] = {"B": 60}
            game["sick"] = {"C": ["痢疾", 3]}
            game["party"]["D"] = 30
            game["weather"] = "辐射风暴"
            random.seed(1)   # 两次过急流, 礁石的位置要一样
            screen = io.StringIO()
            # 只比较字: 网页版里还会画头像这些画面、会清屏换画面, 先关掉
            with redirect_stdout(screen), mock.patch("builtins.input", lambda p="": "1"), \
                    mock.patch.object(w, "ANIMATION", False), mock.patch.object(w, "SCREENS", False):
                w.show_status(game)
                w.show_party(game)
                w.title_screen()
                w.shoot_rapid(game, 1)
            return screen.getvalue()
        plain = screen_text()
        with mock.patch.object(w, "IN_BROWSER", True):
            fancy = screen_text()
        self.assertNotIn("\x1b", plain)
        self.assertIn("\x1b[", fancy)
        self.assertEqual(re.sub(r"\x1b\[[\d;]*m", "", fancy), plain)

    def test_progress_bars(self):
        self.assertEqual(w.progress_bar(0, 100, 10), "[..........]")
        self.assertEqual(w.progress_bar(72, 100, 10), "[#######...]")
        self.assertEqual(w.progress_bar(150, 100, 4), "[####]")
        game = new_test_game()
        game["distance"] = w.TOTAL_DISTANCE // 2
        game["party"]["B"] = 55
        screen = io.StringIO()
        with redirect_stdout(screen):
            w.show_status(game)
        self.assertIn("路程: [##########..........] 49%", screen.getvalue())
        self.assertIn("  [######....] B 一般(55)", screen.getvalue())

    # ---------- 过场动画 ----------

    def test_scene_frames(self):
        """每一帧行数一样、每行一样宽 (窄终端也放得下), 车一直在; 背景会动, 开得越快动得越多"""
        frames = [w.road_scene(frame, 2) for frame in range(w.ANIMATION_FRAMES)]
        for rows in frames:
            self.assertEqual(len(rows), len(frames[0]))
            self.assertEqual({len(row) for row in rows}, {w.SCENE_WIDTH})
            self.assertLess(w.SCENE_WIDTH, 80)
            self.assertIn("(@)", "\n".join(rows))
        self.assertNotEqual(frames[0], frames[1])
        self.assertNotEqual(w.road_scene(5, 1), w.road_scene(5, 3))

    def test_animation_plays_in_terminal(self):
        """在真正的终端里: 一帧一帧画, 每次把光标移回画面顶上盖掉上一帧; 先藏光标, 最后显示回来"""
        screen = io.StringIO()
        with mock.patch.object(w, "can_read_keys", lambda: True), \
                mock.patch.object(w, "enable_ansi", lambda: None), \
                mock.patch.object(w.time, "sleep", lambda seconds: None), redirect_stdout(screen):
            w.drive_animation(w.new_game())
        text = screen.getvalue()
        height = len(w.road_scene(0, 2))
        self.assertEqual(text.count(f"\x1b[{height}A"), w.ANIMATION_FRAMES - 1)
        self.assertTrue(text.startswith("\x1b[?25l"))
        self.assertTrue(text.endswith("\x1b[?25h"))

    def test_animation_plays_in_browser(self):
        """网页版里不是「真正的终端」, 但网页能处理光标上移, 所以也播动画"""
        screen = io.StringIO()
        with mock.patch.object(w, "IN_BROWSER", True), mock.patch.object(w.time, "sleep", lambda seconds: None), \
                redirect_stdout(screen):
            w.drive_animation(w.new_game())
        self.assertIn("(@)", screen.getvalue())

    def test_no_animation_when_not_in_terminal_or_turned_off(self):
        """跑测试 (不是真正的终端) 时赶路不播动画; 设置里关掉了, 在终端里也不播"""
        game = new_test_game()
        screen = io.StringIO()
        with mock.patch("builtins.input", lambda p="": "2"), redirect_stdout(screen):
            w.travel(game)
        self.assertNotIn("\x1b", screen.getvalue())
        self.assertGreater(game["distance"], 0)
        # 这里只测动画本身: 假装在终端里的时候要是去赶路, 路上的事件会去读真的键盘, 测试就卡住了
        screen = io.StringIO()
        with mock.patch.object(w, "can_read_keys", lambda: True), mock.patch.object(w, "ANIMATION", False), \
                redirect_stdout(screen):
            w.drive_animation(game)
        self.assertEqual(screen.getvalue(), "")

    def test_car_shows_people(self):
        """车窗里能看到车上有几个人"""
        for people in range(1, w.MAX_PARTY + 1):
            self.assertEqual(w.car_art(people)[1].count("o"), people)
        self.assertEqual({len(line) for line in w.car_art(4)}, {len(w.CAR_ART[0])})

    def check_frames(self, frames):
        """每一帧行数一样、每行一样宽, 只用英文字符 (中文在终端里占两格, 会对不齐)"""
        self.assertGreater(len(frames), 5)
        for rows in frames:
            self.assertEqual(len(rows), w.SCENE_HEIGHT)
            self.assertEqual({len(row) for row in rows}, {w.SCENE_WIDTH})
            self.assertTrue("".join(rows).isascii())

    def test_weather_in_animation(self):
        """赶路动画跟着天气变: 每种坏天气的画面都跟晴天不一样, 雨雪会动; 暴风雪里车停着, 背景不动"""
        for weather in w.WEATHER:
            with self.subTest(weather=weather):
                frames = [w.road_scene(frame, 2, weather, 3) for frame in range(w.ANIMATION_FRAMES)]
                self.check_frames(frames)
                if weather not in ["晴"]:
                    self.assertNotEqual(frames[4], w.road_scene(4, 2, "晴", 3))
                if weather in w.WEATHER_ART and w.WEATHER_ART[weather][0] != "云":
                    self.assertNotEqual(frames[2][3], frames[3][3])
        stuck = [w.road_scene(frame, 0, "灰色暴风雪", 2) for frame in range(3)]
        self.assertEqual(stuck[0][-1], stuck[1][-1])   # 路面没动
        self.assertNotEqual(stuck[0], stuck[1])        # 雪在动

    def test_river_animation_frames(self):
        """过河动画: 平安过去的车最后停在西岸上; 出事的车停在河中间; 翻了的车轮子朝天"""
        for how, result in [("开", "过去了"), ("开", "进水"), ("开", "翻车"), ("浮", "过去了"), ("浮", "翻车"),
                            ("渡船", "过去了")]:
            with self.subTest(how=how, result=result):
                frames = w.river_frames(how, result, 2)
                self.check_frames(frames)
                last = "\n".join(frames[-1])
                self.assertIn("(@)", last)
                if result != "翻车":
                    self.assertIn("o o", last)   # 车窗里的两个人
                else:
                    self.assertNotIn("o o", last)
        ford = w.river_frames("开", "过去了", 1)[-1]
        self.assertIn("(@)", ford[7][:12])   # 停在西岸上

    def test_raft_animation_frames(self):
        frames = [w.raft_scene(frame, 4) for frame in range(w.ANIMATION_FRAMES)]
        self.check_frames(frames)
        self.assertIn(w.RAFT, "\n".join(frames[0]))
        self.assertNotEqual(frames[0], frames[1])

    def test_pictures(self):
        """每个据点、每个不用过河的地标都有一幅画; 画都不超过画面的宽度, 只用英文字符"""
        places = [name for name, _ in list(w.LANDMARKS.values()) + list(w.OUTPOSTS.values()) if name not in w.RIVERS]
        self.assertEqual(sorted(w.PICTURES), sorted(places))
        arts = [art for art, _ in w.PICTURES.values()]
        arts += [w.HOTSPOT_SIGN, w.TOMBSTONE, w.CITY_ART, w.FIELD_ART, w.WIPEOUT_ART]
        for art in arts:
            self.assertTrue(art and all(line.isascii() and len(line) <= w.SCENE_WIDTH for line in art))
        for color in [color for _, color in w.PICTURES.values()]:
            self.assertIn(color, list(w.COLORS) + [None])

    def test_portraits(self):
        """每个职业、主角的两种性别、路上的陌生人都有自己的样子, 一样高, 放得进头像那一栏"""
        self.assertEqual(sorted(w.PORTRAITS), sorted(list(w.SKILLS) + ["男", "女", "陌生人"]))
        for art in w.PORTRAITS.values():
            self.assertEqual(len(art), 5)
            self.assertTrue(all(line.isascii() and len(line) < w.PORTRAIT_WIDTH for line in art))
        game = new_test_game()
        game["leader"], game["gender"], game["jobs"] = "A", "女", {"B": "医生"}
        self.assertEqual(w.portrait_of(game, "A"), w.PORTRAITS["女"])
        self.assertEqual(w.portrait_of(game, "B"), w.PORTRAITS["医生"])
        self.assertEqual(w.portrait_of(game, "C"), w.PORTRAITS["陌生人"])

    def test_words_beside_pictures(self):
        """画在左边、字在右边: 每行的字都从同一列开始"""
        rows = w.beside(w.PORTRAITS["男"], ["小明 (主角)", "", "特长"], width=w.PORTRAIT_WIDTH)
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[0][w.PORTRAIT_WIDTH:], "小明 (主角)")
        self.assertEqual(rows[2][w.PORTRAIT_WIDTH:], "特长")
        self.assertEqual(rows[1], w.PORTRAITS["男"][1])

    def test_wrap_text_by_screen_width(self):
        """中文占两格: 按终端里的宽度切行, 头像旁边的字不会长到自动换行、把画挤歪"""
        self.assertEqual(w.text_width("A 健康 90"), 9)
        lines = w.wrap_text("特长: 用药一次能恢复 60 点健康 (平时是 35); 有医生照顾, 别人生病受伤好得更快", 20)
        self.assertGreater(len(lines), 1)
        self.assertTrue(all(w.text_width(line) <= 20 for line in lines))
        self.assertEqual("".join(lines), "特长: 用药一次能恢复 60 点健康 (平时是 35); 有医生照顾, 别人生病受伤好得更快")

    def test_party_view_fits_beside_portraits(self):
        """查看队伍时 (开着动画), 头像右边的每一行都不会超出画面的宽度"""
        game = new_test_game()
        game["leader"], game["jobs"] = "A", {"B": "医生", "C": "猎人"}
        game["sick"] = {"C": ["痢疾", 3]}
        game["rads"] = {"B": 60}
        screen = io.StringIO()
        with mock.patch.object(w, "can_animate", lambda: True), redirect_stdout(screen):
            w.show_party(game)
        party = screen.getvalue().split("队伍整体")[0]
        self.assertTrue(all(w.text_width(line) <= w.SCENE_WIDTH for line in party.split("\n")))
        self.assertIn("特长: 打猎得到的肉多一半", party)

    def test_pictures_only_when_animating(self):
        """画面跟动画一样, 只在终端和网页版里显示; 跑测试或者设置里关掉了动画就不显示"""
        screen = io.StringIO()
        with redirect_stdout(screen):
            w.show_picture(w.TOMBSTONE, "灰", ["", "这里长眠着 A"])
        self.assertEqual(screen.getvalue(), "")
        with mock.patch.object(w, "IN_BROWSER", True), mock.patch.object(w.time, "sleep", lambda seconds: None):
            with redirect_stdout(screen):
                w.show_picture(w.TOMBSTONE, "灰", ["", "这里长眠着 A"])
            self.assertIn("R.I.P", screen.getvalue())
            self.assertIn("这里长眠着 A", screen.getvalue())
            screen = io.StringIO()
            with mock.patch.object(w, "ANIMATION", False), redirect_stdout(screen):
                w.show_picture(w.TOMBSTONE)
            self.assertEqual(screen.getvalue(), "")

    def test_pictures_and_animations_in_the_game(self):
        """开着动画玩: 到了据点有画、过河有动画、有人去世有墓碑、查看队伍有头像, 全军覆没也有画面"""
        game = new_test_game()
        game["leader"] = "A"
        game["distance"] = 515   # 刚过卡尼堡
        game["visited"] = [name for km, (name, _) in w.LANDMARKS.items() if km < 510]
        screen = io.StringIO()
        with mock.patch.object(w, "can_animate", lambda: True), mock.patch.object(w.time, "sleep", lambda s: None), \
                mock.patch("builtins.input", lambda p="": "2"), redirect_stdout(screen):
            w.check_places(game)                          # 卡尼堡: 不带人、不买东西
            w.ford_river(game, "大蓝河", 0.1)              # 水很浅, 直接开过去
            w.show_party(game)
            w.lose_member(game, "B", "死于痢疾。")
        text = screen.getvalue()
        self.assertIn("FORT KEARNY", text)
        self.assertIn(f"\x1b[{w.SCENE_HEIGHT}A", text)   # 过河动画一帧一帧盖掉上一帧
        self.assertIn("这里长眠着 B", text)
        self.assertIn(w.PORTRAITS["陌生人"][2], text)
        game["party"] = {}
        screen = io.StringIO()
        with mock.patch.object(w, "can_animate", lambda: True), mock.patch.object(w.time, "sleep", lambda s: None), \
                mock.patch("builtins.input", lambda p="": ""), redirect_stdout(screen):
            w.play(game)
        self.assertIn(w.WIPEOUT_ART[0], screen.getvalue())

    def test_planner_plays_with_animations(self):
        """开着所有动画和画面玩完几局, 不能报错"""
        from tests.balance import play_one
        with real_car(), mock.patch.object(w, "can_animate", lambda: True), \
                mock.patch.object(w.time, "sleep", lambda seconds: None):
            for seed in range(20):
                with self.subTest(seed=seed):
                    text = play_one(seed)
                    self.assertTrue("一共用了" in text or "全军覆没" in text)

    # ---------- 音乐 ----------

    def test_music_files(self):
        """每一首都在 music 文件夹里, 是能放的 .wav; 背景音乐长一些, 一小段的不能太长"""
        import wave
        for name, (file, how) in w.MUSIC_TRACKS.items():
            with self.subTest(name=name):
                self.assertIn(how, ["循环", "一段", "结尾"])
                with wave.open(os.path.join(w.MUSIC_FOLDER, file)) as f:
                    seconds = f.getnframes() / f.getframerate()
                if how == "循环":
                    self.assertTrue(15 <= seconds <= 60)
                else:
                    self.assertTrue(1 <= seconds <= 12)

    def test_music_files_match_the_maker(self):
        """music 文件夹里的音乐, 跟 make_music.py 现在做出来的一模一样 (改了音符要记得重新做)"""
        import importlib.util
        spec = importlib.util.spec_from_file_location("make_music", os.path.join(w.MUSIC_FOLDER, "make_music.py"))
        maker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(maker)
        with tempfile.TemporaryDirectory() as tmp:
            maker.make_all(tmp)
            for file, _ in w.MUSIC_TRACKS.values():
                with open(os.path.join(tmp, file), "rb") as made, open(os.path.join(w.MUSIC_FOLDER, file), "rb") as kept:
                    self.assertEqual(made.read(), kept.read(), file)

    def music_calls(self):
        """假装能放音乐, 记下每次换成了什么播放列表"""
        calls = []
        return calls, mock.patch.multiple(w, can_play_music=lambda: True, start_playing=calls.append), \
            mock.patch.dict(w.music_now, {"background": None, "turn": 0, "process": None})

    def test_play_music(self):
        """背景音乐一直循环, 已经在放就不重来; 一小段放完接着放背景音乐; 结尾的放完就安静了"""
        calls, fake, state = self.music_calls()
        with fake, state:
            w.play_music("主菜单")
            w.play_music("主菜单")
            w.play_music("赶路")
            w.play_music("去世")
            w.play_music("到达")
            w.play_music("热点")
            w.stop_music()
        self.assertEqual(calls, [[("title.wav", True)], [("travel.wav", True)],
                                 [("taps.wav", False), ("travel.wav", True)], [("arrive.wav", False)],
                                 [("geiger.wav", False)], []])

    def test_no_music_when_not_in_terminal_or_turned_off(self):
        calls = []
        with mock.patch.object(w, "start_playing", calls.append):
            w.play_music("主菜单")                      # 跑测试时不是真正的终端
            with mock.patch.object(w, "IN_BROWSER", True), mock.patch.object(w, "MUSIC", False):
                w.play_music("主菜单")                  # 设置里关掉了
        self.assertEqual(calls, [])

    def test_music_in_the_game(self):
        """主菜单、开始赶路、到了据点、开进热点、有人去世、到达终点、全军覆没, 都换上对应的音乐"""
        calls, fake, state = self.music_calls()
        with fake, state, redirect_stdout(io.StringIO()):
            game = new_test_game()
            game["leader"] = "A"
            w.play_music("赶路")
            game["distance"] = w.HOTSPOTS[0][0]
            game["visited"] = [name for km, (name, _) in list(w.LANDMARKS.items()) + list(w.OUTPOSTS.items())
                               if km <= w.HOTSPOTS[0][0]]
            w.check_places(game)                         # 开进辐射热点
            w.lose_member(game, "B", "死于痢疾。")
            with mock.patch("builtins.input", lambda p="": "2"):
                game["distance"] = 999
                w.check_places(game)                     # 拉勒米堡 (不带人、不买东西)
            game["distance"] = w.TOTAL_DISTANCE
            w.arrive(game)
            for name in ["A", "C", "D"]:
                w.lose_member(game, name, "去世了。")    # 最后一个人没了的时候不放熄灯号
            with mock.patch("builtins.input", lambda p="": ""):
                w.play(game)
        files = [playlist[0][0] if playlist else None for playlist in calls]
        self.assertEqual(files, ["travel.wav", "geiger.wav", "taps.wav", "outpost.wav", "arrive.wav",
                                 "taps.wav", "taps.wav", "travel.wav", "game_over.wav"])   # 开始玩 (赶路), 发现全军覆没
        screen = io.StringIO()
        calls.clear()
        with fake, state, mock.patch("builtins.input", lambda p="": "5"), redirect_stdout(screen):
            w.main()                                     # 主菜单, 直接退出
        self.assertEqual(calls, [[("title.wav", True)], []])

    def test_music_thread_plays_one_after_another(self):
        """一段放一遍, 再循环放背景音乐, 直到换了音乐"""
        played = []

        def fake_play(path, turn):
            played.append(os.path.basename(path))
            if len(played) == 4:
                w.music_now["turn"] += 1   # 换音乐了
            return True
        with mock.patch.object(w, "play_file", fake_play), mock.patch.dict(w.music_now, {"turn": 7}):
            w.music_thread([("taps.wav", False), ("travel.wav", True)], 7)
        self.assertEqual(played, ["taps.wav", "travel.wav", "travel.wav", "travel.wav"])

    def test_music_player_is_stopped(self):
        """Mac 和 Linux: 用播放器放音乐, 换音乐或者关游戏时要把播放器关掉, 不然游戏关了还在响"""
        waiting = [sys.executable, "-c", "import time; time.sleep(30)"]   # 假播放器: 什么都不放, 等 30 秒
        with mock.patch.object(w, "music_player", lambda: waiting), mock.patch.object(w, "winsound", None), \
                mock.patch.dict(w.music_now, {"background": None, "turn": 0, "process": None}):
            w.start_playing([("title.wav", True)])
            for _ in range(200):
                if w.music_now["process"]:
                    break
                time.sleep(0.01)
            process = w.music_now["process"]
            self.assertIsNone(process.poll())   # 还在放
            w.stop_music()
            process.wait(timeout=5)
            self.assertIsNotNone(process.poll())

    def test_music_on_windows(self):
        """Windows: 用自带的 winsound 放, 换音乐时先停下 (这台电脑上没有 winsound, 用一个假的代替)"""
        calls = []

        class FakeWinsound:
            SND_FILENAME, SND_ASYNC = 1, 2

            @staticmethod
            def PlaySound(path, flags):
                calls.append((path and os.path.basename(path), flags))
        with mock.patch.object(w, "winsound", FakeWinsound), mock.patch.object(w, "sound_length", lambda path: 0.01), \
                mock.patch.dict(w.music_now, {"background": None, "turn": 3, "process": None}):
            w.music_thread([("outpost.wav", False)], 3)
            w.stop_music()
        self.assertEqual(calls, [("outpost.wav", 3), (None, 0)])

    def test_broken_music_player_is_not_restarted(self):
        """播放器一启动就失败 (比如电脑上没有声音设备): 不再一遍一遍地重新开它"""
        import threading
        failing = [sys.executable, "-c", "import sys; sys.exit(1)"]   # 假播放器: 一开就失败
        started = []
        real_popen = w.subprocess.Popen

        def counting_popen(*args, **kwargs):
            started.append(1)
            return real_popen(*args, **kwargs)
        with mock.patch.object(w, "music_player", lambda: failing), mock.patch.object(w, "winsound", None), \
                mock.patch.object(w.subprocess, "Popen", counting_popen), \
                mock.patch.dict(w.music_now, {"background": None, "turn": 5, "process": None}):
            thread = threading.Thread(target=w.music_thread, args=([("title.wav", True)], 5))
            thread.start()
            thread.join(10)
            still_running = thread.is_alive()
            w.music_now["turn"] += 1   # 万一还在转, 让它停下
        self.assertFalse(still_running)
        self.assertEqual(len(started), 1)

    def test_music_problems_do_not_print_errors(self):
        """放不了音乐 (Windows 上没有声音设备、音乐文件坏了) 时悄悄不放, 不在游戏画面上印出报错"""
        class NoSoundCard:
            SND_FILENAME, SND_ASYNC = 1, 2

            @staticmethod
            def PlaySound(path, flags):
                raise RuntimeError("Failed to play sound")
        real_folder = w.MUSIC_FOLDER
        with tempfile.TemporaryDirectory() as tmp:
            broken = os.path.join(tmp, "broken.wav")
            with open(broken, "wb") as f:
                f.write(b"not a wav file")
            screen, errors = io.StringIO(), io.StringIO()
            with mock.patch.object(w, "winsound", NoSoundCard), \
                    mock.patch.dict(w.music_now, {"background": None, "turn": 1, "process": None}), \
                    redirect_stdout(screen), mock.patch("sys.stderr", errors):
                self.assertFalse(w.play_file(broken, 1))                               # 文件坏了
                self.assertFalse(w.play_file(os.path.join(tmp, "missing.wav"), 1))   # 没有这个文件
                self.assertFalse(w.play_file(os.path.join(real_folder, "title.wav"), 1))   # 好好的文件, 可是没有声音设备
                with mock.patch.object(w, "MUSIC_FOLDER", tmp):
                    w.music_thread([("broken.wav", True)], 1)
                w.music_thread([("title.wav", True)], 1)
                w.start_playing([])
        self.assertEqual(screen.getvalue() + errors.getvalue(), "")

    def test_no_drowning_on_easy(self):
        """简单难度: 过河翻车、木筏撞上礁石都不会有人被冲走 (普通难度会)"""
        for difficulty, lost in [(1, False), (2, True)]:
            with self.subTest(difficulty=difficulty):
                game = new_test_game()
                game["difficulty"] = difficulty
                with mock.patch.multiple(w, DROWN_CHANCE=1, RAPID_HIT_DROWN=1), redirect_stdout(io.StringIO()) as screen:
                    w.capsize(game, "堪萨斯河渡口", "直接开车过河")
                    w.hit_rock(game)
                self.assertEqual(len(game["party"]) < 4, lost)
                if not lost:
                    self.assertIn("差点被急流冲走", screen.getvalue())

    def test_difficulty_changes_every_kind_of_sickness(self):
        """难度也影响喝脏水生病、伤口感染、破伤风, 不只是平常生病"""
        game = new_test_game()
        game["difficulty"] = 3
        self.assertAlmostEqual(w.sick_odds(game, 0.1), 0.14)   # 困难: 多四成
        game["difficulty"] = 1
        self.assertAlmostEqual(w.sick_odds(game, 0.1), 0.04)   # 简单: 只有四成
        sick = {}
        for difficulty in [1, 2, 3]:   # 没水喝, 只能喝脏水: 普通难度 15% 的机会病倒
            game = new_test_game()
            game["difficulty"] = difficulty
            game["supplies"]["水"] = 0
            with mock.patch.object(w, "catch_diseases", lambda *args: None), \
                    mock.patch.object(w.random, "random", lambda: 0.16), redirect_stdout(io.StringIO()):
                w.pass_day(game)
            sick[difficulty] = len(game["sick"])
        self.assertEqual(sick, {1: 0, 2: 0, 3: 4})

    # ---------- 主菜单的小动画 ----------

    def test_title_frames(self):
        """主菜单动画: 每帧一样高、不超过画面宽、只用英文字符; 车和蘑菇云一直在; 转一圈正好接上第一帧, 能无限循环"""
        frames = [w.title_frame(frame) for frame in range(w.TITLE_FRAMES)]
        for rows in frames:
            self.assertEqual(len(rows), w.TITLE_HEIGHT)
            self.assertTrue(all(row.isascii() and len(row) <= w.SCENE_WIDTH for row in rows))
            self.assertIn("|o            o|>", "\n".join(rows))
            self.assertIn("_.-~~~", rows[0])
        self.assertEqual(w.title_frame(0), w.title_frame(w.TITLE_FRAMES))
        self.assertTrue(all(frames[i] != frames[i + 1] for i in range(w.TITLE_FRAMES - 1)))   # 每一帧都在动

    def test_title_animation_knows_where_the_picture_is(self):
        """主菜单动画要往上数几行才是画面的第一行: 数错了就会画到别的地方去"""
        screen = io.StringIO()
        with redirect_stdout(screen):
            height = w.title_screen()
            menu = "\n1. 开始新游戏\n2. 继续游戏 (没有存档)\n3. 游戏说明\n4. 最高分\n5. 退出游戏"
            print(menu)
            print("选哪一项? ", end="")
        lines = screen.getvalue().split("\n")
        top = lines.index(w.title_frame(0)[0])
        self.assertEqual(len(lines) - 1 - top, height + menu.count("\n") + 1)

    def test_title_animation_in_terminal(self):
        """终端里: 记住光标、往上移到画面第一行、换成下一帧、再回到原来的位置; 终端太小或者不能播动画就不播"""
        with mock.patch.object(w, "can_animate", lambda: True), \
                mock.patch.object(w.shutil, "get_terminal_size", lambda fallback=None: os.terminal_size((100, 40))):
            next_frame = w.title_animation(25)
            screen = io.StringIO()
            with redirect_stdout(screen):
                next_frame()
                next_frame()
        text = screen.getvalue()
        self.assertTrue(text.startswith("\x1b7\x1b[?25l\x1b[25A\r"))
        self.assertTrue(text.endswith("\x1b8\x1b[?25h"))
        self.assertIn(w.title_frame(2)[-1], text)
        with mock.patch.object(w, "can_animate", lambda: True), \
                mock.patch.object(w.shutil, "get_terminal_size", lambda fallback=None: os.terminal_size((100, 24))):
            self.assertIsNone(w.title_animation(25))   # 终端只有 24 行, 画面放不下
        self.assertIsNone(w.title_animation(25))       # 跑测试时不是真正的终端

    def test_ask_number_animates_while_waiting(self):
        """在终端里等按键的时候, 一会儿没按就播一帧动画; 按了数字照常读"""
        keys = iter(["3", "\r"])
        waits = iter([False, False, True, True])
        frames = []
        with mock.patch.object(w, "can_read_keys", lambda: True), self.fake_keyboard(keys), \
                mock.patch.object(w, "key_ready", lambda seconds: next(waits)), redirect_stdout(io.StringIO()):
            self.assertEqual(w.ask_number("选哪一项? ", 1, 5, idle=lambda: frames.append(1)), 3)
        self.assertEqual(len(frames), 2)

    def test_title_loop_goes_to_the_web_page(self):
        """网页版: 开始画面印完以后, 把一整圈动画交给网页去播"""
        calls = []
        with mock.patch.object(w, "can_animate", lambda: True), \
                mock.patch.object(w, "show_title_loop", lambda frames, height: calls.append((len(frames), height))), \
                redirect_stdout(io.StringIO()):
            w.title_screen()
        self.assertEqual(calls, [(w.TITLE_FRAMES, w.TITLE_HEIGHT)])

    # ---------- 开始界面和主菜单 ----------

    def run_main(self, answers):
        """按顺序回答问题, 跑一遍 main(), 返回屏幕上的字"""
        keys = iter(answers)
        screen = io.StringIO()
        with mock.patch("builtins.input", lambda p="": next(keys)), redirect_stdout(screen):
            w.main()
        return screen.getvalue()

    def test_title_screen_help_and_quit(self):
        text = self.run_main(["3", "", "4", "", "5"])   # 游戏说明, 按回车回来, 最高分, 按回车回来, 退出
        for words in ["废  土  之  旅", "W A S T E L A N D", w.VERSION, "1. 开始新游戏",
                      "2. 继续游戏 (没有存档)", "游戏说明", "排辐剂", "辐射偏高", "开局先选难度",
                      "困难 ×1.5", "4. 最高分", "还没有人走到", "下次再见"]:
            self.assertIn(words, text)

    def test_continue_without_save(self):
        text = self.run_main(["2", "", "5"])
        self.assertIn("还没有存档", text)

    def test_save_then_back_to_menu_then_continue(self):
        """开新游戏, 存档后回到主菜单, 主菜单上能看到存档, 选继续游戏能接着玩"""
        new_game = ["1", "3", "1", "小明", "1", "5", "0"]   # 新游戏: 困难、公里、名字、男、5 月、不买东西
        text = self.run_main(new_game + ["13", "2", "5"])   # 存档, 回到主菜单, 退出
        self.assertTrue(os.path.exists(w.SAVE_FILE))
        self.assertIn("继续游戏 (困难, 5月1日, 已走 0 公里)", text)
        text = self.run_main(["2", "13", "2", "5"])   # 继续游戏, 马上又存档, 回到主菜单, 退出
        self.assertIn("==== 5月1日 (第 1 天)", text)

    def test_new_game_over_old_save_asks_first(self):
        """已经有存档时开新游戏, 要先确认; 选回到主菜单, 存档还在"""
        game = new_test_game()
        game["leader"] = "老存档"
        with redirect_stdout(io.StringIO()):
            w.save_game(game)
        text = self.run_main(["1", "2", "5"])   # 开始新游戏, 不确定, 退出
        self.assertIn("开始新游戏会把它删掉", text)
        self.assertEqual(w.load_game()["leader"], "老存档")
        new_game = ["1", "1", "2", "1", "小明", "1", "5", "0"]   # 开始新游戏、确定、普通、公里、名字、男、5 月、不买东西
        self.run_main(new_game + ["13", "2", "5"])
        self.assertEqual(w.load_game()["leader"], "小明")

    # ---------- 换画面和一直往前开 ----------

    def screens(self, wide=False):
        """假装能换画面 (在终端或网页里)。按键还是整行读 (测试替玩家打字用的是假的 input), 不播动画。
        wide=True 是窗口很大 (120 x 40, 用大画面), 不然是 Mac 终端默认的 80 x 24"""
        w.screen.update(unread=False, driving=False, room=True, frame=0)
        size = (120, 40) if wide else (80, 24)
        return mock.patch.multiple(w, can_clear_screen=lambda: True, can_animate=lambda: False,
                                   screen_size=lambda: size)

    def test_new_screen_waits_until_words_are_read(self):
        """换画面前, 屏幕上还有没看过的字, 就先等玩家按回车; 玩家刚回答过问题、或者只有例行消息, 就直接清屏"""
        prompts = []
        screen = io.StringIO()
        with self.screens(), mock.patch("builtins.input", lambda p="": prompts.append(p) or "1"), \
                redirect_stdout(screen):
            w.print("出事了!")
            w.new_screen()
            self.assertEqual(prompts, ["按回车继续……"])
            w.new_screen()                               # 刚清过屏, 没有新字
            w.print_routine("车往前开了 100 公里。")      # 例行消息不用等
            w.new_screen()
            w.print("要怎么办?")
            w.ask_number("选哪个? ", 1, 2)               # 回答了问题, 屏幕上的字就看过了
            w.new_screen()
        self.assertEqual(prompts, ["按回车继续……", "选哪个? "])
        self.assertEqual(screen.getvalue().count("\x1b[H\x1b[2J"), 4)

    def test_no_new_screens_when_not_in_terminal(self):
        """不能换画面的时候 (跑测试、用管道输入), 不清屏, 也不会多问一句按回车"""
        screen = io.StringIO()
        with mock.patch("builtins.input", lambda p="": self.fail("不该问玩家")), redirect_stdout(screen):
            w.print("出事了!")
            w.new_screen()
        self.assertEqual(screen.getvalue(), "出事了!\n")

    def skip_to(self, game, km):
        """把车挪到 km 公里的地方, 前面的地方都算去过了"""
        game["distance"] = km
        places = [(start, name) for start, _, name, *_ in w.HOTSPOTS]
        places += [(k, name) for k, (name, _) in list(w.LANDMARKS.items()) + list(w.OUTPOSTS.items())]
        game["visited"] = [name for k, name in places if k <= km]

    def drive(self, game, stop_on_day=None, animate=False, wide=False):
        """选「继续前进」, 车一直往前开, 到了第 stop_on_day 天玩家按回车停下来。返回屏幕上的字, 问过的问题记在 self.prompts"""
        start = game["day"]
        self.frames = 0   # 车开的时候, 一共看了几次玩家有没有按键 (一帧一次)

        def stop_pressed(seconds):
            self.frames += 1
            self.assertLess(game["day"], start + 60, "开了太久还没停")
            return stop_on_day is not None and game["day"] >= stop_on_day

        self.prompts = []

        def answer(prompt=""):
            self.prompts.append(prompt)
            if "买什么" in prompt:
                return "0"
            return "2" if "买卖东西" in prompt else "1"
        screen = io.StringIO()
        with self.screens(wide), mock.patch.object(w, "stop_pressed", stop_pressed), \
                mock.patch.object(w, "can_animate", lambda: animate), \
                mock.patch("builtins.input", answer), redirect_stdout(screen):
            w.travel(game)
        return screen.getvalue()

    def quiet_road(self):
        """一路上不出事、不生病、天气一直晴"""
        return mock.patch.multiple(w, EVENT_CHANCE_PER_100KM=0, SMALL_EVENT_CHANCE_PER_100KM=0, catch_diseases=lambda *args: None,
                                   DIRTY_WATER_CHANCE=0, roll_weather=lambda game: None)

    def test_keep_driving_until_player_presses(self):
        """车一天一天自己往前开, 玩家自己按回车才停。
        天天都有的例行消息 (辐射在身体里作怪) 开车的时候不印出来, 状态栏里看得到"""
        game = new_test_game()
        self.skip_to(game, 515)   # 刚过卡尼堡, 下一个地方是 808 公里的灰洞, 两天开不到
        game["rads"] = {"A": 30}
        with self.quiet_road():
            text = self.drive(game, stop_on_day=3)
        self.assertEqual(game["day"], 3)
        self.assertNotIn("灰洞", game["visited"])
        # 出发时清一次以前按的键, 开了 2 天, 第 3 天的第一帧就停了
        self.assertEqual(self.frames, 1 + 2 * w.DRIVE_DAY_FRAMES + 1)
        self.assertEqual(self.prompts, [])
        self.assertIn("(按回车停下来, 看看情况)", text)
        self.assertIn("A 良好 辐射", text)
        self.assertNotIn("辐射在A的身体里作怪", text)
        self.assertNotIn("车往前开了", text)

    def test_stop_at_a_place(self):
        """像原版那样, 到了地方就停下来 (看完那里的介绍, 回到每天的菜单)"""
        game = new_test_game()
        self.skip_to(game, 515)
        with self.quiet_road():
            text = self.drive(game)   # 玩家一直不按回车
        self.assertIn("灰洞", game["visited"])
        self.assertLess(game["distance"], 808 + 116)   # 开到灰洞的那一天就停了
        self.assertIn("经过了【灰洞】", text)
        self.assertEqual(self.prompts, [])   # 停下来以后才等玩家按回车 (在每天的菜单前面)

    def test_stop_right_away(self):
        """一出发就按回车, 车马上停下来, 一天都没过"""
        game = new_test_game()
        self.skip_to(game, 515)
        with self.quiet_road():
            self.drive(game, stop_on_day=1)
        self.assertEqual((game["day"], game["distance"]), (1, 515))

    def test_things_happen_but_car_keeps_going(self):
        """路上出了事, 写在动画下面, 玩家按了回车接着开"""
        game = new_test_game()
        self.skip_to(game, 515)
        with self.quiet_road(), mock.patch.multiple(w, EVENT_CHANCE_PER_100KM=1000, EVENTS=[w.bad_water]):
            text = self.drive(game, stop_on_day=3)
        self.assertEqual(game["day"], 3)
        self.assertEqual(text.count("【水被污染】"), 2)
        self.assertEqual(self.prompts, ["按回车继续……"] * 2)

    def test_warn_about_bad_weather(self):
        """天气变成酸雨这些在外面伤人的天气, 提醒一下 (要不要停下来躲进车里, 玩家自己决定); 一直在下就不再说"""
        game = new_test_game()
        self.skip_to(game, 515)
        with self.quiet_road(), mock.patch.object(w, "roll_weather", lambda game: game.update(weather="酸雨")):
            text = self.drive(game, stop_on_day=4)
        self.assertEqual(game["day"], 4)
        self.assertEqual(text.count("天气变了: 酸雨。在外面会受伤"), 1)

    def test_blizzard_while_driving(self):
        """暴风雪里车开不动, 每天说一声, 玩家按了回车接着等"""
        game = new_test_game()
        self.skip_to(game, 515)
        game["weather"] = "灰色暴风雪"
        with self.quiet_road():
            text = self.drive(game, stop_on_day=3)
        self.assertEqual((game["day"], game["distance"]), (3, 515))
        self.assertEqual(text.count("车根本开不动"), 2)

    def test_stop_driving_without_fuel(self):
        game = new_test_game()
        self.skip_to(game, 515)
        game["supplies"]["燃料"] = w.PACES[2][2] * 2   # 只够开两天
        with self.quiet_road():
            text = self.drive(game)
        self.assertEqual(game["day"], 3)
        self.assertIn("燃料不够, 车开不动了", text)

    def test_driving_screen_animates(self):
        """开着动画: 车一直在动, 每一帧都画在屏幕最上面, 状态栏在动画下面, 一天一换"""
        game = new_test_game()
        self.skip_to(game, 515)
        with self.quiet_road():
            text = self.drive(game, stop_on_day=3, animate=True)
        self.assertEqual(text.count("\x1b[?25l\x1b[H"), 2 * w.DRIVE_DAY_FRAMES + 1)   # 两天, 再加第 3 天画的第一帧
        self.assertEqual(text.count("日期: "), 3)   # 第 1、2、3 天的状态栏
        self.assertIn("(@)", text)
        self.assertTrue(text.endswith("\x1b[?25h"))   # 停下来以后把光标显示回来

    def test_dashboard_only_in_big_windows(self):
        """窗口够大 (比 100 列宽、至少 28 行) 才用大画面; 不能换画面、或者设置里关掉了, 也不用"""
        for size, can_clear, turned_on, expected in [((120, 40), True, True, True), ((101, 28), True, True, True),
                                                     ((100, 40), True, True, False), ((120, 27), True, True, False),
                                                     ((120, 40), False, True, False), ((120, 40), True, False, False)]:
            with self.subTest(size=size, can_clear=can_clear, turned_on=turned_on), \
                    mock.patch.multiple(w, screen_size=lambda: size, can_clear_screen=lambda: can_clear,
                                        DASHBOARD=turned_on):
                self.assertEqual(w.use_dashboard(), expected)

    def test_dashboard_fits(self):
        """大画面每一行都正好 100 格宽 (中文算两格), 人多、病多、辐射高、名字长、用英里也一样"""
        game = new_test_game()
        game["party"] = {"队长": 100, "玛莎": 55, "埃迪2": 30, "汉娜2": 5}
        game["sick"] = {"玛莎": ["伤口感染", 3], "埃迪2": ["过度劳累", 3], "汉娜2": ["痢疾", 2]}
        game["rads"] = {"玛莎": 99, "埃迪2": 60, "汉娜2": 30}
        game["supplies"].update({"食物": 1500, "水": 400, "冬衣": 0})
        game.update(unit="英里", temperature=-5, distance=950, seeds=True, money=12345)
        for i in range(8):
            w.write_diary(game, "很长很长的一件事, " * (i + 1))
        for weather in w.WEATHER:
            game["weather"] = weather
            rows = w.dashboard_lines(game, w.road_scene(7, 2, weather, 4), w.car_word(game, moving=True))
            self.assertEqual(len(rows), 2 + w.DASH_ROWS)
            for row in rows:
                self.assertEqual(w.visible_width(row), w.DASHBOARD_WIDTH, row)
            self.assertEqual("车: 开不动" in "\n".join(rows), weather == "灰色暴风雪")
        text = "\n".join(rows)
        for words in ["-- 废土之旅", "-- 路线图", "-- 最近的事", "-- 状态", "汉娜2 危险 5 痢疾 辐射30",
                      "注意: 辐射偏高  有人受冻  带着种子"]:
            self.assertIn(words, text)

    def test_route_map(self):
        """路线图: 走过的路是 =, 车 (>) 在走到的地方, 6 个据点 (F) 和 5 条河 (~) 都标出来"""
        game = new_test_game()
        for distance in [0, 1500, w.TOTAL_DISTANCE]:
            game["distance"] = distance
            track = w.route_map(game)[0][1:]
            self.assertEqual(len(track), w.DASH_LEFT - 2)
            car = track.index(">")
            self.assertEqual(car, min(len(track) - 1, distance * len(track) // w.TOTAL_DISTANCE))
            self.assertNotIn("-", track[:car])
            self.assertNotIn("=", track[car:])
        game["distance"] = 0
        track = w.route_map(game)[0]
        self.assertEqual(track.count("F"), len(w.OUTPOSTS))
        self.assertEqual(track.count("~"), len(w.RIVERS))

    def test_recent_events(self):
        """最近的事: 日记的最后几条, 只写日期和事, 太长的分成几行, 正好 5 行"""
        game = new_test_game()
        self.assertEqual(w.recent_events(game), [""] * w.DASH_EVENT_ROWS)
        w.write_diary(game, "到了卡尼堡。")
        self.assertEqual(w.recent_events(game)[0], " 4月1日 到了卡尼堡。")
        w.write_diary(game, "很长" * 40)
        rows = w.recent_events(game)
        self.assertEqual(len(rows), w.DASH_EVENT_ROWS)
        self.assertEqual(rows[0], " 4月1日 到了卡尼堡。")
        self.assertTrue(rows[1].startswith(" 4月1日 很长") and rows[2].startswith("   ") and rows[3].startswith("   "))
        w.write_diary(game, "又长" * 60)   # 放不下前面两条了: 只放最新的一条, 不会只放半条
        rows = w.recent_events(game)
        self.assertTrue(rows[0].startswith(" 4月1日 又长"))
        self.assertNotIn("很长", "".join(rows))
        w.write_diary(game, "特别长" * 200)   # 一条就放不下: 只放前面几行
        rows = w.recent_events(game)
        self.assertEqual(len(rows), w.DASH_EVENT_ROWS)
        for row in rows:
            self.assertLessEqual(w.text_width(row), w.DASH_LEFT)

    def test_drive_on_dashboard(self):
        """窗口很大: 一直往前开用大画面, 每帧只重画方框上面那几行 (边和动画), 每行后面都擦掉剩下的旧字"""
        game = new_test_game()
        self.skip_to(game, 515)
        with self.quiet_road():
            text = self.drive(game, stop_on_day=3, animate=True, wide=True)
        self.assertEqual(game["day"], 3)
        # 头两天: 开始时整个画一次、每一帧画上面几行、开完再画一次; 第三天整个画一次, 画了一帧就按回车了
        self.assertEqual(text.count("-- 废土之旅"), 2 * (1 + w.DRIVE_DAY_FRAMES + 1) + 1 + 1)
        self.assertEqual(text.count("-- 状态"), text.count("-- 废土之旅"))
        self.assertEqual(text.count("-- 路线图"), 2 * 2 + 1)   # 只有每天开始和结束时整个画
        self.assertIn("\x1b[K\n|", text)
        self.assertIn("(按回车停下来, 看看情况)", text)

    def test_menu_dashboard(self):
        """窗口很大: 每天的菜单上面是大画面, 车停着"""
        game = new_test_game()
        with self.screens(wide=True), mock.patch("builtins.input", lambda p="": "13" if "做什么" in p else "2"), \
                redirect_stdout(io.StringIO()) as screen:
            w.play(game)
        text = screen.getvalue()
        self.assertIn("-- 废土之旅", text)
        self.assertIn("车: 停着", text)
        self.assertNotIn("==== 4月1日", text)   # 普通画面的状态栏没出来

    def test_car_remembers_where_it_stopped(self):
        """像原版那样: 刚出发停在起点; 车开走了就不在什么地方; 开到一个地方就停在那里; 以前的存档也知道"""
        game = new_test_game()
        self.assertEqual(game["here"], w.START_PLACE)
        self.skip_to(game, 515)
        with self.quiet_road(), redirect_stdout(io.StringIO()):
            w.drive_one_day(game)
            self.assertIsNone(game["here"])
            while "灰洞" not in game["visited"]:
                w.drive_one_day(game)
        self.assertEqual(game["here"], "灰洞")
        with redirect_stdout(io.StringIO()):
            w.rest_days(game, 1)
        self.assertEqual(game["here"], "灰洞")   # 在这里休息, 还是停在这里
        for distance, here in [(0, w.START_PLACE), (300, None)]:
            old = new_test_game()
            old["distance"] = distance
            del old["here"]
            with open(w.SAVE_FILE, "w", encoding="utf-8") as f:
                json.dump(old, f)
            self.assertEqual(w.load_game()["here"], here)

    def test_place_views(self):
        """停在每一个地方 (起点、地标、河、据点、辐射热点) 都有画, 正好跟动画一样大, 最下面写着地名; 画里只用英文字符"""
        game = new_test_game()
        places = [w.START_PLACE] + [name for name, _ in list(w.LANDMARKS.values()) + list(w.OUTPOSTS.values())]
        places += [name for _, _, name, *_ in w.HOTSPOTS]
        for place in places:
            with self.subTest(place=place):
                game["here"] = place
                rows = w.place_view(game)
                self.assertEqual(len(rows), w.SCENE_HEIGHT)
                self.assertTrue(all(w.visible_width(row) <= w.SCENE_WIDTH for row in rows))
                self.assertEqual(rows[-1].strip(), place)
                self.assertTrue(all(ord(ch) < 128 for row in rows[:-1] for ch in row))
        game["here"] = None
        self.assertIsNone(w.place_view(game))
        self.assertEqual(w.menu_scene(game), w.road_scene(w.screen["frame"], game["pace"], game["weather"], 4, dust=False))

    def test_menu_shows_the_place(self):
        """每天的菜单上面 (大画面和网页版都是), 停在一个地方就画那个地方"""
        game = new_test_game()
        game["here"] = "卡尼堡"
        with self.screens(wide=True), redirect_stdout(io.StringIO()) as screen:
            w.show_dashboard(game)
        self.assertIn("FORT KEARNY", screen.getvalue())
        self.assertIn("卡尼堡", screen.getvalue())
        with mock.patch.object(w, "GUI", True), redirect_stdout(io.StringIO()) as screen:
            w.show_scene(game)
        self.assertIn("FORT KEARNY", screen.getvalue())

    def test_running_out_of_food_is_news_only_the_first_day(self):
        """头一天没吃的是新消息 (要等玩家看), 之后天天都没吃的, 就只是例行消息 (开车时状态栏里提醒)"""
        game = new_test_game()
        game["supplies"]["食物"] = 3
        with no_new_diseases(), redirect_stdout(io.StringIO()) as screen:
            w.screen["unread"] = False
            w.pass_day(game)
            self.assertTrue(w.screen["unread"])
            w.screen["unread"] = False
            w.pass_day(game)
            self.assertFalse(w.screen["unread"])
        self.assertEqual(screen.getvalue().count("食物不够了"), 2)
        self.assertIn("没吃的了", w.drive_status(game)[-1])
        # 劫匪把吃的一下子抢光了: 第二天头一回挨饿, 也要专门说
        game = new_test_game()
        game["supplies"]["食物"] = 0
        with no_new_diseases(), redirect_stdout(io.StringIO()):
            w.screen["unread"] = False
            w.pass_day(game)
            self.assertTrue(w.screen["unread"])
            game["supplies"]["食物"] = 100   # 打猎打到了, 不饿了
            w.pass_day(game)
            self.assertEqual(game["short"], [])

    def test_drive_status_fits_on_screen(self):
        """车自己开的时候, 动画下面的状态栏每一行都不超过画面的宽度 (60 格), 人多了分两行"""
        game = new_test_game()
        game["party"] = {"队长": 100, "玛莎": 55, "埃迪2": 30, "汉娜": 10}
        game["sick"] = {"玛莎": ["伤口感染", 3], "埃迪2": ["过度劳累", 3], "汉娜": ["痢疾", 2]}
        game["rads"] = {"玛莎": 99, "埃迪2": 60, "汉娜": 30}
        game["supplies"].update({"食物": 300, "水": 200, "燃料": 100})
        game["unit"] = "英里"
        game["supplies"]["冬衣"] = 0
        game["temperature"] = -5
        game["distance"] = 950   # 在辐射热点里
        lines = w.drive_status(game)
        for line in lines:
            self.assertLessEqual(w.text_width(line), w.SCENE_WIDTH, line)
        self.assertTrue(lines[1].startswith("队员: 队长 良好"))
        self.assertIn("汉娜 危险 痢疾 辐射30", lines[2])
        self.assertEqual(lines[-1], "注意: 辐射偏高  有人没冬衣在受冻")
        self.assertIn("食物 300 够 37 天  水 200 够 50 天  燃料 100 够 50 天", lines)

    def test_diary_turns_pages(self):
        """换画面的时候, 日记太长就一页一页地看"""
        game = new_test_game()
        for i in range(25):
            w.write_diary(game, f"第 {i} 件事")
        prompts = []
        with self.screens(), mock.patch("builtins.input", lambda p="": prompts.append(p) or ""), \
                redirect_stdout(io.StringIO()) as screen:
            w.show_diary(game)
        self.assertEqual(prompts, ["按回车看下一页……"] * 2)
        self.assertEqual(screen.getvalue().count("旅行日记 (接上页)"), 2)
        self.assertIn("第 24 件事", screen.getvalue())

    def test_party_turns_pages(self):
        """换画面的时候, 查看队伍一页放两个人 (每个人都有头像), 物资另外一页"""
        game = new_test_game()
        prompts = []
        with self.screens(), mock.patch.object(w, "can_animate", lambda: True), \
                mock.patch.object(w.time, "sleep", lambda seconds: None), \
                mock.patch("builtins.input", lambda p="": prompts.append(p) or ""), \
                redirect_stdout(io.StringIO()) as screen:
            w.show_party(game)
        self.assertEqual(prompts, ["按回车继续……"] * 2)
        self.assertEqual(screen.getvalue().count("队伍状态 (接上页)"), 1)

    def test_random_play_with_screens(self):
        """能换画面、车一直往前开的时候, 乱玩 60 局也不能报错 (车时不时被叫停)"""
        for seed in range(60):
            with self.subTest(seed=seed):
                random.seed(seed)
                stops = random.Random(seed + 1000)
                with self.screens(), real_car(), \
                        mock.patch.object(w, "stop_pressed", lambda seconds: seconds > 0 and stops.random() < 0.01), \
                        mock.patch("builtins.input", random_player(random.Random(seed))), \
                        redirect_stdout(io.StringIO()):
                    try:
                        w.main()
                    except StopGame:
                        pass


if __name__ == "__main__":
    unittest.main()
