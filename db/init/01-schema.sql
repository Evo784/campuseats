-- Schéma CampusEats (par Nathan). PostgreSQL.
-- Exécuté automatiquement au premier démarrage du conteneur (base campuseats).

CREATE TABLE roles (
    id_role BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    label VARCHAR(50) NOT NULL UNIQUE,
    role_date DATE NOT NULL DEFAULT CURRENT_DATE
);

CREATE TABLE users (
    id_user BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    password_hash TEXT NOT NULL,
    id_role BIGINT NOT NULL,
    CONSTRAINT uq_users_email UNIQUE (email),
    CONSTRAINT fk_users_role FOREIGN KEY (id_role) REFERENCES roles(id_role) ON DELETE RESTRICT,
    CONSTRAINT ck_users_email CHECK (email = LOWER(email) AND email LIKE '%_@_%._%'),
    CONSTRAINT ck_users_password CHECK (LENGTH(password_hash) > 0)
);

CREATE TABLE dishes (
    id_dish BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    label VARCHAR(150) NOT NULL,
    type VARCHAR(50) NOT NULL CHECK (type IN ('STARTER', 'MAIN', 'DESSERT'))
);

-- Un menu par jour
CREATE TABLE menus (
    id_menu BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    menu_date DATE NOT NULL UNIQUE,
    price NUMERIC(10,2) NOT NULL,
    CONSTRAINT ck_menus_price CHECK (price >= 0)
);

-- Many-to-many : menus <-> dishes
CREATE TABLE menu_items (
    id_menu BIGINT NOT NULL,
    id_dish BIGINT NOT NULL,
    PRIMARY KEY (id_menu, id_dish),
    CONSTRAINT fk_menu_items_menu FOREIGN KEY (id_menu) REFERENCES menus(id_menu) ON DELETE CASCADE,
    CONSTRAINT fk_menu_items_dish FOREIGN KEY (id_dish) REFERENCES dishes(id_dish) ON DELETE RESTRICT
);

-- Une commande = le menu entier ; quantity = nombre de menus complets
CREATE TABLE orders (
    id_order BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_user BIGINT NOT NULL,
    id_menu BIGINT NOT NULL,
    order_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payment_method VARCHAR(20) NOT NULL,
    is_delivered BOOLEAN NOT NULL DEFAULT FALSE,
    quantity INTEGER NOT NULL DEFAULT 1,
    CONSTRAINT fk_orders_user FOREIGN KEY (id_user) REFERENCES users(id_user) ON DELETE RESTRICT,
    CONSTRAINT fk_orders_menu FOREIGN KEY (id_menu) REFERENCES menus(id_menu) ON DELETE RESTRICT,
    CONSTRAINT ck_orders_payment CHECK (payment_method IN ('CARD','CASH','VISA','MASTERCARD','OTHER')),
    CONSTRAINT ck_orders_quantity CHECK (quantity > 0)
);

CREATE INDEX idx_users_role ON users(id_role);
CREATE INDEX idx_menu_items_dish ON menu_items(id_dish);
CREATE INDEX idx_orders_user ON orders(id_user);
CREATE INDEX idx_orders_menu ON orders(id_menu);
CREATE INDEX idx_orders_date ON orders(order_date);

INSERT INTO roles (label) VALUES ('ADMIN'), ('USER');

INSERT INTO dishes (label, type) VALUES ('Salad', 'STARTER'), ('Chicken', 'MAIN'), ('Chocolate Cake', 'DESSERT');

INSERT INTO menus (menu_date, price) VALUES ('2026-10-15', 15.00);

INSERT INTO menu_items (id_menu, id_dish)
SELECT m.id_menu, d.id_dish
FROM menus m CROSS JOIN dishes d
WHERE m.menu_date = '2026-10-15'
  AND d.label IN ('Salad', 'Chicken', 'Chocolate Cake');
