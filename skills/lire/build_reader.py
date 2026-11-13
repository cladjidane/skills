#!/usr/bin/env python3
"""Assemble la page de lecture : le modèle reader.html, la bibliothèque marked et les documents.

reader_server.py importe ces fonctions et sert la page. La page a besoin de ce programme pour
enregistrer les remarques : elle ne s'utilise plus comme simple fichier ouvert dans le navigateur.
"""
import datetime as dt
import json
import pathlib

SKILL_DIR = pathlib.Path(__file__).resolve().parent
TEMPLATE = SKILL_DIR / "reader.html"
MARKED = SKILL_DIR / "vendor" / "marked.min.js"


def load_docs(files):
    """Lit les fichiers. Renvoie (documents, chemins introuvables)."""
    docs, missing = [], []
    for raw in files:
        path = pathlib.Path(raw).expanduser().resolve()
        if not path.is_file():
            missing.append(str(path))
            continue
        mtime = dt.datetime.fromtimestamp(path.stat().st_mtime)
        docs.append({
            "path": str(path),
            "name": path.name,
            "folder": str(path.parent),
            "modified": mtime.strftime("%d/%m/%Y à %H:%M"),
            "content": path.read_text(encoding="utf-8"),
        })
    return docs, missing


def build_html(docs, listen=None):
    """Assemble la page. listen vaut None pour la lecture seule, ou un dict pour activer l'écoute."""
    def embed(value):
        return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")

    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace("/*__MARKED__*/", MARKED.read_text(encoding="utf-8"))
    html = html.replace("__DOCS_JSON__", embed(docs))
    html = html.replace("__LISTEN_JSON__", embed(listen))
    return html
