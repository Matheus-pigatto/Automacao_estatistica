import json
import logging
import os
import shutil
from datetime import datetime
from time import sleep, time

import pandas as pd

from adb_manipulation import (
    abrir_app_android,
    clicar_por_texto,
    dump_ui_xml,
    encontrar_no_xml,
    escrever_texto_adb,
    existe_texto_na_tela,
    extrair_cartela_xml,
    garantir_conexao_adb,
    parse_bounds,
    swipe_adb,
    tap_adb,
)
from config import (
    ADB_DEVICE,
    ARVORE_DECISAO,
    DB_DIR,
    RAG_DIR,
    SS_DIR,
    get_login_credenciais,
)
from db.rag import SorteioRAG
from telegram_bot import TelegramBot

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class AutomacaoADB:
    def __init__(self, rag_sorteios: SorteioRAG):
        self.target_device = ADB_DEVICE
        self.rag = rag_sorteios
        self.telegram = TelegramBot()
        self.config_ia = ARVORE_DECISAO["CARRINHO"]["PAGAMENTO"]["fluxo"][3]["fluxo"][1]["escolher_numeros_titulo"]["config"]

    def reportar_estado(self, percentual: int, mensagem: str) -> None:
        """Atualiza o JSON para o Dashboard Streamlit mostrar o progresso."""
        caminho_config = os.path.join(DB_DIR, "config_automacao.json")
        config_atual = self.carregar_config_dashboard() or {}
        try:
            if os.path.exists(caminho_config):
                path_temp = caminho_config + ".tmp"
                config_atual["progresso"] = percentual
                config_atual["msg_status"] = mensagem
                with open(path_temp, "w", encoding="utf-8") as f:
                    json.dump(config_atual, f, indent=4)
                os.replace(path_temp, caminho_config)
            logging.info(f"📊 Progresso: {percentual}% - {mensagem}")
        except Exception as e:
            logging.error(f"Erro ao reportar estado: {e}")

    def carregar_config_dashboard(self):
        path_original = os.path.join(DB_DIR, "config_automacao.json")
        path_copia_trabalho = os.path.join(DB_DIR, "config_robo_copy.json")

        if not os.path.exists(path_original):
            return None

        try:
            shutil.copy2(path_original, path_copia_trabalho)
            sleep(0.2)
            if os.path.getsize(path_copia_trabalho) > 0:
                with open(path_copia_trabalho, "r", encoding="utf-8") as f:
                    return json.load(f)
        except (json.JSONDecodeError, PermissionError, OSError):
            return None
        return None

    def carregar_credenciais(self) -> tuple[str, str]:
        try:
            return get_login_credenciais()
        except Exception as e:
            logging.error(f"❌ Erro ao carregar credenciais: {e}")
            return "", ""

    def realizar_login(self) -> bool:
        """Verifica se o usuário já está logado via XML; caso contrário, faz login automático."""
        self.reportar_estado(10, "Verificando login via XML...")
        logging.info("🔐 Verificando estado de login via XML...")

        tree = dump_ui_xml()
        if existe_texto_na_tela(["Seu saldo", "Olá "], tree=tree, contem=True):
            logging.info("✅ Usuário já está logado.")
            self.reportar_estado(25, "Login confirmado. Acessando área de compra...")
            return True

        if not clicar_por_texto(["Acessar conta", "Acesse sua conta"], timeout=10, contem=False, delay_pos=2.0):
            logging.error("❌ Botão 'Acessar conta' não encontrado no XML.")
            return False

        self.reportar_estado(20, "Preenchendo CPF e senha...")
        cpf, senha = self.carregar_credenciais()
        if not cpf or not senha:
            logging.error("❌ CPF/Senha vazios. Configure VALECAP_CPF e VALECAP_SENHA no .env.")
            return False

        if not clicar_por_texto("Número do CPF", timeout=8, classe="EditText", delay_pos=0.8):
            logging.error("❌ Campo CPF não encontrado.")
            return False
        escrever_texto_adb(cpf)

        if not clicar_por_texto("Senha de acesso", timeout=8, classe="EditText", delay_pos=0.8):
            logging.error("❌ Campo Senha não encontrado.")
            return False
        escrever_texto_adb(senha)

        if not clicar_por_texto(["Acessar", "Entrar"], timeout=8, delay_pos=4.0):
            logging.error("❌ Botão 'Acessar' não encontrado.")
            return False

        if existe_texto_na_tela(["Seu saldo", "Olá "], contem=True):
            logging.info("✅ Login realizado com sucesso via XML!")
            self.reportar_estado(30, "Login realizado. Acessando área de compra...")
            return True

        logging.warning("⚠️ Login enviado, mas confirmação 'Seu saldo' não apareceu ainda.")
        return True

    def entrar_area_compra(self) -> bool:
        """Navega da Home para a tela de Carrinho/Compra via XML."""
        self.reportar_estado(35, "Abrindo Participe e Concorra...")
        return clicar_por_texto("Participe e Concorra", timeout=10, delay_pos=2.5)

    def selecionar_quantidade(self, tipo_cap: str = "valecap", qtd: int = 1) -> bool:
        """Seleciona a quantidade desejada (ex: 'Quero 1', 'Quero 2', 'Quero 4') e clica em Continuar."""
        self.reportar_estado(45, f"Selecionando {qtd} título(s) ({tipo_cap})...")
        if not clicar_por_texto(f"Quero {qtd}", timeout=10, delay_pos=1.5):
            logging.error(f"❌ Botão 'Quero {qtd}' não encontrado.")
            return False

        self.reportar_estado(55, "Avançando para o pedido...")
        return clicar_por_texto("Continuar", timeout=10, delay_pos=2.5)

    def _rolar_modal_ate_visivel(self, texto: str, contem: bool = True, max_y: int = 2120, max_scrolls: int = 5):
        """Rola o modal 'Complete seu pedido' até que o elemento fique acima do rodapé fixo."""
        for _ in range(max_scrolls):
            tree = dump_ui_xml()
            no = encontrar_no_xml(tree, texto, contem=contem, max_y=max_y)
            if no is not None:
                return no
            swipe_adb(720, 2050, 720, 1650, 400)
            sleep(1.2)
        return None

    def iniciar_por_dashboard(self) -> bool:
        """Orquestra o fluxo completo baseado na configuração gravada pelo Streamlit."""
        config = self.carregar_config_dashboard()
        if not config:
            logging.warning("⚠️ Nenhuma configuração encontrada no Dashboard.")
            return False

        tipo = config.get("tipo", "valecap")
        qtd = int(config.get("quantidade", 1))
        logging.info(f"🎯 Iniciando missão via XML: {tipo} | {qtd} título(s)")

        if not self.selecionar_quantidade(tipo, qtd):
            return False

        return self.analisar_e_escolher_titulos(tipo, qtd)

    def analisar_e_escolher_titulos(self, tipo_jogo: str, qtd_total: int) -> bool:
        """Abre a seção 'Número do titulo', seleciona o produto e analisa cada título via XML + RAG."""
        self.reportar_estado(65, f"Abrindo escolha de títulos ({tipo_jogo})...")

        # 1. Expande 'Número do titulo' (se ainda estiver recolhido com 'Ver mais')
        no_num = self._rolar_modal_ate_visivel("Número do titulo", contem=True)
        if no_num is None:
            logging.error("❌ Seção 'Número do titulo' não encontrada no modal.")
            return False

        tree_atual = dump_ui_xml()
        if existe_texto_na_tela("Ver mais", tree=tree_atual, contem=False):
            _, _, _, _, cx, cy = parse_bounds(no_num.attrib["bounds"])
            tap_adb(cx, cy, random_offset=5)
            sleep(2.0)

        # 2. Abre o grupo do produto ('Vale Cap, X titulo para escolher' / 'Hiper...')
        alvo_produto = "titulo para escolher"
        no_prod = self._rolar_modal_ate_visivel(alvo_produto, contem=True)
        if no_prod is None:
            logging.error("❌ Opção 'titulo para escolher' não encontrada.")
            return False

        _, _, _, _, cx, cy = parse_bounds(no_prod.attrib["bounds"])
        tap_adb(cx, cy, random_offset=5)
        sleep(2.0)

        # 3. Percorre os títulos (1..qtd_total) clicando em 'Escolher número'
        for i in range(1, qtd_total + 1):
            self.reportar_estado(75, f"Abrindo seleção do título {i} de {qtd_total}...")
            no_escolher = self._rolar_modal_ate_visivel("Escolher número", contem=True)
            if no_escolher is None:
                logging.error(f"❌ Botão 'Escolher número' não encontrado para o título {i}.")
                return False

            _, _, _, _, cx, cy = parse_bounds(no_escolher.attrib["bounds"])
            tap_adb(cx, cy, random_offset=5)
            sleep(3.0)

            aprovado = self.processar_ciclo_ia(titulo_idx=i, qtd_total=qtd_total)
            if not aprovado:
                logging.warning(f"⚠️ Título {i} não foi confirmado.")
                return False

        return True

    def _extrair_texto_aviso(self, tree) -> str:
        """Extrai o texto legível do modal de aviso/espera no XML."""
        partes = []
        for el in tree.iter("node"):
            if "TextView" not in el.attrib.get("class", ""):
                continue
            t = el.attrib.get("text", "").strip()
            if t and not (len(t) == 1 and ord(t) > 50000):
                if any(p in t.lower() for p in ("limite", "muitas pessoas", "aguarde", "imprevisto", "minuto", "espera", "tente")):
                    partes.append(t)
        return " | ".join(dict.fromkeys(partes)) or "Aviso de limite/espera"

    def _tratar_avisos_xml(self, tree, cartelas_ate_aviso: int) -> bool:
        """
        Detecta pop-ups de limite/espera no XML, registra quantas cartelas foram lidas
        até o bloqueio e mede o tempo real necessário até o app liberar novamente.
        """
        if not existe_texto_na_tela(["limite", "muitas pessoas", "aguarde", "imprevisto"], tree=tree, contem=True):
            return False

        texto_aviso = self._extrair_texto_aviso(tree)
        inicio_ts = datetime.now()
        t0 = time()
        delay_max = int(self.config_ia.get("delay_bloqueio", 900))

        logging.warning(
            f"⏳ AVISO DE ESPERA após {cartelas_ate_aviso} cartelas! "
            f"Texto: '{texto_aviso}' | Monitorando tempo real de liberação..."
        )
        self.reportar_estado(
            80,
            f"⏳ Aviso após {cartelas_ate_aviso} cartelas ({texto_aviso}). Medindo tempo de espera...",
        )
        self.telegram.enviar_mensagem(
            f"⏳ <b>Aviso de espera detectado</b> após <b>{cartelas_ate_aviso} cartelas</b>.\n"
            f"Mensagem: <i>{texto_aviso}</i>\nMonitorando tempo até liberar..."
        )

        clicar_por_texto(["Entendi", "OK", "Fechar"], timeout=5, contem=True, delay_pos=1.5)

        # Sonda a cada 20s até a tela voltar a aceitar troca de cartela sem novo aviso
        intervalo_sonda = 20
        tempo_espera_s = 0
        while True:
            sleep(intervalo_sonda)
            tempo_espera_s = int(time() - t0)
            self.reportar_estado(
                80,
                f"⏳ Em espera há {tempo_espera_s}s (após {cartelas_ate_aviso} cartelas)...",
            )

            # Tenta avançar uma cartela para testar se o limite já foi liberado
            swipe_adb(1250, 990, 200, 990, 400)
            sleep(1.5)
            tree_sonda = dump_ui_xml()
            if tree_sonda is None:
                continue

            if existe_texto_na_tela(["limite", "muitas pessoas", "aguarde", "imprevisto"], tree=tree_sonda, contem=True):
                clicar_por_texto(["Entendi", "OK", "Fechar"], timeout=4, contem=True, delay_pos=1.0)
                if tempo_espera_s >= delay_max:
                    logging.warning(f"⏰ Tempo máximo ({delay_max}s) atingido ainda sob aviso.")
                    break
                continue

            dados_teste = extrair_cartela_xml(tree_sonda)
            if dados_teste.get("status") == "sucesso":
                logging.info(f"✅ Seleção liberada novamente após {tempo_espera_s}s!")
                break

        salvar_log_limite_espera(
            timestamp_aviso=inicio_ts.strftime("%Y-%m-%d %H:%M:%S"),
            cartelas_ate_aviso=cartelas_ate_aviso,
            tempo_espera_s=tempo_espera_s,
            texto_aviso=texto_aviso,
        )
        self.telegram.enviar_mensagem(
            f"✅ <b>Seleção liberada!</b>\n"
            f"Cartelas antes do aviso: <b>{cartelas_ate_aviso}</b>\n"
            f"Tempo real de espera: <b>{tempo_espera_s}s</b> ({tempo_espera_s / 60:.1f} min)"
        )
        return True

    def processar_ciclo_ia(self, titulo_idx: int = 1, qtd_total: int = 1) -> bool:
        """Lê cartelas via XML, avalia com Monte Carlo RAG e troca por swipe até aprovar."""
        limite_tentativas = int(self.config_ia.get("limite_tentativas", 100))
        tentativas = 0
        cartelas_ate_aviso = 0
        falhas_seguidas = 0
        ultimo_titulo = None

        logging.info(f"🚀 Iniciando análise de cartelas via XML + Monte Carlo RAG (Título {titulo_idx}/{qtd_total})...")

        while tentativas < limite_tentativas:
            tree = dump_ui_xml()
            if tree is None:
                falhas_seguidas += 1
                if falhas_seguidas > 5:
                    logging.error("❌ Múltiplas falhas ao ler XML da tela.")
                    return False
                sleep(1.5)
                continue

            if self._tratar_avisos_xml(tree, cartelas_ate_aviso):
                cartelas_ate_aviso = 0
                continue

            self.reportar_estado(
                85,
                f"Analisando cartela #{cartelas_ate_aviso + 1} (Título {titulo_idx}/{qtd_total})...",
            )
            dados_cartela = extrair_cartela_xml(tree)
            logging.info(f"🎴 Cartela XML: Título={dados_cartela['titulo']} | Dezenas={dados_cartela['dezenas']}")

            if dados_cartela.get("status") != "sucesso":
                falhas_seguidas += 1
                # Se houver overlay da mãozinha ("arraste para o lado"), um toque na tela dispensa o overlay
                logging.warning(f"⚠️ Leitura incompleta ({len(dados_cartela['dezenas'])} dezenas). Tocando na tela para dispensar overlay...")
                tap_adb(720, 990, random_offset=10)
                if falhas_seguidas > 5:
                    logging.error("❌ Múltiplas falhas consecutivas na leitura da cartela.")
                    return False
                sleep(1.5)
                continue

            falhas_seguidas = 0
            if dados_cartela["titulo"] != ultimo_titulo:
                cartelas_ate_aviso += 1
                ultimo_titulo = dados_cartela["titulo"]

            decisao = self.gerir_decisao_cartela(dados_cartela)

            if decisao == "COMPRAR":
                logging.info("🔥 CARTELA APROVADA! Confirmando título via XML...")
                clicar_por_texto(
                    ["Confirmar e escolher próximo", "Confirmar e finalizar", "Confirmar"],
                    timeout=10,
                    contem=True,
                    delay_pos=2.0,
                )
                return True

            # Desliza a cartela para a esquerda para carregar a próxima opção
            logging.info(f"👎 Cartela #{cartelas_ate_aviso} descartada. Arrastando para a próxima...")
            swipe_adb(1250, 990, 200, 990, 400)
            tentativas += 1
            sleep(1.2)

        logging.warning("❌ Limite de tentativas atingido sem aprovação.")
        return False

    def gerir_decisao_cartela(self, dados_cartela: dict) -> str:
        """Executa Monte Carlo ponderado pelo RAG, filtra cartelas frias e consulta o usuário (Streamlit + Telegram)."""
        titulo = dados_cartela.get("titulo", "desconhecido")
        dezenas = dados_cartela.get("dezenas", [])

        try:
            if len(dezenas) != 20:
                return "PROXIMA"

            stats = self.rag.simular_monte_carlo(dezenas_cartela=dezenas)
            media = stats.get("media", 60.0)
            media_corte = float(self.config_ia.get("media_corte", 57.6))

            if media > media_corte:
                salvar_log_decisao(titulo, dezenas, stats, "Rejeitado_IA")
                logging.info(f"🚫 Cartela FRIA (Média RAG: {media:.2f} > {media_corte}). Descartando...")
                return "PROXIMA"

            logging.info(
                f"🔥 Cartela BOA encontrada (Título {titulo} | Média RAG: {media:.2f} | "
                f"Score: {stats.get('weighted_score', 0):.1f})! Aguardando decisão (Streamlit ou Telegram)..."
            )
            self.comunicar_dashboard({"titulo": titulo, "dezenas": dezenas}, stats)
            self.telegram.enviar_cartela_aprovacao(titulo, dezenas, stats)

            caminho_json = os.path.join(DB_DIR, "comunicacao_app.json")
            while True:
                sleep(1.5)
                # 1. Verifica decisão pelo Telegram (celular)
                decisao_tg = self.telegram.verificar_decisao(titulo)
                if decisao_tg in ("ACEITO", "DESISTIDO"):
                    if os.path.exists(caminho_json):
                        os.remove(caminho_json)
                    if decisao_tg == "ACEITO":
                        salvar_log_decisao(titulo, dezenas, stats, "Comprado_Telegram")
                        return "COMPRAR"
                    salvar_log_decisao(titulo, dezenas, stats, "Desistido_Telegram")
                    return "PROXIMA"

                # 2. Verifica decisão pelo Dashboard Streamlit
                if os.path.exists(caminho_json):
                    with open(caminho_json, "r", encoding="utf-8") as f:
                        dados = json.load(f)

                    if dados.get("status") == "ACEITO":
                        salvar_log_decisao(titulo, dezenas, stats, "Comprado")
                        os.remove(caminho_json)
                        self.telegram.enviar_mensagem(f"✅ Título <code>{titulo}</code> aprovado pelo Dashboard!")
                        return "COMPRAR"
                    if dados.get("status") == "DESISTIDO":
                        salvar_log_decisao(titulo, dezenas, stats, "Desistido_Usuario")
                        os.remove(caminho_json)
                        self.telegram.enviar_mensagem(f"❌ Título <code>{titulo}</code> descartado pelo Dashboard.")
                        return "PROXIMA"

        except Exception as e:
            logging.error(f"❌ Erro crítico na análise da cartela: {e}")
            return "PROXIMA"

    def comunicar_dashboard(self, dados_cartela: dict, stats: dict) -> None:
        caminho_temp = os.path.join(DB_DIR, "comunicacao_app.json")
        payload = {
            "timestamp": datetime.now().isoformat(),
            "id_cartela": dados_cartela.get("titulo", "desconhecido"),
            "dezenas": dados_cartela.get("dezenas", []),
            "media": stats.get("media"),
            "media_pura": stats.get("media_pura"),
            "ganho_rag": stats.get("ganho_rag"),
            "prob_50": stats.get("prob_50"),
            "prob_55": stats.get("prob_55"),
            "pure_score": stats.get("pure_score"),
            "weighted_score": stats.get("weighted_score"),
            "resumo_dezenas": stats.get("resumo_dezenas", {}),
            "monte_carlo_data": stats.get("monte_carlo_data"),
            "status": "aguardando_aprovacao",
        }
        with open(caminho_temp, "w", encoding="utf-8") as f:
            json.dump(payload, f)


