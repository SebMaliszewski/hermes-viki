"""Core logic for the Viki plugin (tools + dashboard + CLI: python3 viki_core.py --help).

Genres: Viki genre list (api.viki.io/v4/genres.json) with Polish names; a "genre key" may combine
several genres with '+' (intersection), e.g. "kostiumowe+romans". Each combination has ONE
persistent seen/rejected list (data/genres/<key>.json) and one Hermes chat 'Viki: <Genre>'.
"""
from __future__ import annotations
import json, re, sys, time, concurrent.futures, urllib.error, urllib.parse, urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA_DIR = BASE / "data"            # v4+: English names (legacy: dane/, opisy_pl/, archiwum/ — migrated on import)
GEN = DATA_DIR / "genres"
CACHE = DATA_DIR / "cache"
API = "https://api.viki.io/v4"
APP = "100000a"
CFG_DEFAULT = {"export_dir": "",   # optional: folder (e.g. an Obsidian vault subfolder) for a .md copy of each result
               "min_reviews": 500, "max_pages": 12, "cache_ttl_s": 86400, "max_results": 3,
               "romance_includes_romcom": True}

# Viki genre id -> (stable English key, Polish display name). Unknown ids fall back to a slug of the English name.
GENRES = {
    "1g": ("action", "Akcja"),
    "2g": ("animation", "Animacja"),
    "6g": ("comedy", "Komedia"),
    "7g": ("crime-mystery", "Kryminał i zagadka"),
    "8g": ("documentary", "Dokument"),
    "9g": ("drama", "Dramat"),
    "10g": ("entertainment", "Rozrywka"),
    "12g": ("supernatural", "Nadprzyrodzone"),
    "17g": ("music", "Muzyka"),
    "18g": ("romantic-comedy", "Komedia romantyczna"),
    "19g": ("fantasy", "Fantasy"),
    "20g": ("sports", "Sport"),
    "24g": ("family-kids", "Rodzinne"),
    "25g": ("costume-period", "Kostiumowe"),
    "26g": ("thriller", "Thriller"),
    "1037g": ("historical", "Historyczne"),
    "1038g": ("idol-drama", "Idol drama"),
    "1040g": ("medical", "Medyczne"),
    "1041g": ("melodrama", "Melodramat"),
    "1044g": ("variety-show", "Variety show"),
    "1045g": ("web-drama", "Web drama"),
    "1047g": ("short-films", "Krótkie filmy"),
    "1050g": ("war", "Wojenne"),
    "1055g": ("travel", "Podróże"),
    "1063g": ("horror", "Horror"),
    "1064g": ("sci-fi", "Sci-Fi"),
    "1067g": ("bl", "BL"),
    "1068g": ("romance", "Romans"),
    "1069g": ("awards", "Nagrody"),
    "1070g": ("performance", "Występy"),
    "1071g": ("gl", "GL"),
    "1072g": ("adventure", "Przygodowe"),
    "1073g": ("lgbtq", "LGBTQ+"),
}
# Legacy (v1-v3) Polish keys -> English keys; used by the data migration and to accept old keys as input.
LEGACY_KEYS = {"akcja": "action", "animacja": "animation", "komedia": "comedy", "kryminal": "crime-mystery", "dokument": "documentary", "dramat": "drama", "rozrywka": "entertainment", "nadprzyrodzone": "supernatural", "muzyka": "music", "komedia-romantyczna": "romantic-comedy", "sport": "sports", "rodzinne": "family-kids", "kostiumowe": "costume-period", "historyczne": "historical", "idol": "idol-drama", "medyczne": "medical", "melodramat": "melodrama", "variety": "variety-show", "krotkie": "short-films", "wojenne": "war", "podroze": "travel", "romans": "romance", "nagrody": "awards", "wystepy": "performance", "przygoda": "adventure"}
ALIASES = {"romans": "romance", "romanse": "romance", "romantyczne": "romance", "romantic": "romance",
           "komedia": "comedy", "akcja": "action", "kostiumowe": "costume-period", "costume": "costume-period",
           "period": "costume-period", "historyczne": "historical", "kryminal": "crime-mystery", "crime": "crime-mystery",
           "dramat": "drama", "romcom": "romantic-comedy", "fantastyka": "fantasy", "scifi": "sci-fi", "sci fi": "sci-fi"}
