# Carteiras sancionadas (Suíça/SECO)

import os
import re
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple
import pandas as pd
import requests
from lxml import etree

logger = logging.getLogger(__name__)


class SECOSanctionsEngine:
    """Motor de ingestão da base de sanções e embargos da Suíça (SECO / SESAM)."""

    SECO_XML_URL = "https://www.sesam.search.admin.ch/sesam-search-web/pages/downloadXmlExport.xhtml"
    SECO_CSV_FALLBACK_URL = (
        "https://data.opensanctions.org/datasets/latest/ch_seco_sanctions/targets.simple.csv"
    )
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
            self.data_path = str(root_dir / "data" / "carteiras" / "seco_sanctions.parquet")
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
        return None

    def _parse_xml_to_dict(self, xml_source) -> Dict[str, Dict[str, str]]:
        """Extrai os endereços cripto do XML da Suíça (SECO) para um dicionário estruturado."""
        records: Dict[str, Dict[str, str]] = {}
        tree = etree.parse(xml_source)
        root = tree.getroot()

        targets = root.xpath("//*[local-name()='target']")
        for target in targets:
            ssid = target.get("ssid", "Unknown")
            names = target.xpath(".//*[local-name()='name-part']/text()")
            entity_name = (
                " ".join([str(n).strip() for n in names])
                if names
                else "Swiss Sanctioned Target"
            )

            details = target.xpath(
                ".//*[local-name()='other-information']/text() | .//*[local-name()='justification']/text()"
            )
            for detail in details:
                for token in re.split(r"[\s,;]+", str(detail)):
                    cleaned = token.strip()
                    crypto_match = self._identify_crypto(cleaned)
                    if crypto_match:
                        lookup_key, chain_name = crypto_match
                        records[lookup_key] = {
                            "source": "SWISS_SECO",
                            "chain": chain_name,
                            "sanctions_id": f"SECO-{ssid}",
                            "entity_name": entity_name,
                            "original_address": cleaned,
                        }
        return records

    def _parse_csv_text_to_dict(self, csv_text: str) -> Dict[str, Dict[str, str]]:
        import csv
        import io

        records: Dict[str, Dict[str, str]] = {}
        reader = csv.DictReader(io.StringIO(csv_text))
        for row in reader:
            entity_id = row.get("id", "Unknown")
            entity_name = row.get("name", "Swiss Sanctioned Target")
            for field in [row.get("name", ""), row.get("aliases", ""), row.get("identifiers", "")]:
                for token in re.split(r"[\s,;:|]+", str(field)):
                    cleaned = token.strip()
                    crypto_match = self._identify_crypto(cleaned)
                    if crypto_match:
                        lookup_key, chain_name = crypto_match
                        records[lookup_key] = {
                            "source": "SWISS_SECO",
                            "chain": chain_name,
                            "sanctions_id": f"SECO-{entity_id}",
                            "entity_name": entity_name,
                            "original_address": cleaned,
                        }
        return records

    def sync_database(self, force_download: bool = False) -> None:
        os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
        legacy_xml = str(Path(self.data_path).with_suffix(".xml"))

        if not os.path.exists(self.data_path) or force_download:
            if os.path.exists(legacy_xml) and not force_download:
                logger.info("A converter seco_sanctions.xml local para Parquet...")
                records = self._parse_xml_to_dict(legacy_xml)
            else:
                logger.info("A descarregar e converter lista de sanções da Suíça (SECO) para Parquet...")
                headers = {"User-Agent": "Mozilla/5.0"}
                try:
                    response = requests.get(
                        self.SECO_XML_URL, headers=headers, stream=True, timeout=30
                    )
                    response.raise_for_status()
                    with open(legacy_xml, "wb") as f:
                        for chunk in response.iter_content(chunk_size=65536):
                            f.write(chunk)
                    records = self._parse_xml_to_dict(legacy_xml)
                except Exception:
                    response = requests.get(
                        self.SECO_CSV_FALLBACK_URL, headers=headers, timeout=60
                    )
                    response.raise_for_status()
                    records = self._parse_csv_text_to_dict(response.text)

            rows = [{"lookup_key": k, **v} for k, v in records.items()]
            df = pd.DataFrame(rows, columns=self.COLUMNS)
            df.to_parquet(self.data_path, engine="pyarrow", index=False)
            if os.path.exists(legacy_xml):
                os.remove(legacy_xml)
            logger.info(f"Base da Suíça salva em Parquet ({len(records)} endereços).")

    def load_sanctions(self) -> None:
        if not os.path.exists(self.data_path):
            self.sync_database()

        logger.info("A processar base Parquet da Suíça (SECO)...")
        df = pd.read_parquet(self.data_path, engine="pyarrow")
        records = df.to_dict(orient="records")
        self.sanctioned_addresses = {row.pop("lookup_key"): row for row in records}

        logger.info(f"{len(self.sanctioned_addresses)} endereços únicos indexados da base da Suíça.")

    def is_sanctioned(self, address: str) -> Optional[Dict[str, str]]:
        raw = address.strip()
        return self.sanctioned_addresses.get(raw) or self.sanctioned_addresses.get(raw.lower())