# Analyse des bestehenden HomeQuests-Backends

## Technologie

- FastAPI-Anwendung unter `backend/app/main.py`
- JWT-Bearer-Authentifizierung in `backend/app/security.py`
- Rollenmodell: `admin`, `parent`, `child`
- Live-Events per Server-Sent Events unter `/families/{family_id}/live/stream`
- Die HA-Integration nutzt den Live-Stream fuer zeitnahe Refresh-Trigger und behaelt Polling als Fallback bei

## Authentifizierung

### Login

- `POST /auth/login`
- Request:

```json
{
  "login": "anzeigename-oder-email",
  "password": "..."
}
```

- Response:

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer"
}
```

### Benutzerkontext

- `GET /auth/me`
- benoetigt `Authorization: Bearer <token>`

## Familien und Mitglieder

- `GET /families/my`
- `GET /families/{family_id}/members`

Mitgliedsdaten:
- `membership_id`
- `family_id`
- `user_id`
- `display_name`
- `email`
- `is_active`
- `role`
- `created_at`

## Aufgaben

### Relevante Endpunkte

- `GET /families/{family_id}/tasks`
- `GET /families/{family_id}/tasks/reminders/upcoming?window_minutes=...`
- `POST /tasks/{task_id}/submit`
- `POST /tasks/{task_id}/report-missed`
- `POST /tasks/{task_id}/review`
- `POST /tasks/{task_id}/missed-review`
- `POST /tasks/{task_id}/active`
- `DELETE /tasks/{task_id}`

### Task-Statuswerte

- `open`
- `submitted`
- `missed_submitted`
- `approved`
- `rejected`

### Task-Felder

- `id`
- `family_id`
- `title`
- `description`
- `assignee_id`
- `due_at`
- `points`
- `reminder_offsets_minutes`
- `active_weekdays`
- `recurrence_type`
- `penalty_enabled`
- `penalty_points`
- `penalty_last_applied_at`
- `special_template_id`
- `is_active`
- `status`
- `created_by_id`
- `created_at`
- `updated_at`

### Recurrence-/Scheduling-Werte

- `recurrence_type`: `none`, `daily`, `weekly`, `monthly`
- Wochentage: `0=Mo` bis `6=So`
- Reminder-Minuten: `{15, 30, 60, 120, 1440, 2880}`

## Sonderaufgaben

### Endpunkte

- `GET /families/{family_id}/special-tasks/templates`
- `GET /families/{family_id}/special-tasks/available` (nur Kind-Rolle)
- `POST /special-tasks/templates/{template_id}/claim`

### Template-Felder

- `id`
- `family_id`
- `title`
- `description`
- `points`
- `interval_type`: `daily`, `weekly`, `monthly`
- `max_claims_per_interval`
- `active_weekdays`
- `due_time_hhmm`
- `is_active`
- `created_at`
- `updated_at`

## Punkte

### Endpunkte

- `GET /families/{family_id}/points/balances`
- `GET /families/{family_id}/points/balance/{user_id}`
- `GET /families/{family_id}/points/ledger`
- `GET /families/{family_id}/points/ledger/{user_id}`
- `POST /families/{family_id}/points/adjust`

### Punktequellen

- `task_approval`
- `reward_redemption`
- `reward_contribution`
- `task_penalty`
- `manual_adjustment`

## Belohnungen

### Endpunkte

- `GET /families/{family_id}/rewards`
- `GET /families/{family_id}/rewards/{reward_id}/contributions`
- `POST /rewards/{reward_id}/contribute`
- `POST /rewards/{reward_id}/redeem`
- `GET /families/{family_id}/redemptions`
- `POST /redemptions/{redemption_id}/review`

### Reward-Felder

- `id`
- `family_id`
- `title`
- `description`
- `cost_points`
- `is_shareable`
- `is_active`

### Redemption-Statuswerte

- `pending`
- `approved`
- `rejected`

## Live-Event-Typen im Backend

Direkt im Backend gefunden:
- `task.created`
- `task.updated`
- `task.deleted`
- `task.submitted`
- `task.missed_reported`
- `task.reviewed`
- `task.due_reminder`
- `reward.created`
- `reward.updated`
- `reward.deleted`
- `reward.redeem_requested`
- `reward.redeem_reviewed`
- `reward.contribution.updated`
- `points.adjusted`
- `member.created`
- `member.updated`
- `member.deleted`
- `event.created`
- `special_task_template.created`
- `special_task_template.updated`
- `special_task_template.deleted`
- `notification.test`

## Fachliche Ableitungen fuer die HA-Integration

- `Aufgaben in Pruefung` = `submitted + missed_submitted`
- `Verfuegbare Aufgaben` orientieren sich an der Web-UI (`open`/`rejected`, aktuell bearbeitbar)
- `Ueberfaellige Aufgaben` = bearbeitbare Aufgaben mit `due_at < now`
- `Verfuegbare Sonderaufgaben` werden bei Eltern/Admin lokal aus Templates, Zeitfenster und bereits beanspruchten Aufgaben berechnet
