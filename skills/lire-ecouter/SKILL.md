---
name: lire-ecouter
description: Ouvre les documents Markdown proposés dans la dernière réponse dans la page de lecture de la skill lire, avec en plus une écoute chapitre par chapitre. L'utilisateur la lance à la main avec /lire-ecouter.
disable-model-invocation: true
---

# Lire et écouter des documents

Cette skill ouvre la même page que la skill `lire` : lecture, annotations, bouton « Copier pour Claude ». Elle y ajoute un lecteur audio. Chaque titre de niveau 2 d'un document devient un chapitre, avec un bouton ▶ dans le sommaire. Un chapitre est réécrit pour l'oral par Mistral au moment où l'utilisateur l'écoute, puis dit par la voix Voxtral. Sans clé Mistral, la page lit le texte nettoyé avec la voix du navigateur, gratuitement.

La skill a besoin de la skill `lire`, rangée à côté d'elle dans le même plugin.

## 1. Choisir les documents

Suis l'étape 1 de la skill `lire` : les fichiers donnés après `/lire-ecouter`, sinon les `.md` cités dans ta dernière réponse, sinon demande à l'utilisateur.

## 2. Lancer le programme d'écoute

Le script `listen_server.py` se trouve dans le dossier de cette skill. Lance-le détaché depuis le dossier du projet, pour qu'il continue après ta réponse :

```bash
nohup python3 -I <dossier de cette skill>/listen_server.py /chemin/absolu/A.md /chemin/absolu/B.md > /tmp/lire-ecouter.log 2>&1 &
sleep 3; cat /tmp/lire-ecouter.log
```

La première ligne du journal donne l'adresse de la page, la voix utilisée et le délai d'arrêt. Le script ouvre la page dans le navigateur par défaut ; l'option `--no-open` l'en empêche. Il s'arrête seul après 45 minutes sans écoute. Relancer la skill crée un nouveau programme sur un autre port.

La clé Mistral est cherchée dans la variable d'environnement `MISTRAL_API_KEY`, puis dans le fichier donné par `--env-file`, puis dans `~/.config/fc/env`. Si la première ligne annonce « voix du navigateur » alors que l'utilisateur a une clé, dis-lui où la poser.

## 3. Répondre à l'utilisateur

Ta réponse donne l'adresse de la page, la voix utilisée, et ce mode d'emploi :
1. cliquer sur ▶ à côté d'un chapitre dans le sommaire, ou sur le grand bouton ▶ en bas pour commencer au début ;
2. la lecture enchaîne les chapitres ; les boutons ⏮ et ⏭ changent de chapitre ;
3. le bouton « Texte lu » affiche le texte réellement dit, avec le passage en cours surligné ;
4. la barre du bas affiche le prix estimé du chapitre et la somme dépensée depuis l'ouverture de la page.

Rappelle le coût : avec Voxtral, environ 16 dollars par million de caractères dits, soit quelques dizaines de centimes pour un long document écouté en entier. Rien n'est facturé avant le premier ▶, et un chapitre déjà écouté est gardé en cache dans `~/.cache/fc-lire-ecouter/`.

Les annotations et le collage des remarques fonctionnent comme avec la skill `lire` : suis son étape 4 quand l'utilisateur colle ses remarques.
