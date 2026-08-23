from re import L
from sys import exception
from typing import Any
import pyautogui
from time import sleep
import pygetwindow as gw
import os
from pathlib import Path
import gerenciadorjanelas as gj
from datetime import datetime
import image_read
from config import PROJECT_ROOT, SS_DIR, DB_DIR
from pprint import pprint
import json
import pandas as pd
import logging

pyautogui.useImageNotFoundException(False)
gerenciador = gj.GerenciadorJanelas()
#sleep de 1 min e verificar login
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class AutoParticipar:
    def __init__(self, regiao=(1291, 3, 600, 1040), confianca=0.85):
        self.regiao = regiao
        self.confianca = confianca
        # Caminho base para as imagens
        self.path_base = r"db\imagens_para_automacao"

    def clicar_se_visivel(self, nome_imagem, delay=1.5, obrigatorio=True):
        """Tenta localizar e clicar numa imagem. Retorna True se conseguir."""
        caminho = rf"{self.path_base}\{nome_imagem}.PNG"
        logging.info(f"Procurando: {nome_imagem}")
        print(f"Caminho da imagem: {caminho}")
        

        try:
            # Recebe o resultado numa variável única para evitar o erro de Unpack
            posicao = pyautogui.locateCenterOnScreen(
                image=caminho,
                grayscale=True,
                region=self.regiao,
                confidence=self.confianca
            )

            if posicao and obrigatorio==True:
                x, y = posicao
                pyautogui.click(x, y)
                logging.info(f"✅ Sucesso: {nome_imagem} clicado em ({x}, {y})")
                sleep(delay)
                return True
            
            if obrigatorio:
                logging.warning(f"❌ Falha: {nome_imagem} não encontrado.")
            return False

        except Exception as e:
            logging.error(f"⚠️ Erro ao procurar {nome_imagem}: {e}")
            return False

    def executar(self):
        """Executa a sequência completa de cliques."""
        # Lista de passos: (nome_arquivo, delay, obrigatorio)
        passos = [
            ("participe_e_concorra", 5, True),
            ("quero_1", 2, True),
            ("quero_1_ativo", 2, False), # Exemplo: apenas checagem, sem clique necessário
            ("continuar", 2, True),
            ("escolher", 3, True),
            ("valecap", 3, True),
            ("botao_escolher", 1, True)
        ]

        for nome, espera, obrigatorio in passos:
            sucesso = self.clicar_se_visivel(nome, delay=espera, obrigatorio=obrigatorio)
            
            # Se um passo obrigatório falhar, interrompe a sequência
            if not sucesso and obrigatorio:
                logging.error(f"🛑 Sequência interrompida no passo: {nome}")
                return False
        
        logging.info("🎯 Sequência concluída com sucesso!")
        return True

def abrir_app() -> None:
    pyautogui.click(x=676,y=1060, clicks=1, button='left')
    sleep(40)