COUNTRIES = {"kr": "Korea Płd.", "cn": "Chiny", "jp": "Japonia", "tw": "Tajwan", "th": "Tajlandia", "ph": "Filipiny",
             "hk": "Hongkong", "us": "USA", "in": "Indie", "id": "Indonezja", "vn": "Wietnam", "my": "Malezja"}
ROMANCE_KEYS = {"romance"}
COUNTRIES_JA = {"kr": "韓国", "cn": "中国", "jp": "日本", "tw": "台湾", "th": "タイ", "ph": "フィリピン", "hk": "香港",
                "us": "アメリカ", "in": "インド", "id": "インドネシア", "vn": "ベトナム", "my": "マレーシア"}
COUNTRIES_ZH = {"kr": "韩国", "cn": "中国", "jp": "日本", "tw": "台湾", "th": "泰国", "ph": "菲律宾", "hk": "香港",
                "us": "美国", "in": "印度", "id": "印度尼西亚", "vn": "越南", "my": "马来西亚"}
COUNTRIES_EN = {"kr": "South Korea", "cn": "China", "jp": "Japan", "tw": "Taiwan", "th": "Thailand", "ph": "Philippines",
                "hk": "Hong Kong", "us": "USA", "in": "India", "id": "Indonesia", "vn": "Vietnam", "my": "Malaysia"}
# All user-visible output strings (rendered results) — one dict per language.
LABELS = {
    "pl": {"header": 'Wyniki wyszukiwania: {genre} dla "{query}" na [Rakuten Viki](https://www.viki.com)',
           "desc": "Opis", "country": "Kraj / epoka", "sources": "Źródła happy-end", "watch": "Oglądaj na Viki",
           "rating": "Ocena Viki", "reviews": "ocen", "uk": "Dostępne w UK", "yes": "tak", "no": "nie",
           "badge": "Gwarancja Happy-End", "none": "Brak wyników spełniających kryteria.", "nodesc": "(brak opisu)"},
    "en": {"header": 'Search results: {genre} for "{query}" on [Rakuten Viki](https://www.viki.com)',
           "desc": "Description", "country": "Country / era", "sources": "Happy-end sources", "watch": "Watch on Viki",
           "rating": "Viki rating", "reviews": "ratings", "uk": "Available in UK", "yes": "yes", "no": "no",
           "badge": "Happy-End Guaranteed", "none": "No results matching the criteria.", "nodesc": "(no description)"},
    "ja": {"header": "検索結果：{genre}「{query}」 [Rakuten Viki](https://www.viki.com)",
           "desc": "あらすじ", "country": "国 / 時代", "sources": "ハッピーエンドの出典", "watch": "Vikiで見る",
           "rating": "Viki評価", "reviews": "件", "uk": "英国で視聴可能", "yes": "はい", "no": "いいえ",
           "badge": "ハッピーエンド保証", "none": "条件に合う作品はありません。", "nodesc": "（あらすじなし）"},
    "zh": {"header": "搜索结果：{genre}「{query}」 [Rakuten Viki](https://www.viki.com)",
           "desc": "简介", "country": "国家 / 时代", "sources": "大结局（HE）来源", "watch": "在 Viki 观看",
           "rating": "Viki 评分", "reviews": "条评分", "uk": "英国可观看", "yes": "是", "no": "否",
           "badge": "保证大团圆结局", "none": "没有符合条件的结果。", "nodesc": "（暂无简介）"},
}
LANGS = tuple(LABELS)                     # ("pl", "en", "ja")
def norm_lang(x) -> str: x = str(x or "pl").lower(); x = {"jp": "ja", "cn": "zh"}.get(x, x); return x if x in LABELS else "pl"
def L(lang: str) -> dict: return LABELS.get(lang, LABELS["pl"])
sys.path.insert(0, str(BASE))
import happyend  # noqa: E402

