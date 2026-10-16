# Bot Telegram VIP — V6.0

Liens de parrainage permanents, minutes selon le rang et défi facultatif VIP à vie, avec validation administrateur.

## Mise à jour depuis V5.4 ou V5.5

1. Remplacer l'ancien code par le contenu de cette archive et redéployer.
2. Conserver le même `BOT_TOKEN`, les mêmes `OWNER_IDS` et la même `DATABASE_URL`. Ne pas recréer ni vider la base.
3. Arrêter l'ancienne instance lors du redéploiement. Une seule instance du bot doit fonctionner ; les envois et les décisions sont conçus pour ce mode.
4. Les cinq nouvelles tables sont créées automatiquement au démarrage : `challenge_enrollments`, `challenge_evidence`, `lifetime_accesses`, `release_notices`, `release_notice_deliveries`. Aucun changement de colonne ou d'enum existant n'est requis depuis V5.4/V5.5.
5. Les anciennes variables `CAMPAIGN_LINK_MAX_AGE_HOURS`, `CAMPAIGN_LINK_REFRESH_MINUTES` et `CAMPAIGN_LINK_ROTATION_BATCH` sont ignorées et peuvent être supprimées.

Les utilisateurs, liens, minutes, invitations et campagnes existants sont conservés. Le déploiement lance l'annonce unique décrite ci-dessous. Le ZIP n'exécute rien tant qu'il n'est pas déployé.

## Barème des rangs

| Rang | Invitations déjà validées, cumulées | Minutes par nouvelle invitation |
| --- | ---: | ---: |
| Bronze | 0 à 49 | 1 |
| Silver | 50 à 149 | 2 |
| Gold | 150 à 299 | 3 |
| Platine | 300 à 499 | 4 |
| Omega | 500 et plus | 5 |

Le cumul comprend les anciennes campagnes de la personne, même clôturées. Dépenser des minutes ne diminue pas le rang. Les utilisateurs existants bénéficient du tarif correspondant à leur cumul pour leurs prochaines invitations ; aucun gain passé n'est recalculé.

Le tarif est celui du rang avant la nouvelle validation : la 50e invitation rapporte encore 1 minute ; les 51e et suivantes rapportent 2 minutes jusqu'au prochain rang. Le même principe s'applique aux seuils 150, 300 et 500. Les validations sont traitées par échéance puis par identifiant.

Le bouton **MES RANGS** détaille le barème. **MON COMPTEUR** affiche le rang, le tarif, les invitations cumulées, une barre vers le prochain rang, les statistiques de la campagne et le crédit restant.

Les rangs sont automatiques, indépendants du défi. Omega donne 5 minutes par invitation, jamais un accès à vie.

## Parcours habituel

1. L'administrateur publie une publicité dans un groupe PUB avec le bouton **VIP GRATUIT**.
2. Le bot crée une campagne et un lien de parrainage vers ce groupe. Une seule campagne est active par personne.
3. Une découverte du VIP est proposée une seule fois. Ses 2 minutes par défaut commencent lors de l'entrée réelle.
4. À la fin de l'essai, le bot expulse l'utilisateur puis lui présente le fonctionnement et son lien. Si le crédit atteint déjà le minimum, il convertit l'essai en session normale **avant toute expulsion**.
5. Une nouvelle personne rejoignant le PUB via le lien doit rester au moins 5 minutes par défaut pour que l'invitation soit validée. Les auto-invitations, doublons et bots ne donnent pas de crédit ; le filtre de profils existant reste en place.
6. Chaque invitation validée rapporte 1 à 5 minutes selon le rang.
7. À partir de 10 minutes disponibles par défaut, l'utilisateur peut demander un lien personnel vers le VIP. Le compte à rebours commence à son entrée réelle.
8. Les invitations validées pendant une session prolongent celle-ci du nombre de minutes correspondant au rang, sans créditer deux fois les mêmes minutes.
9. À expiration, le bot retire l'utilisateur et vérifie la sortie. Une erreur Telegram pendant la vérification d'un invité laisse son invitation en attente, sans l'invalider arbitrairement.

