"""
Teclado Científico: teclado flotante de letras griegas y símbolos (Windows, macOS y Linux).

- Queda siempre por encima de las demás ventanas.
- Intenta no quitarle el foco a la aplicación en la que se escribe.
- Al hacer clic en una letra, la escribe donde esté el cursor.
- Se mueve arrastrando la barra superior (sin salirse de la pantalla).
- Recuerda la última posición y la última pestaña usadas.
- Al pasar el mouse sobre un símbolo, muestra su nombre en la barra superior.
- Una fila de "usados recientemente" repite los últimos 9 símbolos escritos.
- Modo compacto (botón ▴/▾): deja solo la barra y la fila de recientes.
- Atajo global (Ctrl+Alt+G por defecto, solo Windows y Linux con X11) para
  ocultar o mostrar el teclado. Se puede cambiar en el archivo de configuración.
- El botón "–" lo minimiza a la barra de tareas, como una ventana común;
  se restaura haciendo clic en su ícono de la barra de tareas. La "x" lo cierra.
- Si no puede escribir, avisa en pantalla y copia el símbolo al portapapeles.

Windows: no requiere nada adicional.
macOS / Linux: requiere "pynput" (pip install pynput).
"""

import json
import os
import queue
import re
import sys
import threading
import tkinter as tk

VERSION = "1.4"
NOMBRE_APP = "TecladoCientifico"
NOMBRE_APP_ANTERIOR = "TecladoGriego"  # nombre de la carpeta de configuración hasta la v1.3
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
    WM_HOTKEY = 0x0312
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
    user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
    user32.RegisterHotKey.restype = wintypes.BOOL
    user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND,
                                   wintypes.UINT, wintypes.UINT]
    user32.GetMessageW.restype = ctypes.c_int

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
        user32.MessageBoxW(None, "El Teclado Científico ya está abierto.\n\n"
                           "Si no lo ve, puede estar oculto: use su atajo "
                           "(por defecto Ctrl+Alt+G) o búsquelo en la barra de tareas.",
                           "Teclado Científico", 0x40)

    def iniciar_atajo(mods, tecla, cola):
        """Registra el atajo global. Los avisos llegan por la cola (hilo aparte)."""
        banderas, codigo = codigo_atajo_windows(mods, tecla)

        def trabajo():
            # El atajo y su bucle de mensajes deben vivir en el mismo hilo.
            if not user32.RegisterHotKey(None, 1, banderas, codigo):
                cola.put(("error", None))
                return
            mensaje = wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(mensaje), None, 0, 0) > 0:
                if mensaje.message == WM_HOTKEY:
                    cola.put(("atajo", None))

        hilo = threading.Thread(target=trabajo, daemon=True)
        hilo.start()
        return hilo

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

    def iniciar_atajo(mods, tecla, cola):
        """Atajo global solo en Linux con X11 (devuelve None si no es posible)."""
        if SISTEMA != "linux" or en_wayland():
            return None
        try:
            from pynput import keyboard
            nombres = {"ctrl": "<ctrl>", "alt": "<alt>", "shift": "<shift>", "win": "<cmd>"}
            final = f"<{tecla}>" if len(tecla) > 1 else tecla
            combinacion = "+".join([nombres[m] for m in mods] + [final])
            escucha = keyboard.GlobalHotKeys({combinacion: lambda: cola.put(("atajo", None))})
            escucha.daemon = True
            escucha.start()
            return escucha
        except Exception:
            cola.put(("error", None))
            return None

    FUENTE = "Helvetica Neue" if SISTEMA == "darwin" else "DejaVu Sans"
    ATAJO_PEGAR = "Cmd+V" if SISTEMA == "darwin" else "Ctrl+V"


# ---------------------------------------------------------------------------
# Atajo global (formato de texto: "ctrl+alt+g")
# ---------------------------------------------------------------------------
ATAJO_PREDETERMINADO = "ctrl+alt+g"
_MODIFICADORES = ("ctrl", "alt", "shift", "win")


