package dev.productivitylock

import android.app.Activity
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import android.os.Build
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/** Updates the app from the PC: the service hands out the APK Gradle built last, Android asks before installing. */
object Updater {
    const val ACTION_INSTALL_STATUS = "dev.productivitylock.INSTALL_STATUS"
    private const val TIMEOUT_MS = 8000

    data class Release(val versionCode: Long, val versionName: String)

    fun installedVersion(context: Context): Long {
        val info = context.packageManager.getPackageInfo(context.packageName, 0)
        return if (Build.VERSION.SDK_INT >= 28) info.longVersionCode else @Suppress("DEPRECATION") info.versionCode.toLong()
    }

    private fun open(context: Context, path: String): HttpURLConnection {
        val connection = URL("${StatusStore.address(context)}$path").openConnection() as HttpURLConnection
        connection.connectTimeout = TIMEOUT_MS
        connection.readTimeout = TIMEOUT_MS * 4
        connection.setRequestProperty("Authorization", "Bearer ${StatusStore.token(context)}")
        return connection
    }

    /** The version the PC offers, or null when the PC is unreachable or has no build. Blocks. */
    fun latest(context: Context): Release? = runCatching {
        val connection = open(context, "/app/version")
        try {
            if (connection.responseCode != 200) return null
            val json = JSONObject(connection.inputStream.bufferedReader().use { it.readText() })
            Release(json.getLong("versionCode"), json.getString("versionName"))
        } finally {
            connection.disconnect()
        }
    }.getOrNull()

    /**
     * Streams the APK into a PackageInstaller session and commits it. Android then shows its own confirmation;
     * the result comes back to MainActivity as [ACTION_INSTALL_STATUS]. Blocks; throws on failure.
     */
    fun install(activity: Activity) {
        val installer = activity.packageManager.packageInstaller
        val params = PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL)
        val sessionId = installer.createSession(params)
        installer.openSession(sessionId).use { session ->
            val connection = open(activity, "/app/latest.apk")
            try {
                check(connection.responseCode == 200) { "Der PC liefert keine App (${connection.responseCode})" }
                session.openWrite("app.apk", 0, connection.contentLengthLong).use { out ->
                    connection.inputStream.use { it.copyTo(out) }
                    session.fsync(out)
                }
            } finally {
                connection.disconnect()
            }
            val flags = PendingIntent.FLAG_UPDATE_CURRENT or
                (if (Build.VERSION.SDK_INT >= 31) PendingIntent.FLAG_MUTABLE else 0)
            val callback = PendingIntent.getActivity(
                activity, sessionId,
                Intent(activity, MainActivity::class.java).setAction(ACTION_INSTALL_STATUS), flags,
            )
            session.commit(callback.intentSender)
        }
    }
}
