# Global Translations

Multi-language support for agent content, allowing administrators to manage translations and end-users to interact with agents in their preferred language.

Default supported languages: English, Spanish, French, German, Portuguese, Chinese. Additional languages can be added via the API.

## API Endpoints

All translation endpoints are under `/api/v1/translations` and require AppSettings permissions.

### Language Management

| Method | URL | Body | Response | Permission |
|---|---|---|---|---|
| `GET` | `/api/v1/translations/languages` | – | `200` list of languages | `AppSettings.READ` |
| `POST` | `/api/v1/translations/languages` | `{ code, name }` | `201` created language | `AppSettings.CREATE` |

### Translation CRUD

| Method | URL | Body | Response | Permission |
|---|---|---|---|---|
| `GET` | `/api/v1/translations` | – | `200` list of translations | `AppSettings.READ` |
| `GET` | `/api/v1/translations/{key}` | – | `200` single translation, `404` | `AppSettings.READ` |
| `POST` | `/api/v1/translations` | `{ key, default?, translations }` | `201` created, `400` if key exists | `AppSettings.CREATE` |
| `PATCH` | `/api/v1/translations/{key}` | `{ default?, translations? }` | `200` updated, `404` | `AppSettings.UPDATE` |
| `DELETE` | `/api/v1/translations/{key}` | – | `204`, `404` | `AppSettings.DELETE` |

The `translations` field is a `dict[str, str]` mapping language codes to values (e.g. `{ "en": "Hello", "es": "Hola" }`).

### Conversation Endpoints

| Method | URL | Headers | Response | Permission |
|---|---|---|---|---|
| `GET` | `/api/v1/conversations/in-progress/agent-info` | – | `200` `{ agent_id, agent_available_languages }` | `Conversation.CREATE_IN_PROGRESS` |
| `POST` | `/api/v1/conversations/in-progress/start` | `Accept-Language` | `200` (see below) | `Conversation.CREATE_IN_PROGRESS` |

**`POST /api/v1/conversations/in-progress/start`** response includes:
```json
{
  "conversation_id": "uuid",
  "agent_id": "uuid",
  "agent_welcome_message": "string|null",
  "agent_welcome_title": "string|null",
  "agent_possible_queries": ["string"],
  "agent_thinking_phrases": ["string"],
  "agent_thinking_phrase_delay": "number|null",
  "agent_input_disclaimer_html": "string|null",
  "agent_available_languages": ["en", "es"],
  "agent_has_welcome_image": "boolean",
  "agent_chat_input_metadata": "object|null",
  "guest_token": "string (if token_based_auth enabled)"
}
```

All text fields (`welcome_message`, `welcome_title`, `possible_queries`, `thinking_phrases`, `input_disclaimer_html`) are resolved against the `Accept-Language` header.

## Translation Key Convention

Keys follow the pattern `agent.{agent_id}.{field_name}`:

| Field | Key Pattern |
|---|---|
| Welcome Title | `agent.{id}.welcome_title` |
| Welcome Message | `agent.{id}.welcome_message` |
| Input Disclaimer | `agent.{id}.input_disclaimer_html` |
| Possible Queries | `agent.{id}.possible_queries.{index}` |
| Thinking Phrases | `agent.{id}.thinking_phrases.{index}` |

## Translation Resolution

Fallback chain: **language-specific value → default value → null**

The system parses the `Accept-Language` header (e.g. `"en-US"` → `"en"`) and resolves translations accordingly. Batch resolution is used during conversation start to resolve all agent fields in one pass.

## Frontend

### Translations Management Page

**Route:** `/settings/translations` (requires `read:app_setting` permission)

- Data table listing all translations with key, default value, language badges, and edit/delete actions.
- Full-text search across keys and values.
- Create/edit dialog with row-based UI per language, language selector, and a radio to mark the default fallback.

### Agent Form Integration

In edit mode, each translatable agent field shows a translation trigger button with a count badge. Clicking opens the translation dialog scoped to the appropriate `agent.{id}.{field}` key.

### Disclaimer Editor

A lightweight rich text editor (bold, font-size, link) for the `input_disclaimer_html` agent field — an HTML disclaimer shown below the chat input.

## React Chat Plugin

- **Language Selector** – displays available languages from the agent, persists selection.
- **Accept-Language header** – sent on all API calls based on the selected language.
- **Browser language detection** – fallback when no explicit selection.
- **i18n** – supports 6 built-in languages (en, es, fr, de, it, pt) with custom override support via the `translations` prop.
- **Props:** `language` (code), `translations` (custom overrides).