def salvar_log_limite_espera(timestamp_aviso: str, cartelas_ate_aviso: int, tempo_espera_s: int, texto_aviso: str):
    """Registra quantas cartelas foram lidas até o aviso de espera e quanto tempo levou para liberar."""
    arquivo = os.path.join(DB_DIR, "log_limites_espera.csv")
    df = pd.DataFrame([{
        "Timestamp_Aviso": timestamp_aviso,
        "Cartelas_Ate_Aviso": cartelas_ate_aviso,
        "Tempo_Espera_Segundos": tempo_espera_s,
        "Tempo_Espera_Minutos": round(tempo_espera_s / 60.0, 2),
        "Texto_Aviso": texto_aviso,
    }])
    if not os.path.exists(arquivo):
        df.to_csv(arquivo, index=False, sep=";")
    else:
        df.to_csv(arquivo, mode="a", header=False, index=False, sep=";")


def salvar_log_decisao(id_ref, dezenas, scores, decisao):
    """Gera o CSV de aprendizado/auditoria de decisões."""
    data_str = datetime.now().strftime("%Y-%m-%d")
    arquivo = os.path.join(DB_DIR, f"{data_str}_log_decisoes.csv")

    novo_log = {
        "ID_Cartela": id_ref,
        "Dezenas": str(dezenas),
        "Pure_Score": scores["pure_score"],
        "Weighted_Score": scores["weighted_score"],
        "Decisao": decisao,
        "Hora": datetime.now().strftime("%H:%M:%S"),
    }

    df = pd.DataFrame([novo_log])
    if not os.path.exists(arquivo):
        df.to_csv(arquivo, index=False, sep=";")
    else:
        df.to_csv(arquivo, mode="a", header=False, index=False, sep=";")