# ---------- one-time migration of v1-v3 data (Polish dir names and genre keys) ----------
def _new_key(k: str) -> str:
    return "+".join(sorted(LEGACY_KEYS.get(p, p) for p in str(k).split("+")))

def migrate() -> list[str]:
    log = []
    old = BASE / "dane"
    if old.exists() and not DATA_DIR.exists():
        old.rename(DATA_DIR); log.append("dane/ -> data/")
    for a, b in (("opisy_pl", "descriptions"), ("archiwum", "archive")):
        if (DATA_DIR / a).exists() and not (DATA_DIR / b).exists():
            (DATA_DIR / a).rename(DATA_DIR / b); log.append(f"data/{a}/ -> data/{b}/")
    for folder in (DATA_DIR / "genres", DATA_DIR / "archive"):
        if not folder.exists(): continue
        for p in sorted(folder.glob("*.json")):
            stem, _, stamp = p.stem.partition("-2") if folder.name == "archive" else (p.stem, "", "")
            nk = _new_key(stem)
            try: st = json.loads(p.read_text())
            except Exception: continue
            if st.get("key") and _new_key(st["key"]) != st["key"]:
                st["key"] = _new_key(st["key"]); p.write_text(json.dumps(st, ensure_ascii=False, indent=1))
            if nk != stem:
                dest = folder / (f"{nk}-2{stamp}.json" if stamp else f"{nk}.json")
                if not dest.exists(): p.rename(dest); log.append(f"{folder.name}/{p.name} -> {dest.name}")
    return log

try: MIGRATION_LOG = migrate()
except Exception as _e: MIGRATION_LOG = [f"migration error: {_e}"]


def cfg() -> dict:
    c = dict(CFG_DEFAULT); p = DATA_DIR / "config.json"
    if p.exists():
        try: c.update(json.loads(p.read_text()))
        except Exception: pass
    return c

def _get(path: str, **params):
    params["app"] = APP
    url = f"{API}/{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (hermes-viki)"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())

def _wjson(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True); tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1)); tmp.replace(p)

# ---------- genres ----------
def genres(force: bool = False) -> list[dict]:
    p = CACHE / "genres.json"
    raw = None
    if not force and p.exists() and time.time() - p.stat().st_mtime < 7 * 86400:
        raw = json.loads(p.read_text())
    if raw is None:
        try: raw = _get("genres.json"); _wjson(p, raw)
        except Exception:
            raw = json.loads(p.read_text()) if p.exists() else [{"id": k, "name": {"en": v[1]}} for k, v in PL.items()]
    out = []
    for g in raw:
        en = (g.get("name") or {}).get("en") or g["id"]
        key, pl = GENRES.get(g["id"], (re.sub(r"[^a-z0-9]+", "-", en.lower()).strip("-"), en))
        ids = [g["id"]]
        if key == "romance" and cfg()["romance_includes_romcom"]: ids.append("18g")
        names = dict(g.get("name") or {}); names["pl"] = pl; names.setdefault("en", en)
        out.append({"key": key, "ids": ids, "name_pl": pl, "name_en": en, "names": names, "happy_end_default": key in ROMANCE_KEYS})
    return sorted(out, key=lambda x: x["name_pl"].lower())

