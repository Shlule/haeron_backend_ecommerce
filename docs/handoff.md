# Handoff — revue de la branche `dev`

Revue de lecture faite le 2026-07-21 sur `dev` (dernier commit `ec26a90`).
Rien n'a été exécuté : pas de `.env`, pas de base Postgres, `uv` absent de la machine.
**Tous les points ci-dessous viennent de la lecture du code, aucun n'est confirmé à l'exécution.**
Les numéros de ligne sont ceux de `ec26a90`.

---

## 1. Ce que fait le projet

Backend Django 5.2 + Strawberry GraphQL pour la vente de guitares custom. ~8,5k lignes.
Deux apps :

- **`authUser`** — auth, signup, reset password, rôles, MFA TOTP au-dessus de django-allauth
- **`haeron_guitar_api`** — le domaine métier

Le domaine se lit sur trois couches :

1. **Traçabilité physique** — `Part`, `PartBatch`, `Instrument`, compteurs de série par usine/date,
   et `PartNFCIdentity` avec dérivation de clé par tag via Vault (HKDF : clé domaine + clé batch + UID NFC).
2. **Configurateur produit** — `ProductSchema` → `ProductComponent` → handlers
   (`custom_piece`, `fixed`, `product_choice`, `product_configurable`), registry + récursion.
   Plus le rule engine (`ConfigurationRule` / `Condition` / `Result` / `SelectableValue`).
3. **Commerce** — `Cart` / `CartItem` (avec `config_snapshot` + `config_hash`),
   checkout → `Order` / `OrderItem`, webhook Stripe.

### Ce qui est solide

- Découpage `dto` / `input` / `service` / `resolver` / `filter` par entité, tenu partout.
  La logique est dans les services, les resolvers sont fins.
- 96 tests, concentrés sur les parties dures : chaque handler, le rule engine, le builder,
  HKDF, le client et le service Vault, cart / cartItem.
- Argon2, longueur mini 10, rate limit allauth sur login raté, vérification email obligatoire.
- `OrderItem` fige nom / prix / config au lieu de pointer sur `Product` — correct, les prix bougent.
- Clé d'idempotence sur `Order` pour encaisser les retries du front.
- `docs/` explique réellement le design (rule engine, handlers, checkout). Rare et utile.

---

## 2. Bugs

Classés par gravité. Chacun est une lecture de code, à confirmer en lançant le projet.

### 2.1 — `VaultService._SCOPES` n'existe pas

`src/haeron_guitar_api/security/vault/vault_service.py:17` et `:20` lisent `self._SCOPES`.
L'attribut n'est défini nulle part dans le repo (`grep -rn "_SCOPES" src/` ne remonte que ces deux lignes).

`get_vault_path()` lève donc `AttributeError`, et avec lui `post_secret()`.
Toute la provision de clés est morte tant que ce dict n'est pas écrit.

À noter : `security/vault/batch_key/batch_key_service.py` fait 0 octet, alors que le commit
`8f3fb15` s'appelle « Adding partbatch service ». Il y a probablement du travail non commité
qui contenait aussi `_SCOPES`.

### 2.2 — Le checkout est appelé avec les mauvais arguments

Signature : `checkout_service.py:12`

```python
def checkout(idempotency_key, user=None, session_key=None):
```

Appel : `checkout_resolver.py:10`

```python
return CheckoutService.checkout(
    user=info.context.request.user,
    session_key=info.context.request.session.session_key,
)
```

`idempotency_key` est obligatoire et n'est pas passé → `TypeError` à chaque appel.
Effet de bord : la protection anti-double-commande ne sert à rien puisqu'on n'arrive jamais
jusqu'à elle. La clé doit venir du front (c'est ce que dit le commentaire du modèle `Order`),
donc il faut l'ajouter à l'input de la mutation.

Deux détails sur la même méthode :

