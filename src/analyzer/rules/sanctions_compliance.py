"""
Motor de Conformidade e Auditoria de Sanções Internacionais (PLD/CFT).
Especializado na detecção rigorosa de carteiras sancionadas por OFAC (EUA), Israel (NBCTF),
Reino Unido (OFSI), União Europeia e órgãos internacionais.
Avalia exclusivamente sanções governamentais oficiais.
"""

from typing import Dict, Any, List, Optional, Union
from src.sanctions.aggregator import UnifiedSanctionsEngine, is_valid_crypto_address


class SanctionsComplianceRule:
    """
    Regra de conformidade mandatória de PLD/CFT.
    Avalia se um endereço de carteira consta expressamente em listas de sanções
    governamentais internacionais.
    """

    def __init__(self, sanctions_engine: Optional[UnifiedSanctionsEngine] = None):
        self.sanctions = sanctions_engine or UnifiedSanctionsEngine()

    def evaluate(self, target_address: str, *args, **kwargs) -> Dict[str, Any]:
        """
        Executa a triagem sancionatória completa do endereço alvo.
        Retorna laudo probatório determinístico.
        """
        raw_target = str(target_address).strip()
        audit_result = self.sanctions.check_wallet(raw_target)

        is_sanctioned = audit_result["is_sanctioned"]
        sources = audit_result["sources"]
        matches = audit_result["sanctions"]
        entities = audit_result["entities"]

        # Construção da certidão e parecer conclusivo
        details: List[str] = []
        for idx, s in enumerate(matches, 1):
            src = s.get("source", "Sanção")
            ent = s.get("entity_name", "Entidade Não Especificada")
            sid = s.get("sanctions_id", "N/A")
            ch = s.get("chain", "N/A")
            details.append(
                f"[{idx}] {src} | Entidade: {ent} | ID: {sid} | Rede: {ch}"
            )

        if is_sanctioned:
            verdict_status = "ALERTA_SANCOES"
            sources_str = ", ".join(sources)
            verdict_summary = (
                f"ALERTA CRÍTICO: Carteira expressamente sancionada em lista(s) oficial(is): {sources_str}. "
                f"Exige bloqueio cautelar imediato conforme diretrizes internacionais de PLD/CFT."
            )
        elif not is_valid_crypto_address(raw_target):
            verdict_status = "FORMATO_INVALIDO"
            verdict_summary = (
                f"FORMATO INVÁLIDO: O texto informado ('{raw_target}') não corresponde a um padrão "
                f"sintático de endereço de criptomoeda suportado (EVM, Bitcoin, Tron, Solana, Litecoin, etc.)."
            )
        else:
            verdict_status = "REGULAR"
            verdict_summary = (
                "REGULAR: O endereço consultado NÃO consta em nenhuma das listas de sanções governamentais "
                "internacionais ativas (OFAC, Israel NBCTF, Reino Unido, União Europeia, ONU)."
            )

        return {
            "target": raw_target,
            "is_sanctioned": is_sanctioned,
            "verdict_status": verdict_status,
            "verdict_summary": verdict_summary,
            "sources": sources,
            "entities": entities,
            "chain": audit_result["chain"],
            "details": details,
            "matches": matches,
            "checks": {
                "sanctions": {
                    "detected": is_sanctioned,
                    "count": len(matches),
                    "sources": sources,
                    "details": details,
                },
            },
        }

    def evaluate_batch(self, addresses: List[str]) -> List[Dict[str, Any]]:
        """Avalia um lote de carteiras em lote de forma determinística."""
        return [self.evaluate(addr) for addr in addresses if addr and addr.strip()]


# Aliases de compatibilidade
ForensicRiskRule = SanctionsComplianceRule
