const CHILD_TILE_KEYS = [
  "points_balance",
  "due_today_tasks",
  "overdue_tasks",
  "tasks_total",
  "pending_reviews",
  "approved_tasks",
];

const GLOBAL_TILE_KEYS = [
  "tasks_pending_review_total",
  "tasks_overdue_total",
  "pending_reward_redemptions_total",
];

const CHILD_TILE_DEFINITIONS = {
  points_balance: {
    title: "Punkte",
    severity: () => "points",
  },
  due_today_tasks: {
    title: "Heute fällig",
    severity: (child) => {
      if (child.due_today_tasks === 0) return "ok";
      if (child.due_today_tasks <= 2) return "warn";
      return "alert";
    },
  },
  overdue_tasks: {
    title: "Überfällig",
    severity: (child) => (child.overdue_tasks >= 1 ? "alert" : "ok"),
  },
  tasks_total: {
    title: "Alle Aufgaben",
    severity: () => "info",
  },
  pending_reviews: {
    title: "In Prüfung",
    severity: (child) => (child.pending_reviews > 0 ? "warn" : "ok"),
  },
  approved_tasks: {
    title: "Bestätigt",
    severity: () => "ok-dark",
  },
};

const GLOBAL_TILE_DEFINITIONS = {
  tasks_pending_review_total: {
    title: "In Prüfung",
    severity: (global) => (global.tasks_pending_review_total > 0 ? "warn" : "ok"),
  },
  tasks_overdue_total: {
    title: "Überfällig",
    severity: (global) => (global.tasks_overdue_total > 0 ? "alert" : "ok"),
  },
  pending_reward_redemptions_total: {
    title: "Belohnungen offen",
    severity: (global) => (global.pending_reward_redemptions_total > 0 ? "warn" : "ok"),
  },
};

class HomeQuestsOverviewCard extends HTMLElement {
  static getStubConfig() {
    return {
      type: "custom:homequests-overview-card",
      title: "HomeQuests Familie",
      child_count: 3,
    };
  }

  static getConfigElement() {
    return document.createElement("homequests-overview-card-editor");
  }

