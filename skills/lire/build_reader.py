#!/usr/bin/env python3
"""Fabrique une page de lecture HTML autonome à partir de fichiers Markdown.

Usage : build_reader.py [--out DOSSIER] [--no-open] FICHIER.md [FICHIER.md ...]

La page embarque le texte des documents et la bibliothèque marked : elle
s'ouvre sans serveur et sans connexion. Par défaut elle est écrite dans
<dossier courant>/exports/lecture/, puis ouverte dans le navigateur.

La skill lire-ecouter importe build_html() pour servir la même page avec le
lecteur audio activé.
"""
import argparse
import datetime as dt
import json
import pathlib
import subprocess
import sys

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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+")
    parser.add_argument("--out", default=None)
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()

    docs, missing = load_docs(args.files)
    for m in missing:
        print(f"Fichier introuvable : {m}", file=sys.stderr)
    if not docs:
        return 1

    out_dir = pathlib.Path(args.out).expanduser() if args.out else pathlib.Path.cwd() / "exports" / "lecture"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"lecture-{dt.datetime.now().strftime('%Y-%m-%d-%H%M%S')}.html"
    out.write_text(build_html(docs), encoding="utf-8")
    print(out)

    if not args.no_open:
        subprocess.run(["open", str(out)], check=False)
    return 0 if not missing else 2


if __name__ == "__main__":
    sys.exit(main())
