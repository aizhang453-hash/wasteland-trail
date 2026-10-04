"""
网页版图形界面的测试: web/gui.py 怎么把选项变成按钮、怎么整理状态; web/run_in_browser.py 交给网页的东西;
index.html 里画地图用的地名跟游戏里的一样。
运行方法: 在游戏文件夹 (wasteland-trail) 里输入 python3 -m unittest (跟别的测试一起跑)
"""

import io
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "web"))
import gui
import wasteland_trail as w
from tests.test_game import StopGame, new_test_game, random_player


class GuiTest(unittest.TestCase):
    def setUp(self):
        # 跟 test_game.py 一样: 整行读输入, 存档和最高分放到临时文件夹
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for name, value in [("can_read_keys", lambda: False),
                            ("SAVE_FILE", os.path.join(tmp.name, "savegame.json")),
                            ("HIGH_SCORE_FILE", os.path.join(tmp.name, "highscores.json"))]:
            patcher = mock.patch.object(w, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_buttons_from_options(self):
        """游戏印出来的「1. 继续前进  2. 休息一天」这些, 变成按钮的号码和名字 (名字只要前面一小段)"""
        menu = gui.number_question("1. 继续前进  2. 休息  3. 搜刮废墟  4. 打猎  5. 交易\n"
                                   "6. 用药  7. 改变口粮  8. 改变速度  9. 丢东西  10. 和人说话\n"
                                   "11. 查看队伍  12. 旅行日记  13. 存档", "你要做什么? ", 1, 13)
        self.assertEqual(menu["kind"], "choices")
        self.assertTrue(menu["actions"])
        self.assertEqual(menu["choices"][0], [1, "继续前进"])
        self.assertEqual(menu["choices"][4], [5, "交易"])
        self.assertEqual(menu["choices"][8], [9, "丢东西"])
        self.assertEqual(menu["choices"][9], [10, "和人说话"])
        self.assertEqual(menu["choices"][12], [13, "存档"])
        cases = [
            ("1. 简单: 一开始有 700 块钱\n2. 普通: 500\n3. 困难: 450", "选哪个? ", 1, 3, ["简单", "普通", "困难"]),
            ("", "距离单位: 1. 公里  2. 英里  ", 1, 2, ["公里", "英里"]),
            ("1. 交出一些物资  2. 开枪(要 15 发子弹)  3. 加速逃跑(要 3 份燃料)", "你怎么办? ", 1, 3, ["交出一些物资", "开枪", "加速逃跑"]),
            ("1. 食物  1 块一份, 每份 0.5 公斤  (现在有 0)\n2. 水  1 块一份\n0. 离开商店", "买什么? ", 0, 2, ["食物", "水", "离开商店"]),
            ("", "1. 确定, 开始新游戏  2. 回到主菜单  ", 1, 2, ["确定", "回到主菜单"]),
            ("", "出发月份 (3~7 月): ", 3, 7, ["3 月", "4 月", "5 月", "6 月", "7 月"]),
            ("0. 不休息了", "休息几天? (1~3) ", 0, 3, ["不休息了", "1 天", "2 天", "3 天"]),
            ("1. 食物  180 份, 一共 90 公斤\n2. 水  120 份, 一共 240 公斤\n0. 不丢了", "丢什么? ", 0, 2, ["食物", "水", "不丢了"]),
            ("  左边水道  中间\x1b[31m礁石\x1b[0m  右边礁石", "往哪边划? ", 1, 3, ["左边", "中间", "右边"]),
        ]
        for text, prompt, low, high, labels in cases:
            with self.subTest(prompt=prompt):
                self.assertEqual([label for _, label in gui.number_question(text, prompt, low, high)["choices"]], labels)
        self.assertEqual(gui.number_question("", "买多少食物? (最多 500) ", 0, 500)["kind"], "number")   # 太多了, 用数字键盘
        self.assertEqual(gui.number_question("", "你要做什么? ", 1, 20)["kind"], "choices")   # 每天的菜单再长也是按钮

    def test_question_above_buttons(self):
        """按钮上面写的问题: 问题里就是选项的话, 用选项前面的字, 或者上面那一句"""
        self.assertEqual(gui.number_question("", "你要做什么? ", 1, 13)["prompt"], "你要做什么?")
        self.assertEqual(gui.number_question("", "要花 2 天去找吗? 1. 去  2. 不去  ", 1, 2)["prompt"], "要花 2 天去找吗?")
        self.assertEqual(gui.number_question("「20 份食物换 8 份燃料, 换不换?」", "1. 换  2. 不换  ", 1, 2)["prompt"],
                         "「20 份食物换 8 份燃料, 换不换?」")

    def test_enter_buttons(self):
        self.assertEqual(gui.enter_question("按回车继续……")["label"], "继续")
        self.assertEqual(gui.enter_question("按回车看下一页……")["label"], "看下一页")
        self.assertEqual(gui.enter_question("按回车回到主菜单……")["label"], "回到主菜单")
        ready = gui.enter_question("准备好了就按回车……")
        self.assertEqual(ready["label"], "准备好了")
        self.assertTrue(ready["typeNext"])   # 打猎: 按完马上要打字

    def test_every_question_gets_buttons(self):
        """乱玩 100 局: 游戏问的每一个选数字的问题, 每个号码都找得到名字 (问「多少」的除外);
        每次问问题的时候, 状态都能整理好、变成 JSON"""
        problems = []
        shown = []
        playing = []
        real_print, real_ask, real_play = w.print, w.ask_number, w.play

        def recording_print(*args, **kwargs):
            real_print(*args, **kwargs)
            shown.append(" ".join(str(arg) for arg in args))

        def checking_ask(prompt, low, high, idle=None):
            question = gui.number_question("\n".join(shown), prompt, low, high)
            shown.clear()
            if question["kind"] == "choices" and "多少" not in prompt:
                missing = [number for number, label in question["choices"] if not label]
                if missing:
                    problems.append((prompt, missing))
            if playing:
                json.dumps(gui.game_state(w, playing[-1]))
            return real_ask(prompt, low, high, idle)

        def recording_play(game):
            playing.append(game)
            return real_play(game)

        for seed in range(100):
            random.seed(seed)
            with mock.patch.multiple(w, print=recording_print, ask_number=checking_ask, play=recording_play), \
                    mock.patch("builtins.input", random_player(random.Random(seed))), redirect_stdout(io.StringIO()):
                try:
                    w.main()
                except StopGame:
                    pass
        self.assertEqual(problems, [])
        self.assertTrue(playing)

    def test_state(self):
        """状态: 面板、地图、旅行日记要用的都在里面"""
        game = new_test_game()
        game.update(leader="A", distance=950, day=12)
        game["jobs"] = {"B": "医生"}
        game["sick"] = {"C": ["痢疾", 3]}
        game["rads"] = {"D": 55}
        w.write_diary(game, "到了卡尼堡。")
        state = gui.game_state(w, game)
        json.dumps(state)
        self.assertEqual(state["date"], "4月12日")
        self.assertEqual((state["next"]["name"], state["next"]["kind"]), ("拉勒米堡", "据点"))
        self.assertEqual([member["name"] for member in state["party"]], ["A", "B", "C", "D"])
        self.assertTrue(state["party"][0]["leader"])
        self.assertEqual(state["party"][1]["job"], "医生")
        self.assertEqual(state["party"][2]["sick"], "痢疾")
        self.assertEqual(state["party"][3]["radsWord"], "严重")
        self.assertEqual(state["notes"][0][1], "在导弹发射井一带, 辐射偏高")
        self.assertEqual(state["diary"], [["4月12日", "到了卡尼堡。"]])
        self.assertEqual(len(state["places"]), len(w.LANDMARKS) + len(w.OUTPOSTS))
        food = state["supplies"][0]
        self.assertEqual((food["name"], food["amount"], food["days"]), ("食物", 100, 12))

    def test_map_places_match_the_game(self):
        """index.html 里画地图用的地名 (和经纬度) 要跟游戏里的一样, 而且按路上的先后排"""
        with open(os.path.join(ROOT, "index.html"), encoding="utf-8") as f:
            page = f.read()
        places = re.findall(r'"([^"]+)": \[[\d.]+, -[\d.]+\]', page.split("const PLACES = {")[1].split("};")[0])
        hotspots = re.findall(r'"([^"]+)": \[', page.split("const HOTSPOT_PLACES = {")[1].split("};")[0])
        route = ["独立城"] + [name for _, (name, _) in sorted({**w.LANDMARKS, **w.OUTPOSTS}.items())] + [w.DESTINATION]
        self.assertEqual(places, route)
        self.assertEqual(hotspots, [name for _, _, name, *_ in w.HOTSPOTS])

    def test_hunt_starts_with_empty_queue(self):
        """网页: 开始打猎时, 上次打猎快结束时多点的、多按的 (比如多按了一下回车) 都扔掉, 不会让这次一开始就结束"""
        script = f"""
import json, sys, types, builtins, runpy, os
sys.path[:0] = [{ROOT!r}, {os.path.join(ROOT, "web")!r}]
js = types.ModuleType("js")
js.guiToPage = js.saveToPage = js.saveScoresToPage = js.musicToPage = js.loopToPage = lambda text: None
js.sleepMs = lambda ms: None
js.stopRequested = lambda: False
js.screenSize = lambda: "61,28"
pending = ["6000000,7003010"]   # 上次打猎剩下的: 结束 (回车)、点了一下
js.huntEvents = lambda: pending.pop() if pending else ""
js.huntToPage = lambda on: None
sys.modules["js"] = js
def no_input(prompt=""):
    raise EOFError
builtins.input = no_input
runner = runpy.run_path({os.path.join(ROOT, "web", "run_in_browser.py")!r}, run_name="game")
runner["hunt_screen"](True)
print(json.dumps(runner["hunt_keys"]({{}})))
"""
        result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, cwd=ROOT, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        self.assertEqual(json.loads(result.stdout.strip().split("\n")[-1]), [])

    def test_run_in_browser(self):
        """假装在网页里: 用一个假的 js (网页那边), 让乱按的玩家玩几局, 看看交给网页的东西对不对"""
        script = f"""
import json, random, sys, types, builtins, runpy, os
sys.path[:0] = [{ROOT!r}, {os.path.join(ROOT, "web")!r}]
messages = []
js = types.ModuleType("js")
js.guiToPage = lambda text: messages.append(json.loads(text))
js.saveToPage = js.saveScoresToPage = js.musicToPage = js.loopToPage = lambda text: None
js.sleepMs = lambda ms: None
stops = random.Random(1)
js.stopRequested = lambda: stops.random() < 0.02
js.screenSize = lambda: "61,28"
js.huntToPage = lambda on: messages.append({{"what": "hunt", "on": bool(on)}})
taps = random.Random(2)   # 打猎时乱点屏幕、乱按键 (7 是点了第几行第几格, 1~6 是方向键、开枪、结束)
js.huntEvents = lambda: ",".join(str(taps.choice([7000000 + taps.randrange(15) * 1000 + taps.randrange(62), 5000000, 1000000, 4000000, 8001030, 6000000]))
                                 for _ in range(taps.randrange(3)))
sys.modules["js"] = js
import importlib
import wasteland_trail as w
from tests.test_game import random_player, StopGame
for seed in range(8):
    importlib.reload(w)   # run_in_browser.py 会换掉游戏里的一些函数, 每一局都从头来
    w.IN_BROWSER = True
    random.seed(seed)
    builtins.input = random_player(random.Random(seed))
    try:
        runpy.run_path({os.path.join(ROOT, "web", "run_in_browser.py")!r}, run_name="game")
    except StopGame:
        pass
print(json.dumps(messages, ensure_ascii=False))
"""
        # run_in_browser.py 会把存档放到 /home/pyodide (网页里的文件夹), 电脑上没有这个文件夹, 存不了档也没关系
        result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, cwd=ROOT, timeout=600)
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        messages = json.loads(result.stdout.strip().split("\n")[-1])
        whats = [message["what"] for message in messages]
        self.assertGreater(whats.count("state"), 50)
        questions = [message["question"] for message in messages if message["what"] == "question"]
        asked = [question for question in questions if question]
        self.assertEqual(len(asked) * 2, len(questions))   # 每个问题问完都说一声「问完了」
        self.assertTrue(any(question["kind"] == "choices" and question["actions"] for question in asked))
        self.assertTrue(any(question["kind"] == "enter" for question in asked))
        driving = [message["driving"] for message in messages if message["what"] == "driving"]
        self.assertTrue(driving)
        self.assertEqual(driving[::2], [True] * len(driving[::2]))   # 开始开、停下来, 一对一对的
        self.assertEqual(driving[1::2], [False] * len(driving[1::2]))
        states = [message["state"] for message in messages if message["what"] == "state" and message["state"]]
        self.assertTrue(states and all("party" in state for state in states))
        hunts = [message["on"] for message in messages if message["what"] == "hunt"]
        self.assertTrue(hunts)   # 网页里打猎是瞄准射击的那种
        self.assertEqual(hunts[::2], [True] * len(hunts[::2]))   # 开始打猎、打完了, 一对一对的
        self.assertEqual(hunts[1::2], [False] * len(hunts[1::2]))


if __name__ == "__main__":
    unittest.main()
