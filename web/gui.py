"""
网页版图形界面用的几个小工具: 把游戏现在的状态、正在问的问题, 整理成网页看得懂的样子 (变成 JSON 交给网页)。
由 web/run_in_browser.py 用。这里不碰网页 (不 import js), 所以在电脑上也能跑测试。

网页上的按钮是怎么来的: 游戏问问题以前会印出选项, 比如「1. 继续前进  2. 休息」或者「1. 让杰克加入  2. 不用了」,
这里把这些字找出来, 变成「号码 + 名字」, 网页就画成按钮, 点一下等于输入那个号码。游戏本身不用改。
"""

import re

# 「1. 继续前进  2. 休息」这样的选项: 号码、点、空格, 后面是名字, 一直到下一个「两个空格 + 号码 + 点」或者这一行完
OPTION = re.compile(r"(?:^|\s)(\d+)\.\s+(.+?)(?=\s{2,}\d+\.\s|\s*$)")
COLOR_CODE = re.compile(r"\x1b\[[\d;]*m")
MOST_BUTTONS = 12   # 能选的数字超过这么多个 (比如买多少东西), 就不画按钮, 用数字键盘


def short_label(text):
    """选项的名字只要前面一小段: 「直接开过去 (车能开过……)」→「直接开过去」,「简单: 一开始有……」→「简单」"""
    return re.split(r"\s\(|\(|:|：|,|，|。|\s{2,}", text, maxsplit=1)[0].strip()


def option_labels(text, low, high):
    """从印出来的字里找出 low 到 high 每个号码的名字, 按出现的先后排好: [[号码, 名字], ...]。
    同一个号码出现好几次, 用最后一次的名字。找不到名字的号码也放进去 (名字是空的)"""
    labels = {}
    for line in COLOR_CODE.sub("", text).split("\n"):
        for number, words in OPTION.findall(line):
            if low <= int(number) <= high:
                labels.pop(int(number), None)   # 后出现的排后面
                labels[int(number)] = short_label(words)
    for number in range(low, high + 1):
        labels.setdefault(number, "")
    return [[number, label] for number, label in labels.items()]


def number_question(text, prompt, low, high):
    """游戏让玩家选 low 到 high 的数字: 能选的不多就画按钮, 太多就用数字键盘"""
    actions = "你要做什么" in prompt   # 每天的菜单, 网页画成带图标的大按钮 (选项再多也是按钮)
    if high - low + 1 > MOST_BUTTONS and not actions:
        return {"kind": "number", "prompt": prompt.strip(), "low": low, "high": high}
    choices = option_labels(text + "\n" + prompt, low, high)
    if "月份" in prompt:   # 出发月份: 按钮上写「4 月」
        choices = [[number, f"{number} 月"] for number in range(low, high + 1)]
    if "几天" in prompt:   # 休息几天: 按钮上写「3 天」
        choices = [[number, label or f"{number} 天"] for number, label in choices]
    if "往哪边" in prompt:   # 过急流: 水道下面那一行「左边水道  中间礁石  右边礁石」
        for line in reversed(COLOR_CODE.sub("", text).split("\n")):
            lanes = line.split()
            if len(lanes) == high - low + 1 and all(lane[:2] in ("左边", "中间", "右边") for lane in lanes):
                choices = [[low + i, lane[:2]] for i, lane in enumerate(lanes)]
                break
    return {"kind": "choices", "prompt": asked(text, prompt), "choices": choices,
            "actions": actions}


def asked(text, prompt):
    """按钮上面写的问题。问题里就是选项 (比如「1. 换  2. 不换」) 的话, 换成上面那一句 (「……换不换?」)"""
    prompt = COLOR_CODE.sub("", prompt).strip()
    found = OPTION.search(prompt)
    if not found:
        return prompt
    before = prompt[:found.start()].strip()   # 「要花 2 天去找吗? 1. 去  2. 不去」: 选项前面就是问题
    if before:
        return before
    for line in reversed(COLOR_CODE.sub("", text).split("\n")):
        line = line.strip()
        if line and not OPTION.search(line):
            return line
    return ""


def enter_question(prompt):
    """游戏等玩家按回车: 网页画一个按钮, 上面写「继续」「看下一页」这些。
    打猎的「准备好了」按完马上要打字, 网页顺便把输入框点开 (手机上要先点一下才会出键盘)"""
    label = prompt.replace("……", "").replace("就按回车", "").replace("按回车", "").strip() or "继续"
    return {"kind": "enter", "label": label, "typeNext": prompt.startswith("准备好了")}


