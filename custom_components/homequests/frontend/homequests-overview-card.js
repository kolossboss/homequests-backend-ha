const CHILD_TILE_KEYS = [
  "points_balance",
  "due_today_tasks",
  "overdue_tasks",
  "tasks_total",
  "available_tasks",
  "pending_reviews",
  "approved_tasks",
  "open_tasks",
  "pending_reward_requests",
];

const STATUS_KEYS = [
  ["open", "Offen", "#2f7cf6"],
  ["submitted", "Prüfung", "#ff9f0a"],
  ["missed_submitted", "Verpasst", "#ff3b30"],
  ["approved", "Bestätigt", "#1f8f45"],
  ["rejected", "Abgelehnt", "#bf5af2"],
];

const PIE_COLORS = ["#0a84ff", "#30d158", "#ff9f0a", "#bf5af2", "#ff453a", "#64d2ff", "#ffd60a"];

const CHILD_TILE_DEFINITIONS = {
  points_balance: { title: "Punkte", severity: () => "points" },
  due_today_tasks: {
    title: "Heute fällig",
    severity: (child) => (child.due_today_tasks === 0 ? "ok" : child.due_today_tasks <= 2 ? "warn" : "alert"),
  },
  overdue_tasks: { title: "Überfällig", severity: (child) => (child.overdue_tasks > 0 ? "alert" : "ok") },
  tasks_total: { title: "Alle Aufgaben", severity: () => "info" },
  available_tasks: { title: "Verfügbar", severity: (child) => (child.available_tasks > 0 ? "info" : "quiet") },
  pending_reviews: { title: "In Prüfung", severity: (child) => (child.pending_reviews > 0 ? "warn" : "ok") },
  approved_tasks: { title: "Bestätigt", severity: () => "ok-dark" },
  open_tasks: { title: "Offen", severity: () => "info" },
  pending_reward_requests: {
    title: "Belohnungen",
    severity: (child) => (child.pending_reward_requests > 0 ? "reward" : "quiet"),
  },
};

class HomeQuestsChildCard extends HTMLElement {
  static getStubConfig() {
    return {
      title: "HomeQuests",
      child_name: "",
      show_status_distribution: true,
      show_reward_pie: true,
    };
  }

  static getConfigElement() {
    return document.createElement("homequests-child-card-editor");
  }

  setConfig(config) {
    if (!config || typeof config !== "object") {
      throw new Error("Ungültige Konfiguration für HomeQuests-Karte.");
    }
    this._config = {
      title: "HomeQuests",
      family_id: null,
      child_id: null,
      child_name: "",
      tile_order: [],
      hidden_tiles: [],
      pie_mode: "requests",
      show_status_distribution: true,
      show_reward_pie: true,
      ...config,
    };
    this._selectedRewardId = null;
    this._pieMode = this._config.pie_mode === "spent" ? "spent" : "requests";
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 7;
  }

  getGridOptions() {
    return {
      rows: 7,
      columns: 6,
      min_rows: 5,
      min_columns: 4,
    };
  }

