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

Für schlechte Tage gibt es einen Joker pro Kalenderwoche (`joker.per_week`): Du setzt ihn auf der Checkliste mit einer
kurzen Begründung ein, und alles ist bis zum nächsten Tag um 4 Uhr frei. Die Woche beginnt montags um 4 Uhr, nicht
genutzte Joker verfallen.

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
- `typing`: Minuten echtes Tippen auf edclub/typingclub, gezählt von der Erweiterung (`"minutes": 10`).
- `papers`: täglich ein Paper aus einer Leseliste abhaken, mit Kernaussage und Projektbezug in eigenen Worten.
- `paper_review`: gelesene Paper nach 7, 30 und 90 Tagen aus dem Kopf wiederholen.
- `log`: Forschungslog mit drei Feldern pro Tag, optional als Markdown-Datei.

```json
{ "id": "paper", "title": "Paper lesen", "type": "papers", "file": "papers.json", "project": "Masterarbeit",
  "min_summary_chars": 150, "min_takeaway_chars": 60 },
{ "id": "wiederholen", "title": "Paper wiederholen", "type": "paper_review", "intervals": [7, 30, 90], "min_recall_chars": 80 },
{ "id": "log", "title": "Forschungslog", "type": "log", "file": "C:/Pfad/FORSCHUNGSLOG.md", "project": "Masterarbeit" }
```

### Leseliste (`papers`)

Die Seite <http://127.0.0.1:47615/papers> zeigt die Liste als Pfad: Zeilen in Lesereihenfolge, Spalten nach Thema,
gestrichelte Bögen für Bezüge zwischen Papern. Mehrere Pfade lassen sich durchwischen (auch mit ←/→). Die Datei hat
einen gemeinsamen Katalog und die Pfade; ein Haken gilt für ein Paper in allen Pfaden:

```json
{
  "papers": { "leandojo": { "short": "LeanDojo", "title": "…", "source": "Yang et al., 2023", "url": "https://arxiv.org/abs/2306.15626" } },
  "paths": [
    { "id": "start", "title": "Einstieg", "stages": { "1": "Stufe 1: Grundlagen" },
      "lanes": [ { "id": "retrieval", "title": "Retrieval" } ],
      "items": [ { "id": "leandojo", "stage": 1, "lane": "retrieval", "why": "Warum lesen", "related": [] } ] }
  ]
}
```

Die Datei wird bei jedem Aufruf neu gelesen, Änderungen brauchen keinen Neustart. `"path"` in der Aufgabe wählt den
Standardpfad, sonst gilt der erste. Höchstens fünf Spalten je Pfad bekommen eigene Farben.

### Forschungslog (`log`)

Die Seite <http://127.0.0.1:47615/log> fragt: gemacht, Ergebnis, als Nächstes. Der heutige Eintrag lässt sich den
ganzen Tag ändern. Mit `file` schreibt der Lock alle Einträge als Markdown, neueste oben. Er überschreibt die Datei bei
jedem Eintrag, aber nur, wenn sie von ihm stammt; eine fremde Datei mit demselben Namen bleibt unberührt.

## Termine

Mit `"termine_file": "termine.json"` in `config.json` zeigt die Checkliste oben die nächsten drei Termine mit
Countdown. <http://127.0.0.1:47615/termine> zeigt alle, mit Zeitstrahl über zwölf Wochen, und hat ein Formular zum
Hinzufügen und Löschen. Arten: `meilenstein`, `frist`, `pruefung`, `treffen`, `cluster`. Zeiträume bekommen ein `end`.
Der Countdown nutzt das echte Datum, nicht den Lock-Tag ab 4 Uhr.

## Anki-Decks ausschließen

`"decks": []` zählt alle Decks, `"exclude_decks": ["Archiv"]` nimmt einzelne aus (samt Unterdecks). Ausschluss gewinnt.

## Firefox

Die Erweiterung läuft auch in Firefox ab Version 140. Dauerhaft installieren lässt sie sich nur signiert: den Inhalt von
`extension` (ohne `_metadata`) zippen, auf addons.mozilla.org als „unlisted“ hochladen und die signierte Datei
installieren. Zum Ausprobieren reicht `about:debugging` → „Temporäres Add-on laden“. Vor dem Hochladen die gecko-ID in
`manifest.json` auf eine eigene ändern und bei jeder Änderung die Version erhöhen.

## Verlauf und Tray-Symbol

Die Checkliste zeigt deine Serie, den Rekord, die Wochenbilanz und einen Kalender. Nur komplett geschaffte Tage zählen
für die Serie. Ein Joker-Tag zählt nicht mit, unterbricht sie aber auch nicht. Der Verlauf beginnt mit dem ersten Tag,
an dem du etwas erledigt hast.

Das Symbol neben der Uhr zeigt, wie viele Aufgaben erledigt sind: rot gesperrt, grün frei, `J` bei aktivem Joker. Ein
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
