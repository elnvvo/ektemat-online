# Plan: US-16, US-17 og US-18 – spørsmål om bestillinger (C5, A4)

## Kontekst
Kundene ringer eller sender e-post for å spørre om bestillingene sine. Ingen svarer (E003 «I called yesterday but nobody picked up»), og i travle perioder tar det en uke (INT-S, E006). US-16 lar kunden stille spørsmål på bestillingssiden, så hele samtalen ligger ved bestillingen. US-17 gir admin en liste over ubesvarte spørsmål, med de eldste først, så ingen blir glemt. US-18 (Could) viser antall ubesvarte spørsmål i admin-menyen. Det er enkelt, så det tas med.

Planen kopieres til `docs/plans/us-16-18-questions.md` som første steg etter godkjenning.

## Filer

```
app/models/question.py                               NY    Question, Answer (validering i modellen)
app/models/repositories/base.py                      ENDRE QuestionRepository
app/models/repositories/sqlite_question_repository.py NY   SQLite-implementasjon
app/models/repositories/__init__.py                  ENDRE question_repository()
app/controllers/account.py                           ENDRE POST /orders/<id>/questions; spørsmål på /orders/<id>
app/controllers/admin.py                             ENDRE /admin/questions, …/<id>/answer; spørsmål på /admin/orders/<id>; antall på /admin
app/__init__.py                                      ENDRE Jinja-filter «datetime_no» (28.10.2026 kl. 11:05)
app/templates/_questions.html                        NY    felles visning av spørsmål og svar (inkluderes av kunde- og admin-siden)
app/templates/account/order_detail.html              ENDRE spørsmål + skjema for nytt spørsmål
app/templates/admin/questions.html                   NY    ubesvarte (eldste først) + nylig besvarte
app/templates/admin/order_detail.html                ENDRE spørsmål + svarskjema
app/templates/admin/index.html                       ENDRE «Spørsmål (2)»
app/static/css/style.css                             ENDRE spørsmål og svar
tests/test_questions.py                              NY    US-16, US-17, US-18
```

Tabellene `questions` og `answers` finnes allerede i `schema.sql`. `answers.question_id` er primærnøkkel, så databasen hindrer også mer enn ett svar per spørsmål. Ingen skjemaendring trengs, og `seed.py` må ikke kjøres på nytt.

## Modell – `app/models/question.py` (design.md §2: `Order 1 *-- 0..* Question 1 *-- 0..1 Answer`)
- `Answer(text, answered_at, user_id)`
- `Question(id, order_id, user_id, text, asked_at, answer: Answer | None = None, customer: User | None = None)` med:
  - `is_answered`, `status_label` («Besvart» eller «Ubesvart») og `order_number` («EM-00001», samme format som `Order.number`)
  - **`Question.ask(order, user, text, now=None)`**: teksten trimmes. Tom tekst gir `ValidationError({"text": "Skriv et spørsmål."})`, og over 2000 tegn gir en melding om lengden. Hvis `order.user_id != user.id`, kastes `ValidationError` («Du kan bare spørre om dine egne bestillinger.»), i tillegg til at controlleren gir 404. `asked_at` settes til `datetime.now()` (lokal tid), så tidspunktet vises riktig og ikke i UTC.
  - **`question.answer_with(admin, text, now=None)`**: tomt svar gir `ValidationError({"text": "Skriv et svar."})`. Er spørsmålet allerede besvart, kommer en egen feil («Spørsmålet er allerede besvart.»), siden det bare kan ha ett svar. Kunden kan stille et nytt spørsmål.

## Repository – `QuestionRepository`
- `add(question) -> Question`
- `list_for_order(order_id) -> list[Question]`: med svar, i rekkefølgen de ble stilt
- `list_unanswered() -> list[Question]`: **eldste først** (`asked_at`, så `id`), med kunde (join mot `users`)
- `list_answered(limit=20) -> list[Question]`: de nyeste svarene først
- `get(question_id) -> Question | None`
- `save_answer(question)`: setter inn i `answers`. Brudd på primærnøkkelen (to admins svarer samtidig) blir den samme feilen som «allerede besvart».
- `count_unanswered() -> int` (US-18)

