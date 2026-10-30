"""
Módulo de compatibilidade: redireciona avaliações de risco para o novo
motor estrito de sanções internacionais (SanctionsComplianceRule).
"""

from src.analyzer.rules.sanctions_compliance import SanctionsComplianceRule, ForensicRiskRule

__all__ = ["SanctionsComplianceRule", "ForensicRiskRule"]
