"""
废土之旅
一个仿照《俄勒冈之旅》的文字冒险游戏。
运行方法: 在终端里输入 python wasteland_trail.py
"""

import random
import time

# ========== 游戏设置(数字都可以随便改) ==========

TOTAL_DISTANCE = 1000   # 到安全城市的总路程(公里)
START_MONEY = 700       # 一开始的钱
WINTER_DAY = 50         # 第几天冬天来, 在那之前要赶到

# 路上的据点: 路程 -> 名字
OUTPOSTS = {250: "锈铁镇", 500: "水塔营地", 750: "旧机场据点"}

# 商店价格(每个多少钱)
PRICES = {"食物": 1, "水": 1, "燃料": 4, "子弹": 1, "零件": 20, "药品": 15}

# 口粮: 编号 -> (名字, 每人每天吃几份, 每天健康变化)
RATIONS = {1: ("少", 1, -2), 2: ("普通", 2, 1), 3: ("饱", 3, 3)}

# 速度: 编号 -> (名字, 每天走几公里, 每天用几份燃料, 每天健康变化)
PACES = {1: ("慢", 25, 1, 1), 2: ("中", 40, 2, 0), 3: ("快", 55, 3, -3)}

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

# 队员的默认名字(不想自己起名字时, 从这里随机挑)
DEFAULT_NAMES = ["阿强", "小美", "老周", "大雷", "眼镜", "胖虎", "小雨", "铁柱"]

# 路上可能遇到的陌生人
STRANGER_NAMES = ["老烟枪", "小石头", "铁姐", "独眼张", "阿飞"]


# ========== 小工具 ==========

def ask_number(prompt, low, high):
    """让玩家输入数字, 输错了就重新问"""
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


def random_member(game):
    return random.choice(list(game["party"]))


def check_deaths(game):
    for name in list(game["party"]):
        if game["party"][name] <= 0:
            del game["party"][name]
            game["dead"].append(name)
            print(f"!!! {name} 没能撑下去, 去世了。")


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
        "visited": set(),   # 已经到过的据点
        "seeds": False,     # 有没有找到种子库(隐藏结局)
    }


def setup(game):
    print("========== 废土之旅 ==========")
    print("核战争已经过去二十年了。")
    print(f"你要带着队伍开车穿过废土, 到 {TOTAL_DISTANCE} 公里外的安全城市。")
    print(f"冬天会在第 {WINTER_DAY} 天到来, 一定要在那之前赶到。\n")
    leader = input("你叫什么名字? (直接按回车就叫\"队长\") ").strip() or "队长"
    names = [leader]
    spare = [n for n in DEFAULT_NAMES if n != leader]
    random.shuffle(spare)

    print("\n你还有 3 个队员。")
    use_default = ask_number("1. 自己给队员起名字  2. 用默认名字  ", 1, 2) == 2
    for i in range(1, 4):
        name = "" if use_default else input(f"第 {i} 个队员叫什么? (直接按回车用默认名字) ").strip()
        name = name or spare.pop()
        while name in names:
            name += "2"
        names.append(name)
    print("你的队员: " + "、".join(names[1:]))
    for name in names:
        game["party"][name] = 100

    print("\n出发前可以在营地买东西。")
    print("提示: 每人每天要吃食物、喝 1 份水, 车每天要用燃料。子弹可以打猎, 也可以防身。")
    shop(game)


def shop(game):
    items = list(PRICES)
    while True:
        print(f"\n------ 商店 ------  你有 {game['money']} 块钱")
        for i, item in enumerate(items, 1):
            print(f"{i}. {item}  {PRICES[item]} 块一个  (现在有 {game['supplies'][item]})")
        print("0. 离开商店")
        choice = ask_number("买什么? ", 0, len(items))
        if choice == 0:
            return
        item = items[choice - 1]
        most = game["money"] // PRICES[item]
        amount = ask_number(f"买多少{item}? (最多 {most}) ", 0, most)
        game["supplies"][item] += amount
        game["money"] -= amount * PRICES[item]


def show_status(game):
    s = game["supplies"]
    left = TOTAL_DISTANCE - game["distance"]
    winter = WINTER_DAY - game["day"]
    print(f"\n==== 第 {game['day']} 天 | 已走 {game['distance']} 公里 | 还剩 {left} 公里"
          f" | 离冬天还有 {winter} 天 ====")
    print(f"天气: {game['weather']} ({WEATHER[game['weather']][4]})")
    print("物资: " + "  ".join(f"{k} {v}" for k, v in s.items()) + f"  钱 {game['money']}")
    print("队员: " + "  ".join(f"{n} {health_word(h)}({h})" for n, h in game["party"].items()))
    print(f"口粮: {RATIONS[game['ration']][0]}  速度: {PACES[game['pace']][0]}")
    if game["seeds"]:
        print("车上带着: 种子库的种子")


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
        print("食物不够了, 大家在挨饿!")

    water_need = people * (1 + extra_water)
    if s["水"] >= water_need:
        s["水"] -= water_need
    else:
        change -= round(15 * (water_need - s["水"]) / water_need)
        s["水"] = 0
        print("干净的水不够了, 大家渴得受不了!")

    game["day"] += 1
    change_all_health(game, change)
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
    km = round((km + random.randint(-5, 5)) * speed)
    km = min(km, TOTAL_DISTANCE - game["distance"])   # 最后一段路不多算
    game["distance"] += km
    if speed < 1:
        print(f"\n{weather}里车开不快, 只往前开了 {km} 公里。")
    else:
        print(f"\n车往前开了 {km} 公里。")
    pass_day(game, pace_health)
    random_event(game)
    check_outposts(game)


