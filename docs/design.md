# Ekte Mat Online – Software design (Oblig 4)

Prepared: 2026-10-22. Requirements: see [backlog.md](backlog.md) (US = user story, K = conflict).
Every diagram exists as Mermaid source (`design/*.mmd`, rendered by GitHub) and as a PNG for the report.
To re-render a PNG: `npx @mermaid-js/mermaid-cli -i design/<name>.mmd -o design/<name>.png`.

## 1 Use case diagram

```mermaid
flowchart LR
    V(("Visitor"))
    C(("Customer"))
    A(("Admin<br/>(event coordinator,<br/>head chef)"))
    AI(("AI image<br/>service"))

    subgraph SYS["Ekte Mat Online"]
        UC1(["UC1 Browse menu by event<br/>(US-01, US-02)"])
        UC2(["UC2 Manage cart<br/>(US-06, US-07)"])
        UC3(["UC3 Register / log in<br/>(US-19)"])
        UC4(["UC4 Submit order with guest groups<br/>(US-08, US-09, US-10)"])
        UC5(["UC5 View my orders<br/>(US-11)"])
        UC6(["UC6 Change number of guests<br/>(US-15)"])
        UC7(["UC7 Ask question about order<br/>(US-16)"])
        UC8(["UC8 Manage food items<br/>(US-03, US-04)"])
        UC9(["UC9 Add / generate item picture<br/>(US-05)"])
        UC10(["UC10 Manage orders:<br/>filter, order and payment status<br/>(US-12, US-13, US-14)"])
        UC11(["UC11 Answer questions<br/>(US-17)"])
        UC12(["UC12 Delete my account<br/>(US-21)"])
    end

    C -. "is a" .-> V
    V --- UC1
    V --- UC2
    V --- UC3
    C --- UC4
    C --- UC5
    C --- UC6
    C --- UC7
    C --- UC12
    UC4 -. "«include» log in" .-> UC3
    A --- UC8
    A --- UC9
    A --- UC10
    A --- UC11
    UC9 --- AI
```

![](design/01_use_case.png)

**How we used it:** to agree on scope and on who does what. Each use case lists the user stories it covers. We used it to split the work between the three blueprints: UC1–UC4 → `shop`, UC3, UC5–UC7 and UC12 → `account`, UC8–UC11 → `admin`.

## 2 Domain class diagram

```mermaid
classDiagram
    direction TB
    class User {
        id: int
        email: str
        name: str
        phone: str
        password_hash: str
        role: Role
    }
    class Role {
        <<enumeration>>
        CUSTOMER
        ADMIN
    }
    class FoodItem {
        id: int
        name: str
        description: str
        price_nok: Decimal
        min_order_qty: int
        published: bool
        archived: bool
        image_path: str
        image_prompt: str
        origin: str [0..1]
    }
    class EventCategory {
        id: int
        name: str
    }
    class Allergen {
        code: str
        name: str
    }
    class DietaryLabel {
        code: str
        name: str
    }
    class Cart {
        estimated_total_nok: Decimal
    }
    class CartLine {
        quantity: int
    }
    class Order {
        id: int
        created_at: datetime
        event_date: date
        guest_count: int
        delivery_address: str
        status: OrderStatus
        payment_status: PaymentStatus
        status_reason: str [0..1]
        estimated_total_nok: Decimal
    }
    class OrderLine {
        quantity: int
        unit_price_nok: Decimal
    }
    class GuestGroup {
        size: int
        notes: str
    }
    class Question {
        id: int
        text: str
        asked_at: datetime
    }
    class Answer {
        text: str
        answered_at: datetime
    }
    class OrderStatus {
        <<enumeration>>
        SUBMITTED
        APPROVED
        IN_PREPARATION
        DELIVERED
        REJECTED
        CANCELLED
    }
    class PaymentStatus {
        <<enumeration>>
        NOT_PAID
        DEPOSIT_PAID
        INVOICED
        PAID
    }

    User "1" --> "0..*" Order : places
    User "1" --> "0..1" Cart : has
    Cart "1" *-- "0..*" CartLine
    CartLine "0..*" --> "1" FoodItem
    Order "1" *-- "1..*" OrderLine
    OrderLine "0..*" --> "1" FoodItem
    Order "1" *-- "0..*" GuestGroup
    GuestGroup "0..*" --> "0..*" Allergen : avoids
    GuestGroup "0..*" --> "0..*" DietaryLabel : needs
    FoodItem "0..*" --> "1..*" EventCategory : suits
    FoodItem "0..*" --> "0..*" Allergen : contains
    FoodItem "0..*" --> "0..*" DietaryLabel : labelled
    Order "1" *-- "0..*" Question
    User "1" --> "0..*" Question : asks
    Question "1" *-- "0..1" Answer
    User "1" --> "0..*" Answer : writes (admin)
    User ..> Role
    Order ..> OrderStatus
    Order ..> PaymentStatus
```

