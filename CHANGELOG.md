# Changelog

## 5.3.0

- Ajoute `campaign_invite_links`, un historique non destructif de tous les liens de parrainage.
- Les anciens liens encore fonctionnels continuent d'attribuer les invitations à la bonne campagne après une rotation.
- Nouveau bouton admin **♻️ RENOUVELER TOUS** avec confirmation, nombre de campagnes concernées et rapport final.
- La rotation globale crée un nouveau lien permanent pour toutes les campagnes actives et prévient les utilisateurs sans toucher aux compteurs/minutes.
- **MON LIEN** ne fait plus confiance indéfiniment à une URL ancienne : passé le délai configuré, un nouveau lien Telegram est créé automatiquement.
- Rotation préventive automatique des liens courants trop anciens, par lots.
- Les liens de campagne sont créés sans expiration, sans limite de membres et sans demande d'adhésion.
- Les groupes PUB perdus révoquent désormais tous les liens historiques connus de leurs campagnes.
- Santé enrichie avec le dernier bilan de rotation préventive et l'âge maximum configuré.
- Backfill automatique de l'historique au démarrage : aucune suppression de base ni migration manuelle nécessaire.

## V5.4 — Gestion manuelle des groupes PUB
- Ajout de **⏸ DÉSACTIVER** : empêche les nouvelles campagnes tout en conservant les campagnes existantes.
- Ajout de **▶️ RÉACTIVER** avec contrôle préalable des droits Telegram du bot.
- Ajout de **🗑 SUPPRIMER & LIBÉRER** avec écran de confirmation et comptage des campagnes, invitations en attente et liens actifs.
- Lors d'une suppression : clôture des campagnes actives, révocation des liens de campagne, annulation des invitations en attente, annulation des liens VIP/découverte non utilisés, notification des utilisateurs, archivage du groupe puis déconnexion du bot.
- L'opération est idempotente et conserve les anciennes données pour les statistiques.
