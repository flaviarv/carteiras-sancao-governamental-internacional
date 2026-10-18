# src/onchain/extractor.py
from typing import Set, Tuple, List, Dict, Any


def extract_counterparties(target_address: str, blockscout_client) -> Set[Tuple[str, str]]:
    """
    Consome as transações da API e retorna um conjunto único de (contraparte, tipo_tx).
    """
    target = target_address.lower()
    counterparties: Set[Tuple[str, str]] = set()

    sources = [
        (blockscout_client.get_native_transactions(target), "native"),
        (blockscout_client.get_token_transfers(target), "token"),
        (blockscout_client.get_internal_transactions(target), "internal"),
    ]

    for tx_list, tx_type in sources:
        for tx in tx_list:
            sender = (tx.get("from") or {}).get("hash", "").lower()
            receiver = (tx.get("to") or {}).get("hash", "").lower()
            
            if sender and sender != target:
                counterparties.add((sender, tx_type))
            if receiver and receiver != target:
                counterparties.add((receiver, tx_type))

    return counterparties