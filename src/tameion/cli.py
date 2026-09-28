"""Commands: init, invoices, book, pay, reconcile, check."""
import argparse
import json
from datetime import date, datetime, timezone
from decimal import Decimal

from eth_account import Account

from . import config as cfg
from .amounts import usdc_to_wei, wei_to_usdc
from .chain import Chain
from .controls import check_invoice, check_payment
from .ledger import (
    CONTRIBUTION_ACCOUNT,
    GAS_ACCOUNT,
    PAYABLE_ACCOUNT,
    TREASURY_ACCOUNT,
    Ledger,
    reconciliation_record,
)


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _invoices(c: cfg.Config) -> dict[str, dict]:
    return {i["id"]: i for i in (_read_json(p) for p in sorted(c.invoices.glob("*.json")))}


def _invoice(c: cfg.Config, invoice_id: str) -> dict:
    invoices = _invoices(c)
    if invoice_id not in invoices:
        raise SystemExit(f"Unknown invoice: {invoice_id}")
    return invoices[invoice_id]


def _pending_sends(c: cfg.Config) -> dict[str, str]:
    """Last status per invoice; 'sent' without 'confirmed'/'failed' = pending."""
    last: dict[str, dict] = {}
    if c.sends.exists():
        for line in c.sends.read_text(encoding="utf-8").splitlines():
            if line.strip():
                s = json.loads(line)
                last[s["invoice"]] = s
    return {invoice_id: s["tx_hash"] for invoice_id, s in last.items() if s["status"] == "sent"}


def _log_send(c: cfg.Config, invoice_id: str, tx_hash: str, status: str) -> None:
    line = {"invoice": invoice_id, "tx_hash": tx_hash, "status": status, "timestamp": datetime.now(timezone.utc).isoformat()}
    with c.sends.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line) + "\n")


def _chain(c: cfg.Config) -> Chain:
    return Chain(c.rpc_url, c.chain_id, c.min_base_fee_gwei)


def cmd_init(c: cfg.Config, _args) -> None:
    ledger = Ledger(c.ledger)
    if ledger.has_contribution():
        raise SystemExit("Initial contribution already recorded.")
    block, balance_wei = _chain(c).balance_at_latest_block(c.wallet_address)
    balance = wei_to_usdc(balance_wei)
    today = date.today()
    ledger.append(
        f'{today} * "Initial contribution" "Balance observed on Arc testnet"\n'
        f'  kind: "contribution"\n'
        f"  {TREASURY_ACCOUNT}  {balance:f} USDC\n"
        f"  {CONTRIBUTION_ACCOUNT}  {-balance:f} USDC\n\n"
        + reconciliation_record(today, TREASURY_ACCOUNT, balance, block)
    )
    print(f"Initial contribution recorded: {balance:f} USDC")


def cmd_invoices(c: cfg.Config, _args) -> None:
    ledger = Ledger(c.ledger)
    booked, paid = ledger.invoices("invoice"), ledger.invoices("payment")
    vendors, purchase_orders = _read_json(c.vendors), _read_json(c.purchase_orders)
    for invoice_id, i in _invoices(c).items():
        status = "paid" if invoice_id in paid else "booked" if invoice_id in booked else "to book"
        print(f"{invoice_id}  {i['amount']} USDC  {vendors.get(i['vendor'], {}).get('name', i['vendor'])}  [{status}]")
        for r in check_invoice(i, vendors, purchase_orders):
            print(f"    REFUSED: {r}")


def cmd_book(c: cfg.Config, args) -> None:
    ledger = Ledger(c.ledger)
    invoice = _invoice(c, args.invoice)
    vendors, purchase_orders = _read_json(c.vendors), _read_json(c.purchase_orders)
    if invoice["id"] in ledger.invoices("invoice"):
        raise SystemExit(f"{invoice['id']} is already booked.")
    refusals = check_invoice(invoice, vendors, purchase_orders)
    if refusals:
        raise SystemExit("Booking refused:\n  " + "\n  ".join(refusals))
    vendor = vendors[invoice["vendor"]]
    amount = Decimal(invoice["amount"])
    ledger.append(
        f'{invoice["date"]} * "{vendor["name"]}" "Invoice {invoice["id"]}: {invoice["description"]}"\n'
        f'  kind: "invoice"\n'
        f'  invoice: "{invoice["id"]}"\n'
        f'  purchase_order: "{invoice["purchase_order"]}"\n'
        f'  document: "{c.invoices.relative_to(c.root) / (invoice["id"] + ".json")}"\n'
        f"  {vendor['expense_account']}  {amount:f} USDC\n"
        f"  {PAYABLE_ACCOUNT}  {-amount:f} USDC"
    )
    print(f"{invoice['id']} booked: {amount:f} USDC owed to {vendor['name']}")


