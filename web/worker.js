// 网页版的后台线程: 在这里下载 Python (Pyodide), 运行游戏。
// 游戏一问问题, 这个线程就停下来, 等网页 (index.html) 把玩家输入的字放进共用内存再接着跑。
// 停在后台线程里不要紧, 网页本身不会卡住。
// 用的是新式的「模块」写法 (import), 老式的 importScripts 在开了 SharedArrayBuffer 的网页里下载不了 CDN 上的文件。

import { loadPyodide } from "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.mjs";

let control;   // 共用内存的前两个数字: [0] 是「玩家输入好了没有」(1 是好了), [1] 是输入的字有几个字节
let letters;   // 共用内存后面的部分: 玩家输入的字 (UTF-8)
const sleeper = new Int32Array(new SharedArrayBuffer(4));   // 专门用来「停一会儿」的一小块内存

self.onmessage = async (event) => {
  const { inputMemory, savedGame } = event.data;
  control = new Int32Array(inputMemory, 0, 2);
  letters = new Uint8Array(inputMemory, 8);

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

  // Python 那边要用的两个小工具 (见 run_in_browser.py)
  self.sleepMs = (ms) => Atomics.wait(sleeper, 0, 0, ms);
  self.saveToPage = (text) => postMessage({ type: "save", text: text });

  postMessage({ type: "status", text: "正在载入游戏……" });
  const game = await (await fetch("../wasteland_trail.py", { cache: "no-cache" })).text();
  const starter = await (await fetch("run_in_browser.py", { cache: "no-cache" })).text();
  pyodide.FS.writeFile("/home/pyodide/wasteland_trail.py", game);
  if (savedGame) {
    pyodide.FS.writeFile("/home/pyodide/savegame.json", savedGame);
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
