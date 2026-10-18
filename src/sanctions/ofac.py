import os
import re
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple
import requests
from lxml import etree

# Configuração básica de log para a biblioteca
logger = logging.getLogger(__name__)


class OFACSanctionsEngine:
    OFAC_XML_URL = "https://www.treasury.gov/ofac/downloads/sanctions/1.0/sdn_advanced.xml"

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
            self.data_path = str(root_dir / "data" / "carteiras" / "sdn_advanced.xml")
        else:
            self.data_path = data_path

        self.sanctioned_addresses: Dict[str, Dict[str, str]] = {}

        self.sanctioned_addresses: Dict[str, Dict[str, str]] = {}

    def sync_database(self, force_download: bool = False) -> None:
        """Transfere o ficheiro oficial da OFAC para o diretório data/."""
        os.makedirs(os.path.dirname(self.data_path), exist_ok=True)

        if not os.path.exists(self.data_path) or force_download:
            logger.info("A descarregar lista oficial sdn_advanced.xml da OFAC...")
            response = requests.get(self.OFAC_XML_URL, stream=True, timeout=60)
            response.raise_for_status()
            with open(self.data_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=65536):
                    f.write(chunk)
            logger.info("Download concluído com sucesso.")

    def _identify_crypto(self, value: str) -> Optional[Tuple[str, str]]:
        if self.PATTERNS["EVM"].match(value):
            return value.lower(), "EVM"
        if value.startswith("bc1") and self.PATTERNS["BITCOIN"].match(value.lower()):
            return value.lower(), "Bitcoin (Bech32)"
        if value.startswith("ltc1") and self.PATTERNS["LITECOIN"].match(value.lower()):
            return value.lower(), "Litecoin (Bech32)"
        if self.PATTERNS["TRON"].match(value):
            return value, "Tron"
        if self.PATTERNS["BITCOIN"].match(value):
            return value, "Bitcoin (Base58)"
        if self.PATTERNS["LITECOIN"].match(value):
            return value, "Litecoin (Base58)"
        if self.PATTERNS["RIPPLE"].match(value):
            return value, "Ripple"
        if self.PATTERNS["SOLANA"].match(value):
            return value, "Solana"
        return None

    def load_sanctions(self) -> None:
        """Carrega e indexa os endereços da lista de sanções da OFAC."""
        if not os.path.exists(self.data_path):
            self.sync_database()

        logger.info("A processar dados XML da OFAC...")
        tree = etree.parse(self.data_path)
        root = tree.getroot()

        # O XML da OFAC agrupa pessoas e entidades em DistinctParty ou Profile
        # Cada endereço de carteira é armazenado sob nós Feature / VersionDetail
        features = root.xpath("//*[local-name()='Feature']")

        for feature in features:
            # No sdn_advanced.xml, o texto do endereço fica em VersionDetail ou Value
            detail_nodes = feature.xpath(".//*[local-name()='VersionDetail']/text() | .//*[local-name()='Value']/text()")
            
            for text_val in detail_nodes:
                cleaned_val = str(text_val).strip()
                crypto_match = self._identify_crypto(cleaned_val)
                
                if crypto_match:
                    lookup_key, chain_name = crypto_match
                    
                    # Sobe na hierarquia para encontrar a entidade dona deste Feature
                    # (geralmente DistinctParty ou Profile)
                    party = feature.xpath("ancestor::*[local-name()='DistinctParty' or local-name()='Profile'][1]")
                    
                    entry_id = "Unknown"
                    entity_name = "OFAC Sanctioned Entity"
                    
                    if party:
                        party_el = party[0]
                        entry_id = party_el.get("ID", party_el.get("FixedRef", "Unknown"))
                        # Extrai o nome da entidade
                        names = party_el.xpath(".//*[local-name()='NamePartValue']/text() | .//*[local-name()='FormattedFullName']/text()")
                        if names:
                            entity_name = " ".join([str(n).strip() for n in names[:2]])

                    self.sanctioned_addresses[lookup_key] = {
                        "chain": chain_name,
                        "sanctions_id": entry_id,
                        "entity_name": entity_name,
                        "original_address": cleaned_val,
                    }

        logger.info(f"{len(self.sanctioned_addresses)} endereços únicos indexados.")

    def is_sanctioned(self, address: str) -> Optional[Dict[str, str]]:
        """Verifica se um endereço consta da lista sancionada."""
        raw_clean = address.strip()
        if raw_clean in self.sanctioned_addresses:
            return self.sanctioned_addresses[raw_clean]
        lower_clean = raw_clean.lower()
        if lower_clean in self.sanctioned_addresses:
            return self.sanctioned_addresses[lower_clean]
        return None