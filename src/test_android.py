from math import e
import subprocess
from tkinter import Y
import cv2
import pytesseract
import numpy as np
import os
from time import sleep

# Função refatorada para capturar e preparar a imagem
def capturar_cartela_android():
    dispositivo = "emulator-5554"
    destino_ss = r"D:\Documentos\Projetos de programacao\Automacao de estatistica vale cap e compra\db\ss"
    nome_arquivo = "ajuda.PNG"
    caminho_completo = os.path.join(destino_ss, nome_arquivo)
    
    print("📸 Capturando via Pipe (contornando erro de permissão)...")
    
    try:
        # 1. Captura via Pipe: Joga o print direto para a memória do Python (STDOUT)
        # Isso ignora completamente o sistema de arquivos do Android
        cmd = ["HD-Adb.exe", "-s", dispositivo, "shell", "screencap", "-p"]
        resultado = subprocess.run(cmd, capture_output=True, check=True)
        
        # Converte os bytes recebidos em imagem OpenCV
        # O replace corrige quebras de linha que o Windows às vezes adiciona ao ADB
        image_bytes = resultado.stdout.replace(b'\r\n', b'\n')
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            print("❌ Erro: Falha ao decodificar a imagem.")
            return None

        # --- O SEU IF ESTÁ AQUI ---
        x = 0  # 1 para fazer o recorte, 0 para salvar a tela inteira
        
        if x == 1:
            print("✂️ Aplicando recorte nas coordenadas configuradas...")
            # Suas coordenadas originais
            x_inicio, x_fim = 993, 1200
            y_inicio, y_fim = 339, 399
            
            # Recorte [y1:y2, x1:x2]
            recorte = img[y_inicio:y_fim, x_inicio:x_fim]
            
            # Salva o recorte para o seu OCR ler
            cv2.imwrite(caminho_completo, recorte)
            return recorte
        else:
            print("🖼️ Salvando print de tela inteira.")
            cv2.imwrite(caminho_completo, img)
            return img

    except Exception as e:
        print(f"Erro na captura: {e}")
        return None
            
    except subprocess.CalledProcessError as e:
        print(f"Erro no ADB: {e}")
    except Exception as e:
        print(f"Erro inesperado: {e}")
    
    return None


def swipe_android(duracao=500):
    dispositivo = "emulator-5554"
    try: 
            comando_0 = ["HD-Adb.exe", "-s", dispositivo, "shell", "input", "tap", "400", "1600", ]
            comando = ["HD-Adb.exe", "-s", dispositivo, "shell", "input", "swipe", "1250", "1600", "400", "1600", str(duracao)]
            subprocess.run(comando_0, check=True)
            sleep(1)

            subprocess.run(comando, check=True)
            print(f"Swipe para escquerda realizado.")
    except Exception as e:
        print(f"Erro ao realizar swipe: {e}")
        return
    
    



#swipe_android(duracao=500)
#sleep(0.5)
cartela_img = capturar_cartela_android()
sleep(1)
print(cartela_img.shape)