def login_app() -> bool:
    print("Verificando se o usuário já está logado...")
    
    # 1. Tenta verificar se já está logado
    login_ok = pyautogui.locateCenterOnScreen(
        image=r"db\imagens_para_automacao\login_ok.PNG", 
        grayscale = False, 
        region=(1291, 3, 600, 1040), 
        confidence=0.8
    )
    
    if login_ok:
        x, y = login_ok
        print(f"✅ Login já realizado: x={x}, y={y}")
        return True

    # 2. Se não estiver logado, tenta iniciar o processo de login
    print("❌ Não logado. Tentando realizar login automático...")
    
    # Tenta encontrar o botão "Acessar Conta"
    acessar = pyautogui.locateCenterOnScreen(
        image=r"db\imagens_para_automacao\acessar_conta.PNG", 
        confidence=0.9, grayscale=True, region=(1291, 3, 600, 1040)
    )

    if acessar:
        pyautogui.click(acessar)
        sleep(2)
        
        # Sequência de Login (CPF -> Senha -> Entrar)
        # CPF
        cpf_campo = pyautogui.locateCenterOnScreen(r"db\imagens_para_automacao\inserir_cpf.PNG", confidence=0.8)
        x_cpf, y_cpf = cpf_campo if cpf_campo else (1600, 628)
        pyautogui.click(x_cpf, y_cpf)
        pyautogui.write("40697047873", interval=0.1)

        # SENHA
        senha_campo = pyautogui.locateCenterOnScreen(r"db\imagens_para_automacao\inserir_senha.PNG", confidence=0.8)
        x_sen, y_sen = senha_campo if senha_campo else (1600, 763)
        pyautogui.click(x_sen, y_sen)
        pyautogui.write("Ma171291th@", interval=0.1)

        # BOTAO ENTRAR
        botao = pyautogui.locateCenterOnScreen(r"db\imagens_para_automacao\botao_entrar.PNG", confidence=0.8)
        x_btn, y_btn = botao if botao else (1600, 883)
        pyautogui.click(x_btn, y_btn)
        
        sleep(5) # Espera o login carregar
        return True
    else:
        print("⚠️ Tela de login não encontrada.")
        return False




def participar() -> bool:
    # Se moveste a janela para (0,0), a região 600x1024 está correta
    bot = AutoParticipar(regiao=(1291, 3, 600, 1040), confianca=0.85) 
    return bot.executar()
    

def buscar_titulo() -> None:
    sucesso = janela_bluestack()
    if sucesso[0]:
        print("Janela BlueStacks ativada.")
        print("-------------------------")
        pasta_ativa = os.getcwd()
        pasta_destino = rf"{SS_DIR}"
        print(f"Endereço atual: {pasta_ativa}")
        print(f"Pasta desejada: {pasta_destino}")
        try :
            if pasta_ativa != pasta_destino and os.path.exists(pasta_destino):
                os.chdir(pasta_destino)
                print(f"Pasta alterada para: {pasta_destino}")
                print(f"Endereço atual: {os.getcwd()}")
        except Exception as e:
            print(f"Erro ao alterar pasta: {e}")
        while True:
            janela_ativa = gerenciador.janela_esta_ativa(titulo_ou_parte="bluestacks")
            if not janela_ativa[0]:
                print("A janela BlueStacks não está ativa.")
                janela = gerenciador.encontrar_janelas(titulo_ou_parte="bluestacks")
            sleep(1)
            pyautogui.moveTo(x=1800, y=690, duration=0.3)
            pyautogui.click()
            sleep(1)
            
            pyautogui.moveTo(x=1800, y=690, duration=0.3)
            pyautogui.click()
            pyautogui.scroll(clicks=10)
            file_name = f"{datetime.today().strftime('%Y-%m-%d')}_cartela"
            file_path = f"{SS_DIR}\\{file_name}.png"
            fileNameColetado = coletar_cartelas(file_name, file_path)
            return fileNameColetado         

def trocar_titulo() -> None:
    sucesso = janela_bluestack()
    if sucesso[0]:
        print("Janela BlueStacks ativada.")
        print("-------------------------")
        pasta_ativa = os.getcwd()
        pasta_destino = rf"{SS_DIR}"
        print(f"Endereço atual: {pasta_ativa}")
        print(f"Pasta desejada: {pasta_destino}")
        try :
            if pasta_ativa != pasta_destino and os.path.exists(pasta_destino):
                os.chdir(pasta_destino)
                print(f"Pasta alterada para: {pasta_destino}")
                print(f"Endereço atual: {os.getcwd()}")
        except Exception as e:
            print(f"Erro ao alterar pasta: {e}")
        while True:
            janela_ativa = gerenciador.janela_esta_ativa(titulo_ou_parte="bluestacks")
            if not janela_ativa[0]:
                print("A janela BlueStacks não está ativa.")
                janela = gerenciador.encontrar_janelas(titulo_ou_parte="bluestacks")
            sleep(0.8)
            pyautogui.moveTo(x=1800, y=690, duration=0.3)
            pyautogui.click()
            pyautogui.drag(xOffset=-400, yOffset=0, button= 'left',duration=0.5)
            os.chdir(PROJECT_ROOT)
            sleep(0.8)
            return

        
