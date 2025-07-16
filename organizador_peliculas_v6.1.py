import os
import re
import json
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
import tmdbsimple as tmdb
from datetime import datetime
import requests
from PIL import Image, ImageTk
import io
import threading
from difflib import SequenceMatcher
import shutil
import webbrowser
from PIL import Image, ImageTk
import requests
import io

CONFIG_PATH = "config.json"
HISTORIAL_PATH = "peliculas_confirmadas.json"

VIDEO_EXTS = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.m4v', '.flv', '.webm', '.mpg', '.mpeg', '.3gp']
SUB_EXTS = ['.srt', '.ass', '.vtt', '.sub', '.idx', '.ssa']

# Colores para los estados
COLORES = {
    'verde': '#4CAF50',  # Alta confianza
    'amarillo': '#FF9800',  # Confianza media
    'rojo': '#F44336',  # Baja confianza o no encontrado
    'confirmado': '#2196F3'  # Ya confirmado por usuario
}

# ---------------------------- Configuración ----------------------------
def cargar_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def guardar_config(config):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

def cargar_historial():
    if not os.path.exists(HISTORIAL_PATH):
        return {}
    try:
        with open(HISTORIAL_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def guardar_historial(historial):
    with open(HISTORIAL_PATH, 'w', encoding='utf-8') as f:
        json.dump(historial, f, indent=4, ensure_ascii=False)

def pedir_api_key():
    root = tk.Tk()
    root.withdraw()
    key = simpledialog.askstring("API Key requerida", 
                                "Necesitas una API Key de TMDb (The Movie Database):\n\n"
                                "1. Ve a https://www.themoviedb.org/settings/api\n"
                                "2. Crea una cuenta si no tienes\n"
                                "3. Solicita una API Key\n"
                                "4. Pégala aquí:\n", 
                                show='*')
    root.destroy()
    return key.strip() if key else None

def validar_api_key(api_key):
    tmdb.API_KEY = api_key
    try:
        search = tmdb.Search()
        response = search.movie(query="test")
        return True
    except:
        return False

# ---------------------------- Utilidades ----------------------------
def limpiar_nombre_archivo(nombre):
    caracteres_ilegales = r'[\\/:*?"<>|]'
    nombre_limpio = re.sub(caracteres_ilegales, '', nombre)
    nombre_limpio = re.sub(r'\.+$', '', nombre_limpio.strip())
    return nombre_limpio

def extraer_info_archivo(nombre_archivo):
    nombre = os.path.splitext(nombre_archivo)[0]
    
    patrones_limpiar = [
        r'\b(1080p|720p|480p|4K|2160p|BluRay|BRRip|DVDRip|WEBRip|HDTV|x264|x265|HEVC|AAC|AC3|DTS)\b',
        r'\b(EXTENDED|DIRECTORS?\.?CUT|UNRATED|THEATRICAL)\b',
        r'\[(.*?)\]',
        r'\(((?!19|20)\d{2})\)',
    ]
    
    for patron in patrones_limpiar:
        nombre = re.sub(patron, '', nombre, flags=re.IGNORECASE)
    
    año_match = re.search(r'\b(19|20)\d{2}\b', nombre)
    año = año_match.group() if año_match else ""
    
    if año:
        nombre = nombre.replace(año, '')
    
    nombre = re.sub(r'[._-]+', ' ', nombre)
    nombre = re.sub(r'\s+', ' ', nombre.strip())
    
    return nombre, año

def buscar_pelicula_tmdb(nombre, idioma, año=None):
    try:
        busqueda = tmdb.Search()
        if año:
            respuesta = busqueda.movie(query=nombre, language=idioma, year=año)
        else:
            respuesta = busqueda.movie(query=nombre, language=idioma)
        return busqueda.results
    except Exception as e:
        print(f"Error buscando en TMDb: {e}")
        return []

def calcular_similitud(texto1, texto2):
    return SequenceMatcher(None, texto1.lower(), texto2.lower()).ratio()

def obtener_confianza_y_resultado(nombre_archivo, nombre_limpio, año_extraido, resultados):
    """Determina la confianza y el mejor resultado"""
    if not resultados:
        return 'rojo', None, f"No se encontraron resultados para '{nombre_limpio}'"
    
    mejor_resultado = None
    mejor_score = 0
    
    for resultado in resultados:
        titulo = resultado.get('title', '')
        titulo_original = resultado.get('original_title', '')
        año_tmdb = resultado.get('release_date', '')[:4] if resultado.get('release_date') else ''
        
        # Calcular similitud
        similitud_titulo = calcular_similitud(nombre_limpio, titulo)
        similitud_original = calcular_similitud(nombre_limpio, titulo_original)
        similitud_maxima = max(similitud_titulo, similitud_original)
        
        # Bonus por año
        bonus_año = 0.3 if año_extraido and año_extraido == año_tmdb else 0
        
        score_total = similitud_maxima + bonus_año
        
        if score_total > mejor_score:
            mejor_score = score_total
            mejor_resultado = resultado
    
    # Determinar color según confianza
    if mejor_score >= 0.85:
        color = 'verde'
        mensaje = f"Alta confianza: {mejor_resultado.get('title', '')}"
    elif mejor_score >= 0.6:
        color = 'amarillo'
        mensaje = f"Confianza media: {mejor_resultado.get('title', '')}"
    else:
        color = 'rojo'
        mensaje = f"Baja confianza: {mejor_resultado.get('title', '')}"
    
    return color, mejor_resultado, mensaje

def generar_nombre_sugerido(pelicula_info):
    """Genera el nombre sugerido para el archivo"""
    if not pelicula_info:
        return ""
    
    titulo = pelicula_info.get('title', '')
    año = pelicula_info.get('release_date', '')[:4] if pelicula_info.get('release_date') else ''
    
    if titulo and año:
        return limpiar_nombre_archivo(f"{titulo} ({año})")
    elif titulo:
        return limpiar_nombre_archivo(titulo)
    else:
        return ""

def mover_archivo(origen, destino_dir):
    """Mueve archivo y sus subtítulos a la carpeta destino"""
    try:
        if not os.path.exists(destino_dir):
            os.makedirs(destino_dir)
        
        nombre_archivo = os.path.basename(origen)
        destino = os.path.join(destino_dir, nombre_archivo)
        
        # Mover archivo principal
        shutil.move(origen, destino)
        
        # Mover subtítulos asociados
        dir_origen = os.path.dirname(origen)
        nombre_base = os.path.splitext(nombre_archivo)[0]
        
        for archivo in os.listdir(dir_origen):
            if archivo.lower().startswith(nombre_base.lower()):
                ext = os.path.splitext(archivo)[1].lower()
                if ext in SUB_EXTS:
                    origen_sub = os.path.join(dir_origen, archivo)
                    destino_sub = os.path.join(destino_dir, archivo)
                    try:
                        shutil.move(origen_sub, destino_sub)
                    except:
                        pass
        
        return destino
    except Exception as e:
        print(f"Error moviendo archivo: {e}")
        return None

def renombrar_archivo(origen, nuevo_nombre, carpeta_destino=None):
    """Renombra archivo y opcionalmente lo mueve"""
    try:
        # Verificar que el archivo original existe
        if not os.path.exists(origen):
            return None, f"El archivo no existe: {origen}"
        
        dir_origen = os.path.dirname(origen)
        ext = os.path.splitext(origen)[1]
        
        if carpeta_destino:
            if not os.path.exists(carpeta_destino):
                os.makedirs(carpeta_destino)
            nuevo_path = os.path.join(carpeta_destino, f"{nuevo_nombre}{ext}")
        else:
            nuevo_path = os.path.join(dir_origen, f"{nuevo_nombre}{ext}")
        
        if os.path.exists(nuevo_path):
            return None, f"Ya existe: {nuevo_path}"
        
        # Renombrar/mover archivo principal
        if carpeta_destino:
            shutil.move(origen, nuevo_path)
        else:
            os.rename(origen, nuevo_path)
        
        # Renombrar/mover subtítulos
        renombrar_subtitulos(origen, nuevo_path, carpeta_destino)
        
        return nuevo_path, "Éxito"
    except Exception as e:
        return None, f"Error: {str(e)}"

def renombrar_subtitulos(origen, nuevo_path, carpeta_destino=None):
    """Renombra y mueve subtítulos asociados"""
    dir_origen = os.path.dirname(origen)
    nombre_antiguo = os.path.splitext(os.path.basename(origen))[0]
    nombre_nuevo = os.path.splitext(os.path.basename(nuevo_path))[0]
    
    if carpeta_destino:
        dir_destino = carpeta_destino
    else:
        dir_destino = os.path.dirname(nuevo_path)
    
    if not os.path.exists(dir_origen):
        return
    
    for archivo in os.listdir(dir_origen):
        if archivo.lower().startswith(nombre_antiguo.lower()):
            ext = os.path.splitext(archivo)[1].lower()
            if ext in SUB_EXTS:
                sufijo = archivo[len(nombre_antiguo):]
                nuevo_sub = nombre_nuevo + sufijo
                
                ruta_antigua = os.path.join(dir_origen, archivo)
                ruta_nueva = os.path.join(dir_destino, nuevo_sub)
                
                if not os.path.exists(ruta_nueva):
                    try:
                        if carpeta_destino:
                            shutil.move(ruta_antigua, ruta_nueva)
                        else:
                            os.rename(ruta_antigua, ruta_nueva)
                    except:
                        pass

# ---------------------------- Diálogo de Selección ----------------------------
class DialogoSeleccion:
    def __init__(self, parent, opciones, titulo="Seleccionar película"):
        self.resultado = None
        self.ventana = tk.Toplevel(parent)
        self.ventana.title(titulo)
        self.ventana.geometry("850x550")  # Tamaño un poco mayor para imágenes
        self.ventana.transient(parent)
        self.ventana.grab_set()
        
        # Centrar ventana
        self.ventana.update_idletasks()
        x = (self.ventana.winfo_screenwidth() // 2) - (850 // 2)
        y = (self.ventana.winfo_screenheight() // 2) - (550 // 2)
        self.ventana.geometry(f"850x550+{x}+{y}")
        
        self.imagenes = []  # Guarda referencias a las imágenes
        self.crear_interfaz(opciones)
    
    def crear_interfaz(self, opciones):
        main_frame = tk.Frame(self.ventana)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Scrollbar
        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Título
        tk.Label(scrollable_frame, text="Selecciona la película correcta:", 
                font=("Arial", 12, "bold")).pack(pady=10)
        
        # Opciones con imágenes
        self.var_seleccion = tk.StringVar()
        
        for i, opcion in enumerate(opciones):
            frame_opcion = tk.Frame(scrollable_frame, relief=tk.RAISED, borderwidth=1)
            frame_opcion.pack(fill=tk.X, padx=5, pady=2)
            
            # Radio button
            tk.Radiobutton(frame_opcion, variable=self.var_seleccion, 
                         value=str(i), font=("Arial", 10)).pack(side=tk.LEFT, padx=5)
            
            # Contenedor de imagen + texto
            contenido_frame = tk.Frame(frame_opcion)
            contenido_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
            
            # Imagen (izquierda)
            img_frame = tk.Frame(contenido_frame)
            img_frame.pack(side=tk.LEFT, padx=5, pady=5)
            
            poster_path = opcion.get('poster_path')
            if poster_path:
                try:
                    # Descargar imagen
                    url = f"https://image.tmdb.org/t/p/w200{poster_path}"
                    response = requests.get(url, stream=True)
                    img = Image.open(io.BytesIO(response.content))
                    img = img.resize((100, 150), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    
                    # Mostrar y guardar referencia
                    label = tk.Label(img_frame, image=photo)
                    label.image = photo
                    self.imagenes.append(photo)
                    label.pack()
                except:
                    tk.Label(img_frame, text="Imagen no disponible", width=15, height=7).pack()
            else:
                tk.Label(img_frame, text="Sin imagen", width=15, height=7).pack()
            
            # Información (derecha)
            info_frame = tk.Frame(contenido_frame)
            info_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
            
            titulo = opcion.get('title', 'Sin título')
            año = opcion.get('release_date', '')[:4] if opcion.get('release_date') else 'Sin año'
            
            tk.Label(info_frame, text=f"{titulo} ({año})", font=("Arial", 11, "bold")).pack(anchor=tk.W)
            
            # Título original si es diferente
            if opcion.get('original_title') and opcion['original_title'] != titulo:
                tk.Label(info_frame, text=f"Original: {opcion['original_title']}", 
                        font=("Arial", 9)).pack(anchor=tk.W)
            
            # Sinopsis (recortada)
            sinopsis = (opcion.get('overview', '')[:120] + '...') if len(opcion.get('overview', '')) > 120 else opcion.get('overview', 'Sin sinopsis')
            tk.Label(info_frame, text=sinopsis, wraplength=500, 
                   font=("Arial", 9), justify=tk.LEFT).pack(anchor=tk.W)
        
        # Scrollbars y botones (igual que antes)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        frame_botones = tk.Frame(self.ventana)
        frame_botones.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Button(frame_botones, text="Seleccionar", command=self.seleccionar).pack(side=tk.LEFT, padx=5)
        tk.Button(frame_botones, text="Buscar otra vez", command=self.buscar_manual).pack(side=tk.LEFT, padx=5)
        tk.Button(frame_botones, text="Cancelar", command=self.cancelar).pack(side=tk.LEFT, padx=5)
        
        if opciones:
            self.var_seleccion.set("0")  # Seleccionar primera opción por defecto
    
    # Los métodos siguientes NO cambian:
    def seleccionar(self):
        seleccion = self.var_seleccion.get()
        if seleccion:
            self.resultado = ("seleccion", int(seleccion))
            self.ventana.destroy()
    
    def buscar_manual(self):
        self.resultado = ("manual", None)
        self.ventana.destroy()
    
    def cancelar(self):
        self.resultado = ("cancelar", None)
        self.ventana.destroy()

# ---------------------------- Clase Principal ----------------------------
class OrganizadorPeliculas:
    def __init__(self, root):
        self.root = root
        self.root.title("Organizador de Películas v6 By Thesombrer - Filtros, Menú Contextual y Renombrado Automático")
        self.root.geometry("1200x800")
        
        self.config = cargar_config()
        self.historial_confirmadas = cargar_historial()
        
        if not self.validar_configuracion():
            self.root.destroy()
            return
        
        self.peliculas_lista = []
        self.procesando = False
        
        self.carpeta_busqueda = self.config.get('carpeta_busqueda', '')
        self.carpeta_destino = self.config.get('carpeta_destino', '')
        self.idioma = self.config.get('idioma', 'es-MX')
        
        self.crear_interfaz()
        
        if self.carpeta_busqueda and os.path.exists(self.carpeta_busqueda):
            self.entry_busqueda.delete(0, tk.END)
            self.entry_busqueda.insert(0, self.carpeta_busqueda)
        
        if self.carpeta_destino:
            self.entry_destino.delete(0, tk.END)
            self.entry_destino.insert(0, self.carpeta_destino)
        
        # Crear menús
        self.menu_filtros = self.crear_menu_filtros()
        self.menu_contextual = self.crear_menu_contextual()
    
    def validar_configuracion(self):
        if 'api_key' not in self.config or not self.config['api_key']:
            api_key = pedir_api_key()
            if not api_key:
                messagebox.showerror("Error", "Se requiere una API Key para continuar")
                return False
            self.config['api_key'] = api_key
        
        if not validar_api_key(self.config['api_key']):
            messagebox.showerror("Error", "La API Key no es válida")
            return False
        
        if 'idioma' not in self.config:
            self.config['idioma'] = 'es-MX'
        
        tmdb.API_KEY = self.config['api_key']
        guardar_config(self.config)
        return True
    
    def detectar_idioma_pelicula(self, nombre_archivo):
        """Intenta detectar el idioma basado en el nombre del archivo"""
        # Patrones comunes para detectar idioma
        patrones = {
            'es-MX': [r'\b(español|español latino|es-mx|es_la|spanish)\b', r'\.es(?:[-_]mx)?\.'],
            'es-ES': [r'\b(español|español castellano|es-es|spanish)\b', r'\.es(?:[-_]es)?\.'],
            'en-US': [r'\b(english|inglés|en-us|en)\b', r'\.en(?:[-_]us)?\.'],
            'fr-FR': [r'\b(french|français|fr-fr|fr)\b', r'\.fr(?:[-_]fr)?\.'],
            'pt-BR': [r'\b(portuguese|português|pt-br|pt)\b', r'\.pt(?:[-_]br)?\.']
        }
        
        nombre = nombre_archivo.lower()
        for idioma, regex_list in patrones.items():
            for regex in regex_list:
                if re.search(regex, nombre, re.IGNORECASE):
                    return idioma
        
        # Si no se detecta, usar el idioma configurado
        return self.idioma
    
    def crear_interfaz(self):
        # Frame principal
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Frame de búsqueda
        buscar_frame = tk.Frame(main_frame)
        buscar_frame.pack(fill=tk.X, pady=(0, 5))

        tk.Label(buscar_frame, text="Buscar título:").pack(side=tk.LEFT, padx=(5, 2))
        self.entry_buscar = tk.Entry(buscar_frame, width=40)
        self.entry_buscar.pack(side=tk.LEFT, padx=5)
        tk.Button(buscar_frame, text="🔍 Buscar", command=self.buscar_en_lista).pack(side=tk.LEFT)
        tk.Button(buscar_frame, text="🧹 Limpiar", command=self.restaurar_lista).pack(side=tk.LEFT, padx=5)
        
        # Frame de configuración
        config_frame = tk.LabelFrame(main_frame, text="Configuración", font=("Arial", 10, "bold"))
        config_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Carpeta de búsqueda
        tk.Label(config_frame, text="Carpeta de búsqueda:", font=("Arial", 9)).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.entry_busqueda = tk.Entry(config_frame, width=60, font=("Arial", 9))
        self.entry_busqueda.grid(row=0, column=1, padx=5, pady=5)
        tk.Button(config_frame, text="Examinar", command=self.seleccionar_carpeta_busqueda).grid(row=0, column=2, padx=5, pady=5)
        
        # Carpeta de destino
        tk.Label(config_frame, text="Carpeta de destino (opcional):", font=("Arial", 9)).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.entry_destino = tk.Entry(config_frame, width=60, font=("Arial", 9))
        self.entry_destino.grid(row=1, column=1, padx=5, pady=5)
        tk.Button(config_frame, text="Examinar", command=self.seleccionar_carpeta_destino).grid(row=1, column=2, padx=5, pady=5)
        
        # Idioma
        tk.Label(config_frame, text="Idioma:", font=("Arial", 9)).grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.combo_idioma = ttk.Combobox(config_frame, values=['es-MX', 'es-ES', 'en-US'], state='readonly', width=15)
        self.combo_idioma.set(self.idioma)
        self.combo_idioma.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        self.combo_idioma.bind('<<ComboboxSelected>>', self.cambiar_idioma)
        
        # Frame de controles
        control_frame = tk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Botones principales
        self.btn_escanear = tk.Button(control_frame, text="🔍 Escanear Películas", 
                                     command=self.escanear_peliculas, font=("Arial", 10, "bold"),
                                     bg='#2196F3', fg='white')
        self.btn_escanear.pack(side=tk.LEFT, padx=5)
        
        tk.Button(control_frame, text="🔄 Refrescar Lista", 
                 command=self.refrescar_lista).pack(side=tk.LEFT, padx=5)
        
        tk.Button(control_frame, text="⚙️ Configurar API", 
                 command=self.configurar_api).pack(side=tk.LEFT, padx=5)
        
        # Botón para renombrar automáticamente
        tk.Button(control_frame, text="✅ Renombrar Automáticamente", 
                 command=self.renombrar_automatico, font=("Arial", 10, "bold"),
                 bg='#4CAF50', fg='white').pack(side=tk.LEFT, padx=5)
        
        # Botón para filtros
        tk.Button(control_frame, text="🎨 Filtrar por Color", 
                 command=lambda: self.menu_filtros.post(control_frame.winfo_rootx(), control_frame.winfo_rooty()+30),
                 font=("Arial", 10)).pack(side=tk.LEFT, padx=5)
        
        # Progress bar
        self.progress = ttk.Progressbar(control_frame, mode='indeterminate')
        self.progress.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)
        
        # Frame de la lista
        lista_frame = tk.LabelFrame(main_frame, text="Lista de Películas", font=("Arial", 10, "bold"))
        lista_frame.pack(fill=tk.BOTH, expand=True)
        
        # Leyenda de colores
        leyenda_frame = tk.Frame(lista_frame)
        leyenda_frame.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Label(leyenda_frame, text="🟢 Alta confianza", fg=COLORES['verde'], font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=10)
        tk.Label(leyenda_frame, text="🟡 Confianza media", fg=COLORES['amarillo'], font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=10)
        tk.Label(leyenda_frame, text="🔴 Baja confianza", fg=COLORES['rojo'], font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=10)
        tk.Label(leyenda_frame, text="🔵 Confirmado", fg=COLORES['confirmado'], font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=10)
        tk.Label(leyenda_frame, text="Doble click para selección manual", font=("Arial", 9, "italic")).pack(side=tk.RIGHT, padx=10)
        
        # Treeview para la lista
        tree_frame = tk.Frame(lista_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        columns = ('seleccionar', 'archivo', 'titulo_encontrado', 'titulo_sugerido', 'año', 'confianza', 'estado')
        self.tree = ttk.Treeview(tree_frame, columns=columns, show='headings', selectmode='extended')
        
        # Configurar columnas
        self.tree.bind("<Double-1>", self.seleccion_manual)
        self.tree.bind("<Button-3>", self.mostrar_menu_contextual)
        self.tree.heading('seleccionar', text='☑️')
        self.tree.heading('archivo', text='Archivo Original')
        self.tree.heading('titulo_encontrado', text='Título Encontrado')
        self.tree.heading('titulo_sugerido', text='Nombre Sugerido')
        self.tree.heading('año', text='Año')
        self.tree.heading('confianza', text='Confianza')
        self.tree.heading('estado', text='Estado')
        
        self.tree.column('seleccionar', width=50)
        self.tree.column('archivo', width=180)
        self.tree.column('titulo_encontrado', width=180)
        self.tree.column('titulo_sugerido', width=180)
        self.tree.column('año', width=60)
        self.tree.column('confianza', width=80)
        self.tree.column('estado', width=100)
        
        # Scrollbars
        scrollbar_v = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar_h = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=scrollbar_v.set, xscrollcommand=scrollbar_h.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_v.pack(side=tk.RIGHT, fill=tk.Y)
        scrollbar_h.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Configurar tags de colores
        self.tree.tag_configure('verde', foreground=COLORES['verde'])
        self.tree.tag_configure('amarillo', foreground=COLORES['amarillo'])
        self.tree.tag_configure('rojo', foreground=COLORES['rojo'])
        self.tree.tag_configure('confirmado', foreground=COLORES['confirmado'])
        
        # Frame de botones de acción
        botones_frame = tk.Frame(lista_frame)
        botones_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Botones de selección
        tk.Button(botones_frame, text="☑️ Seleccionar Todas", 
                 command=self.seleccionar_todas).pack(side=tk.LEFT, padx=5)
        
        tk.Button(botones_frame, text="☐ Deseleccionar Todas", 
                 command=self.deseleccionar_todas).pack(side=tk.LEFT, padx=5)
        
        tk.Button(botones_frame, text="🟢 Seleccionar Verdes", 
                 command=lambda: self.seleccionar_por_color('verde')).pack(side=tk.LEFT, padx=5)
        
        tk.Button(botones_frame, text="🟡 Seleccionar Amarillas", 
                 command=lambda: self.seleccionar_por_color('amarillo')).pack(side=tk.LEFT, padx=5)
        
        tk.Button(botones_frame, text="🗑️ Eliminar Seleccionadas", 
                 command=self.eliminar_seleccionadas).pack(side=tk.LEFT, padx=5)
        
        # Status bar
        self.status_var = tk.StringVar(value="Listo")
        status_bar = tk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def crear_menu_filtros(self):
        """Crea el menú de filtros por color"""
        menu_filtros = tk.Menu(self.root, tearoff=0)
        menu_filtros.add_command(label="Mostrar Todas", command=lambda: self.aplicar_filtro_color())
        menu_filtros.add_command(label="Mostrar Verdes", command=lambda: self.aplicar_filtro_color('verde'))
        menu_filtros.add_command(label="Mostrar Amarillas", command=lambda: self.aplicar_filtro_color('amarillo'))
        menu_filtros.add_command(label="Mostrar Rojas", command=lambda: self.aplicar_filtro_color('rojo'))
        menu_filtros.add_command(label="Mostrar Confirmadas", command=lambda: self.aplicar_filtro_color('confirmado'))
        return menu_filtros
    
    def crear_menu_contextual(self):
        """Crea el menú contextual para click derecho"""
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Seleccionar/Deseleccionar", command=self.seleccionar_item_contextual)
        menu.add_command(label="Renombrar", command=self.renombrar_item_contextual)
        menu.add_command(label="Buscar Manualmente", command=self.buscar_manual_item_contextual)
        menu.add_separator()
        menu.add_command(label="Abrir Ubicación", command=self.abrir_ubicacion_item_contextual)
        return menu
    
    def aplicar_filtro_color(self, color=None):
        """Filtra la lista por color"""
        for item in self.tree.get_children():
            tags = self.tree.item(item, 'tags')
            if color is None or color in tags:
                self.tree.reattach(item, '', 'end')
            else:
                self.tree.detach(item)
    
    def mostrar_menu_contextual(self, event):
        """Muestra el menú contextual al hacer click derecho"""
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.menu_contextual.post(event.x_root, event.y_root)
    
    def seleccionar_item_contextual(self):
        """Selecciona/deselecciona el item del menú contextual"""
        item = self.tree.selection()[0] if self.tree.selection() else None
        if item:
            valores = self.tree.item(item, 'values')
            try:
                indice = int(valores[0]) if valores[0].isdigit() else None
                if indice is not None and 0 <= indice < len(self.peliculas_lista):
                    self.peliculas_lista[indice]['seleccionado'] = not self.peliculas_lista[indice]['seleccionado']
                    self.refrescar_lista()
            except:
                pass
    
    def renombrar_item_contextual(self):
        """Renombra el item del menú contextual"""
        item = self.tree.selection()[0] if self.tree.selection() else None
        if item:
            self.renombrar_automatico()
    
    def buscar_manual_item_contextual(self):
        """Busca manualmente el item del menú contextual"""
        item = self.tree.selection()[0] if self.tree.selection() else None
        if item:
            event = type('Event', (), {'x':0, 'y':0})  # Simulamos un evento
            self.seleccion_manual(event)
    
    def abrir_ubicacion_item_contextual(self):
        """Abre la ubicación del archivo"""
        item = self.tree.selection()[0] if self.tree.selection() else None
        if item:
            valores = self.tree.item(item, 'values')
            try:
                indice = int(valores[0]) if valores[0].isdigit() else None
                if indice is not None and 0 <= indice < len(self.peliculas_lista):
                    ruta = self.peliculas_lista[indice]['archivo']
                    if os.path.exists(ruta):
                        directorio = os.path.dirname(ruta)
                        os.startfile(directorio)
            except:
                pass
    
    def buscar_en_lista(self):
        texto = self.entry_buscar.get().lower()
        if not texto:
            return

        # Ocultar todos los que no coincidan
        for item in self.tree.get_children():
            valores = self.tree.item(item, 'values')
            if texto in valores[1].lower() or texto in valores[2].lower():
                self.tree.reattach(item, '', 'end')
            else:
                self.tree.detach(item)

    def restaurar_lista(self):
        for item in self.tree.get_children(''):
            self.tree.reattach(item, '', 'end')
        self.entry_buscar.delete(0, tk.END)

    def seleccionar_carpeta_busqueda(self):
        carpeta = filedialog.askdirectory(title="Seleccionar carpeta de búsqueda")
        if carpeta:
            self.carpeta_busqueda = carpeta
            self.entry_busqueda.delete(0, tk.END)
            self.entry_busqueda.insert(0, carpeta)
            self.config['carpeta_busqueda'] = carpeta
            guardar_config(self.config)
    
    def seleccionar_carpeta_destino(self):
        carpeta = filedialog.askdirectory(title="Seleccionar carpeta de destino")
        if carpeta:
            self.carpeta_destino = carpeta
            self.entry_destino.delete(0, tk.END)
            self.entry_destino.insert(0, carpeta)
            self.config['carpeta_destino'] = carpeta
            guardar_config(self.config)
    
    def cambiar_idioma(self, event=None):
        self.idioma = self.combo_idioma.get()
        self.config['idioma'] = self.idioma
        guardar_config(self.config)
    
    def configurar_api(self):
        api_key = pedir_api_key()
        if api_key and validar_api_key(api_key):
            self.config['api_key'] = api_key
            tmdb.API_KEY = api_key
            guardar_config(self.config)
            messagebox.showinfo("Éxito", "API Key configurada correctamente")
        else:
            messagebox.showerror("Error", "API Key inválida")
    
    def escanear_peliculas(self):
        if not self.carpeta_busqueda or not os.path.exists(self.carpeta_busqueda):
            messagebox.showerror("Error", "Selecciona una carpeta de búsqueda válida")
            return
        
        if self.procesando:
            return
        
        self.procesando = True
        self.btn_escanear.config(state=tk.DISABLED)
        self.progress.start()
        
        # Limpiar lista anterior
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        self.peliculas_lista = []
        self.status_var.set("Escaneando películas...")
        
        # Ejecutar en hilo separado
        threading.Thread(target=self._escanear_peliculas_thread, daemon=True).start()
    
    def _escanear_peliculas_thread(self):
        try:
            archivos_video = []
            for root, dirs, files in os.walk(self.carpeta_busqueda):
                for file in files:
                    if any(file.lower().endswith(ext) for ext in VIDEO_EXTS):
                        archivos_video.append(os.path.join(root, file))
            
            total_archivos = len(archivos_video)
            
            for i, ruta_completa in enumerate(archivos_video):
                nombre_archivo = os.path.basename(ruta_completa)
                nombre_limpio, año = extraer_info_archivo(nombre_archivo)
                
                self.root.after(0, self.status_var.set, f"Procesando {i+1}/{total_archivos}: {nombre_archivo}")
                
                # Verificar si ya está confirmado
                if ruta_completa in self.historial_confirmadas:
                    info_guardada = self.historial_confirmadas[ruta_completa]
                    pelicula_info = {
                        'archivo': ruta_completa,
                        'nombre_original': nombre_archivo,
                        'nombre_limpio': nombre_limpio,
                        'año_extraido': año,
                        'resultados_tmdb': [],
                        'mejor_resultado': info_guardada,
                        'color': 'confirmado',
                        'mensaje': f"Confirmado: {info_guardada.get('title', '')}",
                        'nombre_sugerido': generar_nombre_sugerido(info_guardada),
                        'seleccionado': False
                    }
                else:
                    # Detectar idioma basado en el nombre del archivo
                    idioma_detectado = self.detectar_idioma_pelicula(nombre_archivo)
                    
                    # Buscar en TMDb con idioma detectado
                    resultados = buscar_pelicula_tmdb(nombre_limpio, idioma_detectado, año)
                    color, mejor_resultado, mensaje = obtener_confianza_y_resultado(
                        nombre_archivo, nombre_limpio, año, resultados
                    )
                    
                    pelicula_info = {
                        'archivo': ruta_completa,
                        'nombre_original': nombre_archivo,
                        'nombre_limpio': nombre_limpio,
                        'año_extraido': año,
                        'resultados_tmdb': resultados,
                        'mejor_resultado': mejor_resultado,
                        'color': color,
                        'mensaje': mensaje,
                        'nombre_sugerido': generar_nombre_sugerido(mejor_resultado),
                        'seleccionado': False
                    }
                
                self.peliculas_lista.append(pelicula_info)
                self.root.after(0, self._agregar_a_lista, pelicula_info)
            
            self.root.after(0, self._finalizar_escaneo)
            
        except Exception as e:
            self.root.after(0, messagebox.showerror, "Error", f"Error durante el escaneo: {str(e)}")
            self.root.after(0, self._finalizar_escaneo)
    
    def _agregar_a_lista(self, pelicula_info):
        archivo = pelicula_info['nombre_original']
        titulo_encontrado = pelicula_info['mejor_resultado'].get('title', 'No encontrado') if pelicula_info['mejor_resultado'] else 'No encontrado'
        titulo_sugerido = pelicula_info['nombre_sugerido']
        año = pelicula_info['mejor_resultado'].get('release_date', '')[:4] if pelicula_info['mejor_resultado'] and pelicula_info['mejor_resultado'].get('release_date') else ''
        confianza = pelicula_info['color']
        estado = "✓" if pelicula_info['seleccionado'] else ""
        
        item = self.tree.insert('', 'end', values=(
            estado, archivo, titulo_encontrado, titulo_sugerido, año, confianza, pelicula_info['mensaje']
        ), tags=(pelicula_info['color'],))
        
        # Asociar el índice de la película con el item
        self.tree.set(item, 'seleccionar', len(self.peliculas_lista) - 1)
    
    def _finalizar_escaneo(self):
        self.procesando = False
        self.btn_escanear.config(state=tk.NORMAL)
        self.progress.stop()
        self.status_var.set(f"Escaneo completado: {len(self.peliculas_lista)} películas encontradas")
    
    def refrescar_lista(self):
        if not self.peliculas_lista:
            return
        
        # Limpiar lista visual
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Volver a agregar elementos actualizados
        for pelicula_info in self.peliculas_lista:
            self._agregar_a_lista(pelicula_info)
    
    def seleccionar_todas(self):
        for i, pelicula_info in enumerate(self.peliculas_lista):
            pelicula_info['seleccionado'] = True
        self.refrescar_lista()
    
    def deseleccionar_todas(self):
        for i, pelicula_info in enumerate(self.peliculas_lista):
            pelicula_info['seleccionado'] = False
        self.refrescar_lista()
    
    def seleccionar_por_color(self, color):
        for i, pelicula_info in enumerate(self.peliculas_lista):
            if pelicula_info['color'] == color:
                pelicula_info['seleccionado'] = True
        self.refrescar_lista()
    
    def eliminar_seleccionadas(self):
        self.peliculas_lista = [p for p in self.peliculas_lista if not p['seleccionado']]
        self.refrescar_lista()
        self.status_var.set(f"Lista actualizada: {len(self.peliculas_lista)} películas")
    
    def toggle_seleccion(self, event):
        """Toggle selección al hacer click en checkbox"""
        item = self.tree.selection()[0] if self.tree.selection() else None
        if item:
            # Obtener el índice de la película
            valores = self.tree.item(item, 'values')
            try:
                indice = int(valores[0]) if valores[0].isdigit() else None
                if indice is not None and 0 <= indice < len(self.peliculas_lista):
                    # Toggle selección
                    self.peliculas_lista[indice]['seleccionado'] = not self.peliculas_lista[indice]['seleccionado']
                    self.refrescar_lista()
            except:
                pass
    
    def seleccion_manual(self, event):
        """Selección manual de película al hacer doble click"""
        item = self.tree.selection()[0] if self.tree.selection() else None
        if not item:
            return
        
        # Obtener información de la película
        valores = self.tree.item(item, 'values')
        nombre_archivo = valores[1]
        
        # Buscar la película en nuestra lista
        pelicula_info = None
        for p in self.peliculas_lista:
            if p['nombre_original'] == nombre_archivo:
                pelicula_info = p
                break
        
        if not pelicula_info:
            return
        
        # Diálogo para buscar manualmente
        busqueda_manual = simpledialog.askstring(
            "Búsqueda Manual",
            f"Buscar película para: {nombre_archivo}\n\nEscribe parte del título:"
        )
        
        if not busqueda_manual:
            return
        
        # Buscar en TMDb con el texto ingresado
        resultados = buscar_pelicula_tmdb(busqueda_manual, self.idioma)
        
        if not resultados:
            messagebox.showwarning("Sin resultados", f"No se encontraron resultados para '{busqueda_manual}'")
            return
        
        # Mostrar diálogo de selección
        dialogo = DialogoSeleccion(self.root, resultados, f"Seleccionar película para: {nombre_archivo}")
        self.root.wait_window(dialogo.ventana)
        
        if dialogo.resultado:
            accion, valor = dialogo.resultado
            
            if accion == "seleccion":
                # Usuario seleccionó una película
                pelicula_seleccionada = resultados[valor]
                
                # Actualizar información
                pelicula_info['mejor_resultado'] = pelicula_seleccionada
                pelicula_info['color'] = 'confirmado'
                pelicula_info['mensaje'] = f"Confirmado: {pelicula_seleccionada.get('title', '')}"
                pelicula_info['nombre_sugerido'] = generar_nombre_sugerido(pelicula_seleccionada)
                pelicula_info['seleccionado'] = True
                
                # Guardar en historial
                self.historial_confirmadas[pelicula_info['archivo']] = pelicula_seleccionada
                guardar_historial(self.historial_confirmadas)
                
                # Actualizar lista visual
                self.refrescar_lista()
                
                # Renombrar automáticamente después de confirmar
                self.renombrar_pelicula(pelicula_info)
                
                messagebox.showinfo("Éxito", f"Película confirmada y renombrada: {pelicula_seleccionada.get('title', '')}")
            
            elif accion == "manual":
                # Usuario quiere buscar otra vez
                self.seleccion_manual(event)
    
    def renombrar_pelicula(self, pelicula_info):
        """Renombra una película individual"""
        if not pelicula_info['mejor_resultado'] or not pelicula_info['nombre_sugerido']:
            return False
        
        archivo_origen = pelicula_info['archivo']
        nombre_nuevo = pelicula_info['nombre_sugerido']
        carpeta_destino = self.entry_destino.get().strip() if self.entry_destino.get().strip() else None
        
        # Verificar que el archivo aún existe
        if not os.path.exists(archivo_origen):
            return False
        
        # Renombrar/mover archivo
        nuevo_path, mensaje = renombrar_archivo(archivo_origen, nombre_nuevo, carpeta_destino)
        
        if nuevo_path:
            # Actualizar información en la lista
            pelicula_info['archivo'] = nuevo_path
            pelicula_info['nombre_original'] = os.path.basename(nuevo_path)
            pelicula_info['seleccionado'] = False
            
            # Actualizar historial con nueva ruta
            if archivo_origen in self.historial_confirmadas:
                pelicula_data = self.historial_confirmadas[archivo_origen]
                del self.historial_confirmadas[archivo_origen]
                self.historial_confirmadas[nuevo_path] = pelicula_data
            
            # Guardar historial actualizado
            guardar_historial(self.historial_confirmadas)
            
            return True
        return False
    
    def renombrar_automatico(self):
        """Renombra automáticamente las películas seleccionadas"""
        seleccionadas = [p for p in self.peliculas_lista if p['seleccionado']]
        
        if not seleccionadas:
            messagebox.showwarning("Sin selección", "No hay películas seleccionadas para renombrar")
            return
        
        # Confirmar acción
        respuesta = messagebox.askyesno(
            "Confirmar renombrado",
            f"¿Renombrar {len(seleccionadas)} película(s) seleccionada(s)?"
        )
        
        if not respuesta:
            return
        
        exitosos = 0
        errores = 0
        
        for pelicula_info in seleccionadas:
            if self.renombrar_pelicula(pelicula_info):
                exitosos += 1
            else:
                errores += 1
        
        # Actualizar lista visual
        self.refrescar_lista()
        
        # Mostrar resultado
        mensaje_resultado = f"Renombrado completado:\n✓ {exitosos} exitosos\n✗ {errores} errores"
        
        if exitosos > 0:
            messagebox.showinfo("Renombrado completado", mensaje_resultado)
        else:
            messagebox.showerror("Error en renombrado", mensaje_resultado)
        
        self.status_var.set(f"Renombrado: {exitosos} exitosos, {errores} errores")

def main():
    root = tk.Tk()
    app = OrganizadorPeliculas(root)
    root.mainloop()

if __name__ == "__main__":
    main()