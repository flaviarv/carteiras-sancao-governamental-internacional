import logging
from src.sanctions.aggregator import UnifiedSanctionsEngine
from src.onchain.blockscout_client import BlockscoutV2Client
from src.onchain.extractor import extract_counterparties
from src.analyzer.rules.risk_scoring import ForensicRiskRule

def main():
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    # 1. Carrega todas as bases de sanções (OFAC + UE)
    sanctions_engine = UnifiedSanctionsEngine()
    sanctions_engine.load_all()

    # 2. Entrada da carteira
    target_wallet = input("\nDigite o endereço da carteira para análise forense: ").strip()
    if not target_wallet:
        return

    # 3. Coleta on-chain
    print(f"[*] Consultando histórico on-chain de {target_wallet}...")
    client = BlockscoutV2Client(chain="eth")
    counterparties = extract_counterparties(target_wallet, client)

    # 4. Avaliação forense integrada
    forensic = ForensicRiskRule(sanctions_engine=sanctions_engine)
    report = forensic.evaluate(target_wallet, counterparties)

    # 5. Laudo
    print("\n" + "=" * 50)
    print("RELATÓRIO FORENSE DE RISCO (MULTIJURISDICIONAL)")
    print("=" * 50)
    print(f"Alvo: {report['target']}")
    print(f"Nível de Risco: {report['risk_level']} (Score: {report['risk_score']})")
    print(f"Contrapartes analisadas: {report['total_counterparties_analyzed']}")
    
    if report["findings"]:
        print("\nEvidências encontradas:")
        for finding in report["findings"]:
            print(f"  [!] {finding}")
    else:
        print("\nNenhuma evidência direta ou indireta de risco detectada.")
    print("=" * 50)

if __name__ == "__main__":
    main()