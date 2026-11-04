# Plan 12: Neo4j for bestillinger og spørsmål (Oblig 5, steg 2)

## Kontekst
Steg 1 (`a11a1c8`, branchen `neo4j`) flyttet matretter og brukere til Neo4j. Med `STORAGE=neo4j` gir bestillinger og spørsmål foreløpig bare tomme lister og en 501-side, fordi de fortsatt lå i SQLite og pekte på brukere og retter som ikke finnes der. Nå flyttes også de, etter grafmodellen i design.md §7, så **hele appen virker med Neo4j**. Kravene er de samme som sist: ingen endringer i controllere, maler eller domeneklasser, alle spørringer bruker parametere, og standardtestene kjører mot SQLite.

Planen er lagret som `docs/plans/12-neo4j-orders-questions.md`.

## Filer

```
app/models/repositories/neo4j_order_repository.py     NY    Neo4jOrderRepository(OrderRepository)
app/models/repositories/neo4j_question_repository.py  NY    Neo4jQuestionRepository(QuestionRepository)
app/models/repositories/neo4j_connection.py           ENDRE nye constraints (Order.id, Question.id, Answer.question_id)
app/models/repositories/__init__.py                   ENDRE fabrikkene gir Neo4j-klassene for ordre og spørsmål
app/models/repositories/not_migrated.py               SLETT plassholderne trengs ikke lenger
app/__init__.py                                       ENDRE fjerner 501-håndteringen fra steg 1 og oppdaterer en kommentar (se under)
tests/test_storage.py                                 ENDRE forventer Neo4j-klassene; testene av plassholderne fjernes
tests/test_neo4j_orders_questions.py                  NY    Neo4j-tester for ordre og spørsmål (bare «pytest -m neo4j»)
README.md, CLAUDE.md, docs/design.md §7               ENDRE «ikke flyttet ennå» fjernes; grafmodellen viser id-er og hjelpeegenskaper
```

## Grafmodell (design.md §7)
```
(:User)-[:PLACED]->(:Order {id, created_at, event_date, guest_count, delivery_address,
                            status, payment_status, status_reason, estimated_total_nok})
(:Order)-[:CONTAINS {quantity, unit_price_nok}]->(:FoodItem)            ← ordrelinjen er en relasjon
(:Order)-[:HAS_GUEST_GROUP]->(:GuestGroup {position, size, notes})       ← ingen navnefelt (NFR-04)
(:GuestGroup)-[:AVOIDS]->(:Allergen)   (:GuestGroup)-[:NEEDS]->(:DietaryLabel)   ← delte noder
(:User)-[:ASKED]->(:Question {id, text, asked_at})-[:ABOUT]->(:Order)
(:Answer {question_id, text, answered_at})-[:ANSWERS]->(:Question)
(:User)-[:WROTE]->(:Answer)
```
- **Egne id-er:** `Order.id` og `Question.id` kommer fra `Sequence`-telleren fra steg 1 (`next_id`), og de får unikhets-constraints.
- **Hvilken kunde ordren og spørsmålet tilhører**, leses av relasjonene `PLACED` og `ASKED`, ikke av en egen `user_id`-egenskap. `Order.user_id` og `Question.user_id` fylles fra `u.id`.
- **Pris og total** (`unit_price_nok` på `CONTAINS` og `estimated_total_nok`) lagres som tekst, som `price_nok` i steg 1, så beløpene blir eksakte. Prisen kopieres fra retten når ordren lagres, så senere prisendringer ikke påvirker gamle ordre.
- **Datoer:** `event_date` lagres som Neo4j `Date`, og `created_at`, `asked_at` og `answered_at` som `LocalDateTime`. Driveren gjør om Python-verdiene, og de gjøres tilbake med `.to_native()`. Som i SQLite er `created_at` i UTC, og spørsmål og svar har lokal tid (satt i modellen).
- **`GuestGroup.position`** (1, 2, …) bevarer rekkefølgen kunden la inn gruppene i. Grafen har ingen rekkefølge av seg selv, og i SQLite ble den bevart av `id`. Det er ingen navn på gruppene.
- **Maks ett svar:** `Answer.question_id` har en unikhets-constraint, som `answers.question_id` var primærnøkkel i SQLite. Svarer to admins samtidig, stopper databasen det andre svaret, og det blir `AlreadyAnsweredError`. Egenskapen er en kopi av relasjonen `ANSWERS`, men det er den enkleste måten å la databasen selv garantere «0..1 svar».

## Neo4jOrderRepository
Den implementerer alle metodene i `OrderRepository` (`base.py`), med samme oppførsel som SQLite-versjonen:
- **`save(order)`** går i **én skrivetransaksjon** via `write_transaction`:
  1. `next_id("Order")`, og så `MATCH (u:User {id: $user_id}) CREATE (u)-[:PLACED]->(o:Order {...}) RETURN o.created_at`
  2. `MATCH (o:Order {id: $id}) UNWIND $lines AS line MATCH (f:FoodItem {id: line.food_item_id}) CREATE (o)-[:CONTAINS {quantity: line.quantity, unit_price_nok: line.unit_price_nok}]->(f)`
  3. Én spørring per gjestegruppe: `CREATE (o)-[:HAS_GUEST_GROUP]->(g:GuestGroup {...})`, så `OPTIONAL MATCH` + `collect` på allergenene og merkene, og `FOREACH … CREATE (g)-[:AVOIDS|NEEDS]->(…)`.
  - Hvis kunden eller en rett ikke finnes (antallet opprettede noder og relasjoner stemmer ikke), kastes en feil. Da **rulles hele transaksjonen tilbake**, så det aldri blir liggende en halv ordre.
