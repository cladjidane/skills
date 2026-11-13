---
name: lire
description: Ouvre dans une page de lecture les documents Markdown proposés dans la dernière réponse, pour que l'utilisateur les lise, les annote et vérifie ensuite les corrections. L'utilisateur la lance à la main avec /lire.
disable-model-invocation: true
---

# Ouvrir des documents dans la page de lecture

Le déroulé est une boucle de relecture :
1. tu rédiges des documents Markdown pendant la session et tu les proposes ;
2. l'utilisateur les ouvre avec cette skill, les lit et annote des passages ;
3. il te transmet ses remarques, tu corriges les documents et tu réponds à chaque remarque ;
4. il relance la skill pour vérifier tes corrections.

La page garde l'état de lecture dans `<projet>/exports/lecture/reading-state.json` : les remarques, tes réponses, et la version de chaque document relue en dernier. À la relance, la page marque chaque document « Nouveau », « Modifié » ou « Inchangé ». Pour un document modifié, elle surligne en vert les passages changés depuis la dernière relecture, met un point dans le sommaire à côté des parties concernées, et liste les passages supprimés.

## 1. Choisir les documents

Les documents à ouvrir sont, dans cet ordre de priorité :
1. les fichiers donnés après `/lire`, si l'utilisateur en a donné (un dossier donne tous ses `.md`) ;
2. sinon, les fichiers `.md` cités dans ta dernière réponse écrite avant `/lire`, dans l'ordre où elle les cite ;
3. sinon, si ta dernière réponse ne cite aucun `.md`, tu demandes à l'utilisateur quels fichiers ouvrir, en listant les `.md` que tu as écrits ou modifiés pendant la session.

Chaque chemin est absolu. Un fichier cité par son seul nom se retrouve dans le dossier du projet.

## 2. Lancer le programme de lecture

La page a besoin d'un petit programme local, `reader_server.py`, rangé dans le dossier de cette skill. Lance-le détaché depuis le dossier du projet, pour qu'il continue après ta réponse :

```bash
nohup python3 -I <dossier de cette skill>/reader_server.py /chemin/absolu/A.md /chemin/absolu/B.md > /tmp/lire.log 2>&1 &
sleep 2; cat /tmp/lire.log
```

La première ligne du journal donne l'adresse de la page et le chemin du fichier d'état. Le programme ouvre la page dans le navigateur par défaut ; l'option `--no-open` l'en empêche. Il s'arrête seul après 45 minutes sans activité de la page. Un programme déjà lancé pour d'autres documents peut continuer à tourner : le nouveau prend le port libre suivant.

## 3. Répondre à l'utilisateur

Ta réponse donne l'adresse de la page, l'état de chaque document (la commande `python3 -I <dossier de cette skill>/reading_state.py status` l'affiche), et ce mode d'emploi :
1. sélectionner un passage, cliquer sur « Annoter », écrire la remarque ;
2. pour une remarque sur un document entier, cliquer sur « Remarque sur ce document » ;
3. pour transmettre les remarques, soit cliquer sur « Copier pour Claude » et coller dans la session, soit écrire « j'ai annoté » dans la session ;
4. une remarque traitée se marque « Réglée » : elle n'est plus surlignée ni transmise.

## 4. Traiter les remarques

Les remarques arrivent de deux façons :
- l'utilisateur colle un texte qui commence par « Voici mes remarques de lecture » ;
- l'utilisateur écrit « j'ai annoté » ou une phrase équivalente : lance depuis le dossier du projet `python3 -I <dossier de cette skill>/reading_state.py remarks`, qui affiche le même texte.

Dans les deux cas, transmettre les remarques clôt le tour de relecture : la version actuelle de chaque document devient la version relue. Les corrections que tu fais ensuite seront surlignées à la prochaine ouverture.

Le texte est groupé par document, avec le chemin du fichier, puis une remarque par numéro (`R1`, `R2`…) : la section, le passage cité et la remarque. Le passage est cité sans les signes de mise en forme du Markdown (`**`, `` ` ``, `#`) : cherche-le dans le fichier sur ses mots, pas à l'identique. Une ligne « Ta réponse précédente » indique que l'utilisateur n'est pas satisfait de ta réponse du tour d'avant.

Pour chaque remarque :
1. corrige le document, ou prépare la question à poser ;
2. écris ta réponse en une phrase dans le fichier d'état : `python3 -I <dossier de cette skill>/reading_state.py reply R3 "Ce que j'ai changé, ou ma question"`. La réponse apparaît sous la remarque dans la page, même si elle est ouverte, en moins de 15 secondes.

Ta réponse dans la session reprend le numéro de chaque remarque et la même phrase. Termine en proposant de relancer `/lire` pour vérifier les corrections.
