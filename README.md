# Productivity Lock

Sperrt YouTube, Netflix, Instagram, LinkedIn, Reddit, League of Legends und World of Warcraft, bis für heute Anki, LeetCode und Lesen erledigt sind.
Der Tag beginnt wie in Anki um 4 Uhr. Erledigtes bleibt bis dahin erledigt. Die Checkliste liegt unter
<http://127.0.0.1:47615/>.

## Einrichtung

1. Abhängigkeiten für das Tray-Symbol installieren, den Dienst starten und in den Autostart legen.
   **Ist etwas gesperrt, wird ein offener League-Client dabei sofort geschlossen.**

   ```powershell
   python -m pip install -r requirements.txt
   powershell -ExecutionPolicy Bypass -File .\install_autostart.ps1
   ```

2. Erweiterung in Edge und Chrome laden:
   1. `edge://extensions` bzw. `chrome://extensions` öffnen.
   2. Den Entwicklermodus einschalten.
   3. „Entpackte Erweiterung laden“ wählen und den Ordner `extension` auswählen.
   4. In den Details der Erweiterung „In InPrivate zulassen“ bzw. „Im Inkognito-Modus zulassen“ einschalten.

   Die Erweiterung hat über `key` in `manifest.json` eine feste ID. Der Dienst nimmt nur Anfragen von ihr an, andere
   Erweiterungen werden abgewiesen.

Abschalten: `powershell -ExecutionPolicy Bypass -File .\uninstall_autostart.ps1` und die Erweiterung entfernen.

## Was als erledigt zählt

| Aufgabe | Bedingung |
| --- | --- |
| Anki | 200 beantwortete Karten oder 30 Minuten Lernzeit, was zuerst erreicht ist |
| LeetCode | Mindestens eine akzeptierte Lösung seit 4 Uhr |
| Lesen | 20-Minuten-Timer abgelaufen und ein Satz dazu (mindestens 20 Zeichen) |

Es müssen alle Aufgaben erledigt sein. Für schlechte Tage hat **jede Aufgabe einen eigenen Joker pro Kalenderwoche**
(`joker.per_week`): Du setzt ihn an der Aufgabe mit einer kurzen Begründung ein, und sie gilt für heute als erledigt, bis
zum nächsten Tag um 4 Uhr. Dieselbe Aufgabe kannst du in einer Woche nur einmal erlassen, damit keine Gewohnheit
wegfällt. Die Woche beginnt montags um 4 Uhr, nicht genutzte Joker verfallen.

Bei Anki zählen nur die Decks unter `Sprachen`, `Essential Spanish Vocabulary Top 5000` und `Sampling Methods for ML`.
`Archiv`, `Master` und `Poker` zählen nicht und blockieren auch nicht. Jede Antwort zählt, auch bei derselben Karte; Antworten unter einer Sekunde zählen nicht als Karte.
Alle Werte stehen in `config.json`. Nach einer Änderung muss der Dienst neu starten.

Karten, die du am Handy lernst, zählen erst, nachdem Anki am PC synchronisiert hat. Der Check liest eine Kopie der
Sammlung und braucht kein AnkiConnect.

## Eigene Aufgaben

Weitere Pflichtaufgaben trägst du in `config.json` unter `custom_tasks` ein:

```json
"custom_tasks": [
  { "id": "sport", "title": "Sport", "type": "check", "prompt": "Was hast du gemacht?" },
  { "id": "studium", "title": "Studium", "type": "timer", "minutes": 45, "min_note_chars": 20 },
  { "id": "code", "title": "GitHub", "type": "github", "username": "DanielD0304" }
]
```

- `check`: nur eine kurze Notiz, ohne Timer.
- `timer`: Timer mit eigener Dauer und danach eine Notiz. Die Notizen stehen in `data/notes_log.jsonl`.
- `github`: mindestens ein Push seit 4 Uhr. Das sieht nur Pushes in **öffentliche** Repositories.

## Lernchat und Sprachchat

Zwei Aufgaben, jede fünfmal pro Woche ein kurzer Chat mit Claude. Du startest sie mit dem Knopf an der Aufgabe auf der
Checkliste. Er öffnet in der Claude-App eine neue Code-Sitzung im Projektordner, mit `/lernchat` bzw. `/sprachchat`
schon im Eingabefeld. Die App fragt jedes Mal kurz, ob sie den Ordner nutzen darf, danach drückst du Enter. Die Skills
laufen mit Sonnet (`model: sonnet` im Skill), das schont das Nutzungslimit deines Abos.

