#!/usr/bin/env python3
"""État de lecture d'un projet : versions lues des documents, remarques, réponses de Claude.

Le fichier vit dans <projet>/exports/lecture/reading-state.json. La page de lecture l'écrit
à travers reader_server.py ; Claude le lit et y répond avec les commandes ci-dessous.

  reading_state.py remarks [--all] [--project DOSSIER]
      affiche les remarques ouvertes, au même format que le bouton « Copier pour Claude »
  reading_state.py reply NUMÉRO "texte" [--project DOSSIER]
      écrit la réponse de Claude sous la remarque (le numéro est celui affiché, par exemple R3)
  reading_state.py status [--project DOSSIER]
      affiche l'état de chaque document suivi : nouveau, modifié ou inchangé

Le fichier est verrouillé pendant chaque écriture : la page et Claude peuvent l'écrire en même
temps sans perdre de remarque.

Un document a trois états, comparés à la version que l'utilisateur a relue en dernier :
  new        jamais relu ;
  modified   relu, puis modifié depuis ;
  unchanged  identique à la version relue.
Une version est marquée relue quand l'utilisateur copie ses remarques pour Claude, quand Claude
lit les remarques avec la commande remarks, ou quand l'utilisateur clique sur « Marquer comme relu ».
"""
import argparse
import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import pathlib
import sys

STATE_NAME = "reading-state.json"


def state_path(project):
    return pathlib.Path(project).expanduser().resolve() / "exports" / "lecture" / STATE_NAME


def content_hash(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def now():
    return dt.datetime.now().isoformat(timespec="seconds")


@contextlib.contextmanager
def locked_state(project):
    """Ouvre l'état sous verrou, le rend modifiable, puis l'écrit à la sortie du bloc."""
    path = state_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_suffix(".lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        state.setdefault("version", 1)
        state.setdefault("next_number", 1)
        state.setdefault("documents", {})
        yield state
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(path)


def read_state(project):
    path = state_path(project)
    if not path.exists():
        return {"version": 1, "next_number": 1, "documents": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def doc_entry(state, doc_path):
    return state["documents"].setdefault(doc_path, {"reviewed": None, "snapshots": {}, "remarks": []})


def doc_status(entry, content):
    """Renvoie (état, texte de la version relue ou None)."""
    reviewed = entry.get("reviewed")
    if not reviewed:
        return "new", None
    if reviewed["hash"] == content_hash(content):
        return "unchanged", None
    return "modified", entry["snapshots"].get(reviewed["hash"])


def mark_reviewed(entry, content):
    h = content_hash(content)
    entry["reviewed"] = {"hash": h, "at": now()}
    # On ne garde que la version relue : c'est la seule qui sert de point de comparaison.
    entry["snapshots"] = {h: content}


# ---------- Opérations envoyées par la page ----------

def apply_op(state, op):
    entry = doc_entry(state, op["doc"])
    remarks = entry["remarks"]
    kind = op["op"]
    if kind == "add":
        remark = dict(op["remark"])
        remark["number"] = f"R{state['next_number']}"
        state["next_number"] += 1
        remark.setdefault("status", "open")
        remark.setdefault("reply", None)
        remarks.append(remark)
        return remark
    if kind == "update":
        for r in remarks:
            if r["id"] == op["id"]:
                for k in ("comment", "status"):
                    if k in op:
                        r[k] = op[k]
                return r
        return None
    if kind == "delete":
        entry["remarks"] = [r for r in remarks if r["id"] != op["id"]]
        return None
    if kind == "clear":
        entry["remarks"] = []
        return None
    raise ValueError(f"opération inconnue : {kind}")


# ---------- Texte des remarques pour Claude ----------

def shorten(quote):
    import re
    flat = re.sub(r"\s+", " ", re.sub(r"\s*\n\s*", " / ", quote))
    return flat if len(flat) <= 420 else flat[:220] + " […] " + flat[-160:]


def remarks_text(state, include_resolved=False):
    lines = [
        "Voici mes remarques de lecture.",
        "Chaque passage est cité tel qu'il s'affiche à l'écran, sans les signes de mise en forme du Markdown. "
        "Le signe « / » marque un changement de paragraphe. Le numéro R… sert à répondre à une remarque précise.",
        "",
    ]
    count = 0
    for path, entry in state["documents"].items():
        items = [r for r in entry.get("remarks", []) if include_resolved or r.get("status") != "resolved"]
        items = [r for r in items if (r.get("comment") or "").strip() or r.get("quote")]
        if not items:
            continue
        lines += ["## " + pathlib.Path(path).name, "Fichier : " + path, ""]
        for r in items:
            count += 1
            head = f"{r['number']}."
            if r.get("quote"):
                section = f"« {r['section']} »" if r.get("section") else "début du document"
                lines.append(f"{head} Section : {section}")
                lines.append(f"   Passage : « {shorten(r['quote'])} »")
                lines.append("   Remarque : " + ((r.get("comment") or "").strip() or "(passage surligné, sans commentaire)"))
            else:
                lines.append(f"{head} Sur tout le document : " + (r.get("comment") or "").strip())
            if r.get("reply"):
                lines.append("   Ta réponse précédente : " + r["reply"]["text"])
            if r.get("status") == "resolved":
                lines.append("   (réglée)")
            lines.append("")
    return "\n".join(lines).strip() + "\n", count


# ---------- Commandes pour Claude ----------

def cmd_remarks(args):
    with locked_state(args.project) as state:
        text, count = remarks_text(state, args.all)
        # Lire les remarques clôt le tour de relecture : la version actuelle de chaque
        # document annoté devient la version relue.
        for path, entry in state["documents"].items():
            if entry.get("remarks") and pathlib.Path(path).is_file():
                mark_reviewed(entry, pathlib.Path(path).read_text(encoding="utf-8"))
    print(text if count else "Aucune remarque ouverte.")


def cmd_reply(args):
    number = args.number.upper()
    if not number.startswith("R"):
        number = "R" + number
    with locked_state(args.project) as state:
        for entry in state["documents"].values():
            for r in entry.get("remarks", []):
                if r.get("number") == number:
                    r["reply"] = {"text": args.text.strip(), "at": now()}
                    print(f"Réponse enregistrée sous {number}.")
                    return
    print(f"Remarque {number} introuvable.", file=sys.stderr)
    sys.exit(1)


def cmd_status(args):
    state = read_state(args.project)
    labels = {"new": "nouveau", "modified": "modifié depuis la dernière relecture", "unchanged": "inchangé"}
    for path, entry in state["documents"].items():
        p = pathlib.Path(path)
        if not p.is_file():
            print(f"{p.name} : fichier introuvable ({path})")
            continue
        status, _ = doc_status(entry, p.read_text(encoding="utf-8"))
        open_count = sum(1 for r in entry.get("remarks", []) if r.get("status") != "resolved")
        print(f"{p.name} : {labels[status]}, {open_count} remarque(s) ouverte(s)  ({path})")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("remarks")
    p.add_argument("--all", action="store_true")
    p.add_argument("--project", default=".")
    p.set_defaults(func=cmd_remarks)
    p = sub.add_parser("reply")
    p.add_argument("number")
    p.add_argument("text")
    p.add_argument("--project", default=".")
    p.set_defaults(func=cmd_reply)
    p = sub.add_parser("status")
    p.add_argument("--project", default=".")
    p.set_defaults(func=cmd_status)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
