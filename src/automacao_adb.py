from calendar import c
from pydoc import cli
from tkinter import N
from typing import Any
from numpy import empty
import pyautogui
from time import sleep, time
import os
from datetime import datetime
import image_read
from config import PROJECT_ROOT, SRC_DIR, SS_DIR, DB_DIR, ARVORE_DECISAO, MOLDES_DIR
import json
import pandas as pd
import logging
from adb_manipulation import match_template_adb, clicar_adb, capturar_cartela_android
import gerenciadorjanelas as gj
import subprocess
import shutil
import matplotlib.pyplot as plt
import numpy as np

from src import automacao


gerenciador = gj.GerenciadorJanelas()
#sleep de 1 min e verificar login
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class AutomacaoADB:
    def __init__(self, agente_instanciado):
        self.path_ss = os.path.join(SS_DIR, "print.PNG")
        #self.target_device = "127.0.0.1:5555"
        self.target_device = "emulator-5554"
        self.agente = agente_instanciado

    def executar_passo(self, dados_passo, timeout=10, treshold=0.8) -> bool:
        """
        Tenta encontrar e clicar em um elemento da árvore de decisão.
        dados_passo: dicionário contendo 'moldes' e 'acao'
        """
        inicio = time()
        moldes = dados_passo.get("moldes", [])
        nome_passo = dados_passo.get("nome", "Passo desconhecido")

        logging.info(f"Executando o passo: {nome_passo},\n molde: {moldes}")

        while time() - inicio < timeout:
            #capturar_cartela_android() # Atualiza o print
            for molde in moldes:
                molde_path = os.path.join(MOLDES_DIR, f"{molde}") # Ajuste o caminho da sua pasta de moldes
                sucesso, x, y, w, h = match_template_adb(molde_path, self.path_ss, threshold=treshold)

                print(f"Tentando encontrar {molde}... Sucesso: {sucesso}")
                print(f"Coordenadas: x={x}, y={y}, w={w}, h={h}")
                
                if sucesso:
                    logging.info(f"✅ Elemento encontrado: {molde}")
                    if dados_passo.get("acao") == "clicar":
                        sleep(0.5)
                        status=clicar_adb(x, y, w, h, random_offset=5)
                        print("")
                        print("-"*50)
                        print("")
                        logging.info(f"O resultado do clique em {molde} foi: {status}")
                        print("")
                        print("-"*50)
                    return True
            
            sleep(1) # Espera 1 segundo antes de tentar novamente (evita uso excessivo de CPU)
        
        logging.warning(f"❌ Timeout: Não foi possível encontrar {nome_passo}")
        return False

    def realizar_login(self):
        self.reportar_estado(10, "A verificar login...")
        logging.info("🔐 Iniciando processo de login via Árvore de Decisão...")
        config_login = ARVORE_DECISAO["HOME"]["login"]
        try: 
            for m in config_login["ancora"]:
                resp = match_template_adb(os.path.join(MOLDES_DIR, m), self.path_ss)
                print(f"Retorno da comparação de {m} foi : {resp[0]}")
                if resp[0] and m == "login_ok.PNG":
                    logging.info("✅ Usuário já logado.")
                    self.reportar_estado(30, "Aceder à área de compra...")
                    return True
                
                elif resp[0] and m=="acessar_conta.PNG": 
                    # 2. Executa passos de preenchimento
                    logging.info("❌ Usuário não logado.") 
                    self.reportar_estado(30, "Aceder à área de login...")
                    logging.info(f"Carregando os passos:\n {config_login["passos"]}")

                    for passo in config_login["passos"]:
                        logging.info(f"\ncarregando o passo: {passo["nome"]}\n passo: {passo["acao"]}")
                        if passo["acao"] == "preencher":
                            cpf, senha = self.carregar_credenciais()
                            # Aqui você chamaria uma função de input de texto ADB
                            for m in passo["moldes"] :
                                print(f"valor de m: {m}")
                                resp = match_template_adb(os.path.join(MOLDES_DIR,m ), self.path_ss)
                                clicar_adb(resp[1],resp[2],resp[3],resp[4])
                                self.escrever_adb(passo['nome'], cpf if passo['nome'] == 'campo_cpf' else senha)
                                self.reportar_estado(30, "Aceder à área de compra...")
                            
                        else:
                            self.executar_passo(passo)
                            self.reportar_estado(30, "Aceder à área de compra...")
                    resp_btn_ativo = True

                    while resp_btn_ativo == True:   
                        nome, molde = config_login["passos"][3], config_login["passos"][3].get("moldes")
                        resp_btn_ativo=self.garantir_botao_ativo(nome,molde[0])
                        sleep(1)
                    return True
        except Exception as e:
                logging.error(f"Erro ao realizar loggin: {e}")
                print("")
                print("-------------------------------------------------------")


    def reportar_estado(self, percentual, mensagem):
            """Atualiza o JSON para o Dashboard mostrar o progresso"""
            caminho_config = os.path.join(DB_DIR, "config_automacao.json")
            # Primeiro, carregamos o que já está lá para não apagar o resto das configs
            config_atual = self.carregar_config_dashboard() or {}
            try:
                if os.path.exists(caminho_config):
                    path_temp = caminho_config + ".tmp"
                    config_atual["progresso"] = percentual
                    config_atual["msg_status"] = mensagem
                    with open(path_temp, "w", encoding='utf-8') as f:
                        json.dump(config_atual, f, indent=4)

                    os.replace(path_temp, caminho_config)
                  
                logging.info(f"📊 Progresso: {percentual}% - {mensagem}")
                print("")
                print("-------------------------------------------------------")
            except Exception as e:
                logging.error(f"Erro ao reportar estado: {e}")
                print("")
                print("-------------------------------------------------------")

    def carregar_credenciais(self):
        caminho = os.path.join("src", "login.txt")
        try:
            with open(caminho, "r") as f:
                linhas = [l.strip() for l in f.readlines() if l.strip()]
                if len(linhas) >= 2:
                    return linhas[0], linhas[1]
                logging.error("❌ Arquivo de login deve ter pelo menos 2 linhas (CPF e Senha).")
                print("")
                print("-------------------------------------------------------")
        except FileNotFoundError:
            logging.error(f"❌ Arquivo {caminho} não encontrado.")
            print("")
            print("-------------------------------------------------------")
        return "00000000000", "senha_padrao" # Valores de fallback
        
    def escrever_adb(self, nome_campo, texto):
        """Envia texto para o campo focado via ADB"""
        logging.info(f"🖊️ Preenchendo {nome_campo}...")
        print("")
        print("-------------------------------------------------------")
        # Primeiro, clicamos no campo para garantir o foco (opcional, dependendo do seu fluxo)
        # O comando abaixo envia o texto diretamente
        cmd = f"HD-Adb.exe -s {self.target_device} shell input text {texto}"
        subprocess.run(cmd, shell=True, capture_output=True)
        sleep(1) # Delay para o sistema processar a entrada

    def carregar_config_dashboard(self):
        path_original = os.path.join(DB_DIR, "config_automacao.json")
        path_copia_trabalho = os.path.join(DB_DIR, "config_robo_copy.json")

        if not os.path.exists(path_original):
            return None

        try:
            # 1. Faz uma cópia física do arquivo original para um novo nome
            # O copy2 é extremamente rápido e não bloqueia o original por muito tempo
            shutil.copy2(path_original, path_copia_trabalho)
            sleep(0.5)
            # 2. Agora o robô lê a CÓPIA dele, sem incomodar o Streamlit
            if os.path.getsize(path_copia_trabalho) > 0:
                with open(path_copia_trabalho, "r", encoding='utf-8') as f:
                    return json.load(f)
        except (json.JSONDecodeError, PermissionError, OSError):
            # Se mesmo a cópia falhar (ex: o original estava sendo escrito no microssegundo da cópia)
            return None
        return None
    
    def iniciar_por_dashboard(self ):
        """Orquestra o início baseado na escolha do usuário"""
        path_config = os.path.join(DB_DIR, "config_automacao.json")
        config = self.carregar_config_dashboard()
        peso_config = os.path.getsize(path_config)
        
        if not config or peso_config == 0:
            logging.warning("⚠️ Nenhuma configuração encontrada no Dashboard. Usando padrão.")
            print("")
            print("-------------------------------------------------------")    
            return False

        tipo = config["tipo"]
        qtd = config["quantidade"]
        
        # Mapeia a quantidade para o índice do molde (0, 1, 2)
        # ValeCap: 1(idx 0), 2(idx 1), 4(idx 2)
        # HiperCap: 2(idx 0), 5(idx 1), 10(idx 2)
        mapa_indices = {
            "valecap": {1: 0, 2: 1, 4: 2},
            "hipercap": {2: 0, 5: 1, 10: 2}
        }
        
        idx_molde = mapa_indices[tipo].get(qtd, 0)
        
        logging.info(f"🎯 Iniciando missão: {tipo} com {qtd} títulos (Índice Molde: {idx_molde})")
        print("")
        print("-------------------------------------------------------")
        
        # Agora executa os passos usando esses dados
        if self.selecionar_quantidade(tipo, idx_molde):
            return self.analisar_e_escolher_titulo(config)
        
        return False


    def analisar_e_escolher_titulo(self, config_dashboard):
        
        tipo_jogo = config_dashboard.get("tipo")
        qtd_total = config_dashboard.get("quantidade", 1)
        
        logging.info(f"🧐 Iniciando análise para: {tipo_jogo} | Qtd: {qtd_total}")
        print("")
        print("-"*50)
        self.reportar_estado(70, f"Configurando checkout para {tipo_jogo}...")

        # 1. ACIONAR "NÚMERO DO TITULO"
        etapa_n_titulo = ARVORE_DECISAO["CARRINHO"]["PAGAMENTO"]["fluxo"][0]
        self.garantir_botao_ativo(etapa_n_titulo, "escolher_ativo.PNG", threshold=0.95)

        # 2. SELECIONAR PRODUTO
        fluxo_pagamento = ARVORE_DECISAO["CARRINHO"]["PAGAMENTO"]["fluxo"]
        etapa_produto = next((item for item in fluxo_pagamento if item.get("nome") == tipo_jogo), None)
        
        if etapa_produto:
            self.garantir_botao_ativo(etapa_produto, f"titulo_ativo.PNG", threshold=0.95)

        # 3. ENTRAR NA GRADE E PROCESSAR DINAMICAMENTE
        etapa_especifico = ARVORE_DECISAO["CARRINHO"]["PAGAMENTO"]["fluxo"][3]
        
        # Abre a grade de títulos
        if self.executar_passo(etapa_especifico["fluxo"][0]):
            # Chamar a função que lida com a quantidade e o scroll
            return self.processar_titulos_dinamico(config_dashboard, etapa_especifico)

    def percorrer_lista_titulos(self, etapa_especifico):
        """
        Procura pelos títulos de 1 a 10. Se não encontrar o próximo da lista,
        rola a tela para baixo até encontrá-lo.
        """
        # i vai de 1 a 10
        for i in range(1, 11):
            molde_nome = f"titulo{i}_escolher.PNG" # Nome do seu arquivo conforme padrão
            self.reportar_estado(75, f"Procurando Título {i} de 10...")
            
            encontrado = False
            tentativas_scroll = 0
            
            # Tenta encontrar o título atual. Se não achar, dá um scroll e tenta de novo (máx 3 scrolls)
            while not encontrado and tentativas_scroll < 3:
                capturar_cartela_android()
                
                res, x_ini, y_ini, w, h = match_template_adb(os.path.join(MOLDES_DIR, molde_nome), self.path_ss)
                
                if res:
                    logging.info(f"🎯 Título {i} localizado! Clicando em ({x_ini}, {y_ini})")
                    print("")
                    print("-------------------------------------------------------")
                    clicar_adb(x_ini, y_ini, w, h, random_offset=5)
                    encontrado = True
                    
                    # ENTRA NA ANÁLISE DA CARTELA (Sua lógica de IA)
                    fluxo_ia = etapa_especifico["fluxo"][1]["escolher_numeros_titulo"]
                    while True:
                        sucesso_compra = self.processar_ciclo_ia(fluxo_ia)
                        
                        if sucesso_compra:
                             # Para tudo e finaliza a missão
                            fluxo_ia_confirma = etapa_especifico["fluxo"][1]["confirmar_titulo"]
                            self.executar_passo(fluxo_ia_confirma)
                            sleep(1)
                            continue
                            
                        
                        elif sucesso_compra is None:
                            logging.info("Numero de tetativas seguidas atingidos.... aguardando tempo de espera de 5min")
                            sleep(300) 
                            continue
                    # Se não comprou, volta para a lista para procurar o próximo (i + 1)
                   
                else:
                    # Se não achou o título i, provavelmente ele está mais abaixo
                    logging.info(f"📜 Título {i} não visível. Rolando tela para baixo...")
                    print("")
                    print("-"*80)
                    # Coordenadas de swipe: [X_inicial, Y_inicial, X_final, Y_final, duração]
                    # Rola de baixo para cima para a lista descer
                    tentativas_scroll += 1
                    sleep(1) # Espera a lista parar de balançar

        return False

    def processar_titulos_dinamico(self, config_dashboard, etapa_especifico):
        """
        Lógica que se adapta à quantidade escolhida no Dashboard.
        """
        qtd_total = config_dashboard.get("quantidade", 1) # Pega 1 como padrão
        logging.info(f"📋 Iniciando busca para {qtd_total} títulos.")


        for i in range(1, qtd_total + 1):
            molde_nome = f"titulo{i}_escolher.PNG"
            self.reportar_estado(75, f"Analisando {i} de {qtd_total}...")
            # Tenta encontrar o título na tela atual
            sleep(5)
            capturar_cartela_android()
            resultado = match_template_adb(os.path.join(MOLDES_DIR, molde_nome), self.path_ss, threshold=0.60)
            print(resultado)
            if resultado[0]==False:
                logging.info(f"📜 Título {i} não visível. Tentando de novo...")
                
                sleep(3)
                clicar_adb(600, 1600, 200, 100, random_offset=10, centro=True)
                capturar_cartela_android() 
                resultado = match_template_adb(os.path.join(MOLDES_DIR, molde_nome), self.path_ss, threshold=0.60)
                print(resultado)
                print("")
                print("-"*80)
                
            res, x_ini, y_ini, w, h = resultado
    
            # Se não achou e a quantidade for alta, tenta o scroll
            if not res and qtd_total > 5:
                logging.info(f"📜 Título {i} não visível e a lista é longa. Rolando...")
                clicar_adb(600, 1600, 200, 100, random_offset=10, centro=True) #remover a gif da mao
                self.fazer_swipe([700, 1700, 700, 500, 800])
                sleep(5)
                clicar_adb(600, 1600, 200, 100, random_offset=10, centro=True) 
                capturar_cartela_android()
                res, x_ini, y_ini, w, h = match_template_adb(os.path.join(MOLDES_DIR, molde_nome), self.path_ss)

            if res:
                print(f"🎯 Título {i} localizado! Clicando em ({x_ini}, {y_ini})")
                print("")
                print("-------------------------------------------------------")
                clicar_adb(x_ini, y_ini+700, w, h, random_offset=5)
                capturar_cartela_android()
                # Inicia análise de IA da cartela
                fluxo_ia = etapa_especifico["fluxo"][1]["escolher_numeros_titulo"]
                if self.processar_ciclo_ia(fluxo_ia):
                    return True # Compra efetuada
            
            else:

                logging.warning(f"❌ Não foi possível localizar o título {i}")
                print("")
                print("-------------------------------------------------------")
        
        return False
    
    def garantir_botao_ativo(self, etapa, molde_sucesso,threshold=0.85):
        """Verifica se o botão já está no estado ativo. Se não, clica."""
        print("")
        print("----------------------------------------")
        capturar_cartela_android() # Método que atualiza o self.path_ss
        print("Verificando estado do botão...")
        print(f"Caminho do molde de sucesso: {molde_sucesso}")
        print("----------------------------------------")
        valores = match_template_adb(os.path.join(MOLDES_DIR, molde_sucesso), self.path_ss, threshold=threshold)
        print(valores)
        res, _, _, _, _ = valores
        print(f"Verificando botão {etapa['nome']} ativo: {res}")
        
        if res:
            logging.info(f"✅ Botão {etapa['nome']} já está ativo.")
            print("")
            print("-------------------------------------------------------")
            return True
        else:
            logging.info(f"skipping: Botão {etapa['nome']} inativo. Ativando...")
            print("")
            print("-------------------------------------------------------")
            self.executar_passo(etapa)
            sleep(1)
            return False

    def confirmacao_estado(self, etapa, molde_sucesso,threshold=0.85) -> bool:
        """Verifica estatus do molde. Se sim retornar true se nao false."""
        print("")
        print("----------------------------------------")
        capturar_cartela_android() # Método que atualiza o self.path_ss
        print("Verificando estado...")
        print(f"Caminho do molde de sucesso: {molde_sucesso}")
        print("----------------------------------------")
        valores = match_template_adb(os.path.join(MOLDES_DIR, molde_sucesso), self.path_ss, threshold=threshold)
        print(valores)
        res, _, _, _, _ = valores
        print(f"Localizando imagem {etapa['nome']} status: {res}")
        
        if res:
            logging.info(f"✅ Botão {etapa['nome']} já está encontrado.")
            print("")
            print("-------------------------------------------------------")
            return True
        else:
            logging.info(f"Imagem {etapa['nome']} não encontrada.")
            print("")
            print("-------------------------------------------------------")
            return False


    def processar_ciclo_ia(self, etapa_config):
        conf = etapa_config["config"]
        etapa_selecao_cartela = ARVORE_DECISAO["CARRINHO"]["PAGAMENTO"]["fluxo"][3]["fluxo"][1]['escolher_numeros_titulo']
        etapa_aviso = ARVORE_DECISAO["CARRINHO"]["PAGAMENTO"]["fluxo"][3]["fluxo"][1]["tela_aviso"]
        etapa_entendi = ARVORE_DECISAO["CARRINHO"]["PAGAMENTO"]["fluxo"][3]["fluxo"][1]["tela_aviso_entendi"]
        print(etapa_selecao_cartela)
        tentativas = 0
        print("")
        print("")
        print("Iniciando ciclo de análise IA para a cartela...")
        print("Configurações:")
        print(f" - Limite de Tentativas: {conf['limite_tentativas']}")
        print(f" - Delay em caso de bloqueio: {conf['delay_bloqueio']}s")  
        print("Analisando cartelas...")
        print("Usando OCR + Agente DeepSeek/RAG para decisão...")
        print("----------------------------------------")
        print("")
        print("")
        clicar_adb(600, 1600, 200, 100, random_offset=10, centro=True) # Clica em ESCOLHER NÚMERO DO TÍTULO
        falhas_leitura_seguidas = 0
        while tentativas < conf["limite_tentativas"]:
            capturar_cartela_android()
            print("Verificando avisos na tela...")
            print(f"etapa_aviso.get('molde'): {etapa_aviso.get('molde')}")
            print(" ----------------------------------------")
            if self.confirmacao_estado(etapa_selecao_cartela, "atualizando_cartela.PNG", threshold=0.90):
                sleep(1)
                logging.info("⏳ Cartela atualizando. Aguardando...")
                print("")
                print("-------------------------------------------------------")
                clicar_adb(600, 1600, 200, 100, random_offset=10, centro=True)
                sleep(10)
                clicar_adb(800, 1600, 200, 100, random_offset=10, centro=True)
            # 1. Verificação de Bloqueio/Aviso (Aviso de carregar títulos)
            
            elif any(self.detectar_aviso(m) for m in etapa_aviso.get("moldes")) :
                for m in etapa_aviso.get("moldes"):
                    if m in "limite_de_escolha.PNG":
                        self.executar_passo(etapa_entendi)
                        sleep(conf['delay_bloqueio'])

                    elif m in "aviso_muitas_pessoas.PNG":
                        self.executar_passo(etapa_entendi)
                        sleep(conf['delay_bloqueio'])

                    _resp,_,_,_,_ = match_template_adb(os.path.join(MOLDES_DIR,m), self.path_ss)
                    if _resp:
                        logging.warning(f"⏳ Aviso. \n {m.replace(".PNG",'')} \nAguardando {conf['delay_bloqueio']}s")
                    for m in etapa_entendi.get("moldes"):  
                        resp,x,y,w,h = match_template_adb(os.path.join(MOLDES_DIR,m), self.path_ss)
                        if resp:
                            clicar_adb(x,y,w,h)
                print("")
                print("-------------------------------------------------------")
                sleep(conf['delay_bloqueio'])
                continue

            # 2. OCR e IA (Análise da cartela visível)
            self.reportar_estado(85, f"Analisando cartela {tentativas+1}...")
            dados_ocr = image_read.imagem_ajuste(self.path_ss, "cartela_atual.png")
            print("")
            print("Dados OCR da cartela atual:")
            print(dados_ocr)
            print("")

            try:
                if dados_ocr.get('status') == 'sucesso':
                    # Aqui você chama o seu agente DeepSeek/RAG para dar a nota
                    decisao = self.gerir_decisao_cartela(dados_ocr, conf)
                    
                    falhas_leitura_seguidas = 0 # Reseta falhas
                                    
                    if decisao == "COMPRAR":
                        logging.info("🔥 CARTELA ENCONTRADA! Selecionando...")
                        logging.info("aguardando confirmacao do Streamlit...")
                        print("")
                        print("-------------------------------------------------------")
                        # Clica na âncora da cartela para confirmar seleção
                        self.executar_passo(etapa_config) 
                        
                        return True
                
                # 3. Se não for boa, Swipe para a próxima
                elif dados_ocr.get('status') == 'alerta_falha_leitura':
                    logging.warning("⚠️ Falha na leitura possivel cartela vazia...")
                    print("")
                    print("-------------------------------------------------------")
                    falhas_leitura_seguidas +=1
                    if falhas_leitura_seguidas > 5:
                        logging.error("Multiplas falhas de leituras da cartela, encerrando programa...")
                        break

                    continue
                elif len(dados_ocr) == 0:
                    logging.warning("⚠️ Dados OCR vazios. Tentando novamente...") 
                    print("")
                    print("-------------------------------------------------------")
                    continue

            except (AttributeError, Exception) as e:
                logging.error(f"❌ Erro ao processar dados OCR: {e}")
                logging.warning("⚠️ Dados OCR inválidos. Tentando novamente...")
                print("")
                print("-------------------------------------------------------")
                tentativas += 1
                continue

            logging.info(f"👎 Cartela {tentativas+1} abaixo da nota. Próxima...")
            print("")
            print("-------------------------------------------------------")
            self.fazer_swipe(conf["swipe_coords"])
            tentativas += 1
            sleep(1.2) # Delay para animação do app
            
        logging.error("❌ Limite de tentativas atingido sem encontrar cartela boa.")
        print("")
        print("-------------------------------------------------------")
        return None

    def gerir_decisao_cartela(self, dezenas_lidas, config):
        # 1. Calcula a estatística primeiro
        conf = config
        titulo = dezenas_lidas.get('titulo', [])
        dezenas = dezenas_lidas.get('dezenas', [])
        print(f"As dezenas coletadas foram: {dezenas}")
        
        try:
            print("")
            print("-"*50)
            print("")
            logging.info("📊 Calculando probabilidades de Monte Carlo...")
            print("")
            print("-"*50)
            print("")

            if len(dezenas) < 20:
                logging.error("❌ Dezenas insuficientes para análise.")
                return "PROXIMA"
            
            stats = self.agente.testar_rag(titulo, dezenas)

            
            
            media = stats.get('media', 60)
            
            # 2. FILTRO AUTOMÁTICO: Se a média for ruim, nem avisa o dashboard
            if media > 57.6:
                print("")
                print("-"*50)
                print("")
                logging.info(f"🚫 Cartela FRIA ({media:.2f}). Descartando automaticamente...")
                print("")
                print("-"*50)
                print("")
                self.fazer_swipe(conf["swipe_coords"])
                sleep(2)
                return "PROXIMA" 

            
            # 3. Se passou no filtro, envia para o Dashboard e TRAVA para decisão humana
            print("")
            print("-"*50)
            print("")
            logging.info(f"🔥 Cartela BOA encontrada ({media:.2f})! Aguardando decisão no Streamlit...")
            print("")
            print("-"*50)
            print("")
            self.comunicar_dashboard({"titulo": titulo, "dezenas": dezenas}, stats)
            
            # Loop de espera (Bloqueia o robô até você clicar no site)
            while True:
                sleep(2)
                caminho_json = os.path.join(DB_DIR, "comunicacao_app.json")
                if os.path.exists(caminho_json):
                    with open(caminho_json, "r") as f:
                        dados = json.load(f)
                    
                    if dados.get("status") == "ACEITO":
                        return "COMPRAR"
                    if dados.get("status") == "DESISTIDO":
                        # Limpa o JSON para o dashboard saber que acabou
                        os.remove(caminho_json)
                        return "PROXIMA"

        except Exception as e:
            print("")
            print("-"*50)
            print("")
            logging.error(f"❌ Erro crítico na análise: {e}")
            print("")
            print("-"*50)
            print("")
            return "PROXIMA"

    def fazer_swipe(self, coords):
        try:
            clicar_adb(400,1600,50,50,centro=True)

            cmd = f"HD-Adb.exe -s {self.target_device} shell input swipe {str(coords[0])} {str(coords[1])} {str(coords[2])} {str(coords[3])} {str(coords[4])}"
            sleep(0.5)
            subprocess.run(cmd, shell=True, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            logging.error(f"Erro ao executar swipe ADB: {e}")
            print("")
            print("-------------------------------------------------------")

    def detectar_aviso(self, molde):
        return match_template_adb(os.path.join(MOLDES_DIR, molde), self.path_ss)[0]

    def fluxo_pagamento_completo(self):
        """Percorre toda a lista de pagamento definida no config.py"""
        logging.info("🚀 Iniciando fluxo de pagamento...")
        
        fluxo = ARVORE_DECISAO["CARRINHO"]["PAGAMENTO"]["fluxo"]
        
        for etapa in fluxo:
            logging.info(msg=f"🔄 Processando etapa: {etapa['nome']}")
            print("")
            print("-------------------------------------------------------")
            resultado = self.executar_passo(etapa)
            
            if not resultado:
                logging.error(f"🛑 Falha crítica na etapa {etapa['nome']}. Abortando.")
                print("")
                print("-------------------------------------------------------")
                return False
            
            sleep(1.5) # Delay entre cliques para o app processar
            
        logging.info("🏆 Fluxo de pagamento concluído com sucesso!")
        print("")
        print("-------------------------------------------------------")
        return True

    def selecionar_quantidade(self, tipo_cap="valecap", qtd_index=0):
        """
        tipo_cap: 'valecap' ou 'hipercap'
        qtd_index: 0 para a primeira opção, 1 para a segunda, 2 para a terceira
        """
        dados = ARVORE_DECISAO["CARRINHO"]["selecao_quantidade"][tipo_cap]
        
        # Tenta clicar na quantidade desejada
        passo_qtd = {
            "nome": f"Quantidade {tipo_cap}",
            "moldes": [dados["moldes"][qtd_index]],
            "acao": "clicar"
        }
        
        if self.executar_passo(passo_qtd, treshold=0.95):
            # Clica em continuar
            continuar = ARVORE_DECISAO["CARRINHO"]["selecao_quantidade"]["continuar"]
            self.reportar_estado(50, f"Selecionar {tipo_cap}...")
            return self.executar_passo(continuar)
        return False

    def comunicar_dashboard(self, dados_cartela, stats):
        caminho_temp = os.path.join(DB_DIR, "comunicacao_app.json")
        payload = {
            "timestamp": datetime.now().isoformat(),
            "id_cartela": dados_cartela.get("titulo", "desconhecido"),
            "dezenas": dados_cartela.get("dezenas", []),
            "media": stats.get('media'),
            "prob_50": stats.get('prob_50'),
            "prob_55": stats.get('prob_55'),
            "monte_carlo_data": stats.get('monte_carlo_data'), # Essencial para o gráfico!
            "status": "aguardando_aprovacao"
        }
        with open(caminho_temp, 'w') as f:
            json.dump(payload, f)


def abrir_app() -> None:
    pyautogui.click(x=676,y=1060, clicks=1, button='left')
    sleep(40)
 
def salvar_log_decisao(id_ref, dezenas, scores, decisao):
    """Gera o CSV de aprendizado conforme planejado"""
    data_str = datetime.now().strftime("%Y-%m-%d")
    arquivo = os.path.join(DB_DIR, f"{data_str}_log_decisoes.csv")
    
    novo_log = {
        "ID_Cartela": id_ref,
        "Dezenas": str(dezenas),
        "Pure_Score": scores['pure_score'],
        "Weighted_Score": scores['weighted_score'],
        "Decisao": decisao,
        "Hora": datetime.now().strftime("%H:%M:%S")
    }
    
    df = pd.DataFrame([novo_log])
    # Se o arquivo não existe, cria com cabeçalho, senão anexa
    if not os.path.exists(arquivo):
        df.to_csv(arquivo, index=False, sep=';')
    else:
        df.to_csv(arquivo, mode='a', header=False, index=False, sep=';')


def janela_bluestack() -> list:
    janela_ativa = gerenciador.janela_esta_ativa(titulo_ou_parte="bluestacks")
    print(f"status janela_ativa: {janela_ativa[0]} e {janela_ativa[1].title}")
    if not janela_ativa[0]:
        print("A janela BlueStacks não está ativa.")
        janela = gerenciador.encontrar_janelas(titulo_ou_parte="bluestacks")
        print(f"status da janela: {janela}")
        if not janela:
            print("A janela BlueStacks não foi encontrada.")
            return janela
    sucesso = gerenciador.esperar_janela(titulo_ou_parte="bluestacks", timeout=60)

    return sucesso

def limparFotos():
    if not os.path.exists(SS_DIR):
        return
    
    os.chdir(path=SS_DIR)
    for item in os.listdir(SS_DIR):
        # Forma correta de verificar extensão
        if item.lower().endswith(".png"):
            try:
                os.remove(item)
            except Exception as e:
                print(f"Erro ao deletar {item}: {e}")

    os.chdir(path=PROJECT_ROOT)    
    return True

# O script principal ficaria muito mais curto:
def main():
    print("")
    print("-------------------------------------------------------")
    print("VERIFICANDO APP ABERTO...")
    while True:
        sleep(2)
        appAberto = janela_bluestack()
        if appAberto:
            break
        print("Abrindo app...")
        abrir_app()
        sleep(5)
    
    # 1. Carregar sua API e Agente (Ajuste o caminho conforme seu projeto)
    try:
        with open("src/api_deepseek.txt", "r") as f:
            api_key = f.read().strip().replace('"', '')
        from agente import AgenteSorteiosDeepSeek
        agente_instanciado = AgenteSorteiosDeepSeek(api_key=api_key)
    except Exception as e:
        logging.error(f"Falha ao iniciar agente: {e}")
        print("")
        print("-------------------------------------------------------")
        return

    # 2. Instanciar o Robô
    robo = AutomacaoADB(agente_instanciado)

    # 3. Fluxo de Execução
    logging.info("🚀 Iniciando Motor de Automação...")
    print("")
    print("-------------------------------------------------------")
    while True:

        config = robo.carregar_config_dashboard()

        print(config)

        if config is None:
            sleep(1)
            continue

        if config and config.get("status") == "PROCESSANDO":
            logging.info("⚡ Comando de início detectado pelo Dashboard!")
            
            # 1. Realiza Login
            if robo.realizar_login():
                # 2. Vai para tela de compra
                if robo.executar_passo(ARVORE_DECISAO["HOME"]["participe_concorra"]):
                    # 3. Usa a lógica dinâmica baseada no Expander
                    robo.iniciar_por_dashboard()                    
                    logging.info("✅ Missão concluída com sucesso!")
                    
            # Reseta o status para não entrar em loop infinito
            config["status"] = "CONCLUIDO"
            with open(os.path.join(DB_DIR, "config_automacao.json"), "w") as f:
                json.dump(config, f)
            if config.get("status") == "CONCLUIDO":
                break
        
        sleep(3)


if __name__ == "__main__":
    main()