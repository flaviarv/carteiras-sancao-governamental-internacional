# Regras de cálculo de severidade ou pontuação de risco

from typing import Dict, Any, Set, Tuple, List
from src.analyzer.data.mixers import KNOWN_MIXERS


class ForensicRiskRule:
    def __init__(self, sanctions_engine, known_mixers: Dict[str, str] = KNOWN_MIXERS):
        self.sanctions = sanctions_engine
        self.known_mixers = known_mixers

    def evaluate(self, target_address: str, counterparties: Set[Tuple[str, str]]) -> Dict[str, Any]:
        target = target_address.lower()
        findings: List[str] = []
        score = 0

        # Nível 0: Checagem direta do alvo
        direct_sanction = self.sanctions.is_sanctioned(target)
        if direct_sanction:
            source = direct_sanction.get("source", "SANCTION_LIST")
            return {
                "target": target,
                "risk_level": "CRITICAL_SANCTIONED",
                "risk_score": 100,
                "direct_sanction": direct_sanction,
                "findings": [f"Endereço alvo listado diretamente na base de sanções ({source})."],
                "total_counterparties_analyzed": len(counterparties)
            }

        # Nível 1: Exposição indireta via contrapartes (1-Hop)
        for address, tx_type in counterparties:
            indirect_sanction = self.sanctions.is_sanctioned(address)
            if indirect_sanction:
                score += 50
                source = indirect_sanction.get("source", "SANCTION_LIST")
                findings.append(
                    f"Exposição 1-Hop ({source}): Interação ({tx_type}) com entidade sancionada: "
                    f"{indirect_sanction['entity_name']} ({address})"
                )

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