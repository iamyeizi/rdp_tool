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
        # Limitar el rango de datos si es posible
        data = sheet.get_all_records()[:116]  # Limitar a 116 filas
        return data
    except Exception as e:
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
        print("PC sin dirección IP")
        return False

    if not is_valid_ip(ip):
        print(f"Dirección IP inválida: {ip}")
        return False

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        try:
            response = await loop.run_in_executor(executor, ping, ip, 1, 1)
            return response.success()
        except Exception as e:
            print(f"Error al hacer ping a {ip}: {e}")
            return False

async def update_leds_async(leds):
    tasks = [async_ping(ip) for _, ip in leds if ip]
    results = await asyncio.gather(*tasks)
    for (led, ip), online in zip(leds, results):
        if not ip:
            led.config(fg="grey")  # Indicar que no hay IP
        else:
            led.config(fg="green" if online else "red")


class RDPApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("RDP Tool")
        self.geometry("450x400")
        self.pc_list = []
        self.filtered_list = []
        self.leds = []
        self.create_widgets()
        self.refresh_data()
        self.update_leds()

    def create_widgets(self):
        # Buscador y botones arriba
        search_frame = tk.Frame(self)
        search_frame.pack(fill='x', padx=10, pady=5, expand=False)
        self.search_var = tk.StringVar()
        tk.Label(search_frame, text="Filtrar:").pack(side='left')
        search_entry = tk.Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(side='left', fill='x', expand=True, padx=5)
        search_entry.bind('<KeyRelease>', lambda e: self.filter_grid())
        tk.Button(search_frame, text="🔎", command=self.refresh_data).pack(
            side='left', padx=5)

        # Canvas con scroll para el grid
        container = tk.Frame(self)
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

        self.bind('<Configure>', self._on_resize)

    def _on_resize(self, event):
        # Ajusta el ancho del canvas al tamaño de la ventana
        self.canvas.config(width=event.width)

    def refresh_data(self):
        self.pc_list = get_pc_list()
        self.filtered_list = self.pc_list.copy()
        self.create_grid()

    def filter_grid(self):
        query = self.search_var.get().lower().strip()
        if not query:
            self.filtered_list = self.pc_list.copy()
        else:
            self.filtered_list = [
                pc for pc in self.pc_list
                if query in str(pc.get('hostname', '')).lower()
                or query in str(pc.get('ip', '')).lower()
                or query in str(pc.get('titular', '')).lower()
            ]
        self.create_grid()

    def adjust_window_size(self):
        self.update_idletasks()  # Asegura que los widgets estén actualizados
        # margen para scrollbar y bordes
        req_width = self.scrollable_frame.winfo_reqwidth() + 40
        # margen para buscador y bordes
        req_height = self.scrollable_frame.winfo_reqheight() + 80

        max_width = self.winfo_screenwidth()
        max_height = self.winfo_screenheight()

        final_width = min(req_width, max_width)
        final_height = min(req_height, max_height)

        self.geometry(f"{final_width}x{final_height}")

    def create_grid(self):
        if not hasattr(self, 'grid_widgets'):
            self.grid_widgets = []

        headers = ["Titular", "Host", "IP", "Ping", "Espejo", "Normal"]
        if not self.grid_widgets:
            for col, h in enumerate(headers):
                tk.Label(self.scrollable_frame, text=h, font=("Arial", 10, "bold")).grid(
                    row=0, column=col, padx=5, pady=2, sticky="ew"
                )
                self.scrollable_frame.grid_columnconfigure(col, weight=1)

        for idx, pc in enumerate(self.filtered_list):
            row = idx + 1
            if len(self.grid_widgets) <= idx:
                self.grid_widgets.append([])

            widgets = self.grid_widgets[idx]
            if not widgets:
                widgets.append(tk.Label(self.scrollable_frame, text=pc.get('titular', '')))
                widgets.append(tk.Label(self.scrollable_frame, text=pc.get('hostname', '')))
                widgets.append(tk.Label(self.scrollable_frame, text=pc.get('ip', '')))
                led = tk.Label(self.scrollable_frame, text="●", fg="grey", font=("Arial", 12))
                widgets.append(led)
                widgets.append(tk.Button(self.scrollable_frame, text="Conectar", command=lambda ip=pc.get('ip', ''): self.connect_remoto(ip)))
                widgets.append(tk.Button(self.scrollable_frame, text="Conectar", command=lambda pc=pc: self.connect_login_remoto(pc)))

            for col, widget in enumerate(widgets):
                widget.grid(row=row, column=col, padx=5, pady=2, sticky="ew")

            self.leds.append((widgets[3], pc.get('ip', '')))

        self.adjust_window_size()

    def update_leds(self):
        asyncio.run(update_leds_async(self.leds))
        self.after(10 * 1000, self.update_leds)
        # Refresca el grid cada 1 minuto para nuevas PCs
        # self.after(60 * 1000, self.refresh_data)

    def connect_remoto(self, ip):
        # Ejecuta mstsc en modo espejo usando la IP
        if not ip:
            return
        comando = [
            'mstsc',
            '/shadow:1',
            f'/v:{ip}',
            '/control',
            '/noConsentPrompt'
        ]
        subprocess.Popen(comando)

    def connect_login_remoto(self, pc):
        if not pc.get('ip', '') or not pc.get('usuario', '') or not pc.get('contrasenia', ''):
            return

        # Guarda las credenciales en el Administrador de Credenciales de Windows
        subprocess.call([
            'cmdkey',
            f'/add:TERMSRV/{pc["ip"]}',
            f'/user:{pc["usuario"]}',
            f'/pass:{pc["contrasenia"]}'
        ])

        with open('template.rdp', 'r', encoding='utf-16') as f:
            lines = f.readlines()

        new_lines = []
        username_set = False
        for line in lines:
            if line.strip().startswith('full address:s:'):
                new_lines.append(f'full address:s:{pc["ip"]}\r\n')
            elif line.strip().startswith('username:s:'):
                new_lines.append(f'username:s:{pc["usuario"]}\r\n')
                username_set = True
            elif line.strip().startswith('prompt for credentials:i:'):
                # No pedir credenciales
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
        threading.Timer(10, lambda: os.remove(temp_rdp)).start()
        # Borrar credenciales
        threading.Timer(60, lambda: subprocess.call([
            'cmdkey', f'/delete:TERMSRV/{pc["ip"]}'
        ])).start()


if __name__ == "__main__":
    app = RDPApp()
    app.mainloop()
