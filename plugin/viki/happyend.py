"""Server-side happy-end checker for Viki titles (free: Hermes' configured web_search backend, no extra keys).

verdict(item) -> {"verdict": HAPPY|SAD|UNCERTAIN, "happy_sources":[{url,title,snippet}], "sad_sources":[...], ...}
HAPPY only if >=2 distinct domains support a happy ending and none clearly says sad/BE/bittersweet/open.
Cached per Viki id in data/happyend/<id>.json (TTL 180 days; UNCERTAIN 14 days).
"""
from __future__ import annotations
import json, re, subprocess, threading, time, urllib.parse
from pathlib import Path

BASE = Path(__file__).resolve().parent
DIR = BASE / "data" / "happyend"
TTL = {"HAPPY": 180 * 86400, "SAD": 180 * 86400, "UNCERTAIN": 14 * 86400}
_lock = threading.Semaphore(3)          # polite: max 3 concurrent searches
import os
HERMES_HOME = Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")
AGENT = os.environ.get("HERMES_AGENT_DIR") or str(HERMES_HOME / "hermes-agent")


def _hermes_python() -> str:
    """Interpreter of the Hermes install (only used when running outside a Hermes process, e.g. CLI)."""
    try:
        launcher = Path(AGENT) / ".hermes" / "bin" / "hermes"
        out = subprocess.run([str(launcher), "--print-runtime-command"], capture_output=True, text=True, timeout=30).stdout
        return json.loads(out)[0]
    except Exception:
        return "python3"

HAPPY = [r"\bhappy ending\b", r"\bhappily ever after\b", r"\bends? (?:on a )?happ(?:y|ily)\b", r"\bhappy note\b",
         r"\bsatisfying (?:and happy )?ending\b", r"\b(?:get|got|gets) married\b", r"\b(?:their|the couple'?s?) (?:own )?wedding\b", r"\bend up together\b",
         r"\bending (?:is|was) happy\b", r"\bHE\b(?! ?\w*man)", r"大结局.*(?:圆满|HE)", r"\bfinally together\b", r"\breunite[sd]?\b"]
SAD = [r"\bsad ending\b", r"\btragic ending\b", r"\bends? (?:in )?tragedy\b", r"\bbittersweet\b", r"\bopen[- ]ending\b",
       r"\bheartbreaking ending\b", r"\bdoes not end happily\b", r"\bdoesn'?t end happily\b", r"\bnot a happy ending\b",
       r"\bdies? (?:at|in) the end\b", r"\bBE\b", r"悲剧|虐结局", r"\bsad end\b", r"\bambiguous ending\b", r"\bunhappy ending\b", r"\bnever after\b",
       r"\bsad (?:conclusion|finale|note)\b", r"\bends? sadly\b", r"\btragic (?:conclusion|finale|outcome)s?\b"]
ENDCTX = re.compile(r"\b(ending|finale|final episode|last episode|ends|ended|concludes?|conclusion|happily ever after)\b|大结局", re.I)
SPEC = re.compile(r"\b(expect\w*|formula|episodes? \d+\s*[-–]\s*\d+|speculat\w*|theor(?:y|ies)|predict\w*|possible|might|could|mid-season|up to episode|first (?:few )?episodes|still airing|ongoing)\b", re.I)
NEG_Q = re.compile(r"(?:avoid\w*|no|without|instead of|rather than|isn'?t|not) (?:a |any |the )?(?:sad|tragic|bittersweet) end\w*|happy or (?:a )?sad|sad or (?:a )?happy|happy,? sad|is it happy|does .{0,40} have a happy", re.I)


def _search(q: str, limit: int = 8) -> list[dict]:
    with _lock:
        try:
            from tools import web_tools as w              # in-process (gateway / dashboard)
            raw = w.web_search_tool(q, limit=limit)
        except Exception:
            code = ("import os,sys,json; sys.path.insert(0,%r); sys._hermes_pin_default_home=True; import hermes_bootstrap; "
                    "from tools import web_tools as w; print(w.web_search_tool(sys.argv[1], limit=int(sys.argv[2])))") % AGENT
            raw = subprocess.run([_hermes_python(), "-I", "-c", code, q, str(limit)], capture_output=True, text=True, timeout=120).stdout
        time.sleep(0.5)
    try: d = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        m = re.search(r"\{.*\}", raw or "", re.S); d = json.loads(m.group(0)) if m else {}
    return ((d or {}).get("data") or {}).get("web") or []