def rest(game):
    print("\n大家躲在车里休息了一天。")
    pass_day(game, 8, indoors=True)


def scavenge(game):
    print("\n你们花了一天搜刮附近的废墟……")
    pass_day(game)
    if not game["party"]:
        return
    roll = random.random()
    if roll < 0.2:
        mutant_attack(game)
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
    print(f"\n你们拿着枪出去打猎, 远处有一只{animal}……")
    input("准备好了就按回车, 然后马上打出屏幕上的词, 再按回车!")
    print(f"\n    >>> {word} <<<\n")
    start = time.time()
    typed = input("> ").strip().lower()
    seconds = time.time() - start

    low, high = ANIMALS[animal]
    food = random.randint(low, high)
    if typed != word:
        print("手一抖打歪了, 猎物跑掉了。")
    elif seconds <= 3:
        print(f"砰! 只用了 {seconds:.1f} 秒, 一枪命中! 得到 {food} 份食物。")
        s["食物"] += food
    elif seconds <= 6:
        food //= 2
        print(f"用了 {seconds:.1f} 秒, 只打伤了它, 追了半天才拿回 {food} 份食物。")
        s["食物"] += food
    else:
        print(f"用了 {seconds:.1f} 秒, 太慢了, 猎物早就跑了。")
    pass_day(game)


def use_medicine(game):
    s = game["supplies"]
    if s["药品"] == 0:
        print("\n你没有药品了。")
        return
    name = min(game["party"], key=game["party"].get)   # 找健康最低的人
    if game["party"][name] >= 100:
        print("\n大家都很健康, 不需要用药。")
        return
    s["药品"] -= 1
    game["party"][name] = min(100, game["party"][name] + 35)
    print(f"\n你给 {name} 用了药, {name} 感觉好多了。")


def change_ration(game):
    print("\n口粮: 1. 少  2. 普通  3. 饱")
    game["ration"] = ask_number("选哪个? ", 1, 3)


def change_pace(game):
    print("\n速度: 1. 慢  2. 中  3. 快")
    game["pace"] = ask_number("选哪个? ", 1, 3)


def check_outposts(game):
    for km, name in OUTPOSTS.items():
        if game["party"] and game["distance"] >= km and name not in game["visited"]:
            game["visited"].add(name)
            print(f"\n你们到了【{name}】, 这里有幸存者在做买卖。")
            if ask_number("要进去买东西吗? 1. 要  2. 不要  ", 1, 2) == 1:
                shop(game)


# ========== 随机事件(想加新事件就照着写一个函数, 再放进 EVENTS) ==========

def radiation_storm(game):
    days = random.randint(1, 2)
    print(f"\n【辐射风暴】天空变成了绿色! 你们躲了 {days} 天, 大家都受到了辐射。")
    for _ in range(days):
        pass_day(game, indoors=True)
    change_all_health(game, -10)


def raiders(game):
    s = game["supplies"]
    print("\n【劫匪】一伙劫匪拦住了路!")
    print("1. 交出一些物资  2. 开枪(要 15 发子弹)  3. 加速逃跑(要 3 份燃料)")
    choice = ask_number("你怎么办? ", 1, 3)

    if choice == 2 and s["子弹"] >= 15:
        s["子弹"] -= 15
        if random.random() < 0.7:
            print("你们打退了劫匪!")
        else:
            victim = random_member(game)
            print(f"劫匪被打跑了, 但是 {victim} 中枪受伤了。")
            hurt(game, victim, 35)
        return

    if choice == 3 and s["燃料"] >= 3:
        s["燃料"] -= 3
        if random.random() < 0.6:
            print("你们甩掉了劫匪!")
            return
        print("没跑掉……")
    elif choice != 1:
        print("你的子弹或燃料不够, 只能交出物资。")

    for item in ["食物", "水", "子弹"]:
        s[item] -= s[item] // 3
    game["money"] -= game["money"] // 3
    print("劫匪抢走了三分之一的食物、水、子弹和钱。")


def breakdown(game):
    s = game["supplies"]
    print("\n【车坏了】车子突然停下, 冒出一股黑烟!")
    if s["零件"] > 0:
        s["零件"] -= 1
        print("你用了 1 个备用零件, 很快就修好了。")
    else:
        print("没有备用零件, 只能自己慢慢修, 花了 3 天。")
        for _ in range(3):
            pass_day(game)


def warehouse(game):
    print("\n【废弃仓库】路边有一个没被搜过的旧仓库!")
    for _ in range(2):
        find_supplies(game)


