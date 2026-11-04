---
name: viki-search
description: "Search Rakuten Viki dramas by genre (romance, comedy, action, costume & period… and '+' combinations), optionally with a verified happy ending: tools viki_candidates / viki_mark + the bundled results template."
version: 4.0.0
author: Sebastian M
homepage: https://x.com/sebnatmal
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [Viki, Drama, K-drama, C-drama, Romance, Costume, Search, Media]
---

# Viki search (Rakuten Viki)

## Note: Viki panel requests
The Viki Desktop panel selects titles and verifies endings itself. It only sends the agent a short translation task
(a message starting with `[Viki-panel] … TASK … DATA`). For those messages do NOT use this skill or any tools —
just return the `{{viki:ID}}` blocks exactly as the task asks.

## When to use
- The user asks for a drama/series "on Viki" (any genre), or for "more"/"next" suggestions in the same chat.

## Tool parameters: `viki_candidates`
- `genre`: genre name or key; combine with `+` (intersection), e.g. `romance`, `comedy`, `action`,
  `costume-period`, `romance + costume-period`. Full list: `viki_genres`.
- `happy_end`: default true for romance, false otherwise — unless the user says otherwise.
- `min_rating` (0–10), `country` (kr, cn, jp, tw, th…), `query` (keyword/title), `count` (≤3).
- Memory is **per genre (combination)**: shown and rejected titles are skipped on every later search in that genre.
  `viki_reset(genre)` only when the user explicitly asks to clear the genre history.

## Procedure
1. Read the template: `~/.hermes/plugins/viki/templates/viki-results.md`.
2. Call `viki_candidates`. With `happy_end=true` the tool verifies endings server-side (≥2 independent domains,
   sources in `happy_end.sources`) and returns only verified titles; rejected ones are recorded automatically.
   The first search in a genre can take 1–3 minutes (cached afterwards).
3. **Do not research endings yourself** (no web_search/web_extract for that) and do not use vision tools.
4. Answer ONLY in the template format: `##` header, then for each candidate a line `{{viki:<id>}}`,
   **Description:** (4–6 sentences in the user's language, actor names in parentheses, no spoilers), **Country / era:**.
   Do NOT write titles, ratings, images, links or sources — the renderer inserts them from Viki data.
5. Call `viki_mark(genre, ids=[...], status="shown")` for the titles you present.

## Rules
- Never invent titles, ratings, images, endings or links — only data returned by `viki_candidates`.
  If the tool returns nothing or an error, answer exactly: "No results matching the criteria."
- No spoilers beyond "it ends well".
- CLI fallback: `python3 ~/.hermes/plugins/viki/viki_core.py candidates --genre romance [--happy-end yes|no] [--min-rating 9] [--country cn]`,
  `... mark --genre romance --status shown|rejected <id...>`, `... genres`, `... history`, `... check <id>`.
