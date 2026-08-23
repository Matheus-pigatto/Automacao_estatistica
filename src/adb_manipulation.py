import logging
import cv2
import numpy as np
import subprocess
import os
from numpy.matlib import rand
from time import sleep


def clicar_adb(x_ini, y_ini, w, h, random_offset=0, centro=False) -> bool:
    random_offset_value = random_offset if random_offset > 0 else 0
    
    if centro:
        # Cálculo do centro do molde
        x_centro = int(x_ini + (w / 2))
        y_centro = int(y_ini + (h / 2))
    else:
        x_centro = int(x_ini + (w / 2)) + random_offset_value
        y_centro = int(y_ini + (h / 2)) + random_offset_value

    print(f"✅ Molde encontrado! Clicando em: {x_centro}, {y_centro}")
    
    # Executa o clique via HD-Adb no dispositivo correto
    comando = ["HD-Adb.exe", "-s", "emulator-5554", "shell", "input", "tap", str(x_centro), str(y_centro)]
    try:
        sleep(0.5)
        subprocess.run(comando)
        return True, x_centro, y_centro
    except Exception as e:
        print(f"Erro ao executar o comando ADB: {e}")
        return False

def capturar_cartela_android():
    #dispositivo = "127.0.0.1:5555"
    dispositivo = "emulator-5554"
    destino_ss = r"D:\Documentos\Projetos de programacao\Automacao de estatistica vale cap e compra\db\ss"
    nome_arquivo = r"print.PNG"
    caminho_completo = os.path.join(destino_ss, nome_arquivo)
    print("Capturando tela do dispositivo Android...")
    print(f"Caminho completo do arquivo: {caminho_completo}")
    # Captura via HD-Adb
    subprocess.run(["HD-Adb.exe", "-s", dispositivo, "shell", "screencap", "-p", "/sdcard/screen.png"], check=True)
    subprocess.run(["HD-Adb.exe", "-s", dispositivo, "pull", "/sdcard/screen.png", caminho_completo], check=True)

    #img = cv2.imread(caminho_completo)


def match_template_adb(molde_path, print_path, threshold=0.8) -> tuple[bool, int, int, int, int]:

    capturar_cartela_android()
    try: 
        # Carrega as imagens
        img_print = cv2.imread(print_path, cv2.IMREAD_GRAYSCALE)
        img_molde = cv2.imread(molde_path, cv2.IMREAD_GRAYSCALE)
        #print(f"Caminho {print_path} \nvalor do print carregado:\n {img_print}")
        #print(f"Caminho {molde_path} \nvalor do molde carregado:\n {img_molde}")
        if img_print is None or img_molde is None:
            logging.error(f"❌ Erro ao carregar imagens. SS is None? = {img_print is None} -- MOLDE is None? = {img_molde is None} Verifique os caminhos.")
            return False, 0, 0, 0, 0
        
        img_print = cv2.cvtColor(img_print, cv2.COLOR_BGR2GRAY) if len(img_print.shape) == 3 else img_print
        img_print = cv2.resize(img_print, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        sleep(0.5)
        img_molde = cv2.cvtColor(img_molde, cv2.COLOR_BGR2GRAY) if len(img_molde.shape) == 3 else img_molde
        img_molde = cv2.resize(img_molde, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        
        #print(f"Dimensões do molde - Largura: {w}, Altura: {h}")
        
        
        # Faz o Match Template
        res = cv2.matchTemplate(img_print, img_molde, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        
        if max_val >= threshold:
            x_ini, y_ini = max_loc
            h, w = img_molde.shape[:2]
            x_ini, y_ini, h, w = (x_ini/2), (y_ini/2), (h/2), (w/2)
            os.remove(print_path)
            return True, x_ini, y_ini, w, h
        
        return False, 0, 0, 0, 0
    except Exception as e:
        logging.error(f"Erro ao verificar imagens, erro: {e}")

def random_offset(valor_maximo):
    return np.random.randint(-valor_maximo, valor_maximo + 1)

