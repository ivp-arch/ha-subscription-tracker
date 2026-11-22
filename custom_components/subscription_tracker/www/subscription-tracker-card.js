// Home Assistant may load the resource before the Lovelace panel is defined (e.g. a
// page opened outside a dashboard): wait for it. Needs the resource as a JavaScript module.
await customElements.whenDefined("ha-panel-lovelace");
const LitElement = Object.getPrototypeOf(customElements.get("ha-panel-lovelace"));
const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

const CARD_VERSION = "0.5.0";
const THEMES = ["auto", "orbit"];
const MODES = ["auto", "dark", "light"];
const PALETTE_SIZE = 6;

// Generic glyphs per category (no brands), same drawings as the Orbit mockup.
// Drawn here, no external resources.
const ICONS = {
  video: html`<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="3"></rect><polygon points="10 9 15 12 10 15 10 9"></polygon></svg>`,
  audio: html`<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="4" y1="10" x2="4" y2="14"></line><line x1="8" y1="7" x2="8" y2="17"></line><line x1="12" y1="4" x2="12" y2="20"></line><line x1="16" y1="8" x2="16" y2="16"></line><line x1="20" y1="11" x2="20" y2="13"></line></svg>`,
  other: html`<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 7l9-4 9 4-9 4z"></path><path d="M3 7v10l9 4 9-4V7"></path><line x1="12" y1="11" x2="12" y2="21"></line></svg>`,
  paused: html`<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="6" y="5" width="4" height="14" rx="1"></rect><rect x="14" y="5" width="4" height="14" rx="1"></rect></svg>`,
};
const TIP_ICON = html`<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 18h6"></path><path d="M10 21h4"></path><path d="M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0 0 12 3z"></path></svg>`;

class SubscriptionTrackerCard extends LitElement {
  static get properties() {
    return { hass: {}, _config: {}, _open: {}, theme: { reflect: true, type: String }, scheme: { reflect: true, type: String } };
  }

  constructor() {
    super();
    this._open = null;
    this.theme = "auto";
    this.scheme = "dark";
  }

  // Orbit colour scheme: "mode" forces it, otherwise it follows Home Assistant
  // (hass.themes.darkMode). If HA does not report it, keep the historical dark look.
  _computeScheme() {
    const m = this._config?.mode;
    if (m === "dark" || m === "light") return m;
    return this.hass?.themes?.darkMode === false ? "light" : "dark";
  }

  willUpdate(changed) {
    if (changed.has("hass") || changed.has("_config")) {
      const scheme = this._computeScheme();
      if (scheme !== this.scheme) this.scheme = scheme;
    }
  }

  setConfig(config) {
    const theme = THEMES.includes(config?.theme) ? config.theme : "auto";
    const mode = MODES.includes(config?.mode) ? config.mode : "auto";
    this._config = {
      summary_entity: "sensor.subscriptions_total",
      show_paused: true,
      show_tip: true,
      show_timeline: true,
      show_budget: true,
      ...config,
      theme,
      mode,
    };
    this.theme = theme;
  }

  getCardSize() {
    const n = this.hass ? this._subscriptions().length : 3;
    return 3 + (this._config?.show_timeline ? 2 : 0) + n;
  }

  static getStubConfig() {
    return { summary_entity: "sensor.subscriptions_total" };
  }

  // Visual editor: HA renders this schema with its own controls (static getConfigForm,
  // https://contributors.home-assistant.io/frontend/custom-ui/card-editor/).
  // Labels are Italian like the rest of the card until the card is localized.
  static getConfigForm() {
    const filter = { domain: "sensor", integration: "subscription_tracker" };
    const boolean = (name) => ({ name, default: true, selector: { boolean: {} } });
    const labels = {
      summary_entity: "Sensore di riepilogo",
      entities: "Abbonamenti (opzionale)",
      theme: "Stile",
      mode: "Schema colori Orbit",
      show_timeline: "Mostra la timeline dei rinnovi",
      show_budget: "Mostra il budget",
      show_paused: "Mostra gli abbonamenti in pausa",
      show_tip: "Mostra il suggerimento",
    };
    const helpers = {
      summary_entity: "Il sensore «Subscriptions total» creato dall'integrazione.",
      entities: "Lascia vuoto per includere automaticamente tutti gli abbonamenti.",
      theme: "Se non scegli nulla viene usato il tema di Home Assistant.",
      mode: "Solo con lo stile Orbit. Automatico segue il tema chiaro o scuro di Home Assistant.",
    };
    return {
      schema: [
        { name: "summary_entity", default: "sensor.subscriptions_total", selector: { entity: { filter } } },
        { name: "entities", selector: { entity: { multiple: true, filter } } },
        {
          type: "grid",
          name: "",
          schema: [
            {
              name: "theme",
              default: "auto",
              selector: {
                select: {
                  mode: "dropdown",
                  options: [
                    { value: "auto", label: "Tema di Home Assistant" },
                    { value: "orbit", label: "Orbit" },
                  ],
                },
              },
            },
            {
              name: "mode",
              default: "auto",
              visible: { field: "theme", value: "orbit" },
              selector: {
                select: {
                  mode: "dropdown",
                  options: [
                    { value: "auto", label: "Automatico" },
                    { value: "dark", label: "Scuro" },
                    { value: "light", label: "Chiaro" },
                  ],
                },
              },
            },
          ],
        },
        {
          type: "grid",
          name: "",
          schema: ["show_timeline", "show_budget", "show_paused", "show_tip"].map(boolean),
        },
      ],
      computeLabel: (schema) => labels[schema.name],
      computeHelper: (schema) => helpers[schema.name],
      // Throwing disables the visual editor (YAML the form cannot represent).
      assertConfig: (config) => {
        if (config.entities !== undefined && !(Array.isArray(config.entities) && config.entities.every((e) => typeof e === "string"))) {
          throw new Error("entities deve essere un elenco di entità.");
        }
        if (config.theme !== undefined && !THEMES.includes(config.theme)) {
          throw new Error("theme non supportato dall'editor visuale.");
        }
        if (config.mode !== undefined && !MODES.includes(config.mode)) {
          throw new Error("mode non supportato dall'editor visuale.");
        }
        for (const k of ["show_timeline", "show_budget", "show_paused", "show_tip"]) {
          if (config[k] !== undefined && typeof config[k] !== "boolean") {
            throw new Error(`${k} deve essere vero o falso.`);
          }
        }
      },
    };
  }

