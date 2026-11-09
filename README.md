# Subscription Tracker per Home Assistant

Integrazione custom per monitorare abbonamenti in streaming: Netflix, Prime Video, Disney+, Paramount+, Crunchyroll, HBO Max, NOW TV, Chili, Apple TV+, DAZN, RaiPlay+, Mediaset Infinity+, TIMvision, Sky, Discovery+, Spotify, Apple Music, Amazon Music, YouTube Music, Tidal, Audible — più qualsiasi servizio personalizzato ("Altro").

## Dati inseriti dall'utente

Nome servizio (con icona e colore pre-mappati), piano/tier, costo per ciclo, ciclo di fatturazione, data prossimo rinnovo, data primo abbonamento, numero di persone che condividono l'account, categoria, metodo di pagamento (nota testuale), note libere, flag "in pausa".

## Dati derivati automaticamente

Ogni abbonamento crea un sensore con **stato = giorni al rinnovo** e questi attributi:

| Attributo | Descrizione |
|---|---|
| `monthly_cost` / `yearly_cost` | Costo normalizzato, così i piani annuali sono confrontabili con i mensili |
| `cost_per_person` | Costo diviso per il numero di condivisioni |
| `status` | `active` / `expiring_soon` / `paused` |
| `subscribed_days` | Da quanti giorni sei cliente |
| `price_history` | Lista di `{date, price}` |
| `price_change_total` / `price_change_pct` / `price_changes_count` | Variazione rispetto al primo prezzo noto |
| `next_renewal` | Prossimo rinnovo effettivo (avanza da solo per ciclo) |
| `color`, `category`, `display_name` | Per il rendering della card |

Il metodo di pagamento **non** viene mai esposto come attributo: resta solo nella configurazione, per non finire nel database del recorder. Attenzione: la configurazione fa parte dei backup di Home Assistant, quindi scrivi una nota generica (es. "Carta personale"), non le cifre della carta. Anche le note libere sono visibili negli attributi: niente dati personali.

### Sensore di riepilogo e voce "Riepilogo abbonamenti"

`sensor.abbonamenti_totale` — stato = costo mensile totale. Appartiene a una voce dedicata, "Riepilogo abbonamenti", creata automaticamente: così non dipende da nessun abbonamento in particolare. Attributi principali: `yearly_cost`, `active_count`, `paused_count`, `by_category`, `expiring` (rinnovi entro il preavviso), `upcoming` (timeline dei rinnovi nei prossimi 30 giorni) e `upcoming_total`, `budget`, `budget_used_pct`, `budget_remaining`, `budget_exceeded`. L'elenco completo, con tipi e regole di versione, è in [`docs/attributes-contract.md`](docs/attributes-contract.md).

**Budget mensile.** Si imposta da Dispositivi e servizi → Subscription Tracker → "Riepilogo abbonamenti" → Configura. Con 0 la soglia è disattivata.

**Valute diverse.** Non c'è conversione di cambio: i totali sommano solo gli abbonamenti nella valuta prevalente; `mixed_currency` e `other_currency_count` segnalano gli esclusi.

**Rinnovo automatico.** La data di rinnovo che inserisci è un'ancora: il sensore calcola da solo il prossimo rinnovo avanzando di cicli interi, senza scrivere nulla in configurazione. Per fermare il conteggio usa "in pausa".

## Storico prezzi

Funziona in due modi, combinati:

- **Automatico** — quando modifichi il costo dalle Opzioni dell'integrazione, la variazione viene registrata con la data odierna.
- **Manuale retroattivo** — il servizio `subscription_tracker.add_price_history` permette di inserire i prezzi precedenti all'installazione, così il grafico è pieno da subito.

```yaml
service: subscription_tracker.add_price_history
data:
  entity_id: sensor.netflix_premium
  price: 12.99
  date: "2021-03-01"
```

## Installazione

### Marketplace di Home Assistant (2026.11 o successivo)
1. Impostazioni → Marketplace → menu (⋮) → **Aggiungi da link** (serve collegare un account GitHub)
2. Inserisci `ivp-arch/ha-subscription-tracker`
3. Installa "Subscription Tracker" e riavvia Home Assistant

### HACS (Home Assistant precedente alla 2026.11)
HACS → Integrazioni → menu (⋮) → Repository personalizzati → aggiungi l'URL di questo repo, categoria "Integrazione".

### Manuale
Copia `custom_components/subscription_tracker` nella cartella `custom_components` della tua istanza, poi riavvia.

## Configurazione

Impostazioni → Dispositivi e servizi → Aggiungi integrazione → "Subscription Tracker". Ripeti per ogni abbonamento. I dati si modificano dalle Opzioni dell'integrazione, senza rimuovere e ricreare.

## Automazioni

Il sensore di riepilogo rende banali le automazioni più utili:

```yaml
# Avviso settimanale sui rinnovi imminenti
trigger:
  - platform: time
    at: "09:00:00"
condition:
  - condition: template
    value_template: "{{ state_attr('sensor.abbonamenti_totale','expiring_count') | int > 0 }}"
action:
  - service: notify.mobile_app
    data:
      title: Rinnovi in arrivo
      message: >-
        {% for s in state_attr('sensor.abbonamenti_totale','expiring') %}
        {{ s.name }}: {{ s.cost }} € tra {{ s.days }} gg.
        {% endfor %}
```

```yaml
# Soglia di budget superata (il budget si imposta nella voce "Riepilogo abbonamenti")
trigger:
  - platform: state
    entity_id: sensor.abbonamenti_totale
    attribute: budget_exceeded
    to: true
action:
  - service: notify.mobile_app
    data:
      message: "Spesa abbonamenti sopra il budget mensile."
```

```yaml
# Aumento di prezzo rilevato su un servizio
trigger:
  - platform: state
    entity_id: sensor.netflix_premium
    attribute: price_changes_count
action:
  - service: notify.mobile_app
    data:
      message: >-
        Netflix ha cambiato prezzo: ora {{ state_attr('sensor.netflix_premium','cost') }} €,
        {{ state_attr('sensor.netflix_premium','price_change_pct') }} % rispetto all'inizio.
```

## Sviluppo

I calcoli sono in `custom_components/subscription_tracker/calc.py`, senza dipendenze da Home Assistant. I test (`tests/`) usano `pytest-homeassistant-custom-component`:

```bash
pip install -r requirements_test.txt
pytest
```

## Roadmap

- Card Lovelace in stile "Orbit" con budget e timeline ([repo della card](https://github.com/ivp-arch/ha-subscription-tracker-card))
- Blueprint di automazione pronti all'uso

## Nota

L'integrazione non si collega agli account reali dei servizi: i dati vengono inseriti manualmente. Non gestisce credenziali né pagamenti.
