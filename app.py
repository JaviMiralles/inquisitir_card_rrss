import streamlit as st
import feedparser
import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps
from io import BytesIO

# --- CONFIGURACIÓN ---
FEED_URL = "https://featured.inquisitr.com/feed/"
LOCAL_LOGO_PATH = "logo.png"       # Nombre exacto de tu archivo local
FONT_PATH = "tiempos-headline-semibold.ttf" # Nombre exacto de tu fuente
TARGET_SIZE = (1080, 1350)

# Ajustes visuales del Logo y Texto
LOGO_WIDTH = 350
LOGO_MARGIN_TOP = 50
LOGO_MARGIN_LEFT = 50
TEXT_MARGIN_BOTTOM = 460 # Espacio desde abajo donde empieza el área de texto

st.set_page_config(page_title="Generador Noticias Inquisitr", page_icon="📰", layout="wide")

# --- FUNCIONES ---

@st.cache_data
def load_resources():
    """Carga la fuente y el logo local una sola vez para mejorar velocidad."""
    resources = {}
    
    # 1. Cargar Fuente
    try:
        resources['font'] = ImageFont.truetype(FONT_PATH, 60)
    except OSError:
        st.warning(f"⚠️ No se encontró '{FONT_PATH}'. Usando fuente por defecto.")
        resources['font'] = ImageFont.load_default()
        
    # 2. Cargar Logo Local
    try:
        logo = Image.open(LOCAL_LOGO_PATH).convert("RGBA")
        # Redimensionar logo manteniendo proporción
        aspect_ratio = logo.height / logo.width
        new_height = int(LOGO_WIDTH * aspect_ratio)
        resources['logo'] = logo.resize((LOGO_WIDTH, new_height), Image.Resampling.LANCZOS)
    except FileNotFoundError:
        st.error(f"❌ No se encuentra el archivo '{LOCAL_LOGO_PATH}' en la carpeta.")
        resources['logo'] = None
        
    return resources

def resize_and_crop(img, size):
    return ImageOps.fit(img, size, method=Image.Resampling.LANCZOS, bleed=0.0, centering=(0.5, 0.5))

def generar_degradado(size, alpha_inicio=0, alpha_fin=230):
    degradado = Image.new("L", (1, size[1]), color=0xFF)
    for y in range(size[1]):
        alpha = int(alpha_inicio + (alpha_fin - alpha_inicio) * (y / size[1]))
        degradado.putpixel((0, y), alpha)
    return degradado.resize(size)

def draw_text_centered(draw, text, font, img_size):
    """Dibuja el texto centrado en la parte inferior."""
    area = (0, img_size[1] - TEXT_MARGIN_BOTTOM, img_size[0], img_size[1] - 40)
    margin = 60
    spacing = 10 # Un poco más de espacio entre líneas
    
    max_width = area[2] - area[0] - 2 * margin
    words = text.split()
    lines = []
    current_line = ""
    
    # Dividir texto en líneas
    for word in words:
        test_line = current_line + " " + word if current_line else word
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word
    if current_line: lines.append(current_line)

    # Calcular altura total del bloque de texto
    try:
        single_line_height = draw.textbbox((0, 0), "Ay", font=font)[3] + spacing
    except:
        single_line_height = 50
        
    total_text_height = single_line_height * len(lines)
    
    # Centrar verticalmente dentro del área definida
    start_y = area[1] + ((area[3] - area[1]) - total_text_height) // 2

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        # Centrar horizontalmente
        x = area[0] + ((area[2] - area[0]) - text_width) // 2
        
        # Sombra negra sutil para mejorar legibilidad (opcional)
        draw.text((x+2, start_y+2), line, font=font, fill="black") 
        
        # Texto blanco
        draw.text((x, start_y), line, font=font, fill="white")
        start_y += single_line_height

def process_entry(entry, res):
    """Procesa una entrada del RSS."""
    title = entry.title.strip()
    media = entry.get("media_content", [])
    if not media: return None
    image_url = media[0].get("url")

    try:
        # Descargar imagen de la noticia
        resp = requests.get(image_url, timeout=10)
        img = Image.open(BytesIO(resp.content)).convert("RGBA")
        
        # 1. Recortar
        img = resize_and_crop(img, TARGET_SIZE)
        
        # 2. Aplicar degradado
        grad_alpha = generar_degradado(TARGET_SIZE)
        grad_rgba = Image.new("RGBA", TARGET_SIZE, (0,0,0,0))
        grad_rgba.putalpha(grad_alpha)
        img = Image.alpha_composite(img, grad_rgba)
        
        # 3. Pegar Logo Local (si existe)
        if res['logo']:
            img.paste(res['logo'], (LOGO_MARGIN_LEFT, LOGO_MARGIN_TOP), res['logo'])
            
        # 4. Escribir Texto
        draw = ImageDraw.Draw(img)
        draw_text_centered(draw, title, res['font'], TARGET_SIZE)
        
        return img.convert("RGB") # Convertir a RGB para que pese menos al descargar
        
    except Exception as e:
        print(f"Error procesando {title}: {e}")
        return None

# --- INTERFAZ DE USUARIO ---

st.title("📰 Creador de Posts para Redes Sociales")
st.markdown("Genera imágenes listas para Instagram/Facebook a partir de las últimas noticias.")

if st.button("🔄 Cargar últimas noticias", type="primary"):
    
    with st.status("Procesando noticias...", expanded=True) as status:
        st.write("Cargando recursos locales...")
        resources = load_resources()
        
        st.write("Leyendo Feed RSS...")
        feed = feedparser.parse(FEED_URL)
        
        if not feed.entries:
            st.error("No se encontraron noticias.")
            status.update(label="Error", state="error")
        else:
            st.write(f"Encontradas {len(feed.entries)} noticias. Generando imágenes...")
            
            # Contenedor para la rejilla de imágenes
            cols = st.columns(3) # Grid de 3 columnas
            
            count = 0
            for i, entry in enumerate(feed.entries[:12]): # Límite de 12
                img = process_entry(entry, resources)
                
                if img:
                    # Convertir a bytes para el botón de descarga
                    buf = BytesIO()
                    img.save(buf, format="JPEG", quality=90)
                    byte_im = buf.getvalue()
                    
                    # Mostrar en la columna correspondiente
                    with cols[count % 3]:
                        st.image(img, use_container_width=True)
                        st.download_button(
                            label="⬇️ Descargar",
                            data=byte_im,
                            file_name=f"post_inquisitr_{i+1}.jpg",
                            mime="image/jpeg",
                            key=f"dl_{i}"
                        )
                    count += 1
            
            status.update(label="¡Proceso completado!", state="complete")