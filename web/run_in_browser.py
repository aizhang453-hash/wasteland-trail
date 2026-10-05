"""
网页版启动游戏用的几行设置。由 web/worker.js 在浏览器的后台线程里运行, 平时在电脑上玩用不到它。

跟在电脑上玩不一样的地方:
- 存档和最高分: 网页里的 Python 写的文件, 关掉网页就没了。所以每次存档、删存档、记最高分, 都把文件内容交给网页,
  让网页存进浏览器里 (localStorage); 下次打开时, worker.js 会先把它们放回来。
- 暂停: 动画要一帧一帧地停, 用的是 worker.js 准备好的 sleepMs (在后台线程里真的停下来等)。
- 音乐: 网页里的 Python 放不了声音, 所以只告诉网页现在该放哪几首 (网页用 music 文件夹里的 .wav 文件放)。
- 主菜单的小动画: 等玩家输入时 Python 停着动不了, 所以把一整圈画面交给网页, 网页自己一帧一帧地换, 玩家一回答就停。
- 一直往前开的时候怎么停车: 网页里读不了键盘, 玩家点屏幕或者按回车时网页记一笔, 游戏每画一帧来问一下。
- 屏幕多大: 网页按屏幕算好字号, 记下一屏放得下几列、几行字, 游戏看够不够用大画面。
- 打猎: 网页把玩家点了屏幕的哪一格、按了什么键记下来, 游戏每画一帧来拿一次。
- 图形界面: 按钮、状态面板、地图、旅行日记都是网页画的。游戏每次问问题以前, 这里把「现在的状态」和「在问什么、能选什么」
  整理好 (见 gui.py) 交给网页; 车自己往前开的时候, 每天也交一次状态。游戏印出来的字照样显示在网页中间的屏幕上。
"""

import json
import os
import sys
import time

import js   # 网页那边 (worker.js) 给 Python 用的东西

import wasteland_trail as game_file

try:
    import gui   # 整理状态和问题 (gui.py, worker.js 会把它放在游戏旁边)
except ImportError:   # 浏览器里还留着旧版的 worker.js (它不会放 gui.py), 就还用以前的样子
    gui = None

game_file.SAVE_FILE = "/home/pyodide/savegame.json"   # worker.js 会把浏览器里的存档放在这里
game_file.HIGH_SCORE_FILE = "/home/pyodide/highscores.json"   # 最高分榜也一样
game_file.SETTINGS_FILE = "/home/pyodide/settings.json"       # 主菜单「设置」里改的也一样

real_save_game = game_file.save_game
real_delete_save = game_file.delete_save
real_save_high_scores = game_file.save_high_scores
real_save_settings = game_file.save_settings


def save_game(game):
    """存档以后, 把存档内容交给网页存进浏览器"""
    real_save_game(game)
    if os.path.exists(game_file.SAVE_FILE):
        with open(game_file.SAVE_FILE, encoding="utf-8") as f:
            js.saveToPage(f.read())


def delete_save():
    """删存档时, 浏览器里的存档也一起删掉"""
    real_delete_save()
    js.saveToPage("")


def save_high_scores(scores):
    """最高分榜存好以后, 也交给网页存进浏览器"""
    real_save_high_scores(scores)
    if os.path.exists(game_file.HIGH_SCORE_FILE):
        with open(game_file.HIGH_SCORE_FILE, encoding="utf-8") as f:
            js.saveScoresToPage(f.read())


def save_settings():
    """主菜单「设置」里改了东西, 也交给网页存进浏览器 (浏览器里还是旧版的 worker.js 时存不了, 刷新就忘了)"""
    real_save_settings()
    tell = getattr(js, "settingsToPage", None)
    if tell:
        tell(json.dumps(game_file.settings, ensure_ascii=False))


def start_playing(playlist):
    """换音乐: 把要放的 [(文件, 是不是一直循环), ...] 交给网页去放"""
    js.musicToPage(json.dumps(playlist))


def show_title_loop(frames, height):
    """主菜单的动画: 画面刚印完, 光标在画面下面一行。把一圈画面交给网页, 网页往上数 height 行就是画面的第一行"""
    sys.stdout.flush()   # 先让网页收到画面, 再收到动画
    js.loopToPage(json.dumps({"frames": ["\n".join(frame) for frame in frames], "height": height,
                              "delay": game_file.TITLE_ANIMATION_DELAY}))


def stop_pressed(seconds):
    """一直往前开的时候: 停 seconds 秒 (一帧), 再问网页玩家有没有点屏幕或者按回车"""
    sys.stdout.flush()   # 先让网页看到今天的状态
    time.sleep(seconds)
    ask = getattr(js, "stopRequested", None)   # 浏览器里还留着旧版的 worker.js 时没有它, 那就只在出事的时候停
    return bool(ask and ask())