![](design/02_domain_class.png)

**How we used it:** this is the source for the domain classes in `app/models/` and for the repository methods. Decisions behind it:

- **OrderLine copies `unit_price_nok`**, so a later price change does not alter old orders. Food items are archived (`archived = true`), never deleted (US-03).
- **GuestGroup has no name field.** Allergy data is stored per group only (GDPR, NFR-04).
- **Order status and payment status are two separate enumerations**, as the assignment requires (A3). Each has its own state machine.
- **Cart is a domain class but is not persisted.** It lives in the Flask session until the order is submitted.
- **Answer is 0..1 per Question.** Ekte Mat gives one answer, and the customer can ask a new question.
- There are no controllers, DTOs or methods in the diagram: it is a domain model, not a design of the implementation.

## 3 Sequence diagram – customer submits an order (C3)

```mermaid
sequenceDiagram
    autonumber
    actor Cu as Customer
    participant B as Browser
    participant OC as controllers<br/>(shop + account blueprints)
    participant Ca as Cart (model)
    participant FR as FoodItemRepository
    participant O as Order (model)
    participant OR as OrderRepository
    participant S as Store<br/>(SQLite now, Neo4j later)
    participant V as View<br/>(Jinja2 templates)

    Cu->>B: Fill in event date, guests,<br/>address, guest groups, then clicks Send order
    B->>OC: POST /order
    alt not logged in
        OC-->>B: 302 redirect /login?next=/order (cart kept in session)
    else logged in
        OC->>Ca: load cart from session
        Ca-->>OC: cart lines (item ids, quantities)
        OC->>FR: get_by_ids(item ids)
        FR->>S: read food items
        S-->>FR: rows
        FR-->>OC: FoodItem objects
        OC->>O: Order.create_from_cart(user, cart, items, form data)
        Note over O: Validates: event date in future,<br/>quantity ≥ min order, sum of guest groups ≤ guests.<br/>Sets status SUBMITTED, payment NOT_PAID,<br/>copies unit prices to order lines.
        alt validation fails
            O-->>OC: ValidationError(messages)
            OC->>V: render order_form.html with errors
            V-->>B: 400 order form with messages
        else valid
            O-->>OC: new Order
            OC->>OR: save(order)
            OR->>S: write order, lines, guest groups
            S-->>OR: order id
            OR-->>OC: saved Order
            OC->>Ca: clear()
            OC-->>B: 303 redirect /orders/<id>
            B->>OC: GET /orders/<id>
            OC->>OR: get_for_user(id, user)
            OR-->>OC: Order
            OC->>V: render order_detail.html
            V-->>B: 200 confirmation with order number and status
        end
    end
```

![](design/03_sequence_place_order.png)

**How we used it:** to show how one request moves through the MVC layers and to decide where validation belongs. It belongs in the **model** (`Order.create_from_cart`), not in the controller, so the same rules apply to future API or admin forms. It also gave us the repository methods we need (`get_by_ids`, `save`, `get_for_user`) and the test cases for US-07, US-08 and US-09.

## 4 State machine – order status