Mit `"chat_app": "terminal"` in der `config.json` startet der Knopf stattdessen `claude.exe` in einem Konsolenfenster
(Modell aus `chat_model`, Pfad bei Bedarf in `claude_path`). Nur dort gibt es „… beenden“ und das automatische Schließen
nach dem Eintrag.

- **Lernchat** (`/lernchat`): zur nächsten Prüfung, mit dem Fach aus deinen Lernmeister-Profilen
  (`~/Lernmeister/<Fach>/`). Jede Vorlesung wird erst **erarbeitet** (Claude erklärt sie wie ein Tutor mit
  Verständnisfragen), dann **gefestigt** (du erklärst sie selbst oder machst ein Quiz, bis mindestens 0,85). Sind die
  Kernvorlesungen (`core_lectures`, hier 1 bis 6) gefestigt und höchstens zwei Schwächen offen, streut der Chat
  20-minütige **Prüfungssimulationen** im Stil der Prüfungsprotokolle ein.
- **Sprachchat** (`/sprachchat`): Englisch, Spanisch oder Chinesisch, du wählst am Anfang. Pro Sprache gibt es zuerst
  eine **Sprachevaluation** (Niveau nach GER, bei Chinesisch auch HSK). Danach lernt der Chat schrittweise auf diesem
  Niveau: erst die offenen Schwächen, dann neues Material, dann Anwenden. Nach drei starken Chats hebt er das Niveau an.

Jede Runde wird mit `scripts/chat.py` in `data/lernchat.jsonl` bzw. `data/sprachchat.jsonl` eingetragen, auch eine
schlechte, zusammen mit den Schwächen (`weak`) und den Punkten, die jetzt sitzen (`fixed`). Eine Schwäche bleibt offen,
bis eine spätere Runde sie als gelöst meldet, und kommt im nächsten Chat zuerst wieder dran. Den Stand zeigen
`python scripts/chat.py lernchat status` und `python scripts/chat.py sprachchat status`.

Einstellungen in `config.json` unter `lernchat` und `sprachchat`:

| Wert | Bedeutung |
| --- | --- |
| `per_week` | Chats pro Woche (je 5) |
| `min_score` | Ab diesem Score zählt ein Chat. 0 heißt: jeder vollständig gemachte Chat zählt (eingestellt) |
| `languages` | Nur Sprachchat: Sprachcode und Name der wählbaren Sprachen |
| `core_lectures` | Nur Lernchat: so viele Vorlesungen müssen gefestigt sein, bevor Simulationen kommen (6) |

Ein Chat zählt, sobald du ihn vollständig gemacht hast. Der Score steuert nur, was wiederholt wird, und ob eine
Vorlesung als erarbeitet (ab 0,7) oder gefestigt (ab 0,85) gilt. Unter 0,7 bietet Claude eine freiwillige zweite Runde
zu den Schwächen an.

Pro Tag zählt höchstens ein Chat je Aufgabe. Die Aufgabe sperrt erst, wenn die übrigen Tage der Woche (bis Sonntag) nur
noch für das Wochenziel reichen, bei 5 pro Woche also ab Mittwoch. An Montag und Dienstag steht sie auf „Heute frei“. Ist
das Ziel erreicht, bleibt sie bis Montag 4 Uhr frei. Die Punktzahl bewertet Claude selbst. Wer sie hochschreibt, betrügt
nur sich. Ohne `lernchat` oder `sprachchat` in der Config gibt es die jeweilige Aufgabe nicht.

## Verlauf und Tray-Symbol

Die Checkliste zeigt deine Serie, den Rekord, die Wochenbilanz und einen Kalender. Der Kalender färbt jeden Tag nach den
erledigten Aufgaben: rot für nichts, grün für alles, dazwischen Orange, Gelb und Hellgrün. Ein gestrichelter Rand
markiert Tage, an denen ein Joker benutzt wurde. Nur komplett geschaffte Tage zählen für die Serie, auch wenn eine
Aufgabe per Joker erlassen wurde. Ein Tag, an dem *alle* Aufgaben per Joker erlassen wurden, zählt nicht mit, unterbricht
die Serie aber auch nicht. Der Verlauf beginnt mit dem ersten Tag, an dem du etwas erledigt hast.

Das Symbol neben der Uhr zeigt, wie viele Aufgaben erledigt sind: rot gesperrt, grün frei. Ein
Klick öffnet die Checkliste. Zu den Zeiten in `reminders` erinnert es dich an alles, was noch offen ist. Die Zeiten
stehen im Format `HH:MM`.

