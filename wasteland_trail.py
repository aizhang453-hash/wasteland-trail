"""
废土之旅
一个仿照《俄勒冈之旅》的文字冒险游戏。
运行方法: 在终端里输入 python wasteland_trail.py
"""

import json
import os
import random
import sys
import time

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

# 存档文件, 放在游戏文件旁边
SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "savegame.json")

# ========== 游戏设置(数字都可以随便改) ==========

# 路线是当年的俄勒冈小道: 从密苏里州独立城到俄勒冈城。
# 距离按 1847 年乔尔·帕尔默的拓荒指南里的路程表算 (经过布里杰堡的那条线)
DESTINATION = "俄勒冈城"
TOTAL_DISTANCE = 3119   # 到俄勒冈城的总路程(公里)
START_MONEY = 700       # 一开始的钱 (一个人出发, 一开始吃喝少)

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

# 商店价格(每个多少钱)
PRICES = {"食物": 1, "水": 1, "燃料": 4, "子弹": 1, "零件": 20, "药品": 15}

# 口粮: 编号 -> (名字, 每人每天吃几份, 每天健康变化)
RATIONS = {1: ("少", 1, -2), 2: ("普通", 2, 1), 3: ("饱", 3, 3)}

# 每开 100 公里, 遇到随机事件的机会
EVENT_CHANCE_PER_100KM = 0.35

# 速度: 编号 -> (名字, 车每天开几公里, 每天用几份燃料, 每天健康变化)
PACES = {1: ("慢", 90, 1, 1), 2: ("中", 105, 2, 0), 3: ("快", 120, 3, -2)}

# 天气: 名字 -> (出现的机会, 路程倍数, 每人多喝几份水, 在外面时每天健康变化, 说明)
WEATHER = {
    "晴朗":   (6, 1.0, 0, 0, "适合赶路"),
    "酷热":   (2, 1.0, 1, -1, "每人要多喝 1 份水"),
    "沙尘暴": (1, 0.5, 0, -2, "车只能开平时一半的路"),
    "酸雨":   (1, 0.7, 0, -5, "在外面会受伤, 休息可以躲雨"),
}

# 搜刮时可能找到的东西: 名字 -> (最少, 最多)
LOOT = {"食物": (10, 40), "水": (10, 30), "燃料": (3, 10),
        "子弹": (10, 30), "零件": (1, 1), "药品": (1, 2)}

# 打猎: 要飞快打出来的词, 和猎物: 名字 -> (最少食物, 最多食物)
HUNT_WORDS = ["bang", "pow", "boom", "zap"]
ANIMALS = {"变异野兔": (10, 25), "双头鹿": (30, 60), "辐射野猪": (50, 90)}

# 队伍最多几个人 (包括主角)
MAX_PARTY = 4

# 每个据点里有 1 个人愿意免费跟你走: 据点名字 -> (这个人的名字, 职业)
RECRUITS = {"卡尼堡": ("杰克", "老兵"), "拉勒米堡": ("玛莎", "医生"), "布里杰堡": ("埃迪", "机械师"),
            "霍尔堡": ("汉娜", "猎人"), "博伊西堡": ("本", "商人"), "达尔斯": ("罗莎", "拾荒者")}

# 职业的特长: 只要这个人还活着、在队伍里, 特长就一直有用
SKILLS = {
    "老兵": "遇到劫匪开枪一定能打赢, 赶走野狗只要 5 发子弹",
    "医生": "用药一次能恢复 60 点健康 (平时是 35)",
    "机械师": "车坏了不用零件也能当场修好",
    "猎人": "打猎得到的肉多一半",
    "商人": "在据点买东西打八折",
    "拾荒者": "搜刮废墟一定有收获, 一次能找到两样东西",
}

# 路上可能遇到的陌生人
STRANGER_NAMES = ["迈克", "安娜", "老乔", "凯特", "比尔"]


# ========== 小工具 ==========

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