def cmd_pay(c: cfg.Config, args) -> None:
    ledger = Ledger(c.ledger)
    invoice = _invoice(c, args.invoice)
    vendors, purchase_orders = _read_json(c.vendors), _read_json(c.purchase_orders)
    chain = _chain(c)
    value_wei = usdc_to_wei(Decimal(invoice["amount"]))

    # The vendor master is checked again at payment time: it may have changed since booking.
    refusals = check_invoice(invoice, vendors, purchase_orders) + check_payment(
        invoice,
        booked=ledger.invoices("invoice"),
        paid=ledger.invoices("payment"),
        pending_sends=_pending_sends(c),
        max_payment=c.max_payment,
        balance_wei=chain.balance_wei(c.wallet_address),
        max_cost_wei=chain.max_cost_wei(value_wei),
    )
    if refusals:
        raise SystemExit("Payment refused:\n  " + "\n  ".join(refusals))

    vendor = vendors[invoice["vendor"]]
    recipient = vendor["address"]
    print(f"Plan: {invoice['amount']} USDC ({value_wei} wei) from {c.wallet_address} to {vendor['name']} {recipient}")
    if not args.execute:
        print("Dry run only. Run again with --execute to send.")
        return

    key = cfg.private_key()
    if Account.from_key(key).address.lower() != c.wallet_address.lower():
        raise SystemExit("The private key does not match wallet.address in config.toml.")

    tx_hash = chain.send(key, recipient, value_wei)
    _log_send(c, invoice["id"], tx_hash, "sent")  # before waiting: a crash here blocks any retry
    print(f"Sent: {c.explorer_url}/tx/{tx_hash}")

    success, fee_wei, block = chain.wait(tx_hash)
    fee = wei_to_usdc(fee_wei)
    amount = Decimal(invoice["amount"])
    if not success:
        _log_send(c, invoice["id"], tx_hash, "failed")
        ledger.append(
            f'{date.today()} * "Arc" "Failed payment {invoice["id"]} (gas only)"\n'
            f'  tx_hash: "{tx_hash}"\n'
            f"  {GAS_ACCOUNT}  {fee:f} USDC\n"
            f"  {TREASURY_ACCOUNT}  {-fee:f} USDC"
        )
        raise SystemExit(f"Transaction reverted (block {block}): only gas was charged and recorded.")

    ledger.append(
        f'{date.today()} * "{vendor["name"]}" "Payment {invoice["id"]}"\n'
        f'  kind: "payment"\n'
        f'  invoice: "{invoice["id"]}"\n'
        f'  tx_hash: "{tx_hash}"\n'
        f'  block: "{block}"\n'
        f"  {PAYABLE_ACCOUNT}  {amount:f} USDC\n"
        f"  {GAS_ACCOUNT}  {fee:f} USDC\n"
        f"  {TREASURY_ACCOUNT}  {-(amount + fee):f} USDC"
    )
    _log_send(c, invoice["id"], tx_hash, "confirmed")
    print(f"Paid and recorded (block {block}, gas {fee:f} USDC). Run `tameion reconcile`.")


def cmd_reconcile(c: cfg.Config, _args) -> None:
    ledger = Ledger(c.ledger)
    block, balance_wei = _chain(c).balance_at_latest_block(c.wallet_address)
    onchain = wei_to_usdc(balance_wei)
    booked = ledger.balance(TREASURY_ACCOUNT)
    print(f"Onchain balance : {onchain:f} USDC (block {block})")
    print(f"Ledger balance  : {booked} USDC")
    if onchain != booked:
        raise SystemExit(
            f"MISMATCH of {onchain - booked} USDC: an operation is missing or wrong in the ledger. "
            "Nothing was written."
        )
    ledger.append(reconciliation_record(date.today(), TREASURY_ACCOUNT, onchain, block))
    print(f"Reconciled: record added to the ledger (block {block}).")


def cmd_check(c: cfg.Config, _args) -> None:
    errors = Ledger(c.ledger).check()
    if errors:
        raise SystemExit("Invalid ledger:\n  " + "\n  ".join(errors))
    print("Ledger is valid.")


def main() -> None:
    p = argparse.ArgumentParser(prog="tameion")
    sp = p.add_subparsers(dest="command", required=True)
    sp.add_parser("init", help="Record the initial contribution from the onchain balance").set_defaults(fn=cmd_init)
    sp.add_parser("invoices", help="List invoices and their controls").set_defaults(fn=cmd_invoices)
    s = sp.add_parser("book", help="Book an invoice after controls")
    s.add_argument("invoice")
    s.set_defaults(fn=cmd_book)
    s = sp.add_parser("pay", help="Pay an invoice (dry run by default)")
    s.add_argument("invoice")
    s.add_argument("--execute", action="store_true", help="Actually send the transaction")
    s.set_defaults(fn=cmd_pay)
    sp.add_parser("reconcile", help="Compare onchain balance with the ledger").set_defaults(fn=cmd_reconcile)
    sp.add_parser("check", help="Validate the ledger with beancount").set_defaults(fn=cmd_check)
    args = p.parse_args()
    args.fn(cfg.load(), args)
