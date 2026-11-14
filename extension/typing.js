// Counts seconds of real typing on edclub; the background reports them to the lock service.
const IDLE_MS = 3000;
const REPORT_MS = 15000;
let lastKey = 0;
let pending = 0;

addEventListener("keydown", (event) => {
  if (event.isTrusted) lastKey = Date.now();
}, true);

setInterval(() => {
  if (document.visibilityState === "visible" && document.hasFocus() && Date.now() - lastKey <= IDLE_MS) pending += 1;
}, 1000);

setInterval(() => {
  if (!pending) return;
  const seconds = pending;
  pending = 0;
  chrome.runtime.sendMessage({ type: "typing", seconds }).catch(() => {});
}, REPORT_MS);
