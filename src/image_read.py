from ast import match_case
import pytesseract
from PIL import Image 
import cv2
import os
from time import sleep
from pprint import pprint
import numpy as np
import gerenciadorjanelas as gj
from datetime import datetime
#from automacao import coletar_cartelas

#print("-------------------------")
#3print("carregando módulo automacao.image_read...")
#3PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__).removesuffix('\\config.py'))
#3pasta_ativa = os.getcwd()
#pasta_destino = rf"{PROJECT_ROOT}"
#print(f"Endereço atual: {pasta_ativa}")
#print(f"Pasta desejada: {pasta_destino}")



# Caminho para o executável do Tesseract (ajuste se necessário)
pytesseract.pytesseract.tesseract_cmd = r'D:\Program Files\Tesseract-OCR\tesseract.exe'
def nada(x):
    # Função obrigatória para o Trackbar, mas não precisa fazer nada
    pass

def ler_imagem(imagem = None) -> None:   
    """Lê o texto de uma imagem usando OCR"""
    # Abra a imagem
    if imagem:
        img = Image.open(imagem)
    else:
        print("Nenhuma imagem fornecida.")

    # Extraia o texto
    texto = pytesseract.image_to_string(img)

    return texto

def imagem_ajuste(imagem_path: str, imagem_nome: str) -> dict:
    try:
        print(f"Processando automaticamente: {imagem_nome}")
        
        # 1. Carregamento e Preparação Base
        img = cv2.imread(imagem_path)
        if img is None:
            print("Erro: Imagem não carregada.")
            return {}

        # Redimensionamento (Essencial para manter a precisão dos cortes fixos)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        h, w = gray.shape

        # --- PARTE A: LEITURA DO TÍTULO (Threshold 196) ---
        _, thresh_titulo = cv2.threshold(gray, 196, 255, cv2.THRESH_BINARY)
        
        # Recorte da área do título (ajustado para a imagem do Vale Cap)
        y_ini_t, y_fim_t = int(h * 0.425), int(h * 0.49)
        x_ini_t, x_fim_t = int(w * 0.27), int(w * 0.64)
        roi_titulo = thresh_titulo[y_ini_t:y_fim_t, x_ini_t:x_fim_t]
        
        # Inversão e Dilatação para o título
        roi_titulo_inv = cv2.bitwise_not(roi_titulo)
        kernel = np.ones((2,2), np.uint8)
        roi_titulo_proc = cv2.dilate(roi_titulo_inv, kernel, iterations=1)
        
        config_t = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789.'
        txt_titulo = pytesseract.image_to_string(roi_titulo_proc, config=config_t).strip()
        titulo_limpo = txt_titulo.replace(" ", "").replace("\n", "")
        val_blur = 4

        # --- PARTE B: LEITURA DAS DEZENAS (Threshold 170) ---
        processed = gray.copy()
        if val_blur > 0:
            k_size = (val_blur * 2) + 1
        processed = cv2.GaussianBlur(processed, (k_size, k_size), 0)
        _, thresh_dezenas = cv2.threshold(processed, 208, 255, cv2.THRESH_BINARY)
        
        y_ini, y_fim = int(h * 0.505), int(h * 0.89)
        x_ini, x_fim = int(w * 0.06), int(w * 0.94)

        cel_h = (y_fim - y_ini) // 4
        cel_w = (x_fim - x_ini) // 5
        m_h, m_w = int(cel_h * 0.25), int(cel_w * 0.25) # Safe Zone

        lista_dezenas = []
        for l in range(4):
            for c in range(5):
                y1 = y_ini + (l * cel_h) + m_h
                y2 = y1 + cel_h - (2 * m_h)
                x1 = x_ini + (c * cel_w) + m_w
                x2 = x1 + cel_w - (2 * m_w)
                
                roi_dezena = thresh_dezenas[y1:y2, x1:x2]
                
                config_d = r'--psm 10 -c tessedit_char_whitelist=0123456789'
                txt_d = pytesseract.image_to_string(roi_dezena, config=config_d).strip()
                
                # Validação simples
                if txt_d.isdigit():
                    lista_dezenas.append(txt_d.zfill(2)) # Mantém formato '02', '09'
                else:
                    lista_dezenas.append(None)

        for idx, dezena in enumerate(lista_dezenas):
            print(f"--- Processando posição {idx} ---")
            
            # 1. Tratamento para falha de leitura
            if dezena is None:
                print(f"⚠️ Falha na leitura da dezena na posição {idx + 1}.")
                status = False
            else:
                # 2. Lógica de validação sem o BREAK
                valor = int(dezena)
                match idx:
                    case 0 | 1 | 2 | 3 | 4:
                        status = False if valor > 15 else True
                    case 5 | 6 | 7 | 8 | 9:
                        status = False if valor < 16 or valor > 30 else True
                    case 10 | 11 | 12 | 13 | 14:
                        status = False if valor < 31 or valor > 45 else True
                    case 15 | 16 | 17 | 18 | 19:
                        status = False if valor < 46 or valor > 60 else True
                    case _:
                        status = False

            # Agora todos os prints vão aparecer para cada um dos 20 itens
            print(f"Valor: {dezena} | Status: {status}")

            if dezena is not None and status == False:
                print(f"⚠️ Dezena {dezena} fora do intervalo esperado.")

        # --- RESULTADO FINAL ---
        resultado = {
            "titulo": titulo_limpo,
            "dezenas": lista_dezenas,
            "status": "sucesso" if len([d for d in lista_dezenas if d]) == 20 and status == True else "alerta_falha_leitura"
        }
        print(f"Leitura Concluída: Título {resultado['titulo']} | {len(lista_dezenas)} dezenas." )
        print(f"Status da leitura: {resultado['status']}")
        return resultado

    except Exception as e:
        print(f"Erro ao carregar a imagem: {e}")
        return
          

def coletar_numeros(file_path, image: str) -> dict:
    """Coleta números do texto extraído da imagem"""
    texto = ler_imagem(image)
    formatacao_texto = texto.splitlines(" ")
    formatacao_texto = [linha.strip("\n") for linha in formatacao_texto ]
    formatacao_texto = [ linha for linha in formatacao_texto if linha != '']
    temp2, posicao, cartela = [], [], {}

    for linha in formatacao_texto:
        #print(linha)
        if " " in linha:
            #print("Linha com espaço detectada:")
            #print(linha)
            if linha.replace(" ", "").isalpha():
                #print("Titulo encontrado")
                cartela["titulo"] = linha
                posicao.append(formatacao_texto.index(linha))
            elif linha.replace(" ", "").isnumeric():
                posicao.append(formatacao_texto.index(linha))
                temp = [int(linha_part) for linha_part in linha.split(" ") if linha_part.isnumeric()]
                temp2.extend(temp)
                #print(temp)
        if "." in linha:
            #print("ID da cartela encontrado")
            #print(float(linha))
            cartela["id_cartela"] = float(linha)
            posicao.append(formatacao_texto.index(linha))
        
        else:
            if linha.isnumeric():
                posicao.append(formatacao_texto.index(linha))
                temp2.append(int(linha))

    numero_cartela = temp2.copy()

    if len(numero_cartela) > 14:
        cartela["números"] = numero_cartela
        print("cartela detectada com sucesso!")
        print("Cartela  :")
        pprint(cartela)
        return cartela
    else:
        print("Falha ao detectar todos os números da cartela.")
        print("Tentando novamente...")
        return None
    
