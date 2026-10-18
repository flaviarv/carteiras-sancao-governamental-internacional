import logging
from typing import Any, Dict, List, Optional
import requests

logger = logging.getLogger(__name__)


class BlockscoutV2Client:
    """Cliente HTTP para a API v2 do explorador Blockscout."""

    SUPPORTED_CHAINS = {
        "eth": "https://eth.blockscout.com/api/v2",
        "polygon": "https://polygon.blockscout.com/api/v2",
        "base": "https://base.blockscout.com/api/v2",
        "arbitrum": "https://arbitrum.blockscout.com/api/v2",
        "optimism": "https://optimism.blockscout.com/api/v2",
    }

    def __init__(self, chain: str = "eth", custom_base_url: Optional[str] = None, timeout: int = 20):
        if custom_base_url:
            self.base_url = custom_base_url.rstrip("/")
        else:
            self.base_url = self.SUPPORTED_CHAINS.get(chain.lower(), self.SUPPORTED_CHAINS["eth"])

        self.session = requests.Session()
        # Headers necessários para evitar bloqueios e erros 422/403
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        })
        self.timeout = timeout

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as exc:
            logger.error(f"Erro ao consultar Blockscout v2 [{url}]: {exc}")
            return {"items": []}

    def get_native_transactions(self, address: str) -> List[Dict[str, Any]]:
        """Transações nativas da camada L1/L2."""
        data = self._get(f"/addresses/{address}/transactions")
        return data.get("items", [])

    def get_token_transfers(self, address: str) -> List[Dict[str, Any]]:
        """Transferências de tokens (ERC-20, etc.)."""
        data = self._get(f"/addresses/{address}/token-transfers")
        return data.get("items", [])

    def get_internal_transactions(self, address: str) -> List[Dict[str, Any]]:
        """Transações internas geradas por contratos (traces)."""
        data = self._get(f"/addresses/{address}/internal-transactions")
        return data.get("items", [])