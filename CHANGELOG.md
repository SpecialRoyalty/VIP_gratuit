# Version 5.0.0

## Groupes PUB perdus

- Détection distincte entre un groupe réellement inaccessible et un simple VIP non associé.
- Délai de confirmation configurable avec `GROUP_LOST_GRACE_MINUTES`.
- Libération automatique des campagnes liées à un groupe PUB confirmé perdu.
- Révocation des liens de parrainage et des liens VIP encore inutilisés.
- Annulation des invitations encore en vérification.
- Notification automatique des utilisateurs concernés, sans bouton supplémentaire.
- Réconciliation rétroactive au démarrage pour corriger les campagnes déjà bloquées.
- Opération idempotente : une campagne ne peut être libérée qu'une seule fois.
- Un ancien groupe perdu peut être ajouté de nouveau et reconfiguré.

## Broadcast privé

- Nouveau bouton `📣 BROADCAST PRIVÉ` dans le panneau administrateur.
- Envoi d'un texte ou d'une photo à tous les utilisateurs enregistrés.
- Aperçu et confirmation avant l'envoi.
- Envoi progressif avec gestion des limites Telegram.
- Rapport final : envoyés, utilisateurs ayant bloqué le bot et erreurs.

## Santé

- Affichage du dernier bilan de réconciliation.
- Les problèmes de configuration ne déclenchent plus une fausse perte de groupe.
- Les expulsions et leurs nouvelles tentatives restent contrôlées automatiquement.
