# Contratto attributi — versione 1

Questo documento è il contratto tra l'integrazione (dati, calcoli, entità) e le card (sola presentazione). Ogni sensore espone `contract_version: 1`.

**Regole di versione.** Aggiungere un attributo non cambia la versione. Rimuovere, rinominare o cambiare il tipo o il significato di un attributo esistente richiede di incrementare `contract_version`, di aggiornare questo file e le card. Le card devono ignorare gli attributi che non conoscono.

**Dati mai esposti.** Il metodo di pagamento (`payment_note`) non compare in nessun attributo di nessuna entità. Lo verifica un test (`test_payment_method_never_in_attributes`). Resta però nella configurazione dell'integrazione e quindi nei backup di Home Assistant.

## Sensore di un abbonamento

Stato: giorni al prossimo rinnovo (intero, mai negativo se la data è valida), unità `days`.

| Attributo | Tipo | Note |
|---|---|---|
| `contract_version` | int | Sempre `1` |
| `service` | str | Chiave del servizio (`netflix`, `altro`, ...) |
| `display_name` | str | Nome mostrabile |
| `category` | str | `video`, `audio`, `altro` |
| `color` | str \| null | Esadecimale; `null` per servizi personalizzati |
| `plan` | str \| null | Piano/tier |
| `cost` | float | Costo per ciclo |
| `currency` | str | `EUR`, `USD`, `GBP` |
| `billing_cycle` | str | `monthly`, `quarterly`, `yearly` |
| `monthly_cost` / `yearly_cost` | float | Costo normalizzato |
| `next_renewal` | str (ISO) \| null | Prossimo rinnovo **effettivo** (vedi sotto) |
| `renewal_advanced` | bool | `true` se `next_renewal` differisce dalla data inserita |
| `shared_count` | int | Persone che condividono (≥ 1) |
| `cost_per_person` | float | `cost / shared_count` |
| `status` | str | `active`, `expiring_soon`, `paused`. `expired` è riservato e non viene prodotto |
| `paused` | bool | |
| `notes` | str \| null | Testo libero: non inserirvi dati personali, finisce nel recorder |
| `price_history` | list | `[{date, price}]` ordinata per data |
| `subscribed_since`, `subscribed_days` | str (ISO), int | Solo se "Cliente dal" è impostato |
| `price_change_total`, `price_change_pct`, `price_changes_count` | float, float, int | Solo con almeno 2 punti di storico |

**Rinnovo automatico.** La data inserita dall'utente è un'ancora: `next_renewal` è la prima data uguale o successiva a oggi ottenuta sommando cicli interi all'ancora (si parte sempre dall'ancora, quindi un rinnovo del 31 gennaio mensile cade il 28 febbraio e torna al 31 marzo). Non viene scritto nulla in configurazione. Per sospendere il conteggio si usa "in pausa".

## Sensore di riepilogo (`sensor.abbonamenti_totale`)

Posseduto dalla voce "Riepilogo abbonamenti" (hub), creata automaticamente. Stato: costo mensile totale degli abbonamenti non in pausa, nella valuta prevalente.

| Attributo | Tipo | Note |
|---|---|---|
| `contract_version` | int | `1` |
| `currency` | str | Valuta prevalente tra gli abbonamenti attivi (`EUR` se non ce ne sono) |
| `mixed_currency` | bool | `true` se ci sono abbonamenti in altre valute |
| `other_currency_count` | int | Quanti abbonamenti attivi sono esclusi dai totali per valuta diversa. Nessuna conversione di cambio |
| `yearly_cost` | float | |
| `active_count`, `paused_count` | int | |
| `by_category` | dict str→float | Costo mensile per categoria |
| `expiring_count`, `expiring_soon_total` | int, float | Rinnovi entro la soglia di preavviso del singolo abbonamento |
| `expiring` | list | Elementi come sotto, ordinati per giorni |
| `upcoming_days` | int | Finestra della timeline, oggi `30` |
| `upcoming` | list | Rinnovi entro `upcoming_days`, ordinati per giorni e nome |
| `upcoming_total` | float | Somma dei costi di `upcoming` |
| `budget` | float \| null | Soglia mensile impostata nell'hub; `null` se non impostata o 0 |
| `budget_used_pct` | float \| null | Spesa mensile / budget × 100, un decimale; `null` senza budget |
| `budget_remaining` | float \| null | `budget - spesa`; negativo se superato |
| `budget_exceeded` | bool | `true` se la spesa mensile supera il budget |

Elemento di `expiring` e `upcoming`: `{name, service, days, cost, renewal}`, con `days` ≥ 0, `renewal` ISO, `cost` per ciclo.

Il budget si imposta da Impostazioni → Dispositivi e servizi → Subscription Tracker → "Riepilogo abbonamenti" → Configura.

## Non incluso nella versione 1

La variazione di spesa rispetto al mese precedente (usata nel mockup Orbit) richiede uno storico mensile del totale che oggi non esiste: non è nel contratto.