  /* ---------- data ---------- */

  get _summary() {
    return this.hass.states[this._config.summary_entity];
  }

  _subscriptions() {
    // If the user lists entities explicitly we use them, otherwise we take
    // every sensor that exposes the integration's attributes.
    // An empty list (what the visual editor writes when the field is cleared) means
    // auto-discovery too. The summary sensor is never a subscription.
    const manual = Array.isArray(this._config.entities) && this._config.entities.length > 0;
    const ids = (manual
      ? this._config.entities
      : Object.keys(this.hass.states).filter((id) => {
        const s = this.hass.states[id];
        return (
          id.startsWith("sensor.") &&
          s.attributes.display_name !== undefined &&
          s.attributes.billing_cycle !== undefined
        );
      })
    ).filter((id) => id !== this._config.summary_entity);

    return ids
      .map((id) => this.hass.states[id])
      .filter(Boolean)
      .filter((s) => this._config.show_paused || s.attributes.status !== "paused")
      .sort((a, b) => {
        const pa = a.attributes.status === "paused" ? 1 : 0;
        const pb = b.attributes.status === "paused" ? 1 : 0;
        if (pa !== pb) return pa - pb;
        return this._daysForSort(a) - this._daysForSort(b);
      });
  }

  _daysForSort(stateObj) {
    // 0 days (renewal today) is a valid value: only non-numeric states go last.
    const n = Number(stateObj.state);
    return stateObj.state !== "" && Number.isFinite(n) ? n : 9999;
  }

  /* ---------- formatting (presentation only) ---------- */

