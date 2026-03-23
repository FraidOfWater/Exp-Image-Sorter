import os, tkinter as tk
from tkinter import ttk
from tkinter.ttk import Panedwindow
class Bindhandler:
    def __init__(self, gui):
        "Binds that touch multiple modules"
        self.gui = gui
        self.fileManager = gui.fileManager
        self.window_focused = "GRID"
        from search_overlay import ImageViewer
        self.search_widget = ImageViewer(self)

    def arrow_key(self, event):
        if isinstance(event.widget, tk.Entry): return
        if self.search_widget.search_active: return
        if event.keysym in ("Up", "Down") and event.state != 262147 and self.gui.folder_explorer.scroll_enabled: # 262147 = capslock
            self.gui.folder_explorer.nav(event.keysym)
        else:
            if "toplevel" in event.widget._w and not (hasattr(self.gui.second_window_viewer, "master") and event.widget == self.gui.second_window_viewer.master):
                self.gui.folder_explorer.destw.navigate(event.keysym)
            else: self.gui.imagegrid.navigate(event.keysym)
            if self.gui.show_next.get():
                if "toplevel" in event.widget._w and not (hasattr(self.gui.second_window_viewer, "master") and event.widget == self.gui.second_window_viewer.master):
                    self.gui.displayimage(self.gui.folder_explorer.destw.current_selection_entry.file)
                else: self.gui.displayimage(self.gui.imagegrid.current_selection_entry.file)

    def undo(self, event):
        if isinstance(event.widget, tk.Entry): return
        if self.fileManager.assigned and self.gui.current_view.get() in ("Unassigned",) :
            last = self.fileManager.assigned.pop()
            self.gui.displayimage(last)
            self.gui.imagegrid.insert_first(last, last.pos) # should add to ALL grids.
            last.color, last.dest = None, ""

    def enter(self, event):
        if isinstance(event.widget, tk.Entry): return
        caps_lock = (event.state & 0x0002) != 0
        if caps_lock and not self.bindhandler.search_widget.search_active:
            fe = self.gui.folder_explorer
            destinat = fe.buttons[fe.selected_index][1]
            coloring = self.gui.folder_explorer.color_cache[destinat]
            self.fileManager.setDestination({"path": destinat, "color": coloring})
        elif self.gui.prediction.get() and not self.search_widget.search_active:
            imagegrid = self.gui.imagegrid
            s = imagegrid.current_selection_entry
            if s is not None:
                a = s.file.predicted_path
                if a:
                    print("Sent:", s.file.name[:20], "to", a)
                    c =  "#FFFFFF" #self.gui.folder_explorer.color_cache[self.old.obj.predicted_path]
                    dest = {"path": a, "color": c}
                    self.fileManager.setDestination(dest) # setdest pulls the image in viewer by default if nothing is marked.
                    self.gui.folder_explorer.set_current(dest["path"])

    def handle_canvas_menu(self, event):
        is_toplevel = "toplevel" in event.widget._w and "canvas" in event.widget._w
        is_middle = "middlepane" in event.widget._w and "canvas" in event.widget._w
        if not (is_toplevel or is_middle):return

        canvas = event.widget
        if "!canvas.!frame.!canvas.!frame" in event.widget._w: return # video cant draw over it
        canvas.delete("canvas_menu")

        x, y = event.x, event.y
        btn_w, btn_h = 150, 35  # Slightly wider to fit the checkmark

        BG_NORMAL = "#2b2b2b"
        BG_HOVER = "#4a4a4a"
        TEXT_COLOR = "white"
        ACCENT_COLOR = "#00ff00" # Green for the checkmark
        BORDER_COLOR = "#696969"

        def helper():
            self.gui.dock_view.set(not self.gui.dock_view.get())
            self.gui.change_viewer() # Execute your detach logic
        def helper2():
            self.gui.dock_side.set(not self.gui.dock_side.get())
            self.gui.change_dock_side() # Execute your detach logic
        def helper3():
            self.gui.show_next.set(not self.gui.show_next.get())
        def helper5():
            options = ["None", "Default", "Advanced", "Debug"]
            def get_next(old):
                old_index = options.index(old)
                if old_index+1 >= len(options): return options[0]
                else: return options[old_index+1]
            if self.gui.Image_frame.canvas == event.widget:
                old = self.gui.Image_frame.statusbar_mode.get()
                self.gui.Image_frame.statusbar_mode.set(get_next(old))
            elif self.gui.second_window_viewer:
                old = self.gui.second_window_viewer.statusbar_mode.get()
                self.gui.second_window_viewer.statusbar_mode.set(get_next(old))

        checkmark = "✓ " if self.gui.show_next.get() else "  "
        options = [("Detach" if is_middle else "Dock", helper)]

        if is_middle:
            options.append(("Switch Sides", helper2))
        options.append((f"Cycle statusbar", helper5))
        options.append((f"{checkmark}Show Next", helper3))

        for i, (label, cmd) in enumerate(options):
            btn_y = y + (i * btn_h)
            row_tag = f"row_{i}"
            bg_tag = f"bg_{i}"
            canvas.create_rectangle(x, btn_y, x + btn_w, btn_y + btn_h,fill=BG_NORMAL, outline=BORDER_COLOR,tags=("canvas_menu", row_tag, bg_tag))
            text_item = canvas.create_text(x + 10, btn_y + (btn_h / 2),text=label, fill=TEXT_COLOR,anchor="w",font=("Segoe UI", 10),tags=("canvas_menu", row_tag))
            if "✓" in label:canvas.itemconfig(text_item, fill=ACCENT_COLOR)

            def on_enter(e, bt=bg_tag):
                canvas.itemconfig(bt, fill=BG_HOVER)
                canvas.config(cursor="hand2")

            def on_leave(e, bt=bg_tag):
                canvas.itemconfig(bt, fill=BG_NORMAL)
                canvas.config(cursor="")

            canvas.tag_bind(row_tag, "<Enter>", on_enter)
            canvas.tag_bind(row_tag, "<Leave>", on_leave)
            canvas.tag_bind(row_tag, "<Button-1>", lambda e, c=cmd: [canvas.delete("canvas_menu"), c()])

