# Responsável por registrar e rodar a esteira de análises

from typing import Any, Dict, List
from src.analyzer.base import BaseAnalysisRule


class AnalyticsEngine:
    def __init__(self, rules: List[BaseAnalysisRule]):
        self.rules = rules

    def run(self, dataset: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Executa todas as regras registradas sobre o dataset."""
        report = {}
        for rule in self.rules:
            report[rule.name] = rule.evaluate(dataset)
        return report