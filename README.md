# Sperrmüll-Termine Frankfurt am Main

Übersicht, **an welchem Wochentag** in welchem Frankfurter Stadtteil Sperrmüll abgeholt wird. Die Daten werden von der **FES (Frankfurter Entsorgungs-Service)** übernommen und regelmäßig aktualisiert.

## Funktionen

- **Übersicht**: Nach Wochentag gruppiert – in welchen Stadtteilen wird an welchem Tag Sperrmüll abgeholt?
- **Siedlungsabfuhr**: In einigen Wohnsiedlungen gibt es einen festen Sperrmüllplatz, der alle vier Wochen geleert wird – diese Termine werden angezeigt, sofern die FES sie liefert.
- **Alle Termine**: Liste aller erfassten Stadtteile mit Beispieladresse, Wochentag und nächsten Abholterminen.
- **Stadtteil-Filter**: Termine nur für einen gewählten Stadtteil anzeigen.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

Die App läuft unter `http://localhost:5001`.

## Datenquelle

Die Termine stammen von der FES-Website ([fes-frankfurt.de/services/sperrmuell](https://www.fes-frankfurt.de/services/sperrmuell)). Pro Stadtteil wird eine Beispieladresse abgefragt; der angezeigte Wochentag gilt in der Regel für das gesamte Gebiet. Ein Aktualisierungslauf erfolgt beim Start und danach alle 24 Stunden.

## Scraper (für Betreiber)

- **Zu viele Anfragen (429):** Der Scraper wartet bei Rate-Limits 90 Sekunden und versucht jede Adresse bis zu 3 Mal. Die Pause zwischen Anfragen beträgt etwa 3 Sekunden (mit leichter Schwankung).
- **Adressen:** `data/addresses.json` – eine Adresse pro Stadtteil. Ungültige Adressen können zu „Keine Termine“ führen und sollten ggf. angepasst werden.

## Siedlungsabfuhr

In bestimmten Wohngebieten (z. B. Nordweststadt, Riedberg) gibt es die **Siedlungsabfuhr**: einen festen Sperrmüllplatz, der alle vier Wochen abgeholt wird. Ob Ihre Liegenschaft angeschlossen ist, erfahren Sie bei Ihrer Wohnungsverwaltung oder der FES unter **0800 2008007-10**. Wo die FES einen festen Termin zurückgibt, zeigt die App diesen als „Siedlungsabfuhr“ mit den nächsten Daten an.

## Tipps

- Sperrmüll wird ab **15:30 Uhr am Vortag** der Abholung rausgestellt.
- Die Abholung erfolgt ab **6:00 Uhr morgens** – früh dran sein lohnt sich.
