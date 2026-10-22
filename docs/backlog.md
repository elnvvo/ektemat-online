# Ekte Mat Online – Product backlog v1 (Oblig 4 scope)

Prepared: 2026-10-22 · Product owner: Ingrid Solheim (fictional) · All data is synthetic.

This backlog covers the scope of Obligatory assignment 4 (customer site C1–C5, admin panel A1–A4) and traces every item to its source. Quotes are copied word for word from the data pack. Anything without a stakeholder source is marked **ASSUMPTION**, or cites the assignment text (**OBLIG4**).

**Priorities (MoSCoW) for Oblig 4**

- **Must**: required for the assignment to be approved (C1–C5, A1–A4, MVC and the repository layer).
- **Should**: small additions that solve a real stakeholder problem. Build them if there is time.
- **Could**: the "Going further" ideas.
- **Won't (this release)**: outside the assignment, for example real payments.

**Source abbreviations**

| Code | File |
|---|---|
| INT-I | interview_Ingrid_owner.txt |
| INT-S | interview_Sunniva_event_coordinator.txt (duplicate: *Kopi av interview Sunniva (2).txt*, identical content) |
| INT-M | interview_Mateo_head_chef.txt |
| INT-F | interview_Fjordtek_customer.txt |
| ASIS | asis_order_process.md |
| GDPR | GDPR note from consultant.txt |
| IT | current_IT_landscape.txt |
| MENU | lunch menu autumn.txt |
| E0xx | customer_emails_export.csv, e-mail ID |
| OBLIG4 | INFO212_Oblig4_EkteMat_Claude_Code.pdf |

---

## 1 Stakeholders

| Stakeholder | Role | Interest / key concerns | Influence | Source |
|---|---|---|---|---|
| Ingrid Solheim | Owner, product owner | Requests that get lost, a 30 % deposit, showing where the food comes from, go-live 2027-03-01, budget 450 000 NOK | High | INT-I |
| Sunniva Berg | Event coordinator (main admin user) | Slow replies in peak season, guest-count changes, capacity, allergies per guest group | High | INT-S, ASIS |
| Mateo Rinaldi | Head chef | Kitchen screen, allergies in red, PIN login, editing the menu, speed | Medium | INT-M |
| Henrik Aas, Fjordtek AS | Corporate customer | Company login, copying last week's order, approval above 15 000 NOK, monthly EHF invoice, data in the EU/EEA | Medium | INT-F |
| Private customers | Weddings, confirmations, birthdays | Prices online, quick confirmation, Vipps, allergy labels | Medium | E001–E030 |
| Data-protection consultant | Advisor | Health data per guest group, retention, access and deletion | Medium (legal) | GDPR |

---

## 2 Epics

| Epic | Name | Assignment reqs | Stories |
|---|---|---|---|
| EP1 | Menu and food catalogue | C1, A1, A2 | US-01 – US-05 |
| EP2 | Cart and ordering | C2, C3 | US-06 – US-10 |
| EP3 | Order follow-up | C4, A3 | US-11 – US-15 |
| EP4 | Questions about orders | C5, A4 | US-16 – US-18 |
| EP5 | Accounts and privacy | C3 (login) | US-19 – US-21 |
| EP6 | Going further | optional | US-22 – US-26 |

---

## 3 User stories

### EP1 Menu and food catalogue

**US-01 Browse the menu by event** · Must · C1
As a *customer* I want to see food items as cards grouped by kind of event (birthday, confirmation, wedding, conference, julebord) so that I can quickly find food that fits my event.
- Given published items in the category "Julebord", when I open the menu and choose "Julebord", then I see only published items in that category, each with a picture, price in NOK and minimum order.
- Given an item that is not published, when any customer opens the menu, then the item is not shown.

Source: INT-I *"Customers must be able to see our menus and prices and send a booking request themselves, at any hour."* · E001 *"Can you send the menu and price?"*

**US-02 See allergens and dietary labels** · Must · C1
As a *customer with allergies among my guests* I want every card to show its allergens and dietary labels so that I do not have to guess what is safe.
- Given an item with the allergens "fish" and "gluten", when it is shown on the menu, then both allergens are visible on the card without opening it.
- Given an item labelled "vegetarian", when I view the card, then the label "V" (or "Vegetarian") is shown.