def resolve(genre) -> dict:
    """'Romance + Costume & Period' / ['romance','25g'] / 'romans' -> combined genre spec."""
    parts = genre if isinstance(genre, list) else re.split(r"\s*[+,&/]\s*|\s+i\s+|\s+and\s+", str(genre or "romance"))
    gl = genres(); found = []
    for raw in parts:
        t = str(raw).strip().lower()
        if not t: continue
        t = ALIASES.get(t, LEGACY_KEYS.get(t, t))
        g = next((x for x in gl if t in (x["key"], x["name_pl"].lower(), x["name_en"].lower()) or t in x["ids"]), None)
        if not g:
            g = next((x for x in gl if x["key"].startswith(t) or x["name_pl"].lower().startswith(t)), None)
        if not g: raise ValueError(f"Unknown genre: {raw!r}. Available: " + ", ".join(x["key"] for x in gl))
        if g not in found: found.append(g)
    if not found: found = [next(x for x in gl if x["key"] == "romance")]
    # display order: romance-like first, then as given; key is order-independent (sorted)
    found.sort(key=lambda x: 0 if x["key"] in ROMANCE_KEYS else 1)
    return {"key": "+".join(sorted(x["key"] for x in found)), "parts": found,
            "name_pl": " + ".join(x["name_pl"] for x in found), "name_en": " + ".join(x["name_en"] for x in found),
            "happy_end_default": any(x["happy_end_default"] for x in found),
            "names": {l: " + ".join((x.get("names") or {}).get(l) or x["name_en"] for x in found) for l in ("pl", "en", "ja", "zh")}}

# ---------- catalog ----------
def _norm(c: dict) -> dict:
    img = c.get("images") or {}
    bb = (img.get("billboards") or {}).get("16x9") or [{}]
    bb_url = (bb[0] or {}).get("url") if bb else None
    poster = (img.get("poster") or {}).get("url")
    rs = c.get("review_stats") or {}; t = c.get("titles") or {}; d = c.get("descriptions") or {}
    return {"id": c["id"], "title": t.get("en") or next(iter(t.values()), c["id"]), "title_pl": t.get("pl"), "title_ja": t.get("ja"), "title_zh": t.get("zh"),
            "rating": round(float(rs.get("average_rating") or 0), 2), "review_count": int(rs.get("count") or 0),
            "blocked": bool(c.get("blocked")), "image_16x9": bb_url, "image_poster": poster, "image": bb_url or poster,
            "url": (c.get("url") or {}).get("web") or f"https://www.viki.com/tv/{c['id']}",
            "description_en": d.get("en") or "", "description_pl": d.get("pl"), "description_ja": d.get("ja"), "description_zh": d.get("zh"), "genres": c.get("genres") or [],
            "origin": (c.get("origin") or {}).get("country"), "type": c.get("type")}

def _genre_catalog(gid: str, force=False) -> dict[str, dict]:
    c = cfg(); p = CACHE / f"genre_{gid}.json"
    if not force and p.exists() and time.time() - p.stat().st_mtime < c["cache_ttl_s"]:
        return json.loads(p.read_text())
    items: dict[str, dict] = {}
    for sort in ("views_recent", "average_rating"):
        for page in range(1, c["max_pages"] + 1):
            try: d = _get("containers.json", genre=gid, per_page=50, page=page, sort=sort, direction="desc")
            except Exception: break
            for raw in d.get("response") or []:
                try: items[raw["id"]] = _norm(raw)
                except Exception: pass
            if not d.get("more"): break
    if items: _wjson(p, items)
    elif p.exists(): return json.loads(p.read_text())
    return items

def catalog(spec: dict, force=False) -> list[dict]:
    pool = None
    for g in spec["parts"]:                 # union inside one genre (romans = 1068g ∪ 18g) ...
        u: dict[str, dict] = {}
        for gid in g["ids"]: u.update(_genre_catalog(gid, force))
        pool = u if pool is None else {k: v for k, v in pool.items() if k in u}   # ... intersection across genres
    return sorted((pool or {}).values(), key=lambda x: (-x["rating"], -x["review_count"]))

# ---------- per-genre state ----------
def _sp(key: str) -> Path: return GEN / (re.sub(r"[^a-z0-9+_-]", "_", key) + ".json")

def load_state(spec: dict) -> dict:
    p = _sp(spec["key"])
    if p.exists():
        try: return json.loads(p.read_text())
        except Exception: pass
    return {"key": spec["key"], "name_pl": spec["name_pl"], "shown": {}, "rejected": {},
            "session_id": "", "searches": [], "created": time.time()}