```mermaid
stateDiagram-v2
    direction LR
    [*] --> Submitted : customer submits
    Submitted --> Approved : admin approves
    Submitted --> Rejected : admin rejects [reason]
    Submitted --> Cancelled : cancel [reason]
    Approved --> InPreparation : admin starts preparation
    Approved --> Cancelled : cancel [reason]
    InPreparation --> Delivered : driver delivers
    Delivered --> [*]
    Rejected --> [*]
    Cancelled --> [*]

    InPreparation : In preparation
    note left of Submitted
        Customer may change guests
        and guest groups.
    end note
    note right of Approved
        Changes allowed until the
        deadline (open question K-02).
    end note
    note right of InPreparation
        Order is locked: no changes.
    end note
```

![](design/04_state_order.png)

**How we used it:** implemented as an allowed-transitions table in `Order` (e.g. `ALLOWED = {SUBMITTED: {APPROVED, REJECTED, CANCELLED}, ...}`). The admin order page shows only the buttons for valid next states, and an invalid transition raises an error (US-13). The deadline for guest changes is still open (K-02).

## 5 State machine – payment status

```mermaid
stateDiagram-v2
    direction LR
    [*] --> NotPaid : order created
    NotPaid --> DepositPaid : deposit registered (weddings / private, see K-01)
    NotPaid --> Invoiced : invoice sent (companies)
    DepositPaid --> Invoiced : final invoice sent
    Invoiced --> Paid : payment registered
    NotPaid --> Paid : paid in full
    Paid --> [*]

    NotPaid : Not paid
    DepositPaid : Deposit paid
```

![](design/05_state_payment.png)

**How we used it:** this machine is independent of the order status. It supports both payment models from conflict K-01: a deposit for weddings and private events, and an invoice for companies.

## 6 MVC architecture sketch

```mermaid
flowchart TB
    BR["<b>Browser</b><br/>HTML · CSS · JavaScript"]
    CTRL["<b>Controllers</b> · app/controllers/ (Flask blueprints)<br/>shop: /menu · /cart · /order<br/>account: /register · /login · /orders · /orders/&lt;id&gt;/questions<br/>admin: /admin/items · /admin/orders · /admin/questions"]
    VIEW["<b>Views</b> · app/templates/ (Jinja2)<br/>shop/*.html · account/*.html · admin/*.html"]
    DOM["<b>Models: domain classes</b> · app/models/<br/>FoodItem · Order · OrderLine · GuestGroup<br/>Question · Answer · User · Cart"]
    REPO["<b>Models: repositories</b> · app/models/repositories/<br/>FoodItemRepository · OrderRepository<br/>UserRepository · QuestionRepository"]
    IMG["services/image_service.py<br/>(AI image generation, optional)"]
    SQL[("SQLite / JSON<br/>Oblig 4")]
    NEO[("Neo4j<br/>Oblig 5")]

    BR -- "1 HTTP request" --> CTRL
    CTRL -- "2 uses domain logic" --> DOM
    CTRL -- "3 load / save" --> REPO
    REPO -- "builds / returns" --> DOM
    REPO -- "only layer that touches storage" --> SQL
    REPO -. "swap implementation later" .-> NEO
    CTRL -- "4 render_template(...)" --> VIEW
    VIEW -- "5 HTML response" --> BR
    CTRL -- "admin only" --> IMG
```

![](design/06_mvc_architecture.png)

Planned folder structure:

```
ektemat-online/
├── CLAUDE.md
├── README.md
├── .env.example            # SECRET_KEY=..., IMAGE_API_KEY=...  (real .env is git-ignored)
├── app/
│   ├── __init__.py         # create_app(), registers blueprints
│   ├── controllers/        # C: shop.py, account.py, admin.py (blueprints)
│   ├── models/             # M: domain classes (food_item.py, order.py, ...)
│   │   └── repositories/   # M: base.py (interfaces), sqlite_*.py now, neo4j_*.py in Oblig 5
│   ├── services/           # image_service.py (optional AI images)
│   ├── templates/          # V: shop/, account/, admin/ (Jinja2)
│   └── static/             # css/, js/, uploads/
├── seed.py                 # synthetic food items, one admin, test customers
├── tests/
└── docs/
    ├── backlog.md
    ├── design.md
    ├── design/             # *.mmd + *.png
    └── plans/              # plan-mode plans, one file per feature
```

