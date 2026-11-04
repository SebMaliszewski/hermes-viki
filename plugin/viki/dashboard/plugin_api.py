"""Backend routes for the Viki desktop panel → /api/plugins/viki/...

Economy flow (v3): the BACKEND selects titles (UK-available, unseen for the genre, happy-end verified server-side
when required); Hermes only translates descriptions in one short tool-free turn; cached translations
(data/descriptions/<id>.json) skip Hermes entirely. Title/rating/image/link/sources are inserted from Viki API + checker.

GET  /genres                        → {genres, countries}
GET  /history                       → {items:[{key,name_pl,session_id,shown,rejected,searches[{…, markdown}],updated}]}
POST /search {genres|key, happy_end, min_rating, count, country, more, lang: pl|en} → {job_id}
GET  /job?id=…                      → {status: running|done|error, result?: {key,name_pl,title,session_id,ids,
                                        header,settings,search_at,prompt|null}}
POST /session {key, session_id}     → remember the Hermes session of a genre combination
POST /render {key, ids, header, text, happy_end, search_at, lang} → {markdown, ids}  (caches PL texts, marks shown,
                                        stores markdown in the search history)
POST /reset {key}                   → archive the genre list → {old_session_id}
"""
from __future__ import annotations
import sys, threading, time, uuid
from pathlib import Path
from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Query

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import viki_core as core  # noqa: E402

router = APIRouter()
PREFIX = "[Viki-panel]"
_jobs: Dict[str, Dict[str, Any]] = {}
_jlock = threading.Lock()


def _spec(g) -> dict:
    try: return core.resolve(g)
    except ValueError as e: raise HTTPException(status_code=400, detail={"code": "bad_genre", "msg": str(e)})


PROMPTS = {
    "pl": ("for each item translate the EN description into Polish (4–6 sentences, keep actor names in parentheses, no spoilers) "
           "and give country and era/dynasty (in Polish) only if stated in the description.", "**Opis:** …\n**Kraj / epoka:** …"),
    "en": ("for each item shorten the EN description to 4–6 sentences (keep actor names in parentheses, no spoilers) "
           "and give country and era only if stated.", "**Description:** …\n**Country / era:** …"),
    "ja": ("各作品の英語のあらすじを日本語に翻訳してください（4〜6文、俳優名は原文どおり括弧内、ネタバレなし）。国と、あらすじから分かる場合のみ時代も。",
           "**あらすじ:** …\n**国 / 時代:** …"),
    "zh": ("请将每部剧的英文简介翻译成简体中文（4–6 句，演员名按原文放在括号内，不剧透），并注明国家；仅当简介中提到时注明时代/朝代。",
           "**简介:** …\n**国家 / 时代:** …"),
}


def build_prompt(spec: dict, items: list[dict], header: str, lang: str = "pl") -> str:
    task, fmt = PROMPTS[lang]
    data = "\n".join(f"[{x['id']}] {x['title']} — country: {x.get('origin') or '?'}\nEN: {x['description_en']}" for x in items)
    return (f"{PREFIX} {header}\n"
            "TASK (do NOT call any tools, do not load skills, do not read files — all data is below): "
            f"{task} Return ONLY this, no comments:\n{{{{viki:ID}}}}\n{fmt}\n\nDATA:\n" + data)


