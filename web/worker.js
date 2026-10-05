// 网页版的后台线程: 在这里下载 Python (Pyodide), 运行游戏。
// 游戏一问问题, 这个线程就停下来, 等网页 (index.html) 把玩家输入的字放进共用内存再接着跑。
// 停在后台线程里不要紧, 网页本身不会卡住。
// 用的是新式的「模块」写法 (import), 老式的 importScripts 在开了 SharedArrayBuffer 的网页里下载不了 CDN 上的文件。

import { loadPyodide } from "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.mjs";

let control;   // 共用内存的前两个数字: [0] 是「玩家输入好了没有」(1 是好了), [1] 是输入的字有几个字节
let letters;   // 共用内存后面的部分: 玩家输入的字 (UTF-8)
let flags;     // 另一小块共用内存: [0] 车自己往前开的时候, 玩家点了屏幕或者按了回车 (1 是要停下来); [1] [2] 网页一屏放得下几列、几行字;
               // [3] 打猎时网页一共记了几件事, [8] 开始的 32 个格子轮流放这些事 (见 index.html 的「打猎」)
let huntRead = 0;   // 打猎的事, 已经交给游戏几件了
const sleeper = new Int32Array(new SharedArrayBuffer(4));   // 专门用来「停一会儿」的一小块内存

self.onmessage = async (event) => {
  const { inputMemory, flagsMemory, savedGame, savedScores, savedSettings } = event.data;
  control = new Int32Array(inputMemory, 0, 2);
  letters = new Uint8Array(inputMemory, 8);
  flags = flagsMemory ? new Int32Array(flagsMemory) : null;

  postMessage({ type: "status", text: "正在下载 Python (第一次大约 10 MB, 请稍等)……" });
  const pyodide = await loadPyodide();

  // 游戏打印的字, 一收到就交给网页显示
  const decoder = new TextDecoder();
  const show = (bytes) => {
    postMessage({ type: "output", text: decoder.decode(bytes, { stream: true }) });
    return bytes.length;
  };
  pyodide.setStdout({ write: show });
  pyodide.setStderr({ write: show });
  pyodide.setStdin({ stdin: waitForAnswer });

  // Python 那边要用的几个小工具 (见 run_in_browser.py)
  self.sleepMs = (ms) => Atomics.wait(sleeper, 0, 0, ms);
  self.saveToPage = (text) => postMessage({ type: "save", text: text });
  self.saveScoresToPage = (text) => postMessage({ type: "scores", text: text });
  self.settingsToPage = (text) => postMessage({ type: "settings", text: text });   // 主菜单「设置」里改的
  self.musicToPage = (text) => postMessage({ type: "music", text: text });
  self.loopToPage = (text) => postMessage({ type: "loop", text: text });
  self.stopRequested = () => (flags ? Atomics.exchange(flags, 0, 0) : 0);   // 看一眼要不要停, 顺便清掉
  self.guiToPage = (text) => postMessage({ type: "gui", text: text });   // 图形界面: 状态、在问什么、车在不在开
  self.screenSize = () => (flags ? `${Atomics.load(flags, 1)},${Atomics.load(flags, 2)}` : "");   // 「几列,几行」
  self.huntToPage = (on) => postMessage({ type: "hunt", on: Boolean(on) });   // 打猎开始了 / 结束了
  if (flags && flags.length >= 8 + 32) {   // 网页还是旧版的话, 记不了打猎的事, 就不给游戏这个 (游戏会用以前打字的打猎)
    self.huntEvents = () => {   // 上次以后网页记下的打猎的事 (点了哪里、按了什么键), 用逗号隔开
      const count = Atomics.load(flags, 3);
      if (count - huntRead > 32) huntRead = count - 32;   // 太多了, 最早的已经被盖掉了
      const events = [];
      for (; huntRead < count; huntRead++) events.push(Atomics.load(flags, 8 + huntRead % 32));
      return events.join(",");
    };
  }

  postMessage({ type: "status", text: "正在载入游戏……" });
  const game = await (await fetch("../wasteland_trail.py", { cache: "no-cache" })).text();
  const starter = await (await fetch("run_in_browser.py", { cache: "no-cache" })).text();
  const gui = await (await fetch("gui.py", { cache: "no-cache" })).text();
  pyodide.FS.writeFile("/home/pyodide/wasteland_trail.py", game);
  pyodide.FS.writeFile("/home/pyodide/gui.py", gui);
  if (savedGame) {
    pyodide.FS.writeFile("/home/pyodide/savegame.json", savedGame);
  }
  if (savedScores) {
    pyodide.FS.writeFile("/home/pyodide/highscores.json", savedScores);
  }
  if (savedSettings) {
    pyodide.FS.writeFile("/home/pyodide/settings.json", savedSettings);
  }

  postMessage({ type: "status", text: "" });
  try {
    pyodide.runPython(starter);
  } catch (error) {
    postMessage({ type: "output", text: "\n\n游戏出错了:\n" + error + "\n" });
  }
  postMessage({ type: "finished" });
};

// 游戏要玩家输入时: 告诉网页, 然后停在这里等, 直到网页把输入的字放进共用内存
function waitForAnswer() {
  postMessage({ type: "need-input" });
  Atomics.wait(control, 0, 0);
  const text = new TextDecoder().decode(letters.slice(0, control[1]));
  Atomics.store(control, 0, 0);
  return text + "\n";
}