def coletar_cartelas(file_name: str, file_path: str = None)  -> Any: 
    alterar_pasta_destino(SS_DIR)
    print("Capturando screenshot da cartela...")
    sleep(3)
    for n in range(2, 0, -1):  
        print(f"Capturando em {n} segundos...", end='\r')
        sleep(0.5)
        pyautogui.moveTo(x=1590, y=730, duration=0.3)
        pyautogui.click()
        pyautogui.screenshot(imageFilename=f"{file_name}_{n}.png", region=(1330, 400, 550, 555))

    for n in range(2, 0, -1):
        #textando os prints tirados
        _fileName = f"{file_name}_{n}.png"    
        _file_path = f"{SS_DIR}\\{_fileName}"
        texto_img_ajustada = image_read.imagem_ajuste(_file_path, _fileName )
        
        print("-------------------------")
        print("Texto extraído da imagem:")
        print(texto_img_ajustada)
        print("O status:")
        print(texto_img_ajustada['status'])
        print("-------------------------")
        if texto_img_ajustada['status'] == "sucesso":
            print("Título capturado com sucesso! Finalizando tentativa.")
            print("Retornando ao diretório principal do projeto.")
            os.chdir(PROJECT_ROOT)
            return texto_img_ajustada
        elif texto_img_ajustada['status'] != "sucesso":
            print("Título não capturado, tentando próxima imagem...")
            pass
        else:
            print("Título não capturado após várias tentativas. Finalizando processo.")
            print("Retornando ao diretório principal do projeto.")
            print("Apagando todas a imagens salvas")
            for n in range(2, 0, -1):
                #textando os prints tirados
                _fileName = f"{file_name}_{n}.png"
                os.remove(_fileName)
            os.chdir(PROJECT_ROOT)
            return None                   

 
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


def selecionar_titulo() -> None:    
    pyautogui.moveTo(x=1663, y=697, duration=0.3)
    pyautogui.click()
    pyautogui.click()

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

def alterar_pasta_destino(pasta_destino: str) -> None:

    pasta_ativa = os.getcwd()
    print(f"Endereço atual: {pasta_ativa}")
    print(f"Pasta desejada: {pasta_destino}")
    try :
        if pasta_ativa != pasta_destino and os.path.exists(pasta_destino):
            os.chdir(pasta_destino)
            print(f"Pasta alterada para: {pasta_destino}")
            print(f"Endereço atual: {os.getcwd()}")
    except Exception as e:
        print(f"Erro ao alterar pasta: {e}")