Source: E019 *"Please label gluten-free items clearly on the buffet. Last time we had to guess."* · MENU *"Allergens to be labelled: fish, milk, gluten, nuts, celery, mustard."*

**US-03 Manage food items** · Must · A1
As an *admin (event coordinator or chef)* I want to add, edit and remove food items (name, description, price, minimum order, event categories, allergens, dietary labels) so that the menu stays correct when it changes with the season.
- Given I am logged in as admin, when I save a new item with all required fields, then it appears in the admin item list.
- Given I enter a negative price or a minimum order below 1, when I save, then the item is not saved and I see a message naming the field.
- Given an item that is part of an existing order, when I remove it, then the item is hidden (unpublished or archived) and is not deleted, so old orders still show what was ordered.

Source: INT-M *"Menus change with the season, four times a year. I want to edit the menu myself"*

**US-04 Publish and unpublish an item** · Must · A1
As an *admin* I want to mark an item as published or not published so that seasonal dishes only appear when they are available.
- Given an unpublished item, when I set it to published, then it appears on the customer menu on the next page load.

Source: MENU *"Rakfisk tasting (seasonal, Nov only)"* · INT-M (seasonal menus, as above)

**US-05 Add a picture to an item** · Must · A2
As an *admin* I want to upload a picture, or write an instruction that an AI image service uses to create or change the picture, and preview the result before saving, so that every card has an attractive photo.
- Given I upload a JPG or PNG under 5 MB, when I click "Preview", then I see the picture on a card preview, and it is only stored when I click "Save".
- Given I write an image instruction, when the image service returns a picture, then I can accept it (save) or reject it (nothing changes).
- Given a file that is not an image, when I upload it, then it is rejected with a message.

Source: OBLIG4 A2. The 5 MB limit is an ASSUMPTION. No stakeholder mentioned pictures, but INT-I asks for a brand that is *"Authentic, seasonal, honest about where the food comes from."*

### EP2 Cart and ordering

**US-06 Shopping cart with estimated total** · Must · C2
As a *customer* I want to add, change and remove items in a cart and see an estimated total so that I know the price before I send the order.
- Given 30 × fish soup at 189 NOK, when I view the cart, then the estimated total is 5 670 NOK.
- Given an item in the cart, when I change the quantity or remove it, then the total is updated at once.

Source: E015 *"We need a quote for a seminar lunch 80 people by Friday for internal approval."* · OBLIG4 C2

**US-07 Enforce minimum order** · Must · C2
As *Ekte Mat* I want quantities below an item's minimum order to be rejected so that we do not receive orders we cannot deliver.
- Given an item with minimum order 10, when a customer enters 8, then the cart is not updated and the message says that the minimum is 10.
- Given a minimum order of 10, when the customer enters 10, then the change is accepted.

Source: OBLIG4 C2

**US-08 Submit an order** · Must · C3
As a *logged-in customer* I want to submit my cart as an order with the event date, number of guests and delivery address so that my request is registered at once and cannot get lost.
- Given a non-empty cart, when I submit a future event date, the number of guests (1 or more) and an address, then an order is created with status "submitted" and I see an order number.
- Given an event date in the past, when I submit, then the order is rejected with a message.
- Given I am not logged in, when I click "Order", then I am sent to log in or register, and my cart is kept.

Source: INT-I *"Last December we found three julebord requests in the spam folder after the date had passed."*

**US-09 Allergy and dietary notes per guest group** · Must · C3
As a *customer* I want to add allergy and dietary notes per guest group (e.g. "4 guests: vegan", "2 guests: nut allergy") so that the kitchen knows exactly what to prepare.
- Given an order form, when I add a guest group, then I must enter a size (1 or more) and at least one allergy or diet.
- Given the total of all guest groups is larger than the number of guests, when I submit, then I am asked to correct it.
- The form never asks for the names of guests (see NFR-04).

Source: INT-S *"Every order has to show allergies and diets per guest group"* · GDPR *"Store per guest group, not per named guest, unless strictly needed."* · E017 *"The note said 'V x4' but nothing came."*

**US-10 Order confirmation** · Should · C3
As a *customer* I want to see a confirmation page (and an e-mail, if this is implemented) after ordering so that I know the order was received.
- Given a submitted order, then the confirmation page shows the order number, date, guests, lines and estimated total.