def save_state(st: dict) -> None:
    st["updated"] = time.time(); _wjson(_sp(st["key"]), st)

def candidates(genre="romance", happy_end=None, min_rating=None, query="", count=8, country="",
               min_reviews=None) -> dict:
    spec = resolve(genre); c = cfg()
    he = spec["happy_end_default"] if happy_end is None else bool(happy_end)
    mr = c["min_reviews"] if min_reviews is None else int(min_reviews)
    st = load_state(spec); seen = set(st["shown"]) | set(st["rejected"])
    pool = catalog(spec)
    if query and query.strip():
        try:
            ids = {h.get("id") for h in (_get("search.json", term=query, per_page=50).get("response") or [])}
            sub = [x for x in pool if x["id"] in ids]
            if sub: pool = sub
        except Exception: pass
    cc = [x.strip().lower() for x in re.split(r"[,\s]+", country or "") if x.strip()]
    elig = [x for x in pool if not x["blocked"] and x["review_count"] >= mr and x["id"] not in seen
            and (min_rating in (None, "") or x["rating"] >= float(min_rating)) and (not cc or (x["origin"] or "") in cc)]
    want = max(1, min(int(count or 8), 20))
    def _pub(x, hv=None):
        d = dict({k: v for k, v in x.items() if k not in ("image", "image_16x9", "image_poster", "blocked")},
                 description_en=x["description_en"][:1500], origin_pl=COUNTRIES.get(x["origin"] or "", x["origin"]))
        if hv: d["happy_end"] = {"verdict": hv["verdict"], "sources": [s["url"] for s in hv["happy_sources"]]}
        return d
    checked = rejected_now = 0
    if not he:
        res = [_pub(x) for x in elig[:want]]
    else:
        # server-side happy-end verification: check in order, small parallel batches sized to what is still
        # missing, stop as soon as enough HAPPY titles are found (cached verdicts cost nothing)
        res, i, budget, need = [], 0, int(c.get("max_new_checks", 15)), min(want, c["max_results"])
        while len(res) < need and i < len(elig) and budget > 0:
            batch = []
            while i < len(elig) and len(batch) < max(1, need - len(res)):
                x = elig[i]; i += 1
                if happyend.cached(x["id"]) is None: budget -= 1
                batch.append(x)
            with concurrent.futures.ThreadPoolExecutor(3) as ex:
                vs = list(ex.map(lambda x: happyend.check(x["id"], x["title"], x["origin"] or ""), batch))
            checked += len(batch)
            for x, v in zip(batch, vs):
                if v["verdict"] == "HAPPY" and len(res) < need: res.append(_pub(x, v))
                elif v["verdict"] != "HAPPY":
                    st["rejected"][x["id"]] = {"title": x["title"], "at": time.time(), "note": "happy-end " + v["verdict"]}
                    rejected_now += 1
        if rejected_now: save_state(st)
    return {"genre_key": spec["key"], "genre_pl": spec["name_pl"], "genre_en": spec["name_en"],
            "happy_end_required": he, "min_rating": min_rating, "country": cc, "query": query,
            "max_results_to_show": c["max_results"], "already_shown": len(st["shown"]),
            "already_rejected": len(st["rejected"]), "remaining_eligible": len(elig) - len(res), "candidates": res,
            "happy_end_checked": checked, "happy_end_rejected_now": rejected_now,
            "note": ("Sorted by Viki rating desc (min %d reviews), UK-available only. " % mr) +
                    ("Happy-end ALREADY VERIFIED server-side (>=2 independent sources each) — do NOT research endings. " if he
                     else "Happy-end NOT required: do not add the 'Gwarancja Happy-End' label. ") +
                    "OUTPUT: start each title block with the line {{viki:<id>}} (heading, rating, image and link are inserted automatically from Viki data — do NOT write them). Call viki_mark(genre=%r, status=shown) for the ones you present." % spec["key"]}

