import pytesseract
from pdf2image import convert_from_path
import pypdf
from pprint import pprint
import os
import pandas as pd
import re
print("")
print("")
print("")
print("**********************************************************************************************")
caminho_pdf = r"D:\Documentos\Projetos de programacao\Automacao de estatistica vale cap e compra\db\pdf_cartelas"
lista_pdf = os.listdir(r"D:\Documentos\Projetos de programacao\Automacao de estatistica vale cap e compra\db\pdf_cartelas")
#print(caminho_pdf)
for item in lista_pdf:
    
    arquivo = os.path.join(caminho_pdf,str(item))
    print("")
    print(f"Caminho do arquivo:{arquivo}")
    print("item sendo aberto")
    
    if "pdf" in item:
        texto_completo = ""
        try:
            # Abre o arquivo PDF em modo binário de leitura ('rb')
            with open(arquivo, 'rb') as arquivo:
                print("")
                print("Arquivo aberto")
                print("")
                leitor_pdf = pypdf.PdfReader(arquivo)

                # Itera por todas as páginas e extrai o texto
                for num_pagina in range(len(leitor_pdf.pages)):
                    pagina = leitor_pdf.pages[num_pagina]
                    texto_completo += pagina.extract_text()

                print(texto_completo)

        except Exception as e:
            print("")
            print(f"Erro ao ler o PDF: {e}")
            

        if texto_completo:
            print("--- Texto Extraído com SUCESSO (1ª tentativa) ---")
            print("")
            print(texto_completo[200:670]) # Mostra as primeiras 500 caracteres
            # O passo seguinte seria usar Regex neste 'texto_bruto'
        else:
            print("O PDF pode ser baseado em imagem. Partindo para OCR...")
            # Se falhou ou retornou texto vazio, você vai para a próxima etapa (OCR)


#        for x in texto_completo:
#          if "º" == x:
#            print("achei")
        posicao_corte_data = texto_completo.index("º")-2
        cabecalho_data = texto_completo[:posicao_corte_data]
        print("")
        print("----------------------------")
        print("cabeçalho")
        print(cabecalho_data)
        print("----------------------------")
        print("")
        texto_cortado= texto_completo[200:900]
        texto_cortado
        texto_listado = texto_cortado.split("\n")
        lista_deletar = []
        lista_de_numeros = []
        dicionario_de_jogos = {}
        dicionario_de_jogos["cabecalho"] = cabecalho_data
        x = 1
        for item in texto_listado:
            #print("")
            #print("item")
            #print(item)
            if ' ' not in item and item.replace(" ","").isdigit() :
                try:
                    numeros_int = [int(n) for n in item]
                    lista_de_numeros.append(item)
                    if len(item) < 32:
                        dicionario_de_jogos[f"{x}o Sorteio"] = lista_de_numeros.copy()
                        lista_de_numeros.clear()
                        x += 1
                
                except ValueError as e:
                    print(f"Erro de Valor: Os dados retornados são inválidos ou incompletos. {e}")
                    pass
            elif ' ' in item and item.replace(" ","").isdigit() :
                #any(char.isdigit() for char in item)
                #print(item)
                #print(len(item))
                # Quebra a string pelo espaço (' ') para obter strings individuais de números
                numeros_str = item.split(' ')
                #print("")
                #print("numeros_str")
                #print(numeros_str)
                #if
                # Converte cada string de número para um inteiro (int)
                try:
                    numeros_int = [int(n) for n in numeros_str]
                    lista_de_numeros.append(numeros_int)
                    if len(item) < 32:
                        dicionario_de_jogos[f"{x}o Sorteio"] = lista_de_numeros.copy()
                        lista_de_numeros.clear()
                        x += 1
                
                except ValueError as e:
                    print(f"Erro de Valor: Os dados retornados são inválidos ou incompletos. {e}")
                    pass

        pprint(dicionario_de_jogos)

        cabecalho = dicionario_de_jogos['cabecalho']

        # Procura o padrão: 2 números / 2 números / 4 números
        busca_data = re.search(r'(\d{2}/\d{2}/\d{4})', cabecalho)

        if busca_data:
            data_sorteio = busca_data.group(1)

        lista_para_df = []

        # 2. Iterar sobre os sorteios (1o, 2o, 3o)
        for nome_sorteio, blocos in dicionario_de_jogos.items():
            if nome_sorteio == 'cabecalho':
                continue
            
            # Unificar as sublistas de cada sorteio em uma única lista de números
            # Isso transforma [[1,2], [3,4]] em [1, 2, 3, 4]
            numeros_unificados = [num for sublista in blocos for num in sublista]
            
            # Criar uma string dos números separados por espaço para o CSV
            str_numeros = " ".join(map(str, numeros_unificados))
            
            lista_para_df.append({
                'Data': data_sorteio,
                'Sorteio': nome_sorteio,
                'Dezenas': str_numeros,
                'Total_Numeros': len(numeros_unificados)
            })

        # 3. Criar o DataFrame e salvar
        df = pd.DataFrame(lista_para_df)
        #print(df)
        if df.shape[0] == 4 :
            arquivo_csv = 'historico_vale_cap.csv'
            header_condicional = not os.path.exists(arquivo_csv)

            df.to_csv(arquivo_csv, mode='a', index=False, sep=';', encoding='utf-8-sig', header=header_condicional)
        else:
            print("df não salvo")
        #resp = input("continuar?")
        #if resp == "s":
            continue
        #else:break
        #lista_numeros