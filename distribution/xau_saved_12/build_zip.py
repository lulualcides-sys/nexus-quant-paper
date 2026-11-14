#!/usr/bin/env python3
"""Build a downloadable package of the EXACT 12 preserved XAU research ideas.

Do not mislabel Python research as 12 compiled MT5 EAs.
This script is run in GitHub Actions from the 2026-11-12 research branch.
Only the existing *different* Nexus Vector Retest EA is MQL5 source.
"""
from __future__ import annotations
import csv
import io
import json
import pathlib
import subprocess
import zipfile

BASE=pathlib.Path(__file__).resolve().parents[2]
SOURCE=BASE/"robots/mt5/nexus_vector_retest"
OUT=BASE/"dist"/"NexusQuant_XAUUSD_12_Salvos_CODIGOS.zip"
PRESERVED=[
"research/preserved/xau_selected_twelve_candidates_20261112.json",
"research/preserved/xau_authoritative_timeframes_m1_m5_m15_m30_20261112.json",
"research/preserved/xau_top_two_priority_er20_m30_shock_m15_20261112.json",
"research/preserved/xau_positive_variants_all_batches6_7_20261112.json",
"research/preserved/xau_batch8_independent_all_2025plus_20261112.json",
"research/preserved/xau_batch9_session_all_2025plus_20261112.json",
"research/preserved/xau_batch9_session_report_2025plus_20261112.md",
"research/preserved/xau_entry_quality_batch7_full_2025plus_20261112.json",
"research/preserved/xau_exit_risk_batch6_full_2025plus_20261112.json",
]
SOURCES={
"XAU_EMA21_RUNNER_M15":["alpha_xau_mtf_2025plus.py","points10k.py"],
"XAU_EMA21_RSI_MACD_M30":["xau_indicator_lab_2025plus.py"],
"XAU_HULL21_PULLBACK_M20":["xau_indicator_batch2_2025plus.py"],
"XAU_ASIA_SWEEP_RECLAIM_M12":["xau_liquidity_session_2025plus.py"],
"XAU_INSIDE_MOTHER_BREAK_M12":["xau_volatility_breakouts_2025plus.py"],
"XAU_VOL_COMPRESSION_RELEASE_M20":["xau_volatility_breakouts_2025plus.py"],
"XAU_EFFICIENCY_ER20_BREAK_M30":["xau_volatility_breakouts_2025plus.py"],
"XAU_SHOCK_EXHAUSTION_M5":["xau_statistical_regimes_batch5_2025plus.py"],
"XAU_SHOCK_EXHAUSTION_M15":["xau_statistical_regimes_batch5_2025plus.py"],
"XAU_EMA21_RSI_MACD_M30_COST_TO_STOP_10PCT":["xau_indicator_lab_2025plus.py","xau_entry_quality_batch7_2025plus.py"],
"XAU_VWAP_EMA_RECLAIM_M30":["xau_session_batch9_2025plus.py"],
"XAU_ASIA_TREND_BREAK_M30":["xau_session_batch9_2025plus.py"],
}
ALLOWED={"M1","M5","M15","M30"}
ARCHIVE_PREFIX="NexusQuant_XAUUSD_12_Salvos"


def main_text(path):
    return subprocess.check_output(
        ["git","show","origin/main:"+path],cwd=BASE).decode("utf-8")


