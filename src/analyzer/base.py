from abc import ABC, abstractmethod
from typing import Any, Dict

# Define o contrato que toda regra de análise deve obrigatoriamente seguir:

class BaseAnalysisRule(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Nome identificador da regra analítica."""
        pass

    @abstractmethod
    def evaluate(self, data: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Recebe os dados normalizados de ofac.py (ex: sanctioned_addresses)
        e retorna as métricas/insights calculados.
        """
        pass