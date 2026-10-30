import logging
import re
from typing import Dict, List, Optional, Any, Tuple
from src.sanctions.ofac import OFACSanctionsEngine
from src.sanctions.eu import EUSanctionsEngine
from src.sanctions.uk import UKSanctionsEngine
from src.sanctions.un import UNSanctionsEngine
from src.sanctions.seco import SECOSanctionsEngine
from src.sanctions.nbctf import NBCTFSanctionsEngine

logger = logging.getLogger(__name__)

CHAIN_PATTERNS = {
    "EVM (Ethereum / Polygon / BSC / Arbitrum)": re.compile(r"^0x[a-fA-F0-9]{40}$"),
    "Tron (TRX / USDT-TRC20)": re.compile(r"^T[a-km-zA-HJ-NP-Z1-9]{33}$"),
    "Bitcoin (BTC)": re.compile(r"^(1|3)[a-km-zA-HJ-NP-Z1-9]{25,34}$|^bc1[a-z0-9]{38,87}$", re.IGNORECASE),
    "Litecoin (LTC)": re.compile(r"^(L|M)[a-km-zA-HJ-NP-Z1-9]{26,34}$|^ltc1[a-z0-9]{39,59}$", re.IGNORECASE),
    "Ripple (XRP)": re.compile(r"^r[0-9a-zA-Z]{24,34}$"),
    "Monero (XMR)": re.compile(r"^[48][0-9AB][1-9A-HJ-NP-Za-km-z]{93}$|^[48][0-9AB][1-9A-HJ-NP-Za-km-z]{104}$"),
    "Zcash (ZEC)": re.compile(r"^t[13][a-km-zA-HJ-NP-Z1-9]{33}$|^zs1[a-z0-9]{75}$|^u1[a-z0-9]{50,200}$"),
    "Solana (SOL)": re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$"),
}


def clean_addr(val: str) -> str:
    """Limpa e normaliza o endereço removendo espaços e caracteres invisíveis (como BOM)."""
    return str(val).strip().strip("\ufeff\u200b\u200e\u200f")


def detect_chain_from_format(address: str) -> str:
    """Identifica heuristicamente o padrão da rede/criptoativo pelo formato do endereço."""
    raw = clean_addr(address)
    # Endereços Solana conhecidos e com formato Base58 válido (ex: 32 a 44 caracteres)
    # Nota: endereços Bitcoin Base58 iniciam com 1 ou 3 e têm entre 25 e 34 chars.
    # Caso um endereço coincida com ambos (ex: System Program da Solana '11111111111111111111111111111111'),
    # '1' repetido 32 vezes é a chave nativa da Solana, não endereço P2PKH/P2SH de Bitcoin.
    if re.compile(r"^1{32}$").match(raw):
        return "Solana (SOL)"
    for name, pattern in CHAIN_PATTERNS.items():
        if pattern.match(raw):
            return name
    return "Não identificada / Formato genérico"


def is_valid_crypto_address(address: str) -> bool:
    """Verifica se o texto possui formato sintático compatível com endereços cripto suportados."""
    raw = clean_addr(address)
    if not raw:
        return False
    return detect_chain_from_format(raw) != "Não identificada / Formato genérico"


