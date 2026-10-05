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
ACHIEVEMENT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "achievements.json")   # 拿到过的成就
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")   # 主菜单「设置」里改的

# ========== 游戏设置(数字都可以随便改) ==========

VERSION = "v4.2"   # 版本号, 显示在开始界面上。发布新版本时要跟着改

# 路线是当年的俄勒冈小道: 从密苏里州独立城到俄勒冈城。
# 距离按 1847 年乔尔·帕尔默的拓荒指南里的路程表算 (经过布里杰堡的那条线)
START_PLACE = "独立城"      # 出发的地方 (避难所就在独立城地下)
DESTINATION = "俄勒冈城"
TOTAL_DISTANCE = 3119   # 到俄勒冈城的总路程(公里)

# 难度 (开局时玩家选): 编号 -> (名字, 一开始有多少钱, 路上出事的机会是平时的百分之几, 生病的机会是平时的百分之几,
#                              得分是百分之几, 说明)
# 「普通」就是没有难度选择以前的样子。跟原版一样, 越难得分越高
# 目标 (用户 2026-10-04 定的): 简单 —— 第一次玩的人基本都能到; 普通 —— 第一次玩的人大概一半能到, 玩熟了的人大多能到;
# 困难 —— 玩熟了的人也常常失败。改了数字要用 tests/balance.py 量一量 (会规划的玩家 = 玩熟了的人, 「新手」= 第一次玩的人)
DIFFICULTIES = {
    1: ("简单", 900, 40, 40, 50, "出事、生病少很多, 过河翻车也不会被冲走"),
    2: ("普通", 500, 100, 100, 100, "钱刚刚够用, 要精打细算"),
    3: ("困难", 370, 140, 140, 150, "钱很紧, 路上出事、生病都多不少"),
}
# 主菜单的「设置」(难度、距离单位、音乐、过场动画) 没改过的时候是什么样。改了会存进 SETTINGS_FILE, 下次打开游戏还是那样
DEFAULT_SETTINGS = {"difficulty": 2, "unit": "公里", "music": True, "animation": True, "window": True}
# 在这些难度里, 过河翻车、坐木筏撞上礁石都不会有人被冲走 (第一次玩的人常常在一开始还只有自己一个人的时候,
# 在头两条河就被冲走了, 一局一下子就结束, 太狠了)
NO_DROWNING = [1]

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
OUTPOST_NAMES = [name for name, _ in OUTPOSTS.values()]   # 据点的名字 (从上面算出来的, 不用改)
# 背景故事: 从这个据点往西, 一直到俄勒冈城, 都是美国政府的地盘 (以政府战时躲进去的夏延山为界)。
# 这些据点是政府重新占领的基地, 驻着政府的人; 往东的据点还是幸存者自己围起来的堡垒
GOVERNMENT_FROM = "拉勒米堡"
GOVERNMENT_BASES = OUTPOST_NAMES[OUTPOST_NAMES.index(GOVERNMENT_FROM):]   # 政府的基地 (从上面算出来的, 不用改)
GOVERNMENT_KM = next(km for km, (name, _) in OUTPOSTS.items() if name == GOVERNMENT_FROM)   # 政府的地盘从几公里开始
# 每个政府基地都不一样 (画在 PICTURES 里): 到了的时候说一句
BASE_NOTES = {
    "拉勒米堡": "政府地盘的第一道检查站。路口拉着铁丝网, 进出的车都要停下来让士兵看一看。",
    "布里杰堡": "这里是政府车队的修车场, 院子里停满了卡车, 修车、加油都在这里。",
    "霍尔堡": "基地里竖着高高的无线电塔, 空地上停着一架直升机。废土上能飞的东西, 只有政府有。",
    "博伊西堡": "基地守着蛇河边的抽水站, 把河水抽上来一遍遍地过滤, 供给政府的人。",
    "达尔斯": "哥伦比亚河边的码头, 政府的巡逻船在河上来来回回。",
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

# ---------- 萨布莱特捷径 ----------

# 1844 年开通的真实近路: 过了南山口可以选, 一路往西直奔格林河, 再翻山回到大路上, 整个绕开布里杰堡
# (那里的商店和愿意跟你走的人都见不到了)。一共少走大约 85 英里 (137 公里), 可是到格林河以前有大约 45 英里 (72 公里) 找不到水
CUTOFF_FROM = "南山口"
CUTOFF_SKIPS = "布里杰堡"
CUTOFF_DRY_UNTIL = "格林河"   # 从南山口到这里, 路边一点水都找不到
CUTOFF_SAVES = 137            # 少走几公里 (开到布里杰堡那么远的时候, 一下子算进去: 翻过山回到了大路上)
CUTOFF_DRY = 72               # 找不到水的路有多长 (公里, 只在说明里用)
DRY_WATER = 2                 # 走在找不到水的路上, 每人每天多喝几份水 (又干又晒)
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
# 成就: 名字 -> 怎么拿到 (写给玩家看的, 什么时候算拿到写在 unlock 用到的地方)。拿到过的记在 ACHIEVEMENT_FILE 里, 一直留着
ACHIEVEMENTS = {
    "终于到了": "第一次走到俄勒冈城",
    "一个都不少": "带上的人全都活着到了 (完美结局)",
    "独行侠": "从头到尾一个人走完全程 (独行结局)",
    "绿色的希望": "把种子库的种子带到终点 (隐藏结局)",
    "硬骨头": "在困难难度下走到俄勒冈城",
    "快马加鞭": "40 天以内走到俄勒冈城",
    "自己过河": "一次渡船都不坐, 走到俄勒冈城",
    "抄近路": "走萨布莱特捷径, 走到俄勒冈城",
    "满员": "车上坐满 4 个人",
    "远离辐射": "三段辐射热点都绕过去",
    "神枪手": "一次打猎打到 3 只以上",
    "激流勇进": "坐木筏过 4 段急流, 一次礁石都没撞上",
    "前车之鉴": "第一次全军覆没",
}
FAST_ARRIVAL_DAYS = 40   # 「快马加鞭」: 几天以内走到

# 商店价格(每个多少钱)
PRICES = {"食物": 1, "水": 1, "燃料": 4, "子弹": 1, "零件": 20, "药品": 15, "冬衣": 10, "排辐剂": 20}
# 越往西东西越贵 (照原版: 起点的东西最便宜, 每往西一个堡垒就贵一些): 据点 -> 是独立城价钱的百分之几
OUTPOST_PRICES = {"卡尼堡": 115, "拉勒米堡": 130, "布里杰堡": 145, "霍尔堡": 160, "博伊西堡": 175, "达尔斯": 190}
# 在据点卖东西: 据点的人只给独立城价钱的百分之几 (有商人帮着讲价能多拿一些)。零头不算。
# 不管在哪个据点卖都一样 (不跟着越往西越贵), 不然在东边买、到西边卖就能赚钱
SELL_SHARE = 50
MERCHANT_SELL_SHARE = 60
# 每种物资怎么数 (5 份食物、30 发子弹、1 套冬衣……)
MEASURES = {"食物": "份", "水": "份", "燃料": "份", "子弹": "发", "零件": "个", "药品": "份", "冬衣": "套", "排辐剂": "支"}

# ---------- 交易 ----------

# 照原版的「Attempt to trade」: 每天的菜单里选「交易」, 花一天找人换东西; 路上碰到的流浪商人也是这样换。
# 对方拿出一样东西 (随机的), 换你车上的另一样。换不换自己定
TRADE_CHANCE = 0.6       # 在路上等一天, 碰到愿意换东西的人的机会 (停在据点里人多, 一定碰得到)
# 对方一次拿出来换的东西: 物资 -> (最少几个, 最多几个)
TRADE_LOTS = {"食物": (20, 40), "水": (20, 40), "燃料": (5, 12), "子弹": (20, 40),
              "零件": (1, 2), "药品": (1, 2), "冬衣": (1, 2), "排辐剂": (1, 1)}
# 对方要你的东西, 按商店的价钱算, 值他拿出来的东西的百分之几 (最少, 最多): 有时划算, 有时吃亏
TRADE_ASK = (70, 140)
MERCHANT_TRADE_ASK = 80  # 有商人帮着讲价, 对方只要原来的八成
# 来换东西的人
TRADERS = ["一个推着生锈购物车的老太太", "一个骑着破摩托车的年轻人", "一队从西边回来的拾荒者",
           "一个背着大包的流浪商人", "一个独眼的老猎人", "一个赶着几头瘦牛的农夫"]

# ---------- 和人说话 ----------

# 照原版的「Talk to people」: 车停在一个地方 (起点、地标、据点、河边、辐射热点) 的时候, 可以跟那里的人聊几句,
# 听听前面的路况、天气、河有多深。跟世界设定、剧情有关的话, 等背景故事定了再写
OUTPOST_TALKERS = ["一个在据点门口晒太阳的老人", "据点里修车的师傅", "一个刚从西边回来的拾荒者",
                   "据点里摆地摊的小贩", "守在墙头上的哨兵"]
ROAD_TALKERS = ["在这里歇脚的一个旅人", "一个往东走的拾荒者", "一个赶着几头瘦牛的农夫", "在这里扎营的一家人"]
# 出发的独立城是拾荒者聚居的地方; 拉勒米堡往西的据点是政府的基地
START_TALKERS = ["独立城集市上摆摊的拾荒者", "一个刚从西边回来的拾荒者", "在独立城歇脚的一个旅人"]
BASE_TALKERS = ["基地门口站岗的士兵", "基地里修车的师傅", "一个刚从西边回来的拾荒者",
                "基地里摆地摊的小贩", "一个在基地门口晒太阳的老人"]
# 跟故事有关的话 (每个地方的人会说其中两句): 出发的独立城 / 政府地盘以东 / 政府的地盘里。
# 主角不知道俄勒冈城是政府的后备据点, 所以谁都不说破这一点
STORY_TALK = {
    "独立城": [
        "往俄勒冈去? 那边有官方的人在收人, 这话我也听过。要我说, 多半是骗人的。",
        "二十年前那一天, 天上全是核弹的白烟。等我从地底下爬出来, 城已经没了。",
        "往西过了堪萨斯, 就要沿着普拉特河走了。河边那条老铁路, 现在归铁道组织管。",
        "能开的车可不好找。你那辆车没怎么坏, 算你走运。",
    ],
    "东边": [
        "这一带沿着铁路的地方, 都归铁道组织管。废土上还能跑的火车, 都在他们手里。",
        "再往西走到拉勒米堡, 就是政府的地盘了。那边的据点, 都有政府的人守着。",
        "政府? 听说他们打仗以前就躲进了山里的基地, 一根汗毛都没伤着。",
        "车能开的人没几个, 走远路的, 大多是搭铁道组织的火车。",
    ],
    "政府": [
        "政府的人手少得很, 能干活的, 他们都欢迎。往西走的人, 多半是去找活干的。",
        "政府也想把东边的地方收回来, 可人太少, 又没有那么多吃的、用的, 打不过去。",
        "辐射偏高的那几段路, 就算在政府的地盘里, 也没人管。要过只能自己硬闯。",
        "这一路上的据点, 以前都是幸存者的, 后来政府的人来了, 就成了他们的基地。",
    ],
}
# 过来人的提醒 (每个地方的人会说其中两句)
TALK_TIPS = [
    "下过雨雪, 河水会涨; 在河边等几天, 水也许就退下去了。",
    "酸雨和辐射风暴的天气, 最好躲在车里, 别在外面淋着。",
    "干净的水一定要带够。路边的水看着清, 喝下去说不定就是霍乱。",
    "车太重的话, 把用不上的东西扔了吧, 给有用的东西腾地方。",
    "人越虚越容易生病。吃饱一点, 累了就歇一歇, 别硬撑。",
    "夜里睡觉要留个人守着, 这一带小偷多。",
    "旧公路的路牌早就倒光了, 认不清路的时候, 就看着太阳往西走。",
    "开得太快, 人颠得受不了, 也更费燃料。",
    "越往西, 据点里的东西越贵。能在东边买的, 就早点买。",
]

# ---------- 休息 ----------

MAX_REST_DAYS = 9   # 选「休息」一次最多休息几天
REST_HEALTH = 8     # 躲在车里休息, 每天多恢复几点健康

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

# 每开 100 公里, 遇到随机事件 (EVENTS 里的大事) 的机会
EVENT_CHANCE_PER_100KM = 0.35
# 没遇到大事的话, 每开 100 公里遇到小事 (SMALL_EVENTS 里的) 的机会。小事跟大事分开算, 加了小事, 大事也不会变少
SMALL_EVENT_CHANCE_PER_100KM = 0.15
# 几种小事的数字 (照原版《俄勒冈之旅》的迷路、着火、小偷、找到野果、废弃的马车、路难走, 做成废土版)
LOST_DAYS = (1, 2)          # 迷路白白耗掉几天 (最少, 最多); 队伍里有猎人认得路, 只耽误 1 天
FIRE_BURN = (10, 30)        # 车着火, 烧着的那样东西烧掉百分之几 (最少, 最多); 有机械师扑火, 只烧掉一半那么多
THEFT = (10, 30)            # 夜里的小偷偷走某样东西的百分之几 (最少, 最多); 有老兵守夜就偷不走
WILD_FOOD = (10, 30)        # 废弃农场里挖到几份能吃的
SPRING_WATER = (20, 40)     # 干净的泉水能装几份
ROUGH_ROAD_BREAK = 0.4      # 烂路上硬冲过去, 把车颠坏的机会
SNAKE_BITE = (15, 25)       # 被变异响尾蛇咬了掉多少健康 (最少, 最多)

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
# 开到辐射热点跟前可以选: 直接开过去 (快, 可是在那一带每天都要多受辐射), 还是绕路 (那一带的辐射就不用受了)。
# 绕路要多开这么多公里: 中速大约多花 1 天 (慢速 2 天), 多吃多喝, 也多用燃料。
# 试过 220 公里 (大约 2 天): 三段都绕的老手到达率从 95% 掉到 72%, 太亏了, 没人会选
DETOUR_KM = 100

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

# 车没燃料的时候去搜刮废墟, 会专门到路边的废车里抽油: 一次能抽到几份燃料 (最少, 最多); 有拾荒者多一半
SIPHON_FUEL = (1, 3)
SIPHON_EMPTY = 0.4   # 翻了好几辆废车, 油箱都是空的的机会 (没碰上野狗的时候; 有拾荒者就不会空手)
# 搜刮时可能找到的东西: 名字 -> (最少, 最多)
LOOT = {"食物": (10, 40), "水": (10, 30), "燃料": (3, 10),
        "子弹": (10, 30), "零件": (1, 1), "药品": (1, 2), "冬衣": (1, 2), "排辐剂": (1, 1)}

# 打猎的猎物: 名字 -> (最少食物, 最多食物)
ANIMALS = {"变异野兔": (10, 25), "双头鹿": (30, 60), "辐射野猪": (50, 90)}
# 打猎小游戏 (照原版: 动物在原野上跑来跑去, 移动准星瞄准开枪)。在电脑的终端里用方向键和空格, 网页版用鼠标或手指点
HUNT_GAME = True        # 改成 False 就是以前那种「看到英文词飞快打出来」的打猎
HUNT_FRAMES = 150       # 一次打猎有几帧 (每帧 HUNT_DELAY 秒, 150 帧大约 15 秒)
HUNT_DELAY = 0.1
HUNT_HEIGHT = 12        # 原野有几行 (宽跟动画一样, SCENE_WIDTH 格)
HUNT_MAX_ANIMALS = 2    # 原野上最多同时有几只动物
HUNT_SPAWN = 0.025      # 动物不到最多的时候, 每一帧跑进来一只新动物的机会
HUNT_STEP = 2           # 按一下左右方向键, 准星横着移几格 (上下方向键移一行)
# 每种动物: 名字 -> (每帧最少跑几格, 最多跑几格, 跑进来的机会有多大)
HUNT_ANIMALS = {"变异野兔": (0.9, 1.3, 45), "双头鹿": (0.6, 0.85, 35), "辐射野猪": (0.35, 0.5, 20)}
# 没打中, 枪声把附近 (这么多格以内) 的动物吓得跑快一些 (快这么多倍)
HUNT_SCARE_RANGE = 10
HUNT_SCARE_SPEED = 1.6
# 以前的打猎 (网页还是旧版、或者跑测试的时候用): 要飞快打出来的词
HUNT_WORDS = ["bang", "pow", "boom", "zap"]

# 过场动画和画面: 赶路 (跟着天气变)、过河、坐木筏的动画, 还有地标、据点、墓碑、结局的画和每个人的样子。
# 只在真正的终端里和网页版里有 (跑测试时没有)
ANIMATION = True          # 改成 False 就完全不放动画 (玩的人在主菜单的「设置」里也能关)
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
# 终端里的方框: 电脑的终端窗口够大的时候 (放得下大画面), 每个画面都摆在窗口正中间一块 DASHBOARD_WIDTH 宽的地方;
# 普通的画面外面画一个方框, 字写在方框正中间 FRAME_PAGE 格宽的地方 (大画面自己就有方框)。不会再挤在窗口的左上角。
# 只在 Mac 和 Linux 的终端里用 (Windows 的终端还没试过)
FRAME = True              # 不想要就改成 False
FRAME_ROWS = 30           # 这一块最高几行 (窗口更高也只用这么多, 上下也摆在中间)
FRAME_PAGE = 80           # 普通的画面一行最多写几格 (游戏的画面都是按 80 列的终端排的)
# 一打开游戏, 窗口太小 (放不下这一块) 就把终端窗口调大到这么大 (Mac 自带的终端、Linux 的大多数终端认得)。
# 窗口比这个大就不动它 (玩的人可能开着全屏, 按 Command 和加号把字放大就能占满)。玩的人在主菜单的「设置」里可以关掉
WINDOW_COLUMNS = DASHBOARD_WIDTH + 2
WINDOW_ROWS = FRAME_ROWS + 1   # 最下面空一行, 退出游戏以后终端接着写字的时候不会盖到方框
# 网页版的图形界面: 按钮、状态面板、地图、旅行日记都由网页来画, 游戏只要告诉网页现在的状态 (gui_update) 和在问什么。
# 这时候游戏自己就不画状态栏和大画面了。由 web/run_in_browser.py 打开, 在电脑上玩一直是 False
GUI = False
DIARY_PAGE = 10           # 换画面的时候, 旅行日记一页放几条 (一条常常要占两行)
PARTY_PAGE = 2            # 换画面的时候, 查看队伍一页放几个人 (每个人都有头像, 要占好几行)
EVENT_ROOM = 12           # 一直往前开的时候, 动画下面还剩这么多行, 路上的事才写在动画下面 (一件事大概 10 行); 不够就换一个新画面
DRIVE_DAY_FRAMES = 20     # 一直往前开的时候, 动画播几帧算过了一天 (每帧 ANIMATION_DELAY 秒, 20 帧大约 1.2 秒)
WARN_WEATHER = ["酸雨", "辐射风暴", "辐射沙尘暴"]   # 一直往前开的时候, 天气变成这几种要提醒一下 (在外面伤人, 也许该停下来躲进车里)

# 音乐: 用代码做的老式游戏机音乐, 放在 music 文件夹里 (做音乐的程序是 music/make_music.py, 想改曲子就改它)。
# 只在真正的终端里和网页版里放 (跑测试时不放)。网页版上还有一个「♪」按钮可以关掉
MUSIC = True              # 改成 False 就完全不放音乐 (玩的人在主菜单的「设置」里也能关)
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

# 据点里的人加入时自带的口粮 (只帮带队友的人, 一个人走还是很难)
RECRUIT_BRINGS = {"食物": 100, "水": 80}

# 职业的特长: 只要这个人还活着、在队伍里, 特长就一直有用
SKILLS = {
    "老兵": "遇到劫匪开枪一定能打赢, 赶走野狗只要 5 发子弹; 夜里守夜, 小偷偷不走东西",
    "医生": "用药一次能恢复 60 点健康 (平时是 35); 有医生照顾, 别人生病受伤好得更快; 被蛇咬了不会感染",
    "机械师": "车坏了不用零件也能当场修好; 过河时给车接上通气管, 车能开过更深的水; 车着火能很快扑灭",
    "猎人": "打猎得到的肉多一半; 认得路, 迷路只耽误一天",
    "商人": "在据点买东西打八折, 卖东西能卖到六成的价钱 (平时只有一半); 跟人交易时对方少要两成",
    "拾荒者": "搜刮废墟一定有收获, 一次能找到两样东西",
}

# 路上可能遇到的陌生人
STRANGER_NAMES = ["迈克", "安娜", "老乔", "凯特", "比尔"]


# ========== 小工具 ==========

# 是不是在网页版里 (网页里的 Python 叫 Pyodide, 它的 sys.platform 是 "emscripten")
IN_BROWSER = sys.platform == "emscripten"
HUNT_IN_BROWSER = False   # 网页认不认得打猎时的点击 (run_in_browser.py 会改成 True; 浏览器里还是旧版的 worker.js 时不认得)

# 屏幕上的字: unread 是有没有玩家还没看过的新消息 (换画面前要先等玩家看完);
# driving 是车是不是正在一直往前开 (这时候例行消息不印出来, 动画下面的状态栏都看得到);
# room 是开车的时候, 动画 (或者大画面) 下面还有没有地方写路上发生的事; frame 是车开到动画的第几帧 (停下来以后画面接得上)
# log 是清屏以后印过的字 (还没挪进方框的样子): 窗口大小变了, 就清屏按新的大小再印一遍 (见 refit_screen);
# logging 是要不要记 (只在电脑真正的终端里记, 跑测试时不记); framed 是这个画面要不要方框
screen = {"unread": False, "driving": False, "room": True, "frame": 0, "log": [], "logging": False, "framed": True}

# 终端里的方框 (见 FRAME): on 是现在用不用; framed 是这个画面外面有没有方框 (大画面自己有方框, 不用再画);
# left、top 是这一块的左上角在窗口里往右、往下挪了几格; height 是这一块有几行 (宽是 DASHBOARD_WIDTH);
# column 是光标现在在这一行写到了第几格 (None 是不知道, 比如玩家刚打完字按了回车, 光标回到了窗口最左边);
# saved 是控制字符 \x1b7 记住光标的时候, 光标在第几格; size 是清屏的时候窗口有多大 (列, 行), 变了就要重新画
layout = {"on": False, "framed": False, "left": 0, "top": 0, "height": FRAME_ROWS, "column": None, "saved": None,
          "size": None}
LAYOUT_CODES = re.compile(r"(\x1b\[[\d;?]*[A-Za-z]|\x1b[78])")   # 控制字符: 光标怎么动、什么颜色……


def can_frame():
    """能不能用终端里的方框: 设置里没关掉、能换画面, 在 Mac 或 Linux 真正的终端里 (跑测试时不用), 窗口放得下大画面"""
    if not (FRAME and can_clear_screen() and can_read_keys()) or IN_BROWSER or GUI or msvcrt:
        return False
    columns, rows = screen_size()
    return columns > DASHBOARD_WIDTH and rows >= DASHBOARD_ROWS


def start_layout(framed):
    """清屏以后用: 算好这一块摆在窗口的哪里 (窗口可能拉大拉小了)。返回要印的控制字符: framed 的话画上方框,
    再把光标挪到写字的地方 (\x1b[行;列H 是把光标挪到第几行第几格)"""
    layout["on"] = can_frame()
    if not layout["on"]:
        return ""
    columns, rows = screen_size()
    height = min(rows - 1, FRAME_ROWS)
    layout.update(framed=framed, height=height, column=0, saved=None,
                  left=(columns - DASHBOARD_WIDTH) // 2, top=(rows - 1 - height) // 2)
    top, left = layout["top"], layout["left"]
    text = ""
    if framed:
        words = f"-- {colored('废土之旅', '黄', bold=True)} "
        rows = ["+" + words + "-" * (DASHBOARD_WIDTH - 2 - visible_width(words)) + "+"]
        rows += ["|" + " " * (DASHBOARD_WIDTH - 2) + "|"] * (height - 2)
        rows += ["+" + "-" * (DASHBOARD_WIDTH - 2) + "+"]
        text = "".join(f"\x1b[{top + 1 + i};{left + 1}H{row}" for i, row in enumerate(rows))
    return text + f"\x1b[{top + (2 if framed else 1)};{page_start()}H"


def page_start():
    """这一块里每一行从窗口的第几格写起 (有方框的话, 字写在方框正中间)"""
    return layout["left"] + 1 + ((DASHBOARD_WIDTH - FRAME_PAGE) // 2 if layout["framed"] else 0)


def place_text(text):
    """终端里用方框的时候, 把要印的字挪进这一块里 (不用方框就原样返回):
    每一行都从这一块的左边写起 (\x1b[NG 是把光标挪到这一行的第 N 格); 太长的行折下来, 不会盖掉方框右边的边;
    回到左上角 (\x1b[H) 是回到这一块的左上角; 有方框的时候, 擦掉一行剩下的字 (\x1b[K) 以后把右边的边补上,
    也不擦下面的字 (\x1b[J, 会连方框一起擦掉)"""
    if not layout["on"]:
        return text
    framed = layout["framed"]
    width = FRAME_PAGE if framed else DASHBOARD_WIDTH   # 一行最多写几格
    to_start = f"\x1b[{page_start()}G"
    out = []
    column = layout["column"]
    if column is None:   # 不知道光标在哪一格 (玩家刚按了回车): 先挪回这一行的开头
        out.append(to_start)
        column = 0
    for part in LAYOUT_CODES.split(text):
        if part.startswith("\x1b"):
            if part == "\x1b[H":
                out.append(f"\x1b[{layout['top'] + (2 if framed else 1)};{page_start()}H")
                column = 0
            elif part == "\x1b[K" and framed:
                out.append(f"\x1b[K\x1b[{layout['left'] + DASHBOARD_WIDTH}G|")
                column = width   # 光标到了方框外面: 这一行再写字就先折下来
            elif part == "\x1b[J" and framed:
                pass
            elif part == "\x1b7":
                layout["saved"] = column
                out.append(part)
            elif part == "\x1b8":
                column = layout["saved"]
                out.append(part)
            else:
                out.append(part)   # 颜色、光标往上移 (还在同一格)、藏起光标这些, 原样留着
            continue
        for char in part:
            if char == "\n":
                out.append("\n" + to_start)
                column = 0
            elif char == "\r":
                out.append(to_start)
                column = 0
            elif char == "\b":
                out.append(char)
                column = max(0, (column or 0) - 1)
            else:
                size = text_width(char)
                if column is None or column + size > width:
                    out.append("\n" + to_start)
                    column = 0
                out.append(char)
                column += size
    layout["column"] = column
    return "".join(out)


def put(text, flush=False, log=True):
    """原样印出来 (不加换行, 也不算新消息), 终端里用方框的时候挪进方框里。画面上的控制字符 (动画、开车的画面) 都用它印。
    log=False 是不用记下来 (窗口大小变了重新画的时候不用再画一遍, 比如主菜单的小动画每一帧)"""
    if log and screen["logging"]:
        screen["log"].append(text)
    builtins.print(place_text(text), end="", flush=flush)


def window_changed():
    """终端窗口的大小变了没有 (玩家拉大拉小了窗口, 或者放大缩小了字)。只在电脑真正的终端里看"""
    return screen["logging"] and screen_size() != layout["size"]


def refit_screen():
    """窗口大小变了: 清屏, 按新的大小重新算方框摆在哪里, 再把这个画面清屏以后印过的字照原样印一遍"""
    log = screen["log"]
    screen["log"] = []
    layout["size"] = screen_size()
    builtins.print("\x1b[H\x1b[2J\x1b[3J" + start_layout(screen["framed"]), end="")
    for text in log:
        put(text)
    builtins.print("", end="", flush=True)


def ask_text(prompt):
    """让玩家打一行字 (比如名字)。终端里用方框的时候, 先把光标挪到写字的地方; 玩家按了回车以后, 光标回到了窗口最左边"""
    put("", flush=True)
    text = input(prompt)
    layout["column"] = None
    return text


def leave_layout():
    """退出游戏的时候: 光标挪到这一块的下面, 终端接下来的字不会写进方框里"""
    if layout["on"]:
        builtins.print(f"\x1b[{layout['top'] + layout['height'] + 1};1H", end="", flush=True)
        layout["on"] = False


def fit_window():
    """一打开游戏, 窗口太小放不下游戏, 就把终端窗口调大 (\x1b[8;行;列t, Mac 自带的终端和 Linux 的大多数终端认得;
    终端不认得的时候, 什么都不会发生)。窗口够大就不动 (不会把全屏的窗口调小)。设置里关了就不调。
    终端调窗口要一点时间: 调好以后, 等按键的时候发现窗口大小变了, 会按新的大小重新画 (见 refit_screen)"""
    if not (settings["window"] and FRAME and can_clear_screen() and can_read_keys()) or IN_BROWSER or GUI or msvcrt:
        return
    columns, rows = screen_size()
    if columns >= WINDOW_COLUMNS and rows >= WINDOW_ROWS:
        return
    builtins.print(f"\x1b[8;{max(rows, WINDOW_ROWS)};{max(columns, WINDOW_COLUMNS)}t", end="", flush=True)
    time.sleep(0.2)   # 等终端把窗口调好, 后面再量窗口多大


def print(*args, **kwargs):
    """跟 Python 自带的 print 一样, 只是顺便记下「屏幕上多了新消息」。这个文件里的 print 都会经过这里。
    每天都会说一遍的例行消息 (比如今天开了多远) 不算新消息, 要用 print_routine。
    终端里用方框的时候, 字会挪进方框里 (见 place_text)"""
    sep, end = kwargs.get("sep", " "), kwargs.get("end", "\n")
    put(sep.join(str(arg) for arg in args) + ("\n" if end is None else end), flush=kwargs.get("flush", False))
    if any(str(arg).strip() for arg in args):
        screen["unread"] = True


def print_routine(text):
    """例行消息: 跟 print 一样显示出来, 只是不算新消息, 换画面前不用等玩家看。
    一直往前开的时候干脆不印 (动画下面的状态栏都看得到), 不然每天都要按一次回车"""
    if not screen["driving"]:
        put(text + "\n")


def can_clear_screen():
    """能不能换画面: 设置里没关掉, 而且是在真正的终端里或者网页版里"""
    return SCREENS and (can_read_keys() or IN_BROWSER)


def clear_screen(framed=True):
    """把屏幕清空, 光标回到左上角。\\x1b[H 是回到左上角, \\x1b[2J 是清屏, \\x1b[3J 是连往上翻才看得到的旧字也清掉。
    终端里用方框的时候, framed 是要不要画方框 (大画面自己有方框, 就不用)"""
    screen.update(framed=framed, log=[], logging=can_read_keys() and not IN_BROWSER and not GUI)
    layout["size"] = screen_size()
    builtins.print("\x1b[H\x1b[2J\x1b[3J" + start_layout(framed), end="", flush=True)
    screen["unread"] = False


def event_screen():
    """路上出事、有人去世的时候用: 一直往前开、屏幕上又没有没看过的字, 就直接写在动画下面 (像原版那样, 车还在画面上);
    别的时候换一个新画面"""
    if screen["driving"] and screen["room"] and not screen["unread"]:
        return
    new_screen()


def new_screen(framed=True):
    """换一个新画面: 屏幕上还有玩家没看过的新消息, 就先等玩家按回车; 再把屏幕清空, 从最上面写起。
    不能换画面的时候 (比如跑测试) 什么都不做, 字还是一直往下写。framed 见 clear_screen"""
    if not can_clear_screen():
        return
    if screen["unread"]:
        wait_enter()
    clear_screen(framed)


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
                if not key_ready(0.25):   # 等按键的时候, 窗口大小变了就重新画
                    if window_changed():
                        refit_screen()
                    continue
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
        if not key_ready(TITLE_ANIMATION_DELAY if idle else 0.25):   # 一会儿都没按键, 就先做别的事
            if window_changed():   # 窗口大小变了, 按新的大小重新画
                refit_screen()
            if idle:
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
        print(f"车上装不下了, 有 {amount - fits} {MEASURES[item]}{item}只能丢下。(每天的菜单里可以把用不上的东西丢掉, 腾出地方)")
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
        if spot[0] <= game["distance"] < spot[1] and spot[2] not in game["avoided"]:   # 绕开了的不算
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
    """找到一样随机的东西 (搜刮、仓库、旧车、地堡), 装上车。返回真正装上车的数量 (车满了可能装不下)"""
    item = random.choice(list(LOOT))
    low, high = LOOT[item]
    amount = random.randint(low, high)
    print(f"找到了 {amount} {MEASURES[item]}{item}!")
    return add_supplies(game, item, amount)


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
        "here": START_PLACE,   # 车现在停在哪个地方 (刚到的地标、据点、河、辐射热点); 车一开走就是 None
        "short": [],        # 昨天不够的东西 ("食物"、"水"): 头一天不够要专门说, 接着不够就只是例行消息
        "talk": [None, 0],  # 和人说话: [在哪个地方, 在那里已经听了几次] (每次换一个人、说一件事)
        "avoided": [],      # 绕开了的辐射热点 (那一带的辐射不用受)
        "detour": 0,        # 绕路还要多开几公里 (开完了路程才接着往前算)
        "cutoff": 0,        # 萨布莱特捷径: 0 是没走, 1 是正在走, 2 是走完了 (回到了大路上)
        "ferries": 0,       # 坐了几次渡船 (成就「自己过河」用)
        "rocks": 0,         # 坐木筏撞了几次礁石 (成就「激流勇进」用)
    }


def setup(game):
    """开新游戏: 难度和距离单位用主菜单「设置」里的, 再起名字、选性别和出发月份, 最后买东西"""
    new_screen()
    game["difficulty"] = settings["difficulty"]
    game["money"] = DIFFICULTIES[game["difficulty"]][1]
    game["unit"] = settings["unit"]
    name, money, *_ = DIFFICULTIES[game["difficulty"]]
    print(colored(f"\n难度: {name} (一开始有 {money} 块钱)。想换难度或者距离单位, 回到主菜单的「设置」里改。", "灰"))
    show_opening(game)
    new_screen()   # 看完开场, 换个画面起名字
    leader = ask_text("你叫什么名字? (直接按回车就叫\"队长\") ").strip() or "队长"
    gender = ask_number("你的性别: 1. 男  2. 女  ", 1, 2)
    game["gender"] = "男" if gender == 1 else "女"
    show_picture(PORTRAITS[game["gender"]], words=["", "", f"{leader}, 这就是你。"])
    print("\n什么时候出发? 当年的拓荒者大多在 4、5 月出发。")
    print("早走天还冷, 山里可能还在下雪, 要带冬衣; 晚走天热, 路上要多喝水。")
    game["start_month"] = ask_number(f"出发月份 ({FIRST_MONTH}~{LAST_MONTH} 月): ", FIRST_MONTH, LAST_MONTH)
    game["leader"] = leader
    game["party"][leader] = 100
    write_diary(game, f"{leader}被赶出了独立城地下的避难所, 开着捡来的车, 一个人踏上了俄勒冈小道。")
    roll_weather(game)   # 出发这天的天气

    new_screen()   # 先看出发前的提示, 按回车再进商店 (像原版那样)
    print("\n出发前可以在独立城的集市上买东西。")
    print("提示: 每人每天要吃食物、喝 1 份水, 车每天要用燃料。子弹可以打猎, 也可以防身。"
          "天冷时每人要有一套冬衣。")
    print("      路上会生病受伤, 药品能治好; 辐射会在身体里越积越多, 只有排辐剂能把它排掉。")
    print("      路上要过好几条大河, 有的河边有渡船, 坐渡船要花钱, 别把钱一下子全花光。")
    print("      有几段路靠近核设施, 辐射偏高, 排辐剂要多备一些。")
    shop(game)


def show_opening(game):
    """开新游戏时的开场: 背景故事 (用户 2026-10-05 定的)。玩家可以选男女, 所以只用「你」, 不写他或她"""
    print("\n2030 年, 第三次世界大战打成了一场核战争。")
    print("核弹在一天之内落遍了全世界, 旧世界就这样毁灭了。")
    print("\n二十年过去了。")
    print("\n你在密苏里州独立城地下的避难所里出生, 从来没见过外面的世界。")
    print("十八岁那年, 避难所里出了一桩命案。真凶是所长的儿子,")
    print("他带着人把罪名栽到了你头上。")
    print("你被赶出避难所, 扔到废土上自生自灭。")
    new_screen()   # 分成两个画面: 网页版在手机上竖着只看得到 18 行, 放在一起开头几句会被挤出屏幕
    print("\n你在独立城靠拾荒活了下来。")
    print("如今的独立城, 是拾荒者聚居的地方。")
    print("有人说, 俄勒冈那边有官方的人, 正在收人, 缺干活的人手。")
    print("很多人不信。你想去试一试。")
    print("\n你捡到了一辆车, 居然没怎么坏, 还能开。")
    print("你要开着它, 沿着课本里讲过的俄勒冈小道,")
    print(f"去 {show_distance(game, TOTAL_DISTANCE)}外的{DESTINATION}。")
    print("路上的据点里, 也许能遇到愿意跟你走的人。")


def choose_difficulty():
    """「设置」里选难度: 决定一开始有多少钱、路上出事和生病的机会, 还有得分要乘多少。返回难度的编号"""
    print("\n选难度 (越难得分越高):")
    for number, (name, money, _, _, score, note) in DIFFICULTIES.items():
        print(f"{number}. {name}: 一开始有 {money} 块钱, {note}。得分 ×{score / 100:g}")
    return ask_number("选哪个? ", 1, len(DIFFICULTIES))


def price_level(game):
    """这里的东西是独立城价钱的百分之几: 停在据点里按 OUTPOST_PRICES (越往西越贵), 出发的独立城是 100"""
    return OUTPOST_PRICES.get(game["here"], 100)


def unit_price(game, item):
    """这里一个 item 卖多少钱 (显示用, 可能有小数, 比如 1.15 块)"""
    return f"{PRICES[item] * price_level(game) / 100:g}"


def cost_of(game, item, amount):
    """买 amount 个 item 要花多少钱: 越往西越贵; 队伍里有商人就打八折; 有零头往上算 1 块"""
    cost = amount * PRICES[item] * price_level(game)   # 先按「分」算 (1 块 = 100 分), 免得有小数算不准
    if skilled(game, "商人"):
        cost = (cost * 8 + 9) // 10
    return (cost + 99) // 100


def most_affordable(game, item, money=None):
    """money 块钱 (不填就是身上所有的钱) 最多能买几个 item"""
    money = game["money"] if money is None else money
    most = money * 100 // (PRICES[item] * price_level(game))
    while most > 0 and cost_of(game, item, most) > money:
        most -= 1
    while cost_of(game, item, most + 1) <= money:   # 商人打折以后能多买几个
        most += 1
    return most


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
        level = price_level(game)
        if level > 100:
            print(f"这里离独立城远了, 东西都比那里贵 {level - 100}%。")
        merchant = skilled(game, "商人")
        if merchant:
            print(f"商人{merchant}帮你讲价, 买什么都打八折。")
        for i, item in enumerate(items, 1):
            measure = MEASURES[item]
            print(f"{i}. {item}  {unit_price(game, item)} 块一{measure}, 每{measure} {show_weight(game, WEIGHTS[item])}"
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
        most = most_affordable(game, item)
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
    print(f"\n------ 卖东西 ------  据点的人只给独立城价钱的 {share}%")
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
    left = road_left(game, TOTAL_DISTANCE)
    print(colored(f"\n==== {date_text(game)} (第 {game['day']} 天) | 已走 {show_distance(game, game['distance'])}"
                  f" | 还剩 {show_distance(game, left)} ====", "青", bold=True))
    percent = game["distance"] * 100 // TOTAL_DISTANCE
    print(f"路程: {colored(progress_bar(game['distance'], TOTAL_DISTANCE, 20), '青')} {percent}%")
    temperature = game["temperature"]
    print(f"地区: {climate_here(game)[0]}  天气: {colored(game['weather'], weather_color(game['weather']))}  "
          f"气温: {show_temperature(game, temperature)} "
          f"{colored(temperature_level(temperature)[1], temperature_color(temperature))}")
    print(f"    {weather_report(game)}")
    # 物资分两行写, 不然东西多了在 80 列宽的终端里放不下, 会折成两行把画面挤乱
    items = [f"{k} {v}" for k, v in s.items()] + [f"钱 {game['money']}"]
    print("物资: " + "  ".join(items[:4]))
    print("      " + "  ".join(items[4:]))
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
    if name in OUTPOST_NAMES:
        note = " (据点, 可以买东西)"
    elif name in RIVERS:
        note = " (要过河)"
    else:
        note = ""
    print(f"下一站: {name}{note}, 还有 {show_distance(game, road_left(game, km))}")
    short = fuel_short(game)
    if out_of_fuel(game):
        print(colored("注意: 没燃料了, 车开不动。去搜刮废墟会专门到废车里抽油, 也可以找人交易", "红"))
    elif short:
        print(colored(f"注意: 燃料不够开到{short[0]}了 (照现在的速度大约要 {short[1]} 份)", "黄"))
    spot = hotspot_here(game)
    ahead = next_hotspot(game)
    if spot:
        print(colored(f"辐射热点: 正在{spot[2]}, 还要开 {show_distance(game, spot[1] - game['distance'])}才能离开", "紫"))
        print(colored(f"          在外面每天受 {spot[3]} 点辐射, 躲在车里 {spot[4]} 点", "紫"))
    elif ahead and ahead[0] - game["distance"] <= HOTSPOT_WARNING:
        print(colored(f"辐射热点: 再开 {show_distance(game, road_left(game, ahead[0]))}就到{ahead[2]}, "
                      f"那一带辐射偏高", "紫"))
    if game["detour"]:
        print(colored(f"绕路: 还要多开 {show_distance(game, game['detour'])}, 路程才接着往前算", "紫"))
    if on_dry_road(game):
        print(colored(f"捷径: 到{CUTOFF_DRY_UNTIL}以前找不到水, 每人每天多喝 {DRY_WATER} 份", "黄"))
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
        if i and i % PARTY_PAGE == 0 and can_show_pictures() and can_clear_screen():   # 有头像的话, 一页放不下所有人
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
        if can_show_pictures():   # 在终端和网页版里, 每个人的样子画在左边, 字写在右边 (切成短行, 免得自动换行把画挤歪)
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
    if can_show_pictures():
        print()   # 跟最后一个人的头像隔开
    print(f"队伍整体: {health_word(average)} (平均健康 {average})")
    if game["dead"]:
        print(f"路上失去的人: {'、'.join(game['dead'])}")

    new_screen()   # 人看完了, 换一个画面看物资
    print("\n---------- 物资还能撑多久 ----------")
    s = game["supplies"]
    people = len(game["party"])
    need = daily_need(game)
    pace_name, km, _, _ = PACES[game["pace"]]
    print(f"食物: {s['食物']} 份。口粮{RATIONS[game['ration']][0]}, 每天吃 {need['食物']} 份 (天冷要多吃), "
          f"还够吃 {days_left(game, '食物')} 天")
    print(f"水: {s['水']} 份。每天喝 {need['水']} 份 (天热、有人得霍乱要多喝), 还够喝 {days_left(game, '水')} 天")
    fuel_days = days_left(game, "燃料")
    print(f"燃料: {s['燃料']} 份。速度{pace_name}, 每天用 {need['燃料']} 份, "
          f"还够开 {fuel_days} 天, 大约 {show_distance(game, fuel_days * km)}")
    clothes = f"冬衣: {s['冬衣']} 套, 队伍 {people} 人"
    if s["冬衣"] < people:
        clothes += f", 天冷时有 {people - s['冬衣']} 个人没冬衣穿"
    print(clothes)
    print(f"药品 {s['药品']}  排辐剂 {s['排辐剂']}  零件 {s['零件']}  子弹 {s['子弹']}  钱 {game['money']}")
    print(f"离{DESTINATION}还有 {show_distance(game, road_left(game, TOTAL_DISTANCE))}")

    print("\n---------- 车上的重量 ----------")
    people_weight = people * PERSON_WEIGHT
    print(f"人 {show_weight(game, people_weight)}  物资 {show_weight(game, load_of(game) - people_weight)}  "
          f"一共 {show_weight(game, load_of(game))} / {show_weight(game, CAR_CAPACITY)}, "
          f"还能装 {show_weight(game, max(0, CAR_CAPACITY - load_of(game)))}")
    heaviest = max(WEIGHTS, key=lambda item: s[item] * WEIGHTS[item])
    if s[heaviest]:
        print(f"最重的是{heaviest}: {show_weight(game, s[heaviest] * WEIGHTS[heaviest])}")


# ========== 每天发生的事 ==========

def daily_need(game):
    """按现在的口粮、速度, 每天大概要用多少食物、水、燃料 (有人得霍乱要多喝水; 天冷天热另外还要多一些, 这里不算)"""
    cholera = sum(disease == "霍乱" for disease, _ in game["sick"].values())
    people = len(game["party"])
    dry = people * DRY_WATER if on_dry_road(game) else 0   # 捷径上找不到水的那一段, 每人多喝一些
    return {"食物": people * RATIONS[game["ration"]][1], "水": people + cholera * CHOLERA_WATER + dry,
            "燃料": PACES[game["pace"]][2]}


def days_left(game, item):
    """食物、水、燃料还够用几天"""
    need = daily_need(game)[item]
    return game["supplies"][item] // need if need else 0


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
    short = []                     # 今天不够的东西
    food_need = people * (per_person + extra_food)
    if s["食物"] >= food_need:
        s["食物"] -= food_need
    else:
        change -= round(10 * (food_need - s["食物"]) / food_need)
        # 头一天挨饿是新消息 (一直往前开的时候也要专门说, 好让玩家想办法); 昨天就在挨饿, 再说一遍只是例行消息
        (print_routine if "食物" in game["short"] else print)(f"食物不够了, {everyone(game)}在挨饿!")
        s["食物"] = 0
        hungry = True
        short.append("食物")

    cholera = sum(disease == "霍乱" for disease, _ in game["sick"].values())
    water_need = people * (1 + extra_water) + cholera * CHOLERA_WATER
    if on_dry_road(game):   # 萨布莱特捷径上找不到水的那一段: 又干又晒, 每人多喝一些
        water_need += people * DRY_WATER
    dirty_water = s["水"] < water_need
    if not dirty_water:
        s["水"] -= water_need
    else:
        change -= round(15 * (water_need - s["水"]) / water_need)
        (print_routine if "水" in game["short"] else print)(f"干净的水不够了, {everyone(game)}渴得受不了, 只能喝路边的脏水!")
        s["水"] = 0
        short.append("水")
    game["short"] = short

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


def place_km(name):
    """路上的一个地方 (地标或者据点) 离起点几公里"""
    return next(km for km, (place, _) in list(LANDMARKS.items()) + list(OUTPOSTS.items()) if place == name)


def road_left(game, km):
    """从现在的地方开到路上第 km 公里的地方, 还要真的开多少公里: 还没绕完的路要加上, 走捷径少走的要减掉"""
    left = max(0, km - game["distance"]) + game["detour"]
    if game["cutoff"] == 1 and km > place_km(CUTOFF_SKIPS):
        left = max(0, left - CUTOFF_SAVES)
    return left


def on_dry_road(game):
    """是不是走在萨布莱特捷径上找不到水的那一段 (南山口到格林河)"""
    return game["cutoff"] == 1 and game["distance"] < place_km(CUTOFF_DRY_UNTIL)


def next_supply_stop(game):
    """下一个能补给的地方: 下一个据点, 后面没有据点了就是终点。返回 (地方, 还有几公里, 照现在的速度大约开几天, 大约要几份燃料)。
    没算坏天气开得慢 (那样用得更多), 所以只是个大概"""
    ahead = [(km, name) for km, (name, _) in sorted(OUTPOSTS.items())
             if km > game["distance"] and name not in game["visited"]]   # 走捷径的话, 布里杰堡不经过
    km, name = ahead[0] if ahead else (TOTAL_DISTANCE, DESTINATION)
    _, per_day, fuel, _ = PACES[game["pace"]]
    left = road_left(game, km)
    days = -(-left // per_day)   # 往上取整
    return name, left, days, days * fuel


def fuel_short(game):
    """燃料够不够按现在的速度开到下一个据点 (后面没有据点了, 就是到终点): 不够的话返回 (那个地方, 大概要几份燃料), 够就返回 None"""
    name, _, _, need = next_supply_stop(game)
    return (name, need) if game["supplies"]["燃料"] < need else None


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
        print("\n燃料不够, 车开不动了! 可以换慢一点的速度, 去搜刮废墟 (会专门到废车里抽油), 或者找人交易。")
        return
    s["燃料"] -= fuel_need
    game["here"] = None   # 车开走了, 不停在什么地方了 (今天要是又到了一个地方, check_places 会再记上)
    if animate:
        drive_animation(game)
    km = round((km + random.randint(-10, 10)) * speed)
    km = min(km, TOTAL_DISTANCE - game["distance"])   # 最后一段路不多算
    driven = km
    around = min(km, game["detour"])   # 还在绕开辐射热点: 先开完绕的那段路, 路程不往前算
    game["detour"] -= around
    km -= around
    game["distance"] += km
    if around:
        left = f", 还要再绕 {show_distance(game, game['detour'])}" if game["detour"] else ", 绕过去了"
        print_routine(f"\n绕路开了 {show_distance(game, around)}{left}。")
    elif speed < 1:
        print_routine(f"\n{weather}里车开不快, 只往前开了 {show_distance(game, km)}。")
    else:
        print_routine(f"\n车往前开了 {show_distance(game, km)}。")
    if game["cutoff"] == 1 and game["distance"] >= place_km(CUTOFF_SKIPS):
        finish_cutoff(game)
    check_places(game)
    if game["distance"] < TOTAL_DISTANCE:   # 已经到了终点 (比如坐木筏漂到了), 就不会再遇到路上的事
        random_event(game, driven)
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
        clear_screen(framed=not use_dashboard())
        while True:
            gui_update(game)         # 网页版的图形界面: 告诉网页今天的状态
            wide = use_dashboard()   # 窗口够大就用大画面 (每天看一次, 窗口拉大拉小也跟得上)
            if wide:
                layout["framed"] = False   # 大画面自己有方框 (路上出事换过画面的话, 那个画面的方框会被大画面盖掉)
            stuck = WEATHER[game["weather"]][0] > 0 and out_of_fuel(game)   # 燃料不够, 车开不动了
            parts = dashboard_parts(game, car_word(game, moving=True)) if wide else None   # 大画面的别的几块, 今天不变
            if not stuck:
                rows, _, moving = drive_screen(game, frame, wide, parts)
                put(redraw(rows) + "\x1b[J\n", flush=True)
                screen["unread"] = False
                # 一天的动画: 一帧一帧地画 (只重画动画那几行), 每画一帧都看看玩家有没有按键, 按了马上停 (这一天还没开完, 不算)
                for _ in range(DRIVE_DAY_FRAMES):
                    frame += 1
                    screen["frame"] = frame
                    if can_animate():
                        rows, _, moving = drive_screen(game, frame, wide, parts)
                        put("\x1b[?25l" + redraw(rows[:moving]), flush=True, log=False)
                    if stop_pressed(ANIMATION_DELAY) or window_changed():   # 窗口大小变了也停下来, 回到菜单按新的大小画
                        return
            # 这一天开完了: 动画 (大画面的话是整个方框) 留着, 擦掉下面的字, 路上发生的事写在下面 (像原版那样车还在画面上)
            rows, keep, _ = drive_screen(game, frame, wide, parts)
            if keep:
                put("\x1b[?25h" + redraw(rows[:keep]) + "\n\x1b[J")
            else:
                clear_screen()
            rows_here = layout["height"] if layout["on"] else screen_size()[1]   # 用方框的时候, 只算这一块
            screen["room"] = rows_here - keep >= EVENT_ROOM   # 下面放得下一件事才写在下面, 不然换新画面
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


def drive_screen(game, frame, wide, parts=None):
    """一直往前开的画面 (像原版那样), 返回 (一行一行的字, 留着的前几行, 动画占了前几行):
    大画面是一个分成几块的方框, 下面一句怎么停车; 普通的画面是动画、怎么停车、状态栏"""
    how = "点一下屏幕或者按回车" if IN_BROWSER else "按回车"
    hint = colored(f"   ({how}停下来, 看看情况)", "灰")
    if wide:
        box = dashboard_lines(game, drive_frame(game, frame), car_word(game, moving=True), parts)
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

    # 食物、水、燃料还够几天 (天冷天热要吃喝得多一些, 这里按平常算), 只剩 3 天以内是红的
    supplies = []
    for item in daily_need(game):
        days = days_left(game, item)
        supplies.append(f"{item} {s[item]} " + colored(f"够 {days} 天", "红" if days <= 3 else None))
    lines.append("  ".join(supplies))

    name, km = next_place(game)
    lines.append(f"下一站: {name}, 还有 {show_distance(game, road_left(game, km))}")
    percent = game["distance"] * 100 // TOTAL_DISTANCE
    lines.append(f"已走 {show_distance(game, game['distance'])}, 还剩 "
                 f"{show_distance(game, road_left(game, TOTAL_DISTANCE))}  "
                 f"{colored(progress_bar(game['distance'], TOTAL_DISTANCE, 10), '青')} {percent}%")

    # 天天都有、开车的时候不会专门说的事: 放在最后一行提醒
    notes = []
    if hotspot_here(game):
        notes.append(colored("辐射偏高", "紫"))
    if game["detour"]:
        notes.append(colored("在绕路", "紫"))
    if on_dry_road(game):
        notes.append(colored("找不到水", "黄"))
    if s["食物"] == 0:
        notes.append(colored("没吃的了", "红"))
    if s["水"] == 0:
        notes.append(colored("没水了", "红"))
    short = fuel_short(game)
    if out_of_fuel(game):
        notes.append(colored("没燃料了", "红"))
    elif short:
        notes.append(colored(f"燃料不够开到{short[0]}", "黄"))
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


def dashboard_parts(game, car):
    """大画面里除了动画以外的几块: 右边的状态、路线图、最近的事 (开车的时候一天只算一次, 每一帧只换动画)"""
    return status_panel(game, car), route_map(game), recent_events(game)


def dashboard_lines(game, scene, car, parts=None):
    """大画面, 一行一行的字。scene 是动画的一帧, car 是车现在怎么样 (在开、停着……);
    parts 是算好的另外几块 (见 dashboard_parts), 不给就现算"""
    panel, track, events = parts or dashboard_parts(game, car)
    left = list(scene) + [None] + track + [None] + events   # None 是左边一栏里的横线
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
    """网页版图形界面的每天的菜单上面: 停在一个地方就画那个地方, 不然画车停在路上 (状态都在网页的面板里)"""
    print("\n" + "\n".join(menu_scene(game)))


def menu_scene(game):
    """每天的菜单上面那一块 (跟动画一样大): 像原版那样, 停在一个地方就画那个地方, 停在半路就画车停在路上"""
    return place_view(game) or road_scene(screen["frame"], game["pace"], game["weather"], len(game["party"]),
                                          dust=False)


def place_view(game):
    """车停在一个地方的时候, 画这个地方的样子, 最下面一行写地名 (正好 SCENE_HEIGHT 行)。没停在什么地方就返回 None。
    地标和据点用 PICTURES 里的画; 河画车停在对岸; 辐射热点画警告牌; 起点画避难所的门"""
    here = game.get("here")
    if not here:
        return None
    if here in RIVERS:
        rows = river_scene(0, 0, "开", people=max(1, len(game["party"])))[:SCENE_HEIGHT - 1]
    else:
        if here == START_PLACE:
            art, color = START_ART, None
        elif here in PICTURES:
            art, color = PICTURES[here]
        elif here in [name for _, _, name, *_ in HOTSPOTS]:
            art, color = HOTSPOT_SIGN, "紫"
        else:
            return None
        top = (SCENE_HEIGHT - 1 - len(art)) // 2
        left = (SCENE_WIDTH - max(len(line) for line in art)) // 2
        rows = [""] * top + [colored(" " * left + line, color) if line.strip() else "" for line in art]
        rows += [""] * (SCENE_HEIGHT - 1 - len(rows))
    rows.append(" " * ((SCENE_WIDTH - text_width(here)) // 2) + colored(here, "青", bold=True))
    return rows


def show_dashboard(game):
    """每天的菜单上面的大画面: 车停着; 停在一个地方就画那个地方, 不然画面停在开车停下来的那一帧"""
    print("\n".join(dashboard_lines(game, menu_scene(game), car_word(game, moving=False))))


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
    left = road_left(game, TOTAL_DISTANCE)
    name, km = next_place(game)
    kind = " (据点)" if name in OUTPOST_NAMES else " (要过河)" if name in RIVERS else ""
    rows = [
        " " + colored(f"{date_text(game)} (第 {game['day']} 天)", "青", bold=True),
        f" 天气: {colored(weather, weather_color(weather))}  {show_temperature(game, temperature)} "
        f"{colored(temperature_level(temperature)[1], temperature_color(temperature))}",
        "",
        f" 下一站: {name}{kind}",
        f"   还有 {show_distance(game, road_left(game, km))}",
        f" 已走 {show_distance(game, game['distance'])}, 还剩 {show_distance(game, left)}",
        "",
    ]
    for item in daily_need(game):
        days = days_left(game, item)
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
    rows = rows[:DASH_ROWS - 2]   # 人再多也不会挤掉最后两行 (现在最多 4 个人, 正好放得下)
    rows += [""] * (DASH_ROWS - 2 - len(rows))

    notes = []   # 天天都有的事, 开车的时候不会专门说
    spot, ahead = hotspot_here(game), next_hotspot(game)
    if spot:
        notes.append(colored("辐射偏高", "紫"))
    elif ahead and ahead[0] - game["distance"] <= HOTSPOT_WARNING:
        notes.append(colored(f"{show_distance(game, road_left(game, ahead[0]))}后辐射偏高", "紫"))
    if game["detour"]:
        notes.append(colored(f"绕路还要 {show_distance(game, game['detour'])}", "紫"))
    if on_dry_road(game):
        notes.append(colored("找不到水", "黄"))
    if s["食物"] == 0:
        notes.append(colored("没吃的", "红"))
    if s["水"] == 0:
        notes.append(colored("没水", "红"))
    short = fuel_short(game)
    if out_of_fuel(game):
        notes.append(colored("没燃料", "红"))
    elif short:
        notes.append(colored(f"燃料不够到{short[0]}", "黄"))
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
    """每天的菜单里的「休息」: 先问休息几天, 再一天一天地过"""
    print(f"\n休息: {everyone(game)}躲在车里, 不怕风吹雨打, 每天多恢复 {REST_HEALTH} 点健康, 病和伤也好得快一些。")
    print(f"食物还够 {days_left(game, '食物')} 天, 水还够 {days_left(game, '水')} 天。")
    print("0. 不休息了")
    days = ask_number(f"休息几天? (1~{MAX_REST_DAYS}) ", 0, MAX_REST_DAYS)
    if days:
        rest_days(game, days)


def rest_days(game, days):
    """躲在车里休息 days 天。中间有人去世、有人病倒, 或者吃的喝的头一回不够了, 就不接着休息了, 让玩家想办法"""
    if days == 1:
        print(f"\n{everyone(game)}躲在车里休息了一天。")
    else:
        print(f"\n{everyone(game)}打算躲在车里休息 {days} 天……")
    for day in range(1, days + 1):
        people, sick, short = len(game["party"]), set(game["sick"]), set(game["short"])
        if days > 1:
            print_routine(f"{date_text(game)} {game['weather']}, 休息了一天。")
        pass_day(game, REST_HEALTH, indoors=True)
        if not game["party"]:
            return
        trouble = len(game["party"]) < people or set(game["sick"]) - sick or set(game["short"]) - short
        if trouble and day < days:
            print(colored(f"出了事, 先不休息了 (休息了 {day} 天)。", "黄"))
            return
    if days > 1:
        print(f"休息了 {days} 天, 今天是{date_text(game)}。")


def scavenge(game):
    """每天的菜单里的「搜刮废墟」(花一天): 随便翻找, 也许能找到东西, 也可能碰上野狗。
    车没燃料了的话, 就专门到路边的废车里抽油 (比随便翻找容易找到燃料)"""
    siphon = out_of_fuel(game)
    if siphon:
        print(f"\n车没燃料了, {you(game)}花了一天, 到附近的废车里找油……")
    else:
        print(f"\n{you(game)}花了一天搜刮附近的废墟……")
    pass_day(game)
    if not game["party"]:
        return
    roll = random.random()
    scavenger = skilled(game, "拾荒者")
    if roll < 0.2:
        mutant_attack(game)
    elif siphon and (scavenger or roll >= 0.2 + SIPHON_EMPTY):
        fuel = random.randint(*SIPHON_FUEL)
        if scavenger:
            fuel = fuel * 3 // 2
            print(f"拾荒者{scavenger}知道哪种车的油箱里还剩着油。")
        fuel = add_supplies(game, "燃料", fuel)
        print(f"从几辆废车的油箱里抽出了 {fuel} 份燃料。")
        write_diary(game, f"车没燃料了, 从路边的废车里抽出 {fuel} 份燃料。")
    elif siphon:
        print("翻了好几辆废车, 油箱都是空的。")
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
    """每天的菜单里的「打猎」(花一天): 像原版那样, 动物在原野上跑来跑去, 移动准星瞄准开枪。
    不能实时读键盘的时候 (跑测试、网页还是旧版), 还是以前那种打字的打猎"""
    if not can_aim():
        typing_hunt(game)
        return
    s = game["supplies"]
    if s["子弹"] == 0:
        print("\n没有子弹, 打不了猎。")
        return
    most = len(game["party"]) * CARRY_PER_PERSON // WEIGHTS["食物"]
    print(f"\n{title('打猎')}{you(game)}拿着枪来到了原野上。现在有 {s['子弹']} 发子弹, 开一枪用 1 发。")
    print("变异野兔、双头鹿、辐射野猪会从两边跑过来, 打中了就有肉。")
    print(f"一次打猎大约 {round(HUNT_FRAMES * HUNT_DELAY)} 秒, 要花一天。想早点回去就按回车。")
    if IN_BROWSER:
        print("怎么打: 用鼠标或手指点一下屏幕上的动物, 就朝那里开枪 (电脑上也可以用方向键移动准星、空格开枪)。")
    else:
        print("怎么打: 用方向键 (或者 W A S D) 移动准星 +, 按空格开枪。")
    print(f"{you(game)}一共只扛得动 {most} 份肉 ({show_weight(game, most * WEIGHTS['食物'])}), 打多了也带不回来。")
    wait_enter("按回车开始打猎……")
    hunting = hunt_game(game)

    bag = hunting["bag"]
    food = sum(meat for _, meat in bag)
    if not bag:
        print(f"这次开了 {hunting['shots']} 枪, 什么都没打到。")
    else:
        counts = {}   # 每种动物打到了几只
        for name, _ in bag:
            counts[name] = counts.get(name, 0) + 1
        names = "、".join(f"{count} 只{name}" for name, count in counts.items())
        print(f"这次开了 {hunting['shots']} 枪, 打到了 {names}, 一共 {food} 份肉。")
        hunter = skilled(game, "猎人")
        if hunter:
            food = food * 3 // 2   # 猎人收拾猎物更干净, 肉多一半
            print(f"猎人{hunter}帮忙收拾猎物, 肉多了一半, 有 {food} 份。")
        brought = carry_meat(game, food)
        write_diary(game, f"打猎打到{names}, 带回 {brought} 份食物。")
        if len(bag) >= 3:
            unlock("神枪手")
    pass_day(game)


def can_aim():
    """能不能玩瞄准射击的打猎: 设置里没关掉, 能换画面, 而且能一边画一边读玩家按的键
    (在真正的终端里; 网页版要网页认得打猎时的点击, 见 run_in_browser.py)"""
    return HUNT_GAME and can_clear_screen() and (can_read_keys() or HUNT_IN_BROWSER)


def new_hunt(game):
    """打猎开始时的样子: 准星在原野中间, 还没有动物"""
    return {
        "aim": [HUNT_HEIGHT // 2, SCENE_WIDTH // 2],   # 准星在原野的第几行、第几格
        "animals": [],   # 原野上的动物: {"name", "x", "y", "speed" (每帧跑几格, 负数是往左跑), "scared", "dead" (死了几帧, 活着是 None)}
        "puffs": [],     # 没打中时扬起的土: [行, 格, 还留几帧]
        "bag": [],       # 打到的: [(名字, 几份肉), ...]
        "shots": 0,      # 开了几枪
        "left": HUNT_FRAMES,   # 还剩几帧
        "over": False,   # 玩家按了回车, 或者子弹打光了
        "message": "",   # 原野下面写的一句话 (打中了没有)
        "frame": 0,
        "ground": hunt_ground(game),
    }


def hunt_game(game):
    """打猎小游戏本身: 一帧一帧地读玩家按的键 (hunt_keys)、开枪、让动物跑, 再画出来。返回打猎的结果 (见 new_hunt)。
    不能换画面的时候 (测试里让电脑玩家打猎) 不画也不停, 一下子就玩完"""
    hunting = new_hunt(game)
    show = can_clear_screen()
    reading = can_read_keys()   # 在真正的终端里: 一个键一个键地读
    old_settings = start_reading_keys() if reading else None
    try:
        if show:
            clear_screen()
            put("\x1b[?25l")   # 藏起光标, 不然它在画面上一闪一闪
            hunt_screen(True)
        if reading:
            forget_keys()   # 之前按的键不算
        while hunting["left"] > 0 and not hunting["over"]:
            for event in hunt_keys(hunting):
                hunt_event(game, hunting, event)
            move_animals(hunting)
            hunting["left"] -= 1
            hunting["frame"] += 1
            if show:
                if window_changed():   # 窗口大小变了: 按新的大小清屏 (下面每一帧本来就整个重画)
                    clear_screen()
                    put("\x1b[?25l", log=False)
                put(redraw(hunt_rows(game, hunting)), flush=True, log=False)
                time.sleep(HUNT_DELAY)
        if not hunting["over"]:
            hunting["message"] = "时间到了, 天快黑了。"
        if show:   # 最后一帧留在画面上, 下面写打到了什么
            put(redraw(hunt_rows(game, hunting)) + "\n\x1b[J", flush=True)
    finally:
        if show:
            builtins.print("\x1b[?25h", end="", flush=True)
            hunt_screen(False)
        if reading:
            forget_keys()   # 打猎时多按的键, 不留给下一个问题
        stop_reading_keys(old_settings)
    return hunting


def hunt_keys(hunting):
    """打猎时, 上一帧以后玩家按了哪些键: 返回 [("上",), ("开枪",), ("走",) ...]。
    终端里认方向键、W A S D、空格 (开枪)、回车和 Q (结束)。
    网页版里 run_in_browser.py 会把它换成读网页上的点击: ("打", 第几行, 第几格) 是点了屏幕上的那一格, ("瞄", 行, 格) 是鼠标移到那里"""
    keys = []
    if msvcrt:
        while msvcrt.kbhit():
            key = msvcrt.getwch()
            if key in ("\x00", "\xe0"):   # 方向键: 后面还跟着一个字
                keys.append({"H": "上", "P": "下", "K": "左", "M": "右"}.get(msvcrt.getwch(), ""))
            else:
                keys.append(key)
    else:
        text = ""
        while select.select([sys.stdin], [], [], 0)[0]:
            data = os.read(sys.stdin.fileno(), 64)
            if not data:
                break
            text += data.decode("utf-8", errors="ignore")
        # 方向键是 ESC [ A 三个字, 偶尔会被拆成两次送来: 结尾只到一半的话, 再等一小会儿后半个
        while text.endswith(("\x1b", "\x1b[", "\x1bO")) and select.select([sys.stdin], [], [], 0.05)[0]:
            data = os.read(sys.stdin.fileno(), 64)
            if not data:
                break
            text += data.decode("utf-8", errors="ignore")
        keys = split_keys(text)
    events = []
    for key in keys:
        if key == "\x03":   # Ctrl+C
            raise KeyboardInterrupt
        action = key if key in ("上", "下", "左", "右") else HUNT_KEYS.get(key.lower())
        if action:
            events.append((action,))
    return events


def split_keys(text):
    """把终端里读到的一串字分成一个一个的键。方向键是 ESC [ A 这样三个字, 换成「上」「下」「左」「右」"""
    keys = []
    i = 0
    while i < len(text):
        if text[i] == "\x1b" and text[i + 1:i + 2] in ("[", "O") and i + 2 < len(text):
            keys.append({"A": "上", "B": "下", "C": "右", "D": "左"}.get(text[i + 2], ""))
            i += 3
        else:
            keys.append(text[i])
            i += 1
    return keys


HUNT_KEYS = {"w": "上", "s": "下", "a": "左", "d": "右", " ": "开枪", "\r": "走", "\n": "走", "q": "走"}


def hunt_screen(on):
    """打猎开始 (on=True) 和结束的时候说一声。电脑上什么都不做; 网页版里 run_in_browser.py 会告诉网页, 网页就把点击当成开枪"""


def hunt_event(game, hunting, event):
    """玩家这一帧按的一个键 (或者网页上的一次点击): 移动准星、开枪, 或者结束打猎"""
    aim = hunting["aim"]
    what = event[0]
    if what == "走":
        hunting["over"] = True
        hunting["message"] = "收拾好东西, 回车上去了。"
    elif what in ("上", "下"):
        aim[0] = max(0, min(HUNT_HEIGHT - 1, aim[0] + (1 if what == "下" else -1)))
    elif what in ("左", "右"):
        aim[1] = max(0, min(SCENE_WIDTH - 1, aim[1] + (HUNT_STEP if what == "右" else -HUNT_STEP)))
    elif what in ("瞄", "打"):   # 网页上的鼠标、手指: 屏幕上第几行第几格 (原野上面还有一行标题)
        row, col = event[1] - 1, event[2]
        if 0 <= row < HUNT_HEIGHT and 0 <= col < SCENE_WIDTH:
            aim[0], aim[1] = row, col
            if what == "打":
                shoot(game, hunting, 1)   # 手指没那么准, 点在动物旁边一格也算
    elif what == "开枪":
        shoot(game, hunting, 0)


def shoot(game, hunting, slack):
    """朝准星开一枪 (用 1 发子弹): 准星在哪只动物身上 (旁边 slack 格以内也算), 就打中了它"""
    s = game["supplies"]
    if s["子弹"] == 0:
        hunting["over"] = True
        hunting["message"] = "没子弹了!"
        return
    s["子弹"] -= 1
    hunting["shots"] += 1
    row, col = hunting["aim"]
    for animal in hunting["animals"]:
        top, left, height, width = animal_box(animal)
        if animal["dead"] is None and top - slack <= row < top + height + slack \
                and left - slack <= col < left + width + slack:
            animal["dead"] = 0
            low, high = ANIMALS[animal["name"]]
            meat = random.randint(low, high)
            hunting["bag"].append((animal["name"], meat))
            hunting["message"] = colored(f"砰! 打中了一只{animal['name']}, 有 {meat} 份肉!", "黄")
            return
    hunting["puffs"].append([row, col, 3])
    hunting["message"] = "砰! 没打中。动物被枪声吓得跑得更快了。"
    for animal in hunting["animals"]:
        _, left, _, width = animal_box(animal)
        if animal["dead"] is None and not animal["scared"] and abs(left + width / 2 - col) <= HUNT_SCARE_RANGE:
            animal["speed"] *= HUNT_SCARE_SPEED
            animal["scared"] = True


def animal_art(animal, frame=0):
    """这只动物的样子: 往右跑的时候左右翻过来 (每行先补齐到一样宽, 翻过来才对得齐)"""
    art = ANIMAL_ART[animal["name"]][frame // 2 % 2]
    if animal["speed"] < 0:
        return art
    width = max(len(line) for line in art)
    return [line.ljust(width)[::-1].translate(MIRROR) for line in art]


def animal_box(animal):
    """动物占的地方: (最上面一行, 最左边一格, 几行高, 几格宽)"""
    art = ANIMAL_ART[animal["name"]][0]
    return animal["y"], round(animal["x"]), len(art), max(len(line) for line in art)


def move_animals(hunting):
    """过一帧: 动物往前跑 (偶尔上下拐一下), 跑出原野的就没了; 打死的留几帧再拿走; 动物不够多就从两边再跑进来一只"""
    for animal in list(hunting["animals"]):
        if animal["dead"] is not None:
            animal["dead"] += 1
            if animal["dead"] > 8:
                hunting["animals"].remove(animal)
            continue
        animal["x"] += animal["speed"]
        top, left, height, width = animal_box(animal)
        if random.random() < 0.05:
            animal["y"] = max(2, min(HUNT_HEIGHT - height, top + random.choice([-1, 1])))
        if left > SCENE_WIDTH or left + width < 0:
            hunting["animals"].remove(animal)
    for puff in list(hunting["puffs"]):
        puff[2] -= 1
        if puff[2] <= 0:
            hunting["puffs"].remove(puff)
    alive = [animal for animal in hunting["animals"] if animal["dead"] is None]
    # 一开始马上跑进来一只, 不用干等
    if len(alive) < HUNT_MAX_ANIMALS and (not hunting["animals"] and hunting["frame"] < 3 or random.random() < HUNT_SPAWN):
        names = list(HUNT_ANIMALS)
        name = random.choices(names, [HUNT_ANIMALS[n][2] for n in names])[0]
        low, high, _ = HUNT_ANIMALS[name]
        art = ANIMAL_ART[name][0]
        width = max(len(line) for line in art)
        speed = random.uniform(low, high)
        from_left = random.random() < 0.5
        hunting["animals"].append({
            "name": name, "x": -width if from_left else SCENE_WIDTH, "speed": speed if from_left else -speed,
            "y": random.randint(2, HUNT_HEIGHT - len(art)), "scared": False, "dead": None})


def hunt_ground(game):
    """原野的背景: 天上的秃鹫、远处的山, 地上稀稀拉拉的枯草、石头和枯树。
    用自己的随机数 (按第几天定), 画不画出来都不影响游戏里别的随机事"""
    rng = random.Random(game["day"])
    rows = [scene_slice(SCENE_SKY, rng.randrange(60)), scene_slice(SCENE_FAR, rng.randrange(60))]
    for _ in range(HUNT_HEIGHT - 2):
        rows.append("".join(rng.choice(".,'`") if rng.random() < 0.05 else " " for _ in range(SCENE_WIDTH)))
    for thing in rng.sample([["\\|/", " | "], ["_.-._"], ["\\ /", " Y ", " | "], ["(@@)"]], 3):
        y, x = rng.randint(2, HUNT_HEIGHT - len(thing)), rng.randrange(SCENE_WIDTH - 6)
        for i, line in enumerate(thing):
            rows[y + i] = rows[y + i][:x] + line + rows[y + i][x + len(line):]
    return rows


def hunt_rows(game, hunting):
    """打猎的一帧画面: 上面一行是子弹、打到了什么、还剩几秒; 中间是原野; 下面是刚才打中了没有、怎么打"""
    canvas = [[[" ", None] for _ in range(SCENE_WIDTH)] for _ in range(HUNT_HEIGHT)]
    for y, line in enumerate(hunting["ground"]):
        draw(canvas, y, 0, line, "灰")
    for animal in hunting["animals"]:
        art = animal_art(animal, hunting["frame"])
        color = ANIMAL_COLORS[animal["name"]]
        if animal["dead"] is not None:   # 打死的动物倒在那里, 眼睛变成 x
            art, color = [line.replace("o", "x").replace("O", "x") for line in art], "灰"
        for i, line in enumerate(art):
            draw(canvas, animal["y"] + i, round(animal["x"]), line, color, solid=True)
    for row, col, _ in hunting["puffs"]:
        draw(canvas, row, col - 1, "*.*", "黄")
    draw(canvas, hunting["aim"][0], hunting["aim"][1], "+", "青")
    food = sum(meat for _, meat in hunting["bag"])
    seconds = int(-(-hunting["left"] * HUNT_DELAY // 1))   # 往上取整
    top = colored(f"打猎  子弹 {game['supplies']['子弹']}  打到 {len(hunting['bag'])} 只 ({food} 份肉)  还剩 {seconds} 秒", "黄", bold=True)
    how = "点一下动物就开枪 (也可以用方向键和空格), 回车结束" if IN_BROWSER else "方向键 / WASD 移动准星 +, 空格开枪, 回车结束"
    return [top] + canvas_lines(canvas) + [hunting["message"], colored(how, "灰")]


def typing_hunt(game):
    """以前的打猎 (不能玩瞄准射击的时候用): 看到词以后越快打出来, 打到的肉越多"""
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
    typed = ask_text("快打: ").strip().lower()
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


def trade(game):
    """每天的菜单里的「交易」: 花一天找人换东西。停在据点里人多, 一定找得到人; 在路上不一定碰得到"""
    place = game["here"]
    at_outpost = place in OUTPOST_NAMES
    if at_outpost:
        print(f"\n{you(game)}在{place}里转了一天, 找人换东西……")
    else:
        print(f"\n{you(game)}在路边等了一天, 看有没有过路的人愿意换东西……")
    pass_day(game)
    if not game["party"]:
        return
    if not at_outpost and random.random() >= TRADE_CHANCE:
        print("等了一整天, 连个人影都没看到。")
        return
    offer_trade(game, random.choice(TRADERS))


def offer_trade(game, who, heading=""):
    """who (比如「一个独眼的老猎人」) 拿出一样东西 (随机的), 换你车上的另一样, 换不换让玩家选。
    他要的东西按商店的价钱算值多少 (TRADE_ASK), 只挑你车上够数的、换完车上还装得下的。heading 是印在最前面的标题"""
    s = game["supplies"]
    give = random.choice(list(TRADE_LOTS))
    amount = random.randint(*TRADE_LOTS[give])
    ask = random.randint(*TRADE_ASK)
    merchant = skilled(game, "商人")
    if merchant:
        ask = ask * MERCHANT_TRADE_ASK // 100
    value = amount * PRICES[give] * ask / 100   # 他想要的东西值多少钱
    prices = {item: round(value / PRICES[item]) for item in PRICES if item != give}   # 换哪样要几个
    print(f"{heading}{who}凑了过来, 拿出 {amount} {MEASURES[give]}{give}, 想跟{you(game)}换点东西。")
    wants = [item for item, price in prices.items() if 1 <= price <= s[item]]
    if not wants:
        print(f"可是{you(game)}车上没有对方想要的东西, 换不成。")
        return
    load = load_of(game)
    wants = [item for item in wants   # 换完车上要装得下 (本来就超重的旧存档, 换完不变得更重就行)
             if load - prices[item] * WEIGHTS[item] + amount * WEIGHTS[give] <= max(CAR_CAPACITY, load)]
    if not wants:
        print(f"可惜车上太重了, 装不下 {amount} {MEASURES[give]}{give}, 换不了。")
        return
    want = random.choice(wants)
    price = prices[want]
    print(f"({you(game)}现在有 {s[want]} {MEASURES[want]}{want}、{s[give]} {MEASURES[give]}{give})")
    if merchant:
        print(f"商人{merchant}帮你讲价, 对方少要了两成。")
    print(f"「{pick(game, '老兄', '妹子')}, 我这 {amount} {MEASURES[give]}{give}换你 {price} {MEASURES[want]}{want}, 换不换?」")
    if ask_number("1. 换  2. 不换  ", 1, 2) == 2:
        print(f"{you(game)}摇了摇头, 没有换。")
        return
    s[want] -= price
    s[give] += amount
    print(f"换好了。现在有 {s[give]} {MEASURES[give]}{give}、{s[want]} {MEASURES[want]}{want}。")
    write_diary(game, f"跟{who}用 {price} {MEASURES[want]}{want}换了 {amount} {MEASURES[give]}{give}。")


def drop(game):
    """每天的菜单里的「丢东西」: 车太重了, 把用不上的东西扔掉, 给别的东西腾地方 (不花时间)。一样一样地丢, 选 0 不丢了"""
    items = list(PRICES)
    s = game["supplies"]
    note = ""   # 刚才丢了什么 (写在下一个画面上, 不用再按一次回车)
    while True:
        new_screen()
        people = len(game["party"]) * PERSON_WEIGHT
        print("\n------ 丢东西 ------")
        print(f"车上: {show_weight(game, load_of(game))} / {show_weight(game, CAR_CAPACITY)}, 其中人占了 {show_weight(game, people)}")
        for i, item in enumerate(items, 1):
            print(f"{i}. {item}  {s[item]} {MEASURES[item]}, 一共 {show_weight(game, s[item] * WEIGHTS[item])}")
        print("0. 不丢了")
        if note:
            print(note)
        choice = ask_number("丢什么? ", 0, len(items))
        if choice == 0:
            return
        item = items[choice - 1]
        if s[item] == 0:
            note = f"车上没有{item}。"
            continue
        amount = ask_number(f"丢多少{item}? (最多 {s[item]}) ", 0, s[item])
        note = ""
        if amount:
            s[item] -= amount
            note = f"扔掉了 {amount} {MEASURES[item]}{item}, 车轻了 {show_weight(game, amount * WEIGHTS[item])}。"
            write_diary(game, f"扔掉了 {amount} {MEASURES[item]}{item}。")


def shop_here(game):
    """每天的菜单里的「买卖东西」: 只有停在据点里的时候才有 (原版在堡垒里随时能买东西), 不花时间"""
    shop(game, can_sell=True)


def talk(game):
    """每天的菜单里的「和人说话」(不花时间): 车停在一个地方的时候, 听那里的人说说前面的路况、天气、河有多深。
    在同一个地方多问几次, 每次换一个人、说一件事; 都说完了从头再说"""
    place = game["here"]
    if not place:
        print("\n四下里一个人影都没有。到了地标、据点这些地方, 再找人问问吧。")
        return
    region = story_region(game)
    if region == "独立城":
        talkers = START_TALKERS
    elif place in GOVERNMENT_BASES:
        talkers = BASE_TALKERS
    else:
        talkers = OUTPOST_TALKERS if place in OUTPOST_NAMES else ROAD_TALKERS
    tips = random.Random(place).sample(TALK_TIPS, 2)   # 每个地方的人说的提醒不一样, 可同一个地方每次问都一样
    story = random.Random(place + "故事").sample(STORY_TALK[region], 2)
    lines = story[:1] + [line for line in (topic(game) for topic in TALK_TOPICS) if line] + story[1:] + tips
    heard = game["talk"][1] if game["talk"][0] == place else 0   # 在这里已经听了几次
    game["talk"] = [place, heard + 1]
    print(f"\n{talkers[heard % len(talkers)]}说:")
    print(f"「{lines[heard % len(lines)]}」")
    if heard + 1 == len(lines):
        print(colored(f"(这里的人知道的, 都跟{you(game)}说过了)", "灰"))


def story_region(game):
    """和人说话时, 这里的人说哪一类跟故事有关的话: 独立城 / 政府地盘以东 / 政府的地盘里"""
    if game["here"] == START_PLACE:
        return "独立城"
    return "政府" if game["distance"] >= GOVERNMENT_KM else "东边"


def talk_river(game):
    """前面最近的一条河: 还有多远、这几天大概多深、车开不开得过去、有没有渡船"""
    for km, (place, _) in sorted(LANDMARKS.items()):
        if km > game["distance"] and place in RIVERS:
            river, _, _, fare = RIVERS[place]
            depth = round(usual_depth(game, place), 1)   # 只是大概 (不掷骰子: 同一天问几次都一样, 也不影响别的随机事)
            wade = "车直接开得过去" if depth <= wade_depth(game) else "车直接开过去, 发动机怕是要进水"
            ferry = f"河边有人摆渡, 收 {fare} 块钱" if fare else "那里没有渡船, 只能自己想办法过"
            return (f"再往西 {show_distance(game, road_left(game, km))}就是{river}。"
                    f"这几天水大概有 {show_length(game, depth)}深, {wade}。{ferry}。")
    return None


def talk_weather(game):
    """前面一段路 (下一个气候区, 后面没有了就是这里) 这个月多热、常不常下雨下雪"""
    month = date_of(game)[0]
    ahead = [km for km in CLIMATE if km > game["distance"]]
    region, highs, wet, snow = CLIMATE[min(ahead)] if ahead else climate_here(game)
    high, wet_days, snow_days = highs[month - 1], round(wet[month - 1]), round(snow[month - 1])
    where = f"再往西到了{region}一带" if ahead else "这一带"
    text = f"{where}, 这个时候白天大概 {show_temperature(game, high)}, 一个月里有 {wet_days} 天左右下雨下雪"
    if snow_days:
        text += f", 其中 {snow_days} 天是灰雪"
    if high < 10:
        return text + "。晚上冷得很, 冬衣每人一套, 吃的也要多带点。"
    if high >= 32:
        return text + "。热得要命, 水要多带。"
    if wet_days >= 8:
        return text + "。黑雨、酸雨多, 碰上了就躲在车里。"
    return text + "。天气还算好走。"


def talk_supplies(game):
    """下一个能买东西的据点: 还有多远, 照现在的速度要开几天、用多少燃料"""
    name, left, days, fuel = next_supply_stop(game)
    if name == DESTINATION:
        return f"从这里到{DESTINATION}, 路上再也没有能买东西的地方了, 缺什么得自己想办法。"
    return (f"下一个能买东西的地方是{name}, 离这里还有 {show_distance(game, left)}。"
            f"照{you(game)}现在的速度, 得开 {days} 天上下, 燃料要 {fuel} 份。")


def talk_hotspot(game):
    """辐射热点: 在里面的话还要开多远才出得去; 不在的话前面的下一个还有多远"""
    spot = hotspot_here(game)
    if spot:
        return (f"这一带辐射偏高, 还要再开 {show_distance(game, spot[1] - game['distance'])}才出得去。"
                "能少在外面待就少待, 开快一点也能少受些辐射。")
    spot = next_hotspot(game)
    if spot:
        return (f"再往西 {show_distance(game, road_left(game, spot[0]))}就到{spot[2]}了, 那一带辐射偏高。"
                f"排辐剂带上几支, 到了那里别在外面磨蹭; 也可以绕过去, 要多开大约 {show_distance(game, DETOUR_KM)}。")
    return None


def talk_last_road(game):
    """到达尔斯以前: 最后一段路的两种走法"""
    if game["distance"] >= max(OUTPOSTS):
        return None
    return (f"到了{LAST_ROAD_FROM}, 最后一段路有两种走法: 扎木筏顺着哥伦比亚河漂下去, 不要钱也不用燃料, 可是急流里有礁石; "
            f"或者交 {BARLOW_TOLL} 块钱过路费, 开车走绕过胡德山的巴洛路。")


def talk_cutoff(game):
    """到南山口以前: 过了南山口有一条近路"""
    if game["distance"] >= place_km(CUTOFF_FROM):
        return None
    return (f"过了{CUTOFF_FROM}, 有一条近路叫萨布莱特捷径, 能少走大约 {show_distance(game, CUTOFF_SAVES)}。"
            f"可是到{CUTOFF_DRY_UNTIL}以前有大约 {show_distance(game, CUTOFF_DRY)}找不到水, 也路过不了{CUTOFF_SKIPS}。")


TALK_TOPICS = [talk_river, talk_weather, talk_supplies, talk_hotspot, talk_cutoff, talk_last_road]


def make_room(game, name):
    """有人想上车, 可车上东西太重, 再坐一个人就超载了: 问要不要先丢掉一些东西, 给他腾个座位。
    坐得下 (本来就坐得下, 或者丢完东西坐得下了) 返回 True, 玩家不丢了返回 False"""
    while not has_seat_for_one_more(game):
        print(f"可惜车上东西太重, 再坐一个人就超载了 (每个人算 {show_weight(game, PERSON_WEIGHT)})。")
        if ask_number(f"1. 先丢掉一些东西, 给{name}腾个座位  2. 算了  ", 1, 2) == 2:
            return False
        drop(game)
        new_screen()
    return True


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
        if km > game["distance"] and name not in game["visited"]:   # 走捷径的话, 布里杰堡不经过
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
        game["here"] = name    # 像原版那样停在这里, 每天的菜单上面画这个地方 (见 place_view)
        new_screen()           # 每到一个地方都换一个画面
        if name in PICTURES:   # 先看一眼那里的样子
            show_picture(*PICTURES[name])
        if kind == "热点":
            play_music("热点")
            show_picture(HOTSPOT_SIGN, "紫")
            print(f"\n{you(game)}开到了{title(name, '紫')}{intro}{colored('盖革计数器响个不停, 这一带辐射偏高。', '紫')}")
            choose_hotspot_road(game, name, km)
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
            if name == CUTOFF_FROM:
                choose_cutoff(game, km)
            continue
        play_music("据点")
        print(f"\n{you(game)}到了{title(name, '青')}{intro}")
        base = name in GOVERNMENT_BASES   # 拉勒米堡往西是政府的基地
        if name == GOVERNMENT_FROM:
            print(colored("从这里往西, 是美国政府的地盘。", "黄"))   # 不说到哪里为止: 主角不知道终点是政府的后备据点
        if base:
            print(colored("这里现在是美国政府重新占领的基地, 驻着政府的人。", "黄"))
            print(BASE_NOTES[name])
            write_diary(game, f"到了{name}, 这里现在是美国政府的基地。", km)
        else:
            write_diary(game, f"到了{name}。", km)
        offer_recruit(game, name, km)
        traders = "基地里也有人" if base else "这里有幸存者"
        if ask_number(f"{traders}在做买卖, 要进去买卖东西吗? 1. 要  2. 不要  ", 1, 2) == 1:
            shop(game, can_sell=True)
        if name == LAST_ROAD_FROM:
            choose_last_road(game, km)


def choose_hotspot_road(game, name, km):
    """开到辐射热点跟前: 直接开过去 (快, 可是在那一带每天都要多受辐射), 还是绕路 (多开 DETOUR_KM 公里, 不受那里的辐射)"""
    start, end, _, outdoor, indoor, _ = next(spot for spot in HOTSPOTS if spot[2] == name)
    _, per_day, fuel, _ = PACES[game["pace"]]
    days = -(-DETOUR_KM // per_day)   # 往上取整
    print(f"1. 直接开过去: 大约 {show_distance(game, end - start)}, 在这一带每天多受 {outdoor} 点辐射 (躲在车里 {indoor} 点)")
    print(f"2. 绕路: 多开大约 {show_distance(game, DETOUR_KM)}, 照现在的速度多花 {days} 天、{days * fuel} 份燃料,")
    print("         这一带的辐射就不用受了")
    day_end = game["distance"]
    game["distance"] = km   # 车先停在热点跟前选 (像过河一样, 状态栏写的也是这里)
    if ask_number("怎么过这一带? ", 1, 2) == 1:
        game["distance"] = day_end   # 直接开过去: 接着开完今天的路
        write_diary(game, f"开进了{name}, 这一带辐射偏高。", km)
        return
    game["avoided"].append(name)
    over = day_end - km   # 今天本来还要往热点里开这么远: 这一段改成在绕路 (不然今天就会开到热点里面的地方)
    game["distance"] = km + max(0, over - DETOUR_KM)
    game["detour"] += max(0, DETOUR_KM - over)
    print(f"{you(game)}掉转车头, 找了一条离{name}远一点的路。")
    write_diary(game, f"绕开了{name}, 要多开大约 {show_distance(game, DETOUR_KM)}。", km)
    if len(game["avoided"]) == len(HOTSPOTS):
        unlock("远离辐射")


def choose_cutoff(game, km):
    """到了南山口: 照大路走, 经过布里杰堡; 还是走萨布莱特捷径 (少走一段路, 可是有一段找不到水, 也不经过布里杰堡)"""
    print(f"\n过了{CUTOFF_FROM}, 前面有两条路:")
    print(f"1. 走大路, 经过{CUTOFF_SKIPS} (能买卖东西, 那里还有人愿意跟你走)")
    print(f"2. 走萨布莱特捷径 (1844 年开出来的近路): 少走大约 {show_distance(game, CUTOFF_SAVES)},")
    print(f"   可是到{CUTOFF_DRY_UNTIL}以前有大约 {show_distance(game, CUTOFF_DRY)}找不到水 (每人每天多喝 {DRY_WATER} 份),"
          f" 也不经过{CUTOFF_SKIPS}")
    if ask_number("走大路还是走捷径? ", 1, 2) == 1:
        return
    game["cutoff"] = 1
    game["visited"].append(CUTOFF_SKIPS)   # 不经过布里杰堡: 到了那么远也不会停下来
    print(f"{you(game)}拐上了捷径。前面是一片干巴巴的荒原, 水要省着喝。")
    write_diary(game, f"在{CUTOFF_FROM}拐上了萨布莱特捷径。", km)


def finish_cutoff(game):
    """捷径走到头了: 翻过山, 回到了大路上 (一下子少走 CUTOFF_SAVES 公里)"""
    game["cutoff"] = 2
    game["distance"] = min(TOTAL_DISTANCE, game["distance"] + CUTOFF_SAVES)
    print(f"\n{you(game)}翻过山, 走完了萨布莱特捷径, 回到了大路上, 少走了大约 {show_distance(game, CUTOFF_SAVES)}。")
    write_diary(game, f"走完了萨布莱特捷径, 回到大路上, 少走了大约 {show_distance(game, CUTOFF_SAVES)}。")


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
    brings = "和".join(f" {amount} 份{item}" for item, amount in RECRUIT_BRINGS.items())
    show_picture(PORTRAITS[job], words=["", "", f"{name} ({job})"])
    print(f"这里有个叫 {name} 的{job}也想往西走, 愿意跟{you(game)}一起, 还会带上自己的{brings}。")
    print(f"特长: {SKILLS[job]}。不过多一个人, 每天也要多吃多喝, 天冷时还要多一套冬衣。")
    want = ask_number(f"1. 让{name}加入  2. 不用了  ", 1, 2) == 1
    if want and not make_room(game, name):   # 先问带不带, 带的话车上坐不下再问要不要丢东西
        print(f"{name} 摇摇头, 留在了{place}。")
        return
    if want:
        game["party"][name] = 100
        game["jobs"][name] = job
        print(f"{name} 带着自己的{brings}加入了队伍!")
        for item, amount in RECRUIT_BRINGS.items():
            add_supplies(game, item, amount)
        write_diary(game, f"{job}{name}在{place}加入了队伍。", km)
        if len(game["party"]) >= MAX_PARTY:
            unlock("满员")
    else:
        print(f"{name} 点点头, 留在了{place}。")


# ========== 过河 ==========

def usual_depth(game, place):
    """这几天这条河大概有多深 (米): 平常的水深, 按月份涨落, 这几天下了雨雪还会涨。没算每天的随机变化"""
    month = date_of(game)[0]
    return RIVERS[place][2] * RIVER_SEASON[month - 1] * (1 + RAIN_RISE * game["rain"])


def river_depth(game, place):
    """今天这条河有多深 (米, 只留一位小数): 大概的水深 (usual_depth), 每天再有一点随机变化"""
    return round(usual_depth(game, place) * random.uniform(0.85, 1.15), 1)


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
    game["ferries"] += 1
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
        if game["difficulty"] in NO_DROWNING:
            print(f"{victim} 差点被急流冲走, 好在死死抓住了车门。")
        else:
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
    if not game["rocks"]:
        unlock("激流勇进")


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
    game["rocks"] += 1
    s = game["supplies"]
    lost = []
    for item in random.sample([item for item in s if s[item]], min(2, sum(1 for item in s if s[item]))):
        amount = max(1, s[item] * random.randint(20, 50) // 100)
        s[item] -= amount
        lost.append(f"{amount} {MEASURES[item]}{item}")
    if lost:
        print(f"掉进河里冲走了: {'、'.join(lost)}。")
    victim = random_member(game)
    if random.random() < RAPID_HIT_DROWN and game["difficulty"] not in NO_DROWNING:
        lose_member(game, victim, "掉进了哥伦比亚河, 被急流冲走了。")
    else:
        print(f"{victim} 撞伤了, 还呛了几口带辐射的河水。")
        irradiate(game, victim, RIVER_RADS)
        hurt(game, victim, random.randint(10, 20))
    write_diary(game, "木筏在哥伦比亚河的急流里撞上了礁石。")


# ========== 随机事件(想加新事件就照着写一个函数, 再放进 EVENTS (大事) 或者 SMALL_EVENTS (小事)) ==========
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
    """路上碰到流浪商人, 跟每天的菜单里的「交易」一样换东西, 只是不用专门花一天"""
    offer_trade(game, "一个背着大包的流浪商人", heading=f"\n{title('流浪商人')}")


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
    print("多一个人能多一份力气, 但每天也要多吃多喝。")
    if ask_number(f"1. 让{name}加入  2. 拒绝  ", 1, 2) == 2:
        print(f"{name} 失望地走开了。")
        return
    if not make_room(game, name):   # 先问带不带, 带的话车上坐不下再问要不要丢东西 (不然丢了东西又不带人, 白丢了)
        print(f"只能让 {name} 自己走了。")
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
        if len(game["party"]) >= MAX_PARTY:
            unlock("满员")


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


def lost_way(game):
    """迷路 (原版的 Lose trail): 白白耗掉几天"""
    print(f"\n{title('迷路', '红')}旧公路的路牌早就倒了, 风沙又把路埋了一大半。{you(game)}绕来绕去, 迷了路……")
    hunter = skilled(game, "猎人")
    days = 1 if hunter else random.randint(*LOST_DAYS)
    if hunter:
        print(f"猎人{hunter}看着太阳和远处的山认出了方向, 只耽误了一天。")
    write_diary(game, f"迷了路, 耽误了 {days} 天。")   # 会花好几天的事, 在开始那天记
    for _ in range(days):
        pass_day(game, traveling=True)
        if not game["party"]:
            return
    print(f"花了 {days} 天, 才找回原来的路。")


def car_fire(game):
    """车着火 (原版的马车着火): 烧掉一样东西的一部分"""
    s = game["supplies"]
    print(f"\n{title('车着火了', '红')}发动机过热, 车厢里冒出了黑烟, 火苗窜了起来!")
    mechanic = skilled(game, "机械师")
    if mechanic:
        print(f"机械师{mechanic}抓起灭火毯扑了上去, 火很快就灭了。")
    burning = [item for item in s if s[item] > 0]
    amount = 0
    if burning:
        item = random.choice(burning)
        amount = s[item] * random.randint(*FIRE_BURN) // 100
        if mechanic:
            amount //= 2
        s[item] -= amount
    if amount:
        print(f"烧掉了 {amount} {MEASURES[item]}{item}。")
        write_diary(game, f"车着火了, 烧掉了 {amount} {MEASURES[item]}{item}。")
    else:
        print("幸好没烧掉什么东西。")
        write_diary(game, "车着火了, 幸好没烧掉什么东西。")


def thief(game):
    """夜里有小偷 (原版的 Thief comes during the night)"""
    s = game["supplies"]
    print(f"\n{title('小偷', '红')}夜里, 有人悄悄摸到了车边……")
    veteran = skilled(game, "老兵")
    if veteran:
        print(f"老兵{veteran}在守夜, 朝天开了一枪, 小偷吓得什么都没拿就跑了。")
        write_diary(game, f"夜里来了小偷, 被守夜的老兵{veteran}吓跑了。")
        return
    have = [item for item in s if s[item] > 0]
    if not have:
        print("小偷翻了半天, 什么都没找到, 骂骂咧咧地走了。")
        return
    item = random.choice(have)
    amount = max(1, s[item] * random.randint(*THEFT) // 100)
    s[item] -= amount
    print(f"第二天早上一看, 少了 {amount} {MEASURES[item]}{item}!")
    write_diary(game, f"夜里来了小偷, 偷走了 {amount} {MEASURES[item]}{item}。")


def wild_food(game):
    """找到吃的 (原版的找到野果): 废弃农场里自己长出来的庄稼"""
    print(f"\n{title('找到吃的', '绿')}路边一个废弃的农场里, 地里自己长出了一片土豆和玉米。"
          "盖革计数器只轻轻响了几下, 还能吃。")
    food = add_supplies(game, "食物", random.randint(*WILD_FOOD))
    if food:
        print(f"{you(game)}挖了 {food} 份带上车。")
        write_diary(game, f"在一个废弃的农场里挖到 {food} 份能吃的。")


def clean_spring(game):
    """找到干净的水"""
    print(f"\n{title('干净的泉水', '绿')}岩缝里流出一股泉水, 盖革计数器一声都没响!")
    water = add_supplies(game, "水", random.randint(*SPRING_WATER))
    if water:
        print(f"{you(game)}装了 {water} 份水。")
        write_diary(game, f"找到一股干净的泉水, 装了 {water} 份水。")


def abandoned_car(game):
    """废弃的车 (原版的 Find an abandoned wagon): 车上还剩些东西, 也许还能拆个零件"""
    print(f"\n{title('废弃的车')}路边翻倒着一辆被扔下的旧车, 车门还开着。")
    got = 0   # 一共拿上车几样
    if random.random() < 0.5:
        if add_supplies(game, "零件", 1):
            print("从车上拆下了 1 个还能用的零件!")
            got += 1
    if find_supplies(game):
        got += 1
    if got:
        write_diary(game, "在路边一辆被扔下的旧车里找到了一些东西。")


def rough_road(game):
    """路太难走 (原版的 Rough trail): 慢慢开要多花一天, 硬冲过去可能把车颠坏"""
    print(f"\n{title('路太难走')}前面一段公路被炸得坑坑洼洼, 还有一半塌进了沟里。")
    if ask_number("1. 慢慢开过去 (多花 1 天)  2. 冲过去 (车可能会颠坏)  ", 1, 2) == 1:
        write_diary(game, "一段烂路, 慢慢开了一整天。")
        pass_day(game, traveling=True)
        if game["party"]:
            print(f"{you(game)}一点一点地把车挪了过去, 花了一整天。")
        return
    if random.random() < ROUGH_ROAD_BREAK:
        print("哐当一声, 车颠坏了!")
        breakdown(game)
    else:
        print("车颠得厉害, 好在冲过去了, 什么都没坏。")


def snake_bite(game):
    """被蛇咬 (原版的 Snakebite)"""
    victim = random_member(game)
    print(f"\n{title('毒蛇', '红')}{victim} 下车找柴火的时候, 被一条变异的响尾蛇咬了一口!")
    write_diary(game, f"{victim} 被变异的响尾蛇咬了。")
    doctor = skilled(game, "医生")
    if doctor:
        print(f"医生{doctor}马上把毒血挤了出来, 伤口包扎得很干净。")
    hurt(game, victim, random.randint(*SNAKE_BITE))
    if not doctor and victim in game["party"] and random.random() < sick_odds(game, INFECTION_CHANCE):
        get_sick(game, victim, "伤口感染")


EVENTS = [raiders, breakdown, warehouse,
          mutant_attack, radiation_sickness, bad_water, trader,
          stranger, minefield, radio_signal]
SMALL_EVENTS = [lost_way, car_fire, thief, wild_food, clean_spring, abandoned_car, rough_road, snake_bite]


def random_event(game, km):
    """路上发生随机事件的机会跟开了多远有关: 每开 100 公里, 大约有 35% 的机会遇到大事 (简单难度少一些, 困难多一些);
    没遇到大事的话, 还有 15% 的机会遇到小事 (有好有坏, 不分难度)。
    这样开得慢不会因为在路上的天数多, 就遇到更多倒霉事"""
    if not game["party"]:
        return
    chance = EVENT_CHANCE_PER_100KM * km / 100 * DIFFICULTIES[game["difficulty"]][2] / 100
    if random.random() < chance:
        event_screen()
        random.choice(EVENTS)(game)
    elif random.random() < SMALL_EVENT_CHANCE_PER_100KM * km / 100:
        event_screen()
        random.choice(SMALL_EVENTS)(game)


# ========== 结局 ==========

def arrive(game):
    """到达俄勒冈城, 根据路上的情况决定是哪个结局。返回结局的名字 (比如"完美结局"), 记最高分时要用"""
    last_day = game["day"] - 1
    new_screen()
    play_music("到达")
    show_picture(CITY_ART, "绿")
    print(f"\n{date_text(game, last_day)}, {you(game)}到达了{DESTINATION}! 一共用了 {last_day} 天。")
    write_diary(game, f"到达了{DESTINATION}! 政府收下了{'、'.join(game['party'])}。", day=last_day)
    print(f"活下来的人: {'、'.join(game['party'])}")
    if game["dead"]:
        print(f"路上失去的人: {'、'.join(game['dead'])}")
    if game["leader"] in game["dead"]:
        print(f"{game['leader']} 没能走到这里, 是同伴们替{game['leader']}走完了这条路。")
    print(colored(f"城门口站着政府的士兵。原来, {DESTINATION}是美国政府的后备据点。", "黄"))
    print(f"那个消息是真的: 政府收下了{you(game)}。从明天起, {you(game)}就要在{DESTINATION}干活了。")

    if game["seeds"]:
        ending = "隐藏结局"
        print("\n" + title("隐藏结局: 绿色的希望", "绿"))
        print("政府的科学家打开种子库, 激动得说不出话。")
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


def load_achievements():
    """读拿到过的成就: 名字的列表 (按拿到的先后)。没有文件或者文件坏了, 就当一个都没拿到"""
    try:
        with open(ACHIEVEMENT_FILE, encoding="utf-8") as f:
            got = json.load(f)
    except (OSError, ValueError):
        return []
    if not isinstance(got, list):
        return []
    return [name for name in got if name in ACHIEVEMENTS]


def save_achievements(got):
    try:
        with open(ACHIEVEMENT_FILE, "w", encoding="utf-8") as f:
            json.dump(got, f, ensure_ascii=False)
    except OSError:
        print("成就没能存下来, 可能是文件夹不能写入。")


def unlock(name, quiet=False):
    """拿到一个成就: 以前没拿到过的就记下来, 告诉玩家 (quiet=True 先不说)。返回是不是这次新拿到的"""
    got = load_achievements()
    if name in got:
        return False
    save_achievements(got + [name])
    if not quiet:
        print(colored(f"★ 新成就: {name} —— {ACHIEVEMENTS[name]}", "黄", bold=True))
    return True


def arrival_achievements(game, ending):
    """走到俄勒冈城以后: 看看这一局拿到了哪些成就, 新拿到的写出来"""
    checks = {
        "终于到了": True,
        "一个都不少": ending == "完美结局",
        "独行侠": ending == "独行结局",
        "绿色的希望": ending == "隐藏结局",
        "硬骨头": game["difficulty"] == 3,
        "快马加鞭": game["day"] - 1 <= FAST_ARRIVAL_DAYS,
        "自己过河": not game["ferries"],
        "抄近路": game["cutoff"] == 2,
    }
    new = [name for name, ok in checks.items() if ok and unlock(name, quiet=True)]
    if new:
        print("\n========== 新成就 ==========")
        for name in new:
            print(colored(f"★ {name} —— {ACHIEVEMENTS[name]}", "黄", bold=True))
    return new


def show_achievements():
    """主菜单里的「最高分和成就」的第二页: 一共有哪些成就, 拿到了哪些"""
    got = load_achievements()
    print(f"\n========== 成就 (拿到了 {len(got)} 个, 一共 {len(ACHIEVEMENTS)} 个) ==========")
    for name, how in ACHIEVEMENTS.items():
        if name in got:
            print(colored(f"★ {name}", "黄", bold=True) + f": {how}")
        else:
            print(colored(f"☆ {name}: {how}", "灰"))


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


settings = dict(DEFAULT_SETTINGS)   # 现在的设置 (main() 一开始从 SETTINGS_FILE 读)


def load_settings():
    """读主菜单「设置」里改过的东西。没有设置文件、文件坏了、哪一项不对, 就用原来的"""
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            saved = json.load(f)
    except (OSError, ValueError):
        return
    if not isinstance(saved, dict):
        return
    if saved.get("difficulty") in DIFFICULTIES:
        settings["difficulty"] = saved["difficulty"]
    if saved.get("unit") in UNITS:
        settings["unit"] = saved["unit"]
    for key in ["music", "animation", "window"]:
        if isinstance(saved.get(key), bool):
            settings[key] = saved[key]


def save_settings():
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False)
    except OSError:
        print("\n设置存不下来 (文件夹不能写入), 这次关掉游戏以后就忘了。")


def settings_menu():
    """主菜单的「设置」: 难度、距离单位、音乐、过场动画。改了马上记下来, 下次打开游戏还是这样。
    网页版的音乐用网页右上角的「♪」开关, 这里就不放了"""
    while True:
        new_screen()
        name, money, *_ = DIFFICULTIES[settings["difficulty"]]
        on = {True: "开", False: "关"}
        items = [("难度", f"难度: {name} (一开始有 {money} 块钱; 以后开新游戏用, 已经开始的那一局不变)"),
                 ("单位", f"距离单位: {settings['unit']} (重量也跟着变: 公里配公斤, 英里配磅)")]
        if not IN_BROWSER:
            items.append(("音乐", f"音乐: {on[settings['music']]}"))
        items.append(("动画", f"过场动画: {on[settings['animation']]} (关了以后, 赶路、过河这些动画不放, 画一下子画出来)"))
        if not IN_BROWSER and not msvcrt:
            items.append(("窗口", f"自动调整窗口大小: {on[settings['window']]} (窗口太小的时候, 一打开游戏就把它调大)"))
        print("\n------ 设置 ------")
        for number, (_, words) in enumerate(items, 1):
            print(f"{number}. {words}")
        if IN_BROWSER:
            print("音乐: 点网页右上角的「♪」开关")
        print("0. 回到主菜单")
        choice = ask_number("改哪一项? ", 0, len(items))
        if choice == 0:
            return
        what = items[choice - 1][0]
        if what == "难度":
            settings["difficulty"] = choose_difficulty()
        elif what == "单位":
            settings["unit"] = "公里" if ask_number("距离单位: 1. 公里  2. 英里  ", 1, 2) == 1 else "英里"
        elif what == "音乐":
            settings["music"] = not settings["music"]
            if settings["music"]:
                play_music("主菜单")
            else:
                stop_music()
        elif what == "窗口":
            settings["window"] = not settings["window"]
            fit_window()
        else:
            settings["animation"] = not settings["animation"]
        save_settings()


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
    if "here" not in saved:   # 以前的存档不知道车停在哪, 只知道还没出发的话是在起点
        game["here"] = START_PLACE if game["distance"] == 0 else None
    game["unit"] = settings["unit"]   # 距离单位在主菜单的「设置」里改, 接着玩的存档也跟着变
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
    return MUSIC and settings["music"] and (can_read_keys() or IN_BROWSER)


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


def can_show_pictures():
    """能不能显示画 (地标的画、每个人的样子……): 在真正的终端里或者网页版里 (跑测试时不显示)"""
    return can_read_keys() or IN_BROWSER


def can_animate():
    """能不能播动画 (赶路、过河、主菜单的小动画, 画一行一行地画出来): 设置里没关掉, 而且能显示画"""
    return ANIMATION and settings["animation"] and can_show_pictures()


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
    # 据点: 卡尼堡是幸存者用废铁、旧轮胎和沙袋重新围起来的堡垒和贸易站;
    # 拉勒米堡往西是美国政府重新占领的基地, 每个都不一样 (说明在 BASE_NOTES): 检查站、修车场、信号站和直升机、抽水站、河港
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
                                     |>>>>>>
    .-----.         ______________   |
    | (o) |        | FORT LARAMIE |  |
    |_____|        |  CHECKPOINT  |  |
     |   |         |ALL CARS STOP!|  |
     |   |         |______________|  |
     |   |   ___       ||    ||      |
     |   |  |___|==============================o
 -x--|---|--x-|-|-x-----x-----x-----x-----x-----x-
_____|___|____|_|_________________________________
"""), None),
    "布里杰堡": (picture(r"""
       /\           /\      /\                |>>>
      /  \    /\   /  \    /  \               |
 ____/____\__/__\_/____\__/____\______________|___
|          FORT BRIDGER  *  MOTOR POOL            |
|   ____________     ____________     ______      |
|  |   ______   |   |   ______   |   | FUEL |     |
|  |  |______|__|   |  |______|__|   |  ()  |     |
|  |__(o)___(o)_|   |__(o)___(o)_|   |______|     |
|_________________________________________________|
"""), None),
    "霍尔堡": (picture(r"""
        /\                     ---------+---------
       /||\        .---.            ____|____
      / || \      ( (o) )          /  []     \____.
     /  ||  \      '---'           \_________/
    /   ||   \       ||              _|_   _|_
 __/____||____\______||___      ==================
|  FORT HALL   SIGNAL STN |    |       H          |
|  [ ]   [ ]   [ ]   [ ]  |    |    HELIPAD       |
|_________________________|____|__________________|
"""), None),
    "博伊西堡": (picture(r"""
      .------.         ___     ___     ___
     | WATER  |       |   |   |   |   |   |
      '------'        |___|   |___|   |___|
        |  |     _______|_______|_______|______
        |  |    | FORT BOISE   *  WATER WORKS  |
       /|  |\   |  [ ]   [ ]   [ ]   [ ]   [ ] |
 _____/_|__|_\__|______________________________|___
  ~   ~~  ~   ~~~  ~  ~~~ ======PIPE====== ~  ~~~
 ~~  ~   ~~~  ~   ~~  ~   ~~~  ~   ~~  ~   ~~  ~
"""), None),
    "达尔斯": (picture(r"""
    _________________                |>>>>
    |               |                |
    |               o    ____________|______________
    |                   | THE DALLES  *  RIVER PORT |
    |                   |  [ ]   [ ]   [ ]    [ ]   |
 ___|___________________|___________________________|_
 ~~~~~~~~~~ ____/[]\____ ~~~~~ <=O==O==O==O=> ~~~~~~~~~
  ~   ~~    \__________/  ~~   ~   ~~  ~  ~~~   ~  ~
"""), None),
}

# 出发的地方: 独立城外面山坡上避难所的大门, 路边一块牌子
START_ART = picture(r"""
            _.-''''''''''''-._           ______________
        _.-'    .--------.    '-._      | INDEPENDENCE |
     .-'      .'  .----.  '.      '-.   |______MO______|
   .'        /   /  ()  \   \        '.       ||
  /         |   |  -/\-  |   |         \      ||
_/__________|___|________|___|__________\_____||_______
""")

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
# 打猎时的动物: 头朝左 (往右跑的时候左右翻过来), 每种两帧, 腿一前一后地动
ANIMAL_ART = {
    "变异野兔": [["(\\_/)", "(oOo)", ' " " '],
                 ["(\\_/)", "(oOo)", '"   "']],
    "双头鹿": [[" Y  Y", "<o><o>____", "   (______)", "    |\\  |\\"],
               [" Y  Y", "<o><o>____", "   (______)", "    /|  /|"]],
    "辐射野猪": [["   _______", "<(o       )~", "  ||    ||"],
                 ["   _______", "<(o       )~", "  //    //"]],
}
ANIMAL_COLORS = {"变异野兔": None, "双头鹿": "黄", "辐射野猪": "红"}
MIRROR = str.maketrans("()<>/\\[]{}", ")(><\\/][}{")   # 画左右翻过来的时候, 这些字也要换成反方向的


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
    """显示一幅画, 一行一行地慢慢画出来 (设置里关了动画就一下子画出来); words 是写在画右边的字。跑测试时不显示"""
    if not can_show_pictures():
        return
    print()
    for row in beside(art, words or [], color):
        print(row)
        if can_animate():
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
        put("\x1b7\x1b[?25l" + f"\x1b[{lines_up}A\r" + "\n".join(frames[counter[0]]) + "\x1b8\x1b[?25h",
            flush=True, log=False)
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
2030 年, 一场核战争毁灭了旧世界。二十年后, 你被人栽赃, 赶出了独立城的避难所。
听说俄勒冈那边有官方的人在收人, 你开着捡来的车, 沿着当年拓荒者走过的俄勒冈小道,
去 {TOTAL_DISTANCE} 公里 ({miles} 英里) 外的{DESTINATION}。只要还有人活着走到, 就算成功。

难度在主菜单的「设置」里选 ({difficulties}):
越难, 一开始的钱越少, 路上出事、生病的机会越多。

每天可以选一件事做:
  继续前进  开车赶路, 要用燃料。开得越快越费燃料, 人也越累。
            车会像原版那样一直往前开, 出了事说一声, 看完接着开; 到了地方就停。
            想停下来休息、用药、看看情况, 就按回车 (网页版点一下屏幕)
  休息      躲在车里养伤养病, 不怕风吹雨打。一次最多 {MAX_REST_DAYS} 天, 出了事就停下来
  搜刮废墟  也许能找到物资, 也可能碰上危险
  打猎      方向键移动准星, 空格开枪 (网页版用鼠标或手指点), 打中动物就有肉
  交易      花一天找人换东西, 换不换你定 (在路上不一定碰得到人)
  用药      药品治病治伤, 排辐剂排辐射, 自己选给谁用
  和人说话  车停在地标、据点时, 听那里的人说说前面的路况、天气、河有多深
  还可以改变口粮和速度、丢东西、查看队伍、看旅行日记、存档, 这几样都不花时间
""")
    new_screen()   # 一页放不下, 分成三页
    print(f"""
路上要注意:
  - 每人每天都要吃要喝。天热要多喝水, 天冷要多吃东西, 还得每人一套冬衣
  - 车最多装 {capacity_kg} 公斤 ({capacity_lb} 磅), 人也算在里面。燃料最重, 要算好在哪里补给
  - 没燃料了就去搜刮废墟, 会专门到废车里抽油。停在据点时, 随时能买卖东西
  - 天气按走到哪里、几月份变。坏天气车开得慢, 酸雨和辐射风暴天最好躲在车里
  - 辐射会在身体里越积越多, 只有排辐剂能排掉
  - 有 {len(HOTSPOTS)} 段路靠近核设施, 辐射偏高 (状态栏会提前提醒), 开快点、躲在车里能少受些;
    开到跟前也可以绕路, 多开一天左右, 那一带的辐射就不用受了
  - 过了{CUTOFF_FROM}可以走萨布莱特捷径: 少走一段路, 可是有一段找不到水,
    也不经过{CUTOFF_SKIPS}
  - 健康越差越容易生病。生病了要休息, 或者用药品治
  - 路上要过 5 条大河: 水浅就直接开过去, 水深就绑上空油桶浮过去 (可能翻车),
    有的河边有渡船, 花钱最安全。化雪、下雨以后河水会涨, 等几天也许会退
  - 据点能买东西, 也能卖掉用不上的东西 (只给独立城一半的价钱)
  - 越往西, 据点的东西越贵 ({LAST_ROAD_FROM}是独立城的 {OUTPOST_PRICES[LAST_ROAD_FROM] / 100:g} 倍), 能早买就早买
  - 每个据点有一个人愿意跟你走。带上队友更安全; 一个人走省吃省喝, 病了没人照顾
  - 到了{LAST_ROAD_FROM}, 可以扎木筏顺哥伦比亚河漂下去 (要躲礁石), 也可以交过路费走巴洛路
  - 3 月出发天冷, 7 月出发天热, 4~6 月最好走
""")
    new_screen()
    print(f"""
走到{DESTINATION}才算分: 活下来的人越多、越健康分越高, 剩下的物资和钱也能换成分。
最后再按难度乘一下: {scores}。
主菜单的「最高分和成就」里记着前 {HIGH_SCORES} 名, 还有 {len(ACHIEVEMENTS)} 个成就, 看看你拿到了几个。

主菜单的「设置」里还能换距离单位 (公里或英里)、关掉音乐和过场动画。
网页版的音乐用右上角的「♪」开关。

在 Mac 的终端里玩, 窗口太小时游戏一打开会把它调大 (设置里可以关掉);
字太小就按 Command 和加号键。窗口够大的时候, 每个画面都摆在窗口中间的方框里;
每天的菜单和开车的画面是分成几块的大画面: 动画、状态、路线图、最近的事。
网页版本来就有这些面板。
""")
    wait_enter("按回车回到主菜单……")


# ========== 主菜单和主循环 ==========

def main():
    """主菜单: 开始新游戏、继续游戏、看说明, 或者退出。一局玩完会回到这里"""
    enable_ansi()   # 颜色和动画都要用控制字符, Windows 的终端要先打开这个开关
    screen["unread"] = False   # 刚打开游戏, 屏幕上还没有要看的字
    load_settings()
    fit_window()
    while True:
        new_screen()
        play_music("主菜单")
        columns, rows = screen_size()
        if layout["on"] and (columns >= WINDOW_COLUMNS + 30 or rows >= WINDOW_ROWS + 12):   # 窗口比游戏大很多 (多半是全屏)
            keys = "Command" if sys.platform == "darwin" else "Ctrl"
            print(colored(f"字太小? 按住 {keys} 键, 再按几下加号键 (+), 字会变大, 方框跟着变大;", "灰"))
            print(colored(f"方框快占满窗口就行。放过头了就按 {keys} 和减号键 (-)。", "灰"))
        height = title_screen()
        saved = load_game()
        if saved:
            note = (f"{DIFFICULTIES[saved['difficulty']][0]}, {date_text(saved)}, "
                    f"已走 {show_distance(saved, saved['distance'])}")
        else:
            note = "没有存档"
        # 后面几个短的排成一行: 开始画面在 80x24 的终端里正好放得下, 还能播小动画
        menu = f"\n1. 开始新游戏\n2. 继续游戏 ({note})\n3. 游戏说明  4. 最高分和成就  5. 设置  6. 退出游戏"
        print(menu)
        choice = ask_number("选哪一项? ", 1, 6, idle=title_animation(height + menu.count("\n") + 1))
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
            new_screen()   # 第二页是成就
            show_achievements()
            wait_enter("按回车回到主菜单……")
        elif choice == 5:
            settings_menu()
        else:
            stop_music()
            print("\n下次再见!")
            leave_layout()
            return


def play(game):
    """玩一局, 直到走到终点、全军覆没, 或者存档后回到主菜单"""
    actions = {1: travel, 2: rest, 3: scavenge, 4: hunt, 5: trade, 6: take_medicine,
               7: change_ration, 8: change_pace, 9: drop, 10: talk, 11: show_party, 12: show_diary, 14: shop_here}
    ending = None   # 走到终点时是哪个结局 (全军覆没就没有, 也不算分)
    play_music("赶路")

    while True:
        if not game["party"]:
            new_screen()
            play_music("全军覆没")
            show_picture(WIPEOUT_ART, "灰")
            print("\n" + title("结局: 全军覆没", "红"))
            print("所有人都死了。废土上又多了一辆空车……")
            unlock("前车之鉴")
            break
        if game["distance"] >= TOTAL_DISTANCE:
            ending = arrive(game)
            break

        new_screen(framed=not use_dashboard())   # 每天的菜单是一个画面: 上面是状态 (窗口够大就用大画面), 下面是选项
        if GUI:
            show_scene(game)
        elif use_dashboard():
            show_dashboard(game)
        else:
            show_status(game)
        # 第一行要花时间, 第二行不花时间, 第三行看看、存档
        print("1. 继续前进  2. 休息  3. 搜刮废墟  4. 打猎  5. 交易")
        print("6. 用药  7. 改变口粮  8. 改变速度  9. 丢东西  10. 和人说话")
        at_outpost = game["here"] in OUTPOST_NAMES   # 停在据点里, 还能进去买卖东西
        print("11. 查看队伍  12. 旅行日记  13. 存档" + ("  14. 买卖东西" if at_outpost else ""))
        choice = ask_number("你要做什么? ", 1, 14 if at_outpost else 13)
        if choice == 13:
            save_game(game)
            if ask_number("1. 继续玩  2. 回到主菜单  ", 1, 2) == 2:
                return
            continue
        new_screen()   # 做的事换一个画面
        actions[choice](game)

    delete_save()
    if ending:
        new_screen()   # 走到了: 先看看拿到了什么新成就 (没有新的就什么都不写)
        arrival_achievements(game, ending)
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
        leave_layout()
        print("\n\n游戏中途退出了, 下次再见!")