def analizar_atajo(texto):
    """'ctrl+alt+g' -> (['ctrl', 'alt'], 'g'). Devuelve None si no es válido."""
    if not isinstance(texto, str):
        return None
    partes = [p.strip().lower() for p in texto.split("+")]
    if len(partes) < 2 or "" in partes:
        return None
    *mods, tecla = partes
    if len(set(mods)) != len(mods) or not set(mods) <= set(_MODIFICADORES):
        return None
    es_letra_o_numero = len(tecla) == 1 and tecla.isascii() and tecla.isalnum()
    if not (es_letra_o_numero or re.fullmatch(r"f([1-9]|1[0-2])", tecla)):
        return None
    return mods, tecla


def texto_atajo(mods, tecla):
    """Para mostrar al usuario: 'Ctrl+Alt+G'."""
    return "+".join([m.capitalize() for m in mods] + [tecla.upper()])


def codigo_atajo_windows(mods, tecla):
    """(banderas, código de tecla virtual) para RegisterHotKey de Windows."""
    banderas = 0x4000  # MOD_NOREPEAT: no repite al mantener pulsado
    for m in mods:
        banderas |= {"alt": 0x1, "ctrl": 0x2, "shift": 0x4, "win": 0x8}[m]
    if len(tecla) > 1:  # F1 a F12
        return banderas, 0x70 + int(tecla[1:]) - 1
    return banderas, ord(tecla.upper())


def en_wayland():
    return (os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"
            or bool(os.environ.get("WAYLAND_DISPLAY")))


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
        if en_wayland():
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
def ruta_config(nombre=None):
    if SISTEMA == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif SISTEMA == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, nombre or NOMBRE_APP, "config.json")


def _leer_config(ruta):
    try:
        with open(ruta, encoding="utf-8") as archivo:
            datos = json.load(archivo)
        return datos if isinstance(datos, dict) else {}
    except (OSError, ValueError):
        return {}


def cargar_config():
    if os.path.exists(ruta_config()):
        return _leer_config(ruta_config())
    # Primera vez tras el cambio de nombre: se aprovecha la configuración anterior
    # (posición, pestaña y atajo) para que el usuario no la pierda.
    return _leer_config(ruta_config(NOMBRE_APP_ANTERIOR))


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
    # Química y medicina: subíndices, superíndices (² ³ ⁺ ⁻ están en "±") y símbolos
    "H₂": list("₀₁₂₃₄₅₆₇₈₉⁰¹⁴⁵⁶⁷⁸⁹⇌≠∞√∑∝"),
}
COLUMNAS = 9
MAX_RECIENTES = 9

# Nombres que se muestran al pasar el mouse (deben ser cortos: caben en la barra)
_GRIEGAS = [  # (minúscula, mayúscula, nombre)
    ("α", "Α", "alfa"), ("β", "Β", "beta"), ("γ", "Γ", "gamma"), ("δ", "Δ", "delta"),
    ("ε", "Ε", "épsilon"), ("ζ", "Ζ", "zeta"), ("η", "Η", "eta"), ("θ", "Θ", "theta"),
    ("ι", "Ι", "iota"), ("κ", "Κ", "kappa"), ("λ", "Λ", "lambda"), ("μ", "Μ", "mu"),
    ("ν", "Ν", "nu"), ("ξ", "Ξ", "xi"), ("ο", "Ο", "ómicron"), ("π", "Π", "pi"),
    ("ρ", "Ρ", "rho"), ("σ", "Σ", "sigma"), ("τ", "Τ", "tau"), ("υ", "Υ", "ípsilon"),
    ("φ", "Φ", "fi (phi)"), ("χ", "Χ", "ji (chi)"), ("ψ", "Ψ", "psi"), ("ω", "Ω", "omega"),
]
NOMBRES = {"ς": "sigma final"}
for _min, _may, _nombre in _GRIEGAS:
    NOMBRES[_min] = _nombre
    NOMBRES[_may] = _nombre + " mayús."
NOMBRES.update({
    "↑": "flecha arriba", "↓": "flecha abajo", "→": "flecha derecha",
    "←": "flecha izquierda", "↔": "flecha doble", "±": "más o menos",
    "≥": "mayor o igual", "≤": "menor o igual", "≈": "aprox. igual",
    "°": "grados", "×": "por (multiplicar)", "·": "punto medio",
    "²": "al cuadrado", "³": "al cubo", "⁺": "superíndice +",
    "⁻": "superíndice −", "‰": "por mil",
    "⇌": "equilibrio", "≠": "distinto de", "∞": "infinito",
    "√": "raíz cuadrada", "∑": "sumatoria", "∝": "proporcional a",
})
for _i, _c in enumerate("₀₁₂₃₄₅₆₇₈₉"):
    NOMBRES[_c] = f"subíndice {_i}"
