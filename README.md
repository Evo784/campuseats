# CampusEats

Commande de repas en ligne pour la cafétéria du campus.

- `api-django/` : API REST (Django REST Framework), modèles, stats pandas, prévisions
- `web-symfony/` : site web (Twig), panier, paiement simulé, back-office
- `db/init/` : scripts SQL exécutés au premier démarrage de Postgres

## Démarrage

```
cp .env.example .env     # puis adapter le mot de passe
docker compose up -d
```

Postgres écoute sur `127.0.0.1:5432`.

Pour rejouer les scripts de `db/init/` : `docker compose down -v` puis `docker compose up -d` (efface les données).
