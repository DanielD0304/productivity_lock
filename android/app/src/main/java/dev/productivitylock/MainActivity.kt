package dev.productivitylock

import android.annotation.SuppressLint
import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.content.pm.PackageInstaller
import android.content.res.Configuration
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import android.text.InputType
import android.view.Gravity
import android.view.View
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.ViewGroup.LayoutParams.WRAP_CONTENT
import android.webkit.CookieManager
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import java.time.LocalDateTime
import kotlin.concurrent.thread

/** Shows the checklist from the PC; without a connection it asks for address and token first. */
class MainActivity : Activity() {
    private var webView: WebView? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = groundColor
        window.navigationBarColor = groundColor
        if (!night) {
            @Suppress("DEPRECATION")
            window.decorView.systemUiVisibility =
                View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR or View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR
        }
        handle(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handle(intent)
    }

    // The checklist page polls while it is visible. Out of sight the WebView is thrown away entirely and built
    // fresh on return, which also shows the current state. (pauseTimers() froze the page for every WebView.)
    override fun onStop() {
        webView?.let { web ->
            (web.parent as? LinearLayout)?.removeView(web)
            web.destroy()
        }
        webView = null
        super.onStop()
    }

    override fun onResume() {
        super.onResume()
        // Coming back from the accessibility settings: drop the banner if the service is on now.
        if (StatusStore.isConfigured(this)) showChecklist()
    }

    private fun handle(intent: Intent) {
        if (intent.action == Updater.ACTION_INSTALL_STATUS) {
            installStatus(intent)
            intent.action = null
        }
        val data = intent.data
        if (data?.scheme == "productivitylock" && data.host == "pair") {
            // Handled once; a rotation must not ask again.
            intent.data = null
            val address = data.getQueryParameter("url").orEmpty()
            val token = data.getQueryParameter("token").orEmpty()
            if (address.isNotEmpty() && token.isNotEmpty()) confirmPairing(address, token)
        }
        if (intent.getBooleanExtra(EXTRA_BLOCKED, false)) {
            Toast.makeText(this, "Gesperrt, bis die Aufgaben von heute erledigt sind", Toast.LENGTH_LONG).show()
        }
        if (StatusStore.isConfigured(this)) showChecklist() else showSetup()
    }

    /** A pairing link can come from any web page, so it only takes effect after a look at the address. */
    private fun confirmPairing(rawAddress: String, token: String) {
        val address = StatusStore.normalizeAddress(rawAddress)
        val host = Uri.parse(address).host.orEmpty()
        val warning = if (StatusStore.isTailscaleAddress(host)) "" else
            "\n\nAchtung: Das ist keine Tailscale-Adresse (100.x.y.z). Verbinde nur, wenn du den Link selbst am PC erzeugt hast."
        AlertDialog.Builder(this)
            .setTitle("Mit diesem PC verbinden?")
            .setMessage("$address$warning")
            .setPositiveButton("Verbinden") { _, _ ->
                StatusStore.save(this, address, token)
                Toast.makeText(this, "Mit dem PC verbunden", Toast.LENGTH_SHORT).show()
                webView = null
                showChecklist()
            }
            .setNegativeButton("Abbrechen", null)
            .show()
    }

    private fun serviceEnabled(): Boolean {
        val enabled = Settings.Secure.getString(contentResolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES)
        return enabled?.split(':')?.any { it.startsWith("$packageName/") } == true
    }

