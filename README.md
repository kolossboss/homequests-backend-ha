# HomeQuests Home Assistant Integration

Custom Integration fuer Home Assistant, die das bestehende HomeQuests-Backend anbindet und als eigenes HACS-Repository installierbar ist.

## Funktionsumfang

- Einrichtung komplett ueber die Home-Assistant-UI
- Login mit Backend-URL, Benutzername/E-Mail und Passwort
- Familien-Device plus ein Device pro Kind
- Globale Sensoren fuer Aufgaben, Pruefungen, Belohnungen und Sonderaufgaben
- Pro-Kind Sensoren fuer Aufgabenstatus, Punkte, Belohnungsanfragen und verfuegbare Sonderaufgaben
- Binary Sensoren fuer Automationen
- Home-Assistant-Event `homequests_event` bei relevanten Aenderungen
- Native Event-Entities pro Familie und pro Kind
- Native To-do-Listen (Familie: Aufgaben in Pruefung, Kind: verfuegbare Aufgaben)
- Native Kalender-Entities (Familie + Kind) fuer faellige Aufgaben mit Due-Date
- Eigene Lovelace Custom Card `homequests-overview-card`
- Live-Refresh ueber SSE (`/live/stream`) plus Polling-Fallback
- Services fuer Review-/Punkte-Workflows
- Diagnostics-Unterstuetzung
- HACS-kompatible Repo-Struktur

## Was die Integration anlegt

### Familienweite Sensoren

- Aufgaben gesamt
- Sonderaufgaben gesamt
- Sonderaufgaben aktiv
- Offene Aufgaben
- Abgelehnte Aufgaben
- Abgeschlossene Aufgaben
- Ueberfaellige Aufgaben
- Eingereichte Aufgaben
- Als nicht erledigt gemeldete Aufgaben
- Aufgaben in Pruefung
- Verfuegbare Aufgaben
- Aktive Belohnungen
- Offene Belohnungsanfragen
- Anstehende Erinnerungen (24h)

### Pro Kind

- Offene Aufgaben
- Abgelehnte Aufgaben
- Heute faellige Aufgaben
- Verfuegbare Aufgaben
- Ueberfaellige Aufgaben
- Eingereichte Aufgaben
- Nicht erledigt gemeldete Aufgaben
- Aufgaben in Pruefung
- Abgeschlossene Einzelaufgaben
- Punktestand
- Offene Belohnungsanfragen
- Verfuegbare Sonderaufgaben

### Binary Sensoren

Familienweit:
- Hat ueberfaellige Aufgaben
- Hat offene Aufgaben-Freigaben
- Hat offene Belohnungsanfragen

Pro Kind:
- Hat ueberfaellige Aufgaben
- Hat Aufgaben in Pruefung
- Hat verfuegbare Sonderaufgaben

### Button

- Jetzt aktualisieren

### Event-Entities

- Pro Familie: Event-Entity fuer HomeQuests-Automationsereignisse
- Pro Kind: Event-Entity mit gefilterten Ereignissen fuer das jeweilige Kind

### To-do-Listen

- Familie: `Aufgaben in Pruefung`
- Pro Kind: `Verfuegbare Aufgaben`

### Kalender

- Familie: `Aufgaben-Kalender`
- Pro Kind: `Aufgaben-Kalender`

### Lovelace Karte

- Custom Card Typ: `custom:homequests-overview-card`
- Resource-URL: `/homequests_frontend/homequests-overview-card.js` (Typ `JavaScript-Modul`)
- Kachel-Design mit globalen Werten plus pro Kind:
  - Punkte
  - Heute faellige Aufgaben (0 = gruen, 1-2 = orange, >2 = rot)
  - Ueberfaellige Aufgaben (>=1 = rot)
  - Alle Aufgaben
  - In Pruefung
  - Bestaetigt
- Konfigurierbar mit `child_count` und optional expliziter `children`-Liste

## Einrichtungsablauf in Home Assistant

1. Repository in GitHub bereitstellen.
2. In HACS unter `Integrationen` dieses Repo als Custom Repository hinzufuegen.
3. Integration `HomeQuests` installieren.
4. Home Assistant neu starten.
5. `Einstellungen -> Geraete & Dienste -> Integration hinzufuegen -> HomeQuests`.
6. Backend-URL, Benutzername/E-Mail und Passwort eingeben.
7. Wenn der Benutzer mehreren Familien angehoert, waehlt man die gewuenschte Familie im zweiten Schritt aus.
8. Danach legt die Integration die passenden Devices/Entities automatisch an.

## Aktualisierung der Werte (Reload vs automatisch)