HUNT_EVENTS = {1: "上", 2: "下", 3: "左", 4: "右", 5: "开枪", 6: "走", 7: "打", 8: "瞄"}


def hunt_keys(hunting):
    """打猎时, 上一帧以后玩家在网页上做了什么: 点了屏幕的哪一格 ("打")、鼠标移到哪一格 ("瞄")、按了什么键"""
    events = []
    for code in (js.huntEvents() or "").split(","):
        if code:
            kind, rest = divmod(int(code), 1000000)
            row, col = divmod(rest, 1000)
            name = HUNT_EVENTS.get(kind)
            if name:
                events.append((name, row, col) if name in ("打", "瞄") else (name,))
    return events


def hunt_screen(on):
    """打猎开始、结束时告诉网页: 打猎的时候, 点屏幕就是开枪。
    开始的时候先把网页记下的事都拿走扔掉: 上次打猎快结束时多点的、多按的 (比如多按了一下回车) 不能留到这一次"""
    sys.stdout.flush()
    if on:
        js.huntEvents()
    js.huntToPage(on)


def screen_size():
    """网页一屏放得下几列、几行字 (网页按屏幕大小算好的)。问不到就当是手机竖着拿的大小"""
    ask = getattr(js, "screenSize", None)
    size = ask() if ask else ""
    if not size or size.startswith("0,"):
        return 61, 28
    columns, rows = size.split(",")
    return int(columns), int(rows)


# ---------- 图形界面 ----------

shown = {"game": None, "state": None, "text": []}   # 现在在玩的这一局、上次交给网页的状态、上一个问题以后游戏印出来的字
real_print = game_file.print
real_ask_number = game_file.ask_number
real_wait_enter = game_file.wait_enter
real_setup = game_file.setup
real_play = game_file.play
real_drive_on = game_file.drive_on


def to_page(message):
    js.guiToPage(json.dumps(message, ensure_ascii=False))


def send_state(game=None):
    """把这一局现在的状态交给网页 (跟上次一样就不交了)。没在玩 (在主菜单) 的时候交一个空的"""
    game = game or shown["game"]
    state = gui.game_state(game_file, game) if game else None
    text = json.dumps(state, ensure_ascii=False)
    if text != shown["state"]:
        shown["state"] = text
        to_page({"what": "state", "state": state})


def recording_print(*args, **kwargs):
    """游戏印字照常印, 再记下来 (网页的按钮上写什么, 要从这些字里找)"""
    real_print(*args, **kwargs)
    shown["text"].append(kwargs.get("sep", " ").join(str(arg) for arg in args))


def asking(question):
    """游戏要问问题了: 先交状态, 再告诉网页在问什么"""
    send_state()
    to_page({"what": "question", "question": question})
    shown["text"].clear()


def ask_number(prompt, low, high, idle=None):
    asking(gui.number_question("\n".join(shown["text"]), prompt, low, high))
    try:
        return real_ask_number(prompt, low, high, idle)
    finally:
        to_page({"what": "question", "question": None})   # 问完了


def wait_enter(prompt="按回车继续……"):
    asking(gui.enter_question(prompt))
    try:
        return real_wait_enter(prompt)
    finally:
        to_page({"what": "question", "question": None})


def setup(game):
    shown["game"] = game   # 开局买东西的时候, 面板上也看得到钱和物资
    return real_setup(game)


def play(game):
    shown["game"] = game
    try:
        return real_play(game)
    finally:
        shown["game"] = None
        send_state()


def drive_on(game):
    """车一直往前开: 告诉网页 (网页把按钮换成「停下来」)"""
    to_page({"what": "driving", "driving": True})
    try:
        return real_drive_on(game)
    finally:
        to_page({"what": "driving", "driving": False})
        send_state(game)


if gui and getattr(js, "guiToPage", None):   # 浏览器里还留着旧版的 worker.js 时没有这些, 就还用以前的样子
    game_file.GUI = True
    game_file.print = recording_print
    game_file.ask_number = ask_number
    game_file.wait_enter = wait_enter
    game_file.setup = setup
    game_file.play = play
    game_file.drive_on = drive_on
    game_file.gui_update = send_state

game_file.save_game = save_game
game_file.delete_save = delete_save
game_file.save_high_scores = save_high_scores
game_file.save_settings = save_settings
game_file.start_playing = start_playing
game_file.show_title_loop = show_title_loop
game_file.stop_pressed = stop_pressed
game_file.screen_size = screen_size
if getattr(js, "huntEvents", None):   # 浏览器里还留着旧版的 worker.js 时没有它, 打猎就还是以前打字的样子
    game_file.HUNT_IN_BROWSER = True
    game_file.hunt_keys = hunt_keys
    game_file.hunt_screen = hunt_screen
time.sleep = lambda seconds: js.sleepMs(int(seconds * 1000))

try:
    game_file.main()
except (EOFError, KeyboardInterrupt):
    pass