def main():
    registry=json.loads(main_text(PRESERVED[0]))
    items=registry["selected_candidates"]
    if len(items)!=12 or len(SOURCES)!=12:
        raise AssertionError("expected precisely 12 saved research candidates")
    if len({x["id"] for x in items})!=12:
        raise AssertionError("duplicate candidate id")
    existing={x.name for x in SOURCE.glob("*.py")}
    for x in items:
        if x["id"] not in SOURCES:
            raise AssertionError("missing code mapping "+x["id"])
        if any(f not in existing for f in SOURCES[x["id"]]):
            raise AssertionError("missing code "+x["id"])
    mql=SOURCE/"Nexus_Vector_Retest_EA_v1.00.mq5"
    if not mql.is_file():
        raise AssertionError("the one separate existing EA source is missing")
    readme="""# NEXUS QUANT - 12 CANDIDATOS XAUUSD (PACOTE DE CÓDIGO)

Este arquivo ZIP contém os **12 candidatos de pesquisa salvos**, seus
**códigos-fonte Python reais**, os resultados e um exemplo de EA .mq5
**DISTINTO** das 12 estratégias. NÃO inclui 12 EAs MQL5 nem arquivos .ex5
compilados. Não é correto abrir scripts .py no MetaEditor e esperar que
operem como Expert Advisors.

## O que foi incluído
- catalogo/12_candidatos_salvos.json e catalogo/configuracoes_individuais/
  registram todas as estratégias e parâmetros/históricos existentes.
- pesquisa_python/ possui o código integral de experimentos e bibliotecas.
- TESTAR_8_PERMITIDOS_2026.bat + testar_8_permitidos.py podem reproduzir
  backtests com OHLC 2026 parcial e custo fixo em dados públicos, com
  Python 3.11, numpy e pandas, internet e Windows. Não rodam ordens.
- 4 candidatos M12/M20 permanecem em historico/ e constam no catálogo,
  porém NÃO devem ser retestados em M12/M20 segundo a política atual.
- mt5_ea_separado/Nexus_Vector_Retest_EA_v1.00.mq5 é o único EA
  MQL5 detectado nesse conjunto. **É UMA ESTRATÉGIA DIFERENTE**,
  NÃO implementa ER20 M30, Shock Exhaustion M15 nem os 12 candidatos.

## Teste de pesquisa imediato em Windows
1. Instale Python 3.11 e marque Add Python to PATH; precisa de internet.
2. Extraia o ZIP inteiro.
3. Execute TESTAR_8_PERMITIDOS_2026.bat para instalar dependências
   e rodar o replay OHLC das 8 variantes em timeframes autorizados.
4. Consulte resultados_2026_parcial_8_candidatos.json e .csv gerados
   dentro da pasta resultados/.

Teste 2025 opcional: instale Git e rode
  PREPARAR_DADOS_2025.bat
depois:
  py -3.11 testar_8_permitidos.py --periodo 2025

## MT5
Apenas o arquivo em mt5_ea_separado/ pode ser aberto no MetaEditor,
compilado em sua instalação e usado no Strategy Tester. Não há .ex5
pré-compilado e **não houve validação de compilação em MetaEditor**
neste pacote. Ele é um robô de vector breakout/retest diferente e deve
ser testado em conta DEMO, não real. Por padrão o EA existente requer
opt-in explícito para conta real.

Para os 12 candidatos estudados, construir, conferir e compilar ports
MQL5 separados antes de testes no Strategy Tester de MT5. As dezenas
de números históricos registrados são replay OHLC com pontos assumidos
de 0,01 USD/oz por ponto, custos simulados, e **não lucros reais**.

**Padrão de pesquisa ativo: somente XAUUSD M1, M5, M15, M30.**
Resultados 2025 vs 2026 parcial, fontes diferentes, não OOS independente.
"""
    bat="""@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul || (echo Instale Python 3.11 e tente novamente. & pause & exit /b 1)
py -3.11 -m pip install --disable-pip-version-check -r requirements.txt || (echo Falha nas dependencias. & pause & exit /b 1)
py -3.11 testar_8_permitidos.py --periodo 2026
echo.
echo Veja a pasta resultados.
pause
"""
    prepare="""@echo off
setlocal
cd /d "%~dp0"
where git >nul 2>nul || (echo Instale Git para Windows. & pause & exit /b 1)
if exist thirdparty\gold\.git (echo Fonte 2025 ja presente. & pause & exit /b 0)
mkdir thirdparty 2>nul
git clone --quiet --filter=blob:none --sparse https://github.com/parshant65-lang/Gold-XAUUSD-1m-2020-2025-Historical-Data.git thirdparty\gold || (echo Falha git clone. & pause & exit /b 1)
git -C thirdparty\gold checkout --quiet b2cfdc571ffac9eff9f2132ea6946da559d29af2 || (echo Falha no commit fixo. & pause & exit /b 1)
git -C thirdparty\gold sparse-checkout set XAUUSD/1m/2025 || (echo Falha ao baixar dados 2025. & pause & exit /b 1)
echo Dados 2025 preparados.
pause
"""
    OUT.parent.mkdir(exist_ok=True,parents=True)
    with zipfile.ZipFile(OUT,"w",zipfile.ZIP_DEFLATED,compresslevel=8) as zipf:
        prefix=ARCHIVE_PREFIX+"/"
        def write(name,content):
            zipf.writestr(prefix+name,content)
        write("LEIA_PRIMEIRO.md",readme)
        write("requirements.txt","numpy==2.3.4\npandas==2.3.3\n")
        write("TESTAR_8_PERMITIDOS_2026.bat",bat)
        write("PREPARAR_DADOS_2025.bat",prepare)
        runner=BASE/"distribution/xau_saved_12/testar_8_permitidos.py"
        if not runner.exists():raise AssertionError("runner not found")
        write("testar_8_permitidos.py",runner.read_text(encoding="utf-8"))
        write("catalogo/12_candidatos_salvos.json",json.dumps(registry,indent=2,ensure_ascii=False)+"\n")
        mapping=[]
        count_eligible=0
        for candidate in items:
            allowed=candidate["timeframe"] in ALLOWED
            count_eligible+=allowed
            manifest=dict(
                id=candidate["id"],timeframe=candidate["timeframe"],
                current_research_scope="TF_PERMITIDO" if allowed else "APENAS_HISTORICO_M12_M20",
                implementation_language="Python research, NOT MT5 .ex5",
                code_files=["pesquisa_python/"+f for f in SOURCES[candidate["id"]]],
                candidate_definition=candidate,
                is_compiled_ea=False,
                real_trading_approved=False)
            write("catalogo/configuracoes_individuais/"+candidate["id"]+".json",
                  json.dumps(manifest,indent=2,ensure_ascii=False)+"\n")
            mapping.append(dict(id=candidate["id"],TF=candidate["timeframe"],
                 type="research_Python",status="PERMITIDO" if allowed else "HISTORICO_SOMENTE",
                 src=";".join(SOURCES[candidate["id"]])))
        if count_eligible!=8:raise AssertionError("expected 8 authorized and 4 legacy TF")
        buf=io.StringIO();csvw=csv.DictWriter(buf,fieldnames=["id","TF","type","status","src"]);csvw.writeheader();csvw.writerows(mapping)
        write("catalogo/INDICE_CODIGOS.csv",buf.getvalue())
        for file in sorted(SOURCE.glob("*.py")):
            write("pesquisa_python/"+file.name,file.read_text(encoding="utf-8"))
        write("pesquisa_python/README_original.md",(SOURCE/"README.md").read_text(encoding="utf-8"))
        write("mt5_ea_separado/Nexus_Vector_Retest_EA_v1.00.mq5",mql.read_text(encoding="utf-8"))
        write("mt5_ea_separado/NAO_SAO_OS_12.txt",
         "EA MQL5 diferente (Vector breakout/retest). Nao reproduz os backtests dos 12 catalogados.\nNao afirmar compilado nem validado ate MetaEditor confirmar.\n")
        for entry in PRESERVED:
            write("historico/"+pathlib.Path(entry).name,main_text(entry))
    with zipfile.ZipFile(OUT) as check:
        names=check.namelist()
        actual={p.split("catalogo/configuracoes_individuais/")[1].removesuffix(".json")
                 for p in names if "catalogo/configuracoes_individuais/" in p}
        if actual!={x["id"] for x in items}:raise AssertionError("missing per-model manifests")
        if sum(x.endswith(".mq5") for x in names)!=1:raise AssertionError("wrong EA count")
        if not any(x.endswith("xau_session_batch9_2025plus.py") for x in names):
            raise AssertionError("latest candidate code not included")
    print(json.dumps({"zip":str(OUT),"size_bytes":OUT.stat().st_size,
     "saved_models":len(items),"eligible_tf":count_eligible,
     "historical_only":len(items)-count_eligible,
     "actual_MQL5_EAs_SEPARATE":1,"compiled_ex5":0,
     "files_in_zip":len(names)}))


if __name__=="__main__":main()