def mark(genre, ids, status, note="") -> dict:
    spec = resolve(genre)
    if isinstance(ids, str): ids = [i for i in re.split(r"[,\s]+", ids) if i]
    if status not in ("shown", "rejected"): return {"error": "status must be shown|rejected"}
    st = load_state(spec); titles = {x["id"]: x["title"] for x in catalog(spec)}
    for i in ids:
        st[status][i] = {"title": titles.get(i, i), "at": time.time(), "note": note}
        st["shown" if status == "rejected" else "rejected"].pop(i, None)
    save_state(st)
    return {"ok": True, "genre_key": spec["key"], "status": status, "ids": ids,
            "shown_total": len(st["shown"]), "rejected_total": len(st["rejected"])}

def reset(genre) -> dict:
    spec = resolve(genre); st = load_state(spec); old = st.get("session_id", "")
    p = _sp(spec["key"])
    if p.exists():
        arch = DATA_DIR / "archive"; arch.mkdir(parents=True, exist_ok=True)
        p.replace(arch / f"{p.stem}-{time.strftime('%Y%m%d-%H%M%S')}.json")
    return {"ok": True, "genre_key": spec["key"], "reset": True, "old_session_id": old}

def history() -> list[dict]:
    out = []
    for p in sorted(GEN.glob("*.json")) if GEN.exists() else []:
        try: st = json.loads(p.read_text())
        except Exception: continue
        out.append({"key": st["key"], "name_pl": st.get("name_pl", st["key"]), "session_id": st.get("session_id", ""),
                    "shown": len(st.get("shown", {})), "rejected": len(st.get("rejected", {})),
                    "searches": st.get("searches", [])[-50:], "updated": st.get("updated", 0)})
    return sorted(out, key=lambda x: -x["updated"])

# ---------- authoritative rendering (title/rating/image/link come from the API, never from the model) ----------
def lookup(cid: str) -> dict | None:
    for p in CACHE.glob("genre_*.json"):
        try:
            d = json.loads(p.read_text())
            if cid in d: return d[cid]
        except Exception: pass
    try: return _norm(_get(f"containers/{cid}.json"))
    except Exception: return None

def _title_index() -> dict[str, str]:
    idx = {}
    for p in CACHE.glob("genre_*.json"):
        try:
            for k, v in json.loads(p.read_text()).items():
                idx[re.sub(r"\W+", "", v["title"].lower())] = k
        except Exception: pass
    return idx

def url_alive(u: str) -> bool:
    """False only for definite dead links (404/410, DNS failure); 403/anti-bot pages count as alive. Cached."""
    p = CACHE / "urls.json"
    try: cache = json.loads(p.read_text())
    except Exception: cache = {}
    if u in cache: return cache[u]
    ok = True
    try:
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}, method="GET")
        urllib.request.urlopen(req, timeout=6).close()
    except urllib.error.HTTPError as e: ok = e.code not in (404, 410)
    except Exception: ok = False
    cache[u] = ok
    try: _wjson(p, cache)
    except Exception: pass
    return ok

MARK_RE = re.compile(r"\{\{\s*viki:([0-9]+c)\s*\}\}")

