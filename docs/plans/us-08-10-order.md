# Plan: US-08, US-09 og US-10 – sende bestilling med gjestegrupper, og bekreftelse (C3)

## Kontekst
Kunden kan fylle handlekurven (US-06/07, `05b08b0`) og logge inn (US-19), men kan ikke sende noen bestilling. I dag kommer forespørsler på e-post og blir borte («three julebord requests in the spam folder», INT-I). US-08 registrerer bestillingen med en gang, US-09 tar med allergier og dietter per gjestegruppe (GDPR: aldri navn, NFR-04), og US-10 viser en bekreftelse. Flyten følger sekvensdiagrammet i design.md §3. «Mine bestillinger» (US-11) og adminsidene for ordre er **utenfor scope**.

Planen kopieres til `docs/plans/us-08-10-order.md` som første steg etter godkjenning.

## Filer

```
app/models/order.py                                  NY    OrderStatus, PaymentStatus, OrderLine, GuestGroup, Order
app/models/repositories/base.py                      ENDRE OrderRepository: save, get_for_user
app/models/repositories/sqlite_order_repository.py   NY    SQLite-implementasjon
app/models/repositories/__init__.py                  ENDRE order_repository()
app/controllers/shop.py                              ENDRE GET/POST /order (@login_required)
app/controllers/account.py                           ENDRE GET /orders/<id> (@login_required)
app/__init__.py                                      ENDRE Jinja-filter «date_no» (2027-01-15 → 15.01.2027)
app/templates/shop/order_form.html                   NY    bestillingsskjema
app/templates/account/order_detail.html              NY    bekreftelse / bestillingsside
app/templates/shop/cart.html                         ENDRE knapp «Gå til bestilling»
app/static/css/style.css                             ENDRE skjema for gjestegrupper, ordreside
tests/test_order.py                                  NY    US-08, US-09, US-10 (+ NFR-04, NFR-06)
```

Skjemaet i `schema.sql` har allerede alle tabellene (orders, order_lines, guest_groups med koblingstabeller), så databasen trenger ingen endring og `seed.py` må ikke kjøres på nytt.

## Modell – `app/models/order.py` (design.md §2)
- `OrderStatus(str, Enum)`: SUBMITTED, APPROVED, IN_PREPARATION, DELIVERED, REJECTED, CANCELLED. Verdiene er de samme som i CHECK i `schema.sql` (`"submitted"`, …), og hver har en norsk visningstekst (`label`: «Sendt inn», «Godkjent», …).
- `PaymentStatus(str, Enum)`: NOT_PAID, DEPOSIT_PAID, INVOICED, PAID, også med `label` («Ikke betalt», …).
- `OrderLine(food_item_id, food_item_name, quantity, unit_price_nok)` med `line_total_nok`. `unit_price_nok` **kopieres fra retten** når bestillingen lages.
- `GuestGroup(size, allergens: list[Allergen], dietary_labels: list[DietaryLabel], notes)`. **Ingen navnefelt.**
- `Order(id, user_id, created_at, event_date: date, guest_count, delivery_address, status, payment_status, status_reason, estimated_total_nok, lines, guest_groups)` med `number`-property («EM-00042») og `guest_group_total`.
- **`Order.create_from_cart(user, cart, event_date, guest_count, delivery_address, guest_groups, today=None)`** gjør all valideringen og kaster `ValidationError({felt: melding})`:
  - handlekurven er ikke tom («Handlekurven er tom.»)
  - `event_date` er en gyldig dato (ISO, fra `<input type="date">`) og **etter i dag** («Arrangementsdatoen må være i fremtiden.»)
  - `guest_count` er et heltall ≥ 1 («Antall gjester må være minst 1.»)
  - `delivery_address` er fylt ut
  - hver linje har antall ≥ minimumsantallet (sjekkes på nytt, i tilfelle admin har endret minimum)
  - hver gjestegruppe har størrelse ≥ 1 og **minst ett allergen eller diettmerke** («Gjestegruppe 2: velg minst ett allergen eller diettmerke.»)
  - **summen av gjestegruppene er ikke større enn antall gjester** («Gjestegruppene har til sammen 12 gjester, men bestillingen har bare 10.»)
  - Hvis alt er gyldig, får bestillingen `status = SUBMITTED` og `payment_status = NOT_PAID`, linjene får kopiert prisen, og `estimated_total_nok` settes.
  - `today` kan sendes inn, så testene ikke avhenger av dagens dato.

## Repository – `OrderRepository`
- `save(order) -> Order`: setter inn ordre, linjer, gjestegrupper og koblingene deres i **én transaksjon** (rollback ved feil), og returnerer ordren med id og `created_at`.
- `get_for_user(order_id, user_id) -> Order | None`: gir `None` hvis ordren ikke finnes **eller tilhører en annen kunde**. Navnet på retten hentes med en join mot `food_items`, så linjene viser navnet også etter at retten er arkivert. Prisen tas fra `order_lines.unit_price_nok`, ikke fra matretten.