class GUIManager(tk.Tk):
    Image_frame = None
    second_window_viewer = None
    focused_on_secondwindow = False
    last_model = None
    displayed_obj = None
    last_displayed = None
    def __init__(self, jprefs, jthemes) -> None:
        super().__init__()
        self.fileManager = None
        self.train_thread = None
        self.train_status_var = tk.StringVar(value="")
        self.model_path = None
        self.selected_btn = None
        self.first_render = True
        "INITIALIZE USING PREFS: THEME"
        self.jprefs = jprefs
        self.themes = jthemes
        default = self.themes.get("Midnight", {})
        self.d_theme = default

        "INITIALIZE USING PREFS: SETTINGS"
        "VALIDATION"
        expected_keys = ["paths", "user", "technical", "qui", "window_settings", "viewer"]
        missing_keys = [key for key in expected_keys if jprefs and key not in jprefs]
        if missing_keys: print(f"Missing a key(s) in prefs: {missing_keys}, defaults will be used.")
        if jprefs == None: jprefs = {}
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
        self.auto_load = bool(user.get("auto_load", True))
        self.do_debug = tk.BooleanVar(value=user.get("do_debug", False))

        tech = jprefs.get("technical", {})
        self.filter_mode = tech.get("quick_preview_filter") if tech.get("quick_preview_filter") in ["NEAREST", "BILINEAR", "BICUBIC", "LANCZOS"] else "BILINEAR"

        gui = jprefs.get("qui", {}) # should be spelled gui XD
        self.squares_per_page_intvar = tk.IntVar(value=int(gui.get("squares_per_page", 500)))
        a = gui.get("display_order")
        if a not in ("Smart", "Filename", "Date", "Type", "Size", "Dimensions", "Nearest", "Histogram"):
            a = "Smart"
        self.display_order = tk.StringVar(value=a)

        self.show_next = tk.BooleanVar(value=bool(gui.get("show_next", True)))
        self.dock_view = tk.BooleanVar(value=bool(gui.get("dock_view", True)))
        self.dock_side = tk.BooleanVar(value=bool(gui.get("dock_side", True)))
        self.theme = tk.StringVar(value=gui.get("theme", "Midnight"))
        self.d_theme = self.themes[self.theme.get()]
        self.volume = int(gui.get("volume", 50))

        w = jprefs.get("window_settings", {})
        self.main_geometry = w.get("main_geometry", "zoomed")
        self.viewer_geometry = w.get("viewer_geometry", f"{int(self.winfo_screenwidth()*0.5)}x{int(self.winfo_screenheight()*0.5)}+{-8+365}+60")
        self.destpane_geometry = w.get("destpane_geometry", f"{int(self.winfo_screenwidth()*0.5)}x{int(self.winfo_screenheight()-120)}+{-8+365}+60")
        self.leftpane_width = int(w.get("leftpane_width", 363))
        self.middlepane_width = int(w.get("middlepane_width", 363))
        self.images_sorted = int(w.get("images_sorted", 0))
        self.images_sorted_strvar = tk.StringVar(value=f"Sorted: {self.images_sorted}") # Sorted: 1953
        self.winfo_toplevel().title(f"")

        self.viewer_prefs = jprefs.get("viewer", {})
        self.viewer_prefs["colors"] = self.viewer_prefs.get("colors", None) or {
                "canvas": self.d_theme["viewer_bg"],
                "statusbar": self.d_theme["main_colour"],
                "statusbar_divider": self.d_theme.get("main_accent", self.d_theme["main_colour"]),
                "button": self.d_theme["button_colour"],
                "active_button": self.d_theme["button_colour_when_pressed"],
                "text": self.d_theme["field_text_colour"]
                }

        if self.main_geometry == "zoomed": self.state("zoomed")
        else: self.geometry(self.main_geometry)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.protocol("WM_DELETE_WINDOW", self.closeprogram)
        self.current_ram_strvar = tk.StringVar(value="RAM: 0 MB") # RAM: 95.34 MB
        self.animation_stats_var = tk.StringVar(value="Anim: 0/100") # Anim: displayedlist with frames/displayedlist with framecount/(queue)
        self.resource_limiter_var = tk.StringVar(value="0/1000") # Frames: frames + frames_dest / max
        self.frame_gen_queue_var = tk.StringVar(value="Q:")

    def filedialog(self, entry, event=None, type1=None):
        from tkinter import filedialog as tkFileDialog
        match type1:
            case "session": path = tkFileDialog.askopenfile(initialdir=os.getcwd(), title="Select Session Data File", filetypes=(("JavaScript Object Notation", "*.json"),))
            case "src": path = tkFileDialog.askdirectory(initialdir=self.source_entry_field.get(), title="Select Source folder")
            case "dst": path = tkFileDialog.askdirectory(initialdir=self.destination_entry_field.get(), title="Select Destination folder")
        if path == "" or path == None: return
        entry.delete(0, tk.END)
        entry.insert(0, path.name if type1 == "session" else path)
        entry.xview_moveto(1.0)
        if type1 == "dst" and hasattr(self, "folder_explorer") and self.folder_explorer:
            self.folder_explorer.set_view(path)
            self.fileManager.validate("button")
        elif type1 == "src": self.fileManager.validate("button")

    def initialize(self):
        self.bindhandler = Bindhandler(self)
        style = ttk.Style()
        style.configure('Theme_dividers.TPanedwindow', background=self.d_theme["pane_divider_colour"])
        style.configure("Theme_checkbox.TCheckbutton", background=self.d_theme["main_colour"], foreground=self.d_theme["button_text_colour"], highlightthickness = 0) # Theme for checkbox
        style.configure("Theme_square.TCheckbutton", background=self.d_theme["square_text_box_colour"], foreground=self.d_theme["button_text_colour"])
        self.style = style

        statusbar_bg = "#202041"
        txt_color = "#FFFFFF"

        statusbar = tk.Frame(self, bd=1, relief=tk.SUNKEN, bg=statusbar_bg)

        if self.do_debug.get(): statusbar.grid(row=1, column=0, sticky="ew")
        self.statusbar = statusbar

        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_columnconfigure(0, weight=1)

        self.sorted_label = tk.Label(statusbar, textvariable=self.images_sorted_strvar, bg=statusbar_bg, fg=txt_color, anchor="e", padx=5)
        self.animation_stats_label = tk.Label(statusbar, textvariable=self.animation_stats_var, bg=statusbar_bg, fg=txt_color, anchor="e", padx=5)
        self.resource_limiter = tk.Label(statusbar, textvariable=self.resource_limiter_var, bg=statusbar_bg, fg=txt_color, anchor="e", padx=5)
        self.frame_gen_queue_label = tk.Label(statusbar, textvariable=self.frame_gen_queue_var, bg=statusbar_bg, fg=txt_color, anchor="e", padx=5)
        self.ram_label = tk.Label(statusbar, textvariable=self.current_ram_strvar, bg=statusbar_bg, fg=txt_color, anchor="e", padx=5)
        self.train_status = tk.Label(statusbar, textvariable=self.train_status_var, bg=statusbar_bg , fg=txt_color, anchor="w", padx=10)

        self.sorted_label.pack(side="left", fill="y")
        self.train_status.pack(side="right", fill="y")
        if self.do_debug.get():
            self.animation_stats_label.pack(side="left", fill="y")
            self.resource_limiter.pack(side="left", fill="y")
            self.frame_gen_queue_label.pack(side="left", fill="y")
            self.ram_label.pack(side="left", fill="y")

        # Menus
        menu_bar = tk.Menu(self.master)
        file_menu = tk.Menu(menu_bar, tearoff=tk.OFF)
        view_menu = tk.Menu(menu_bar, tearoff=tk.OFF)
        order_menu = tk.Menu(menu_bar, tearoff=tk.OFF)
        category_menu = tk.Menu(menu_bar, tearoff=tk.OFF)
        theme_menu = tk.Menu(menu_bar, tearoff=tk.OFF)

        menu_bar.add_cascade(label="Order", menu=order_menu)
        menu_bar.add_cascade(label="Themes", menu=theme_menu)
        menu_bar.add_cascade(label="Training", menu=category_menu)
        # File
        file_menu.add_command(label="Source Folder", command=lambda: self.filedialog(self.source_entry_field, type="src"), accelerator="Ctrl+S")
        file_menu.add_command(label="Destination Folder", command=lambda: self.filedialog(self.destination_entry_field, type="dst"), accelerator="Ctrl+D")
        file_menu.add_command(label="Select Session", command=lambda: self.filedialog(self.session_entry_field, type="session"))
        file_menu.add_separator()
        #file_menu.add_command(label="Exclusions", command=self.excludeshow)
        file_menu.add_separator()
        file_menu.add_command(label="Save Session", command=lambda: self.fileManager.savesession(True), accelerator="Ctrl+S")
        file_menu.add_command(label="Load Session", command=self.fileManager.loadsession, accelerator="Ctrl+L")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.closeprogram, accelerator="Ctrl+Q")

        # View
        self.prediction = tk.BooleanVar(value=False)

        order_menu.add_radiobutton(label="Filename++", value="Smart", variable=self.display_order, command=self.fileManager.sort_imagelist)
        order_menu.add_radiobutton(label="Filename",value="Filename", variable=self.display_order, command=self.fileManager.sort_imagelist)
        order_menu.add_radiobutton(label="Date", value="Date", variable=self.display_order, command=self.fileManager.sort_imagelist)
        order_menu.add_radiobutton(label="Type",value="Type", variable=self.display_order, command=self.fileManager.sort_imagelist)
        order_menu.add_radiobutton(label="Size", value="Size", variable=self.display_order, command=self.fileManager.sort_imagelist)
        order_menu.add_radiobutton(label="Dimensions", value="Dimensions", variable=self.display_order, command=self.fileManager.sort_imagelist)
        order_menu.add_radiobutton(label="Histogram", value="Histogram", variable=self.display_order, command=self.fileManager.sort_imagelist)
        order_menu.add_radiobutton(label="Nearest", value="Nearest", variable=self.display_order, command=self.fileManager.sort_imagelist)
        order_menu.add_radiobutton(label="Confidence", value="Confidence", variable=self.display_order, command=self.fileManager.sort_imagelist)

        self.order_menu = order_menu
        order_menu.entryconfig("Confidence", state="disabled")
        order_menu.add_separator()
        def test():
            if self.prediction.get():
                order_menu.entryconfig("Confidence", state="active")
                imagefiles = [x for x in self.fileManager.imagelist if x.pred == None or self.last_model != self.model_path]
                imagefiles.extend([entry.file for entry in self.imagegrid.image_items if entry.file.pred == None or self.last_model != self.model_path])
                if imagefiles:
                    load_module()
                    self.predictions.model_infer(self.model_path, imagefiles)
                    self.display_order.set("Confidence")
            else:
                order_menu.entryconfig("Confidence", state="normal")
                order_menu.entryconfig("Confidence", state="disabled")
        order_menu.add_checkbutton(label="Group by Prediction", variable=self.prediction, command=test)

        def toggle_statusbar():
            if not self.do_debug.get():
                self.statusbar.grid_forget()
                if self.Image_frame:
                    self.Image_frame.mouse_double_click_left()
            else:
                self.statusbar.grid(row=1, column=0, sticky="ew")
                if self.Image_frame:
                    self.Image_frame.mouse_double_click_left()

        view_menu.add_checkbutton(label="Statusbar", variable=self.do_debug, command=toggle_statusbar)
        view_menu.add_separator()
        view_menu.add_separator()
        view_menu.add_command(label="Settings")

        # Category
        def load_module():
            "This module is extremely heavy, adding 5-6 seconds of load time alone. We don't load it until we need it."
            if not hasattr(self, "predictions"):
                from Advanced_sorting import Predictions
                self.predictions = Predictions(self)
        def select_model():
            from tkinter import filedialog as tkFileDialog
            self.model_path = tkFileDialog.askopenfilename(defaultextension=".pt", filetypes=(("Model File", "*.pt"),),initialdir=self.fileManager.model_dir, title="Select a trained model to use.")
            if hasattr(self.fileManager, "all_objs"):
                self.prediction.set(True)
                test()
        category_menu.add_command(label="Select model", command=select_model)
        category_menu.add_separator()
        category_menu.add_command(label="Automatic", command=lambda: (load_module(), self.predictions.automatic_training()))
        category_menu.add_command(label="Manual", command=lambda: (load_module(), self.predictions.open_category_manager()))

        # Themes
        def hints():
            height = 250
            width = int(height * 2.1)
            new = tk.Toplevel(self, width=width, height=height, bg=self.d_theme["main_colour"])
            new.transient(self)
            new.geometry(f"{width}x{height}+{int(self.winfo_width()/2-width/2)}+{int(self.winfo_height()/2-height/2)}")
            new.grid_rowconfigure(0, weight=1)
            new.grid_columnconfigure(0, weight=1)
            text = """Select model:\n    Use a previously trained model.\n\nAutomatic (Recursive):\n    Train from current destinations. Marks each destination as a category,\n    all images inside will belong to that category.\n\nManual (Recursive): \n    Train from user-defined destinations.\n    A marked folder counts all folders inside it as the same category\n    except for other marked folders inside it, which count as their own catgories.\n\nGroup by Prediction (Order):\n    Will predict each image's destination and group them together. (Uses last model used/trained as default)\n    You can sort by Confidence or Nearest. Nearest uses a lightweight model estimate "similarity". \n    If you have grouping on, all sort options will sort each group individually.\n"""
            label = tk.Label(new,text=text, fg=self.d_theme["field_text_colour"], bg=self.d_theme["main_colour"],justify='left',anchor='nw', wraplength=height)
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
        leftui = tk.Frame(toppane, name="leftui", width=self.leftpane_width, bg=self.d_theme["main_colour"])
        middlepane_frame = tk.Frame(toppane, name="middlepane", bg=self.d_theme["viewer_bg"], width = self.middlepane_width)

        font_style = ("Consolas", 11)
        help_text = ("--- NAVIGATION & SELECTION -----\n"f"{'Left-Click, Hotkey':<22} Mark\n"f"{'Arrows':<22} Navigate Images\n\n""--- FOLDERS & ASSIGNING --------------\n"f"{'Left-Click, Hotkey':<22} Assign to Folder\n"f"{'Right-Click':<22} Expand / Collapse\n"f"{'Shift + L-Click':<22} View Assigned\n"f"{'Shift + R-Click':<22} Open in Explorer\n"f"{'Mid-Click + Key':<22} Reassign Hotkey\n"f"{'Caps + Scroll':<22} Navigate Destinations\n\n""--- VIEWER CONTROLS ------\n"f"{'L-Click (Drag)':<22} Pan\n"f"{'Scroll':<22} Zoom\n"f"{'Shift + Scroll':<22} Rotate\n"f"{'R-Click':<22} Open Options\n\n""--- FINAL ACTIONS -------------------\n"f"{'Move All':<22} Transfer Files.\n\n""--- OTHER --------------------------------------------------\n""The grey dividers can be Moved. Each Section can be Resized.\n""Current highlighted item will be Assigned if nothing else is Marked.")

        canvas = tk.Canvas(middlepane_frame, bg=self.d_theme["viewer_bg"],highlightthickness=0,width=self.middlepane_width,height=600)
        canvas.place(relx=0.5, rely=0.5, anchor="center")

        ascii_art = """"""
        canvas.create_text(self.middlepane_width//2+100, 300,text=ascii_art,fill="grey",font=("Consolas", 4),justify="center")
        canvas.create_text(self.middlepane_width//2, 300,text=help_text,fill="white",font=font_style,justify="left")

        self.middle_label = canvas
        self.destgrid = None
        leftui.grid_propagate(False)
        self.leftui = leftui
        leftui.bind("<Button-1>", lambda e: self.focus())
        middlepane_frame.bind("<Button-1>", lambda e: self.focus())
        toppane.add(leftui, weight=0)
        toppane.add(middlepane_frame, weight=0)
        self.first_page_buttons()

        from imagegrid import ImageGrid
        imagegrid = ImageGrid(toppane, gui=self, thumb_size=self.thumbnailsize, center=False, bg=self.d_theme["grid_background_colour"], theme=self.d_theme)
        imagegrid.grid(row=0, column=0, padx = max(0, self.d_theme["gridsquare_padx"]-1), pady=max(0, self.d_theme["gridsquare_pady"]-1), sticky="NSEW")
        imagegrid.rowconfigure(1, weight=0)
        imagegrid.rowconfigure(0, weight=1)
        imagegrid.columnconfigure(1, weight=0)
        imagegrid.columnconfigure(0, weight=1)
        toppane.add(imagegrid, weight=0)
        self.imagegrid = imagegrid
        toppane.grid(row=0, column=0, sticky="NSEW")
        toppane.configure(style='Theme_dividers.TPanedwindow')
        self.toppane = toppane
        self.middlepane_frame = middlepane_frame

        self.change_theme(self.theme.get())

    def first_page_buttons(self):
        self.first_frame = tk.Frame(self.leftui)

        self.source_entry_field = tk.Entry(self.first_frame, text="")
        self.destination_entry_field = tk.Entry(self.first_frame, text="")
        self.session_entry_field = tk.Entry(self.first_frame)

        s_b = tk.Button(self.first_frame, text="Source", command=lambda: self.filedialog(self.source_entry_field, type="src"))
        d_b = tk.Button(self.first_frame, text="Destination", command=lambda: self.filedialog(self.destination_entry_field, type="dst"))
        self.ses_b = tk.Button(self.first_frame, text="Session", command=lambda: self.filedialog(self.session_entry_field, type="session"))

        self.source_entry_field.insert(0, self.source_folder or "Right click to Select Source Folder")
        self.source_entry_field.xview_moveto(1.0)
        self.destination_entry_field.insert(0, self.destination_folder or "Right click to Select Destination Folder")
        self.destination_entry_field.xview_moveto(1.0)
        self.session_entry_field.insert(0, self.lastsession or "No last Session")
        self.session_entry_field.xview_moveto(1.0)

        new_session_b = tk.Button(self.first_frame, text="New Session", command=lambda: self.after_idle(self.fileManager.validate))
        self.new_session_b = new_session_b
        load_session_b = tk.Button(self.first_frame, text="Load Session", command=lambda: self.after_idle(self.fileManager.loadsession))

        self.first_frame.columnconfigure(0, weight=0)
        self.first_frame.columnconfigure(1, weight=1)
        s_b.grid(row=0, column=0, sticky="ew", padx=2)
        self.source_entry_field.grid(row=0, column=1, sticky="ew", padx=2)
        new_session_b.grid(row=1, column=2, sticky="ew", padx=2)

        d_b.grid(row=1, column=0, sticky="ew", padx=2)
        self.destination_entry_field.grid(row=1, column=1, sticky="ew", padx=2)

        self.ses_b.grid(row=2, column=0, sticky="ew", padx=2)
        self.session_entry_field.grid(row=2, column=1, sticky='ew', padx=2)
        load_session_b.grid(row=2, column=2, sticky="ew", padx=2)

        self.leftui.columnconfigure(0, weight=1)
        self.first_frame.grid(row=0, column=0, sticky="ew")
        self.first_page = [new_session_b, load_session_b]

        self.load_session_b = load_session_b

        for x, t in [(self.source_entry_field, "src"), (self.destination_entry_field, "dst"), (self.session_entry_field, "session")]:
            x.bind("<Button-3>", lambda e, x=x, t=t: self.filedialog(x, type=t))

    def guisetup(self):
        x = self.bindhandler

        action_map = {"<Up>": x.arrow_key, "<Down>": x.arrow_key, "<Left>": x.arrow_key, "<Right>": x.arrow_key, "<Return>": x.enter, "<Control-z>": x.undo, "<Control-Z>": x.undo}
        for name, func in action_map.items():
            self.bind_all(f"{name}", func)

        self.load_session_b.grid_forget()
        self.session_entry_field.grid_forget()
        self.ses_b.grid_forget()

        frame = tk.Frame(self.first_frame)

        def clear():
            for x in self.imagegrid.selected.copy():
                self.imagegrid.unmark_entry(x)
            if hasattr(self.folder_explorer, "dest"):
                for x in  self.folder_explorer.destw.selected.copy():
                    self.folder_explorer.destw.unmark_entry(x)

        clear_all_b = tk.Button(frame, text="Unselect", command=clear)

        move_all_b = tk.Button(self.first_frame, text="Move All", command=self.fileManager.moveall)

        view_options = ["Unassigned", "Assigned", "Moved"]
        self.current_view = tk.StringVar(value="Unassigned")
        self.current_view.trace_add("write", lambda *args: self.current_view_changed())

        view_menu = tk.OptionMenu(frame, self.current_view, *view_options)
        view_menu.config(highlightthickness=0)

        from destinations import FolderExplorer
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

        self.change_theme(self.theme.get())

    "Navigation / options"
    def change_viewer(self):
        """Change which viewer is in use. Dock or secondary window"""
        m_frame = self.middlepane_frame
        toppane = self.toppane
        imagegrid = self.imagegrid
        if m_frame.winfo_width() > 1: self.middlepane_width = m_frame.winfo_width()
        self.displayed_obj = None
        self.focused_on_secondwindow = False
        current_panes = [str(p) for p in toppane.panes()]
        if str(m_frame) in current_panes: toppane.forget(m_frame)
        if str(imagegrid) in current_panes: toppane.forget(imagegrid)
        if self.dock_view.get():
            if self.dock_side.get(): # Middlepane on Left
                toppane.add(m_frame)
                toppane.add(imagegrid)
            else: # Middlepane on Right
                toppane.add(imagegrid)
                toppane.add(m_frame)
            if self.second_window_viewer:
                self.second_window_viewer.window_close()
                self.second_window_viewer = None
            if self.imagegrid.current_selection_entry:
                self.Image_frame.canvas.update()
                self.bindhandler.search_widget.new_canvas(self.Image_frame.canvas)
                self.displayimage(self.imagegrid.current_selection_entry.file)
            if self.Image_frame:
                self.bindhandler.search_widget.new_canvas(self.Image_frame.canvas)
            self.bind("<Control-s>", lambda e: self.Image_frame.statusbar.set(not self.Image_frame.statusbar.get()))
            self.bind("<Control-S>", lambda e: self.Image_frame.statusbar.set(not self.Image_frame.statusbar.get()))
        else:
            original = self.title().split(" -", 1)[0]
            self.title(original)
            try:
                if self.Image_frame:
                    self.Image_frame.set_image(None)
                    self.Image_frame.save_json()
                toppane.add(imagegrid)
                if self.imagegrid.current_selection_entry: self.displayimage(self.imagegrid.current_selection_entry.file)
                if self.second_window_viewer: self.bindhandler.search_widget.new_canvas(self.second_window_viewer.canvas)
                def safe_call(event=None):
                    if self.second_window_viewer and hasattr(self.second_window_viewer, "statusbar"):
                        self.second_window_viewer.statusbar.set(not self.second_window_viewer.statusbar.get())
                self.bind("<Control-s>", safe_call)
                self.bind("<Control-S>", safe_call)
            except Exception as e: print(f"Error in change_viewer (Window Mode): {e}")
        toppane.update_idletasks()

    def change_dock_side(self):
        "Change which side you want the dock"
        m_frame = self.middlepane_frame
        toppane = self.toppane
        imagegrid = self.imagegrid
        if m_frame.winfo_width() == 1: return
        self.middlepane_width = m_frame.winfo_width()
        m_frame.configure(width = self.middlepane_width)
        if self.dock_view.get():
            toppane.forget(m_frame)
            toppane.forget(imagegrid)
            if self.dock_side.get():
                toppane.add(m_frame, weight = 0)
                toppane.add(imagegrid, weight = 1)
            else:
                toppane.add(imagegrid, weight = 1)
                toppane.add(m_frame, weight = 0)

    def current_view_changed(self):
        "When view is changed, send the wanted list to the gridmanager for rendering"
        fileManager = self.fileManager
        if fileManager.first_run: return
        fileManager.thumbs.stop_background_worker()
        selected_option = self.current_view.get()
        if selected_option == "Unassigned":
            list_to_display = []
            for i in range(0, len(fileManager.all_objs)):
                obj = fileManager.all_objs[i]
                if not obj.dest and not obj.moved:
                    list_to_display.append(obj)
            self.imagegrid.clear_canvas(unload=True)
            self.fileManager.imagelist = list_to_display
            fileManager.load_more()
            return
        elif selected_option == "Assigned": list_to_display = list(reversed(fileManager.assigned))
        elif selected_option == "Moved": list_to_display = [obj for obj in fileManager.all_objs if obj.moved]
        self.imagegrid.clear_canvas(unload=True)
        self.imagegrid.theme = self.d_theme
        self.imagegrid.add(list_to_display)

    def change_theme(self, theme_name):
        def set_vals(theme):
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

            "Checkboxes"
            self.style.configure("Theme_checkbox.TCheckbutton", background=theme["main_colour"], foreground=theme["button_text_colour"]) # Theme for checkbox
            for x in all_children["frame"]:
                if x.winfo_exists() and x.widgetName != "ttk::frame":
                    x.config(bg=theme["main_colour"])

            "Frames"
            self.style.configure("Theme_square.TCheckbutton", background=theme["square_text_box_colour"], foreground=theme["button_text_colour"]) # Gridsquare name and checkbox
            for x in all_children["frame"]:
                if x.winfo_exists() and x.widgetName != "ttk::frame":
                    x.configure(bg=theme["grid_background_colour"])

            "Buttons"
            self.style.configure("Theme_square.TCheckbutton", background=theme["square_text_box_colour"], foreground=theme["button_text_colour"]) # Gridsquare name and checkbox
            but_c_bg = theme["button_colour"]
            but_c_fg = theme["button_text_colour"]
            but_c_a_bg = theme["button_colour_when_pressed"]
            but_c_a_fg = theme["button_text_colour_when_pressed"]

            for x in all_children["button"]:
                if "!folderexplorer" in x._w or not x.winfo_exists(): continue
                x.configure(bg=but_c_bg, fg=but_c_fg, activebackground=but_c_a_bg, activeforeground=but_c_a_fg)
                x.bind("<Enter>", lambda e, x=x: x.config(bg=but_c_a_bg, fg=but_c_a_fg))
                x.bind("<Leave>", lambda e, x=x: x.config(bg=but_c_bg, fg=but_c_fg))

            "Optionmenus"
            for x in all_children.get("optionmenu", []):
                if x.winfo_exists():
                    x.config(bg=theme["button_colour"], fg=theme["button_text_colour"],
                        activebackground = theme["button_colour_when_pressed"], activeforeground=theme["button_text_colour_when_pressed"])
            "Entryfields"
            f_a_bg = theme["field_activated_colour"]
            f_a_fg = theme["field_text_activated_colour"]
            field_c = theme["field_colour"]
            field_t_c = theme["field_text_colour"]
            for x in all_children["entry"]:
                if x.winfo_exists():
                    x.config(bg=theme["field_colour"], fg=theme["field_text_colour"])
                    x.bind("<FocusIn>", lambda e, x=x: x.config(bg=f_a_bg, fg=f_a_fg))
                    x.bind("<FocusOut>", lambda e, x=x: x.config(bg=field_c, fg=field_t_c))

        theme = self.themes[theme_name]
        self.d_theme = theme

        self.config(bg=theme["main_colour"])
        self.style.configure('Theme_dividers.TPanedwindow', background=theme["pane_divider_colour"])

        self.leftui.configure(bg=theme["main_colour"])

        self.middlepane_frame.configure(bg=theme["viewer_bg"])
        if self.Image_frame != None:
            self.Image_frame.style.configure("bg.TFrame", background=theme["viewer_bg"])
            self.Image_frame.canvas.config(bg=theme["viewer_bg"])

        self.imagegrid.configure(bg=theme["grid_background_colour"])
        self.imagegrid.change_theme(theme=self.d_theme)

        if hasattr(self, "folder_explorer") and hasattr(self.folder_explorer, "destw") and self.folder_explorer.destw != None and self.folder_explorer.destw.winfo_exists():
            self.folder_explorer.destw.configure(bg=theme["grid_background_colour"])
            self.folder_explorer.destw.change_theme(theme=self.d_theme)

        if hasattr(self, "folder_explorer"):
            self.folder_explorer.style.configure("Theme_dividers.TFrame", background=theme["main_colour"])
            self.folder_explorer.canvas.configure(bg=theme["main_colour"])
        if hasattr(self, "Image_frame") and self.Image_frame: self.Image_frame.canvas.config(bg=theme["viewer_bg"])
        if hasattr(self, "second_window_viewer") and self.second_window_viewer: self.second_window_viewer.canvas.config(bg=theme["viewer_bg"])
        set_vals(theme)

        self.update()

    "Viewer"
    def displayimage(self, obj):
        "Display image in viewer"
        if self.middle_label != None:
            self.middle_label.destroy()
            self.middle_label = None
        self.displayed_obj = obj
        self.focused_on_secondwindow = True
        from viewer import Application
        f = False
        adjacent = []
        n = 1  # How many steps outward you want to go
        current = self.imagegrid.current_selection
        items = self.imagegrid.image_items

        for i in range(1, n + 1):
            if current + i < len(items):
                adjacent.append(items[current + i].file.path)
            if current - i >= 0:
                adjacent.append(items[current - i].file.path)

        if self.imagegrid.cols > n and 0 <= current-self.imagegrid.cols < len(items):
            adjacent.insert(1, items[current-self.imagegrid.cols].file.path)
        if self.imagegrid.cols > n and 0 <= current+self.imagegrid.cols < len(items):
            adjacent.insert(1, items[current+self.imagegrid.cols].file.path)

        if self.dock_view.get(): # Dock
            flag = False
            if not self.Image_frame:
                self.first_render = True
                flag = True
                self.Image_frame = Application(self.middlepane_frame, savedata=self.viewer_prefs, gui=self)
            else:
                f = True
            self.Image_frame.set_image(None if obj == None else obj.path, obj=obj, adjacent=adjacent, first_run=flag)

        else: # Window
            if not self.second_window_viewer:
                self.first_render = True
                self.second_window_viewer = Application(savedata=self.viewer_prefs, gui=self)
            else:
                f = True
            self.second_window_viewer.master.lift()
            self.second_window_viewer.set_image(None if obj == None else obj.path, obj=obj, adjacent=adjacent)
        if self.first_render and f:
            self.first_render = False
            self.bindhandler.search_widget.canvas.delete("msg")

    "Exit function"
    def closeprogram(self):
        "This should clear cache of imgs that are not in gridsquarelist"
        "Stop animations and threads."
        "Save preferences, close windows, move temp to trash and exit the application."
        def purge_cache():
            data_dir = self.fileManager.data_dir
            if os.path.isdir(data_dir):
                with os.scandir(data_dir) as files:
                    ids = {entry.file.id for entry in self.imagegrid.image_items}
                    for file in files:
                        id = file.name.rsplit(".", 1)[0]
                        if id in ids: continue
                        try: os.remove(file.path)
                        except Exception as e: print("Failed to remove old cached thumbnails from the data directory.", e)
        def move_temp_to_trash():
            trash_dir = self.fileManager.trash_dir
            if not os.path.isdir(trash_dir): return
            from send2trash import send2trash
            with os.scandir(trash_dir) as files:
                for file in files:
                    try:
                        send2trash(file.path)
                    except Exception as e:
                        print("Trashing error", e)

        if self.fileManager.autosave and self.fileManager.assigned and self.fileManager.assigned != self.fileManager.last_assigned_list_for_autosave:
            try:
                self.fileManager.last_assigned_list_for_autosave = self.fileManager.assigned.copy()
                self.fileManager.savesession(asksavelocation=False)
            except Exception as e:
                print(("Failed to save session:", e))

        self.fileManager._autosave
        from tkinter.messagebox import askokcancel
        if hasattr(self.fileManager, "all_objs") and [x for x in self.fileManager.all_objs if x.dest] and not askokcancel("Designated but Un-Moved files, really quit?", "You have destination designated, but unmoved files. (Simply cancel and Move All if you want)"):
            return

        self.fileManager.thumbs.stop_background_worker()

        for id in self.fileManager.animate.running.copy():
            self.fileManager.animate.stop(id)

        if hasattr(self.fileManager, "all_objs"):
            image_references = [obj for obj in self.fileManager.all_objs if obj.thumb]
            for obj in image_references:
                obj.thumb = None

        # dest close
        if self.second_window_viewer: self.second_window_viewer.window_close()
        if self.Image_frame: self.Image_frame.save_json()

        self.fileManager.saveprefs(self)
        self.destroy()
        purge_cache()
        move_temp_to_trash()
