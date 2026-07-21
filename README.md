# Bot Telegram VIP à la minute V3 — Railway + PostgreSQL

## Parcours utilisateur

1. Une publicité est publiée dans un groupe PUB avec son image, son texte et le bouton unique **🎁 VIP GRATUIT**.
2. Le bouton ouvre le bot en privé et mémorise définitivement le premier groupe PUB utilisé. Un simple `/start` renvoie également le lien découverte lorsqu’une campagne existante n’a encore jamais profité de l’essai.
3. Le bot crée immédiatement un lien personnel vers le VIP, sans afficher les conditions.
4. Le délai découverte commence uniquement lorsque Telegram confirme l'entrée réelle dans le VIP.
5. Après `TRIAL_MINUTES` (2 minutes par défaut), le bot retire l'utilisateur, vérifie l'expulsion puis lui envoie les conditions et son lien de parrainage.
6. Une invitation validée rapporte une minute. Il faut au moins 10 minutes disponibles pour démarrer une nouvelle session VIP.
7. Les invitations validées pendant une session payée prolongent la session d'une minute.

L'essai découverte ne peut être utilisé qu'une fois. Un lien découverte expiré avant utilisation peut être recréé.

## Notifications d'entrée et de sortie

Dans les groupes configurés en VIP, le bot supprime automatiquement les messages de service Telegram du type « X a rejoint le groupe » et « X a quitté le groupe ».

Le bot doit être administrateur du VIP avec les droits :

- inviter des utilisateurs ;
- bannir/restreindre des membres ;
- supprimer les messages.

## Contrôle des expulsions

- tentative d'expulsion toutes les `KICK_RETRY_SECONDS` secondes ;
- bannissement puis débannissement afin de permettre une future réentrée ;
- vérification immédiate du statut Telegram après l'opération ;
- conservation du statut `kick_pending` tant que Telegram ne confirme pas la sortie ;
- alerte administrateur à la première erreur puis toutes les trois tentatives ;
- audit récapitulatif toutes les cinq minutes ;
- compteur des expulsions en attente dans **🩺 SANTÉ**.

## Bouton Santé

Le bouton **🩺 SANTÉ** contrôle :

- Telegram ;
- PostgreSQL ;
- présence d'au moins un groupe PUB ;
- présence d'au moins un VIP ;
- droits du bot dans chaque groupe ;
- droit de suppression des messages dans le VIP ;
- association de chaque PUB à un VIP ;
- essais et sessions restant à expulser.

Une surveillance automatique avertit les administrateurs lorsqu'un groupe devient inaccessible, lorsque le bot perd ses droits ou lorsqu'une association PUB/VIP manque.

## Raccordement non autorisé

Si un non-administrateur autorisé ajoute le bot dans un groupe, le bot tente de récupérer un lien du groupe, transmet le groupe, l'auteur et le lien aux administrateurs, écrit **Garde la pêche 👋**, puis quitte le groupe.

## Déploiement Railway

1. Créer un projet Railway.
2. Ajouter PostgreSQL.
3. Déployer ce dépôt ou cette archive.
4. Ajouter les variables de `.env.example` dans Railway.
5. Mettre votre identifiant Telegram dans `OWNER_IDS`.
6. Ajouter le bot dans les groupes, le promouvoir administrateur, puis utiliser `/start` en privé.
7. Classer les groupes avec le panneau : PUB ou VIP.
8. Pour chaque PUB, configurer le texte, l'image et le VIP associé, puis publier.

## Base existante

Cette version ajoute la table `trial_accesses` et de nouvelles valeurs d'événements. Sur une installation de test, le plus simple est d'utiliser une nouvelle base PostgreSQL. Pour une base contenant déjà des données importantes, effectuer une migration SQL contrôlée avant le redéploiement.


## Correctif V3

La V3 corrige le cas visible dans la capture où `/start` affichait directement le compteur pour une campagne créée avant l’ajout de l’essai. Tant qu’aucun essai n’a été commencé ou terminé, le bot génère maintenant le lien découverte de `TRIAL_MINUTES`, y compris sur un simple `/start`.

## Fin de l’accès découverte

À la fin de l’essai, le bot affiche automatiquement le compteur réel et le lien personnel de l’utilisateur.
Si le crédit disponible atteint déjà le seuil `MINIMUM_VIP_MINUTES`, l’utilisateur n’est pas expulsé : l’essai devient directement une session VIP normale.

## Libération automatique après perte d'un groupe PUB

Lorsqu'un groupe PUB est réellement inaccessible pendant le délai configuré, le bot clôture les campagnes actives liées à ce groupe, révoque les liens encore actifs, annule les invitations en attente et libère automatiquement les utilisateurs. Une réconciliation est lancée au démarrage pour corriger également les anciennes campagnes bloquées.

Variable :

```env
GROUP_LOST_GRACE_MINUTES=10
```

Un simple VIP non associé est considéré comme une configuration incomplète et non comme une perte de connexion.

## Broadcast privé

Le bouton `📣 BROADCAST PRIVÉ` permet à un administrateur d'envoyer un texte ou une photo à tous les utilisateurs enregistrés. Le bot affiche un aperçu, demande confirmation, respecte un délai entre les messages et fournit un rapport final.

```env
BROADCAST_DELAY_SECONDS=0.05
```
