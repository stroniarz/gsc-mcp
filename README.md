# gsc-mcp

MCP server dla Google Search Console — multi-property, OAuth2 user-flow (Service Account jako fallback), FastMCP/stdio.

## Why another GSC MCP?

Popularna alternatywa: **[AminForou/mcp-gsc](https://github.com/AminForou/mcp-gsc)** (842⭐, na PyPI jako `mcp-search-console`). Świetny, comprehensive — 15+ tools obejmujących batch inspection, indexing issues, performance overview, advanced analytics z pre-formatted string responses.

To repo (`gsc-mcp`) jest **niezależną minimalną implementacją** zorientowaną inaczej:

- 5 essential tools (`gsc_list_sites`, `gsc_search_analytics`, `gsc_inspect_url`, `gsc_list_sitemaps`, `gsc_compare_periods`)
- Returns **structured dicts** (raw API data) zamiast pre-formatted stringów — agent (Claude Code, Codex CLI) sam formatuje dla swojego kontekstu
- Modern Python: package structure `src/gsc_mcp/{server,auth}.py`, type hints, sync `def`
- Explicit OAuth2 + Service Account split w osobnym `auth.py`
- **OAuth2 user-flow domyślnie** (Domain properties działają, w przeciwieństwie do Service Account który Google blokuje od kilku miesięcy)

Wybierz AminForou jeśli chcesz comprehensive batch tools. Wybierz to jeśli chcesz minimal + structured data + modern packaging.


MCP server dla Google Search Console — multi-property, OAuth2 user-flow (Service Account jako fallback), FastMCP/stdio.

## Tools

- `gsc_list_sites` — wszystkie properties dostępne dla zalogowanego konta
- `gsc_search_analytics` — query Search Analytics API (queries/pages/dates/devices/countries z filtrami)
- `gsc_inspect_url` — URL Inspection API (status indeksu, schema, rich results)
- `gsc_list_sitemaps` — submitted sitemaps + status
- `gsc_compare_periods` — diff dwóch okresów (post-deploy SEO check)

## Auth — dwa tryby

### OAuth2 user-flow (default, **rekomendowane** dla Domain properties)

Jednorazowy login w przeglądarce → refresh token persistuje miesiącami → MCP widzi **wszystkie** properties do których Ty masz dostęp w GSC. Działa też dla Domain properties (które blokują Service Accounts).

### Service Account (fallback, dla URL-prefix properties)

Per-property `Add user` w GSC. Działa tylko dla URL-prefix properties (Domain properties odrzucają SA emaile). `GSC_MCP_AUTH=sa`.

## Setup OAuth2 (default)

### W GCP (jednorazowo, ~5 min)

1. [Google Cloud Console](https://console.cloud.google.com) → projekt
2. **APIs & Services → Library → Search Console API → Enable**
3. **APIs & Services → OAuth consent screen** (jeśli nie skonfigurowany):
   - User Type: **External**
   - App name: `gsc-mcp` (cokolwiek)
   - User support email + Developer contact: Twój email
   - Scopes: pomiń (Test users wystarczą)
   - **Test users**: dodaj swój email (Twoje konto z GSC)
   - Save
4. **APIs & Services → Credentials → + Create Credentials → OAuth client ID**:
   - Application type: **Desktop app**
   - Name: `gsc-mcp-desktop`
   - Create → ściągnij JSON

### Lokalnie

```sh
mkdir -p ~/.config/gsc-mcp
mv ~/Downloads/client_secret_*.json ~/.config/gsc-mcp/oauth-client.json
chmod 600 ~/.config/gsc-mcp/oauth-client.json
```

Pierwszy run otworzy przeglądarkę → wybierz konto → "Allow" → token się zapisze do `~/.config/gsc-mcp/oauth-tokens.json` (chmod 600 auto). Kolejne runy używają refresh tokenu.

## Setup Service Account (fallback dla URL-prefix properties)

Patrz [Service Account section](#service-account-shortcut) na dole.

## Instalacja

```sh
cd ~/Projects/github/stroniarz-tools/gsc-mcp
uv venv && source .venv/bin/activate
uv pip install -e .
```

Albo przez root `install.sh`.

## Wpis w Claude Code

`~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "gsc": {
      "command": "/Users/<you>/Projects/github/stroniarz-tools/gsc-mcp/.venv/bin/gsc-mcp"
    }
  }
}
```

Po restarcie CC tools `gsc_*` widoczne.

## Test

```sh
gsc-mcp  # standalone, czeka na MCP stdio input
```

Albo MCP Inspector:

```sh
npx @modelcontextprotocol/inspector gsc-mcp
```

Albo bezpośrednio sprawdzić listę properties:

```sh
uv run python -c "from gsc_mcp.server import gsc_list_sites; import json; print(json.dumps(gsc_list_sites(), indent=2, ensure_ascii=False))"
```

## Konfiguracja (env)

| ENV | Default | Opis |
|---|---|---|
| `GSC_MCP_AUTH` | `oauth` | `oauth` lub `sa` |
| `GSC_MCP_OAUTH_CLIENT` | `~/.config/gsc-mcp/oauth-client.json` | OAuth client JSON (Desktop app) |
| `GSC_MCP_OAUTH_TOKENS` | `~/.config/gsc-mcp/oauth-tokens.json` | Cache refresh tokenu (auto-managed) |
| `GSC_MCP_SA_KEY` | `~/.config/gsc-mcp/sa-key.json` | Service Account JSON (tylko `GSC_MCP_AUTH=sa`) |

## Domain vs URL-prefix properties

GSC ma dwa typy property:

- **Domain property** — `sc-domain:ircsklep.pl` (cała domena, DNS verification). **Wymaga OAuth2** — Service Account nie pozwala się dodać.
- **URL prefix** — `https://ircsklep.pl/`. Działa z obu trybów auth.

`gsc_list_sites` pokaże wszystkie do których masz dostęp — kopiuj `siteUrl` 1:1 jako argument do innych tools.

## Limit

GSC API: 25k requests / day / project (gratis). `gsc_search_analytics` ma `row_limit` do 25000 per request.

## Service Account shortcut

Gdyby kiedyś trzeba było SA (np. CI bez interaktywnego loginu):

1. GCP → IAM → Service Accounts → Create → JSON key
2. `~/.config/gsc-mcp/sa-key.json` chmod 600
3. W każdej **URL-prefix property** GSC → Settings → Users → Add user → SA email → Restricted
4. `GSC_MCP_AUTH=sa gsc-mcp`
