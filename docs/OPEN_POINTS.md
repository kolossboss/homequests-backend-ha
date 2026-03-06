# Offene Punkte, Annahmen und Risiken

## Klare Annahmen

1. Der konfigurierte Benutzer ist `admin` oder `parent`.
2. Falls ein Benutzer mehreren Familien zugeordnet ist, wird im Config Flow eine Familie ausgewaehlt.
3. Naive Datumswerte aus dem Backend werden wie in der vorhandenen Web-UI interpretiert und fuer die Verfuegbarkeitslogik lokal bewertet.
4. `verfuegbare Aufgaben` sollen die aktuell bearbeitbaren Aufgaben spiegeln, nicht nur reine `status=open`-Eintraege.

## Bekannte Luecken der ersten Version

Aktuell keine offenen funktionalen MVP-Luecken.

## Risiken

1. Wenn kuenftig eine Backend-Instanz-ID hinzukommt, sollte der Config-Entry-Unique-Identifier darauf umgestellt werden.
2. Falls sich Backend-Datumslogik oder Task-Kategorisierung aendert, muessen die abgeleiteten HA-Sensoren nachgezogen werden.
3. Service-Aufrufe wie `submit_task` und `report_task_missed` schlagen mit Eltern-/Admin-Zugang erwartungsgemaess fehl, wenn das Backend die Aktion nur fuer das zugewiesene Kind erlaubt.
4. Der SSE-Live-Stream wird parallel zu Polling genutzt; falls Reverse Proxy/Netzwerk `text/event-stream` unterbricht, faellt die Integration automatisch auf Polling zurueck.
