# config.py na raiz do projeto
import sys
import os

from pandas.tests.dtypes.test_inference import MockNumpyLikeArray

# Configurações do projeto
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__).removesuffix('src\\config.py'))
SRC_DIR = os.path.join(PROJECT_ROOT, 'src')
DB_DIR = os.path.join(PROJECT_ROOT, 'db')
SS_DIR = os.path.join(DB_DIR, 'ss')
MOLDES_DIR = os.path.join(DB_DIR, 'moldes')


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
                                "nota_corte": 11.8,
                                "limite_tentativas": 30,
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