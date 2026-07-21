# Changelog

## 4.0.0

- Nouveau message motivant envoyé après l’accès découverte de 2 minutes.
- Le message affiche le compteur réel, le crédit disponible, le nombre manquant et le lien personnel.
- Si l’utilisateur atteint le seuil minimum pendant l’essai, il n’est plus expulsé.
- L’essai est alors transformé automatiquement en session VIP normale avec tout le crédit disponible.
- Les vérifications automatiques d’expulsion, les nouvelles tentatives et les alertes administrateur restent actives.

## 3.0.0

- Corrige le démarrage des essais pour les campagnes déjà existantes.
- Un simple `/start` génère le lien découverte si l’utilisateur n’a jamais utilisé son essai.
- `TRIAL_MINUTES` reste configurable et vaut 2 par défaut.