  _date(iso) {
    // "YYYY-MM-DD" is parsed as UTC by new Date(): we read it as a local date.
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || "");
    return m ? new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])) : new Date(iso);
  }

  _money(value, currency, digits = 2) {
    if (value === null || value === undefined || isNaN(value)) return "—";
    return new Intl.NumberFormat("it-IT", {
      style: "currency",
      currency: currency || "EUR",
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
      useGrouping: "always",
    }).format(Number(value));
  }

  _trend(a, currency) {
    // Change against the previous month: shown only when the integration provides it.
    const change = a.change_vs_previous;
    if (change === null || change === undefined || isNaN(change)) return null;
    const n = Number(change);
    if (n === 0) return { tone: "", text: "Invariata rispetto al mese scorso" };
    const sign = n > 0 ? "+" : "−";
    const pct = a.change_vs_previous_pct;
    const pctText =
      pct === null || pct === undefined || isNaN(pct)
        ? ""
        : ` (${sign}${Math.abs(Number(pct)).toFixed(1).replace(".", ",")} %)`;
    return {
      tone: n > 0 ? "tone-warn" : "tone-ok",
      text: `${sign}${this._money(Math.abs(n), currency)}${pctText} rispetto al mese scorso`,
    };
  }

  _moneyCompact(value, currency) {
    // "100 €" for whole amounts, "85,50 €" otherwise.
    const n = Number(value);
    return this._money(n, currency, Number.isInteger(n) ? 0 : 2);
  }

  _amount(value) {
    // Bare amount without currency, as in the timeline labels ("19,99").
    return Number(value).toFixed(2).replace(".", ",");
  }

  _shortDate(iso) {
    if (!iso) return "—";
    return this._date(iso).toLocaleDateString("it-IT", { day: "numeric", month: "short" });
  }

  _longDate(iso) {
    if (!iso) return "—";
    return this._date(iso).toLocaleDateString("it-IT", {
      day: "numeric",
      month: "long",
      year: "numeric",
    });
  }

  _cycleLabel(cycle) {
    return { monthly: "mensile", quarterly: "trimestrale", semiannual: "semestrale", yearly: "annuale" }[cycle] || cycle;
  }

  _urgency(days) {
    if (days <= 3) return "danger";
    if (days <= 7) return "warn";
    if (days <= 14) return "ok";
    return "info";
  }

  _daysLabel(days) {
    if (days === 0) return "oggi";
    if (days === 1) return "domani";
    return `tra ${days} giorni`;
  }

  _palette(service) {
    // Stable color per service, picked from the --stc-palette-* tokens.
    let h = 0;
    for (const ch of String(service || "")) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
    return `var(--_p${(h % PALETTE_SIZE) + 1})`;
  }

  /* ---------- contextual tip ---------- */

  _tip() {
    const sum = this._summary;
    if (!sum) return null;
    const expiring = sum.attributes.expiring || [];
    const currency = sum.attributes.currency || "EUR";

    if (expiring.length >= 2) {
      const span = expiring[expiring.length - 1].days - expiring[0].days;
      if (span <= 7) {
        const tot = expiring.reduce((acc, e) => acc + Number(e.cost || 0), 0);
        const names = expiring.map((e) => e.display_name || e.name).join(" e ");
        const when = span === 0 ? "lo stesso giorno" : `a ${span} giorni di distanza`;
        return {
          pre: `${names} si rinnovano ${when}: `,
          strong: this._money(tot, currency),
          post: " nella stessa settimana.",
        };
      }
    }

    const subs = this._subscriptions();
    const paused = subs.find((s) => s.attributes.status === "paused");
    if (paused) {
      return { pre: `${paused.attributes.display_name} è in pausa: valuta se disdirlo del tutto.` };
    }

    const risen = subs
      .filter((s) => Number(s.attributes.price_change_pct) > 20)
      .sort((a, b) => b.attributes.price_change_pct - a.attributes.price_change_pct)[0];
    if (risen) {
      return {
        pre: `${risen.attributes.display_name} è aumentato del `,
        strong: `${Math.round(risen.attributes.price_change_pct)} %`,
        post: " da quando sei cliente.",
      };
    }

    return null;
  }

  /* ---------- price history ---------- */

  _priceChart(stateObj) {
    const history = (stateObj.attributes.price_history || []).slice().sort((a, b) =>
      a.date < b.date ? -1 : 1
    );
    if (history.length === 0) {
      return html`<div class="empty">Storico prezzi non ancora disponibile.</div>`;
    }
    if (history.length === 1) {
      return html`<div class="empty">Un solo prezzo registrato finora.</div>`;
    }

    const W = 320;
    const H = 96;
    const prices = history.map((h) => Number(h.price));
    const min = Math.min(...prices);
    const max = Math.max(...prices);
    const range = max - min || 1;

    const x = (i) => 4 + (i / Math.max(history.length - 1, 1)) * (W - 8);
    const y = (p) => 70 - ((p - min) / range) * 46;

    // Step line: the price stays constant until it changes.
    let d = `${x(0)},${y(prices[0])}`;
    for (let i = 1; i < history.length; i++) {
      d += ` ${x(i)},${y(prices[i - 1])} ${x(i)},${y(prices[i])}`;
    }

    const summary = history
      .map((h) => `${this._date(h.date).getFullYear()}: ${this._amount(h.price)}`)
      .join(", ");

    // Built with createElementNS: nested html templates inside an <svg>
    // would create elements in the HTML namespace and the labels would not be drawn.
    const NS = "http://www.w3.org/2000/svg";
    const el = (tag, attrs = {}, text) => {
      const n = document.createElementNS(NS, tag);
      for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, String(v));
      if (text !== undefined) n.textContent = text;
      return n;
    };
    const svg = el("svg", {
      viewBox: `0 0 ${W} ${H}`,
      class: "chart",
      role: "img",
      "aria-label": "Storico dei prezzi. " + summary,
    });
    svg.append(
      el("line", { x1: 0, y1: 76, x2: W, y2: 76, class: "chart-base" }),
      el("polyline", {
        points: d, fill: "none", class: "chart-line", "stroke-width": 2,
        "stroke-linejoin": "round", "stroke-linecap": "round",
      })
    );
    history.forEach((h, i) => {
      const last = i === history.length - 1;
      const anchor = last ? "end" : i === 0 ? "start" : "middle";
      svg.append(
        el("text", { x: x(i), y: y(prices[i]) - 7, class: "chart-label", "text-anchor": anchor }, this._amount(h.price)),
        el("text", { x: x(i), y: H - 3, class: "chart-axis", "text-anchor": anchor }, String(this._date(h.date).getFullYear()))
      );
    });
    return svg;
  }

  /* ---------- render ---------- */

  _toggle(entityId) {
    this._open = this._open === entityId ? null : entityId;
  }

  _renderRing(a, currency) {
    const pct = Number(a.budget_used_pct);
    const shown = Math.max(0, Math.min(pct, 100));
    const R = 44;
    const C = 2 * Math.PI * R;
    const label = `Spesa al ${Math.round(pct)} % della soglia mensile di ${this._moneyCompact(a.budget, currency)}`;
    return html`
      <div class="ring ${a.budget_exceeded ? "tone-danger" : "tone-accent"}">
        <svg width="116" height="116" viewBox="0 0 116 116" role="img" aria-label=${label}>
          <circle class="ring-dots" cx="58" cy="58" r="52" fill="none" stroke-width="1" stroke-dasharray="1.5 4.5"></circle>
          <circle class="ring-track" cx="58" cy="58" r=${R} fill="none" stroke-width="7"></circle>
          <circle class="ring-bar" cx="58" cy="58" r=${R} fill="none" stroke-width="7"
                  stroke-linecap="round" transform="rotate(-90 58 58)"
                  stroke-dasharray=${`${(C * shown) / 100} ${C}`}></circle>
        </svg>
        <span class="ring-center" aria-hidden="true">
          <span class="ring-pct">${Math.round(pct)}%</span>
          <span class="ring-of">di ${this._moneyCompact(a.budget, currency)}</span>
        </span>
      </div>
    `;
  }

  _renderHeader() {
    const sum = this._summary;
    if (!sum) {
      return html`<div class="header"><span class="lbl">
        Sensore di riepilogo non trovato: ${this._config.summary_entity}
      </span></div>`;
    }

    const a = sum.attributes;
    const currency = a.currency || "EUR";
    const hasBudget =
      this._config.show_budget && a.budget !== null && a.budget !== undefined &&
      a.budget_used_pct !== null && a.budget_used_pct !== undefined;
    const rem = Number(a.budget_remaining);
    const trend = this._trend(a, currency);

    return html`
      <div class="header">
        <div class="head-main">
          <span class="lbl">Spesa ricorrente</span>
          <div class="kpi-value">
            <span class="big">${Number(sum.state).toFixed(2).replace(".", ",")}</span>
            <span class="unit">${currency === "EUR" ? "€" : currency}/mese</span>
          </div>
          ${hasBudget
            ? html`<div class="head-note ${a.budget_exceeded ? "tone-danger" : ""}">
                ${a.budget_exceeded
                  ? `Budget superato di ${this._money(Math.abs(rem), currency)}`
                  : `Restano ${this._money(rem, currency)} questo mese`}
              </div>`
            : ""}
          ${trend ? html`<div class="head-note ${trend.tone}">${trend.text}</div>` : ""}
          ${a.mixed_currency
            ? html`<div class="head-note">
                Esclusi ${a.other_currency_count} abbonamenti in un'altra valuta
              </div>`
            : ""}
        </div>
        ${hasBudget ? this._renderRing(a, currency) : ""}
      </div>

      <div class="stats">
        <div><span class="lbl-s">Attivi</span><span class="stat-value">${a.active_count ?? "—"}</span></div>
        <div><span class="lbl-s">Annuo</span><span class="stat-value">${this._money(a.yearly_cost, currency, 0)}</span></div>
        <div><span class="lbl-s">In pausa</span><span class="stat-value muted">${a.paused_count ?? 0}</span></div>
      </div>
    `;
  }

  _renderTimeline() {
    const sum = this._summary;
    if (!sum || !this._config.show_timeline) return "";
    const a = sum.attributes;
    const items = Array.isArray(a.upcoming) ? a.upcoming : [];
    const window = Number(a.upcoming_days) || 30;
    const currency = a.currency || "EUR";
    const end = new Date();
    end.setDate(end.getDate() + window);
    const endLabel = end
      .toLocaleDateString("it-IT", { day: "numeric", month: "short" })
      .replace(".", "");

    // Labels of marks closer than 9 % to the previous one go below the line.
    let lastLeft = -100;
    let lastBelow = true;
    const marks = items.map((it) => {
      const left = Math.max(0, Math.min(100, (it.days / window) * 100));
      const below = left - lastLeft < 9 ? !lastBelow : false;
      lastLeft = left;
      lastBelow = below;
      return { it, left, below };
    });

    return html`
      <section class="timeline" aria-labelledby="stc-tl-title">
        <div class="tl-head">
          <h3 id="stc-tl-title" class="lbl">Prossimi ${window} giorni</h3>
          <span class="tl-total">${items.length ? this._money(a.upcoming_total, currency) + " in uscita" : ""}</span>
        </div>
        ${items.length
          ? html`
              <div class="tl-track" aria-hidden="true">
                <div class="tl-line"></div>
                <div class="tl-today"></div>
                <span class="tl-edge tl-start">Oggi</span>
                ${marks.map(
                  ({ it, left, below }) => html`<div class="tl-mark tone-${this._urgency(it.days)} ${below ? "below" : ""}"
                      style=${`left:${left}%`}>
                      <span class="tl-amt">${this._amount(it.cost)}</span>
                      <span class="tl-dot"></span>
                    </div>`
                )}
                <span class="tl-edge tl-end">${endLabel}</span>
              </div>
              <ol class="sr-only">
                ${items.map(
                  (it) => html`<li>${it.display_name || it.name}: ${this._money(it.cost, currency)},
                    ${this._daysLabel(it.days)} (${this._shortDate(it.renewal)})</li>`
                )}
              </ol>
            `
          : html`<div class="empty">Nessun rinnovo nei prossimi ${window} giorni.</div>`}
      </section>
    `;
  }

  _rowMeta(a, paused, currency) {
    if (paused) return "In pausa";
    if (a.shared_count > 1) return `1 di ${a.shared_count}`;
    if (a.billing_cycle !== "monthly") return `${this._money(a.monthly_cost, currency)}/mese`;
    return "Solo io";
  }

  _renderRow(s) {
    const a = s.attributes;
    const days = Number(s.state);
    const paused = a.status === "paused";
    const open = this._open === s.entity_id;
    const currency = a.currency || "EUR";
    const kind = paused ? "paused" : ICONS[a.category] ? a.category : "other";
    const color = paused ? "var(--_muted)" : this._palette(a.service);
    const detailId = "stc-d-" + s.entity_id.replace(/\W/g, "_");
    const showPill = !paused && a.status === "expiring_soon";

    return html`
      <div class="sub ${open ? "open" : ""} ${paused ? "paused" : ""}" style=${`--c:${color}`}>
        <button type="button" class="row" aria-expanded=${open ? "true" : "false"}
                aria-controls=${detailId} @click=${() => this._toggle(s.entity_id)}>
          <span class="svc-icon">${a.custom_icon && !paused
            ? html`<ha-icon .icon=${a.custom_icon}></ha-icon>`
            : ICONS[kind]}</span>
          <span class="row-main">
            <span class="row-title">
              <span class="name">${a.display_name}</span>
              ${showPill
                ? html`<span class="pill tone-${days <= 3 ? "danger" : "warn"}">${days} gg</span>`
                : ""}
            </span>
            <span class="row-sub">
              ${paused
                ? `${a.plan ? a.plan + " · " : ""}in pausa`
                : `${a.plan ? a.plan + " · " : ""}${this._cycleLabel(a.billing_cycle)} · ${this._shortDate(a.next_renewal)}`}
            </span>
          </span>
          <span class="row-right">
            <span class="cost">${paused ? "—" : this._money(a.cost, currency)}</span>
            <span class="row-meta">${this._rowMeta(a, paused, currency)}</span>
          </span>
        </button>
        ${open ? this._renderDetail(s, detailId) : ""}
      </div>
    `;
  }

  _renderDetail(s, detailId) {
    const a = s.attributes;
    const currency = a.currency || "EUR";
    const paused = a.status === "paused";

    const rows = [
      ["Ciclo", this._cycleLabel(a.billing_cycle)],
      ["Prossimo rinnovo", paused ? "In pausa" : this._longDate(a.next_renewal)],
      ["Profili condivisi", a.shared_count > 1 ? `${a.shared_count} persone` : "Solo io"],
    ];
    if (a.subscribed_since) {
      const years = Math.floor(a.subscribed_days / 365);
      rows.push([
        "Cliente dal",
        `${this._date(a.subscribed_since).toLocaleDateString("it-IT", { month: "long", year: "numeric" })} · ${years} ${years === 1 ? "anno" : "anni"}`,
      ]);
    }
    if (a.notes) rows.push(["Note", a.notes]);

    const total = Number(a.price_change_total);
    const hasDelta = a.price_change_total !== undefined && a.price_change_total !== null;
    const delta = !hasDelta
      ? ""
      : total === 0
      ? "nessuna variazione"
      : `${total > 0 ? "+" : "−"}${this._money(Math.abs(total), currency)} · ${total > 0 ? "+" : "−"}${Math.abs(Math.round(Number(a.price_change_pct)))}%`;

    return html`
      <div class="detail" id=${detailId}>
        <div class="detail-kpis">
          <div><span class="lbl-s">Per ciclo</span><span class="detail-kpi">${this._money(a.cost, currency)}</span></div>
          <div><span class="lbl-s">Al mese</span><span class="detail-kpi">${this._money(a.monthly_cost, currency)}</span></div>
          <div><span class="lbl-s">A persona</span><span class="detail-kpi">${this._money(a.cost_per_person, currency)}</span></div>
        </div>

        <div class="facts">
          ${rows.map(([k, v]) => html`<div class="fact"><span>${k}</span><span class="v">${v}</span></div>`)}
        </div>

        <div class="history">
          <div class="history-head">
            <span class="lbl">Storico prezzo</span>
            <span class="delta ${total > 0 ? "tone-warn" : total < 0 ? "tone-ok" : "muted"}">${delta}</span>
          </div>
          ${this._priceChart(s)}
        </div>

        <div class="detail-actions">
          <button type="button" class="btn" @click=${() => this._more(s.entity_id)}>
            Dettagli entità
          </button>
        </div>
      </div>
    `;
  }

  _more(entityId) {
    const ev = new Event("hass-more-info", { bubbles: true, composed: true });
    ev.detail = { entityId };
    this.dispatchEvent(ev);
  }

  render() {
    if (!this.hass || !this._config) return html``;

    const subs = this._subscriptions();
    const tip = this._config.show_tip ? this._tip() : null;

    return html`
      <ha-card>
        ${this._renderHeader()} ${this._renderTimeline()}
        <div class="list">
          ${subs.length
            ? subs.map((s) => this._renderRow(s))
            : html`<div class="empty">Nessun abbonamento configurato.</div>`}
        </div>
        ${tip
          ? html`<div class="tip">
              ${TIP_ICON}
              <span>${tip.pre}${tip.strong ? html`<span class="tip-strong">${tip.strong}</span>` : ""}${tip.post || ""}</span>
            </div>`
          : ""}
      </ha-card>
    `;
  }

  static get styles() {
    return css`
      /* Public tokens: --stc-*. When not set they inherit the Home Assistant theme.
         They can be overridden from an HA theme or card-mod. The theme: orbit preset
         sets fixed values. The --_x aliases are internal. */
      :host {
        display: block;
        --_bg: var(--stc-bg, var(--ha-card-background, var(--card-background-color, #fff)));
        --_surface: var(--stc-surface, var(--secondary-background-color, #f5f5f5));
        --_border: var(--stc-border, var(--divider-color, #e0e0e0));
        --_border-strong: var(--stc-border-strong, var(--divider-color, #e0e0e0));
        --_track: var(--stc-track, var(--divider-color, #e0e0e0));
        --_text: var(--stc-text, var(--primary-text-color, #212121));
        --_muted: var(--stc-muted, var(--secondary-text-color, #727272));
        --_accent: var(--stc-accent, var(--primary-color, #03a9f4));
        --_ok: var(--stc-ok, var(--success-color, #2e7d32));
        --_warn: var(--stc-warn, var(--warning-color, #b26a00));
        --_danger: var(--stc-danger, var(--error-color, #c62828));
        --_info: var(--stc-info, var(--info-color, #0288d1));
        /* Contrast-safe variants derived from the theme: -t for text (mixed toward the
           text colour), -g for graphics (dots, ring). Orbit overrides them below. */
        --_ok-t: color-mix(in srgb, var(--_ok) 50%, var(--_text));
        --_warn-t: color-mix(in srgb, var(--_warn) 50%, var(--_text));
        --_danger-t: color-mix(in srgb, var(--_danger) 50%, var(--_text));
        --_info-t: color-mix(in srgb, var(--_info) 50%, var(--_text));
        --_accent-t: color-mix(in srgb, var(--_accent) 55%, var(--_text));
        --_ok-g: color-mix(in srgb, var(--_ok) 70%, var(--_text));
        --_warn-g: color-mix(in srgb, var(--_warn) 70%, var(--_text));
        --_danger-g: color-mix(in srgb, var(--_danger) 70%, var(--_text));
        --_info-g: color-mix(in srgb, var(--_info) 70%, var(--_text));
        --_accent-g: color-mix(in srgb, var(--_accent) 70%, var(--_text));
        --_p1: var(--stc-palette-1, var(--red-color, #e53935));
        --_p2: var(--stc-palette-2, var(--amber-color, #ffb300));
        --_p3: var(--stc-palette-3, var(--green-color, #43a047));
        --_p4: var(--stc-palette-4, var(--blue-color, #1e88e5));
        --_p5: var(--stc-palette-5, var(--purple-color, #8e24aa));
        --_p6: var(--stc-palette-6, var(--cyan-color, #00acc1));
        --_radius: var(--stc-radius, var(--ha-card-border-radius, 12px));
        --_row-radius: var(--stc-row-radius, 16px);
        --_font: var(--stc-font, inherit);
        --_font-display: var(--stc-font-display, inherit);
        --_font-mono: var(--stc-font-mono, inherit);
      }
      :host([theme="orbit"]) {
        --stc-bg: #0c1019;
        --stc-surface: #121826;
        --stc-border: #1c2331;
        --stc-border-strong: #232c3d;
        --stc-track: #1a2130;
        --stc-text: #e8ecf4;
        --stc-muted: #9aa4b6;
        --stc-accent: #4fd6f0;
        --stc-ok: #3ddc84;
        --stc-warn: #f5b74a;
        --stc-danger: #ff5a5f;
        --stc-info: #4fa8ff;
        --stc-palette-1: #ff5a5f;
        --stc-palette-2: #f2c94c;
        --stc-palette-3: #3ddc84;
        --stc-palette-4: #4fa8ff;
        --stc-palette-5: #8c7cff;
        --stc-palette-6: #4fd6f0;
        --stc-radius: 24px;
        --stc-row-radius: 16px;
        --stc-font: Inter, system-ui, sans-serif;
        --stc-font-display: "Space Grotesk", Inter, system-ui, sans-serif;
        --stc-font-mono: "JetBrains Mono", ui-monospace, monospace;
        --_ok-t: var(--_ok); --_warn-t: var(--_warn); --_danger-t: var(--_danger);
        --_info-t: var(--_info); --_accent-t: var(--_accent);
        --_ok-g: var(--_ok); --_warn-g: var(--_warn); --_danger-g: var(--_danger);
        --_info-g: var(--_info); --_accent-g: var(--_accent);
      }

      ha-card {
        display: block;
        overflow: hidden;
        background: var(--_bg);
        color: var(--_text);
        border-radius: var(--_radius);
        font-family: var(--_font);
      }
      /* Orbit, light scheme: used when Home Assistant is in light mode (or mode: light). */
      :host([theme="orbit"][scheme="light"]) {
        --stc-bg: #ffffff;
        --stc-surface: #f4f6fa;
        --stc-border: #e3e8f0;
        --stc-border-strong: #d3dae6;
        --stc-track: #e6eaf2;
        --stc-text: #0f1623;
        --stc-muted: #55607a;
        --stc-accent: #0b7a91;
        --stc-ok: #1b7f45;
        --stc-warn: #935600;
        --stc-danger: #c1282f;
        --stc-info: #1f6fc4;
        --stc-palette-1: #d9363e;
        --stc-palette-2: #a66f00;
        --stc-palette-3: #1b7f45;
        --stc-palette-4: #1f6fc4;
        --stc-palette-5: #6d5bd0;
        --stc-palette-6: #0b7a91;
      }
      :host([theme="orbit"]) ha-card { border: 1px solid var(--_border); }

      .tone-ok { color: var(--_ok-t); --_g: var(--_ok-g); }
      .tone-warn { color: var(--_warn-t); --_g: var(--_warn-g); }
      .tone-danger { color: var(--_danger-t); --_g: var(--_danger-g); }
      .tone-accent { color: var(--_accent-t); --_g: var(--_accent-g); }
      .tone-info { color: var(--_info-t); --_g: var(--_info-g); }
      .muted { color: var(--_muted); }

      .sr-only {
        position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
        overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0;
      }

      button { font: inherit; color: inherit; }
      button:focus-visible { outline: 2px solid var(--_accent-g); outline-offset: -2px; }

      /* Small uppercase labels */
      .lbl, .lbl-s {
        font-family: var(--_font-mono); text-transform: uppercase; color: var(--_muted);
        font-weight: 400; margin: 0;
      }
      .lbl { font-size: 11px; letter-spacing: 0.14em; }
      .lbl-s { font-size: 10px; letter-spacing: 0.1em; }

      /* Header */
      .header {
        display: flex; align-items: center; justify-content: space-between; gap: 16px;
        padding: 22px 22px 18px;
      }
      .head-main { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
      .kpi-value { display: flex; align-items: baseline; gap: 6px; }
      .big {
        font-family: var(--_font-display); font-size: 46px; font-weight: 500;
        line-height: 1; letter-spacing: -0.02em;
      }
      .unit { font-size: 14px; color: var(--_muted); }
      .head-note { font-size: 12px; color: var(--_muted); }
      .head-note.tone-ok { color: var(--_ok-t); }
      .head-note.tone-warn { color: var(--_warn-t); }
      .head-note.tone-danger { color: var(--_danger-t); }

      .ring { position: relative; width: 116px; height: 116px; flex: none; }
      .ring svg { display: block; }
      .ring-dots { stroke: var(--_border); }
      .ring-track { stroke: var(--_track); }
      .ring-bar { stroke: var(--_g, currentColor); }
      .ring-center {
        position: absolute; inset: 0; display: flex; flex-direction: column;
        align-items: center; justify-content: center; gap: 2px;
      }
      .ring-pct { font-family: var(--_font-display); font-size: 22px; font-weight: 500; color: var(--_text); }
      .ring-of { font-family: var(--_font-mono); font-size: 10px; color: var(--_muted); }

      /* Stat strip */
      .stats {
        display: grid; grid-template-columns: repeat(3, minmax(0, 1fr));
        border-top: 1px solid var(--_border); border-bottom: 1px solid var(--_border);
      }
      .stats > div { display: flex; flex-direction: column; gap: 4px; padding: 12px 16px; }
      .stats > div:first-child { padding-left: 22px; }
      .stats > div + div { border-left: 1px solid var(--_border); }
      .stat-value { font-family: var(--_font-display); font-size: 18px; font-weight: 500; }

      /* Timeline */
      .timeline {
        display: flex; flex-direction: column; gap: 14px;
        padding: 18px 22px 20px; border-bottom: 1px solid var(--_border);
      }
      .tl-head { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
      .tl-total { font-size: 13px; }
      .tl-track { position: relative; height: 64px; }
      .tl-line {
        position: absolute; left: 0; right: 0; top: 26px; height: 2px;
        background: var(--_border); border-radius: 2px;
      }
      .tl-today { position: absolute; left: 0; top: 20px; width: 2px; height: 14px; background: var(--_text); }
      .tl-edge {
        position: absolute; top: 46px; font-family: var(--_font-mono); font-size: 10px;
        text-transform: uppercase; color: var(--_muted);
      }
      .tl-start { left: 0; color: var(--_text); }
      .tl-end { right: 0; }
      .tl-mark {
        position: absolute; top: 0; transform: translateX(-50%);
        display: flex; flex-direction: column; align-items: center; gap: 5px;
      }
      .tl-mark.below { flex-direction: column-reverse; top: 18px; }
      .tl-amt { font-family: var(--_font-mono); font-size: 10px; line-height: 13px; }
      .tl-mark.tone-ok .tl-amt, .tl-mark.tone-info .tl-amt { color: var(--_muted); }
      .tl-dot {
        width: 12px; height: 12px; border-radius: 50%; background: var(--_g, currentColor);
        border: 3px solid var(--_bg); box-sizing: content-box; flex: none;
      }

      /* Subscriptions */
      .list { display: flex; flex-direction: column; padding: 6px 12px 10px; }
      .sub {
        display: flex; flex-direction: column; margin-top: 6px;
        border-radius: var(--_row-radius); border: 1px solid transparent;
      }
      .sub.open { background: var(--_surface); border-color: var(--_border-strong); }
      /* Paused rows are muted by colour, not opacity: opacity would drop the text below AA. */
      .sub.paused .name, .sub.paused .cost { color: var(--_muted); }
      .row {
        display: flex; align-items: center; gap: 12px; width: 100%; box-sizing: border-box;
        min-height: 64px; padding: 10px; margin: 0; text-align: left; cursor: pointer;
        background: transparent; border: 0; border-radius: var(--_row-radius);
      }
      .sub:not(.open) .row:hover { background: var(--_surface); }
      .svc-icon {
        flex: none; width: 42px; height: 42px; box-sizing: border-box; border-radius: 13px;
        display: flex; align-items: center; justify-content: center; color: var(--c);
        background: color-mix(in srgb, var(--c) 12%, transparent);
        border: 1px solid color-mix(in srgb, var(--c) 32%, transparent);
      }
      .svc-icon ha-icon { --mdc-icon-size: 20px; }
      .row-main { display: flex; flex-direction: column; gap: 4px; flex: 1; min-width: 0; }
      .row-title { display: flex; align-items: center; gap: 8px; }
      .name { font-family: var(--_font-display); font-size: 15px; font-weight: 500; }
      .pill {
        font-family: var(--_font-mono); font-size: 10px; text-transform: uppercase;
        padding: 2px 7px; border-radius: 99px; white-space: nowrap;
        background: color-mix(in srgb, currentColor 10%, transparent);
      }
      .row-sub {
        font-size: 12px; color: var(--_muted);
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
      }
      .row-right { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; flex: none; }
      .cost { font-family: var(--_font-display); font-size: 15px; font-weight: 500; }
      .row-meta {
        font-family: var(--_font-mono); font-size: 10px; text-transform: uppercase; color: var(--_muted);
      }

      /* Detail */
      .detail { display: flex; flex-direction: column; gap: 16px; padding: 4px 14px 16px; }
      .detail-kpis { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
      .detail-kpis > div {
        display: flex; flex-direction: column; gap: 4px; padding: 10px 12px;
        border-radius: 12px; background: var(--_bg); border: 1px solid var(--_border);
      }
      .detail-kpi { font-family: var(--_font-display); font-size: 15px; font-weight: 500; }
      .facts { display: flex; flex-direction: column; }
      .fact {
        display: flex; justify-content: space-between; gap: 12px;
        padding: 9px 2px; border-bottom: 1px solid var(--_border); font-size: 13px;
        color: var(--_muted);
      }
      .fact .v { color: var(--_text); text-align: right; }
      .history { display: flex; flex-direction: column; gap: 10px; }
      .history-head { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
      .delta { font-size: 12px; }
      .chart { width: 100%; height: 96px; display: block; overflow: visible; }
      .chart-base { stroke: var(--_border); stroke-width: 1; }
      .chart-line { stroke: var(--c); }
      .chart-label { font-family: var(--_font-mono); font-size: 10px; fill: var(--_text); }
      .chart-axis { font-family: var(--_font-mono); font-size: 10px; fill: var(--_muted); }

      .detail-actions { display: flex; }
      .btn {
        min-height: 44px; min-width: 44px; padding: 0 16px; cursor: pointer;
        font-size: 13px; background: none; color: var(--_accent-t);
        border: 1px solid var(--_border); border-radius: 12px;
      }
      .btn:hover { background: color-mix(in srgb, var(--_accent) 10%, transparent); }

      /* Tip */
      .tip {
        display: flex; align-items: flex-start; gap: 12px;
        margin: 4px 12px 14px; padding: 14px; border-radius: var(--_row-radius);
        background: color-mix(in srgb, var(--_warn) 8%, transparent);
        border: 1px solid color-mix(in srgb, var(--_warn) 28%, transparent);
        font-size: 13px; line-height: 1.5; color: var(--_text);
      }
      .tip svg { flex: none; margin-top: 1px; color: var(--_warn-t); }
      .tip-strong { color: var(--_warn-t); }

      .empty { padding: 4px 0; font-size: 12px; color: var(--_muted); }

      @media (prefers-reduced-motion: no-preference) {
        .ring-bar { transition: stroke-dasharray 0.4s ease; }
      }
    `;
  }
}

// The card ships with the integration; a copy installed separately (before 0.5.0)
// may also be loaded: whichever comes first registers the element.
if (!customElements.get("subscription-tracker-card")) {
  customElements.define("subscription-tracker-card", SubscriptionTrackerCard);

  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "subscription-tracker-card",
    name: "Subscription Tracker Card",
    description: "Elenco abbonamenti con spesa ricorrente, budget, timeline dei rinnovi e storico prezzi.",
    preview: true,
    documentationURL: "https://github.com/ivp-arch/ha-subscription-tracker",
  });
}

console.info(
  `%c SUBSCRIPTION-TRACKER-CARD %c ${CARD_VERSION} `,
  "background:#0F6E56;color:#fff",
  ""
);
