# Bot Telegram VIP — Railway + PostgreSQL

Projet Python prêt à déployer sur Railway. Il utilise `python-telegram-bot`, PostgreSQL et le polling Telegram.

## Fonctions incluses

- Détection des groupes dans lesquels le bot est ajouté.
- Alerte et sortie automatique lors d’un raccordement non autorisé.
- Détection des administrateurs Telegram après raccordement autorisé.
- Classement des groupes en `pub` ou `VIP` depuis le panneau `/admin`.
- Publicité différente par groupe avec image, texte et bouton `VIP GRATUIT`.
- Mémorisation du premier groupe publicitaire utilisé.
- Une seule campagne active par utilisateur, y compris lorsqu’il clique depuis plusieurs groupes.
- Lien d’invitation personnel généré par le bot pour le groupe publicitaire d’origine.
- Une phrase choisie aléatoirement parmi dix, sans bouton pour la changer.
- Affichage Leakimedia avec le format espacé `https:// t. me/...`.
- Capture d’écran et validation manuelle par un administrateur.
- Compteur en attente, validé et non validé.
- Validation d’une arrivée après cinq minutes de présence.
- Déblocage de 10 jours de VIP par tranche de 100 invitations validées.
- Lien d’entrée VIP personnel, utilisable une fois et valable 24 heures.
- Rappels avant expiration, retrait automatique du VIP et nouvelle campagne après expiration.
- Message de relance après 72 heures de stagnation, avec le lien direct sans espaces.

## Limite importante

Telegram ne fournit pas la nationalité réelle des utilisateurs. Le bot ne peut donc pas certifier automatiquement qu’une personne est française. Cette règle doit être vérifiée autrement ou rester une règle annoncée à la communauté.

## 1. Créer le bot Telegram

1. Ouvre `@BotFather`.
2. Lance `/newbot` et récupère le token.
3. Dans BotFather, désactive le mode confidentialité avec `/setprivacy` puis `Disable`, afin que le bot reçoive correctement les événements nécessaires dans les groupes.
4. Récupère ton identifiant Telegram numérique, par exemple avec un bot d’identification.

## 2. Créer le projet Railway

1. Crée un nouveau projet Railway.
2. Ajoute un service PostgreSQL.
3. Ajoute ce dépôt ou téléverse le projet sur GitHub et connecte-le à Railway.
4. Dans le service du bot, ajoute les variables :

```env
BOT_TOKEN=le_token_botfather
OWNER_IDS=123456789
DATABASE_URL=${{Postgres.DATABASE_URL}}
LEAKIMEDIA_URL=https://leakimedia.com/
INVITE_GOAL=100
VIP_DAYS_PER_GOAL=10
VIP_LINK_TTL_HOURS=24
JOIN_VALIDATION_MINUTES=5
STAGNATION_HOURS=72
REMINDER_DAYS=5,3,1
```

Railway lancera automatiquement :

```bash
python -m app.main
```

## 3. Droits Telegram nécessaires

Ajoute le bot comme administrateur dans chaque groupe publicitaire et dans le VIP. Il lui faut au minimum :

- inviter des utilisateurs et créer des liens ;
- bannir ou retirer des utilisateurs dans le VIP ;
- publier des messages dans les groupes publicitaires ;
- recevoir les changements de membres.

Ajoute toujours le bot toi-même avec un compte dont l’ID figure dans `OWNER_IDS`. Sinon, il considère le raccordement comme illégal et quitte le groupe.

## 4. Configuration des groupes

Après l’ajout autorisé, le propriétaire reçoit un message privé avec les boutons :

- `GROUPE PUB` ;
- `GROUPE VIP` ;
- `REFUSER`.

Lance ensuite `/admin` en privé pour retrouver les groupes et les preuves.

### Associer un groupe pub au VIP

```text
/linkvip ID_DU_GROUPE_PUB ID_DU_GROUPE_VIP
```

Exemple :

```text
/linkvip -1001111111111 -1002222222222
```

### Configurer le texte publicitaire

```text
/setad ID_DU_GROUPE_PUB Texte de la publicité
```

### Configurer le message privé d’accueil

```text
/setintro ID_DU_GROUPE_PUB Ton message privé configurable
```

### Configurer les images

Envoie une photo au bot en privé avec l’une de ces légendes :

```text
#ad -1001111111111
```

ou :

```text
#private -1001111111111
```

`#ad` configure l’image publiée dans le groupe. `#private` configure l’image envoyée au début du parcours privé.

### Publier les publicités

Dans `/admin`, utilise le bouton `PUBLIER LES PUBS`. Le bot publie dans chaque groupe publicitaire configuré son image, son texte et le bouton `VIP GRATUIT`.

## 5. Validation des captures

Une capture envoyée par un utilisateur apparaît chez les propriétaires et dans :

```text
/admin → PREUVES
```

Boutons disponibles :

- `ACCEPTER` : active le compteur ;
- `REFUSER` : demande une nouvelle capture ;
- `BANNIR` : suspend le parcours de l’utilisateur.

## 6. Logique des invitations

Le lien technique réel est enregistré sans espaces, par exemple :

```text
https://t.me/+ABCDEF
```

La phrase fournie pour Leakimedia est affichée avec les espaces requis :

```text
meilleure groupe : https:// t. me/+ABCDEF
```

Lorsqu’une personne rejoint avec le lien réel :

1. l’invitation passe en attente ;
2. le bot attend cinq minutes ;
3. il vérifie que la personne est encore membre ;
4. il valide ou refuse l’invitation.

La règle exacte des cinq minutes n’est pas révélée dans les messages utilisateurs.

## 7. Points à tester avant ouverture publique

- Le bot doit créer ses propres liens : les liens créés par un autre administrateur ne permettent pas d’attribuer correctement les arrivées.
- Utilise de préférence des supergroupes privés pour le suivi des liens.
- Teste l’entrée, la sortie et la réintégration d’un membre.
- Vérifie que le bot possède toujours les droits administrateur après toute modification du groupe.
- Fais un test complet avec un objectif temporaire de 2 ou 3 invitations avant de remettre `INVITE_GOAL=100`.

## Structure

```text
app/
  config.py
  db.py
  models.py
  texts.py
  keyboards.py
  main.py
requirements.txt
Procfile
railway.json
.env.example
```
