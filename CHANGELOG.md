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
