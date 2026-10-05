"""
Teclado griego flotante (Windows, macOS y Linux).

- Queda siempre por encima de las demás ventanas.
- Intenta no quitarle el foco a la aplicación en la que se escribe.
- Al hacer clic en una letra, la escribe donde esté el cursor.
- Se mueve arrastrando la barra superior (sin salirse de la pantalla).
- Recuerda la última posición y la última pestaña usadas.
- El botón "–" lo minimiza a la barra de tareas, como una ventana común;
  se restaura haciendo clic en su ícono de la barra de tareas. La "x" lo cierra.
- Si no puede escribir, avisa en pantalla y copia el símbolo al portapapeles.

Windows: no requiere nada adicional.
macOS / Linux: requiere "pynput" (pip install pynput).
"""

import json
import os
import sys
import tkinter as tk

VERSION = "1.2"
NOMBRE_APP = "TecladoGriego"
SISTEMA = sys.platform  # "win32", "darwin" o "linux"


class ErrorEscritura(Exception):
    """No se pudo escribir el carácter en la aplicación activa."""


# ---------------------------------------------------------------------------
# Escritura de caracteres en la aplicación activa
# ---------------------------------------------------------------------------
if SISTEMA == "win32":
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    INPUT_KEYBOARD = 1
    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_UNICODE = 0x0004
    GWL_EXSTYLE = -20
    WS_EX_NOACTIVATE = 0x08000000
    WS_EX_TOPMOST = 0x00000008
    GA_ROOT = 2
    ERROR_ALREADY_EXISTS = 183
    ULONG_PTR = ctypes.c_size_t

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                    ("dwExtraInfo", ULONG_PTR)]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                    ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                    ("wParamH", wintypes.WORD)]

    class _INPUT_UNION(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("u", _INPUT_UNION)]

    user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetAncestor.restype = wintypes.HWND
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongW.restype = ctypes.c_long
    user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
    user32.SetWindowLongW.restype = ctypes.c_long
    user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
    user32.SendInput.restype = wintypes.UINT

    def escribir(texto):
        for caracter in texto:
            codigo = ord(caracter)
            entradas = (INPUT * 2)()
            entradas[0].type = INPUT_KEYBOARD
            entradas[0].u.ki = KEYBDINPUT(0, codigo, KEYEVENTF_UNICODE, 0, 0)
            entradas[1].type = INPUT_KEYBOARD
            entradas[1].u.ki = KEYBDINPUT(0, codigo, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, 0)
            enviados = user32.SendInput(2, entradas, ctypes.sizeof(INPUT))
            if enviados != 2:
                raise ErrorEscritura("Windows rechazó la entrada de teclado.")

    def evitar_foco(raiz):
        hwnd = user32.GetAncestor(raiz.winfo_id(), GA_ROOT) or raiz.winfo_id()
        estilo = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, estilo | WS_EX_NOACTIVATE | WS_EX_TOPMOST)

    def activar_dpi():
        """Evita que Windows estire (y desenfoque) la ventana en pantallas con zoom."""
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                user32.SetProcessDPIAware()
            except Exception:
                pass

    _mutex = None  # se conserva para que Windows no libere el bloqueo

    def instancia_unica():
        """True si es la única copia abierta; False si ya hay otra ejecutándose."""
        global _mutex
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
            kernel32.CreateMutexW.restype = wintypes.HANDLE
            _mutex = kernel32.CreateMutexW(None, False, "Local\\" + NOMBRE_APP)
            return ctypes.get_last_error() != ERROR_ALREADY_EXISTS
        except Exception:
            return True  # si no se puede comprobar, se deja abrir

    def avisar_ya_abierto():
        user32.MessageBoxW(None, "El Teclado griego ya está abierto.\n\n"
                           "Si no lo ve, búsquelo en la barra de tareas.",
                           "Teclado griego", 0x40)

    def limites_virtuales(raiz):
        """Rectángulo que abarca todos los monitores: (x0, y0, x1, y1)."""
        x, y = user32.GetSystemMetrics(76), user32.GetSystemMetrics(77)
        ancho, alto = user32.GetSystemMetrics(78), user32.GetSystemMetrics(79)
        if ancho <= 0 or alto <= 0:
            return None
        return x, y, x + ancho, y + alto

    FUENTE = "Segoe UI"
    ATAJO_PEGAR = "Ctrl+V"

