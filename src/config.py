# config.py na raiz do projeto
import sys
import os
import shutil
import logging

# Configurações do projeto
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, 'src')
DB_DIR = os.path.join(PROJECT_ROOT, 'db')
SS_DIR = os.path.join(DB_DIR, 'ss')
MOLDES_DIR = os.path.join(DB_DIR, 'moldes')
RAG_DIR = os.path.join(DB_DIR, 'RAG')
PDF_DIR = os.path.join(DB_DIR, 'pdf_cartelas')


def carregar_env() -> None:
    """Carrega variáveis do arquivo .env na raiz do projeto (com ou sem python-dotenv)."""
    caminho_env = os.path.join(PROJECT_ROOT, '.env')
    if not os.path.exists(caminho_env):
        return
    try:
        from dotenv import load_dotenv
        load_dotenv(caminho_env, override=False)
        return
    except ImportError:
        pass

    with open(caminho_env, 'r', encoding='utf-8') as f:
        for linha in f:
            linha = linha.strip()
            if not linha or linha.startswith('#') or '=' not in linha:
                continue
            chave, valor = linha.split('=', 1)
            chave = chave.strip()
            valor = valor.strip().strip('"').strip("'")
            os.environ.setdefault(chave, valor)


carregar_env()


def resolver_adb_bin() -> str:
    """Resolve o executável ADB (env ADB_BIN -> BlueStacks HD-Adb.exe -> adb no PATH)."""
    env_bin = os.getenv('ADB_BIN', '').strip()
    if env_bin and os.path.exists(env_bin):
        return env_bin

    candidatos = [
        shutil.which('HD-Adb.exe'),
        shutil.which('adb'),
        r'C:\Program Files\BlueStacks_polar\HD-Adb.exe',
        r'C:\Program Files\BlueStacks_nxt\HD-Adb.exe',
        r'C:\Program Files (x86)\BlueStacks_nxt\HD-Adb.exe',
        r'D:\Program Files\BlueStacks_nxt\HD-Adb.exe',
    ]
    for cand in candidatos:
        if cand and os.path.exists(cand):
            return cand
    return 'HD-Adb.exe'


def resolver_tesseract_cmd() -> str:
    """Resolve o executável Tesseract (env TESSERACT_CMD -> PATH -> caminhos padrão Windows)."""
    env_cmd = os.getenv('TESSERACT_CMD', '').strip()
    if env_cmd and os.path.exists(env_cmd):
        return env_cmd

    candidatos = [
        shutil.which('tesseract'),
        r'D:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
    ]
    for cand in candidatos:
        if cand and os.path.exists(cand):
            return cand
    return 'tesseract'


ADB_BIN = resolver_adb_bin()
ADB_DEVICE = os.getenv('ADB_DEVICE', '127.0.0.1:6610').strip() or '127.0.0.1:6610'
ANDROID_APP_PACKAGE = os.getenv('ANDROID_APP_PACKAGE', 'com.ideamaker.valecap').strip()
TESSERACT_CMD = resolver_tesseract_cmd()
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '').strip()


def get_deepseek_api_key() -> str:
    """Obtém a chave da API DeepSeek do .env (fallback temporário para src/api_deepseek.txt)."""
    chave = os.getenv('DEEPSEEK_API_KEY', '').strip().strip('"').strip("'")
    if chave:
        return chave

    caminho_legado = os.path.join(SRC_DIR, 'api_deepseek.txt')
    if os.path.exists(caminho_legado):
        logging.warning("⚠️ Usando src/api_deepseek.txt (legado). Migre para DEEPSEEK_API_KEY no arquivo .env.")
        with open(caminho_legado, 'r', encoding='utf-8') as f:
            return f.read().strip().replace('"', '')

    raise RuntimeError("DEEPSEEK_API_KEY não configurada. Crie um arquivo .env baseado no .env.example.")


def get_login_credenciais() -> tuple[str, str]:
    """Obtém CPF e senha do .env (fallback temporário para src/login.txt)."""
    cpf = os.getenv('VALECAP_CPF', '').strip()
    senha = os.getenv('VALECAP_SENHA', '').strip()
    if cpf and senha:
        return cpf, senha

    caminho_legado = os.path.join(SRC_DIR, 'login.txt')
    if os.path.exists(caminho_legado):
        logging.warning("⚠️ Usando src/login.txt (legado). Migre para VALECAP_CPF e VALECAP_SENHA no arquivo .env.")
        with open(caminho_legado, 'r', encoding='utf-8') as f:
            linhas = [l.strip() for l in f.readlines() if l.strip()]
            if len(linhas) >= 2:
                return linhas[0], linhas[1]

    raise RuntimeError("Credenciais VALECAP_CPF/VALECAP_SENHA não configuradas no .env.")


# Adiciona ao path do Python
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, SRC_DIR)
sys.path.insert(0, DB_DIR)
sys.path.insert(0, SS_DIR)
sys.path.insert(0, MOLDES_DIR)

print("")
print("-------------------------------------------------------")
print(f"✅ Projeto configurado:")
print(f"   Raiz: {PROJECT_ROOT}")
print(f"   SRC: {SRC_DIR}")
print(f"   DB: {DB_DIR}")
print(f"   SS: {SS_DIR}")
print(f"   Moldes: {MOLDES_DIR}")
print("")
print("-------------------------------------------------------")
print("")

#-----------------------------------------------------------------------