  _ensureRoot() {
    if (this._root) return;
    this._root = this.attachShadow({ mode: "open" });
    const style = document.createElement("style");
    style.textContent = `
      :host { display: block; }
      ha-card {
        overflow: hidden;
        border-radius: 14px;
        background:
          linear-gradient(135deg, rgba(10, 132, 255, 0.14), rgba(48, 209, 88, 0.08)),
          var(--ha-card-background, var(--card-background-color));
      }
      .shell { padding: 14px; display: grid; gap: 12px; }
      .hero {
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 12px;
        align-items: start;
      }
      .eyebrow {
        margin: 0 0 3px;
        color: var(--secondary-text-color);
        font-size: 0.76rem;
        letter-spacing: 0;
      }
      .name {
        margin: 0;
        font-size: 1.25rem;
        line-height: 1.15;
        font-weight: 750;
      }
      .points-pill {
        min-width: 84px;
        border-radius: 12px;
        padding: 8px 10px;
        text-align: right;
        background: rgba(255, 159, 10, 0.18);
        border: 1px solid rgba(255, 159, 10, 0.42);
      }
      .points-pill span {
        display: block;
        font-size: 0.72rem;
        color: var(--secondary-text-color);
      }
      .points-pill strong {
        display: block;
        font-size: 1.35rem;
        line-height: 1.1;
      }
      .tile-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 8px;
      }
      @media (min-width: 520px) {
        .tile-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }
      }
      .tile {
        min-height: 72px;
        border-radius: 10px;
        padding: 9px;
        border: 1px solid rgba(255,255,255,0.1);
        background: rgba(255,255,255,0.045);
        display: grid;
        align-content: space-between;
      }
      .tile.clickable { cursor: pointer; }
      .tile.clickable:focus-visible {
        outline: 2px solid var(--primary-color);
        outline-offset: 2px;
      }
      .tile-title { font-size: 0.72rem; color: var(--secondary-text-color); }
      .tile-value { font-size: 1.25rem; font-weight: 800; line-height: 1.1; }
      .tile.ok { background: rgba(48, 209, 88, 0.15); border-color: rgba(48, 209, 88, 0.4); }
      .tile.ok-dark { background: rgba(31, 143, 69, 0.24); border-color: rgba(31, 143, 69, 0.55); }
      .tile.warn, .tile.points { background: rgba(255, 159, 10, 0.2); border-color: rgba(255, 159, 10, 0.48); }
      .tile.info { background: rgba(10, 132, 255, 0.18); border-color: rgba(10, 132, 255, 0.42); }
      .tile.alert { background: rgba(255, 59, 48, 0.18); border-color: rgba(255, 59, 48, 0.48); }
      .tile.reward { background: rgba(191, 90, 242, 0.16); border-color: rgba(191, 90, 242, 0.44); }
      .section {
        border-radius: 12px;
        border: 1px solid rgba(255,255,255,0.1);
        background: rgba(255,255,255,0.035);
        padding: 10px;
      }
      .section-head {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 10px;
        margin-bottom: 9px;
      }
      .section-head h4 { margin: 0; font-size: 0.95rem; }
      .segmented {
        display: inline-grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        border-radius: 9px;
        overflow: hidden;
        border: 1px solid rgba(255,255,255,0.12);
      }
      .segmented button {
        border: 0;
        background: transparent;
        color: var(--secondary-text-color);
        padding: 6px 8px;
        font: inherit;
        font-size: 0.78rem;
        cursor: pointer;
      }
      .segmented button.active {
        color: var(--primary-text-color);
        background: rgba(10, 132, 255, 0.2);
      }
      .status-list { display: grid; gap: 8px; }
      .status-row { display: grid; gap: 4px; }
      .status-label { display: flex; justify-content: space-between; font-size: 0.78rem; }
      .track { height: 7px; border-radius: 999px; background: rgba(255,255,255,0.08); overflow: hidden; }
      .fill { display: block; height: 100%; border-radius: inherit; }
      .pie-area {
        display: grid;
        grid-template-columns: 150px minmax(0, 1fr);
        gap: 10px;
        align-items: center;
      }
      @media (max-width: 480px) {
        .pie-area { grid-template-columns: 1fr; }
      }
      .pie-wrap {
        position: relative;
        min-height: 150px;
        display: grid;
        place-items: center;
      }
      .pie-svg { width: 146px; height: 146px; }
      .pie-segment { cursor: pointer; transition: stroke-width 160ms ease, opacity 160ms ease; }
      .pie-segment.active { filter: drop-shadow(0 0 7px rgba(255,255,255,0.28)); }
      .pie-center {
        position: absolute;
        width: 70px;
        height: 70px;
        border-radius: 999px;
        background: rgba(8,10,14,0.72);
        border: 1px solid rgba(255,255,255,0.12);
        display: grid;
        place-content: center;
        text-align: center;
      }
      .pie-center strong { font-size: 1.05rem; line-height: 1; }
      .pie-center small { color: var(--secondary-text-color); font-size: 0.68rem; }
      .legend { display: grid; gap: 6px; }
      .legend-button {
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 9px;
        background: rgba(255,255,255,0.035);
        color: var(--primary-text-color);
        display: grid;
        grid-template-columns: 10px minmax(0, 1fr) auto;
        gap: 7px;
        align-items: center;
        padding: 7px;
        text-align: left;
        cursor: pointer;
      }
      .legend-button.active { border-color: rgba(10,132,255,0.52); background: rgba(10,132,255,0.15); }
      .dot { width: 9px; height: 9px; border-radius: 999px; }
      .legend-title { font-size: 0.78rem; font-weight: 700; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .legend-value { font-size: 0.76rem; color: var(--secondary-text-color); }
      .empty { color: var(--secondary-text-color); font-size: 0.85rem; }
    `;
    this._root.appendChild(style);
    this._card = document.createElement("ha-card");
    this._root.appendChild(this._card);
  }

