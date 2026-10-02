"""
Teclado griego flotante (Windows, macOS y Linux).

- Queda siempre por encima de las demás ventanas.
- Intenta no quitarle el foco a la aplicación en la que se escribe.
- Al hacer clic en una letra, la escribe donde esté el cursor.
- Se mueve arrastrando la barra superior. La "x" lo cierra.

Windows: no requiere nada adicional.
macOS / Linux: requiere "pynput" (pip install pynput).
"""

import sys
import tkinter as tk

SISTEMA = sys.platform  # "win32", "darwin" o "linux"

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
            user32.SendInput(2, entradas, ctypes.sizeof(INPUT))

    def evitar_foco(raiz):
        hwnd = user32.GetAncestor(raiz.winfo_id(), GA_ROOT) or raiz.winfo_id()
        estilo = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, estilo | WS_EX_NOACTIVATE | WS_EX_TOPMOST)

    FUENTE = "Segoe UI"

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
            print("No se pudo escribir el caracter:", error)

    def evitar_foco(raiz):
        # En Linux (X11), las ventanas sin borde no reciben el foco al hacer clic.
        # En macOS se intenta marcar la ventana como "no activable".
        if SISTEMA == "darwin":
            try:
                raiz.tk.call("::tk::unsupported::MacWindowStyle", "style",
                             raiz._w, "plain", "noActivates")
            except tk.TclError:
                pass

    FUENTE = "Helvetica Neue" if SISTEMA == "darwin" else "DejaVu Sans"


# ---------------------------------------------------------------------------
# Contenido del teclado
# ---------------------------------------------------------------------------
PAGINAS = {
    "α": list("αβγδεζηθικλμνξοπρσςτυφχψω"),
    "Α": list("ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ"),
    "±": list("↑↓→←↔±≥≤≈°×·²³⁺⁻‰µ"),
}
COLUMNAS = 9

FONDO, BARRA, BOTON = "#1e1e2e", "#11111b", "#313244"
HOVER, TEXTO, ACENTO, CERRAR = "#45475a", "#cdd6f4", "#89b4fa", "#f38ba8"

# ---------------------------------------------------------------------------
# Interfaz
# ---------------------------------------------------------------------------
raiz = tk.Tk()
raiz.title("Teclado griego")
raiz.overrideredirect(True)
raiz.attributes("-topmost", True)
try:
    raiz.attributes("-alpha", 0.96)
except tk.TclError:
    pass
raiz.configure(bg=FONDO)
raiz.geometry("+120+120")


def crear_boton(padre, texto, comando, ancho=3, tamano=12, negrita=False,
                bg=BOTON, fg=TEXTO, hover=HOVER):
    fuente = (FUENTE, tamano, "bold") if negrita else (FUENTE, tamano)
    etiqueta = tk.Label(padre, text=texto, width=ancho, font=fuente,
                        bg=bg, fg=fg, cursor="hand2")
    etiqueta.bind("<Button-1>", lambda e: comando())
    etiqueta.bind("<Enter>", lambda e: etiqueta.configure(bg=hover))
    etiqueta.bind("<Leave>", lambda e: etiqueta.configure(bg=bg))
    return etiqueta


barra = tk.Frame(raiz, bg=BARRA)
barra.pack(fill="x")
cuadricula = tk.Frame(raiz, bg=FONDO)
cuadricula.pack(padx=3, pady=3)
pestanas = {}


def mostrar(pagina):
    for hijo in cuadricula.winfo_children():
        hijo.destroy()
    for i, caracter in enumerate(PAGINAS[pagina]):
        boton = crear_boton(cuadricula, caracter, lambda c=caracter: escribir(c))
        boton.grid(row=i // COLUMNAS, column=i % COLUMNAS, padx=1, pady=1)
    for nombre, etiqueta in pestanas.items():
        etiqueta.configure(fg=ACENTO if nombre == pagina else TEXTO)


for nombre in PAGINAS:
    pestana = crear_boton(barra, nombre, lambda n=nombre: mostrar(n), tamano=10,
                          negrita=True, bg=BARRA)
    pestana.pack(side="left")
    pestanas[nombre] = pestana

crear_boton(barra, "✕", raiz.destroy, tamano=10, negrita=True, bg=BARRA,
            hover=CERRAR).pack(side="right")

asa = tk.Label(barra, text="⠿", bg=BARRA, fg="#6c7086", cursor="fleur",
               font=(FUENTE, 10))
asa.pack(side="left", fill="x", expand=True)

desplazamiento = {"x": 0, "y": 0}


def iniciar_arrastre(evento):
    desplazamiento["x"] = evento.x_root - raiz.winfo_x()
    desplazamiento["y"] = evento.y_root - raiz.winfo_y()


def arrastrar(evento):
    raiz.geometry(f"+{evento.x_root - desplazamiento['x']}+{evento.y_root - desplazamiento['y']}")


for zona in (barra, asa):
    zona.bind("<ButtonPress-1>", iniciar_arrastre)
    zona.bind("<B1-Motion>", arrastrar)


def mantener_arriba():
    raiz.attributes("-topmost", True)
    raiz.lift()
    raiz.after(1500, mantener_arriba)


mostrar("α")
raiz.update_idletasks()
raiz.after(100, lambda: evitar_foco(raiz))
raiz.after(1500, mantener_arriba)
raiz.mainloop()
