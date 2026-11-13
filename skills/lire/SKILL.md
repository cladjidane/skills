---
name: lire
description: Ouvre dans une page de lecture les documents Markdown proposés dans la dernière réponse, pour que l'utilisateur les lise, les annote et colle ses remarques dans la session. L'utilisateur la lance à la main avec /lire.
disable-model-invocation: true
---

# Ouvrir des documents dans la page de lecture

L'utilisateur veut lire confortablement les documents Markdown que tu viens de lui proposer, et les annoter. La page de lecture liste les documents dans une colonne de gauche et affiche le texte en grand. Il sélectionne un passage, écrit sa remarque, puis le bouton « Copier pour Claude » copie toutes ses remarques. Il les colle ensuite dans la session.

## 1. Choisir les documents

Les documents à ouvrir sont, dans cet ordre de priorité :
1. les fichiers donnés après `/lire`, si l'utilisateur en a donné (un dossier donne tous ses `.md`) ;
2. sinon, les fichiers `.md` cités dans ta dernière réponse écrite avant `/lire`, dans l'ordre où elle les cite ;
3. sinon, si ta dernière réponse ne cite aucun `.md`, tu demandes à l'utilisateur quels fichiers ouvrir, en listant les `.md` que tu as écrits ou modifiés pendant la session.

Chaque chemin est absolu. Un fichier cité par son seul nom se retrouve dans le dossier du projet.

## 2. Fabriquer et ouvrir la page

Le script `build_reader.py` se trouve dans le dossier de cette skill. Lance-le depuis le dossier du projet, avec Python 3 :

```bash
python3 -I <dossier de cette skill>/build_reader.py /chemin/absolu/A.md /chemin/absolu/B.md
```

Le script écrit la page dans `<projet>/exports/lecture/lecture-AAAA-MM-JJ-HHMMSS.html`, l'ouvre dans le navigateur par défaut et affiche son chemin. Il signale un fichier introuvable sur la sortie d'erreur, et ouvre quand même les autres. L'option `--out DOSSIER` change le dossier de sortie. L'option `--no-open` écrit la page sans l'ouvrir : utilise-la hors de macOS, puis donne le chemin à l'utilisateur.

La page embarque le texte des documents : elle montre leur état au moment de la commande. Après une modification d'un document, relance la commande pour avoir une page à jour.

## 3. Répondre à l'utilisateur

Ta réponse tient en quelques lignes : les documents ouverts, le chemin absolu de la page, et le mode d'emploi en trois étapes :
1. sélectionner un passage, cliquer sur « Annoter », écrire la remarque ;
2. pour une remarque sur un document entier, cliquer sur « Remarque sur ce document » ;
3. cliquer sur « Copier pour Claude », puis coller dans la session.

Les remarques restent gardées dans le navigateur si l'utilisateur ferme la page, et elles réapparaissent quand il rouvre une page qui contient le même document.

## 4. Quand l'utilisateur colle ses remarques

Le texte collé commence par « Voici mes remarques de lecture ». Il est groupé par document, avec le chemin du fichier, puis une remarque numérotée par passage : la section, le passage cité et la remarque. Le passage est cité sans les signes de mise en forme du Markdown (`**`, `` ` ``, `#`) : cherche-le dans le fichier sur ses mots, pas à l'identique.

Traite chaque remarque. Ta réponse reprend le nom du document et le numéro de chaque remarque, et dit en une phrase ce que tu as changé dans le fichier ou la question que tu poses à l'utilisateur.