    // Follows the phone's light or dark mode, in the same greys as the checklist page.
    private val night get() =
        (resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES
    private val groundColor get() = if (night) Color.rgb(22, 22, 24) else Color.rgb(245, 245, 247)
    private val primaryText get() = if (night) Color.rgb(236, 236, 239) else Color.rgb(29, 29, 31)
    private val secondaryText get() = if (night) Color.rgb(161, 161, 166) else Color.rgb(110, 110, 115)

    private fun text(value: String, size: Float = 16f, color: Int = primaryText) = TextView(this).apply {
        text = value
        textSize = size
        setTextColor(color)
        setPadding(0, 0, 0, dp(12))
    }

    private fun button(label: String, onClick: () -> Unit) = Button(this).apply {
        text = label
        isAllCaps = false
        setOnClickListener { onClick() }
    }

    private fun dp(value: Int) = (value * resources.displayMetrics.density).toInt()

    private fun showSetup() {
        webView = null
        val address = EditText(this).apply {
            hint = "100.x.y.z:47616"
            setText(StatusStore.address(this@MainActivity))
            inputType = InputType.TYPE_TEXT_VARIATION_URI
            setTextColor(primaryText)
            setHintTextColor(secondaryText)
        }
        val token = EditText(this).apply {
            hint = "Token"
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD
            setTextColor(primaryText)
            setHintTextColor(secondaryText)
        }
        setContentView(LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(groundColor)
            setPadding(dp(24), dp(48), dp(24), dp(24))
            addView(text("Mit dem PC verbinden", 24f))
            addView(text(
                "Am PC im Projektordner „python -m app.phone“ ausführen und den QR-Code mit der Kamera scannen. " +
                    "Oder Adresse und Token hier eintragen. Tailscale muss auf PC und Handy laufen.",
                15f, secondaryText,
            ))
            addView(address)
            addView(token)
            addView(button("Speichern") {
                if (address.text.isBlank() || token.text.isBlank()) {
                    Toast.makeText(this@MainActivity, "Bitte beides ausfüllen", Toast.LENGTH_SHORT).show()
                } else {
                    StatusStore.save(this@MainActivity, address.text.toString(), token.text.toString())
                    showChecklist()
                }
            })
        })
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun showChecklist() {
        val address = StatusStore.address(this)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(groundColor)
            fitsSystemWindows = true
        }
        if (!serviceEnabled()) {
            root.addView(LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                setPadding(dp(16), dp(12), dp(16), dp(4))
                setBackgroundColor(if (night) Color.rgb(70, 24, 24) else Color.rgb(255, 228, 226))
                addView(text("Die Sperre ist aus. Schalte „Productivity Lock“ in den Bedienungshilfen ein.", 15f))
                addView(button("Bedienungshilfen öffnen") {
                    startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
                })
            })
        }
        val web = webView ?: WebView(this).apply {
            setBackgroundColor(groundColor)
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            webViewClient = object : WebViewClient() {
                override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                    // The checklist stays in the app; its links (LeetCode, YouTube …) open outside.
                    if (StatusStore.sameServer(request.url, address)) return false
                    runCatching { startActivity(Intent(Intent.ACTION_VIEW, request.url)) }
                    return true
                }

                override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
                    if (request.isForMainFrame) view.loadDataWithBaseURL(null, offlinePage(address), "text/html", "utf-8", null)
                }
            }
            // HttpOnly keeps it from page scripts; Lax keeps other sites from sending it. Secure needs HTTPS.
            CookieManager.getInstance().setCookie(
                address, "plock_token=${StatusStore.token(this@MainActivity)}; Path=/; HttpOnly; SameSite=Lax",
            )
            CookieManager.getInstance().flush()
            loadUrl("$address/")
        }
        webView = web
        (web.parent as? LinearLayout)?.removeView(web)
        root.addView(web, LinearLayout.LayoutParams(MATCH_PARENT, 0, 1f))
        root.addView(LinearLayout(this).apply {
            gravity = Gravity.END
            addView(button("Synchronisieren") { sync() }, LinearLayout.LayoutParams(WRAP_CONTENT, WRAP_CONTENT))
            addView(button("Update") { update() }, LinearLayout.LayoutParams(WRAP_CONTENT, WRAP_CONTENT))
            addView(button("Verbindung") { showSetup() }, LinearLayout.LayoutParams(WRAP_CONTENT, WRAP_CONTENT))
        })
        setContentView(root)
    }

    /** Asks the PC for a newer build and installs it; Android shows its own confirmation first. */
    private fun update() {
        if (!packageManager.canRequestPackageInstalls()) {
            Toast.makeText(this, "Erlaube Productivity Lock einmal, Apps zu installieren, dann tippe nochmal auf Update.",
                Toast.LENGTH_LONG).show()
            startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:$packageName")))
            return
        }
        Toast.makeText(this, "Suche nach Updates …", Toast.LENGTH_SHORT).show()
        thread {
            val latest = Updater.latest(this)
            val installed = Updater.installedVersion(this)
            when {
                latest == null -> toast("PC nicht erreichbar oder keine App gebaut.")
                latest.versionCode <= installed -> toast("Die App ist aktuell.")
                else -> {
                    toast("Lade Version ${latest.versionName} …")
                    runCatching { Updater.install(this) }.onFailure { toast("Update fehlgeschlagen: ${it.message}") }
                }
            }
        }
    }

    private fun toast(message: String) = runOnUiThread { Toast.makeText(this, message, Toast.LENGTH_LONG).show() }

    private fun installStatus(intent: Intent) {
        when (intent.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE)) {
            PackageInstaller.STATUS_PENDING_USER_ACTION -> {
                @Suppress("DEPRECATION")
                val confirm = intent.getParcelableExtra<Intent>(Intent.EXTRA_INTENT)
                confirm?.let { startActivity(it.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }
            }
            PackageInstaller.STATUS_SUCCESS -> Toast.makeText(this, "Update installiert", Toast.LENGTH_SHORT).show()
            else -> {
                val reason = intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE) ?: "abgebrochen"
                Toast.makeText(this, "Update nicht installiert: $reason", Toast.LENGTH_LONG).show()
            }
        }
    }

    /** The only way the lock learns about finished tasks, besides opening a blocked app. */
    private fun sync() {
        Toast.makeText(this, "Synchronisiere …", Toast.LENGTH_SHORT).show()
        thread {
            val status = StatusStore.fetch(this)
            runOnUiThread {
                val message = when {
                    status == null -> "PC nicht erreichbar. Es bleibt beim letzten Stand."
                    StatusStore.isUnlocked(status) -> "Alles erledigt. Die Apps sind frei."
                    else -> {
                        val checks = status.optJSONObject("checks")
                        val names = checks?.keys()?.asSequence()?.toList().orEmpty()
                        val done = names.count { checks!!.optJSONObject(it)?.optBoolean("done") == true }
                        "Noch gesperrt: $done von ${names.size} erledigt."
                    }
                }
                Toast.makeText(this, message, Toast.LENGTH_LONG).show()
                webView?.reload()
            }
        }
    }

    private fun offlinePage(address: String): String {
        val status = StatusStore.cached(this)
        val state = if (StatusStore.isUnlocked(status)) "Heute schon alles erledigt: frei." else "Gesperrt."
        val since = status?.optString("day")?.takeIf { it.isNotEmpty() }?.let { "Letzter Stand vom Lerntag $it." } ?: "Noch kein Stand vom PC."
        return """
            <html><head><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="color-scheme" content="light dark">
            <style>body{background:#f5f5f7;color:#1d1d1f}@media (prefers-color-scheme:dark){body{background:#161618;color:#ececef}}</style></head>
            <body style="font-family:sans-serif;padding:24px">
            <h2>PC nicht erreichbar</h2>
            <p>$state $since</p>
            <p style="color:#aaa">Läuft der PC mit Tailscale? Neuer Versuch:</p>
            <p><a style="color:#0a84ff;font-size:18px" href="$address/">Erneut laden</a></p>
            <p style="color:#666">${LocalDateTime.now().withNano(0)}</p>
            </body></html>
        """.trimIndent()
    }

    @Deprecated("Back on the checklist goes home, not into a blocked app.")
    override fun onBackPressed() {
        val web = webView
        if (web != null && web.canGoBack()) web.goBack() else moveTaskToBack(true)
    }

    companion object {
        const val EXTRA_BLOCKED = "blocked"
    }
}
