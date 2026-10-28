# Plan: US-12, US-13 og US-14 – admin håndterer bestillinger (A3)

## Kontekst
Kundene kan sende bestillinger og følge dem (US-08–11, `7f51d6d`), men Ekte Mat har ingen måte å se eller behandle dem på. I dag skriver koordinatoren ut bestillingen og henger den på kjøkkentavla (ASIS), og depositum blir glemt (ASIS, E030). US-12 gir en ordreliste med filtre, US-13 flytter ordren gjennom statusene, og US-14 setter betalingsstatus. Begge statusene følger tilstandsmaskinene i design.md §4 og §5.

Planen kopieres til `docs/plans/us-12-14-admin-orders.md` som første steg etter godkjenning.

## Filer

```
app/models/order.py                                  ENDRE ALLOWED-tabeller, change_status, change_payment_status, customer
app/models/errors.py                                 ENDRE InvalidTransitionError(ValidationError)
app/models/repositories/base.py                      ENDRE OrderRepository: list_all, get, update_status
app/models/repositories/sqlite_order_repository.py   ENDRE implementasjon (+ felles _load_details)
app/controllers/admin.py                             ENDRE /admin/orders, /admin/orders/<id>, …/status, …/payment
app/templates/admin/orders.html                      NY    liste med filtre
app/templates/admin/order_detail.html                NY    hele bestillingen + statusknapper
app/templates/admin/index.html                       ENDRE lenke «Bestillinger»
app/templates/account/order_detail.html              ENDRE viser begrunnelsen ved avvist/kansellert
app/static/css/style.css                             ENDRE filterlinje og statusknapper
tests/test_admin_orders.py                           NY    US-12, US-13, US-14
```

## Modell – tilstandsmaskinene i `app/models/order.py`
Overgangene ligger som tabeller i modellen, nøyaktig som i design.md:

```python
ORDER_TRANSITIONS = {                       # design.md §4
    OrderStatus.SUBMITTED:      {APPROVED, REJECTED, CANCELLED},
    OrderStatus.APPROVED:       {IN_PREPARATION, CANCELLED},
    OrderStatus.IN_PREPARATION: {DELIVERED},
    OrderStatus.DELIVERED:      set(),      # sluttilstander
    OrderStatus.REJECTED:       set(),
    OrderStatus.CANCELLED:      set(),
}
PAYMENT_TRANSITIONS = {                     # design.md §5
    PaymentStatus.NOT_PAID:     {DEPOSIT_PAID, INVOICED, PAID},
    PaymentStatus.DEPOSIT_PAID: {INVOICED},
    PaymentStatus.INVOICED:     {PAID},
    PaymentStatus.PAID:         set(),
}
REASON_REQUIRED = {OrderStatus.REJECTED, OrderStatus.CANCELLED}
```

- `order.allowed_statuses` og `order.allowed_payment_statuses` returnerer de lovlige neste tilstandene, i en fast rekkefølge, til knappene.
- `order.change_status(new, reason=None)`: en ulovlig overgang kaster **`InvalidTransitionError`**, for eksempel «Kan ikke endre status fra Levert til Sendt inn.». Avvis eller kanseller uten begrunnelse kaster `ValidationError({"reason": "Skriv en begrunnelse …"})`. Ordren endres ikke før alt er sjekket. Når overgangen er gyldig, settes `status` og `status_reason` (begrunnelsen settes bare ved avvist eller kansellert).
- `order.change_payment_status(new)`: fungerer på samme måte, med sin egen tabell.
- `InvalidTransitionError` arver fra `ValidationError` i `app/models/errors.py`, så controlleren kan håndtere begge likt.
- `Order` får feltet `customer: User | None = None` (assosiasjonen User 1 → 0..* Order i klassediagrammet), så adminlisten kan vise kunden. Repositoryet fyller det bare inn når admin henter ordre.

## Repository – `OrderRepository`
- `list_all(status=None, date_from=None, date_to=None) -> list[Order]`: alle bestillinger, med kunde (join mot `users`), **sortert etter arrangementsdato** og så id. Status og datoperiode filtreres i SQL (`event_date BETWEEN ? AND ?`, begge grensene er valgfrie).
- `get(order_id) -> Order | None`: hele bestillingen for admin, med kunde, linjer og gjestegrupper. Koden som henter linjer og grupper, flyttes fra `get_for_user` til en felles `_load_details(order)`.
- `update_status(order)`: lagrer `status`, `status_reason` og `payment_status`. Valideringen er allerede gjort i modellen.

