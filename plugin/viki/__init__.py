"""Viki plugin — Rakuten Viki UK drama search tools for Hermes (genre-generic, per-genre memory)."""
from __future__ import annotations
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import viki_core as core  # noqa: E402

G = {"type": "string", "description": "Genre name (PL/EN) or Viki id; combine with '+' for intersection, e.g. 'romance', 'comedy', 'action', 'romance + costume-period'."}
CAND_SCHEMA = {"name": "viki_candidates", "description": (
    "Rakuten Viki (UK) drama search. Returns next UNSEEN, UK-available candidates for the genre (combination), "
    "sorted by highest Viki rating: id, title, rating, url, origin country, English description. With happy_end=true the "
    "tool itself verifies endings server-side (>=2 independent sites) and returns only verified titles (may take 1-3 min first time). "
    "Titles already shown/rejected for this genre are skipped (one list per genre). Use with skill 'viki-search'."),
    "parameters": {"type": "object", "properties": {
        "genre": G,
        "happy_end": {"type": "boolean", "description": "Require confirmed happy end (default: true for romance, false otherwise)."},
        "min_rating": {"type": "number", "description": "Minimum Viki rating (0-10), optional."},
        "country": {"type": "string", "description": "Optional origin filter: kr, cn, jp, tw, th... (comma separated)."},
        "query": {"type": "string", "description": "Optional keyword/title to narrow via Viki search."},
        "count": {"type": "integer", "description": "How many candidates (default 8, to allow rejections)."},
        "session": {"type": "string", "description": "Ignored (kept for compatibility; memory is per genre)."}}, "required": ["genre"]}}
MARK_SCHEMA = {"name": "viki_mark", "description": "Record Viki titles as 'shown' or 'rejected' (happy-end not confirmed) for a genre so they are skipped next time.",
    "parameters": {"type": "object", "properties": {"genre": G,
        "ids": {"type": "array", "items": {"type": "string"}}, "status": {"type": "string", "enum": ["shown", "rejected"]},
        "note": {"type": "string"}}, "required": ["genre", "ids", "status"]}}
GENRES_SCHEMA = {"name": "viki_genres", "description": "List Viki genres with Polish names and keys.", "parameters": {"type": "object", "properties": {}}}
RESET_SCHEMA = {"name": "viki_reset", "description": "Clear the shown/rejected history of a Viki genre (only when the user explicitly asks to clear the genre history).",
    "parameters": {"type": "object", "properties": {"genre": G}, "required": ["genre"]}}

def _j(f):
    def h(args, **kw):
        try: return json.dumps(f(args or {}), ensure_ascii=False)
        except ValueError as e: return json.dumps({"error": str(e)}, ensure_ascii=False)
    return h

def register(ctx) -> None:
    ctx.register_tool(name="viki_candidates", toolset="viki", schema=CAND_SCHEMA, emoji="🎬", handler=_j(lambda a: core.candidates(
        a.get("genre") or "romance", a.get("happy_end"), a.get("min_rating"), a.get("query", ""), a.get("count") or 8, a.get("country", ""))))
    ctx.register_tool(name="viki_mark", toolset="viki", schema=MARK_SCHEMA, emoji="🎬",
                      handler=_j(lambda a: core.mark(a.get("genre") or "romance", a.get("ids") or [], a.get("status", ""), a.get("note", ""))))
    ctx.register_tool(name="viki_genres", toolset="viki", schema=GENRES_SCHEMA, emoji="🎬",
                      handler=_j(lambda a: [{k: g[k] for k in ("key", "name_pl", "name_en", "ids")} for g in core.genres()]))
    ctx.register_tool(name="viki_reset", toolset="viki", schema=RESET_SCHEMA, emoji="🎬", handler=_j(lambda a: core.reset(a.get("genre"))))
