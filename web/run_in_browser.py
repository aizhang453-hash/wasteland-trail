"""
网页版启动游戏用的几行设置。由 web/worker.js 在浏览器的后台线程里运行, 平时在电脑上玩用不到它。

跟在电脑上玩不一样的地方:
- 存档: 网页里的 Python 写的文件, 关掉网页就没了。所以每次存档、删存档, 都把存档交给网页,
  让网页存进浏览器里 (localStorage); 下次打开时, worker.js 会先把存档放回来。
- 暂停: 动画要一帧一帧地停, 用的是 worker.js 准备好的 sleepMs (在后台线程里真的停下来等)。
"""

import os
import time

import js   # 网页那边 (worker.js) 给 Python 用的东西

import wasteland_trail as game_file

game_file.SAVE_FILE = "/home/pyodide/savegame.json"   # worker.js 会把浏览器里的存档放在这里

real_save_game = game_file.save_game
real_delete_save = game_file.delete_save


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


game_file.save_game = save_game
game_file.delete_save = delete_save
time.sleep = lambda seconds: js.sleepMs(int(seconds * 1000))

try:
    game_file.main()
except (EOFError, KeyboardInterrupt):
    pass
