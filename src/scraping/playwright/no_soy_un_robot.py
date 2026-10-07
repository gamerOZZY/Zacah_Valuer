import os
from playwright.sync_api import sync_playwright, TimeoutError
from playwright_stealth import Stealth # Importación para la versión 2.x
import math 
import random


def generar_curva_bezier(x0, y0, x1, y1, x2, y2, num_puntos=40):
    """Genera los puntos de una curva de Bézier cuadrática."""
    puntos = []
    for t in range(num_puntos + 1):
        t = t / num_puntos
        # Fórmula de Bézier Cuadrática
        x = (1 - t)**2 * x0 + 2 * (1 - t) * t * x1 + t**2 * x2
        y = (1 - t)**2 * y0 + 2 * (1 - t) * t * y1 + t**2 * y2
        puntos.append((x, y))
    return puntos

def mover_raton_humano(page, origen_x, origen_y, destino_x, destino_y):
    """Mueve el ratón usando una trayectoria curva y con velocidades variables."""
    # Usamos una distribución normal para crear un punto de control (curvatura)
    distancia = math.hypot(destino_x - origen_x, destino_y - origen_y)
    
    # El offset determina qué tan pronunciada será la curva
    # Media 0, Desviación estándar = distancia / 4
    offset = random.gauss(0, distancia / 4) 
    
    # Calculamos el punto medio y aplicamos el offset perpendicularmente
    mid_x = (origen_x + destino_x) / 2
    mid_y = (origen_y + destino_y) / 2
    angulo = math.atan2(destino_y - origen_y, destino_x - origen_x) + math.pi / 2
    
    control_x = mid_x + math.cos(angulo) * offset
    control_y = mid_y + math.sin(angulo) * offset

    # Generamos la trayectoria
    trayectoria = generar_curva_bezier(origen_x, origen_y, control_x, control_y, destino_x, destino_y)

    # Recorremos los puntos con pequeñas pausas variables para simular inercia
    for x, y in trayectoria:
        # Añadimos un micro-temblor (jitter) al ratón usando distribución normal
        jitter_x = random.gauss(0, 1.5)
        jitter_y = random.gauss(0, 1.5)
        
        page.mouse.move(x + jitter_x, y + jitter_y, steps=1)
        # Pausa aleatoria entre movimientos (aceleración/desaceleración)
        page.wait_for_timeout(random.randint(5, 15))


def main():
    # 1. Envolvemos sync_playwright() con Stealth().use_sync()
    with Stealth().use_sync(sync_playwright()) as p:
        
        # Crea una carpeta local para guardar cookies y sesión humana
        user_data_dir = os.path.join(os.getcwd(),"src", "scraping", "playwright", "perfil_playwright")
        
        # 2. Iniciamos el contexto. Gracias a la línea de arriba, 
        # TODAS las páginas que se abran aquí ya tendrán el modo bot oculto.
        context = p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"], 
            viewport={"width": 1280, "height": 720}
        )
        
        # 3. Usamos la primera pestaña que se abre por defecto
        page = context.pages[0]

        page.goto("https://propiedades.com/gustavo-a-madero/casas-venta")

        try:
            # Obtenemos el tamaño de la ventana para los clics aleatorios
            viewport = page.viewport_size or {"width": 1280, "height": 720}
            centro_x = viewport["width"] / 2
            centro_y = viewport["height"] / 2

            # --- INICIO: Clics aleatorios de "distracción" ---
            # Guardamos la posición actual del ratón (iniciamos en el centro)
            raton_actual_x, raton_actual_y = centro_x, centro_y 
            page.mouse.move(raton_actual_x, raton_actual_y)
            
            for _ in range(2): # 2 clics aleatorios
                # Generamos coordenadas usando distribución normal
                # Concentramos la probabilidad cerca del centro, pero puede ir a los bordes
                rand_x = random.gauss(centro_x, viewport["width"] / 4)
                rand_y = random.gauss(centro_y, viewport["height"] / 4)
                
                # Mantenemos el clic dentro de los límites de la pantalla
                rand_x = max(10, min(rand_x, viewport["width"] - 10))
                rand_y = max(10, min(rand_y, viewport["height"] - 10))
                
                mover_raton_humano(page, raton_actual_x, raton_actual_y, rand_x, rand_y)
                page.wait_for_timeout(random.randint(100, 400))
                page.mouse.click(rand_x, rand_y)
                
                # Actualizamos la posición
                raton_actual_x, raton_actual_y = rand_x, rand_y
                page.wait_for_timeout(random.randint(500, 1500))
            # --- FIN: Clics aleatorios ---

            # Buscamos el checkbox del captcha
            checkbox_locator = page.frame_locator("iframe").first.locator("#robot-checkbox")
            checkbox_locator.wait_for(state="visible", timeout=5000)
            
            # 1. Obtenemos las dimensiones y posición de la casilla
            box = checkbox_locator.bounding_box()
            if box:
                # Calculamos un punto de impacto LIGERAMENTE descentrado (los humanos no atinan al centro exacto)
                destino_x = box["x"] + box["width"] / 2 + random.gauss(0, box["width"] / 6)
                destino_y = box["y"] + box["height"] / 2 + random.gauss(0, box["height"] / 6)
                
                # 2. Movemos el ratón con la trayectoria curva de Bézier
                mover_raton_humano(page, raton_actual_x, raton_actual_y, destino_x, destino_y)
                raton_actual_x, raton_actual_y = destino_x, destino_y # Actualizamos
                
                page.wait_for_timeout(random.randint(200, 500)) # Breve pausa antes de hacer clic
                
                # 3. Simulamos presionar y soltar el botón del ratón
                page.mouse.down()
                page.wait_for_timeout(random.randint(80, 200)) # Tiempo que el dedo está presionado
                page.mouse.up()
                print("Clic humanizado en casilla realizado.")
            else:
                checkbox_locator.click(delay=random.randint(100, 250))
                
            page.wait_for_timeout(random.randint(1500, 3000))

            # Buscamos el botón de progreso y aplicamos el mismo método
            button_locator = page.frame_locator("iframe").first.locator("#progress-button")
            if button_locator.is_visible():
                box_btn = button_locator.bounding_box()
                if box_btn:
                    dest_btn_x = box_btn["x"] + box_btn["width"] / 2 + random.gauss(0, 3)
                    dest_btn_y = box_btn["y"] + box_btn["height"] / 2 + random.gauss(0, 3)
                    
                    mover_raton_humano(page, raton_actual_x, raton_actual_y, dest_btn_x, dest_btn_y)
                    
                    page.wait_for_timeout(random.randint(200, 400))
                    page.mouse.down()
                    page.wait_for_timeout(random.randint(80, 180))
                    page.mouse.up()
            
        except TimeoutError:
            print("No se encontró el captcha o se resolvió automáticamente.")

        # Esperamos un momento para que la página termine de cargar el contenido
        page.wait_for_timeout(5000) 
        title = page.title()
        print(f"Título obtenido: {title}")
        
        context.close()

if __name__ == "__main__":
    main()