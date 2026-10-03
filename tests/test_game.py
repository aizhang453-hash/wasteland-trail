"""
废土之旅的自动测试。
运行方法: 在 game 文件夹里输入 python3 -m unittest
"""

import io
import json
import os
import random
import sys
import tempfile
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
            return "4" if played[0] else rng.choice(["1", "1", "1", "2", "3"])
        if "买多少" in prompt:
            most = int(prompt.split("最多")[1].split(")")[0])
            return str(rng.randint(0, most // 3))
        if "买什么" in prompt:
            return rng.choice(["0", "0", "1", "2", "3", "4", "5", "6", "7", "8"])
        if "你要做什么" in prompt:      # 一半时候往前开, 这样才能走得远、遇到更多事
            played[0] = True
            return rng.choice(["1", "1", "1", "1", "1", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"])
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
        answers = iter(["1", "小明", "2", "6", "0"])   # 公里、名字、女、6 月出发、不买东西
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
        answers = iter(["1", "小明", "1", "5", "0"])   # 公里、名字、男、5 月出发、不买东西
        game = w.new_game()
        with mock.patch("builtins.input", lambda p="": next(answers)), redirect_stdout(io.StringIO()):
            w.setup(game)
        game["distance"] = 510   # 一路开到卡尼堡, 带上杰克, 不买东西
        with mock.patch("builtins.input", lambda p="": "1" if "加入" in p else "2"), \
                redirect_stdout(io.StringIO()):
            w.check_places(game)
            w.hurt(game, "杰克", 100)
        diary = "\n".join(game["diary"])
        for words in ["小明被赶出了独立城地下的避难所", "经过了堪萨斯河渡口", "到了卡尼堡",
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
        for key in ["start_month", "temperature", "warmth", "rads", "sick"]:
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
        with real_car(), mock.patch("builtins.input", lambda p="": "1"), redirect_stdout(screen):
            w.offer_recruit(game, "卡尼堡")
        self.assertEqual(list(game["party"]), ["小明"])
        self.assertIn("超载", screen.getvalue())

    def test_recruit_brings_only_what_fits(self):
        game = w.new_game()
        game["party"] = {"小明": 100}
        game["supplies"]["燃料"] = 100   # 800 + 70 = 870, 杰克坐上来 940, 还剩 60 公斤
        with real_car(), mock.patch("builtins.input", lambda p="": "1"), redirect_stdout(io.StringIO()):
            w.offer_recruit(game, "卡尼堡")
        self.assertIn("杰克", game["party"])
        self.assertEqual(game["supplies"]["食物"], 60)   # 30 公斤, 装得下
        self.assertEqual(game["supplies"]["水"], 15)     # 只剩 30 公斤, 只装得下 15 份水

    def test_trader_needs_room(self):
        game = w.new_game()
        game["party"] = {"A": 100}
        game["supplies"]["食物"] = 20
        game["supplies"]["燃料"] = 110   # 70 + 10 + 880 = 960 公斤, 换掉食物也装不下 64 公斤燃料
        screen = io.StringIO()
        with real_car(), mock.patch("builtins.input", lambda p="": "1"), redirect_stdout(screen):
            w.trader(game)
        self.assertIn("装不下 8 份燃料", screen.getvalue())
        self.assertEqual(game["supplies"]["燃料"], 110)

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
        answers = iter(["2", "2", "", "4"])
        with mock.patch("builtins.input", lambda p="": next(answers)), redirect_stdout(io.StringIO()):
            w.main()
        self.assertFalse(os.path.exists(w.SAVE_FILE))

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

    # ---------- 开始界面和主菜单 ----------

    def run_main(self, answers):
        """按顺序回答问题, 跑一遍 main(), 返回屏幕上的字"""
        keys = iter(answers)
        screen = io.StringIO()
        with mock.patch("builtins.input", lambda p="": next(keys)), redirect_stdout(screen):
            w.main()
        return screen.getvalue()

    def test_title_screen_help_and_quit(self):
        text = self.run_main(["3", "", "4"])   # 游戏说明, 按回车回来, 退出
        for words in ["废  土  之  旅", "W A S T E L A N D", w.VERSION, "1. 开始新游戏",
                      "2. 继续游戏 (没有存档)", "游戏说明", "排辐剂", "下次再见"]:
            self.assertIn(words, text)

    def test_continue_without_save(self):
        text = self.run_main(["2", "", "4"])
        self.assertIn("还没有存档", text)

    def test_save_then_back_to_menu_then_continue(self):
        """开新游戏, 存档后回到主菜单, 主菜单上能看到存档, 选继续游戏能接着玩"""
        new_game = ["1", "1", "小明", "1", "5", "0"]   # 新游戏: 公里、名字、男、5 月、不买东西
        text = self.run_main(new_game + ["10", "2", "4"])   # 存档, 回到主菜单, 退出
        self.assertTrue(os.path.exists(w.SAVE_FILE))
        self.assertIn("继续游戏 (5月1日, 已走 0 公里)", text)
        text = self.run_main(["2", "10", "2", "4"])   # 继续游戏, 马上又存档, 回到主菜单, 退出
        self.assertIn("==== 5月1日 (第 1 天)", text)

    def test_new_game_over_old_save_asks_first(self):
        """已经有存档时开新游戏, 要先确认; 选回到主菜单, 存档还在"""
        game = new_test_game()
        game["leader"] = "老存档"
        with redirect_stdout(io.StringIO()):
            w.save_game(game)
        text = self.run_main(["1", "2", "4"])   # 开始新游戏, 不确定, 退出
        self.assertIn("开始新游戏会把它删掉", text)
        self.assertEqual(w.load_game()["leader"], "老存档")
        new_game = ["1", "1", "1", "小明", "1", "5", "0"]   # 开始新游戏、确定、公里、名字、男、5 月、不买东西
        self.run_main(new_game + ["10", "2", "4"])
        self.assertEqual(w.load_game()["leader"], "小明")


if __name__ == "__main__":
    unittest.main()