def ask_number(prompt, low, high):
    """让玩家输入 low 到 high 之间的数字。
    只有数字键、退格键和回车有用, 按空格、字母这些键什么都不会发生;
    回车也只在输入的数字在范围里时才算数"""
    if not can_read_keys():
        return ask_number_by_line(prompt, low, high)
    print(prompt, end="", flush=True)
    old_settings = start_reading_keys()
    try:
        return read_number(low, high)
    finally:
        stop_reading_keys(old_settings)   # 不管怎么结束 (包括按 Ctrl+C), 都要把终端还原


def read_number(low, high):
    text = ""
    while True:
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
    game["diary"].append(f"第 {day} 天, 已走 {show_distance(game, km)}: {text}")


def show_diary(game):
    """查看旅行日记。不花时间"""
    print("\n========== 旅行日记 ==========")
    if not game["diary"]:
        print("日记里还什么都没有。")
    for line in game["diary"]:
        print(line)


def check_deaths(game):
    for name in list(game["party"]):
        if game["party"][name] <= 0:
            del game["party"][name]
            game["dead"].append(name)
            print(f"!!! {name} 没能撑下去, 去世了。")
            write_diary(game, f"{name} 去世了。")


def hurt(game, name, amount):
    """让一个队员掉血"""
    game["party"][name] = max(0, game["party"][name] - amount)
    check_deaths(game)


def change_all_health(game, amount):
    """所有队员的健康一起变化(正数是加, 负数是减)"""
    for name in game["party"]:
        game["party"][name] = max(0, min(100, game["party"][name] + amount))
    check_deaths(game)


def find_supplies(game):
    item = random.choice(list(LOOT))
    low, high = LOOT[item]
    amount = random.randint(low, high)
    game["supplies"][item] += amount
    print(f"找到了{item}, 一共 {amount} 个!")


def roll_weather(game):
    """随机决定明天的天气"""
    names = list(WEATHER)
    chances = [WEATHER[name][0] for name in names]
    game["weather"] = random.choices(names, chances)[0]


# ========== 开始游戏 ==========

def new_game():
    return {
        "day": 1,
        "distance": 0,
        "money": START_MONEY,
        "supplies": {item: 0 for item in PRICES},
        "party": {},        # 队员名字 -> 健康(0 到 100)
        "dead": [],         # 路上去世的人
        "ration": 2,
        "pace": 2,
        "weather": "晴朗",
        "visited": [],      # 已经到过的据点
        "seeds": False,     # 有没有找到种子库(隐藏结局)
        "gender": "男",     # 主角的性别
        "unit": "公里",     # 显示路程用的单位
        "leader": "",       # 主角的名字
        "jobs": {},         # 队员名字 -> 职业 (主角和路上的陌生人没有职业)
        "diary": [],        # 旅行日记: 路上发生的大事, 一条一条记下来
    }


def setup(game):
    unit = ask_number("距离单位: 1. 公里  2. 英里  ", 1, 2)
    game["unit"] = "公里" if unit == 1 else "英里"
    print("\n核战争已经过去二十年了。")
    print("你被赶出了密苏里州独立城地下的避难所。")
    print(f"你要一个人开车, 沿着当年拓荒者走过的俄勒冈小道, "
          f"去 {show_distance(game, TOTAL_DISTANCE)}外的{DESTINATION}。")
    print("路上的据点里也许能遇到愿意跟你走的人。\n")
    leader = input("你叫什么名字? (直接按回车就叫\"队长\") ").strip() or "队长"
    gender = ask_number("你的性别: 1. 男  2. 女  ", 1, 2)
    game["gender"] = "男" if gender == 1 else "女"
    game["leader"] = leader
    game["party"][leader] = 100
    write_diary(game, f"{leader}被赶出了独立城地下的避难所, 一个人踏上了俄勒冈小道。")

    print("\n出发前可以在营地买东西。")
    print("提示: 每人每天要吃食物、喝 1 份水, 车每天要用燃料。子弹可以打猎, 也可以防身。")
    shop(game)


def cost_of(game, item, amount):
    """买 amount 个 item 要花多少钱。队伍里有商人就打八折, 有零头往上算 1 块"""
    cost = amount * PRICES[item]
    if skilled(game, "商人"):
        cost = (cost * 8 + 9) // 10
    return cost


