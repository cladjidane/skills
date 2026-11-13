#!/usr/bin/env python3
"""Sert la page de lecture des skills lire et lire-ecouter, et garde l'état de lecture.

Usage : reader_server.py [--listen] [--project DOSSIER] [--env-file FICHIER] [--port N] [--no-open] FICHIER.md ...

Le programme tourne sur la machine de l'utilisateur pendant la lecture. Il sert la page, et il
écrit les remarques dans <projet>/exports/lecture/reading-state.json (voir reading_state.py).
Ce fichier garde aussi la version de chaque document relue en dernier : la page affiche si un
document est nouveau, modifié ou inchangé, et surligne les passages changés.

Avec --listen, la page gagne un lecteur audio chapitré. Un chapitre est réécrit pour l'oral avec
Mistral, puis chaque morceau est dit par Voxtral, seulement quand l'utilisateur clique sur ▶.
Les textes réécrits et les sons sont gardés en cache : réécouter ne coûte rien. Sans clé Mistral,
la page lit le texte nettoyé avec la voix du navigateur.

La clé est cherchée dans la variable d'environnement MISTRAL_API_KEY, puis dans le fichier
donné par --env-file, puis dans ~/.config/fc/env. Elle n'est jamais envoyée à la page.

Le programme s'arrête seul après IDLE_MINUTES minutes sans demande de la page.
"""
import argparse
import hashlib
import http.server
import json
import os
import pathlib
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

SKILL_DIR = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(SKILL_DIR))
from build_reader import build_html, load_docs  # noqa: E402
import reading_state as rs  # noqa: E402

CACHE_DIR = pathlib.Path.home() / ".cache" / "fc-lire-ecouter"
DEFAULT_ENV_FILE = pathlib.Path.home() / ".config" / "fc" / "env"
IDLE_MINUTES = 45
CHUNK_CHARS = 600
TTS_MODEL = "voxtral-mini-tts-2603"
PRICE_PER_MILLION_CHARS = 16.0  # dollars, prix Voxtral publié en 2026, à vérifier sur mistral.ai/pricing
CHAT_MODELS = ["mistral-medium-latest", "mistral-small-latest", "ministral-8b-latest"]
DEFAULT_VOICE_NAME = "Marie - Neutral"

SPOKEN_PROMPT = """Tu reçois une partie d'un document Markdown. Prépare-la pour qu'elle soit écoutée.

Le texte que tu rends est lu tel quel par une voix de synthèse. L'auditeur connaît le document écrit : il doit entendre les mêmes phrases, dans le même ordre.

Règles :
- Recopie les phrases du document mot pour mot. Une phrase lisible à voix haute ne change pas.
- Une citation entre guillemets se recopie mot pour mot, même si elle est mal écrite.
- Garde chaque fait, chaque chiffre, chaque date et chaque nom. N'ajoute aucun mot d'introduction, de liaison ou de conclusion.
- Le titre de la partie se dit seul, en première ligne, sans son numéro de liste.
- Un élément d'une liste à puces devient une phrase complète : ajoute le sujet de la liste et garde les mots de l'élément. Exemple : sous « La formatrice : », l'élément « choisit les exemples » devient « La formatrice choisit les exemples. »
- Un chemin de fichier, une commande, un nom de variable ou un bout de code se remplace par trois à cinq mots qui disent de quoi il s'agit, ou disparaît s'il n'apporte rien à l'oral.
- Une mention entre crochets, comme une date ou une étiquette, disparaît.
- Un tableau se dit ligne par ligne, en phrases qui reprennent les mots des cases.
- Une liste de références, de sources ou de liens ne se lit pas : dis en une phrase combien il y en a.
- Aucun signe de mise en forme : pas d'astérisque, pas de dièse, pas de tiret en début de ligne.

Réponds uniquement avec le texte à dire, en paragraphes séparés par une ligne vide."""

STATE = {"last_request": time.time()}


# ---------- Clé et appels à Mistral ----------

def find_api_key(env_file):
    key = os.environ.get("MISTRAL_API_KEY")
    if key:
        return key.strip()
    for candidate in [env_file, DEFAULT_ENV_FILE]:
        if candidate and pathlib.Path(candidate).expanduser().is_file():
            for line in pathlib.Path(candidate).expanduser().read_text(encoding="utf-8").splitlines():
                m = re.match(r"\s*(?:export\s+)?MISTRAL_API_KEY\s*=\s*(.*)$", line)
                if m:
                    return m.group(1).strip().strip("\"'")
    return None


