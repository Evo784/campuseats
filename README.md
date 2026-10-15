# CampusEats

Commande de repas en ligne pour la cafétéria du campus.

- `api-django/` : API REST (Django REST Framework), modèles, stats pandas, prévisions
- `web-symfony/` : site web (Twig), panier, paiement simulé, back-office
- `docs/schema-nathan.sql` : schéma SQL initial, conservé comme référence (les tables sont créées par les migrations Django)

## Démarrage

```
copy .env.example .env     # puis adapter le mot de passe
docker compose up -d       # Postgres sur 127.0.0.1:5432

cd api-django
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python manage.py migrate    # crée les tables + les rôles ADMIN / USER
venv\Scripts\python manage.py seed       # comptes de test + menu d'exemple (dev seulement)
venv\Scripts\python manage.py runserver
```

Comptes de test (dev uniquement) : `etudiant@campus.fr` / `Etudiant123!` (USER), `admin@campus.fr` / `Admin123!` (ADMIN).

Créer un compte : `POST /v1/users` avec `{"email": "...", "password": "..."}` (8 caractères min, rôle USER, mot de passe hashé en Argon2id).
Mots de passe stockés en Argon2id.

Repartir de zéro : `docker compose down -v`, puis `docker compose up -d` et relancer `migrate` + `seed` (efface les données).
