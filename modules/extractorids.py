# modules/extractorids.py

import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException, WebDriverException
import time
import re
from datetime import datetime

# --- Configuración ---
BASE_URL_SCRAPER = "https://live19.nowgoal25.com"
SELENIUM_TIMEOUT_SECONDS_SCRAPER = 20
SELENIUM_POLL_FREQUENCY_SCRAPER = 0.2

# --- FUNCIONES DE CONFIGURACIÓN DEL DRIVER ---

@st.cache_resource
def get_selenium_driver_scraper():
    """Configura e inicia el driver de Selenium, cacheado como recurso."""
    options = ChromeOptions()
    options.add_argument("--headless=new") # Crucial para Streamlit
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    # Añadir User-Agent para parecer más un navegador real
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36")
    options.add_argument('--blink-settings=imagesEnabled=false') # Desactivar imágenes puede acelerar un poco

    try:
        # Selenium 4.6+ debería manejar el driver automáticamente con Selenium Manager
        driver = webdriver.Chrome(options=options)
        # Intenta evitar detección básica
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver
    except WebDriverException as e:
        st.error(f"Error inicializando Selenium driver (Scraper): {e}")
        return None

def ensure_filters_and_order(driver_scraper):
    """Asegura que los filtros y orden estén configurados correctamente."""
    try:
        wait = WebDriverWait(driver_scraper, SELENIUM_TIMEOUT_SECONDS_SCRAPER, poll_frequency=SELENIUM_POLL_FREQUENCY_SCRAPER)
        # Esperar a que el contenedor de herramientas esté presente
        tools_div = wait.until(EC.presence_of_element_located((By.ID, "tools")))
        
        # 1. Asegurar que el filtro de ligas esté activo
        st.info("🔍 Verificando filtro de ligas...")
        li_filter_lea = tools_div.find_element(By.ID, "li_FilterLea")
        if "on" not in (li_filter_lea.get_attribute("class") or ""):
            st.info("🔄 Activando filtro de ligas...")
            driver_scraper.execute_script("arguments[0].click();", li_filter_lea)
            # Esperar a que la clase 'on' se añada al elemento, confirmando la activación.
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "li#li_FilterLea.on")))
            st.success("✅ Filtro de ligas activado.")
        else:
            st.success("✅ Filtro de ligas ya está activo.")
        
        # 2. Asegurar orden por tiempo
        st.info("🔍 Verificando orden por tiempo...")
        li_league_span = tools_div.find_element(By.ID, "li_league") # By league
        
        # Si el span "By league" está visible (su estilo no es 'display: none'), entonces el orden no es por tiempo.
        if "display: none" not in (li_league_span.get_attribute("style") or ""):
            st.info("🔄 El orden actual es 'By league'. Cambiando a 'By time'...")
            li_time_span = tools_div.find_element(By.ID, "li_time") # By time
            # Hacer clic en el span "By time"
            driver_scraper.execute_script("arguments[0].click();", li_time_span)
            
            # Esperar a que el span "By league" se oculte. Esto confirma que el cambio se ha aplicado.
            # El selector CSS busca un span con id 'li_league' que tenga un atributo 'style' que contenga 'display: none'.
            wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "span#li_league[style*='display: none']"))
            )
            st.success("✅ Orden cambiado a 'By time'.")
        else:
            st.success("✅ El orden ya está en 'By time'.")
            
    except TimeoutException as te:
        st.error(f"⏳ Timeout al configurar filtros/orden: {te}")
    except Exception as e:
        st.error(f"💥 Error al configurar filtros/orden: {e}")

