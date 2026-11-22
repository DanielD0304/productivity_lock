package dev.productivitylock

import android.accessibilityservice.AccessibilityService
import android.content.Intent
import android.os.Handler
import android.os.Looper
import android.view.accessibility.AccessibilityEvent
import android.widget.Toast
import kotlin.concurrent.thread

/** Watches which app comes to the front and sends blocked ones home while the day's tasks are open. */
class LockAccessibilityService : AccessibilityService() {
    private val handler = Handler(Looper.getMainLooper())
    private var foreground: String? = null

    // No polling: the phone asks the PC only when a blocked app opens or when "Synchronisieren" is tapped.
    // A cached "done" stops counting at 4 a.m. by itself, because it belongs to the previous learning day.

    override fun onDestroy() {
        handler.removeCallbacksAndMessages(null)
        super.onDestroy()
    }

    override fun onInterrupt() {}

    override fun onAccessibilityEvent(event: AccessibilityEvent) {
        val app = event.packageName?.toString() ?: return
        if (app in BROWSER_URL_BARS && !StatusStore.isUnlocked(StatusStore.cached(this))) {
            // Pages load and change without a new window; check the address bar at most once a second,
            // and not at all once the day is done.
            browser = app
            if (!browserCheckPending) {
                browserCheckPending = true
                handler.postDelayed(browserCheck, BROWSER_CHECK_DELAY_MS)
            }
        }
        if (event.eventType != AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) return
        foreground = app
        if (enforce(app)) refresh(reopen = app)
    }

    private var browser: String? = null
    private var browserCheckPending = false
    private val browserCheck = Runnable {
        browserCheckPending = false
        browser?.let { checkBrowser(it) }
    }

    /** Leaves a blocked site in the browser: back to the previous page, or out of a fresh tab. */
    private fun checkBrowser(app: String) {
        if (!StatusStore.isConfigured(this)) return
        val status = StatusStore.cached(this)
        if (StatusStore.isUnlocked(status)) return
        val root = rootInActiveWindow ?: return
        if (root.packageName?.toString() != app) return
        val bar = root.findAccessibilityNodeInfosByViewId(BROWSER_URL_BARS.getValue(app)).firstOrNull() ?: return
        // While the address is being typed, wait for the page to load instead of closing the keyboard.
        if (bar.isFocused) return
        val site = StatusStore.blockedSite(bar.text?.toString(), StatusStore.blockedSites(status)) ?: return
        performGlobalAction(GLOBAL_ACTION_BACK)
        Toast.makeText(this, "$site ist gesperrt, bis die Aufgaben von heute erledigt sind", Toast.LENGTH_SHORT).show()
        // Still there after going back (e.g. more pages of the site in the history)? Check again.
        handler.removeCallbacks(browserCheck)
        browserCheckPending = true
        handler.postDelayed(browserCheck, BROWSER_RECHECK_MS)
    }

    /**
     * Asks the PC once, off the main thread, right after a blocked app was closed.
     * The block itself goes by the cached status; if the fresh one says the day is done, [reopen] comes back.
     */
    private fun refresh(reopen: String) {
        thread {
            val status = StatusStore.fetch(this)
            handler.post {
                if (StatusStore.isUnlocked(status)) {
                    packageManager.getLaunchIntentForPackage(reopen)?.let {
                        startActivity(it.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
                    }
                }
            }
        }
    }

    private fun enforce(app: String): Boolean {
        if (app == packageName || !StatusStore.isConfigured(this)) return false
        val status = StatusStore.cached(this)
        if (app !in StatusStore.blockedApps(status) || StatusStore.isUnlocked(status)) return false
        performGlobalAction(GLOBAL_ACTION_HOME)
        startActivity(
            Intent(this, MainActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
                .putExtra(MainActivity.EXTRA_BLOCKED, true)
        )
        foreground = packageName
        return true
    }

    companion object {
        private const val BROWSER_CHECK_DELAY_MS = 1_000L
        private const val BROWSER_RECHECK_MS = 1_000L

        /** The address bar of each supported browser; others are not checked. */
        private val BROWSER_URL_BARS = mapOf(
            "com.android.chrome" to "com.android.chrome:id/url_bar",
            "com.chrome.beta" to "com.chrome.beta:id/url_bar",
            "com.brave.browser" to "com.brave.browser:id/url_bar",
            "com.microsoft.emmx" to "com.microsoft.emmx:id/url_bar",
            "com.vivaldi.browser" to "com.vivaldi.browser:id/url_bar",
            "com.kiwibrowser.browser" to "com.kiwibrowser.browser:id/url_bar",
            "com.sec.android.app.sbrowser" to "com.sec.android.app.sbrowser:id/location_bar_edit_text",
            "org.mozilla.firefox" to "org.mozilla.firefox:id/mozac_browser_toolbar_url_view",
            "com.opera.browser" to "com.opera.browser:id/url_field",
            "com.duckduckgo.mobile.android" to "com.duckduckgo.mobile.android:id/omnibarTextInput",
        )
    }
}
