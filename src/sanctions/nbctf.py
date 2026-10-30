import os
import re
import csv
import json
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple
import pandas as pd
import requests

logger = logging.getLogger(__name__)


class NBCTFSanctionsEngine:
    """Motor de ingestão da lista completa consolidada de carteiras sancionadas por Israel (NBCTF)."""

    # Dataset aberto e consolidado de todas as ordens de apreensão do NBCTF (dataset: il_mod_crypto)
    NBCTF_CSV_URL = "https://data.opensanctions.org/datasets/latest/il_mod_crypto/targets.simple.csv"
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
        "LITECOIN": re.compile(r"^(L|M)[a-km-zA-HJ-NP-Z1-9]{26,34}$|^ltc1[a-z0-9]{39,59}$"),
        "RIPPLE": re.compile(r"^r[0-9a-zA-Z]{24,34}$"),
    }

    def __init__(self, data_path: Optional[str] = None):
        if data_path is None:
            root_dir = Path(__file__).resolve().parent.parent.parent
            self.data_path = str(root_dir / "data" / "carteiras" / "israel_nbctf.parquet")
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
        if self.PATTERNS["RIPPLE"].match(value):
            return value, "Ripple"
        if self.PATTERNS["LITECOIN"].match(value):
            return value, "Litecoin"
        return None

    def _parse_csv_to_dict(self, csv_path: str) -> Dict[str, Dict[str, str]]:
        records: Dict[str, Dict[str, str]] = {}
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                entity_id = row.get("id", "Unknown")
                entity_name = row.get("name", "NBCTF Terror-Financing Target")

                for field in [row.get("name", ""), row.get("aliases", ""), row.get("id", "")]:
                    for token in re.split(r"[\s,;:|]+", str(field)):
                        cleaned = token.strip()
                        crypto_match = self._identify_crypto(cleaned)
                        if crypto_match:
                            lookup_key, chain_name = crypto_match
                            records[lookup_key] = {
                                "source": "ISRAEL_NBCTF",
                                "chain": chain_name,
                                "sanctions_id": f"NBCTF-{entity_id}",
                                "entity_name": entity_name,
                                "original_address": cleaned,
                            }
        return records

    def _parse_json_to_dict(self, json_path: str) -> Dict[str, Dict[str, str]]:
        records: Dict[str, Dict[str, str]] = {}
        with open(json_path, "r", encoding="utf-8") as f:
            items = json.load(f)
        for item in items:
            raw_addr = str(item.get("address", "")).strip()
            if not raw_addr:
                continue
            lookup_key = raw_addr.lower() if raw_addr.startswith("0x") or raw_addr.lower().startswith("bc1") else raw_addr
            records[lookup_key] = {
                "source": "ISRAEL_NBCTF",
                "chain": item.get("chain", "Unknown"),
                "sanctions_id": item.get("id", "NBCTF-ORD"),
                "entity_name": item.get("entity", "NBCTF Terror-Financing Target"),
                "original_address": raw_addr,
            }
        return records

    def sync_database(self, force_download: bool = False) -> None:
        """Converte ou descarrega todas as ordens de apreensão de Israel em Parquet para data/carteiras/israel_nbctf.parquet."""
        os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
        legacy_csv = str(Path(self.data_path).with_suffix(".csv"))
        legacy_json = str(Path(self.data_path).with_suffix(".json"))

        if not os.path.exists(self.data_path) or force_download:
            records: Dict[str, Dict[str, str]] = {}

            if os.path.exists(legacy_json):
                logger.info("A incorporar israel_nbctf.json local no Parquet...")
                records.update(self._parse_json_to_dict(legacy_json))

            if os.path.exists(legacy_csv) and not force_download:
                logger.info("A converter israel_nbctf.csv local para Parquet...")
                records.update(self._parse_csv_to_dict(legacy_csv))
            else:
                logger.info("A descarregar e converter lista completa de apreensões de cripto de Israel (NBCTF) para Parquet...")
                headers = {"User-Agent": "Mozilla/5.0"}
                response = requests.get(self.NBCTF_CSV_URL, headers=headers, stream=True, timeout=60)
                response.raise_for_status()
                with open(legacy_csv, "wb") as f:
                    for chunk in response.iter_content(chunk_size=65536):
                        f.write(chunk)
                records.update(self._parse_csv_to_dict(legacy_csv))

            rows = [{"lookup_key": k, **v} for k, v in records.items()]
            df = pd.DataFrame(rows, columns=self.COLUMNS)
            df.to_parquet(self.data_path, engine="pyarrow", index=False)

            if os.path.exists(legacy_csv):
                os.remove(legacy_csv)
            if os.path.exists(legacy_json):
                os.remove(legacy_json)
            logger.info(f"Base completa de Israel salva em Parquet ({len(records)} carteiras).")

    def load_sanctions(self) -> None:
        """Processa o Parquet consolidado e indexa todas as carteiras em memória RAM."""
        if not os.path.exists(self.data_path):
            self.sync_database()

        logger.info("A processar base Parquet do NBCTF (Israel)...")
        df = pd.read_parquet(self.data_path, engine="pyarrow")
        records = df.to_dict(orient="records")
        self.sanctioned_addresses = {row.pop("lookup_key"): row for row in records}

        logger.info(f"{len(self.sanctioned_addresses)} carteiras únicas indexadas da base completa de Israel.")

    def is_sanctioned(self, address: str) -> Optional[Dict[str, str]]:
        raw = address.strip()
        return self.sanctioned_addresses.get(raw) or self.sanctioned_addresses.get(raw.lower())