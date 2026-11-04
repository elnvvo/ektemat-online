# Plan: US-05 – bilde på matretten: opplasting eller bildeinstruks, med forhåndsvisning (A2)

## Kontekst
Alle rettene viser i dag plassholderbildet. Admin trenger å kunne gi hvert kort et ordentlig bilde (A2), enten ved å laste opp et foto eller ved å skrive en instruks til en bildetjeneste. Bildet skal forhåndsvises på kortet før det lagres. Dette er den siste Must-storyen i backlogen. Appen må virke uten API-nøkkel, og nøkkelen skal aldri stå i koden (NFR-03).

Planen kopieres til `docs/plans/10-us-05-images.md` som første steg etter godkjenning.

## Filer

```
app/models/item_image.py                       NY    validering av bildefil (type, størrelse) – i modellen
app/services/__init__.py                       NY
app/services/image_service.py                  NY    ImageService-grensesnitt, DummyImageService, ApiImageService, get_image_service()
app/services/image_store.py                    NY    lagring av filer i app/static/uploads (midlertidig → lagret, sletting, opprydding)
app/models/repositories/base.py                ENDRE FoodItemRepository.set_image(item_id, image_path, image_prompt)
app/models/repositories/sqlite_food_item_repository.py ENDRE set_image
app/controllers/admin.py                       ENDRE /admin/items/<id>/image (+ upload, generate, save, cancel)
app/config.py                                  ENDRE UPLOAD_FOLDER, MAX_CONTENT_LENGTH, IMAGE_API_KEY/IMAGE_API_URL fra .env
app/__init__.py                                ENDRE 413-handler (for stor fil)
app/templates/_food_card.html                  NY    matkortet som makro (brukes av menyen og forhåndsvisningen)
app/templates/shop/menu.html                   ENDRE bruker makroen
app/templates/admin/item_image.html            NY    bildesiden: nåværende kort, forhåndsvisning, opplasting, instruks
app/templates/admin/items.html, item_form.html ENDRE lenke «Bilde»
app/static/uploads/.gitkeep                    NY
.gitignore                                     ENDRE app/static/uploads/* (men behold .gitkeep)
.env.example                                   ENDRE IMAGE_API_KEY=, IMAGE_API_URL=
tests/conftest.py                              ENDRE UPLOAD_FOLDER = tmp_path i test-appen
tests/test_item_images.py                      NY    US-05
```

Plassholderbildet ligger i `app/static/img/` og påvirkes ikke av `.gitignore`. `schema.sql` har allerede `image_path` og `image_prompt`, så databasen trenger ingen endring.

## Validering – `app/models/item_image.py`
`validate_image(filename, data) -> extension` kaster `ValidationError({"image": …})`:
- Ingen fil eller tom fil gir «Velg en bildefil.»
- Over **5 MB** gir «Bildet er for stort (maks 5 MB).»
- Filtypen må være **.jpg, .jpeg eller .png**, og **innholdet må også være et ekte JPG eller PNG**. Det sjekkes med de første bytene i filen (PNG `\x89PNG\r\n\x1a\n`, JPEG `\xff\xd8\xff`), så en tekstfil som har fått navnet `bilde.png`, blir avvist. Ellers gir det «Bare JPG- og PNG-bilder er tillatt.». Dette krever ingen ny pakke (som Pillow).
- `MAX_CONTENT_LENGTH` settes til 6 MB, så Flask stopper veldig store opplastinger før de leses inn. Det gir 413 og en vennlig melding.

## Bildetjenesten – `app/services/image_service.py`
```python
class ImageService(ABC):
    def generate(self, prompt: str, current_image: bytes | None = None) -> GeneratedImage: ...
GeneratedImage(data: bytes, extension: str)
get_image_service()  # DummyImageService hvis IMAGE_API_KEY mangler, ellers ApiImageService
```
- **`DummyImageService`**: lager et enkelt **PNG** på 400×300 i ren Python (`zlib` + `struct`). Fargen er avledet av instruksen, så ulike instrukser gir synlig ulike bilder. Appen virker dermed uten nøkkel, og bildet kan forhåndsvises og lagres som et ekte bilde.
- **`ApiImageService`**: et generisk HTTP-kall med `urllib`. POST til `IMAGE_API_URL` med `Authorization: Bearer <IMAGE_API_KEY>` og JSON `{"prompt": …}`, og svaret forventes å være bildebytes. Svaret valideres med `validate_image`. Ved tidsavbrudd eller feil kommer meldingen «Bildetjenesten svarte ikke. Prøv igjen eller last opp et bilde.». Ingen leverandør er bestemt, så denne klassen må tilpasses den tjenesten dere velger.
- Nøkkel og URL leses bare fra `.env` via `Config`. `.env.example` får `IMAGE_API_KEY=` og `IMAGE_API_URL=` med tomme verdier.

