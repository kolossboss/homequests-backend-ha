# Testanleitung

## 1. Struktur lokal pruefen

Im Repo-Ordner ausfuehren:

```bash
python3 -m compileall custom_components
```

## 2. Integration in Home Assistant einbinden

### Variante A: direkt lokal

- Repo nach `/config/custom_components/homequests` kopieren oder als Git-Submodule/Checkout einbinden.
- Home Assistant neu starten.

### Variante B: ueber HACS

- GitHub-Repo anlegen und pushen.
- In HACS als Custom Repository vom Typ `Integration` hinzufuegen.
- `HomeQuests` installieren.
- Home Assistant neu starten.

## 3. Config Flow testen

1. `Einstellungen -> Geraete & Dienste -> Integration hinzufuegen`.
2. `HomeQuests` waehlen.
3. Backend-URL, Benutzername/E-Mail und Passwort eingeben.
4. Erfolgsfall: Familie und Kinder-Devices werden angelegt.

## 4. Sensoren pruefen

- Familie: offene Aufgaben, Pruefungen, Belohnungsanfragen, Erinnerungen
- Pro Kind: offene/verfuegbare/ueberfaellige Aufgaben, Punkte, Sonderaufgaben

## 5. Services pruefen

Beispiel im Developer-Tool `Aktionen`:

```yaml
action: homequests.review_task
data:
  task_id: 123
  decision: approved
```

Weitere sinnvolle Tests:
- `homequests.review_missed_task`
- `homequests.review_redemption`
- `homequests.adjust_points`
- `homequests.refresh`

## 6. Automations-Event pruefen

Im Entwicklerwerkzeug `Ereignisse` auf `homequests_event` lauschen und dann im Backend eine neue Aufgabe einreichen oder verfuegbar machen.

Erwartete Felder:
- `type`
- `family_id`
- `family_name`
- optional `member_user_id`
- optional `member_name`
- `delta_count`
- `item_ids`
- `items`
- `device_id` (falls passendes HA-Device existiert)

## 7. Diagnostics pruefen

- `Einstellungen -> Geraete & Dienste -> HomeQuests -> Diagnose herunterladen`
- pruefen, dass Passwoerter und personenbezogene Felder redigiert sind
