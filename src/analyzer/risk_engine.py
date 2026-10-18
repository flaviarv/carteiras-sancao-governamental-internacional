from typing import Dict, Any, List

class ForensicRiskEngine:
    # Contratos clássicos do Tornado Cash para validação direta
    KNOWN_MIXERS = {
        "0xd90e2f925da726b50c4ed8d0fb90ad053324f31b": "Tornado.Cash: Router",
        "0x12d66f87a04a9e220743712ce6d9bb1b5616b8fc": "Tornado.Cash: 0.1 ETH",
        "0x47ce0c6ed5b0ce3d3a51fdb1c52dc66a7c3c2936": "Tornado.Cash: 1 ETH",
        "0x910cbd523d972eb0a6f4cae4618ad62622b39dbf": "Tornado.Cash: 10 ETH",
        "0xa160cdab224e496084ac5974e4fe1536b139943f": "Tornado.Cash: 100 ETH"
    }

    def __init__(self, ofac_engine):
        self.ofac = ofac_engine

    def evaluate_wallet(self, target_address: str, blockscout_client) -> Dict[str, Any]:
        target = target_address.lower()
        findings: List[str] = []
        score = 0

        # 1. Checagem Nível 1: Endereço Alvo na OFAC
        direct_sanction = self.ofac.is_sanctioned(target)
        if direct_sanction:
            return {
                "target": target,
                "risk_level": "CRITICAL_SANCTIONED",
                "risk_score": 100,
                "direct_sanction": direct_sanction,
                "findings": ["Endereço alvo listado diretamente na base de sanções da OFAC."]
            }

        # 2. Coleta de dados on-chain
        native_txs = blockscout_client.get_native_transactions(target)
        token_txs = blockscout_client.get_token_transfers(target)
        internal_txs = blockscout_client.get_internal_transactions(target)

        counterparties = set()

        # Extração de contrapartes das transações nativas
        for tx in native_txs:
            _from = (tx.get("from") or {}).get("hash", "").lower()
            _to = (tx.get("to") or {}).get("hash", "").lower()
            if _from and _from != target: counterparties.add((_from, "native"))
            if _to and _to != target: counterparties.add((_to, "native"))

        # Extração de contrapartes de tokens
        for tx in token_txs:
            _from = (tx.get("from") or {}).get("hash", "").lower()
            _to = (tx.get("to") or {}).get("hash", "").lower()
            if _from and _from != target: counterparties.add((_from, "token"))
            if _to and _to != target: counterparties.add((_to, "token"))

        # Extração de contrapartes internas
        for tx in internal_txs:
            _from = (tx.get("from") or {}).get("hash", "").lower()
            _to = (tx.get("to") or {}).get("hash", "").lower()
            if _from and _from != target: counterparties.add((_from, "internal"))
            if _to and _to != target: counterparties.add((_to, "internal"))

        # 3. Análise de 1º Salto (1-Hop Exposure) contra OFAC e Mixers
        for address, tx_type in counterparties:
            # Checa sanção direta da contraparte
            indirect_sanction = self.ofac.is_sanctioned(address)
            if indirect_sanction:
                score += 50
                findings.append(
                    f"Exposição 1-Hop: Interação ({tx_type}) com entidade sancionada: "
                    f"{indirect_sanction['entity_name']} ({address})"
                )

            # Checa interação com Mixer
            if address in self.KNOWN_MIXERS:
                score += 40
                findings.append(
                    f"Exposição a Mixer: Interação ({tx_type}) com contrato {self.KNOWN_MIXERS[address]}"
                )

        score = min(score, 100)
        risk_level = "BAIXO"
        if score >= 70:
            risk_level = "CRÍTICO"
        elif score >= 40:
            risk_level = "ALTO"
        elif score > 0:
            risk_level = "MÉDIO"

        return {
            "target": target,
            "risk_score": score,
            "risk_level": risk_level,
            "total_counterparties_analyzed": len(counterparties),
            "findings": findings
        }