- `checkout()` n'est ni `@staticmethod` ni pourvue de `self`. Ça marche parce qu'elle est
  appelée sur la classe, mais c'est fragile : au premier `CheckoutService().checkout(...)`
  l'instance passe en `idempotency_key`. Mettre `@staticmethod` explicitement.
- La désactivation du panier après commande est commentée
  (`checkout_service.py`, `# cart.is_active = False`). Volontaire ou oubli ?

### 2.3 — Quatre resolvers ne sont jamais branchés au schéma

`src/haeron_backend/schema.py` agrège 13 resolvers. Absents :

- `cart/cart_resolver.py`
- `cartItem/cartItem_resolver.py`
- `checkout/checkout_resolver.py`
- `product_configurator/product_schema/product_schema_resolver.py`

Donc toute la moitié e-commerce de l'API est injoignable en GraphQL aujourd'hui.
C'est probablement pour ça que 2.2 n'a jamais pété : le resolver n'est pas exposé.

### 2.4 — `token_blacklist` n'est pas installé

`settings.py:112-113` active :

```python
"ROTATE_REFRESH_TOKENS": True,
"BLACKLIST_AFTER_ROTATION": True,
```

et `authUser/services/tokens.py:2` importe `OutstandingToken` / `BlacklistedToken`.

Mais `INSTALLED_APPS` ne contient que `rest_framework_simplejwt` (`settings.py:49`),
pas `rest_framework_simplejwt.token_blacklist`. Sans cette app, pas de tables, pas de migrations :
`revoke_user_refresh_tokens()` et `revoke_refresh_token()` cassent, et le blacklisting
à la rotation ne se fait pas. Un refresh token volé reste valable 7 jours.

### 2.5 — `CorsMiddleware` est au mauvais endroit

`settings.py:82` le place en dernier, après `CommonMiddleware` (`:76`).
django-cors-headers demande qu'il soit **le plus haut possible et avant `CommonMiddleware`**,
sinon les en-têtes CORS ne sont pas posés sur toutes les réponses.

### 2.6 — Le cache par défaut ne tient pas la charge

Pas de bloc `CACHES` dans `settings.py` → Django tombe sur `LocMemCache`, qui est **par process**.

Or c'est là que vivent :

- les challenges MFA (`mfa_challenge.py`, clé `mfa:{uuid}`, TTL 300s)
- les secrets TOTP en attente de confirmation (`mfa.py`, clé `totp_pending:{user.id}`, TTL 600s)

Dès qu'uvicorn tourne avec plus d'un worker, le login MFA échoue de façon aléatoire :
le challenge créé par le worker A est invisible depuis le worker B. Il faut Redis
(ou au minimum le cache base de données) avant toute mise en ligne.

### 2.7 — Le webhook Stripe cherche sur la mauvaise clé

`payments/stripe_webhook.py:38` :

```python
Order.objects.filter(id=order_id).update(status="paid")
```

`Order` a un champ `uuid` (unique, non-PK) et donc aussi un `id` auto-incrémenté implicite.
Tout le reste du code identifie les commandes par `uuid`. Si la metadata Stripe contient
l'uuid, ce filtre ne matche rien — et comme `.update()` ne lève pas, **le paiement est
silencieusement perdu**. À vérifier en priorité, c'est le seul bug de la liste qui coûte de l'argent.

Sur le même fichier : le `except Exception` du `construct_event` avale tout dans un `print`,
et il reste deux `print` de debug. Il faudrait du `logging` et une remontée d'erreur.

---

## 3. Points secondaires

- `settings.py:29` `DEBUG = True` et `:31` `ALLOWED_HOSTS = []` en dur.
  `:33` `VAULT_ADDR` en dur sur localhost. Le reste du fichier utilise `config()`, autant s'y tenir.
- `https://hoppscotch.io` est dans `CORS_ALLOWED_ORIGINS` (`:92`) et `CSRF_TRUSTED_ORIGINS` (`:98`).
  Pratique en dev, à ne pas laisser passer en prod.
