const STATUS_URL = "http://127.0.0.1:47615/status";
const RULESET = "block";
const BLOCKED_TABS = [
  "*://*.youtube.com/*",
  "*://youtu.be/*",
  "*://*.youtube-nocookie.com/*",
  "*://*.netflix.com/*",
  "*://*.instagram.com/*",
];

// Stays locked when the service is unreachable, so stopping it opens nothing.
async function isUnlocked() {
  try {
    const response = await fetch(STATUS_URL, { cache: "no-store", signal: AbortSignal.timeout(4000) });
    return response.ok && (await response.json()).unlocked === true;
  } catch {
    return false;
  }
}

async function closeOpenTabs() {
  const tabs = await chrome.tabs.query({ url: BLOCKED_TABS });
  await Promise.all(tabs.map((tab) => chrome.tabs.update(tab.id, { url: chrome.runtime.getURL("locked.html") })));
}

async function sync() {
  const unlocked = await isUnlocked();
  await chrome.declarativeNetRequest.updateEnabledRulesets(
    unlocked ? { disableRulesetIds: [RULESET] } : { enableRulesetIds: [RULESET] },
  );
  if (!unlocked) await closeOpenTabs();
  return unlocked;
}

chrome.alarms.create("sync", { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener(sync);
chrome.runtime.onInstalled.addListener(sync);
chrome.runtime.onStartup.addListener(sync);
chrome.runtime.onMessage.addListener((message, sender, respond) => {
  if (message.type !== "sync") return false;
  sync().then(respond);
  return true;
});