def game_state(w, game):
    """游戏现在的状态, 网页画状态面板、地图和旅行日记用。w 是游戏 (wasteland_trail), game 是这一局"""
    s = game["supplies"]
    people = len(game["party"])
    weather, temperature = game["weather"], game["temperature"]
    name, km = w.next_place(game)
    outposts = [n for n, _ in w.OUTPOSTS.values()]
    kind = "据点" if name in outposts else "河" if name in w.RIVERS else "终点" if name == w.DESTINATION else "地标"

    supplies = []
    for item, amount in s.items():
        days = w.days_left(game, item) if item in w.daily_need(game) else None
        supplies.append({"name": item, "amount": amount, "measure": w.MEASURES[item], "days": days})

    party = []
    for member, health in game["party"].items():
        rads = game["rads"].get(member, 0)
        sick = game["sick"].get(member)
        party.append({"name": member, "job": game["jobs"].get(member, ""), "leader": member == game["leader"],
                      "health": health, "word": w.health_word(health), "color": w.health_color(health),
                      "sick": sick[0] if sick else "", "rads": rads, "radsWord": w.radiation_level(rads)[1]})

    notes = []
    spot, ahead = w.hotspot_here(game), w.next_hotspot(game)
    if spot:
        notes.append(["紫", f"在{spot[2]}, 辐射偏高"])
    elif ahead and ahead[0] - game["distance"] <= w.HOTSPOT_WARNING:
        notes.append(["紫", f"再开 {w.show_distance(game, ahead[0] - game['distance'])}就到{ahead[2]}, 辐射偏高"])
    if s["食物"] == 0:
        notes.append(["红", "没吃的了"])
    if s["水"] == 0:
        notes.append(["红", "没有干净的水了"])
    if w.temperature_level(temperature)[5] and s["冬衣"] < people:
        notes.append(["红", "冬衣不够, 有人在受冻"])
    if game["seeds"]:
        notes.append(["绿", "车上带着种子库的种子"])

    if w.WEATHER[weather][0] == 0:
        car = f"开不动 ({weather})"
    elif w.out_of_fuel(game):
        car = "没燃料了"
    else:
        car = ""   # 在开还是停着, 网页自己知道

    diary = []
    for line in game["diary"]:
        found = re.match(r"(\S+) \(第 \d+ 天\), 已走 [^:]+: (.*)", line)
        diary.append([found[1], found[2]] if found else ["", line])

    places = [{"name": n, "km": k, "kind": "河" if n in w.RIVERS else "地标"} for k, (n, _) in w.LANDMARKS.items()]
    places += [{"name": n, "km": k, "kind": "据点"} for k, (n, _) in w.OUTPOSTS.items()]
    places.sort(key=lambda place: place["km"])

    return {
        "date": w.date_text(game), "day": game["day"], "difficulty": w.DIFFICULTIES[game["difficulty"]][0],
        "weather": weather, "weatherColor": w.weather_color(weather), "weatherNote": w.weather_report(game),
        "temperature": w.show_temperature(game, temperature), "temperatureWord": w.temperature_level(temperature)[1],
        "temperatureColor": w.temperature_color(temperature),
        "km": game["distance"], "total": w.TOTAL_DISTANCE,
        "traveled": w.show_distance(game, game["distance"]),
        "left": w.show_distance(game, w.TOTAL_DISTANCE - game["distance"]),
        "next": {"name": name, "kind": kind, "distance": w.show_distance(game, km - game["distance"])},
        "supplies": supplies, "money": game["money"],
        "load": w.show_weight(game, w.load_of(game)), "capacity": w.show_weight(game, w.CAR_CAPACITY),
        "loadPercent": min(100, w.load_of(game) * 100 // w.CAR_CAPACITY),
        "ration": w.RATIONS[game["ration"]][0], "pace": w.PACES[game["pace"]][0],
        "party": party, "dead": game["dead"], "notes": notes, "car": car, "diary": diary,
        "places": places, "destination": w.DESTINATION, "here": game.get("here"),
        "hotspots": [[start, end, spot_name] for start, end, spot_name, *_ in w.HOTSPOTS],
    }