def gerir_decisao_cartela(dados_cartela, agente):
    # 1. Extração dos dados que já vieram no dicionário
    id_ref = dados_cartela.get("titulo", "desconhecido")
    dezenas = dados_cartela.get("dezenas", [])
    
    # 2. Obter Scores do RAG
    # Aqui usamos o método comparativo que criámos no rag.py
    scores = agente.testar_rag(dezenas)

    print(f"Scores obtidos para a cartela {id_ref}: {scores}")
    
    # 3. Filtro de Corte Automático (IA)
    # Se a cartela for muito má estatisticamente, o robô pula automaticamente
    if float(scores['weighted_score']) < 40.0:
        salvar_log_decisao(id_ref, dezenas, scores, "Rejeitado_IA")
        print(f"🚫 Cartela {id_ref} rejeitada pelo filtro de IA (Score: {scores['weighted_score']})")
        return "PROXIMA"

    # 4. Comunicação com o Streamlit (Aperto de Mão)
    comunicacao = {
        "id_cartela": id_ref,
        "dezenas": [int(d) for d in dezenas], # Garante que são ints no JSON
        "pure_score": round(float(scores['pure_score']), 2),
        "weighted_score": round(float(scores['weighted_score']), 2),
        "media_bolas": round(float(scores.get('media_bolas_viciado', 60)), 1),
        "status": "aguardando_aprovacao",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    with open("db/comunicacao_app.json", "w") as f:
        json.dump(comunicacao, f)

    # 5. Laço While: Aguarda a tua decisão no Streamlit
    print(f"⏳ Cartela {id_ref} aguardando decisão no Dashboard...")
    while True:
        sleep(1)
        with open("db/comunicacao_app.json", "r") as f:
            status_atual = json.load(f)
        
        if status_atual["status"] == "ACEITO":
            salvar_log_decisao(id_ref, dezenas, scores, "Comprado")
            return "COMPRAR"
        
        elif status_atual["status"] == "DESISTIDO":
            salvar_log_decisao(id_ref, dezenas, scores, "Desistido_Usuario")
            return "PROXIMA"


def script(agente_instanciado):
    print("")
    while True:
        appAberto = janela_bluestack()
        if len(appAberto) > 0:
            break
        print("Abrindo app...")
        abrir_app()
        sleep(5)
    
    print("Padronizando janela BlueStacks...")
    gerenciador.padronizar_janela(titulo="bluestacks", largura=600, altura=1040, pos_x=1291, pos_y=3)

    print(f"Verificando Login")            
    loginOk = login_app()
    if not loginOk:
        # Tenta mais uma vez antes de desistir
        sleep(3)
        loginOk = login_app()

    if not loginOk:
        print("Falha persistente no login. Abortando.")
        input("Pressione Enter para fechar...")
        return
    participarValecap = participar()
    if not participarValecap:
        print("não foi possivel participar")
        input("Pressione Enter para fechar...")
        return
    
    while True:
            dados_da_cartela = buscar_titulo() # Já retorna o teu dicionário
            
            if dados_da_cartela and dados_da_cartela['status'] == 'sucesso':
                print("Dados da cartela coletados:")
                print(dados_da_cartela)
                print("Analisando decisão com o agente...")
                decisao = gerir_decisao_cartela(dados_da_cartela, agente_instanciado)
                
                print(f"Decisão tomada: {decisao}")
                if decisao == "COMPRAR":
                    selecionar_titulo() # Teu script de clicar
                    break 
                else:
                    pyautogui.moveTo(x=1590, y=690, duration=0.3)
                    trocar_titulo() # Teu script de arrastar para o lado
                    limparFotos()
                    sleep(2)


def salvar_cartela_para_analise(dados_cartela, status="pendente"):
    """
    dados_cartela: dict com 'id_cartela', 'números', 'score_puro', 'score_viciado'
    status: 'pendente' (esperando usuário), 'aceito', 'descartado'
    """
    caminho_temp = os.path.join(DB_DIR, "comunicacao_app.json")
    payload = {
        "timestamp": datetime.now().isoformat(),
        "dados": dados_cartela,
        "status": status
    }
    with open(caminho_temp, 'w') as f:
        json.dump(payload, f)

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





if __name__ == "__main__":
    try:
        from agente import AgenteSorteiosDeepSeek 
        print("🔍 Tentando carregar a API Key...")

        # Garante o caminho correto do arquivo de texto
        caminho_api = os.path.join(PROJECT_ROOT, "src", "api_deepseek.txt")
        
        if not os.path.exists(caminho_api):
            print(f"❌ ERRO: Arquivo não encontrado em: {caminho_api}")
        else:
            with open(caminho_api, "r") as txt:
                conteudo = txt.read().strip()
                # Remove aspas se existirem
                api_key = conteudo.replace('"', '')
            
            print("🚀 Iniciando motor de automação...")
            agente_instancia = AgenteSorteiosDeepSeek(api_key=api_key)
            
            # CHAMA A FUNÇÃO
            script(agente_instancia)

    except Exception as e:
        print(f"💥 ERRO FATAL NA INICIALIZAÇÃO: {e}")
        input("Pressione Enter para fechar...") # Mantém a janela aberta para você ler o erro
        