def render(text: str, happy_end: bool = True, key: str = "", mark_shown: bool = True, lang: str = "pl") -> dict:
    lb = L(lang)
    """Turn the agent's reply into final markdown. Each title block starts with {{viki:<id>}}; we insert the
    heading (title, real rating, label), the original 16:9 image and the Viki link from API data.
    Model-written headings/images/links inside blocks are discarded. Legacy replies without markers:
    '### N. Title ...' headings are matched to ids by title."""
    lines = str(text or "").replace("\r", "").split("\n")
    tidx = None; out_lines = []
    for l in lines:                                   # legacy: convert '### 1. Title ⭐ 9.0 ...' to markers
        m = re.match(r"^#{2,4}\s*\d+[.)]\s*(.+?)(\s*⭐.*)?$", l.strip())
        if m and not MARK_RE.search(l):
            tidx = tidx or _title_index()
            t = re.sub(r"`[^`]*`", "", m.group(1)); cid = tidx.get(re.sub(r"\W+", "", t.lower()))
            if cid: out_lines.append("{{viki:%s}}" % cid); continue
        out_lines.append(l)
    head, blocks, cur = [], [], None
    for l in out_lines:
        m = MARK_RE.search(l)
        if m: cur = {"id": m.group(1), "lines": []}; blocks.append(cur); continue
        (cur["lines"] if cur else head).append(l)
    ids, md = [], []
    md += [l for l in head if not re.match(r"^\s*(!\[|\(.*Zaznaczon)", l)]
    n = 0
    for b in blocks:
        it = lookup(b["id"])
        if not it: continue
        n += 1; ids.append(b["id"])
        body = [l for l in b["lines"] if l.strip() and not re.match(r"^\s*(#{1,4}\s|!\[|\[Oglądaj|\(.*(shown|Zaznaczon))", l)]
        body = [re.sub(r"\s*·?\s*\[Oglądaj na Viki\]\([^)]*\).*$", "", l) for l in body]
        body = [l for l in body if not re.match(r"^(źródła happy-end|happy-end sources)", l.lower())]   # model source lines ignored
        hv = happyend.cached(b["id"]) if happy_end else None
        label = ""
        if hv and hv.get("verdict") == "HAPPY":
            label = f" `{lb['badge']}`"
            body.append(f"{lb['sources']}: " + " · ".join(f"[{happyend._dom(s['url'])}]({s['url']})" for s in hv["happy_sources"][:4]))
        title = it.get(f"title_{lang}") or it["title"] if lang != "en" else it["title"]
        md += ["", f"### {n}. {title} ⭐ {it['rating']:.1f}{label}",
               f"![{title}]({it.get('image_16x9') or it.get('image_poster') or ''})", *body,
               f"[{lb['watch']}]({it['url']}) · {lb['rating']}: {it['rating']:.1f} ({format(it['review_count'], ',').replace(',', ' ')} {lb['reviews']}) · {lb['uk']}: {lb['no'] if it['blocked'] else lb['yes']}"]
    if mark_shown and key and ids:
        try:
            st = load_state(resolve(key)); new = [i for i in ids if i not in st["shown"]]
            if new: mark(key, new, "shown", "panel-render")
        except Exception: pass
    return {"markdown": "\n".join(md).strip() if blocks else str(text or ""), "ids": ids}

def export_markdown(md: str, genre_name: str, lang: str = "en") -> str:
    """Write a rendered result to config export_dir (if set). Returns the file path or ''."""
    d = str(cfg().get("export_dir") or "").strip()
    if not d or not md.strip(): return ""
    folder = Path(d).expanduser(); folder.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^\w +&.-]+", "_", genre_name).strip() or "viki"
    p = folder / f"Viki {time.strftime('%Y-%m-%d %H%M%S')} - {safe} ({lang}).md"
    p.write_text(md + "\n", encoding="utf-8"); return str(p)


# ---------- translated description cache ----------
DESC_DIR = DATA_DIR / "descriptions"

def _opath(cid: str, lang: str) -> Path: return DESC_DIR / (f"{cid}.json" if lang == "pl" else f"{cid}.{lang}.json")

def _mk(cid: str, lang: str, desc: str, it: dict) -> dict:
    lb = L(lang); cmap = {"en": COUNTRIES_EN, "ja": COUNTRIES_JA, "zh": COUNTRIES_ZH, "pl": COUNTRIES}[lang]
    sents = re.split(r"(?<=[.!?…。！？])\s*", desc.strip()) if lang in ("ja", "zh") else re.split(r"(?<=[.!?…])\s+", desc.strip())
    sep = "" if lang in ("ja", "zh") else " "
    return {"id": cid, "opis": f"**{lb['desc']}:** " + sep.join(x for x in sents[:6] if x),
            "kraj": f"**{lb['country']}:** " + cmap.get(it.get("origin") or "", it.get("origin") or "?"), "at": time.time()}