#Arvore de decisao
ARVORE_DECISAO = {
    "HOME": {
        "ancora": "home_ancora.PNG",
        "login": {
            "ancora": ["login_ok.PNG", "acessar_conta.PNG"],
            "passos": [
                {"nome": "acesse_sua_conta", "moldes":["acessar_conta.PNG"], "acao": "clicar" },
                {"nome": "campo_cpf", "moldes": ["inserir_cpf.PNG"], "acao": "preencher"},
                {"nome": "campo_senha", "moldes": ["inserir_senha.PNG"], "acao": "preencher"},
                {"nome": "acessar_sua_conta", "moldes": ["acesse_sua_conta.PNG"], "acao": "clicar"},
                {"nome": "botao_entrar", "moldes": ["botao_entrar.PNG"], "acao": "clicar"},
                
            ]
        },
        "participe_concorra": {
            "moldes": ["btn_participe_concorra.PNG"],
            "acao": "clicar"
        }
    },

    "CARRINHO": {
        "selecao_quantidade": {
            "valecap": {
                "moldes": ["quero_1.PNG", "quero_2.PNG", "quero_4.PNG"],
                "ativos": ["quero_1_ativo.PNG", "quero_2_ativo.PNG", "quero_4_ativo.PNG"],
                "acao": "clicar"
            },
            "hipercap": {
                "moldes": ["quero_2_hiper.PNG", "quero_5_hiper.PNG", "quero_10_hiper.PNG"],
                "ativos": ["quero_2_ativo_hiper.PNG", "quero_5_ativo_hiper.PNG", "quero_10_ativo_hiper.PNG"],
                "acao": "clicar"
            },
            "continuar": {
                "moldes": ["continuar.PNG"],
                "acao": "clicar"
            }
        },

        "PAGAMENTO": {
            "ancora": "seu_pagamento.PNG",
            "fluxo": [
                {
                    "nome": "selecionar_n_titulo", 
                    "moldes": ["escolher_inativo.PNG", "escolher_ativo.PNG"], 
                    "acao": "clicar"
                },
                {
                    "nome": "valecap", 
                    "moldes": ["titulo_valecap.PNG", "titulo_inativo.PNG", "titulo_ativo.PNG"], 
                    "acao": "clicar"
                },
                 {
                    "nome": "hipercap", 
                    "moldes": ["titulo_hipercap.PNG","titulo_inativo.PNG","titulo_ativo.PNG"], 
                    "acao": "clicar"
                },
                {
                    "ancora": "escolher_titulo_especifico.PNG", 
                    "fluxo": [
                        {
                        "nome": "escolher_titulo_especifico",
                        "moldes": ["btn_escolher_titulo.PNG","titulo_valecap_escolher.PNG","titulo_hipercap_escolher.PNG",*(f"titulo{i}_escolher.PNG" for i in range(1, 11))], 
                        "acao": "clicar"
                        },
                        {
                        "escolher_numeros_titulo": {
                            "nome": "escolher_numeros_titulo",
                            "moldes": ["cartela_visivel_ancora.PNG", "atualizando_cartela.PNG"], 
                            "config": {
                                "media_corte": 57.80,
                                "nota_corte": 11.8,
                                "limite_tentativas": 200,
                                "espera_entre_limite_tentativas": 300,
                                "delay_bloqueio": 900, # Tempo que ele vai dormir se o aviso aparecer
                                "swipe_coords": [1250, 1600, 400, 1600, 500], # x1, y1, x2, y2, duracao

                                
                                }
                             },
                        "tela_aviso": {
                            "nome": "avisos",
                            "moldes":["aviso_aguardar.PNG", "aviso_muitas_pessoas.PNG" , "limite_de_escolha.PNG", "limite_escolha.PNG"],
                            "acao": "clicar",# Seu novo PNG aqui
                            "config": {
                                "delay_bloqueio": 900, # Tempo que ele vai dormir se o aviso aparecer
                                                      
                                }
                             },
                        "tela_aviso_entendi": {
                            "nome": "avisos",
                            "moldes": ["entendi.PNG", "entendi_imprevisto.PNG","entetndi_limite.PNG"],
                            "acao": "clicar",# Seu novo PNG aqui
                            "config": {
                                "delay_bloqueio": 900, # Tempo que ele vai dormir se o aviso aparecer
                                                      
                                }
                             }
                        },
                        {
                            "confirmar_titulo":{
                                    "nome": "confirmar_titulo",
                                    "moldes": ['confirmar_e_escolher_proximo.PNG', "confirmar_e_finalizar.PNG"], 
                                    "acao": "clicar",

                            }
                        }
                            ]                
                },
                {
                    "nome": "concordar_termos", 
                    "moldes": ["concordar_ativo.PNG", "concordar_inativo.PNG"], 
                    "acao": "clicar"
                },
                {
                    "nome": "confirmar_compra", 
                    "moldes": ["btn_confirmar_compra.PNG"], 
                    "acao": "clicar"
                },
                {
                    "nome": "fechar_modal", 
                    "moldes": ["fechar.PNG"], 
                    "acao": "clicar"
                }
            ]
        },
        "AVISOS": {
            "fluxo_limite_escolhas": {
                "nome": "escolher_titulo_especifico", "moldes": "confirmar.PNG"
            }
        }
    },
    "NAVEGACAO_FIXA": {
        "meus_titulos": {"moldes": ["meus_titulos.PNG"], "acao": "clicar"},
        "ganhadores": {"moldes": ["ganhadores.PNG"], "acao": "clicar"},
        "carteira": {"moldes": ["carteira.PNG"], "acao": "clicar"}
    }
}