for _c, _i in zip("⁰¹⁴⁵⁶⁷⁸⁹", (0, 1, 4, 5, 6, 7, 8, 9)):
    NOMBRES[_c] = f"superíndice {_i}"
SIMBOLOS_VALIDOS = {c for pagina in PAGINAS.values() for c in pagina}

FONDO, BARRA, BOTON = "#1e1e2e", "#11111b", "#313244"
HOVER, TEXTO, ACENTO, CERRAR = "#45475a", "#cdd6f4", "#89b4fa", "#f38ba8"
AVISO_FONDO, AVISO_TEXTO = "#45475a", "#f9e2af"
RECIENTE_FONDO, NOMBRE_TEXTO, ASA_TEXTO = "#383852", "#a6adc8", "#6c7086"


def ruta_recurso(nombre):
    """Ubica un archivo junto al programa, también dentro del ejecutable."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, nombre)


def crear_boton(padre, texto, comando, ancho=3, tamano=12, negrita=False,
                bg=BOTON, fg=TEXTO, hover=HOVER, al_pasar=None):
    """al_pasar(True/False) se llama cuando el mouse entra o sale del botón."""
    fuente = (FUENTE, tamano, "bold") if negrita else (FUENTE, tamano)
    etiqueta = tk.Label(padre, text=texto, width=ancho, font=fuente,
                        bg=bg, fg=fg, cursor="hand2")

    def entrar(evento):
        etiqueta.configure(bg=hover)
        if al_pasar:
            al_pasar(True)

    def salir(evento):
        etiqueta.configure(bg=bg)
        if al_pasar:
            al_pasar(False)

    etiqueta.bind("<Button-1>", lambda e: comando())
    etiqueta.bind("<Enter>", entrar)
    etiqueta.bind("<Leave>", salir)
    return etiqueta


# ---------------------------------------------------------------------------
# Interfaz
# ---------------------------------------------------------------------------
class Teclado:
    def __init__(self):
        self.raiz = raiz = tk.Tk()
        raiz.title("Teclado Científico")
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
        recientes = config.get("recientes")
        self.recientes = []
        if isinstance(recientes, list):
            for c in recientes:
                if c in SIMBOLOS_VALIDOS and c not in self.recientes:
                    self.recientes.append(c)
        del self.recientes[MAX_RECIENTES:]
        self.minimizado = False
        self.x, self.y = 120, 120
        self.desplazamiento = (0, 0)
        self.trabajo_aviso = None
        self.compacto = False
        self.oculto = False
        self.cola_atajo = queue.SimpleQueue()
        self.escucha_atajo = None
        aviso_atajo = None
        atajo_texto = config.get("atajo", ATAJO_PREDETERMINADO)
        if atajo_texto == "":
            self.atajo = None  # desactivado por el usuario
        else:
            self.atajo = analizar_atajo(atajo_texto)
            if self.atajo is None:
                predeterminado = analizar_atajo(ATAJO_PREDETERMINADO)
                aviso_atajo = (f"El atajo «{atajo_texto}» del archivo de configuración "
                               f"no es válido; se usa {texto_atajo(*predeterminado)}.")
                self.atajo = predeterminado

        self.barra = tk.Frame(raiz, bg=BARRA)
        self.barra.pack(fill="x")
        self.aviso = tk.Label(raiz, text="", bg=AVISO_FONDO, fg=AVISO_TEXTO,
                              font=(FUENTE, 9), justify="left", anchor="w",
                              padx=6, pady=3, cursor="hand2")
        self.aviso.bind("<Button-1>", lambda e: self.ocultar_aviso())
        self.recientes_marco = tk.Frame(raiz, bg=FONDO)
        self.recientes_marco.pack(padx=3, pady=(3, 0), anchor="w")
        self.slots = [self.crear_slot(i) for i in range(MAX_RECIENTES)]
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
        self.boton_compacto = crear_boton(
            self.barra, "▴", self.alternar_compacto, tamano=10, negrita=True, bg=BARRA,
            al_pasar=lambda dentro: self.mostrar_nombre(
                ("Expandir" if self.compacto else "Modo compacto") if dentro else None))
        self.boton_compacto.pack(side="right")
        # width=1: el texto se recorta en vez de agrandar la ventana
        self.asa = tk.Label(self.barra, text="⠿", bg=BARRA, fg=ASA_TEXTO, width=1,
                            cursor="fleur", font=(FUENTE, 10))
        self.asa.pack(side="left", fill="x", expand=True)

        for zona in (self.barra, self.asa):
            zona.bind("<ButtonPress-1>", self.iniciar_arrastre)
            zona.bind("<B1-Motion>", self.arrastrar)
            zona.bind("<ButtonRelease-1>", lambda e: self.guardar())

        self.refrescar_recientes()
        self.fijar_tamano()  # recorre todas las pestañas para medirlas
        self.mostrar(pagina_inicial)
        if config.get("compacto") is True:
            self.aplicar_compacto(True)

        raiz.update_idletasks()
        self.x, self.y = self.limitar(config.get("x"), config.get("y"))
        raiz.geometry(f"+{self.x}+{self.y}")

        raiz.protocol("WM_DELETE_WINDOW", self.cerrar)
        raiz.bind("<Map>", self.al_restaurar)
        raiz.after(100, lambda: evitar_foco(raiz))
        raiz.after(1500, self.mantener_arriba)
        avisos = avisos_de_entorno()
        if aviso_atajo:
            avisos.append(aviso_atajo)
        if avisos:
            raiz.after(400, lambda: self.avisar("\n\n".join(avisos), segundos=20))
        if self.atajo and SISTEMA in ("win32", "linux"):
            self.escucha_atajo = iniciar_atajo(*self.atajo, self.cola_atajo)
        raiz.after(100, self.revisar_atajo)

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
        self.mostrar_nombre(None)
        for hijo in self.cuadricula.winfo_children():
            hijo.destroy()
        for i, caracter in enumerate(PAGINAS[pagina]):
            boton = crear_boton(self.cuadricula, caracter,
                                lambda c=caracter: self.escribir_caracter(c),
                                al_pasar=lambda dentro, c=caracter:
                                self.mostrar_nombre(NOMBRES.get(c) if dentro else None))
            boton.grid(row=i // COLUMNAS, column=i % COLUMNAS, padx=1, pady=1)
        for nombre, etiqueta in self.pestanas.items():
            etiqueta.configure(fg=ACENTO if nombre == pagina else TEXTO)
        self.pagina = pagina

    def cambiar_pagina(self, pagina):
        self.mostrar(pagina)
        if self.compacto:
            self.alternar_compacto(False)  # elegir una pestaña expande el teclado
        else:
            self.guardar()

    # -- modo compacto -------------------------------------------------------
    def aplicar_compacto(self, compacto):
        """Muestra u oculta la cuadrícula (queda solo la barra y los recientes)."""
        self.compacto = compacto
        if compacto:
            self.cuadricula.pack_forget()
        else:
            self.cuadricula.pack(padx=3, pady=3)
        self.recientes_marco.pack_configure(pady=(3, 3) if compacto else (3, 0))
        self.boton_compacto.configure(text="▾" if compacto else "▴")

    def alternar_compacto(self, compacto=None):
        self.aplicar_compacto(not self.compacto if compacto is None else compacto)
        self.mostrar_nombre("Expandir" if self.compacto else "Modo compacto")
        self.raiz.after_idle(self.reajustar)
        self.guardar()

    # -- atajo global: ocultar / mostrar -------------------------------------
    def revisar_atajo(self):
        """Atiende los avisos del hilo del atajo (se consulta cada 100 ms)."""
        try:
            while True:
                tipo, _ = self.cola_atajo.get_nowait()
                if tipo == "atajo":
                    self.alternar_visibilidad()
                elif tipo == "error":
                    self.avisar(f"No se pudo activar el atajo {texto_atajo(*self.atajo)}: "
                                "quizá otra aplicación ya lo usa. Puede cambiarlo en el "
                                f"archivo {ruta_config()}", segundos=15)
        except queue.Empty:
            pass
        self.raiz.after(100, self.revisar_atajo)

    def alternar_visibilidad(self):
        if self.oculto or self.minimizado:
            self.mostrar_ventana()
        else:
            self.guardar()
            self.oculto = True
            self.raiz.withdraw()

    def mostrar_ventana(self):
        estaba_minimizado = self.minimizado
        self.oculto = False
        self.raiz.deiconify()  # si estaba minimizado, al_restaurar completa el trabajo
        if not estaba_minimizado:
            self.raiz.geometry(f"+{self.x}+{self.y}")
            self.raiz.attributes("-topmost", True)
            self.raiz.lift()
            self.raiz.after(80, lambda: evitar_foco(self.raiz))

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

    def mostrar_nombre(self, nombre):
        """Muestra el nombre del símbolo en la barra (o el asa si no hay ninguno)."""
        if nombre:
            self.asa.configure(text=nombre, fg=NOMBRE_TEXTO, font=(FUENTE, 8))
        else:
            self.asa.configure(text="⠿", fg=ASA_TEXTO, font=(FUENTE, 10))

    # -- fila de recientes ---------------------------------------------------
    def crear_slot(self, indice):
        etiqueta = tk.Label(self.recientes_marco, text="", width=3, font=(FUENTE, 12),
                            bg=BARRA, fg=ACENTO)
        etiqueta.grid(row=0, column=indice, padx=1, pady=1)

        def lleno():
            return indice < len(self.recientes)

        def entrar(evento):
            if lleno():
                etiqueta.configure(bg=HOVER)
                self.mostrar_nombre(NOMBRES.get(self.recientes[indice]))

        def salir(evento):
            etiqueta.configure(bg=RECIENTE_FONDO if lleno() else BARRA)
            self.mostrar_nombre(None)

        def pulsar(evento):
            if lleno():
                # Desde esta fila no se reordena: el símbolo no se mueve bajo el mouse.
                self.escribir_caracter(self.recientes[indice], reordenar=False)

        etiqueta.bind("<Enter>", entrar)
        etiqueta.bind("<Leave>", salir)
        etiqueta.bind("<Button-1>", pulsar)
        return etiqueta

    def refrescar_recientes(self):
        for i, etiqueta in enumerate(self.slots):
            if i < len(self.recientes):
                etiqueta.configure(text=self.recientes[i], bg=RECIENTE_FONDO,
                                   cursor="hand2")
            else:
                etiqueta.configure(text="", bg=BARRA, cursor="arrow")

    def registrar_reciente(self, caracter, reordenar=True):
        if caracter in self.recientes:
            if not reordenar:
                return
            self.recientes.remove(caracter)
        self.recientes.insert(0, caracter)
        del self.recientes[MAX_RECIENTES:]
        self.refrescar_recientes()
        self.guardar()

    # -- escritura y avisos --------------------------------------------------
    def escribir_caracter(self, caracter, reordenar=True):
        self.registrar_reciente(caracter, reordenar)
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
        self.aviso.pack(fill="x", padx=3, before=self.recientes_marco)
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
        if self.minimizado or self.oculto:
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
        if not self.minimizado and not self.oculto:
            self.x, self.y = self.raiz.winfo_x(), self.raiz.winfo_y()
        guardar_config({"version": VERSION, "x": self.x, "y": self.y,
                        "pagina": self.pagina, "recientes": self.recientes,
                        "compacto": self.compacto,
                        "atajo": texto_atajo(*self.atajo).lower() if self.atajo else ""})

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
        if not self.minimizado and not self.oculto:
            self.raiz.attributes("-topmost", True)
            self.raiz.lift()
        self.raiz.after(1500, self.mantener_arriba)

    def cerrar(self):
        self.guardar()
        self.raiz.destroy()

    def ejecutar(self):
        self.raiz.mainloop()


def autodiagnostico():
    """Comprueba que el módulo de escritura esté disponible (lo usa la compilación)."""
    if SISTEMA != "win32":
        try:
            from pynput.keyboard import Controller
            Controller()
        except Exception as error:
            print("ERROR: no se puede escribir:", error)
            return 1
    print("OK")
    return 0


def main():
    if "--version" in sys.argv[1:]:
        print(VERSION)
        return
    if "--autodiagnostico" in sys.argv[1:]:
        sys.exit(autodiagnostico())
    if SISTEMA == "win32":
        activar_dpi()  # debe hacerse antes de crear la ventana
        if not instancia_unica():
            avisar_ya_abierto()
            return
    Teclado().ejecutar()


if __name__ == "__main__":
    main()
