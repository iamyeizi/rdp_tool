import tkinter as tk
from tkinter import ttk
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from pythonping import ping
import threading
import subprocess
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
import ipaddress
import socket
import logging
from functools import partial

# Configuración de logging
logging.basicConfig(
    filename='itool.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='a'
)

# También mostrar logs en consola
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logging.getLogger().addHandler(console_handler)

# --- Configuración Google Sheets ---
SCOPE = ['https://spreadsheets.google.com/feeds',
         'https://www.googleapis.com/auth/drive']
CREDS = ServiceAccountCredentials.from_json_keyfile_name(
    os.path.join(os.path.expanduser("~"), '.gsheet-creds.json'), SCOPE)
gc = gspread.authorize(CREDS)
sheet = gc.open('bd_pcs').sheet1  # Cambia por el nombre de tu sheet

# --- Optimización de la lectura de Google Sheets ---
def get_pc_list():
    try:
        logging.info("Obteniendo datos de Google Sheets...")
        data = sheet.get_all_records()
        logging.info(f"Datos obtenidos: {len(data)} registros")
        return data
    except Exception as e:
        logging.error(f"Error al leer Google Sheets: {e}")
        print(f"Error al leer Google Sheets: {e}")
        return []

# --- Validación de direcciones IP ---
def is_valid_ip(ip):
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

# --- Ping asincrónico con manejo de PCs sin IP ---
async def async_ping(ip):
    if not ip:
        return False

    if not is_valid_ip(ip):
        return False

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        try:
            response = await loop.run_in_executor(executor, ping, ip, 1, 1)
            return response.success()
        except Exception as e:
            logging.debug(f"Error al hacer ping a {ip}: {e}")
            return False

async def update_leds_async(leds, app_instance):
    if not leds:
        return

    # Separar IPs que necesitan ping de las que ya están en cache
    tasks = []
    cached_results = []

    for led, ip in leds:
        if not ip:
            cached_results.append((led, False))
        elif app_instance.is_cache_valid(ip) and ip in app_instance.ping_cache:
            # Usar resultado del cache
            cached_results.append((led, app_instance.ping_cache[ip]))
        else:
            # Necesita ping
            tasks.append((led, ip, async_ping(ip)))

    # Ejecutar solo los pings necesarios
    if tasks:
        ping_results = await asyncio.gather(*[task[2] for task in tasks])
        for (led, ip, _), result in zip(tasks, ping_results):
            app_instance.ping_cache[ip] = result
            app_instance.update_cache_timestamp(ip)
            cached_results.append((led, result))

    # Aplicar todos los resultados
    for led, online in cached_results:
        if not led.winfo_exists():  # Verificar que el widget aún existe
            continue
        led.config(fg="green" if online else "red")

async def async_is_port_open(ip, port):
    """Verifica asincrónicamente si un puerto específico está abierto en una IP dada."""
    if not ip or not is_valid_ip(ip):
        return False

    def check_port():
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(3)
                result = s.connect_ex((ip, port))
                return result == 0
        except Exception:
            return False

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        try:
            result = await loop.run_in_executor(executor, check_port)
            return result
        except Exception as e:
            logging.debug(f"Error al verificar el puerto {port} en {ip}: {e}")
            return False

async def update_ssh_buttons_async(buttons, app_instance):
    """Actualiza los botones SSH según la disponibilidad del puerto 22."""
    if not buttons:
        return

    # Separar botones que necesitan verificación de los que están en cache
    tasks = []
    cached_results = []

    for button, ip in buttons:
        if not ip:
            cached_results.append((button, False))
        elif app_instance.is_cache_valid(ip) and ip in app_instance.ssh_port_cache:
            # Usar resultado del cache
            cached_results.append((button, app_instance.ssh_port_cache[ip]))
        else:
            # Necesita verificación
            tasks.append((button, ip, async_is_port_open(ip, 22)))

    # Ejecutar solo las verificaciones necesarias
    if tasks:
        port_results = await asyncio.gather(*[task[2] for task in tasks])
        for (button, ip, _), result in zip(tasks, port_results):
            app_instance.ssh_port_cache[ip] = result
            app_instance.update_cache_timestamp(ip)
            cached_results.append((button, result))

    # Aplicar todos los resultados
    for button, port_open in cached_results:
        if not button.winfo_exists():  # Verificar que el widget aún existe
            continue
        if port_open:
            button.config(state="normal", text="SSH")
        else:
            button.config(state="disabled", text="✗")

