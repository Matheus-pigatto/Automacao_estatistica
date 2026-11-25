import base64
import json
import os
import sys
import xml.etree.ElementTree as ET

import pytest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT_DIR, "src")
DB_DIR = os.path.join(ROOT_DIR, "db")

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
if DB_DIR not in sys.path:
    sys.path.insert(0, DB_DIR)

import config
from adb_manipulation import ADBController
from database import DatabaseManager
from db.rag import SorteioRAG
from image_read import extrair_cartela_ocr_1440
from telegram_bot import TelegramBot
from ui import AbaEstatisticas, AbaRobo, AbaSimuladas, AbaSistema
from webScrapy import _decodificar_pdfemb_urls


# ----------------------------------------------------------------------
# 1. CONFIGURAÇÃO E MÓDULOS UI
# ----------------------------------------------------------------------
def test_config_caminhos_existem():
    assert os.path.isdir(config.PROJECT_ROOT)
    assert os.path.isdir(config.SRC_DIR)
    assert os.path.isdir(config.DB_DIR)
    assert os.path.isdir(config.RAG_DIR)


def test_ui_classes_importadas():
    assert all(cls is not None for cls in (AbaRobo, AbaSimuladas, AbaEstatisticas, AbaSistema))


# ----------------------------------------------------------------------
# 2. DATABASE MANAGER (SQLITE ISOLADO EM tmp_path)
# ----------------------------------------------------------------------
def test_database_estado_e_decisoes(tmp_path):
    db_file = str(tmp_path / "test_valecap.db")
    db = DatabaseManager(db_path=db_file, migrar_csvs=False)
    db.init_db()

    estado = db.obter_estado_robo()
    assert estado["status"] == "AGUARDANDO"
    assert estado["quantidade"] == 1

    db.atualizar_estado_robo(tipo="hipercap", quantidade=5, media_corte=57.85, status="PROCESSANDO", progresso=50)
    estado2 = db.obter_estado_robo()
    assert estado2["tipo"] == "hipercap"
    assert estado2["quantidade"] == 5
    assert pytest.approx(estado2["media_corte"], 0.001) == 57.85
    assert estado2["progresso"] == 50

    db.registrar_decisao("123.456", ["01", "02"], 51.2, 54.8, "Rejeitado_IA")
    df_dec = db.carregar_decisoes_df()
    assert len(df_dec) == 1
    assert df_dec.iloc[0]["ID_Cartela"] == "123.456"
    assert pytest.approx(float(df_dec.iloc[0]["Weighted_Score"]), 0.01) == 54.8


def test_database_aprovacao_e_limites(tmp_path):
    db = DatabaseManager(db_path=str(tmp_path / "test_aprov.db"), migrar_csvs=False)
    db.init_db()

    stats = {
        "media": 57.75,
        "media_pura": 58.10,
        "ganho_rag": 0.35,
        "prob_50": 1.8,
        "prob_55": 15.2,
        "pure_score": 50.0,
        "weighted_score": 55.25,
        "resumo_dezenas": {"elite": 7, "medio": 9, "inerte": 4, "atraso_medio": 0.9},
        "monte_carlo_data": [55, 57, 58, 59],
    }
    db.salvar_aprovacao_pendente("999.111", ["01", "02", "03"], stats)
    pend = db.obter_aprovacao_pendente()
    assert pend is not None
    assert pend["id_cartela"] == "999.111"
    assert pend["status"] == "aguardando_aprovacao"
    assert pend["dezenas"] == ["01", "02", "03"]

    db.atualizar_status_aprovacao("ACEITO")
    assert db.obter_aprovacao_pendente()["status"] == "ACEITO"

    db.limpar_aprovacao_pendente()
    assert db.obter_aprovacao_pendente() is None

    db.registrar_limite_espera("2026-11-21 14:00:00", 15, 24, "Muitas pessoas escolhendo agora")
    df_lim = db.carregar_limites_espera_df()
    assert len(df_lim) == 1
    assert int(df_lim.iloc[0]["Cartelas_Ate_Aviso"]) == 15
    assert int(df_lim.iloc[0]["Tempo_Espera_Segundos"]) == 24