  _render() {
    if (!this._config || !this._hass) return;
    this._ensureRoot();
    const data = this._collectData();
    if (!data || !data.child) {
      this._card.innerHTML = `<div class="shell"><p class="empty">Kein Kind gefunden. Setze in der Karte child_id oder child_name.</p></div>`;
      return;
    }

    const child = data.child;
    const order = this._resolveTileOrder();
    const tiles = order.map((key) => {
      const definition = CHILD_TILE_DEFINITIONS[key];
      return definition ? this._tile(definition.title, child[key] ?? 0, definition.severity(child), child.entities[key]) : "";
    }).join("");

    this._card.innerHTML = `
      <div class="shell">
        <div class="hero">
          <div>
            <p class="eyebrow">${this._escape(this._config.title || "HomeQuests")}</p>
            <h3 class="name">${this._escape(child.display_name)}</h3>
          </div>
          <div class="points-pill">
            <span>Punkte</span>
            <strong>${this._escape(child.points_balance)}</strong>
          </div>
        </div>
        <div class="tile-grid">${tiles}</div>
        ${this._config.show_status_distribution === false ? "" : this._statusSection(child)}
        ${this._config.show_reward_pie === false ? "" : this._rewardPieSection(child)}
      </div>
    `;
    this._wireTileClicks();
    this._wirePieControls(child);
  }

  _statusSection(child) {
    const total = STATUS_KEYS.reduce((sum, [key]) => sum + Number(child.status_distribution[key] || 0), 0);
    const rows = STATUS_KEYS.map(([key, label, color]) => {
      const value = Number(child.status_distribution[key] || 0);
      const pct = total > 0 ? Math.round((value / total) * 100) : 0;
      return `
        <div class="status-row">
          <div class="status-label"><span>${this._escape(label)}</span><strong>${value} (${pct}%)</strong></div>
          <div class="track"><span class="fill" style="width:${pct}%;background:${color}"></span></div>
        </div>
      `;
    }).join("");
    return `<div class="section"><div class="section-head"><h4>Statusverteilung</h4></div><div class="status-list">${rows}</div></div>`;
  }