- Nein, der Reload-Button muss nicht gedrueckt werden, damit neue Werte kommen.
- Die Integration aktualisiert automatisch per Polling (Intervall: 2 Minuten).
- Zusaetzlich wird der Backend-Live-Stream (SSE) genutzt: bei `family_update`/`notification.test` wird zeitnah ein Refresh angestossen.
- Der Reload-Button ist nur fuer sofortige manuelle Aktualisierung gedacht.

## HACS-Struktur

- `custom_components/homequests/manifest.json`
- `custom_components/homequests/__init__.py`
- `custom_components/homequests/config_flow.py`
- `custom_components/homequests/api.py`
- `custom_components/homequests/coordinator.py`
- `custom_components/homequests/sensor.py`
- `custom_components/homequests/binary_sensor.py`
- `custom_components/homequests/button.py`
- `custom_components/homequests/event.py`
- `custom_components/homequests/todo.py`
- `custom_components/homequests/calendar.py`
- `custom_components/homequests/frontend/homequests-overview-card.js`
- `custom_components/homequests/diagnostics.py`
- `custom_components/homequests/services.yaml`
- `custom_components/homequests/strings.json`
- `custom_components/homequests/translations/de.json`
- `custom_components/homequests/brand/icon.png`
- `custom_components/homequests/brand/logo.png`
- `hacs.json`

## Home Assistant Events fuer Automationen

Die Integration feuert bei erkannten Aenderungen das Event `homequests_event` auf den HA-Event-Bus. Das Feld `type` ist eines von:

- `new_available_tasks`
- `tasks_submitted`
- `reward_requests_pending`
- `special_tasks_available`

Beispiel fuer eine Automation:

```yaml
alias: HomeQuests Freigaben melden
triggers:
  - trigger: event
    event_type: homequests_event
    event_data:
      type: tasks_submitted
actions:
  - action: notify.mobile_app_iphone
    data:
      title: HomeQuests
      message: >-
        {{ trigger.event.data.family_name }}: {{ trigger.event.data.delta_count }} neue Aufgabe(n) in Pruefung.
mode: queued
```

## Services

- `homequests.refresh`
- `homequests.review_task`
- `homequests.review_missed_task`
- `homequests.review_redemption`
- `homequests.adjust_points`
- `homequests.submit_task`
- `homequests.report_task_missed`

Wenn mehrere HomeQuests-Eintraege vorhanden sind, `entry_id` mitsenden.

## Dashboard-Beispiel

Ein fertiges Lovelace-Beispiel liegt unter [examples/lovelace-dashboard.yaml](/Users/macminiserver/Documents/Xcode/Familienplaner/backend-HA-integration/examples/lovelace-dashboard.yaml).
Ein Custom-Card-Beispiel liegt unter [examples/lovelace-homequests-card.yaml](/Users/macminiserver/Documents/Xcode/Familienplaner/backend-HA-integration/examples/lovelace-homequests-card.yaml).

## Annahmen und Grenzen

- Das Backend liefert keine globale Instanz-ID. Der Config-Entry-Unique-Identifier basiert deshalb auf `Backend-URL + family_id`.
- Bei mehreren Familien wird im Config Flow eine Familie ausgewaehlt; pro Familie entsteht ein eigener Config Entry.
- `verfuegbare Aufgaben` orientieren sich an der vorhandenen Web-UI-Logik: offene oder abgelehnte, aktuell bearbeitbare Aufgaben.
- Sonderaufgaben werden fuer Admin-/Eltern-Zugaenge lokal aus Templates und bereits beanspruchten Aufgaben abgeleitet, weil der Backend-Endpunkt fuer `available` nur fuer Kinder verfuegbar ist.
- Integrations-Icons in HA sind versionsabhaengig: lokale `brand/`-Assets werden erst in neueren HA-Versionen direkt genutzt. In aelteren Versionen kommt das Icon aus dem zentralen HA-Brands-System.

## Weiterfuehrende Doku

- [Backend-Analyse](/Users/macminiserver/Documents/Xcode/Familienplaner/backend-HA-integration/docs/API_ANALYSIS.md)
- [Testanleitung](/Users/macminiserver/Documents/Xcode/Familienplaner/backend-HA-integration/docs/TESTING.md)
- [Offene Punkte und Risiken](/Users/macminiserver/Documents/Xcode/Familienplaner/backend-HA-integration/docs/OPEN_POINTS.md)
- [GitHub-Repo-Befehle](/Users/macminiserver/Documents/Xcode/Familienplaner/backend-HA-integration/GITHUB_REPO_COMMANDS.md)
