// 网页版用的 service worker (浏览器在后台替网页处理请求的小程序)。
//
// 为什么要它: 网页版里, Python 要停下来等玩家输入, 得用浏览器的 SharedArrayBuffer (网页和后台线程共用的一块内存)。
// 浏览器只在网页带着两个特殊的「响应头」时才给用这个功能, 可 GitHub Pages 不让我们自己设置响应头。
// 所以由它在浏览器里拦下网页的每个请求, 给回来的内容补上这两个响应头。
// 第一次打开网页时它还没装好, 网页会自动刷新一次 (见 index.html)。
//
// 别的网站的东西 (比如从 jsDelivr 下载的 Python) 也要经过它: 开了这两个响应头以后, 别的网站的文件要写明「允许别的网站用」
// (Cross-Origin-Resource-Policy) 才能用。jsDelivr 本来写了, Chrome 认, 可 Safari 的内核 (iPhone、iPad 上所有的浏览器都用它,
// 包括 Chrome) 还是不让后台线程用, 网页版打不开。所以这里也给它们补上, 再交给网页。

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

self.addEventListener("fetch", (event) => {
  const request = event.request;
  // 只许用缓存、又不是本网站的请求, 浏览器规定不能经过这里, 让浏览器自己处理
  if (request.cache === "only-if-cached" && request.mode !== "same-origin") return;
  event.respondWith(
    fetch(request).then((response) => {
      if (response.status === 0) return response;   // 看不到内容的跨站响应, 原样交回去
      const headers = new Headers(response.headers);
      headers.set("Cross-Origin-Opener-Policy", "same-origin");
      headers.set("Cross-Origin-Embedder-Policy", "require-corp");
      headers.set("Cross-Origin-Resource-Policy", "cross-origin");
      return new Response(response.body, {
        status: response.status,
        statusText: response.statusText,
        headers: headers,
      });
    })
  );
});
