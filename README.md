# haeron-backend-ecommerce

Backend Django + GraphQL pour la vente de guitares custom : configurateur de produit,
panier / commande, et traçabilité des pièces par tag NFC adossée à Vault.

## Stack

| | |
|---|---|
| Python | 3.12 (voir `.python-version`) |
| Framework | Django 5.2 |
| API | Strawberry GraphQL (`strawberry-graphql-django`) |
| Base | PostgreSQL |
| Auth | django-allauth + simplejwt, MFA TOTP, Argon2 |
| Secrets | HashiCorp Vault (`hvac`) |
| Paiement | Stripe |
| Paquets | uv |
| Tests | pytest + pytest-django + factory-boy |

## Prérequis

- Python 3.12
- [uv](https://docs.astral.sh/uv/) — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- PostgreSQL en local
- Vault (optionnel, uniquement pour les fonctionnalités de clés NFC) — `brew install vault`
- Stripe CLI (optionnel, pour tester le webhook) — `brew install stripe/stripe-cli/stripe`

## Installation

> **Note** — ces étapes ont été écrites à partir de `pyproject.toml` et
> `.python-version`, mais n'ont pas été exécutées de bout en bout. Si l'une
> d'elles coince, la corriger ici au passage.

```bash
# 1. dépendances
uv sync

# 2. base de données
createdb haeron

# 3. configuration
cp .env.example .env
$EDITOR .env          # voir les commentaires du fichier pour chaque variable

# 4. migrations
uv run python src/manage.py migrate

# 5. compte admin
uv run python src/manage.py createsuperuser
```

Le `.env` se met **à la racine du repo** : python-decouple remonte l'arborescence
depuis `src/haeron_backend/settings.py` jusqu'à le trouver.

## Lancer

```bash
uv run python src/manage.py runserver
```

| Route | |
|---|---|
| `/graphql/` | l'API (interface GraphiQL en dev) |
| `/admin/` | admin Django |
| `/api/token/resfresh/` | refresh du JWT |
| `/api/payments/stripe/webhook/` | webhook Stripe |

Les emails partent sur la console en dev (`EMAIL_BACKEND` = `console`) : les liens de
vérification d'adresse et de reset password s'affichent dans le terminal du serveur.

### Vault

Nécessaire seulement pour la partie clés NFC. Dans un autre terminal :

```bash
vault server -dev
```

Recopier le « Root Token » affiché dans `VAULT_TOKEN`. Le serveur écoute sur
`http://localhost:8200`, qui est l'adresse attendue par `settings.py`.

### Webhook Stripe

```bash
stripe listen --forward-to localhost:8000/api/payments/stripe/webhook/
```

Recopier le `whsec_...` affiché dans `STRIPE_WEBHOOK_SECRET`.

## Tests

```bash
uv run pytest                       # tout
uv run pytest src/authUser          # une app
uv run pytest --cov=src             # avec couverture
```

La configuration pytest est dans `pyproject.toml` (`DJANGO_SETTINGS_MODULE`,
`pythonpath`, `testpaths`). Les tests créent leur propre base, l'utilisateur
PostgreSQL doit donc avoir le droit `CREATEDB`.

## Organisation

```
src/
├── haeron_backend/        # settings, urls, schéma GraphQL racine
├── authUser/              # utilisateurs, auth, MFA
│   └── services/          # auth, signup, password, tokens, roles, mfa/
└── haeron_guitar_api/     # domaine métier
    ├── product_configurator/   # schémas produit, handlers, rule engine
    ├── security/vault/         # dérivation de clés NFC (HKDF + Vault)
    ├── payments/               # webhook Stripe
    └── <entité>/               # dto / input / service / resolver / filter
```

Chaque entité suit le même découpage : le `service` porte la logique, le `resolver`
reste fin, le `dto` et l'`input` font la frontière avec GraphQL.

## Documentation

- [`docs/handler.md`](docs/handler.md) — les ProductType et Component handlers
- [`docs/rule_engine.md`](docs/rule_engine.md) — le moteur de règles de configuration
- [`docs/checkout.md`](docs/checkout.md) — le passage panier → commande
- [`docs/handoff.md`](docs/handoff.md) — revue de la branche `dev` (2026-07-21)


## TODO - 
mettre ne place un systeme de securite pour l'authentification . du rate limit, complexity limit,
depth limit etc. regarde les limiter de bas de strawberry , tu as aussi graphene-protector qui peux aider 
ensuite si tu as la fois faire des limiter custom

mettre en place le systeme authorization. 

regarde comment fonctionne les app django . le but est de peu etre separer l'app d'authentificaiton des guitare et 
l'app du site de e commerce . le but etatn que si l'un crash l'autre soit toujours accessible . Idealement
ils doivent utiliser la meme base de donne 

Faire l'application d'quthenfication des guitare. commen cela est un autre application reflechir a la communication de la base 
et peut etre mettre en place un service rabbitmq pour la communication des servers .