def opis_get(cid: str, lang: str = "pl") -> dict | None:
    try: return json.loads(_opath(cid, lang).read_text())
    except Exception: pass
    if lang in ("en", "ja", "zh"):        # use Viki's own text when it exists (no model call)
        it = lookup(cid)
        if it and lang in ("ja", "zh") and f"title_{lang}" not in it:
            try: it = _norm(_get(f"containers/{cid}.json"))      # old cache rows lack ja fields
            except Exception: pass
        desc = (it or {}).get(f"description_{lang}")
        if desc:
            d = _mk(cid, lang, desc, it); _wjson(_opath(cid, lang), d); return d
    return None

def opis_put(cid: str, lines: list[str], lang: str = "pl") -> None:
    lb = L(lang)
    opis = next((l for l in lines if l.startswith(f"**{lb['desc']}:**") or l.startswith("**Opis:**")), "")
    if len(opis) < (30 if lang in ("ja", "zh") else 60): return
    kraj = next((l for l in lines if l.startswith(f"**{lb['country']}:**") or l.lower().startswith("**kraj")), "")
    _wjson(_opath(cid, lang), {"id": cid, "opis": opis, "kraj": kraj, "at": time.time()})

def compose(ids: list[str], header: str, agent_text: str = "", lang: str = "pl") -> str:
    """Merge the agent's blocks (stored into the cache) with cached texts, in the selected order."""
    cur = None; blocks: dict[str, list[str]] = {}
    for l in str(agent_text or "").replace("\r", "").split("\n"):
        m = MARK_RE.search(l)
        if m: cur = m.group(1); blocks[cur] = []; continue
        if cur and l.strip(): blocks[cur].append(l.strip())
    for cid, ls in blocks.items(): opis_put(cid, ls, lang)
    out = [header, ""]
    for cid in ids:
        o = opis_get(cid, lang)
        out += ["{{viki:%s}}" % cid, *([o["opis"], o["kraj"]] if o else blocks.get(cid, [f"**{L(lang)['desc']}:** {L(lang)['nodesc']}"])), ""]
    return "\n".join(out)

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("candidates"); a.add_argument("--genre", default="romance"); a.add_argument("--query", default="")
    a.add_argument("--count", type=int, default=8); a.add_argument("--happy-end", choices=["yes", "no"]); a.add_argument("--min-rating", type=float)
    a.add_argument("--country", default="")
    m = sp.add_parser("mark"); m.add_argument("--genre", default="romance"); m.add_argument("--status", required=True); m.add_argument("ids", nargs="+")
    r = sp.add_parser("reset"); r.add_argument("--genre", default="romance")
    sp.add_parser("genres"); sp.add_parser("history")
    hc = sp.add_parser("check"); hc.add_argument("ids", nargs="+"); hc.add_argument("--force", action="store_true")
    rn = sp.add_parser("render"); rn.add_argument("--genre", default=""); rn.add_argument("--happy-end", choices=["yes", "no"], default="yes")
    o = ap.parse_args()
    if o.cmd == "candidates":
        out = candidates(o.genre, None if o.happy_end is None else o.happy_end == "yes", o.min_rating, o.query, o.count, o.country)
    elif o.cmd == "mark": out = mark(o.genre, o.ids, o.status)
    elif o.cmd == "reset": out = reset(o.genre)
    elif o.cmd == "genres": out = genres()
    elif o.cmd == "check":
        out = []
        for i in o.ids:
            it = lookup(i); out.append(happyend.check(i, it["title"], it.get("origin") or "", force=o.force))
    elif o.cmd == "render":
        print(render(sys.stdin.read(), o.happy_end == "yes", o.genre, mark_shown=bool(o.genre))["markdown"]); sys.exit(0)
    else: out = history()
    print(json.dumps(out, ensure_ascii=False, indent=1))
