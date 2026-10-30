"""Mapeamento das fontes de sanções para a jurisdição (país/bloco) que as emite."""

from typing import Dict, Tuple

# source (valor gravado nas bases) -> (país/bloco, sigla da lista)
JURISDICTIONS: Dict[str, Tuple[str, str]] = {
    "OFAC": ("Estados Unidos", "OFAC"),
    "ISRAEL_NBCTF": ("Israel", "NBCTF"),
    "UK_OFSI": ("Reino Unido", "OFSI"),
    "EU": ("União Europeia", "EEAS"),
    "UN_SECURITY_COUNCIL": ("Nações Unidas", "Conselho de Segurança"),
    "SWISS_SECO": ("Suíça", "SECO"),
}


def jurisdiction_label(source: str) -> str:
    """Ex.: 'OFAC' -> 'Estados Unidos (OFAC)'."""
    country, agency = JURISDICTIONS.get(source, (source, ""))
    return f"{country} ({agency})" if agency else country
