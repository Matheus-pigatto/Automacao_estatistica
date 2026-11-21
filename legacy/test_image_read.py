from time import sleep
import cv2
import pytesseract
import numpy as np
import os
from config import SS_DIR

# Configuração do Tesseract (ajuste se necessário)
pytesseract.pytesseract.tesseract_cmd = r'D:\Program Files\Tesseract-OCR\tesseract.exe'

file_name = "print.png"
file_path = os.path.join(SS_DIR, f"{file_name}.png")

def nada(x):
    pass

def calibrar_e_ler(path):
    img = cv2.imread(path)
    if img is None:
        print("Erro: Imagem não encontrada.")
        return

    # Escala de cinza e redimensionamento inicial
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

    cv2.namedWindow('Painel')
    # Trackbars para ajuste fino
    cv2.createTrackbar('Threshold', 'Painel', 176, 255, nada)
    cv2.createTrackbar('Blur', 'Painel', 0, 10, nada) # Barra de Blur

    print("Pressione 'S' para ler a cartela ou 'ESC' para sair.")

    while True:
        val_thresh = cv2.getTrackbarPos('Threshold', 'Painel')
        val_blur = cv2.getTrackbarPos('Blur', 'Painel')

        # Aplicar Blur (deve ser ímpar)
        processed = gray.copy()
        if val_blur > 0:
            k_size = (val_blur * 2) + 1
            processed = cv2.GaussianBlur(processed, (k_size, k_size), 0)

        # Aplicar Threshold
        _, img_bw = cv2.threshold(processed, val_thresh, 255, cv2.THRESH_BINARY)
        
        # --- LÓGICA DE DESENHO DA GRADE PARA VISUALIZAÇÃO ---
        display_img = cv2.cvtColor(img_bw, cv2.COLOR_GRAY2BGR) # Converte para desenhar colorido
        h, w = img_bw.shape
        print(f"Dimensões da imagem: Largura={w}, Altura={h}")
        sleep(1)
        print("")
        y_ini, y_fim = int(h * 0.505), int(h * 0.89)
        x_ini, x_fim = int(w * 0.06), int(w * 0.94)
        cel_h, cel_w = (y_fim - y_ini) // 4, (x_fim - x_ini) // 5
        m_h, m_w = int(cel_h * 0.25), int(cel_w * 0.25)

        print("Desenhando grade de calibração...")
        print(f"y_ini: {y_ini}, \ny_fim: {y_fim}, \nx_ini: {x_ini}, \nx_fim: {x_fim}")

        for l in range(4):
            for c in range(5):
                # Coordenadas do Safe Zone (1 pixel maior para visualização como pedido)
                y1 = y_ini + (l * cel_h) + m_h - 1
                y2 = y_ini + (l * cel_h) + cel_h - m_h + 1
                x1 = x_ini + (c * cel_w) + m_w - 1
                x2 = x_ini + (c * cel_w) + cel_w - m_w + 1
                
                # Desenha o retângulo no painel (Verde, espessura 1)
                cv2.rectangle(display_img, (x1, y1), (x2, y2), (0, 255, 0), 1)
        monitor_view = cv2.resize(display_img, (int(w * 0.25), int(h * 0.25))) 
        cv2.imshow('Painel', monitor_view)
        key = cv2.waitKey(1) & 0xFF

        if key == 27: # ESC
            break

        if key == ord('s'):
            lista_dezenas = []
            for l in range(4):
                for c in range(5):
                    # Recorte exato para o OCR (sem o ajuste de 1px do desenho)
                    ry1, ry2 = y_ini+(l*cel_h)+m_h, y_ini+(l*cel_h)+cel_h-m_h
                    rx1, rx2 = x_ini+(c*cel_w)+m_w, x_ini+(c*cel_w)+cel_w-m_w
                    
                    roi = img_bw[ry1:ry2, rx1:rx2]
                    
                    config = r'--psm 10 -c tessedit_char_whitelist=0123456789'
                    txt = pytesseract.image_to_string(roi, config=config).strip()
                    lista_dezenas.append(txt if txt else "??")

            # Exibição do resultado
            print("\n" + "="*20)
            for i in range(0, 20, 5):
                print(" | ".join(lista_dezenas[i:i+5]))
            print("="*20)

        # TECLA 'T' - LER APENAS O NÚMERO DO TÍTULO
        elif key == ord('t'):
            h, w = img_bw.shape
            
            # 1. Definir a área do Título (Topo da imagem)
            # Ajuste os valores 0.10 e 0.25 conforme a posição do retângulo azul
            y_ini_t, y_fim_t = int(h * 0.425), int(h * 0.49)
            x_ini_t, x_fim_t = int(w * 0.27), int(w * 0.64)
            
            roi_titulo = img_bw[y_ini_t:y_fim_t, x_ini_t:x_fim_t]
            
            # 2. INVERSÃO DE CORES (O pulo do gato)
            # Como o título é branco no azul, no preto e branco ele fica Branco no Preto.
            # O Tesseract precisa de Preto no Branco.
            roi_titulo_inv = cv2.bitwise_not(roi_titulo)
            
            # 3. Engordar os números (Dilatação)
            # Isso ajuda o Tesseract a conectar os pixels do número
            kernel = np.ones((2,2), np.uint8)
            roi_processada = cv2.dilate(roi_titulo_inv, kernel, iterations=1)

            # 4. OCR com configuração robusta
            # Adicionamos o ponto '.' e mudamos para PSM 6
            config_titulo = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789.'
            resultado = pytesseract.image_to_string(roi_processada, config=config_titulo).strip()
            print(f"DEBUG LEITURA BRUTA: {resultado}")
            
        elif key == 27:
            break

    cv2.destroyAllWindows()

# Chamada principal
if __name__ == "__main__":
    file_path = os.path.join(SS_DIR, "print.png")
    calibrar_e_ler(file_path)