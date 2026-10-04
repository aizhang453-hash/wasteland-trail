"""
用代码做游戏里的音乐: 老式游戏机那种「哔哔」的电子音乐, 做好的音乐存成这个文件夹里的 .wav 文件。
游戏只管放这些 .wav 文件。想改音乐: 改下面的音符, 再运行一次:
    python3 music/make_music.py
只用 Python 自带的库。每次做出来的文件都一模一样 (随机的部分也固定了), 没改音符就不会变。

音符的写法: "C5:1" 是 5 号八度的 C (do), 唱 1 拍; "-:1" 是停 1 拍; 不写拍数就是 1 拍。
升半音写 #, 比如 "G#4"; A4 是 440 赫兹, 就是钢琴中间那个 la。
"""

import math
import os
import random
import struct
import sys
import wave

RATE = 16000   # 每秒多少个采样点。越多声音越细, 文件也越大
NOTES = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}


def frequency(note):
    """音符的频率 (每秒振动几次), 比如 frequency("A4") 是 440"""
    name, octave = note[:-1], int(note[-1])
    return 440 * 2 ** ((NOTES[name] + 12 * (octave + 1) - 69) / 12)


def notes_of(text):
    """把 "C5:1 -:0.5 E5" 这样的字变成 [(音符, 拍数), ...], 停顿的音符是 None"""
    result = []
    for token in text.split():
        note, _, beats = token.partition(":")
        result.append((None if note == "-" else note, float(beats or 1)))
    return result


def arpeggio(chords, beats_per_chord, pattern_beats):
    """伴奏: 每个和弦把几个音轮流弹 (分解和弦)。chords 是 [("A2", "E3", "A3", "E3"), ...]"""
    text = []
    for chord in chords:
        count = round(beats_per_chord / pattern_beats)
        text += [f"{chord[i % len(chord)]}:{pattern_beats}" for i in range(count)]
    return " ".join(text)


def octave_shift(text, octaves):
    """整段音符升高 (正数) 或者降低 (负数) 几个八度"""
    shifted = []
    for note, beats in notes_of(text):
        shifted.append(f"{'-' if note is None else note[:-1] + str(int(note[-1]) + octaves)}:{beats:g}")
    return " ".join(shifted)


def wave_value(shape, phase):
    """一个周期里第 phase (0 到 1) 处的声音: 方波像老游戏机, 三角波柔和, 用来弹低音"""
    if shape == "方波":
        return 1.0 if phase < 0.25 else -1.0      # 窄一点的方波, 声音亮
    if shape == "宽方波":
        return 1.0 if phase < 0.5 else -1.0
    return 4 * abs(phase - 0.5) - 1               # 三角波