def scrape_nowgoal_data():
    """Función principal para scrapear los datos de partidos próximos."""
    driver_scraper = get_selenium_driver_scraper()

    if not driver_scraper:
        st.error("❌ No se pudo obtener un driver de Selenium.")
        return []

    partidos_extraidos = []
    max_partidos = 10

    try:
        with st.spinner(f"🌐 Navegando a {BASE_URL_SCRAPER}..."):
            driver_scraper.get(BASE_URL_SCRAPER)
            # Esperar a que se cargue el contenido principal de partidos
            WebDriverWait(driver_scraper, SELENIUM_TIMEOUT_SECONDS_SCRAPER, poll_frequency=SELENIUM_POLL_FREQUENCY_SCRAPER).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "tr[id^='tr1_']"))
            )
            st.success("✅ Página cargada.")

        # --- Asegurar filtros y orden ---
        st.subheader("🔧 Configurando filtros y orden...")
        ensure_filters_and_order(driver_scraper)
        st.subheader("⚽ Extrayendo datos de partidos próximos...")

        # Re-encontrar las filas de partidos después del posible reordenamiento
        WebDriverWait(driver_scraper, SELENIUM_TIMEOUT_SECONDS_SCRAPER, poll_frequency=SELENIUM_POLL_FREQUENCY_SCRAPER).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "tr.tds[id^='tr1_']"))
        )
        
        # Encontrar todas las filas de partidos individuales
        filas_partidos = driver_scraper.find_elements(By.CSS_SELECTOR, "tr.tds[id^='tr1_']")
        st.info(f"📊 Se encontraron {len(filas_partidos)} filas de partidos potenciales.")

        partidos_procesados = 0
        for fila in filas_partidos:
            if partidos_procesados >= max_partidos:
                break

            try:
                # --- Obtener el ID del partido ---
                match_id = None
                fila_id = fila.get_attribute('id')
                match_id_search = re.search(r'tr1_(\d+)', fila_id)
                if match_id_search:
                    match_id = match_id_search.group(1)

                if not match_id:
                    st.warning("⚠️ No se pudo encontrar el ID del partido para una fila, saltando...")
                    continue

                # --- Verificar si el partido ya ha comenzado ---
                # Buscar el td con clase 'status' y texto 'FT' (Finalizado) o que contenga números (minuto)
                try:
                    status_td = fila.find_element(By.CSS_SELECTOR, f"td.status#time_{match_id}")
                    status_text = status_td.text.strip()
                    # Si el texto es "FT" o contiene números (minuto del partido), el partido ya empezó
                    if status_text == "FT" or re.search(r'\d+', status_text):
                        st.info(f"⏭️ Partido {match_id} ya ha comenzado ({status_text}), saltando...")
                        continue
                except NoSuchElementException:
                    # Si no se encuentra el td de status, asumimos que no ha empezado (pre-partido)
                    pass

                # --- Extraer nombres de los equipos ---
                equipo1_nombre = "N/A"
                equipo2_nombre = "N/A"
                try:
                    # Equipo Local
                    equipo1_elem = fila.find_element(By.CSS_SELECTOR, f"a#team1_{match_id}")
                    equipo1_nombre = equipo1_elem.text.strip()

                    # Equipo Visitante (navegando por estructura)
                    # Buscamos el siguiente <td> que contenga un <a> y que no sea un equipo con id específico
                    equipo1_td = equipo1_elem.find_element(By.XPATH, "./..")
                    # Encontrar el td hermano que contiene el equipo visitante
                    # El HTML muestra que el equipo2 está en un td hermano que contiene un <a>
                    equipo2_td = equipo1_td.find_element(By.XPATH, "./following-sibling::td[.//a and not(.//a[@id])]") 
                    equipo2_elem = equipo2_td.find_element(By.TAG_NAME, "a")
                    equipo2_nombre = equipo2_elem.text.strip()
                    
                except (NoSuchElementException, StaleElementReferenceException) as e:
                    st.warning(f"⚠️ Advertencia al extraer nombres para partido {match_id}: {e}")

                # --- Extraer datos de apuestas ---
                handicap_asiatico = "N/A"
                linea_goles = "N/A"

                try:
                    # --- Intentar encontrar y hacer clic en el icono de 'matchdata' ---
                    # Usar find_elements para evitar NoSuchElementException si no existe
                    iconos_matchdata = fila.find_elements(By.CSS_SELECTOR, "td.oddstd span.matchdata-icon.l0")

                    if iconos_matchdata:
                        # Si se encontró el icono, proceder a hacer clic
                        icono_matchdata_span = iconos_matchdata[0] # Tomar el primero si hay varios
                        # Buscar el <i> dentro del span
                        icono_matchdata_i = icono_matchdata_span.find_element(By.TAG_NAME, "i")

                        # Hacer clic usando JavaScript para mayor robustez
                        st.info(f"🔍 Haciendo clic en Match Data para partido {match_id}...")
                        driver_scraper.execute_script("arguments[0].click();", icono_matchdata_i)

                        # --- Esperar a que aparezca el contenido dinámico con las cuotas ---
                        # Basado en el HTML, se carga un div con id 'goalDiv'
                        WebDriverWait(driver_scraper, SELENIUM_TIMEOUT_SECONDS_SCRAPER, poll_frequency=SELENIUM_POLL_FREQUENCY_SCRAPER).until(
                            EC.visibility_of_element_located((By.ID, "goalDiv"))
                        )
                        st.info("📈 Contenido de cuotas cargado (goalDiv visible).")

                        # --- Extraer Handicap Asiático ---
                        try:
                            # Buscar el div con título "Asian Handicap" dentro de goalDiv
                            # Usar contains(text()) para ser más flexible con espacios
                            asian_handicap_div = WebDriverWait(driver_scraper, 5, poll_frequency=SELENIUM_POLL_FREQUENCY_SCRAPER).until(
                                EC.presence_of_element_located((By.XPATH, "//div[@id='goalDiv']//div[contains(@class, 'goalTitle') and contains(text(), 'Asian Handicap')]"))
                            )
                            # Encontrar la tabla de handicaps más cercana (hermana)
                            tabla_handicap = asian_handicap_div.find_element(By.XPATH, "./following-sibling::table[1]")

                            filas_handicap = tabla_handicap.find_elements(By.TAG_NAME, "tr")
                            if filas_handicap:
                                # Intentar encontrar la primera fila con datos significativos
                                for fila_h in filas_handicap:
                                    celdas_h = fila_h.find_elements(By.TAG_NAME, "td")
                                    # Una fila típica tiene al menos 4 celdas (checkbox, valor, cuota, checkbox)
                                    if len(celdas_h) >= 4:
                                        # Tomar el valor del segundo handicap (normalmente el de la derecha)
                                        # La estructura puede variar, pero el valor suele estar en la celda [3] o [4]
                                        # Vamos a buscar el primer valor que parezca un handicap
                                        for i in range(1, len(celdas_h)): # Empezar desde 1 para evitar checkbox
                                            texto_celda = celdas_h[i].text.strip()
                                            # Verificar si es un valor de handicap (ej: 0, 0/0.5, -0.5, etc.)
                                            if re.match(r'^[+-]?\d*\.?\d+(/\d*\.?\d+)?$', texto_celda):
                                                handicap_asiatico = texto_celda
                                                break
                                        if handicap_asiatico != "N/A":
                                            break # Salir del loop de filas si encontramos uno

                                if handicap_asiatico != "N/A":
                                    st.info(f"🎯 Handicap Asiático encontrado para {match_id}: {handicap_asiatico}")
                                else:
                                    st.info(f"ℹ️ No se encontró un valor de Handicap Asiático válido para {match_id}.")
                            else:
                                st.info(f"ℹ️ Tabla de Handicap Asiático vacía para {match_id}.")
                        except TimeoutException:
                            st.warning(f"⏳ Sección 'Asian Handicap' no encontrada o no cargada a tiempo para {match_id}.")
                        except Exception as e:
                            st.error(f"💥 Error al extraer Handicap Asiático para {match_id}: {e}")

                        # --- Extraer Línea de Goles (Over/Under) ---
                        try:
                            # Buscar el div con título "Over/Under" dentro de goalDiv
                            over_under_div = WebDriverWait(driver_scraper, 5, poll_frequency=SELENIUM_POLL_FREQUENCY_SCRAPER).until(
                                EC.presence_of_element_located((By.XPATH, "//div[@id='goalDiv']//div[contains(@class, 'goalTitle') and contains(text(), 'Over/Under')]"))
                            )
                            # Encontrar la tabla de Over/Under más cercana (hermana)
                            tabla_over_under = over_under_div.find_element(By.XPATH, "./following-sibling::table[1]")

                            filas_over_under = tabla_over_under.find_elements(By.TAG_NAME, "tr")
                            if filas_over_under:
                                # Intentar encontrar la primera fila con datos significativos
                                for fila_ou in filas_over_under:
                                    celdas_ou = fila_ou.find_elements(By.TAG_NAME, "td")
                                    if len(celdas_ou) >= 4:
                                        # Buscar el primer valor numérico (línea de goles)
                                        for i in range(1, len(celdas_ou)):
                                            texto_celda = celdas_ou[i].text.strip()
                                            # Verificar si es un valor de línea (ej: 2, 2.5, 2/2.5, etc.)
                                            if re.match(r'^\d*\.?\d+(/\d*\.?\d+)?$', texto_celda):
                                                linea_goles = texto_celda
                                                break
                                        if linea_goles != "N/A":
                                             break # Salir del loop de filas si encontramos uno

                                if linea_goles != "N/A":
                                    st.info(f"🎯 Línea de Goles encontrada para {match_id}: {linea_goles}")
                                else:
                                    st.info(f"ℹ️ No se encontró un valor de Línea de Goles válido para {match_id}.")
                            else:
                                st.info(f"ℹ️ Tabla de Over/Under vacía para {match_id}.")
                        except TimeoutException:
                            st.warning(f"⏳ Sección 'Over/Under' no encontrada o no cargada a tiempo para {match_id}.")
                        except Exception as e:
                            st.error(f"💥 Error al extraer Línea de Goles para {match_id}: {e}")

                        # --- Cerrar el popup de cuotas ---
                        try:
                            # Buscar botón de cierre dentro de #goalDiv
                            # El botón tiene clase 'closeBtn'
                            boton_cerrar = WebDriverWait(driver_scraper, 5, poll_frequency=SELENIUM_POLL_FREQUENCY_SCRAPER).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, "#goalDiv .closeBtn"))
                            )
                            boton_cerrar.click()
                            st.info("⏹️ Popup de cuotas cerrado.")
                            time.sleep(0.5) # Breve pausa
                        except TimeoutException:
                            st.warning("⚠️ Botón de cierre del popup no encontrado, continuando...")
                        except Exception as e:
                            st.error(f"💥 Error al cerrar el popup para {match_id}: {e}")
                    else:
                        st.info(f"ℹ️ Partido {match_id} no tiene icono de 'Match Data' disponible.")
                        
                except Exception as e:
                    st.error(f"💥 Error general al interactuar o extraer datos de apuestas para el partido {match_id}: {e}")

                # --- Almacenar los datos extraídos ---
                partido_info = {
                    "ID": match_id,
                    "Local": equipo1_nombre,
                    "Visitante": equipo2_nombre,
                    "Handicap Asiático (Bet365)": handicap_asiatico,
                    "Línea de Goles (Bet365)": linea_goles
                }
                partidos_extraidos.append(partido_info)
                partidos_procesados += 1
                st.success(f"✅ Partido {match_id} procesado. ({partidos_procesados}/{max_partidos})")

                # Pequeña pausa entre partidos para no sobrecargar el servidor
                time.sleep(1)

            except StaleElementReferenceException:
                st.warning(f"⚠️ Elemento obsoleto encontrado para una fila, saltando...")
                continue
            except Exception as e:
                st.error(f"💥 Error inesperado al procesar una fila de partido: {e}")
                continue

    except Exception as e:
        st.error(f"💥 Error general durante el scraping: {e}")
    finally:
        # No cerramos el driver aquí porque está cacheado con @st.cache_resource
        pass

    return partidos_extraidos