Source: E011 *"Is our order for tomorrow confirmed? We never got a confirmation e-mail."*

### EP3 Order follow-up

**US-11 My orders** · Must · C4
As a *customer* I want to see my own orders with their order status and payment status so that I do not have to e-mail to ask.
- Given I have three orders, when I open "My orders", then I see all three, sorted by event date, each showing its order status and payment status.
- Given another customer's order ID in the URL, when I open it, then I get "not found" or "forbidden" and none of the data is shown.

Source: E011 (as above)

**US-12 Order list for admin** · Must · A3
As an *admin* I want a list of all orders that I can filter by status and by event date so that I can see what needs handling and what is happening each day.
- Given orders with different statuses, when I filter on "submitted", then only submitted orders are shown.
- Given a date range, when I filter, then only orders with an event date in that range are shown, sorted by date.

Source: ASIS *"Coordinator prints the order and pins it on the kitchen board."* · INT-S *"I read the e-mail, check the calendar in Google to see if we have capacity that day"*

**US-13 Manage order status** · Must · A3
As an *admin* I want to move an order through the statuses submitted → approved → in preparation → delivered, or reject or cancel it, so that customer and staff always see where the order stands.
- Given an order in "submitted", when I approve it, then the status becomes "approved" and the customer sees this in "My orders".
- Given an order in "delivered", when I try to set it back to "submitted", then this is not allowed (see the state machine).
- Given an order in "submitted" or "approved", when I reject or cancel it, then I must enter a reason.

Source: ASIS steps 2–10 · E011 · OBLIG4 A3

**US-14 Manage payment status** · Must · A3
As an *admin* I want to set the payment status (not paid, deposit paid, invoiced, paid) so that we know who has paid without checking Fiken by hand.
- Given an order, when I set the payment status to "deposit paid", then it is shown on the order page and in "My orders".

Source: ASIS *"For weddings, the coordinator sends a Vipps payment request for a deposit (sometimes forgotten)."* · E030 *"We received a payment reminder for an invoice we paid on 2 Sept."*

**US-15 Change number of guests** · Should
As a *customer* I want to change the number of guests and the guest groups on an order before a deadline so that I do not have to phone.
- Given an order in "submitted" or "approved" and the deadline has not passed, when I change the guests from 40 to 55, then the order is updated and the admin can see that it was changed.
- Given the deadline has passed, then the fields are read-only and I am told to ask a question (US-16).

Source: E003 *"we need to change from 40 to 55 guests for our event next Thursday. I called yesterday but nobody picked up."* · INT-S *"Changes in guest numbers come by phone ... Sometimes I forget."* The deadline is an open question, see conflict K-02.

### EP4 Questions about orders

**US-16 Ask a question about an order** · Must · C5
As a *customer* I want to ask a question about a specific order and read the answer on the same page so that the whole conversation is kept with the order.
- Given my order, when I send a question, then it appears under the order with the time it was sent and the status "unanswered".
- Given an answer from Ekte Mat, when I open the order, then I see the answer under my question.

Source: E013 *"What are your cancellation terms?"* · E003 *"I called yesterday but nobody picked up."*

**US-17 Answer customer questions** · Must · A4
As an *admin* I want a list of unanswered questions, oldest first, with a link to the order so that no question is forgotten.
- Given two unanswered questions, when I open "Questions", then both are shown, oldest first.
- Given I answer a question, then it is marked "answered" and leaves the unanswered list.

Source: INT-S *"In December and in May it can be a week. People get annoyed."* · E006 *"I sent a request 6 days ago and have not heard back. We have booked another caterer now."*

**US-18 Question count on the admin start page** · Could
As an *admin* I want to see the number of unanswered questions on the admin start page so that I notice new questions right away.
Source: ASSUMPTION, derived from INT-S and E006.

### EP5 Accounts and privacy

**US-19 Register and log in** · Must · C3
As a *customer* I want to register with my e-mail and a password and log in so that my orders and questions are kept together.
- Given a new e-mail address, when I register with a password of at least 8 characters, then my account is created and I am logged in.
- Given the wrong password, when I log in, then I see a general error message that does not say whether the e-mail exists.