**How we used it:** to enforce NFR-02. Controllers only call repository interfaces, so the SQLite implementation can be replaced with Neo4j in Oblig 5 without touching controllers or templates. We also gave the layout to Claude Code in `CLAUDE.md`.

## 7 Graph data model (preparation for Neo4j, Oblig 5)

```mermaid
flowchart LR
    U(("User<br/>{id, email, name, role}"))
    O(("Order<br/>{id, created_at, event_date, guest_count,<br/>status, payment_status}"))
    F(("FoodItem<br/>{id, name, price_nok,<br/>min_order_qty, published, archived}"))
    E(("EventCategory<br/>{id, name}"))
    AL(("Allergen<br/>{code, name}"))
    D(("DietaryLabel<br/>{code, name}"))
    G(("GuestGroup<br/>{position, size, notes}"))
    Q(("Question<br/>{id, text, asked_at}"))
    AN(("Answer<br/>{question_id, text, answered_at}"))

    U -- "PLACED" --> O
    O -- "CONTAINS {quantity, unit_price_nok}" --> F
    F -- "SUITS" --> E
    F -- "CONTAINS_ALLERGEN" --> AL
    F -- "HAS_LABEL" --> D
    O -- "HAS_GUEST_GROUP" --> G
    G -- "AVOIDS" --> AL
    G -- "NEEDS" --> D
    U -- "ASKED" --> Q
    Q -- "ABOUT" --> O
    AN -- "ANSWERS" --> Q
    U -- "WROTE" --> AN
```

![](design/07_graph_data_model.png)

**How we used it:** to check that the domain model maps cleanly to a graph. OrderLine becomes the relationship `CONTAINS {quantity, unit_price_nok}`. Allergen and DietaryLabel become shared nodes, which makes queries like "all of tomorrow's orders with guests who avoid nuts" easy for the optional kitchen view (US-22). Cart is not stored. **Implementation (Oblig 5):** `id` is our own integer property from a `(:Sequence {name, value})` counter, never Neo4j's internal id, because URLs and the session use integer ids. Unique constraints on `User.email`, `User.id`, `FoodItem.id`, `EventCategory.id/name`, `Allergen.code` and `DietaryLabel.code`. `price_nok`, `unit_price_nok` and `estimated_total_nok` are stored as text so amounts stay exact. An order with its `CONTAINS` relationships and guest groups is saved in one transaction. `GuestGroup.position` keeps the order the customer entered the groups in (a graph has no order); guest groups have no name field (NFR-04). `Answer.question_id` has a unique constraint so the database itself allows at most one answer per question. Constraints also cover `Order.id` and `Question.id`.

## 8 Consistency check

| Check | Result |
|---|---|
| Every use case traces to at least one user story | OK: UC1–UC12 all list their US IDs. |
| Every Must/Should story appears in a use case | OK, except **US-20** (admin access) and NFRs, which are cross-cutting and implemented as a `@admin_required` decorator, not a use case. EP6 (Could) is out of scope for the diagram. |
| Every model class in the sequence diagram exists in the class diagram | OK: Cart, FoodItem, Order (+ OrderLine and GuestGroup created inside). Controllers, repositories, store and views are architecture elements, shown in the MVC sketch. |
| The OrderStatus enumeration matches the state machine | OK: 6 values, 6 states. |
| The PaymentStatus enumeration matches the state machine | OK: 4 values, 4 states. |
| Every assignment requirement C1–C5 and A1–A4 is covered | C1 US-01/02 · C2 US-06/07 · C3 US-08/09/19 · C4 US-11 · C5 US-16 · A1 US-03/04 · A2 US-05 · A3 US-12/13/14 · A4 US-17 |
| Graph model matches the class diagram | OK. Intentional differences: Cart is not stored, and OrderLine is a relationship. |