# ----------------------------------------------------------------------
# 3. ADB CONTROLLER & XML PARSING
# ----------------------------------------------------------------------
def test_adb_parse_bounds_e_extrair_cartela_xml():
    ctrl = ADBController()
    assert ctrl.parse_bounds("[100,200][300,400]") == (100, 200, 300, 400, 200, 300)
    assert ctrl.parse_bounds("invalido") == (0, 0, 0, 0, 0, 0)

    dezenas_mock = [
        "01", "03", "04", "06", "15",
        "17", "20", "24", "25", "26",
        "32", "33", "37", "39", "44",
        "50", "52", "53", "57", "59",
    ]
    nos_dezenas = "\n".join(
        f'<node class="android.widget.TextView" text="{d}" bounds="[62,{565 + (i // 5) * 102}][140,{643 + (i // 5) * 102}]" />'
        for i, d in enumerate(dezenas_mock)
    )
    xml_str = f"""
    <hierarchy>
        <node class="android.widget.TextView" text="464.155" bounds="[576,434][798,488]" />
        {nos_dezenas}
    </hierarchy>
    """
    tree = ET.ElementTree(ET.fromstring(xml_str))
    res = ctrl.extrair_cartela_xml(tree)
    assert res["status"] == "sucesso"
    assert res["titulo"] == "464.155"
    assert res["dezenas"] == dezenas_mock


def test_adb_xml_parcial_retorna_alerta():
    ctrl = ADBController()
    xml_str = """
    <hierarchy>
        <node class="android.widget.TextView" text="464.155" bounds="[576,434][798,488]" />
        <node class="android.widget.TextView" text="01" bounds="[62,565][140,643]" />
        <node class="android.widget.TextView" text="03" bounds="[372,565][450,643]" />
    </hierarchy>
    """
    tree = ET.ElementTree(ET.fromstring(xml_str))
    res = ctrl.extrair_cartela_xml(tree)
    assert res["status"] == "alerta_falha_leitura"
    assert res["dezenas"] == ["01", "03"]


# ----------------------------------------------------------------------
# 4. RAG & MONTE CARLO VETORIZADO
# ----------------------------------------------------------------------
def test_rag_monte_carlo_valido_e_invalido(tmp_path):
    rag = SorteioRAG(caminho_base=str(tmp_path / "rag"))
    cartela = [1, 3, 4, 7, 9, 18, 20, 23, 25, 27, 32, 34, 36, 43, 44, 50, 54, 56, 59, 60]
    res = rag.simular_monte_carlo(cartela, num_simulacoes=2000, usar_pesos_rag=False)

    assert len(res["monte_carlo_data"]) == 2000
    assert 57.5 <= res["media"] <= 58.6  # média teórica uniforme é ~58.10
    assert 0.0 <= res["prob_50"] <= 100.0
    assert 0.0 <= res["prob_55"] <= 100.0
    assert 0.0 <= res["weighted_score"] <= 100.0

    invalida = rag.simular_monte_carlo([1, 2, 3], num_simulacoes=100)
    assert invalida["monte_carlo_data"] == []
    assert invalida["media"] == 60.0


def test_rag_base_real_carregada():
    rag = SorteioRAG(caminho_base=config.RAG_DIR)
    assert len(rag.memoria.get("objetos_sorteio", [])) >= 372
    stats = rag.memoria.get("estatisticas", {})
    assert "frequencia" in stats
    av = rag.memoria.get("metricas_avancadas", {})
    assert "chi_score" in av and "atrasos" in av and "tendencias" in av


# ----------------------------------------------------------------------
# 5. OCR FALLBACK (1440x2560) NOS PRINTS REAIS DE TESTE
# ----------------------------------------------------------------------
def test_ocr_1440_print_debug_exato():
    caminho = os.path.join(config.SS_DIR, "print_debug.PNG")
    if not os.path.exists(caminho):
        pytest.skip(f"Imagem de referência ausente: {caminho}")
    res = extrair_cartela_ocr_1440(caminho)
    assert res["status"] == "sucesso"
    assert res["titulo"] == "473.656"
    assert res["dezenas"] == [
        "02", "06", "12", "13", "14",
        "18", "22", "24", "27", "28",
        "34", "36", "37", "41", "44",
        "50", "54", "58", "59", "60",
    ]


