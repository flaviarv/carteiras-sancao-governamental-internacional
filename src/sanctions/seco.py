# Carteiras sancionadas (Suíça/SECO)

import os
import re
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple
import requests
from lxml import etree

logger = logging.getLogger(__name__)


class SECOSanctionsEngine:
    """Motor de ingestão da base de sanções e embargos da Suíça (SECO / SESAM)."""

    SECO_XML_URL = "https://www.sesam.search.admin.ch/sesam-search-web/pages/downloadXmlExport.xhtml"

    PATTERNS = {
        "EVM": re.compile(r"^0x[a-fA-F0-9]{40}$"),
        "BITCOIN": re.compile(r"^(1|3)[a-km-zA-HJ-NP-Z1-9]{25,34}$|^bc1[a-z0-9]{38,87}$"),
        "SOLANA": re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$"),
        "TRON": re.compile(r"^T[a-km-zA-HJ-NP-Z1-9]{33}$"),
    }

    def __init__(self, data_path: Optional[str] = None):
        if data_path is None:
            root_dir = Path(__file__).resolve().parent.parent.parent
            self.data_path = str(root_dir / "data" / "carteiras" / "seco_sanctions.xml")
        else:
            self.data_path = data_path

        self.sanctioned_addresses: Dict[str, Dict[str, str]] = {}

    def sync_database(self, force_download: bool = False) -> None:
        os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
        if not os.path.exists(self.data_path) or force_download:
            logger.info("A descarregar lista de sanções da Suíça (SECO)...")
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(self.SECO_XML_URL, headers=headers, stream=True, timeout=60)
            response.raise_for_status()
            with open(self.data_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=65536):
                    f.write(chunk)
            logger.info("Download da base da Suíça concluído.")

    def _identify_crypto(self, value: str) -> Optional[Tuple[str, str]]:
        if self.PATTERNS["EVM"].match(value):
            return value.lower(), "EVM"
        if value.startswith("bc1") and self.PATTERNS["BITCOIN"].match(value.lower()):
            return value.lower(), "Bitcoin (Bech32)"
        if self.PATTERNS["TRON"].match(value):
            return value, "Tron"
        if self.PATTERNS["BITCOIN"].match(value):
            return value, "Bitcoin (Base58)"
        return None

    def load_sanctions(self) -> None:
        if not os.path.exists(self.data_path):
            self.sync_database()

        logger.info("A processar dados XML da Suíça (SECO)...")
        tree = etree.parse(self.data_path)
        root = tree.getroot()

        targets = root.xpath("//*[local-name()='target']")
        for target in targets:
            ssid = target.get("ssid", "Unknown")
            names = target.xpath(".//*[local-name()='name-part']/text()")
            entity_name = " ".join([str(n).strip() for n in names]) if names else "Swiss Sanctioned Target"

            details = target.xpath(".//*[local-name()='other-information']/text() | .//*[local-name()='justification']/text()")
            for detail in details:
                for token in re.split(r"[\s,;]+", str(detail)):
                    cleaned = token.strip()
                    crypto_match = self._identify_crypto(cleaned)
                    if crypto_match:
                        lookup_key, chain_name = crypto_match
                        self.sanctioned_addresses[lookup_key] = {
                            "source": "SWISS_SECO",
                            "chain": chain_name,
                            "sanctions_id": f"SECO-{ssid}",
                            "entity_name": entity_name,
                            "original_address": cleaned,
                        }

        logger.info(f"{len(self.sanctioned_addresses)} endereços únicos indexados da base da Suíça.")

    def is_sanctioned(self, address: str) -> Optional[Dict[str, str]]:
        raw = address.strip()
        return self.sanctioned_addresses.get(raw) or self.sanctioned_addresses.get(raw.lower())