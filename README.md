# Tameion (test skeleton)

A **beancount** ledger + **native USDC payments on Arc testnet**, with the controls recommended by the
article *Agents and Ledgers in 2026*. Fake data, solo use. No LLM agent yet: these are the rails
it will run on.

## How it works

```
invoice (data/invoices) ─► controls ─► beancount entry ─► Arc payment ─► beancount entry ─► onchain reconciliation
```

| Idea from the article | Where it lives in the code |
|---|---|
| Three-way match (invoice / purchase order / goods receipt) | `controls.check_invoice` |
| Vendor master change control | invoice address compared with `data/vendors.json`; payments always go to the vendor master address |
| Every entry points to a document | `invoice`, `purchase_order`, `document`, `tx_hash` metadata |
| A witness before writing | `tameion reconcile` compares the onchain balance (read at a precise block) with the ledger, to the wei, and refuses on any mismatch; the check is recorded as a `custom "reconciliation"` directive |
| Refuse rather than repair | `Ledger.append` restores the file if beancount rejects it; amounts are `Decimal`, exactly 6 decimals on invoices, 18 for gas |
| Idempotency / no double payment | `data/sends.jsonl` is written **before** waiting for confirmation; an unconfirmed send blocks any retry |
| Limits the tool cannot bypass | `max_payment_usdc` cap in `config.toml` (enforced in code for now, not yet in a contract) |

## Setup

```bash
uv sync
uv run pytest -q
```

## Walkthrough

```bash
uv run tameion init                 # records the onchain balance as the initial contribution
uv run tameion invoices             # lists invoices; F-003 is a trap (different address, no goods receipt)
uv run tameion book F-001
uv run tameion pay F-001            # dry run: prints the plan, sends nothing
```

To actually pay, the program reads the key from the `TAMEION_PRIVATE_KEY` environment variable
(it does **not** read `.env` itself). Two ways to provide it:

```bash
# a) .env file (ignored by git), loaded by uv on each command
cp .env.example .env                # then put the key in it
uv run --env-file .env tameion pay F-001 --execute

# b) variable exported in the current terminal only
export TAMEION_PRIVATE_KEY=$(sed -n 's/^private_key: *//p' ~/.arc-canteen/wallet.yaml)
uv run tameion pay F-001 --execute
```

Then:

```bash
uv run tameion reconcile            # onchain == ledger, otherwise MISMATCH
uv run tameion check
```

Useful experiments:
- run `pay F-001 --execute` again: refused (already paid);
- `book F-003`: refused (changed address, no goods receipt);
- send a few cents from your wallet outside the tool, or top it up from a faucet, then `reconcile`: the mismatch is detected.

View the ledger: `uvx fava ledger/main.beancount` (optional, not installed in the project).

## Known limitations

- Vendor addresses are throwaway (keys not kept): USDC sent to them is lost, keep amounts small.
- Reconciliations are `custom` directives, not `balance` assertions (which hold for a whole day and would
  block later operations on the same day): `bean-check` does not re-verify them, only a new `reconcile` does.
- Incoming or outgoing funds moved outside the tool, and sends stuck in `sent`, must be recorded by hand.
- The cap is enforced by code, not yet by a smart contract (next step).