def shop(game):
    items = list(PRICES)
    while True:
        print(f"\n------ 商店 ------  你有 {game['money']} 块钱")
        merchant = skilled(game, "商人")
        if merchant:
            print(f"商人{merchant}帮你讲价, 买什么都打八折。")
        for i, item in enumerate(items, 1):
            print(f"{i}. {item}  {PRICES[item]} 块一个  (现在有 {game['supplies'][item]})")
        print("0. 离开商店")
        choice = ask_number("买什么? ", 0, len(items))
        if choice == 0:
            return
        item = items[choice - 1]
        most = game["money"] // PRICES[item]
        while cost_of(game, item, most + 1) <= game["money"]:   # 打折以后能多买几个
            most += 1
        amount = ask_number(f"买多少{item}? (最多 {most}) ", 0, most)
        game["supplies"][item] += amount
        game["money"] -= cost_of(game, item, amount)


def show_status(game):
    s = game["supplies"]
    left = TOTAL_DISTANCE - game["distance"]
    print(f"\n==== 第 {game['day']} 天 | 已走 {show_distance(game, game['distance'])}"
          f" | 还剩 {show_distance(game, left)} ====")
    print(f"天气: {game['weather']} ({WEATHER[game['weather']][4]})")
    print("物资: " + "  ".join(f"{k} {v}" for k, v in s.items()) + f"  钱 {game['money']}")
    people = []
    for n, h in game["party"].items():
        job = f"[{game['jobs'][n]}]" if n in game["jobs"] else ""
        people.append(f"{n}{job} {health_word(h)}({h})")
    print("队员: " + "  ".join(people))
    print(f"口粮: {RATIONS[game['ration']][0]}  速度: {PACES[game['pace']][0]}")
    name, km = next_place(game)
    shop_note = " (据点, 可以买东西)" if name in [n for n, _ in OUTPOSTS.values()] else ""
    print(f"下一站: {name}{shop_note}, 还有 {show_distance(game, km - game['distance'])}")
    if game["seeds"]:
        print("车上带着: 种子库的种子")


def health_bar(h):
    """把健康画成一条, 比如 72 -> [#######...]"""
    filled = round(h / 10)
    return "[" + "#" * filled + "." * (10 - filled) + "]"


def show_party(game):
    """查看队伍: 每个人的详细情况, 还有物资大概能撑多久。不花时间"""
    print("\n========== 队伍状态 ==========")
    for name, h in game["party"].items():
        tags = []
        if name == game["leader"]:
            tags.append("主角")
        if name in game["jobs"]:
            tags.append(game["jobs"][name])
        tag = f" ({'、'.join(tags)})" if tags else ""
        print(f"{name}{tag}  健康 {h} {health_word(h)}  {health_bar(h)}")
        if name in game["jobs"]:
            print(f"    特长: {SKILLS[game['jobs'][name]]}")
    average = sum(game["party"].values()) // len(game["party"])
    print(f"队伍整体: {health_word(average)} (平均健康 {average})")
    if game["dead"]:
        print(f"路上失去的人: {'、'.join(game['dead'])}")

    print("\n---------- 物资还能撑多久 ----------")
    s = game["supplies"]
    people = len(game["party"])
    ration_name, per_person, _ = RATIONS[game["ration"]]
    pace_name, km, fuel_per_day, _ = PACES[game["pace"]]
    food_per_day = people * per_person
    print(f"食物: {s['食物']} 份。口粮{ration_name}, 每天吃 {food_per_day} 份, 还够吃 {s['食物'] // food_per_day} 天")
    print(f"水: {s['水']} 份。每天喝 {people} 份 (酷热天要多喝), 还够喝 {s['水'] // people} 天")
    fuel_days = s["燃料"] // fuel_per_day
    print(f"燃料: {s['燃料']} 份。速度{pace_name}, 每天用 {fuel_per_day} 份, "
          f"还够开 {fuel_days} 天, 大约 {show_distance(game, fuel_days * km)}")
    print(f"药品 {s['药品']}  零件 {s['零件']}  子弹 {s['子弹']}  钱 {game['money']}")
    print(f"离{DESTINATION}还有 {show_distance(game, TOTAL_DISTANCE - game['distance'])}")


# ========== 每天发生的事 ==========

