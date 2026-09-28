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
| Un témoin avant d'écrire | `tameion rapprocher` compare le solde onchain au grand livre et refuse en cas d'écart |
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

Pour payer vraiment, charger la clé du wallet arc-canteen **dans le shell uniquement** (jamais dans un fichier du projet) :

```bash
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
- Une assertion `balance` beancount porte sur le début de sa journée : elle est datée du lendemain.
- Le plafond est appliqué par le code, pas encore par un smart contract (prochaine étape).