- **`get(id)`** (admin, med kunde) og **`get_for_user(id, user_id)`** (`MATCH (u:User {id: $user_id})-[:PLACED]->(o:Order {id: $id})`, ellers `None`, som gir 404): én spørring med mønsterforståelse for linjene (`[(o)-[c:CONTAINS]->(f) | {…}]`) og gruppene, med allergenene og merkene inni. Sorteringen er den samme som i SQLite: linjene etter rettens navn, gruppene etter `position`, allergenene etter navn og merkene etter kode.
- **`list_for_user(user_id)`**: kundens ordre etter `event_date` og så `id`, uten linjer og grupper.
- **`list_all(status, date_from, date_to)`**: med kunde. Filtrene er parametere (`$status IS NULL OR o.status = $status`, og det samme for datoene), og sorteringen er `event_date` og så `id`.
- **`update_status(order)`**: `SET o.status = $status, o.status_reason = $reason, o.payment_status = $payment`. Valideringen skjer i `Order` i modellen, som før.

## Neo4jQuestionRepository
- **`add(question)`**: `next_id("Question")`, og så `MATCH (u:User {id: $user_id}), (o:Order {id: $order_id}) CREATE (u)-[:ASKED]->(q:Question {...})-[:ABOUT]->(o)` i én transaksjon. Den feiler hvis kunden eller ordren mangler.
- **`get`**, **`list_for_order`** (rekkefølgen de ble stilt), **`list_unanswered`** (eldste først, med kunde) og **`list_answered(limit)`** (nyeste svar først, `LIMIT $limit`) bruker samme mønster: `MATCH (q)-[:ABOUT]->(o)`, `OPTIONAL MATCH (u)-[:ASKED]->(q)`, `OPTIONAL MATCH (a:Answer)-[:ANSWERS]->(q)` og `OPTIONAL MATCH (w)-[:WROTE]->(a)`.
- **`save_answer(question)`**: `CREATE (a:Answer {question_id, text, answered_at})-[:ANSWERS]->(q)` og `WROTE` fra admin. `ConstraintError` gir `AlreadyAnsweredError`, som i SQLite.
- **`count_unanswered()`**: `WHERE NOT EXISTS { (:Answer)-[:ANSWERS]->(q) }`

Alle spørringene er konstanter med `$parametere`, så testen fra steg 1 (`test_cypher_only_uses_parameters`) sjekker de nye filene automatisk.

## Endringer utenfor `repositories/` (to små)
- **`app/__init__.py`**: håndteringen av `StorageNotMigratedError` (501) og kommentaren om at ordre «ligger i SQLite til de er flyttet» la jeg til i steg 1. Nå fjernes begge, sammen med `not_migrated.py`. 503-siden for «databasen svarer ikke» og `errors/storage.html` blir værende.
- SQLite kobles fortsatt alltid til i `create_app` (det er ufarlig og gjør testene enkle), men den brukes ikke når `STORAGE=neo4j`.

Ingen endringer i controllere, maler eller domeneklasser.

## Tester
- **`pytest`** bruker SQLite som før, og alle testene skal være grønne. `test_storage.py` sjekker nå at `STORAGE=neo4j` gir `Neo4jOrderRepository` og `Neo4jQuestionRepository`.
- **`tests/test_neo4j_orders_questions.py`** (`@pytest.mark.neo4j`, kjøres bare med `pytest -m neo4j`). Hver test lager sin egen kunde, katalog og sine egne retter med unike navn for kjøringen, og sletter **bare** det den har laget (ordre, gjestegrupper, spørsmål og svar via id-ene) etterpå. Databasen tømmes aldri.
  - En ordre med to linjer og to gjestegrupper lagres og leses tilbake likt: status, betaling, linjer med kopiert pris, gruppene i riktig rekkefølge med allergener og dietter, og ingen navneegenskap på `GuestGroup`.
  - Prisendring på retten endrer ikke ordrelinjen.
  - En annen kunde får `None` fra `get_for_user`.
  - `list_for_user` er sortert etter dato, og `list_all` filtrerer på status og periode og har med kunden.
  - `update_status` lagrer status, begrunnelse og betaling.
  - **Én transaksjon:** en ordre med en rett som ikke finnes, kaster feil, og det blir ikke liggende noen `Order`- eller `GuestGroup`-noder for kunden.
  - Spørsmål: `add` og `list_for_order` virker. `list_unanswered` viser eldste først (bare testens egne spørsmål sammenlignes, siden databasen er delt). `count_unanswered` går ned med 1 etter et svar. Et andre svar gir `AlreadyAnsweredError`, også direkte mot repositoryet (constrainten). `list_answered` har med svaret.

## Verifisering
1. `pytest` → alt grønt (SQLite)
2. `pytest -m neo4j` → alle Neo4j-testene grønne, og en telling etterpå viser at det ikke er noen testnoder igjen
3. Nettleseren med `STORAGE=neo4j` på port 5001, mot Aura-databasen som er seedet. Midlertidig kunde og admin.
   - **Kunde:** handlekurv, bestilling med to gjestegrupper, bekreftelse, «Mine bestillinger» og et spørsmål.
   - **Admin:** ordrelisten med filter, godkjenn, «Depositum betalt», svar på spørsmålet, og «Spørsmål (n)».
   - Til slutt slettes alt jeg laget fra Aura, så bare seed-dataene er igjen.
4. Commit og push på branchen `neo4j` (når du ber om det).
