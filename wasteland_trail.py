"""
废土之旅
一个仿照《俄勒冈之旅》的文字冒险游戏。
运行方法: 在终端里输入 python wasteland_trail.py
"""

import atexit
import builtins
import json
import os
import random
import re
import select
import shutil
import subprocess
import sys
import threading
import time
import unicodedata
import wave

# 一个键一个键地读键盘: Mac 和 Linux 用 termios, Windows 用 msvcrt
try:
    import termios
    import tty
except ImportError:
    termios = None
try:
    import msvcrt
except ImportError:
    msvcrt = None
# 放音乐: Windows 用自带的 winsound; Mac 和 Linux 用系统自带的播放器 (见 music_player)
try:
    import winsound
except ImportError:
    winsound = None

# 存档文件和最高分榜, 都放在游戏文件旁边
SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "savegame.json")
HIGH_SCORE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "highscores.json")

# ========== 游戏设置(数字都可以随便改) ==========

VERSION = "v3.0"   # 版本号, 显示在开始界面上。发布新版本时要跟着改

# 路线是当年的俄勒冈小道: 从密苏里州独立城到俄勒冈城。
# 距离按 1847 年乔尔·帕尔默的拓荒指南里的路程表算 (经过布里杰堡的那条线)
DESTINATION = "俄勒冈城"
TOTAL_DISTANCE = 3119   # 到俄勒冈城的总路程(公里)

# 难度 (开局时玩家选): 编号 -> (名字, 一开始有多少钱, 路上出事的机会是平时的百分之几, 生病的机会是平时的百分之几,
#                              得分是百分之几, 说明)
# 「普通」就是没有难度选择以前的样子。跟原版一样, 越难得分越高
DIFFICULTIES = {
    1: ("简单", 700, 70, 70, 50, "路上出事、生病都少一些"),
    2: ("普通", 500, 100, 100, 100, "钱刚刚够用, 要精打细算"),
    3: ("困难", 450, 130, 130, 150, "路上出事、生病都多一些"),
}

# 距离单位(开局时玩家选): 名字 -> 1 公里等于多少这个单位。游戏里的路程一律按公里算, 只在显示时换算
UNITS = {"公里": 1, "英里": 0.621371}

# 路上的据点(可以买东西), 都是当年拓荒者补给的贸易站或军事堡垒: 离起点几公里 -> (名字, 介绍)
OUTPOSTS = {
    510: ("卡尼堡", "1848 年建的军事堡垒, 专门保护走俄勒冈小道的拓荒者。"),
    999: ("拉勒米堡", "1834 年建的毛皮贸易站, 1849 年被军队买下, 是拓荒者路上最重要的补给站之一。"),
    1633: ("布里杰堡", "山地向导吉姆·布里杰在 1840 年代初建的贸易站, 拓荒者在这里修车、换牲口。"),
    1952: ("霍尔堡", "1834 年建的毛皮贸易站。再往前不远, 去加州的人和去俄勒冈的人就要分道扬镳了。"),
    2400: ("博伊西堡", "1834 年建的毛皮贸易站, 就在蛇河边上。"),
    2861: ("达尔斯", "哥伦比亚河边, 1850 年在这里建了军营。当年的拓荒者从这里要么顺着大河漂流而下, "
                     "要么走绕过胡德山的巴洛路。"),
}

# 路上的风景地标(只看不买): 离起点几公里 -> (名字, 介绍)
LANDMARKS = {
    130: ("堪萨斯河渡口", "拓荒者遇到的第一条大河, 当年有人在这里摆渡, 过河要交钱。"),
    280: ("大蓝河", "河边的凹泉是拓荒者喜欢的宿营地, 石头上还留着 1846 年刻下的名字。"),
    808: ("灰洞", "因为长着白蜡树而得名。下来要经过陡峭的绞盘山, 当年得锁住车轮、用绳子拉着车慢慢往下放。"),
    875: ("法院岩", "这块巨岩让拓荒者想起了家乡小镇上的法院大楼, 旁边小一点的那块叫监狱岩。"),
    901: ("烟囱岩", "一根细长的石柱, 拓荒者提前好几天就能远远望见, 是他们日记里写得最多的地标。"),
    941: ("斯科茨崖", "以一位 1828 年前后死在这附近的毛皮商人海勒姆·斯科特命名。"),
    1202: ("北普拉特河渡口", "拓荒者在这里最后一次渡过北普拉特河, 1847 年有人在这里开了渡口。"),
    1275: ("独立岩", "传说拓荒者要在 7 月 4 日独立日前赶到这里, 才不会在冬天前被困在山里。石头上刻满了几千个名字。"),
    1283: ("魔鬼门", "甜水河从一道 100 多米高的石缝中间穿了过去。"),
    1450: ("南山口", "翻越落基山脉最平缓的山口, 也是大陆分水岭: 过了这里, 河水都往太平洋流。路程差不多走了一半。"),
    1548: ("格林河", "又宽又急的大河, 是整条小道上最危险的渡口之一。"),
    1852: ("苏打泉", "地下冒出天然的气泡水, 拓荒者觉得尝起来像苏打水。"),
    1981: ("美国瀑布", "蛇河上的一道大瀑布, 传说名字来自一群在这里翻了船的美国毛皮商人。"),
    2176: ("鲑鱼瀑布", "当地的原住民在这里捕鲑鱼, 拓荒者常拿东西跟他们换鱼吃。"),
    2213: ("蛇河渡口", "河中间有三个小岛, 拓荒者借着小岛一段一段地渡过蛇河。"),
    2596: ("大圆谷", "被群山围起来的一大片圆形草地, 拓荒者在这里歇脚, 准备翻越蓝山。"),
    2651: ("蓝山", "远远看去山是蓝色的。当年拓荒者要一路砍树开路, 车才能翻过去。"),
}

# ---------- 过河 ----------

# 路上要过的大河 (都在上面的地标里, 车开到河边会停下来): 地标名字 -> (河名, 河面宽几米, 平常水深几米, 坐渡船要几块钱)
# 渡船是 None 的地方没有渡船。当年的拓荒者要么赶着马车蹚过去, 要么把车厢的缝塞住、像船一样漂过去, 要么花钱坐渡船
RIVERS = {
    "堪萨斯河渡口": ("堪萨斯河", 190, 0.9, 5),
    "大蓝河": ("大蓝河", 60, 0.6, None),
    "北普拉特河渡口": ("北普拉特河", 100, 0.9, 10),
    "格林河": ("格林河", 120, 1.6, 15),
    "蛇河渡口": ("蛇河", 300, 1.2, None),
}
# 河水按月份涨落: 春天山里的雪化了, 5、6 月水最深, 秋天水最浅。1 月到 12 月, 每个月是平常水深的几倍
RIVER_SEASON = [0.7, 0.7, 0.9, 1.1, 1.3, 1.4, 1.1, 0.8, 0.7, 0.7, 0.8, 0.7]
RAIN_RISE = 0.1         # 这几天每下一天雨雪, 河水涨一成
RAIN_FADE = 0.7         # 雨雪停了以后, 涨起来的水每天退掉三成
CAR_WADE_DEPTH = 0.6    # 车能直接开过多深的水 (米), 再深发动机就会进水
SNORKEL_DEPTH = 0.3     # 有机械师的话, 他给车接上通气管, 车能多开过这么深的水
SOAK_DEPTH = 0.3        # 水比车能开过的深度再深这么多以内, 只是发动机进水; 再深, 车就会被急流冲翻
SOAK_FOOD = 4           # 发动机进水时, 泡了河水的食物要扔掉几分之一
FLOAT_RISK = 0.1        # 绑上空油桶浮过去时翻车的机会; 水比 1 米每深 1 米, 再多这么多
DROWN_CHANCE = 0.2      # 车在河里翻了, 有人被冲走的机会
RIVER_RADS = 10         # 车翻了掉进河里, 每个人受多少辐射 (河水也被污染了)
FERRY_WAIT = 2          # 坐渡船最多要排几天队

# ---------- 最后一段路 ----------

# 当年的拓荒者到了达尔斯, 要么扎木筏顺着哥伦比亚河漂下去, 要么交过路费走绕过胡德山的巴洛路
LAST_ROAD_FROM = "达尔斯"
BARLOW_TOLL = 10        # 巴洛路的过路费 (1846 年是每辆马车 5 美元)
RAPIDS = 4              # 坐木筏一路上要过几段急流 (要漂两天, 每天两段)
RAPID_SECONDS = 5       # 看到急流以后, 几秒内选对方向才算躲开; 慢了就看运气
RAPID_HIT_DROWN = 0.15  # 木筏撞上礁石时, 有人掉进河里被冲走的机会

# ---------- 得分 ----------

# 照原版: 走到终点才算分。活下来的每个人按健康给分 (健康的说法见 health_word), 剩下的物资和钱也能换成分
SCORE_PER_PERSON = {"良好": 500, "一般": 400, "很差": 300, "危险": 200}
# 剩下的物资怎么算分: 物资 -> (每几个, 算几分)
SCORE_SUPPLIES = {"食物": (25, 1), "水": (25, 1), "燃料": (5, 1), "子弹": (50, 1),
                  "零件": (1, 2), "药品": (1, 2), "冬衣": (1, 2), "排辐剂": (1, 2)}
SCORE_MONEY = 5         # 每剩几块钱算 1 分
SCORE_SEEDS = 1000      # 把种子库的种子带到终点 (隐藏结局), 再加这么多分
HIGH_SCORES = 10        # 最高分榜记几名

# 商店价格(每个多少钱)
PRICES = {"食物": 1, "水": 1, "燃料": 4, "子弹": 1, "零件": 20, "药品": 15, "冬衣": 10, "排辐剂": 20}
# 在据点卖东西: 据点的人只给买价的百分之几 (有商人帮着讲价能多拿一些)。零头不算
SELL_SHARE = 50
MERCHANT_SELL_SHARE = 60
# 每种物资怎么数 (5 份食物、30 发子弹、1 套冬衣……)
MEASURES = {"食物": "份", "水": "份", "燃料": "份", "子弹": "发", "零件": "个", "药品": "份", "冬衣": "套", "排辐剂": "支"}

# ---------- 重量 ----------

# 重量一律按克算 (整数不会有小数算不准的问题), 显示的时候再换成公斤或磅。
# 车最多能装多重: 人和东西加起来 1000 公斤, 差不多是一辆皮卡的载重。装不下的东西就拿不了
CAR_CAPACITY = 1000000
PERSON_WEIGHT = 70000       # 每个人 70 公斤 (人越多, 车上能装的东西越少)
# 每种物资一个多重 (克), 尽量按现实来
WEIGHTS = {
    "食物": 500,      # 一顿饭的干粮, 半公斤
    "水": 2000,       # 2 升水
    "燃料": 8000,     # 10 升汽油连桶, 够车开 50 公里左右
    "子弹": 20,       # 一发步枪子弹
    "零件": 10000,
    "药品": 200,
    "冬衣": 2000,
    "排辐剂": 200,
}
CARRY_PER_PERSON = 20000    # 打猎时每个人能扛多少肉回车上 (20 公斤), 人多扛得多
# 重量单位跟着距离单位走: 距离单位 -> (重量单位, 1 公斤等于多少这个单位)
WEIGHT_UNITS = {"公里": ("公斤", 1), "英里": ("磅", 2.20462)}

# 口粮: 编号 -> (名字, 每人每天吃几份, 每天健康变化)
RATIONS = {1: ("少", 1, -2), 2: ("普通", 2, 1), 3: ("饱", 3, 3)}

# 每开 100 公里, 遇到随机事件的机会
EVENT_CHANCE_PER_100KM = 0.35

# 速度: 编号 -> (名字, 车每天开几公里, 每天用几份燃料, 每天健康变化)
PACES = {1: ("慢", 90, 1, 1), 2: ("中", 105, 2, 0), 3: ("快", 120, 3, -2)}

# ---------- 日期和天气 ----------

# 出发月份: 跟原版《俄勒冈之旅》一样, 可以选 3 月到 7 月。第 1 天是出发那个月的 1 号
FIRST_MONTH = 3
LAST_MONTH = 7
MONTH_DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]   # 每个月有几天 (不算闰年)

# 沿路的气候: 从几公里开始 -> (地区名, 每个月白天的平均最高气温 (摄氏度, 1 月到 12 月),
#                              每个月有几天下雨或下雪, 其中有几天下雪)
# 数字用的是每个地区里一个真实气象站 1991~2020 年的平均值 (美国国家海洋和大气管理局 NOAA)
CLIMATE = {
    # 堪萨斯州和内布拉斯加州东部, 气象站: 内布拉斯加州卡尼 (就在卡尼堡旁边)
    0: ("大平原", [2, 4, 11, 16, 22, 28, 30, 29, 26, 18, 10, 3],
        [3.8, 4.5, 5.9, 8.5, 11.7, 9.6, 8.8, 8.4, 6.5, 6.6, 4.2, 3.5],
        [2.7, 3.4, 1.8, 0.9, 0, 0, 0, 0, 0, 0.5, 1.3, 2.4]),
    # 内布拉斯加州西部到怀俄明州东部, 气象站: 内布拉斯加州斯科茨布拉夫 (就在斯科茨崖旁边)
    800: ("高平原", [5, 7, 13, 17, 22, 29, 33, 32, 27, 18, 11, 5],
          [4.7, 6.3, 6.9, 9.4, 12.1, 10.7, 7.7, 6.7, 6.7, 7.0, 5.3, 5.2],
          [4.1, 5.1, 3.9, 2.8, 0.3, 0, 0, 0, 0.2, 1.6, 3.5, 4.8]),
    # 甜水河谷、南山口、格林河、布里杰堡一带, 海拔 2000 米上下, 气象站: 怀俄明州法森 (离南山口不远)
    1270: ("落基山区", [-2, -1, 6, 12, 18, 23, 28, 27, 22, 14, 5, -1],
           [3.1, 3.3, 3.5, 4.7, 6.0, 4.1, 3.1, 3.7, 4.1, 3.2, 2.5, 3.2],
           [3.2, 3.0, 2.6, 2.1, 0.3, 0, 0, 0, 0, 0.9, 1.9, 2.9]),
    # 爱达荷州南部的蛇河平原, 气象站: 爱达荷州特温福尔斯 (离鲑鱼瀑布不远)
    1900: ("蛇河平原", [3, 6, 11, 15, 20, 25, 30, 30, 24, 17, 9, 3],
           [10.6, 8.7, 9.3, 10.1, 8.5, 6.5, 2.8, 2.7, 2.9, 5.4, 7.7, 10.3],
           [5.7, 3.9, 1.8, 0.8, 0, 0, 0, 0, 0, 0.4, 2.1, 5.0]),
    # 大圆谷和蓝山, 气象站: 俄勒冈州拉格兰德 (就在大圆谷里)
    2560: ("蓝山", [4, 7, 11, 15, 20, 24, 30, 31, 25, 17, 9, 4],
           [9.8, 7.9, 10.2, 9.9, 9.2, 7.9, 3.8, 3.0, 3.8, 7.8, 10.1, 11.2],
           [3.2, 1.6, 1.3, 0.2, 0, 0, 0, 0, 0, 0, 1.3, 3.5]),
    # 哥伦比亚河南岸, 气象站: 达尔斯对岸的哥伦比亚峡谷机场
    2720: ("哥伦比亚河谷", [6, 9, 14, 18, 23, 26, 31, 31, 27, 19, 10, 5],
           [14.1, 11.3, 10.8, 7.9, 6.4, 3.8, 1.5, 1.7, 2.7, 8.3, 13.1, 13.9],
           [3.7, 2.2, 0.5, 0, 0, 0, 0, 0, 0, 0.1, 1.4, 5.0]),
    # 绕过胡德山的巴洛路, 气象站: 俄勒冈州政府营 (在胡德山山腰上, 海拔 1186 米)
    2900: ("胡德山", [3, 3, 5, 7, 12, 15, 21, 21, 18, 12, 5, 2],
           [20.2, 17.4, 19.9, 18.7, 14.3, 10.6, 3.8, 4.1, 7.4, 13.1, 18.7, 21.0],
           [10.1, 9.4, 9.2, 6.6, 2.1, 0.4, 0, 0, 0.1, 1.2, 7.1, 12.1]),
}

# 天气: 名字 -> (路程倍数, 在外面时每天健康变化, 在外面时每天受多少辐射, 躲在车里时每天受多少辐射, 说明)
# 什么时候下雨下雪还是按真实的气候, 但核战争以后, 天上落下来的东西都不干净了
WEATHER = {
    "晴":         (1.0, 0, 0, 0, "天空是脏兮兮的黄色, 适合赶路"),
    "辐射尘云":   (1.0, 0, 0, 0, "灰褐色的云压得很低, 看着吓人, 不影响赶路"),
    "毒雾":       (0.6, -2, 0, 0, "黄绿色的毒雾看不清路, 车开得慢, 在外面会呛伤"),
    "黑雨":       (0.8, 0, 3, 0, "混着灰烬的黑雨, 路上泥泞, 在外面会受一点辐射"),
    "酸雨":       (0.7, -5, 0, 0, "在外面会受伤, 休息可以躲雨"),
    "辐射风暴":   (0.6, 0, 15, 5, "天空变成了绿色, 连闪电都是绿的, 在外面辐射很重, 躲在车里也挡不住全部"),
    "灰雪":       (0.5, 0, 2, 0, "核尘混在雪里, 积雪路滑, 车只能开平时一半的路, 在外面会受一点辐射"),
    "灰色暴风雪": (0, -3, 2, 0, "车根本开不动, 只能等雪停; 在外面会冻伤, 还会受一点辐射"),
    "辐射沙尘暴": (0.5, -1, 6, 0, "车只能开平时一半的路, 在外面会呛伤, 还会受辐射"),
}
WET_WEATHER = ["黑雨", "酸雨", "辐射风暴", "灰雪", "灰色暴风雪"]   # 算"下雨下雪"的天气
DIARY_WEATHER = ["辐射风暴", "灰色暴风雪"]   # 碰上这些天气要记进旅行日记

ACID_RAIN_CHANCE = 0.3    # 下雨的日子里, 下的是酸雨的机会 (不是酸雨就是黑雨)
STORM_CHANCE = 0.5        # 天热 (25 度以上) 时下雨, 是辐射风暴的机会 (就是废土上的雷暴)
BLIZZARD_CHANCE = 0.25    # 下雪的日子里, 是暴风雪的机会
FOG_CHANCE = 0.1          # 天凉 (12 度以下) 又不下雨的日子, 起毒雾的机会
DUST_STORM_CHANCE = 0.1   # 在又干又多风的地方, 不下雨的日子刮沙尘暴的机会
DUSTY_REGIONS = ["高平原", "落基山区", "蛇河平原", "哥伦比亚河谷"]

# 气温分几档 (按白天最高气温, 摄氏度。32 度和 38 度就是美国人常说的 90 度和 100 度华氏度):
# (到几度算这一档, 名字, 每人多喝几份水, 每人多吃几份食物, 在外面时每天健康变化, 没穿冬衣的人每天健康变化, 说明)
# 天热出汗要多喝水; 天冷身体要多烧热量保暖, 要多吃东西
TEMPERATURES = [
    (38, "酷热", 2, 0, -2, 0, "每人要多喝 2 份水, 在外面会中暑"),
    (32, "炎热", 1, 0, 0, 0, "每人要多喝 1 份水"),
    (20, "温暖", 0, 0, 0, 0, ""),
    (10, "凉爽", 0, 0, 0, 0, ""),
    (0, "寒冷", 0, 1, 0, -3, "每人要多吃 1 份食物, 没穿冬衣的人会冻伤"),
    (-99, "严寒", 0, 1, -1, -8, "每人要多吃 1 份食物, 没穿冬衣的人会严重冻伤, 穿了冬衣在外面也会受冻"),
]

# ---------- 辐射 ----------

# 每个人身上都有辐射值 (0 到 100), 不会自己降下来, 只能用排辐剂排掉。
# 辐射值分几档: (到多少算这一档, 名字, 每天健康变化)
RADIATION_LEVELS = [
    (80, "致命", -6),
    (50, "严重", -3),
    (25, "轻度", -1),
    (0, "", 0),
]
ANTI_RAD = 50          # 一支排辐剂能排掉多少辐射
SICKNESS_RADS = 40     # 「辐射病」事件一下子增加多少辐射

# 辐射热点: 路线经过几个真实的核设施附近, 停在这几段路上的每一天都要多受辐射 (开快一点能少待几天)。
# (从几公里, 到几公里, 名字, 在外面时每天受多少辐射, 躲在车里时每天受多少辐射, 介绍)
# 战争里这些地方出了什么事, 等背景故事定了再说, 所以现在只说"辐射偏高", 几个地方也一样重。
# 每一段都比车一天最多能开的路 (130 公里) 长, 不会一天就整段开过去、一点辐射都不受
HOTSPOTS = [
    (920, 1060, "导弹发射井一带", 6, 2, "南边的高平原下面, 埋着冷战时修的洲际导弹发射井。"),
    (1910, 2050, "爱达荷国家实验室一带", 6, 2, "北边的荒原上是爱达荷国家实验室, 冷战时在那里建过几十座试验用的核反应堆。"),
    (2720, 2861, "汉福德核基地下游", 6, 2, "哥伦比亚河上游是汉福德核基地, 当年美国造原子弹用的钚就是在那里造出来的。"),
]
HOTSPOT_WARNING = 350  # 离下一个辐射热点还有多远时, 状态栏开始提醒 (公里)

# ---------- 生病和受伤 ----------

# 这些老病现在都能治, 可核战争以后没有了干净的水、疫苗和医院, 它们又回来了。用药品能马上治好。
# 病和伤: 名字 -> (每天健康变化, 一般要几天才好, 得病时怎么说, 症状)
DISEASES = {
    "痢疾":     (-3, 5, "得了痢疾", "拉肚子拉得站不起来"),
    "霍乱":     (-6, 4, "得了霍乱", "上吐下泻, 每天要多喝 2 份水"),
    "伤寒":     (-3, 8, "得了伤寒", "一直发高烧"),
    "肺炎":     (-4, 6, "得了肺炎", "咳嗽、喘不上气"),
    "伤口感染": (-3, 6, "的伤口感染了", "伤口红肿化脓"),
    "骨折":     (-1, 12, "骨折了", "腿断了, 只能躺在车上"),
    "破伤风":   (-5, 5, "得了破伤风", "浑身抽筋"),
    "过度劳累": (-2, 3, "累倒了", "累得抬不起头"),
}
CHOLERA_WATER = 2     # 得了霍乱的人每天多喝几份水