def _dom(u: str) -> str:
    d = urllib.parse.urlparse(u).netloc.lower()
    d = re.sub(r"^(www|m|en|old)\.", "", d)
    parts = d.split(".")
    if len(parts) >= 3 and len(parts[-1]) == 2 and parts[-2] in ("co", "com", "org", "net", "gov", "ac"):
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def classify(text: str) -> str:
    t = NEG_Q.sub(" ", text)
    s = sum(bool(re.search(p, t, re.I if not p.startswith(r"\bBE") and not p.startswith(r"\bHE") else 0)) for p in SAD)
    h = sum(bool(re.search(p, t, re.I if not p.startswith(r"\bHE") else 0)) for p in HAPPY)
    if s and s >= h: return "sad"
    if h and not s and (SPEC.search(t) or not ENDCTX.search(t)): return "none"   # speculation/partial or not about the ending
    if h and not s: return "happy"
    return "mixed" if (h and s) else "none"


def check(cid: str, title: str, origin: str = "", year: str = "", force: bool = False) -> dict:
    DIR.mkdir(parents=True, exist_ok=True); p = DIR / f"{cid}.json"
    if not force and p.exists():
        try:
            c = json.loads(p.read_text())
            if time.time() - c.get("checked_at", 0) < TTL.get(c.get("verdict"), 0): return c
        except Exception: pass
    t0 = time.time(); kind = {"kr": "K-drama", "cn": "C-drama", "jp": "J-drama", "tw": "Taiwanese drama", "th": "Thai drama"}.get(origin, "drama")
    queries = [f'"{title}" {kind} ending explained happy or sad', f'"{title}" {kind} finale ending reddit mydramalist']
    seen, hs, ss = set(), {}, {}
    for q in queries:
        for r in _search(q):
            u = r.get("url") or ""; txt = f"{r.get('title','')} {r.get('description','')}"
            if not u or u in seen: continue
            seen.add(u)
            if not re.search(re.escape(title.split(":")[0][:25]), txt, re.I) and title.lower() not in u.lower().replace("-", " "):
                continue                                              # result not about this title
            c = classify(txt); d = _dom(u)
            src = {"url": u, "title": r.get("title", "")[:200], "snippet": r.get("description", "")[:400], "domain": d}
            if c == "happy": hs.setdefault(d, src)
            elif c in ("sad", "mixed"): ss.setdefault(d, src)
        v1 = "HAPPY" if len(hs) >= 2 and (not ss or (len(ss) == 1 and len(hs) >= 4)) else ("SAD" if len(ss) >= 2 and len(ss) >= len(hs) else "UNCERTAIN")
        if v1 != "UNCERTAIN": queries = queries[:1]; break          # second query only when the first is UNCERTAIN
    # HAPPY: >=2 distinct domains say happy and no real dissent (a single dissenting site is tolerated only
    # against an overwhelming majority of >=4 happy domains)
    v = "HAPPY" if len(hs) >= 2 and (not ss or (len(ss) == 1 and len(hs) >= 4)) else ("SAD" if len(ss) >= 2 and len(ss) >= len(hs) else "UNCERTAIN")
    out = {"id": cid, "title": title, "verdict": v, "happy_sources": list(hs.values()), "sad_sources": list(ss.values()),
           "queries": queries, "results_seen": len(seen), "checked_at": time.time(), "seconds": round(time.time() - t0, 1),
           "method": "Hermes web_search backend (web.backend) + keyword classifier; HAPPY = >=2 distinct domains happy and 0 sad (or 1 sad vs >=4 happy)"}
    tmp = p.with_suffix(".tmp"); tmp.write_text(json.dumps(out, ensure_ascii=False, indent=1)); tmp.replace(p)
    return out


def cached(cid: str) -> dict | None:
    p = DIR / f"{cid}.json"
    try: return json.loads(p.read_text())
    except Exception: return None
