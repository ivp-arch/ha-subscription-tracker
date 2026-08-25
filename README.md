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
| `status` | `active` / `expiring_soon` / `expired` / `paused` |
| `subscribed_days` | Da quanti giorni sei cliente |
| `price_history` | Lista di `{date, price}` |
| `price_change_total` / `price_change_pct` / `price_changes_count` | Variazione rispetto al primo prezzo noto |
| `color`, `category`, `display_name` | Per il rendering della card |

Il metodo di pagamento **non** viene esposto come attributo di stato: resta solo nella configurazione, per non finire nel database del recorder né nei backup in chiaro.

### Sensore di riepilogo

`sensor.abbonamenti_totale` — stato = costo mensile totale. Attributi: `yearly_cost`, `active_count`, `paused_count`, `expiring_count`, `expiring` (lista ordinata per urgenza), `expiring_soon_total`, `by_category`.

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

### Via HACS (repository personalizzato)
1. HACS → Integrazioni → menu (⋮) → Repository personalizzati
2. Aggiungi l'URL di questo repo, categoria "Integrazione"
3. Installa "Subscription Tracker" e riavvia Home Assistant

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
# Soglia di spesa superata
trigger:
  - platform: numeric_state
    entity_id: sensor.abbonamenti_totale
    above: 70
action:
  - service: notify.mobile_app
    data:
      message: "Spesa abbonamenti sopra i 70 €/mese."
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

## Roadmap

- Card Lovelace dedicata (elenco con icone, KPI, storico prezzi, drill-down)
- Blueprint di automazione pronti all'uso

## Nota

L'integrazione non si collega agli account reali dei servizi: i dati vengono inseriti manualmente. Non gestisce credenziali né pagamenti.
