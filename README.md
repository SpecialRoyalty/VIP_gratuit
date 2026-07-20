# Bot Telegram VIP à la minute — Railway/PostgreSQL

## Principe

- Chaque groupe PUB possède son texte et son image.
- Le bouton public est toujours `🎁 VIP GRATUIT`.
- Le clic mémorise le groupe d'origine.
- Une seule campagne active par utilisateur.
- 1 invitation validée = 1 minute.
- Au moins 10 minutes sont nécessaires pour générer un lien VIP.
- Le temps démarre à l'entrée réelle dans le VIP.
- Les invitations reçues pendant la session prolongent l'expiration.
- À zéro, le bot expulse puis vérifie la sortie.

## Installation Railway

1. Créer un bot avec BotFather et désactiver le mode confidentialité si les événements de membres ne remontent pas.
2. Créer un dépôt GitHub avec ce dossier.
3. Dans Railway, créer un projet, ajouter PostgreSQL puis le service GitHub.
4. Ajouter les variables de `.env.example`. `DATABASE_URL` peut référencer `${{Postgres.DATABASE_URL}}`.
5. Déployer.

## Droits Telegram obligatoires

Dans chaque groupe PUB et VIP, le bot doit être administrateur avec :

- Inviter des utilisateurs / gérer les liens d'invitation.
- Bannir ou restreindre des membres.

Le bot doit recevoir les mises à jour `chat_member`. Telegram exige que le bot soit administrateur pour recevoir ces informations de façon fiable.

## Premier branchement

`OWNER_IDS` constitue la racine de confiance. Lorsque l'un de ces comptes ajoute le bot :

1. Le groupe apparaît dans `👥 GROUPES`.
2. Promouvoir le bot administrateur.
3. Appuyer sur `🔄 VÉRIFIER`.
4. Choisir `📢 GROUPE PUB` ou `🔐 GROUPE VIP`.
5. Pour un PUB : configurer texte, image et VIP associé, prévisualiser, puis publier.

Toute tentative d'ajout par un compte non autorisé provoque : récupération d'un lien quand possible, alerte aux administrateurs, message `Garde la pêche 👋`, puis départ du bot.

## Statistiques

Le bot enregistre par groupe et par version publicitaire :

- publications ;
- clics ;
- campagnes ;
- invitations validées/refusées ;
- entrées VIP ;
- expulsions ;
- évolution des clics sur 7 jours par rapport aux 7 jours précédents.

## Filtrage interne

Le menu `🚫 MOTS INTERDITS` ajoute des mots isolés insensibles à la casse. Ainsi `CP` correspond à `cp`, mais pas à `cpourtoi`. Après trois profils non conformes invités, le parrain est banni. Cette règle interne ne doit pas être présentée comme une vérification fiable de nationalité : Telegram ne fournit pas la nationalité des comptes.

## Limites Telegram importantes

- Un bot ne peut attribuer une arrivée à un parrain que si la personne utilise un lien d'invitation créé par le bot et que l'événement contient ce lien.
- Le bot ne peut pas connaître le nombre réel de vues d'une publicité ; les statistiques commencent au clic sur le bouton.
- Pour expulser sans bannissement permanent, le bot bannit puis débannit immédiatement l'utilisateur.
