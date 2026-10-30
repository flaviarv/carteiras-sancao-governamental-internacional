# 🛡️ Sistema de Detecção de Sanções Internacionais em Criptoativos (PLD/CFT)

Solução especializada em auditoria e conformidade determinística para **Prevenção à Lavagem de Dinheiro e Combate ao Financiamento do Terrorismo (PLD/CFT)** com foco estrito na detecção de carteiras sancionadas por listas internacionais oficiais (como **OFAC** e **Israel NBCTF**).

---

## 📌 Sumário Executivo

A aplicação provê um motor de busca indexado, offline, de altíssima performance e **zero alucinação**, permitindo a verificação instantânea de endereços de criptomoedas contra bases sancionatórias oficiais consolidadas.

### Principais Capacidades:
1. **Inteligência Sancionatória Global Multijurisdicional:**
   - **OFAC (EUA - Specially Designated Nationals / SDN):** Mais de 1.000 endereços cripto sancionados vinculados a entidades terroristas, ciberataques estatais, cartéis e regimes sancionados.
   - **Israel NBCTF (National Bureau for Counter Terror Financing):** Mais de 600 carteiras formalmente confiscadas e sancionadas por financiamento ao terrorismo (Hamas, Hezbollah, PIJ).
   - **Reino Unido (FCDO / OFSI):** Sanções financeiras do Reino Unido para ativos digitais.
   - **União Europeia (EEAS):** Regime unificado de sanções financeiras da UE.
   - **Nações Unidas (CSNU / ONU) & Suíça (SECO):** Monitoramento contínuo de listas consolidadas.
2. **Suporte Multicadeia Universal:**
   - Detecção e normalização em múltiplas redes: **EVM** (Ethereum, BSC, Polygon, Arbitrum), **Tron** (TRX/USDT-TRC20), **Bitcoin** (BTC - Bech32 e Base58), **Solana** (SOL), **Monero** (XMR), **Litecoin** (LTC), **Ripple** (XRP) e **Zcash** (ZEC).
3. **Detecção Cruzada Multi-Jurisdição:**
   - Identifica quando um endereço figura em múltiplos órgãos simultaneamente (ex: OFAC e Israel).
4. **Armazenamento e Performance em Parquet:**
   - Bases indexadas localmente em arquivos colunares Parquet (`data/carteiras/*.parquet`), garantindo consultas em microsegundos e 100% de disponibilidade sem depender de chamadas a exploradores de blocos.

---

## 🚀 Como Executar

### 1. Consulta Interativa
```bash
python main.py
```
Permite digitar ou colar qualquer endereço de carteira no terminal para receber o parecer imediato de auditoria.

### 2. Consulta Direta via Argumento
```bash
python main.py <ENDEREÇO_DA_CARTEIRA>
```
Exemplo com carteira sancionada pela OFAC e Israel:
```bash
python main.py TWBAPzpPiZarfVsY2BLXeaLhNHurn4wkWG
```

### 3. Consulta em Lote a partir de Arquivo
```bash
python main.py --file carteiras_para_auditar.txt
```

### 4. Estatísticas das Bases
```bash
python main.py --stats
```
Exibe o quantitativo total de endereços indexados por jurisdição.
