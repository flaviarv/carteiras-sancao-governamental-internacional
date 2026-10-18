# Carteiras sancionadas (Reino Unido - FCDO/OFSI)

import os
import re
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple
import requests
from lxml import etree

logger = logging.getLogger(__name__)


class UKSanctionsEngine:
    """Motor de ingestão da lista oficial de sanções do Reino Unido (UK Sanctions List / OFSI)."""

    UK_XML_URL = "https://sanctionslist.fcdo.gov.uk/docs/UK-Sanctions-List.xml"

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
            self.data_path = str(root_dir / "data" / "carteiras" / "uk_sanctions.xml")
        else:
            self.data_path = data_path

        self.sanctioned_addresses: Dict[str, Dict[str, str]] = {}

    def sync_database(self, force_download: bool = False) -> None:
        os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
        if not os.path.exists(self.data_path) or force_download:
            logger.info("A descarregar lista de sanções do Reino Unido (UK/OFSI)...")
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(self.UK_XML_URL, headers=headers, stream=True, timeout=60)
            response.raise_for_status()
            with open(self.data_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=65536):
                    f.write(chunk)
            logger.info("Download da base do Reino Unido concluído.")

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
        return None

    def load_sanctions(self) -> None:
        if not os.path.exists(self.data_path):
            self.sync_database()

        logger.info("A processar dados XML do Reino Unido...")
        tree = etree.parse(self.data_path)
        root = tree.getroot()

        # O XML britânico estrutura entidades sob Designation
        designations = root.xpath("//*[local-name()='Designation']")
        for desig in designations:
            desig_id = desig.xpath(".//*[local-name()='UniqueID']/text()")
            desig_id_val = desig_id[0] if desig_id else "Unknown"

            name_nodes = desig.xpath(".//*[local-name()='Name6']/text() | .//*[local-name()='Name1']/text()")
            entity_name = " ".join([str(n).strip() for n in name_nodes]) if name_nodes else "UK Sanctioned Target"

            # Busca em campos de texto livre, endereços e notas cripto
            texts = desig.xpath(".//*[local-name()='OtherInformation']/text() | .//*[local-name()='AddressLine']/text()")
            for text in texts:
                for token in re.split(r"[\s,;]+", str(text)):
                    cleaned = token.strip()
                    crypto_match = self._identify_crypto(cleaned)
                    if crypto_match:
                        lookup_key, chain_name = crypto_match
                        self.sanctioned_addresses[lookup_key] = {
                            "source": "UK_OFSI",
                            "chain": chain_name,
                            "sanctions_id": f"UK-{desig_id_val}",
                            "entity_name": entity_name,
                            "original_address": cleaned,
                        }

        logger.info(f"{len(self.sanctioned_addresses)} endereços únicos indexados da base do Reino Unido.")

    def is_sanctioned(self, address: str) -> Optional[Dict[str, str]]:
        raw = address.strip()
        return self.sanctioned_addresses.get(raw) or self.sanctioned_addresses.get(raw.lower())