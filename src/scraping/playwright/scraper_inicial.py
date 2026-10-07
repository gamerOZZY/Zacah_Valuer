## Este codigo es capaz de entrar a la pagina y sacar los datos de las
## paginas subsecuentes de las carpetas, pero se debe de dar click
## manualmente al "No soy un robot"


import os
from playwright.sync_api import sync_playwright

def main():
    with sync_playwright() as p:
        user_data_dir = os.path.join(os.getcwd(),"src", "scraping", "playwright", "perfil_playwright")
    
        context = p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"] # Oculta que es un bot
        )
        
        page = context.new_page()
        url_inicial = "https://propiedades.com/gustavo-a-madero/casas-venta"
        page.goto(url_inicial)

        # Esperamos a que el selector de los enlaces de las tarjetas cargue en el DOM
        page.wait_for_selector("a.pcom-property-card-body-main-info-street")
        
        # 1. Extraer todas las URLs de la página actual antes de empezar a navegar
        enlaces_locators = page.locator("a.pcom-property-card-body-main-info-street").all()
        urls_propiedades = []
        for enlace in enlaces_locators:
            href = enlace.get_attribute("href")
            # En caso de que el href sea relativo, lo convertimos a absoluto si es necesario.
            # En este sitio web los href suelen ser absolutos (https://...)
            urls_propiedades.append(href)
            
        print(f"Se encontraron {len(urls_propiedades)} propiedades en esta página.")

        # 2. Recorrer la lista de URLs extraídas
        for index, url_propiedad in enumerate(urls_propiedades):
            
            # Intervalo de espera de 2 segundos antes de acceder a la tarjeta
            page.wait_for_timeout(2000) 
            
            print(f"Accediendo a la propiedad {index + 1} de {len(urls_propiedades)}...")
            
            # Entrar a la tarjeta (página de detalles del inmueble)
            page.goto(url_propiedad)
            
            # ====================================================================
            # === ESPACIO PARA GUARDAR VALORES CON SELECTORES CSS EN VARIABLES ===
            # ====================================================================
            
            # Es recomendable esperar a que un elemento clave de la nueva página cargue
            # page.wait_for_selector("h1.titulo-propiedad-css", timeout=5000)
            
            try:
                # Ejemplo de variables (debes reemplazar los selectores por los reales de la página de destino):
                # titulo      = page.locator("SELECTOR_CSS_DEL_TITULO").inner_text()
                # precio      = page.locator("SELECTOR_CSS_DEL_PRECIO").inner_text()
                # ubicacion   = page.locator("SELECTOR_CSS_DE_LA_UBICACION").inner_text()
                # descripcion = page.locator("SELECTOR_CSS_DE_LA_DESCRIPCION").inner_text()
                
                # print(f"Extraído: {titulo} | {precio}")
                pass # Elimina este 'pass' cuando agregues tus selectores
                
            except Exception as e:
                print(f"Error al extraer datos de {url_propiedad}: {e}")
                
            # ====================================================================
            
            # 3. Regresar a la página inicial
            # Usar goto() con la url inicial es más robusto que usar page.go_back()
            page.goto(url_inicial)
            
            # Esperar nuevamente a que el listado de tarjetas se vuelva a renderizar 
            # para estar listos para el siguiente ciclo
            page.wait_for_selector("a.pcom-property-card-body-main-info-street")

        print("Extracción de la página completada.")

if __name__ == "__main__":
    main()