def limparFotos():
    if not os.path.exists(SS_DIR):
        return False

    for item in os.listdir(SS_DIR):
        if item.lower().endswith((".png", ".xml")):
            try:
                os.remove(os.path.join(SS_DIR, item))
            except Exception as e:
                print(f"Erro ao deletar {item}: {e}")
    return True


def main():
    logging.info("🔌 Conectando ao dispositivo Android via ADB (100% XML + segundo plano)...")
    if not garantir_conexao_adb(timeout=120):
        logging.error("❌ Não foi possível conectar ao BlueStacks via ADB.")
        return

    abrir_app_android()

    try:
        rag_sorteios = SorteioRAG(caminho_base=RAG_DIR)
        avancadas = rag_sorteios.memoria.get("metricas_avancadas", {})
        if rag_sorteios.memoria.get("objetos_sorteio") and "tendencias" not in avancadas:
            rag_sorteios._recalcular_e_salvar()
    except Exception as e:
        logging.error(f"Falha ao iniciar motor RAG local: {e}")
        return

    robo = AutomacaoADB(rag_sorteios)
    logging.info("🚀 Motor de Automação XML pronto e aguardando comando do Dashboard...")

    while True:
        config = robo.carregar_config_dashboard()
        if config is None:
            sleep(1)
            continue

        if config.get("status") == "PROCESSANDO":
            logging.info("⚡ Comando de início detectado pelo Dashboard!")

            if robo.realizar_login() and robo.entrar_area_compra():
                robo.iniciar_por_dashboard()
                logging.info("✅ Missão concluída!")

            config["status"] = "CONCLUIDO"
            config["progresso"] = 100
            config["msg_status"] = "Concluído"
            with open(os.path.join(DB_DIR, "config_automacao.json"), "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)
            break

        sleep(3)


if __name__ == "__main__":
    main()
