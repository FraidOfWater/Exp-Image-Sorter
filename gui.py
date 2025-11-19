import os, threading, tkinter as tk, tkinter.font as tkfont, tkinter.scrolledtext as tkst, json
import os, json, tkinter as tk
from tkinter import ttk
from tkinter.ttk import Panedwindow

import subprocess, sys
from collections import deque
from destination_viewer import Destination_Viewer
from resizing import Application

import threading

class GUIManager(tk.Tk):
    "Initialization"
    Image_frame = None
    second_window_viewer = None
    focused_on_secondwindow = False
    last_model = None
    displayed_obj = None
    def __init__(self, fileManager, jprefs) -> None:
        super().__init__()
        self.fileManager = fileManager
        self.train_thread = None
        self.train_status_var = tk.StringVar(value="")
        self.model_path = None
        self.selected_btn = None
        "INITIALIZE USING PREFS: THEME"
        self.themes = fileManager.jthemes
        default = self.themes.get("Midnight", {})

        self.main_colour =                      default.get("main_colour") or "#202041"
        self.viewer_bg =                        default.get("viewer_bg") or "#141433"
        self.grid_background_colour =           default.get("grid_background_colour") or "#303276"
        self.pane_divider_colour =              default.get("pane_divider_colour") or "grey"

        self.button_colour =                    default.get("button_colour") or "#24255C",
        self.button_colour_when_pressed =       default.get("button_colour_when_pressed") or "#303276",
        self.button_text_colour =               default.get("button_text_colour") or "white"
        self.button_text_colour_when_pressed =  default.get("button_text_colour_when_pressed") or "white"

        self.field_colour =                     default.get("field_colour") or "#303276"
        self.field_activated_colour =           default.get("field_activated_colour") or "#888BF8"
        self.field_text_colour =                default.get("field_text_colour") or "white"
        self.field_text_activated_colour =      default.get("field_text_activated_colour") or "black"

        self.checkbox_height =                  int(default.get("checkbox_height")) or 25
        self.gridsquare_padx =                  int(default.get("gridsquare_padx")) or 2
        self.gridsquare_pady =                  int(default.get("gridsquare_pady")) or 2
        self.whole_box_size =                   int(default.get("whole_box_size")) or 0
        self.square_border_size =               int(default.get("square_border_size")) or 0

        self.square_default =                   default.get("square_default") or "#303276"
        self.square_selected =                  default.get("square_selected") or "#888BF8"

        self.square_text_colour =               default.get("square_text_colour") or "white"
        self.square_text_box_colour =           default.get("square_text_box_colour") or "#303276"
        self.square_text_box_selection_colour = default.get("square_text_box_selection_colour") or "#888BF8"
            
        "INITIALIZE USING PREFS: SETTINGS"
        "VALIDATION"
        expected_keys = ["paths", "user", "technical", "qui", "window_settings", "viewer"]
        missing_keys = [key for key in expected_keys if jprefs and key not in jprefs]
        if missing_keys: print(f"Missing a key(s) in prefs: {missing_keys}, defaults will be used.")

        if jprefs == None:
            jprefs = {}
        paths = jprefs.get("paths", {})
        self.source_folder = paths.get("source", "")
        self.destination_folder = paths.get("destination", "")
        self.lastsession = paths.get("lastsession", "")
        self.categories = paths.get("categories", [])
        self.excludes = paths.get("excludes", [])
        self.model_path = paths.get("model", None)

        user = jprefs.get("user", {})
        self.thumbnailsize = int(user.get("thumbnailsize", 256))
        self.prediction_thumbsize = int(user.get("prediction_thumbsize", 224))
        self.hotkeys = user.get("hotkeys", "123456qwerty7890uiopasdfghjklzxcvbnm")
        self.force_scrollbar = bool(user.get("force_scrollbar", True))
        self.auto_load = bool(user.get("auto_load", True))
        self.do_anim_loading_colors = bool(user.get("do_anim_loading_colors", False))
        self.show_statusbar = tk.BooleanVar(value=user.get("show_statusbar", True))
        self.show_ram = tk.BooleanVar(value=user.get("show_ram", False))
        self.show_advanced = tk.BooleanVar(value=user.get("show_advanced", False))
        
        tech = jprefs.get("technical", {})
        self.filter_mode = tech.get("quick_preview_filter") if tech.get("quick_preview_filter") in ["NEAREST", "BILINEAR", "BICUBIC", "LANCZOS"] else "BILINEAR"
        #threads                # Exlusively for fileManager
        #max_concurrent_frames  # Exlusively for fileManager
        #autosave               # Exlusively for fileManager

        gui = jprefs.get("qui", {}) # should be spelled gui XD
        self.squares_per_page_intvar = tk.IntVar(value=int(gui.get("squares_per_page", 17)))
        a = gui.get("display_order")
        if a not in ("Filename", "Date"):
            a = "Filename"
        self.display_order = tk.StringVar(value=a)

        self.show_next = tk.BooleanVar(value=bool(gui.get("show_next", True)))
        self.dock_view = tk.BooleanVar(value=bool(gui.get("dock_view", True)))
        self.dock_side = tk.BooleanVar(value=bool(gui.get("dock_side", True)))
        self.theme = tk.StringVar(value=gui.get("theme", "Midnight"))
        self.volume = int(gui.get("volume", 50))

        w = jprefs.get("window_settings", {})
        self.main_geometry = w.get("main_geometry") # Will go fullscreen if None.
        self.viewer_geometry = w.get("viewer_geometry", f"{int(self.winfo_screenwidth()*0.5)}x{int(self.winfo_screenheight()*0.5)}+{-8+365}+60") 
        self.destpane_geometry = w.get("destpane_geometry", f"{int(self.winfo_screenwidth()*0.5)}x{int(self.winfo_screenheight()-120)}+{-8+365}+60") 
        self.leftpane_width = int(w.get("leftpane_width", 363))
        self.middlepane_width = int(w.get("middlepane_width", 363))
        self.images_sorted = tk.IntVar(value=int(w.get("images_sorted", 363)))
        self.images_sorted_strvar = tk.StringVar(value=f"Sorted: {self.images_sorted.get()}") # Sorted: 1953
        self.winfo_toplevel().title(f"EXP: {self.images_sorted_strvar.get()}")

        self.viewer_prefs = jprefs.get("viewer", {})
        self.viewer_prefs["colors"] = self.viewer_prefs.get("colors", None) or {
                "canvas": self.viewer_bg or"#303276",
                "statusbar": "#202041",
                "button": "#24255C",
                "active_button": "#303276",
                "text": "#FFFFFF",
                "volume": self.volume,
                }

        if self.main_geometry: self.geometry(self.main_geometry)
        else: 
            self.state('zoomed')
            self.main_geometry = f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+-8+0"
        
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        
        self.protocol("WM_DELETE_WINDOW", self.closeprogram)

        self.images_left_stats_strvar = tk.StringVar(value="Left: NaN/NaN/NaN")
        self.current_ram_strvar = tk.StringVar(value="RAM: 0 MB") # RAM: 95.34 MB
        self.animation_stats_var = tk.StringVar(value="Anim: 0/100") # Anim: displayedlist with frames/displayedlist with framecount/(queue)
        self.resource_limiter_var = tk.StringVar(value="0/1000") # Frames: frames + frames_dest / max
        self.frame_gen_queue_var = tk.StringVar(value="Q:")

        self.standalone_var = tk.BooleanVar(value=False)
    
    def toggle_statusbar(self):
        if not self.show_statusbar.get():
            self.statusbar.grid_forget()
            if self.Image_frame:
                #self.Image_frame.master.update()
                self.Image_frame.mouse_double_click_left()

        else:
            self.statusbar.grid(row=1, column=0, sticky="ew")
            if self.Image_frame:
                #self.Image_frame.master.update()
                self.Image_frame.mouse_double_click_left()

    def toggle_ram_label(self):
        if not self.show_ram.get():
            self.ram_label.pack_forget()
        else:
            self.ram_label.pack(side=tk.LEFT, fill="y")

    def toggle_advanced_label(self):
        if not self.show_advanced.get():
            self.animation_stats_label.pack_forget()
            self.resource_limiter.pack_forget()
            self.frame_gen_queue_label.pack_forget()
        else:
            self.animation_stats_label.pack(side="left", fill="y")
            self.resource_limiter.pack(side="left", fill="y")
            self.frame_gen_queue_label.pack(side="left", fill="y")

    def initialize(self):
        self.smallfont = tkfont.Font(family='Helvetica', size=10)
        style = ttk.Style()
        style.configure('Theme_dividers.TPanedwindow', background=self.pane_divider_colour)
        style.configure("Theme_checkbox.TCheckbutton", background=self.main_colour, foreground=self.button_text_colour, highlightthickness = 0) # Theme for checkbox
        style.configure("Theme_square.TCheckbutton", background=self.square_text_box_colour, foreground=self.button_text_colour)
        self.style = style

        statusbar_bg = "#202041"
        txt_color = "#FFFFFF"

        statusbar = tk.Frame(self, bd=1, relief=tk.SUNKEN, bg=statusbar_bg)

        if self.show_statusbar.get():
            statusbar.grid(row=1, column=0, sticky="ew")
        self.statusbar = statusbar

        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_columnconfigure(0, weight=1)

        self.sorted_label = tk.Label(statusbar, textvariable=self.images_sorted_strvar, 
                                     bg=statusbar_bg, fg=txt_color, anchor="e", padx=5)
        self.images_left_label = tk.Label(statusbar, textvariable=self.images_left_stats_strvar, 
                                          bg=statusbar_bg, fg=txt_color, anchor="e", padx=5)
        self.animation_stats_label = tk.Label(statusbar, textvariable=self.animation_stats_var, 
                                              bg=statusbar_bg, fg=txt_color, anchor="e", padx=5)
        self.resource_limiter = tk.Label(statusbar, textvariable=self.resource_limiter_var, 
                                         bg=statusbar_bg, fg=txt_color, anchor="e", padx=5)
        self.frame_gen_queue_label = tk.Label(statusbar, textvariable=self.frame_gen_queue_var, 
                                              bg=statusbar_bg, fg=txt_color, anchor="e", padx=5)
        self.ram_label = tk.Label(statusbar, textvariable=self.current_ram_strvar, 
                                  bg=statusbar_bg, fg=txt_color, anchor="e", padx=5)
        self.train_status = tk.Label(statusbar, textvariable=self.train_status_var, 
                                     bg=statusbar_bg, fg=txt_color, anchor="w", padx=10)

        self.sorted_label.pack(side="left", fill="y")
        self.images_left_label.pack(side="left", fill="y")
        self.train_status.pack(side="right", fill="y")
        if self.show_advanced.get():
            self.animation_stats_label.pack(side="left", fill="y")
            self.resource_limiter.pack(side="left", fill="y")
            self.frame_gen_queue_label.pack(side="left", fill="y")
        if self.show_ram.get():
            self.ram_label.pack(side="left", fill="y")
        
        # Menus
        menu_bar = tk.Menu(self.master)

        file_menu = tk.Menu(menu_bar, tearoff=tk.OFF)
        view_menu = tk.Menu(menu_bar, tearoff=tk.OFF)
        order_menu = tk.Menu(menu_bar, tearoff=tk.OFF)
        category_menu = tk.Menu(menu_bar, tearoff=tk.OFF)
        theme_menu = tk.Menu(menu_bar, tearoff=tk.OFF)

        menu_bar.add_cascade(label="File", menu=file_menu)
        menu_bar.add_cascade(label="View", menu=view_menu)
        menu_bar.add_cascade(label="Order", menu=order_menu)
        menu_bar.add_cascade(label="Training", menu=category_menu)
        menu_bar.add_cascade(label="Themes", menu=theme_menu)

        # File
        file_menu.add_command(label="Source Folder", command=lambda: self.filedialog(self.source_entry_field, type="src"), accelerator="Ctrl+S")
        file_menu.add_command(label="Destination Folder", command=lambda: self.filedialog(self.destination_entry_field, type="dst"), accelerator="Ctrl+D")
        file_menu.add_command(label="Select Session", command=lambda: self.filedialog(self.session_entry_field, type="session"))
        file_menu.add_separator()
        file_menu.add_command(label="Exclusions", command=self.excludeshow)        
        file_menu.add_separator()
        file_menu.add_command(label="Load Session", command=self.fileManager.loadsession, accelerator="Ctrl+L")
        file_menu.add_command(label="Save Session", command=lambda: self.fileManager.savesession(True), accelerator="Ctrl+S")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.closeprogram, accelerator="Ctrl+Q")
        
        # View
        def toggle_standalone_mode():
            for x in self.gridmanager.displayedlist:
                obj = x.obj
                x.canvas.itemconfig(x.canvas_image_id, image=None)
                obj.frame = None
                if not obj.destframe:
                    obj.thumb = None
                    if obj.frames:
                        obj.clear_frames()

        self.prediction = tk.BooleanVar(value=False)
        
        order_menu.add_radiobutton(label="Filename",value="Filename", variable=self.display_order, command=self.sort_imagelist)
        order_menu.add_radiobutton(label="Date", value="Date", variable=self.display_order, command=self.sort_imagelist)
        order_menu.add_radiobutton(label="Size", value="Size", variable=self.display_order, command=self.sort_imagelist)
        order_menu.add_radiobutton(label="Dimensions", value="Dimensions", variable=self.display_order, command=self.sort_imagelist)
        order_menu.add_radiobutton(label="Nearest", value="Nearest", variable=self.display_order, command=self.sort_imagelist)
        order_menu.add_radiobutton(label="Confidence", value="Confidence", variable=self.display_order, command=self.sort_imagelist)
        order_menu.entryconfig("Nearest", state="disabled")
        self.order_menu = order_menu
        order_menu.entryconfig("Confidence", state="disabled")
        order_menu.add_separator()
        def test():
            if self.prediction.get():
                order_menu.entryconfig("Confidence", state="active")
                imagefiles = [x for x in self.fileManager.imagelist if x.pred == None or self.last_model != self.model_path]
                imagefiles.extend([x.obj for x in self.gridmanager.unassigned if x.obj.pred == None or self.last_model != self.model_path])
                if imagefiles:
                    self.model_infer(self.model_path, imagefiles)
                    self.display_order.set("Confidence")
            else:
                order_menu.entryconfig("Confidence", state="normal")
                order_menu.entryconfig("Confidence", state="disabled")
        order_menu.add_checkbutton(label="Group by Prediction", variable=self.prediction, command=test)

        view_menu.add_checkbutton(label="Show-next", variable=self.show_next)
        #view_menu.add_checkbutton(label="Single-Image", variable=self.standalone_var, command=toggle_standalone_mode)
        view_menu.add_checkbutton(label="Statusbar", variable=self.show_statusbar, command=self.toggle_statusbar)
        view_menu.add_checkbutton(label="Dock Type", variable=self.dock_view, command=self.change_viewer)
        view_menu.add_checkbutton(label="Dock side", variable=self.dock_side, command=self.change_dock_side)

        view_menu.add_separator()
        view_menu.add_checkbutton(label="Show RAM", variable=self.show_ram, command=self.toggle_ram_label)
        view_menu.add_checkbutton(label="Show Advanved", variable=self.show_advanced, command=self.toggle_advanced_label)
        view_menu.add_separator()
        view_menu.add_command(label="Settings")
                        
        # Category
        category_menu.add_command(label="Select model", command=self.select_model)
        category_menu.add_separator()
        category_menu.add_command(label="Automatic", command=self.automatic_training)
        category_menu.add_command(label="Manual", command=self.open_category_manager)
    
        # Themes
        def hints():
            height = 250
            width = int(height * 2.1)
            new = tk.Toplevel(self, width=width, height=height, bg=self.main_colour) 
            new.transient(self)
            new.geometry(f"{width}x{height}+{int(self.winfo_width()/2-width/2)}+{int(self.winfo_height()/2-height/2)}")
            new.grid_rowconfigure(0, weight=1)
            new.grid_columnconfigure(0, weight=1)
            text = """\
Select model:
    Use a previously trained model.

Automatic (Recursive):
    Train from current destinations. Marks each destination as a category,
    and tries to predict similar images.

Manual (Recursive): 
    Train from user-defined destinations. (Uses source-folder as root for now.)
    Each category is independent, "subcategories", (and their subfolders), 
    will be excluded from the "parent categories".

Show Predictions:
    Will predict each image's destination and group them together.
            """
            # Create a Label with wraplength
            label = tk.Label(
                new,
                text=text, fg=self.field_text_colour, bg=self.main_colour,
                justify='left',
                anchor='nw', wraplength=height
            )
            label.pack(fill='both', expand=False, padx=10, pady=10)
            def on_resize(e):
                new_width = max(e.width - 20, 20)
                label.config(wraplength=new_width)
            new.bind('<Configure>', on_resize)
        
        for x in self.themes.keys():
            theme_menu.add_command(label=x, command=lambda x=x: self.change_theme(x))
        category_menu.add_separator()
        category_menu.add_command(label="Hints", command=hints)

        self.config(menu=menu_bar)
        
        toppane = Panedwindow(self, orient="horizontal")

        leftui = tk.Frame(toppane, name="leftui", width=self.leftpane_width, bg=self.main_colour)
        middlepane_frame = tk.Frame(toppane, name="middlepane", bg=self.viewer_bg, width = self.middlepane_width)
        imagegridframe = tk.Frame(toppane, bg=self.grid_background_colour)
        imagegrid = tk.Text(imagegridframe, name="imagegrid", wrap='word', borderwidth=0,
                                highlightthickness=0, state="normal", bg = self.grid_background_colour)
        self.vbar = tk.Scrollbar(imagegridframe, command=lambda *args: scroll(imagegrid, args))

        leftui.grid_propagate(False)

        imagegridframe.grid(row=0, column=2, sticky="NSEW")
        
        imagegrid.configure(state="disabled")
        imagegrid.bind("<Up>", lambda e: "break")
        imagegrid.bind("<Down>", lambda e: "break")
        imagegrid.bind("<MouseWheel>", lambda e: "break")
        imagegrid.bind("<MouseWheel>", lambda e: scroll(imagegrid , ("scroll_s", e)))
        leftui.bind("<Button-1>", lambda e: self.focus())
        middlepane_frame.bind("<Button-1>", lambda e: self.focus())

        toppane.add(leftui, weight=0)
        self.leftui = leftui
        self.first_page_buttons()

        if self.force_scrollbar:
            self.vbar.grid(row=0, column=1, sticky='ns')
            imagegrid.configure(yscrollcommand=self.vbar.set)

        imagegrid.grid(row=0, column=0, padx = max(0, self.gridsquare_padx-1), pady=max(0, self.gridsquare_pady-1), sticky="NSEW")
        imagegridframe.rowconfigure(1, weight=0)
        imagegridframe.rowconfigure(0, weight=1)
        imagegridframe.columnconfigure(1, weight=0)
        imagegridframe.columnconfigure(0, weight=1)
        toppane.add(imagegridframe, weight=1)

        toppane.grid(row=0, column=0, sticky="NSEW")
        toppane.configure(style='Theme_dividers.TPanedwindow')

        self.toppane = toppane
        
        self.middlepane_frame = middlepane_frame
        self.imagegridframe = imagegridframe
        self.imagegrid = imagegrid
        
        self.destination_viewer = Destination_Viewer(self.fileManager)
        self.gridmanager = GridManager(self.fileManager)

    def filedialog(self, entry, event=None, type=None):
        from tkinter import filedialog as tkFileDialog
        if type == "session":
            path = tkFileDialog.askopenfile(initialdir=os.getcwd(), 
                                        title="Select Session Data File", filetypes=(("JavaScript Object Notation", "*.json"),))
        elif type == "src":
            path = tkFileDialog.askdirectory(title="Select Source folder")
        elif type == "dst":
            path = tkFileDialog.askdirectory(title="Select Destination folder")
        if path == "" or path == None:
            return
        entry.delete(0, tk.END)
        entry.insert(0, path)
        if type == "dst" and hasattr(self, "folder_explorer") and self.folder_explorer:
            self.folder_explorer.set_view(path)
        elif type == "src":
            self.fileManager.validate("button")

    def first_page_buttons(self):
        but_t = self.button_text_colour
        but_c = self.button_colour
        but_c_a = self.button_colour_when_pressed
        but_c_a_t = self.button_text_colour_when_pressed
        
        self.first_frame = tk.Frame(self.leftui, bg=self.field_colour)

        self.source_entry_field = tk.Entry(self.first_frame, text=self.source_folder, bg=self.field_colour, fg=self.field_text_colour)
        self.destination_entry_field = tk.Entry(self.first_frame, text=self.destination_folder, bg=self.field_colour, fg=self.field_text_colour)
        self.session_entry_field = tk.Entry(self.first_frame, text=self.lastsession, bg=self.field_colour, fg=self.field_text_colour)

        s_b = tk.Button(self.first_frame, text="Source", command=lambda: self.filedialog(self.source_entry_field, type="src"),
            bg=but_c, fg=but_t, activebackground = but_c_a, activeforeground=but_c_a_t)
        d_b = tk.Button(self.first_frame, text="Destination", command=lambda: self.filedialog(self.destination_entry_field, type="dst"),
            bg=but_c, fg=but_t, activebackground = but_c_a, activeforeground=but_c_a_t)
        self.ses_b = tk.Button(self.first_frame, text="Session", command=lambda: self.filedialog(self.session_entry_field, type="session"),
            bg=but_c, fg=but_t, activebackground = but_c_a, activeforeground=but_c_a_t)
        
        self.source_entry_field.insert(0, self.source_folder or "Right click to Select Source Folder")
        self.destination_entry_field.insert(0, self.destination_folder or "Right click to Select Destination Folder")
        self.session_entry_field.insert(0, self.lastsession or "No last Session")

        new_session_b = tk.Button(self.first_frame, text="New Session", command=self.fileManager.validate,
            bg=but_c, fg=but_t, activebackground = but_c_a, activeforeground=but_c_a_t)
        self.new_session_b = new_session_b
        load_session_b = tk.Button(self.first_frame, text="Load Session", command=self.fileManager.loadsession,
            bg=but_c, fg=but_t, activebackground = but_c_a, activeforeground=but_c_a_t)
        squares_per_page_b = tk.Entry(self.first_frame, textvariable=self.squares_per_page_intvar, takefocus=False, 
                                      bg=self.field_colour, fg=self.field_text_colour)
        if self.squares_per_page_intvar.get() < 0: self.squares_per_page_intvar.set(1)
        
        self.first_frame.columnconfigure(0, weight=0)
        self.first_frame.columnconfigure(1, weight=1)
        s_b.grid(row=0, column=0, sticky="ew", padx=2)
        self.source_entry_field.grid(row=0, column=1, sticky="ew", padx=2)
        new_session_b.grid(row=0, column=2, sticky="ew", padx=2)

        d_b.grid(row=1, column=0, sticky="ew", padx=2)
        self.destination_entry_field.grid(row=1, column=1, sticky="ew", padx=2)
        #squares_per_page_b.grid(row=1, column=2, sticky="ew", padx=2)

        self.ses_b.grid(row=2, column=0, sticky="ew", padx=2)
        self.session_entry_field.grid(row=2, column=1, sticky='ew', padx=2)
        load_session_b.grid(row=2, column=2, sticky="ew", padx=2)
        
        self.leftui.columnconfigure(0, weight=1)
        self.first_frame.grid(row=0, column=0, sticky="ew")
        self.first_page = [new_session_b, load_session_b]

        new_session_b.bind("<Enter>", lambda e: new_session_b.config(bg=but_c_a, fg=but_c_a_t,))
        new_session_b.bind("<Leave>", lambda e: new_session_b.config(bg=but_c, fg=but_t))

        load_session_b.bind("<Enter>", lambda e: load_session_b.config(bg=but_c_a, fg=but_c_a_t,))
        load_session_b.bind("<Leave>", lambda e: load_session_b.config(bg=but_c, fg=but_t))


        self.load_session_b = load_session_b

        squares_per_page_b.bind("<FocusIn>", lambda e: squares_per_page_b.config(bg=self.field_activated_colour, fg=self.field_text_activated_colour))
        squares_per_page_b.bind("<FocusOut>", lambda e: (squares_per_page_b.config(bg=self.field_colour, fg=self.field_text_colour), self.focus()))
           
        for x, t in [(self.source_entry_field, "src"), (self.destination_entry_field, "dst"), (self.session_entry_field, "session")]:
            x.bind("<FocusIn>", lambda e, x=x: x.config(bg=self.field_activated_colour, fg=self.field_text_activated_colour))
            x.bind("<FocusOut>", lambda e, x=x: x.config(bg=self.field_colour, fg=self.field_text_colour))
            x.bind("<Button-3>", lambda e, x=x, t=t: self.filedialog(x, type=t))

    def guisetup(self):
        self.order_menu.entryconfig("Nearest", state="normal")
        filemanager = self.fileManager
        but_t = self.button_text_colour
        but_c = self.button_colour
        but_c_a = self.button_colour_when_pressed
        but_c_a_t = self.button_text_colour_when_pressed

        arrowkeys = ["<Up>", "<Down>", "<Left>", "<Right>", "<Return>","<space>", "<F2>", "<Control-z>", "<Control-Z>"]
        for arrowkey in arrowkeys:
            self.bind_all(f"{arrowkey}", lambda e: filemanager.navigator.bindhandler(e))

        self.load_session_b.grid_forget()
        self.session_entry_field.grid_forget()
        self.ses_b.grid_forget()

        frame = tk.Frame(self.first_frame, bg=self.field_colour)

        clear_all_b = tk.Button(frame, text="Unselect", command=self.fileManager.clear, bg=but_c, fg=but_t, 
                                activebackground = but_c_a, activeforeground=but_c_a_t,)

        move_all_b = tk.Button(self.first_frame, text="Move All", command=self.fileManager.moveall, bg=but_c, fg=but_t, 
                               activebackground = but_c_a, activeforeground=but_c_a_t,)
        
        view_options = ["Unassigned", "Assigned", "Moved"]
        self.current_view = tk.StringVar(value="Unassigned")
        self.current_view.trace_add("write", lambda *args: self.current_view_changed())

        view_menu = tk.OptionMenu(frame, self.current_view, *view_options)
        view_menu.config(bg=but_c, fg=but_t,activebackground=but_c_a, activeforeground=but_c_a_t, highlightbackground=but_c, highlightthickness=1)

        clear_all_b.bind("<Enter>", lambda e: clear_all_b.config(bg=but_c_a, fg=but_c_a_t,))
        clear_all_b.bind("<Leave>", lambda e: clear_all_b.config(bg=but_c, fg=but_t))
        move_all_b.bind("<Enter>", lambda e: move_all_b.config(bg=but_c_a, fg=but_c_a_t,))
        move_all_b.bind("<Leave>", lambda e: move_all_b.config(bg=but_c, fg=but_t))
                 
        from folders import FolderExplorer
        self.folder_explorer = FolderExplorer(self.leftui, self.hotkeys)
        self.new_session_b.destroy()
        
        self.first_frame.grid(row=1, column=0, sticky="ew")

        frame.columnconfigure(0, weight=8)
        frame.columnconfigure(1, weight=1)

        view_menu.grid(row=0, column=0, sticky = "EW")
        clear_all_b.grid(row=0, column=1, sticky="EW")

        move_all_b.grid(row=2, column=0, sticky="EW")
        frame.grid(row=2, column=1, sticky="ew")
        
        self.leftui.rowconfigure(3, weight=1)
        self.folder_explorer.grid(row=3, column=0, sticky="nsew")
    
        if self.dock_view.get():
            self.change_viewer()
            self.update()
    
    "Navigation / options"
    def change_viewer(self):
        "Change which viewer is in use. Dock or secondary window"
        old = self.fileManager.navigator.old
        m_frame = self.middlepane_frame
        toppane = self.toppane
        imagegridframe = self.imagegridframe
        if m_frame.winfo_width() != 1:
            self.middlepane_width = m_frame.winfo_width()
        
        self.displayed_obj = None
        m_frame.configure(width = self.middlepane_width)
        self.focused_on_secondwindow = False
        if self.dock_view.get():
            self.toppane.forget(imagegridframe)
            if self.dock_side.get():
                toppane.add(m_frame, weight = 0)
                toppane.add(imagegridframe, weight = 1)
            else:
                toppane.add(imagegridframe, weight = 1)
                toppane.add(m_frame, weight = 0)
            
            if self.second_window_viewer:
                m_frame.configure(width = self.middlepane_width)
                self.toppane.update()
                self.second_window_viewer.window_close()
                self.displayimage(old.obj)

        else: # Window
            try:
                panes = [x for x in self.toppane.panes() if x != None]
                if "middlepane" in [x.rsplit(".", 1)[1] for x in panes]:
                    self.toppane.forget(m_frame)
                if self.Image_frame != None:
                    self.Image_frame.set_image(None)
                    #self.viewer_prefs["volume"] = self.Image_frame.volume
                    self.Image_frame.save_json()
                    
                    m_frame.grid_forget()
                    self.displayimage(old.obj)
                    
            except Exception as e:
                print(f"Error in change_viewer: {e}")

    def change_dock_side(self):
        "Change which side you want the dock"
        m_frame = self.middlepane_frame
        toppane = self.toppane
        imagegridframe = self.imagegridframe
        imagegrid = self.imagegrid

        if m_frame.winfo_width() == 1:
            return
        self.middlepane_width = m_frame.winfo_width()
        m_frame.configure(width = self.middlepane_width)
        if self.dock_view.get():
            toppane.forget(m_frame)
            toppane.forget(self.imagegridframe)
            if self.dock_side.get():
                if self.force_scrollbar:
                    self.vbar.grid(row=0, column=1, sticky='ns')
                    imagegrid.configure(yscrollcommand=self.vbar.set)
                    imagegrid.grid(row=0, column=0, padx = max(0, self.gridsquare_padx-1), sticky="NSEW")

                    imagegridframe.columnconfigure(1, weight=0)
                    imagegridframe.columnconfigure(0, weight=1)

                toppane.add(m_frame, weight = 0)
                toppane.add(imagegridframe, weight = 1)
            else:
                if self.force_scrollbar:
                    self.vbar.grid(row=0, column=0, sticky='ns')
                    imagegrid.configure(yscrollcommand=self.vbar.set)
                    imagegrid.grid(row=0, column=1, padx = max(0, self.gridsquare_padx-1), sticky="NSEW")

                    imagegridframe.columnconfigure(0, weight=0)
                    imagegridframe.columnconfigure(1, weight=1)

                toppane.add(imagegridframe, weight = 1)
                toppane.add(m_frame, weight = 0)
    
    def sort_imagelist(self):
        # size, dimensions
        # first CLEAR the imagegrid...
        from operator import attrgetter
        from natsort import natsorted
        from PIL import Image
        if self.fileManager.first_run: return

        def main_thread():
            self.current_view_changed()

        MODE = self.display_order.get().lower()
        self.fileManager.imagelist.extend(reversed([x.obj for x in self.gridmanager.unassigned]))
        self.gridmanager.unassigned.clear()
        self.gridmanager.gridsquarelist.clear()
        if self.prediction.get():
            def run():
                # reorder by confidence.
                CONF_THRESHOLD = 0.4            
                no_pred = []
                predictable = []
                for x in self.fileManager.imagelist:
                    if x.pred:
                        predictable.append(x)
                    else:
                        no_pred.append(x)

                # group together with same predicted label.
                classes = {}
                for x in predictable:
                    if classes.get(x.pred, None) == None:
                        classes[x.pred] = []
                    classes[x.pred].append(x)

                # distinguish using colors
                for key, c in classes.items():
                    c[:] = [x for x in c if x.conf >= CONF_THRESHOLD]
                    if len(c) < 2:
                        continue
                    
                    if MODE.lower() == "filename":
                        classes[key] = natsorted(c, key=attrgetter("name"), reverse=True)
                    elif MODE.lower() == "date":
                        for obj in c:
                            obj.mod_time = os.path.getmtime(obj.path)
                        c.sort(key=attrgetter("mod_time"), reverse=False)
                    elif MODE == "size":
                        for obj in c:
                            file_stats = os.stat(obj.path)
                            obj.file_size = file_stats.st_size
                        c.imagelist.sort(key=attrgetter("file_size"), reverse=False)
                    elif MODE == "dimensions":
                        from imageio import get_reader
                        for obj in self.fileManager.imagelist:
                            if obj.dimensions == (-2, 0.0):
                                if obj.ext in ("mp4", "webm"):
                                    try:
                                        reader = None
                                        reader = get_reader(obj.path)
                                        pil_img = Image.fromarray(reader.get_data(0))
                                        w, h = pil_img.size
                                        ratio = w/h # ratio 
                                        if w == h: orientation = 0.0
                                        elif w < h: orientation = -1.0
                                        else: orientation = 1.0
                                        obj.dimensions = (orientation, ratio)
                                    except Exception as e:
                                        print(f"Couldn't read: {obj.name} : Error: {e}")
                                    finally: 
                                        if reader: reader.close()
                                else:
                                    with Image.open(obj.path) as pil_img:
                                        w, h = pil_img.size
                                        ratio = w/h # ratio
                                        if w == h: orientation = 0.0
                                        elif w < h: orientation = -1.0
                                        else: orientation = 1.0
                                        obj.dimensions = (orientation, ratio)
                                        
                        self.fileManager.imagelist.sort(key=attrgetter("dimensions"), reverse=False)

                    elif MODE.lower() == "nearest":
                        self.fileManager.reorder_as_nearest(c)
                    elif MODE.lower() == "confidence":
                        c.sort(key=lambda x: x.conf, reverse=False) 
                classes = sorted(list(classes.values()), key=lambda x: len(x), reverse=False) # sorted by class and conf

                predictable = []
                for x in classes:
                    predictable.extend(x)

                def helper():
                    self.fileManager.imagelist = predictable + no_pred
                    self.gridmanager.change_view([])
                    self.fileManager.navigator.view_change()
                    to_load = self.squares_per_page_intvar.get() - len(self.gridmanager.displayedlist)
                    left = len(self.fileManager.imagelist)
                    items = min(to_load, left)
                    if items > 0: self.gridmanager.load_more(amount=items)
                self.after(1, helper)
            def helper():
                self.fileManager.reorder_as_nearest(self.fileManager.imagelist)
                self.after(1, run)
            if MODE == "nearest":
                a = threading.Thread(target=helper, daemon=True)
                a.start()
            else:
                a = threading.Thread(target=run, daemon=True)
                a.start()
            return
        elif MODE == "filename":
            self.fileManager.imagelist = natsorted(self.fileManager.imagelist, key=attrgetter("name"), reverse=True)
        elif MODE == "date":
            for obj in self.fileManager.imagelist:
                obj.mod_time = os.path.getmtime(obj.path)
            self.fileManager.imagelist.sort(key=attrgetter("mod_time"), reverse=False)
        elif MODE == "size":
            for obj in self.fileManager.imagelist:
                file_stats = os.stat(obj.path)
                obj.file_size = file_stats.st_size
            self.fileManager.imagelist.sort(key=attrgetter("file_size"), reverse=False)
        elif MODE == "dimensions":
            from imageio import get_reader
            for obj in self.fileManager.imagelist:
                if obj.dimensions == (-2, 0.0):
                    if obj.ext in ("mp4", "webm", "mkv", "m4v", "mov"):
                        try:
                            reader = None
                            reader = get_reader(obj.path)
                            pil_img = Image.fromarray(reader.get_data(0))
                            w, h = pil_img.size
                            ratio = w/h # ratio 
                            if w == h: orientation = 0.0
                            elif w < h: orientation = -1.0
                            else: orientation = 1.0
                            obj.dimensions = (orientation, ratio)
                        except Exception as e:
                            print(f"Couldn't read: {obj.name} : Error: {e}")
                        finally: 
                            if reader: reader.close()
                    else:
                        with Image.open(obj.path) as pil_img:
                            w, h = pil_img.size
                            ratio = w/h # ratio
                            if w == h: orientation = 0.0
                            elif w < h: orientation = -1.0
                            else: orientation = 1.0
                            obj.dimensions = (orientation, ratio)

            self.fileManager.imagelist.sort(key=attrgetter("dimensions"), reverse=False)
        elif MODE == "nearest": # threaded gen
            def helper1():
                self.fileManager.reorder_as_nearest(self.fileManager.imagelist)
                self.after(1, main_thread)
            a = threading.Thread(target=helper1, daemon=True)
            a.start()
            return
        elif MODE == "confidence":
            # reorder by confidence.
            CONF_THRESHOLD = 0.4            
            no_pred = []
            predictable = []
            for x in self.fileManager.imagelist:
                if x.pred:
                    predictable.append(x)
                else:
                    no_pred.append(x)

            # group together with same predicted label.
            classes = {}
            for x in predictable:
                if classes.get(x.pred, None) == None:
                    classes[x.pred] = []
                classes[x.pred].append(x)

            # distinguish using colors
            for key, c in classes.items():
                c[:] = [x for x in c if x.conf >= CONF_THRESHOLD]
                c.sort(key=lambda x: x.conf, reverse=True)
            classes = sorted(list(classes.values()), key=lambda x: len(x), reverse=True) # sorted by class and conf

            predictable = []
            for x in classes:
                predictable.extend(x)
            self.fileManager.imagelist = predictable + no_pred

        main_thread()
        
        
    def current_view_changed(self, selected_option=None):
        "When view is changed, send the wanted list to the gridmanager for rendering"
        mgr = self.gridmanager
        fileManager = self.fileManager
        if fileManager.first_run: return
        selected_option = self.current_view.get() if selected_option == None else selected_option

        if selected_option == "Unassigned":
            if not self.prediction.get():
                list_to_display = mgr.unassigned
            else:
                imagefiles = [x for x in self.fileManager.imagelist if x.pred == None or self.last_model != self.model_path]
                imagefiles.extend([x.obj for x in mgr.unassigned if x.obj.pred == None or self.last_model != self.model_path])
                if imagefiles:
                    self.model_infer(self.model_path, imagefiles)
                else:
                    self.display_order.set("Confidence")
                    self.sort_imagelist()
                return
        elif selected_option == "Assigned":
            list_to_display = mgr.assigned
        elif selected_option == "Moved":
            list_to_display = mgr.moved

        mgr.change_view(list_to_display)
        fileManager.navigator.view_change()
        to_load = self.squares_per_page_intvar.get() - len(mgr.displayedlist)
        left = len(self.fileManager.imagelist)
        items = min(to_load, left)
        if items > 0: mgr.load_more(amount=items)
    
    def change_theme(self, theme_name):
        navigator = self.fileManager.navigator
        def set_vals(dict):
            def recursive(children, all_children={}):
                def add_to_dict(key):
                    if key:
                        vals = all_children.get(key, None)
                        if isinstance(vals, list):
                            vals.append(value)
                            all_children[key] = vals
                        else:
                            all_children[key] = [value]
                
                for key, value in children.items():
                    key = key.strip("!")
                    while key and key[-1].isdigit():
                        key = key[:-1]
                    add_to_dict(key)
                    if value.children != {}:
                        recursive(value.children, all_children)
                    """if key in ("button", "frame", "checkbutton", "canvas"):
                        add_to_dict(key)"""
                return all_children
                    
            all_children = recursive(self.toppane.children)

            self.button_text_colour = dict["button_text_colour"]
            self.button_text_colour_when_pressed = dict["button_text_colour_when_pressed"]
            # Main
            self.main_colour = dict["main_colour"]
            self.grid_background_colour = dict["grid_background_colour"]
            self.viewer_bg = dict["viewer_bg"]
            #Buttons
            self.button_colour = dict["button_colour"]
            self.button_colour_when_pressed = dict["button_colour_when_pressed"]
            #Fields
            self.field_colour = dict["field_colour"]
            self.field_text_colour = dict["field_text_colour"]
            self.field_activated_colour = dict["field_activated_colour"]
            self.field_text_activated_colour = dict["field_text_activated_colour"]
            #Divider
            self.pane_divider_colour = dict["pane_divider_colour"]
            #Gridsquares
            self.square_text_colour = dict["square_text_colour"]
            self.square_text_box_colour = dict["square_text_box_colour"]
            self.square_text_box_selection_colour = dict["square_text_box_selection_colour"]

            self.whole_box_size = dict["whole_box_size"]
            self.square_border_size = dict["square_border_size"] # should update gridsquare image pos

            self.checkbox_height = dict["checkbox_height"]
            self.gridsquare_padx = dict["gridsquare_padx"] # should update imagegrid
            self.gridsquare_pady = dict["gridsquare_pady"] # should update imagegrid
            self.whole_box_size = dict["whole_box_size"]
            self.square_border_size = dict["square_border_size"] ### switch all these to one dict only...

            but_t = self.button_text_colour
            but_c = self.button_colour
            but_c_a = self.button_colour_when_pressed
            but_c_a_t = self.button_text_colour_when_pressed

            self.square_default = dict["square_default"]
            self.square_selected = dict["square_selected"]

            navigator.style.configure("Theme_square1.TCheckbutton", background=self.square_text_box_colour, foreground=self.square_text_colour)
            navigator.style.configure("Theme_square2.TCheckbutton", background=self.square_text_box_selection_colour, foreground=self.square_text_colour)

            #Main
            self.config(bg=self.main_colour)
            #Recolor frames (Main_colour, text_colour)
            self.style.configure("Theme_checkbox.TCheckbutton", background=self.main_colour, foreground=but_t) # Theme for checkbox
            for x in all_children["frame"]:
                if x.winfo_exists() and x.widgetName != "ttk::frame":
                    x.config(bg=self.main_colour)

            #Recolor grid (grid_background_colour, text_colour)
            self.style.configure("Theme_square.TCheckbutton", background=self.square_text_box_colour, foreground=but_t) # Gridsquare name and checkbox
            for x in all_children["frame"]:
                if x.winfo_exists() and x.widgetName != "ttk::frame":
                    x.configure(bg=self.grid_background_colour)
            self.leftui.configure(bg = self.main_colour)
            self.imagegrid.configure(bg = self.grid_background_colour)
            
            #Recolor dock background (canvasimage_background)
            self.middlepane_frame.configure(bg = self.viewer_bg)
            
            #Recolor buttons (button_colour, button_press_colour)
            
            """for x in all_children["button"]:
                if x.winfo_exists() and not getattr(x, "tag", None) == "dest_button":
                    x.config(bg = but_c, fg = but_t, activebackground = but_c_a)"""
    
            for x in all_children["optionmenu"]:
                if x.winfo_exists():
                    x.config(bg = but_c, fg = but_t, 
                        activebackground = but_c_a, activeforeground=but_c_a_t)

            #Recolor fields (text_field_colour, field_text_colour)
            for x in all_children["entry"]:
                if x.winfo_exists():
                    x.config(bg = self.field_colour, fg = self.field_text_colour)

            #Gridsquares
            for x in self.gridmanager.gridsquarelist:
                x.configure(background = self.square_default, highlightthickness = self.whole_box_size, highlightcolor=self.square_default,highlightbackground=self.square_default)
                x.canvas.configure(bg=self.square_default, highlightthickness=self.square_border_size, highlightcolor=self.square_default, highlightbackground = self.square_default)
                x.cf.configure(height=self.checkbox_height, background = self.square_text_box_colour)
                x.c.configure(style="Theme_square1.TCheckbutton")
            
            if self.Image_frame != None:
                self.Image_frame.style.configure("bg.TFrame", background=self.viewer_bg)
                self.Image_frame.canvas.config(bg = self.viewer_bg)
                
            #Pane divider (pane_divider_colour)
            self.style.configure('Theme_dividers.TPanedwindow', background=self.pane_divider_colour)

            base = self.thumbnailsize + self.square_border_size + self.whole_box_size
            navigator.actual_gridsquare_width = base + self.gridsquare_padx + self.whole_box_size
            navigator.actual_gridsquare_height = base + self.gridsquare_pady + self.checkbox_height
        
        theme = self.themes[theme_name]
        set_vals(theme)
        navigator.selected(navigator.old)
        self.update()

    "Viewer"
    def displayimage(self, obj):
        "Display image in viewer"
        
        self.displayed_obj = obj
        if self.dock_view.get(): # Dock
            if not self.Image_frame:
                
                self.Image_frame = Application(self.middlepane_frame, savedata=self.viewer_prefs, gui=self)

                #app2 = ImageViewer(self.Image_frame.master, self.Image_frame.canvas)
                self.Image_frame.app2.set_inclusion(self.fileManager.ddp)
                
                #self.loader = AsyncImageLoader(self.Image_frame.set_image)

            #self.Image_frame.loader.request_load(None if obj is None else obj.path, obj)
            self.Image_frame.set_image(None if obj == None else obj.path, obj=obj)
            #self.loader.request_load(None if obj is None else obj.path, obj)
        else: # Window
            if not self.second_window_viewer:                    
                self.second_window_viewer = Application(savedata=self.viewer_prefs, gui=self)
                self.second_window_viewer.app2.set_inclusion(self.fileManager.ddp)
                #self.loader = AsyncImageLoader(self.second_window_viewer.set_image)
            self.second_window_viewer.master.lift()
            self.second_window_viewer.set_image(None if obj == None else obj.path, obj=obj)
            #self.after_idle(self.second_window_viewer.master.focus)
            #self.loader.request_load(None if obj is None else obj.path, obj)

        self.focused_on_secondwindow = True

    "Exit function"
    def closeprogram(self):
        from tkinter.messagebox import askokcancel
        gridmanager = self.gridmanager
        filemanager = self.fileManager
        dest_viewer = filemanager.gui.destination_viewer
        animate = filemanager.animate
        data_dir = filemanager.data_dir

        if gridmanager.assigned and not askokcancel("Designated but Un-Moved files, really quit?", "You have destination designated, but unmoved files. (Simply cancel and Move All if you want)"):
            return
    
        def purge_cache():
            if os.path.isdir(data_dir):
                with os.scandir(data_dir) as entries:
                    ids = {x.obj.id for x in gridmanager.gridsquarelist}
                    for entry in entries:
                        if entry.is_file():
                            id = entry.name.rsplit(".", 1)[0]
                            if id not in ids:
                                try:
                                    os.remove(entry.path)
                                except Exception as e:
                                    print("Failed to remove old cached thumbnails from the data directory.", e)
        def move_temp_to_trash():
            from send2trash import send2trash
            for x in os.listdir(self.fileManager.trash_dir):
                path = os.path.join(self.fileManager.trash_dir, x)
                try:
                    send2trash(path)
                except Exception as e:
                    print("Trash errors:", e)

        filemanager.thumbs.stop_background_worker()
        animate.running.clear()

        if self.second_window_viewer: 
            self.second_window_viewer.window_close()
        if hasattr(dest_viewer, "destwindow"): dest_viewer.close_window()
        if self.Image_frame: self.Image_frame.save_json()
        filemanager.saveprefs(self)
        purge_cache()
        move_temp_to_trash()
        
        self.destroy()

    "Exclusions window"
    def excludeshow(self):
        excludewindow = tk.Toplevel()
        excludewindow.winfo_toplevel().title(
            "Folder names to ignore, one per line. This will ignore sub-folders too.")
        excludetext = tkst.ScrolledText(excludewindow, bg=self.main_colour, fg=self.button_text_colour)
        for x in self.fileManager.exclude:
            excludetext.insert("1.0", x+"\n")
        excludetext.pack()
        excludewindow.protocol("WM_DELETE_WINDOW", lambda: self.excludesave(text=excludetext, toplevelwin=excludewindow))
    
    def excludesave(self, text, toplevelwin):
        text = text.get('1.0', tk.END).splitlines()
        exclude = []
        for line in text:
            if line != "":
                exclude.append(line)
        self.fileManager.exclude = exclude
        try:
            toplevelwin.destroy()
        except Exception as e:
            print(f"Error in excludesave: {e}")

    "Prediction"
    def monitor_csv(self, path, total_epochs):
        import time, os, csv
        waited = 0
        
        dots = "."
        while not os.path.exists(path):
            self.train_status_var.set(f"Waiting to start{dots}")
            if len(dots) == 4:
                dots = "."
            else:
                dots += "."
            time.sleep(3)
            waited += 5
            if waited > 420:
                self.train_status_var.set("Monitor timeout...")
                return
        last_epoch = 0
        while True:
            try:
                time.sleep(3)
                with open(path, newline='') as f:
                    reader = list(csv.reader(f))
                    epoch_rows = len(reader) - 1
                    if epoch_rows != last_epoch:
                        last_epoch = epoch_rows
                        progress = min(100, int((epoch_rows / total_epochs) * 100))
                        if len(dots) == 4:
                            dots = "."
                        else:
                            dots += "."
                        self.train_status_var.set(f"Training: {progress}% ({epoch_rows}/{total_epochs}){dots}")
                        if epoch_rows >= total_epochs:
                            self.train_status_var.set("Model ready.")
                            break
            except Exception:
                self.train_status_var.set("Monitor thread crashed!")

    def automatic_training(self):
        "Generate all files from destinations. Assign as categories. Need self.labels... Inferring size and pred_dir location."
        def train():
            self.train_status_var.set("Labelling dataset...")

            label_path_dict = self.get_folder_contents_with_labels([folder_path for _, folder_path, _, _, _ in self.buttons])
            
            self.train_status_var.set("Building dataset...")
            from Dataset_gen import Dataset_gen
            Data = Dataset_gen(self.fileManager.train_dir, label_path_dict, self.prediction_thumbsize, self.fileManager)       
            path_hash_lookup = Data.gen_thumbs()
            Data.split(0.9)
            
            self.train_status_var.set("Starting model...")
            
            script = os.path.join(os.path.dirname(__file__), "Model_trainer.py")
            python_exe = sys.executable
            names_2_path = {os.path.basename(x[1]): x[1] for x in self.buttons}

            with open(os.path.join(self.fileManager.model_dir, "latest_model_paths.json"), "w") as f:
                json_dict = {}
                json_dict["names_2_path"] = names_2_path
                json.dump(json_dict, f, indent=4)

            cmd = [
                python_exe, script,
                "--data", self.fileManager.train_dir,
                "--epochs", str(100),
                "--name", "latest_model"
            ]

            path_to_results_csv = os.path.join(self.fileManager.model_dir, "classify", "latest_run", "results.csv")
            monitor_thread = threading.Thread(target=self.monitor_csv,
                                            args=(path_to_results_csv, 20), name="monitor", daemon=True)
            monitor_thread.start()
            subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)

            self.model_path = os.path.join(self.fileManager.model_dir, f"latest_model.pt")
            self.train_status_var.set("Model Ready.")
        
        if self.train_thread and self.train_thread.is_alive():
            print("Already running.")
            return
        if self.gridmanager.gridsquarelist:
            self.train_thread = threading.Thread(target=train, name="Auto-training", daemon=True)
            self.train_thread.start()
        else:
            print("You must start a new session before auto-training to generate the destinations.")

    def open_category_manager(self):
        def on_close():
            self.categories = [path for path, state in self.app.folder_states.items() if state == "category"]
            self.excludes = [path for path, state in self.app.folder_states.items() if state == "exclude"]
            self.app.destroy()
        from Category_manager import FolderTreeApp
        dest_root = self.destination_entry_field.get()
        self.app = FolderTreeApp(dest_root, self.categories, self.excludes, self.manual_training) 
        self.app.protocol("WM_DELETE_WINDOW", on_close)
        
    def manual_training(self, name="latest_model"):
        def train():   
            self.categories = [path for path, state in self.app.folder_states.items() if state == "category"]
            self.excludes = [path for path, state in self.app.folder_states.items() if state == "exclude"]
            names_2_path = {os.path.basename(x): x for x in self.categories}
            with open(os.path.join(self.fileManager.model_dir, f"{name}_paths.json"), "w") as f:
                json_dict = {}
                json_dict["names_2_path"] = names_2_path
                json.dump(json_dict, f, indent=4)

            print("Category folders:")
            for path in self.categories:
                print("  ", path)

            print("Excluded folders:")
            for path in self.excludes:
                print("  ", path)

            label_path_dict = self.get_folder_contents_with_labels(self.categories, self.excludes)

            self.train_status_var.set("Building dataset...")
            from Dataset_gen import Dataset_gen
            Data = Dataset_gen(self.fileManager.train_dir, label_path_dict, self.prediction_thumbsize, self.fileManager)       
            path_hash_lookup = Data.gen_thumbs()
            Data.split(0.9)
            
            self.train_status_var.set("Starting model...")
            script = os.path.join(os.path.dirname(__file__), "Model_trainer.py")
            python_exe = sys.executable
            
            names_2_path = {os.path.basename(x): x for x in self.categories}
            cmd = [
                python_exe, script,
                "--data", self.fileManager.train_dir,
                "--epochs", str(100),
                "--name", name
            ]
            
            path_to_results_csv = os.path.join(self.fileManager.model_dir, "classify", "latest_run", "results.csv")
            monitor_thread = threading.Thread(target=self.monitor_csv,
                                            args=(path_to_results_csv, 20), name="monitor", daemon=True)
            monitor_thread.start()
            subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            self.model_path = os.path.join(self.fileManager.model_dir, f"{name}.pt")
            
        if self.train_thread and self.train_thread.is_alive():
            print("Already running.")
            return
        self.train_thread = threading.Thread(target=train, name="Manual-training", daemon=True)
        self.train_thread.start()
    
    def select_model(self):
        from tkinter import filedialog as tkFileDialog
        self.model_path = tkFileDialog.askopenfilename(defaultextension=".pt", filetypes=(("Model File", "*.pt"),),initialdir=self.fileManager.model_dir, title="Select a model to use.")
                                                      
    def get_folder_contents_with_labels(self, destinations, excludes=[]):
        categories = [os.path.abspath(c) for c in destinations]
        excludes = set(os.path.abspath(e) for e in excludes)
        data = {}
        for category_path in categories:
            label = os.path.basename(category_path)
            label_list = data.get(label, [])
            data[label] = label_list
            print(f"[Category] {category_path}")

            for root, dirs, files in os.walk(category_path):
                abs_root = os.path.abspath(root)

                # Prune dirs list to exclude excluded or category folders, so os.walk won't go into them
                pruned_dirs = []
                for d in dirs:
                    d_abs = os.path.abspath(os.path.join(root, d))

                    if any(d_abs == ex or d_abs.startswith(ex + os.sep) for ex in excludes):
                        pass
                    elif any(d_abs == cat for cat in categories):
                        pass
                    else:
                        pruned_dirs.append(d)
                dirs[:] = pruned_dirs
                
                print(f"  Subfolder: {abs_root}")

                for file in files:
                    if file.lower().endswith(("png", "gif", "jpg", "jpeg", "bmp", "pcx", "tiff", "webp", "psd", "jfif", "mp4", "mkv", "m4v", "mov", "webm")):
                        data[label].append((os.path.join(root, file)))
        return data
        
    def model_infer(self, model=None, imagefiles=[]):
        if not imagefiles:
            return
        self.train_status_var.set("Loading model...")
        from Model_inferer import Model_inferer
        model_inferer = Model_inferer(self.fileManager, model, self.prediction_thumbsize)
        for x in imagefiles:
            if x.id == None:
                x.gen_id()
        lookup = {x.id: x for x in imagefiles}
        self.train_status_var.set("Sorting...")

        thread = threading.Thread(target=model_inferer.infer, args=(imagefiles, lookup), daemon=True)
        thread.start()

        self.last_model = model