## Défi VIP à vie — facultatif

Le menu propose **DÉFI VIP À VIE · FACULTATIF**. Consulter cette page n'inscrit personne : il faut cliquer sur **JE PARTICIPE**.

- Objectif : 200 nouvelles invitations validées de personnes provenant de Leakmedia ou Discord, dans la campagne inscrite.
- Le même lien de parrainage est utilisé. Les anciennes URL encore actives et rattachées à cette campagne continuent également de fonctionner.
- Seules les arrivées après l'inscription comptent. Une arrivée antérieure ne compte pas même si sa validation ou la réception de l'événement Telegram est tardive.
- Les invitations du défi font aussi gagner les minutes et progresser le rang.
- La page affiche les invitations validées, en attente, la barre sur 200 et les justificatifs enregistrés.
- L'utilisateur peut transmettre un texte (3 000 caractères maximum) ou une photo avec légende via **AJOUTER UN JUSTIFICATIF**. Les administrateurs peuvent consulter ces pièces.
- À 200 validations, l'utilisateur peut cliquer sur **DEMANDER MON ACCÈS À VIE**. Le statut devient « en attente », sans accorder de droit automatique.
- La provenance Leakmedia/Discord n'est pas détectée automatiquement : elle est vérifiée par l'administrateur, à partir du dossier et des justificatifs.

### Décision administrateur

Le panneau contient **DEMANDES VIP À VIE**. Chaque demande indique la personne, le groupe PUB, le VIP visé, le nombre d'invitations depuis l'inscription, les justificatifs et son statut.

- **APPROUVER** affiche une confirmation explicite de la vérification de provenance et de l'attribution à vie.
- **REFUSER** demande un motif, communiqué à l'utilisateur et conservé en base.
- Après un refus, un nouvel examen nécessite au moins un nouveau justificatif. Les boutons liés à une ancienne demande sont neutralisés.
- Les demandes sont persistantes et accessibles depuis le panneau même si leur notification privée a échoué.

### Accès permanent

L'approbation crée un droit nominatif pour le **VIP associé au défi**. Ce droit n'a pas de durée ; il ne se transfère pas automatiquement à d'autres VIP. Les minuteurs existants de ce VIP sont annulés, et les contrôles d'expulsion vérifient aussi le droit permanent avant d'agir.

Le bouton **MES ACCÈS À VIE** permet de rejoindre le VIP. Son lien d'entrée personnel dure 15 minutes par défaut et accepte une personne : c'est le **droit d'accès** qui est permanent. Le titulaire peut demander un nouveau lien d'entrée sans dépenser de minutes. Une personne non bénéficiaire utilisant ce lien ne reçoit pas le droit d'accès.

Si le groupe PUB de la campagne disparaît, un défi non approuvé est annulé. Un droit déjà approuvé pour un VIP reste acquis tant que ce VIP est disponible. Les rangs cumulés ne sont pas remis à zéro.

## Annonce unique au premier déploiement V6

La liste des utilisateurs déjà enregistrés au premier démarrage V6 est figée en base. Le bot leur annonce les liens stables, la conservation des compteurs, les rangs et le défi facultatif. Il joint le lien actuel lorsqu'une campagne active existe ; sinon il indique comment reprendre depuis un groupe partenaire.

- Les envois commencent environ 45 secondes après démarrage, par lots de 25 par minute.
- Le statut de chaque envoi est enregistré : un redémarrage ou un nouveau push ne relance pas les messages déjà envoyés.
- Les utilisateurs qui s'inscrivent après ce premier déploiement ne reçoivent pas cette ancienne annonce.
- Les destinataires qui ont bloqué le bot ou les envois définitivement refusés sont marqués en échec.
- Si une erreur réseau ou un arrêt du processus rend la remise incertaine, le bot ne renvoie pas automatiquement le message, pour éviter les doublons. Une remise à tous ne peut donc pas être garantie.
- Les limites Telegram reportent toute la file jusqu'à l'échéance indiquée.
- **BILAN ANNONCE** affiche les nombres envoyés, en attente, en cours, en échec et incertains.

