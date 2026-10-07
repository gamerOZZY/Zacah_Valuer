import os
import random
import time
from playwright.sync_api import sync_playwright, expect

def test_perfil_navegacion(perfil_nombre, delay_min, delay_max, num_paginas=10):
    with sync_playwright() as p:
        user_data_dir = os.path.join(os.getcwd(),"src", "scraping", "playwright", "perfil_playwright")
        
        # Usamos el perfil persistente que ya tiene la cookie del CAPTCHA resuelto
        context = p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            viewport={"width": 1280, "height": 720}
        )
        
        page = context.pages[0]
        base_url = "https://propiedades.com/gustavo-a-madero/casas-venta?pagina={}"
        
        print(f"--- Iniciando prueba: {perfil_nombre} ---")
        print(f"Intervalo de espera: {delay_min}s - {delay_max}s")
        
        paginas_visitadas = 0
        
        for i in range(1, num_paginas + 1):
            url = base_url.format(i)
            print(f"[{time.strftime('%H:%M:%S')}] Navegando a página {i}...")
            
            # Guardamos el tiempo de inicio para medir la respuesta del servidor
            start_time = time.time()
            
            try:
                # Vamos a la página y esperamos a que la red se calme un poco
                response = page.goto(url, wait_until="domcontentloaded")
                load_time = time.time() - start_time
                
                # Le damos 2 segundos a la página para renderizar el iframe del CAPTCHA si es que existe
                page.wait_for_timeout(2000)
                
                bloqueo_detectado = False
                motivo_bloqueo = ""

                # --- SENSOR 1: Código de Estado HTTP ---
                # Cloudflare suele devolver 503 cuando lanza un reto interactivo
                if response and response.status in [403, 503]:
                    bloqueo_detectado = True
                    motivo_bloqueo = f"Status Code HTTP {response.status}"

                # --- SENSOR 2: Título de la Página ---
                # Cloudflare cambia el título de la pestaña temporalmente
                titulo = page.title().lower()
                if any(frase in titulo for frase in ["just a moment", "un momento", "attention", "cloudflare", "security"]):
                    bloqueo_detectado = True
                    motivo_bloqueo = f"Título sospechoso ('{page.title()}')"

                # --- SENSOR 3: Iframe del Checkbox (El que ya conocemos) ---
                # Buscamos el checkbox específicamente DENTRO del iframe
                captcha_checkbox = page.frame_locator("iframe").locator("#robot-checkbox")
                # count() > 0 asegura que existe, is_visible() asegura que se está mostrando
                if captcha_checkbox.count() > 0 and captcha_checkbox.first.is_visible():
                    bloqueo_detectado = True
                    motivo_bloqueo = "Checkbox '#robot-checkbox' visible en Iframe"

                # --- SENSOR 4: Iframe genérico de Cloudflare Turnstile ---
                # A veces no hay checkbox, solo un spinner que gira. Ese iframe viene de cloudflare.
                turnstile_iframe = page.locator("iframe[src*='challenges.cloudflare.com']")
                if turnstile_iframe.count() > 0:
                    bloqueo_detectado = True
                    motivo_bloqueo = "Iframe de Cloudflare Turnstile detectado"

                # --- EVALUACIÓN DE LOS SENSORES ---
                if bloqueo_detectado:
                    print(f"\n❌ ¡BLOQUEO DETECTADO en la página {i}!")
                    print(f"   Motivo: {motivo_bloqueo}")
                    print(f"   La sesión sobrevivió {paginas_visitadas} páginas con el {perfil_nombre}.")
                    break # Rompemos el ciclo for para que el bot se detenga
                    
                paginas_visitadas += 1
                print(f"✅ Página {i} cargada en {load_time:.2f}s. (Status: {response.status if response else 'N/A'})")
                
                # Simular scroll humano para cargar imágenes diferidas
                scroll_steps = random.randint(3, 6)
                for _ in range(scroll_steps):
                    page.mouse.wheel(0, random.randint(300, 700))
                    page.wait_for_timeout(random.randint(500, 1500))
                
                # Calcular tiempo restante del delay y esperar
                tiempo_scroll = scroll_steps * 1.0 
                espera_total = random.uniform(delay_min, delay_max)
                espera_restante = max(1.0, espera_total - tiempo_scroll)
                
                print(f"   Esperando {espera_restante:.2f} segundos...")
                page.wait_for_timeout(int(espera_restante * 1000))

            except Exception as e:
                print(f"⚠️ Error inesperado en la página {i}: {str(e)}")
                break

        if paginas_visitadas == num_paginas:
            print(f"🏆 Prueba completada. El {perfil_nombre} no disparó las alarmas.")
            
        context.close()

if __name__ == "__main__":
    # Ejecuta UNA prueba por sesión para no mezclar los resultados.
    # Comenta y descomenta según el perfil que quieras probar hoy.
    
    # test_perfil_navegacion("Perfil A - Lector", 25.0, 45.0, num_paginas=5)
    test_perfil_navegacion("Perfil B - Buscador Activo", 8.0, 15.0, num_paginas=15)
    # test_perfil_navegacion("Perfil C - Al Límite", 2.0, 5.0, num_paginas=30)