def pass_day(game, health_bonus=0, indoors=False):
    """过一天: 吃东西、喝水、更新健康, 再换成明天的天气。
    indoors=True 表示躲在车里, 不受天气伤害。"""
    s = game["supplies"]
    people = len(game["party"])
    _, per_person, ration_health = RATIONS[game["ration"]]
    _, _, extra_water, weather_health, _ = WEATHER[game["weather"]]
    change = ration_health + health_bonus
    if not indoors:
        change += weather_health

    # 食物和水不够的话, 有多少吃多少, 缺得越多健康掉得越多
    food_need = people * per_person
    if s["食物"] >= food_need:
        s["食物"] -= food_need
    else:
        change -= round(10 * (food_need - s["食物"]) / food_need)
        s["食物"] = 0
        print(f"食物不够了, {everyone(game)}在挨饿!")

    water_need = people * (1 + extra_water)
    if s["水"] >= water_need:
        s["水"] -= water_need
    else:
        change -= round(15 * (water_need - s["水"]) / water_need)
        s["水"] = 0
        print(f"干净的水不够了, {everyone(game)}渴得受不了!")

    change_all_health(game, change)
    game["day"] += 1
    roll_weather(game)


def travel(game):
    s = game["supplies"]
    _, km, fuel_need, pace_health = PACES[game["pace"]]
    if s["燃料"] < fuel_need:
        print("\n燃料不够, 车开不动了! 试试换慢一点的速度, 或者去搜刮废墟找燃料。")
        return
    s["燃料"] -= fuel_need
    weather = game["weather"]
    speed = WEATHER[weather][1]
    km = round((km + random.randint(-10, 10)) * speed)
    km = min(km, TOTAL_DISTANCE - game["distance"])   # 最后一段路不多算
    game["distance"] += km
    if speed < 1:
        print(f"\n{weather}里车开不快, 只往前开了 {show_distance(game, km)}。")
    else:
        print(f"\n车往前开了 {show_distance(game, km)}。")
    check_places(game)
    random_event(game, km)
    pass_day(game, pace_health)   # 一天结束: 吃喝、更新健康、换成明天的天气


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
    input("准备好了就按回车……")
    print(f"\n    >>> {word} <<<\n")
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
    elif seconds <= 3:
        print(f"砰! 只用了 {seconds:.1f} 秒, 一枪命中! 得到 {food} 份食物。")
        s["食物"] += food
        write_diary(game, f"打猎打到一只{animal}, 得到 {food} 份食物。")
    elif seconds <= 6:
        food //= 2
        print(f"用了 {seconds:.1f} 秒, 只打伤了它, 追了半天才拿回 {food} 份食物。")
        s["食物"] += food
        write_diary(game, f"打猎打伤了一只{animal}, 拿回 {food} 份食物。")
    else:
        print(f"用了 {seconds:.1f} 秒, 太慢了, 猎物早就跑了。")
    if hunter and typed == word and seconds <= 6:
        print(f"(猎人{hunter}帮忙收拾猎物, 肉多了一半。)")
    pass_day(game)


def use_medicine(game):
    s = game["supplies"]
    if s["药品"] == 0:
        print("\n你没有药品了。")
        return
    name = min(game["party"], key=game["party"].get)   # 找健康最低的人
    if game["party"][name] >= 100:
        print("\n现在没人受伤, 不需要用药。")
        return
    s["药品"] -= 1
    doctor = skilled(game, "医生")
    heal = 60 if doctor else 35
    game["party"][name] = min(100, game["party"][name] + heal)
    if doctor:
        print(f"\n医生{doctor}给 {name} 用了药, {name} 好多了。")
    else:
        print(f"\n你给 {name} 用了药, {name} 感觉好多了。")


def change_ration(game):
    print("\n口粮: 1. 少  2. 普通  3. 饱")
    game["ration"] = ask_number("选哪个? ", 1, 3)


