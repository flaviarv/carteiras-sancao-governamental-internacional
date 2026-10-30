"""Motores de execução de triagem e conformidade de sanções internacionais."""

from typing import Any, Dict, List, Optional
from src.analyzer.base import BaseAnalysisRule
from src.analyzer.rules.sanctions_compliance import SanctionsComplianceRule
from src.sanctions.aggregator import UnifiedSanctionsEngine


class AnalyticsEngine:
    """Executa uma esteira de regras analíticas (BaseAnalysisRule) sobre um conjunto de dados."""

    def __init__(self, rules: List[BaseAnalysisRule]):
        self.rules = rules

    def run(self, dataset: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        report = {}
        for rule in self.rules:
            report[rule.name] = rule.evaluate(dataset)
        return report


class SanctionsAnalysisEngine:
    """Orquestra a triagem automatizada de carteiras contra todas as listas de sanções internacionais."""

    def __init__(self, sanctions_engine: Optional[UnifiedSanctionsEngine] = None):
        self.sanctions = sanctions_engine or UnifiedSanctionsEngine()
        self.rule = SanctionsComplianceRule(sanctions_engine=self.sanctions)

    def evaluate_wallet(self, target_address: str) -> Dict[str, Any]:
        """Avalia individualmente uma carteira contra as listas sancionatórias."""
        return self.rule.evaluate(target_address)

    def evaluate_batch(self, addresses: List[str]) -> List[Dict[str, Any]]:
        """Avalia uma lista de carteiras em lote."""
        return self.rule.evaluate_batch(addresses)


# Alias de compatibilidade
ForensicRiskEngine = SanctionsAnalysisEngine
