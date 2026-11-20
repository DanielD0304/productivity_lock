package dev.productivitylock

import android.annotation.SuppressLint
import android.app.Activity
import android.content.Intent
import android.graphics.Color
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

/** Shows the checklist from the PC; without a connection it asks for address and token first. */
class MainActivity : Activity() {
    private var webView: WebView? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = BACKGROUND
        window.navigationBarColor = BACKGROUND
        handle(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handle(intent)
    }

    override fun onResume() {
        super.onResume()
        // Coming back from the accessibility settings: drop the banner if the service is on now.
        if (StatusStore.isConfigured(this)) showChecklist()
    }

    private fun handle(intent: Intent) {
        val data = intent.data
        if (data?.scheme == "productivitylock" && data.host == "pair") {
            val address = data.getQueryParameter("url").orEmpty()
            val token = data.getQueryParameter("token").orEmpty()
            if (address.isNotEmpty() && token.isNotEmpty()) {
                StatusStore.save(this, address, token)
                Toast.makeText(this, "Mit dem PC verbunden", Toast.LENGTH_SHORT).show()
            }
        }
        if (intent.getBooleanExtra(EXTRA_BLOCKED, false)) {
            Toast.makeText(this, "Gesperrt, bis die Aufgaben von heute erledigt sind", Toast.LENGTH_LONG).show()
        }
        if (StatusStore.isConfigured(this)) showChecklist() else showSetup()
    }

    private fun serviceEnabled(): Boolean {
        val enabled = Settings.Secure.getString(contentResolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES)
        return enabled?.split(':')?.any { it.startsWith("$packageName/") } == true
    }

    private fun text(value: String, size: Float = 16f, color: Int = Color.WHITE) = TextView(this).apply {
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
            setTextColor(Color.WHITE)
            setHintTextColor(Color.GRAY)
        }
        val token = EditText(this).apply {
            hint = "Token"
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD
            setTextColor(Color.WHITE)
            setHintTextColor(Color.GRAY)
        }
        setContentView(LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(BACKGROUND)
            setPadding(dp(24), dp(48), dp(24), dp(24))
            addView(text("Mit dem PC verbinden", 24f))
            addView(text(
                "Am PC im Projektordner „python -m app.phone“ ausführen und den QR-Code mit der Kamera scannen. " +
                    "Oder Adresse und Token hier eintragen. Tailscale muss auf PC und Handy laufen.",
                15f, Color.LTGRAY,
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
            setBackgroundColor(BACKGROUND)
            fitsSystemWindows = true
        }
        if (!serviceEnabled()) {
            root.addView(LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                setPadding(dp(16), dp(12), dp(16), dp(4))
                setBackgroundColor(Color.rgb(90, 30, 30))
                addView(text("Die Sperre ist aus. Schalte „Productivity Lock“ in den Bedienungshilfen ein.", 15f))
                addView(button("Bedienungshilfen öffnen") {
                    startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
                })
            })
        }
        val web = webView ?: WebView(this).apply {
            setBackgroundColor(BACKGROUND)
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            webViewClient = object : WebViewClient() {
                override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                    // The checklist stays in the app; its links (LeetCode, YouTube …) open outside.
                    if (request.url.toString().startsWith(address)) return false
                    runCatching { startActivity(Intent(Intent.ACTION_VIEW, request.url)) }
                    return true
                }

                override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
                    if (request.isForMainFrame) view.loadDataWithBaseURL(null, offlinePage(address), "text/html", "utf-8", null)
                }
            }
            CookieManager.getInstance().setCookie(address, "plock_token=${StatusStore.token(this@MainActivity)}; Path=/")
            CookieManager.getInstance().flush()
            loadUrl("$address/")
        }
        webView = web
        (web.parent as? LinearLayout)?.removeView(web)
        root.addView(web, LinearLayout.LayoutParams(MATCH_PARENT, 0, 1f))
        root.addView(LinearLayout(this).apply {
            gravity = Gravity.END
            addView(button("Verbindung ändern") { showSetup() }, LinearLayout.LayoutParams(WRAP_CONTENT, WRAP_CONTENT))
        })
        setContentView(root)
    }

    private fun offlinePage(address: String): String {
        val status = StatusStore.cached(this)
        val state = if (StatusStore.isUnlocked(status)) "Heute schon alles erledigt: frei." else "Gesperrt."
        val since = status?.optString("day")?.takeIf { it.isNotEmpty() }?.let { "Letzter Stand vom Lerntag $it." } ?: "Noch kein Stand vom PC."
        return """
            <html><body style="background:#1c1c1e;color:#fff;font-family:sans-serif;padding:24px">
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
        private val BACKGROUND = Color.rgb(28, 28, 30)
    }
}