  _rewardPieSection(child) {
    const series = this._rewardSeries(child);
    const buttons = `
      <div class="segmented">
        <button type="button" data-pie-mode="requests" class="${this._pieMode === "requests" ? "active" : ""}">Häufigkeit</button>
        <button type="button" data-pie-mode="spent" class="${this._pieMode === "spent" ? "active" : ""}">Punkte</button>
      </div>
    `;
    if (!series.length) {
      return `<div class="section"><div class="section-head"><h4>Belohnungen</h4>${buttons}</div><p class="empty">Noch keine Belohnungsdaten vorhanden.</p></div>`;
    }

    if (!series.some((entry) => entry.id === this._selectedRewardId)) {
      this._selectedRewardId = series[0].id;
    }
    const total = series.reduce((sum, entry) => sum + entry.value, 0);
    let offset = 0;
    const radius = 46;
    const circumference = 2 * Math.PI * radius;
    const selected = series.find((entry) => entry.id === this._selectedRewardId) || series[0];
    const circles = series.map((entry, index) => {
      const arc = total > 0 ? circumference * (entry.value / total) : 0;
      const active = entry.id === selected.id;
      const segment = `<circle class="pie-segment ${active ? "active" : ""}" cx="70" cy="70" r="${radius}" fill="none" stroke="${PIE_COLORS[index % PIE_COLORS.length]}" stroke-width="${active ? 22 : 19}" stroke-dasharray="${arc} ${Math.max(circumference - arc, 0)}" stroke-dashoffset="${-offset}" transform="rotate(-90 70 70)" data-reward-id="${entry.id}"></circle>`;
      offset += arc;
      return segment;
    }).join("");
    const share = total > 0 ? Math.round((selected.value / total) * 100) : 0;
    const legend = series.map((entry, index) => {
      const active = entry.id === selected.id;
      const itemShare = total > 0 ? Math.round((entry.value / total) * 100) : 0;
      return `<button type="button" class="legend-button ${active ? "active" : ""}" data-reward-id="${entry.id}"><span class="dot" style="background:${PIE_COLORS[index % PIE_COLORS.length]}"></span><span class="legend-title">${this._escape(entry.title)}</span><span class="legend-value">${entry.value} · ${itemShare}%</span></button>`;
    }).join("");

    return `
      <div class="section">
        <div class="section-head"><h4>Belohnungen</h4>${buttons}</div>
        <div class="pie-area">
          <div class="pie-wrap">
            <svg viewBox="0 0 140 140" class="pie-svg" aria-label="Belohnungsdiagramm">
              <circle cx="70" cy="70" r="${radius}" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="19"></circle>
              ${circles}
            </svg>
            <div class="pie-center"><strong>${this._escape(selected.value)}</strong><small>${share}%</small></div>
          </div>
          <div class="legend">${legend}</div>
        </div>
      </div>
    `;
  }

  _rewardSeries(child) {
    const source = this._pieMode === "spent" ? child.reward_spent_stats : child.reward_request_stats;
    return (Array.isArray(source) ? source : []).map((entry) => {
      if (this._pieMode === "spent") {
        return {
          id: Number(entry.reward_id),
          title: String(entry.reward_title || "Belohnung"),
          value: Number(entry.points_spent || 0),
        };
      }
      return {
        id: Number(entry.reward_id),
        title: String(entry.reward_title || "Belohnung"),
        value: Number(entry.request_count || 0),
      };
    }).filter((entry) => entry.id && entry.value > 0);
  }

  _wirePieControls(child) {
    for (const button of this._card.querySelectorAll("[data-pie-mode]")) {
      button.addEventListener("click", () => {
        this._pieMode = button.dataset.pieMode === "spent" ? "spent" : "requests";
        this._selectedRewardId = null;
        this._render();
      });
    }
    for (const item of this._card.querySelectorAll("[data-reward-id]")) {
      item.addEventListener("click", () => {
        this._selectedRewardId = Number(item.dataset.rewardId);
        this._render();
      });
    }
  }