  setConfig(config) {
    if (!config || typeof config !== "object") {
      throw new Error("Ungültige Konfiguration für HomeQuests-Karte.");
    }

    this._config = {
      title: "HomeQuests Übersicht",
      child_count: 3,
      family_id: null,
      children: this._normalizeArrayConfig(config.children),
      child_tile_order: this._normalizeArrayConfig(config.child_tile_order),
      hidden_child_tiles: this._normalizeArrayConfig(config.hidden_child_tiles),
      global_tile_order: this._normalizeArrayConfig(config.global_tile_order),
      hidden_global_tiles: this._normalizeArrayConfig(config.hidden_global_tiles),
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
      .tile.clickable {
        cursor: pointer;
      }
      .tile.clickable:focus-visible {
        outline: 2px solid var(--primary-color);
        outline-offset: 2px;
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

    const globalOrder = this._resolveOrder(
      this._config.global_tile_order,
      GLOBAL_TILE_KEYS,
      this._config.hidden_global_tiles,
    );
    const globalTiles = globalOrder
      .map((key) => {
        const definition = GLOBAL_TILE_DEFINITIONS[key];
        if (!definition) return "";
        return this._tile(
          definition.title,
          data.global[key] ?? 0,
          definition.severity(data.global),
          data.global_entities[key],
        );
      })
      .join("");

    const childOrder = this._resolveOrder(
      this._config.child_tile_order,
      CHILD_TILE_KEYS,
      this._config.hidden_child_tiles,
    );

    const childrenHtml = data.children
      .map((child) => {
        const childTiles = childOrder
          .map((key) => {
            const definition = CHILD_TILE_DEFINITIONS[key];
            if (!definition) return "";
            return this._tile(
              definition.title,
              child[key] ?? 0,
              definition.severity(child),
              child.entities[key],
            );
          })
          .join("");

        return `
          <div class="child-card">
            <div class="child-name">${this._escape(child.display_name)}</div>
            <div class="metric-grid">${childTiles}</div>
          </div>
        `;
      })
      .join("");

    const subtitle = `${data.children.length} Kind${data.children.length === 1 ? "" : "er"} angezeigt`;
    this._card.innerHTML = `
      <div class="title">${this._escape(this._config.title)}<br><span style="font-size:0.8rem;color:var(--secondary-text-color);font-weight:400;">${this._escape(subtitle)}</span></div>
      <div class="section-label">Gesamt</div>
      <div class="global-grid">${globalTiles || '<div class="empty">Keine globalen Kacheln aktiv.</div>'}</div>
      <div class="section-label">Kinder</div>
      <div class="children-grid">${childrenHtml || '<div class="empty">Keine Kinderdaten gefunden.</div>'}</div>
    `;

    this._attachTileClickHandlers();
  }

  _attachTileClickHandlers() {
    const tiles = this._card.querySelectorAll(".tile[data-entity-id]");
    for (const tile of tiles) {
      const entityId = tile.dataset.entityId;
      if (!entityId) continue;
      tile.addEventListener("click", () => this._openMoreInfo(entityId));
      tile.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          this._openMoreInfo(entityId);
        }
      });
    }
  }

  _openMoreInfo(entityId) {
    this.dispatchEvent(
      new CustomEvent("hass-more-info", {
        detail: { entityId },
        bubbles: true,
        composed: true,
      }),
    );
  }

  _resolveOrder(configuredOrder, allowedKeys, hiddenKeys) {
    const hidden = new Set(this._normalizeArrayConfig(hiddenKeys));
    const order = this._normalizeArrayConfig(configuredOrder)
      .filter((key) => allowedKeys.includes(key))
      .filter((key) => !hidden.has(key));
    const remaining = allowedKeys.filter((key) => !order.includes(key) && !hidden.has(key));
    return [...order, ...remaining];
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
    const globalEntities = {};
    const byChild = new Map();

    for (const state of relevantSensors) {
      const metricKey = state.attributes.metric_key;
      const value = this._toNumber(state.state);
      const userIdRaw = state.attributes.user_id;

      if (userIdRaw === undefined || userIdRaw === null) {
        if (metricKey in global) {
          global[metricKey] = value;
          globalEntities[metricKey] = state.entity_id;
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
          entities: {},
        });
      }
      const child = byChild.get(userId);
      if (metricKey in child) {
        child[metricKey] = value;
        child.entities[metricKey] = state.entity_id;
      }
    }

    let children = Array.from(byChild.values()).sort((a, b) => a.display_name.localeCompare(b.display_name, "de"));
    children = this._filterChildren(children);

    return { family_id: familyId, global, global_entities: globalEntities, children };
  }

  _resolveFamilyId(sensors) {
    if (this._config.family_id !== null && this._config.family_id !== undefined && this._config.family_id !== "") {
      return String(this._config.family_id);
    }
    const first = sensors.find((state) => state.attributes.family_id !== undefined);
    return first ? String(first.attributes.family_id) : null;
  }

  _filterChildren(children) {
    const configuredChildren = this._normalizeArrayConfig(this._config.children);
    if (configuredChildren.length > 0) {
      const wanted = configuredChildren.map((value) => String(value).toLowerCase());
      return children.filter((child) => wanted.includes(String(child.user_id).toLowerCase()) || wanted.includes(String(child.display_name).toLowerCase()));
    }

    const count = Number(this._config.child_count);
    const safeCount = Number.isFinite(count) && count > 0 ? Math.floor(count) : children.length;
    return children.slice(0, safeCount);
  }

  _tile(title, value, severity = "", entityId = null) {
    const clickableClass = entityId ? "clickable" : "";
    const dataAttr = entityId ? `data-entity-id="${this._escape(entityId)}"` : "";
    const tabIndex = entityId ? 'tabindex="0" role="button"' : "";
    return `
      <div class="tile ${severity} ${clickableClass}" ${dataAttr} ${tabIndex}>
        <div class="tile-title">${this._escape(title)}</div>
        <div class="tile-value">${this._escape(value)}</div>
      </div>
    `;
  }

  _normalizeArrayConfig(value) {
    if (!value) return [];
    if (Array.isArray(value)) return value.map((item) => String(item).trim()).filter(Boolean);
    if (typeof value === "string") {
      return value.split(",").map((item) => item.trim()).filter(Boolean);
    }
    return [];
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

class HomeQuestsOverviewCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
  }

  _ensureRoot() {
    if (this._root) return;
    this._root = this.attachShadow({ mode: "open" });
    const style = document.createElement("style");
    style.textContent = `
      :host {
        display: block;
      }
      .editor {
        display: grid;
        gap: 10px;
      }
      .field {
        display: grid;
        gap: 4px;
      }
      label {
        font-size: 0.9rem;
        font-weight: 600;
      }
      input, textarea {
        width: 100%;
        box-sizing: border-box;
        padding: 8px;
        border-radius: 8px;
        border: 1px solid var(--divider-color);
        background: var(--card-background-color);
        color: var(--primary-text-color);
        font: inherit;
      }
      .hint {
        font-size: 0.78rem;
        color: var(--secondary-text-color);
      }
    `;
    this._root.appendChild(style);
    this._container = document.createElement("div");
    this._container.className = "editor";
    this._root.appendChild(this._container);
  }

  _render() {
    if (!this._config) return;
    this._ensureRoot();

    this._container.innerHTML = `
      ${this._textField("title", "Titel", this._config.title || "HomeQuests Übersicht")}
      ${this._numberField("child_count", "Anzahl Kinder", this._config.child_count ?? 3)}
      ${this._textField("family_id", "Family ID (optional)", this._config.family_id ?? "")}
      ${this._textField("children", "Kinder (CSV, optional)", this._toCsv(this._config.children))}
      ${this._textField("child_tile_order", "Kind-Kachel-Reihenfolge (CSV)", this._toCsv(this._config.child_tile_order))}
      <div class="hint">Mögliche Werte: ${CHILD_TILE_KEYS.join(", ")}</div>
      ${this._textField("hidden_child_tiles", "Kind-Kacheln ausblenden (CSV)", this._toCsv(this._config.hidden_child_tiles))}
      ${this._textField("global_tile_order", "Globale Kachel-Reihenfolge (CSV)", this._toCsv(this._config.global_tile_order))}
      <div class="hint">Mögliche Werte: ${GLOBAL_TILE_KEYS.join(", ")}</div>
      ${this._textField("hidden_global_tiles", "Globale Kacheln ausblenden (CSV)", this._toCsv(this._config.hidden_global_tiles))}
    `;

    for (const input of this._container.querySelectorAll("input")) {
      input.addEventListener("change", (event) => this._valueChanged(event));
    }
  }

  _textField(key, label, value) {
    return `
      <div class="field">
        <label for="${key}">${label}</label>
        <input id="${key}" data-key="${key}" type="text" value="${this._escape(value)}" />
      </div>
    `;
  }

  _numberField(key, label, value) {
    return `
      <div class="field">
        <label for="${key}">${label}</label>
        <input id="${key}" data-key="${key}" type="number" min="1" value="${this._escape(value)}" />
      </div>
    `;
  }

  _toCsv(value) {
    if (!value) return "";
    if (Array.isArray(value)) return value.join(", ");
    return String(value);
  }

  _valueChanged(event) {
    if (!this._config) return;
    const target = event.target;
    const key = target.dataset.key;
    if (!key) return;

    let value = target.value;
    if (key === "child_count") {
      const parsed = Number(value);
      value = Number.isFinite(parsed) && parsed > 0 ? Math.floor(parsed) : 1;
    } else if (
      key === "children" ||
      key === "child_tile_order" ||
      key === "hidden_child_tiles" ||
      key === "global_tile_order" ||
      key === "hidden_global_tiles"
    ) {
      value = value.split(",").map((item) => item.trim()).filter(Boolean);
    } else if (key === "family_id") {
      value = value.trim();
      if (!value) value = null;
    } else {
      value = value.trim();
    }

    const newConfig = { ...this._config, [key]: value };
    this._config = newConfig;
    this.dispatchEvent(
      new CustomEvent("config-changed", {
        detail: { config: newConfig },
        bubbles: true,
        composed: true,
      }),
    );
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

if (!customElements.get("homequests-overview-card-editor")) {
  customElements.define("homequests-overview-card-editor", HomeQuestsOverviewCardEditor);
}

window.customCards = window.customCards || [];
window.customCards.push({
  type: "homequests-overview-card",
  name: "HomeQuests Übersicht",
  description: "Klickbare Kachel-Übersicht für HomeQuests mit Editor-Unterstützung.",
});
