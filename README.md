# Skills de Fabien Canu

Skills pour Claude Code et Codex, écrites en français.

## Installer

Dans Claude Code :

```
/plugin marketplace add cladjidane/skills
/plugin install fc@fc
```

Les skills s'appellent ensuite `fc:<nom>`, par exemple `/fc:lire`.

## Les skills

| Skill | Ce qu'elle fait |
|---|---|
| `lire` | Ouvre dans le navigateur les documents Markdown que Claude vient de proposer. On les lit, on annote des passages, puis le bouton « Copier pour Claude » copie les remarques à coller dans la session. Demande Python 3. |
| `lire-ecouter` | Même page que `lire`, avec une écoute chapitre par chapitre. Chaque chapitre est réécrit pour l'oral par Mistral, puis dit par la voix Voxtral, seulement quand on clique sur ▶. Sans clé Mistral (`MISTRAL_API_KEY`), la page utilise la voix gratuite du navigateur. Demande Python 3 et la skill `lire`. |

## Bibliothèques incluses

`skills/lire/vendor/marked.min.js` est la bibliothèque [marked](https://github.com/markedjs/marked) 12.0.2, sous licence MIT, copyright Christopher Jeffrey et les contributeurs de marked.

## Licence

Les skills sont publiées sous licence MIT (fichier `LICENSE`).