Source: INT-F *"A login for our company where I can see our standing orders"* · OBLIG4 C3

**US-20 Separate admin access** · Must · A1–A4
As *Ekte Mat* I want only admin users to reach the admin panel so that customers cannot change menus or orders.
- Given a logged-in customer, when they open /admin, then they get 403 or are sent to the login page.

Source: OBLIG4 §2. ASSUMPTION: a seeded admin user is enough, so admin registration is not needed.

**US-21 Delete my account** · Should
As a *customer* I want to ask for my personal data to be deleted so that Ekte Mat follows GDPR.
- Given I delete my account, then my name, e-mail and phone number are removed or anonymised. Orders that are needed for bookkeeping are kept without personal identifiers.

Source: E010 *"Please delete all personal data you have about me and confirm by e-mail."* · GDPR *"Customers must be able to request access and deletion."*

### EP6 Going further (optional ideas from the data pack)

| ID | Story | Priority | Source |
|---|---|---|---|
| US-22 | As the *head chef* I want a kitchen view of today's orders with portions per dish and allergies in red so that nothing is missed. | Could | INT-M *"For each day: which orders, how many portions of each dish, allergies in red."* |
| US-23 | As the *event coordinator* I want a warning when the guests for a date go over the kitchen's capacity so that I do not overbook. | Could | INT-S *"Our kitchen can do about 400 covers a day, 250 if there is a wedding with a served dinner."* |
| US-24 | As a *corporate customer* I want to copy a previous order so that I do not have to type it in again. | Could | INT-F *"copy last week's order"* · E028 *"Could we just get exactly the same as our order in September?"* |
| US-25 | As a *customer* I want to see the origin of the food (farm or boat) on each card so that I can choose local food. | Could | INT-I *"I would love every menu to show where the lamb or the fish comes from"* · E008 *"Which farm is the lamb from?"* |
| US-26 | As an *international customer* I want the site in English and Norwegian so that I understand the menu. | Could | IT *"Norwegian and English UI."* · E012 *"Is your menu available in English with allergens marked?"* |

**Won't (this release):** real Vipps payment, a Fiken/EHF integration, and approval rules for company accounts (above 15 000 NOK). The assignment says *"No payment solution is needed."* (OBLIG4 C3). They stay in the product backlog for later releases (sources: INT-I, INT-F, E004, E016).

---

## 4 Non-functional requirements

| ID | Quality characteristic | Measurable requirement | Source |
|---|---|---|---|
| NFR-01 | Performance | The menu page and the admin order list load in under 2 s with 100 food items and 1 000 orders (seed data, local machine). | INT-M *"The old booking plugin on the website took ten seconds to load a page."* The number is an ASSUMPTION. |
| NFR-02 | Maintainability (modularity) | 100 % of storage access goes through repository classes in `app/models/`. 0 imports of `sqlite3`, `json` file I/O or a database driver in controllers or templates (checked with grep in CI or before tagging). | OBLIG4 §3 |
| NFR-03 | Security (confidentiality) | Passwords are stored only as salted hashes (e.g. Werkzeug `generate_password_hash`). 0 secrets (API keys, `SECRET_KEY`) in the Git history. `.env` is in `.gitignore` from the first commit. | OBLIG4 §3 |
| NFR-04 | Privacy | Allergy and diet data is stored per guest group only. The data model has 0 fields for guest names. | GDPR *"Store per guest group, not per named guest, unless strictly needed."* |
| NFR-05 | Privacy (retention) | Order data needed for bookkeeping is kept for 5 years. A deleted account is anonymised within 30 days. | GDPR *"Keep order data needed for bookkeeping 5 years"*. The 30 days is an ASSUMPTION. |
| NFR-06 | Security (access control) | 100 % of `/admin/*` routes require the admin role. A customer can read only their own orders (verified by an automated test per route). | ASSUMPTION based on OBLIG4 §2 |
| NFR-07 | Portability (data residency) | When deployed, all data is hosted in the EU/EEA. | INT-F *"They want it in the EU/EEA"* · IT *"data must stay in EU/EEA (GDPR)"* |
| NFR-08 | Usability | All customer pages work on a 360 px wide screen without horizontal scrolling. | ASSUMPTION. Customers order "at any hour" (INT-I), often from their phone. |
| NFR-09 | Testability | `README.md` gives the commands to install, seed, run and test. Every Must story has at least one automated test, and `pytest` passes before the `oblig4` tag. | OBLIG4 §3. The test rule is a team rule (ASSUMPTION). |