SICK_CHANCE = 0.01                # 健康满分的人, 每天生病的机会
SICK_CHANCE_PER_HEALTH = 0.0005   # 健康每少 1 点, 生病的机会多这么多 (健康 40 的人: 1% + 3% = 4%)
COMMON_DISEASES = ["痢疾", "伤寒"]   # 平常最容易得的病
# 这些情况会让人更容易生病, 而且容易得某种病: 情况 -> (多出来的机会, 容易得的病)
SICK_CAUSES = {
    "挨饿":   (0.02, "痢疾"),       # 食物不够, 或者口粮选了"少"
    "受冻":   (0.03, "肺炎"),       # 天冷没冬衣穿
    "开太快": (0.03, "过度劳累"),   # 用"快"的速度赶路
    "辐射高": (0.02, None),         # 辐射让人抵抗力变差, 什么病都容易得
}
DIRTY_WATER_CHANCE = 0.15   # 没有干净的水、只能喝脏水的日子, 每个人得霍乱或痢疾的机会
INFECTION_CHANCE = 0.5      # 被咬伤、中枪以后伤口感染的机会
TETANUS_CHANCE = 0.08       # 搜刮废墟时被生锈的铁皮划伤、得破伤风的机会
SOLO_SICK_DAMAGE = 2        # 一个人生病没人照顾 (烧水做饭开车都得自己来), 每天多掉的健康

# 搜刮时可能找到的东西: 名字 -> (最少, 最多)
LOOT = {"食物": (10, 40), "水": (10, 30), "燃料": (3, 10),
        "子弹": (10, 30), "零件": (1, 1), "药品": (1, 2), "冬衣": (1, 2), "排辐剂": (1, 1)}

# 打猎: 要飞快打出来的词, 和猎物: 名字 -> (最少食物, 最多食物)
HUNT_WORDS = ["bang", "pow", "boom", "zap"]
ANIMALS = {"变异野兔": (10, 25), "双头鹿": (30, 60), "辐射野猪": (50, 90)}

# 过场动画和画面: 赶路 (跟着天气变)、过河、坐木筏的动画, 还有地标、据点、墓碑、结局的画和每个人的样子。
# 只在真正的终端里和网页版里有 (跑测试时没有)
ANIMATION = True          # 不想看就改成 False
ANIMATION_FRAMES = 24     # 一共几帧
ANIMATION_DELAY = 0.06    # 每帧停几秒 (24 帧大约 1.5 秒)
PICTURE_DELAY = 0.03      # 地标、据点这些画一行一行地画出来, 每行停几秒
TITLE_ANIMATION_DELAY = 0.12   # 主菜单的小动画 (车一直往前开、蘑菇云翻滚) 每帧停几秒

# 换画面: 像原版那样一个画面一个画面地换。每个画面都从屏幕最上面写起, 屏幕上有还没看的字时, 先等玩家按回车再换。
# 只在真正的终端里和网页版里换 (跑测试时还是一直往下写)
SCREENS = True            # 想要以前那样一直往下滚, 就改成 False
# 一直往前开: 选「继续前进」以后, 车像原版一样一直往前开, 动画一直在动, 下面的日期、路程跟着变;
# 路上出了事, 说完了接着开; 到了地方、或者玩家按了回车才停下来。要换画面 (SCREENS) 才能一直开
KEEP_DRIVING = True       # 改成 False 就是选一次「继续前进」只走一天
# 大画面: 窗口够大的时候 (电脑的终端窗口拉大, 或者在电脑、平板上打开网页版), 每天的菜单和开车的画面像原版 CD 版那样,
# 一个画面分成几块: 动画、状态、路线图、最近的事。窗口太小就用普通的画面
DASHBOARD = True          # 不想要就改成 False
DASHBOARD_WIDTH = 100     # 大画面有多宽 (窗口要比这个宽一点才用)
DASHBOARD_ROWS = 28       # 窗口至少要有几行才用大画面
# 网页版的图形界面: 按钮、状态面板、地图、旅行日记都由网页来画, 游戏只要告诉网页现在的状态 (gui_update) 和在问什么。
# 这时候游戏自己就不画状态栏和大画面了。由 web/run_in_browser.py 打开, 在电脑上玩一直是 False
GUI = False
DIARY_PAGE = 10           # 换画面的时候, 旅行日记一页放几条 (一条常常要占两行)
PARTY_PAGE = 2            # 换画面的时候, 查看队伍一页放几个人 (每个人都有头像, 要占好几行)
DRIVE_DAY_FRAMES = 20     # 一直往前开的时候, 动画播几帧算过了一天 (每帧 ANIMATION_DELAY 秒, 20 帧大约 1.2 秒)
WARN_WEATHER = ["酸雨", "辐射风暴", "辐射沙尘暴"]   # 一直往前开的时候, 天气变成这几种要提醒一下 (在外面伤人, 也许该停下来躲进车里)

# 音乐: 用代码做的老式游戏机音乐, 放在 music 文件夹里 (做音乐的程序是 music/make_music.py, 想改曲子就改它)。
# 只在真正的终端里和网页版里放 (跑测试时不放)。网页版上还有一个「♪」按钮可以关掉
MUSIC = True              # 不想听就改成 False
MUSIC_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "music")
# 什么时候放什么: 名字 -> (文件, 怎么放)。
# 「循环」是背景音乐, 一直放到换成别的; 「一段」放完接着放原来的背景音乐; 「结尾」放完就安静了
MUSIC_TRACKS = {
    "主菜单": ("title.wav", "循环"),       # 自己写的, 有点悲伤的废土曲子
    "赶路": ("travel.wav", "循环"),        # 《哦! 苏珊娜》, 1848 年拓荒者一路上唱的歌
    "据点": ("outpost.wav", "一段"),
    "热点": ("geiger.wav", "一段"),        # 盖革计数器的咔嗒声
    "去世": ("taps.wav", "一段"),          # 《熄灯号》
    "到达": ("arrive.wav", "结尾"),
    "全军覆没": ("game_over.wav", "结尾"),
}

# 彩色界面: 只在真正的终端里和网页版里有颜色 (跑测试时没有)。不想要颜色就改成 False
COLOR = True
# 用到的颜色: 名字 -> ANSI 控制字符里的颜色编号 (终端和网页版都认得)
COLORS = {"红": "31", "绿": "32", "黄": "33", "蓝": "34", "紫": "35", "青": "36", "灰": "90"}

# 队伍最多几个人 (包括主角)
MAX_PARTY = 4

# 每个据点里有 1 个人愿意免费跟你走: 据点名字 -> (这个人的名字, 职业)
RECRUITS = {"卡尼堡": ("杰克", "老兵"), "拉勒米堡": ("玛莎", "医生"), "布里杰堡": ("埃迪", "机械师"),
            "霍尔堡": ("汉娜", "猎人"), "博伊西堡": ("本", "商人"), "达尔斯": ("罗莎", "拾荒者")}

# 据点里的人加入时自带的口粮
RECRUIT_BRINGS = {"食物": 60, "水": 40}

# 职业的特长: 只要这个人还活着、在队伍里, 特长就一直有用
SKILLS = {
    "老兵": "遇到劫匪开枪一定能打赢, 赶走野狗只要 5 发子弹",
    "医生": "用药一次能恢复 60 点健康 (平时是 35); 有医生照顾, 别人生病受伤好得更快",
    "机械师": "车坏了不用零件也能当场修好; 过河时给车接上通气管, 车能开过更深的水",
    "猎人": "打猎得到的肉多一半",
    "商人": "在据点买东西打八折, 卖东西能卖到六成的价钱 (平时只有一半)",
    "拾荒者": "搜刮废墟一定有收获, 一次能找到两样东西",
}

# 路上可能遇到的陌生人
STRANGER_NAMES = ["迈克", "安娜", "老乔", "凯特", "比尔"]


# ========== 小工具 ==========

# 是不是在网页版里 (网页里的 Python 叫 Pyodide, 它的 sys.platform 是 "emscripten")
IN_BROWSER = sys.platform == "emscripten"

# 屏幕上的字: unread 是有没有玩家还没看过的新消息 (换画面前要先等玩家看完);
# driving 是车是不是正在一直往前开 (这时候例行消息不印出来, 动画下面的状态栏都看得到);
# room 是开车的时候, 动画 (或者大画面) 下面还有没有地方写路上发生的事; frame 是车开到动画的第几帧 (停下来以后画面接得上)
screen = {"unread": False, "driving": False, "room": True, "frame": 0}


def print(*args, **kwargs):
    """跟 Python 自带的 print 一样, 只是顺便记下「屏幕上多了新消息」。这个文件里的 print 都会经过这里。
    每天都会说一遍的例行消息 (比如今天开了多远) 不算新消息, 要用 print_routine"""
    builtins.print(*args, **kwargs)
    if any(str(arg).strip() for arg in args):
        screen["unread"] = True


def print_routine(text):
    """例行消息: 跟 print 一样显示出来, 只是不算新消息, 换画面前不用等玩家看。
    一直往前开的时候干脆不印 (动画下面的状态栏都看得到), 不然每天都要按一次回车"""
    if not screen["driving"]:
        builtins.print(text)


def can_clear_screen():
    """能不能换画面: 设置里没关掉, 而且是在真正的终端里或者网页版里"""
    return SCREENS and (can_read_keys() or IN_BROWSER)


def clear_screen():
    """把屏幕清空, 光标回到左上角。\\x1b[H 是回到左上角, \\x1b[2J 是清屏, \\x1b[3J 是连往上翻才看得到的旧字也清掉"""
    builtins.print("\x1b[H\x1b[2J\x1b[3J", end="", flush=True)
    screen["unread"] = False


def event_screen():
    """路上出事、有人去世的时候用: 一直往前开、屏幕上又没有没看过的字, 就直接写在动画下面 (像原版那样, 车还在画面上);
    别的时候换一个新画面"""
    if screen["driving"] and screen["room"] and not screen["unread"]:
        return
    new_screen()


def new_screen():
    """换一个新画面: 屏幕上还有玩家没看过的新消息, 就先等玩家按回车; 再把屏幕清空, 从最上面写起。
    不能换画面的时候 (比如跑测试) 什么都不做, 字还是一直往下写"""
    if not can_clear_screen():
        return
    if screen["unread"]:
        wait_enter()
    clear_screen()


def wait_enter(prompt="按回车继续……"):
    """等玩家按回车。在终端里只认回车键, 按别的键什么都不会发生, 也不会显示出来"""
    if not can_read_keys():
        input(prompt)
    else:
        print(prompt, end="", flush=True)
        old_settings = start_reading_keys()
        forget_keys()   # 这句话出来以前按的回车不算 (比如开车时按的), 不然画面一闪就过去了
        try:
            while True:
                keys = read_keys()
                if "\x03" in keys:                      # Ctrl+C
                    raise KeyboardInterrupt
                if "\x04" in keys or "\x1a" in keys:    # Ctrl+D (Mac) 或 Ctrl+Z (Windows)
                    raise EOFError
                if "\r" in keys or "\n" in keys:
                    break
        finally:
            stop_reading_keys(old_settings)
        print()
    screen["unread"] = False


def stop_pressed(seconds):
    """一直往前开的时候用: 最多等 seconds 秒, 看玩家有没有按键要停下来 (按过的键都读掉, 不留给下一个问题)。
    这时候终端已经是「按一个键就读一个键」的状态, 一按就知道。
    网页版里 run_in_browser.py 会把它换成: 看玩家有没有点屏幕或者按回车"""
    if not can_read_keys():
        time.sleep(seconds)
        return False
    if not key_ready(seconds):
        return False
    if "\x03" in read_keys():   # Ctrl+C
        raise KeyboardInterrupt
    forget_keys()
    return True


def can_read_keys():
    """是不是在真正的终端里玩, 能一个键一个键地读。跑测试或者用管道输入时就不是"""
    return sys.stdin.isatty() and sys.stdout.isatty() and bool(termios or msvcrt)


def start_reading_keys():
    """让终端进入"按一个键就读一个键"的状态 (不用等回车, 按的键也不会自己显示出来)。
    返回原来的设置, 用完要交给 stop_reading_keys 还原"""
    if msvcrt:
        return None
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    return old_settings


def stop_reading_keys(old_settings):
    if old_settings is not None:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_settings)


def read_keys():
    """读玩家刚按下的键。方向键这类特殊键会被丢掉, 返回空字符串"""
    if msvcrt:
        key = msvcrt.getwch()
        if key in ("\x00", "\xe0"):   # 方向键之类, 后面还跟着一个字符, 一起丢掉
            msvcrt.getwch()
            return ""
        return key
    data = os.read(sys.stdin.fileno(), 64)
    if data.startswith(b"\x1b"):        # 方向键之类会发来一串以 ESC 开头的字符
        return ""
    return data.decode("utf-8", errors="ignore")


def forget_keys():
    """把之前按了、还没读的键都丢掉"""
    if msvcrt:
        while msvcrt.kbhit():
            msvcrt.getwch()
    else:
        termios.tcflush(sys.stdin.fileno(), termios.TCIFLUSH)


def key_ready(seconds):
    """最多等 seconds 秒, 看玩家有没有按键 (在终端里一个键一个键读的时候用)"""
    if msvcrt:
        end = time.time() + seconds
        while time.time() < end:
            if msvcrt.kbhit():
                return True
            time.sleep(0.01)
        return msvcrt.kbhit()
    return bool(select.select([sys.stdin], [], [], seconds)[0])


def ask_number(prompt, low, high, idle=None):
    """让玩家输入 low 到 high 之间的数字。
    只有数字键、退格键和回车有用, 按空格、字母这些键什么都不会发生;
    回车也只在输入的数字在范围里时才算数。
    idle: 在终端里等按键的时候, 每隔 TITLE_ANIMATION_DELAY 秒做一次的事 (主菜单用它播动画)"""
    if not can_read_keys():
        number = ask_number_by_line(prompt, low, high)
    else:
        print(prompt, end="", flush=True)
        old_settings = start_reading_keys()
        try:
            number = read_number(low, high, idle)
        finally:
            stop_reading_keys(old_settings)   # 不管怎么结束 (包括按 Ctrl+C), 都要把终端还原
    screen["unread"] = False   # 玩家回答了, 说明屏幕上的字都看过了
    return number


def read_number(low, high, idle=None):
    text = ""
    while True:
        if idle and not key_ready(TITLE_ANIMATION_DELAY):   # 一会儿都没按键, 就先做别的事
            idle()
            continue
        for key in read_keys():
            if key == "\x03":                       # Ctrl+C
                raise KeyboardInterrupt
            if key in ("\x04", "\x1a"):             # Ctrl+D (Mac) 或 Ctrl+Z (Windows)
                raise EOFError
            if key in ("\r", "\n"):
                if text and low <= int(text) <= high:
                    print()
                    return int(text)
            elif key in ("\x7f", "\b"):             # 退格键: 删掉最后一个数字
                if text:
                    text = text[:-1]
                    print("\b \b", end="", flush=True)
            elif key.isdecimal():
                digit = str(int(key))                 # 全角的 ３ 也当成 3
                if text != "0" and int(text + digit) <= high:
                    text += digit
                    print(digit, end="", flush=True)


def ask_number_by_line(prompt, low, high):
    """不能一个键一个键读的时候 (比如跑测试), 就整行读, 输错了重新问"""
    while True:
        text = input(prompt).strip()
        if text.isdecimal() and low <= int(text) <= high:
            return int(text)
        print(f"请输入 {low} 到 {high} 之间的数字。")


def colored(text, color, bold=False):
    """给一段字上色, 比如 colored("危险", "红")。颜色关掉了、或者不在终端里 (比如跑测试), 就原样返回"""
    if not color or not COLOR or not (can_read_keys() or IN_BROWSER):
        return text
    code = COLORS[color] + (";1" if bold else "")
    return f"\x1b[{code}m{text}\x1b[0m"   # \x1b[0m 是把颜色变回原样


def title(text, color="黄"):
    """事件和地名的标题, 比如【劫匪】, 带上颜色更显眼"""
    return colored(f"【{text}】", color, bold=True)


def health_color(h):
    """健康好是绿的, 一般是黄的, 差了是红的"""
    if h >= 70:
        return "绿"
    if h >= 40:
        return "黄"
    return "红"


def health_word(h):
    if h >= 70:
        return "良好"
    if h >= 40:
        return "一般"
    if h >= 15:
        return "很差"
    return "危险"


def pick(game, male_word, female_word):
    """按主角的性别选一个称呼, 比如 pick(game, "大哥", "大姐")"""
    return male_word if game["gender"] == "男" else female_word


def you(game):
    """队伍里只有一个人时说"你", 有好几个人时说"你们" """
    return "你" if len(game["party"]) == 1 else "你们"


def everyone(game):
    """队伍里只有一个人时说"你", 有好几个人时说"大家" """
    return "你" if len(game["party"]) == 1 else "大家"


def show_distance(game, km):
    """按玩家选的单位显示路程, 比如选了英里时 show_distance(game, 40) 是 "25 英里" """
    return f"{round(km * UNITS[game['unit']])} {game['unit']}"


def show_weight(game, grams):
    """按玩家选的单位显示重量: 选了公里就用公斤, 选了英里就用磅。比如 show_weight(game, 8000) 是 "8 公斤" """
    name, per_kg = WEIGHT_UNITS[game["unit"]]
    value = grams / 1000 * per_kg
    if value >= 10:
        return f"{round(value)} {name}"
    return f"{round(value, 2):g} {name}"   # 很轻的东西留两位小数, 比如子弹 0.02 公斤


def show_length(game, meters):
    """河有多宽、多深: 选了公里就用米, 选了英里就用英尺。比如 show_length(game, 1.2) 是 "1.2 米" """
    if game["unit"] == "英里":
        value, name = meters * 3.28084, "英尺"
    else:
        value, name = meters, "米"
    if value >= 10:
        return f"{round(value)} {name}"
    return f"{round(value, 1):g} {name}"


def load_of(game):
    """车上现在有多重 (克): 人加上所有物资"""
    stuff = sum(game["supplies"][item] * WEIGHTS[item] for item in WEIGHTS)
    return len(game["party"]) * PERSON_WEIGHT + stuff


