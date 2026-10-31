# Productivity Lock

Sperrt YouTube, Netflix und League of Legends, bis für heute Anki, LeetCode und Lesen erledigt sind.
Der Tag beginnt wie in Anki um 4 Uhr. Erledigtes bleibt bis dahin erledigt. Die Checkliste liegt unter
<http://127.0.0.1:47615/>.

## Einrichtung

1. Dienst starten und in den Autostart legen. **Ein offener League-Client wird dabei sofort geschlossen.**

   ```powershell
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
| Anki | 10 neue Wörter und alle fälligen Wiederholungen, höchstens 100. Spätestens nach 30 Minuten gilt Anki als erledigt, wenn du mindestens eine Karte gelernt hast. |
| LeetCode | Mindestens eine akzeptierte Lösung seit 4 Uhr |
| Lesen | 20-Minuten-Timer abgelaufen und ein Satz dazu (mindestens 20 Zeichen) |

Für schlechte Tage gibt es einen Joker pro Kalenderwoche (`joker.per_week`): Du setzt ihn auf der Checkliste mit einer
kurzen Begründung ein, und alles ist bis zum nächsten Tag um 4 Uhr frei. Die Woche beginnt montags um 4 Uhr, nicht
genutzte Joker verfallen.

Bei Anki zählen nur die Decks unter `Sprachen` und `Essential Spanish Vocabulary Top 5000`. `Archiv`, `Master` und
`Poker` zählen nicht und blockieren auch nicht. Jede Karte zählt einmal, Antworten unter einer Sekunde gar nicht.
Alle Werte stehen in `config.json`. Nach einer Änderung muss der Dienst neu starten.

Karten, die du am Handy lernst, zählen erst, nachdem Anki am PC synchronisiert hat. Der Check liest eine Kopie der
Sammlung und braucht kein AnkiConnect.

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
