# 参与贡献

谢谢你愿意帮忙让《废土之旅》变得更好!

## 报告 bug、提建议

在 GitHub 仓库的 [Issues](https://github.com/aizhang453-hash/wasteland-trail/issues) 页面新建一个 Issue 就行。

- 报告 bug: 写清楚你做了什么、看到了什么、本来应该是什么样。能附上终端里的文字最好。
- 提建议: 想加什么玩法、什么随机事件, 直接写下来。

## 关于背景故事

背景故事和世界观还在设计中。想改剧情的话, 请先开一个 Issue 讨论, 不要直接提交改动。

## 改代码

这个项目不是开源项目 (见 [LICENSE](LICENSE)), 想提交代码改动, 请先开一个 Issue 跟作者商量, 得到同意后再动手。

1. 先 Fork (复制一份到你自己的 GitHub 账号下), 改完以后提交 Pull Request (请求把你的改动合并进来)。
2. 项目里的文件:
   - `wasteland_trail.py`: 整个游戏都在这一个文件里
   - `tests/`: 自动测试 (`test_game.py`) 和难度测试 (`balance.py`)
   - `index.html`、`sw.js`、`web/`: 网页版。网页里跑的还是同一份 `wasteland_trail.py`, 这几个文件只是让它能在浏览器里跑
   - `music/`: 游戏里的音乐 (.wav), 还有做音乐的程序 `make_music.py`
   - `images/`: README 里的图
3. 代码风格:
   - 用中文写注释, 让初学者也能看懂
   - 只用 Python 自带的库, 不装第三方库。唯一的例外是网页版: 浏览器里要靠 Pyodide (让 Python 在网页里跑的工具) 才能跑 Python, 游戏代码本身不用它
   - 能调的数字放在文件最上面的「游戏设置」里
   - 想加新的随机事件, 就照着已有的事件写一个函数, 再放进 `EVENTS` (大事) 或者 `SMALL_EVENTS` (小事) 列表
   - 字符画 (赶路的动画、地标的画、每个人的样子) 里只用英文字符: 一个中文字在终端里占两格, 画会歪掉。要写中文, 就写在画的右边或者下面
   - 想改音乐: 改 `music/make_music.py` 里的音符, 再运行一次 `python3 music/make_music.py` 重新做出 .wav 文件 (测试会检查音乐文件跟这个程序对不对得上)
4. 提交之前跑一遍测试, 全部通过再提交 (Windows 上把命令里的 `python3` 换成 `python`, 下面也一样):

   ```bash
   python3 -m unittest
   ```

5. 如果改了游戏里的数字, 再跑一下难度测试, 看看难度有没有变得太离谱。默认是普通难度, 后面加上局数和难度 (1 简单、2 普通、3 困难) 可以测别的难度:

   ```bash
   python3 tests/balance.py
   ```

   ```bash
   python3 tests/balance.py 1000 3
   ```

6. 如果改了网页版, 或者改了画面、颜色、音乐, 在浏览器里也试一下。在游戏文件夹里运行下面的命令, 再用浏览器打开 http://localhost:8765/ :

   ```bash
   python3 -m http.server 8765
   ```

7. 在 `CHANGELOG.md` 最上面写一下你改了什么, 用玩家看得懂的话写。

## 许可证

提交 Pull Request 就表示你同意: 作者可以自由地使用、修改和发布你提交的代码。