def mutant_attack(game):
    s = game["supplies"]
    print("\n【变异野兽】一群变异野狗冲了过来!")
    if s["子弹"] >= 10:
        s["子弹"] -= 10
        print("你们开枪把它们赶走了, 用掉 10 发子弹。")
    else:
        victim = random_member(game)
        print(f"子弹不够! {victim} 被咬伤了。")
        hurt(game, victim, 30)


def radiation_sickness(game):
    victim = random_member(game)
    print(f"\n【辐射病】{victim} 开始掉头发、发烧, 得了辐射病。")
    hurt(game, victim, 25)


def bad_water(game):
    s = game["supplies"]
    lost = s["水"] // 4
    s["水"] -= lost
    print(f"\n【水被污染】一桶水漏进了脏东西, 倒掉了 {lost} 份水。")


def trader(game):
    s = game["supplies"]
    print("\n【流浪商人】一个流浪商人想跟你换东西: 20 份食物换 8 份燃料。")
    if s["食物"] < 20:
        print("可惜你的食物不够, 换不了。")
        return
    if ask_number("1. 换  2. 不换  ", 1, 2) == 1:
        s["食物"] -= 20
        s["燃料"] += 8
        print("交换成功。")


def stranger(game):
    s = game["supplies"]
    name = random.choice(STRANGER_NAMES)
    while name in game["party"] or name in game["dead"]:
        name += "2"
    print(f"\n【陌生人】路边有个叫 {name} 的幸存者, 想跟你们一起走。")
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
    else:
        game["party"][name] = random.randint(60, 90)
        print(f"{name} 加入了队伍!")


def minefield(game):
    s = game["supplies"]
    print("\n【雷区】路边插着一块歪掉的牌子: \"小心地雷\"。")
    print("1. 绕路(多花 1 天和 2 份燃料)  2. 慢慢开过去")
    choice = ask_number("你怎么办? ", 1, 2)
    if choice == 1 and s["燃料"] >= 2:
        s["燃料"] -= 2
        pass_day(game)
        print("你们绕开了雷区, 平安无事。")
        return
    if choice == 1:
        print("燃料不够绕路, 只能硬着头皮开过去……")
    if random.random() < 0.4:
        victim = random_member(game)
        print(f"轰! 车轮压到了一颗地雷, {victim} 受了重伤。")
        hurt(game, victim, 40)
    else:
        print("你们小心翼翼地开了过去, 什么都没炸。")


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
        print("你们找到了一个旧世界的种子库! 里面封存着几千种植物的种子。")
        print("这些种子也许能让废土重新变绿……一定要把它们带到安全城市!")
    elif roll < 0.7:
        print("地堡里还剩下不少旧物资!")
        for _ in range(3):
            find_supplies(game)
    else:
        print("这是个陷阱! 信号是劫匪放出来的!")
        raiders(game)


EVENTS = [radiation_storm, raiders, breakdown, warehouse,
          mutant_attack, radiation_sickness, bad_water, trader,
          stranger, minefield, radio_signal]


def random_event(game):
    """每走一天, 有 35% 的机会发生一个随机事件"""
    if game["party"] and random.random() < 0.35:
        random.choice(EVENTS)(game)


# ========== 结局 ==========

def arrive(game):
    """到达安全城市, 根据路上的情况决定是哪个结局"""
    print(f"\n你们到达了安全城市! 一共用了 {game['day'] - 1} 天。")
    print(f"活下来的人: {'、'.join(game['party'])}")
    if game["dead"]:
        print(f"路上失去的人: {'、'.join(game['dead'])}")

    if game["seeds"]:
        print("\n【隐藏结局: 绿色的希望】")
        print("城里的科学家打开种子库, 激动得说不出话。")
        print("第二年春天, 城墙外第一次长出了麦子。废土开始变绿了。")
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


# ========== 主循环 ==========

def main():
    game = new_game()
    setup(game)
    actions = {1: travel, 2: rest, 3: scavenge, 4: hunt, 5: use_medicine,
               6: change_ration, 7: change_pace}

    while True:
        if not game["party"]:
            print("\n【结局: 全军覆没】")
            print("所有人都死了。废土上又多了一辆空车……")
            break
        if game["distance"] >= TOTAL_DISTANCE:
            arrive(game)
            break
        if game["day"] >= WINTER_DAY:
            print("\n【结局: 核冬天】")
            print("灰色的雪开始落下, 气温一夜之间降到零下三十度。")
            print(f"你们离安全城市还有 {TOTAL_DISTANCE - game['distance']} 公里, 再也走不动了……")
            break

        show_status(game)
        print("1. 继续前进  2. 休息一天  3. 搜刮废墟  4. 打猎  5. 使用药品  6. 改变口粮  7. 改变速度")
        choice = ask_number("你要做什么? ", 1, 7)
        actions[choice](game)

    print("\n====== 游戏结束 ======")


if __name__ == "__main__":
    try:
        main()
    except (EOFError, KeyboardInterrupt):
        print("\n\n游戏中途退出了, 下次再见!")