  _wireTileClicks() {
    for (const tile of this._card.querySelectorAll(".tile[data-entity-id]")) {
      const entityId = tile.dataset.entityId;
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
    this.dispatchEvent(new CustomEvent("hass-more-info", { detail: { entityId }, bubbles: true, composed: true }));
  }

  _collectData() {
    const states = Object.values(this._hass.states || {});
    const sensors = states.filter((state) => state.entity_id.startsWith("sensor.") && state.attributes?.metric_key);
    if (!sensors.length) return null;
    const familyId = this._resolveFamilyId(sensors);
    const relevant = familyId ? sensors.filter((state) => String(state.attributes.family_id) === String(familyId)) : sensors;
    const children = this._childrenFromSensors(relevant);
    return { child: this._selectChild(children) };
  }

  _childrenFromSensors(sensors) {
    const byChild = new Map();
    for (const state of sensors) {
      const userIdRaw = state.attributes.user_id;
      if (userIdRaw === undefined || userIdRaw === null) continue;
      const userId = String(userIdRaw);
      if (!byChild.has(userId)) {
        byChild.set(userId, {
          user_id: userId,
          display_name: state.attributes.display_name || `Kind ${userId}`,
          entities: {},
          reward_request_stats: [],
          reward_spent_stats: [],
          status_distribution: {},
        });
      }
      const child = byChild.get(userId);
      const key = state.attributes.metric_key;
      child[key] = this._toNumber(state.state);
      child.entities[key] = state.entity_id;
      if (key === "points_balance") {
        child.reward_request_stats = Array.isArray(state.attributes.reward_request_stats) ? state.attributes.reward_request_stats : [];
        child.reward_spent_stats = Array.isArray(state.attributes.reward_spent_stats) ? state.attributes.reward_spent_stats : [];
        child.status_distribution = state.attributes.status_distribution || {};
        child.lifetime_earned_points = this._toNumber(state.attributes.lifetime_earned_points);
        child.lifetime_spent_points = this._toNumber(state.attributes.lifetime_spent_points);
      }
    }
    return Array.from(byChild.values()).sort((a, b) => a.display_name.localeCompare(b.display_name, "de"));
  }

  _selectChild(children) {
    if (!children.length) return null;
    if (this._config.child_id !== null && this._config.child_id !== undefined && this._config.child_id !== "") {
      const child = children.find((entry) => String(entry.user_id) === String(this._config.child_id));
      if (child) return child;
    }
    if (this._config.child_name) {
      const wanted = String(this._config.child_name).toLowerCase();
      const child = children.find((entry) => String(entry.display_name).toLowerCase() === wanted);
      if (child) return child;
    }
    return children[0];
  }

  _resolveFamilyId(sensors) {
    if (this._config.family_id !== null && this._config.family_id !== undefined && this._config.family_id !== "") {
      return String(this._config.family_id);
    }
    const first = sensors.find((state) => state.attributes.family_id !== undefined);
    return first ? String(first.attributes.family_id) : null;
  }

  _resolveTileOrder() {
    const hidden = new Set(this._normalizeArrayConfig(this._config.hidden_tiles));
    const configured = this._normalizeArrayConfig(this._config.tile_order).filter((key) => CHILD_TILE_KEYS.includes(key));
    const remaining = CHILD_TILE_KEYS.filter((key) => !configured.includes(key));
    return [...configured, ...remaining].filter((key) => !hidden.has(key));
  }

  _tile(title, value, severity, entityId) {
    const data = entityId ? `data-entity-id="${this._escape(entityId)}" tabindex="0" role="button"` : "";
    return `<div class="tile ${this._escape(severity)} ${entityId ? "clickable" : ""}" ${data}><span class="tile-title">${this._escape(title)}</span><strong class="tile-value">${this._escape(value)}</strong></div>`;
  }

  _normalizeArrayConfig(value) {
    if (!value) return [];
    if (Array.isArray(value)) return value.map((item) => String(item).trim()).filter(Boolean);
    return String(value).split(",").map((item) => item.trim()).filter(Boolean);
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

class HomeQuestsChildCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._config) {
      this._render();
    }
  }

  _ensureRoot() {
    if (this._root) return;
    this._root = this.attachShadow({ mode: "open" });
    const style = document.createElement("style");
    style.textContent = `
      .editor { display: grid; gap: 10px; }
      .field { display: grid; gap: 4px; }
      label { font-size: 0.9rem; font-weight: 600; }
      input,
      select {
        width: 100%;
        box-sizing: border-box;
        padding: 8px;
        border-radius: 8px;
        border: 1px solid var(--divider-color);
        background: var(--card-background-color);
        color: var(--primary-text-color);
        font: inherit;
      }
      .hint { font-size: 0.78rem; color: var(--secondary-text-color); }
      .toggle-row { display: flex; align-items: center; gap: 8px; }
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
      ${this._textField("title", "Titel", this._config.title || "HomeQuests")}
      ${this._selectField("child_id", "Kind", this._config.child_id ?? "", this._childOptions())}
      ${this._textField("child_name", "Kind-Name Fallback", this._config.child_name ?? "")}
      ${this._textField("family_id", "Family ID (optional)", this._config.family_id ?? "")}
      ${this._textField("tile_order", "Kachel-Reihenfolge (CSV)", this._toCsv(this._config.tile_order))}
      <div class="hint">Mögliche Werte: ${CHILD_TILE_KEYS.join(", ")}</div>
      ${this._textField("hidden_tiles", "Kacheln ausblenden (CSV)", this._toCsv(this._config.hidden_tiles))}
      ${this._textField("pie_mode", "Pie-Modus: requests oder spent", this._config.pie_mode || "requests")}
      ${this._toggleField("show_status_distribution", "Statusverteilung anzeigen", this._config.show_status_distribution !== false)}
      ${this._toggleField("show_reward_pie", "Belohnungsdiagramm anzeigen", this._config.show_reward_pie !== false)}
    `;
    for (const input of this._container.querySelectorAll("input, select")) {
      input.addEventListener("change", (event) => this._valueChanged(event));
    }
  }

