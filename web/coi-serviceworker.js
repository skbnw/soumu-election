/* coi-serviceworker v0.1.7 - https://github.com/gzuidhof/coi-serviceworker - MIT License */
if (typeof window === 'undefined') {
    self.addEventListener("install", () => self.skipWaiting());
    self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

    async function handleFetch(request) {
        if (request.cache === "only-if-cached" && request.mode !== "same-origin") return;
        const r = await fetch(request).catch(e => console.error(e));
        if (!r) return;
        const newHeaders = new Headers(r.headers);
        newHeaders.set("Cross-Origin-Opener-Policy", "same-origin");
        newHeaders.set("Cross-Origin-Embedder-Policy", "require-corp");
        newHeaders.set("Cross-Origin-Resource-Policy", "cross-origin");
        return new Response(r.body, { status: r.status, statusText: r.statusText, headers: newHeaders });
    }

    self.addEventListener("fetch", (event) => event.respondWith(handleFetch(event.request)));
} else {
    (async function () {
        if (window.crossOriginIsolated !== false) return;
        if (!navigator.serviceWorker) {
            console.warn("coi-serviceworker: Service workers are not supported.");
            return;
        }
        try {
            await navigator.serviceWorker.register(window.document.currentScript.src);
        } catch (e) {
            console.error("coi-serviceworker: Failed to register service worker.", e);
            return;
        }
        if (navigator.serviceWorker.controller) return;
        await new Promise(resolve => {
            navigator.serviceWorker.addEventListener("controllerchange", resolve, { once: true });
        });
        location.reload();
    })();
}
