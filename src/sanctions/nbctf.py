import os
import re
import csv
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple
import requests

logger = logging.getLogger(__name__)


class NBCTFSanctionsEngine:
    """Motor de ingestão da lista completa consolidada de carteiras sancionadas por Israel (NBCTF)."""

    # Dataset aberto e consolidado de todas as ordens de apreensão do NBCTF (dataset: il_mod_crypto)
    NBCTF_CSV_URL = "https://data.opensanctions.org/datasets/latest/il_mod_crypto/targets.simple.csv"

    PATTERNS = {
        "EVM": re.compile(r"^0x[a-fA-F0-9]{40}$"),
        "BITCOIN": re.compile(r"^(1|3)[a-km-zA-HJ-NP-Z1-9]{25,34}$|^bc1[a-z0-9]{38,87}$"),
        "SOLANA": re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$"),
        "TRON": re.compile(r"^T[a-km-zA-HJ-NP-Z1-9]{33}$"),
        "LITECOIN": re.compile(r"^(L|M)[a-km-zA-HJ-NP-Z1-9]{26,34}$|^ltc1[a-z0-9]{39,59}$"),
        "RIPPLE": re.compile(r"^r[0-9a-zA-Z]{24,34}$"),
    }

    def __init__(self, data_path: Optional[str] = None):
        if data_path is None:
            root_dir = Path(__file__).resolve().parent.parent.parent
            self.data_path = str(root_dir / "data" / "carteiras" / "israel_nbctf.csv")
        else:
            self.data_path = data_path

        self.sanctioned_addresses: Dict[str, Dict[str, str]] = {}

    def sync_database(self, force_download: bool = False) -> None:
        """Garante o download de todas as ordens de apreensão de Israel para a pasta data/."""
        os.makedirs(os.path.dirname(self.data_path), exist_ok=True)

        if not os.path.exists(self.data_path) or force_download:
            logger.info("A descarregar lista completa de apreensões de cripto de Israel (NBCTF)...")
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(self.NBCTF_CSV_URL, headers=headers, stream=True, timeout=60)
            response.raise_for_status()
            with open(self.data_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=65536):
                    f.write(chunk)
            logger.info("Base completa de Israel descarregada com sucesso.")

    def _identify_crypto(self, value: str) -> Optional[Tuple[str, str]]:
        if self.PATTERNS["EVM"].match(value):
            return value.lower(), "EVM"
        if value.startswith("bc1") and self.PATTERNS["BITCOIN"].match(value.lower()):
            return value.lower(), "Bitcoin (Bech32)"
        if self.PATTERNS["TRON"].match(value):
            return value, "Tron"
        if self.PATTERNS["BITCOIN"].match(value):
            return value, "Bitcoin (Base58)"
        if self.PATTERNS["SOLANA"].match(value):
            return value, "Solana"
        if self.PATTERNS["RIPPLE"].match(value):
            return value, "Ripple"
        if self.PATTERNS["LITECOIN"].match(value):
            return value, "Litecoin"
        return None

    def load_sanctions(self) -> None:
        """Processa o CSV consolidado e indexa todas as carteiras em memória RAM."""
        if not os.path.exists(self.data_path):
            self.sync_database()

        logger.info("A processar base completa do NBCTF (Israel)...")
        with open(self.data_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # O CSV targets.simple.csv possui as colunas 'id', 'name', 'schema', 'properties'
                entity_id = row.get("id", "Unknown")
                entity_name = row.get("name", "NBCTF Terror-Financing Target")
                
                # Varre os campos em busca de endereços cripto válidos
                for field in [row.get("name", ""), row.get("aliases", ""), row.get("id", "")]:
                    for token in re.split(r"[\s,;:|]+", str(field)):
                        cleaned = token.strip()
                        crypto_match = self._identify_crypto(cleaned)
                        if crypto_match:
                            lookup_key, chain_name = crypto_match
                            self.sanctioned_addresses[lookup_key] = {
                                "source": "ISRAEL_NBCTF",
                                "chain": chain_name,
                                "sanctions_id": f"NBCTF-{entity_id}",
                                "entity_name": entity_name,
                                "original_address": cleaned,
                            }

        logger.info(f"{len(self.sanctioned_addresses)} carteiras únicas indexadas da base completa de Israel.")

    def is_sanctioned(self, address: str) -> Optional[Dict[str, str]]:
        raw = address.strip()
        return self.sanctioned_addresses.get(raw) or self.sanctioned_addresses.get(raw.lower())