def test_ocr_1440_print_atual_invariantes():
    caminho = os.path.join(config.SS_DIR, "print.PNG")
    if not os.path.exists(caminho):
        pytest.skip("Sem screenshot ativo em db/ss/print.PNG")
    res = extrair_cartela_ocr_1440(caminho)
    assert res["status"] == "sucesso"
    assert len(res["dezenas"]) == 20
    assert len(set(res["dezenas"])) == 20
    vals = [int(d) for d in res["dezenas"]]
    assert all(1 <= v <= 15 for v in vals[0:5])
    assert all(16 <= v <= 30 for v in vals[5:10])
    assert all(31 <= v <= 45 for v in vals[10:15])
    assert all(46 <= v <= 60 for v in vals[15:20])


# ----------------------------------------------------------------------
# 6. WEBSCRAPY & TELEGRAM BOT
# ----------------------------------------------------------------------
def test_webscrapy_decodificar_pdfemb():
    payload = json.dumps({"url": "https://www.portalr3.com.br/wp-content/uploads/2026/11/teste.pdf"})
    b64 = base64.b64encode(payload.encode("utf-8")).decode("utf-8")
    html = f'<iframe src="https://www.portalr3.com.br/?pdfemb-data={b64}"></iframe>'
    urls = _decodificar_pdfemb_urls(html)
    assert urls == ["https://www.portalr3.com.br/wp-content/uploads/2026/11/teste.pdf"]


def test_telegram_bot_sem_credenciais():
    bot = TelegramBot(token="", chat_id="")
    assert bot.esta_configurado() is False
    assert bot.enviar_mensagem("teste") is False
    assert bot.enviar_cartela_aprovacao("123.456", ["01"], {}) is None
    assert bot.verificar_decisao("123.456") is None


def test_adb_limites_cards_e_qtd_modal():
    from automacao_adb import AutomacaoADB

    xml_carrinho_vale_topo = """<?xml version="1.0" encoding="UTF-8"?>
    <hierarchy rotation="0">
      <node text="Vale Cap" class="android.view.View" bounds="[652,72][764,109]" />
      <node text="Vale Cap" class="android.widget.TextView" bounds="[42,216][1362,254]" />
      <node content-desc="Quero 1" class="android.view.ViewGroup" bounds="[42,919][159,973]" />
      <node text="HiperXCAP" class="android.widget.TextView" bounds="[42,1146][1362,1184]" />
      <node content-desc="Quero 1" class="android.view.ViewGroup" bounds="[42,1846][158,1900]" />
    </hierarchy>"""
    xml_carrinho_hiper_topo = """<?xml version="1.0" encoding="UTF-8"?>
    <hierarchy rotation="0">
      <node text="Vale Cap" class="android.view.View" bounds="[652,72][764,109]" />
      <node text="HiperXCAP" class="android.widget.TextView" bounds="[42,216][1362,254]" />
      <node content-desc="Quero 1" class="android.view.ViewGroup" bounds="[42,916][158,970]" />
      <node text="Vale Cap" class="android.widget.TextView" bounds="[42,1143][1362,1181]" />
      <node content-desc="Quero 1" class="android.view.ViewGroup" bounds="[42,1846][158,1900]" />
    </hierarchy>"""
    xml_modal = """<?xml version="1.0" encoding="UTF-8"?>
    <hierarchy rotation="0">
      <node text="Complete seu pedido" class="android.widget.TextView" bounds="[24,949][1416,985]" />
      <node text="Qtd. selecionada" class="android.widget.TextView" bounds="[24,1020][300,1050]" />
      <node text="3" class="android.widget.TextView" bounds="[24,1055][80,1095]" />
    </hierarchy>"""

    robo = AutomacaoADB(rag_sorteios=None)
    limites1 = robo._obter_limites_cards_carrinho(ET.ElementTree(ET.fromstring(xml_carrinho_vale_topo)))
    assert limites1["valecap"] == (216, 1146)
    assert limites1["hiperxcap"] == (1146, 2250)

    limites2 = robo._obter_limites_cards_carrinho(ET.ElementTree(ET.fromstring(xml_carrinho_hiper_topo)))
    assert limites2["hiperxcap"] == (216, 1143)
    assert limites2["valecap"] == (1143, 2250)

    qtd_modal = robo._extrair_qtd_modal_pedido(ET.ElementTree(ET.fromstring(xml_modal)))
    assert qtd_modal == 3