"""    def view_model_confusion(self):
        from viewer import ConfusionViewer
        from Dataset_gen import Dataset_gen
        Data = Dataset_gen(os.path.join(self.fileManager.pred_dir, "viewer"), self.labels, self.prediction_thumbsize, self.fileManager)
        path_hash_lookup = Data.gen_thumbs() # {"original_path": path, "prediction_thumb_path": thumbpath} key is id.

        confusion_viewer = ConfusionViewer(self.fileManager.model_classes)
        confusion_viewer.infer(self.fileManager.pred_dir, self.prediction_thumbsize, path_hash_lookup)
        confusion_viewer.gui()"""

class GridManager:
    "Handles the gridsqures in the imagegrid"
    def __init__(self, fileManager):
        self.fileManager = fileManager
        self.gui = fileManager.gui

        self.gridsquarelist = []
        self.displayedlist = []
        self.unassigned = []
        self.assigned = []
        self.moved = []
        self.undo = deque(maxlen=20)

        self.style = ttk.Style()
    
    def clear_all(self):
        self.change_view([])
        self.displayedlist.clear()
        self.gridsquarelist.clear()
        self.unassigned.clear()
        self.assigned.clear()
        self.moved.clear()
        self.undo.clear()

    def makegridsquare(self, parent, obj):
        gui = self.gui
        navigator = self.fileManager.navigator

        frame = tk.Frame(parent, borderwidth=0, highlightthickness = gui.whole_box_size, 
                         highlightcolor=gui.square_default, highlightbackground=gui.square_default, padx=0, pady=0)
        frame.grid_propagate(True)
        frame.rowconfigure(0, weight=4)
        frame.rowconfigure(1, weight=1)

        frame.obj = obj

        truncated_name_var = tk.StringVar(frame, value="...")
        frame.obj2 = truncated_name_var

        frame.type = "GRID"

        canvas = tk.Canvas(frame, width=gui.thumbnailsize, height=gui.thumbnailsize, bg=gui.square_default, 
                            highlightthickness=gui.square_border_size, highlightcolor=gui.square_default, 
                            highlightbackground = gui.square_default)
        canvas.grid(column=0, row=0, sticky="NSEW")
        frame.canvas = canvas
        
        canvas_image_id = canvas.create_image(gui.thumbnailsize/2+gui.square_border_size, 
                                                gui.thumbnailsize/2+gui.square_border_size, 
                                                anchor="center", image=frame.obj.thumb)
        frame.canvas_image_id = canvas_image_id

        # --- Create overlay labels (confidence + prediction name) ---
        confidence_text = "97%"  # Example; you’ll replace this dynamically later
        prediction_text = "Cat"  # Example; you’ll replace this dynamically later

        # Padding and styling
        overlay_pad_x = 6
        overlay_pad_y = 4
        overlay_font = ("Arial", 12, "bold")
        overlay_fg = "white"
        overlay_bg = self.gui.main_colour  # black background
        overlay_bg_alpha = 120  # semi-transparent feel (simulated via stipple)

        # Create group for overlays
        # Confidence (bottom-right corner)
        text_id = canvas.create_text(
            gui.thumbnailsize - overlay_pad_x,
            gui.thumbnailsize - overlay_pad_y,
            anchor="se",
            text=confidence_text,
            fill=overlay_fg,
            font=overlay_font
        )
        bbox = canvas.bbox(text_id)
        rect_id = canvas.create_rectangle(
            bbox[0] - 4, bbox[1] - 2, bbox[2] + 4, bbox[3] + 2,
            fill=overlay_bg, outline="", stipple="gray50"
        )
        canvas.tag_lower(rect_id, text_id)

        # Prediction name (top-left corner)
        text_id2 = canvas.create_text(
            overlay_pad_x+2,
            overlay_pad_y+4,
            anchor="nw",
            text=prediction_text,
            fill=overlay_fg,
            font=overlay_font
        )
        bbox2 = canvas.bbox(text_id2)
        rect_id2 = canvas.create_rectangle(
            bbox2[0] - 4, bbox2[1] - 2, bbox2[2] + 4, bbox2[3] + 2,
            fill=overlay_bg, outline="", stipple="gray50"
        )
        canvas.tag_lower(rect_id2, text_id2)

        # Save references
        frame.text_id = text_id
        frame.rect_id = rect_id
        frame.text_id2 = text_id2
        frame.rect_id2 = rect_id2
        canvas.itemconfigure(text_id, state="hidden")
        canvas.itemconfigure(rect_id, state="hidden")
        canvas.itemconfigure(text_id2, state="hidden")
        canvas.itemconfigure(rect_id2, state="hidden")

        check_frame = tk.Frame(frame, height=gui.checkbox_height, padx= 2, bg=gui.square_text_box_colour)
        check_frame.grid_propagate(False)
        check_frame.grid(column=0, row=1, sticky="EW") 
        frame.cf = check_frame

        checked = tk.BooleanVar(value=False)
        check = ttk.Checkbutton(check_frame, textvariable=truncated_name_var, variable=checked, onvalue=True, offvalue=False, 
                                command=lambda: setattr(gui, 'focused_on_secondwindow', False), 
                                style="Theme_square.TCheckbutton")
        check.grid(sticky="EW")
        frame.c = check
        frame.checked = checked

        obj.color = obj.color or gui.square_default
        frame['background'] = obj.color
        canvas['background'] = obj.color
        
        def invoke(e):
            if e.state == 2:
                return
            check.invoke()
            gui.focus()
            
        canvas.bind("<Button-1>", lambda e: invoke(e))
        canvas.bind("<Button-2>", lambda e: (navigator.open_file(frame, e), gui.focus()))
        canvas.bind("<Button-3>", lambda e: (navigator.select(frame, e), gui.focus()))
        check.bind("<Button-3>", lambda e: (navigator.select(frame, e), gui.focus()))
        check_frame.bind("<Button-3>", lambda e: (navigator.select(frame, e)))

        canvas.bind("<MouseWheel>", lambda e: scroll(parent, ("scroll", e)))
        check.bind("<MouseWheel>", lambda e: scroll(parent, ("scroll", e)))
        check_frame.bind("<MouseWheel>", lambda e: scroll(parent, ("scroll", e)))
        if not self.gui.standalone_var.get():
            obj.gridsquare = frame
        return frame
    
    def load_session(self, moved_or_assigned):
        self.fileManager.timer.start()
        gui = self.gui
        for obj in moved_or_assigned:
            gridsquare = self.makegridsquare(gui.imagegrid, obj)
            self.gridsquarelist.append(gridsquare)
            if obj.moved:
                self.moved.append(gridsquare)
            elif obj.dest:
                self.assigned.append(gridsquare)
            else:
                print("error, session list moved or append is in unassigned")
                self.unassigned.append(gridsquare)
        
        for square in self.assigned:
            for btn, folder_path, _, _, _ in self.buttons:
                if square.obj.dest == folder_path:
                    square.obj.setdest((folder_path, btn.default_c))
                    square.obj.color = btn.default_c
                    self.change_square_color(obj, obj.color)
                    break

        for square in self.moved:
            for btn, folder_path, _, _, _ in self.buttons:
                if folder_path in square.obj.path:
                    square.obj.setdest((folder_path, btn.default_c))
                    square.obj.color = btn.default_c
                    self.change_square_color(obj, obj.color)
                    break
        
        self.load_more()
    
    def load_more(self, amount=None) -> None:
        gui = self.gui
        filelist = self.fileManager.imagelist

        if gui.current_view.get() == "Unassigned": pass
        else: return
        
        amount = amount if amount else gui.squares_per_page_intvar.get()
        items = min(len(filelist), amount) # Cap to remaining filelist length.

        if amount == 0: return
        if items == 0: return
        
        sublist = filelist[-items:]
        sublist.reverse()
        del filelist[-items:]

        generated = []
        for obj in sublist:
            if not obj.gridsquare:
                gridsquare = self.makegridsquare(gui.imagegrid, obj)
                generated.append(gridsquare)
            else:
                generated.append(obj.gridsquare)
        if self.gui.prediction.get():
            for x in generated:
                if x.obj.conf:
                    percentage = f"{x.obj.conf:.2f}"
                    x.canvas.itemconfig(x.text_id, state="normal")
                    x.canvas.itemconfig(x.rect_id, state="normal")
                    if x.obj.conf < 0.5:
                        # Red → Yellow transition
                        r = 255
                        g = int(510 * x.obj.conf)  # 0→255 as conf goes 0→0.5
                        b = 0
                    else:
                        # Yellow → Green transition
                        r = int(255 * (1 - x.obj.conf))  # 255→0 as conf goes 0.5→1
                        g = 255
                        b = 0
                    t_color = f"#{r:02x}{g:02x}{b:02x}"
                    x.canvas.itemconfig(x.text_id, text=percentage, fill=t_color)
                    if x.obj.pred != None:
                        x.canvas.itemconfig(x.text_id2, state="normal")
                        path = self.fileManager.names_2_path[x.obj.pred]
                        x.obj.predicted_path = path
                        color = self.gui.folder_explorer.color_cache.get(path, None)
                        if color:
                            x.canvas.itemconfig(x.text_id2, text=x.obj.pred, fill=color)
                        else: 
                            x.canvas.itemconfig(x.text_id2, text=x.obj.pred)

                        bbox2 = x.canvas.bbox(x.text_id2)
                        if bbox2 is not None:
                            x.canvas.coords(
                                x.rect_id2,
                                bbox2[0] - 4, bbox2[1] - 2,
                                bbox2[2] + 4, bbox2[3] + 2
                            )

                        if not color:
                            self.gui.folder_explorer.executor.submit(self.gui.folder_explorer.get_set_color, path, square=x)
                        
                        x.canvas.itemconfig(x.rect_id2, state="normal")
                    else:
                        print("hmm")

        self.unassigned.extend(generated)
        self.gridsquarelist.extend(generated)
        self.add_squares(generated)
        gui.images_left_stats_strvar.set(f"Left: {len(self.assigned)}/{len(self.gridsquarelist)-len(self.assigned)-len(self.moved)}/{len(filelist)}")
    
    def change_view(self, squares) -> None:
        "Remove all squares from grid, but add them back without unloading according how they should be ordered."
        self.fileManager.thumbs.flush_all()
        
        not_in_new_list = [x for x in self.displayedlist if x not in squares] # Unload their thumbs and frames.
        in_both_lists = [x for x in self.displayedlist if x in squares] # Remove them from gridview. But dont unload

        if not_in_new_list: # Normal remove
            self.remove_squares(not_in_new_list, unload=True)
        if in_both_lists: # Remove but without unloading from memory. We want to readd these.
            self.remove_squares(in_both_lists, unload=False)
        if squares: # Read all
            self.add_squares(squares) # This will know if thumb is loaded or not and will reload as needed.
 
    def add_squares(self, squares: list, insert=False) -> None:
        gui = self.gui
        if not squares: return
        objs = [square.obj for square in squares]
        loads = [obj for obj in objs if obj.thumb != None]
        gens = [obj for obj in objs if obj.thumb == None]
        if gui.current_view.get() in ("Assigned", "Moved"): 
            objs.reverse()
            order = "1.0"
        else: 
            order = "insert"
        
        if insert:
            order = insert[0]

        for sqr in squares:
            gui.imagegrid.window_create(
                order, window=sqr, padx=gui.gridsquare_padx, pady=gui.gridsquare_pady)
            sqr.obj.frame = sqr
        if insert:
            for x in squares:
                self.displayedlist.insert(insert[1], x)
        else:
            self.displayedlist.extend(squares)
        
        if gens:
            self.fileManager.thumbs.generate(gens, dest=False)
        elif loads:
            for obj in loads:
                obj.frame.canvas.itemconfig(obj.frame.canvas_image_id, image=obj.thumb)
    
    def remove_squares(self, squares: list, unload=True) -> None:
        if not squares: return
        for gridsquare in squares:
            if hasattr(gridsquare, "rect_id"):
                gridsquare.canvas.itemconfigure(gridsquare.text_id, state="hidden")
                gridsquare.canvas.itemconfigure(gridsquare.rect_id, state="hidden")
                gridsquare.canvas.itemconfig(gridsquare.text_id2, state="hidden")
                gridsquare.canvas.itemconfig(gridsquare.rect_id2, state="hidden")
                self.gui.imagegrid.window_configure(gridsquare, window="")
                self.displayedlist.remove(gridsquare)

            if unload:
                obj = gridsquare.obj
                gridsquare.canvas.itemconfig(gridsquare.canvas_image_id, image=None)
                obj.frame = None
                if not obj.destframe:
                    obj.thumb = None
                    if obj.frames:
                        self.fileManager.animate.remove_animation(obj)
                        obj.clear_frames()
                else:
                    pass
        for x in squares:
            if x.obj.thumb != None:
                print("hey")
                    
    def refresh_squares(self, squares):
        if not squares: return
        self.remove_squares(squares, unload=False)
        self.add_squares(squares)
    
    def move_to_assigned(self, marked):
        gui = self.gui
        if gui.current_view.get() == "Unassigned":
            handled_list = self.unassigned
        elif gui.current_view.get() == "Moved":
            handled_list = self.moved
        elif gui.current_view.get() == "Assigned":
            handled_list = self.assigned
        
        for x in marked:
            try:
                if gui.current_view.get() == "Unassigned":
                    index1 = self.unassigned.index(x)
                    index = self.gui.imagegrid.index(x)
                    self.undo.append((index, index1, x))
                handled_list.remove(x)
                self.assigned.append(x)
                
            except ValueError:
                pass
        try:
            if gui.current_view.get() == "Assigned":
                self.refresh_squares(marked)
            else:
                self.remove_squares(marked)
        except ValueError:
            pass

    def change_square_color(self, obj, color):
        frames = []
        if obj.frame: frames.append(obj.frame)
        if obj.destframe: frames.append(obj.destframe)

        for frame in frames:
            frame.configure(highlightcolor = color,  highlightbackground = color) # Trying to access destroyed destsquare? # If dest is closed, remove self.old if any frame was there.
            frame.canvas.configure(bg=color, highlightcolor=color, highlightbackground = color)
            frame.cf.configure(bg=color)

