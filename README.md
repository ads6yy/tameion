# Tameion

Learning playground for the [Tameion Agents Hackathon](https://tameion.thecanteenapp.com/) (Canteen × Circle × Arc),
based on the article [Agents and Ledgers in 2026](https://thecanteenapp.com/analysis/2026/09/12/agents-and-ledgers.html).

> I'm new to blockchain. This repo is pure discovery: small experiments to learn and understand, not a product.
> Fake data, Arc **testnet** only.

## What it does

A [beancount](https://github.com/beancount/beancount) ledger that pays fake vendors in USDC on Arc testnet,
with the controls from the article: three-way match, vendor master check, no double payment,
and reconciliation of the ledger against the onchain balance (to the wei).

## Usage

```bash
uv sync && uv run pytest -q

uv run tameion init              # record the current onchain balance
uv run tameion invoices          # list invoices (F-003 is a trap)
uv run tameion book F-001        # book the invoice after controls
uv run tameion pay F-001         # dry run
uv run --env-file .env tameion pay F-001 --execute   # real testnet payment (key in .env, see .env.example)
uv run tameion reconcile         # onchain balance == ledger?
```

## Links

- [Arc docs](https://docs.arc.io) · [Circle Agent Stack](https://developers.circle.com/agent-stack) · [Arc testnet explorer](https://explorer.testnet.arc.io)