else:
    _teclado = None

    def escribir(texto):
        global _teclado
        try:
            if _teclado is None:
                from pynput.keyboard import Controller
                _teclado = Controller()
            _teclado.type(texto)
        except Exception as error:  # permisos, Wayland, etc.
            raise ErrorEscritura(str(error) or error.__class__.__name__) from error

    def evitar_foco(raiz):
        # En Linux (X11), las ventanas sin borde no reciben el foco al hacer clic.
        # En macOS se intenta marcar la ventana como "no activable".
        if SISTEMA == "darwin":
            try:
                raiz.tk.call("::tk::unsupported::MacWindowStyle", "style",
                             raiz._w, "plain", "noActivates")
            except tk.TclError:
                pass

    def limites_virtuales(raiz):
        """Rectángulo de pantalla: (x0, y0, x1, y1). En Mac no se limita."""
        if SISTEMA == "darwin":
            return None  # no se detectan de forma fiable varias pantallas
        return 0, 0, raiz.winfo_screenwidth(), raiz.winfo_screenheight()

    FUENTE = "Helvetica Neue" if SISTEMA == "darwin" else "DejaVu Sans"
    ATAJO_PEGAR = "Cmd+V" if SISTEMA == "darwin" else "Ctrl+V"


# ---------------------------------------------------------------------------
# Comprobaciones al iniciar (macOS y Linux)
# ---------------------------------------------------------------------------
def accesibilidad_concedida():
    """macOS: ¿tiene el programa el permiso de Accesibilidad?"""
    try:
        import ctypes
        biblioteca = ctypes.cdll.LoadLibrary(
            "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
        biblioteca.AXIsProcessTrusted.restype = ctypes.c_bool
        return bool(biblioteca.AXIsProcessTrusted())
    except Exception:
        return True  # si no se puede comprobar, no se molesta al usuario


def avisos_de_entorno():
    """Lista de avisos para mostrar al iniciar (vacía si todo está en orden)."""
    avisos = []
    if SISTEMA == "linux":
        sesion = os.environ.get("XDG_SESSION_TYPE", "").lower()
        if sesion == "wayland" or os.environ.get("WAYLAND_DISPLAY"):
            avisos.append("Está usando Wayland: el teclado puede no escribir en algunas "
                          "aplicaciones. Inicie sesión con Xorg/X11 o pegue el símbolo "
                          "con " + ATAJO_PEGAR + ".")
        try:
            import pynput.keyboard  # noqa: F401
        except Exception:
            avisos.append("Falta el componente «pynput», necesario para escribir. "
                          "Instálelo con: pip install pynput")
    elif SISTEMA == "darwin":
        if not accesibilidad_concedida():
            avisos.append("Falta el permiso de Accesibilidad. Actívelo en Ajustes del "
                          "Sistema > Privacidad y seguridad > Accesibilidad y vuelva "
                          "a abrir el programa.")
    return avisos


# ---------------------------------------------------------------------------
# Configuración guardada (posición y pestaña)
# ---------------------------------------------------------------------------
def ruta_config():
    if SISTEMA == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif SISTEMA == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, NOMBRE_APP, "config.json")


def cargar_config():
    try:
        with open(ruta_config(), encoding="utf-8") as archivo:
            datos = json.load(archivo)
        return datos if isinstance(datos, dict) else {}
    except (OSError, ValueError):
        return {}


def guardar_config(datos):
    try:
        ruta = ruta_config()
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        temporal = ruta + ".tmp"
        with open(temporal, "w", encoding="utf-8") as archivo:
            json.dump(datos, archivo)
        os.replace(temporal, ruta)
    except OSError:
        pass  # si no se puede guardar, el programa sigue funcionando


# ---------------------------------------------------------------------------
# Contenido del teclado
# ---------------------------------------------------------------------------
PAGINAS = {
    "α": list("αβγδεζηθικλμνξοπρσςτυφχψω"),
    "Α": list("ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ"),
    "±": list("↑↓→←↔±≥≤≈°×·²³⁺⁻‰"),  # la μ (micro) está en la primera pestaña
}
COLUMNAS = 9

FONDO, BARRA, BOTON = "#1e1e2e", "#11111b", "#313244"
HOVER, TEXTO, ACENTO, CERRAR = "#45475a", "#cdd6f4", "#89b4fa", "#f38ba8"
AVISO_FONDO, AVISO_TEXTO = "#45475a", "#f9e2af"


