-- Ekte Mat Online – SQLite-skjema (Oblig 4). Speiler klassediagrammet i docs/design.md §2.
-- Cart lagres ikke (ligger i Flask-sesjonen).

DROP TABLE IF EXISTS answers;
DROP TABLE IF EXISTS questions;
DROP TABLE IF EXISTS guest_group_dietary_labels;
DROP TABLE IF EXISTS guest_group_allergens;
DROP TABLE IF EXISTS guest_groups;
DROP TABLE IF EXISTS order_lines;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS food_item_dietary_labels;
DROP TABLE IF EXISTS food_item_allergens;
DROP TABLE IF EXISTS food_item_event_categories;
DROP TABLE IF EXISTS food_items;
DROP TABLE IF EXISTS dietary_labels;
DROP TABLE IF EXISTS allergens;
DROP TABLE IF EXISTS event_categories;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT NOT NULL UNIQUE,
    name          TEXT NOT NULL,
    phone         TEXT,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'customer' CHECK (role IN ('customer', 'admin'))
);

CREATE TABLE event_categories (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE allergens (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE dietary_labels (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE food_items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    price_nok     NUMERIC NOT NULL CHECK (price_nok >= 0),
    min_order_qty INTEGER NOT NULL DEFAULT 1 CHECK (min_order_qty >= 1),
    published     INTEGER NOT NULL DEFAULT 0 CHECK (published IN (0, 1)),
    image_path    TEXT,
    image_prompt  TEXT,
    origin        TEXT
);

CREATE TABLE food_item_event_categories (
    food_item_id      INTEGER NOT NULL REFERENCES food_items (id),
    event_category_id INTEGER NOT NULL REFERENCES event_categories (id),
    PRIMARY KEY (food_item_id, event_category_id)
);

CREATE TABLE food_item_allergens (
    food_item_id  INTEGER NOT NULL REFERENCES food_items (id),
    allergen_code TEXT NOT NULL REFERENCES allergens (code),
    PRIMARY KEY (food_item_id, allergen_code)
);

CREATE TABLE food_item_dietary_labels (
    food_item_id       INTEGER NOT NULL REFERENCES food_items (id),
    dietary_label_code TEXT NOT NULL REFERENCES dietary_labels (code),
    PRIMARY KEY (food_item_id, dietary_label_code)
);

CREATE TABLE orders (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER REFERENCES users (id),
    created_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    event_date          TEXT NOT NULL,
    guest_count         INTEGER NOT NULL CHECK (guest_count >= 1),
    delivery_address    TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'submitted'
        CHECK (status IN ('submitted', 'approved', 'in_preparation', 'delivered', 'rejected', 'cancelled')),
    payment_status      TEXT NOT NULL DEFAULT 'not_paid'
        CHECK (payment_status IN ('not_paid', 'deposit_paid', 'invoiced', 'paid')),
    status_reason       TEXT,
    estimated_total_nok NUMERIC NOT NULL DEFAULT 0
);

-- unit_price_nok kopieres ved bestilling, så senere prisendringer ikke endrer gamle ordre.
CREATE TABLE order_lines (
    order_id       INTEGER NOT NULL REFERENCES orders (id),
    food_item_id   INTEGER NOT NULL REFERENCES food_items (id),
    quantity       INTEGER NOT NULL CHECK (quantity >= 1),
    unit_price_nok NUMERIC NOT NULL,
    PRIMARY KEY (order_id, food_item_id)
);

-- GDPR (NFR-04): allergier og dietter lagres per gjestegruppe. Ingen felt for gjestenavn.
CREATE TABLE guest_groups (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders (id),
    size     INTEGER NOT NULL CHECK (size >= 1),
    notes    TEXT NOT NULL DEFAULT ''
);

CREATE TABLE guest_group_allergens (
    guest_group_id INTEGER NOT NULL REFERENCES guest_groups (id),
    allergen_code  TEXT NOT NULL REFERENCES allergens (code),
    PRIMARY KEY (guest_group_id, allergen_code)
);

CREATE TABLE guest_group_dietary_labels (
    guest_group_id     INTEGER NOT NULL REFERENCES guest_groups (id),
    dietary_label_code TEXT NOT NULL REFERENCES dietary_labels (code),
    PRIMARY KEY (guest_group_id, dietary_label_code)
);

CREATE TABLE questions (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders (id),
    user_id  INTEGER REFERENCES users (id),
    text     TEXT NOT NULL,
    asked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Maks ett svar per spørsmål (design.md §2).
CREATE TABLE answers (
    question_id INTEGER PRIMARY KEY REFERENCES questions (id),
    user_id     INTEGER REFERENCES users (id),
    text        TEXT NOT NULL,
    answered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
