"""
SISTEMA DE DETECÇÃO DE SANÇÕES INTERNACIONAIS EM CRIPTOATIVOS (PLD/CFT)
========================================================================
Varredura direta em listas oficiais de sanções governamentais:
  • OFAC (EUA - SDN)
  • Israel NBCTF (Financiamento ao Terrorismo)
  • Reino Unido (FCDO / OFSI)
  • União Europeia (EEAS)
  • Nações Unidas (ONU) e Suíça (SECO)
========================================================================
"""

import sys
import os
import argparse
import logging
from typing import Dict, Any

# Suporte UTF-8 no console Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.sanctions.aggregator import UnifiedSanctionsEngine
from src.analyzer.rules.sanctions_compliance import SanctionsComplianceRule
from src.sanctions.jurisdictions import jurisdiction_label


PLACEHOLDER_NAMES = {
    "cryptocurrency wallet",
    "ofac sanctioned entity",
    "uk sanctioned target",
    "eu sanctioned entity",
    "nbctf terror-financing target",
}


def _clean(value) -> str:
    """Normaliza valores vindos das bases (None/NaN/vazio -> '')."""
    return value.strip() if isinstance(value, str) else ""


def format_sanctions_report(report: Dict[str, Any]) -> str:
    """Relatório curto: sancionada (lista/país, nome, nacionalidade) ou não sancionada."""
    target = report["target"]
    matches = report.get("matches", [])
    lines = [
        "=" * 72,
        f"Endereço consultado: {target}",
        f"Rede identificada  : {report.get('chain', 'Não identificada')}",
        "-" * 72,
    ]

    if report["is_sanctioned"]:
        labels = list(dict.fromkeys(jurisdiction_label(m.get("source", "")) for m in matches))
        lines.append("🚨 CARTEIRA SANCIONADA")
        lines.append(f"Lista(s) governamental(is): {', '.join(labels)}")

        for idx, m in enumerate(matches, 1):
            name = _clean(m.get("entity_name"))
            if not name or name.lower() in PLACEHOLDER_NAMES or name.lower() == target.lower():
                name = "não informado na lista"

            nationality = _clean(m.get("nationality"))
            if not nationality:
                nationality = "não informada na lista"
                related = _clean(m.get("related_country"))
                if related:
                    nationality += f" (país vinculado: {related})"

            lines.append("")
            lines.append(f"[{idx}] {jurisdiction_label(m.get('source', ''))}")
            lines.append(f"    • Nome / entidade : {name}")
            lines.append(f"    • Nacionalidade   : {nationality}")
    elif report.get("verdict_status") == "FORMATO_INVALIDO":
        lines.append("⚠️ FORMATO INVÁLIDO")
        lines.append("O texto informado não corresponde a um formato de endereço cripto válido.")
    else:
        lines.append("✅ CARTEIRA NÃO SANCIONADA")
        lines.append("A carteira não está sancionada em nenhuma lista governamental.")

    lines.append("=" * 72)
    return "\n".join(lines)


def run_interactive(rule: SanctionsComplianceRule, engine: UnifiedSanctionsEngine):
    """Executa o loop interativo no terminal."""
    stats = engine.get_stats()
    print("\n" + "=" * 72)
    print("      SISTEMA DE DETECÇÃO DE SANÇÕES INTERNACIONAIS (PLD/CFT)          ")
    print("=" * 72)
    print(f"Total de Carteiras Sancionadas Indexadas: {stats['total_unique_sanctioned']:,} endereços únicos")
    for jur, count in stats["jurisdictions"].items():
        print(f"  • {jur:<40} : {count:>5} endereços")
    print("=" * 72)
    print("Digite o endereço da carteira para consultar.")
    print("Digite 'sair' para encerrar ou 'stats' para ver as estatísticas.\n")

    while True:
        try:
            target = input("carteira > ").strip()
            if not target:
                continue
            if target.lower() in ("sair", "exit", "quit", "q"):
                print("\nEncerrando o sistema. Até logo!")
                break
            if target.lower() == "stats":
                curr_stats = engine.get_stats()
                print(f"\n[ESTATÍSTICAS DA BASE]")
                for jur, count in curr_stats["jurisdictions"].items():
                    print(f"  • {jur:<40} : {count:>5}")
                print(f"  Total único: {curr_stats['total_unique_sanctioned']} endereços\n")
                continue

            report = rule.evaluate(target)
            print("\n" + format_sanctions_report(report) + "\n")

        except (KeyboardInterrupt, EOFError):
            print("\nSessão encerrada.")
            break


