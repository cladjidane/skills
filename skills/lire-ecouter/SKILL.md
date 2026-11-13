---
name: lire-ecouter
description: Ouvre les documents Markdown proposés dans la dernière réponse dans la page de lecture de la skill lire, avec en plus une écoute chapitre par chapitre. L'utilisateur la lance à la main avec /lire-ecouter.
disable-model-invocation: true
---

# Lire et écouter des documents

Cette skill ouvre la page de la skill `lire`, avec la même boucle de relecture : annotations, réponses de Claude, documents marqués « Nouveau », « Modifié » ou « Inchangé ». Elle y ajoute un lecteur audio. Chaque titre de niveau 2 d'un document devient un chapitre, avec un bouton ▶ dans le sommaire. Un chapitre est réécrit pour l'oral par Mistral au moment où l'utilisateur l'écoute, puis dit par la voix Voxtral. Sans clé Mistral, la page lit le texte nettoyé avec la voix du navigateur, gratuitement.

Tous les fichiers de cette skill sont dans le dossier de la skill `lire`, rangé à côté de celui-ci dans le même plugin. Suis les étapes de la skill `lire`, avec les différences ci-dessous.

## Étape 2 : lancer le programme avec l'écoute

Ajoute l'option `--listen` :

```bash
nohup python3 -I <dossier de la skill lire>/reader_server.py --listen /chemin/absolu/A.md /chemin/absolu/B.md > /tmp/lire-ecouter.log 2>&1 &
sleep 3; cat /tmp/lire-ecouter.log
```

La première ligne du journal donne aussi la voix utilisée. La clé Mistral est cherchée dans la variable d'environnement `MISTRAL_API_KEY`, puis dans le fichier donné par `--env-file`, puis dans `~/.config/fc/env`. Si la ligne annonce « voix : navigateur » alors que l'utilisateur a une clé, dis-lui où la poser.

## Étape 3 : le mode d'emploi de l'écoute

Ajoute au mode d'emploi de la skill `lire` :
1. cliquer sur ▶ à côté d'un chapitre dans le sommaire, ou sur le grand bouton ▶ en bas pour commencer au début ;
2. la lecture enchaîne les chapitres ; les boutons ⏮ et ⏭ changent de chapitre ;
3. pour un document modifié, le bouton « Écouter les parties modifiées » enchaîne seulement les chapitres qui ont changé ;
4. le bouton « Texte lu » affiche le texte réellement dit, avec le passage en cours surligné ;
5. la barre du bas affiche le prix estimé du chapitre et la somme dépensée depuis l'ouverture de la page.

Rappelle le coût : avec Voxtral, environ 16 dollars par million de caractères dits, soit quelques dizaines de centimes pour un long document écouté en entier. Rien n'est facturé avant le premier ▶. Un chapitre déjà écouté est gardé en cache dans `~/.cache/fc-lire-ecouter/`, même si son numéro de titre a changé : le réécouter ne coûte rien.