def room_for(game, item):
    """车上还能再装几个这种物资"""
    return max(0, (CAR_CAPACITY - load_of(game)) // WEIGHTS[item])


def has_seat_for_one_more(game):
    """车上还坐不坐得下一个人 (车太重了就坐不下)"""
    return CAR_CAPACITY - load_of(game) >= PERSON_WEIGHT


def add_supplies(game, item, amount):
    """往车上装东西, 装不下的只能丢下。返回真正装上车的数量"""
    fits = min(amount, room_for(game, item))
    game["supplies"][item] += fits
    if fits < amount:
        print(f"车上装不下了, 有 {amount - fits} {MEASURES[item]}{item}只能丢下。")
    return fits


def show_temperature(game, celsius):
    """显示气温: 选了公里就用摄氏度, 选了英里就用华氏度 (美国人习惯用的)"""
    if game["unit"] == "英里":
        return f"{round(celsius * 9 / 5 + 32)}°F"
    return f"{celsius}°C"


def date_of(game, day=None):
    """第几天是几月几号, 返回 (月, 日)。第 1 天是出发那个月的 1 号。day 不填就是今天"""
    day = game["day"] if day is None else day
    month = game["start_month"]
    while day > MONTH_DAYS[month - 1]:
        day -= MONTH_DAYS[month - 1]
        month = month % 12 + 1
    return month, day


def date_text(game, day=None):
    """比如 "5月12日" """
    month, date = date_of(game, day)
    return f"{month}月{date}日"


def skilled(game, job):
    """队伍里活着的人里, 谁是这个职业。没有就返回 None"""
    for name in game["party"]:
        if game["jobs"].get(name) == job:
            return name
    return None


def random_member(game):
    return random.choice(list(game["party"]))


def write_diary(game, text, km=None, day=None):
    """往旅行日记里记一笔: 第几天、走到哪了、发生了什么。只记大事, 不记每天的赶路。
    km 和 day 不填, 就用现在走到的路程和今天是第几天"""
    km = game["distance"] if km is None else km
    day = game["day"] if day is None else day
    game["diary"].append(f"{date_text(game, day)} (第 {day} 天), 已走 {show_distance(game, km)}: {text}")


def show_diary(game):
    """查看旅行日记。不花时间"""
    print("\n========== 旅行日记 ==========")
    if not game["diary"]:
        print("日记里还什么都没有。")
    for i, line in enumerate(game["diary"]):
        if i and i % DIARY_PAGE == 0 and can_clear_screen():   # 一页放不下了, 翻到下一页
            wait_enter("按回车看下一页……")
            clear_screen()
            print("\n========== 旅行日记 (接上页) ==========")
        print(line)


def check_deaths(game):
    for name in list(game["party"]):
        if game["party"][name] <= 0:
            sick = game["sick"].get(name)
            if sick:
                lose_member(game, name, f"死于{sick[0]}。")
            else:
                lose_member(game, name, "没能撑下去, 去世了。", "去世了。")


def lose_member(game, name, saying, diary_saying=None):
    """一个队员没了: 从队伍里去掉, 记进日记。
    saying 是屏幕上怎么说, diary_saying 是日记里怎么写 (不填就跟屏幕上一样)"""
    del game["party"][name]
    game["rads"].pop(name, None)
    game["sick"].pop(name, None)
    game["dead"].append(name)
    event_screen()
    if game["party"]:   # 最后一个人也没了的话, 放的是全军覆没的音乐
        play_music("去世")
    show_picture(TOMBSTONE, "灰", ["", "", f"这里长眠着 {name}"])
    print(colored(f"!!! {name} {saying}", "红", bold=True))
    write_diary(game, f"{name} {diary_saying or saying}")


def hurt(game, name, amount):
    """让一个队员掉血"""
    game["party"][name] = max(0, game["party"][name] - amount)
    check_deaths(game)


def change_all_health(game, amount):
    """所有队员的健康一起变化(正数是加, 负数是减)"""
    for name in game["party"]:
        game["party"][name] = max(0, min(100, game["party"][name] + amount))
    check_deaths(game)


def freeze(game, cold_health):
    """天冷时, 冬衣不够每人一套的话, 没穿上的人会冻伤。冬衣按队伍里的顺序分, 主角先穿。
    返回冻着的人 (他们也更容易得肺炎)"""
    cold = list(game["party"])[game["supplies"]["冬衣"]:]
    if cold_health == 0 or not cold:
        return []
    who = "你" if len(game["party"]) == 1 else "、".join(cold)
    print_routine(f"天太冷了, {who}没有冬衣穿, 冻伤了!")
    for name in cold:
        hurt(game, name, -cold_health)
    return cold


def radiation_level(rads):
    """这个辐射值属于哪一档: 返回 RADIATION_LEVELS 里的那一行"""
    for level in RADIATION_LEVELS:
        if rads >= level[0]:
            return level
    return RADIATION_LEVELS[-1]


def irradiate(game, name, amount):
    """让一个人受到辐射 (amount 是负数就是排掉辐射)。辐射值在 0 到 100 之间"""
    game["rads"][name] = max(0, min(100, game["rads"].get(name, 0) + amount))


def hotspot_here(game):
    """现在是不是在辐射热点里: 是的话返回 HOTSPOTS 里的那一行, 不是就返回 None"""
    for spot in HOTSPOTS:
        if spot[0] <= game["distance"] < spot[1]:
            return spot
    return None


def next_hotspot(game):
    """前面的下一个辐射热点 (HOTSPOTS 里的那一行), 后面都没有了就返回 None"""
    for spot in HOTSPOTS:
        if spot[0] > game["distance"]:
            return spot
    return None


def radiation_damage(game):
    """辐射值高的人每天掉血, 辐射越高掉得越多"""
    sick = [name for name in game["party"] if radiation_level(game["rads"].get(name, 0))[2] < 0]
    if not sick:
        return
    who = "你" if len(game["party"]) == 1 else "、".join(sick)
    print_routine(f"辐射在{who}的身体里作怪, 身体越来越差。")
    for name in sick:
        hurt(game, name, -radiation_level(game["rads"].get(name, 0))[2])


def get_sick(game, name, disease):
    """让一个人得病或受伤。每人同时只会有一种病或伤, 已经病了的人不会再得新的"""
    if name not in game["party"] or name in game["sick"]:
        return
    _, days, saying, symptom = DISEASES[disease]
    game["sick"][name] = [disease, days]
    print(f"{title(disease, '红')}{name}{saying}! {symptom}。")
    if len(game["party"]) == 1:
        print("一个人生病, 没人照顾, 什么都得自己硬撑。")
    write_diary(game, f"{name}{saying}。")


def sickness_day(game, indoors):
    """生病受伤的人每天掉血, 同时一天天好起来。躲在车里休养好得快一倍, 有医生照顾也更快"""
    doctor = skilled(game, "医生")
    for name in list(game["sick"]):
        disease, days = game["sick"][name]
        damage = -DISEASES[disease][0]
        if len(game["party"]) == 1:
            damage += SOLO_SICK_DAMAGE
        days -= 2 if indoors else 1
        if doctor and doctor != name:
            days -= 1
        hurt(game, name, damage)
        if name not in game["party"]:   # 没撑过去
            continue
        if days <= 0:
            del game["sick"][name]
            print_routine(f"{name}的{disease}好了。")
        else:
            game["sick"][name][1] = days


def sick_odds(game, chance):
    """生病受伤的机会按难度变: 简单少一些, 困难多一些"""
    return chance * DIFFICULTIES[game["difficulty"]][3] / 100


def catch_diseases(game, hungry, cold_people, traveling):
    """每天看看有没有人生病: 健康越差越容易病; 挨饿、受冻、开太快、辐射高, 也会更容易病"""
    for name in list(game["party"]):
        if name in game["sick"]:
            continue
        reasons = []
        if hungry:
            reasons.append("挨饿")
        if name in cold_people:
            reasons.append("受冻")
        if traveling and game["pace"] == 3:
            reasons.append("开太快")
        if radiation_level(game["rads"].get(name, 0))[2]:
            reasons.append("辐射高")
        chance = SICK_CHANCE + (100 - game["party"][name]) * SICK_CHANCE_PER_HEALTH
        likely = list(COMMON_DISEASES)
        for reason in reasons:
            extra, disease = SICK_CAUSES[reason]
            chance += extra
            if disease:
                likely += [disease, disease]   # 跟这个情况有关的病更容易得
        if random.random() < sick_odds(game, chance):
            get_sick(game, name, random.choice(likely))


def find_supplies(game):
    item = random.choice(list(LOOT))
    low, high = LOOT[item]
    amount = random.randint(low, high)
    print(f"找到了 {amount} {MEASURES[item]}{item}!")
    add_supplies(game, item, amount)


def climate_here(game):
    """现在走到的地方属于哪个气候区: 返回 CLIMATE 里的那一项 (地区名, 平均最高气温, 下雨下雪天数, 下雪天数)"""
    start = max(km for km in CLIMATE if km <= game["distance"])
    return CLIMATE[start]


def temperature_level(temperature):
    """这个气温属于哪一档: 返回 TEMPERATURES 里的那一行"""
    for level in TEMPERATURES:
        if temperature >= level[0]:
            return level
    return TEMPERATURES[-1]


def weather_color(weather):
    """天气的颜色: 不影响赶路的不上色, 会伤人或者拖慢车的是黄的, 最凶的是红的"""
    if weather in ["辐射风暴", "灰色暴风雪"]:
        return "红"
    speed, outdoor_health, outdoor_rads, _, _ = WEATHER[weather]
    if speed < 1 or outdoor_health < 0 or outdoor_rads > 0:
        return "黄"
    return None


def temperature_color(temperature):
    """酷热和严寒是红的, 炎热和寒冷是黄的"""
    name = temperature_level(temperature)[1]
    if name in ["酷热", "严寒"]:
        return "红"
    if name in ["炎热", "寒冷"]:
        return "黄"
    return None


def weather_report(game):
    """今天的天气和气温对赶路有什么影响, 用一句话说清楚"""
    notes = [WEATHER[game["weather"]][-1]]
    temperature_note = temperature_level(game["temperature"])[-1]
    if temperature_note:
        notes.append(temperature_note)
    return "; ".join(notes)


def roll_weather(game):
    """按现在走到的地方和今天的日期, 随机决定今天的天气和气温。
    平常有多热、一个月有几天下雨下雪, 都按当地气象站的历年平均来; 冷热和雨雪常常会连着好几天"""
    region, highs, wet_days, snow_days = climate_here(game)
    month = date_of(game)[0] - 1   # 列表从 0 开始数, 所以 1 月是第 0 个
    old_weather = game["weather"]

    # 这几天比平常热几度 (负数是冷): 每天变一点, 又慢慢回到平常, 所以热浪和寒潮会持续几天
    game["warmth"] = round(game["warmth"] * 0.7) + random.randint(-5, 5)
    temperature = highs[month] + game["warmth"]

    # 下不下雨雪: 昨天下了, 今天接着下的机会大一些; 昨天没下, 今天的机会就小一些。
    # 这样一个月算下来, 下雨下雪的天数还是跟真实的一样多
    chance = wet_days[month] / MONTH_DAYS[month]
    if old_weather in WET_WEATHER:
        chance = (1 + chance) / 2
    else:
        chance = chance / 2

    if random.random() < chance:
        temperature -= 3   # 阴雨天凉快一些
        if random.random() < snow_days[month] / wet_days[month]:
            if temperature > 2:   # 下雪说明冷空气来了, 接下来几天也会冷一些
                game["warmth"] -= temperature - 2
                temperature = 2
            weather = "灰色暴风雪" if random.random() < BLIZZARD_CHANCE else "灰雪"
        elif temperature >= 25 and random.random() < STORM_CHANCE:
            weather = "辐射风暴"
        elif random.random() < ACID_RAIN_CHANCE:
            weather = "酸雨"
        else:
            weather = "黑雨"
    elif region in DUSTY_REGIONS and random.random() < DUST_STORM_CHANCE:
        weather = "辐射沙尘暴"
    elif temperature <= 12 and random.random() < FOG_CHANCE:
        weather = "毒雾"
    else:
        weather = random.choice(["晴", "晴", "辐射尘云"])

    game["weather"] = weather
    game["temperature"] = temperature
    # 这几天下了多少雨雪 (河水会跟着涨): 以前下的慢慢退掉, 今天下了就再加 1
    game["rain"] = round(game["rain"] * RAIN_FADE + (1 if weather in WET_WEATHER else 0), 2)
    if weather in DIARY_WEATHER and weather != old_weather:
        write_diary(game, f"遇到了{weather}。")


# ========== 开始游戏 ==========

def new_game():
    return {
        "day": 1,
        "distance": 0,
        "difficulty": 2,    # 难度 (开局时玩家选, 见 DIFFICULTIES)。以前的存档没有难度, 就算普通
        "money": DIFFICULTIES[2][1],
        "supplies": {item: 0 for item in PRICES},
        "party": {},        # 队员名字 -> 健康(0 到 100)
        "dead": [],         # 路上去世的人
        "ration": 2,
        "pace": 2,
        "start_month": 4,   # 几月出发 (开局时玩家选)
        "weather": "晴",
        "temperature": 20,  # 今天白天的最高气温 (摄氏度)
        "warmth": 0,        # 这几天比平常热几度 (负数是冷)
        "rain": 0,          # 这几天下了多少雨雪 (下得越多, 河水越深)
        "visited": [],      # 已经到过的地方 (地标、据点, 还有进过的辐射热点)
        "seeds": False,     # 有没有找到种子库(隐藏结局)
        "gender": "男",     # 主角的性别
        "unit": "公里",     # 显示路程用的单位
        "leader": "",       # 主角的名字
        "jobs": {},         # 队员名字 -> 职业 (主角和路上的陌生人没有职业)
        "rads": {},         # 队员名字 -> 辐射值 (0 到 100, 没记的就是 0)
        "sick": {},         # 生病受伤的队员: 名字 -> [病名, 还要几天才好]
        "diary": [],        # 旅行日记: 路上发生的大事, 一条一条记下来
    }


def setup(game):
    new_screen()
    choose_difficulty(game)
    unit = ask_number("距离单位: 1. 公里  2. 英里  ", 1, 2)
    game["unit"] = "公里" if unit == 1 else "英里"
    new_screen()
    print("\n核战争已经过去二十年了。")
    print("你被赶出了密苏里州独立城地下的避难所。")
    print(f"你要一个人开车, 沿着当年拓荒者走过的俄勒冈小道, "
          f"去 {show_distance(game, TOTAL_DISTANCE)}外的{DESTINATION}。")
    print("路上的据点里也许能遇到愿意跟你走的人。\n")
    leader = input("你叫什么名字? (直接按回车就叫\"队长\") ").strip() or "队长"
    gender = ask_number("你的性别: 1. 男  2. 女  ", 1, 2)
    game["gender"] = "男" if gender == 1 else "女"
    show_picture(PORTRAITS[game["gender"]], words=["", "", f"{leader}, 这就是你。"])
    print("\n什么时候出发? 当年的拓荒者大多在 4、5 月出发。")
    print("早走天还冷, 山里可能还在下雪, 要带冬衣; 晚走天热, 路上要多喝水。")
    game["start_month"] = ask_number(f"出发月份 ({FIRST_MONTH}~{LAST_MONTH} 月): ", FIRST_MONTH, LAST_MONTH)
    game["leader"] = leader
    game["party"][leader] = 100
    write_diary(game, f"{leader}被赶出了独立城地下的避难所, 一个人踏上了俄勒冈小道。")
    roll_weather(game)   # 出发这天的天气

    new_screen()   # 先看出发前的提示, 按回车再进商店 (像原版那样)
    print("\n出发前可以在营地买东西。")
    print("提示: 每人每天要吃食物、喝 1 份水, 车每天要用燃料。子弹可以打猎, 也可以防身。"
          "天冷时每人要有一套冬衣。")
    print("      路上会生病受伤, 药品能治好; 辐射会在身体里越积越多, 只有排辐剂能把它排掉。")
    print("      路上要过好几条大河, 有的河边有渡船, 坐渡船要花钱, 别把钱一下子全花光。")
    print("      有几段路靠近核设施, 辐射偏高, 排辐剂要多备一些。")
    shop(game)


def choose_difficulty(game):
    """开局选难度: 决定一开始有多少钱、路上出事和生病的机会, 还有得分要乘多少"""
    print("\n选难度 (越难得分越高):")
    for number, (name, money, _, _, score, note) in DIFFICULTIES.items():
        print(f"{number}. {name}: 一开始有 {money} 块钱, {note}。得分 ×{score / 100:g}")
    game["difficulty"] = ask_number("选哪个? ", 1, len(DIFFICULTIES))
    game["money"] = DIFFICULTIES[game["difficulty"]][1]


def cost_of(game, item, amount):
    """买 amount 个 item 要花多少钱。队伍里有商人就打八折, 有零头往上算 1 块"""
    cost = amount * PRICES[item]
    if skilled(game, "商人"):
        cost = (cost * 8 + 9) // 10
    return cost


def sale_price(game, item, amount):
    """在据点卖 amount 个 item 能拿到多少钱: 平时只给一半的价钱, 有商人帮着讲价能拿到六成。零头不算"""
    share = MERCHANT_SELL_SHARE if skilled(game, "商人") else SELL_SHARE
    return amount * PRICES[item] * share // 100


def shop(game, can_sell=False):
    """商店。can_sell=True 表示在路上的据点里, 还可以把东西卖掉换钱 (出发前的营地只能买)"""
    items = list(PRICES)
    while True:
        new_screen()   # 每买一样, 商店的画面都重新画一遍 (钱和车上的东西都变了)
        print(f"\n------ 商店 ------  你有 {game['money']} 块钱")
        print(f"车上: {show_weight(game, load_of(game))} / {show_weight(game, CAR_CAPACITY)}, "
              f"还能装 {show_weight(game, max(0, CAR_CAPACITY - load_of(game)))}")
        merchant = skilled(game, "商人")
        if merchant:
            print(f"商人{merchant}帮你讲价, 买什么都打八折。")
        for i, item in enumerate(items, 1):
            measure = MEASURES[item]
            print(f"{i}. {item}  {PRICES[item]} 块一{measure}, 每{measure} {show_weight(game, WEIGHTS[item])}"
                  f"  (现在有 {game['supplies'][item]})")
        if can_sell:
            print(f"{len(items) + 1}. 卖东西")
        print("0. 离开商店")
        choice = ask_number("买什么? ", 0, len(items) + 1 if can_sell else len(items))
        if choice == 0:
            new_screen()   # 走出商店, 把商店的画面换掉
            return
        if choice == len(items) + 1:
            sell(game)
            continue
        item = items[choice - 1]
        most = game["money"] // PRICES[item]
        while cost_of(game, item, most + 1) <= game["money"]:   # 打折以后能多买几个
            most += 1
        if room_for(game, item) < most:
            most = room_for(game, item)
            print(f"车上只装得下 {most} {MEASURES[item]}{item}了。")
        amount = ask_number(f"买多少{item}? (最多 {most}) ", 0, most)
        game["supplies"][item] += amount
        game["money"] -= cost_of(game, item, amount)


def sell(game):
    """在据点卖东西换钱。卖掉的东西也会让车变轻"""
    items = list(PRICES)
    share = MERCHANT_SELL_SHARE if skilled(game, "商人") else SELL_SHARE
    new_screen()
    print(f"\n------ 卖东西 ------  据点的人只给买价的 {share}%")
    merchant = skilled(game, "商人")
    if merchant:
        print(f"商人{merchant}帮你讲价, 能卖到六成的价钱。")
    for i, item in enumerate(items, 1):
        measure = MEASURES[item]
        print(f"{i}. {item}  {PRICES[item] * share / 100:g} 块一{measure}  (现在有 {game['supplies'][item]})")
    print("0. 不卖了")
    choice = ask_number("卖什么? ", 0, len(items))
    if choice == 0:
        return
    item = items[choice - 1]
    have = game["supplies"][item]
    if have == 0:
        print(f"你没有{item}可以卖。")
        return
    amount = ask_number(f"卖多少{item}? (最多 {have}) ", 0, have)
    money = sale_price(game, item, amount)
    game["supplies"][item] -= amount
    game["money"] += money
    if amount:
        print(f"卖掉了 {amount} {MEASURES[item]}{item}, 拿到 {money} 块钱。")


def show_status(game):
    s = game["supplies"]
    left = TOTAL_DISTANCE - game["distance"]
    print(colored(f"\n==== {date_text(game)} (第 {game['day']} 天) | 已走 {show_distance(game, game['distance'])}"
                  f" | 还剩 {show_distance(game, left)} ====", "青", bold=True))
    percent = game["distance"] * 100 // TOTAL_DISTANCE
    print(f"路程: {colored(progress_bar(game['distance'], TOTAL_DISTANCE, 20), '青')} {percent}%")
    temperature = game["temperature"]
    print(f"地区: {climate_here(game)[0]}  天气: {colored(game['weather'], weather_color(game['weather']))}  "
          f"气温: {show_temperature(game, temperature)} "
          f"{colored(temperature_level(temperature)[1], temperature_color(temperature))}")
    print(f"    {weather_report(game)}")
    print("物资: " + "  ".join(f"{k} {v}" for k, v in s.items()) + f"  钱 {game['money']}")
    print("队员:")   # 每人一行, 前面是健康条
    for n, h in game["party"].items():
        job = f"[{game['jobs'][n]}]" if n in game["jobs"] else ""
        sick = game["sick"].get(n)
        sick_note = colored(f" {sick[0]}", "红") if sick else ""
        rads = game["rads"].get(n, 0)
        rads_note = colored(f" 辐射{rads}", "紫") if radiation_level(rads)[2] else ""   # 辐射到了会掉血的程度才显示
        print(f"  {health_bar(h)} {n}{job} {colored(f'{health_word(h)}({h})', health_color(h))}{sick_note}{rads_note}")
    print(f"口粮: {RATIONS[game['ration']][0]}  速度: {PACES[game['pace']][0]}"
          f"  载重: {show_weight(game, load_of(game))} / {show_weight(game, CAR_CAPACITY)}")
    name, km = next_place(game)
    if name in [n for n, _ in OUTPOSTS.values()]:
        note = " (据点, 可以买东西)"
    elif name in RIVERS:
        note = " (要过河)"
    else:
        note = ""
    print(f"下一站: {name}{note}, 还有 {show_distance(game, km - game['distance'])}")
    spot = hotspot_here(game)
    ahead = next_hotspot(game)
    if spot:
        print(colored(f"辐射热点: 正在{spot[2]}, 在外面每天受 {spot[3]} 点辐射, 躲在车里 {spot[4]} 点。"
                      f"还要开 {show_distance(game, spot[1] - game['distance'])}才能离开", "紫"))
    elif ahead and ahead[0] - game["distance"] <= HOTSPOT_WARNING:
        print(colored(f"辐射热点: 再开 {show_distance(game, ahead[0] - game['distance'])}就到{ahead[2]}, "
                      f"那一带辐射偏高", "紫"))
    if game["seeds"]:
        print("车上带着: 种子库的种子")


def progress_bar(value, total, width):
    """进度条: value 占 total 的多少, 画成 width 格, 比如 progress_bar(72, 100, 10) 是 [#######...]"""
    filled = max(0, min(width, round(value * width / total)))
    return "[" + "#" * filled + "." * (width - filled) + "]"


def health_bar(h):
    """把健康画成一条, 比如 72 -> [#######...]。颜色跟着健康好坏变"""
    return colored(progress_bar(h, 100, 10), health_color(h))


def show_party(game):
    """查看队伍: 每个人的详细情况, 还有物资大概能撑多久。不花时间"""
    print("\n========== 队伍状态 ==========")
    for i, (name, h) in enumerate(game["party"].items()):
        if i and i % PARTY_PAGE == 0 and can_animate() and can_clear_screen():   # 有头像的话, 一页放不下所有人
            new_screen()
            print("\n========== 队伍状态 (接上页) ==========")
        tags = []
        if name == game["leader"]:
            tags.append("主角")
        if name in game["jobs"]:
            tags.append(game["jobs"][name])
        tag = f" ({'、'.join(tags)})" if tags else ""
        rads = game["rads"].get(name, 0)
        _, rads_word, rads_health = radiation_level(rads)
        rads_note = f" {rads_word}, 每天掉 {-rads_health} 点健康" if rads_health else ""
        health = f"健康 {h} {health_word(h)}  {health_bar(h)}"
        radiation = f"辐射 {rads}{rads_note}"
        notes = []   # 病和特长
        if name in game["sick"]:
            disease, days = game["sick"][name]
            damage = -DISEASES[disease][0]
            alone = ""
            if len(game["party"]) == 1:
                damage += SOLO_SICK_DAMAGE
                alone = " (没人照顾, 病得更重)"
            notes.append(f"{disease}: {DISEASES[disease][3]}, 每天掉 {damage} 点健康{alone}, "
                         f"大约还要 {days} 天才好 (躲在车里休养好得快一倍, 用药品马上就好)")
        if name in game["jobs"]:
            notes.append(f"特长: {SKILLS[game['jobs'][name]]}")
        if can_animate():   # 在终端和网页版里, 每个人的样子画在左边, 字写在右边 (切成短行, 免得自动换行把画挤歪)
            words = [f"{name}{tag}", health, radiation]
            for note in notes:
                words += wrap_text(note, SCENE_WIDTH - PORTRAIT_WIDTH)
            print()
            print("\n".join(beside(portrait_of(game, name), words, width=PORTRAIT_WIDTH)))
        else:
            print(f"{name}{tag}  {health}  {radiation}")
            for note in notes:
                print("    " + note)
    average = sum(game["party"].values()) // len(game["party"])
    if can_animate():
        print()   # 跟最后一个人的头像隔开
    print(f"队伍整体: {health_word(average)} (平均健康 {average})")
    if game["dead"]:
        print(f"路上失去的人: {'、'.join(game['dead'])}")

    new_screen()   # 人看完了, 换一个画面看物资
    print("\n---------- 物资还能撑多久 ----------")
    s = game["supplies"]
    people = len(game["party"])
    ration_name, per_person, _ = RATIONS[game["ration"]]
    pace_name, km, fuel_per_day, _ = PACES[game["pace"]]
    food_per_day = people * per_person
    print(f"食物: {s['食物']} 份。口粮{ration_name}, 每天吃 {food_per_day} 份 (天冷要多吃), "
          f"还够吃 {s['食物'] // food_per_day} 天")
    cholera = sum(disease == "霍乱" for disease, _ in game["sick"].values())
    water_per_day = people + cholera * CHOLERA_WATER
    print(f"水: {s['水']} 份。每天喝 {water_per_day} 份 (天热、有人得霍乱要多喝), 还够喝 {s['水'] // water_per_day} 天")
    fuel_days = s["燃料"] // fuel_per_day
    print(f"燃料: {s['燃料']} 份。速度{pace_name}, 每天用 {fuel_per_day} 份, "
          f"还够开 {fuel_days} 天, 大约 {show_distance(game, fuel_days * km)}")
    clothes = f"冬衣: {s['冬衣']} 套, 队伍 {people} 人"
    if s["冬衣"] < people:
        clothes += f", 天冷时有 {people - s['冬衣']} 个人没冬衣穿"
    print(clothes)
    print(f"药品 {s['药品']}  排辐剂 {s['排辐剂']}  零件 {s['零件']}  子弹 {s['子弹']}  钱 {game['money']}")
    print(f"离{DESTINATION}还有 {show_distance(game, TOTAL_DISTANCE - game['distance'])}")

    print("\n---------- 车上的重量 ----------")
    people_weight = people * PERSON_WEIGHT
    print(f"人 {show_weight(game, people_weight)}  物资 {show_weight(game, load_of(game) - people_weight)}  "
          f"一共 {show_weight(game, load_of(game))} / {show_weight(game, CAR_CAPACITY)}, "
          f"还能装 {show_weight(game, max(0, CAR_CAPACITY - load_of(game)))}")
    heaviest = max(WEIGHTS, key=lambda item: s[item] * WEIGHTS[item])
    if s[heaviest]:
        print(f"最重的是{heaviest}: {show_weight(game, s[heaviest] * WEIGHTS[heaviest])}")


# ========== 每天发生的事 ==========

def pass_day(game, health_bonus=0, indoors=False, traveling=False):
    """过一天: 吃东西、喝水、更新健康、养病、看看有没有人生病, 再换成明天的天气。
    indoors=True 表示躲在车里, 不受风吹雨打 (但天冷时没穿冬衣还是会冻着, 辐射风暴也挡不住全部),
    生病的人也好得更快。traveling=True 表示今天在赶路。"""
    s = game["supplies"]
    people = len(game["party"])
    _, per_person, ration_health = RATIONS[game["ration"]]
    _, _, extra_water, extra_food, outdoor_health, cold_health, _ = temperature_level(game["temperature"])
    change = ration_health + health_bonus
    if not indoors:
        change += WEATHER[game["weather"]][1] + outdoor_health

    # 食物和水不够的话, 有多少吃多少, 缺得越多健康掉得越多
    hungry = game["ration"] == 1   # 口粮选了"少", 也算挨饿
    food_need = people * (per_person + extra_food)
    if s["食物"] >= food_need:
        s["食物"] -= food_need
    else:
        change -= round(10 * (food_need - s["食物"]) / food_need)
        # 头一天挨饿是新消息 (一直往前开会停下来, 好让玩家想办法); 早就吃光了的话, 再说一遍只是例行消息
        (print if s["食物"] else print_routine)(f"食物不够了, {everyone(game)}在挨饿!")
        s["食物"] = 0
        hungry = True

    cholera = sum(disease == "霍乱" for disease, _ in game["sick"].values())
    water_need = people * (1 + extra_water) + cholera * CHOLERA_WATER
    dirty_water = s["水"] < water_need
    if not dirty_water:
        s["水"] -= water_need
    else:
        change -= round(15 * (water_need - s["水"]) / water_need)
        (print if s["水"] else print_routine)(f"干净的水不够了, {everyone(game)}渴得受不了, 只能喝路边的脏水!")
        s["水"] = 0

    change_all_health(game, change)
    cold_people = freeze(game, cold_health)

    # 辐射: 先算今天受了多少辐射, 再看辐射高的人掉多少血
    _, _, outdoor_rads, indoor_rads, _ = WEATHER[game["weather"]]
    for name in game["party"]:
        irradiate(game, name, indoor_rads if indoors else outdoor_rads)
    spot = hotspot_here(game)
    if spot and game["party"]:   # 在辐射热点里, 不管天气好坏, 每天都要多受辐射
        rads = spot[4] if indoors else spot[3]
        for name in game["party"]:
            irradiate(game, name, rads)
        print_routine(colored(f"{spot[2]}辐射偏高, {everyone(game)}又受了 {rads} 点辐射。", "紫"))
    radiation_damage(game)

    # 生病: 已经病了的人养病, 再看看今天有没有人病倒
    sickness_day(game, indoors)
    if dirty_water:
        for name in list(game["party"]):
            if random.random() < sick_odds(game, DIRTY_WATER_CHANCE):
                get_sick(game, name, random.choice(["霍乱", "痢疾"]))
    catch_diseases(game, hungry, cold_people, traveling)

    game["day"] += 1
    roll_weather(game)


def travel(game):
    """每天的菜单里的「继续前进」: 能换画面的时候, 像原版一样一直往前开; 不能换画面的时候 (比如跑测试), 只开一天"""
    if KEEP_DRIVING and can_clear_screen():
        drive_on(game)
    else:
        drive_one_day(game)


def out_of_fuel(game):
    """燃料够不够按现在的速度开一天"""
    return game["supplies"]["燃料"] < PACES[game["pace"]][2]


def drive_one_day(game, animate=True):
    """开一天车: 路过的地方、路上的事、一天的吃喝, 都在这里。animate=False 是不播这一天的动画 (一直往前开的时候, 动画另外一直在播)"""
    s = game["supplies"]
    _, km, fuel_need, pace_health = PACES[game["pace"]]
    weather = game["weather"]
    speed = WEATHER[weather][0]
    if speed == 0:
        if animate:
            drive_animation(game, moving=False)
        print(f"\n{weather}太大了, 车根本开不动, {everyone(game)}只能躲在车里等了一天。")
        pass_day(game, indoors=True)
        return
    if out_of_fuel(game):
        print("\n燃料不够, 车开不动了! 试试换慢一点的速度, 或者去搜刮废墟找燃料。")
        return
    s["燃料"] -= fuel_need
    if animate:
        drive_animation(game)
    km = round((km + random.randint(-10, 10)) * speed)
    km = min(km, TOTAL_DISTANCE - game["distance"])   # 最后一段路不多算
    game["distance"] += km
    if speed < 1:
        print_routine(f"\n{weather}里车开不快, 只往前开了 {show_distance(game, km)}。")
    else:
        print_routine(f"\n车往前开了 {show_distance(game, km)}。")
    check_places(game)
    if game["distance"] < TOTAL_DISTANCE:   # 已经到了终点 (比如坐木筏漂到了), 就不会再遇到路上的事
        random_event(game, km)
    pass_day(game, pace_health, traveling=True)   # 一天结束: 吃喝、更新健康、换成明天的天气


def drive_on(game):
    """像原版一样一直往前开: 上面的动画一直在动, 车一天一天往前走, 下面的日期、路程这些跟着变。
    路上出了事, 就说一说 (要做决定的让玩家选), 玩家按了回车以后接着开。
    到了地方 (地标、河、据点、辐射热点)、玩家自己按了回车, 或者燃料不够、人都没了、到了终点, 车才停下来, 回到每天的菜单"""
    # 在终端里先换成「按一个键就读一个键」: 开车时按的键不会显示在画面上, 一按就知道
    old_settings = start_reading_keys() if can_read_keys() else None
    screen["driving"] = True   # 开车的时候, 例行消息不用印出来, 下面的状态栏都看得到
    frame = screen["frame"]
    try:
        stop_pressed(0)   # 之前按的键不算
        clear_screen()
        while True:
            gui_update(game)         # 网页版的图形界面: 告诉网页今天的状态
            wide = use_dashboard()   # 窗口够大就用大画面 (每天看一次, 窗口拉大拉小也跟得上)
            stuck = WEATHER[game["weather"]][0] > 0 and out_of_fuel(game)   # 燃料不够, 车开不动了
            if not stuck:
                rows, _, moving = drive_screen(game, frame, wide)
                builtins.print(redraw(rows) + "\x1b[J", flush=True)
                screen["unread"] = False
                # 一天的动画: 一帧一帧地画 (只重画动画那几行), 每画一帧都看看玩家有没有按键, 按了马上停 (这一天还没开完, 不算)
                for _ in range(DRIVE_DAY_FRAMES):
                    frame += 1
                    screen["frame"] = frame
                    if can_animate():
                        rows, _, moving = drive_screen(game, frame, wide)
                        builtins.print("\x1b[?25l" + redraw(rows[:moving]), end="", flush=True)
                    if stop_pressed(ANIMATION_DELAY):
                        return
            # 这一天开完了: 动画 (大画面的话是整个方框) 留着, 擦掉下面的字, 路上发生的事写在下面 (像原版那样车还在画面上)
            rows, keep, _ = drive_screen(game, frame, wide)
            if keep:
                builtins.print("\x1b[?25h" + redraw(rows[:keep]) + "\n\x1b[J", end="")
            else:
                clear_screen()
            screen["room"] = screen_size()[1] - keep >= 12   # 下面放得下一件事 (大概 10 行) 才写在下面, 不然换新画面
            weather = game["weather"]
            places = len(game["visited"])
            drive_one_day(game, animate=False)
            if stuck or not game["party"] or game["distance"] >= TOTAL_DISTANCE:
                return
            if len(game["visited"]) > places:   # 今天到了新的地方: 像原版那样停下来, 回到每天的菜单
                return
            now = game["weather"]   # 明天的天气
            if now != weather and now in WARN_WEATHER:
                print(f"\n天气变了: {colored(now, weather_color(now))}。{WEATHER[now][-1]}。")
            if screen["unread"]:   # 路上出了事: 等玩家看完、按了回车, 再接着开
                new_screen()
    finally:
        screen["driving"] = False
        builtins.print("\x1b[?25h", end="", flush=True)
        stop_reading_keys(old_settings)


def redraw(rows):
    """回到屏幕左上角, 一行一行盖掉原来的字。每行后面加一个 \x1b[K (擦掉这一行后面剩下的旧字):
    新的一行比原来的短 (比如中文字多了, 字的个数就少了), 不擦的话后面会留着旧字"""
    return "\x1b[H" + "\x1b[K\n".join(rows) + "\x1b[K"


def drive_frame(game, frame):
    """一直往前开的时候, 动画的第 frame 帧: 天气跟着变, 暴风雪里、没燃料时车停着"""
    moving = WEATHER[game["weather"]][0] > 0 and not out_of_fuel(game)
    return road_scene(frame, game["pace"] if moving else 0, game["weather"], len(game["party"]))


def drive_screen(game, frame, wide):
    """一直往前开的画面 (像原版那样), 返回 (一行一行的字, 留着的前几行, 动画占了前几行):
    大画面是一个分成几块的方框, 下面一句怎么停车; 普通的画面是动画、怎么停车、状态栏"""
    how = "点一下屏幕或者按回车" if IN_BROWSER else "按回车"
    hint = colored(f"   ({how}停下来, 看看情况)", "灰")
    if wide:
        box = dashboard_lines(game, drive_frame(game, frame), car_word(game, moving=True))
        return box + ["", hint], len(box), 1 + SCENE_HEIGHT   # 动画在方框里, 上面还有一行边
    rows = drive_frame(game, frame) if can_animate() else []
    if GUI:   # 网页版的图形界面: 状态在网页的面板里, 停车有按钮, 这里只画动画
        return rows, len(rows), len(rows)
    return rows + ["", hint, ""] + drive_status(game), len(rows), len(rows)


def drive_status(game):
    """一直往前开的时候, 动画下面的状态栏 (像原版那样), 返回一行一行的字:
    日期、天气、每个人怎么样、吃的喝的还够几天、下一站、走了多远, 还有要注意的事"""
    s = game["supplies"]
    weather = game["weather"]
    people = len(game["party"])
    lines = [f"日期: {date_text(game)} (第 {game['day']} 天)   天气: {colored(weather, weather_color(weather))}  "
             f"{show_temperature(game, game['temperature'])}"]

    # 每个人: 名字 健康 (病) (辐射), 一行放不下就分两行
    members = []
    for name, h in game["party"].items():
        words = [(name, None), (health_word(h), health_color(h))]
        if name in game["sick"]:
            words.append((game["sick"][name][0], "红"))
        rads = game["rads"].get(name, 0)
        if radiation_level(rads)[2]:   # 辐射到了会掉血的程度才写
            words.append((f"辐射{rads}", "紫"))
        members.append(words)
    row, used = [], 0
    for words in members:
        width = text_width(" ".join(word for word, _ in words)) + 2
        if row and used + width > SCENE_WIDTH - 6:
            lines.append(("队员: " if len(lines) == 1 else "      ") + "  ".join(row))
            row, used = [], 0
        row.append(" ".join(colored(word, color) for word, color in words))
        used += width
    lines.append(("队员: " if len(lines) == 1 else "      ") + "  ".join(row))

    # 食物、水、燃料还够几天 (天冷天热、有人得霍乱要吃喝得多一些, 这里按平常算), 只剩 3 天以内是红的
    cholera = sum(disease == "霍乱" for disease, _ in game["sick"].values())
    per_day = {"食物": people * RATIONS[game["ration"]][1], "水": people + cholera * CHOLERA_WATER,
               "燃料": PACES[game["pace"]][2]}
    supplies = []
    for item, need in per_day.items():
        days = s[item] // need
        supplies.append(f"{item} {s[item]} " + colored(f"够 {days} 天", "红" if days <= 3 else None))
    lines.append("  ".join(supplies))

    name, km = next_place(game)
    lines.append(f"下一站: {name}, 还有 {show_distance(game, km - game['distance'])}")
    percent = game["distance"] * 100 // TOTAL_DISTANCE
    lines.append(f"已走 {show_distance(game, game['distance'])}, 还剩 "
                 f"{show_distance(game, TOTAL_DISTANCE - game['distance'])}  "
                 f"{colored(progress_bar(game['distance'], TOTAL_DISTANCE, 10), '青')} {percent}%")

    # 天天都有、开车的时候不会专门说的事: 放在最后一行提醒
    notes = []
    if hotspot_here(game):
        notes.append(colored("辐射偏高", "紫"))
    if s["食物"] == 0:
        notes.append(colored("没吃的了", "红"))
    if s["水"] == 0:
        notes.append(colored("没水了", "红"))
    if temperature_level(game["temperature"])[5] and s["冬衣"] < people:
        notes.append(colored("有人没冬衣在受冻", "红"))
    if notes:
        lines.append("注意: " + "  ".join(notes))
    return lines


# ---------- 大画面 (像原版 CD 版那样, 一个画面分成几块) ----------
# +-- 废土之旅 ----------------------------+-- 状态 ------------+
# | 动画 (11 行)                           | 日期、天气、下一站、 |
# +-- 路线图 -------------------------------+ 物资、队伍……       |
# | 路线图 (3 行)                          |                    |
# +-- 最近的事 -----------------------------+                    |
# | 旅行日记最后几条 (5 行)                 |                    |
# +----------------------------------------+--------------------+
# 方框只用英文字符画 (中文的「─」这类线在有的终端里占两格, 会对不齐)

# 大小见 SCENE_WIDTH 下面的 DASH_LEFT 这几个


def screen_size():
    """屏幕 (终端窗口) 放得下几列、几行字。网页版里 run_in_browser.py 会换成问网页"""
    size = shutil.get_terminal_size((80, 24))
    return size.columns, size.lines


def use_dashboard():
    """用不用大画面: 设置里没关掉、能换画面, 而且窗口够大 (网页版的图形界面自己有面板, 不用)"""
    if GUI or not (DASHBOARD and can_clear_screen()):
        return False
    columns, rows = screen_size()
    return columns > DASHBOARD_WIDTH and rows >= DASHBOARD_ROWS


def visible_width(text):
    """一段字在屏幕上占几格 (颜色的控制字符不占地方)"""
    return text_width(re.sub(r"\x1b\[[\d;]*m", "", text))


def fit(text, width):
    """把一段字补上空格, 正好占 width 格; 太长就切掉 (切的时候颜色就不要了)"""
    size = visible_width(text)
    if size > width:
        text = wrap_text(re.sub(r"\x1b\[[\d;]*m", "", text), width)[0]
        size = text_width(text)
    return text + " " * (width - size)


def dashboard_border(left_title=None, right_title=None, right=None):
    """方框的一条横线, 线上可以写标题。right 不是 None 的话, 横线只画左边一栏, 右边一栏这一行写 right"""
    def line(title, width):
        words = f"-- {colored(title, '黄', bold=True)} " if title else ""
        return words + "-" * (width - visible_width(words))
    if right is None:
        return "+" + line(left_title, DASH_LEFT) + "+" + line(right_title, DASH_RIGHT) + "+"
    return "+" + line(left_title, DASH_LEFT) + "+" + fit(right, DASH_RIGHT) + "|"


def dashboard_lines(game, scene, car):
    """大画面, 一行一行的字。scene 是动画的一帧, car 是车现在怎么样 (在开、停着……)"""
    panel = status_panel(game, car)
    left = list(scene) + [None] + route_map(game) + [None] + recent_events(game)   # None 是左边一栏里的横线
    titles = iter(["路线图", "最近的事"])
    rows = [dashboard_border("废土之旅", "状态")]
    for words, right in zip(left, panel):
        if words is None:
            rows.append(dashboard_border(next(titles), right=right))
        else:
            rows.append("|" + fit(words, DASH_LEFT) + "|" + fit(right, DASH_RIGHT) + "|")
    rows.append(dashboard_border())
    return rows


def gui_update(game):
    """网页版的图形界面用: 告诉网页现在的状态 (日期、物资、队伍……), 让网页画面板。
    在电脑上什么都不做; 网页版里 run_in_browser.py 会换掉它"""


def show_scene(game):
    """网页版图形界面的每天的菜单上面: 只画车停着的样子 (状态都在网页的面板里)"""
    scene = road_scene(screen["frame"], game["pace"], game["weather"], len(game["party"]), dust=False)
    print("\n" + "\n".join(scene))


def show_dashboard(game):
    """每天的菜单上面的大画面: 车停着, 动画停在开车停下来的那一帧"""
    scene = road_scene(screen["frame"], game["pace"], game["weather"], len(game["party"]), dust=False)
    print("\n".join(dashboard_lines(game, scene, car_word(game, moving=False))))


def car_word(game, moving):
    """状态栏最后一行: 车现在怎么样"""
    if WEATHER[game["weather"]][0] == 0:
        return colored(f"开不动 ({game['weather']})", "红")
    if out_of_fuel(game):
        return colored("没燃料了", "红")
    return colored("在开", "绿") if moving else "停着"


def status_panel(game, car):
    """大画面右边一栏的状态 (正好 DASH_ROWS 行): 日期天气、下一站、物资还够几天、队伍、要注意的事"""
    s = game["supplies"]
    weather = game["weather"]
    temperature = game["temperature"]
    people = len(game["party"])
    left = TOTAL_DISTANCE - game["distance"]
    name, km = next_place(game)
    kind = " (据点)" if name in [n for n, _ in OUTPOSTS.values()] else " (要过河)" if name in RIVERS else ""
    rows = [
        " " + colored(f"{date_text(game)} (第 {game['day']} 天)", "青", bold=True),
        f" 天气: {colored(weather, weather_color(weather))}  {show_temperature(game, temperature)} "
        f"{colored(temperature_level(temperature)[1], temperature_color(temperature))}",
        "",
        f" 下一站: {name}{kind}",
        f"   还有 {show_distance(game, km - game['distance'])}",
        f" 已走 {show_distance(game, game['distance'])}, 还剩 {show_distance(game, left)}",
        "",
    ]
    cholera = sum(disease == "霍乱" for disease, _ in game["sick"].values())
    per_day = {"食物": people * RATIONS[game["ration"]][1], "水": people + cholera * CHOLERA_WATER,
               "燃料": PACES[game["pace"]][2]}
    for item, need in per_day.items():
        days = s[item] // need
        rows.append(f" {item} {s[item]} {MEASURES[item]}  " + colored(f"够 {days} 天", "红" if days <= 3 else None))
    rows += [
        f" 子弹 {s['子弹']}  药品 {s['药品']}  排辐剂 {s['排辐剂']}",
        f" 零件 {s['零件']}  冬衣 {s['冬衣']}  钱 {game['money']}",
        f" 载重 {show_weight(game, load_of(game))} / {show_weight(game, CAR_CAPACITY)}",
        "",
        f" 口粮: {RATIONS[game['ration']][0]}   速度: {PACES[game['pace']][0]}",
    ]
    for member, h in game["party"].items():   # 最多 4 个人
        words = f" {member} {colored(f'{health_word(h)} {h}', health_color(h))}"
        if member in game["sick"]:
            words += " " + colored(game["sick"][member][0], "红")
        rads = game["rads"].get(member, 0)
        if radiation_level(rads)[2]:
            words += " " + colored(f"辐射{rads}", "紫")
        rows.append(words)
    rows += [""] * (DASH_ROWS - 2 - len(rows))

    notes = []   # 天天都有的事, 开车的时候不会专门说
    spot, ahead = hotspot_here(game), next_hotspot(game)
    if spot:
        notes.append(colored("辐射偏高", "紫"))
    elif ahead and ahead[0] - game["distance"] <= HOTSPOT_WARNING:
        notes.append(colored(f"{show_distance(game, ahead[0] - game['distance'])}后辐射偏高", "紫"))
    if s["食物"] == 0:
        notes.append(colored("没吃的", "红"))
    if s["水"] == 0:
        notes.append(colored("没水", "红"))
    if temperature_level(temperature)[5] and s["冬衣"] < people:
        notes.append(colored("有人受冻", "红"))
    if game["seeds"]:
        notes.append(colored("带着种子", "绿"))
    rows.append((" 注意: " + "  ".join(notes)) if notes else "")
    rows.append(f" 车: {car}")
    return rows


def route_map(game):
    """路线图 (3 行): 一条路, 走过的是 =, 没走的是 -, 上面标着据点 (F)、河 (~)、地标 (^)、辐射热点 (*), 车 (>) 在走到的地方"""
    width = DASH_LEFT - 2
    track = [("=", "青") if (i + 1) * TOTAL_DISTANCE / width <= game["distance"] else ("-", "灰")
             for i in range(width)]

    def column(km):
        return min(width - 1, int(km * width / TOTAL_DISTANCE))

    for km, (place, _) in LANDMARKS.items():   # 后标的盖住先标的: 地标 < 辐射热点 < 河 < 据点 < 车
        if place not in RIVERS:
            track[column(km)] = ("^", None)
    for start, end, *_ in HOTSPOTS:
        for i in range(column(start), column(end) + 1):
            track[i] = ("*", "紫")
    for km, (place, _) in LANDMARKS.items():
        if place in RIVERS:
            track[column(km)] = ("~", "蓝")
    for km in OUTPOSTS:
        track[column(km)] = ("F", "黄")
    track[column(game["distance"])] = (">", "绿")
    line = ""
    for symbol, color in track:
        line += colored(symbol, color, bold=symbol == ">")
    percent = f"已走 {game['distance'] * 100 // TOTAL_DISTANCE}%"
    gap = width - text_width("独立城" + DESTINATION + percent)
    middle = " " * (gap // 2) + percent + " " * (gap - gap // 2)
    legend = (f"{colored('>', '绿', bold=True)} 你在这里  {colored('F', '黄')} 据点  {colored('~', '蓝')} 河  "
              f"^ 地标  {colored('*', '紫')} 辐射热点")
    return [" " + line, " 独立城" + middle + DESTINATION, " " + legend]


def recent_events(game):
    """旅行日记的最后几条, 正好 DASH_EVENT_ROWS 行。太长的一条分成几行; 放不下的旧的就不放 (不会只放半条)"""
    rows = []
    for line in reversed(game["diary"]):   # 从最新的一条往回放
        found = re.match(r"(\S+) \(第 \d+ 天\), 已走 [^:]+: (.*)", line)
        words = f"{found[1]} {found[2]}" if found else line
        parts = wrap_text(words, DASH_LEFT - 2)
        lines = [" " + parts[0]] + ["   " + part for part in wrap_text("".join(parts[1:]), DASH_LEFT - 4) if part]
        if len(rows) + len(lines) > DASH_EVENT_ROWS:
            if not rows:   # 最新的一条自己就放不下, 只放前面几行
                rows = lines[:DASH_EVENT_ROWS]
            break
        rows = lines + rows
    return rows + [""] * (DASH_EVENT_ROWS - len(rows))


def rest(game):
    print(f"\n{everyone(game)}躲在车里休息了一天。")
    pass_day(game, 8, indoors=True)


def scavenge(game):
    print(f"\n{you(game)}花了一天搜刮附近的废墟……")
    pass_day(game)
    if not game["party"]:
        return
    roll = random.random()
    scavenger = skilled(game, "拾荒者")
    if roll < 0.2:
        mutant_attack(game)
    elif scavenger:
        print(f"拾荒者{scavenger}知道该往哪儿翻。")
        for _ in range(2):
            find_supplies(game)
    elif roll < 0.4:
        print("什么有用的都没找到。")
    else:
        find_supplies(game)
    if game["party"] and random.random() < sick_odds(game, TETANUS_CHANCE):
        victim = random_member(game)
        print(f"{victim} 在废墟里被生锈的铁皮划了一道口子……")
        get_sick(game, victim, "破伤风")


def hunt(game):
    """打猎小游戏: 看到词以后越快打出来, 打到的肉越多"""
    s = game["supplies"]
    if s["子弹"] < 5:
        print("\n打猎至少要 5 发子弹。")
        return
    s["子弹"] -= 5
    animal = random.choice(list(ANIMALS))
    word = random.choice(HUNT_WORDS)
    print(f"\n{you(game)}拿着枪出去打猎, 远处有一只{animal}……")
    print("按下回车后, 屏幕上会出现一个英文词。看到后马上把它打出来, 再按一次回车, 越快越好!")
    print("(记得先切换成英文输入法)")
    wait_enter("准备好了就按回车……")
    print(f"\n    >>> {colored(word, '黄', bold=True)} <<<\n")
    start = time.time()
    typed = input("快打: ").strip().lower()
    seconds = time.time() - start

    low, high = ANIMALS[animal]
    food = random.randint(low, high)
    hunter = skilled(game, "猎人")
    if hunter:
        food = food * 3 // 2   # 猎人收拾猎物更干净, 肉多一半
    if typed != word:
        print("手一抖打歪了, 猎物跑掉了。")
    elif seconds <= 6:
        if seconds <= 3:
            print(f"砰! 只用了 {seconds:.1f} 秒, 一枪命中! 打到了 {food} 份肉。")
            how = "打到"
        else:
            food //= 2
            print(f"用了 {seconds:.1f} 秒, 只打伤了它, 追了半天才拿回 {food} 份肉。")
            how = "打伤了"
        if hunter:
            print(f"(猎人{hunter}帮忙收拾猎物, 肉多了一半。)")
        brought = carry_meat(game, food)
        write_diary(game, f"打猎{how}一只{animal}, 带回 {brought} 份食物。")
    else:
        print(f"用了 {seconds:.1f} 秒, 太慢了, 猎物早就跑了。")
    pass_day(game)


def carry_meat(game, food):
    """打到的肉要扛回车上: 每个人只扛得动 CARRY_PER_PERSON 那么多, 车上也要装得下。返回真正带回来的份数"""
    most = len(game["party"]) * CARRY_PER_PERSON // WEIGHTS["食物"]
    if food > most:
        print(f"肉太多了, {you(game)}只扛得动 {most} 份, 剩下的只能留在原地。")
        food = most
    return add_supplies(game, "食物", food)


def take_medicine(game):
    """每天的菜单里的「用药」: 先选用药品还是排辐剂, 再选给谁用"""
    s = game["supplies"]
    print(f"\n1. 药品 (现在有 {s['药品']}): 治好病或伤, 再恢复一些健康")
    print(f"2. 排辐剂 (现在有 {s['排辐剂']}): 排掉 {ANTI_RAD} 点辐射")
    print("0. 不用了")
    choice = ask_number("用哪种药? ", 0, 2)
    if choice == 0:
        return
    item = "药品" if choice == 1 else "排辐剂"
    if s[item] == 0:
        print(f"\n你没有{item}了。")
        return
    name = choose_member(game, f"给谁用{item}? ")
    if name is None:
        return
    if choice == 1:
        use_medicine(game, name)
    else:
        use_anti_rad(game, name)


def choose_member(game, prompt):
    """让玩家从队伍里选一个人, 会列出每个人的健康、病和辐射。只有一个人时不用选。选 0 就返回 None"""
    names = list(game["party"])
    if len(names) == 1:
        return names[0]
    print()
    for i, name in enumerate(names, 1):
        sick = game["sick"].get(name)
        sick_note = f"  {sick[0]}" if sick else ""
        print(f"{i}. {name}  健康 {game['party'][name]}{sick_note}  辐射 {game['rads'].get(name, 0)}")
    print("0. 不用了")
    choice = ask_number(prompt, 0, len(names))
    return names[choice - 1] if choice else None


def use_anti_rad(game, name):
    """给一个人打一针排辐剂"""
    if game["rads"].get(name, 0) == 0:
        print(f"\n{name} 身上没有辐射, 不需要用排辐剂。")
        return
    game["supplies"]["排辐剂"] -= 1
    irradiate(game, name, -ANTI_RAD)
    print(f"\n{name} 打了一针排辐剂, 辐射降到了 {game['rads'][name]}。")


def use_medicine(game, name):
    """给一个人用药品: 治好他的病或伤, 再恢复一些健康 (有医生在恢复得更多)"""
    sick = game["sick"].get(name)
    if not sick and game["party"][name] >= 100:
        print(f"\n{name} 没病没伤, 不需要用药。")
        return
    game["supplies"]["药品"] -= 1
    doctor = skilled(game, "医生")
    heal = 60 if doctor else 35
    game["party"][name] = min(100, game["party"][name] + heal)
    if doctor == name:
        giver = f"医生{name}给自己"
    elif doctor:
        giver = f"医生{doctor}给 {name} "
    elif name == game["leader"]:
        giver = "你给自己"
    else:
        giver = f"你给 {name} "
    if sick:
        del game["sick"][name]
        print(f"\n{giver}用了药, {name}的{sick[0]}治好了。")
    else:
        print(f"\n{giver}用了药, {name} 感觉好多了。")


def change_ration(game):
    print(f"\n口粮 (现在是{RATIONS[game['ration']][0]}):")
    for number, (name, per_person, health) in RATIONS.items():
        if health < 0:
            note = f", {everyone(game)}会挨饿, 每天掉 {-health} 点健康, 也更容易生病"
        else:
            note = f", 每天恢复 {health} 点健康"
        print(f"{number}. {name}: 每人每天吃 {per_person} 份食物{note}")
    game["ration"] = ask_number("选哪个? ", 1, 3)


def change_pace(game):
    print(f"\n速度 (现在是{PACES[game['pace']][0]}):")
    for number, (name, km, fuel, health) in PACES.items():
        if health > 0:
            note = f", {everyone(game)}比较轻松"
        elif health < 0:
            note = f", 路上颠簸, {everyone(game)}会掉血"
        else:
            note = ""
        print(f"{number}. {name}: 每天大约开 {show_distance(game, km)}, 用 {fuel} 份燃料{note}")
    game["pace"] = ask_number("选哪个? ", 1, 3)


def next_place(game):
    """下一个要到的地方: 返回 (名字, 离起点几公里)"""
    places = [(km, name) for km, (name, _) in LANDMARKS.items()]
    places += [(km, name) for km, (name, _) in OUTPOSTS.items()]
    places.append((TOTAL_DISTANCE, DESTINATION))
    for km, name in sorted(places):
        if km > game["distance"]:
            return name, km
    return DESTINATION, TOTAL_DISTANCE


def reached(game, km, name):
    """是不是第一次走到这个地方"""
    if game["party"] and game["distance"] >= km and name not in game["visited"]:
        game["visited"].append(name)
        return True
    return False


def check_places(game):
    """路过风景地标会介绍一下, 到了据点还可以进去买东西, 开进辐射热点会提醒。
    一天可能连着经过好几个地方, 所以把它们放在一起, 按路程从近到远排好再一个个看"""
    places = [(km, name, intro, "地标") for km, (name, intro) in LANDMARKS.items()]
    places += [(km, name, intro, "据点") for km, (name, intro) in OUTPOSTS.items()]
    places += [(start, name, intro, "热点") for start, _, name, _, _, intro in HOTSPOTS]
    for km, name, intro, kind in sorted(places):
        if not reached(game, km, name):
            continue
        new_screen()           # 每到一个地方都换一个画面
        if name in PICTURES:   # 先看一眼那里的样子
            show_picture(*PICTURES[name])
        if kind == "热点":
            play_music("热点")
            show_picture(HOTSPOT_SIGN, "紫")
            print(f"\n{you(game)}开进了{title(name, '紫')}{intro}{colored('盖革计数器响个不停, 这一带辐射偏高。', '紫')}")
            write_diary(game, f"开进了{name}, 这一带辐射偏高。", km)
            continue
        if name in RIVERS:
            print(f"\n{you(game)}来到了{title(name, '青')}{intro}")
            day_end = game["distance"]
            game["distance"] = km        # 等水退、过河的时候, 车停在河边 (日记、天气都按河边算)
            cross_river(game, name)
            game["distance"] = day_end   # 过了河, 接着开完今天的路
            continue
        if kind == "地标":
            print(f"\n{you(game)}经过了{title(name, '青')}{intro}")
            write_diary(game, f"经过了{name}。", km)
            continue
        play_music("据点")
        print(f"\n{you(game)}到了{title(name, '青')}{intro}")
        write_diary(game, f"到了{name}。", km)
        offer_recruit(game, name, km)
        if ask_number("这里有幸存者在做买卖, 要进去买卖东西吗? 1. 要  2. 不要  ", 1, 2) == 1:
            shop(game, can_sell=True)
        if name == LAST_ROAD_FROM:
            choose_last_road(game, km)


def offer_recruit(game, place, km=None):
    """据点里有个人愿意免费跟你走, 车上坐满了、或者太重了就带不了"""
    if place not in RECRUITS:
        return
    name, job = RECRUITS[place]
    while name in game["party"] or name in game["dead"]:   # 跟主角或别人重名就加个 2
        name += "2"
    new_screen()   # 看完据点的介绍, 换个画面见见这里的人
    if len(game["party"]) >= MAX_PARTY:
        print(f"这里有个叫 {name} 的{job}也想往西走, 可惜你们的车已经坐满了。")
        return
    if not has_seat_for_one_more(game):
        print(f"这里有个叫 {name} 的{job}也想往西走, 可惜车上东西太重, 再坐一个人就超载了。")
        return
    brings = "和".join(f" {amount} 份{item}" for item, amount in RECRUIT_BRINGS.items())
    show_picture(PORTRAITS[job], words=["", "", f"{name} ({job})"])
    print(f"这里有个叫 {name} 的{job}也想往西走, 愿意跟{you(game)}一起, 还会带上自己的{brings}。")
    print(f"特长: {SKILLS[job]}。不过多一个人, 每天也要多吃多喝, 天冷时还要多一套冬衣。")
    if ask_number(f"1. 让{name}加入  2. 不用了  ", 1, 2) == 1:
        game["party"][name] = 100
        game["jobs"][name] = job
        print(f"{name} 带着自己的{brings}加入了队伍!")
        for item, amount in RECRUIT_BRINGS.items():
            add_supplies(game, item, amount)
        write_diary(game, f"{job}{name}在{place}加入了队伍。", km)
    else:
        print(f"{name} 点点头, 留在了{place}。")


# ========== 过河 ==========

def river_depth(game, place):
    """今天这条河有多深 (米, 只留一位小数): 平常的水深, 按月份涨落, 这几天下了雨雪还会涨, 每天再有一点随机变化"""
    month = date_of(game)[0]
    depth = RIVERS[place][2] * RIVER_SEASON[month - 1] * (1 + RAIN_RISE * game["rain"])
    return round(depth * random.uniform(0.85, 1.15), 1)


def wade_depth(game):
    """车能直接开过多深的水 (米)。有机械师的话, 他会给车接上通气管, 能开过更深的水"""
    extra = SNORKEL_DEPTH if skilled(game, "机械师") else 0
    return round(CAR_WADE_DEPTH + extra, 1)   # 只留一位小数, 不然 0.6 + 0.3 会算成 0.8999…


def cross_river(game, place):
    """到了河边: 直接开过去、绑上空油桶浮过去、等水退, 有渡船的地方还能花钱坐渡船。
    不过河就没法往前走, 所以一直问到过了河 (或者人都没了) 为止"""
    river, width, _, fare = RIVERS[place]
    depth = river_depth(game, place)
    mechanic = skilled(game, "机械师")
    if mechanic:
        print(f"机械师{mechanic}给车接上了一根通气管, 车能开过更深的水。")
    while game["party"]:
        print(f"\n{river}河面宽 {show_length(game, width)}, 今天水深 {show_length(game, depth)}。")
        print(f"1. 直接开过去 (车能开过 {show_length(game, wade_depth(game))}深的水, "
              f"再深发动机会进水, 太深车会被冲翻)")
        print("2. 绑上空油桶, 把车浮过去 (水再深也能过, 可是有可能翻车)")
        print("3. 在河边等一天, 看水会不会退")
        if fare:
            print(f"4. 坐渡船 (要 {fare} 块钱, 你有 {game['money']} 块。最安全, 可能要排队)")
        choice = ask_number("怎么过河? ", 1, 4 if fare else 3)
        new_screen()
        if choice == 1:
            ford_river(game, place, depth)
        elif choice == 2:
            float_river(game, place, depth)
        elif choice == 3:
            print(f"\n{everyone(game)}在{river}边等了一天。")
            pass_day(game, indoors=True)
            new_depth = river_depth(game, place)
            if new_depth < depth:
                print("河水退了一些。")
            elif new_depth > depth:
                print("河水又涨了。")
            else:
                print("河水跟昨天差不多。")
            depth = new_depth
            continue
        elif game["money"] < fare:
            print("\n你的钱不够, 坐不了渡船。")
            continue
        else:
            take_ferry(game, place)
        return


def ford_river(game, place, depth):
    """直接把车开过河: 水浅没事; 稍微深一点, 发动机进水, 要花一天晾干; 太深, 车会被冲翻"""
    river = RIVERS[place][0]
    limit = wade_depth(game)
    if depth <= limit:
        river_animation(game, "开", "过去了")
        print(f"\n车稳稳地蹚过了{river}。")
        write_diary(game, f"直接开车过了{river}。")
    elif depth <= round(limit + SOAK_DEPTH, 1):
        s = game["supplies"]
        spoiled = s["食物"] // SOAK_FOOD
        s["食物"] -= spoiled
        river_animation(game, "开", "进水")
        print("\n车开到河中间, 河水漫过了车门, 发动机进水熄火了!")
        print(f"{everyone(game)}好不容易把车推上了对岸, 泡了脏河水的 {spoiled} 份食物不能吃了。")
        print("又花了一天, 才把发动机晾干。")
        write_diary(game, f"开车过{river}时发动机进了水, 扔掉了 {spoiled} 份食物, 晾了一天车。")
        pass_day(game)
    else:
        river_animation(game, "开", "翻车")
        capsize(game, place, f"开车过{river}")


def float_river(game, place, depth):
    """绑上空油桶, 让车像船一样漂过去。水越深, 水流越急, 越容易翻车"""
    river = RIVERS[place][0]
    print(f"\n{you(game)}把空油桶绑在车身四周, 车像船一样, 慢慢漂向对岸……")
    if random.random() < FLOAT_RISK * (1 + max(0, depth - 1)):
        river_animation(game, "浮", "翻车")
        capsize(game, place, f"把车浮过{river}")
    else:
        river_animation(game, "浮", "过去了")
        print("车平平安安地漂到了对岸。")
        write_diary(game, f"绑上空油桶, 把车浮过了{river}。")


def take_ferry(game, place):
    """花钱坐渡船: 最安全, 可是渡口常常排着队"""
    river, _, _, fare = RIVERS[place]
    game["money"] -= fare
    wait = random.randint(0, FERRY_WAIT)
    if wait:
        print(f"\n渡口排着好几辆车, {you(game)}等了 {wait} 天才轮到。")
        for _ in range(wait):
            pass_day(game, indoors=True)
            if not game["party"]:
                return
    river_animation(game, "渡船", "过去了")
    print(f"\n{you(game)}交了 {fare} 块钱。摆渡的是一伙背着枪的幸存者, 他们拉着一根横过河面的钢缆, "
          f"用废油桶和铁板扎成的大筏子把车送到了对岸。")
    write_diary(game, f"花 {fare} 块钱坐渡船过了{river}。")


def capsize(game, place, how):
    """车在河里翻了: 物资被冲走一些, 掉进河里的人都受了辐射, 还可能有人被急流冲走。how 是怎么过河时翻的, 写进日记"""
    river = RIVERS[place][0]
    s = game["supplies"]
    print(f"\n{title('翻车', '红')}车在{river}中间被急流冲翻了!")
    lost = []
    for item in s:
        if s[item] and random.random() < 0.5:   # 每样东西有一半的机会被冲走一些
            amount = max(1, s[item] * random.randint(20, 50) // 100)
            s[item] -= amount
            lost.append(f"{amount} {MEASURES[item]}{item}")
    if lost:
        print(f"被河水冲走了: {'、'.join(lost)}。")
    if len(game["party"]) == 1:
        print("你掉进了河里, 灌了好几口带辐射的河水。")
    else:
        print("车上的人全掉进了河里, 灌了好几口带辐射的河水。")
    for name in game["party"]:
        irradiate(game, name, RIVER_RADS)
    write_diary(game, f"{how}时翻了车, 丢了不少东西。")
    if random.random() < DROWN_CHANCE:
        victim = random_member(game)
        lose_member(game, victim, f"被{river}的急流冲走了, 再也没有上来。", f"被{river}的急流冲走了。")
    if game["party"]:
        print(f"{everyone(game)}好不容易把车拖上了对岸。")


# ========== 最后一段路: 漂流还是走巴洛路 ==========

def choose_last_road(game, km):
    """到了达尔斯, 选最后一段路怎么走。km 是达尔斯离起点几公里"""
    left = show_distance(game, TOTAL_DISTANCE - km)
    new_screen()
    print(f"\n从{LAST_ROAD_FROM}到{DESTINATION}还剩最后 {left}。当年的拓荒者在这里有两种走法:")
    print("1. 扎木筏顺着哥伦比亚河漂下去: 不要钱、不用燃料, 两天就到;")
    print("   可是河上有急流, 撞上礁石会丢东西, 还可能有人掉进河里")
    print(f"2. 走巴洛路, 开车绕过胡德山: 要交 {BARLOW_TOLL} 块过路费 (你有 {game['money']} 块), 山路要用燃料, 山里还可能下雪")
    choice = ask_number("走哪条路? ", 1, 2)
    if choice == 2 and game["money"] < BARLOW_TOLL:
        print("\n你的钱不够交过路费, 只能扎木筏漂下去了。")
        choice = 1
    if choice == 2:
        game["money"] -= BARLOW_TOLL
        print(f"\n{you(game)}交了 {BARLOW_TOLL} 块过路费, 沿着巴洛路往胡德山开去。")
        write_diary(game, f"在{LAST_ROAD_FROM}交了 {BARLOW_TOLL} 块过路费, 走巴洛路绕过胡德山。", km)
    else:
        raft_trip(game, km)


def raft_trip(game, km):
    """坐木筏顺着哥伦比亚河漂到终点: 扎木筏花一天, 再漂两天, 一路上要躲开急流里的礁石。
    漂流的时候车停在木筏上, 路程先按达尔斯算 (天气也按达尔斯一带的河谷算), 漂到了再算走完全程"""
    game["distance"] = km
    print(f"\n{you(game)}在{LAST_ROAD_FROM}找来废油桶和木板, 花了一天扎成一个大木筏, 把车也开了上去。")
    write_diary(game, f"在{LAST_ROAD_FROM}扎了一个木筏, 顺着哥伦比亚河漂下去。")
    pass_day(game)
    raft_animation(game)
    print("\n木筏顺着哥伦比亚河往下漂。前面会有急流: 看清楚哪边是水道, 就飞快地按那个数字!")
    for number in range(1, RAPIDS + 1):
        if not game["party"]:
            return
        if number == RAPIDS // 2 + 1:   # 漂了一半, 天黑了, 靠岸过一夜
            new_screen()
            print(f"\n天黑了, {you(game)}把木筏拴在岸边过夜。")
            pass_day(game)
            if not game["party"]:
                return
            raft_animation(game)   # 第二天一早接着往下漂
        shoot_rapid(game, number)
    if not game["party"]:
        return
    game["distance"] = TOTAL_DISTANCE
    print(f"\n木筏漂出了峡谷, 河面越来越宽。{you(game)}从威拉米特河口上了岸, 把车开到了{DESTINATION}!")
    write_diary(game, f"坐木筏顺着哥伦比亚河漂到了{DESTINATION}。")


# 急流的画面: 每一条水道 8 格宽, 有礁石和没礁石各画两行 (画里只用英文字符, 中文字在终端里占两格, 会对不齐)
ROCK_ART = ["  /\\/\\  ", " /_/\\_\\ "]
WATER_ART = ["  ~  ~  ", "   ~  ~ "]
LANES = ["左边", "中间", "右边"]


def shoot_rapid(game, number):
    """过一段急流: 三条水道里有礁石, 要在几秒内选一条没礁石的"""
    rocks = [True, True, True]
    for lane in random.sample(range(3), random.randint(1, 2)):   # 一两条水道能过
        rocks[lane] = False
    new_screen()   # 先让玩家看完上一段 (按了回车, 急流才出现, 才开始算时间)
    print(f"\n{title('急流')}第 {number} 段急流!")
    print("      1        2        3")   # 数字正好在三条水道的正中间
    for row in range(2):
        print("  |" + "|".join(colored(ROCK_ART[row], "红") if rock else colored(WATER_ART[row], "蓝")
                               for rock in rocks) + "|")
    print("  " + "  ".join(LANES[i] + (colored("礁石", "红") if rock else colored("水道", "蓝"))
                           for i, rock in enumerate(rocks)))
    start = time.time()
    lane = ask_number("往哪边划? ", 1, 3) - 1
    seconds = time.time() - start
    if rocks[lane]:
        print(f"往{LANES[lane]}划, 正好撞上了礁石!")
        hit_rock(game)
    elif seconds > RAPID_SECONDS and random.random() < 0.5:
        print(f"用了 {seconds:.1f} 秒, 太慢了, 木筏被水流冲歪, 擦着礁石撞了上去!")
        hit_rock(game)
    elif seconds > RAPID_SECONDS:
        print(f"用了 {seconds:.1f} 秒, 有点慢, 好在木筏还是从{LANES[lane]}冲过去了。")
    else:
        print(f"木筏从{LANES[lane]}的水道冲了过去, 礁石就在旁边擦过!")


def hit_rock(game):
    """木筏撞上礁石: 一些东西掉进河里, 有人受伤, 还可能有人被冲走"""
    s = game["supplies"]
    lost = []
    for item in random.sample([item for item in s if s[item]], min(2, sum(1 for item in s if s[item]))):
        amount = max(1, s[item] * random.randint(20, 50) // 100)
        s[item] -= amount
        lost.append(f"{amount} {MEASURES[item]}{item}")
    if lost:
        print(f"掉进河里冲走了: {'、'.join(lost)}。")
    victim = random_member(game)
    if random.random() < RAPID_HIT_DROWN:
        lose_member(game, victim, "掉进了哥伦比亚河, 被急流冲走了。")
    else:
        print(f"{victim} 撞伤了, 还呛了几口带辐射的河水。")
        irradiate(game, victim, RIVER_RADS)
        hurt(game, victim, random.randint(10, 20))
    write_diary(game, "木筏在哥伦比亚河的急流里撞上了礁石。")


# ========== 随机事件(想加新事件就照着写一个函数, 再放进 EVENTS) ==========
# (辐射风暴以前是随机事件, 现在是天气, 写在 roll_weather 里)


def raiders(game):
    s = game["supplies"]
    print(f"\n{title('劫匪', '红')}一伙劫匪拦住了路!")
    print(f"「{pick(game, '小子', '丫头')}, 把东西交出来, 饶{you(game)}不死!」")
    print("1. 交出一些物资  2. 开枪(要 15 发子弹)  3. 加速逃跑(要 3 份燃料)")
    choice = ask_number("你怎么办? ", 1, 3)

    if choice == 2 and s["子弹"] >= 15:
        s["子弹"] -= 15
        veteran = skilled(game, "老兵")
        if veteran:
            print(f"老兵{veteran}几枪就把劫匪打跑了, 谁都没受伤。")
            write_diary(game, f"遇到劫匪, 老兵{veteran}把他们打跑了。")
        elif random.random() < 0.7:
            print(f"{you(game)}打退了劫匪!")
            write_diary(game, "遇到劫匪, 开枪打退了他们。")
        else:
            victim = random_member(game)
            print(f"劫匪被打跑了, 但是 {victim} 中枪受伤了。")
            write_diary(game, f"遇到劫匪, 打跑了他们, 但是 {victim} 中枪受伤了。")
            hurt(game, victim, 35)
            if random.random() < sick_odds(game, INFECTION_CHANCE):
                get_sick(game, victim, "伤口感染")
        return

    if choice == 3 and s["燃料"] >= 3:
        s["燃料"] -= 3
        if random.random() < 0.6:
            print(f"{you(game)}甩掉了劫匪!")
            write_diary(game, "遇到劫匪, 加速甩掉了他们。")
            return
        print("没跑掉……")
    elif choice != 1:
        print("你的子弹或燃料不够, 只能交出物资。")

    for item in ["食物", "水", "子弹"]:
        s[item] -= s[item] // 3
    game["money"] -= game["money"] // 3
    print("劫匪抢走了三分之一的食物、水、子弹和钱。")
    write_diary(game, "遇到劫匪, 被抢走了三分之一的食物、水、子弹和钱。")


def breakdown(game):
    s = game["supplies"]
    print(f"\n{title('车坏了', '红')}车子突然停下, 冒出一股黑烟!")
    mechanic = skilled(game, "机械师")
    if mechanic:
        print(f"机械师{mechanic}钻到车底下鼓捣了一会儿, 没用零件就修好了。")
        write_diary(game, f"车坏了, 机械师{mechanic}当场修好了。")
    elif s["零件"] > 0:
        s["零件"] -= 1
        print("你用了 1 个备用零件, 很快就修好了。")
        write_diary(game, "车坏了, 用掉 1 个零件修好了。")
    else:
        print("没有备用零件, 只能自己慢慢修, 花了 3 天。")
        write_diary(game, "车坏了, 没有零件, 修了 3 天。")
        for _ in range(3):
            pass_day(game)


def warehouse(game):
    print(f"\n{title('废弃仓库')}路边有一个没被搜过的旧仓库!")
    write_diary(game, "发现一个没被搜过的旧仓库, 找到了一些物资。")
    for _ in range(2):
        find_supplies(game)


def mutant_attack(game):
    s = game["supplies"]
    print(f"\n{title('变异野兽', '红')}一群变异野狗冲了过来!")
    veteran = skilled(game, "老兵")
    bullets = 5 if veteran else 10
    if s["子弹"] >= bullets:
        s["子弹"] -= bullets
        if veteran:
            print(f"老兵{veteran}枪法准, 只用 5 发子弹就把它们赶走了。")
        else:
            print(f"{you(game)}开枪把它们赶走了, 用掉 10 发子弹。")
        write_diary(game, "遇到一群变异野狗, 开枪赶走了。")
    else:
        victim = random_member(game)
        print(f"子弹不够! {victim} 被咬伤了。")
        write_diary(game, f"遇到一群变异野狗, 子弹不够, {victim} 被咬伤了。")
        hurt(game, victim, 30)
        if random.random() < sick_odds(game, INFECTION_CHANCE):
            get_sick(game, victim, "伤口感染")


def radiation_sickness(game):
    victim = random_member(game)
    irradiate(game, victim, SICKNESS_RADS)
    print(f"\n{title('辐射病', '紫')}{victim} 开始掉头发、发烧, 身体里积了太多辐射 (辐射升到了 {game['rads'][victim]})。")
    print("不用排辐剂排掉的话, 辐射会一天天折磨人。")
    write_diary(game, f"{victim} 得了辐射病。")


def bad_water(game):
    s = game["supplies"]
    lost = s["水"] // 4
    s["水"] -= lost
    print(f"\n{title('水被污染', '红')}一桶水漏进了脏东西, 倒掉了 {lost} 份水。")
    write_diary(game, f"一桶水被污染了, 倒掉了 {lost} 份水。")


def trader(game):
    s = game["supplies"]
    print(f"\n{title('流浪商人')}一个背着大包的流浪商人凑了过来:")
    print(f"「{pick(game, '老兄', '妹子')}, 20 份食物换 8 份燃料, 换不换?」")
    if s["食物"] < 20:
        print("可惜你的食物不够, 换不了。")
        return
    if CAR_CAPACITY - load_of(game) + 20 * WEIGHTS["食物"] < 8 * WEIGHTS["燃料"]:   # 给出 20 份食物以后, 装不装得下 8 份燃料
        print("可惜车上太重了, 装不下 8 份燃料, 换不了。")
        return
    if ask_number("1. 换  2. 不换  ", 1, 2) == 1:
        s["食物"] -= 20
        s["燃料"] += 8
        print("交换成功。")
        write_diary(game, "跟流浪商人用 20 份食物换了 8 份燃料。")


def stranger(game):
    s = game["supplies"]
    name = random.choice(STRANGER_NAMES)
    while name in game["party"] or name in game["dead"]:
        name += "2"
    print(f"\n{title('陌生人')}路边有个叫 {name} 的幸存者, 想跟{you(game)}一起走。")
    show_picture(PORTRAITS["陌生人"], words=["", "", name])
    print(f"「{pick(game, '大哥', '大姐')}, 带上我吧, 我什么活都能干!」")
    if len(game["party"]) >= MAX_PARTY:
        print(f"可惜车上已经坐满了, 只能让 {name} 自己走。")
        return
    if not has_seat_for_one_more(game):
        print(f"可惜车上东西太重, 再坐一个人就超载了, 只能让 {name} 自己走。")
        return
    print("多一个人能多一份力气, 但每天也要多吃多喝。")
    if ask_number(f"1. 让{name}加入  2. 拒绝  ", 1, 2) == 2:
        print(f"{name} 失望地走开了。")
        return
    if random.random() < 0.25:
        food = s["食物"] // 4
        fuel = s["燃料"] // 4
        s["食物"] -= food
        s["燃料"] -= fuel
        print(f"第二天早上, {name} 不见了, 还偷走了 {food} 份食物和 {fuel} 份燃料!")
        write_diary(game, f"收留了陌生人 {name}, 结果被偷走了 {food} 份食物和 {fuel} 份燃料。")
    else:
        game["party"][name] = random.randint(60, 90)
        print(f"{name} 加入了队伍!")
        write_diary(game, f"路上遇到的 {name} 加入了队伍。")


def minefield(game):
    s = game["supplies"]
    print(f"\n{title('雷区', '红')}路边插着一块歪掉的牌子: \"小心地雷\"。")
    print("1. 绕路(多花 1 天和 2 份燃料)  2. 慢慢开过去")
    choice = ask_number("你怎么办? ", 1, 2)
    if choice == 1 and s["燃料"] >= 2:
        s["燃料"] -= 2
        write_diary(game, "绕路避开了一片雷区, 多花了 1 天。")
        pass_day(game)
        print(f"{you(game)}绕开了雷区, 平安无事。")
        return
    if choice == 1:
        print("燃料不够绕路, 只能硬着头皮开过去……")
    if random.random() < 0.4:
        victim = random_member(game)
        print(f"轰! 车轮压到了一颗地雷, {victim} 受了重伤。")
        write_diary(game, f"开过雷区时压到地雷, {victim} 受了重伤。")
        hurt(game, victim, 40)
        get_sick(game, victim, "骨折")
    else:
        print(f"{you(game)}小心翼翼地开了过去, 什么都没炸。")
        write_diary(game, "冒险开过了一片雷区, 平安无事。")


def radio_signal(game):
    print(f"\n{title('神秘无线电')}收音机里传来断断续续的声音, 好像在说附近有个旧世界的地堡。")
    if ask_number("要花 2 天去找吗? 1. 去  2. 不去  ", 1, 2) == 2:
        return
    for _ in range(2):
        pass_day(game)
    if not game["party"]:
        return
    roll = random.random()
    if roll < 0.2 and not game["seeds"]:
        game["seeds"] = True
        print(f"{you(game)}找到了一个旧世界的种子库! 里面封存着几千种植物的种子。")
        print("这些种子也许能让废土重新变绿……一定要把它们带到俄勒冈城!")
        write_diary(game, "顺着神秘无线电, 找到了一个旧世界的种子库!")
    elif roll < 0.7:
        print("地堡里还剩下不少旧物资!")
        write_diary(game, "顺着神秘无线电找到一个地堡, 搜到了不少旧物资。")
        for _ in range(3):
            find_supplies(game)
    else:
        print("这是个陷阱! 信号是劫匪放出来的!")
        write_diary(game, "神秘无线电是劫匪设的陷阱。")
        raiders(game)


EVENTS = [raiders, breakdown, warehouse,
          mutant_attack, radiation_sickness, bad_water, trader,
          stranger, minefield, radio_signal]


def random_event(game, km):
    """路上发生随机事件的机会跟开了多远有关: 每开 100 公里, 大约有 35% 的机会 (简单难度少一些, 困难多一些)。
    这样开得慢不会因为在路上的天数多, 就遇到更多倒霉事"""
    chance = EVENT_CHANCE_PER_100KM * km / 100 * DIFFICULTIES[game["difficulty"]][2] / 100
    if game["party"] and random.random() < chance:
        event_screen()
        random.choice(EVENTS)(game)


# ========== 结局 ==========

def arrive(game):
    """到达俄勒冈城, 根据路上的情况决定是哪个结局。返回结局的名字 (比如"完美结局"), 记最高分时要用"""
    last_day = game["day"] - 1
    new_screen()
    play_music("到达")
    show_picture(CITY_ART, "绿")
    print(f"\n{date_text(game, last_day)}, {you(game)}到达了{DESTINATION}! 一共用了 {last_day} 天。")
    write_diary(game, f"到达了{DESTINATION}!", day=last_day)
    print(f"活下来的人: {'、'.join(game['party'])}")
    if game["dead"]:
        print(f"路上失去的人: {'、'.join(game['dead'])}")
    if game["leader"] in game["dead"]:
        print(f"{game['leader']} 没能走到这里, 是同伴们替{game['leader']}走完了这条路。")

    if game["seeds"]:
        ending = "隐藏结局"
        print("\n" + title("隐藏结局: 绿色的希望", "绿"))
        print("城里的科学家打开种子库, 激动得说不出话。")
        print("第二年春天, 城墙外第一次长出了麦子。废土开始变绿了。")
        show_picture(FIELD_ART, "绿")
    elif not game["dead"] and len(game["party"]) == 1:
        ending = "独行结局"
        print("\n" + title("独行结局: 一个人走完全程", "绿"))
        print("没有人陪你, 也没有人掉队。你一个人走完了整条俄勒冈小道。")
    elif not game["dead"]:
        ending = "完美结局"
        print("\n" + title("完美结局: 一个都不少", "绿"))
        print("所有人都平安到达。城门打开的那一刻, 大家抱在一起哭了。")
    elif len(game["party"]) == 1:
        name = list(game["party"])[0]
        ending = "孤独结局"
        print("\n" + title("孤独结局: 最后一个人", "绿"))
        print(f"{name} 一个人走进城门, 身后的车里空荡荡的。")
        print("活下来的人, 要带着所有人的那一份继续活下去。")
    else:
        ending = "普通结局"
        print("\n" + title("普通结局: 带着伤痕到达", "绿"))
        print("你们活下来了, 但这条路让每个人都付出了代价。")
    return ending


# ========== 得分和最高分 ==========

def score_of(game):
    """算分: 活下来的人按健康给分, 剩下的物资和钱也换成分。返回 (总分, 每一项怎么算的)"""
    total = 0
    lines = []
    for name, h in game["party"].items():
        points = SCORE_PER_PERSON[health_word(h)]
        total += points
        lines.append(f"{name} 健康{health_word(h)}: {points} 分")
    for item, (per, points) in SCORE_SUPPLIES.items():
        have = game["supplies"][item]
        got = have // per * points
        if got:
            total += got
            lines.append(f"剩下 {have} {MEASURES[item]}{item}: {got} 分")
    got = game["money"] // SCORE_MONEY
    if got:
        total += got
        lines.append(f"剩下 {game['money']} 块钱: {got} 分")
    if game["seeds"]:
        total += SCORE_SEEDS
        lines.append(f"带来了种子库的种子: {SCORE_SEEDS} 分")
    name, _, _, _, percent, _ = DIFFICULTIES[game["difficulty"]]
    if percent != 100:   # 普通难度不用乘
        total = total * percent // 100
        lines.append(f"{name}难度: 得分 ×{percent / 100:g}")
    return total, lines


def load_high_scores():
    """读最高分榜: 一个列表, 每一项是一局的成绩 (分数从高到低)。没有文件或者文件坏了, 就当是空的"""
    if not os.path.exists(HIGH_SCORE_FILE):
        return []
    try:
        with open(HIGH_SCORE_FILE, encoding="utf-8") as f:
            scores = json.load(f)
    except (OSError, ValueError):
        return []
    if not isinstance(scores, list):
        return []
    keys = ["name", "score", "ending", "days", "survivors"]
    return [entry for entry in scores if isinstance(entry, dict) and all(key in entry for key in keys)]


def save_high_scores(scores):
    try:
        with open(HIGH_SCORE_FILE, "w", encoding="utf-8") as f:
            json.dump(scores, f, ensure_ascii=False, indent=2)
    except OSError:
        print("最高分没能存下来, 可能是文件夹不能写入。")


def record_score(game, ending):
    """走到终点以后: 算分, 再看看能不能进最高分榜"""
    total, lines = score_of(game)
    print("\n========== 得分 ==========")
    for line in lines:
        print("  " + line)
    print(colored(f"总分: {total} 分", "黄", bold=True))
    entry = {"name": game["leader"], "score": total, "ending": ending,
             "days": game["day"] - 1, "survivors": len(game["party"]),
             "difficulty": DIFFICULTIES[game["difficulty"]][0]}
    scores = load_high_scores() + [entry]
    scores.sort(key=lambda e: e["score"], reverse=True)   # 分数一样时, 先得到的排在前面
    scores = scores[:HIGH_SCORES]
    ranks = [i for i, e in enumerate(scores, 1) if e is entry]
    if not ranks:
        print(f"没能进前 {HIGH_SCORES} 名, 下次再加油!")
        return
    save_high_scores(scores)
    print(colored(f"进了最高分榜, 第 {ranks[0]} 名!", "绿", bold=True))
    show_high_scores()


def show_high_scores():
    """主菜单里的「最高分」, 也在进榜的时候给玩家看"""
    print(f"\n========== 最高分 (前 {HIGH_SCORES} 名) ==========")
    scores = load_high_scores()
    if not scores:
        print("还没有人走到俄勒冈城。走到终点才算分。")
    for i, e in enumerate(scores, 1):
        difficulty = e.get("difficulty", "普通")   # 以前没有难度选择, 那时候的成绩都算普通
        print(f"{i:>2}. {e['score']:>5} 分  {e['name']}  {difficulty}  {e['ending']}, "
              f"用了 {e['days']} 天, {e['survivors']} 个人到达")


# ========== 存档 ==========

def save_game(game):
    try:
        with open(SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(game, f, ensure_ascii=False, indent=2)
        print("\n存档成功! 下次打开游戏可以接着玩。")
    except OSError:
        print("\n存档失败了, 可能是文件夹不能写入。")


def load_game():
    """读存档。没有存档或者存档坏了, 就返回 None"""
    if not os.path.exists(SAVE_FILE):
        return None
    try:
        with open(SAVE_FILE, encoding="utf-8") as f:
            saved = json.load(f)
    except (OSError, ValueError):
        print("存档文件坏了, 只能开始新游戏。")
        return None
    game = new_game()   # 先放好默认值, 这样旧版本的存档少了什么也不怕
    game.update(saved)
    for item in PRICES:   # 旧存档里没有后来才加的物资 (比如冬衣)
        game["supplies"].setdefault(item, 0)
    if game["weather"] not in WEATHER:   # 旧版本的天气 (比如"晴朗""酷热") 现在没有了
        game["weather"] = "晴"
    for start, _, name, _, _, _ in HOTSPOTS:   # 旧存档里已经开进去 (或者开过去) 的辐射热点, 不用再提醒
        if game["distance"] >= start and name not in game["visited"]:
            game["visited"].append(name)
    return game


def delete_save():
    """一局玩完就删掉存档, 不能读档重来"""
    if os.path.exists(SAVE_FILE):
        os.remove(SAVE_FILE)


# ========== 音乐 ==========
# 在终端里: 另外开一个线程 (跟游戏同时跑的一小段程序) 一首一首地放, 游戏照常往下走。
# 网页版里: run_in_browser.py 把 start_playing 换掉, 让网页去放

music_now = {"background": None, "turn": 0, "process": None}   # 现在的背景音乐、第几次换音乐、正在放的播放器
music_lock = threading.Lock()   # 换音乐和开始放一首, 不能同时进行


def can_play_music():
    """能不能放音乐: 设置里没关掉, 而且是在真正的终端里或者网页版里"""
    return MUSIC and (can_read_keys() or IN_BROWSER)


def play_music(name):
    """放 MUSIC_TRACKS 里的一首。背景音乐已经在放了就不重新开始"""
    if not can_play_music():
        return
    file, how = MUSIC_TRACKS[name]
    if how == "循环":
        if music_now["background"] == name:
            return
        music_now["background"] = name
        start_playing([(file, True)])
        return
    if how == "结尾":
        music_now["background"] = None
    playlist = [(file, False)]
    if music_now["background"]:   # 放完这一段, 接着放原来的背景音乐
        playlist.append((MUSIC_TRACKS[music_now["background"]][0], True))
    start_playing(playlist)


def stop_music():
    music_now["background"] = None
    start_playing([])


def start_playing(playlist):
    """停下正在放的, 改放 playlist: [(文件, 是不是一直循环), ...], 一首一首地放"""
    with music_lock:
        music_now["turn"] += 1   # 以前的线程看到这个数变了, 就知道该停了
        process = music_now["process"]
        if process and process.poll() is None:
            process.terminate()
        if winsound:
            try:
                winsound.PlaySound(None, 0)
            except RuntimeError:
                pass
    if playlist:
        threading.Thread(target=music_thread, args=(playlist, music_now["turn"]), daemon=True).start()


def music_thread(playlist, turn):
    """在另一个线程里一首一首地放, 直到换了音乐"""
    for file, loop in playlist:
        path = os.path.join(MUSIC_FOLDER, file)
        while music_now["turn"] == turn:
            if not play_file(path, turn):
                return
            if not loop:
                break


def play_file(path, turn):
    """把一首放一遍, 放完 (或者换了音乐) 才回来。放不了 (没有这个文件、文件坏了、电脑上没有播放器或者声音设备) 就返回 False"""
    try:
        seconds = sound_length(path)
    except (OSError, EOFError, wave.Error):   # 没有这个文件, 或者文件坏了
        return False
    if winsound:
        with music_lock:
            if music_now["turn"] != turn:
                return False
            try:
                winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            except RuntimeError:   # 电脑上没有能出声音的设备
                return False
        end = time.time() + seconds
        while time.time() < end and music_now["turn"] == turn:
            time.sleep(0.05)
        return True
    player = music_player()
    if not player:
        return False
    with music_lock:
        if music_now["turn"] != turn:
            return False
        try:
            process = subprocess.Popen(player + [path], stdin=subprocess.DEVNULL,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            return False
        music_now["process"] = process
    process.wait()
    # 放完了是 0。不是 0 又不是被我们换音乐时关掉的, 就是播放器放不了 (比如电脑上没有声音设备),
    # 这时别再重新开它, 不然循环的背景音乐会让播放器一秒钟重启几百次
    return process.returncode == 0 or music_now["turn"] != turn


def music_player():
    """Mac 和 Linux 上用系统自带的播放器: Mac 有 afplay, Linux 一般有 paplay 或 aplay。都没有就返回 None"""
    for command in [["afplay"], ["paplay"], ["aplay", "-q"]]:
        if shutil.which(command[0]):
            return command
    return None


def sound_length(path):
    """一首有几秒长"""
    with wave.open(path) as f:
        return f.getnframes() / f.getframerate()


atexit.register(stop_music)   # 游戏关掉的时候 (包括按 Ctrl+C), 把音乐也关掉


# ========== 过场动画 ==========
# 只在真正的终端里和网页版里播 (跑测试、用管道输入时不播)。
# 画面里只用英文字符: 中文字在终端里占两格, 跟英文字对不齐。要写中文就写在画面的下面

# 一帧画面就是一块「画布」: 一行一行的格子, 每个格子是 [字, 颜色]。
# 先画远处的东西, 再画近处的, 后画的盖住先画的, 就有了前后
SCENE_WIDTH = 60
SCENE_HEIGHT = 11

# 大画面 (见 dashboard_lines) 的大小
DASH_LEFT = SCENE_WIDTH                           # 左边一栏多宽 (跟动画一样宽)
DASH_RIGHT = DASHBOARD_WIDTH - DASH_LEFT - 3      # 右边一栏多宽 (三条竖线各占一格)
DASH_MAP_ROWS = 3
DASH_EVENT_ROWS = 5
DASH_ROWS = SCENE_HEIGHT + 1 + DASH_MAP_ROWS + 1 + DASH_EVENT_ROWS   # 方框里面有几行 (右边一栏也是这么多行)


def can_animate():
    """能不能播动画、显示画面: 设置里没关掉, 而且是在真正的终端里或者网页版里"""
    return ANIMATION and (can_read_keys() or IN_BROWSER)


def new_canvas():
    return [[[" ", None] for _ in range(SCENE_WIDTH)] for _ in range(SCENE_HEIGHT)]


def draw(canvas, y, x, text, color=None, behind=False, solid=False):
    """把 text 画在画布的第 y 行、第 x 列 (画到画布外面的部分就不要了)。
    text 里的空格是透明的, 会透出后面的东西; solid=True 时, 字中间的空格也会盖住后面 (比如车身里面不该看到雨)。
    behind=True 时只画在还空着的格子上 (比如雨雪落在山和车的后面)"""
    if not 0 <= y < len(canvas) or not text.strip():
        return
    first = len(text) - len(text.lstrip())
    last = len(text.rstrip())
    for i, ch in enumerate(text):
        if not 0 <= x + i < SCENE_WIDTH:
            continue
        if ch == " " and not (solid and first <= i < last):
            continue
        cell = canvas[y][x + i]
        if behind and cell[0] != " ":
            continue
        cell[0], cell[1] = ch, color


def canvas_lines(canvas):
    """把画布变成一行一行可以打印的字: 颜色一样的几个字连在一起上色"""
    lines = []
    for row in canvas:
        line = ""
        start = 0
        while start < len(row):
            color = row[start][1]
            end = start
            while end < len(row) and row[end][1] == color:
                end += 1
            line += colored("".join(ch for ch, _ in row[start:end]), color)
            start = end
        lines.append(line)
    return lines


def scene_slice(tile, offset):
    """背景是一条可以无限循环的长条, 从里面切出屏幕宽的一段"""
    start = offset % len(tile)
    return (tile * (SCENE_WIDTH // len(tile) + 3))[start:start + SCENE_WIDTH]


def play_frames(frames, delay=None):
    """一帧一帧地播动画: 画完一帧, 用控制字符 \\x1b[NA 把光标往上移 N 行, 下一帧盖掉上一帧。
    动画不算新消息 (一直往前开的时候, 每天都有动画, 不能因为它停下来)"""
    enable_ansi()
    before = dict(screen)
    print("\x1b[?25l", end="")   # 先把光标藏起来, 不然它会在画面上一闪一闪
    try:
        print()
        for i, rows in enumerate(frames):
            if i:
                print(f"\x1b[{len(rows)}A", end="")   # 光标往上移回画面顶上, 用新的一帧盖掉旧的
            print("\n".join(rows), flush=True)
            time.sleep(ANIMATION_DELAY if delay is None else delay)
        # 擦掉动画下面剩下的旧字 (\x1b[J): 一直往前开的时候, 动画是盖在昨天的画面上的, 下面还有昨天的状态
        print("\x1b[J", end="")
    finally:
        print("\x1b[?25h", end="", flush=True)   # 不管怎么结束 (包括按 Ctrl+C), 都要把光标显示回来
        screen.update(before)


def enable_ansi():
    """颜色和动画都要用控制字符 (比如动画要把光标往上移, 好让新的一帧盖掉旧的)。
    Mac 和 Linux 的终端本来就认得; Windows 的要先把这个功能打开"""
    if os.name != "nt":
        return
    try:
        import ctypes   # 只有 Windows 用得到, 放在这里 (网页版里的 Python 不一定有这个模块)
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)                # -11 表示"屏幕输出"
        mode = ctypes.c_uint32()
        kernel32.GetConsoleMode(handle, ctypes.byref(mode))
        kernel32.SetConsoleMode(handle, mode.value | 4)    # 4 就是"认得控制字符"的开关
    except (ImportError, AttributeError, OSError):
        pass


# ---------- 车 ----------

# 车头朝左 (往西开)。1~4 是车窗里的座位, 有人坐就画成 o (司机先坐), 没人就空着
CAR_ART = [
    "        _________    ",
    "  _____/1 2 | 3 4\\__ ",
    " <________________o_|",
    "   (@)          (@)  ",
]
# 在河里翻过来的车: 轮子朝天
FLIPPED_CAR = [
    "   (@)          (@)  ",
    " <________________o_|",
    "  ~~~~~\\__ | __/~~~  ",
]
DUST = ["  . o ", " o . O", "O  o .", " . O  "]   # 车尾扬起的尘土, 一帧换一个


def car_art(people):
    """车的样子: 车窗里坐着几个人"""
    rows = []
    for line in CAR_ART:
        for seat in "1234":
            line = line.replace(seat, "o" if int(seat) <= people else " ")
        rows.append(line)
    return rows


# ---------- 赶路 ----------

# 赶路时车停在中间往西 (左) 开, 背景往右退。远处的山退得慢, 近处的东西退得快, 看起来就有远近
SCENE_SKY = "       v                       .                  v          "     # 天上盘旋的秃鹫
SCENE_FAR = "      /\\           __/\\__              /\\/\\          ___/\\_   "   # 远处的山
SCENE_NEAR = [                                                                  # 近处的废墟、枯树、破车
    "       _               \\ /                        ._.          ",
    "     _| |_      __     _|_        ___            |  |    \\|/  ",
    "    |  |  |    /  \\   |   |      /_x_\\    .      |  |_    |   ",
]
# 路面上的裂缝要不规则: 要是每隔 4 格一个, 每帧又正好移 4 格, 看起来就像没动 (跟电影里车轮像是倒着转一个道理)
SCENE_ROAD = "=  =   =   .  =  =    =   , =  ==   =  .   =  =  "
CAR_X = 18   # 赶路时车画在第几列

# 天气在动画里的样子: 天气 -> (怎么动, 一长条会循环的花纹, 颜色)
# 怎么动: 雨每帧往下落一行, 雪两帧落一行, 风横着吹, 雾慢慢飘, 云只在天上
WEATHER_ART = {
    "辐射尘云":   ("云", "  (   ~~~   )        (~~   ~~)            (  ~~  ~ )         ", "灰"),
    "毒雾":       ("雾", "~~~   ~~~~~    ~~  ~~~~     ~~~    ~~~~~  ~~      ", "黄"),
    "黑雨":       ("雨", "'     ,      '       ,    '        ,     '    ,       ", "灰"),
    "酸雨":       ("雨", "'     ,      '       ,    '        ,     '    ,       ", "黄"),
    "辐射风暴":   ("雨", "'     ,      '       ,    '        ,     '    ,       ", "绿"),
    "灰雪":       ("雪", "*       .      *         .     *       .        *    ", "灰"),
    "灰色暴风雪": ("风", "-  *  --  .   *  -   --  *   . -  *    --   .  *  - ", "灰"),
    "辐射沙尘暴": ("风", ".  :  -   .  ~  .  :  -  .   ~  :  .  -   :  .  ~ ", "黄"),
}
STORM_CLOUDS = " (~~~~)  ( ~~~ )   (~~~~~)   ( ~~ )  (~~~~~~)  (~~~)   "   # 辐射风暴时天上的绿云
LIGHTNING = ["  \\", "  /", " / ", " \\ "]                                    # 绿色的闪电


def weather_layer(canvas, frame, moved, weather, bottom):
    """把天气画到画布上 (从最上面画到第 bottom 行)。moved 是背景已经退了几格"""
    if weather not in WEATHER_ART:
        return
    how, tile, color = WEATHER_ART[weather]
    if how == "云":
        draw(canvas, 0, 0, scene_slice(tile, -moved // 6 - frame // 3), color)
        return
    if weather == "辐射风暴":   # 天变绿, 隔一会儿打一个闪电
        draw(canvas, 0, 0, scene_slice(STORM_CLOUDS, -moved // 6), "绿")
        if frame % 9 in (4, 5):
            x = 8 + frame * 7 % 40
            for i, part in enumerate(LIGHTNING):
                draw(canvas, 1 + i, x, part, "绿")
    for y in range(1 if weather == "辐射风暴" else 0, bottom + 1):
        if how == "雨":      # 每帧往下落一行, 稍微往右斜
            text = scene_slice(tile, 3 * y - 4 * frame - moved)
        elif how == "雪":    # 两帧往下落一行
            text = scene_slice(tile, 5 * y - 6 * (frame // 2) - moved)
        elif how == "风":    # 横着往左吹得很快
            text = scene_slice(tile, 7 * y + 5 * frame)
        else:                # 雾只在半空中, 慢慢飘
            if not 2 <= y <= 5:
                continue
            text = scene_slice(tile, 9 * y + frame // 2 - moved)
        draw(canvas, y, 0, text, color, behind=(how != "雾"))


def road_scene(frame, speed, weather="晴", people=1, dust=True):
    """赶路的第 frame 帧。speed 是车速 (1 慢, 2 中, 3 快, 0 是车停着), 越快背景退得越快。
    weather 是今天的天气, people 是车上有几个人"""
    moved = frame * speed
    canvas = new_canvas()
    draw(canvas, 0, 0, scene_slice(SCENE_SKY, -moved // 6))
    draw(canvas, 1, 0, scene_slice(SCENE_FAR, -moved // 3))
    for i, line in enumerate(SCENE_NEAR):
        draw(canvas, 2 + i, 0, scene_slice(line, -moved))
    draw(canvas, 5, 0, "_" * SCENE_WIDTH)                    # 地平线
    draw(canvas, 10, 0, scene_slice(SCENE_ROAD, -moved))     # 路面
    weather_layer(canvas, frame, moved, weather, 9)
    car = car_art(people)
    for i, part in enumerate(car):
        draw(canvas, 6 + i, CAR_X, part, solid=True)
    if speed and dust:   # 车在开, 车尾扬起尘土 (dust=False 是画一个停着的样子)
        draw(canvas, 8, CAR_X + len(car[2].rstrip()), DUST[frame % len(DUST)])
    return canvas_lines(canvas)


def drive_animation(game, moving=True):
    """赶路时播放的过场动画: 天气跟着变, 车窗里能看到车上的人。moving=False 是车开不动、停在原地 (暴风雪)"""
    if not can_animate():
        return
    speed = game["pace"] if moving else 0
    people = len(game["party"])
    play_frames(road_scene(frame, speed, game["weather"], people) for frame in range(ANIMATION_FRAMES))


# ---------- 过河 ----------

# 河在中间, 两边是河岸; 车从右边 (东岸) 开到左边 (西岸)。第 8 行是地面和水面, 越往下河越窄
RIVER_ROWS = [
    "===========\\" + "w" * 36 + "/===========",
    "############\\" + "w" * 34 + "/############",
    "#############\\" + "w" * 32 + "/#############",
]
RIVER_WAVES = "~  ~~ ~   ~ ~~  ~  ~~~ ~   ~~ ~  ~ ~~~  ~   ~~ "
FLOAT_BARRELS = " [O]   [O]  [O]   [O] "   # 绑在车身下面的空油桶
FERRY_RAFT = "|=======================|"
SPLASH = ["  *  .  * ", " . * ~ * .", "* . ~  . *"]   # 发动机进水、翻车时溅起的水花


def river_scene(frame, x, how, sunk=0, flipped=False, splash=False, people=1):
    """过河的一帧: 车的左边在第 x 列; how 是怎么过河 ("开" "浮" "渡船");
    sunk 是车在水里往下沉了几行; flipped=True 时车翻了; splash=True 时水花四溅"""
    canvas = new_canvas()
    draw(canvas, 0, 0, SCENE_SKY)
    draw(canvas, 1, 0, SCENE_FAR)
    if how == "渡船":   # 横过河面的钢缆, 两头拴在岸上的柱子上
        draw(canvas, 2, 3, "o" + "-" * 52 + "o")
        for y in range(3, 8):
            draw(canvas, y, 3, "|")
            draw(canvas, y, 56, "|")
        draw(canvas, 3, x + 10, "Y")   # 挂在钢缆上的滑轮
    for i, line in enumerate(RIVER_ROWS):   # 河岸先画好, 水留着空
        draw(canvas, 8 + i, 0, line.replace("w", " "))
    if flipped:
        for i, part in enumerate(FLIPPED_CAR):
            draw(canvas, 5 + sunk + i, x, part, solid=True)
    else:
        for i, part in enumerate(car_art(people)):
            draw(canvas, 4 + sunk + i, x, part, solid=True)
    for i, line in enumerate(RIVER_ROWS):   # 再画水: 水面会盖住车泡在水里的部分
        start = line.index("w")
        water = scene_slice(RIVER_WAVES, frame + i * 5)[:line.count("w")]
        if i == 0:   # 水面: 浪花之间透出车
            draw(canvas, 8, start, water, "蓝")
        else:        # 水下: 什么都看不见, 整个盖住
            for j, ch in enumerate(water):
                canvas[8 + i][start + j] = [ch, "蓝" if ch != " " else None]
    if how == "浮" and not flipped and in_river(x):   # 漂在水面上的油桶和渡船的筏子
        draw(canvas, 8, x, FLOAT_BARRELS)
    if how == "渡船":
        draw(canvas, 8, x - 2, FERRY_RAFT, solid=True)
    if splash:
        draw(canvas, 3 + sunk, x + 5, SPLASH[frame % len(SPLASH)], "蓝")
    return canvas_lines(canvas)


def in_river(x):
    """车的左边在第 x 列时, 车身中间是不是在河里"""
    return 12 <= x + 10 <= 47


def river_frames(how, result, people):
    """过河的整段动画: 一帧一帧的画面。how 是 "开" "浮" "渡船"; result 是 "过去了" "进水" "翻车"。
    车从东岸开下水, 过了河停在西岸上 (出了事就停在河中间)"""
    if how == "渡船":   # 渡船慢慢地沿着钢缆横过河面
        return [river_scene(frame, 26 - frame // 2, how, people=people) for frame in range(28)]
    sunk_in_water = 0 if how == "浮" else (1 if result == "过去了" else 2)
    frames = []
    frame = 0
    for x in range(44, -1, -2):
        if result != "过去了" and x <= 20:
            break   # 开到河中间出事了, 下面接着画
        frames.append(river_scene(frame, x, how, sunk_in_water if in_river(x) else 0, people=people))
        frame += 1
    if result == "进水":     # 熄火停在河中间, 水花四溅; 再慢慢推上岸
        for i in range(10):
            frames.append(river_scene(frame + i, 20, how, 2, splash=True, people=people))
        for i, x in enumerate(range(19, -1, -1)):
            frames.append(river_scene(frame + 10 + i, x, how, 2 if in_river(x) else 0, people=people))
    elif result == "翻车":   # 车被急流掀翻, 在水里一沉一浮
        for i in range(15):   # 最后一帧轮子还露在水面上
            frames.append(river_scene(frame + i, 20, how, 2 + i % 2, flipped=True, splash=i < 8, people=people))
    return frames


def river_animation(game, how, result):
    """过河时播放的动画"""
    if can_animate():
        play_frames(river_frames(how, result, len(game["party"])))


# ---------- 坐木筏 ----------

# 哥伦比亚河峡谷: 远处是雪山, 近处是玄武岩的崖壁和松树。木筏停在中间, 两岸往右退
GORGE_FAR = "         /\\                         ___         /\\/\\                    "
GORGE_NEAR = [
    "  _/|\\_      __/||\\_         _/|\\__      __/|\\_       ",
    " /|||||\\  ^ /||||||\\  ^  ^  /||||||\\ ^  /|||||\\   ^  ",
]
RAFT = "<=O===O===O===O===O==>"
RAFT_X = 18


def raft_scene(frame, people):
    """坐木筏漂流的第 frame 帧: 车停在木筏上, 河水和两岸往右退"""
    canvas = new_canvas()
    draw(canvas, 0, 0, scene_slice(SCENE_SKY, -frame // 2))
    draw(canvas, 1, 0, scene_slice(GORGE_FAR, -frame // 2))
    for i, line in enumerate(GORGE_NEAR):
        draw(canvas, 2 + i, 0, scene_slice(line, -frame))
    for i, part in enumerate(car_art(people)):
        draw(canvas, 4 + i, RAFT_X, part, solid=True)
    for y in range(8, SCENE_HEIGHT):
        draw(canvas, y, 0, scene_slice(RIVER_WAVES, y * 7 - frame * 3), "蓝")
    draw(canvas, 8, RAFT_X - 1, RAFT, solid=True)
    return canvas_lines(canvas)


def raft_animation(game):
    """坐木筏顺流而下的动画"""
    if can_animate():
        play_frames(raft_scene(frame, len(game["party"])) for frame in range(ANIMATION_FRAMES))


# ---------- 画面: 地标、据点、结局和人 ----------

def picture(text):
    """把一幅用三引号写的画变成一行一行的字 (去掉头尾的空行和每行后面的空格)"""
    return [line.rstrip() for line in text.strip("\n").split("\n")]


# 走到这些地方时先看一幅画: 名字 -> (画, 颜色)。过河的地方不用, 过河时有动画
PICTURES = {
    "灰洞": (picture(r"""
____
    \__
       \__      WINDLASS HILL
          \__
             \__              ,@@,      ,@@@,
                \__         ,@@@@@,   ,@@@@@@,
                   \__        |||        |||    ,@,
                      \_______|||________|||____|||____
"""), None),
    "法院岩": (picture(r"""
                    _______
              _____|       |_____
             |                   |              __
          ___|                   |___         _/  \_
         /                           \       /      \
   _____/                             \_____/        \______
"""), None),
    "烟囱岩": (picture(r"""
                      _
                     | |
                     | |
                     | |
                    /   \
                  _/     \_
              ___/         \___
        _____/                 \______
"""), None),
    "斯科茨崖": (picture(r"""
     ________                        __________
    /  ||  | \____                 _/ |  ||    \
   /   ||  |   |  \               /   |  ||  |  \
  /  | ||  |   |   \_____________/  | |  ||  |   \
 /___|_||__|___|_______________________|__||__|____\
"""), None),
    "独立岩": (picture(r"""
              _.-----------------._
          _.-'   1846   J.B.      '-._
       .-'  A.W.     1849    T.F.     '-.
     _/   1852   M.R.    S.H.  1847      \_
 ___/_______________________________________\___
"""), None),
    "魔鬼门": (picture(r"""
   ________                    ________
  |        \                  /        |
  |         \                /         |
  |          |      ~~      |          |
  |          |     ~~~~     |          |
__|__________|____~~~~~~____|__________|__
"""), None),
    "南山口": (picture(r"""
       /\                                     /\
      /  \/\         SOUTH PASS          /\/\/  \
     /      \__     ELEV 7412 FT      __/        \
    /          \______          _____/            \
___/                  \________/                   \___
"""), None),
    "苏打泉": (picture(r"""
             o    .   O     .   o
          .    O    .    o    O    .
        ___o_____.____O_____.____o___
       (  ~  ~  o  ~  ~  O  ~  ~  ~  )
        \___________________________/
"""), "青"),
    "美国瀑布": (picture(r"""
 ___________________________________
 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~|
 || |  || |  || |  || |  || |  || | |
 || |  || |  || |  || |  || |  || | |
 || |  || |  || |  || |  || |  || | |
~*~~*~~~*~~*~~~*~~*~~~*~~*~~~*~~*~~*~~
"""), "青"),
    "鲑鱼瀑布": (picture(r"""
                       ><>
  ~~~~~~~~~~~~~\            <><
  ~~~~~~~~~~~~~ \     ><>
                 | || | || |       <><
                 | || | || |
  ~~~~~~~~~~~~~~~*~~*~~*~~*~~*~~~~~~~~~~~
"""), "青"),
    "大圆谷": (picture(r"""
    /\    /\  /\      /\    /\  /\    /\
   /  \  /  \/  \    /  \/\/  \/  \  /  \
  /    \/  ,   ,  \/  ,    ,     ,  \/    \
 /  ,    ,    ,     ,    ,    ,   ,     ,  \
/__,___,____,____,____,____,____,____,___,_\
"""), None),
    "蓝山": (picture(r"""
           /\                 /\
          /^^\     /\        /^^\       /\
         /^^^^\   /^^\      /^^^^\     /^^\
    /\  /^^^^^^\ /^^^^\    /^^^^^^\   /^^^^\
   /^^\/^^^^^^^^V^^^^^^\  /^^^^^^^^\_/^^^^^^\
  /^^^^^^^^^^^^^^^^^^^^^\/^^^^^^^^^^^^^^^^^^^\
"""), "蓝"),
    # 据点: 幸存者用废铁、旧轮胎和沙袋重新围起来的堡垒和贸易站
    "卡尼堡": (picture(r"""
        |>
        |                 _______________
     ___|___             |  FORT KEARNY  |
    |  [=]  |            |_______________|
    |_______|_____________________|_|________
    | || || || || || || || || || || || || |
____|_||_||_||_||_||_||_||_||_||_||_||_||_|____
   (__)(__)(__)(__)(__)(__)(__)(__)(__)(__)
"""), None),
    "拉勒米堡": (picture(r"""
     ____                                     ____
    |[][]|___________________________________|[][]|
    |    |    F O R T   L A R A M I E        |    |
    |    |             .-------.             |    |
    |    |             |       |             |    |
 ___|____|_____________|       |_____________|____|___
"""), None),
    "布里杰堡": (picture(r"""
                     (  )
                      ()
          ____________||____________
         /                          \
        /        FORT BRIDGER        \
       |==============================|
       |  [_]    .------.     [_]     |   _[ ]_
 ______|_________|      |_____________|___|___|___
"""), None),
    "霍尔堡": (picture(r"""
     ___                                  ___
    /___\        F O R T   H A L L       /___\
    |[ ]|                                |[ ]|
    |   |^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^|   |
    |   ||||||||||||||| .---. ||||||||||||   |
 ___|___||||||||||||||| |   | ||||||||||||___|___
"""), None),
    "博伊西堡": (picture(r"""
         ________________________
        |   F O R T   B O I S E  |
     ___|________________________|___
    |  _      _      _      _       |
    | |_|    |_|    |_|    |_|      |
 ___|_______________________________|_______
  ~   ~~  ~   ~~~   ~  ~~   ~   ~~  ~  ~~~
 ~~  ~   ~~~  ~   ~~  ~   ~~~  ~   ~~  ~
"""), None),
    "达尔斯": (picture(r"""
  |\                                          /|
  ||\         T H E   D A L L E S            /||
  |||\     _____    _____                   /|||
  ||||\___|[] []|__|[] []|_________________/||||
  |||||    |    |  |    |                   ||||
 ~|||||~~~~~~~~~~~~~~~~~~~~~<=O==O==O==O=>~~||||~
  ~   ~~  ~   ~~~   ~  ~~   ~   ~~  ~  ~~~   ~
"""), None),
}

# 开进辐射热点时路边的警告牌
HOTSPOT_SIGN = picture(r"""
     ___________________________
    |  /!\    D A N G E R  /!\  |
    |    RADIATION   HAZARD     |
    |___________________________|
          ||               ||
   _______||_______________||_______
""")

# 有人去世时的墓碑
TOMBSTONE = picture(r"""
      .-----.
     /       \
    |  R.I.P  |
    |    +    |
    |         |
  __|_________|__
""")

# 结局: 到达俄勒冈城、带着种子到达 (隐藏结局)、全军覆没
CITY_ART = picture(r"""
                         |>
          ____         __|__         ____
   ______|[][]|_______|     |_______|[][]|______
  |      |    | OREGON|  _  | CITY  |    |      |
  |  []  |    |       | | | |       |    |  []  |
  |______|____|_______|_| |_|_______|____|______|
 ======================/   \======================
""")
FIELD_ART = picture(r"""
    \|/  \|/  \|/  \|/  \|/  \|/  \|/  \|/  \|/
     |    |    |    |    |    |    |    |    |
  ___|____|____|____|____|____|____|____|____|___
""")
WIPEOUT_ART = picture(r"""
            v           v
                  v
                            _________
                      _____/    |    \__        +     +
                     <________________o_|       |     |
                       (@)          (@)       __|__ __|__
 __________________________________________________________
""")

# 每个人的样子 (5 行, 不超过 11 个字宽): 主角按性别, 据点里的人按职业, 路上遇到的陌生人都是一个样子
PORTRAITS = {
    "男": picture(r"""
   ,,,,,
  ( o o )
   \ - /
  __|=|__
 /  | |  \
"""),
    "女": picture(r"""
   .~~~.
  ( o o )
  (\ - /)
  __|=|__
 /  | |  \
"""),
    "老兵": picture(r"""
   _____
  /_____\
  | # o |
   \ = /
 _/|*  |\_
"""),
    "医生": picture(r"""
   .-+-.
  /     \
 |(o)-(o)|
   \ - /
  /|+  |\
"""),
    "机械师": picture(r"""
  (O)-(O)
  /     \
  | o o |
   \ = /
 ]=|___|\
"""),
    "猎人": picture(r"""
   _.-._
  (#####)
  | o o |/
   \ - //
  /|  //|\
"""),
    "商人": picture(r"""
    ___
 __|___|__
   |o o|
   \_~_/
  /|$  |\
"""),
    "拾荒者": picture(r"""
   .---.
  ( O O )
  ( [#] )
   \___/
  /|===|\
"""),
    "陌生人": picture(r"""
   .---.
   |o o|
   |vvv|
   '---'
  /|   |\
"""),
}
PORTRAIT_WIDTH = 14   # 头像旁边写字的时候, 字从第几列开始 (每个人都一样, 字才对得齐)


def portrait_of(game, name):
    """这个人长什么样: 据点里的人按职业, 主角按性别, 路上遇到的陌生人都一样"""
    if name in game["jobs"]:
        return PORTRAITS[game["jobs"][name]]
    if name == game["leader"]:
        return PORTRAITS[game["gender"]]
    return PORTRAITS["陌生人"]


def text_width(text):
    """一段字在终端里占几格: 中文和全角的标点占两格, 英文、数字和空格占一格"""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def wrap_text(text, width):
    """把一段字切成好几行, 每行在终端里不超过 width 格"""
    lines = [""]
    used = 0   # 这一行已经占了几格
    for ch in text:
        size = text_width(ch)
        if used + size > width:
            lines.append("")
            used = 0
        lines[-1] += ch
        used += size
    return lines


def beside(art, words, color=None, width=None):
    """把画放在左边、字写在右边, 拼成一行一行。画只用英文字符, 所以每行的字都从同一列开始, 中文也对得齐。
    width 是字从第几列开始 (不填就是画的宽度再空 3 格); color 是画的颜色 (字不上色)"""
    width = width or max(len(line) for line in art) + 3
    rows = []
    for i in range(max(len(art), len(words))):
        left = art[i] if i < len(art) else ""
        right = words[i] if i < len(words) else ""
        if right:
            left = left.ljust(width)
        rows.append((colored(left, color) if left.strip() else left) + right)
    return rows


def show_picture(art, color=None, words=None):
    """显示一幅画, 一行一行地慢慢画出来; words 是写在画右边的字。只在能播动画的时候显示"""
    if not can_animate():
        return
    print()
    for row in beside(art, words or [], color):
        print(row)
        time.sleep(PICTURE_DELAY)


# ========== 开始界面 ==========

# 开始画面: 远处的蘑菇云和废墟, 路上一辆车。在主菜单等玩家选的时候, 它是一段一直循环的小动画:
# 车停在原地往右开, 路面和废墟往左退 (近处的快, 远处的慢); 蘑菇云离得远, 不跟着动, 云顶慢慢翻滚, 柱子里的烟尘往上冒。
# 每一层退的速度都配好了, 转一圈 TITLE_FRAMES 帧正好接上第一帧, 所以能无限循环
TITLE_FRAMES = 112
TITLE_HEIGHT = 14   # 开始画面加上标题和菜单一共 24 行, Mac 自带的终端默认就是 24 行高, 刚好放得下, 能播动画
TITLE_CLOUDS = [   # 云顶翻滚的几个样子, 轮流换 (第 4 个跟第 2 个一样, 来回翻)
    ["                        _.-~~~~~~~-._",
     "                    .-~~   .-~~~-.   ~~-.",
     "                   (     (         )     )",
     "                    `-._  `~~---~~'  _.-'",
     "                        `~~--. .--~~'"],
    ["                        _.-~~~~~~~-._",
     "                    .-~~    .-~~~-.  ~~-.",
     "                   (      (    ~    )    )",
     "                    `-._   `~~---~~' _.-'",
     "                        `~~--. .--~~'"],
    ["                       _.-~~~~~~~~~-._",
     "                    .-~~  .-~~~~~-.   ~-.",
     "                   (    (     ~~    )     )",
     "                    `-._ `~~-----~~'  _.-'",
     "                        `~~--. .--~~'"],
]
TITLE_CLOUD_ORDER = [0, 1, 2, 1]   # 每 7 帧换一个样子
TITLE_SMOKE = ["'", " ", ".", " "]  # 柱子里往上冒的烟尘
TITLE_RUINS = [   # 远处的废墟, 一长条 56 格, 会循环
    "       __        ___                     __     _      ",
    "      |  |___   |   |   _          ____ |  |___| |     ",
    "   ___|  |   |__|   |__| |_________|    ||  |   | |___ ",
]
TITLE_CAR = [
    "        ____",
    "    ___/_[]_\\____",
    "   |o            o|>",
]
TITLE_ROAD = "=  ==  =   =  ==   =  =   = "    # 路面, 28 格, 不规则 (见 SCENE_ROAD 的说明)
TITLE_PEBBLES = "  .        ,      .     '    "  # 路边的小石子, 跟路面一样快
TITLE_WHEELS = ["(|)", "(/)", "(-)", "(\\)"]       # 转动的轮子
TITLE_DUST = [".o ", " o.", "o .", ". o"]          # 车尾扬起的尘土


def title_frame(frame):
    """主菜单动画的第 frame 帧 (TITLE_HEIGHT 行)"""
    frame %= TITLE_FRAMES
    canvas = [[[" ", None] for _ in range(SCENE_WIDTH)] for _ in range(TITLE_HEIGHT)]
    wing = "v" if frame // 4 % 2 == 0 else "-"           # 天上的秃鹫扇翅膀
    draw(canvas, 0, 7, wing, "灰")
    draw(canvas, 1, 50, wing, "灰")
    cloud = TITLE_CLOUDS[TITLE_CLOUD_ORDER[frame // 7 % len(TITLE_CLOUD_ORDER)]]
    for y, line in enumerate(cloud):
        draw(canvas, y, 0, line, "灰")
    for y in range(5, 9):                                  # 蘑菇云的柱子, 烟尘一帧一帧往上冒
        smoke = TITLE_SMOKE[(y + frame // 2) % len(TITLE_SMOKE)]
        draw(canvas, y, 29, "|" + smoke + "|", "灰", solid=True)
    for y, line in enumerate(TITLE_RUINS):                 # 废墟在柱子前面, 两帧退一格
        draw(canvas, 6 + y, 0, scene_slice(line, frame // 2)[:56], "灰")
    draw(canvas, 9, 2, "_" * 52, "灰")                     # 地平线
    draw(canvas, 12, 0, scene_slice(TITLE_PEBBLES, frame * 2)[:56], "灰")
    draw(canvas, 13, 1, scene_slice(TITLE_ROAD, frame * 2)[:55], "灰")   # 路面一帧退两格
    for y, line in enumerate(TITLE_CAR):
        draw(canvas, 10 + y, 0, line, "灰", solid=True)
    wheel = TITLE_WHEELS[frame % len(TITLE_WHEELS)]
    draw(canvas, 13, 3, wheel, "灰", solid=True)
    draw(canvas, 13, 16, wheel, "灰", solid=True)
    draw(canvas, 12, 0, TITLE_DUST[frame % len(TITLE_DUST)], "灰")
    return canvas_lines(canvas)


def title_screen():
    """开始画面。返回从画面的第一行到这里一共印了几行 (主菜单的动画要知道往上数几行)"""
    print()
    for row in title_frame(0):
        print(row)
    if can_animate():
        show_title_loop([title_frame(frame) for frame in range(TITLE_FRAMES)], TITLE_HEIGHT)
    print()
    print(colored("                     废  土  之  旅", "绿", bold=True))
    print(f"              W A S T E L A N D   T R A I L   {VERSION}")
    return TITLE_HEIGHT + 3


def show_title_loop(frames, height):
    """把一圈动画交给能自己播的地方 (网页版用, 见 run_in_browser.py)。终端里不用它, 终端是等按键时一帧一帧地画 (title_animation)"""


def title_animation(lines_up):
    """主菜单等按键时, 每次调用就把开始画面换成下一帧。lines_up 是从现在光标所在的行往上数几行是画面的第一行。
    终端太小 (画面放不下) 或者不能播动画时返回 None, 画面就不动"""
    size = shutil.get_terminal_size((0, 0))
    if not can_animate() or IN_BROWSER or size.lines <= lines_up or size.columns <= SCENE_WIDTH:
        return None
    frames = [title_frame(frame) for frame in range(TITLE_FRAMES)]
    counter = [0]

    def next_frame():
        counter[0] = (counter[0] + 1) % TITLE_FRAMES
        # 记住光标的位置 (\x1b7), 藏起光标, 往上移到画面的第一行, 一行一行盖掉, 再回到原来的位置 (\x1b8), 显示光标
        print("\x1b7\x1b[?25l" + f"\x1b[{lines_up}A\r" + "\n".join(frames[counter[0]]) + "\x1b8\x1b[?25h",
              end="", flush=True)
    return next_frame


def show_help():
    """主菜单里的「游戏说明」"""
    miles = round(TOTAL_DISTANCE * UNITS["英里"])
    capacity_kg = CAR_CAPACITY // 1000
    capacity_lb = round(capacity_kg * WEIGHT_UNITS["英里"][1])
    difficulties = "、".join(f"{name} {money} 块钱" for name, money, *_ in DIFFICULTIES.values())
    scores = "、".join(f"{name} ×{score / 100:g}" for name, _, _, _, score, _ in DIFFICULTIES.values())
    print(f"""
========== 游戏说明 ==========
你被赶出了密苏里州独立城地下的避难所, 要开车沿着当年拓荒者走过的俄勒冈小道,
去 {TOTAL_DISTANCE} 公里 ({miles} 英里) 外的{DESTINATION}。只要还有人活着走到, 就算成功。

开局先选难度 ({difficulties}): 越难, 一开始的钱越少, 路上出事、生病的机会越多。

每天可以选一件事做:
  继续前进  开车赶路, 要用燃料。开得越快越费燃料, 人也越累。
            车会像原版那样一直往前开, 路上出了事会说一声, 看完接着开; 到了地方就停下来。
            想停下来休息、用药、看看情况, 就按回车 (网页版点一下屏幕)
  休息一天  躲在车里养伤养病, 不怕风吹雨打
  搜刮废墟  也许能找到物资, 也可能碰上危险
  打猎      屏幕上出现英文词就飞快打出来, 越快肉越多 (记得先切换成英文输入法)
  用药      药品治病治伤, 排辐剂排辐射, 自己选给谁用
  还可以改变口粮和速度、查看队伍、看旅行日记、存档。这几样不花时间
""")
    new_screen()   # 一页放不下, 分成三页
    print(f"""
路上要注意:
  - 每人每天都要吃要喝。天热要多喝水, 天冷要多吃东西, 还得每人一套冬衣
  - 车最多装 {capacity_kg} 公斤 ({capacity_lb} 磅), 人也算在里面, 装不下就拿不了。燃料最重, 要算好在哪里补给
  - 天气按走到哪里、几月份变。坏天气车开得慢, 酸雨和辐射风暴天最好躲在车里
  - 辐射会在身体里越积越多, 只有排辐剂能排掉
  - 有 {len(HOTSPOTS)} 段路靠近核设施, 辐射偏高 (状态栏会提前提醒)。在那里的每一天都要多受辐射,
    躲在车里能少受一些, 开快一点能少待几天
  - 健康越差越容易生病。生病了要休息, 或者用药品治
  - 路上要过 5 条大河。水浅可以直接开过去, 水深了就绑上空油桶浮过去 (可能翻车),
    有的河边有渡船, 花钱最安全。春天化雪、刚下过雨, 河水都会涨, 等几天水也许会退
  - 路上的据点能买东西, 也能把用不上的东西卖掉换钱 (只给一半的价钱); 每个据点还有一个人愿意跟你走
  - 到了达尔斯, 最后一段路可以扎木筏顺着哥伦比亚河漂下去 (要躲急流里的礁石), 也可以交过路费走巴洛路
  - 带上队友更安全; 一个人走省吃省喝, 可生病了没人照顾
  - 3 月出发天冷, 7 月出发天热, 4~6 月最好走
""")
    new_screen()
    print(f"""
走到{DESTINATION}才算分: 活下来的人越多、越健康分越高, 剩下的物资和钱也能换成分。
最后再按难度乘一下: {scores}。主菜单的「最高分」里记着前 {HIGH_SCORES} 名。

游戏有音乐。不想听: 网页版点右上角的「♪」; 在电脑上玩, 把游戏文件开头「游戏设置」里的 MUSIC 改成 False。

在电脑的终端里玩, 窗口够大的时候 (拉大到 101 列、28 行以上), 每天的菜单和开车的画面
会变成一个分成几块的大画面: 动画、状态、路线图、最近发生的事都在一起。网页版本来就有这些面板。
""")
    wait_enter("按回车回到主菜单……")


# ========== 主菜单和主循环 ==========

def main():
    """主菜单: 开始新游戏、继续游戏、看说明, 或者退出。一局玩完会回到这里"""
    enable_ansi()   # 颜色和动画都要用控制字符, Windows 的终端要先打开这个开关
    screen["unread"] = False   # 刚打开游戏, 屏幕上还没有要看的字
    while True:
        new_screen()
        play_music("主菜单")
        height = title_screen()
        saved = load_game()
        if saved:
            note = (f"{DIFFICULTIES[saved['difficulty']][0]}, {date_text(saved)}, "
                    f"已走 {show_distance(saved, saved['distance'])}")
        else:
            note = "没有存档"
        menu = f"\n1. 开始新游戏\n2. 继续游戏 ({note})\n3. 游戏说明\n4. 最高分\n5. 退出游戏"
        print(menu)
        choice = ask_number("选哪一项? ", 1, 5, idle=title_animation(height + menu.count("\n") + 1))
        if choice == 1:
            if saved:
                print("\n已经有一个存档了, 开始新游戏会把它删掉。")
                if ask_number("1. 确定, 开始新游戏  2. 回到主菜单  ", 1, 2) == 2:
                    continue
                delete_save()
            game = new_game()
            setup(game)
            play(game)
        elif choice == 2:
            if saved:
                play(saved)
            else:
                print("\n还没有存档, 先开始一局新游戏吧。")
                wait_enter("按回车回到主菜单……")
        elif choice == 3:
            new_screen()
            show_help()
        elif choice == 4:
            new_screen()
            show_high_scores()
            wait_enter("按回车回到主菜单……")
        else:
            stop_music()
            print("\n下次再见!")
            return


def play(game):
    """玩一局, 直到走到终点、全军覆没, 或者存档后回到主菜单"""
    actions = {1: travel, 2: rest, 3: scavenge, 4: hunt, 5: take_medicine,
               6: change_ration, 7: change_pace, 8: show_party, 9: show_diary}
    ending = None   # 走到终点时是哪个结局 (全军覆没就没有, 也不算分)
    play_music("赶路")

    while True:
        if not game["party"]:
            new_screen()
            play_music("全军覆没")
            show_picture(WIPEOUT_ART, "灰")
            print("\n" + title("结局: 全军覆没", "红"))
            print("所有人都死了。废土上又多了一辆空车……")
            break
        if game["distance"] >= TOTAL_DISTANCE:
            ending = arrive(game)
            break

        new_screen()   # 每天的菜单是一个画面: 上面是状态 (窗口够大就用大画面), 下面是选项
        if GUI:
            show_scene(game)
        elif use_dashboard():
            show_dashboard(game)
        else:
            show_status(game)
        print("1. 继续前进  2. 休息一天  3. 搜刮废墟  4. 打猎  5. 用药")
        print("6. 改变口粮  7. 改变速度  8. 查看队伍  9. 旅行日记  10. 存档")
        choice = ask_number("你要做什么? ", 1, 10)
        if choice == 10:
            save_game(game)
            if ask_number("1. 继续玩  2. 回到主菜单  ", 1, 2) == 2:
                return
            continue
        new_screen()   # 做的事换一个画面
        actions[choice](game)

    delete_save()
    new_screen()   # 看完结局, 再看一遍旅行日记, 最后算分
    show_diary(game)
    if ending:
        new_screen()
        record_score(game, ending)
    print("\n====== 游戏结束 ======")
    wait_enter("按回车回到主菜单……")


if __name__ == "__main__":
    try:
        main()
    except (EOFError, KeyboardInterrupt):
        print("\n\n游戏中途退出了, 下次再见!")
