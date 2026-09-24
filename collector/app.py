from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import unicodedata

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse


DB = Path(os.environ.get("KANZI_ANNOTATION_DB", Path(__file__).parent / "annotations.db"))
MAX_PAGE_SIZE = 200
MAX_REQUEST_BYTES = 2_000_000
MAX_BATCH_SIZE = 5_000

app = FastAPI(title="Kanzi Annotation Collector")


def _normalise(text: str) -> str:
    value = unicodedata.normalize("NFKC", text or "").lower()
    value = re.sub(r"-\s*\n\s*", "", value)
    value = re.sub(r"[\u2010-\u2015\u2018\u2019\u201c\u201d]", "'", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _hash_norm(text: str) -> str:
    return hashlib.sha256(_normalise(text).encode()).hexdigest()[:16]


def _fuzzy_hash(text: str) -> str:
    norm = _normalise(text)
    if len(norm) < 3:
        return _hash_norm(text)
    trigrams = {norm[index : index + 3] for index in range(len(norm) - 2)}
    words = sorted(norm.split())
    word_trigrams = {
        " ".join(words[index : index + 3])
        for index in range(max(1, len(words) - 2))
    }
    return hashlib.sha256(" ".join(sorted(trigrams | word_trigrams)).encode()).hexdigest()[:16]


def _connect() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 5000")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def init_db() -> None:
    with _connect() as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS highlights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                anon_id TEXT,
                citation_key TEXT,
                doi TEXT,
                isbn TEXT,
                issn TEXT,
                publication_title TEXT,
                clipping_id_hash TEXT,
                norm_hash TEXT,
                fuzzy_hash TEXT,
                text TEXT,
                color TEXT,
                has_comment INTEGER,
                comment TEXT,
                comment_hash TEXT,
                clipping_added_on_iso TEXT,
                integrated_at TEXT,
                received_at TEXT,
                raw TEXT
            )"""
        )
        existing_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(highlights)")
        }
        required_columns = {
            "doi": "TEXT",
            "isbn": "TEXT",
            "issn": "TEXT",
            "publication_title": "TEXT",
            "clipping_id_hash": "TEXT",
            "norm_hash": "TEXT",
            "fuzzy_hash": "TEXT",
            "text": "TEXT",
            "comment": "TEXT",
            "comment_hash": "TEXT",
            "clipping_added_on_iso": "TEXT",
            "integrated_at": "TEXT",
            "received_at": "TEXT",
            "raw": "TEXT",
        }
        for name, column_type in required_columns.items():
            if name not in existing_columns:
                connection.execute(f"ALTER TABLE highlights ADD COLUMN {name} {column_type}")
        connection.execute(
            """CREATE TABLE IF NOT EXISTS raw_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                anon_id TEXT,
                received_at TEXT,
                body TEXT
            )"""
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS installations (
                anon_id TEXT PRIMARY KEY,
                token_hash TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL
            )"""
        )
        # Older collector versions appended every retry. Retain only the newest
        # record for each installation/clipping before enforcing idempotency.
        connection.execute(
            """DELETE FROM highlights
               WHERE clipping_id_hash IS NOT NULL
                 AND id NOT IN (
                     SELECT MAX(id) FROM highlights
                     WHERE clipping_id_hash IS NOT NULL
                     GROUP BY anon_id, clipping_id_hash
                 )"""
        )
        connection.execute(
            """CREATE UNIQUE INDEX IF NOT EXISTS highlights_identity
               ON highlights(anon_id, clipping_id_hash)
               WHERE clipping_id_hash IS NOT NULL"""
        )


init_db()