def mistral(path, payload, key, timeout=180):
    req = urllib.request.Request(
        "https://api.mistral.ai/v1/" + path,
        data=json.dumps(payload).encode(),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def list_french_voices(key):
    try:
        req = urllib.request.Request("https://api.mistral.ai/v1/audio/voices?limit=100",
                                     headers={"Authorization": "Bearer " + key})
        with urllib.request.urlopen(req, timeout=20) as resp:
            items = json.load(resp).get("items", [])
    except (urllib.error.URLError, TimeoutError, ValueError):
        return []
    voices = [{"id": v["id"], "name": v["name"]} for v in items
              if any(lang.startswith("fr") for lang in v.get("languages", []))]
    voices.sort(key=lambda v: (v["name"] != DEFAULT_VOICE_NAME, v["name"]))
    return voices


# ---------- Préparation du texte ----------

def clean_markdown(md):
    """Nettoyage sans IA : retire ce qui ne se prononce pas."""
    text = re.sub(r"```[\s\S]*?```", " ", md)
    text = re.sub(r"^\s*\|.*\|\s*$", " ", text, flags=re.M)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"(?:~|/[A-Za-z0-9_.-]+)(?:/[^\s`)]+)+/?", lambda m: m.group(0).rstrip("/").split("/")[-1], text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"^#{1,6}\s+(.*)$", r"\1.", text, flags=re.M)
    text = re.sub(r"(\*\*|__)(.+?)\1", r"\2", text)
    text = re.sub(r"(?<!\w)[*_](.+?)[*_](?!\w)", r"\1", text)
    text = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", text, flags=re.M)
    text = re.sub(r"^\s*>\s?", "", text, flags=re.M)
    text = re.sub(r"^\s*-{3,}\s*$", " ", text, flags=re.M)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def rewrite_for_speech(md, key):
    """Réécriture par Mistral. Renvoie (texte, modèle) ou (None, raison de l'échec)."""
    last_error = "aucun modèle"
    # Mistral répond 429 quand les demandes arrivent trop vite : on attend avant chaque nouvel essai.
    attempts = [(m, wait) for m in CHAT_MODELS for wait in (0, 4)]
    for model, wait in attempts:
        time.sleep(wait)
        try:
            data = mistral("chat/completions", {
                "model": model, "temperature": 0.1,
                "messages": [{"role": "system", "content": SPOKEN_PROMPT}, {"role": "user", "content": md}],
            }, key)
            text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()
            if text:
                text = re.sub(r"(\*\*|__|\*|`)", "", text)
                text = re.sub(r"^\s*(#{1,6}|[-•])\s+", "", text, flags=re.M)
                return text, model
            last_error = f"{model} a répondu sans texte"
        except urllib.error.HTTPError as e:
            last_error = f"{model} : erreur {e.code}"
            if e.code not in (429, 503):
                break
        except (urllib.error.URLError, TimeoutError) as e:
            last_error = f"{model} : {e}"
    return None, last_error


def split_for_speech(text, max_chars=CHUNK_CHARS):
    """Découpe en morceaux d'au plus max_chars caractères, sur les paragraphes puis les phrases."""
    pieces = []
    for para in [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]:
        if len(para) <= max_chars:
            pieces.append(para)
            continue
        buf = ""
        for sentence in re.split(r"(?<=[.!?…])\s+", para):
            if buf and len(buf) + 1 + len(sentence) > max_chars:
                pieces.append(buf)
                buf = sentence
            else:
                buf = f"{buf} {sentence}" if buf else sentence
        if buf:
            pieces.append(buf)
    merged = []
    for piece in pieces:
        if merged and len(merged[-1]) + 2 + len(piece) <= max_chars:
            merged[-1] += "\n\n" + piece
        else:
            merged.append(piece)
    return merged


def cache_path(kind, *parts, suffix):
    digest = hashlib.sha1("|".join(parts).encode()).hexdigest()[:20]
    folder = CACHE_DIR / kind
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{digest}{suffix}"


def strip_heading_numbers(md):
    """« ## 4. Les règles » devient « ## Les règles » : ajouter une partie avant celle-ci ne
    change plus son texte, et sa version déjà réécrite et dite reste dans le cache."""
    return re.sub(r"^(#{1,6})\s+(?:\d+(?:\.\d+)*[.)]?|[IVXLC]+\.)\s+", r"\1 ", md, flags=re.M)


def prepare(md, key):
    md = strip_heading_numbers(md)
    mode = "rewrite" if key else "clean"
    cached = cache_path("text", mode, SPOKEN_PROMPT if key else "", md, suffix=".json")
    if cached.exists():
        return json.loads(cached.read_text(encoding="utf-8"))
    note = None
    if key:
        text, info = rewrite_for_speech(md, key)
        if text is None:
            text, mode, note = clean_markdown(md), "clean", f"Réécriture indisponible ({info}) : texte nettoyé lu tel quel."
    else:
        text = clean_markdown(md)
    result = {"chunks": split_for_speech(text), "mode": mode, "note": note}
    if note is None:
        cached.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return result


def synthesize(text, voice_id, key):
    """Renvoie (son mp3, venu du cache ou non)."""
    cached = cache_path("audio", TTS_MODEL, voice_id, text, suffix=".mp3")
    if cached.exists():
        return cached.read_bytes(), True
    import base64
    data = mistral("audio/speech", {"model": TTS_MODEL, "input": text,
                                    "voice_id": voice_id, "response_format": "mp3"}, key, timeout=120)
    audio = base64.b64decode(data["audio_data"])
    cached.write_bytes(audio)
    return audio, False


# ---------- Serveur ----------

