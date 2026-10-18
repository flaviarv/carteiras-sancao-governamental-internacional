from src.onchain.blockscout_client import BlockscoutV2Client

# Caso já tenha criado o extractor.py:
try:
    from src.onchain.extractor import extract_counterparties
    __all__ = ["BlockscoutV2Client", "extract_counterparties"]
except ImportError:
    __all__ = ["BlockscoutV2Client"]