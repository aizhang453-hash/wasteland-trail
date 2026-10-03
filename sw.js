// 网页版用的 service worker (浏览器在后台替网页处理请求的小程序)。
//
// 为什么要它: 网页版里, Python 要停下来等玩家输入, 得用浏览器的 SharedArrayBuffer (网页和后台线程共用的一块内存)。
// 浏览器只在网页带着两个特殊的「响应头」时才给用这个功能, 可 GitHub Pages 不让我们自己设置响应头。
// 所以由它在浏览器里拦下本网站的每个请求, 给回来的内容补上这两个响应头。
// 第一次打开网页时它还没装好, 网页会自动刷新一次 (见 index.html)。

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

self.addEventListener("fetch", (event) => {
  const request = event.request;
  // 别的网站的东西 (比如从 CDN 下载的 Python) 不管, 让浏览器照常去拿
  if (new URL(request.url).origin !== self.location.origin) return;
  event.respondWith(
    fetch(request).then((response) => {
      const headers = new Headers(response.headers);
      headers.set("Cross-Origin-Opener-Policy", "same-origin");
      headers.set("Cross-Origin-Embedder-Policy", "require-corp");
      return new Response(response.body, {
        status: response.status,
        statusText: response.statusText,
        headers: headers,
      });
    })
  );
});