def _run_job(jid: str, spec: dict, body: dict) -> None:
    try:
        he = body.get("happy_end"); he = spec["happy_end_default"] if he is None else bool(he)
        count = max(1, min(3, int(body.get("count") or 3)))
        mr = body.get("min_rating"); mr = float(mr) if mr not in (None, "") else None
        country = ",".join(c for c in str(body.get("country") or "").lower().replace(" ", "").split(",") if c)
        t0 = time.time()
        r = core.candidates(spec["key"], he, mr, "", count, country)
        items = r["candidates"][:count]
        label = spec["name_pl"] + (f", min. {mr}" if mr else "") + \
            (f", {', '.join(core.COUNTRIES.get(c, c) for c in country.split(','))}" if country else "")
        lang = core.norm_lang(body.get("lang"))
        gname = spec["names"].get(lang) or spec["name_en"]
        if lang != "pl":
            cm = {"en": core.COUNTRIES_EN, "ja": core.COUNTRIES_JA, "zh": core.COUNTRIES_ZH}[lang]
            label = gname + (f", min. {mr}" if mr else "") + (f", {', '.join(cm.get(c, c) for c in country.split(','))}" if country else "")
        header = "## " + core.L(lang)["header"].format(genre=gname, query=label)
        st = core.load_state(spec); st["name_pl"] = spec["name_pl"]
        entry = {"at": time.time(), "happy_end": he, "min_rating": mr, "count": count, "country": country,
                 "more": bool(body.get("more")), "ids": [x["id"] for x in items], "select_s": round(time.time() - t0, 1),
                 "checked": r.get("happy_end_checked", 0), "lang": lang}
        st.setdefault("searches", []).append(entry); core.save_state(st)
        todo = [x for x in items if not core.opis_get(x["id"], lang)]   # EN/JA: Viki text when available
        res = {"key": spec["key"], "name_pl": spec["name_pl"], "title": f"Viki: {spec['name_pl']}",
               "session_id": st.get("session_id", ""), "ids": entry["ids"], "header": header, "settings": entry,
               "search_at": entry["at"], "label": label, "lang": lang, "prompt": build_prompt(spec, todo, header, lang) if todo else None,
               "cached": len(items) - len(todo)}
        with _jlock: _jobs[jid] = {"status": "done", "result": res, "at": time.time()}
    except Exception as e:  # noqa: BLE001
        with _jlock: _jobs[jid] = {"status": "error", "error": str(e), "at": time.time()}


@router.get("/genres")
def get_genres() -> Dict[str, Any]:
    return {"genres": core.genres(), "countries": core.COUNTRIES}


@router.get("/history")
def get_history() -> Dict[str, Any]:
    return {"items": core.history()}


@router.post("/search")
def post_search(body: Dict[str, Any]) -> Dict[str, Any]:
    spec = _spec(body.get("genres") or body.get("key") or "romance")
    if body.get("more") and body.get("key"):
        last = (core.load_state(spec).get("searches") or [{}])[-1]
        for k in ("happy_end", "min_rating", "count", "country", "lang"):
            body.setdefault(k, last.get(k))
    jid = uuid.uuid4().hex[:12]
    with _jlock:
        for k in [k for k, v in _jobs.items() if time.time() - v.get("at", time.time()) > 3600]: _jobs.pop(k, None)
        _jobs[jid] = {"status": "running", "at": time.time()}
    threading.Thread(target=_run_job, args=(jid, spec, dict(body)), daemon=True).start()
    return {"job_id": jid}


@router.get("/job")
def get_job(id: str = Query(..., max_length=40)) -> Dict[str, Any]:
    with _jlock: j = _jobs.get(id)
    if not j: raise HTTPException(status_code=404, detail={"code": "no_job"})
    return j


@router.post("/session")
def post_session(body: Dict[str, Any]) -> Dict[str, Any]:
    spec = _spec(body.get("key")); sid = str(body.get("session_id") or "")[:200]
    st = core.load_state(spec); st["session_id"] = sid; st["name_pl"] = spec["name_pl"]; core.save_state(st)
    return {"ok": True, "key": spec["key"], "session_id": sid}


@router.post("/render")
def post_render(body: Dict[str, Any]) -> Dict[str, Any]:
    key = str(body.get("key") or "")
    if key: key = _spec(key)["key"]
    he = body.get("happy_end"); he = True if he is None else bool(he)
    text = str(body.get("text") or "")[:200_000]
    ids = [str(i) for i in (body.get("ids") or [])][:10]
    lang = core.norm_lang(body.get("lang"))
    if ids: text = core.compose(ids, str(body.get("header") or ""), text, lang)
    out = core.render(text, he, key, lang=lang)
    try:
        if key and ids: out["exported"] = core.export_markdown(out["markdown"], core.resolve(key)["names"].get(lang) or key, lang)
    except Exception: pass
    at = body.get("search_at")
    if key and at:
        st = core.load_state(core.resolve(key))
        for e in st.get("searches", []):
            if abs(float(e.get("at", 0)) - float(at)) < 0.001:
                e["markdown"] = out["markdown"]; e["agent"] = bool(str(body.get("text") or "").strip())
        core.save_state(st)
    return out


@router.post("/reset")
def post_reset(body: Dict[str, Any]) -> Dict[str, Any]:
    return core.reset(_spec(body.get("key"))["key"])
