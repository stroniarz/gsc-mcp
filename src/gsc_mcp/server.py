"""FastMCP server exposing Google Search Console.

Auth: OAuth2 user-flow (default, supports domain properties) or Service Account
(fallback via GSC_MCP_AUTH=sa). See auth.py.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from googleapiclient.errors import HttpError
from mcp.server.fastmcp import FastMCP

from gsc_mcp.auth import get_service as _get_service

mcp = FastMCP("gsc-mcp")


def _resolve_date_range(
    start_date: str | None, end_date: str | None, days: int | None
) -> tuple[str, str]:
    if start_date and end_date:
        return start_date, end_date
    today = date.today()
    end = today - timedelta(days=2)  # GSC has ~2 day lag
    span = days or 28
    return (end - timedelta(days=span - 1)).isoformat(), end.isoformat()


def _format_http_error(e: HttpError) -> str:
    try:
        return f"GSC API error {e.status_code}: {e.reason} — {e.error_details}"
    except Exception:
        return f"GSC API error: {e}"


@mcp.tool()
def gsc_list_sites() -> dict[str, Any]:
    """List all GSC properties this Service Account has access to.

    Returns a list of {siteUrl, permissionLevel}. Use the siteUrl values
    (e.g. "sc-domain:ircsklep.pl" for domain properties or
    "https://example.com/" for URL-prefix properties) as input to other tools.
    """
    try:
        svc = _get_service()
        resp = svc.sites().list().execute()
        return {"sites": resp.get("siteEntry", [])}
    except HttpError as e:
        return {"error": _format_http_error(e)}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def gsc_search_analytics(
    site_url: str,
    dimensions: list[str] | None = None,
    days: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    filters: list[dict[str, str]] | None = None,
    row_limit: int = 1000,
    search_type: str = "web",
) -> dict[str, Any]:
    """Query GSC Search Analytics API.

    Args:
        site_url: GSC property identifier (e.g. "sc-domain:ircsklep.pl").
        dimensions: Any of "query", "page", "country", "device", "date", "searchAppearance".
            Defaults to ["query", "page"].
        days: Trailing window ending 2 days ago (GSC lag). Defaults to 28.
            Ignored if start_date+end_date provided.
        start_date / end_date: ISO YYYY-MM-DD. Override `days` if both given.
        filters: List of {dimension, operator, expression}. operator one of
            "contains", "equals", "notContains", "notEquals", "includingRegex", "excludingRegex".
        row_limit: Max rows (default 1000, hard max 25000).
        search_type: "web" (default), "image", "video", "news", "discover", "googleNews".

    Returns:
        {"rows": [...], "summary": {clicks, impressions, ctr, position}, "period": {...}}
    """
    try:
        svc = _get_service()
        sd, ed = _resolve_date_range(start_date, end_date, days)
        body: dict[str, Any] = {
            "startDate": sd,
            "endDate": ed,
            "dimensions": dimensions or ["query", "page"],
            "rowLimit": min(row_limit, 25000),
            "type": search_type,
        }
        if filters:
            body["dimensionFilterGroups"] = [{"filters": filters}]
        resp = (
            svc.searchanalytics()
            .query(siteUrl=site_url, body=body)
            .execute()
        )
        rows = resp.get("rows", [])
        totals = {"clicks": 0, "impressions": 0}
        for r in rows:
            totals["clicks"] += r.get("clicks", 0)
            totals["impressions"] += r.get("impressions", 0)
        summary = {
            "clicks": totals["clicks"],
            "impressions": totals["impressions"],
            "ctr": (totals["clicks"] / totals["impressions"]) if totals["impressions"] else 0,
            "rows_returned": len(rows),
        }
        return {
            "period": {"startDate": sd, "endDate": ed},
            "summary": summary,
            "rows": rows,
        }
    except HttpError as e:
        return {"error": _format_http_error(e)}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def gsc_inspect_url(
    site_url: str, inspection_url: str, language_code: str = "pl-PL"
) -> dict[str, Any]:
    """Run URL Inspection API for a single URL.

    Args:
        site_url: GSC property the URL belongs to (e.g. "sc-domain:ircsklep.pl").
        inspection_url: Full URL to inspect (must be on the property).
        language_code: BCP-47 (default "pl-PL").

    Returns full inspection result including index status, last crawl,
    rich result enhancements (BlogPosting, FAQ, etc.), mobile usability,
    and AMP if applicable.
    """
    try:
        svc = _get_service()
        body = {
            "inspectionUrl": inspection_url,
            "siteUrl": site_url,
            "languageCode": language_code,
        }
        resp = svc.urlInspection().index().inspect(body=body).execute()
        return resp.get("inspectionResult", resp)
    except HttpError as e:
        return {"error": _format_http_error(e)}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def gsc_list_sitemaps(site_url: str) -> dict[str, Any]:
    """List sitemaps submitted for a GSC property.

    Returns errors, warnings, contents (per type: web/image/video/news), and
    last download/submitted timestamps for each sitemap.
    """
    try:
        svc = _get_service()
        resp = svc.sitemaps().list(siteUrl=site_url).execute()
        return {"sitemaps": resp.get("sitemap", [])}
    except HttpError as e:
        return {"error": _format_http_error(e)}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def gsc_compare_periods(
    site_url: str,
    days_a: int = 7,
    days_b: int = 7,
    gap_days: int = 0,
    dimensions: list[str] | None = None,
    filters: list[dict[str, str]] | None = None,
    row_limit: int = 100,
) -> dict[str, Any]:
    """Compare two trailing periods (B is more recent, A is older).

    Default: last 7 days (B) vs the 7 days before that (A), no gap.

    Args:
        days_a / days_b: Length of each window.
        gap_days: Days between A end and B start (e.g. 0 = adjacent).
        dimensions / filters / row_limit: Same as gsc_search_analytics.

    Returns:
        {"period_a": {...}, "period_b": {...}, "delta": {...}, "rows": [{key, a, b, delta}]}
    """
    try:
        svc = _get_service()
        today = date.today()
        b_end = today - timedelta(days=2)
        b_start = b_end - timedelta(days=days_b - 1)
        a_end = b_start - timedelta(days=1 + gap_days)
        a_start = a_end - timedelta(days=days_a - 1)
        dims = dimensions or ["query"]

        def _query(sd: date, ed: date) -> list[dict[str, Any]]:
            body: dict[str, Any] = {
                "startDate": sd.isoformat(),
                "endDate": ed.isoformat(),
                "dimensions": dims,
                "rowLimit": min(row_limit, 25000),
                "type": "web",
            }
            if filters:
                body["dimensionFilterGroups"] = [{"filters": filters}]
            r = svc.searchanalytics().query(siteUrl=site_url, body=body).execute()
            return r.get("rows", [])

        rows_a = _query(a_start, a_end)
        rows_b = _query(b_start, b_end)

        def _key(r: dict[str, Any]) -> str:
            return "|".join(r.get("keys", []))

        index_a = {_key(r): r for r in rows_a}
        index_b = {_key(r): r for r in rows_b}
        all_keys = set(index_a) | set(index_b)

        diffs = []
        for k in all_keys:
            a = index_a.get(k, {})
            b = index_b.get(k, {})
            diffs.append(
                {
                    "key": k,
                    "a_clicks": a.get("clicks", 0),
                    "b_clicks": b.get("clicks", 0),
                    "delta_clicks": b.get("clicks", 0) - a.get("clicks", 0),
                    "a_impressions": a.get("impressions", 0),
                    "b_impressions": b.get("impressions", 0),
                    "delta_impressions": b.get("impressions", 0) - a.get("impressions", 0),
                    "a_position": a.get("position"),
                    "b_position": b.get("position"),
                }
            )
        diffs.sort(key=lambda x: abs(x["delta_clicks"]), reverse=True)

        def _totals(rows: list[dict[str, Any]]) -> dict[str, float]:
            return {
                "clicks": sum(r.get("clicks", 0) for r in rows),
                "impressions": sum(r.get("impressions", 0) for r in rows),
            }

        return {
            "period_a": {
                "startDate": a_start.isoformat(),
                "endDate": a_end.isoformat(),
                **_totals(rows_a),
            },
            "period_b": {
                "startDate": b_start.isoformat(),
                "endDate": b_end.isoformat(),
                **_totals(rows_b),
            },
            "rows": diffs[:row_limit],
        }
    except HttpError as e:
        return {"error": _format_http_error(e)}
    except Exception as e:
        return {"error": str(e)}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