def display_scraper_ui():
    """Función para mostrar la interfaz de usuario del scraper en Streamlit."""
    st.header("🔍 IDs y Datos de Próximos Partidos")
    st.subheader("⚽ Obteniendo datos de Nowgoal...")
    st.markdown("""
    Esta herramienta extrae los IDs, nombres de equipos y apuestas clave (Handicap Asiático y Línea de Goles de Bet365)
    de los próximos partidos listados en Nowgoal, **ordenados por tiempo** y filtrados para mostrar solo partidos que aún no han comenzado.
    """)

    # Botón para iniciar el scraping
    if st.button("🚀 Extraer Datos de los Próximos 10 Partidos"):
        with st.spinner("🧠 Procesando... (Esto puede tardar unos segundos)"):
            datos = scrape_nowgoal_data()

        if datos:
            st.balloons()
            st.success(f"🎉 ¡Datos extraídos con éxito! Se encontraron {len(datos)} partidos próximos.")
            # Mostrar resultados en una tabla
            st.dataframe(datos)

            # Opción para descargar como CSV
            import pandas as pd
            df = pd.DataFrame(datos)
            csv = df.to_csv(index=False)
            st.download_button(
                label="💾 Descargar como CSV",
                data=csv,
                file_name='proximos_partidos_nowgoal_orden_tiempo.csv',
                mime='text/csv',
            )
        else:
            st.error("❌ No se pudieron extraer datos. Revisa los mensajes de error anteriores.")

    # Botón para reiniciar el driver (útil si se corrompe)
    if st.button("🔄 Reiniciar Driver Selenium (si hay problemas)"):
        get_selenium_driver_scraper.clear()
        st.success("✅ Caché del driver limpiada.")
