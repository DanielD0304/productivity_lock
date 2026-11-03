# Productivity Lock

Sperrt YouTube, Netflix, Instagram und League of Legends, bis für heute Anki, LeetCode und Lesen erledigt sind.
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

Bei Anki zählen nur die Decks unter `Sprachen` und `Essential Spanish Vocabulary Top 5000`. `Archiv`, `Master` und
`Poker` zählen nicht und blockieren auch nicht. Jede Antwort zählt, auch bei derselben Karte; Antworten unter einer Sekunde zählen nicht als Karte.
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
Checkliste. Er öffnet Claude Code in einem eigenen Fenster mit dem passenden Skill (Pfad zur `claude.exe` bei Bedarf in
`claude_path` in der `config.json`).

- **Lernchat** (`/lernchat`): Quiz oder Feynman (du erklärst) zur nächsten Prüfung. Der Skill sucht über deine
  Lernmeister-Profile (`~/Lernmeister/<Fach>/`) das Fach mit der nächsten Prüfung und das Thema, das laut Lernplan dran
  ist.
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
| `per_week` | Chats pro Woche, an denen du mindestens `min_score` erreichst (je 5) |
| `min_score` | Ab diesem Anteil richtiger Antworten zählt ein Chat (0,7) |
| `languages` | Nur Sprachchat: Sprachcode und Name der wählbaren Sprachen |

Liegt der Score unter `min_score`, ist die Aufgabe heute offen, auch an einem freien Tag, bis eine Wiederholungsrunde
besteht. Läuft ein Chat, wird aus dem Knopf „… beenden“, der das Fenster schließt. Nach einem Chat mit zählendem Score
schließt es sich etwa 15 Sekunden nach dem Eintrag von selbst. Unter dem Schwellwert bleibt es offen für eine zweite
Runde.

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

## Tests

```powershell
python -m unittest discover -s tests
```

`python main.py --dry-run` startet alles, ohne ein Programm zu schließen.

## Grenzen

Die Sperre ist eine Hürde, keine Festung. Sie lässt sich umgehen, indem du die Erweiterung entfernst, einen anderen
Browser oder das Handy nutzt oder `data/state.json` bearbeitest. Die LeetCode-Prüfung nutzt eine inoffizielle
öffentliche Schnittstelle. Fällt sie aus, bleibt die Sperre aktiv.
