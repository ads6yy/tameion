"""Lecture et écriture du grand livre beancount. Toute écriture est validée par beancount, sinon annulée."""
from decimal import Decimal
from pathlib import Path

from beancount import loader
from beancount.core import data

COMPTE_TRESORERIE = "Assets:Arc:Tresorerie"
COMPTE_FOURNISSEURS = "Liabilities:Fournisseurs"
COMPTE_GAS = "Expenses:Frais:Gas"
COMPTE_APPORT = "Equity:Apport"


def constat_rapprochement(jour, compte: str, solde: Decimal, bloc: int) -> str:
    """Directive `custom` et non `balance` : une assertion beancount vaut pour toute une journée
    et deviendrait fausse à la première opération suivante du même jour."""
    return f'{jour} custom "rapprochement" {compte} {solde:f} USDC\n  bloc: "{bloc}"'


class GrandLivre:
    def __init__(self, chemin: Path):
        self.chemin = chemin

    def charger(self):
        entrees, erreurs, _ = loader.load_file(str(self.chemin))
        return entrees, erreurs

    def verifier(self) -> list[str]:
        _, erreurs = self.charger()
        return [f"{e.source.get('filename', '?')}:{e.source.get('lineno', '?')} {e.message}" for e in erreurs]

    def ajouter(self, texte: str) -> None:
        """Ajoute un bloc, puis le retire si beancount refuse le fichier (pas de réparation silencieuse)."""
        avant = self.chemin.read_text(encoding="utf-8")
        self.chemin.write_text(avant.rstrip("\n") + "\n\n" + texte.strip("\n") + "\n", encoding="utf-8")
        erreurs = self.verifier()
        if erreurs:
            self.chemin.write_text(avant, encoding="utf-8")
            raise SystemExit("Écriture refusée par beancount, fichier restauré :\n  " + "\n  ".join(erreurs))

    def _transactions(self):
        entrees, _ = self.charger()
        return [e for e in entrees if isinstance(e, data.Transaction)]

    def factures(self, nature: str) -> set[str]:
        """Identifiants de factures ayant une écriture de cette nature ('facture' ou 'paiement')."""
        return {t.meta["facture"] for t in self._transactions() if t.meta.get("nature") == nature and "facture" in t.meta}

    def a_un_apport(self) -> bool:
        return any(p.account == COMPTE_APPORT for t in self._transactions() for p in t.postings)

    def solde(self, compte: str) -> Decimal:
        total = Decimal(0)
        for t in self._transactions():
            for p in t.postings:
                if p.account == compte:
                    total += p.units.number
        return total