  _textField(key, label, value) {
    return `<div class="field"><label for="${key}">${label}</label><input id="${key}" data-key="${key}" type="text" value="${this._escape(value)}" /></div>`;
  }

  _selectField(key, label, value, options) {
    const optionMarkup = [
      { value: "", label: "Automatisch erstes Kind" },
      ...options,
    ].map((option) => {
      const selected = String(value ?? "") === String(option.value) ? "selected" : "";
      return `<option value="${this._escape(option.value)}" ${selected}>${this._escape(option.label)}</option>`;
    }).join("");
    return `<div class="field"><label for="${key}">${label}</label><select id="${key}" data-key="${key}">${optionMarkup}</select></div>`;
  }

  _toggleField(key, label, checked) {
    return `<label class="toggle-row"><input data-key="${key}" type="checkbox" ${checked ? "checked" : ""} />${label}</label>`;
  }

  _valueChanged(event) {
    const target = event.target;
    const key = target.dataset.key;
    if (!key) return;
    let value = target.type === "checkbox" ? target.checked : target.value;
    if (["tile_order", "hidden_tiles"].includes(key)) {
      value = String(value).split(",").map((item) => item.trim()).filter(Boolean);
    } else if (["child_id", "child_name", "family_id"].includes(key)) {
      value = String(value).trim() || null;
    } else if (key === "pie_mode") {
      value = String(value).trim() === "spent" ? "spent" : "requests";
    } else if (typeof value === "string") {
      value = value.trim();
    }
    const config = { ...this._config, [key]: value };
    this._config = config;
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
  }

  _toCsv(value) {
    if (!value) return "";
    return Array.isArray(value) ? value.join(", ") : String(value);
  }

  _childOptions() {
    if (!this._hass) return [];
    const configuredFamilyId = this._config?.family_id;
    const byUser = new Map();
    for (const state of Object.values(this._hass.states || {})) {
      const attrs = state.attributes || {};
      if (!state.entity_id?.startsWith("sensor.") || !attrs.metric_key || attrs.user_id === undefined || attrs.user_id === null) {
        continue;
      }
      if (configuredFamilyId && String(attrs.family_id) !== String(configuredFamilyId)) {
        continue;
      }
      const userId = String(attrs.user_id);
      const familySuffix = attrs.family_id !== undefined ? ` · Familie ${attrs.family_id}` : "";
      byUser.set(userId, {
        value: userId,
        label: `${attrs.display_name || `Kind ${userId}`}${familySuffix}`,
      });
    }
    return Array.from(byUser.values()).sort((a, b) => a.label.localeCompare(b.label, "de"));
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

if (!customElements.get("homequests-child-card")) {
  customElements.define("homequests-child-card", HomeQuestsChildCard);
}

if (!customElements.get("homequests-overview-card")) {
  customElements.define("homequests-overview-card", HomeQuestsChildCard);
}

if (!customElements.get("homequests-child-card-editor")) {
  customElements.define("homequests-child-card-editor", HomeQuestsChildCardEditor);
}

window.customCards = window.customCards || [];
window.customCards.push({
  type: "homequests-child-card",
  name: "HomeQuests Kind",
  description: "Kind-Fokus-Karte mit Aufgaben, Punkten und Belohnungsdiagramm.",
});
