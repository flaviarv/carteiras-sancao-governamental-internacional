# Tendências de inclusão de carteiras por data/ano

# src/analyzer/rules/risk_scoring.py
from typing import Dict, Any, Set, Tuple, List
from src.analyzer.data.mixers import KNOWN_MIXERS


class ForensicRiskRule:
    def __init__(self, ofac_engine, known_mixers: Dict[str, str] = KNOWN_MIXERS):
        self.ofac = ofac_engine
        self.known_mixers = known_mixers

    def evaluate(self, target_address: str, counterparties: Set[Tuple[str, str]]) -> Dict[str, Any]:
        target = target_address.lower()
        findings: List[str] = []
        score = 0

        # Nível 0: Checagem direta do alvo na OFAC
        direct_sanction = self.ofac.is_sanctioned(target)
        if direct_sanction:
            return {
                "target": target,
                "risk_level": "CRITICAL_SANCTIONED",
                "risk_score": 100,
                "direct_sanction": direct_sanction,
                "findings": ["Endereço alvo listado diretamente na base de sanções da OFAC."],
                "total_counterparties_analyzed": len(counterparties)
            }

        # Nível 1: Exposição indireta via contrapartes (1-Hop)
        for address, tx_type in counterparties:
            # 1. Sanção da contraparte
            indirect_sanction = self.ofac.is_sanctioned(address)
            if indirect_sanction:
                score += 50
                findings.append(
                    f"Exposição 1-Hop: Interação ({tx_type}) com entidade sancionada: "
                    f"{indirect_sanction['entity_name']} ({address})"
                )

            # 2. Interação com Mixer
            if address in self.known_mixers:
                score += 40
                findings.append(
                    f"Exposição a Mixer: Interação ({tx_type}) com contrato "
                    f"{self.known_mixers[address]} ({address})"
                )

        score = min(score, 100)
        
        if score >= 70:
            risk_level = "CRÍTICO"
        elif score >= 40:
            risk_level = "ALTO"
        elif score > 0:
            risk_level = "MÉDIO"
        else:
            risk_level = "BAIXO"

        return {
            "target": target,
            "risk_score": score,
            "risk_level": risk_level,
            "total_counterparties_analyzed": len(counterparties),
            "findings": findings
        }