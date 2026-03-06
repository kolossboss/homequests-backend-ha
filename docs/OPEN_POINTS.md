# Offene Punkte, Annahmen und Risiken

## Klare Annahmen

1. Der konfigurierte Benutzer ist `admin` oder `parent`.
2. `GET /families/my` liefert genau den relevanten Haushalt; die Integration nutzt die erste Familie.
3. Naive Datumswerte aus dem Backend werden wie in der vorhandenen Web-UI interpretiert und fuer die Verfuegbarkeitslogik lokal bewertet.
4. `verfuegbare Aufgaben` sollen die aktuell bearbeitbaren Aufgaben spiegeln, nicht nur reine `status=open`-Eintraege.

## Bekannte Luecken der ersten Version

1. Kein dauerhafter SSE-Client auf `/live/stream`; Aenderungserkennung erfolgt per Polling.
2. Keine Event-Entity-Plattform, sondern HA-Bus-Event `homequests_event`.
3. Keine native To-do-Entity oder Kalender-Entity fuer Aufgaben/Events.
4. Kein eigener Lovelace-Frontend-Baustein; stattdessen ein Standard-Lovelace-Beispiel.
5. Mehrfamilien-Support pro Benutzer ist im Backend praktisch nicht vorgesehen; die Integration waehlt deshalb nicht interaktiv zwischen mehreren Familien.

## Risiken

1. Wenn kuenftig eine Backend-Instanz-ID hinzukommt, sollte der Config-Entry-Unique-Identifier darauf umgestellt werden.
2. Falls sich Backend-Datumslogik oder Task-Kategorisierung aendert, muessen die abgeleiteten HA-Sensoren nachgezogen werden.
3. Service-Aufrufe wie `submit_task` und `report_task_missed` schlagen mit Eltern-/Admin-Zugang erwartungsgemaess fehl, wenn das Backend die Aktion nur fuer das zugewiesene Kind erlaubt.