---

## 5 Conflicts and open questions for the product owner

| ID | Conflict | Who disagrees | Question for Ingrid | Our working decision for Oblig 4 |
|---|---|---|---|---|
| K-01 | A deposit for every booking, or no prepayment for companies | Ingrid (*"no deposit, no booking"*) vs Sunniva (*"corporate clients hate prepayment"*) and Fjordtek (*"We cannot prepay"*) | Should the 30 % deposit apply only to weddings and private events, and companies get a monthly invoice? (yes/no) | The payment status has both "deposit paid" and "invoiced", so either rule can be used. |
| K-02 | Deadline for changing the number of guests | Fjordtek (*"until 10:00 the day before"*) vs Sunniva (reminder *"seven days before the event"*) vs E022 (change on the same day) | What is the last time a customer can change the guests: days before the event, and does it differ by event type? (number) | Changes are allowed until the order is "in preparation". |
| K-03 | Ordering only online vs by phone | Vision (*"book and change orders any time"*) vs E024 (*"Jeg er 82 år ... Kan jeg fortsatt bestille på telefon?"*) | Should staff be able to register an order on behalf of a phone customer? (yes/no) | Not in Oblig 4. Admins can see and edit orders, but cannot create them. |
| K-04 | Delivery only vs pickup | OBLIG4 C3 (delivery address) vs E014 (*"Kan vi hente maten selv i stedet for levering?"*) | Should customers be able to choose pickup? (yes/no) | Delivery address is required. Pickup is a possible extension. |
| K-05 | Kitchen capacity depends on the event type | INT-S (400 covers, or 250 with a wedding dinner) vs a simple per-day limit | Is 250 the limit for the whole day when there is a wedding dinner, or 250 for the wedding alone? (number) | Only relevant if US-23 is built. |
| K-06 | Easy PIN login in the kitchen vs protecting health data | INT-M (*"a PIN is fine"*) vs GDPR (allergy data is special-category data) | Can the kitchen tablet show allergy data behind a 4-digit PIN? (yes/no) | Only relevant if US-22 is built. |
| K-07 | Changes after "approved" | OBLIG4 lifecycle vs E003 and E022 (late changes) | Does a change of guests after approval need a new approval? (yes/no) | The order stays "approved", and the change is visible to the admin. |
| K-08 | Build our own system or use an off-the-shelf SaaS | Kick-off notes: *"Open question: build our own system or configure an off-the-shelf catering SaaS?"* | Decided by the assignment: we build our own. | Closed. |

---

## 6 Audit trail

| File | Read | Stories / NFRs that cite it |
|---|---|---|
| interview_Ingrid_owner.txt | yes | US-01, 05, 08, 25, K-01 |
| interview_Sunniva_event_coordinator.txt | yes | US-09, 12, 15, 17, 23, K-01, K-02, K-05 |
| Kopi av interview Sunniva (2).txt | yes, identical to the above | (duplicate, not cited) |
| interview_Mateo_head_chef.txt | yes | US-03, 04, 22, NFR-01, K-06 |
| interview_Fjordtek_customer.txt | yes | US-19, 24, NFR-07, K-01, K-02 |
| notes meeting 12 aug FINAL.txt | yes | K-08 |
| asis_order_process.md | yes | US-12, 13, 14 |
| GDPR note from consultant.txt | yes | US-09, 21, NFR-04, NFR-05 |
| current_IT_landscape.txt | yes | US-26, NFR-07 |
| budget and constraints.txt | yes | (context only: go-live 2027-03-01) |
| lunch menu autumn.txt | yes | US-02, 04 (and seed data) |
| vision_draft_v0.3.docx | yes | K-03 |
| customer_emails_export.csv | yes (30 e-mails) | US-01, 02, 06, 09, 10, 11, 14, 15, 16, 17, 21, 24, 25, 26, K-02, K-03, K-04 |
| orders_2024_2025_export.xlsx | no | not needed for the Oblig 4 scope |
| logo ideas.txt, untitled.txt, competitor links.txt | no | not relevant |
