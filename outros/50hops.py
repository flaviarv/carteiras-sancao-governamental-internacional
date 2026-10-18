import os
import re
import time
import json
import requests
from collections import deque
from lxml import etree
from typing import Dict, List, Set, Tuple, Optional

# ==============================================================================
# CONFIGURAÇÕES E CONSTANTES FORENSES
# ==============================================================================
TARGET_WALLET = "0x220866b1a2219f40e72f5c628b65d54268ca3a9d"
MAX_HOPS = 50
MAX_BRANCHES_PER_NODE = 2  # Poda necessária para viabilizar 50 saltos sem estourar rate limit
REQUEST_DELAY = 0.25       # Delay entre chamadas para evitar HTTP 429

OFAC_XML_URL = "https://www.treasury.gov/ofac/downloads/sanctions/1.0/sdn_advanced.xml"
OFAC_LOCAL_FILE = "sdn_advanced.xml"
BLOCKSCOUT_API_BASE = "https://eth.blockscout.com/api/v2"

# Contratos notórios do ecossistema Tornado Cash (Mixers: ETH, USDC e USDT)
KNOWN_MIXERS = {
    # Roteadores Principais
    "0xd90e2f925da726b50c4ed8d0fb90ad053324f31b": "Tornado.Cash: Router",
    "0x8576acc5c05d6ce88f4e49bf65bdf0c62f91353c": "Tornado.Cash: Proxy / Router",

    # Cofres de ETH (Moeda Nativa)
    "0x12d66f87a04a9e220743712ce6d9bb1b5616b8fc": "Tornado.Cash: 0.1 ETH",
    "0x47ce0c6ed5b0ce3d3a51fdb1c52dc66a7c3c2936": "Tornado.Cash: 1 ETH",
    "0x910cbd523d972eb0a6f4cae4618ad62622b39dbf": "Tornado.Cash: 10 ETH",
    "0xa160cdab225685da1d56aa342ad8841c3b53f291": "Tornado.Cash: 100 ETH",

    # Cofres de USDC (USD Coin)
    "0xd96f2b1c14db8458374d9aca76e26c3d18364307": "Tornado.Cash: 100 USDC",
    "0x4736dcf1b7a3d580672cce6e7c65cd5cc9cfba9d": "Tornado.Cash: 1,000 USDC",

    # Cofres de USDT (Tether USD)
    "0x169ad27a470d064dede56a2d3ff727986b15d52b": "Tornado.Cash: 100 USDT",
    "0x0836222f2b2b24a3f36f98668ed8f0b38d1a872f": "Tornado.Cash: 1,000 USDT"
}

EVM_REGEX = re.compile(r"^0x[a-fA-F0-9]{40}$")

# ==============================================================================
# INGESTÃO DA BASE OFAC (XML AVANÇADO)
# ==============================================================================
def carregar_base_ofac() -> Dict[str, Dict[str, str]]:
    if not os.path.exists(OFAC_LOCAL_FILE):
        print("[*] Baixando base oficial sdn_advanced.xml da OFAC...")
        res = requests.get(OFAC_XML_URL, stream=True, timeout=60)
        res.raise_for_status()
        with open(OFAC_LOCAL_FILE, "wb") as f:
            for chunk in res.iter_content(chunk_size=65536):
                f.write(chunk)
        print("[+] Download do XML finalizado.")

    print("[*] Analisando estrutura XML da OFAC...")
    tree = etree.parse(OFAC_LOCAL_FILE)
    root = tree.getroot()
    ns = {"ns": root.nsmap.get(None, "http://www.un.org/sanctions/1.0")}

    sanctioned = {}
    entries = root.xpath("//ns:SanctionsEntry", namespaces=ns)

    for entry in entries:
        entry_id = entry.get("ID", "Unknown")
        name_node = entry.xpath(".//ns:NamePartValue/text()", namespaces=ns)
        entity_name = " ".join([str(n).strip() for n in name_node]) if name_node else "N/A"

        features = entry.xpath(".//ns:Feature", namespaces=ns)
        for feature in features:
            for val in feature.xpath(".//ns:Value/text()", namespaces=ns):
                cleaned = str(val).strip()
                if EVM_REGEX.match(cleaned):
                    sanctioned[cleaned.lower()] = {
                        "entity_name": entity_name,
                        "sanctions_id": entry_id
                    }

    print(f"[+] OFAC carregada: {len(sanctioned)} endereços EVM únicos indexados.\n")
    return sanctioned

