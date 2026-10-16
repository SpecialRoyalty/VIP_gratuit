# V6.0 — Rangs et défi VIP à vie

- Bronze 0 / Silver 50 / Gold 150 / Platine 300 / Omega 500 : de 1 à 5 minutes par nouvelle invitation validée.
- Rang cumulatif, indépendant de la participation au défi, sans recalcul des anciens crédits.
- Défi facultatif de 200 arrivées postérieures à l'inscription, avec progression, justificatifs et décision administrateur.
- Droits VIP permanents nominatifs par groupe ; protection contre les expulsions temporisées et les boutons de dépenses anciens.
- Annonce unique aux utilisateurs déjà enregistrés au premier déploiement, avec suivi persistant et bilan admin.
- Nouvelles tables créées automatiquement sans modifier le schéma des tables existantes depuis V5.4/V5.5.
- Correction de l'ordre essai → session créditée : aucune expulsion avant la conversion.
- Une erreur de vérification Telegram laisse l'invitation en attente.
- Utilisation de l'heure réelle de l'arrivée Telegram pour le défi, même en cas d'événement retardé.

# V5.5 — Liens de parrainage permanents

- Suppression des rotations périodiques, sur clic utilisateur, au démarrage et après échec d'audit.
- Suppression du renouvellement global ; anciens boutons neutralisés.
- Liens PUB créés sans expiration ni quota ; contrôle du même lien avec suppression des limites.
- Audits silencieux, erreurs exactes réservées aux administrateurs avec déduplication persistante et rappel après 24 h.
- Respect de RetryAfter : pause des audits sans remplacement de lien.
- Conservation des anciennes URL, de l'attribution, des compteurs et des minutes.
- Perte des droits seule : aucune libération automatique des campagnes.
- Tests de régression hors ligne ; aucune migration SQL depuis V5.4.

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
