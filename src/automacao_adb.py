import logging
from logging.handlers import RotatingFileHandler
import os
from datetime import datetime
from time import sleep, time

from adb_manipulation import (
    abrir_app_android,
    capturar_cartela_android,
    clicar_atualizar_cartela,
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
from image_read import extrair_cartela_ocr_1440
from config import (
    ADB_DEVICE,
    ARVORE_DECISAO,
    DB_DIR,
    RAG_DIR,
    SS_DIR,
    get_login_credenciais,
)
from database import (
    atualizar_estado_robo,
    limpar_aprovacao_pendente,
    obter_aprovacao_pendente,
    obter_estado_robo,
    registrar_decisao,
    registrar_limite_espera,
    salvar_aprovacao_pendente,
)
from db.rag import SorteioRAG
from telegram_bot import TelegramBot

LOG_FILE = os.path.join(DB_DIR, "robo.log")
os.makedirs(DB_DIR, exist_ok=True)
_handlers = [
    logging.StreamHandler(),
    RotatingFileHandler(LOG_FILE, maxBytes=1_500_000, backupCount=2, encoding="utf-8"),
]
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", handlers=_handlers)


class AutomacaoADB:
    def __init__(self, rag_sorteios: SorteioRAG):
        self.target_device = ADB_DEVICE
        self.rag = rag_sorteios
        self.telegram = TelegramBot()
        self.config_ia = ARVORE_DECISAO["CARRINHO"]["PAGAMENTO"]["fluxo"][3]["fluxo"][1]["escolher_numeros_titulo"]["config"]

    def reportar_estado(self, percentual: int, mensagem: str) -> None:
        """Atualiza o estado do robô no SQLite para o Dashboard mostrar o progresso."""
        try:
            atualizar_estado_robo(progresso=percentual, msg_status=mensagem)
            logging.info(f"📊 Progresso: {percentual}% - {mensagem}")
        except Exception as e:
            logging.error(f"Erro ao reportar estado: {e}")

    def carregar_config_dashboard(self):
        return obter_estado_robo()

    def carregar_credenciais(self) -> tuple[str, str]:
        try:
            return get_login_credenciais()
        except Exception as e:
            logging.error(f"❌ Erro ao carregar credenciais: {e}")
            return "", ""

    def garantir_tela_inicial(self) -> str:
        """
        Verifica em qual tela o app está: 'CARTELA', 'CARRINHO' (Quero 1/2/4) ou 'HOME'.
        Se estiver em outra tela intermediária, tenta voltar para a Home.
        """
        for tentativa in range(5):
            tree = dump_ui_xml()
            if existe_texto_na_tela(["Escolher o titulo", "Confirmar e finalizar"], tree=tree, contem=True):
                logging.info("🎴 App já está aberto na tela da cartela! Indo direto para análise...")
                return "CARTELA"
            if existe_texto_na_tela(["Quero 1", "Quero 2", "Outra quantidade"], tree=tree, contem=True):
                logging.info("🛒 App está na tela de seleção de quantidade (Carrinho).")
                return "CARRINHO"
            if existe_texto_na_tela(["Seu saldo", "Olá ", "Acessar conta", "Participe e Concorra"], tree=tree, contem=True):
                return "HOME"
            if clicar_por_texto("Home", timeout=2, contem=False, delay_pos=1.5):
                continue
            logging.info(f"↩️ App fora da Home (tentativa {tentativa + 1}/5). Fechando modal / voltando...")
            if not clicar_por_texto("Fechar", timeout=2, contem=False, delay_pos=1.5):
                from adb_manipulation import _run_adb
                _run_adb(["shell", "input", "keyevent", "4"])
                sleep(1.5)
        return "HOME"

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

        # 1. Expande 'Número do titulo' SOMENTE se ainda estiver recolhido ('Ver mais' ativo e 'Ver menos' / títulos ausentes)
        tree_atual = dump_ui_xml()
        ja_expandido = existe_texto_na_tela(
            ["Ver menos", "titulo para escolher", "Escolher número"],
            tree=tree_atual,
            contem=True,
        )
        if not ja_expandido:
            no_num = self._rolar_modal_ate_visivel("Número do titulo", contem=True)
            if no_num is None:
                logging.error("❌ Seção 'Número do titulo' não encontrada no modal.")
                return False

            tree_atual = dump_ui_xml()
            if (
                existe_texto_na_tela("Ver mais", tree=tree_atual, contem=False)
                and not existe_texto_na_tela(["Ver menos", "titulo para escolher"], tree=tree_atual, contem=True)
            ):
                logging.info("🔽 Expandindo dropdown 'Número do titulo' (Ver mais)...")
                _, _, _, _, cx, cy = parse_bounds(no_num.attrib["bounds"])
                tap_adb(cx, cy, random_offset=5)
                sleep(2.0)
        else:
            logging.info("ℹ️ Dropdown 'Número do titulo' já está aberto — mantendo expandido.")

        # 2. Abre o grupo do produto ('Vale Cap, X titulo para escolher') SOMENTE se 'Escolher número' ainda não estiver visível
        tree_atual = dump_ui_xml()
        if not existe_texto_na_tela("Escolher número", tree=tree_atual, contem=True):
            alvo_produto = "titulo para escolher"
            no_prod = self._rolar_modal_ate_visivel(alvo_produto, contem=True)
            if no_prod is None:
                logging.error("❌ Opção 'titulo para escolher' não encontrada.")
                return False

            _, _, _, _, cx, cy = parse_bounds(no_prod.attrib["bounds"])
            tap_adb(cx, cy, random_offset=5)
            sleep(2.0)
        else:
            logging.info("ℹ️ Grupo do título já está expandido ('Escolher número' visível).")

        # 3. Percorre os títulos (1..qtd_total) clicando em 'Escolher número'
        for i in range(1, qtd_total + 1):
            self.reportar_estado(75, f"Abrindo seleção do título {i} de {qtd_total}...")
            abriu_cartela = False
            for tentativa_abrir in range(3):
                # Se a 1ª tentativa não abriu (modal travado/expirado), fecha e reabre o modal pelo botão Continuar
                if tentativa_abrir == 1:
                    logging.warning("🔄 Modal 'Complete seu pedido' não respondeu. Fechando e reabrindo via 'Continuar'...")
                    clicar_por_texto("Fechar", timeout=3, contem=False, delay_pos=1.5)
                    clicar_por_texto("Continuar", timeout=5, contem=False, delay_pos=2.5)

                # Garante que 'Ver mais' e 'titulo para escolher' estejam expandidos antes de procurar 'Escolher número'
                tree_check = dump_ui_xml()
                if existe_texto_na_tela("Ver mais", tree=tree_check, contem=False) and not existe_texto_na_tela("Escolher número", tree=tree_check, contem=True):
                    no_vm = encontrar_no_xml(tree_check, "Ver mais", contem=False)
                    if no_vm is not None:
                        _, _, _, _, vx, vy = parse_bounds(no_vm.attrib["bounds"])
                        tap_adb(vx, vy, random_offset=0)
                        sleep(2.0)
                        tree_check = dump_ui_xml()

                if existe_texto_na_tela("titulo para escolher", tree=tree_check, contem=True) and not existe_texto_na_tela("Escolher número", tree=tree_check, contem=True):
                    no_tp = encontrar_no_xml(tree_check, "titulo para escolher", contem=True)
                    if no_tp is not None:
                        _, _, _, _, tx, ty = parse_bounds(no_tp.attrib["bounds"])
                        tap_adb(tx, ty, random_offset=0)
                        sleep(2.0)

                no_escolher = self._rolar_modal_ate_visivel("Escolher número", contem=True)
                if no_escolher is None:
                    logging.error(f"❌ Botão 'Escolher número' não encontrado para o título {i}.")
                    return False

                _, _, _, _, cx, cy = parse_bounds(no_escolher.attrib["bounds"])
                if tentativa_abrir == 2:
                    cx = 720
                logging.info(f"🖱️ Clicando em 'Escolher número' ({cx}, {cy}) [tentativa {tentativa_abrir + 1}/3]...")
                tap_adb(cx, cy, random_offset=0)

                # Aguarda confirmar que a tela da cartela realmente abriu
                # (ou saiu de 'Complete seu pedido' exibindo o overlay da mãozinha)
                for _ in range(5):
                    sleep(1.5)
                    tree_pos = dump_ui_xml(tentativas=1)
                    if existe_texto_na_tela(["Escolher o titulo", "Confirmar e finalizar"], tree=tree_pos, contem=True):
                        abriu_cartela = True
                        break
                    if tree_pos is not None and not existe_texto_na_tela("Complete seu pedido", tree=tree_pos, contem=True):
                        # Saiu do modal 'Complete seu pedido' -> provavelmente abriu a cartela com o overlay da mãozinha
                        tap_adb(720, 1600, random_offset=5)
                        sleep(1.0)
                        tree_pos2 = dump_ui_xml(tentativas=1)
                        if existe_texto_na_tela(["Escolher o titulo", "Confirmar e finalizar"], tree=tree_pos2, contem=True):
                            abriu_cartela = True
                            break
                        # Mesmo se o overlay ainda estiver fechando, já saiu de 'Complete seu pedido'
                        abriu_cartela = True
                        break
                if abriu_cartela:
                    break

            if not abriu_cartela:
                logging.error(f"❌ Não foi possível abrir a tela da cartela para o título {i}.")
                return False

            aprovado = self.processar_ciclo_ia(titulo_idx=i, qtd_total=qtd_total)
            if aprovado == "REINICIAR_FLUXO":
                return "REINICIAR_FLUXO"
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

    def _tratar_avisos_xml(self, tree, cartelas_ate_aviso: int) -> str | bool:
        """
        Detecta pop-ups de limite/espera no XML, fecha o aviso e retorna 'REINICIAR_FLUXO'
        para que o robô volte para a Home e aguarde o cooldown (900s) antes de recomeçar.
        """
        if not existe_texto_na_tela(["limite", "muitas pessoas", "aguarde", "imprevisto"], tree=tree, contem=True):
            return False

        texto_aviso = self._extrair_texto_aviso(tree)
        inicio_ts = datetime.now()
        delay_espera = int(self.config_ia.get("delay_bloqueio", 900))

        logging.warning(
            f"⏳ AVISO DE ESPERA após {cartelas_ate_aviso} cartelas! "
            f"Texto: '{texto_aviso}' | Fechando aviso e retornando para a Home..."
        )
        self.reportar_estado(
            80,
            f"⏳ Aviso após {cartelas_ate_aviso} cartelas ({texto_aviso}). Voltando para a Home...",
        )
        self.telegram.enviar_mensagem(
            f"⏳ <b>Aviso de espera detectado</b> após <b>{cartelas_ate_aviso} cartelas</b>.\n"
            f"Mensagem: <i>{texto_aviso}</i>\nVoltando para a Home e aguardando <b>{delay_espera}s</b>..."
        )

        clicar_por_texto(["Entendi", "OK", "Fechar"], timeout=5, contem=True, delay_pos=1.5)
        salvar_log_limite_espera(
            timestamp_aviso=inicio_ts.strftime("%Y-%m-%d %H:%M:%S"),
            cartelas_ate_aviso=cartelas_ate_aviso,
            tempo_espera_s=delay_espera,
            texto_aviso=texto_aviso,
        )
        return "REINICIAR_FLUXO"

    def processar_ciclo_ia(self, titulo_idx: int = 1, qtd_total: int = 1) -> bool:
        """Lê cartelas via XML, avalia com Monte Carlo RAG e troca por swipe até aprovar."""
        limite_tentativas = int(self.config_ia.get("limite_tentativas", 200))
        tentativas = 0
        cartelas_ate_aviso = 0
        falhas_seguidas = 0
        repeticoes_seguidas = 0
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

            # Se por algum motivo voltou para 'Complete seu pedido' sem aviso, aborta o ciclo para reabrir direito
            if existe_texto_na_tela("Complete seu pedido", tree=tree, contem=True):
                logging.warning("⚠️ Tela voltou para 'Complete seu pedido'. Reiniciando fluxo de seleção...")
                return "REINICIAR_FLUXO"

            aviso_res = self._tratar_avisos_xml(tree, cartelas_ate_aviso)
            if aviso_res == "REINICIAR_FLUXO":
                return "REINICIAR_FLUXO"
            if aviso_res:
                cartelas_ate_aviso = 0
                repeticoes_seguidas = 0
                continue

            dados_cartela = extrair_cartela_xml(tree)

            # Se o XML veio parcial, mostra quais dezenas leu e tenta mais 2x (2.0s e 1.5s) antes do OCR
            if dados_cartela.get("status") != "sucesso":
                logging.info(
                    f"ℹ️ XML parcial ({len(dados_cartela['dezenas'])} dezenas: {dados_cartela['dezenas']}). "
                    f"Tocando na tela e aguardando 2s para 2ª leitura XML..."
                )
                tap_adb(720, 1600, random_offset=10)
                sleep(2.0)
                tree_retry = dump_ui_xml()
                if tree_retry is not None:
                    if self._tratar_avisos_xml(tree_retry, cartelas_ate_aviso):
                        cartelas_ate_aviso = 0
                        repeticoes_seguidas = 0
                        continue
                    dados_cartela = extrair_cartela_xml(tree_retry)

            if dados_cartela.get("status") != "sucesso":
                logging.info(
                    f"ℹ️ 2ª leitura XML parcial ({len(dados_cartela['dezenas'])} dezenas: {dados_cartela['dezenas']}). "
                    f"Aguardando 1.5s para 3ª leitura XML..."
                )
                sleep(1.5)
                tree_retry2 = dump_ui_xml()
                if tree_retry2 is not None:
                    if self._tratar_avisos_xml(tree_retry2, cartelas_ate_aviso):
                        cartelas_ate_aviso = 0
                        repeticoes_seguidas = 0
                        continue
                    dados_cartela = extrair_cartela_xml(tree_retry2)

            # Se ainda assim o XML falhar, usa screencap + OCR 1440x2560 como fallback
            if dados_cartela.get("status") != "sucesso":
                logging.info(
                    f"ℹ️ 3ª leitura XML parcial ({len(dados_cartela['dezenas'])} dezenas: {dados_cartela['dezenas']}). "
                    f"Recorrendo a screencap + OCR..."
                )
                caminho_ss = capturar_cartela_android()
                dados_ocr = extrair_cartela_ocr_1440(caminho_ss)
                if dados_ocr.get("status") == "sucesso":
                    dados_cartela = dados_ocr
                else:
                    falhas_seguidas += 1
                    logging.warning(
                        f"⚠️ Leitura incompleta (XML={dados_cartela.get('dezenas')}, "
                        f"OCR título={dados_ocr.get('titulo')}, OCR dezenas={dados_ocr.get('dezenas')}). Tocando na tela..."
                    )
                    tap_adb(720, 1600, random_offset=10)
                    if falhas_seguidas > 5:
                        logging.error("❌ Múltiplas falhas consecutivas na leitura da cartela.")
                        return False
                    sleep(1.5)
                    continue

            falhas_seguidas = 0

            # Evita reavaliar/regravar a mesma cartela se o botão atualizar ainda estiver carregando ou overlay bloqueou
            if ultimo_titulo is not None and dados_cartela["titulo"] == ultimo_titulo:
                repeticoes_seguidas += 1
                logging.warning(
                    f"🔁 Cartela {ultimo_titulo} repetiu ({repeticoes_seguidas}x). "
                    f"Dispensando mãozinha e clicando em ↻..."
                )
                tap_adb(720, 1600, random_offset=10)
                sleep(0.5)
                if repeticoes_seguidas % 3 == 0:
                    swipe_adb(1300, 990, 140, 990, 600)
                else:
                    clicar_atualizar_cartela(tree)
                sleep(2.5)

                if repeticoes_seguidas >= 6:
                    logging.warning(
                        f"⏸️ Cartela {ultimo_titulo} não troca após {cartelas_ate_aviso} cartelas "
                        f"(possível limite silencioso). Aguardando 30s antes de tentar novamente..."
                    )
                    self.reportar_estado(
                        80,
                        f"⏸️ Travado na cartela {ultimo_titulo} após {cartelas_ate_aviso} cartelas. Aguardando 30s...",
                    )
                    sleep(30)
                    repeticoes_seguidas = 0
                continue

            repeticoes_seguidas = 0
            cartelas_ate_aviso += 1
            ultimo_titulo = dados_cartela["titulo"]

            self.reportar_estado(
                85,
                f"Analisando cartela #{cartelas_ate_aviso} ({ultimo_titulo}) - Título {titulo_idx}/{qtd_total}...",
            )
            logging.info(f"🎴 Cartela #{cartelas_ate_aviso} XML: Título={ultimo_titulo} | Dezenas={dados_cartela['dezenas']}")

            decisao = self.gerir_decisao_cartela(dados_cartela)

            if decisao == "COMPRAR":
                logging.info("🔥 CARTELA APROVADA! Dispensando mãozinha e confirmando título via XML...")
                confirmou = False
                for tent_conf in range(3):
                    tap_adb(720, 1600, random_offset=5)
                    sleep(1.0)
                    if clicar_por_texto(
                        ["Confirmar e escolher próximo", "Confirmar e finalizar", "Confirmar"],
                        timeout=6,
                        contem=True,
                        delay_pos=2.5,
                    ):
                        tree_pos = dump_ui_xml(tentativas=1)
                        if existe_texto_na_tela(["imprevisto", "não conseguimos processar"], tree=tree_pos, contem=True):
                            logging.warning("⚠️ Aviso 'Tivemos um imprevisto' ao confirmar título. Fechando e reiniciando fluxo...")
                            clicar_por_texto(["Entendi", "OK"], timeout=4, contem=True, delay_pos=1.5)
                            return "REINICIAR_FLUXO"
                        confirmou = True
                        break
                    logging.warning(f"⚠️ Botão 'Confirmar' não apareceu (tentativa {tent_conf + 1}/3). Repetindo limpeza...")
                return confirmou

            # Toca antes para limpar a mãozinha, aguarda 1.5s, faz o duplo clique em ↻ (0.5s entre cliques) e aguarda 1.5s
            logging.info(f"👎 Cartela #{cartelas_ate_aviso} ({ultimo_titulo}) descartada. Limpando tela e clicando em ↻...")
            tap_adb(720, 1600, random_offset=10)
            sleep(1.5)
            clicar_atualizar_cartela(tree)
            tentativas += 1
            sleep(1.5)

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
            cfg_dash = self.carregar_config_dashboard() or {}
            media_corte = float(cfg_dash.get("media_corte", self.config_ia.get("media_corte", 57.80)))

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

            while True:
                sleep(1.5)
                # 1. Verifica decisão pelo Telegram (celular)
                decisao_tg = self.telegram.verificar_decisao(titulo)
                if decisao_tg in ("ACEITO", "DESISTIDO"):
                    limpar_aprovacao_pendente()
                    if decisao_tg == "ACEITO":
                        salvar_log_decisao(titulo, dezenas, stats, "Comprado_Telegram")
                        return "COMPRAR"
                    salvar_log_decisao(titulo, dezenas, stats, "Desistido_Telegram")
                    return "PROXIMA"

                # 2. Verifica decisão pelo Dashboard Streamlit (via SQLite)
                dados = obter_aprovacao_pendente()
                if dados:
                    if dados.get("status") == "ACEITO":
                        salvar_log_decisao(titulo, dezenas, stats, "Comprado")
                        limpar_aprovacao_pendente()
                        self.telegram.enviar_mensagem(f"✅ Título <code>{titulo}</code> aprovado pelo Dashboard!")
                        return "COMPRAR"
                    if dados.get("status") == "DESISTIDO":
                        salvar_log_decisao(titulo, dezenas, stats, "Desistido_Usuario")
                        limpar_aprovacao_pendente()
                        self.telegram.enviar_mensagem(f"❌ Título <code>{titulo}</code> descartado pelo Dashboard.")
                        return "PROXIMA"

        except Exception as e:
            logging.error(f"❌ Erro crítico na análise da cartela: {e}")
            return "PROXIMA"

    def comunicar_dashboard(self, dados_cartela: dict, stats: dict) -> None:
        salvar_aprovacao_pendente(
            dados_cartela.get("titulo", "desconhecido"),
            dados_cartela.get("dezenas", []),
            stats,
        )


def salvar_log_limite_espera(timestamp_aviso: str, cartelas_ate_aviso: int, tempo_espera_s: int, texto_aviso: str):
    """Registra no SQLite quantas cartelas foram lidas até o aviso de espera e quanto tempo levou."""
    registrar_limite_espera(timestamp_aviso, cartelas_ate_aviso, tempo_espera_s, texto_aviso)


def salvar_log_decisao(id_ref, dezenas, scores, decisao):
    """Registra a decisão da cartela no SQLite."""
    registrar_decisao(
        id_ref,
        dezenas,
        scores.get("pure_score", 0.0),
        scores.get("weighted_score", 0.0),
        decisao,
    )


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

            while True:
                cfg_loop = robo.carregar_config_dashboard()
                if not cfg_loop or cfg_loop.get("status") != "PROCESSANDO":
                    logging.info("🛑 Execução interrompida pelo usuário.")
                    break

                tela = robo.garantir_tela_inicial()
                if tela == "CARTELA":
                    qtd = int(cfg_loop.get("quantidade", 1))
                    resultado = robo.processar_ciclo_ia(titulo_idx=1, qtd_total=qtd)
                elif tela == "CARRINHO":
                    resultado = robo.iniciar_por_dashboard()
                else:
                    if robo.realizar_login() and robo.entrar_area_compra():
                        resultado = robo.iniciar_por_dashboard()
                    else:
                        resultado = False

                if resultado == "REINICIAR_FLUXO":
                    logging.info("🔄 Retornando para a tela inicial (Home) antes da espera de 900s...")
                    for _ in range(5):
                        tree_home = dump_ui_xml()
                        if existe_texto_na_tela(["Participe e Concorra", "Acessar conta"], tree=tree_home, contem=True):
                            break
                        if not clicar_por_texto("Fechar", timeout=2, contem=False, delay_pos=1.2):
                            if not clicar_por_texto("Home", timeout=2, contem=False, delay_pos=1.5):
                                from adb_manipulation import _run_adb
                                _run_adb(["shell", "input", "keyevent", "4"])
                                sleep(1.5)

                    delay_espera = int(robo.config_ia.get("delay_bloqueio", 900))
                    t_esp = time()
                    logging.info(f"⏳ Na tela inicial. Aguardando {delay_espera}s ({delay_espera // 60} min) antes de iniciar nova busca...")
                    while True:
                        decorrido = int(time() - t_esp)
                        if decorrido >= delay_espera:
                            break
                        cfg_esp = robo.carregar_config_dashboard()
                        if not cfg_esp or cfg_esp.get("status") != "PROCESSANDO":
                            logging.info("🛑 Busca encerrada pelo usuário durante a espera na Home.")
                            break
                        restante = delay_espera - decorrido
                        robo.reportar_estado(80, f"⏳ Na Home aguardando liberação: {restante}s de {delay_espera}s...")
                        sleep(min(15, restante))

                    cfg_pos = robo.carregar_config_dashboard()
                    if not cfg_pos or cfg_pos.get("status") != "PROCESSANDO":
                        break
                    robo.telegram.enviar_mensagem(f"🔄 <b>900s concluídos na Home!</b> Reiniciando busca...")
                    continue

                logging.info("✅ Missão concluída!")
                break

            atualizar_estado_robo(status="CONCLUIDO", progresso=100, msg_status="Concluído")
            break

        sleep(3)


if __name__ == "__main__":
    main()
