import os
import re
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple
import requests
from lxml import etree

logger = logging.getLogger(__name__)


class EUSanctionsEngine:
    """Motor de ingestão e consulta da lista de sanções financeiras da União Europeia."""

    # Endpoint oficial de download do XML consolidado da UE
    EU_XML_URL = "https://webgate.ec.europa.eu/europeaid/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content?token=dG9rZW4tMjAxNw"

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
            self.data_path = str(root_dir / "data" / "carteiras" / "eu_sanctions.xml")
        else:
            self.data_path = data_path

        self.sanctioned_addresses: Dict[str, Dict[str, str]] = {}

    def sync_database(self, force_download: bool = False) -> None:
        """Garante o download do XML da União Europeia para data/."""
        os.makedirs(os.path.dirname(self.data_path), exist_ok=True)

        if not os.path.exists(self.data_path) or force_download:
            logger.info("A descarregar lista oficial de sanções da União Europeia...")
            response = requests.get(self.EU_XML_URL, stream=True, timeout=60)
            response.raise_for_status()
            with open(self.data_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=65536):
                    f.write(chunk)
            logger.info("Download da base da UE concluído com sucesso.")

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
        """Carrega e indexa os endereços da lista da União Europeia."""
        if not os.path.exists(self.data_path):
            self.sync_database()

        logger.info("A processar dados XML da União Europeia...")
        tree = etree.parse(self.data_path)
        root = tree.getroot()

        # O XML da UE armazena entidades em <sanctionEntity>
        entities = root.xpath("//*[local-name()='sanctionEntity']")

        for entity in entities:
            entity_id = entity.get("logicalId", "Unknown")

            # Nome da entidade
            name_nodes = entity.xpath(".//*[local-name()='nameAlias']/@wholeName")
            entity_name = name_nodes[0].strip() if name_nodes else "EU Sanctioned Entity"

            # A UE frequentemente coloca endereços cripto em campos de identificação ou comentários
            text_nodes = entity.xpath(".//*[local-name()='identification']/@number | .//*[local-name()='remark']/text()")

            for text_val in text_nodes:
                # O texto da UE pode vir com mais de um endereço ou descrições no mesmo campo
                tokens = re.split(r"[\s,;]+", str(text_val))
                for token in tokens:
                    cleaned_val = token.strip()
                    crypto_match = self._identify_crypto(cleaned_val)
                    if crypto_match:
                        lookup_key, chain_name = crypto_match
                        self.sanctioned_addresses[lookup_key] = {
                            "source": "EU",
                            "chain": chain_name,
                            "sanctions_id": f"EU-{entity_id}",
                            "entity_name": entity_name,
                            "original_address": cleaned_val,
                        }

        logger.info(f"{len(self.sanctioned_addresses)} endereços únicos indexados da base da UE.")

    def is_sanctioned(self, address: str) -> Optional[Dict[str, str]]:
        raw_clean = address.strip()
        if raw_clean in self.sanctioned_addresses:
            return self.sanctioned_addresses[raw_clean]
        lower_clean = raw_clean.lower()
        if lower_clean in self.sanctioned_addresses:
            return self.sanctioned_addresses[lower_clean]
        return None