def change_pace(game):
    print("\n速度:")
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
    """路过风景地标会介绍一下, 到了据点还可以进去买东西。
    一天可能连着经过好几个地方, 所以把地标和据点放在一起, 按路程从近到远排好再一个个看"""
    places = [(km, name, intro, False) for km, (name, intro) in LANDMARKS.items()]
    places += [(km, name, intro, True) for km, (name, intro) in OUTPOSTS.items()]
    for km, name, intro, can_shop in sorted(places):
        if not reached(game, km, name):
            continue
        if not can_shop:
            print(f"\n{you(game)}经过了【{name}】。{intro}")
            write_diary(game, f"经过了{name}。", km)
            continue
        print(f"\n{you(game)}到了【{name}】。{intro}")
        write_diary(game, f"到了{name}。", km)
        offer_recruit(game, name, km)
        if ask_number("这里有幸存者在做买卖, 要进去买东西吗? 1. 要  2. 不要  ", 1, 2) == 1:
            shop(game)


def offer_recruit(game, place, km=None):
    """据点里有个人愿意免费跟你走, 车上坐满了就带不了"""
    if place not in RECRUITS:
        return
    name, job = RECRUITS[place]
    while name in game["party"] or name in game["dead"]:   # 跟主角或别人重名就加个 2
        name += "2"
    if len(game["party"]) >= MAX_PARTY:
        print(f"这里有个叫 {name} 的{job}也想往西走, 可惜你们的车已经坐满了。")
        return
    print(f"这里有个叫 {name} 的{job}也想往西走, 愿意跟{you(game)}一起。")
    print(f"特长: {SKILLS[job]}。但多一个人, 每天也要多吃多喝。")
    if ask_number(f"1. 让{name}加入  2. 不用了  ", 1, 2) == 1:
        game["party"][name] = 100
        game["jobs"][name] = job
        print(f"{name} 加入了队伍!")
        write_diary(game, f"{job}{name}在{place}加入了队伍。", km)
    else:
        print(f"{name} 点点头, 留在了{place}。")


# ========== 随机事件(想加新事件就照着写一个函数, 再放进 EVENTS) ==========

def radiation_storm(game):
    days = random.randint(1, 2)
    print(f"\n【辐射风暴】天空变成了绿色! {you(game)}躲了 {days} 天, 还是受到了辐射。")
    write_diary(game, f"遇到辐射风暴, 躲了 {days} 天。")
    for _ in range(days):
        pass_day(game, indoors=True)
    change_all_health(game, -10)


def raiders(game):
    s = game["supplies"]
    print("\n【劫匪】一伙劫匪拦住了路!")
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
    print("\n【车坏了】车子突然停下, 冒出一股黑烟!")
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
    print("\n【废弃仓库】路边有一个没被搜过的旧仓库!")
    write_diary(game, "发现一个没被搜过的旧仓库, 找到了一些物资。")
    for _ in range(2):
        find_supplies(game)


def mutant_attack(game):
    s = game["supplies"]
    print("\n【变异野兽】一群变异野狗冲了过来!")
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


def radiation_sickness(game):
    victim = random_member(game)
    print(f"\n【辐射病】{victim} 开始掉头发、发烧, 得了辐射病。")
    write_diary(game, f"{victim} 得了辐射病。")
    hurt(game, victim, 25)


def bad_water(game):
    s = game["supplies"]
    lost = s["水"] // 4
    s["水"] -= lost
    print(f"\n【水被污染】一桶水漏进了脏东西, 倒掉了 {lost} 份水。")
    write_diary(game, f"一桶水被污染了, 倒掉了 {lost} 份水。")


def trader(game):
    s = game["supplies"]
    print("\n【流浪商人】一个背着大包的流浪商人凑了过来:")
    print(f"「{pick(game, '老兄', '妹子')}, 20 份食物换 8 份燃料, 换不换?」")
    if s["食物"] < 20:
        print("可惜你的食物不够, 换不了。")
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
    print(f"\n【陌生人】路边有个叫 {name} 的幸存者, 想跟{you(game)}一起走。")
    print(f"「{pick(game, '大哥', '大姐')}, 带上我吧, 我什么活都能干!」")
    if len(game["party"]) >= MAX_PARTY:
        print(f"可惜车上已经坐满了, 只能让 {name} 自己走。")
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
    print("\n【雷区】路边插着一块歪掉的牌子: \"小心地雷\"。")
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
    else:
        print(f"{you(game)}小心翼翼地开了过去, 什么都没炸。")
        write_diary(game, "冒险开过了一片雷区, 平安无事。")