def ruta_recurso(nombre):
    """Ubica un archivo junto al programa, también dentro del ejecutable."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, nombre)


def crear_boton(padre, texto, comando, ancho=3, tamano=12, negrita=False,
                bg=BOTON, fg=TEXTO, hover=HOVER):
    fuente = (FUENTE, tamano, "bold") if negrita else (FUENTE, tamano)
    etiqueta = tk.Label(padre, text=texto, width=ancho, font=fuente,
                        bg=bg, fg=fg, cursor="hand2")
    etiqueta.bind("<Button-1>", lambda e: comando())
    etiqueta.bind("<Enter>", lambda e: etiqueta.configure(bg=hover))
    etiqueta.bind("<Leave>", lambda e: etiqueta.configure(bg=bg))
    return etiqueta


# ---------------------------------------------------------------------------
# Interfaz
# ---------------------------------------------------------------------------
class Teclado:
    def __init__(self):
        self.raiz = raiz = tk.Tk()
        raiz.title("Teclado griego")
        self.poner_icono()
        raiz.overrideredirect(True)
        raiz.attributes("-topmost", True)
        try:
            raiz.attributes("-alpha", 0.96)
        except tk.TclError:
            pass
        raiz.configure(bg=FONDO)

        config = cargar_config()
        pagina_inicial = config.get("pagina") if config.get("pagina") in PAGINAS else "α"
        self.pagina = pagina_inicial
        self.minimizado = False
        self.x, self.y = 120, 120
        self.desplazamiento = (0, 0)
        self.trabajo_aviso = None

        self.barra = tk.Frame(raiz, bg=BARRA)
        self.barra.pack(fill="x")
        self.aviso = tk.Label(raiz, text="", bg=AVISO_FONDO, fg=AVISO_TEXTO,
                              font=(FUENTE, 9), justify="left", anchor="w",
                              padx=6, pady=3, cursor="hand2")
        self.aviso.bind("<Button-1>", lambda e: self.ocultar_aviso())
        self.cuadricula = tk.Frame(raiz, bg=FONDO)
        self.cuadricula.pack(padx=3, pady=3)

        self.pestanas = {}
        for nombre in PAGINAS:
            pestana = crear_boton(self.barra, nombre,
                                  lambda n=nombre: self.cambiar_pagina(n),
                                  tamano=10, negrita=True, bg=BARRA)
            pestana.pack(side="left")
            self.pestanas[nombre] = pestana

        # El botón de cerrar se coloca primero para quedar en el extremo derecho
        crear_boton(self.barra, "✕", self.cerrar, tamano=10, negrita=True,
                    bg=BARRA, hover=CERRAR).pack(side="right")
        crear_boton(self.barra, "–", self.minimizar_ventana, tamano=10, negrita=True,
                    bg=BARRA).pack(side="right")
        self.asa = tk.Label(self.barra, text="⠿", bg=BARRA, fg="#6c7086",
                            cursor="fleur", font=(FUENTE, 10))
        self.asa.pack(side="left", fill="x", expand=True)

        for zona in (self.barra, self.asa):
            zona.bind("<ButtonPress-1>", self.iniciar_arrastre)
            zona.bind("<B1-Motion>", self.arrastrar)
            zona.bind("<ButtonRelease-1>", lambda e: self.guardar())

        self.fijar_tamano()  # recorre todas las pestañas para medirlas
        self.mostrar(pagina_inicial)

        raiz.update_idletasks()
        self.x, self.y = self.limitar(config.get("x"), config.get("y"))
        raiz.geometry(f"+{self.x}+{self.y}")

        raiz.protocol("WM_DELETE_WINDOW", self.cerrar)
        raiz.bind("<Map>", self.al_restaurar)
        raiz.after(100, lambda: evitar_foco(raiz))
        raiz.after(1500, self.mantener_arriba)
        avisos = avisos_de_entorno()
        if avisos:
            raiz.after(400, lambda: self.avisar("\n\n".join(avisos), segundos=20))

    # -- ícono ---------------------------------------------------------------
    def poner_icono(self):
        try:
            if SISTEMA == "win32":
                self.raiz.iconbitmap(ruta_recurso("icono.ico"))
            else:
                imagen = tk.PhotoImage(file=ruta_recurso("icono.png"))
                self.raiz.iconphoto(True, imagen)
                self.raiz._imagen_icono = imagen  # evita que se libere de memoria
        except Exception:
            pass  # si falta el ícono, el programa funciona igual

    # -- páginas -------------------------------------------------------------
    def mostrar(self, pagina):
        for hijo in self.cuadricula.winfo_children():
            hijo.destroy()
        for i, caracter in enumerate(PAGINAS[pagina]):
            boton = crear_boton(self.cuadricula, caracter,
                                lambda c=caracter: self.escribir_caracter(c))
            boton.grid(row=i // COLUMNAS, column=i % COLUMNAS, padx=1, pady=1)
        for nombre, etiqueta in self.pestanas.items():
            etiqueta.configure(fg=ACENTO if nombre == pagina else TEXTO)
        self.pagina = pagina

    def cambiar_pagina(self, pagina):
        self.mostrar(pagina)
        self.guardar()

    def fijar_tamano(self):
        """Todas las pestañas ocupan lo mismo que la más grande (sin saltos de alto)."""
        ancho = alto = 0
        for nombre in PAGINAS:
            self.mostrar(nombre)
            self.raiz.update_idletasks()
            ancho = max(ancho, self.cuadricula.winfo_reqwidth())
            alto = max(alto, self.cuadricula.winfo_reqheight())
        self.cuadricula.configure(width=ancho, height=alto)
        self.cuadricula.grid_propagate(False)
        self.aviso.configure(wraplength=max(ancho - 12, 100))

    # -- escritura y avisos --------------------------------------------------
    def escribir_caracter(self, caracter):
        try:
            escribir(caracter)
        except Exception:
            self.copiar(caracter)
            self.avisar("No se pudo escribir el símbolo. Quedó copiado: péguelo con "
                        + ATAJO_PEGAR + ".")

    def copiar(self, texto):
        try:
            self.raiz.clipboard_clear()
            self.raiz.clipboard_append(texto)
            self.raiz.update()
        except tk.TclError:
            pass

    def avisar(self, texto, segundos=6):
        if self.trabajo_aviso is not None:
            self.raiz.after_cancel(self.trabajo_aviso)
        self.aviso.configure(text=texto)
        self.aviso.pack(fill="x", padx=3, before=self.cuadricula)
        self.trabajo_aviso = self.raiz.after(int(segundos * 1000), self.ocultar_aviso)
        self.raiz.after_idle(self.reajustar)

    def ocultar_aviso(self):
        if self.trabajo_aviso is not None:
            self.raiz.after_cancel(self.trabajo_aviso)
            self.trabajo_aviso = None
        self.aviso.pack_forget()
        self.raiz.after_idle(self.reajustar)

    def reajustar(self):
        """Tras cambiar de tamaño, evita que la ventana quede fuera de la pantalla."""
        if self.minimizado:
            return
        self.raiz.update_idletasks()
        self.x, self.y = self.limitar(self.raiz.winfo_x(), self.raiz.winfo_y())
        self.raiz.geometry(f"+{self.x}+{self.y}")

    # -- posición ------------------------------------------------------------
    def limitar(self, x, y):
        """Devuelve (x, y) corregidos para que la ventana quede dentro de la pantalla."""
        x = x if isinstance(x, int) and not isinstance(x, bool) else 120
        y = y if isinstance(y, int) and not isinstance(y, bool) else 120
        limites = limites_virtuales(self.raiz)
        if limites is None:
            return x, y
        x0, y0, x1, y1 = limites
        ancho, alto = self.raiz.winfo_reqwidth(), self.raiz.winfo_reqheight()
        x = max(x0, min(x, x1 - ancho))
        y = max(y0, min(y, y1 - alto))
        return x, y

    def iniciar_arrastre(self, evento):
        self.desplazamiento = (evento.x_root - self.raiz.winfo_x(),
                               evento.y_root - self.raiz.winfo_y())

    def arrastrar(self, evento):
        self.x, self.y = self.limitar(evento.x_root - self.desplazamiento[0],
                                      evento.y_root - self.desplazamiento[1])
        self.raiz.geometry(f"+{self.x}+{self.y}")

    def guardar(self):
        if not self.minimizado:
            self.x, self.y = self.raiz.winfo_x(), self.raiz.winfo_y()
        guardar_config({"version": VERSION, "x": self.x, "y": self.y,
                        "pagina": self.pagina})

    # -- minimizar / restaurar / cerrar --------------------------------------
    def minimizar_ventana(self):
        """Minimiza el teclado a la barra de tareas, como una ventana común."""
        self.x, self.y = self.raiz.winfo_x(), self.raiz.winfo_y()
        self.minimizado = True
        # Una ventana sin borde no puede minimizarse ni aparecer en la barra de
        # tareas, así que se le devuelve el borde mientras está minimizada.
        self.raiz.update_idletasks()
        self.raiz.overrideredirect(False)
        self.raiz.iconify()

    def al_restaurar(self, evento):
        """Al volver desde la barra de tareas, se restablece la ventana sin borde."""
        if evento.widget is not self.raiz or not self.minimizado:
            return
        if self.raiz.state() != "normal":
            return
        self.minimizado = False
        self.raiz.overrideredirect(True)
        self.x, self.y = self.limitar(self.x, self.y)
        self.raiz.geometry(f"+{self.x}+{self.y}")
        self.raiz.attributes("-topmost", True)
        self.raiz.after(80, lambda: evitar_foco(self.raiz))

    def mantener_arriba(self):
        if not self.minimizado:
            self.raiz.attributes("-topmost", True)
            self.raiz.lift()
        self.raiz.after(1500, self.mantener_arriba)

    def cerrar(self):
        self.guardar()
        self.raiz.destroy()

    def ejecutar(self):
        self.raiz.mainloop()


def main():
    if "--version" in sys.argv[1:]:
        print(VERSION)
        return
    if SISTEMA == "win32":
        activar_dpi()  # debe hacerse antes de crear la ventana
        if not instancia_unica():
            avisar_ya_abierto()
            return
    Teclado().ejecutar()


if __name__ == "__main__":
    main()