async def update_rdp_buttons_async(buttons, app_instance):
    """Actualiza los botones RDP según la disponibilidad del puerto 3389."""
    if not buttons:
        return

    # Separar botones que necesitan verificación de los que están en cache
    tasks = []
    cached_results = []

    for button, ip in buttons:
        if not ip:
            cached_results.append((button, False))
        elif app_instance.is_cache_valid(ip) and ip in app_instance.rdp_port_cache:
            # Usar resultado del cache
            cached_results.append((button, app_instance.rdp_port_cache[ip]))
        else:
            # Necesita verificación
            tasks.append((button, ip, async_is_port_open(ip, 3389)))

    # Ejecutar solo las verificaciones necesarias
    if tasks:
        port_results = await asyncio.gather(*[task[2] for task in tasks])
        for (button, ip, _), result in zip(tasks, port_results):
            app_instance.rdp_port_cache[ip] = result
            app_instance.update_cache_timestamp(ip)
            cached_results.append((button, result))

    # Aplicar todos los resultados
    for button, port_open in cached_results:
        if not button.winfo_exists():  # Verificar que el widget aún existe
            continue
        # Solo habilitar si el puerto está abierto
        if port_open:
            button.config(state="normal")
            # Restaurar texto original según el botón
            if "Espejo" in button.cget('text') or button.cget('text') == "✗":
                button.config(text="Espejo")
            elif "Normal" in button.cget('text') or button.cget('text') == "✗":
                button.config(text="Normal")
        else:
            button.config(state="disabled")
            # Agregar ✗ según el tipo de botón
            if "Espejo" in button.cget('text') or button.cget('text') == "✗":
                button.config(text="✗")
            elif "Normal" in button.cget('text') or button.cget('text') == "✗":
                button.config(text="✗")

class ItoolApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Itool")
        self.pc_list = []
        self.filtered_list = []
        self.leds = []
        self.ssh_buttons = []
        self.rdp_buttons = []  # Para trackear botones RDP
        self.filter_timer = None   # Para debounce del filtro
        self.sort_column = None    # Columna actual de ordenamiento
        self.sort_ascending = True # Dirección del ordenamiento
        self.window_size_set = False  # Flag para evitar múltiples ajustes de ventana

        # Cache para resultados de ping y puertos
        self.ping_cache = {}       # IP -> bool (ping result)
        self.ssh_port_cache = {}   # IP -> bool (port 22)
        self.rdp_port_cache = {}   # IP -> bool (port 3389)
        self.cache_timeout = 30    # Segundos antes de invalidar cache
        self.last_check_time = {}  # IP -> timestamp

        # Hacer que la ventana no sea redimensionable
        self.resizable(False, False)

        self.create_widgets()
        self.refresh_data()
        self.update_leds()

    def create_widgets(self):
        # Frame principal para organizar la interfaz
        main_frame = tk.Frame(self)
        main_frame.pack(fill='both', expand=True, padx=10, pady=5)

        # Buscador y botones arriba (FIJO)
        search_frame = tk.Frame(main_frame)
        search_frame.pack(fill='x', pady=(0, 5), expand=False)
        self.search_var = tk.StringVar()
        tk.Label(search_frame, text="Filtrar:").pack(side='left')
        search_entry = tk.Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(side='left', fill='x', expand=True, padx=5)
        # Usar debounce para el filtro - solo filtrar después de 500ms sin escribir
        search_entry.bind('<KeyRelease>', self.on_search_change)
        search_entry.bind('<Return>', lambda e: self.apply_filter())
        search_entry.bind('<Escape>', lambda e: self.clear_filter())
        tk.Button(search_frame, text="🔍", command=self.apply_filter).pack(side='left', padx=2)
        tk.Button(search_frame, text="🔄", command=self.refresh_data).pack(side='left', padx=2)

        # Frame para headers (FIJO)
        self.headers_frame = tk.Frame(main_frame, bg='lightgray')
        self.headers_frame.pack(fill='x', pady=(0, 2), expand=False)

        # Canvas con scroll para el grid (SCROLLEABLE)
        container = tk.Frame(main_frame)
        container.pack(fill='both', expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(container, borderwidth=0)
        self.scrollbar = tk.Scrollbar(
            container, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )

        self.canvas.create_window(
            (0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        # Bind para scroll con rueda del mouse
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)

        # Crear headers fijos
        self.create_fixed_headers()

    def is_cache_valid(self, ip):
        """Verifica si el cache para una IP sigue siendo válido"""
        import time
        if ip not in self.last_check_time:
            return False
        return time.time() - self.last_check_time[ip] < self.cache_timeout

    def update_cache_timestamp(self, ip):
        """Actualiza el timestamp del cache para una IP"""
        import time
        self.last_check_time[ip] = time.time()

    def create_fixed_headers(self):
        """Crea los headers fijos que no se mueven al hacer scroll"""
        # Limpiar headers existentes
        for widget in self.headers_frame.winfo_children():
            widget.destroy()

        headers = ["Titular", "Host", "IP", "Ping", "Espejo", "Normal", "SSH"]
        header_keys = ["titular", "hostname", "ip", "", "", "", ""]  # Keys para ordenamiento

        for col, (h, key) in enumerate(zip(headers, header_keys)):
            if key:  # Solo las columnas con datos son clickeables
                # Mostrar indicador de ordenamiento
                text = h
                if self.sort_column == key:
                    text += " ↓" if self.sort_ascending else " ↑"

                header_label = tk.Label(self.headers_frame, text=text, font=("Arial", 10, "bold"),
                                        bg='lightblue' if self.sort_column == key else 'lightgray',
                                        relief='raised', bd=1, cursor="hand2", anchor='w')
                header_label.bind("<Button-1>", lambda e, column=key: self.sort_by_column(column))
            else:
                header_label = tk.Label(self.headers_frame, text=h, font=("Arial", 10, "bold"),
                                        bg='lightgray', relief='raised', bd=1, anchor='w')

            header_label.grid(row=0, column=col, padx=2, pady=1, sticky="nsew")

        # Configurar el peso de la fila
        self.headers_frame.grid_rowconfigure(0, weight=1)

    def sort_by_column(self, column):
        """Ordena la lista por la columna especificada"""
        logging.info(f"Ordenando por columna: {column}")

        # Si ya estamos ordenando por esta columna, cambiar dirección
        if self.sort_column == column:
            self.sort_ascending = not self.sort_ascending
        else:
            self.sort_column = column
            self.sort_ascending = True

        # Ordenar la lista filtrada
        try:
            self.filtered_list.sort(
                key=lambda x: str(x.get(column, '')).lower(),
                reverse=not self.sort_ascending
            )
            logging.debug(f"Lista ordenada por {column}, ascendente: {self.sort_ascending}")

            # Actualizar headers para mostrar el indicador de ordenamiento
            self.create_fixed_headers()

            # Actualizar la visualización
            self.update_grid_display()

        except Exception as e:
            logging.error(f"Error al ordenar por {column}: {e}")

    def _on_mousewheel(self, event):
        """Permite scroll con la rueda del mouse"""
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def on_search_change(self, event):
        """Implementa debounce para el filtro"""
        if self.filter_timer:
            self.after_cancel(self.filter_timer)
        self.filter_timer = self.after(500, self.apply_filter)  # Espera 500ms antes de filtrar

    def apply_filter(self):
        """Aplica el filtro después del debounce"""
        query = self.search_var.get().lower().strip()
        logging.info(f"Aplicando filtro: '{query}'")
        if not query:
            self.filtered_list = self.pc_list.copy()
        else:
            self.filtered_list = [
                pc for pc in self.pc_list
                if query in str(pc.get('hostname', '')).lower()
                or query in str(pc.get('ip', '')).lower()
                or query in str(pc.get('titular', '')).lower()
            ]
        logging.debug(f"Resultados del filtro: {len(self.filtered_list)} PCs")
        self.update_grid_display()

    def refresh_data(self):
        logging.info("Refrescando datos desde Google Sheets")
        try:
            self.pc_list = get_pc_list()
            self.filtered_list = self.pc_list.copy()
            logging.debug(f"Datos cargados: {len(self.pc_list)} PCs")
            self.create_grid()
            # Solo ajustar ventana la primera vez o cuando se refresca completamente
            if not self.window_size_set:
                self.adjust_window_to_content()
                self.window_size_set = True
        except Exception as e:
            logging.error(f"Error al refrescar datos: {e}")

    def clear_filter(self):
        logging.info("Limpiando filtro")
        self.search_var.set("")
        self.filtered_list = self.pc_list.copy()
        self.update_grid_display()

    def adjust_window_to_content(self):
        """Ajusta la ventana al contenido - ancho fijo basado en contenido, alto para máximo 20 filas"""
        self.update_idletasks()

        # Calcular el ancho necesario basado en el contenido más largo de cada columna
        column_widths = self.calculate_column_widths()
        total_width = sum(column_widths) + 60  # +60 para márgenes, padding y scrollbar

        # Altura fija para siempre 20 filas
        row_height = 30  # Altura por fila
        base_height = 120  # Para filtro, headers y márgenes
        content_height = 20 * row_height  # SIEMPRE 20 filas
        total_height = base_height + content_height

        # Centrar la ventana en la pantalla
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - total_width) // 2
        y = (screen_height - total_height) // 2

        # Configurar el tamaño mínimo y máximo para evitar redimensionamiento en ancho
        self.minsize(total_width, total_height)
        self.maxsize(total_width, total_height)  # Fijar también la altura

        self.geometry(f"{total_width}x{total_height}+{x}+{y}")
        logging.debug(f"Ventana ajustada a: {total_width}x{total_height} en posición {x},{y}")

    def calculate_column_widths(self):
        """Calcula el ancho óptimo para cada columna basado en su contenido"""
        headers = ["Titular", "Host", "IP", "Ping", "Espejo", "Normal", "SSH"]
        column_widths = []

        for col, header in enumerate(headers):
            max_length = len(header)  # Empezar con la longitud del header

            # Buscar el contenido más largo en cada columna usando TODA la lista, no solo filtrada
            if col == 0:  # Titular
                for pc in self.pc_list:  # Usar pc_list completa en lugar de filtered_list
                    max_length = max(max_length, len(str(pc.get('titular', ''))))
            elif col == 1:  # Host
                for pc in self.pc_list:
                    max_length = max(max_length, len(str(pc.get('hostname', ''))))
            elif col == 2:  # IP
                for pc in self.pc_list:
                    max_length = max(max_length, len(str(pc.get('ip', ''))))
            elif col == 3:  # Ping (solo el LED)
                max_length = 4  # Ancho fijo para el LED
            elif col in [4, 5, 6]:  # Botones
                max_length = max(max_length, 8)  # Ancho mínimo para botones

            # Convertir caracteres a píxeles (aproximado: 1 carácter = 8 píxeles)
            # Reducir el padding para evitar espacio extra
            width_pixels = max_length * 8 + 15  # +15 para padding
            column_widths.append(width_pixels)

        return column_widths

    def sync_column_widths(self):
        """Sincroniza el ancho de las columnas entre headers y contenido basado en contenido"""
        try:
            self.update_idletasks()

            # Calcular anchos óptimos basados en contenido
            column_widths = self.calculate_column_widths()

            # Aplicar el ancho calculado a todas las columnas
            for col, width in enumerate(column_widths):
                self.headers_frame.grid_columnconfigure(col, minsize=width, weight=0)
                self.scrollable_frame.grid_columnconfigure(col, minsize=width, weight=0)

        except Exception as e:
            logging.debug(f"Error al sincronizar anchos de columna: {e}")

    def update_grid_display(self):
        """Actualiza la visualización del grid alineada con los headers"""
        logging.info("Actualizando visualización del grid")
        # Limpiar todas las filas existentes
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        # Reiniciar seguimiento
        self.leds.clear()
        self.ssh_buttons.clear()
        self.rdp_buttons.clear()

        # Crear cada celda directamente en scrollable_frame para alinear columnas
        for row, pc in enumerate(self.filtered_list):
            # Titular
            tk.Label(self.scrollable_frame, text=pc.get('titular', ''), anchor='w',
                    bg='white' if row % 2 == 0 else '#f0f0f0').grid(row=row, column=0, padx=2, sticky='nsew')
            # Host
            tk.Label(self.scrollable_frame, text=pc.get('hostname', ''), anchor='w',
                    bg='white' if row % 2 == 0 else '#f0f0f0').grid(row=row, column=1, padx=2, sticky='nsew')
            # IP
            tk.Label(self.scrollable_frame, text=pc.get('ip', ''), anchor='w',
                    bg='white' if row % 2 == 0 else '#f0f0f0').grid(row=row, column=2, padx=2, sticky='nsew')
            # LED Ping
            led = tk.Label(self.scrollable_frame, text='●', fg='grey', font=('Arial', 12),
                          bg='white' if row % 2 == 0 else '#f0f0f0')
            led.grid(row=row, column=3, padx=2, sticky='nsew')
            self.leds.append((led, pc.get('ip', '')))
            # Botón Espejo
            btn_espejo = tk.Button(self.scrollable_frame, text='Espejo',
                                   command=partial(self.connect_remoto, pc.get('ip', '')))
            btn_espejo.grid(row=row, column=4, padx=2, sticky='nsew')
            self.rdp_buttons.append((btn_espejo, pc.get('ip', '')))  # Trackear para verificar puerto

            # Botón Normal
            btn_normal = tk.Button(self.scrollable_frame, text='Normal',
                                   command=partial(self.connect_login_remoto, pc))
            btn_normal.grid(row=row, column=5, padx=2, sticky='nsew')
            self.rdp_buttons.append((btn_normal, pc.get('ip', '')))  # Trackear para verificar puerto
            # Botón SSH
            btn_ssh = tk.Button(self.scrollable_frame, text='✗', state='disabled',
                                 command=partial(self.connect_ssh, pc))
            btn_ssh.grid(row=row, column=6, padx=2, sticky='nsew')
            self.ssh_buttons.append((btn_ssh, pc.get('ip', '')))

            # Configurar el peso de cada fila
            self.scrollable_frame.grid_rowconfigure(row, weight=1)

        # Actualizar botones SSH y RDP en segundo plano
        if self.ssh_buttons:
            threading.Thread(target=self.update_ssh_buttons_threaded, daemon=True).start()
        if self.rdp_buttons:
            threading.Thread(target=self.update_rdp_buttons_threaded, daemon=True).start()

        # Solo sincronizar columnas, NO ajustar ventana en cada actualización
        self.after(100, self.sync_column_widths)

    def create_grid(self):
        """Inicializa el grid básico"""
        logging.info("Inicializando grid de PCs")

        # Limpiar cualquier widget existente
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        self.leds.clear()
        self.ssh_buttons.clear()
        self.rdp_buttons.clear()

        # Actualizar headers fijos
        self.create_fixed_headers()

        # Actualizar la visualización con las PCs
        self.update_grid_display()

    def update_ssh_buttons_threaded(self):
        """Actualiza botones SSH en un hilo separado"""
        try:
            asyncio.run(update_ssh_buttons_async(self.ssh_buttons, self))
        except Exception as e:
            logging.error(f"Error al actualizar botones SSH: {e}")

    def update_rdp_buttons_threaded(self):
        """Actualiza botones RDP en un hilo separado"""
        try:
            asyncio.run(update_rdp_buttons_async(self.rdp_buttons, self))
        except Exception as e:
            logging.error(f"Error al actualizar botones RDP: {e}")

    def update_leds(self):
        if self.leds:
            try:
                asyncio.run(update_leds_async(self.leds, self))
            except Exception as e:
                logging.error(f"Error al actualizar LEDs: {e}")
        self.after(10 * 1000, self.update_leds)

    def connect_remoto(self, ip):
        """Ejecuta mstsc en modo espejo usando la IP"""
        if not ip:
            logging.warning("No se puede conectar: IP vacía")
            return

        logging.info(f"Conectando en modo espejo a {ip}")
        comando = [
            'mstsc',
            '/shadow:1',
            f'/v:{ip}',
            '/control',
            '/noConsentPrompt'
        ]
        subprocess.Popen(comando)

    def connect_login_remoto(self, pc):
        """Conecta usando credenciales del PC"""
        if not pc.get('ip', '') or not pc.get('usuario', '') or not pc.get('contrasenia', ''):
            logging.warning("Datos incompletos para conexión normal")
            return

        ip = pc["ip"]
        logging.info(f"Conectando normalmente a {ip}")

        # Guarda las credenciales en el Administrador de Credenciales de Windows
        subprocess.call([
            'cmdkey',
            f'/add:TERMSRV/{ip}',
            f'/user:{pc["usuario"]}',
            f'/pass:{pc["contrasenia"]}'
        ])

        try:
            with open('template.rdp', 'r', encoding='utf-16') as f:
                lines = f.readlines()
        except FileNotFoundError:
            logging.error("Archivo template.rdp no encontrado")
            return

        new_lines = []
        username_set = False
        for line in lines:
            if line.strip().startswith('full address:s:'):
                new_lines.append(f'full address:s:{ip}\r\n')
            elif line.strip().startswith('username:s:'):
                new_lines.append(f'username:s:{pc["usuario"]}\r\n')
                username_set = True
            elif line.strip().startswith('prompt for credentials:i:'):
                new_lines.append('prompt for credentials:i:0\r\n')
            elif line.strip().startswith('promptcredentialonce:i:'):
                new_lines.append('promptcredentialonce:i:1\r\n')
            else:
                new_lines.append(line)

        if not username_set:
            new_lines.append(f'username:s:{pc["usuario"]}\r\n')
            new_lines.append('prompt for credentials:i:0\r\n')
            new_lines.append('promptcredentialonce:i:1\r\n')

        temp_rdp = f'{pc.get("hostname", "pc")}.rdp'
        with open(temp_rdp, 'w', encoding='utf-16') as f:
            f.writelines(new_lines)

        subprocess.Popen(['mstsc', temp_rdp])
        threading.Timer(10, lambda: os.remove(temp_rdp) if os.path.exists(temp_rdp) else None).start()
        # Borrar credenciales
        threading.Timer(60, lambda: subprocess.call([
            'cmdkey', f'/delete:TERMSRV/{ip}'
        ])).start()

    def connect_ssh(self, pc):
        """Conecta por SSH"""
        if not pc or not pc.get('ip', ''):
            return

        ip = pc.get('ip', '')
        usuario = pc.get('usuario', 'admin')
        contrasenia = pc.get('contrasenia', '')

        # Generar nombre único para el archivo BAT
        unique_id = uuid.uuid4().hex[:8]
        temp_dir = tempfile.gettempdir()
        bat_filename = os.path.join(temp_dir, f"connect_ssh_{unique_id}.bat")

        # Contenido del BAT
        bat_content = f"""@echo off
    chcp 65001 > nul
    echo.
    echo CONTRASEÑA: {contrasenia}
    echo.
    ssh {usuario}@{ip} -p {ssh_port}
    echo.
    pause
    del "%~f0"
    """

        # Guardar archivo BAT
        with open(bat_filename, "w", encoding="utf-8") as f:
            f.write(bat_content)

        # Ejecutar en nueva ventana CMD
        comando = ["cmd.exe", "/c", f"start cmd /k {bat_filename}"]

        subprocess.Popen(comando)

if __name__ == "__main__":
    logging.info("Iniciando Itool")
    app = ItoolApp()
    app.mainloop()
