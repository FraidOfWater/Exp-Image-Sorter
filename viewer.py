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

# 3. Do PYVIPS overhaul. All pil nearset/bilinear/lanczos will be replaced with
# PYVIPS alternatives, and we add the PIL methods as fallback.
# Do the transform with PYVIPS, not PIL. 
# Gif will remain as is because of PIL's immediate seek behaviour, whereas PYVIPS wants to load the whole file.

# 4. Reactivate fast pan logic. Add button for fast pan ON/OFF, because very large images suffer from it.
# We need to compare old zoom behaviour with new.

# 5. Separate RENDERER from GUI. Separate CONFIG from GUI and RENDERER.
# The shared config is updated by any instance of GUI. set_vals deprecated.
# Separate CurrentImage from RENDERER.
# Rework cleanup logic, just delete the current object etc.

# fast pan has been disabled again. Just not stable enough

# pyvips transform requires us to change all PIL to pyvips. So in zoom cache wed store the pyvips image instead. wed need to convert to pil every time though.
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

    def __init__(self, master=None, savedata={}, gui=None):
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
            savedata = self.load_json(self.save_path)
            self.savedata = savedata

        self.lastdir = savedata.get("lastdir", None)

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

            master.bind("<Control-s>", lambda e: self.toggle_statusbar(True))
            master.bind("<Control-S>", lambda e: self.toggle_statusbar(True))
            master.bind_all("<Control-o>", self.menu_reveal_in_file_explorer_clicked)
            master.bind_all("<Control-O>", self.menu_reveal_in_file_explorer_clicked)
            master.bind("<Button-1>", helper)
            master.geometry(savedata.get("geometry", None) or "800x600")
            master.title(self.title)
            master.protocol("WM_DELETE_WINDOW", lambda: (self.set_image(None), self.master.attributes("-alpha", 0.0),  self.canvas.update(), self.master.withdraw()))
        else: # Gui embedded
            self.app2 = master.master.master.fileManager.gui.bindhandler.search_widget
            self.app2.root.gui.bind("<Control-s>", lambda e: self.toggle_statusbar(True))
            self.app2.root.gui.bind("<Control-S>", lambda e: self.toggle_statusbar(True))
            self.app2.root.gui.bind_all("<Control-o>", self.menu_reveal_in_file_explorer_clicked)
            self.app2.root.gui.bind_all("<Control-O>", self.menu_reveal_in_file_explorer_clicked)
            self.app2.root.gui.bind("<Button-1>", helper)

        if True:
            self.zoom_magnitude = float(savedata.get("zoom_magnitude", 1.20))

            self.unbound_var = tk.BooleanVar(value=savedata.get("unbound_pan", False))

            self.disable_menubar = savedata.get("disable_menubar", False)
            self.statusbar_mode = tk.StringVar(value=savedata.get("statusbar_mode", "Default"))
            self.statusbar_mode.trace_add("write", lambda *_: self.toggle_statusbar(caller="Menu"))

            self.filter = Application.QUALITY.get(savedata.get("filter", "pyvips").lower().capitalize())
            self.drag_quality = savedata.get("drag_quality", "No buffer").lower().capitalize()
            self.drag_quality = self.drag_quality if self.drag_quality == "No buffer" else Application.QUALITY.get(self.drag_quality)
            self.anti_aliasing = tk.BooleanVar(value=savedata.get("anti_aliasing", True))
            def toggle_antialiasing(event=None):
                self.full_res = None
                self.cache.clear()
                self._zoom_cache.clear()
                self._imagetk_cache.clear()
                self.first_render_info = None
                self.second_render_info = None
                self.debug = []
                self.draw_image()

            self.anti_aliasing.trace_add("write", lambda *_: toggle_antialiasing())
            self.quick_zoom = tk.BooleanVar(value=savedata.get("quick_zoom", True))
            self.do_caching = tk.BooleanVar(value=savedata.get("pre-caching", True))
            if self.do_caching.get(): self.drag_quality = "No buffer"
            def uncheck_buffer():
                if self.do_caching.get():
                    self.drag_quality = "No buffer"
                    self.selected_option1.set(self.drag_quality)
            self.do_caching.trace_add("write", lambda *_: uncheck_buffer())
            self.thumbnail_var = tk.StringVar(value=savedata.get("thumbnail_var", "No thumb"))
            self.filter_delay = tk.IntVar(value=int(savedata.get("final_filter_delay", 200)))
            self.thumb_qual = tk.IntVar(value=int(savedata.get("thumb_qual", 32)))
            self.statusbar_up_down = savedata.get("statusbar_up_down", False)
            self.show_ram = tk.BooleanVar(value=savedata.get("show_ram", False))
            self.show_ram.trace_add("write", lambda *_: self.toggle_ram_indicator())
            self.volume = int(savedata.get("volume", 50))
            self.order = tk.StringVar(value=savedata.get("order", "Name"))
            self.reverse_sort = tk.BooleanVar(value=savedata.get("reverse", False))

            self.colors = savedata.get("colors", {
                    "canvas": "#303276", #141433
                    "statusbar": "#202041",
                    "statusbar_divider": "#545685",
                    "button": "#24255C",
                    "active_button": "#303276",
                    "text": "#FFFFFF"
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
            
        super().__init__(master, bg=self.colors["canvas"])
        self.bg_color = self.get_rgba_tuple(self.colors["canvas"])
        self.master = master

        self.style = ttk.Style()
        self.style.configure("bg.TFrame", background="black")
        self.style.configure("Horizontal.TScale", background="black")
        self.style.configure("theme.Horizontal.TScale", background="red")

        self.config(bg=self.colors["canvas"])
        self.master.configure(bg=self.colors["canvas"])
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
        self.last_known_buffer = None
        self._zoom_cache = LRUCache(maxsize=32, name="zoom") # saved zoom levels
        self._imagetk_cache = LRUCache(maxsize=0, name="imagetk") # saved gif imagetks.
        self.cache = {}
        self.adjacent = []

        self.vlc_instance = vlc.Instance()
        self.vlc_frame = None
        self.old = None

        self._old = None
        self.frames = []
        self.lazy_index = 0
        self.scale_key = None
        self.dragging = False
        self.dragging_and_zooming = False
        self.ready = True
        self.open_thread = None
        self._stop_thread = Event()
        self.is_gif = False
        self.first_render_info = None
        self.second_render_info = None

        self.filenames = []
        self.filename_index = 0

        self.reset_transform()
        self.create_widgets()

    "UI creation"
    def create_widgets(self):
        if self.standalone:
            self.create_menu()
        self.create_status_bar()
        self.create_canvas()
        self.bind_mouse_events()

    def create_menu(self):
        menu_bar = tk.Menu(self.master)

        # File menu
        file_menu = tk.Menu(menu_bar, tearoff=tk.OFF)
        menu_bar.add_cascade(label="File", menu=file_menu)
        if self.gui:
            file_menu.add_command(label="Open in File Explorer", command=self.menu_reveal_in_file_explorer_clicked, accelerator="Ctrl+O")
            file_menu.add_separator()
            file_menu.add_command(label="Exit", command=self.window_close)
        else:
            file_menu.add_command(label="Open", command=self.menu_open_clicked, accelerator="Ctrl+F")
            file_menu.add_command(label="Open folder", command=self.menu_open_dir_clicked, accelerator="Ctrl+D")
            file_menu.add_separator()
            file_menu.add_command(label="Open in File Explorer", command=self.menu_reveal_in_file_explorer_clicked, accelerator="Ctrl+O")
            file_menu.add_command(label="Rename", command=self.rename, accelerator="F2")
            file_menu.add_separator()
            file_menu.add_command(label="Trash", command=self.trash, accelerator="Delete")
            file_menu.add_command(label="Undo trash", command=self.on_ctrl_z, accelerator="Ctrl+Z")
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

        view_menu.add_separator()
        view_menu.add_checkbutton( label="Show Ram", variable=self.show_ram, offvalue=False, onvalue=True)

        if not self.gui:
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

            order_menu.add_radiobutton(label="Name", variable=self.order, value="Name", command=resort)
            order_menu.add_radiobutton(label="Date", variable=self.order, value="Date", command=resort)

            def helper11():
                resort()

            menu_bar.add_cascade(label="Order", menu=order_menu)
            order_menu.add_separator()

            order_menu.add_checkbutton(label="Reverse", variable=self.reverse_sort, offvalue=False, onvalue=True, command=helper11)
        
        if not self.gui:
            self.master.bind_all("<Control-f>", self.menu_open_clicked)
            self.master.bind_all("<Control-d>", self.menu_open_dir_clicked)
            self.master.bind_all("<Control-o>", self.menu_reveal_in_file_explorer_clicked)

            self.master.bind_all("<Control-F>", self.menu_open_clicked)
            self.master.bind_all("<Control-D>", self.menu_open_dir_clicked)
            self.master.bind_all("<Control-O>", self.menu_reveal_in_file_explorer_clicked)

        if not self.disable_menubar and self.master.config().get("menu"): # disable menubar for embedded view. (not supported)
            self.master.config(menu=menu_bar)

    def create_status_bar(self):
        def _on_image_quality_change(*args):
            self.image_quality_menu_open.set(False)
            #self.full_res = None # do we really need to delete this? no, full res isnt going through any filters.
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
            self.draw_image()

        def _on_drag_quality_change(*args):
            self.drag_quality_button_menu_open.set(False)
            #self.full_res = None
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
                def quick():
                    source_dict, scale_key = self.get_first_zoom_level(self.filename, self.drag_quality)
                    initial_fit = source_dict.get("img")
                    self.full_res = source_dict.get("full_res") or self.full_res
                    self.img_pointer = source_dict.get("pointer") or self.img_pointer
                    self.draw_image(initial_fit, initial_filter=self.drag_quality)
                    
                id1 = self.after(0, quick)
                id2 = self.after(0, lambda: (self.draw_image()))
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
        if self.show_ram.get():
            self.ram_indicator.pack(side=tk.RIGHT, pady=0)

        def get_memory_usage():
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            self.ram_indicator.config(text=f"RAM: {memory_info.rss / (1024 ** 2):.1f} MB")
            if self.show_ram.get(): self.memory_after_id = self.after(500, get_memory_usage)

        get_memory_usage()

        if self.statusbar_mode != "None":
            side = tk.TOP if self.statusbar_up_down else tk.BOTTOM
            self.frame_statusbar.pack(side=side, fill=tk.X)

    def create_canvas(self):
        canvas = tk.Canvas(self.master, background=self.colors["canvas"], highlightthickness=0)
        canvas.pack(expand=True, fill=tk.BOTH)
        self.canvas = canvas
        self.divider = tk.Frame(self.master, bg=self.colors["statusbar_divider"], height=1)
        if self.statusbar_mode.get() != "None":
            self.divider.pack(fill=tk.X)
        canvas.update()
        self.canvas = canvas

    def bind_mouse_events(self):
        def mouse_event_guard(event):
            search_widget = self.gui.bindhandler.search_widget
            if search_widget.search_active and not search_widget.search_minimized and search_widget.dragging: return
            match int(event.type):
                case 4:
                    setattr(self, "_old", event)
                    self.master.focus()
                case 5:
                    self.mouse_release(event)
                case 6: 
                    self.mouse_move_left(event)
                
        canvas = self.canvas
        canvas.bind("<Button-1>", mouse_event_guard)
        canvas.bind("<B1-Motion>", mouse_event_guard)
        canvas.bind("<ButtonRelease-1>", mouse_event_guard)

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
        if self.filename:
            self.zoom_fit()
            self.draw_image()

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
        self.draw_image(quick_zoom_event=self.quick_zoom.get())
        #if hasattr(self, "since_last"): print(perf_counter()-self.since_last)
        self.since_last = perf_counter()

    def mouse_move_left(self, event):
        if not self.ready:
            self._old = event
            return
        self.dragging = True
        if self.save1: self.after_cancel(self.save1)
        if event.state == 258: return
        if self.filename and self._old:
            dx, dy = event.x - self._old.x, event.y - self._old.y
            self.translate(dx, dy)
            if not self.unbound_var.get(): self.restrict_pan()
            zoom = self.scale_key[0]

            if self.dragging_and_zooming or True:
                self.draw_image(initial_filter=Image.Resampling.NEAREST if self.dragging else None)
            elif (self.img_pointer.width * zoom * self.img_pointer.height * zoom) > 3_000_000:
                if self.is_gif:
                    self.draw_image(initial_filter=Image.Resampling.NEAREST if self.dragging else None)
                    self._old = event
                    return
                diff_x = self.mat_affine[0, 2] - getattr(self, "buffer_ref_tx", 0)
                diff_y = self.mat_affine[1, 2] - getattr(self, "buffer_ref_ty", 0)
                curr_x = getattr(self, "buffer_start_x", 0) + diff_x
                curr_y = getattr(self, "buffer_start_y", 0) + diff_y
                if self.image_id: self.canvas.coords(self.image_id, curr_x, curr_y)
            else:
                if self.image_id: self.canvas.coords(self.image_id, self.mat_affine[0, 2], self.mat_affine[1, 2])
        self._old = event

    def mouse_release(self, event):
        self._old = None
        self.dragging = False

        # Cancel any pending renders
        if self.save1:
            self.after_cancel(self.save1)

        # Trigger the re-centered, high-quality redraw
        if self.is_gif: 
            self.dragging = False
            self.dragging_and_zooming = False
            return
        self.save1 = self.after_idle(
            lambda: (
                setattr(self, "dragging", False),
                setattr(self, "dragging_and_zooming", False),
                self.draw_image(buffer_multiplier=3)
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
        if not self.filename or not self.filenames: return
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
        if not self.filename or not self.filenames: return # only works when viewer has indexed its list to iterate through.
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

    def toggle_statusbar(self, flag=False, caller=None):
        def helper5():
            options = ["None", "Default", "Advanced", "Debug"]
            def get_next(old):
                old_index = options.index(old)
                if old_index+1 >= len(options): return options[0]
                else: return options[old_index+1]
            old = self.statusbar_mode.get()
            self.statusbar_mode.set(get_next(old))
        if flag and not caller == "Menu":
            helper5()
        if self.statusbar_mode.get() == "None":
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
            elif self.img_pointer:
                self.statusbar_event = True
        elif self.statusbar_mode.get() == "Default":
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
            elif self.img_pointer:
                self.statusbar_event = True
        
        else:
            self.pack_statusbar()

    def toggle_ram_indicator(self):
        if self.show_ram.get():
            self.ram_indicator.pack(side=tk.RIGHT)
        else:
            self.ram_indicator.pack_forget()

    def change_theme(self, colors):
        self.savedata["colors"] = colors
        self.colors = colors
        self.canvas.config(bg=colors["canvas"])

        lbl_style = {"background": colors["statusbar"], "foreground": colors["text"]}
        btn_style = {"background": colors["statusbar"], "activebackground": colors["active_button"],
                     "foreground": colors["text"], "activeforeground": colors["text"]}
        menu_style = {**btn_style, "width": 6}

        self.config(bg=colors["canvas"])
        self.master.configure(bg=colors["canvas"])


        self.bg_color = self.get_rgba_tuple(colors["canvas"])

        self.ram_indicator.config(bg=colors["statusbar"], foreground=colors["text"])
        self.frame_statusbar.config(bg=colors["statusbar"])

        self.divider.config(bg=colors["statusbar_divider"])
        self.label_image_format.config(**lbl_style)
        self.label_image_mode.config(**lbl_style)
        self.label_image_dimensions.config(**lbl_style)
        self.label_image_size.config(**lbl_style)
        self.render_info.config(**lbl_style)
        self.anim_info.config(**lbl_style)

        self.image_quality.configure(**menu_style)
        self.thumb_quality.configure(**menu_style)
        self.drag_quality_button.configure(**menu_style)

        chk_style = {**btn_style, "selectcolor": colors["statusbar"]}
        self.anti_aliasing_button.configure(**chk_style)
        self.quick_zoom_button.configure(**chk_style)
        self.unbound_pan_button.configure(**chk_style)
        self.pre_caching_button.configure(**chk_style)

    def window_resize(self, event): #window
        if self.filename == None: return
        if self.statusbar_event:
            self.statusbar_event = False
            self.zoom_fit()
            self.draw_image()
            return
        if (event.widget is self.canvas or event.widget is self.master) and self.filename:
            self.zoom_fit()
            self.dragging = True

            self.draw_image(drag=True, initial_filter=Image.Resampling.NEAREST)

            if self.save1:
                self.after_cancel(self.save1)

            def refresh():
                self.zoom_fit()
                self.cache.clear() 
                self._imagetk_cache.clear()
                self._zoom_cache.clear()
                setattr(self, "first_render_info", None)
                setattr(self, "second_render_info", None)
                setattr(self, "debug", [])
                setattr(self, "dragging", False)
                self.draw_image()
                
            self.save1 = self.after(self.filter_delay.get(), refresh)
        elif self.vlc_frame:
            vlc_player = self.old  # or however you store the instance
            if vlc_player and vlc_player.video_frame:
                w = event.width
                h = event.height

                if self.statusbar_mode.get() != "None":
                    h -= 25

                # Resize the containing frames
                vlc_player.video_container.config(width=w, height=h)

                vlc_player.video_frame.config(width=w, height=h - 35)  # leave space for controls
                vlc_player.controls_frame.config(width=w)

        # Move the instructions text to the new center
        # We find it using the "sorter" tag
        w, h = event.width, event.height
        if self.app2 and hasattr(self.app2, "canvas") and self.app2.canvas is not None and self.app2.canvas.master == self.master:
            self.app2.canvas.coords("sorter", w // 2, h // 2)

    def window_close(self, e=None):
        from send2trash import send2trash
        for x in self.undo:
            path = os.path.normpath(x[0])
            try:
                send2trash(path)
            except Exception as e:
                print("Trash errors:", e)

        self.save_json()
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

    "Preferences"
    def set_vals(self, savedata):
        self.do_caching.set(savedata.get("pre-caching", self.do_caching.get()))
        self.unbound_var.set(savedata.get("unbound_pan", self.unbound_var.get()))
        self.quick_zoom.set(savedata.get("quick_zoom", self.quick_zoom.get()))
        self.anti_aliasing.set(savedata.get("anti_aliasing", self.anti_aliasing.get()))
        self.thumbnail_var.set(savedata.get("thumbnail_var", self.thumbnail_var.get()))
        self.selected_option1.set(savedata.get("drag_quality", "Nearest").lower().capitalize())
        self.selected_option.set(savedata.get("filter", "Nearest").lower().capitalize())

        self.statusbar_mode.set(savedata.get("statusbar_mode", self.statusbar_mode.get()))

        self.filter_delay.set(int(savedata.get("final_filter_delay", self.filter_delay.get())))
        self.thumb_qual.set(int(savedata.get("thumb_qual", self.thumb_qual.get())))
        self.volume = int(savedata.get("volume", self.volume))

    def save_json(self):
        if self.filter == "pyvips":
            name = "Pyvips"
        else:
            name= self.filter.name
        data = {
                "geometry": self.master.winfo_geometry(),       # "600x800+100+100" Width x Height + x + y
                "disable_menubar": self.disable_menubar,        # Disable the menu bar
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
            if not self.standalone:
                del data["geometry"]
            for key, x in data.items():
                self.savedata[key] = data[key]
        if self.standalone and not self.gui:
            with open(self.save_path, "w") as f:
                json.dump(data, f, indent=4)

    def load_json(path):
        if os.path.isfile(path):
            try:
                with open(path) as f:
                    return json.load(f)
            except Exception as e:
                print("Json load error:", e)
        return {}
    
    def get_rgba_tuple(widget, color_name):
        rgb_16 = widget.winfo_rgb(color_name)
        rgb_8 = tuple(c >> 8 for c in rgb_16)
        return rgb_8 + (0,)
    
    # mkae gui a class, then have the below be a draw class which just draws to the ready canvas! #################
    # Affine transforms
    def reset_transform(self):
        self.mat_affine = np.eye(3)

    def translate(self, ox, oy):
        m = np.eye(3)
        m[0, 2], m[1, 2] = ox, oy
        self.mat_affine = m @ self.mat_affine

        scale_up = np.eye(3)
        zoom, _ = self.scale_key
        inv_f = 1.0 / zoom
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

        if not is_video:
            x, y = (self.img_pointer.width, self.img_pointer.height)
            text = f"{x}x{y}"
            self.label_image_dimensions_var.set(f"{text:^11}")
            return (x, y)

    def set_image(self, filename, obj=None, adjacent=[]):
        self.adjacent = [x for x in adjacent if x.endswith((".png", ".jpg", ".jpeg", ".bmp", ".pcx", ".tiff", ".webp", ".psd", ".jfif", ".avif"))]
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
            self.imagetk = None
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
            is_animated = True if self.img_pointer.get_n_pages() > 1 else False
            if is_animated:
                self._set_animation(filename)
                return
        token = None
        doing_thumb = False
        if self.thumbnail_var.get() != "No thumb":
            doing_thumb = True
            token = self._set_thumbnail(thumbpath=thumbpath)
        else:
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
                if self.statusbar_mode.get() != "None":
                    self.frame_statusbar.pack_forget()
                    self.divider.pack_forget()
                    self.divider.pack(expand=False, fill=tk.X)
                    self.frame_statusbar.pack(expand=False, fill=tk.X)

        self.obj = None
        for call in self.draw_queue:
            self.after_cancel(call)
        self.draw_queue.clear()

        for x in [x for x in (self.gif_after_id, self.gif_gen_after_id, self.draw_img_id, self.zoom_after_id) if x is not None]:
            self.after_cancel(x)

        self.gif_after_id = None
        self.gif_gen_after_id = None
        self.open_thread = None
        self._stop_thread.clear()
        self.dragging = False
        self.dragging_and_zooming = False
        self.ready = True

        self.frames.clear()
        self.dont_garbage_collect = None
        self.img_pointer = None
        self.full_res = None
        self.last_known_buffer = None
        self._zoom_cache.clear()
        self._imagetk_cache.clear()
        self._zoom_cache.set_maxsize(0)
        self._imagetk_cache.set_maxsize(0)
        self.debug.clear()
        self.lazy_index = 0

        self.filename = None
        #self.imagetk = None # dont clear this if we dont delete the canvas items.
        # we could have a self.img = img() that is an object holding all this info, because we could just create a new one each time, update its values and forget it, without having to "reset" all values here...
        self.image_id = None
        self.is_gif = False
        self.first_render_info = None
        self.second_render_info = None
        self.debug = []
        self.render_info.config(text="R:")
        #self.canvas.delete("_IMG")

        if not filename or not os.path.exists(filename):
            self.imagetk = None
            self.canvas.delete("all")
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
                    self.canvas.configure(bg=self.colors["canvas"])
                    #self.update()
                    close_vlc()
                    #self.update()
                self.f = True
                return True

            else:
                self.imagetk = None
                self.canvas.delete("_IMG")
                if self.standalone:
                    self.master.winfo_toplevel().title(self.title)
                self.label_image_format_var.set("")
                self.label_image_mode_var.set("")
                self.label_image_dimensions_var.set("")
                self.label_image_size_var.set("")
                close_vlc()
                self.a = False
                return False

    "Static Images"
    def _set_thumbnail(self, thumbpath=None):
        self.a = False
        if thumbpath: token = self.loader.request_load(thumbpath, caller="cached_thumb")
        else: token = self.loader.request_load(thumbpath, caller="gen_thumb")
        return token

    def _set_picture(self, filename, token=None, doing_thumb=False):
        "Close the handle and load full copy to memory."
        self.a = False
        if self.do_caching.get(): # If cache, we should see if its in there
            cached = self.cache.get(filename)
            if cached: # if cached
                self._on_async_ready(filename, self.current_load_token, cached, caller="cached")
                #if not cached.get("full_res"):
                #    token = self.loader.request_load(filename, token, caller="full_res")
            
            else:
                token = self.loader.request_load(filename, token, caller="fit")
                token = self.loader.request_load(filename, token, caller="full_res")

            if self.adjacent:
                for x in list(self.cache.keys()):
                    if x != filename and x not in self.adjacent:
                        del self.cache[x]
                            
                keys = set(self.cache.keys())
                self.adjacent = [x for x in self.adjacent if x not in keys and x != filename]
                if self.adjacent:
                    self.loader.request_load(self.adjacent.copy(), token, caller="load_to_cache")
        else:
            if self.selected_option1.get() != "No buffer":
                if type(self.filter) == Image.Resampling and self.drag_quality.name.lower() == self.filter.name.lower(): pass
                elif type(self.filter) == str and self.filter.lower() == "pyvips": pass
                else: token = self.loader.request_load(filename, token, caller="buffer")
            token = self.loader.request_load(filename, token, caller="fit")
            token = self.loader.request_load(filename, token, caller="full_res")

    "Animation"
    def _set_animation(self, filename):
        self.zoom_fit()
        self.a = False
        self.is_gif = True
        self.open_thread = Thread(target=self._preload_frames, args=(self.filename, self.id), name="(Thread) Viewer frame preload", daemon=True)
        self.open_thread.start()
        self.timer1 = perf_counter()

    def _preload_frames(self, filename, id1):
        def fallback():
            self.is_gif = False
            self.frames.clear()
            self._set_picture(filename)
        if self._stop_thread.is_set(): 
            return
        try:
            with Image.open(filename, "r") as handle: # I like how PIL allows us to lazily load each frame.
                i = 0
                while True:
                    if self._stop_thread.is_set(): return
                    if self.filename != filename: return
                    if id1 != self.id: return
                    
                    handle.seek(i)
                    duration = handle.info.get('duration', 100)
                    if handle.mode not in ("RGBA", "RGB"): frame = handle.convert("RGB")
                    else: frame = handle.copy()
                    i += 1
                    if self._stop_thread.is_set(): return
                    if self.filename != filename: return
                    if id1 != self.id: return
                    self.frames.append((frame, duration))
                    if i-1 == 1: self.after(0, self._update_frame)
                    self._zoom_cache.set_maxsize(i)
                    self._imagetk_cache.set_maxsize(i)

        except EOFError:
            if i == 1: # perhaps redundant, pyvips already checks n_pages.
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
        self.pil_image, gif_duration = frames[lazy_index] # Updates reference (for panning/zooming)
        self.anim_info.config(text=f"A: {lazy_index+1}/{len(frames)}/{gif_duration}ms")

        self.gif_after_id = self.after(gif_duration, lambda: self._update_frame(lazy_index+1))

        def _step():
            self.draw_image(initial_filter=Image.Resampling.NEAREST if self.dragging else None)

        self.after(0, _step)

    "Video"
    def _set_video(self):
        def close_vlc():
            if self.vlc_frame != None: # forget statusbar and divider
                if self.statusbar_mode.get() != "None":
                    self.divider.pack(expand=False, fill=tk.X)
                    self.frame_statusbar.pack(expand=False, fill=tk.X)
                self.vlc_frame.pack_forget()
                if self.old:
                    self.old.player.pause()
                    self.old.destroy()  # Bug fix for mp4
                    self.old = None
                self.vlc_frame = None
                self.old = None
                
        self._set_info(self.filename, self.ext, is_video=True)
        close_vlc()
        new = VlcPlayer(self, self.master.winfo_geometry().split("+",1)[0], self.filename, self.label_image_dimensions_var)

        if self.statusbar_mode.get() != "None":
            self.frame_statusbar.pack_forget()
            self.divider.pack_forget()
            
            # Apply side explicitly so it doesn't default to TOP behind the video
            side = tk.TOP if self.statusbar_up_down else tk.BOTTOM
            self.frame_statusbar.pack(side=side, fill=tk.X)
            self.divider.pack(expand=False, fill=tk.X)
            
        self.update() # This single update cleanly renders the final layout

        #self.update()
        self.a = False
        self.old = new
    
    "Thread to Main thread handoff"
    def _on_async_ready(self, path: str, token, data: dict, caller: str) -> None:
        "Unpacks data from ASYNCHLOADER and draws the first render. Quaranteed to have all parameters."
        if token != self.current_load_token: return
        self._zoom_cache.set_maxsize(32)
        if self.do_caching.get() and not self.cache.get(path):
            self.cache[path] = {}
            
        match caller:
            case "cached_thumb" | "gen_thumb":
                initial_fit = data["thumb"]
                self.zoom_fit(initial_fit)
                self.draw_image(initial_fit) # draw full res after a delay.
                self._set_picture(self.filename, token)

            case "buffer":
                initial_fit = data.get("img", data.get("full_res")) # not generating this identically to fit for reasons? should be fit but with initial filter.
                # have to add buffer to the dict.
                self.zoom_fit()
                self.draw_image(initial_fit)

            case "fit":
                initial_fit = data["img"] # got the find a way to add this to zoom cache.
                self._zoom_cache[(self.lazy_index, data["scale_key"])] = initial_fit
                
                self.zoom_fit(initial_fit)
                self.draw_image(initial_fit) # calculates the current zoom key and retrieves from cache

                if self.do_caching.get():
                    self.cache[path]["img"] = data["img"]
                    self.cache[path]["scale_key"] = data["scale_key"]
                
            case "full_res":
                self.full_res = data["full_res"]
                self.img_pointer = data.get("pointer", self.img_pointer)

                if self.do_caching.get():
                    self.cache[path]["full_res"] = self.full_res
                    self.cache[path]["pointer"] = self.img_pointer

            case "cached": # Cached DATA is the same as fit's + full_res + buffer
                initial_fit = data["img"]
                self.full_res = data.get("full_res")
                self.img_pointer = data.get("pointer", self.img_pointer)
                self._zoom_cache[(self.lazy_index, data["scale_key"])] = initial_fit
                self.zoom_fit()
                self.draw_image(initial_fit)

    "Rendering"
    def draw_image(self, initial_fit=None, drag=False, initial_filter=None, quick_zoom_event=False, buffer_multiplier=1, special2=False):
        start = perf_counter()
        if self.img_pointer == None: ##?
            return
        if self.f and not special2: ##########?
            self.imagetk = None
            self.canvas.delete("_IMG")

        # prefetch values
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        zoom, scale_key = self.scale_key
        size = max(1, round(self.img_pointer.width * zoom)), max(1, round(self.img_pointer.height * zoom))    
        fast_pan_active = (size[0]*size[1]) < 3_000_000 and False

        if fast_pan_active:
            render_w, render_h = cw, ch
            buffer_screen_x, buffer_screen_y = self.mat_affine[0, 2], self.mat_affine[1, 2]
            self.buffer_screen_x, self.buffer_screen_y = buffer_screen_x, buffer_screen_y
        else:
            render_w, render_h = int(cw * buffer_multiplier), int(ch * buffer_multiplier)
            offset_factor = (buffer_multiplier - 1) / 2
            buffer_screen_x, buffer_screen_y = -int(cw * offset_factor), -int(ch * offset_factor)
            self.buffer_screen_x, self.buffer_screen_y = buffer_screen_x, buffer_screen_y
            self.buffer_ref_tx, self.buffer_ref_ty = self.mat_affine[0, 2], self.mat_affine[1, 2]
            self.buffer_start_x, self.buffer_start_y = buffer_screen_x, buffer_screen_y
        
        def get_source(zoom=zoom, scale_key=scale_key, size=size): # movements pan/zoom/rotation
            "Returns a resized image at the given, secondary filter, and caches it."
            if initial_fit: # thumbnail or first filter
                return initial_fit
            
            # we shouldnt get source if drag, we should do simply scale current or last from cache.
            # if drag is false, then we can call get_source, this separates these two functions neatyl.
            # then we'd also split off quick_zoom from this. Well, it would ask getsource for the correct image, but it would ignore cache and generate nearest using a parameter initial filter.
            # gif is pil images, full_res. we just need to resize these. unfortunately we cant do this in pyvips, unless we have a pyvips object.
            # note, affine should zoom for us from here? we dont need to resize past full res.
            zoom_key = (self.lazy_index, scale_key)
            resized = None
            if zoom >= 1.0 or not self.anti_aliasing.get(): # if fit is 1.0 or more at start, is it in cache already?
                if self.is_gif: return self.pil_image
                if self.full_res: return self.full_res
                return self.full_res
        
            elif drag and self._zoom_cache and not self.is_gif: # gen levels from cached instead for a blur effect and maybe perf?
                default = Image.Resampling.NEAREST # default drag quality when resizing window
                
                tupl, cached = self._zoom_cache.last()
                index, last_zoom_key = tupl

                # SAFETY: Prevent zoom from hitting 0 and causing the 1px collapse
                safe_zoom = max(0.01, zoom) 
                size1 = max(10, round(self.img_pointer.width * safe_zoom)), max(10, round(self.img_pointer.height * safe_zoom))
                
                zoom_key = (self.lazy_index, last_zoom_key)

                self._zoom_cache.clear()
                # If cached is somehow None, we generate it from pil_image using the safe size
                cached = cached or self.pil_image.resize(size1, default)
                self._zoom_cache[zoom_key] = cached

                if zoom >= 1.0: # DRAGGING bigger
                    # Scaling up from cached to the original pointer size
                    resized = cached.resize((self.img_pointer.width, self.img_pointer.height), default)
                    if resized.mode != "RGBA": 
                        resized = resized.convert("RGBA")
                        
                elif zoom < 1.0: # DRAGGING smaller
                    resized = cached.resize(size, default)
                    if scale_key < last_zoom_key:
                        if not self.full_res:
                            try:
                                with Image.open(self.filename) as img:
                                    copy = img.copy()
                                    if copy.mode != "RGBA": copy = copy.convert("RGBA")
                                    self.full_res = copy
                            except Exception as e:
                                print("draw_image, get_source:", e)
                                # Fallback to pyvips pointer if file open fails
                                buffer = self.img_pointer.write_to_memory()
                                mode = get_mode(self.img_pointer)
                                resized_full = Image.frombytes(mode, (self.img_pointer.width, self.img_pointer.height), buffer, "raw")
                                if resized_full.mode != "RGBA": resized_full = resized_full.convert("RGBA")
                                self.full_res = resized_full

                        # Always pull from full_res when scaling down to maintain quality/stability
                        resized = self.full_res.resize(size, default)
                        new_zoom_key = (self.lazy_index, scale_key)
                        if resized.mode != "RGBA": resized = resized.convert("RGBA")
                        
                        self._zoom_cache.clear()
                        self._zoom_cache[new_zoom_key] = resized
                    else:
                        new_zoom_key = (self.lazy_index, scale_key)
                        self._zoom_cache.clear()
                        self._zoom_cache[new_zoom_key] = cached

            ################
            elif quick_zoom_event and self.full_res: # we could do this in pyvips exclusively!!!! # resize is actually the fastest...
                fail = True
                try:
                    resized = self._zoom_cache.__getitem__(zoom_key)
                    if resized:
                        correction = size[0] - resized.width
                    else: correction = 0
                    resized = self.full_res.resize((size[0]-correction, size[1]), Image.Resampling.NEAREST)
                    fail = False
                except Exception as e: 
                    print("couldnt zoom via PIL", e)
                    pass
                if fail:
                    try:
                        vips_img = pyvips.Image.thumbnail_buffer(self.pyvips_buffer or self.img_pointer, size[0], height=size[1]) #LINEAR, #CUBIC, #MITCHELL, #LANCZOS2, #LANCZOS3, #MKS2013, #MKS2021
                        buff = vips_img.write_to_memory()
                        mode = get_mode(vips_img)
                        resized = Image.frombytes(mode, (vips_img.width, vips_img.height), buff, "raw")
                        if resized.mode not in ("RGBA", "RGB"): resized = resized.convert("RGB")
                    except Exception as e:
                        print("couldnt zoom via pyvips", e)            
            
            else:
                resized = self._zoom_cache.__getitem__(zoom_key)
                if resized: 
                    return resized

                if self.is_gif:
                    f1 = Image.Resampling.LANCZOS if self.filter == "pyvips" else self.filter
                    if quick_zoom_event: f1 = Image.Resampling.NEAREST

                    try:
                        resized = self.pil_image.resize(size, f1)
                    except Exception as e:
                        print("Gif resizing error", e)
                else:
                    fail = True # would be better to have a fallback that generates from the filesystem, and to have resizing with pyvips so you could do
                    # first pyvips fails, so flalback to pil. We would always use pyvips if possible, we could change the filter easily.
                    if self.filter != "pyvips" and self.full_res:
                        try:
                            if quick_zoom_event: 
                                return self.full_res.resize(size, Image.Resampling.NEAREST)
                            f1 = initial_filter or self.filter if self.filter != "pyvips" else Image.Resampling.NEAREST
                            resized = self.full_res.resize(size, f1)
                            fail = False
                        except Exception as e:
                            print("Fallback PyVips:", e)
                    if fail:
                        try:
                            vips_img = pyvips.Image.thumbnail_image(self.img_pointer, size[0], height=size[1]) #LINEAR, #CUBIC, #MITCHELL, #LANCZOS2, #LANCZOS3, #MKS2013, #MKS2021
                            buffer = vips_img.write_to_memory()
                            mode = get_mode(vips_img)
                            resized = Image.frombytes(mode, (vips_img.width, vips_img.height), buffer, "raw")
                            if resized.mode not in ("RGBA", "RGB"): resized = resized.convert("RGB")
                        except Exception as e:
                            print("Couldnt resize:", e)
                            return

                if quick_zoom_event:
                    return resized

                self._zoom_cache[zoom_key] = resized
            
            return resized
        
        def get_imagetk(): # static redraws for animation
            matrix = self.combined.copy() if self.anti_aliasing.get() and zoom < 1.0 else self.mat_affine.copy()
            if fast_pan_active: ############### why are there two.....
                matrix[0, 2] = 0
                matrix[1, 2] = 0
            else:
                matrix[0, 2] -= buffer_screen_x
                matrix[1, 2] -= buffer_screen_y

            inv = np.linalg.inv(matrix)
            affine_inv = (inv[0,0], inv[0,1], inv[0,2], 
                          inv[1,0], inv[1,1], inv[1,2])            
        
            if self.is_gif and not drag:
                affine_bucket = (round(affine_inv[0], 3), round(affine_inv[1], 3), int(round(affine_inv[2])), 
                                 round(affine_inv[3], 3), round(affine_inv[4], 3), int(round(affine_inv[5])))
                transform_key = (self.lazy_index, scale_key, affine_bucket, cw, ch, self.filter)
                imagetk = self._imagetk_cache.__getitem__(transform_key)
                if imagetk: return imagetk, affine_inv
            
            # we might not have to do scaling at all using transform, except when resizing bigger, and then we can do that by resizing too.
            source = get_source(zoom, scale_key, size)
            if not source: return None, affine_inv
            
            """import pyvips
            a, b, tx, c, d, ty = affine_inv
            dst = source.affine((a, b, c, d), 
                    o_x=tx, 
                    o_y=ty, 
                    interpolate=pyvips.Interpolate.new("nearest"),
                    extend="background",
                    background=self.bg_color)
            dst = dst.extract_area(0, 0, render_w, render_h)"""

            dst = source.transform((render_w, render_h), 
                                                              Image.AFFINE, affine_inv, 
                                                              resample=Image.Resampling.NEAREST, 
                                                              fillcolor=self.bg_color if source.mode=="RGBA" else self.bg_color)

            if special2: ######### ?
                self.dont_garbage_collect = dst
                return dst, affine_inv
            
            imagetk = ImageTk.PhotoImage(dst)

            if self.is_gif and not drag:
                self._imagetk_cache[transform_key] = imagetk

            return imagetk, affine_inv
        
        imagetk, affine_inv = get_imagetk()
        if special2: return imagetk ########### hacky
        if not imagetk: return

        tx = self.mat_affine[0, 2] if fast_pan_active else buffer_screen_x
        ty = self.mat_affine[1, 2] if fast_pan_active else buffer_screen_y

        if self.image_id:
            self.canvas.itemconfig(self.image_id, image=imagetk)
            self.canvas.coords(self.image_id, tx, ty)
        else:
            self.image_id = self.canvas.create_image(tx, ty, anchor='nw', image=imagetk, tags="_IMG")
            guide = self.gui.bindhandler.search_widget.guide_text_id
            if guide: 
                self.canvas.lift(guide)
            if self.app2.canvas == self.canvas:
                self.app2.bring_forth()

        self.imagetk = imagetk
        self.f = False
        self.debug_info(start)

        if not drag: 
            self.update_idletasks() # This lets zoom events complete.
        
        if quick_zoom_event and not self.is_gif:
            self.draw_pan_buffer(zoom, affine_inv)

    def debug_info(self, start):
        "Update the drawtimes for the statusbar when in debug mode."
        if self.statusbar_mode.get() != "Debug": return
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
        if self.debug:
            info_msg += average_render_time
        info_msg += " ms"

        self.render_info.config(text=info_msg)

    def draw_pan_buffer(self, zoom, affine_inv):
        "Redraws the image at the highest quality, adding a buffer for smooth panning. Or defaulting to a simple redraw if user is dragging."
        def threaded_buffer_gen(n, do_again=False):
            a = Thread(target=get_transform, args=(n, self.zoom_after_id, affine_inv, do_again), daemon=True)
            a.start()

        def get_transform(n, id, affine_inv, do_again): # check if the zoom level is still correct, else discard?
            dst = self.draw_image(buffer_multiplier=n, special2=affine_inv)
            if self.zoom_after_id: 
                self.after_cancel(self.zoom_after_id)
            self.canvas.after(0, handoff, id, dst, do_again)

        def handoff(id, source, do_again):
            if id != self.zoom_after_id:
                return
            
            self.ready = False ############### ? guards against mouse move jitter?
            imagetk = ImageTk.PhotoImage(source)

            tx = self.buffer_screen_x
            ty = self.buffer_screen_y

            if self.image_id:
                self.canvas.itemconfig(self.image_id, image=imagetk)
                self.imagetk = imagetk
                self.canvas.coords(self.image_id, tx, ty)

            self.canvas.update() # pans during this time are essentially cancelled

            self.ready = True
            if do_again and False:
                after_id3 = self.after(40, threaded_buffer_gen, 5)
                self.zoom_after_id = after_id3
        if self.zoom_after_id: 
            self.after_cancel(self.zoom_after_id)

        if self.dragging: # only do deferred buffer when zoomed in more than 1.0? 
            self.dragging_and_zooming = True # uses compatibility mode for performance reasons
            return
        else:
            after_id3 = self.after(40, threaded_buffer_gen, 1, True) # if img actually fits the screen, we shouldnt draw the buffer around it? should cap to the acutal size


                
        self.zoom_after_id = after_id3

    def get_first_zoom_level(self, path, initial_filter=None):
        "Returns the source image resized to the canvas width and post processed with filters."
        "We get this here and cache it for the main thread."
        # isnt this the same as the one in draw? cant we just use this to get all zoom levels? in theory yes.
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

            zoom = min(sx, sy)
            scale_key = int(round(zoom, 3) * 1000)
            scale_key = zoom, scale_key, max(0.001, zoom)

            ####
            #### translate
            m = np.eye(3)
            m[0, 2], m[1, 2] = ox, oy
            mat_affine = m @ mat_affine

            scale_up = np.eye(3)
            zoom, _, _ = scale_key
            inv_f = 1.0 / zoom
            scale_up[0,0] = scale_up[1,1] = inv_f
            self.combined = mat_affine @ scale_up
            ####

            ###
            mat = mat_affine
            sx, sy = (mat[0, 0]**2 + mat[1, 0]**2)**0.5, (mat[0, 1]**2 + mat[1, 1]**2)**0.5

            exact_zoom = min(sx, sy)
            scale_key = int(round(exact_zoom, 3) * 1000)
            
            return exact_zoom, scale_key

        def get_source():
            if zoom >= 1.0 or not self.anti_aliasing.get(): # if fit is 1.0 or more at start, is it in cache already?¨
                full_res_dict = load_full_res(path)
                full_res = full_res_dict.get("full_res")
                img_pointer = full_res_dict.get("pointer") # we should mvoe this to the main thread, unsafe!!!
                return {"img": full_res, "full_res": full_res, "img_pointer": img_pointer}
            else:
                fail = True
                if self.filter == "pyvips":
                    try:
                        vips_img = pyvips.Image.thumbnail(path, max(size))
                        buffer = vips_img.write_to_memory()
                        mode = get_mode(vips_img)
                        resized = Image.frombytes(mode, (vips_img.width, vips_img.height), buffer, "raw")
                        fail = False
                    except Exception as e:
                        print("Fallback:", e)
                if fail:
                    try:
                        with Image.open(path) as img:
                            f1 = initial_filter if initial_filter is not None else self.filter if self.filter != "pyvips" else Image.Resampling.NEAREST
                            resized = img.resize(size, f1)
                    except Exception as e:
                        print("Failed to resize", e)
                        return
                if resized.mode not in ("RGBA", "RGB"): resized = resized.convert("RGB")
                return {"img": resized}

        # prefetch values
        handle = pyvips.Image.new_from_file(path)
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        if cw <= 1 or ch <= 1 or handle == None: return

        zoom, scale_key = get_scale_key() # scale key is precomputed by get_scale_key each time def scale() is called.
        size = max(1, round(handle.width * zoom)), max(1, round(handle.height * zoom)) # calc desired size

        source_dict = get_source()
        return source_dict, scale_key

    "Helpers"
    def get_scale_key(self):
        mat = self.mat_affine
        sx, sy = (mat[0, 0]**2 + mat[1, 0]**2)**0.5, (mat[0, 1]**2 + mat[1, 1]**2)**0.5
        
        exact_zoom = min(sx, sy)
        scale_key = int(round(exact_zoom, 3) * 1000)
        self.scale_key = exact_zoom, scale_key

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
        zoom, _ = self.scale_key
        inv_f = 1.0 / zoom
        scale_up[0,0] = scale_up[1,1] = inv_f
        self.combined = self.mat_affine @ scale_up

def get_mode(vips_img) -> str:
    "Return the mode needed to convert a PYVIPS.Image to a PIL.Image format via PIL.Image.frombytes()."
    "Most common formats are srgb, b-w, rgb16 and grey16."
    pformat = str(vips_img.interpretation).lower()
    match pformat:
        case "srgb": pformat = "RGBA" if vips_img.bands == 4 else "RGB"
        case "b-w": pformat = "LA" if vips_img.bands == 2 else "L"
        case "rgb16" | "grey16": pformat = "I;16"
    return pformat

def pyvips_to_pillows_for_thumb(filename: str, mode: str, pre_existing_thumbs: bool) -> Image.Image | None:
    filter = Image.Resampling.NEAREST if mode == "Fast" else Image.Resampling.LANCZOS
    try:
        if pre_existing_thumbs: # guaranteed to be rgba
            thumb = pyvips.Image.new_from_file(filename)
            if mode == "Fast": res_thumb = thumb
            else: res_thumb = pyvips.Image.thumbnail(filename, 32)
            buffer = res_thumb.write_to_memory()
            pil_format = get_mode(res_thumb)
            resized = Image.frombytes(pil_format, (res_thumb.width, res_thumb.height), buffer, "raw")
            if mode != "Fast": resized = resized.resize((thumb.width, thumb.height), filter)
        else: # does this work?
            vips_img = pyvips.Image.thumbnail(filename, 256)
            if mode != "Fast": vips_img = vips_img.gaussblur(2)
            buffer = vips_img.write_to_memory()
            pil_format = get_mode(vips_img)
            resized = Image.frombytes(pil_format, (vips_img.width, vips_img.height), buffer, "raw")
    except Exception as e:
        print("Fallback: (thumb)", e, filename)
        try:
            with Image.open(filename) as img:
                img.thumbnail((256, 256))
        except Exception as e:
            print("Failed to generate thumb:", filename, e)
            return

    if resized.mode not in ("RGBA", "RGB"): resized = resized.convert("RGB")
    return resized

def load_full_res(path: str) -> dict:
    "Return full_res and optionally the loaded in pointer using Vips, or only full_res with PIL as fallback."
    try:
        pointer = pyvips.Image.new_from_file(path) # cheap
        pointer = pointer.copy_memory()
        buffer = pointer.write_to_memory() # we want to generate thumbnails from THIS
        mode = get_mode(pointer)
        img = Image.frombytes(mode, (pointer.width, pointer.height), buffer, "raw")
        if img.mode in ("RGBA", "RGB"): pass
        else: img = img.convert("RGB")
        return {"full_res": img, "pointer": pointer}
    except Exception as e:
        print("Fallback to PIL:", e, path)
        try:
            with Image.open(path) as img:
                if img.mode in ("RGBA", "RGB"): img.load()
                else: img = img.convert("RGB")
                return {"full_res": img}
        except Exception as e:
            print("Error (load_full_res):", e, path)
            return {}

from concurrent.futures import ThreadPoolExecutor
class AsyncImageLoader:
    def __init__(self, viewer):
        self.viewer = viewer
        self.lock = Lock()
        self.queue = queue.Queue()
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="AsyncLoader")
    
    def request_load(self, path, token=None, caller=None):
        token = token or object()
        self.viewer.current_load_token = token
        self.queue.put((path, token, caller))
        self.executor.submit(self._process_request, path, token, caller)
        return token
    
    def stop(self):
        self.executor.shutdown(wait=False)

    def _process_request(self, path, token, caller):   
        def move_to_main_thread(data, path=path):
            if not data or self.viewer.current_load_token is not token: return # out of scope | Fail
            with self.lock:
                self.viewer.master.after(0, self.viewer._on_async_ready, path, token, data, caller) # compares tokens automatically

        try: # one potential problem is full_res being generated immediately by fit, and full_res caller immediately after is doing empty work. we should calculate the zoom BEFORE its scheduled.
            if self.viewer.current_load_token is not token: return # clear cache until call is reached
            match caller:
                case "cached_thumb" | "gen_thumb":
                    quality = self.viewer.thumbnail_var.get()
                    thumbnail_exists =  bool(caller=="cached_thumb")
                    img = pyvips_to_pillows_for_thumb(path, quality, thumbnail_exists)
                    move_to_main_thread({"thumb": img})

                case "fit" | "buffer": # get_first_zoom should only return the zoomed image! make sure its scope is exactly that.
                    inital_filter = None if caller=="fit" else self.viewer.drag_quality
                    source_dict, scale_key = self.viewer.get_first_zoom_level(path, initial_filter=inital_filter)
                    source_dict["scale_key"] = scale_key
                    move_to_main_thread(source_dict)

                case "full_res": # for currently displayed image!!!
                    full_res_dict = load_full_res(path)
                    move_to_main_thread(full_res_dict)

                case "load_to_cache":
                    adjacent_copy = path
                    for x in adjacent_copy:
                        source_dict, scale_key = self.viewer.get_first_zoom_level(x)
                        if self.viewer.current_load_token is not token: return
                        move_to_main_thread(source_dict, x)

                    for x in adjacent_copy:
                        full_res_dict = load_full_res(x)
                        if self.viewer.current_load_token is not token: return
                        move_to_main_thread(full_res_dict, x)

        except Exception as e: 
            print(f"Async loader processing error: {e}")
        finally:
            self.queue.task_done()
   
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
        if self.app.statusbar_mode.get() != "None":
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
        if perf_counter() - self._last_seek_time > 0.05:  # 50 ms throttle
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
        self.app.canvas.configure(bg="black")
        self.app.canvas.pack_forget()
        self.app.vlc_frame.pack(expand=True, fill=tk.BOTH)
        self.app.vlc_frame.bind("<Configure>", self.app.window_resize)

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