current_selection = 0
def scroll(parent, args):
    global current_selection
    def scroll_btn(direction):
        global current_selection
        btns = parent.master.master.master.color_change_buttons
        previous = btns[current_selection]
        current_selection += direction * -1
        if current_selection >= len(btns):
            current_selection = 0
        elif current_selection < 0:
            current_selection = len(btns)-1
        previous[1]["btn"].config(bg=previous[1]["color"], fg="white")
        current = btns[current_selection]
        def darken_color(color, factor=0.0):
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)

            r = int(r * factor)
            g = int(g * factor)
            b = int(b * factor)
            return f'#{r:02x}{g:02x}{b:02x}'   
        
        current[1]["btn"].config(bg=darken_color(current[1]["color"]), fg='cyan')
        parent.master.master.master.selected_btn = current
        
    command = args[0]
    val = args[1]

    if command == "moveto":
        moveto = float(val)
        parent.yview_moveto(moveto)
        #parent.update()

    elif command == "scroll":
        if args[-1] == "pages": return
        if args[-1] == "units": direction = -1 if int(val) > 0 else 1
        else: direction = int(args[-1].delta/120)
        if not isinstance(val, str) and val.state == 2:
            return
            scroll_btn(direction)
        else:
            parent.yview_scroll(-1*direction, "units")

    elif command == "scroll_s":
        direction = int(args[-1].delta/120)
        if args[1].state == 2: 
            parent.yview_scroll(40*direction, "pixels")
            return
        parent.yview_scroll(-1*direction, "units")
        parent.yview_scroll(40*direction, "pixels")