## Controller – `admin.py`
Alle rutene har `@admin_required`, i tillegg til `before_request`-sjekken som gjelder hele blueprinten. Tilgangstesten for NFR-06 dekker de nye rutene automatisk.

| Rute | Metode | Hva |
|---|---|---|
| `/admin/orders` | GET | liste; filtre `?status=submitted&from=2027-01-01&to=2027-01-31` |
| `/admin/orders/<id>` | GET | hele bestillingen + knapper for lovlige overganger |
| `/admin/orders/<id>/status` | POST | `status`, `reason` → `order.change_status` → `update_status` |
| `/admin/orders/<id>/payment` | POST | `payment_status` → `order.change_payment_status` → `update_status` |

- Ved feil (ulovlig overgang eller manglende begrunnelse) vises en feilmelding (`flash(…, "error")`) og redirect tilbake til ordren. **Ingenting lagres.** Ved suksess vises f.eks. «Status endret til Godkjent.».
- Ukjent id gir 404. Ugyldig status i filteret eller ugyldig dato ignoreres, og en melding sier fra.

## Views
- **`admin/orders.html`**: en filterlinje (GET-skjema) med nedtrekksliste for status («Alle» + de seks statusene), «Fra»- og «Til»-dato og knappene «Filtrer» og «Nullstill». Under kommer tabellen med kolonnene Bestilling (lenke), Kunde (navn og e-post), Arrangementsdato, Gjester, Total, Status (merke) og Betaling, og antall treff. Tabellen stables på mobil med `data-label`, som de andre tabellene.
- **`admin/order_detail.html`**: fakta (kunde, datoer, gjester, adresse, status, betaling og begrunnelse), gjestegruppene med allergier og dietter, og linjene med total. Statusbehandlingen er delt i to:
  - **Ordrestatus**: én knapp per lovlig overgang («Godkjenn», «Start forberedelse», «Marker som levert»). «Avvis» og «Kanseller» er egne små skjemaer med et **påkrevd** felt for begrunnelse. I en sluttilstand står det «Ingen flere endringer mulig».
  - **Betaling**: én knapp per lovlig overgang («Depositum betalt», «Fakturert», «Betalt»).
- **Kundens ordreside**: hvis ordren er avvist eller kansellert, vises «Begrunnelse: …» under statusen.
- **Admin-menyen** (`admin/index.html`): lenken «Bestillinger».

## Tester – `tests/test_admin_orders.py`
Bestillingene lages direkte med `order_repository().save()`, og admin og kunde logges inn via fixtures.

**US-12**
- `test_admin_list_shows_all_orders_sorted_by_event_date`: med kunde, dato, gjester, total og statuser
- `test_filter_by_status_submitted`: bare innsendte bestillinger vises
- `test_filter_by_date_range`: bare bestillinger i perioden vises, sortert etter dato (grensene er med)
- `test_list_all_filters_in_repository`: enhetstest

**US-13**
- `test_approve_is_visible_to_customer`: SUBMITTED → APPROVED, og kunden ser «Godkjent» på «Mine bestillinger»
- `test_delivered_cannot_go_back_to_submitted`: POST gir en feilmelding, og statusen er fortsatt DELIVERED
- `test_reject_without_reason_is_refused`, og det samme for kanseller, fra både SUBMITTED og APPROVED
- `test_reject_with_reason_is_shown_to_customer`
- `test_only_allowed_transition_buttons_are_shown`: for SUBMITTED vises Godkjenn, Avvis og Kanseller, men ikke «Marker som levert». For DELIVERED vises ingen knapper.
- `test_order_state_machine_matches_design`: enhetstest som går gjennom alle kombinasjonene og sjekker at bare overgangene i tabellen er lov
- Hele flyten SUBMITTED → APPROVED → IN_PREPARATION → DELIVERED

**US-14**
- `test_set_deposit_paid_shown_on_order_page_and_my_orders`
- `test_payment_state_machine`: PAID → NOT_PAID er ulovlig, og DEPOSIT_PAID → INVOICED → PAID er lov

## Verifisering
1. `pytest` → alle tester grønne (`test_every_admin_route_requires_admin_role` skal dekke de fire nye rutene)
2. Midlertidig testserver med egen database og noen testbestillinger: logg inn som admin og åpne «Bestillinger». Filtrer på status og dato, godkjenn en bestilling, prøv å avvise uten begrunnelse (skal gi melding), avvis med begrunnelse, og sett «Depositum betalt». Logg så inn som kunden og sjekk at status, betaling og begrunnelse vises. Sjekk også visningen på 360 px.
3. Start `flask` på port 5000 på nytt etterpå.
4. Commit (når du ber om det) med en melding som nevner US-12, US-13 og US-14