## Liens de parrainage permanents et contrôles silencieux

Les liens de parrainage PUB sont créés sans expiration ni quota de membres. Aucun renouvellement n'est déclenché par leur âge, par **MON LIEN**, par le démarrage ou par une erreur d'audit. Les anciennes URL partagées continuent d'attribuer les invitations à la même campagne.

L'audit vérifie le lien courant en éditant ses paramètres sans changer son URL, avec `expire_date=0`, `member_limit=0` et sans demande d'adhésion. La Bot API ne propose pas de test de clic ; un contrôle réussi ne garantit pas l'accès d'une personne particulière.

- En cas de réussite : aucun message.
- En cas d'échec : alerte réservée aux administrateurs avec groupe, utilisateur, lien et erreur exacte. Aucun remplacement ni message à l'utilisateur.
- Même erreur : rappel au plus une fois par 24 heures, avec déduplication persistante. Un changement d'erreur ou une nouvelle panne après rétablissement peut déclencher une alerte.
- **AUDITER LES LIENS** lance le même contrôle. Les anciens boutons de renouvellement ne peuvent plus changer les liens.
- Une simple perte de droits ne clôture plus la campagne. Un groupe réellement perdu ou supprimé manuellement peut toujours entraîner sa clôture et la révocation des liens associés.

Un lien sans expiration peut toujours devenir inutilisable après une révocation manuelle ou la disparition du groupe.

## Configuration et administration

Voir `env.example` pour les paramètres. Les variables obligatoires sont `BOT_TOKEN`, `OWNER_IDS` et `DATABASE_URL`.

| Paramètre | Défaut | Usage |
| --- | ---: | --- |
| `JOIN_VALIDATION_MINUTES` | 5 | Présence minimale des invités |
| `MINIMUM_VIP_MINUTES` | 10 | Crédit minimum d'une nouvelle session |
| `TRIAL_MINUTES` | 2 | Découverte VIP |
| `VIP_LINK_TTL_MINUTES` | 15 | Validité des liens personnels d'entrée VIP |
| `KICK_RETRY_SECONDS` | 20 | Vérification des sorties dues |
| `CAMPAIGN_LINK_AUDIT_MINUTES` | 10 | Fréquence des audits de liens PUB |
| `CAMPAIGN_LINK_AUDIT_BATCH` | 100 | Taille des lots d'audit |
| `GROUP_LOST_GRACE_MINUTES` | 10 | Délai de réconciliation des groupes perdus |

Le bot doit être administrateur des groupes, avec les droits d'invitation et de restriction ; le VIP nécessite aussi le droit de suppression des messages. Le bot supprime les notifications de service d'entrée/sortie dans les VIP.

Le panneau conserve la gestion des groupes, les publicités avec image, les statistiques, les mots interdits, le broadcast privé avec confirmation, les contrôles de santé et les opérations de désactivation/suppression de groupes.

Le filtre de noms et pseudos ne prouve ni la nationalité d'une personne ni sa provenance Discord/Leakmedia.

## Installation neuve

1. Préparer une base PostgreSQL et renseigner les variables de `env.example` sur l'hébergement.
2. Installer `requirements.txt` et lancer `python -m app.main` (ou utiliser le Dockerfile/Procfile fourni).
3. Ajouter le bot aux groupes et lui donner les droits requis.
4. Ouvrir `/start` en privé avec un compte présent dans `OWNER_IDS`.
5. Classer les groupes en PUB/VIP, associer chaque PUB à un VIP, configurer la publicité et publier.

## Vérifications hors ligne

```bash
pip install -r requirements.txt
pip install aiosqlite
python -m unittest discover -s tests -v
```

Les tests utilisent un bot simulé et une base SQLite en mémoire, jamais Telegram ni la base de production. Ils couvrent les liens stables, les rangs et leurs seuils, les bonus de session, l'inscription volontaire, les arrivées tardives, les décisions admin, les droits permanents, les expulsions et les envois uniques. Les verrous PostgreSQL et la remise réelle de messages restent à observer après déploiement.