## Controllere
**`account.py`** (kunde, `@login_required`)
- `/orders/<id>` henter også `question_repository().list_for_order(id)`.
- `POST /orders/<id>/questions`: ordren hentes med `order_repository().get_for_user(id, g.user.id)`, og **andres ordre gir 404** uten at noe lagres. Deretter kalles `Question.ask` og `add`. Når det går bra, vises «Spørsmålet er sendt. Du får svar her på siden.». Ved feil vises en feilmelding, og ingenting lagres. Uansett sendes kunden tilbake til `/orders/<id>#questions`.

**`admin.py`** (alle har `@admin_required`, og tilgangstesten dekker dem automatisk)
- `GET /admin/questions`: ubesvarte spørsmål med de eldste først, hver med bestillingsnummer (lenke til `/admin/orders/<id>`), kunde, tidspunkt, teksten og et svarskjema. Under kommer en egen del, «Nylig besvart».
- `POST /admin/questions/<id>/answer`: `question.answer_with(g.user, text)` og så `save_answer`. Etterpå sendes admin tilbake til `next` (listen eller ordresiden). `next` sjekkes med `is_safe_next`.
- `/admin/orders/<id>` viser spørsmålene med svarskjema for de ubesvarte.
- `/admin` (index) viser **«Spørsmål (n)»** med `count_unanswered()` (US-18).

## Views
- **`_questions.html`** (felles): hvert spørsmål vises med tidspunkt, et statusmerke («Ubesvart» eller «Besvart») og teksten. Svaret står under, med «Svar fra Ekte Mat» og tidspunkt. Teksten vises med `white-space: pre-line` og escapes som vanlig av Jinja.
- **Kundesiden**: overskriften «Spørsmål om bestillingen», listen og et skjema med textarea og knappen «Send spørsmål». Uten spørsmål står det «Har du spørsmål om bestillingen? Skriv dem her.».
- **Admin**: under hvert ubesvarte spørsmål står et svarskjema (textarea og «Send svar»).

## Tester – `tests/test_questions.py`
**US-16**
- `test_customer_asks_question_shown_with_time_and_unanswered`
- `test_answer_is_shown_under_question_and_marked_answered`
- `test_customer_can_ask_new_question_after_answer`
- `test_empty_question_is_rejected` (gjelder også bare mellomrom; ingenting lagres)
- `test_cannot_ask_about_other_customers_order`: 404, og ingenting lagres
- `test_ask_requires_login`
- enhetstester av `Question.ask` (tom, for lang, feil eier)

**US-17**
- `test_unanswered_questions_oldest_first`: spørsmålene lagres med kjente tidspunkter
- `test_answer_marks_question_answered_and_removes_from_list`: spørsmålet er borte fra «ubesvarte» og står under «Nylig besvart»
- `test_only_one_answer_per_question`: i modellen, og via repositoryet (`save_answer` to ganger)
- `test_empty_answer_is_rejected`
- `test_question_links_to_order`
- `test_questions_shown_on_admin_order_page`

**US-18**
- `test_admin_menu_shows_unanswered_count`: «Spørsmål (2)» blir «Spørsmål (1)» etter ett svar

## Verifisering
1. `pytest` → alle tester grønne
2. Midlertidig testserver: logg inn som kunde, still to spørsmål på en bestilling, og prøv et tomt spørsmål (skal gi melding). Logg inn som admin og sjekk at menyen viser «Spørsmål (2)», at den eldste kommer først, og svar på ett. Sjekk at det havner under «Nylig besvart» og at menyen viser «Spørsmål (1)». Logg inn som kunde igjen og sjekk at svaret og «Besvart» vises. Sjekk også visningen på 360 px.
3. Start `flask` på port 5000 på nytt.
4. Commit (når du ber om det) med en melding som nevner US-16, US-17 og US-18
