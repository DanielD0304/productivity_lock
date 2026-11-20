package dev.productivitylock

import android.accessibilityservice.AccessibilityService
import android.content.Intent
import android.os.Handler
import android.os.Looper
import android.view.accessibility.AccessibilityEvent
import kotlin.concurrent.thread

/** Watches which app comes to the front and sends blocked ones home while the day's tasks are open. */
class LockAccessibilityService : AccessibilityService() {
    private val handler = Handler(Looper.getMainLooper())
    private var foreground: String? = null

    private val poll = object : Runnable {
        override fun run() {
            refresh()
            // Every minute is enough for 4 a.m. and costs next to no battery; opening a blocked app asks at once.
            handler.postDelayed(this, POLL_MS)
        }
    }

    override fun onServiceConnected() {
        handler.post(poll)
    }

    override fun onDestroy() {
        handler.removeCallbacks(poll)
        super.onDestroy()
    }

    override fun onInterrupt() {}

    override fun onAccessibilityEvent(event: AccessibilityEvent) {
        if (event.eventType != AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) return
        val app = event.packageName?.toString() ?: return
        foreground = app
        if (enforce(app)) refresh(reopen = app)
    }

    /**
     * Fetches the status off the main thread and closes a blocked app that is still open, e.g. after 4 a.m.
     * The block itself goes by the cached status; if the fresh one says the day is done, [reopen] comes back.
     */
    private fun refresh(reopen: String? = null) {
        thread {
            val status = StatusStore.fetch(this)
            handler.post {
                if (reopen != null && StatusStore.isUnlocked(status)) {
                    packageManager.getLaunchIntentForPackage(reopen)?.let {
                        startActivity(it.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
                    }
                } else {
                    foreground?.let { enforce(it) }
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
        private const val POLL_MS = 60_000L
    }
}
