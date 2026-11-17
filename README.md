# Tickets de maintenance ERP

API de suivi centralisé des interventions de maintenance pour un groupe d'**établissements
recevant du public** (ERP) : création de tickets, assignation à un technicien ou à un prestataire,
workflow de statuts, photos avant/après, notifications e-mail + Discord, tableau de bord et
historique complet par établissement.

**Stack :** Python 3.12+, FastAPI, SQLAlchemy 2 (typé), Pydantic v2, Alembic, Argon2id, JWT.

---

## Démarrage rapide

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env    # puis renseigner APP_SECRET_KEY
```

```bash
alembic upgrade head
```

Création du premier administrateur (le mot de passe n'est jamais passé en argument) :

```bash
python -m app.cli create-admin --email admin@example.org --full-name "Responsable maintenance"
```

```bash
uvicorn app.main:create_app --factory --reload
```

Documentation interactive : <http://localhost:8000/docs> (Swagger) et `/redoc`. Le bouton
**Authorize** de Swagger utilise directement le flux OAuth2 *password* de `/api/v1/auth/login`.

Avec Docker (PostgreSQL recommandé en production) :

```bash
docker build -t erp-maintenance .
```

```bash
docker run -p 8000:8000 -e APP_SECRET_KEY=... -e APP_DATABASE_URL=postgresql+psycopg://... erp-maintenance
```

## Qualité (Definition of Done)

```bash
ruff check . && ruff format --check .
```

```bash
mypy
```

```bash
pytest --cov
```

```bash
APP_DATABASE_URL=sqlite:///./check.db alembic upgrade head && APP_DATABASE_URL=sqlite:///./check.db alembic check
```

Ces mêmes étapes tournent dans la CI GitHub Actions (`.github/workflows/ci.yml`), avec un seuil de
couverture à 90 %. `mypy` est en mode `strict` sur `app/` **et** `tests/`.

| Critère DoD | Où le vérifier |
|---|---|
| Linting + type checking | `ruff`, `mypy --strict` |
| Cycle de vie d'un ticket | `tests/integration/test_ticket_lifecycle.py`, `tests/unit/test_workflow.py` |
| Permissions RBAC | `tests/integration/test_rbac.py`, `tests/unit/test_rbac.py` (matrice complète rôle × permission) |
| Ticket créé, assigné, notification envoyée | `test_create_assign_and_notify` + endpoint `POST /api/v1/notifications/test` |
| Documentation API | `/docs`, `/redoc`, `/openapi.json` (couvert par `test_openapi_documents_all_features`) |

## Architecture

```
app/
├── api/            # Couche HTTP : routes FastAPI, injection de dépendances, mapping des erreurs
├── services/       # Cas d'usage (logique métier, transactions, déclenchement des notifications)
├── domain/         # Règles pures : RBAC (rbac.py) et machine à états des tickets (workflow.py)
├── repositories/   # Repository pattern + Unit of Work (seul endroit qui parle SQL)
├── models/         # Modèles SQLAlchemy 2 typés (Mapped[...])
├── schemas/        # Schémas Pydantic d'entrée/sortie (extra="forbid" sur toutes les entrées)
├── notifications/  # Canaux (e-mail SMTP, webhook Discord, log, mémoire) + dispatcher
├── storage/        # Stockage des fichiers (interface FileStorage) + assainissement des images
└── core/           # Configuration, sécurité (hash, JWT), rate limiting, middlewares
migrations/         # Alembic
tests/{unit,integration}
```

Flux d'une requête : `route → dépendances (auth + AccessPolicy) → service → repositories (UnitOfWork)
→ commit → notifications planifiées en tâche de fond`.

**Extensibilité (stocks, signatures numériques…)** : un nouveau module ajoute ses modèles, un
repository déclaré dans `UnitOfWork` (même transaction que les tickets), un service, des permissions
dans `domain/rbac.py` et un routeur. Il peut écrire dans le journal d'audit via
`TicketService.record_event`. Les interfaces `FileStorage`, `Notifier` et `RateLimiter` sont des
`Protocol` : S3, SMS/Teams ou Redis s'y branchent sans toucher au métier.

## Fonctionnalités (MVP)

### Tickets
- **Création** : titre, description, priorité (`low`, `medium`, `high`, `critical`) et localisation
  précise (`building`, `floor`, `room`, `details`) rattachée à un établissement.
- **Assignation** (`PUT /tickets/{id}/assignment`) : soit `technician_id` (technicien actif,
  rattaché au site), soit `provider_id` (prestataire externe actif). `{}` désassigne.
- **Statuts** (`POST /tickets/{id}/status`) :

  | De \ Vers | todo | in_progress | blocked | done |
  |---|---|---|---|---|
  | **todo** | – | ✔ (assigné) | ✔ (motif) | ✘ |
  | **in_progress** | ✔ | – | ✔ (motif) | ✔ |
  | **blocked** | ✔ | ✔ | – | ✘ |
  | **done** | ✘ | ✔ réouverture *admin* | ✘ | – |

  Le passage en `blocked` exige un commentaire ; `in_progress`/`done` exigent un assigné.
- **Archivage** (`POST /tickets/{id}/archive`, tickets terminés) : le ticket devient en lecture
  seule et sort des listes par défaut (`?include_archived=true` pour l'inclure).
- **Verrouillage optimiste** : deux modifications concurrentes du même ticket → `409`.

### Photos avant / après
`POST /tickets/{id}/photos` (multipart : `kind=before|after`, `file`). Seuls JPEG et PNG sont
acceptés, **détectés par signature binaire** (le `Content-Type` déclaré est ignoré). Les
métadonnées (EXIF/GPS, XMP, commentaires, chunks texte PNG) sont **supprimées** avant stockage.
Taille max configurable (`413` au-delà), 30 photos par ticket, noms de fichiers générés côté
serveur, téléchargement uniquement via l'API avec contrôle d'accès.

### Notifications
Déclenchées sur **assignation** et **changement de statut**, envoyées en tâche de fond (la réponse
HTTP n'attend pas SMTP/Discord) ; une panne d'un canal n'affecte pas les autres.

| Canal | Destinataires | Contenu |
|---|---|---|
| E-mail (SMTP + STARTTLS) | assigné (technicien ou prestataire) ; créateur + assigné pour les statuts | détail du ticket, en `Bcc` |
| Discord (webhook) | canal d'équipe | **aucune donnée personnelle** ; mentions `@everyone` neutralisées |
| Log | – | repli automatique si aucun canal n'est configuré |

`POST /api/v1/notifications/test` (admin) envoie un message de test sur tous les canaux et renvoie
le résultat par canal.

### Multi-sites, reporting et historique
- Établissements avec type et catégorie ERP (1 à 5), rattachement des utilisateurs aux sites.
- `GET /reports/dashboard` : par site visible, total, ouverts, répartition par statut, tickets
  ouverts par priorité, archivés, délai moyen de résolution. `GET /reports/sites/{id}` pour un site.
- `GET /tickets/{id}/history` et `GET /sites/{id}/history` : journal d'audit **append-only**
  (création, modifications, assignations, statuts avec commentaire, photos, archivage), tickets
  archivés compris. Aucune API ne permet de modifier ou supprimer un événement.

## Sécurité

### RBAC
Deux niveaux, vérifiés à chaque requête (garde au niveau route **et** re-vérification dans le
service) :

1. **Permissions par rôle** (`app/domain/rbac.py`)

   | Action | admin | technician | client |
   |---|:-:|:-:|:-:|
   | Créer / consulter un ticket, photos, rapports, historique | ✔ | ✔ | ✔ |
   | Modifier un ticket, ajouter des photos | ✔ | ✔ | |
   | Changer le statut | ✔ | ✔ *si assigné* | |
   | Assigner, archiver, rouvrir | ✔ | | |
   | Consulter les prestataires | ✔ | ✔ | |
   | Gérer sites, utilisateurs, prestataires, test notif. | ✔ | | |

2. **Cloisonnement par établissement** : hors admin, un utilisateur ne voit que les sites dont il
   est membre. Une ressource hors périmètre répond **404** (et non 403) pour ne pas révéler son
   existence. Les appelants non autorisés reçoivent 403 *avant* toute validation du corps.

### Sessions
- Mots de passe hachés en **Argon2id** (re-hachage transparent si les paramètres évoluent),
  politique : 12 caractères min., 3 classes de caractères, ne contient pas l'e-mail.
- **Access token JWT** court (15 min), algorithme imposé côté serveur, `iss`/`aud`/`exp`/`nbf`/`jti`
  obligatoires ; l'utilisateur est rechargé à chaque requête (compte désactivé = accès coupé).
- **Refresh token** opaque, stocké uniquement haché (SHA-256), **rotation** à chaque usage et
  **détection de rejeu** : réutiliser un ancien refresh token révoque toute la famille de session.
- `POST /auth/logout`, `POST /auth/logout-all` ; changement de mot de passe, changement de rôle ou
  désactivation invalident **tous** les tokens (compteur `token_version`).
- Anti brute-force : limitation par (IP, e-mail) et par e-mail → `429` + `Retry-After` ; messages
  d'erreur identiques et temps constant que l'utilisateur existe ou non.

### Durcissement HTTP
En-têtes `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`,
CSP `default-src 'none'` et `Cache-Control: no-store` sur l'API, HSTS en production. CORS fermé par
défaut (`*` interdit en production). Swagger désactivable (`APP_DOCS_ENABLED=false`). Toutes les
entrées Pydantic refusent les champs inconnus (protection contre l'assignation de masse, ex.
`"role": "admin"`). URL de webhook Discord validée (anti-SSRF), en-têtes e-mail assainis.

## Conformité RGPD

| Principe | Mise en œuvre |
|---|---|
| Minimisation | Utilisateur : e-mail, nom, téléphone optionnel. Pas de nom de fichier d'origine ni de métadonnées photo. Discord ne reçoit aucune donnée personnelle ; les autres utilisateurs ne voient que le nom de l'assigné. |
| Droit d'accès / portabilité (art. 15, 20) | `GET /users/me/export` : profil, tickets créés, actions réalisées, sessions actives (JSON). |
| Droit à l'effacement (art. 17) | `DELETE /users/me` ou `POST /users/{id}/anonymize` (admin) : e-mail, nom, téléphone remplacés de façon irréversible, sessions révoquées, compte désactivé, plus aucune notification. |
| Limitation de conservation | Les registres de maintenance d'un ERP relèvent d'une obligation légale (registre de sécurité) : les tickets sont **conservés** mais liés à un identifiant opaque après anonymisation. Refresh tokens expirés après 7 jours. |
| Sécurité (art. 32) | Voir section Sécurité ; aucune donnée personnelle dans les logs applicatifs. |

À compléter côté organisation : registre des traitements, durée de conservation des photos,
mentions d'information, chiffrement du disque/base et sauvegardes.

## Configuration

Toutes les variables sont préfixées par `APP_` (voir `.env.example`). Principales :

| Variable | Défaut | Rôle |
|---|---|---|
| `APP_SECRET_KEY` | **obligatoire** (≥ 32 car.) | Signature des JWT |
| `APP_DATABASE_URL` | `sqlite:///./maintenance.db` | PostgreSQL recommandé en production (`pip install -e ".[postgres]"`) |
| `APP_ENVIRONMENT` | `development` | `production` active HSTS et des garde-fous de configuration |
| `APP_SMTP_HOST`, `APP_SMTP_*` | – | Active le canal e-mail |
| `APP_DISCORD_WEBHOOK_URL` | – | Active le canal Discord |
| `APP_MAX_UPLOAD_BYTES` | 10 Mo | Taille max d'une photo |
| `APP_LOGIN_MAX_ATTEMPTS` / `APP_LOGIN_WINDOW_SECONDS` | 5 / 300 | Anti brute-force |

## Limites connues / prochaines étapes

- Le rate limiter est en mémoire : pour plusieurs instances, fournir une implémentation Redis de
  `RateLimiter`. Derrière un reverse proxy, configurer `--forwarded-allow-ips` pour que l'IP client
  soit correcte.
- Notifications via `BackgroundTasks` (même processus) : pour garantir la livraison en cas de
  redémarrage, passer à une file (outbox + worker).
- Stockage local des photos : une implémentation S3 de `FileStorage` est conseillée en production.
- Le refresh token est renvoyé dans le corps JSON ; pour un front web, préférer un cookie
  `HttpOnly; Secure; SameSite=Strict`.
