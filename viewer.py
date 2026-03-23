import vlc, tkinter as tk, numpy as np, os, json, queue
from time import perf_counter
from PIL import Image, ImageTk
from collections import OrderedDict
from threading import Thread, Lock, Event
from tkinter import ttk, simpledialog

Image.MAX_IMAGE_PIXELS = 346724322
vipsbin = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vips-dev-8.18", "bin")
os.environ['PATH'] = os.pathsep.join((vipsbin, os.environ['PATH']))
os.add_dll_directory(vipsbin)
import pyvips

class Application(tk.Frame):
    BUTTON_MODIFIER_CTRL = 1
    BUTTON_MODIFIER_CTRL_LEFT_CLICK = 257
    BUTTON_MODIFIER_RIGHT_CLICK = 1024
    LAST_USED_CACHED_IMG = None

    QUALITY = {
            "Nearest": Image.Resampling.NEAREST,
            "Bilinear": Image.Resampling.BILINEAR,
            "Bicubic": Image.Resampling.BICUBIC,
            "Lanczos": Image.Resampling.LANCZOS,
            "Pyvips": "pyvips"
        }

    def __init__(self, master=None,
                 geometry: str=None, lastdir: str=None,
                 zoom_magnitude: float=None, unbound_var: bool=None,
                 disable_menubar: bool=None, statusbar: bool=None,
                 initial_filter: Image.Resampling=None, drag_quality: Image.Resampling=None, anti_aliasing: bool=None, thumbnail_var: str=None,
                 filter_delay: int=None, thumb_qual: int=None, show_ram: bool=None,
                 canvas_color=None, text_color=None, order=None,
                 button_color=None, active_button_color=None, statusbar_mode=None,
                 statusbar_color=None, statusbar_divider_color=None, volume=None, savedata={}, gui=None):

        self.ready = True
        self.dragging_and_zooming = False
        self.current_load_token = None
        self.loader = AsyncImageLoader(self)
        self.draw_queue = []
        self.undo = []
        self.debug = []
        self.filename = None
        self.timer = Timer()
        self.timer.start()
        self.gui = gui
        self.savedata = savedata
        self.f = True
        self.statusbar_event = False # Control-s, statusbar added or removed. This flag is used to skip the "drag" filter, and instead we render best quality.

        self.save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "viewer_prefs.json")
        if not savedata:
            savedata = self.load_json()
            self.savedata = savedata

        self.lastdir = lastdir or savedata.get("lastdir", None)

        self.standalone = True if master == None else False
        self.title = "Python Media Viewer"
        self.a = False
        self.app2 = None
        def helper(event):
            if ".!optionmenu" not in event.widget._w:
                self.image_quality_menu_open.set(False)
                self.thumb_quality_menu_open.set(False)
                self.drag_quality_button_menu_open.set(False)
            elif hasattr(event.widget, "test"): # specific button gets pressed, false all others.
                other_buttons = [x[1] for x in event.widget.master.children.items() if "optionmenu" in x[0]]
                for btn in other_buttons:
                    if btn == event.widget: continue
                    btn.test.set(False)
        self.dont_do_move = False
        if self.standalone:
            if gui: # NOT standalone per-say.
                master = tk.Toplevel()
                self.app2 = master.master.fileManager.gui.bindhandler.search_widget
            else:
                master = tk.Tk()
                master.bind('<KeyPress-Left>', lambda e: self.key_press(-1))
                master.bind('<KeyPress-Down>', lambda e: self.key_press(-1))
                master.bind('<KeyPress-Right>', lambda e: self.key_press(1))
                master.bind('<KeyPress-Up>', lambda e: self.key_press(1))
                master.bind('<F2>', lambda e: self.rename())
                master.bind('<Delete>', lambda e: self.trash())
                master.bind('<Control-z>', lambda e: self.on_ctrl_z())
                master.bind('<Control-Z>', lambda e: self.on_ctrl_z())

            master.bind("<Control-s>", lambda e: self.statusbar.set(not self.statusbar.get()))
            master.bind("<Control-S>", lambda e: self.statusbar.set(not self.statusbar.get()))
            master.bind_all("<Control-o>", self.menu_reveal_in_file_explorer_clicked)
            master.bind_all("<Control-O>", self.menu_reveal_in_file_explorer_clicked)
            master.bind("<Button-1>", helper)
            master.geometry(geometry or savedata.get("geometry", None) or "800x600")
            master.title(self.title)
            master.protocol("WM_DELETE_WINDOW", self.window_close)
        else: # Gui embedded
            self.app2 = master.master.master.fileManager.gui.bindhandler.search_widget
            self.app2.root.gui.bind("<Control-s>", lambda e: self.statusbar.set(not self.statusbar.get()))
            self.app2.root.gui.bind("<Control-S>", lambda e: self.statusbar.set(not self.statusbar.get()))
            self.app2.root.gui.bind_all("<Control-o>", self.menu_reveal_in_file_explorer_clicked)
            self.app2.root.gui.bind_all("<Control-O>", self.menu_reveal_in_file_explorer_clicked)
            self.app2.root.gui.bind("<Button-1>", helper)

        if True:
            self.zoom_magnitude = zoom_magnitude or float(savedata.get("zoom_magnitude", 1.20))

            self.unbound_var = tk.BooleanVar(value=unbound_var or savedata.get("unbound_pan", False))

            self.disable_menubar = disable_menubar or savedata.get("disable_menubar", False)
            self.statusbar = statusbar or tk.BooleanVar(value=savedata.get("statusbar", True))
            self.statusbar_mode = statusbar_mode or tk.StringVar(value=savedata.get("statusbar_mode", "Default"))
            self.statusbar.trace_add("write", lambda *_: self.toggle_statusbar())
            def helper11():
                if self.statusbar_mode.get() == "None": self.statusbar.set(False)
                else: self.statusbar.set(True)
            self.statusbar_mode.trace_add("write", lambda *_: helper11())

            self.filter = initial_filter or Application.QUALITY.get(savedata.get("filter", "pyvips").lower().capitalize())
            self.drag_quality = drag_quality or savedata.get("drag_quality", "No buffer").lower().capitalize()
            self.drag_quality = self.drag_quality if self.drag_quality == "No buffer" else Application.QUALITY.get(self.drag_quality)
            self.anti_aliasing = tk.BooleanVar(value=anti_aliasing or savedata.get("anti_aliasing", True))
            self.anti_aliasing.trace_add("write", lambda *_: (setattr(self, "full_res", None), self.cache.clear(), self._zoom_cache.clear(), self._imagetk_cache.clear(), setattr(self, "first_render_info", None), setattr(self, "second_render_info", None), setattr(self, "debug", []), self.draw_image(self.pil_image)))
            self.quick_zoom = tk.BooleanVar(value=savedata.get("quick_zoom", True))
            self.do_caching = tk.BooleanVar(value=savedata.get("pre-caching", True))
            if self.do_caching.get(): self.drag_quality = "No buffer"
            def uncheck_buffer():
                if self.do_caching.get():
                    self.drag_quality = "No buffer"
                    self.selected_option1.set(self.drag_quality)
            self.do_caching.trace_add("write", lambda *_: uncheck_buffer())
            self.thumbnail_var = tk.StringVar(value=thumbnail_var or savedata.get("thumbnail_var", "No thumb"))
            self.filter_delay = tk.IntVar(value=filter_delay or int(savedata.get("final_filter_delay", 200)))
            self.thumb_qual = tk.IntVar(value=thumb_qual or int(savedata.get("thumb_qual", 32)))
            self.statusbar_up_down = savedata.get("statusbar_up_down", False)
            self.show_ram = tk.BooleanVar(value=show_ram or savedata.get("show_ram", False))
            self.show_ram.trace_add("write", lambda *_: self.toggle_ram_indicator())
            self.volume = volume or int(savedata.get("volume", 50))
            self.order = order or tk.StringVar(value=savedata.get("order", "Name"))
            self.reverse_sort = tk.BooleanVar(value=savedata.get("reverse", False))

            self.colors = savedata.get("colors", {
                    "canvas": "#303276" or canvas_color, #141433
                    "statusbar": "#202041" or statusbar_color,
                    "statusbar_divider": "#545685" or statusbar_divider_color,
                    "button": "#24255C" or button_color,
                    "active_button": "#303276" or active_button_color,
                    "text": "#FFFFFF" or text_color
                    } or #white
                    {
                    "canvas": "#000000",
                    "statusbar": "#f0f0f0",
                    "statusbar_divider": "#f0f0f0",
                    "button": "#f0f0f0",
                    "active_button": "#f0f0f0",
                    "text": "#000000"
                    }
                )
        self.bg_color = tuple(int(self.colors["canvas"][i:i+2], 16) for i in (1, 3, 5)) + (0,)
        super().__init__(master, bg=self.colors["canvas"])
        self.master = master

        self.style = ttk.Style()
        self.style.configure("bg.TFrame", background="black")
        self.style.configure("Horizontal.TScale", background="black")
        self.style.configure("theme.Horizontal.TScale", background="red")

        self.config(bg=self.colors["canvas"])
        self.master.configure(bg=self.colors["canvas"])
        self.pil_image = None
        self.img_pointer = None
        self._last_draw_time = 0.0
        self.image_id = None
        self.drag_buffer = None
        self.save = None
        self.save1 = None
        self.memory_after_id = None
        self.gif_after_id = None
        self.gif_gen_after_id = None
        self.draw_img_id = None
        self.zoom_after_id = None

        self.full_res = None # Full res copy of the image
        self._zoom_cache = LRUCache(maxsize=32, name="zoom") # saved zoom levels
        self._imagetk_cache = LRUCache(maxsize=0, name="imagetk") # saved gif imagetks.
        self.cache = {}
        self.adjacent = []

        self.vlc_instance = vlc.Instance()
        self.vlc_frame = None
        self.old = None

        self._old = None
        self.frames = []
        self._frame_lock = Lock()
        self.lazy_index = 0
        self.scale_key = None
        self.dragging = False
        self.open_thread = None
        self._stop_thread = Event()
        self.is_gif = False
        self.first_render_info = None
        self.second_render_info = None

        self.filenames = []
        self.filename_index = 0

        #self.save_json()
        self.reset_transform()
        self.create_widgets()

    "UI creation"
    def create_widgets(self):
        self.create_menu()
        self.create_status_bar()
        self.create_canvas()
        self.bind_mouse_events()

    def create_menu(self):
        def hints():
            def on_resize(e):
                new_width = max(e.width - 20, 20)
                self.label.config(wraplength=new_width)

            height = 220
            width = 350
            new = tk.Toplevel(self.master, width=width, height=height, bg=self.colors["canvas"])
            new.transient(self.master)
            new.geometry(f"{width}x{height}+{int(self.master.winfo_width()/2-width/2)}+{int(self.master.winfo_height()/2-height/2)}")
            new.grid_rowconfigure(0, weight=1)
            new.grid_columnconfigure(0, weight=1)
            text = """Small guide:
    Control-d: Open folder.
    Control-f: Open file.

    Double-click: "Center & Resize."
    Arrowkeys: Next/Previous image.

    F2: Rename file.
    Delete: Move to trash. (Done when closing the app)
    Control-z: Undo.

    Control-s: toggle statusbar and access some settings.
                """

            self.label = tk.Label(
                new,
                text=text,
                justify='left',
                anchor='nw', wraplength=height, bg=self.colors["canvas"], fg=self.colors["text"]
            )
            self.label.pack(fill='both', expand=False, padx=10, pady=10)
            new.bind('<Configure>', on_resize)

        menu_bar = tk.Menu(self.master)

        # File menu
        file_menu = tk.Menu(menu_bar, tearoff=tk.OFF)
        menu_bar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open", command=self.menu_open_clicked, accelerator="Ctrl+F")
        file_menu.add_command(label="Open folder", command=self.menu_open_dir_clicked, accelerator="Ctrl+D")

        file_menu.add_separator()
        file_menu.add_command(label="Open in File Explorer", command=self.menu_reveal_in_file_explorer_clicked, accelerator="Ctrl+O")
        file_menu.add_command(label="Rename", command=self.rename, accelerator="F2")
        file_menu.add_separator()
        file_menu.add_command(label="Trash", command=self.trash, accelerator="Delete")
        file_menu.add_command(label="Undo trash", command=self.trash, accelerator="Ctrl+Z")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.window_close)

        # View menu
        view_menu = tk.Menu(menu_bar, tearoff=tk.OFF)
        menu_bar.add_cascade(label="View", menu=view_menu)


        statusbar_menu = tk.Menu(view_menu, tearoff=tk.OFF)
        view_menu.add_cascade(label="Statusbar      Ctrl+S", menu=statusbar_menu)

        statusbar_menu.add_radiobutton(label="None", variable=self.statusbar_mode, value="None")
        statusbar_menu.add_radiobutton(label="Default", variable=self.statusbar_mode, value="Default")
        statusbar_menu.add_radiobutton(label="Advanced", variable=self.statusbar_mode, value="Advanced")
        statusbar_menu.add_radiobutton(label="Debug", variable=self.statusbar_mode, value="Debug")

        order_menu = tk.Menu(view_menu, tearoff=0)
        # 'value' is what self.order becomes when that item is clicked

        def resort():
            if len(self.filenames) < 2: return
            if self.order.get() == "Name":
                from natsort import natsorted
                self.filenames = natsorted(self.filenames, reverse=self.reverse_sort.get())
            elif self.order.get() == "Date":
                self.filenames.sort(key=lambda path: os.path.getmtime(path), reverse=not self.reverse_sort.get()) # window's sort by "date" is a hybrid, it looks for exif, hence the mismatch if you compare these. Sort by modification date instead in file explorer.
            self.filename_index = 0
            self.set_image(self.filenames[self.filename_index])

        order_menu.add_radiobutton(
            label="Name",
            variable=self.order,
            value="Name",
            command=resort
        )
        order_menu.add_radiobutton(
            label="Date",
            variable=self.order,
            value="Date",
            command=resort
        )

        def helper11():
            resort()

        menu_bar.add_cascade(label="Order", menu=order_menu)
        order_menu.add_separator()

        order_menu.add_checkbutton(
            label="Reverse",
            variable=self.reverse_sort,
            offvalue=False,
            onvalue=True,
            command=helper11
        )
        view_menu.add_separator()
        view_menu.add_checkbutton(
            label="Show Ram",
            variable=self.show_ram,
            offvalue=False,
            onvalue=True
        )

        view_menu.add_separator()
        view_menu.add_command(label="Hints", command=hints)

        if self.standalone and not self.gui:
            self.master.bind_all("<Control-f>", self.menu_open_clicked)
            self.master.bind_all("<Control-d>", self.menu_open_dir_clicked)
            self.master.bind_all("<Control-o>", self.menu_reveal_in_file_explorer_clicked)

            self.master.bind_all("<Control-F>", self.menu_open_clicked)
            self.master.bind_all("<Control-D>", self.menu_open_dir_clicked)
            self.master.bind_all("<Control-O>", self.menu_reveal_in_file_explorer_clicked)

        if not self.disable_menubar and self.master.config().get("menu"): # disable menubar for embedded view. (not supported)
            self.master.config(menu=menu_bar)
        #self.master.config(menu=menu_bar)

    def create_status_bar(self):
        def _on_image_quality_change(*args):
            self.image_quality_menu_open.set(False)
            self.full_res = None
            self.cache.clear()
            self._zoom_cache.clear()
            self._imagetk_cache.clear()
            self.first_render_info = None
            self.second_render_info = None
            self.debug = []
            self.filter = Application.QUALITY[self.selected_option.get()]

            if self.filter == "pyvips":
                self.selected_option1.set("No buffer")

            self.timer.start()
            self.debug.clear()
            self.render_info.config(text="R:")
            self.draw_image(self.pil_image)

        def _on_drag_quality_change(*args):
            self.drag_quality_button_menu_open.set(False)
            self.full_res = None
            self.cache.clear()
            self._zoom_cache.clear()
            self._imagetk_cache.clear()
            self.first_render_info = None
            self.second_render_info = None
            self.debug = []

            selected_drag_opt = self.selected_option1.get()
            if selected_drag_opt == "No buffer":
                self.drag_quality = "No buffer"
            else:
                self.timer.start()
                self.debug.clear()
                self.render_info.config(text="R:")
                self.drag_quality = Application.QUALITY[selected_drag_opt]

                # Queue drawing operations
                id1 = self.after(0, lambda: (self.draw_image(self.pil_image, initial_filter=self.drag_quality)))
                id2 = self.after(0, lambda: (self.draw_image(self.pil_image)))
                self.draw_queue.extend([id1, id2])

        # --- Variables ---
        self.image_quality_menu_open = tk.BooleanVar(value=False)
        self.thumb_quality_menu_open = tk.BooleanVar(value=False)
        self.drag_quality_button_menu_open = tk.BooleanVar(value=False)

        self.label_image_format_var = tk.StringVar(value="")
        self.label_image_mode_var = tk.StringVar(value="")
        self.label_image_dimensions_var = tk.StringVar(value="")
        self.label_image_size_var = tk.StringVar(value="")

        # Initialize Image Quality Option
        opts_img = ["Nearest", "Bilinear", "Bicubic", "Lanczos", "Pyvips"]
        init_filter = self.filter if isinstance(self.filter, str) else self.filter.name
        self.selected_option = tk.StringVar(value=self.savedata.get("filter", init_filter).lower().capitalize())
        self.selected_option.trace_add("write", _on_image_quality_change)

        # Initialize Thumb Quality Option
        opts_thumb = ["No thumb", "Fast", "Quality"]
        self.thumbnail_var.trace_add("write", lambda *_: self.thumb_quality_menu_open.set(False))

        # Initialize Drag Quality Option
        opts_drag = ["No buffer", "Nearest", "Bilinear", "Bicubic", "Lanczos"]
        init_drag = self.drag_quality if isinstance(self.drag_quality, str) else self.drag_quality.name
        self.selected_option1 = tk.StringVar(value=init_drag.lower().capitalize())
        self.selected_option1.trace_add("write", _on_drag_quality_change)

        # --- UI Construction ---
        self.frame_statusbar = tk.Frame(self.master, bd=0, relief=tk.SUNKEN, background=self.colors["statusbar"])
        self.ram_indicator = tk.Label(self.frame_statusbar, text="RAM:", anchor=tk.W, padx=5, background=self.colors["statusbar"], foreground=self.colors["text"])

        # Styling Dictionaries (prevents repetitive boilerplate)
        lbl_style = {"background": self.colors["statusbar"], "foreground": self.colors["text"], "font": ("Consolas", 10)}
        btn_style = {
            "background": self.colors["statusbar"], "activebackground": self.colors["active_button"],
            "foreground": self.colors["text"], "activeforeground": self.colors["text"],
            "highlightthickness": 0, "relief": "flat", "font": ('Arial', 8), "padx": 5, "pady": 0
        }
        menu_style = {**btn_style, "width": 6}

        # Labels
        self.label_image_format = tk.Label(self.frame_statusbar, textvariable=self.label_image_format_var, anchor=tk.E, **lbl_style)
        self.label_image_mode = tk.Label(self.frame_statusbar, textvariable=self.label_image_mode_var, anchor=tk.E, **lbl_style)
        self.label_image_dimensions = tk.Label(self.frame_statusbar, textvariable=self.label_image_dimensions_var, anchor=tk.E, **lbl_style)
        self.label_image_size = tk.Label(self.frame_statusbar, textvariable=self.label_image_size_var, anchor=tk.E, **lbl_style)
        self.render_info = tk.Label(self.frame_statusbar, text="R:", anchor=tk.W, padx=5, **lbl_style)
        self.anim_info = tk.Label(self.frame_statusbar, text="", anchor=tk.W, padx=5, **lbl_style)

        # Option Menus
        self.image_quality = tk.OptionMenu(self.frame_statusbar, self.selected_option, *opts_img)
        self.image_quality.configure(**menu_style)

        self.thumb_quality = tk.OptionMenu(self.frame_statusbar, self.thumbnail_var, *opts_thumb)
        self.thumb_quality.configure(**menu_style)

        self.drag_quality_button = tk.OptionMenu(self.frame_statusbar, self.selected_option1, *opts_drag)
        self.drag_quality_button.configure(**menu_style)

        # Checkbuttons
        chk_style = {**btn_style, "selectcolor": self.colors["statusbar"]}
        self.anti_aliasing_button = tk.Checkbutton(self.frame_statusbar, text="Antialiasing", variable=self.anti_aliasing, onvalue=True, offvalue=False)
        self.anti_aliasing_button.configure(**chk_style)

        self.quick_zoom_button = tk.Checkbutton(self.frame_statusbar, text="Quick zoom", variable=self.quick_zoom, onvalue=True, offvalue=False)
        self.quick_zoom_button.configure(**chk_style)

        self.unbound_pan_button = tk.Checkbutton(self.frame_statusbar, text="Unbound pan", variable=self.unbound_var, onvalue=True, offvalue=False)
        self.unbound_pan_button.configure(**chk_style)

        self.pre_caching_button = tk.Checkbutton(self.frame_statusbar, text="Pre-caching", variable=self.do_caching, onvalue=True, offvalue=False)
        self.pre_caching_button.configure(**chk_style)

        self.pack_statusbar()

    def pack_statusbar(self):
        mode = self.statusbar_mode.get()
        self.frame_statusbar.pack_forget()

        if getattr(self, "memory_after_id", None):
            self.after_cancel(self.memory_after_id)

        # 1. Clean slate: Forget all widgets inside the statusbar instead of doing it 1 by 1
        for widget in self.frame_statusbar.winfo_children():
            widget.pack_forget()

        # 2. Pack Base Elements (Always visible if statusbar is packed)
        self.label_image_dimensions.pack(side=tk.RIGHT)
        self.label_image_size.pack(side=tk.RIGHT)
        self.label_image_format.pack(side=tk.RIGHT)

        # 3. Pack Advanced/Debug Elements
        if mode in ("Advanced", "Debug"):
            self.image_quality.pack(side=tk.RIGHT, pady=0)
            self.drag_quality_button.pack(side=tk.RIGHT, pady=0)
            self.thumb_quality.pack(side=tk.RIGHT, pady=0)
            self.anti_aliasing_button.pack(side=tk.RIGHT, pady=0)
            self.quick_zoom_button.pack(side=tk.RIGHT, pady=0)
            self.unbound_pan_button.pack(side=tk.RIGHT, pady=0)
            self.pre_caching_button.pack(side=tk.RIGHT, pady=0)

        # 4. Pack Debug-Only Elements
        if mode == "Debug":
            self.render_info.pack(side=tk.LEFT)
            self.anim_info.pack(side=tk.LEFT)
            self.ram_indicator.pack(side=tk.RIGHT, pady=0)

            def get_memory_usage():
                import psutil
                process = psutil.Process()
                memory_info = process.memory_info()
                self.ram_indicator.config(text=f"RAM: {memory_info.rss / (1024 ** 2):.1f} MB")
                if self.show_ram.get(): self.memory_after_id = self.after(500, get_memory_usage)

            get_memory_usage()


        # 5. Show Master Frame
        if self.statusbar.get():
            side = tk.TOP if self.statusbar_up_down else tk.BOTTOM
            self.frame_statusbar.pack(side=side, fill=tk.X)

    def create_canvas(self):
        canvas = tk.Canvas(self.master, background=self.colors["canvas"], highlightthickness=0)
        canvas.pack(expand=True, fill=tk.BOTH)
        self.canvas = canvas
        self.divider = tk.Frame(self.master, bg=self.colors["statusbar_divider"], height=1)
        if self.statusbar.get():
            self.divider.pack(fill=tk.X)
        canvas.update()
        self.canvas = canvas

    def bind_mouse_events(self):
        canvas = self.canvas
        canvas.bind("<Button-1>", lambda event: (setattr(self, "_old", event), self.master.focus()))
        canvas.bind("<Button-2>", lambda event: (setattr(self, "_old", event), self.master.focus()))
        canvas.bind("<B1-Motion>", self.mouse_move_left)
        canvas.bind("<B2-Motion>", self.mouse_move_left)
        canvas.bind("<ButtonRelease-1>", self.mouse_release)
        canvas.bind("<ButtonRelease-2>", self.mouse_release)
        canvas.bind("<Double-Button-1>", self.mouse_double_click_left)
        canvas.bind("<MouseWheel>", self.mouse_wheel)
        canvas.bind("<Configure>", self.window_resize)

        if self.standalone:
            pass
            #canvas.bind("<Button-3>", self.window_close)
        else:
            #canvas.bind("<Button-3>", lambda e: self.set_image(None))
            pass

    "Mouse"
    def mouse_double_click_left(self, event=None):
        if event and event.state == 2:
            return
        if self.pil_image:
            self.zoom_fit()
            self.draw_image(self.pil_image)

    def mouse_wheel(self, event):
        if event.state == 2:
            return
        if not self.img_pointer:
            return
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        iw, ih = self.img_pointer.width, self.img_pointer.height
        s_current = self.mat_affine[0, 0]

        factor = self.zoom_magnitude if event.delta > 0 else (1 / self.zoom_magnitude)

        # --- MINIMUM SIZE CHECK ---
        if factor < 1.0:
            # Calculate what the new dimensions would be
            new_width = iw * s_current * factor
            new_height = ih * s_current * factor

            # If either dimension drops below 10px, clamp the factor
            # so it only scales down to exactly 10px (or don't scale at all)
            if new_width < 0 or new_height < 0:
                # Calculate the factor needed to hit exactly 10px for the smaller side
                limit_factor = max(0 / (iw * s_current), 0 / (ih * s_current))
                factor = max(factor, limit_factor)
        # ---------------------------

        if not self.unbound_var.get():
            s_fit = min(cw / iw, ch / ih)
            if factor < 1.0:
                factor = max(factor, s_fit / s_current)

        # Final check: if factor is effectively 1 (no change), skip scale_at to save perf
        if factor != 1.0:
            self.scale_at(factor, event.x, event.y)

        if not self.unbound_var.get():
            s_new = s_current * factor
            if s_new <= s_fit:
                tx = (cw - iw * s_new) / 2
                ty = (ch - ih * s_new) / 2
                self.mat_affine[0, 2] = tx
                self.mat_affine[1, 2] = ty
            else:
                self.restrict_pan()
        if self.zoom_after_id: self.after_cancel(self.zoom_after_id)
        self.draw_image(self.pil_image, low_qual=self.quick_zoom.get())
        if hasattr(self, "since_last"): print(perf_counter()-self.since_last)
        self.since_last = perf_counter()

    def mouse_move_left(self, event):
        if not self.ready:
            self._old = event
            return
        self.dragging = True
        if self.save1:
            self.after_cancel(self.save1)
        if event.state == 258: return
        if self.pil_image and self._old:
            dx, dy = event.x - self._old.x, event.y - self._old.y

            self.translate(dx, dy)
            if not self.unbound_var.get():
                self.restrict_pan()

            zoom = self.scale_key[0]
            if self.dragging_and_zooming:
                self.draw_image(self.pil_image)
            elif (self.img_pointer.width * zoom * self.img_pointer.height * zoom) > 3_000_000:
                # 1. VISUAL MOVE (Instant)
                diff_x = self.mat_affine[0, 2] - getattr(self, "buffer_ref_tx", 0)
                diff_y = self.mat_affine[1, 2] - getattr(self, "buffer_ref_ty", 0)
                curr_x = getattr(self, "buffer_start_x", 0) + diff_x
                curr_y = getattr(self, "buffer_start_y", 0) + diff_y

                if self.image_id:
                    self.canvas.coords(self.image_id, curr_x, curr_y)
                self.pan_buffer_moved = True

            else:
                if self.image_id:
                    self.canvas.coords(self.image_id, self.mat_affine[0, 2], self.mat_affine[1, 2])

            self._old = event

    def mouse_release(self, event):
        self._old = None
        self.dragging = False

        # If we didn't actually move a large image buffer, do nothing
        if not getattr(self, "pan_buffer_moved", False):
            return

        self.pan_buffer_moved = False

        # Cancel any pending renders
        if self.save1:
            self.after_cancel(self.save1)

        # Trigger the re-centered, high-quality redraw
        self.save1 = self.after_idle(
            lambda: (
                setattr(self, "dragging", False),
                setattr(self, "dragging_and_zooming", False),
                self.draw_image(self.pil_image, special=3)
            )
        )

    "Keys"
    def key_press(self, delta=0):
        if len(self.filenames) <= 1:
            return
        if len(self.filenames) > (self.filename_index + delta): # ENSURE INDEX IS THE LENGTH OF THE LIST
            self.filename_index += delta
            if self.filename_index < 0: # ENSURE NEGATIVES LOOP
                self.filename_index = len(self.filenames)-1
        else: # ENSURE POSITIVES LOOP
            self.filename_index = 0
        self.set_image(self.filenames[self.filename_index])

    def rename(self, event=None):
        def ask_prefilled_text(parent, title, message, default_text=""):
            dialog = PrefilledInputDialog(parent, title, message, default_text)
            return dialog.result
        if not self.filename: return
        title = "Rename Image"
        label = ""
        path = self.filename
        old_name = os.path.basename(path)

        while True:
            new_name = ask_prefilled_text(
            self, title, label, default_text=old_name)
            if new_name:
                new_path = os.path.join(os.path.dirname(path), new_name)
                try:
                    os.rename(path, new_path)
                    self.set_image(new_path)
                    break
                except Exception as e:
                    print("Rename errors:", e)
                    label = f"{new_name} already exists in {os.path.basename(os.path.dirname(path))}"
                    old_name = new_name
            else:
                break

    def trash(self, event=None):
        if not self.filename or not self.filenames: return
        path = self.filenames.pop(self.filename_index)
        self.undo.append((path, self.filename_index))
        if not self.filenames: self.set_image(None) # doesnt exist, display none
        elif self.filename_index >= len(self.filenames): # index is over, diosplay latest
            self.set_image(self.filenames[-1])
            self.filename_index = len(self.filenames)-1
        else:
            self.set_image(self.filenames[self.filename_index]) # index exists

    def on_ctrl_z(self, event=None):
        if not self.undo: return
        path, index = self.undo.pop()
        self.set_image(path)
        self.filenames.insert(index, path)

    "GUI operations"
    def menu_open_clicked(self, event=None): #ui
        from tkinter import filedialog

        self.filenames = []
        temp = filedialog.askopenfilenames(
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.pcx *.tiff *.psd *.jfif *.gif *.webp *.webm *.mp4 *.mkv *.mov *.m4v *.avif")]
        )
        if isinstance(temp, tuple): self.filenames = list(temp)
        if not self.filenames:
            return
        self.lastdir = os.path.dirname(self.filenames[0])
        self.filename_index = 0
        self.set_image(self.filenames[self.filename_index])

    def menu_open_dir_clicked(self, event=None):
        from tkinter import filedialog
        self.lastdir = filedialog.askdirectory()
        if not self.lastdir:
            return
        file_list = []
        for root, dirs, files in os.walk(self.lastdir):
            for file in files:
                file_list.append(os.path.join(root, file))

        self.filenames = list(x for x in file_list if x.endswith((  ".png", ".jpg", ".jpeg",
                                                                                            ".bmp", ".pcx", ".tiff",
                                                                                            ".psd", ".jfif", ".gif",
                                                                                            ".webp", ".webm", ".mp4", ".mkv", ".m4v", "mov", ".avif")))
        if not self.filenames:
            return

        if self.order.get() == "Name":
            from natsort import natsorted
            self.filenames = natsorted(self.filenames, reverse=not self.reverse_sort.get())
        elif self.order.get() == "Date":
            self.filenames.sort(key=lambda path: os.path.getmtime(path), reverse=not self.reverse_sort.get()) # window's sort by "date" is a hybrid, it looks for exif, hence the mismatch if you compare these. Sort by modification date instead in file explorer.
        self.filename_index = 0
        self.set_image(self.filenames[self.filename_index])

    def menu_reveal_in_file_explorer_clicked(self, event=None):
        if not self.filename: return
        import subprocess
        subprocess.run(['explorer', '/select,', os.path.normpath(self.filename)])

    def toggle_statusbar(self):
        if not self.statusbar.get():
            self.frame_statusbar.pack_forget()
            self.divider.pack_forget()
            if self.vlc_frame:
                vlc_player = self.old
                if vlc_player and vlc_player.video_frame:
                    w, h = self.master.winfo_geometry().split("+",1)[0].split("x", 1)
                    w = int(w)
                    h = int(h)

                    vlc_player.video_container.config(width=w, height=h)
                    vlc_player.video_frame.config(width=w, height=h - 35)  # leave space for controls
                    vlc_player.controls_frame.config(width=w)
                    self.master.update()
            elif self.pil_image:
                self.statusbar_event = True
        else:
            if self.statusbar_up_down: self.canvas.pack_forget()
            self.pack_statusbar()
            self.frame_statusbar.pack(side=tk.TOP if self.statusbar_up_down else tk.BOTTOM, fill=tk.X)
            if self.statusbar_up_down: self.canvas.pack(expand=True, fill=tk.BOTH)
            self.divider.pack(expand=False, fill=tk.X)

            if self.vlc_frame:
                vlc_player = self.old
                if vlc_player and vlc_player.video_frame:
                    w, h = self.master.winfo_geometry().split("+",1)[0].split("x", 1)
                    w = int(w)
                    h = int(h)-20

                    vlc_player.video_container.config(width=w, height=h)
                    vlc_player.video_frame.config(width=w, height=h - 35)  # leave space for controls
                    vlc_player.controls_frame.config(width=w)
            elif self.pil_image:
                self.statusbar_event = True

    def toggle_ram_indicator(self):
        if self.show_ram.get():
            self.ram_indicator.pack(side=tk.LEFT)
        else:
            self.ram_indicator.pack_forget()

    def window_resize(self, event): #window
        if self.filename == None: return
        if self.statusbar_event:
            self.statusbar_event = False
            self.zoom_fit()
            self.draw_image(self.pil_image)
            return
        if (event.widget is self.canvas or event.widget is self.master) and self.pil_image:
            self.zoom_fit()
            self.dragging = True

            self.draw_image(self.pil_image, drag=True, initial_filter=Image.Resampling.NEAREST)

            if self.save1:
                self.after_cancel(self.save1)

            #self.update_idletasks() # prevent lag
            self.save1 = self.after(self.filter_delay.get(), lambda: self.after_idle(lambda: (self._imagetk_cache.clear(), self._zoom_cache.clear(), setattr(self, "first_render_info", None), setattr(self, "second_render_info", None), setattr(self, "debug", []), self.draw_image(self.pil_image), setattr(self, "dragging", False))))
        elif self.vlc_frame:
            vlc_player = self.old  # or however you store the instance
            if vlc_player and vlc_player.video_frame:
                w = event.width
                h = event.height

                if self.statusbar.get():
                    h -= 25

                # Resize the containing frames
                vlc_player.video_container.config(width=w, height=h)

                vlc_player.video_frame.config(width=w, height=h - 35)  # leave space for controls
                vlc_player.controls_frame.config(width=w)

        # Move the instructions text to the new center
        # We find it using the "sorter" tag
        w, h = event.width, event.height
        if self.app2 and hasattr(self.app2, "canvas") and self.app2.canvas.master == self.master:
            self.app2.canvas.coords("sorter", w // 2, h // 2)

    def window_close(self, e=None):
        from send2trash import send2trash
        if self.gui:
            self.gui.displayed_obj = None
        self.save_json()
        for x in self.undo:
            path = os.path.normpath(x[0])
            try:
                send2trash(path)
            except Exception as e:
                print("Trash errors:", e)
        if self.gui and self.gui.Image_frame:
            self.gui.Image_frame.set_vals(self.savedata)
        if self.drag_buffer:
            self.after_cancel(self.drag_buffer)
        if self.save:
            self.after_cancel(self.save)
        if self.save1:
            self.after_cancel(self.save1)
        if self.memory_after_id:
            self.after_cancel(self.memory_after_id)
        if self.gif_after_id:
            self.after_cancel(self.gif_after_id)
        if self.gif_gen_after_id:
            self.after_cancel(self.gif_gen_after_id)

        self.full_res = None
        self.pil_image = None
        self.image = None

        self.canvas = None
        self.image_id = None
        self.frames.clear()
        with self._frame_lock:
            self.full_res = None
            self.cache.clear()
            self._zoom_cache.clear()
            self._imagetk_cache.clear()
            self.first_render_info = None
            self.second_render_info = None
            self.debug = []

        if self.gui:
            self.gui.second_window_viewer = None
        if hasattr(self, "app2") and self.app2 is not None:
            self.app2.close_search()

        if self.vlc_frame:
            self.old.destroy(threaded=False)
            self.vlc_frame.destroy()
            self.vlc_frame = None
            del self.old

        if self.loader is not None:
            self.loader.stop()
            self.loader = None
        self.destroy()
        self.master.destroy()

    # Affine transforms
    def reset_transform(self):
        self.mat_affine = np.eye(3)

    def translate(self, ox, oy):
        m = np.eye(3)
        m[0, 2], m[1, 2] = ox, oy
        self.mat_affine = m @ self.mat_affine

        scale_up = np.eye(3)
        _, _, f = self.scale_key
        inv_f = 1.0 / f
        scale_up[0,0] = scale_up[1,1] = inv_f
        self.combined = self.mat_affine @ scale_up

    def scale(self, s):
        m = np.eye(3)
        m[0, 0], m[1, 1] = s, s
        self.mat_affine = m @ self.mat_affine
        self.get_scale_key()

    def scale_at(self, s, cx, cy):
        self.translate(-cx, -cy)
        self.scale(s)
        self.translate(cx, cy)

    def zoom_fit(self, handle=None):
        if not self.img_pointer: return
        iw, ih = (handle.width, handle.height) if handle else (self.img_pointer.width, self.img_pointer.height)
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        if iw <= 0 or ih <= 0 or cw <= 0 or ch <= 0: return
        self.reset_transform()
        s = min(cw / iw, ch / ih)
        ox, oy = (cw - iw * s) / 2, (ch - ih * s) / 2
        self.scale(s)
        self.translate(ox, oy)

    "Display"
    def _set_info(self, filename, ext, is_video=False):
        if self.standalone:
            self.master.winfo_toplevel().title(f"{self.title} - {os.path.basename(filename)}")
        else:
            original = self.gui.title().split(" -", 1)[0]
            self.gui.title(f"{original} - {os.path.basename(filename)}")
        size_bytes = os.path.getsize(filename)
        val = size_bytes
        unit = "B"
        if val >= 1000:
            val /= 1024
            unit = "KB"
            if val >= 1000:
                val /= 1024
                unit = "MB"
                if val >= 1000:
                    val /= 1024
                    unit = "GB"
        if unit == "B": text = f"{int(val):^5d} {unit}"
        else: text = f"{val:^5.1f} {unit}"

        self.label_image_size_var.set(text)
        self.label_image_format_var.set(f"{ext.upper()}")
        #self.label_image_mode_var.set(f"{ext.upper()} if hasattr(self.pil_image, 'mode') else ext.upper()")

        if not is_video:
            x, y = (self.img_pointer.width, self.img_pointer.height)
            text = f"{x}x{y}"
            self.label_image_dimensions_var.set(f"{text:^11}")
            return (x, y)

    def set_image(self, filename, obj=None, adjacent=[], first_run=False):
        self.first_run = first_run
        with self._frame_lock:
            self.adjacent = adjacent
        if self.a: # guards against vlc crashes by rejecting queued tkinter calls. dont remove
            return
        self.a = True
        " Give image path and display it "
        self.id = object()
        self.timer.start()

        if not self.reset(filename): return # returns False if we cant clear the canvas or cant set the image. (unsupported format)

        self.filename = filename
        self.ext = filename.rsplit(".", 1)[1].lower()
        self.obj = obj
        thumbpath = None if not obj or self.thumbnail_var.get().lower() == "no" else obj.thumbnail
        if self.ext in ("mp4", "webm", "mkv", "m4v", "mov"): # is video
            self.image = None
            self.canvas.delete("_IMG")
            id1 = self.after(0, self._set_video)
            self.draw_queue.append(id1)
            return
        try:
            self.img_pointer = pyvips.Image.new_from_file(filename)
        except Exception as e:
            print("Coudldn't load image:", e)
            return
        self.x, self.y = self._set_info(self.filename, self.ext)
        if hasattr(obj, "thumbnail") and not self.thumbnail_var.get().lower() == "no thumb":
            thumbpath = obj.thumbnail
        else:
            thumbpath = filename

        if self.ext in ("gif", "webp"): # is animation
            """if thumbpath:
                self._set_thumbnail(thumbpath=thumbpath)"""

            self._set_animation(filename)
        else: # is picture
            token = None
            doing_thumb = False
            if self.thumbnail_var.get() != "No thumb":
                doing_thumb = True
                token = self._set_thumbnail(thumbpath=thumbpath)

            self._set_picture(filename, token, doing_thumb)

    def reset(self, filename):
        def close_vlc():
            if self.vlc_frame != None:
                def close_old(frame):
                    if frame:
                        frame.player.pause()
                        frame.destroy()  # Bug fix for mp4
                        frame = None
                self.vlc_frame.pack_forget()
                if self.canvas:
                    self.canvas.pack(expand=True, fill=tk.BOTH)
                close_old(self.old)
                self.vlc_frame = None
                self.old = None
                if self.statusbar.get():
                    self.frame_statusbar.pack_forget()
                    self.divider.pack_forget()
                    self.divider.pack(expand=False, fill=tk.X)
                    self.frame_statusbar.pack(expand=False, fill=tk.X)

        self.obj = None
        for call in self.draw_queue:
            self.after_cancel(call)
        self.draw_queue.clear()
        # gif thread is experimentally closed via id check, id changes every time set_image is called, so each thread should exit cleanly.

        if self.gif_after_id:
            self.after_cancel(self.gif_after_id)
        if self.gif_gen_after_id:
            self.after_cancel(self.gif_gen_after_id)
        if self.draw_img_id:
            self.after_cancel(self.draw_img_id)
        if self.zoom_after_id:
            self.after_cancel(self.zoom_after_id)

        self.full_res = None
        self.pil_image = None
        self.img_pointer = None

        self.gif_after_id = None
        self.gif_gen_after_id = None
        self.open_thread = None
        self._stop_thread.clear()

        self.frames.clear()
        with self._frame_lock:
            self.full_res = None
            self._zoom_cache.clear()
            self._imagetk_cache.clear()
        self.debug.clear()
        self.lazy_index = 0

        self.filename = None
        #self.image = None
        self.image_id = None
        self.is_gif = False
        self.first_render_info = None
        self.second_render_info = None
        self.debug = []
        self.render_info.config(text="R:")
        #self.canvas.delete("_IMG")

        if not filename or not os.path.exists(filename):
            self.image = None
            self.canvas.delete("_IMG")
            if self.standalone:
                self.master.winfo_toplevel().title(self.title)
            self.label_image_format_var.set(f"")
            self.label_image_mode_var.set("")
            self.label_image_dimensions_var.set("")
            self.label_image_size_var.set("")
            #self.update()
            close_vlc()
            #self.update()
            self.a = False
            return False
        else:
            ext = filename.rsplit(".", 1)[1].lower()
            supported_formats = {"png", "gif", "jpg", "jpeg", "bmp", "pcx", "tiff", "webp", "psd", "jfif", "avif", "mp4", "mkv", "m4v", "mov", "webm"}
            if ext in supported_formats:
                if ext not in ("mp4", "webm", "mkv", "m4v", "mov"):
                    #self.update()
                    close_vlc()
                    #self.update()
                self.f = True
                return True

            else:
                self.image = None
                self.canvas.delete("_IMG")
                if self.standalone:
                    self.master.winfo_toplevel().title(self.title)
                self.label_image_format_var.set("")
                self.label_image_mode_var.set("")
                self.label_image_dimensions_var.set("")
                self.label_image_size_var.set("")
                #self.update()
                close_vlc()
                #self.update()
                self.a = False
                return False

    "Static Images"
    def _set_thumbnail(self, thumbpath=None):
        if thumbpath: token = self.loader.request_load(thumbpath, caller="cached_thumb")
        else: token = self.loader.request_load(thumbpath, caller="gen_thumb")
        return token

    def _set_picture(self, filename, token=None, doing_thumb=False):
        "Close the handle and load full copy to memory."
        self.a = False

        if self.do_caching.get():
            with self._frame_lock:
                cached = self.cache.get(filename)

            if cached:
                if doing_thumb and self.do_caching.get():
                    self.pending_cached = (filename, cached, self.current_load_token) # previous, thumb token
                else:
                    self._on_async_image_ready(filename, cached, self.current_load_token, caller="cached")

                with self._frame_lock:
                    keys_to_check = list(self.cache.keys())
                    print(len(self.cache))
                    for x in keys_to_check:
                        if x != filename and x not in self.adjacent:
                            del self.cache[x]
                with self._frame_lock:
                    self.adjacent = [x for x in self.adjacent if x not in self.cache.keys() and x != filename]
                    if self.adjacent:
                        self.loader.request_load(self.adjacent, token, caller="load_to_cache")
                return

        if self.selected_option1.get() != "No buffer":
            if type(self.filter) == Image.Resampling and self.drag_quality.name.lower() == self.filter.name.lower():
                pass
            elif type(self.filter) == str and self.filter.lower() == "pyvips":
                pass
            else:
                token = self.loader.request_load(filename, token, caller="buffer") # token from set_thumbnail tells the loader to not ignore the thumbnail call as it empties the queue.
        token = self.loader.request_load(filename, token, caller="preloader") # token from set_thumbnail tells the loader to not ignore the thumbnail call as it empties the queue.
        token = self.loader.request_load(filename, token, caller="optimization")
        if self.do_caching.get() and self.adjacent:
            with self._frame_lock:
                self.loader.request_load([path for path in self.adjacent if path not in self.cache.keys()], token, caller="load_to_cache")

    "Animation"
    def _set_animation(self, filename):
        self.zoom_fit()
        self.a = False

        is_animated = True if self.img_pointer.get_n_pages() > 1 else False

        if is_animated:
            self.is_gif = True
            self.open_thread = Thread(target=self._preload_frames, args=(self.filename, self.id), name="(Thread) Viewer frame preload", daemon=True)
            self.open_thread.start()
            self.timer1 = perf_counter()
        else:
            self.loader.request_load(filename)
    def _preload_frames(self, filename, id1):
        def fallback():
            self.is_gif = False
            self.frames.clear()
            self._set_picture(filename)
        if self._stop_thread.is_set(): return
        try:
            with Image.open(filename, "r") as handle: # I like how PIL allows us to lazily load each frame.
                i = 0
                while True:
                    with self._frame_lock:
                        if self._stop_thread.is_set(): return
                        if self.filename != filename: return
                        if id1 != self.id: return
                    if i == 1: self.after(0, self._update_frame)
                    handle.seek(i)
                    duration = handle.info.get('duration', 100) or 100
                    if handle.mode != "RGBA": frame = handle.convert("RGBA")
                    else: frame = handle.copy()
                    i += 1
                    with self._frame_lock:
                        if self._stop_thread.is_set(): return
                        if self.filename != filename: return
                        if id1 != self.id: return
                        self.frames.append((frame, duration))
                        self._zoom_cache.set_maxsize(i)
                        self._imagetk_cache.set_maxsize(i)

        except EOFError:
            if i == 1:
                self.after(0, fallback)
                print("Error in _preload_frames (eoferror), falling back as a static image.")
    def _update_frame(self, lazy_index=0):
        if not self.is_gif: return
        self.timer.start()
        frames = self.frames
        if not frames: return
        if lazy_index > len(frames)-1:
            lazy_index = 0 # looping back
        self.lazy_index = lazy_index
        with self._frame_lock:
            self.pil_image, gif_duration = frames[lazy_index] # Updates reference (for panning/zooming)
            self.full_res = self.pil_image
        self.anim_info.config(text=f"A: {lazy_index+1}/{len(frames)}/{gif_duration}ms")

        self.gif_after_id = self.after(gif_duration, lambda: self._update_frame(lazy_index+1))

        def _step():
            self.draw_image(self.pil_image, drag=self.dragging, initial_filter=Image.Resampling.NEAREST if self.dragging else None)

        self.after(0, _step)

    "Video"
    def _set_video(self):
        def close_vlc():
            if self.vlc_frame != None:

                self.vlc_frame.pack_forget()
                if self.canvas:
                    self.canvas.pack(expand=True, fill=tk.BOTH)
                if self.old:
                    self.old.player.pause()
                    self.old.destroy()  # Bug fix for mp4
                    self.old = None
                self.vlc_frame = None
                self.old = None

        self._set_info(self.filename, self.ext, is_video=True)
        #self.update()
        close_vlc()
        f = self.vlc_frame == None
        new = VlcPlayer(self, self.master.winfo_geometry().split("+",1)[0], self.filename, self.label_image_dimensions_var)
        if f and self.statusbar.get():
            self.frame_statusbar.pack_forget()
            self.divider.pack_forget()
            self.divider.pack(expand=False, fill=tk.X)
            self.frame_statusbar.pack(expand=False, fill=tk.X)
        #self.update()
        self.a = False
        self.old = new

    "Rendering"
    def draw_image(self, pil_image, drag=False, ignore_anti_alias=False, initial_filter=None, low_qual=False, special=1, special2=False):
        start = perf_counter()
        if self.f and not special2:
            self.image = None
            self.canvas.delete("_IMG")
        def calc_transform(aa, zoom):
            if special2:
                with self._frame_lock:
                    matrix = self.mat_affine.copy()
            else:
                matrix = self.mat_affine.copy()
            if fast_pan_active:
                matrix[0, 2] = 0; matrix[1, 2] = 0
            else:
                matrix[0, 2] -= buffer_screen_x
                matrix[1, 2] -= buffer_screen_y

            if aa and (zoom < 1.0):
                if special2:
                    with self._frame_lock:
                        matrix = self.combined.copy()
                else:
                    matrix = self.combined.copy()
                if fast_pan_active:
                    matrix[0, 2] = 0
                    matrix[1, 2] = 0
                else:
                    matrix[0, 2] -= buffer_screen_x
                    matrix[1, 2] -= buffer_screen_y

            inv = np.linalg.inv(matrix)
            return (inv[0,0], inv[0,1], inv[0,2],
                    inv[1,0], inv[1,1], inv[1,2])
        def get_transform_filter(aa, gif, resize_filter):
            if aa or gif: transform_filter = Image.Resampling.NEAREST
            elif resize_filter == Image.Resampling.LANCZOS or resize_filter == "pyvips": transform_filter = Image.Resampling.BICUBIC
            else: transform_filter = resize_filter
            return transform_filter
        def get_transform_key(lazy_index, scale_key, affine_inv, cw, ch, transform_filter):
            affine_bucket = (round(affine_inv[0], 3), round(affine_inv[1], 3), int(round(affine_inv[2])), round(affine_inv[3], 3), round(affine_inv[4], 3), int(round(affine_inv[5])))
            transform_key = (lazy_index, scale_key, affine_bucket, cw, ch, int(transform_filter))
            return transform_key # pan/zoom/rotation key
        def get_source(pil_img_variables): # movements pan/zoom/rotation
            pil_image, aa, should_blur, resize_filter = pil_img_variables
            with self._frame_lock:
                if self._zoom_cache:
                    zoom_cache = True
                else:
                    zoom_cache = False
            if ignore_anti_alias or (initial_filter != None and not drag): # thumbnail
                if pil_image.mode != "RGBA": pil_image = pil_image.convert("RGBA")
                return pil_image
            if not aa or zoom >= 1.0:
                if gif: return pil_image
                pil_image = self.full_res
                if not self.full_res:
                    try:
                        with Image.open(self.filename) as img:
                            pil_image = img.copy()
                            if pil_image.mode != "RGBA": pil_image = pil_image.convert("RGBA")
                            with self._frame_lock:
                                self.full_res = pil_image
                    except:
                        buffer = self.img_pointer.write_to_memory()
                        mode = get_mode(self.img_pointer)
                        resized = Image.frombytes(mode, (self.img_pointer.width, self.img_pointer.height), buffer, "raw")
                        if resized.mode != "RGBA": resized = resized.convert("RGBA")
                        with self._frame_lock:
                            self.full_res = resized

                return pil_image
            elif should_blur and zoom_cache: # gen levels from cached instead for a blur effect and maybe perf?
                default = Image.Resampling.NEAREST # default drag quality when resizing window
                with self._frame_lock:
                    tupl, cached = self._zoom_cache.last()
                index, last_zoom_key = tupl
                f = last_zoom_key / 1000
                size1 = max(1, round(self.img_pointer.width * f)), max(1, round(self.img_pointer.height * f))
                zoom_key = (self.lazy_index, last_zoom_key)
                with self._frame_lock:
                    self._zoom_cache.clear()
                    cached = cached or pil_image.resize(size1, default)
                    self._zoom_cache[zoom_key] = cached

                if zoom >= 1.0: # DRAGGING bigger
                    resized = cached.resize((self.img_pointer.width, self.img_pointer.height), default)
                    if resized.mode != "RGBA": resized = resized.convert("RGBA")
                elif zoom < 1.0: # DRAGGING smaller
                    resized = cached.resize(size, default)
                    if scale_key < last_zoom_key:
                        if not self.full_res:
                            try:
                                with Image.open(self.filename) as img:
                                    copy = img.copy()
                                    if copy.mode != "RGBA": copy = copy.convert("RGBA")
                                    self.full_res = copy
                            except:
                                buffer = self.img_pointer.write_to_memory()
                                mode = get_mode(self.img_pointer)
                                resized = Image.frombytes(mode, (self.img_pointer.width, self.img_pointer.height), buffer, "raw")
                                if resized.mode != "RGBA": resized = resized.convert("RGBA")
                                with self._frame_lock:
                                    self.full_res = resized

                        resized = self.full_res.resize(size, default)
                        new_zoom_key = (self.lazy_index, scale_key)
                        if resized.mode != "RGBA": resized = resized.convert("RGBA")
                        with self._frame_lock:
                            self._zoom_cache.clear()
                            self._zoom_cache[new_zoom_key] = resized
            elif zoom < 1.0: # thumb gen # window resize resets caches
                use_pyvips = resize_filter == "pyvips"
                if initial_filter == None and not low_qual:
                    resized = self._zoom_cache.__getitem__(self.zoom_key)
                    if resized: return resized
                if gif:
                    try:
                        f1 = Image.Resampling.LANCZOS if use_pyvips else resize_filter
                        resized = pil_image.resize(size, f1)
                    except Exception as e:
                        print("Error in draw (gif):", e)
                        return
                else:
                    try:
                        if use_pyvips:
                            if low_qual:
                                try:
                                    if not self.full_res:
                                        with Image.open(self.filename) as img:
                                            copy = img.copy()
                                            if copy.mode != "RGBA": copy = copy.convert("RGBA")
                                            self.full_res = copy
                                    resized1 = self._zoom_cache.__getitem__(self.zoom_key)
                                    if resized1:
                                        correction = size[0] - resized1.width
                                    else: correction = 0
                                    resized = self.full_res.resize((size[0]-correction, size[1]), Image.Resampling.NEAREST)
                                    return resized
                                except: pass
                            vips_img = pyvips.Image.thumbnail_image(self.img_pointer, size[0], height=size[1])
                            buffer = vips_img.write_to_memory()
                            mode = get_mode(vips_img)
                            resized = Image.frombytes(mode, (vips_img.width, vips_img.height), buffer, "raw")
                        else:
                            resized = None
                            try:
                                if not self.full_res:
                                    with Image.open(self.filename) as img:
                                        copy = img.copy()
                                        if copy.mode != "RGBA": copy = copy.convert("RGBA")
                                        self.full_res = copy
                                if low_qual: return self.full_res.resize(size, Image.Resampling.NEAREST)
                                resized = self.full_res.resize(size, resize_filter)
                            except:
                                vips_img = pyvips.Image.thumbnail_image(self.img_pointer, size[0], height=size[1])
                                buffer = vips_img.write_to_memory()
                                mode = get_mode(vips_img)
                                resized = Image.frombytes(mode, (vips_img.width, vips_img.height), buffer, "raw")
                    except Exception as e:
                        print("Error in draw:", e)
                        return
                if resized.mode != "RGBA": resized = resized.convert("RGBA")
                with self._frame_lock:
                    self._zoom_cache[(self.lazy_index, scale_key)] = resized
            return resized

        def get_imagetk(resized_pil_img: Image.Image=None, variables=None): # static redraws for animation
            if not resized_pil_img and not variables: return
            source = resized_pil_img or get_source(variables)
            if source == None: return None
            try:
                # old was cw, ch
                dst = source.transform((render_w, render_h), Image.AFFINE, affine_inv, resample=transform_filter, fillcolor=self.bg_color)
            except:
                self._zoom_cache.clear()
                self.draw_image(pil_image)
                return

            if special2:
                self.dont_garbage_collect = dst
                return dst
            imagetk = ImageTk.PhotoImage(dst)

            if gif and not drag:
                with self._frame_lock:
                    self._imagetk_cache[transform_key] = imagetk
            return imagetk

        # prefetch values
        if special2:
            with self._frame_lock:
                cw, ch = self.cw, self.ch
                aa = self.aa
                gif = self.is_gif
                if cw <= 1 or ch <= 1 or self.img_pointer == None: return
                lazy_index = self.lazy_index
                zoom, scale_key, f = self.scale_key
                tw = max(1, int(self.img_pointer.width * zoom))
                th = max(1, int(self.img_pointer.height * zoom))
                size = max(1, round(self.img_pointer.width * f)), max(1, round(self.img_pointer.height * f))
        else:
            cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
            self.cw, self.ch = cw, ch
            aa = False if ignore_anti_alias else self.anti_aliasing.get()
            self.aa = aa
            gif = self.is_gif
            if cw <= 1 or ch <= 1 or self.img_pointer == None: return
            lazy_index = self.lazy_index
            zoom, scale_key, f = self.scale_key
            tw = max(1, int(self.img_pointer.width * zoom))
            th = max(1, int(self.img_pointer.height * zoom))
            size = max(1, round(self.img_pointer.width * f)), max(1, round(self.img_pointer.height * f))

        fast_pan_active = (tw * th) < 3_000_000

        # end goal here is to have 1 here for fast zooming, then when user no longer zooms, so quick zoom ends, we render with buffer multiplier 3 or 5.
        # when mouse left ends we schedule a buffer refresh that is cancelled if user pans more.
        buffer_multiplier = special
        if not fast_pan_active:
            # 1. Define the size: 3x the current window
            render_w = int(cw * buffer_multiplier)
            render_h = int(ch * buffer_multiplier)

            offset_factor = (buffer_multiplier - 1) / 2
            # 2. Define the screen position:
            # To center the middle 'tile' of our 3x3 grid on the screen,
            # the image's top-left must be at (-cw, -ch)
            buffer_screen_x = -int(cw * offset_factor)
            buffer_screen_y = -int(ch * offset_factor)
            self.buffer_screen_x, self.buffer_screen_y = buffer_screen_x, buffer_screen_y

            # 3. Store these so mouse_move knows the 'home' position of this specific render
            if special2:
                with self._frame_lock:
                    self.buffer_ref_tx = self.mat_affine[0, 2]
                    self.buffer_ref_ty = self.mat_affine[1, 2]
                    self.buffer_start_x = buffer_screen_x
                    self.buffer_start_y = buffer_screen_y

            else:
                self.buffer_ref_tx = self.mat_affine[0, 2]
                self.buffer_ref_ty = self.mat_affine[1, 2]
                self.buffer_start_x = buffer_screen_x
                self.buffer_start_y = buffer_screen_y
        else:
            # Small image mode: standard behavior
            render_w = tw
            render_h = th
            if special2:
                with self._frame_lock:
                    buffer_screen_x = self.mat_affine[0, 2]
                    buffer_screen_y = self.mat_affine[1, 2]
                    self.buffer_screen_x, self.buffer_screen_y = buffer_screen_x, buffer_screen_y
            else:
                buffer_screen_x = self.mat_affine[0, 2]
                buffer_screen_y = self.mat_affine[1, 2]
                self.buffer_screen_x, self.buffer_screen_y = buffer_screen_x, buffer_screen_y

        # ---------------------------

        # prefs
        if special2:
            with self._frame_lock:
                resize_filter = initial_filter if initial_filter is not None else self.filter
        else:
            resize_filter = initial_filter if initial_filter is not None else self.filter
        resize_blur = True
        resize_blur_for_gif = False
        should_blur = resize_blur_for_gif and drag if gif else resize_blur and drag

        affine_inv = calc_transform(aa, zoom) # calculate the transform
        transform_filter = get_transform_filter(aa, gif, resize_filter) # generate keys for cache
        transform_key = get_transform_key(lazy_index, scale_key, affine_inv, cw, ch, transform_filter) # anim rame, scale, transformation, canvas size and filter determine render cache key. (imagetk)
        self.zoom_key = (lazy_index, scale_key) # zoom level is just frame and scale (pil_image)

        def clean_cache(resize_blur_for_gif, gif, zoom):
            if not resize_blur_for_gif and gif:
                if zoom > 1.0: # zoom below 1.0 shouldnt keep cache alive for gif.
                    with self._frame_lock:
                        self._zoom_cache.clear()
                elif drag: # dragging shouldnt keep any cache alive for gif.
                    with self._frame_lock:
                        self._zoom_cache.clear()
                        self._imagetk_cache.clear()
        clean_cache(resize_blur_for_gif, gif, zoom)

        with self._frame_lock:
            imagetk = self._imagetk_cache.__getitem__(transform_key) if gif else None
        if not imagetk:
            imagetk = get_imagetk(variables=(pil_image, aa, should_blur, resize_filter))
            if special2: return imagetk
            if imagetk == None: return
        if initial_filter is not None and not drag: # removes the initial render from the cache.
            with self._frame_lock:
                self._zoom_cache.clear()
                self._imagetk_cache.clear()

        tx = self.mat_affine[0, 2] if fast_pan_active else buffer_screen_x
        ty = self.mat_affine[1, 2] if fast_pan_active else buffer_screen_y

        if self.image_id:
            self.canvas.itemconfig(self.image_id, image=imagetk)
            self.canvas.coords(self.image_id, tx, ty)
        else:
            self.image_id = self.canvas.create_image(tx, ty, anchor='nw', image=imagetk, tags="_IMG")

        self.image = imagetk

        if self.app2 and hasattr(self.app2, "canvas") and self.app2.canvas and self.app2.canvas.master == self.master:
            self.app2.bring_forth()

        time = self.timer.stop()
        average_render_time = ""
        if self.second_render_info:
            self.debug.append(round(perf_counter()-start, 3)*1000)
            if len(self.debug) > 10: self.debug.pop(0)
            average_render_time = f", {(sum(self.debug)/len(self.debug)):.1f}"
        self.second_render_info = self.second_render_info or f"-{time}" if self.first_render_info else None
        self.first_render_info = self.first_render_info or f"R: {time}"

        info_msg = None
        if self.first_render_info:
            info_msg = self.first_render_info
        if self.second_render_info and (self.thumbnail_var.get() != "No thumb" or (self.drag_quality != "No buffer" and not self.filter == "pyvips")):
            info_msg += self.second_render_info
        if self.debug :
            info_msg += average_render_time
        info_msg += " ms"

        self.render_info.config(text=info_msg)

        if self.gui and drag:
            pass
        else:
            self.update_idletasks() # idea is that no queue is formed.

        if self.f:
            self.f = False

        if low_qual:
            #broken
            def helper(x):
                def helper2(x, n, id):
                    source = self.draw_image(x, special=n, special2=True)
                    def helper3(id, source):
                        if id != self.zoom_after_id:
                            return
                        self.ready = False
                        imagetk = ImageTk.PhotoImage(source)

                        tx = self.buffer_screen_x
                        ty = self.buffer_screen_y

                        if self.image_id:
                            self.canvas.itemconfig(self.image_id, image=imagetk)
                            self.image = imagetk
                            self.canvas.coords(self.image_id, tx, ty)
                        self.canvas.update()
                        self.ready = True

                    self.canvas.after(0, helper3, id, source)

                a = Thread(target=helper2, args=(x, 5, self.zoom_after_id), daemon=True)
                a.start()
            def helper1(x, n=5):
                self.draw_image(x, special=n)
            if self.zoom_after_id: self.after_cancel(self.zoom_after_id)
            if zoom <= 1.0:
                after_id3 = self.after(40, helper1, pil_image)
                self.zoom_after_id = after_id3
                self.draw_queue.append(after_id3)
            else:
                if self.dragging: # force old implementation, redraws. If we dragged and zoomed at the same time, a flag should be active "dragging+zoom", that forces redraw in mouse_move_left.
                    self.dragging_and_zooming = True
                    self.draw_image(pil_image, special=1)
                else:
                    after_id3 = self.after(40, helper, pil_image)
                    self.zoom_after_id = after_id3
                    self.draw_queue.append(after_id3)
        if self.first_run:
            self.first_run = False
            self.gui.fileManager.gui.bindhandler.search_widget.new_canvas(self.canvas)
            self.canvas.lift(self.gui.fileManager.gui.bindhandler.search_widget.a)

    def _on_async_image_ready(self, path, image, token, caller):
        """Called in main thread after background decode finishes."""
        if image is None:
            print("Image load failed for:", path)
            return
        if getattr(self, "current_load_token", None) != token:
            if caller == "cached":
                return
            image.close()
            image = None
            return  # outdated load result, ignore

        if caller == "cached":
            self.pil_image = image["img"]
            if self.filter == "pyvips" and not self.quick_zoom.get():
                self.img_pointer = image["full_res"]
            else:
                self.full_res = image["full_res"]
        else:
            self.pil_image = image

        if caller == "cached_thumb" or caller == "gen_thumb":
            self.zoom_fit(image)
            with self._frame_lock:
                self._zoom_cache.set_maxsize(0) # wont allow thumbnail in cache
                self._imagetk_cache.set_maxsize(0)

            self.draw_image(image, ignore_anti_alias=True, initial_filter=Image.Resampling.NEAREST)

            if hasattr(self, "pending_cached") and self.pending_cached[2] == token and self.do_caching.get():
                #self._on_async_image_ready(self.pending_cached[0], self.pending_cached[1], self.current_load_token, caller="cached")
                id = self.after(0, lambda p=self.pending_cached[0], c=self.pending_cached[1], t=self.current_load_token: self._on_async_image_ready(p, c, t, caller="cached"))
                self.draw_queue.append(id)

        else:
            self.zoom_fit()
            with self._frame_lock:
                self._zoom_cache.set_maxsize(32)
                self._imagetk_cache.set_maxsize(0)
            if caller == "cached":
                self._zoom_cache[(self.lazy_index, self.scale_key[1])] = self.pil_image
                self.draw_image(self.pil_image, initial_filter=None)
            else:
                id2 = self.after(0, lambda: self.draw_image(image if not caller == "cached" else image[0], initial_filter=self.drag_quality if caller == "buffer" else None))
                self.draw_queue.append(id2)

    def get_source_1(self, path, initial_filter=None, ignore_caching=False):
        "Returns the source image resized to the canvas width and post processed with filters."
        "We get this here and cache it for the main thread."
        if ignore_caching:
            handle = pyvips.Image.new_from_file(path)
        else:
            handle = self.img_pointer
        def get_scale_key():
            if handle == None: return
            iw, ih = handle.width, handle.height
            cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
            if iw <= 0 or ih <= 0 or cw <= 0 or ch <= 0: return

            #### reset transform
            mat_affine = np.eye(3)
            ####
            s = min(cw / iw, ch / ih)
            ox, oy = (cw - iw * s) / 2, (ch - ih * s) / 2
            ### scale
            m = np.eye(3)
            m[0, 0], m[1, 1] = s, s
            mat_affine = m @ mat_affine
            ########## here
            mat = mat_affine
            sx, sy = (mat[0, 0]**2 + mat[1, 0]**2)**0.5, (mat[0, 1]**2 + mat[1, 1]**2)**0.5

            zoom = round(min(sx, sy), 3)

            scale_key = int(zoom * 1000)
            scale_key = zoom, scale_key, max(0.001, zoom)

            ####
            #### translate
            m = np.eye(3)
            m[0, 2], m[1, 2] = ox, oy
            mat_affine = m @ mat_affine

            scale_up = np.eye(3)
            _, _, f = scale_key
            inv_f = 1.0 / f
            scale_up[0,0] = scale_up[1,1] = inv_f
            self.combined = mat_affine @ scale_up
            ####

            ###
            mat = mat_affine
            sx, sy = (mat[0, 0]**2 + mat[1, 0]**2)**0.5, (mat[0, 1]**2 + mat[1, 1]**2)**0.5
            scale_key = int(zoom * 1000)
            return zoom, scale_key, max(0.001, zoom)

        def get_source(): # movements pan/zoom
            resized = None
            if not self.anti_aliasing.get() or zoom >= 1.0:
                pil_img = None
                with Image.open(path) as img:
                    pil_img = img.copy()
                    if pil_img.mode != "RGBA": pil_img = pil_img.convert("RGBA")
                return pil_img
            elif zoom < 1.0: # thumb gen # window resize resets caches
                start = perf_counter()
                try:
                    if self.filter == "pyvips":
                        vips_img = pyvips.Image.thumbnail(path, max(size))
                        buffer = vips_img.write_to_memory()
                        mode = get_mode(vips_img)
                        resized = Image.frombytes(mode, (vips_img.width, vips_img.height), buffer, "raw")
                    else:
                        with Image.open(path) as img:
                            f1 = self.filter if self.filter != "pyvips" else Image.Resampling.LANCZOS
                            resized = img.resize(size, (initial_filter if initial_filter != None else f1))

                except Exception as e:
                    print("Error in draw:", e)
                    return
                print(perf_counter()-start)
                if resized.mode != "RGBA": resized = resized.convert("RGBA")
                if initial_filter == None and not ignore_caching:
                    with self._frame_lock:
                        self._zoom_cache[(self.lazy_index, scale_key)] = resized
            return resized

        # prefetch values
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        if cw <= 1 or ch <= 1 or handle == None: return

        zoom, scale_key, f = get_scale_key() # scale key is precomputed by get_scale_key each time def scale() is called.
        size = max(1, round(handle.width * f)), max(1, round(handle.height * f)) # calc desired size

        source = get_source()
        return source

    def lazy_load_full_res_to_memory_for_zooming(self, id, token, path=None): # pil version of the same method, but also improves zooming in low res for pyvips. (quick zoom)
        if self.current_load_token != token or self.id != id: return
        if self.filter == "pyvips" and not self.quick_zoom.get(): return # we can turn this quick zoom off optionally
        try:
            p = path if path is not None else self.filename
            with Image.open(p) as img:
                copy = img.copy()
                if copy.mode != "RGBA": copy = copy.convert("RGBA")
                if path: return copy
                with self._frame_lock:
                    if self.current_load_token != token or self.id != id: return
                    self.full_res = copy
                    if self.cache.get(self.filename):
                        self.cache[self.filename]["full_res"] = copy
        except Exception as e:
            print("PIL couldn't load image. Fallback (Some PyVips+PIL optimizations disabled):", e)

    def lazy_load_img_pointer_to_memory_for_zooming(self, id, token, path=None): # actually improves zooming performance by a tiny bit.
        if self.current_load_token != token or self.id != id: return
        if path:
            self.img_pointer = pyvips.Image.new_from_file(path)
        temp = self.img_pointer.copy_memory()
        if path: return temp
        with self._frame_lock:
            if self.current_load_token != token or self.id != id: return
            self.img_pointer = temp
            if self.cache.get(self.filename):
                self.cache[self.filename]["full_res"] = self.img_pointer

    "Helpers"
    def pyvips_to_pillows_for_thumb(self, filename, caller):
        f1 = Image.Resampling.NEAREST if self.thumbnail_var.get() == "Fast" else Image.Resampling.LANCZOS
        if caller == "cached_thumb":
            thumb = pyvips.Image.new_from_file(filename)
            res_thumb = pyvips.Image.thumbnail(filename, 32)
            if self.thumbnail_var.get() == "Fast": res_thumb = thumb
            buffer = res_thumb.write_to_memory()
            pil_format = get_mode(res_thumb)
            resized = Image.frombytes(pil_format, (res_thumb.width, res_thumb.height), buffer, "raw")
            if self.thumbnail_var.get() != "Fast": resized = resized.resize((thumb.width, thumb.height), f1)
        else:
            try:
                vips_img = pyvips.Image.thumbnail(filename, 256)
                vips_img = vips_img.gaussblur(2)
                buffer = vips_img.write_to_memory()
                pil_format = get_mode(vips_img)
                resized = Image.frombytes(pil_format, (vips_img.width, vips_img.height), buffer, "raw")
            except Exception as e:
                print("Pyvips failed to gen thumb for viewer, attempting PIL:", filename, e)
                try:
                    with Image.open(filename) as pil_img:
                        resized = pil_img.copy()
                except Exception as e:
                    print("Pil failed to gen thumb for viewer:", filename, e)
                    return

        if resized.mode != "RGBA": resized = resized.convert("RGBA")
        return resized

    def get_scale_key(self):
        mat = self.mat_affine
        sx, sy = (mat[0, 0]**2 + mat[1, 0]**2)**0.5, (mat[0, 1]**2 + mat[1, 1]**2)**0.5

        zoom = round(min(sx, sy), 3)

        scale_key = int(zoom * 1000)
        self.scale_key = zoom, scale_key, max(0.001, zoom)

    def restrict_pan(self):
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        iw, ih = self.img_pointer.width, self.img_pointer.height

        tw = iw * self.mat_affine[0, 0]
        th = ih * self.mat_affine[1, 1]

        tx = self.mat_affine[0, 2]
        ty = self.mat_affine[1, 2]

        if tw <= cw:
            tx_min, tx_max = 0, cw - tw
        else:
            tx_min, tx_max = cw - tw, 0
        tx = min(max(tx, tx_min), tx_max)

        if th <= ch:
            ty_min, ty_max = 0, ch - th
        else:
            ty_min, ty_max = ch - th, 0
        ty = min(max(ty, ty_min), ty_max)

        self.mat_affine[0, 2] = tx
        self.mat_affine[1, 2] = ty

        scale_up = np.eye(3)
        _, _, f = self.scale_key
        inv_f = 1.0 / f
        scale_up[0,0] = scale_up[1,1] = inv_f
        self.combined = self.mat_affine @ scale_up

    "Preferences"
    def set_vals(self, savedata):
        self.do_caching.set(savedata.get("pre-caching", self.do_caching.get()))
        self.unbound_var.set(savedata.get("unbound_pan", self.unbound_var.get()))
        self.quick_zoom.set(savedata.get("quick_zoom", self.quick_zoom.get()))
        self.anti_aliasing.set(savedata.get("anti_aliasing", self.anti_aliasing.get()))
        self.thumbnail_var.set(savedata.get("thumbnail_var", self.thumbnail_var.get()))
        self.selected_option1.set(savedata.get("drag_quality", "Nearest").lower().capitalize())
        self.selected_option.set(savedata.get("filter", "Nearest").lower().capitalize())

        self.statusbar.set(savedata.get("statusbar", self.statusbar.get()))
        self.statusbar_mode.set(savedata.get("statusbar_mode", self.statusbar_mode.get()))

        self.filter_delay.set(int(savedata.get("final_filter_delay", self.filter_delay.get())))
        self.thumb_qual.set(int(savedata.get("thumb_qual", self.thumb_qual.get())))
        self.volume = int(savedata.get("volume", self.volume))

    def load_json(self):
        if os.path.isfile(self.save_path):
            try:
                with open(self.save_path) as f:
                    return json.load(f)
            except Exception as e:
                print("Json load error:", e)
        return {}

    def save_json(self):
        if self.filter == "pyvips":
            name = "Pyvips"
        else:
            name= self.filter.name
        data = {
                "geometry": self.master.winfo_geometry(),       # "600x800+100+100" Width x Height + x + y
                "disable_menubar": self.disable_menubar,        # Disable the menu bar
                "statusbar": self.statusbar.get(),     # Disable the statusbar
                "statusbar_mode": self.statusbar_mode.get(),
                "order": self.order.get(),
                "reverse": self.reverse_sort.get(),
                "lastdir": self.lastdir or None,                # Last folder viewed
                "unbound_pan": self.unbound_var.get(),          # Go out of bounds
                "zoom_magnitude": self.zoom_magnitude,                # Zoom amount
                "filter": name,                         # Default filter
                "drag_quality": self.drag_quality if type(self.drag_quality) == str else self.drag_quality.name,              #
                "anti_aliasing": self.anti_aliasing.get(),
                "quick_zoom": self.quick_zoom.get(),
                "pre-caching": self.do_caching.get(),
                "thumbnail_var": self.thumbnail_var.get(),
                "final_filter_delay": self.filter_delay.get(),
                "thumb_qual": self.thumb_qual.get(),
                "statusbar_up_down": self.statusbar_up_down,
                "show_ram": self.show_ram.get(),
                "colors": self.colors,
                "volume": self.volume,
                        }
        if self.savedata:
            for key, x in data.items():
                self.savedata[key] = data[key]
        if self.standalone and not self.gui:
            with open(self.save_path, "w") as f:
                json.dump(data, f, indent=4)

def get_mode(vips_img):
    "Return the mode needed to convert a PYVIPS.Image to a PIL.Image format via PIL.Image.frombytes()."
    "Most common formats are srgb, b-w, rgb16 and grey16."
    vips_format, pil_format = str(vips_img.interpretation).lower(), None
    match vips_format:
        case "srgb":
            pil_format = "RGB" if vips_img.bands == 3 else "RGBA"
        case "b-w": pil_format = "L"
        case "rgb16": pil_format = "I;16"
        case "grey16": pil_format = "I;16"
    return pil_format

class VlcPlayer:
    """Handles VLC video playback and GUI embedding"""
    def __init__(self, app, geometry, path, info=None):
        self.last_click = perf_counter()
        self.f = True
        self._last_seek_time = 0
        self.app = app
        w, h = geometry.split('x', 1)
        self.w = int(w)
        self.h = int(h)
        if self.app.statusbar.get():
            self.h -= 25

        self.path = path
        self.info = info

        do_pack = False
        if app.vlc_frame is None:
            app.vlc_frame = ttk.Frame(app.master, style="bg.TFrame")
            do_pack = True

        self.canvas = tk.Canvas(
            app.vlc_frame,
            bg="black",
            highlightthickness=0,
            width=self.w,
            height=self.h
        )
        self.canvas.grid(row=0, column=0)

        self.handle_video()
        if do_pack:
            self.pack()

    def return_dimensions(self):
        try:
            w = self.player.video_get_width()
            h = self.player.video_get_height()
            return w, h
        except:
            return 0, 0

    def handle_video(self):
        """Set up VLC playback"""
        self.pressed = False
        self.vlc_instance = self.app.vlc_instance
        self.media_list_player = self.vlc_instance.media_list_player_new()
        self.media_list = self.vlc_instance.media_list_new()
        self.media = self.vlc_instance.media_new(self.path)
        self.media_list.add_media(self.media)
        self.media_list_player.set_media_list(self.media_list)
        self.player = self.media_list_player.get_media_player()
        self.events = self.player.event_manager()

        new_width = self.w
        new_height = self.h - 35

        self.video_container = tk.Frame(
            self.canvas,
            bg="black",
            width=self.w,
            height=self.h
        )
        self.video_container.grid_propagate(False)
        self.video_container.grid(row=0, column=0, sticky="nsew")

        self.video_frame = tk.Canvas(
            self.video_container,
            width=new_width,
            height=new_height,
            bg="black",
            highlightbackground="black",
            highlightthickness=0,
            borderwidth=0
        )
        self.video_frame.grid(row=0, column=0)

        self.controls_frame = tk.Frame(self.video_container, bg="black")
        self.controls_frame.grid(row=1, column=0, sticky="ew")
        self.controls_frame.grid_remove()
        self.controls_frame.columnconfigure(0, weight=30)
        self.controls_frame.columnconfigure(1, weight=1)

        self.timeline_slider = ttk.Scale(
            self.controls_frame,
            from_=0,
            to=self.media.get_duration(),
            orient=tk.HORIZONTAL,
            style="Horizontal.TScale"
        )
        self.timeline_slider.grid(row=0, column=0, sticky="ew", padx=(5,2), pady=5)

        def timeline_click(event):
            self.pressed = True
            slider = event.widget
            from_ = float(slider.cget("from"))
            to = float(slider.cget("to"))
            slider_width = slider.winfo_width()

            click_fraction = event.x / slider_width
            new_value = from_ + (to - from_) * click_fraction

            slider.set(new_value)
            self.seek_video(new_value)

        def on_drag(event):
            slider = event.widget
            from_ = float(slider.cget("from"))
            to = float(slider.cget("to"))
            slider_width = slider.winfo_width()

            x = max(0, min(event.x, slider_width))
            fraction = x / slider_width
            new_value = from_ + (to - from_) * fraction

            slider.set(new_value)       # move handle to cursor
            self.seek_video(new_value)  # update video

        def on_release(event):
            self.pressed = False

        def on_scroll(event):
            if event.state == 2:
                return
            ctrl_pressed = (event.state & 0x0004) != 0
            step_volume = 2
            step_seek = 300  # milliseconds to jump per scroll tick

            delta = int(event.delta / 120) if event.delta else 0
            if delta == 0:
                return

            if ctrl_pressed:
                # Seek video
                self.pressed = True
                current_time = self.player.get_time()
                new_time = current_time + delta * step_seek
                duration = self.media.get_duration()
                new_time = max(0, min(duration, new_time))
                self.timeline_slider.set(new_time)
                self.seek_video(new_time)
            else:
                # Change volume
                new_volume = self.app.volume + delta * step_volume
                new_volume = max(0, min(100, new_volume))
                self.volume_slider.set(new_volume)
                self.change_volume(new_volume)

        # Bindings
        # puts overlay to capture bindings from vlc.
        self.overlay = tk.Frame(self.video_frame, bg="", width=self.w, height=self.h)
        self.overlay.place(x=0, y=0)

        self.overlay.bind("<MouseWheel>", on_scroll)

        self.timeline_slider.bind("<Button-1>", timeline_click)
        self.timeline_slider.bind("<B1-Motion>", on_drag)
        self.timeline_slider.bind("<ButtonRelease-1>", on_release)
        self.overlay.bind("<KeyRelease-Control_L>", on_release)
        self.overlay.bind("<KeyRelease-Control_R>", on_release)
        self.overlay.bind("<Button-1>", self.toggle_pause)
        # Bind hover events to the overlay
        self.video_container.bind("<Enter>", self.show)
        self.video_container.bind("<Leave>", self.hide)

        # Volume slider
        self.volume_slider = ttk.Scale(
            self.controls_frame,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            style="Horizontal.TScale",
            command=self.change_volume
        )
        self.volume_slider.set(self.app.volume)
        self.volume_slider.grid(row=0, column=1, sticky="ew", padx=(2, 5), pady=5)

        def volume_click(event):
            slider = event.widget
            slider_width = slider.winfo_width()
            click_fraction = event.x / slider_width
            new_value = float(slider.cget("from")) + (float(slider.cget("to")) - float(slider.cget("from"))) * click_fraction
            slider.set(new_value)
            self.change_volume(new_value)

        self.volume_slider.bind("<Button-1>", volume_click)

        self.player.set_fullscreen(True)
        self.video_frame_id = self.video_frame.winfo_id()
        self.player.set_hwnd(self.video_frame_id)

        self.media_list_player.set_playback_mode(vlc.PlaybackMode.loop)
        self.media_list_player.play()

        self.events.event_attach(vlc.EventType.MediaPlayerPlaying, self.ready)

        self.disable = False

    def toggle_pause(self, event=None):
        if perf_counter() - self.last_click <= 0.25:
            self.last_click = perf_counter()-0.5
            pass
        else:
            self.last_click = perf_counter()
            return
        if self.player:
            if self.player.is_playing():
                self.player.pause()
                self.controls_frame.config(bg="red")
                self.timeline_slider.config(style="theme.Horizontal.TScale")
                self.timeline_slider.config(style="theme.Horizontal.TScale")
                self.volume_slider.config(style="theme.Horizontal.TScale")
            else:
                self.player.play()
                self.controls_frame.config(bg="black")
                self.timeline_slider.config(style="Horizontal.TScale")
                self.volume_slider.config(style="Horizontal.TScale")

    def ready(self, event):
        self.canvas.after_idle(self.update_timeline_slider)
        self.canvas.after_idle(self.update_info)

    def update_info(self):
        if self.f:
            self.f = False
            if self.info:
                w, h = self.return_dimensions()
                text = f"{w}x{h}"
                self.info.set(f"{text:^11}")

    def update_slider_position(self):
        try:
            if hasattr(self, "player") and self.player and self.player.is_playing():
                if not self.pressed:
                    self.timeline_slider.set(self.player.get_time())
                self.canvas.after(200, self.update_slider_position)
        except:
            pass

    def update_timeline_slider(self):
        try:
            duration = self.media.get_duration()
            self.timeline_slider.config(to=duration)
            self.update_slider_position()
        except:
            pass

    def seek_video(self, value, event=None):
        if perf_counter() - self._last_seek_time > 0.05:  # 100 ms throttle
            pass
        else:
            return
        self._last_seek_time = perf_counter()
        self.player.set_time(int(float(value)))

    def change_volume(self, value):
        new_volume = int(float(value))
        self.player.audio_set_volume(new_volume)
        self.app.volume = new_volume

    def pack(self, **kw):
        self.app.canvas.pack_forget()
        self.app.vlc_frame.pack(expand=True, fill=tk.BOTH)
        self.app.vlc_frame.bind("<Configure>", self.app.window_resize)
        self.app.master.update()

    def destroy(self, threaded=True):
        import gc
        try:
            # Detach events early
            if getattr(self, "events", None):
                self.events.event_detach(vlc.EventType.MediaPlayerPlaying)
                self.events.event_detach(vlc.EventType.MediaPlayerEndReached)
                self.events = None

            # Stop media list player first
            if getattr(self, "media_list_player", None):
                self.media_list_player.stop()
                self.media_list_player.release()
                self.media_list_player = None

            # Stop the main player synchronously
            if getattr(self, "player", None):
                try:
                    self.player.set_hwnd(0)  # ensure handle cleared before stopping
                except Exception:
                    pass

                # Stop and release directly
                self.player.stop()
                self.player.release()
                self.player = None

            # Release media objects
            if getattr(self, "media_list", None):
                self.media_list.release()
                self.media_list = None

            if getattr(self, "media", None):
                self.media.release()
                self.media = None

            # Give VLC time to fully release resources
            self.app.after(100, lambda: self._finalize_destroy())

        except Exception as e:
            print("Destroy error:", e)
            gc.collect()

    def _finalize_destroy(self):
        # now safe to destroy GUI widgets
        if getattr(self, "video_frame", None):
            self.video_frame.grid_forget()
            self.video_frame.destroy()
        if getattr(self, "canvas", None):
            self.canvas.destroy()
        import gc
        gc.collect()

    def hide(self, event=None):
        try:
            self.controls_frame.grid_remove()
        except:
            pass

    def show(self, event):
        try:
            self.controls_frame.grid()
        except:
            pass

class AsyncImageLoader:
    def __init__(self, viewer):
        self.viewer = viewer
        self.queue = queue.Queue()
        self.thread = Thread(target=self._worker, name="(Thread) Viewer Asynch Tasks", daemon=True)
        self.stop_flag = False
        self.thread.start()  # Only one thread ever

    def _worker(self):
        while not self.stop_flag:
            try:
                # 1. Get the item
                path, token, caller = self.queue.get(timeout=10)
                if caller == "STOP": return
            except queue.Empty: continue
            except Exception as e:
                print(f"Queue get error: {e}")
                continue

            try:
                if token is not self.viewer.current_load_token:
                    continue
                if caller in ["cached_thumb", "gen_thumb"]: # defererd thumb gen
                    img = self.viewer.pyvips_to_pillows_for_thumb(path, caller)
                elif caller == "buffer":
                    img = self.viewer.get_source_1(path, self.viewer.drag_quality)
                elif caller == "optimization": # load full res.
                    if self.viewer.filter == "pyvips" and not self.viewer.quick_zoom.get():
                        self.viewer.lazy_load_img_pointer_to_memory_for_zooming(self.viewer.id, token)
                    elif not self.viewer.full_res:
                        self.viewer.lazy_load_full_res_to_memory_for_zooming(self.viewer.id, token)
                    continue
                elif caller == "load_to_cache":
                    # 'path' is actually the list of adjacent paths here
                    for x in path:
                        with self.viewer._frame_lock: # make the cache object so no duplicate threads process the same images.
                            self.viewer.cache[x] = {"img": None, "full_res": None}
                        img_data = self.viewer.get_source_1(x, ignore_caching=True)
                        with self.viewer._frame_lock:
                            if path not in self.viewer.adjacent:
                                continue
                            self.viewer.cache[x] = {"img": img_data, "full_res": None}
                    for x in path:
                        with self.viewer._frame_lock:
                            if path not in self.viewer.adjacent: continue
                            if not self.viewer.cache.get(x, None) or self.viewer.cache.get(x)["full_res"] is not None: continue
                        if self.viewer.filter == "pyvips" and not self.viewer.quick_zoom.get():
                            full_res = self.viewer.lazy_load_img_pointer_to_memory_for_zooming(self.viewer.id, token, x)
                        else:
                            full_res = self.viewer.lazy_load_full_res_to_memory_for_zooming(self.viewer.id, token, x)
                        with self.viewer._frame_lock:
                            self.viewer.cache[x]["full_res"] = full_res
                    continue
                else:
                    img = self.viewer.get_source_1(path) # this is a pil img?
                    if self.viewer.do_caching.get():
                        with self.viewer._frame_lock:
                            self.viewer.cache[path] = {"img": img, "full_res": None}

                # 4. HANDOFF
                def handoff(p=path, i=img, t=token, c=caller):
                    self.viewer._on_async_image_ready(p, i, t, c)

                after_c = self.viewer.master.after(0, handoff)
                self.viewer.draw_queue.append(after_c)

            except Exception as e: print(f"Async loader processing error: {e}")
            finally:
                self.queue.task_done()

    def request_load(self, path, token=None, caller=None):
        token = token or object()
        self.viewer.current_load_token = token
        self.queue.put((path, token, caller))

        return token

    def stop(self):
        self.stop_flag = True
        self.queue.put((None, None, "STOP"))

class LRUCache(OrderedDict):
    """A lightweight LRU (Least Recently Used) cache with adjustable maxsize."""
    def __init__(self, maxsize=128, name="default"):
        super().__init__()
        self.maxsize = maxsize
        self.name = name

    def __getitem__(self, key):
        """Get an item and mark it as recently used."""
        if key not in self: return None
        value = super().__getitem__(key)
        self.move_to_end(key)
        return value

    def __setitem__(self, key, value):
        """Insert/Update an item and enforce maxsize."""
        if self.maxsize == 0: return
        if key in self:
            self.move_to_end(key)
        super().__setitem__(key, value)
        self._enforce_limit()

    def _enforce_limit(self):
        """Ensure cache size does not exceed maxsize."""
        while len(self) > self.maxsize:
            item = self.popitem(last=False)  # remove least recently used (oldest)
            pass

    def set_maxsize(self, new_maxsize: int):
        """Change maxsize dynamically and trim if needed."""
        self.maxsize = new_maxsize
        self._enforce_limit()

    def last(self):
        """Return (key, value) of the most recently used item."""
        try:
            key = next(reversed(self))
            return key, self[key]
        except StopIteration:
            raise KeyError("Cache is empty")

    def __repr__(self):
        return f"<LRUCache size={len(self)}/{self.maxsize}>"

class PrefilledInputDialog(simpledialog.Dialog):
    def __init__(self, parent, title:str, message:str, default_text=""):
        self.message = message
        self.default_text = default_text
        self.result = None
        super().__init__(parent, title)

    def body(self, master):
        base_name = os.path.basename(self.default_text)
        if base_name.startswith(".") and "." not in base_name[1:]:
            name_part, ext_part = base_name, ""
        elif "." in base_name:
            name_part, ext_part = base_name.rsplit(".", 1)
            ext_part = "." + ext_part
        else:
            name_part, ext_part = base_name, ""
        tk.Label(master, text=self.message, justify="left", wraplength=300).pack(padx=10, pady=(10, 5))
        frame = tk.Frame(master)
        frame.pack(padx=10, pady=(0, 10))

        self.entry = tk.Entry(frame, width=30)
        self.entry.insert(0, name_part)
        self.entry.pack(side="left")

        tk.Label(frame, text=ext_part, width=len(ext_part) + 1, anchor="w").pack(side="left")

        self.ext_part = ext_part
        return self.entry  # initial focus

    def apply(self):
        name = self.entry.get().strip()
        if not name:
            self.result = None
        else:
            self.result = name + self.ext_part

class Timer:
    "Timer for benchmarking"
    def __init__(self):
        self.creation_time = None
    def start(self):
        self.creation_time = perf_counter()
    def stop(self):
        elapsed_time = (perf_counter() - self.creation_time)*1000
        return (f"{elapsed_time:.1f}")

if __name__ == "__main__":
    app = Application()
    #app.set_image(path)
    app.master.mainloop()
