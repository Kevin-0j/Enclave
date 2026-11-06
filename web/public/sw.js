/* Enclave service worker. Caches the app shell for fast, installable start-up. Never caches API
   responses, video or anything authenticated. Web Push handlers arrive in M4. */
const VERSION = "enclave-shell-v1";
const SHELL = ["/", "/manifest.webmanifest", "/icons/icon.svg", "/icons/icon-192.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin) return;
  if (/^\/(api|media|hls|internal)\//.test(url.pathname)) return; // always network, never cached

  if (event.request.mode === "navigate") {
    // Network first so deploys show up; fall back to the cached shell when offline.
    event.respondWith(fetch(event.request).catch(() => caches.match("/")));
    return;
  }
  if (url.pathname.startsWith("/assets/")) {
    // Hashed, immutable build assets: cache first.
    event.respondWith(
      caches.match(event.request).then(
        (hit) => hit || fetch(event.request).then((res) => {
          const copy = res.clone();
          caches.open(VERSION).then((c) => c.put(event.request, copy));
          return res;
        }),
      ),
    );
  }
});
