package dev.productivitylock

import android.content.Context
import android.net.Uri
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.time.LocalDateTime

/** Connection settings and the last status the PC sent; the phone decides from this when the PC is off. */
object StatusStore {
    private const val PREFS = "lock"
    private const val TIMEOUT_MS = 4000
    val DEFAULT_BLOCKED = setOf(
        "com.google.android.youtube",
        "com.instagram.android",
        "com.netflix.mediaclient",
        "com.riotgames.league.wildrift",
    )

    private fun prefs(context: Context) = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun address(context: Context): String = prefs(context).getString("address", "") ?: ""
    fun token(context: Context): String = prefs(context).getString("token", "") ?: ""
    fun isConfigured(context: Context) = address(context).isNotEmpty() && token(context).isNotEmpty()

    fun normalizeAddress(raw: String): String {
        var address = raw.trim().trimEnd('/')
        if (address.isEmpty()) return ""
        if (!address.startsWith("http://") && !address.startsWith("https://")) address = "http://$address"
        if (Uri.parse(address).port == -1) address += ":47616"
        return address
    }

    fun save(context: Context, address: String, token: String) {
        prefs(context).edit()
            .putString("address", normalizeAddress(address))
            .putString("token", token.trim())
            .remove("status")
            .apply()
    }

    fun cached(context: Context): JSONObject? =
        prefs(context).getString("status", null)?.let { runCatching { JSONObject(it) }.getOrNull() }

    /** Asks the PC; on success the answer becomes the new cached status. Blocks, so never call it on the UI thread. */
    fun fetch(context: Context): JSONObject? {
        if (!isConfigured(context)) return null
        return try {
            val connection = URL("${address(context)}/status").openConnection() as HttpURLConnection
            connection.connectTimeout = TIMEOUT_MS
            connection.readTimeout = TIMEOUT_MS
            connection.setRequestProperty("Authorization", "Bearer ${token(context)}")
            try {
                if (connection.responseCode != 200) return null
                val body = connection.inputStream.bufferedReader().use { it.readText() }
                val status = JSONObject(body)
                prefs(context).edit().putString("status", body).apply()
                status
            } finally {
                connection.disconnect()
            }
        } catch (error: Exception) {
            null
        }
    }

    /** The learning day, as on the PC: before the rollover hour it is still yesterday. */
    fun logicalDay(rolloverHour: Int, now: LocalDateTime = LocalDateTime.now()): String =
        now.minusHours(rolloverHour.toLong()).toLocalDate().toString()

    /** Unlocked only if the PC said so for today; an old or missing answer means locked. */
    fun isUnlocked(status: JSONObject?, now: LocalDateTime = LocalDateTime.now()): Boolean {
        if (status == null || !status.optBoolean("unlocked")) return false
        return status.optString("day") == logicalDay(status.optInt("rollover_hour", 4), now)
    }

    fun blockedApps(status: JSONObject?): Set<String> {
        val list = status?.optJSONObject("phone")?.optJSONArray("blocked_apps") ?: return DEFAULT_BLOCKED
        return (0 until list.length()).map { list.getString(it) }.toSet()
    }
}