## Sprachen lernen mit diesem Ziel

- **Neue Wörter nur in einer Hauptsprache.** Stell in den anderen Decks „Neue Karten pro Tag“ auf 0, dort läuft nur
  noch die Wiederholung. Bei 10 Wörtern pro Tag dauert ein 5000-Wörter-Deck etwa 16 Monate.
- **Wiederholungen vor neuen Karten.** Nach einigen Wochen sind 10 neue Wörter pro Tag etwa 60 bis 100 Wiederholungen.
  Wird es dauerhaft zu viel, senke die neuen Karten statt Wiederholungen liegen zu lassen.
- **FSRS mit 90 % Merkquote.** Das FSRS-Helper-Add-on hast du bereits. Mehr als 90 % kostet deutlich mehr
  Wiederholungen für wenig Gewinn.
- **Laut mitsprechen und Audio hören.** So übst du auch Aussprache und Hörverstehen.
- **Karten bringen Wörter, Texte bringen Sprache.** Lesen in der Zielsprache zählt auch für den Lese-Timer und
  verankert die Wörter im Zusammenhang.

## Handy-App (Android)

Die App sperrt YouTube, Instagram, Netflix, LinkedIn, Reddit und Wild Rift auf dem Handy, als App und als Webseite im
Browser, bis die Aufgaben des Tages erledigt sind, und
zeigt dieselbe Checkliste wie am PC. Lese-Timer, Notizen und Joker gehen auch am Handy. Chats startest du weiter am PC.
Das Handy fragt den PC über [Tailscale](https://tailscale.com/). Ist der PC aus, gilt der letzte bekannte Stand, und ab
4 Uhr ist wieder gesperrt, bis der PC etwas anderes meldet.

Das Handy fragt nicht ständig nach, das schont den Akku. Es holt den Stand nur, wenn du in der App auf
**Synchronisieren** tippst oder eine gesperrte App öffnest. Ist der Tag dann erledigt, geht die App gleich wieder auf.

1. Tailscale auf PC und Handy installieren und mit demselben Konto anmelden.
2. Den Dienst neu starten. Er öffnet den Handy-Zugang auf Port 47616, nur auf der Tailscale-Adresse und nur mit Token.
   Fragt die Windows-Firewall nach, den Zugriff erlauben.
3. Die APK bauen (`android\gradlew.bat -p android assembleRelease`) oder die fertige nehmen:
   `android\app\build\outputs\apk\release\app-release.apk`. Aufs Handy kopieren und installieren
   („Unbekannte Apps installieren“ erlauben).
4. Am PC koppeln und den QR-Code mit der Handy-Kamera scannen. Die App zeigt die Adresse und verbindet erst nach
   deiner Bestätigung. Klappt das nicht, Adresse und Token von Hand eintragen.

   ```powershell
   python -m app.phone
   ```

5. Die Sperre einschalten: Einstellungen → Bedienungshilfen → Productivity Lock. Ist der Schalter ausgegraut
   (Android 13 und neuer), zuerst unter Einstellungen → Apps → Productivity Lock oben rechts im Menü
   „Eingeschränkte Einstellungen zulassen“ wählen.

Welche Apps gesperrt sind, steht in `config.json` unter `phone.blocked_apps` (Paketnamen), welche Webseiten unter
`phone.blocked_sites`. Webseiten erkennt die App an der Adresszeile von Chrome, Firefox, Edge, Brave, Samsung Internet,
Opera, DuckDuckGo, Vivaldi und Kiwi. In anderen Browsern und in Apps, die Seiten selbst anzeigen, greift das nicht. Der
Handy-Zugang lässt sich mit `"phone": {"enabled": false}` abschalten. Das Token liegt in `data/phone_token.txt`.
Löschst du es, entsteht beim nächsten Start ein neues, und das Handy muss neu koppeln. Wer die Bedienungshilfe
abschaltet, hebt die Sperre auf.

## Tests

```powershell
python -m unittest discover -s tests
```

`python main.py --dry-run` startet alles, ohne ein Programm zu schließen.

## Grenzen

Die Sperre ist eine Hürde, keine Festung. Sie lässt sich umgehen, indem du die Erweiterung entfernst, einen anderen
Browser oder das Handy nutzt oder `data/state.json` bearbeitest. Die LeetCode-Prüfung nutzt eine inoffizielle
öffentliche Schnittstelle. Fällt sie aus, bleibt die Sperre aktiv.