def page_state(project, docs):
    """État envoyé à la page : pour chaque document, son état, la version relue et ses remarques."""
    with rs.locked_state(project) as state:
        result = {}
        for d in docs:
            entry = rs.doc_entry(state, d["path"])
            status, baseline = rs.doc_status(entry, d["content"])
            result[d["path"]] = {
                "status": status, "baseline": baseline,
                "reviewedAt": (entry.get("reviewed") or {}).get("at"),
                "remarks": entry["remarks"],
            }
    return result


def make_handler(html, key, voices, project, docs):
    contents = {d["path"]: d["content"] for d in docs}

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, code, body, ctype, extra=None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def send_json(self, code, obj):
            self.send(code, json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8")

        def do_GET(self):
            STATE["last_request"] = time.time()
            if self.path in ("/", "/index.html"):
                self.send(200, html.encode(), "text/html; charset=utf-8")
            elif self.path == "/api/ping":
                self.send_json(200, {"ok": True})
            elif self.path == "/api/state":
                self.send_json(200, page_state(project, docs))
            else:
                self.send_json(404, {"error": "introuvable"})

        def do_POST(self):
            STATE["last_request"] = time.time()
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length) or b"{}")
                if self.path == "/api/remark":
                    if payload.get("doc") not in contents:
                        self.send_json(400, {"error": "document inconnu"})
                        return
                    with rs.locked_state(project) as state:
                        remark = rs.apply_op(state, payload)
                    self.send_json(200, {"remark": remark})
                elif self.path == "/api/reviewed":
                    # payload.docs : chemins des documents dont la version affichée devient la version relue
                    with rs.locked_state(project) as state:
                        for path in payload.get("docs", []):
                            if path in contents:
                                rs.mark_reviewed(rs.doc_entry(state, path), contents[path])
                    self.send_json(200, page_state(project, docs))
                elif self.path == "/api/prepare":
                    self.send_json(200, prepare(payload["markdown"], key))
                elif self.path == "/api/audio":
                    if listen_off:
                        self.send_json(404, {"error": "écoute non activée"})
                        return
                    if not key:
                        self.send_json(400, {"error": "Pas de clé Mistral : la voix du navigateur est utilisée."})
                        return
                    voice = payload.get("voice") or (voices[0]["id"] if voices else "")
                    audio, from_cache = synthesize(payload["text"], voice, key)
                    self.send(200, audio, "audio/mpeg", {"X-From-Cache": "1" if from_cache else "0"})
                else:
                    self.send_json(404, {"error": "introuvable"})
            except urllib.error.HTTPError as e:
                self.send_json(502, {"error": f"Mistral a répondu par l'erreur {e.code}."})
            except Exception as e:  # la page affiche le message à l'utilisateur
                self.send_json(500, {"error": f"{type(e).__name__} : {e}"})

    listen_off = voices is None
    return Handler


def free_port(preferred):
    for port in [preferred] + list(range(preferred + 1, preferred + 50)):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise SystemExit("Aucun port libre trouvé.")


def watch_idle(server):
    while True:
        time.sleep(30)
        if time.time() - STATE["last_request"] > IDLE_MINUTES * 60:
            server.shutdown()
            return


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+")
    parser.add_argument("--env-file", default=None)
    parser.add_argument("--port", type=int, default=8780)  # le premier port libre à partir de celui-ci
    parser.add_argument("--no-open", action="store_true")
    parser.add_argument("--listen", action="store_true")
    parser.add_argument("--project", default=".")
    args = parser.parse_args()

    docs, missing = load_docs(args.files)
    for m in missing:
        print(f"Fichier introuvable : {m}", file=sys.stderr)
    if not docs:
        return 1

    project = str(pathlib.Path(args.project).expanduser().resolve())
    page_state(project, docs)  # crée le fichier d'état et y inscrit les documents

    key = find_api_key(args.env_file) if args.listen else None
    voices = list_french_voices(key) if key else []
    listen = None if not args.listen else {
        "engine": "voxtral" if key and voices else "browser",
        "voices": voices,
        "pricePerMillion": PRICE_PER_MILLION_CHARS,
        "idleMinutes": IDLE_MINUTES,
    }
    if args.listen and key and not voices:
        print("Clé Mistral trouvée, mais la liste des voix est inaccessible : voix du navigateur.", file=sys.stderr)
    html = build_html(docs, listen)

    port = free_port(args.port)
    handler = make_handler(html, key if voices else None, voices if args.listen else None, project, docs)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=watch_idle, args=(server,), daemon=True).start()
    url = f"http://127.0.0.1:{port}/"
    if listen:
        engine = "voix : Voxtral (Mistral)" if listen["engine"] == "voxtral" else "voix : navigateur"
    else:
        engine = "lecture seule, sans écoute"
    print(f"{url}  |  {len(docs)} document(s)  |  {engine}  |  arrêt après {IDLE_MINUTES} min sans activité"
          f"  |  état : {rs.state_path(project)}", flush=True)
    if not args.no_open:
        subprocess.run(["open", url], check=False)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