# ==============================================================================
# EXTRAÇÃO ON-CHAIN (BLOCKSCOUT API V2)
# ==============================================================================
def obter_contrapartes_blockscout(address: str) -> List[str]:
    url = f"{BLOCKSCOUT_API_BASE}/addresses/{address}/transactions"
    headers = {"Accept": "application/json"}
    
    time.sleep(REQUEST_DELAY)
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 429:
            print(f"\n[!] Rate limit atingido. Aguardando 3 segundos...")
            time.sleep(3)
            response = requests.get(url, headers=headers, timeout=15)
            
        if response.status_code != 200:
            return []

        data = response.json()
        items = data.get("items", [])
    except Exception as e:
        return []

    counterparties = []
    addr_lower = address.lower()

    for tx in items:
        _from = (tx.get("from") or {}).get("hash", "").lower()
        _to = (tx.get("to") or {}).get("hash", "").lower()

        if _from and _from != addr_lower and _from not in counterparties:
            counterparties.append(_from)
        if _to and _to != addr_lower and _to not in counterparties:
            counterparties.append(_to)

    return counterparties

# ==============================================================================
# MOTOR FORENSE: EXECUÇÃO DOS 50 HOPS
# ==============================================================================
def rastrear_50_hops(start_address: str, ofac_db: Dict[str, Dict[str, str]]):
    start_node = start_address.lower()
    
    # Fila BFS: tupla (endereço, histórico_do_caminho_de_hops)
    queue: deque[Tuple[str, List[str]]] = deque([(start_node, [start_node])])
    visited: Set[str] = {start_node}
    
    print("=" * 70)
    print(f"[*] INICIANDO ANÁLISE DE ATÉ {MAX_HOPS} HOPS")
    print(f"[*] Carteira Alvo: {start_node}")
    print(f"[*] Limite de ramificação por nó: {MAX_BRANCHES_PER_NODE}")
    print("=" * 70)

    passo = 0
    max_hop_atingido = 0

    while queue:
        current_addr, path = queue.popleft()
        current_hop = len(path) - 1
        
        if current_hop > max_hop_atingido:
            max_hop_atingido = current_hop

        passo += 1
        print(f"[{passo}] Verificando Nó: {current_addr[:10]}... | Salto Atual: {current_hop} / {MAX_HOPS} | Fila: {len(queue)}", end="\r")

        # 1. Checagem Determinística: Consta na OFAC?
        if current_addr in ofac_db:
            entidade = ofac_db[current_addr]["entity_name"]
            print(f"\n\n[🚨 ALERTA FORENSE - CONEXÃO COM OFAC ENCONTRADA!]")
            print(f"Distância: {current_hop} Saltos")
            print(f"Endereço Sancionado: {current_addr}")
            print(f"Entidade: {entidade}")
            print("\nCadeia de Custódia (Trilha de Hops):")
            for i, step in enumerate(path):
                print(f"  Salto {i}: {step}")
            return

        # 2. Checagem Determinística: Consta na lista de Mixers?
        if current_addr in KNOWN_MIXERS:
            mixer_name = KNOWN_MIXERS[current_addr]
            print(f"\n\n[🚨 ALERTA FORENSE - INTERAÇÃO COM MIXER DETECTADA!]")
            print(f"Distância: {current_hop} Saltos")
            print(f"Contrato Mixer: {current_addr} ({mixer_name})")
            print("\nCadeia de Custódia (Trilha de Hops):")
            for i, step in enumerate(path):
                print(f"  Salto {i}: {step}")
            return

        # 3. Limite de Profundidade
        if current_hop >= MAX_HOPS:
            continue

        # 4. Expansão de Vizinhança (Nível seguinte)
        contrapartes = obter_contrapartes_blockscout(current_addr)
        
        novos_vizinhos = []
        for neighbor in contrapartes:
            if neighbor not in visited:
                visited.add(neighbor)
                novos_vizinhos.append(neighbor)

        # Adiciona até MAX_BRANCHES_PER_NODE para cada ramo
        for prox in novos_vizinhos[:MAX_BRANCHES_PER_NODE]:
            queue.append((prox, path + [prox]))

    print(f"\n\n[+] Varredura concluída.")
    print(f"Nós auditados: {len(visited)}")
    print(f"Profundidade máxima percorrida: {max_hop_atingido} saltos.")
    print("Nenhum endereço sancionado ou mixer colidiu com os ramos analisados.")

# ==============================================================================
# PONTO DE ENTRADA
# ==============================================================================
if __name__ == "__main__":
    ofac_sanctions = carregar_base_ofac()
    rastrear_50_hops(TARGET_WALLET, ofac_sanctions)