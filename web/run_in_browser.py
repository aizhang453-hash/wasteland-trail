"""
网页版启动游戏用的几行设置。由 web/worker.js 在浏览器的后台线程里运行, 平时在电脑上玩用不到它。

跟在电脑上玩不一样的地方:
- 存档和最高分: 网页里的 Python 写的文件, 关掉网页就没了。所以每次存档、删存档、记最高分, 都把文件内容交给网页,
  让网页存进浏览器里 (localStorage); 下次打开时, worker.js 会先把它们放回来。
- 暂停: 动画要一帧一帧地停, 用的是 worker.js 准备好的 sleepMs (在后台线程里真的停下来等)。
- 音乐: 网页里的 Python 放不了声音, 所以只告诉网页现在该放哪几首 (网页用 music 文件夹里的 .wav 文件放)。
- 主菜单的小动画: 等玩家输入时 Python 停着动不了, 所以把一整圈画面交给网页, 网页自己一帧一帧地换, 玩家一回答就停。
"""

import json
import os
import sys
import time

import js   # 网页那边 (worker.js) 给 Python 用的东西

import wasteland_trail as game_file

game_file.SAVE_FILE = "/home/pyodide/savegame.json"   # worker.js 会把浏览器里的存档放在这里
game_file.HIGH_SCORE_FILE = "/home/pyodide/highscores.json"   # 最高分榜也一样

real_save_game = game_file.save_game
real_delete_save = game_file.delete_save
real_save_high_scores = game_file.save_high_scores


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


def start_playing(playlist):
    """换音乐: 把要放的 [(文件, 是不是一直循环), ...] 交给网页去放"""
    js.musicToPage(json.dumps(playlist))


def show_title_loop(frames, height):
    """主菜单的动画: 画面刚印完, 光标在画面下面一行。把一圈画面交给网页, 网页往上数 height 行就是画面的第一行"""
    sys.stdout.flush()   # 先让网页收到画面, 再收到动画
    js.loopToPage(json.dumps({"frames": ["\n".join(frame) for frame in frames], "height": height,
                              "delay": game_file.TITLE_ANIMATION_DELAY}))


game_file.save_game = save_game
game_file.delete_save = delete_save
game_file.save_high_scores = save_high_scores
game_file.start_playing = start_playing
game_file.show_title_loop = show_title_loop
time.sleep = lambda seconds: js.sleepMs(int(seconds * 1000))

try:
    game_file.main()
except (EOFError, KeyboardInterrupt):
    pass