def radio_signal(game):
    print("\n【神秘无线电】收音机里传来断断续续的声音, 好像在说附近有个旧世界的地堡。")
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


EVENTS = [radiation_storm, raiders, breakdown, warehouse,
          mutant_attack, radiation_sickness, bad_water, trader,
          stranger, minefield, radio_signal]


def random_event(game, km):
    """路上发生随机事件的机会跟开了多远有关: 每开 100 公里, 大约有 35% 的机会。
    这样开得慢不会因为在路上的天数多, 就遇到更多倒霉事"""
    if game["party"] and random.random() < EVENT_CHANCE_PER_100KM * km / 100:
        random.choice(EVENTS)(game)


# ========== 结局 ==========

def arrive(game):
    """到达俄勒冈城, 根据路上的情况决定是哪个结局"""
    print(f"\n{you(game)}到达了{DESTINATION}! 一共用了 {game['day'] - 1} 天。")
    write_diary(game, f"到达了{DESTINATION}!", day=game["day"] - 1)
    print(f"活下来的人: {'、'.join(game['party'])}")
    if game["dead"]:
        print(f"路上失去的人: {'、'.join(game['dead'])}")
    if game["leader"] in game["dead"]:
        print(f"{game['leader']} 没能走到这里, 是同伴们替{game['leader']}走完了这条路。")

    if game["seeds"]:
        print("\n【隐藏结局: 绿色的希望】")
        print("城里的科学家打开种子库, 激动得说不出话。")
        print("第二年春天, 城墙外第一次长出了麦子。废土开始变绿了。")
    elif not game["dead"] and len(game["party"]) == 1:
        print("\n【独行结局: 一个人走完全程】")
        print("没有人陪你, 也没有人掉队。你一个人走完了整条俄勒冈小道。")
    elif not game["dead"]:
        print("\n【完美结局: 一个都不少】")
        print("所有人都平安到达。城门打开的那一刻, 大家抱在一起哭了。")
    elif len(game["party"]) == 1:
        name = list(game["party"])[0]
        print("\n【孤独结局: 最后一个人】")
        print(f"{name} 一个人走进城门, 身后的车里空荡荡的。")
        print("活下来的人, 要带着所有人的那一份继续活下去。")
    else:
        print("\n【普通结局: 带着伤痕到达】")
        print("你们活下来了, 但这条路让每个人都付出了代价。")


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
    return game


def delete_save():
    """一局玩完就删掉存档, 不能读档重来"""
    if os.path.exists(SAVE_FILE):
        os.remove(SAVE_FILE)


# ========== 主循环 ==========

def main():
    print("========== 废土之旅 ==========")
    game = load_game()
    if game:
        print(f"发现存档: 第 {game['day']} 天, 已经走了 {show_distance(game, game['distance'])}。")
        if ask_number("1. 继续上次的游戏  2. 开始新游戏  ", 1, 2) == 2:
            game = None
    if not game:
        game = new_game()
        setup(game)
    actions = {1: travel, 2: rest, 3: scavenge, 4: hunt, 5: use_medicine,
               6: change_ration, 7: change_pace, 8: show_party, 9: show_diary}

    while True:
        if not game["party"]:
            print("\n【结局: 全军覆没】")
            print("所有人都死了。废土上又多了一辆空车……")
            break
        if game["distance"] >= TOTAL_DISTANCE:
            arrive(game)
            break

        show_status(game)
        print("1. 继续前进  2. 休息一天  3. 搜刮废墟  4. 打猎  5. 使用药品  "
              "6. 改变口粮  7. 改变速度  8. 查看队伍  9. 旅行日记  10. 存档")
        choice = ask_number("你要做什么? ", 1, 10)
        if choice == 10:
            save_game(game)
            if ask_number("1. 继续玩  2. 退出游戏  ", 1, 2) == 2:
                print("下次再见!")
                return
            continue
        actions[choice](game)

    delete_save()
    show_diary(game)
    print("\n====== 游戏结束 ======")


if __name__ == "__main__":
    try:
        main()
    except (EOFError, KeyboardInterrupt):
        print("\n\n游戏中途退出了, 下次再见!")