- `permissions/authenticateJwt.py:10-11` imprime l'objet user à chaque vérification de permission.
- Deux conventions de contexte cohabitent : `info.context["user"]` dans les permissions,
  `info.context.request.user` dans le checkout resolver. Le `get_context` de `urls.py` renvoie
  un dict `{"request", "user"}`, et l'auth JWT y est faite à la main — donc
  `info.context.request.user` est `AnonymousUser` même quand le JWT est valide.
  Le checkout lit vraisemblablement le mauvais user. À uniformiser sur une seule forme.
- Pas de classe de permission sur la mutation `checkout` — aucune vérification d'authentification.
- `authUser.MFADevice` est du code mort : c'est l'`Authenticator` d'allauth qui est utilisé partout.
- `User.email_verified` fait doublon avec `EmailAddress.verified` d'allauth, et c'est ce dernier
  que `auth.py` interroge réellement. Deux sources de vérité pour le même fait.
- `haeron_guitar_api/schema.py` est encore le stub de `startapp` (type `Book`).
- `old_migrations/` est commité à côté de `migrations/`.
- Le TODO du README signale déjà l'absence de limite de profondeur / complexité / rate limit
  sur GraphQL. À faire avant toute exposition publique : un client non authentifié peut
  actuellement envoyer des requêtes arbitrairement profondes.

---

## 4. Ce qui manque autour du code

| Manque | Conséquence |
|---|---|
| Pas de `.github/`, aucune CI | 96 tests existent, personne ne sait s'ils passent |
| Pas de `.env.example` | Impossible de démarrer le projet sans grepper le code |
| Pas de section setup dans le README | Idem |
| Pas de config lint / format | Imports morts et `print` de debug qui s'accumulent |
| `authUser/tests/graphql_client.py` fait 0 octet | **Aucun test ne traverse la couche GraphQL** |

La dernière ligne explique les trois autres. Les 96 tests sont tous unitaires, contre les
services. Les bugs 2.2, 2.3 et 2.7 vivent tous dans le câblage entre le resolver et le service —
exactement la zone que rien n'exerce. Un seul test qui envoie une vraie mutation GraphQL
de bout en bout les aurait tous les trois attrapés.

Les variables d'environnement attendues, relevées par `grep -rn 'config("' src/` :

```
SECRET_KEY
DB_NAME  DB_USER  DB_PASSWORD  DB_HOST  DB_PORT
VAULT_TOKEN
STRIPE_SECRET_KEY
STRIPE_WEBHOOK_SECRET
```

---

## 5. Ordre suggéré

1. **2.7** (webhook Stripe) — seul bug qui perd de l'argent.
2. **2.3 + 2.2** (câblage schéma + signature checkout) — débloque la moitié de l'API.
3. **2.1** (`_SCOPES`) — débloque Vault. Vérifier d'abord s'il n'y a pas du local non poussé.
4. **2.4 + 2.6** (blacklist + Redis) — sécurité auth, à faire avant toute mise en ligne.
5. **CI + `.env.example`** — transforme « 96 tests » en un chiffre observable.
6. **Harness de test GraphQL** — remplir `graphql_client.py`, couvrir login → MFA → panier → checkout.
7. **2.5** et la section 3 — au fil de l'eau.

---

## 6. Questions ouvertes

Points où je n'ai pas su trancher à la lecture seule :

- `batch_key_service.py` vide + `_SCOPES` manquant : il y a du travail local non poussé ?
- La désactivation du panier après checkout est commentée volontairement ?
- La metadata `order_id` envoyée à Stripe contient l'`id` entier ou l'`uuid` ?
- `MFADevice` et `User.email_verified` : reliquats à supprimer, ou prévu pour remplacer allauth ?
- Le split en deux apps Django évoqué dans le TODO du README est toujours d'actualité ?
