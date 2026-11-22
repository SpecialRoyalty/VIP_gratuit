# Bot Telegram VIP — V6.2

Liens de parrainage permanents, minutes selon le rang et défi facultatif VIP à vie, avec validation administrateur.

## Redémarrer avec une base vide

1. Créer une nouvelle base PostgreSQL et conserver l'ancienne base ou une sauvegarde avant la bascule. Le bot crée ses tables au démarrage.
2. Renseigner `DATABASE_URL` avec l'adresse de la nouvelle base. Conserver `BOT_TOKEN` et `OWNER_IDS` si le bot et les propriétaires restent les mêmes. Arrêter l'ancienne instance avant de démarrer la nouvelle.
3. Avec un compte propriétaire, ouvrir `/start` en privé. Si le bot fait déjà partie des groupes à reprendre, le retirer puis le réajouter pour que la nouvelle base détecte ces groupes. Lui redonner ses droits d'administration.
4. Classer les groupes en PUB/VIP, refaire les associations et republier les annonces. Les anciens boutons de campagne doivent être remplacés.
5. Tester avec un parrain et un invité distincts. Après l'essai VIP, ouvrir le lien du parrain avec le compte invité, rejoindre le groupe PUB et vérifier le crédit après le délai de validation.

Les anciennes campagnes, minutes, invitations, configurations et décisions VIP à vie restent dans l'ancienne base. Pour éviter de laisser circuler des invitations directes de l'ancien système, les retirer dans Telegram lors de la bascule. Une base neuve ne révoque pas ces invitations chez Telegram.

### Mettre à jour en conservant les données

Déployer avec la même `DATABASE_URL`. Le bot crée la table `campaign_referrals` ou ajoute sa colonne de date au démarrage. Les comptes, campagnes, crédits et décisions existants sont conservés. Les utilisateurs obtiennent leur nouvelle adresse stable avec **MON LIEN**. Les anciennes invitations directes encore valides restent attribuées à leur campagne.

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
2. Le bot crée une campagne et une adresse de parrainage qui ouvre le bot. Une seule campagne est active par personne.
3. Une découverte du VIP est proposée une seule fois. Ses 2 minutes par défaut commencent lors de l'entrée réelle.
4. À la fin de l'essai, le bot expulse l'utilisateur puis lui présente le fonctionnement et son lien. Si le crédit atteint déjà le minimum, il convertit l'essai en session normale **avant toute expulsion**.
5. L'invité ouvre le lien partagé, appuie sur **Démarrer** et utilise le bouton **REJOINDRE LE GROUPE**. Il doit rester dans le PUB au moins 5 minutes par défaut pour que l'invitation soit validée. Les auto-invitations, doublons et bots ne donnent pas de crédit ; le filtre de profils existant reste en place.
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

## Partager et vérifier un lien de parrainage

**MON LIEN** et les messages de fin de VIP affichent la même adresse cliquable du bot, avec **Partager mon lien** et **Mon lien ne marche pas**. Ce dernier bouton teste l'invitation au groupe et affiche le résultat. L'invité peut aussi vérifier le lien depuis le bouton proposé par le bot après **Démarrer**.

Quand Telegram confirme que l'invitation au groupe PUB est invalide, le bot la remplace à la demande, tout en conservant l'adresse de parrainage et son attribution. Une panne réseau, une limite Telegram ou une erreur de droits ne déclenche pas de remplacement.

Depuis le panneau admin, **VÉRIFIER LES LIENS RÉCENTS** contrôle les 10 derniers liens. Les boutons permettent de contrôler les 5, 10 ou 20 derniers. Le rapport affiche le lien cliquable, l'identifiant du parrain, le groupe et le résultat Telegram. La vérification admin ne remplace aucun lien. Pour les campagnes dont la date d'émission du lien est inconnue, le classement utilise la date de création de la campagne. Les contrôles périodiques et au démarrage ont été retirés.

Un résultat positif confirme que Telegram accepte l'invitation lors du contrôle. L'accès peut dépendre du compte invité et de l'état du groupe. Les invitations d'entrée dans le VIP conservent la durée définie par `VIP_LINK_TTL_MINUTES`.

## Configuration et administration

Voir `env.example` pour les paramètres. Les variables obligatoires sont `BOT_TOKEN`, `OWNER_IDS` et `DATABASE_URL`.

| Paramètre | Défaut | Usage |
| --- | ---: | --- |
| `JOIN_VALIDATION_MINUTES` | 5 | Présence minimale des invités |
| `MINIMUM_VIP_MINUTES` | 10 | Crédit minimum d'une nouvelle session |
| `TRIAL_MINUTES` | 2 | Découverte VIP |
| `VIP_LINK_TTL_MINUTES` | 15 | Validité des liens personnels d'entrée VIP |
| `KICK_RETRY_SECONDS` | 20 | Vérification des sorties dues |
| `GROUP_LOST_GRACE_MINUTES` | 10 | Délai de réconciliation des groupes perdus |

Le bot doit être administrateur des groupes, avec les droits d'invitation et de restriction ; le VIP nécessite aussi le droit de suppression des messages. Le bot supprime les notifications de service d'entrée/sortie dans les VIP.

Le panneau conserve la gestion des groupes, les publicités avec image, les statistiques, les mots interdits, le broadcast privé avec confirmation, les contrôles de santé et les opérations de désactivation/suppression de groupes.

Le filtre de noms et pseudos ne prouve ni la nationalité d'une personne ni sa provenance Discord/Leakmedia.

## Vérifications hors ligne

```bash
pip install -r requirements.txt
pip install aiosqlite
python -m unittest discover -s tests -v
```

Les tests exercent le démarrage sur une base SQLite en mémoire avec Telegram simulé, l'envoi du lien après la découverte VIP, le remplacement d'une invitation invalide, l'attribution et le calcul des minutes.