def voice(text, bpm, shape, volume, vibrato=0.0):
    """一个声部 (一条旋律或者伴奏) 的声音: 一串 -1 到 1 之间的数"""
    samples = []
    for note, beats in notes_of(text):
        count = round(beats * 60 / bpm * RATE)
        if note is None:
            samples += [0.0] * count
            continue
        freq = frequency(note)
        sounding = int(count * 0.88)          # 每个音最后留一点空, 一个一个分得清
        attack = int(RATE * 0.008)
        release = min(int(RATE * 0.05), sounding // 3)
        phase = 0.0
        for i in range(sounding):
            if i < attack:                    # 慢慢响起来、慢慢停下, 不然会有「啪」的杂音
                level = i / attack
            elif i > sounding - release:
                level = (sounding - i) / release
            else:
                level = 1 - 0.25 * i / sounding   # 唱着唱着稍微变轻一点
            wobble = 1 + vibrato * math.sin(2 * math.pi * 5 * i / RATE)   # 颤音 (像小号)
            phase = (phase + freq * wobble / RATE) % 1
            samples.append(wave_value(shape, phase) * level * volume)
        samples += [0.0] * (count - sounding)
    return samples


def drums(text, bpm, volume, seed):
    """鼓: 一下一下的「嚓」声 (随机的杂音, 很快变轻)。音符写 x 是敲一下, - 是不敲"""
    noise = random.Random(seed)
    samples = []
    for hit, beats in notes_of(text):
        count = round(beats * 60 / bpm * RATE)
        length = min(count, int(RATE * 0.06))
        for i in range(count):
            samples.append(noise.uniform(-1, 1) * volume * (1 - i / length) if hit and i < length else 0.0)
    return samples


def geiger(seconds, seed):
    """开进辐射热点: 盖革计数器 (测辐射的仪器) 越响越快的「咔嗒」声, 底下一个低沉的嗡嗡声"""
    noise = random.Random(seed)
    count = int(seconds * RATE)
    samples = [0.0] * count
    for i in range(count):   # 低沉的嗡嗡声, 一下强一下弱
        t = i / RATE
        fade = min(1, t / 0.5, (seconds - t) / 0.5)
        samples[i] = 0.25 * fade * (4 * abs((t * frequency("E2")) % 1 - 0.5) - 1) * (0.6 + 0.4 * math.sin(t * 9))
    t = 0.1
    while t < seconds - 0.1:   # 咔嗒声: 一开始稀, 越来越密
        start = int(t * RATE)
        for i in range(int(RATE * 0.003)):
            if start + i < count:
                samples[start + i] += noise.uniform(-1, 1) * 0.9
        t += noise.expovariate(4 + 30 * t / seconds)
    return samples


def mix(*voices):
    """几个声部叠在一起, 再调到不太响也不太轻"""
    length = max(len(v) for v in voices)
    mixed = [sum(v[i] for v in voices if i < len(v)) for i in range(length)]
    loudest = max(abs(x) for x in mixed) or 1
    return [x * 0.85 / loudest for x in mixed]


def save(folder, name, samples):
    """存成 .wav 文件 (单声道、8 位, 文件小)"""
    with wave.open(os.path.join(folder, name), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(1)
        f.setframerate(RATE)
        f.writeframes(bytes(max(0, min(255, round(128 + x * 127))) for x in samples))


# ========== 音乐 ==========

# 主菜单: 慢慢的、有点悲伤的曲子 (自己写的), A 小调, 8 小节, 一直循环
TITLE_BPM = 80
TITLE_MELODY = ("E5:1.5 D5:0.5 C5:1 A4:1   F4:1 A4:1 C5:2   G4:1.5 E4:0.5 G4:1 C5:1   B4:3 -:1 "
                "E5:1.5 D5:0.5 C5:1 A4:1   A4:1 C5:1 F5:2   E5:1.5 D5:0.5 B4:1 G#4:1   A4:3 -:1")
TITLE_CHORDS = [("A2", "E3", "A3", "E3"), ("F2", "C3", "F3", "C3"), ("C3", "G3", "C4", "G3"), ("G2", "D3", "G3", "D3"),
                ("A2", "E3", "A3", "E3"), ("F2", "C3", "F3", "C3"), ("E2", "B2", "E3", "B2"), ("A2", "E3", "A3", "E3")]

# 赶路: 《哦! 苏珊娜》(斯蒂芬·福斯特 1848 年写的, 当年去西部的拓荒者一路上都在唱, 早就是大家都能用的老歌了)。
# 每小节 2 拍。第一遍是原调, 第二遍低一个八度、换个音色, 听着不那么单调
SUSANNA = ("E5:.5 G5:.5 G5:.75 A5:.25  G5:.5 E5:.5 C5:.75 D5:.25  E5:.5 E5:.5 D5:.5 C5:.5  D5:1 C5:.5 D5:.5 "
           "E5:.5 G5:.5 G5:.75 A5:.25  G5:.5 E5:.5 C5:.75 D5:.25  E5:.5 E5:.5 D5:.5 D5:.5  C5:1.5 -:.5 "
           "F5:1 A5:1  A5:.5 A5:.5 G5:.5 G5:.5  E5:.5 C5:.5 D5:1  -:1 C5:.5 D5:.5 "
           "E5:.5 G5:.5 G5:.75 A5:.25  G5:.5 E5:.5 C5:.75 D5:.25  E5:.5 E5:.5 D5:.5 D5:.5  C5:1 C5:.5 D5:.5")
SUSANNA_CHORDS = "C C C G  C C G C  F C G G  C C G C"   # 每小节一个和弦
TRAVEL_BPM = 132
BASS_OF = {"C": "C3:1 G2:1", "G": "G2:1 D3:1", "F": "F2:1 C3:1"}   # 低音: 每小节先弹根音, 再弹五度音

# 到了据点: 一小段高兴的
OUTPOST_BPM = 160
OUTPOST_MELODY = "C5:.5 E5:.5 G5:.5 C6:.5 -:.25 G5:.25 C6:2"
OUTPOST_BASS = "C3:2 G2:.5 C3:2"

# 有人去世: 《熄灯号》(美国军队给去世的人吹的号, 也是大家都能用的老曲子), 用像小号的声音吹
TAPS_BPM = 120
TAPS = "G4:.75 G4:.25 C5:2 -:.5  G4:.75 C5:.25 E5:2 -:.5  C5:.75 E5:.25 G5:2 -:.5  E5:.75 C5:.25 G4:2 -:.5  G4:.75 G4:.25 C5:3"

# 到达俄勒冈城: 胜利的号角 (自己写的)
ARRIVE_BPM = 132
ARRIVE_MELODY = ("G4:.5 C5:.5 E5:.5 G5:1 E5:.5 G5:1   A5:1 G5:.5 E5:.5 C5:1 D5:1 "
                 "E5:1 D5:.5 C5:.5 D5:1 G4:1   C5:4")
ARRIVE_BASS = "C3:1 G3:1 C3:1 G3:1  F2:1 C3:1 C3:1 G2:1  G2:1 D3:1 G2:1 D3:1  C3:4"

# 全军覆没: 慢慢往下走的小调 (自己写的)
GAME_OVER_BPM = 70
GAME_OVER_MELODY = "A4:1 G4:1 F4:1 E4:2  D4:1 C4:1 B3:1 A3:3"
GAME_OVER_BASS = "A2:3 F2:2 D2:3 E2:1 A2:2"


def make_all(folder):
    """做出所有的音乐, 存进 folder"""
    title = mix(voice(TITLE_MELODY, TITLE_BPM, "宽方波", 0.5),
                voice(arpeggio(TITLE_CHORDS, 4, 0.5), TITLE_BPM, "三角波", 0.6))
    save(folder, "title.wav", title)

    bass = " ".join(BASS_OF[chord] for chord in SUSANNA_CHORDS.split())
    beat = " ".join("-:1 x:1" for _ in SUSANNA_CHORDS.split())   # 每小节第二拍「嚓」一下
    first = mix(voice(SUSANNA, TRAVEL_BPM, "方波", 0.45), voice(bass, TRAVEL_BPM, "三角波", 0.7),
                drums(beat, TRAVEL_BPM, 0.2, seed=1))
    second = mix(voice(octave_shift(SUSANNA, -1), TRAVEL_BPM, "宽方波", 0.45), voice(bass, TRAVEL_BPM, "三角波", 0.7),
                 drums(beat, TRAVEL_BPM, 0.2, seed=2))
    save(folder, "travel.wav", first + second)

    save(folder, "outpost.wav", mix(voice(OUTPOST_MELODY, OUTPOST_BPM, "方波", 0.5),
                                    voice(OUTPOST_BASS, OUTPOST_BPM, "三角波", 0.6)))
    save(folder, "geiger.wav", mix(geiger(2.5, seed=3)))
    save(folder, "taps.wav", mix(voice(TAPS, TAPS_BPM, "宽方波", 0.6, vibrato=0.006)))
    save(folder, "arrive.wav", mix(voice(ARRIVE_MELODY, ARRIVE_BPM, "方波", 0.5),
                                   voice(ARRIVE_BASS, ARRIVE_BPM, "三角波", 0.6)))
    save(folder, "game_over.wav", mix(voice(GAME_OVER_MELODY, GAME_OVER_BPM, "宽方波", 0.5),
                                      voice(GAME_OVER_BASS, GAME_OVER_BPM, "三角波", 0.6)))


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    make_all(sys.argv[1] if len(sys.argv) > 1 else here)
    print("音乐做好了。")