HTML = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Kanzi annotations</title>
<style>
:root{font-family:'iA Writer Duo','JetBrains Mono',ui-monospace,monospace;color:#111;background:#f8f8f8;--panel:#fff;--soft:#f0f0f0;--line:#ddd;--muted:#666;--radius:8px}*{box-sizing:border-box}body{margin:0}main{max-width:1280px;margin:auto;padding:20px 24px}h1{margin:0 0 4px;font-size:28px}h2{font-size:16px;border-bottom:1px solid var(--line);padding-bottom:6px;margin-top:24px}.muted{color:var(--muted);font-size:12px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:16px 0}.card,table{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius)}.card{padding:14px}.card strong{display:block;font-size:22px}table{width:100%;border-collapse:collapse;table-layout:fixed;overflow:hidden}th,td{padding:9px 10px;border-bottom:1px solid var(--line);text-align:left;overflow-wrap:anywhere;font-size:12px}th{background:var(--soft);color:var(--muted);font-size:10px;text-transform:uppercase}.pager{display:flex;justify-content:flex-end;align-items:center;gap:8px;margin:10px 0}.pager button{padding:5px 9px;border:1px solid var(--line);border-radius:var(--radius);background:var(--panel)}.pager button:disabled{color:#999}@media(max-width:700px){main{padding:14px 10px}.table-wrap{overflow-x:auto}table{min-width:800px}}
</style></head><body><main><h1>Kanzi annotations</h1><div class="muted">Private pseudonymous collector. Raw highlight text and comments are stored.</div>
<div class="grid"><div class="card"><strong id="total">-</strong><span>highlights</span></div><div class="card"><strong id="uniq">-</strong><span>citekeys</span></div><div class="card"><strong id="anons">-</strong><span>installations</span></div><div class="card"><strong id="today">-</strong><span>received today</span></div></div>
<h2>Recent</h2><div class="table-wrap"><table><thead><tr><th>anon</th><th>citekey</th><th>DOI / ISBN</th><th>text</th><th>colour</th><th>received</th></tr></thead><tbody id="recent"></tbody></table></div><div class="pager" id="recent-pager"></div>
<h2>Top citekeys</h2><div class="table-wrap"><table><thead><tr><th>citekey</th><th>count</th></tr></thead><tbody id="top"></tbody></table></div>
<h2>Common highlights</h2><div class="muted">Same publication and normalised text across at least two installations.</div><div class="table-wrap"><table><thead><tr><th>DOI / ISBN</th><th>text</th><th>norm</th><th>installations</th><th>citekeys</th></tr></thead><tbody id="common"></tbody></table></div><div class="pager" id="common-pager"></div>
<script>
const size=50,state={recent:0,common:0};
function cell(row,value){const td=document.createElement('td');td.textContent=value??'';row.appendChild(td);return td}
function empty(body,span,message){body.textContent='';const row=body.insertRow();const td=cell(row,message);td.colSpan=span;td.className='muted'}
function pager(id,key,count,load){const root=document.getElementById(id);root.textContent='';const pages=Math.max(1,Math.ceil(count/size));state[key]=Math.min(state[key],pages-1);const prev=document.createElement('button');prev.textContent='Previous';prev.disabled=state[key]===0;prev.onclick=()=>{state[key]--;load()};root.append(prev);const text=document.createElement('span');text.textContent=`Page ${state[key]+1} of ${pages}`;root.append(text);const next=document.createElement('button');next.textContent='Next';next.disabled=state[key]>=pages-1;next.onclick=()=>{state[key]++;load()};root.append(next)}
async function loadRecent(){const result=await fetch(`/recent?limit=${size}&offset=${state.recent*size}`).then(r=>r.json());const body=document.getElementById('recent');body.textContent='';for(const h of result.recent){const row=body.insertRow();cell(row,(h.anon_id||'').slice(0,8));cell(row,h.citation_key);cell(row,h.doi||h.isbn);cell(row,(h.text||'').slice(0,180));cell(row,h.color);cell(row,(h.received_at||'').slice(0,16).replace('T',' '))}if(!result.recent.length)empty(body,6,'No data');pager('recent-pager','recent',result.total,loadRecent)}
async function loadCommon(){const result=await fetch(`/common?limit=${size}&offset=${state.common*size}`).then(r=>r.json());const body=document.getElementById('common');body.textContent='';for(const h of result.common){const row=body.insertRow();cell(row,h.publication);cell(row,(h.example_text||'').slice(0,180));cell(row,h.norm_hash);cell(row,h.installations);cell(row,h.citekeys)}if(!result.common.length)empty(body,5,'No common highlights yet');pager('common-pager','common',result.total,loadCommon)}
async function load(){const stats=await fetch('/stats').then(r=>r.json());for(const [id,key] of [['total','total_highlights'],['uniq','unique_citekeys'],['anons','unique_anons'],['today','today']])document.getElementById(id).textContent=stats[key];const top=await fetch('/top').then(r=>r.json());const body=document.getElementById('top');body.textContent='';for(const h of top.top){const row=body.insertRow();cell(row,h.citation_key);cell(row,h.count)}await Promise.all([loadRecent(),loadCommon()])}load();
</script></main></body></html>"""


@app.get("/", response_class=HTMLResponse)
def root() -> str:
    return HTML


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@app.post("/register")
def register() -> dict[str, str]:
    token = secrets.token_urlsafe(32)
    anon_id = secrets.token_hex(16)
    with _connect() as connection:
        connection.execute(
            "INSERT INTO installations (anon_id, token_hash, created_at) VALUES (?, ?, ?)",
            (anon_id, _token_hash(token), datetime.now(timezone.utc).isoformat()),
        )
    return {"anonId": anon_id, "token": token}


def _authenticated_anon_id(request: Request) -> str:
    authorization = request.headers.get("authorization", "")
    scheme, separator, token = authorization.partition(" ")
    if not separator or scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Missing collector credential")
    with _connect() as connection:
        row = connection.execute(
            "SELECT anon_id FROM installations WHERE token_hash = ?",
            (_token_hash(token),),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="Invalid collector credential")
    return str(row["anon_id"])


@app.get("/stats")
def stats() -> dict[str, int]:
    today = datetime.now(timezone.utc).date().isoformat()
    with _connect() as connection:
        row = connection.execute(
            """SELECT COUNT(*) AS total_highlights,
                      COUNT(DISTINCT citation_key) AS unique_citekeys,
                      COUNT(DISTINCT anon_id) AS unique_anons,
                      SUM(CASE WHEN substr(received_at, 1, 10) = ? THEN 1 ELSE 0 END) AS today
               FROM highlights""",
            (today,),
        ).fetchone()
    return {key: int(row[key] or 0) for key in row.keys()}


@app.get("/recent")
def recent(limit: int = 50, offset: int = 0) -> dict:
    limit = max(1, min(limit, MAX_PAGE_SIZE))
    offset = max(0, offset)
    with _connect() as connection:
        total = connection.execute("SELECT COUNT(*) FROM highlights").fetchone()[0]
        rows = connection.execute(
            """SELECT anon_id, citation_key, doi, isbn, text, clipping_id_hash,
                      norm_hash, fuzzy_hash, color, has_comment, received_at
               FROM highlights ORDER BY id DESC LIMIT ? OFFSET ?""",
            (limit, offset),
        ).fetchall()
    return {"recent": [dict(row) for row in rows], "total": total}


@app.get("/top")
def top(limit: int = 20) -> dict:
    limit = max(1, min(limit, 100))
    with _connect() as connection:
        rows = connection.execute(
            """SELECT citation_key, COUNT(*) AS count FROM highlights
               WHERE citation_key IS NOT NULL AND citation_key != ''
               GROUP BY citation_key ORDER BY count DESC, citation_key LIMIT ?""",
            (limit,),
        ).fetchall()
    return {"top": [dict(row) for row in rows]}


@app.get("/common")
def common(limit: int = 50, offset: int = 0) -> dict:
    limit = max(1, min(limit, MAX_PAGE_SIZE))
    offset = max(0, offset)
    group_sql = """FROM highlights
        WHERE norm_hash IS NOT NULL AND norm_hash != ''
          AND COALESCE(NULLIF(doi, ''), NULLIF(isbn, ''), NULLIF(citation_key, '')) IS NOT NULL
        GROUP BY COALESCE(NULLIF(doi, ''), NULLIF(isbn, ''), citation_key), norm_hash
        HAVING COUNT(DISTINCT anon_id) > 1"""
    with _connect() as connection:
        total = connection.execute(f"SELECT COUNT(*) FROM (SELECT 1 {group_sql})").fetchone()[0]
        rows = connection.execute(
            f"""SELECT COALESCE(NULLIF(doi, ''), NULLIF(isbn, ''), citation_key) AS publication,
                       norm_hash, COUNT(DISTINCT anon_id) AS installations,
                       GROUP_CONCAT(DISTINCT citation_key) AS citekeys,
                       MAX(text) AS example_text
                {group_sql}
                ORDER BY installations DESC, publication, norm_hash LIMIT ? OFFSET ?""",
            (limit, offset),
        ).fetchall()
    return {"common": [dict(row) for row in rows], "total": total}


@app.post("/highlights")
async def post_highlights(request: Request) -> dict:
    anon = _authenticated_anon_id(request)
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_REQUEST_BYTES:
                raise HTTPException(status_code=413, detail="Request body is too large")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid Content-Length")
    body = await request.body()
    if len(body) > MAX_REQUEST_BYTES:
        raise HTTPException(status_code=413, detail="Request body is too large")
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise HTTPException(status_code=400, detail="Invalid JSON") from error
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Payload must be an object")
    highlights = payload.get("data") or payload.get("highlights") or []
    if isinstance(highlights, dict):
        highlights = [highlights]
    if not isinstance(highlights, list):
        raise HTTPException(status_code=422, detail="data must be a list")
    if len(highlights) > MAX_BATCH_SIZE:
        raise HTTPException(status_code=413, detail="Too many highlights in one request")
    now = datetime.now(timezone.utc).isoformat()
    inserted = updated = 0
    with _connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        for highlight in highlights:
            if not isinstance(highlight, dict):
                continue
            text = str(highlight.get("text") or "")[:2000]
            clipping_hash = str(highlight.get("clipping_id_hash") or "")[:128] or None
            values = (
                anon,
                str(highlight.get("citation_key") or "")[:512] or None,
                str(highlight.get("doi") or "")[:512] or None,
                str(highlight.get("isbn") or "")[:512] or None,
                str(highlight.get("issn") or "")[:512] or None,
                str(highlight.get("publication_title") or "")[:1000] or None,
                clipping_hash,
                highlight.get("norm_hash") or _hash_norm(text),
                highlight.get("fuzzy_hash") or _fuzzy_hash(text),
                text,
                str(highlight.get("color") or "")[:32] or None,
                1 if highlight.get("has_comment") else 0,
                str(highlight.get("comment") or "")[:2000],
                str(highlight.get("comment_hash") or "")[:256] or None,
                str(highlight.get("clipping_added_on_iso") or "")[:64] or None,
                str(highlight.get("integrated_at") or "")[:64] or None,
                now,
                json.dumps(highlight, ensure_ascii=False)[:8000],
            )
            existing = None
            if clipping_hash:
                legacy_hash = clipping_hash[:8]
                existing = connection.execute(
                    """SELECT id FROM highlights
                       WHERE anon_id = ? AND clipping_id_hash IN (?, ?)
                       ORDER BY clipping_id_hash = ? DESC LIMIT 1""",
                    (anon, clipping_hash, legacy_hash, clipping_hash),
                ).fetchone()
            if existing:
                connection.execute(
                    """UPDATE highlights SET citation_key=?, doi=?, isbn=?, issn=?, publication_title=?, clipping_id_hash=?,
                           norm_hash=?, fuzzy_hash=?, text=?, color=?, has_comment=?, comment=?, comment_hash=?,
                           clipping_added_on_iso=?, integrated_at=?, received_at=?, raw=? WHERE id=?""",
                    (*values[1:7], *values[7:], existing["id"]),
                )
                updated += 1
            else:
                connection.execute(
                    """INSERT INTO highlights (
                           anon_id, citation_key, doi, isbn, issn, publication_title, clipping_id_hash,
                           norm_hash, fuzzy_hash, text, color, has_comment, comment, comment_hash,
                           clipping_added_on_iso, integrated_at, received_at, raw
                       ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    values,
                )
                inserted += 1
    return {
        "status": "ok",
        "received": len(highlights),
        "inserted": inserted,
        "updated": updated,
        "anon": anon,
    }
