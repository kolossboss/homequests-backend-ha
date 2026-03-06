class HomeQuestsOverviewCard extends HTMLElement {
  setConfig(config) {
    if (!config || typeof config !== "object") {
      throw new Error("Ungültige Konfiguration für HomeQuests-Karte.");
    }
    this._config = {
      title: "HomeQuests Übersicht",
      child_count: 3,
      family_id: null,
      children: [],
      ...config,
    };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    const count = Number(this?._config?.child_count ?? 3);
    const safeCount = Number.isFinite(count) && count > 0 ? count : 3;
    return Math.max(4, 2 + safeCount);
  }

  _ensureRoot() {
    if (this._root) return;
    this._root = this.attachShadow({ mode: "open" });
    const style = document.createElement("style");
    style.textContent = `
      :host {
        display: block;
      }
      ha-card {
        padding: 14px;
      }
      .title {
        font-size: 1.1rem;
        font-weight: 600;
        margin-bottom: 10px;
      }
      .section-label {
        font-size: 0.85rem;
        color: var(--secondary-text-color);
        margin: 12px 0 8px 0;
        text-transform: uppercase;
        letter-spacing: 0.06em;
      }
      .global-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(120px, 1fr));
        gap: 8px;
      }
      .children-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
        gap: 10px;
      }
      .tile {
        border-radius: 12px;
        padding: 10px;
        background: var(--ha-card-background, var(--card-background-color));
        border: 1px solid rgba(0, 0, 0, 0.08);
      }
      .tile-title {
        font-size: 0.75rem;
        color: var(--secondary-text-color);
        margin-bottom: 3px;
      }
      .tile-value {
        font-size: 1.2rem;
        font-weight: 700;
      }
      .tile.ok {
        background: rgba(64, 181, 73, 0.15);
        border-color: rgba(64, 181, 73, 0.4);
      }
      .tile.ok-dark {
        background: rgba(28, 94, 32, 0.25);
        border-color: rgba(28, 94, 32, 0.55);
      }
      .tile.warn {
        background: rgba(245, 151, 60, 0.18);
        border-color: rgba(245, 151, 60, 0.45);
      }
      .tile.points {
        background: rgba(245, 151, 60, 0.2);
        border-color: rgba(245, 151, 60, 0.52);
      }
      .tile.info {
        background: rgba(42, 116, 255, 0.18);
        border-color: rgba(42, 116, 255, 0.45);
      }
      .tile.alert {
        background: rgba(226, 44, 44, 0.18);
        border-color: rgba(226, 44, 44, 0.45);
      }
      .child-card {
        border-radius: 14px;
        border: 1px solid rgba(0, 0, 0, 0.1);
        padding: 10px;
      }
      .child-name {
        font-size: 1rem;
        font-weight: 600;
        margin-bottom: 8px;
      }
      .metric-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(70px, 1fr));
        gap: 8px;
      }
      .empty {
        color: var(--secondary-text-color);
        padding: 6px 0;
      }
    `;
    this._root.appendChild(style);
    this._card = document.createElement("ha-card");
    this._root.appendChild(this._card);
  }

  _render() {
    if (!this._config || !this._hass) return;
    this._ensureRoot();

    const data = this._collectData();
    if (!data) {
      this._card.innerHTML = `<div class="title">${this._escape(this._config.title)}</div><div class="empty">Keine HomeQuests-Daten gefunden.</div>`;
      return;
    }

    const globalTiles = [
      this._tile("In Prüfung", data.global.tasks_pending_review_total, data.global.tasks_pending_review_total > 0 ? "warn" : "ok"),
      this._tile("Überfällig", data.global.tasks_overdue_total, data.global.tasks_overdue_total > 0 ? "alert" : "ok"),
      this._tile("Belohnungen offen", data.global.pending_reward_redemptions_total, data.global.pending_reward_redemptions_total > 0 ? "warn" : "ok"),
    ].join("");

    const childrenHtml = data.children
      .map((child) => {
        const dueClass = child.due_today_tasks === 0 ? "ok" : (child.due_today_tasks <= 2 ? "warn" : "alert");
        const overdueClass = child.overdue_tasks >= 1 ? "alert" : "ok";
        return `
          <div class="child-card">
            <div class="child-name">${this._escape(child.display_name)}</div>
            <div class="metric-grid">
              ${this._tile("Punkte", child.points_balance, "points")}
              ${this._tile("Heute fällig", child.due_today_tasks, dueClass)}
              ${this._tile("Überfällig", child.overdue_tasks, overdueClass)}
              ${this._tile("Alle Aufgaben", child.tasks_total, "info")}
              ${this._tile("In Prüfung", child.pending_reviews, child.pending_reviews > 0 ? "warn" : "ok")}
              ${this._tile("Bestätigt", child.approved_tasks, "ok-dark")}
            </div>
          </div>
        `;
      })
      .join("");

    const subtitle = `${data.children.length} Kind${data.children.length === 1 ? "" : "er"} angezeigt`;
    this._card.innerHTML = `
      <div class="title">${this._escape(this._config.title)}<br><span style="font-size:0.8rem;color:var(--secondary-text-color);font-weight:400;">${this._escape(subtitle)}</span></div>
      <div class="section-label">Gesamt</div>
      <div class="global-grid">${globalTiles}</div>
      <div class="section-label">Kinder</div>
      <div class="children-grid">${childrenHtml || '<div class="empty">Keine Kinderdaten gefunden.</div>'}</div>
    `;
  }

  _collectData() {
    const states = Object.values(this._hass.states || {});
    const sensors = states.filter((state) => state.entity_id.startsWith("sensor.") && state.attributes && state.attributes.metric_key);
    if (!sensors.length) return null;

    const familyId = this._resolveFamilyId(sensors);
    if (familyId === null) return null;

    const relevantSensors = sensors.filter((state) => String(state.attributes.family_id) === String(familyId));

    const global = {
      tasks_pending_review_total: 0,
      tasks_overdue_total: 0,
      pending_reward_redemptions_total: 0,
    };
    const byChild = new Map();

    for (const state of relevantSensors) {
      const metricKey = state.attributes.metric_key;
      const value = this._toNumber(state.state);
      const userIdRaw = state.attributes.user_id;
      if (userIdRaw === undefined || userIdRaw === null) {
        if (metricKey in global) {
          global[metricKey] = value;
        }
        continue;
      }

      const userId = String(userIdRaw);
      if (!byChild.has(userId)) {
        byChild.set(userId, {
          user_id: userId,
          display_name: state.attributes.display_name || `Kind ${userId}`,
          points_balance: 0,
          due_today_tasks: 0,
          overdue_tasks: 0,
          tasks_total: 0,
          pending_reviews: 0,
          approved_tasks: 0,
        });
      }
      const child = byChild.get(userId);
      if (metricKey in child) {
        child[metricKey] = value;
      }
    }

    let children = Array.from(byChild.values()).sort((a, b) => a.display_name.localeCompare(b.display_name, "de"));
    children = this._filterChildren(children);

    return { family_id: familyId, global, children };
  }

  _resolveFamilyId(sensors) {
    if (this._config.family_id !== null && this._config.family_id !== undefined) {
      return String(this._config.family_id);
    }
    const first = sensors.find((state) => state.attributes.family_id !== undefined);
    return first ? String(first.attributes.family_id) : null;
  }

  _filterChildren(children) {
    const configuredChildren = Array.isArray(this._config.children) ? this._config.children : [];
    if (configuredChildren.length > 0) {
      const wanted = configuredChildren.map((value) => String(value).toLowerCase());
      return children.filter((child) => wanted.includes(String(child.user_id).toLowerCase()) || wanted.includes(String(child.display_name).toLowerCase()));
    }

    const count = Number(this._config.child_count);
    const safeCount = Number.isFinite(count) && count > 0 ? Math.floor(count) : children.length;
    return children.slice(0, safeCount);
  }

  _tile(title, value, severity = "") {
    return `
      <div class="tile ${severity}">
        <div class="tile-title">${this._escape(title)}</div>
        <div class="tile-value">${this._escape(value)}</div>
      </div>
    `;
  }

  _toNumber(value) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  _escape(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
}

if (!customElements.get("homequests-overview-card")) {
  customElements.define("homequests-overview-card", HomeQuestsOverviewCard);
}

window.customCards = window.customCards || [];
window.customCards.push({
  type: "homequests-overview-card",
  name: "HomeQuests Übersicht",
  description: "Kachel-Übersicht für HomeQuests (Kinder + globale Kennzahlen).",
});
