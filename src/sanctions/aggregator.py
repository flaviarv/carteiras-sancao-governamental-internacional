import logging
from typing import Dict, Optional
from src.sanctions.ofac import OFACSanctionsEngine
from src.sanctions.eu import EUSanctionsEngine
from src.sanctions.uk import UKSanctionsEngine
from src.sanctions.un import UNSanctionsEngine
from src.sanctions.seco import SECOSanctionsEngine
from src.sanctions.nbctf import NBCTFSanctionsEngine

logger = logging.getLogger(__name__)


class UnifiedSanctionsEngine:
    """Orquestrador global de inteligência sancionatória multijurisdicional."""

    def __init__(self):
        self.engines = [
            OFACSanctionsEngine(),    # EUA
            EUSanctionsEngine(),      # União Europeia
            UKSanctionsEngine(),      # Reino Unido
            UNSanctionsEngine(),      # Nações Unidas (ONU)
            SECOSanctionsEngine(),    # Suíça
            NBCTFSanctionsEngine(),   # Israel (NBCTF)
        ]

    def load_all(self) -> None:
        """Carrega e indexa todas as jurisdições suportadas."""
        logger.info(">>> Iniciando sincronização e carregamento global de sanções...")
        total_unique = 0
        for engine in self.engines:
            try:
                engine.load_sanctions()
                total_unique += len(engine.sanctioned_addresses)
            except Exception as exc:
                logger.warning(f"Não foi possível sincronizar base {engine.__class__.__name__}: {exc}")
        logger.info(f">>> Carga global concluída: {total_unique} registos acumulados em memória.")

    def is_sanctioned(self, address: str) -> Optional[Dict[str, str]]:
        """Varre todas as jurisdições ativas à procura do endereço."""
        for engine in self.engines:
            result = engine.is_sanctioned(address)
            if result:
                if "source" not in result:
                    result["source"] = "OFAC"
                return result
        return None