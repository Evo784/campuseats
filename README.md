# CampusEats

Commande de repas en ligne pour la cafétéria du campus (TP IT6, Campus Saint-Michel).

Un étudiant consulte le menu du jour, commande un ou plusieurs menus complets et choisit son moyen de paiement. La cafétéria marque les commandes comme livrées et consulte des statistiques et des prévisions de ventes.

## Architecture

```
Navigateur  →  Symfony (site web)  →  Django (API REST)  →  PostgreSQL
                   │                       │
                   └ petite base           └ seul à accéder à la base principale
                     (comptes, panier)       (ORM, stats pandas, admin Django)
```

| Dossier | Rôle | État |
|---|---|---|
| `api-django/` | API REST (Django + DRF), modèles, authentification, stats et prévisions (pandas) | fait |
| `web-symfony/` | Site web qui appelle l'API Django | à faire |
| `docker-compose.yml` | PostgreSQL 16 | fait |
| `docs/schema-nathan.sql` | Schéma SQL initial, gardé comme référence seulement | référence |

Les tables sont créées par les **migrations Django** (ORM), pas par le script SQL.

## Démarrage

Prérequis : Docker, Python 3.12+.

```powershell
copy .env.example .env          # puis adapter POSTGRES_PASSWORD
docker compose up -d            # PostgreSQL sur 127.0.0.1:5432

cd api-django
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python manage.py migrate   # crée les tables et les rôles ADMIN / USER
venv\Scripts\python manage.py seed      # comptes de test + menu d'exemple (dev seulement)
venv\Scripts\python manage.py runserver # http://127.0.0.1:8000
```

Repartir de zéro (efface toutes les données) : `docker compose down -v`, puis `docker compose up -d`, `migrate`, `seed`.

### Comptes de test (dev uniquement)

| Email | Mot de passe | Rôle |
|---|---|---|
| `etudiant@campus.fr` | `Etudiant123!` | USER |
| `admin@campus.fr` | `Admin123!` | ADMIN |

Le seed crée aussi le menu du 2026-10-15 (15 € : Salad, Chicken, Chocolate Cake). Ces comptes ne doivent jamais exister en production.

### Variables d'environnement

| Variable | Défaut | Rôle |
|---|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `campuseats` / `campuseats_dev` / `campuseats` | Connexion à la base (fichier `.env`) |
| `POSTGRES_HOST` / `POSTGRES_PORT` | `127.0.0.1` / `5432` | Adresse de la base |
| `DJANGO_SECRET_KEY` | clé de dev | Signe les JWT. **À changer en production.** |
| `DJANGO_DEBUG` | `1` | Mettre `0` en production |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Hôtes autorisés, séparés par des virgules |
| `JWT_EXPIRES_IN` | `1800` | Durée de vie du token en secondes |

## Authentification

- Les mots de passe sont hashés en **Argon2id** (`$argon2id$v=19$m=65536,t=3,p=4$…`), format lisible aussi par PHP (`password_verify`).
- `POST /v1/login` renvoie un **JWT (HS256)** valable 30 minutes.
- Les routes protégées demandent le header `Authorization: Bearer <token>`.
- Deux rôles : `USER` (étudiant) et `ADMIN` (cafétéria).

## API

Base : `http://127.0.0.1:8000/v1`. Les dates sont au format `YYYY-MM-DD`. Les erreurs renvoient `400` (données invalides), `401` (non connecté ou token expiré), `403` (rôle insuffisant), `404`, `409` (email déjà pris).

| Méthode | Route | Accès | Description |
|---|---|---|---|
| POST | `/users` | public | Crée un compte USER |
| POST | `/login` | public | Renvoie `{token, expires_in}` |
| GET | `/menus?date=` | public | Menu du jour (ou de la date donnée) |
| GET | `/menus/{id}` | public | Menu par identifiant |
| POST | `/orders` | connecté | Crée une commande |
| GET | `/orders/{id}` | propriétaire ou admin | Détail d'une commande |
| PATCH | `/orders/{id}` | admin | Marque la commande livrée |
| GET | `/dishes/stats?startDate=&endDate=` | connecté | Quantités commandées par plat |
| GET | `/orders/stats?startDate=&endDate=` | admin | Statistiques des commandes |
| GET | `/orders/forecast?startDate=&endDate=` | admin | Prévisions jour par jour |