## Lagring av filer – `app/services/image_store.py`
- `save_temp(data, original_name, ext) -> filnavn`: lagres i `UPLOAD_FOLDER/tmp/` med navnet `<uuid4>_<secure_filename(navn)>.<ext>`
- `promote(temp_name) -> "uploads/<navn>"`: flytter filen fra `tmp/` til `uploads/` og returnerer stien relativt til `static`, som er den som lagres på `FoodItem`
- `discard(temp_name)` sletter den midlertidige filen, og `delete_saved(image_path)` sletter et tidligere opplastet bilde. `delete_saved` rører **aldri** `img/placeholder.svg` eller noe utenfor `uploads/`.
- `cleanup_stale(max_age=1 time)`: sletter gamle midlertidige filer, og kjøres ved hver ny opplasting
- Filnavn fra sessionen sjekkes mot mønsteret `^[0-9a-f]{32}_[\w.-]+$` og må finnes i `tmp/`, så ingen kan sende inn en sti som `../`.

Dette er filer og ikke databasen, så det ligger i `services/` (som design.md §6 viser) og ikke i en controller.

## Flyten – `admin.py`
Alle rutene har `@admin_required`, og tilgangstesten dekker dem automatisk.

| Rute | Metode | Hva |
|---|---|---|
| `/admin/items/<id>/image` | GET | nåværende kort; hvis et bilde venter: **forhåndsvisning** av kortet + «Lagre» og «Avbryt»/«Avvis» |
| `/admin/items/<id>/image/upload` | POST | `validate_image` → `save_temp` → `session["pending_image"] = {item_id, file, prompt: None}` |
| `/admin/items/<id>/image/generate` | POST | tom instruks avvises → `get_image_service().generate(prompt)` → `save_temp` → pending med prompt |
| `/admin/items/<id>/image/save` | POST | `promote` → `repository.set_image(id, path, prompt)` → sletter forrige opplastede bilde → tømmer pending |
| `/admin/items/<id>/image/cancel` | POST | `discard` → tømmer pending (det gamle bildet blir stående) |

- Det ventende bildet hører til én rett. Hvis `item_id` ikke stemmer, eller filen mangler, ignoreres det og ryddes bort.
- Lastes det opp eller genereres et nytt bilde mens et annet venter, slettes det forrige midlertidige bildet først.
- Lagres et opplastet bilde, beholdes `image_prompt` som før. Lagres et generert bilde, lagres instruksen.

## Views
- **`_food_card.html`**: matkortet fra `menu.html` flyttes til en makro `food_card(item, image_path=None, with_cart_form=True)`, så forhåndsvisningen er nøyaktig det kunden vil se.
- **`admin/item_image.html`**: «Nåværende kort» og, hvis et bilde venter, «Forhåndsvisning» side om side. Under forhåndsvisningen står knappene **«Lagre»** og **«Avbryt»** (for opplasting) eller **«Avvis»** (for generert bilde). Til slutt kommer to skjemaer: «Last opp bilde» (`accept=".jpg,.jpeg,.png"`, `enctype=multipart/form-data`, «JPG eller PNG, maks 5 MB») og «Lag bilde fra instruks» (textarea fylt ut med `item.image_prompt`). En liten tekst sier om bildetjenesten er i demo-modus (uten nøkkel).
- Adminlisten og skjemaet for å endre en rett får lenken «Bilde».

## Tester – `tests/test_item_images.py`
Testappen bruker `UPLOAD_FOLDER = tmp_path/"uploads"` og `IMAGE_API_KEY = None`.
- `test_upload_png_shows_preview_but_does_not_save`: forhåndsvisningen viser det midlertidige bildet, og retten har fortsatt det gamle bildet
- `test_save_stores_image_on_food_item_and_menu_shows_it`: `image_path` begynner med `uploads/`, filen finnes, `tmp/` er tom, og `/menu` viser bildet
- `test_cancel_keeps_old_image_and_removes_temp_file`
- `test_upload_jpg_is_accepted`
- `test_non_image_file_is_rejected` (tekstfil, og tekst med navnet `.png`), med melding
- `test_gif_is_rejected`
- `test_file_over_5_mb_is_rejected` (5 MB + 1 byte), med melding
- `test_filename_is_secure_and_unique`: `../../evil name.png` blir `<uuid>_evil_name.png`, og to opplastinger gir ulike navn
- `test_prompt_generates_preview_with_dummy_service`: uten nøkkel brukes `DummyImageService`, og forhåndsvisningen vises
- `test_accept_generated_image_saves_path_and_prompt`
- `test_reject_generated_image_changes_nothing`
- `test_empty_prompt_is_rejected`
- `test_get_image_service_uses_dummy_without_key` / `…api_with_key`
- `test_save_replaces_and_deletes_previous_upload` (plassholderen slettes aldri)
- `test_save_without_pending_image_does_nothing`
- `test_validate_image_unit`: enhetstester av valideringen

## Verifisering
1. `pytest` → alle tester grønne, og `test_every_admin_route_requires_admin_role` dekker de fem nye rutene
2. Midlertidig testserver (egen database og egen uploads-mappe i scratchpad): logg inn som admin og åpne «Bilde» på Fiskesuppe. Last opp en PNG (forhåndsvisning), trykk «Avbryt» (gammelt bilde står igjen), last opp på nytt og trykk «Lagre» (vises på `/menu`). Prøv en `.txt`-fil (melding). Skriv en instruks (dummy-bilde), og trykk «Avvis» og så «Lagre». Sjekk at `tmp/` er tom etterpå, og visningen på 360 px.
3. `git status` → filer i `app/static/uploads/` vises ikke
4. Start `flask` på port 5000 på nytt.
5. Commit (når du ber om det) med en melding som nevner US-05
