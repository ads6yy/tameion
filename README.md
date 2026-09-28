# Tameion (squelette de test)

Grand livre **beancount** + paiements **USDC natifs sur Arc testnet**, avec les contrôles recommandés
par l'article *Agents and Ledgers in 2026*. Données factices, usage solo. Pas encore d'agent LLM :
ce sont les rails sur lesquels il viendra se poser.

## Principe

```
facture (data/factures) ─► contrôles ─► écriture beancount ─► paiement Arc ─► écriture beancount ─► rapprochement onchain
```

| Idée de l'article | Où c'est dans le code |
|---|---|
| Rapprochement à trois (facture / commande / réception) | `controles.controler_facture` |
| Contrôle des changements de coordonnées fournisseur | adresse de la facture comparée à `data/fournisseurs.json` ; on paie toujours l'adresse du référentiel |
| Chaque écriture pointe vers un document | métadonnées `facture`, `commande`, `document`, `tx_hash` |
| Un témoin avant d'écrire | `tameion rapprocher` compare le solde onchain (lu à un bloc précis) au grand livre, au wei près, et refuse en cas d'écart ; le constat est tracé par une directive `custom "rapprochement"` |
| Refuser plutôt que réparer | `GrandLivre.ajouter` restaure le fichier si beancount le rejette ; montants en `Decimal`, 6 décimales exactes sur les factures, 18 pour le gas |
| Idempotence / pas de double paiement | `data/envois.jsonl` est écrit **avant** d'attendre la confirmation ; un envoi non confirmé bloque tout nouvel essai |
| Limites que l'outil ne contourne pas | plafond `max_payment_usdc` dans `config.toml` (côté code pour l'instant, pas encore dans un contrat) |

## Installation

```bash
uv sync
uv run pytest -q
```

## Scénario

```bash
uv run tameion init                 # enregistre le solde onchain comme apport initial
uv run tameion factures             # liste les factures ; F-003 est piégée (autre adresse, pas de réception)
uv run tameion comptabiliser F-001
uv run tameion payer F-001          # simulation : affiche le plan, n'envoie rien
```

Pour payer vraiment, le programme lit la clé dans la variable d'environnement `TAMEION_PRIVATE_KEY`
(il ne lit **pas** `.env` lui-même). Deux façons de la fournir :

```bash
# a) fichier .env (ignoré par git), chargé par uv à chaque commande
cp .env.example .env                # puis y mettre la clé
uv run --env-file .env tameion payer F-001 --executer

# b) variable exportée dans le terminal courant uniquement
export TAMEION_PRIVATE_KEY=$(sed -n 's/^private_key: *//p' ~/.arc-canteen/wallet.yaml)
uv run tameion payer F-001 --executer
uv run tameion rapprocher           # solde onchain == grand livre, sinon ÉCART
uv run tameion verifier
```

Expériences utiles :
- relancer `payer F-001 --executer` : refusé (déjà payée) ;
- `comptabiliser F-003` : refusé (adresse modifiée, réception absente) ;
- envoyer quelques centimes depuis ton wallet hors outil, puis `rapprocher` : l'écart est détecté (erreur d'omission).

Visualiser le grand livre : `uvx fava ledger/main.beancount` (optionnel, non installé dans le projet).

## Limites connues

- Les adresses fournisseurs sont jetables (clés non conservées) : les USDC envoyés sont perdus, garder de petits montants.
- Les rapprochements sont des directives `custom`, pas des assertions `balance` (qui valent pour une journée entière et
  bloqueraient les opérations suivantes du même jour) : `bean-check` ne les revérifie pas, seul un nouveau `rapprocher` le fait.
- Le plafond est appliqué par le code, pas encore par un smart contract (prochaine étape).
