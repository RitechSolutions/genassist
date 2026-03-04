## Translations API

The backend exposes a centralized translations store backed by the `translations` table:

- `id` (UUID, PK via shared `Base`)
- `key` (string, unique, required) – logical translation key
- `default`, `en`, `es`, `fr`, `de`, `pt`, `zh` – language-specific values (all optional)

### Endpoints

Base path: `/api/v1/translations` (all endpoints protected by AppSettings permissions).

- `GET /api/v1/translations`  
  - Lists all translations.  
  - Response: `List[TranslationRead]`.  
  - Permissions: `Permissions.AppSettings.READ`.

- `GET /api/v1/translations/{key}`  
  - Returns a single translation by `key`.  
  - 404 if not found.  
  - Permissions: `Permissions.AppSettings.READ`.

- `POST /api/v1/translations`  
  - Creates a new translation.  
  - Body: `TranslationCreate` (`key`, plus any of `default`, `en`, `es`, `fr`, `de`, `pt`, `zh`).  
  - 201 on success; 400 if a translation with the same `key` already exists.  
  - Permissions: `Permissions.AppSettings.CREATE`.

- `PATCH /api/v1/translations/{key}`  
  - Partially updates an existing translation identified by `key`.  
  - Body: `TranslationUpdate` (all fields optional).  
  - 404 if `key` does not exist.  
  - Permissions: `Permissions.AppSettings.UPDATE`.

- `DELETE /api/v1/translations/{key}`  
  - Deletes the translation identified by `key`.  
  - 204 on success; 404 if `key` does not exist.  
  - Permissions: `Permissions.AppSettings.DELETE`.

### Caching Behavior

Translations are cached in Redis using `fastapi-cache`:

- `TranslationsService.get_all()` is cached for 300 seconds using namespace `translations:get_all` and a tenant-aware key builder.
- `TranslationsService.get_by_key(key)` reads from the cached list returned by `get_all()` and looks up the matching `key`.
- On `create`, `update`, and `delete`, the service invalidates the `translations:get_all` cache so that subsequent reads see fresh data.

