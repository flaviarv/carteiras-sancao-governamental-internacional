# Carteiras sancionadas (Nações Unidas / CSNU)

import os
import re
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple
import pandas as pd
import requests
from lxml import etree

logger = logging.getLogger(__name__)


class UNSanctionsEngine:
    """Motor de ingestão da Lista Consolidada do Conselho de Segurança das Nações Unidas (ONU)."""

    UN_XML_URL = "https://scsanctions.un.org/resources/xml/en/consolidated.xml"
    COLUMNS = ["lookup_key", "source", "chain", "sanctions_id", "entity_name", "original_address", "nationality", "related_country"]

    PATTERNS = {
        "EVM": re.compile(r"^0x[a-fA-F0-9]{40}$"),
        "BITCOIN": re.compile(r"^(1|3)[a-km-zA-HJ-NP-Z1-9]{25,34}$|^bc1[a-z0-9]{38,87}$"),
        "MONERO": re.compile(
            r"^[48][0-9AB][1-9A-HJ-NP-Za-km-z]{93}$|^[48][0-9AB][1-9A-HJ-NP-Za-km-z]{104}$"
        ),
        "ZCASH": re.compile(
            r"^t[13][a-km-zA-HJ-NP-Z1-9]{33}$|^zs1[a-z0-9]{75}$|^u1[a-z0-9]{50,200}$"
        ),
        "SOLANA": re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$"),
        "TRON": re.compile(r"^T[a-km-zA-HJ-NP-Z1-9]{33}$"),
    }

    def __init__(self, data_path: Optional[str] = None):
        if data_path is None:
            root_dir = Path(__file__).resolve().parent.parent.parent
            self.data_path = str(root_dir / "data" / "carteiras" / "un_sanctions.parquet")
        else:
            self.data_path = data_path

        self.sanctioned_addresses: Dict[str, Dict[str, str]] = {}

    def _identify_crypto(self, value: str) -> Optional[Tuple[str, str]]:
        if self.PATTERNS["EVM"].match(value):
            return value.lower(), "EVM"
        if self.PATTERNS["MONERO"].match(value):
            return value, "Monero (XMR)"
        if self.PATTERNS["ZCASH"].match(value):
            return value, "Zcash (ZEC)"
        if value.startswith("bc1") and self.PATTERNS["BITCOIN"].match(value.lower()):
            return value.lower(), "Bitcoin (Bech32)"
        if self.PATTERNS["TRON"].match(value):
            return value, "Tron"
        if self.PATTERNS["BITCOIN"].match(value):
            return value, "Bitcoin (Base58)"
        if self.PATTERNS["SOLANA"].match(value):
            return value, "Solana"
        return None

    def _parse_xml_to_dict(self, xml_source) -> Dict[str, Dict[str, str]]:
        """Extrai os endereços cripto do XML da ONU para um dicionário estruturado."""
        records: Dict[str, Dict[str, str]] = {}
        tree = etree.parse(xml_source)
        root = tree.getroot()

        # O XML da ONU organiza os alvos em INDIVIDUAL e ENTITY
        targets = root.xpath("//*[local-name()='INDIVIDUAL' or local-name()='ENTITY']")
        for target in targets:
            dataid = target.xpath(".//*[local-name()='DATAID']/text()")
            dataid_val = dataid[0] if dataid else "Unknown"

            name_nodes = target.xpath(
                ".//*[local-name()='FIRST_NAME']/text() | .//*[local-name()='SECOND_NAME']/text()"
            )
            entity_name = (
                " ".join([str(n).strip() for n in name_nodes])
                if name_nodes
                else "UN Sanctioned Entity"
            )

            comments = target.xpath(".//*[local-name()='COMMENTS_NOTES']/text()")
            for comment in comments:
                for token in re.split(r"[\s,;]+", str(comment)):
                    cleaned = token.strip()
                    crypto_match = self._identify_crypto(cleaned)
                    if crypto_match:
                        lookup_key, chain_name = crypto_match
                        records[lookup_key] = {
                            "source": "UN_SECURITY_COUNCIL",
                            "chain": chain_name,
                            "sanctions_id": f"UN-{dataid_val}",
                            "entity_name": entity_name,
                            "original_address": cleaned,
                        }
        return records

    def sync_database(self, force_download: bool = False) -> None:
        os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
        legacy_xml = str(Path(self.data_path).with_suffix(".xml"))

        if not os.path.exists(self.data_path) or force_download:
            if os.path.exists(legacy_xml) and not force_download:
                logger.info("A converter un_sanctions.xml local para Parquet...")
                records = self._parse_xml_to_dict(legacy_xml)
            else:
                logger.info("A descarregar e converter lista consolidada da ONU para Parquet...")
                response = requests.get(self.UN_XML_URL, stream=True, timeout=60)
                response.raise_for_status()
                with open(legacy_xml, "wb") as f:
                    for chunk in response.iter_content(chunk_size=65536):
                        f.write(chunk)
                records = self._parse_xml_to_dict(legacy_xml)

            rows = [{"lookup_key": k, **v} for k, v in records.items()]
            df = pd.DataFrame(rows, columns=self.COLUMNS)
            df.to_parquet(self.data_path, engine="pyarrow", index=False)
            if os.path.exists(legacy_xml):
                os.remove(legacy_xml)
            logger.info(f"Base da ONU salva em Parquet ({len(records)} endereços).")

    def load_sanctions(self) -> None:
        if not os.path.exists(self.data_path):
            self.sync_database()

        logger.info("A processar base Parquet da ONU...")
        df = pd.read_parquet(self.data_path, engine="pyarrow")
        records = df.to_dict(orient="records")
        self.sanctioned_addresses = {row.pop("lookup_key"): row for row in records}

        logger.info(f"{len(self.sanctioned_addresses)} endereços únicos indexados da base da ONU.")

    def is_sanctioned(self, address: str) -> Optional[Dict[str, str]]:
        raw = address.strip()
        return self.sanctioned_addresses.get(raw) or self.sanctioned_addresses.get(raw.lower())