### Exemples

Créer un compte :

```http
POST /v1/users
{"email": "nouveau@campus.fr", "password": "MotDePasse1!"}
→ 201 {"id_user": 3, "email": "nouveau@campus.fr", "role": "USER"}
```

Se connecter :

```http
POST /v1/login
{"email": "etudiant@campus.fr", "password": "Etudiant123!"}
→ 200 {"token": "eyJhbGciOi...", "expires_in": 1800}
```

Commander (`payment_method` : `CARD`, `CASH`, `VISA`, `MASTERCARD`, `OTHER`, voir `Order.PAYMENT_METHODS` dans `api/models.py`) :

```http
POST /v1/orders        Authorization: Bearer <token>
{"id_menu": 1, "quantity": 2, "payment_method": "VISA"}
→ 201 {
  "id_order": 1, "id_user": 1, "id_menu": 1,
  "dishes": [{"label": "Salad", "type": "STARTER"},
             {"label": "Chicken", "type": "MAIN"},
             {"label": "Chocolate Cake", "type": "DESSERT"}],
  "order_date": "2026-10-15T12:30:00Z", "quantity": 2,
  "payment_method": "VISA", "is_delivered": false, "total_price": 30.0
}
```

Marquer comme livrée (admin) : `PATCH /v1/orders/1` avec `{"is_delivered": true}`.

### Règles métier

- Un seul menu par jour (une entrée, un plat, un dessert). Une commande porte sur le menu entier, avec une quantité.
- `total_price` = prix du menu × quantité.
- L'identifiant de l'utilisateur vient du JWT, jamais du corps de la requête.
- Le moyen de paiement est obligatoire à la création (une seule requête, pas d'étape de paiement séparée).

### Statistiques et prévisions

Calculées avec pandas (`api-django/api/analytics.py`).

- **`/dishes/stats`** : pour chaque plat, la quantité commandée sur la période.
- **`/orders/stats`** : nombre de commandes et de menus, chiffre d'affaires, panier moyen, commandes livrées et en attente, répartition par moyen de paiement.
- **`/orders/forecast`** : pour chaque jour de la période (93 jours maximum), moyenne des jours de menu de même jour de semaine sur les 28 derniers jours. Un jour avec menu mais sans commande compte pour 0. Chiffre d'affaires prévu = quantité prévue × prix moyen du menu. C'est une estimation simple : elle est fiable seulement avec assez d'historique.

## Base de données

| Table | Contenu |
|---|---|
| `roles` | ADMIN, USER |
| `users` | email unique, mot de passe Argon2id, rôle |
| `dishes` | libellé, type (STARTER, MAIN, DESSERT) |
| `menus` | un menu par date, avec son prix |
| `menu_items` | plats d'un menu (clé primaire composée menu + plat) |
| `orders` | utilisateur, menu, date, moyen de paiement, livrée, quantité |

Les contraintes (CHECK sur les types, quantité > 0, email valide) sont déclarées dans les modèles et appliquées par la base.

L'interface d'administration Django (`/admin`) est disponible après `python manage.py createsuperuser`. Ce compte est distinct de la table `users` de l'API.

## Structure

```
api-django/
  config/            réglages et routes racine
  api/
    models.py        tables
    auth.py          Argon2id + JWT
    serializers.py   format des réponses
    views.py         routes
    analytics.py     stats et prévisions (pandas)
    migrations/      création des tables et des rôles
    management/commands/seed.py   données de test
```

## Reste à faire

- Site Symfony (`web-symfony/`).
- Tests automatisés de l'API (`manage.py test`).
- Configuration de production (`DJANGO_DEBUG=0`, vraie `DJANGO_SECRET_KEY`, hôtes autorisés).
