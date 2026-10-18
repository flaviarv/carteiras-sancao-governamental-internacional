# Análise de volume/proporção por blockchain

from collections import Counter
from typing import Any, Dict
from src.analyzer.base import BaseAnalysisRule


class NetworkDistributionRule(BaseAnalysisRule):
    @property
    def name(self) -> str:
        return "network_distribution"

    def evaluate(self, data: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        chains = [item.get("chain", "Unknown") for item in data.values()]
        distribution = Counter(chains)
        total = sum(distribution.values())

        percentages = {
            chain: round((count / total) * 100, 2)
            for chain, count in distribution.items()
        } if total > 0 else {}

        return {
            "total_addresses": total,
            "counts_by_chain": dict(distribution),
            "share_by_chain_pct": percentages,
        }