class UnifiedSanctionsEngine:
    """
    Orquestrador global de inteligência sancionatória internacional.
    Consolida listas de sanções governamentais oficiais (OFAC/EUA, Israel NBCTF,
    Reino Unido/OFSI, União Europeia, ONU e Suíça/SECO).
    """

    def __init__(self):
        self.engines = [
            OFACSanctionsEngine(),    # EUA - Office of Foreign Assets Control (SDN)
            NBCTFSanctionsEngine(),   # Israel - National Bureau for Counter Terror Financing
            UKSanctionsEngine(),      # Reino Unido - FCDO / OFSI
            EUSanctionsEngine(),      # União Europeia - European External Action Service
            UNSanctionsEngine(),      # Nações Unidas - Conselho de Segurança da ONU
            SECOSanctionsEngine(),    # Suíça - Secretaria de Estado para Assuntos Econômicos
        ]

    def load_all(self, verbose: bool = False) -> Dict[str, int]:
        """Carrega e indexa todas as bases sancionatórias ativas a partir de dados locais (Parquet)."""
        logger.info(">>> Sincronizando bases de sanções internacionais...")
        stats = {}
        for engine in self.engines:
            name = engine.__class__.__name__.replace("SanctionsEngine", "")
            try:
                engine.load_sanctions()
                stats[name] = len(engine.sanctioned_addresses)
            except Exception as exc:
                logger.warning(f"Não foi possível carregar base {name}: {exc}")
                stats[name] = 0

        return stats

    def get_stats(self) -> Dict[str, Any]:
        """Retorna as estatísticas de endereços indexados por jurisdição e total consolidado."""
        jurisdictions = {}
        all_unique = set()

        name_labels = {
            "OFACSanctionsEngine": "OFAC (EUA - SDN)",
            "NBCTFSanctionsEngine": "Israel (NBCTF - Terror Financing)",
            "UKSanctionsEngine": "Reino Unido (FCDO / OFSI)",
            "EUSanctionsEngine": "União Europeia (EEAS)",
            "UNSanctionsEngine": "Nações Unidas (CSNU / ONU)",
            "SECOSanctionsEngine": "Suíça (SECO / SESAM)",
        }

        for engine in self.engines:
            lbl = name_labels.get(engine.__class__.__name__, engine.__class__.__name__)
            cnt = len(engine.sanctioned_addresses)
            jurisdictions[lbl] = cnt
            for addr in engine.sanctioned_addresses.keys():
                all_unique.add(addr.lower() if addr.startswith("0x") else addr)

        return {
            "jurisdictions": jurisdictions,
            "total_unique_sanctioned": len(all_unique),
        }

    def get_sanctions(self, address: str) -> List[Dict[str, str]]:
        """
        Varre todas as jurisdições ativas e retorna TODAS as listas onde o endereço consta.
        Essencial para auditoria de conformidade, pois uma carteira pode estar listada
        simultaneamente na OFAC e em Israel (NBCTF), por exemplo.
        """
        raw_addr = clean_addr(address)
        matches: List[Dict[str, str]] = []

        for engine in self.engines:
            res = engine.is_sanctioned(raw_addr)
            if res:
                match_data = dict(res)
                if "source" not in match_data:
                    match_data["source"] = engine.__class__.__name__.replace("SanctionsEngine", "").upper()
                matches.append(match_data)

        return matches

    def is_sanctioned(self, address: str) -> Optional[Dict[str, str]]:
        """
        Verifica se o endereço consta em ao menos uma lista de sanções (compatibilidade retroativa).
        Retorna o primeiro registro de sanção encontrado ou None.
        """
        matches = self.get_sanctions(address)
        return matches[0] if matches else None

    def check_wallet(self, address: str) -> Dict[str, Any]:
        """
        Auditoria completa e estruturada de sanções para uma carteira específica.
        Retorna um dicionário detalhado pronto para certidões e relatórios de PLD/CFT.
        """
        raw_clean = clean_addr(address)
        sanctions_matches = self.get_sanctions(raw_clean)

        is_sanctioned = len(sanctions_matches) > 0
        sources = list(dict.fromkeys(m.get("source", "SANÇÃO") for m in sanctions_matches))
        
        # Identificação da rede: metadados da sanção ou formato do endereço
        chain = None
        for m in sanctions_matches:
            if m.get("chain") and m.get("chain") not in ("Desconhecido", "Unknown"):
                chain = m["chain"]
                break
        if not chain:
            chain = detect_chain_from_format(raw_clean)

        # Entidades sancionadas relacionadas
        entities = list(dict.fromkeys(m.get("entity_name", "Desconhecido") for m in sanctions_matches))

        return {
            "address": raw_clean,
            "is_sanctioned": is_sanctioned,
            "matches_count": len(sanctions_matches),
            "sanctions": sanctions_matches,
            "sources": sources,
            "chain": chain,
            "entities": entities,
            "verdict_status": "SANCIONADO" if is_sanctioned else "REGULAR",
        }