## Controllere
**`shop.py` – `/order` (`@login_required`)**
- Ikke innlogget: redirect til `/login?next=/order`. Handlekurven beholdes, siden innloggingen allerede tar vare på `session["cart"]`.
- Tom handlekurv: redirect til `/cart` med en melding.
- **GET**: skjemaet vises med én tom gjestegruppe og et sammendrag av handlekurven (linjer og estimert total).
- **POST** med `action=add_group` / `action=remove_group-<n>`: skjemaet vises på nytt med det kunden har skrevet, og én gruppe mer eller mindre. Dette **lagrer ingenting** og trenger ikke JavaScript (dialoger og skript kan være blokkert i nettleservinduet i appen).
- **POST** med `action=submit`: controlleren slår opp allergener og diettmerker i `food_item_repository()` (de samme listene som matrettene bruker) og kaller `Order.create_from_cart`. Grupper som er helt tomme, hoppes over. Ved `ValidationError` vises skjemaet igjen med **status 400**, meldingene og alt kunden skrev. Når det går bra: `order_repository().save(order)`, handlekurven tømmes, en flash-melding vises, og kunden sendes til `/orders/<id>` med **303**.

**`account.py` – `/orders/<id>` (`@login_required`)**: `get_for_user(id, g.user.id)`. Er svaret `None`, gis **404** (avslører ikke at ordren finnes, NFR-06).

## Views
- **`order_form.html`**: arrangementsdato (`type="date"`, `min` = i morgen), antall gjester, leveringsadresse (textarea) og så gjestegruppene. Hver gruppe ligger i en `<fieldset>` med «Antall gjester i gruppen», avkrysningsbokser for allergener og diettmerker, en valgfri merknad og knappen «Fjern gruppe». Knappen «+ Legg til gjestegruppe» står under. Merknadsfeltet har teksten **«Ikke skriv navn på gjester»**, og skjemaet har **ingen felt for navn** (NFR-04). Til høyre (eller under, på mobil) vises et sammendrag av handlekurven med estimert total. Feilmeldingene står ved feltene.
- **`order_detail.html`** (US-10): «Takk! Bestillingen er mottatt.» (bare rett etter innsending, via flash), og så bestillingsnummer, opprettet-tidspunkt, arrangementsdato, antall gjester, leveringsadresse, status («Sendt inn») og betalingsstatus («Ikke betalt»). Under følger gjestegruppene og en tabell med linjene (antall × pris per stk = sum) og estimert total.
- **`cart.html`**: knappen «Gå til bestilling» (til `/order`).

## Tester – `tests/test_order.py`
Fixtures: matretter og katalog via repositoryene, `customer`/`customer2` og en innlogget klient. Datoer settes i forhold til `date.today()`.

**US-08**
- `test_submit_creates_order_with_status_submitted`: 302/303 til `/orders/<id>`, status SUBMITTED, betalingsstatus NOT_PAID, og et ordrenummer vises
- `test_cart_is_emptied_after_order`
- `test_past_event_date_is_rejected`: 400 med melding, ingen ordre, og skjemaet viser fortsatt adressen kunden skrev
- `test_guest_count_must_be_at_least_one`
- `test_not_logged_in_is_sent_to_login_and_cart_kept`: `/order` gir `/login?next=/order`, handlekurven er uendret, og etter innlogging virker bestillingen
- `test_empty_cart_redirects_to_cart`
- `test_order_line_copies_price`: prisen på retten endres etter bestilling, og ordresiden viser fortsatt den gamle prisen
- enhetstester av `Order.create_from_cart` for hver regel (dato i dag/fortid, gjester 0, minimumsantall, tom handlekurv)

**US-09**
- `test_guest_groups_are_saved_and_shown`: «4 gjester: Vegan», «2 gjester: Nøtter»
- `test_guest_group_needs_allergen_or_diet`
- `test_guest_groups_larger_than_guest_count_are_rejected`
- `test_add_group_button_adds_row_without_saving`
- `test_form_never_asks_for_guest_names` (NFR-04): ingen input-navn i skjemaet inneholder «navn»/«name», og `PRAGMA table_info(guest_groups)` har ingen navnekolonne

**US-10**
- `test_confirmation_shows_order_details`: bestillingsnummer, dato, gjester, linjer, estimert total og status

**NFR-06**
- `test_customer_cannot_see_other_customers_order`: 404
- `test_order_page_requires_login`

## Verifisering
1. `pytest` → alle tester grønne
2. Start `flask` på nytt i nettleservinduet. Logg ut og legg 30 fiskesupper i handlekurven, klikk «Gå til bestilling» (skal sende til innlogging), og logg inn som en testkunde. Prøv en dato i fortiden (skal gi melding, og utfylte felt skal være beholdt). Legg til to gjestegrupper, send inn og sjekk bekreftelsessiden. Sjekk også visningen på 360 px.
3. `grep sqlite3` treffer ikke controllerne eller templates
4. Commit (når du ber om det) med en melding som nevner US-08, US-09 og US-10
