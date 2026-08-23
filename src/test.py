import os
from config import PROJECT_ROOT, SRC_DIR, SS_DIR, DB_DIR, ARVORE_DECISAO, MOLDES_DIR

etapa_aviso = ARVORE_DECISAO["CARRINHO"]["PAGAMENTO"]["fluxo"][3]["fluxo"][1]["tela_aviso"]
print("Molde(s) de aviso na tela:")
print(etapa_aviso.get("moldes"))