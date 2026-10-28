# Plan: US-11 – Mine bestillinger (C4)

## Kontekst
Kunden kan sende bestillinger og se bekreftelsen på `/orders/<id>` (US-08–10, `b2be577`), men har ingen oversikt over bestillingene sine. Kunder sender e-post bare for å spørre om status (E011 «Is our order for tomorrow confirmed?»). US-11 gir en liste med ordrestatus og betalingsstatus, så kunden slipper å spørre. Adminsidene for ordre (US-12–14) er **utenfor scope**.

Planen kopieres til `docs/plans/us-11-my-orders.md` som første steg etter godkjenning.

## Filer

```
app/models/repositories/base.py                    ENDRE OrderRepository.list_for_user(user_id)
app/models/repositories/sqlite_order_repository.py ENDRE list_for_user + felles _to_order(row)
app/controllers/account.py                         ENDRE GET /orders (@login_required)
app/templates/account/orders.html                  NY    listen
app/templates/account/order_detail.html            ENDRE lenke «← Mine bestillinger»
app/templates/base.html                            ENDRE «Mine bestillinger» i toppmenyen for innlogget kunde
app/static/css/style.css                           ENDRE små justeringer (gjenbruker .cart-table og .status)
tests/test_my_orders.py                            NY    US-11 (+ NFR-06)
```

## Repository
- `list_for_user(user_id) -> list[Order]`: alle bestillingene til denne kunden, **sortert etter arrangementsdato** (stigende, så den neste kommer først), og deretter etter id. Listen trenger ikke linjer eller gjestegrupper, så den bruker én spørring uten N+1.
- Koden som gjør en rad om til et `Order`-objekt flyttes fra `get_for_user` til en felles hjelpefunksjon `_to_order(row)`, så den gjenbrukes.
- Statusene vises med de norske tekstene som allerede finnes i `OrderStatus.label` og `PaymentStatus.label` (`app/models/order.py`): «Sendt inn», «Godkjent», «Under forberedelse», «Levert», «Avvist», «Kansellert», «Ikke betalt», «Depositum betalt», «Fakturert» og «Betalt».

## Controller – `account.py`
`GET /orders` med `@login_required` (ikke innlogget → `/login?next=/orders`). Kaller `order_repository().list_for_user(g.user.id)` og rendrer `account/orders.html`. Kunden kan aldri se andres bestillinger, fordi spørringen alltid filtrerer på den innloggede brukeren.

## Views
- **`account/orders.html`**: overskriften «Mine bestillinger» og en tabell med kolonnene Bestilling (lenke `EM-00001` → `/orders/<id>`), Arrangementsdato, Gjester, Estimert total, Status og Betaling. Statusen vises som merke. Tabellen stables på mobil på samme måte som handlekurven (`data-label`). Uten bestillinger vises «Du har ingen bestillinger ennå.» og en lenke «Se menyen».
- **Toppmenyen**: «Mine bestillinger» vises bare når en **kunde** er innlogget. Den vises ikke for besøkende eller admin, siden admin ikke bestiller selv og skal få egne ordresider (US-12).
- **`order_detail.html`**: lenken nederst blir «← Mine bestillinger».

## Tester – `tests/test_my_orders.py`
Bestillingene lages med `Order(...)` + `order_repository().save()` direkte, så testene er raske og ikke avhenger av skjemaet.
- `test_my_orders_lists_all_three_sorted_by_event_date`: tre bestillinger lagret i tilfeldig rekkefølge vises sortert etter dato, hver med nummer, dato, gjester, total, status og betalingsstatus
- `test_status_labels_are_norwegian`: én ordre er APPROVED/DEPOSIT_PAID og vises som «Godkjent» og «Depositum betalt», og en ny vises som «Sendt inn» og «Ikke betalt»
- `test_each_order_links_to_detail_page`: `href="/orders/<id>"` for hver bestilling
- `test_customer_only_sees_own_orders` (NFR-06): en annen kundes bestilling vises ikke i listen, og `/orders/<id>` for den gir 404
- `test_list_for_user_only_returns_own_orders`: enhetstest av repositoryet
- `test_no_orders_shows_text_and_menu_link`
- `test_my_orders_requires_login`: redirect til `/login?next=/orders`
- `test_nav_link_only_for_logged_in_customer`: vises ikke for besøkende eller admin, men vises for kunde

## Verifisering
1. `pytest` → alle tester grønne
2. Start `flask` på nytt og kjør den midlertidige testserveren (egen database): logg inn som testkunde, send to bestillinger med ulike datoer, og åpne «Mine bestillinger». Sjekk sorteringen, de norske statusene, lenkene til hver bestilling og visningen på 360 px.
3. Commit (når du ber om det) med en melding som nevner US-11
