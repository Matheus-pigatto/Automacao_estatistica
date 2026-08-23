import requests
#from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
# selenium.webdriver.support.ui import WebDriverWait
#from selenium.webdriver.support import expected_conditions as EC
#from selenium.webdriver.common.action_chains import ActionChains
from time import sleep
import os
from seleniumwire import webdriver # Importe do seleniumwire em vez do selenium comum





chrome_options = Options()
prefs = {
    "download.default_directory": r"D:\Documentos\Projetos de programacao\Automacao de estatistica vale cap e compra\db\pdf_cartelas, # Pasta de destino",
    "download.prompt_for_download": False,       # Desativa a pergunta "Salvar como"
    "download.directory_upgrade": True,
    "plugins.always_open_pdf_externally": True   # OBRIGATÓRIO: Faz o Chrome baixar em vez de abrir no navegador
}
chrome_options.add_experimental_option("prefs", prefs)
chrome_options.add_argument('--ignore-certificate-errors')
chrome_options.add_argument('--ignore-ssl-errors')
driver = webdriver.Chrome(options=chrome_options)
driver.scopes = [
    '.*portalr3.*' ,    # Permite tudo do site oficial
    '.*pdfemb-data.*'  # Permite o plugin de PDF
]

download_dir = r"D:\Documentos\Projetos de programacao\Automacao de estatistica vale cap e compra\db\pdf_cartelas"
x = 1
for x in range (10,1,-1):
    URL = f"https://www.portalr3.com.br/editoria/vale-cap/page/{x}" 
    print("iniciando a pesquisa")
    driver.get(URL)
    sleep(1)
    # Exemplo de site para prática
    #response = requests.get(URL)
    try:
        # 2. Captura todos os links dos posts primeiro (Evita Stale Element)
        posts = driver.find_elements(By.XPATH, '//*[@id="posts-container"]/li//h2/a')
        sleep(1)
        links_posts = [p.get_attribute("href") for p in posts if p.get_attribute("href")]
        
        print(f"Encontrados {len(links_posts)} posts. Iniciando varredura...")
        contador = 1
        for link_post in links_posts:
            try:
                print("link #:")
                print(contador)
                contador +=1
                del driver.requests
                sleep(0.5)
                print(f"\nAcessando post: {link_post}")
                nome_arquivo = link_post.split("/")[-1]
                nome_arquivo = nome_arquivo + ".pdf"
                driver.get(link_post)
                sleep(0.5)
                _contador = 1
                for request in driver.requests:
                    print("request #:")
                    print(_contador)
                    _contador +=1
                    if request.response:
                        if "?pdfemb-data=" in request.url.lower():
                            if len(request.url.lower())>220 and len(request.url.lower()) < 280  and request.response.status_code == 200:
                                url_pdf = request.url
                                print(url_pdf)
                                driver.get(url_pdf)
                                link_pdf = driver.find_elements(By.XPATH, '//*[@id="wp-pdf-embbed"]/head/link[@rel="canonical"]')
                                
                                #print(link_pdf)
                                link_down = link_pdf[0].get_attribute("href")
                                conteudo_pdf = requests.get(link_down).content
                                print(f"Baixando: {nome_arquivo}")
                                #print(conteudo_pdf)
                                caminho_completo = os.path.join(download_dir, nome_arquivo)
                                # 5. Download com Requests
                                with open(caminho_completo, 'wb') as f:
                                    f.write(conteudo_pdf)
                                    print("Arquivo salvo com sucesso!")
                                break

            except Exception as e:
                print(f"Erro ao processar este post: {e}")
                #driver.switch_to.default_content() # Garante que saia do iframe em caso de erro
                continue
    except Exception as e:
        print(f"Não foi possível clicar no elemento: {e}")