def run_batch_file(file_path: str, rule: SanctionsComplianceRule):
    """Executa auditoria em lote a partir de arquivo de texto (um endereço por linha)."""
    if not os.path.exists(file_path):
        print(f"Erro: Arquivo '{file_path}' não foi encontrado.")
        sys.exit(1)

    with open(file_path, "r", encoding="utf-8") as f:
        raw_lines = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

    if not raw_lines:
        print(f"Aviso: Nenhuma carteira encontrada no arquivo '{file_path}'.")
        return

    print("\n" + "=" * 72)
    print(f"AUDITORIA EM LOTE: {len(raw_lines)} carteiras ({file_path})")
    print("=" * 72)

    sanctioned_count = 0
    invalid_count = 0
    clean_count = 0

    for idx, addr in enumerate(raw_lines, 1):
        report = rule.evaluate(addr)
        status = report.get("verdict_status")
        chain = report.get("chain", "N/A")

        if status == "ALERTA_SANCOES":
            sanctioned_count += 1
            sources = ", ".join(report.get("sources", []))
            print(f"[{idx:>3}/{len(raw_lines)}] 🚨 SANCIONADA | {addr} ({chain}) -> {sources}")
        elif status == "FORMATO_INVALIDO":
            invalid_count += 1
            print(f"[{idx:>3}/{len(raw_lines)}] ⚠️ INVÁLIDA   | {addr} ({chain})")
        else:
            clean_count += 1
            print(f"[{idx:>3}/{len(raw_lines)}] ✅ CONFORME   | {addr} ({chain})")

    print("=" * 72)
    print(f"Resumo da Auditoria:")
    print(f"  • Total auditado : {len(raw_lines)}")
    print(f"  • Sancionadas    : {sanctioned_count}")
    print(f"  • Conformes      : {clean_count}")
    print(f"  • Inválidas      : {invalid_count}")
    print("=" * 72 + "\n")


def main():
    logging.basicConfig(level=logging.WARNING, format="[%(levelname)s] %(message)s")

    parser = argparse.ArgumentParser(
        description="Sistema de Detecção de Carteiras Sancionadas por Listas Internacionais."
    )
    parser.add_argument("address", nargs="?", help="Endereço de criptomoeda a consultar.")
    parser.add_argument("--file", "-f", help="Caminho do arquivo com endereços para auditoria em lote.")
    parser.add_argument("--stats", "-s", action="store_true", help="Exibe estatísticas das bases de dados.")
    args = parser.parse_args()

    engine = UnifiedSanctionsEngine()
    engine.load_all()
    rule = SanctionsComplianceRule(sanctions_engine=engine)

    if args.stats:
        curr_stats = engine.get_stats()
        print(f"\n[ESTATÍSTICAS DA BASE DE SANÇÕES]")
        for jur, count in curr_stats["jurisdictions"].items():
            print(f"  • {jur:<40} : {count:>5} endereços")
        print(f"  Total único: {curr_stats['total_unique_sanctioned']:,} endereços\n")
    elif args.file:
        run_batch_file(args.file, rule)
    elif args.address:
        report = rule.evaluate(args.address)
        print("\n" + format_sanctions_report(report) + "\n")
    else:
        run_interactive(rule, engine)


if __name__ == "__main__":
    main()