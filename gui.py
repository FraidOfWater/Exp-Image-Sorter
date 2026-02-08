import os, tkinter as tk, tkinter.font as tkfont

from tkinter import ttk
from tkinter.ttk import Panedwindow

from folders import FolderExplorer
from imagegrid import ImageGrid
from resizing import Application

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
        self.d_theme = default
            
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
        if a not in ("Filename", "Date", "Type", "Size", "Dimensions"):
            a = "Filename"
        self.display_order = tk.StringVar(value=a)

        self.show_next = tk.BooleanVar(value=bool(gui.get("show_next", True)))
        self.dock_view = tk.BooleanVar(value=bool(gui.get("dock_view", True)))
        self.dock_side = tk.BooleanVar(value=bool(gui.get("dock_side", True)))
        self.theme = tk.StringVar(value=gui.get("theme", "Midnight"))
        self.d_theme = self.themes[self.theme.get()]
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
                "canvas": "#303276",
                "statusbar": "#202041",
                "button": "#24255C",
                "active_button": "#303276",
                "text": "#FFFFFF"
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
        entry.insert(0, path.name if type == "session" else path)
        entry.xview_moveto(1.0)
        if type == "dst" and hasattr(self, "folder_explorer") and self.folder_explorer:
            self.folder_explorer.set_view(path)
        elif type == "src":
            self.fileManager.validate("button")

    def initialize(self):
        self.smallfont = tkfont.Font(family='Helvetica', size=10)
        style = ttk.Style()
        style.configure('Theme_dividers.TPanedwindow', background=self.d_theme["pane_divider_colour"])
        style.configure("Theme_checkbox.TCheckbutton", background=self.d_theme["main_colour"], foreground=self.d_theme["button_text_colour"], highlightthickness = 0) # Theme for checkbox
        style.configure("Theme_square.TCheckbutton", background=self.d_theme["square_text_box_colour"], foreground=self.d_theme["button_text_colour"])
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
        #file_menu.add_command(label="Exclusions", command=self.excludeshow)        
        file_menu.add_separator()
        file_menu.add_command(label="Save Session", command=lambda: self.fileManager.savesession(True), accelerator="Ctrl+S")
        file_menu.add_command(label="Load Session", command=self.fileManager.loadsession, accelerator="Ctrl+L")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.closeprogram, accelerator="Ctrl+Q")
        
        # View
        self.prediction = tk.BooleanVar(value=False)
        
        order_menu.add_radiobutton(label="Filename",value="Filename", variable=self.display_order, command=self.fileManager.sort_imagelist)
        order_menu.add_radiobutton(label="Date", value="Date", variable=self.display_order, command=self.fileManager.sort_imagelist)
        order_menu.add_radiobutton(label="Type",value="Type", variable=self.display_order, command=self.fileManager.sort_imagelist)
        order_menu.add_radiobutton(label="Size", value="Size", variable=self.display_order, command=self.fileManager.sort_imagelist)
        order_menu.add_radiobutton(label="Dimensions", value="Dimensions", variable=self.display_order, command=self.fileManager.sort_imagelist)
        order_menu.add_radiobutton(label="Nearest", value="Nearest", variable=self.display_order, command=self.fileManager.sort_imagelist)
        order_menu.add_radiobutton(label="Confidence", value="Confidence", variable=self.display_order, command=self.fileManager.sort_imagelist)
        order_menu.entryconfig("Nearest", state="disabled")
        self.order_menu = order_menu
        order_menu.entryconfig("Confidence", state="disabled")
        order_menu.add_separator()
        def test():
            if self.prediction.get():
                order_menu.entryconfig("Confidence", state="active")
                imagefiles = [x for x in self.fileManager.imagelist if x.pred == None or self.last_model != self.model_path]
                imagefiles.extend([entry.file for entry in self.imagegrid.image_items if entry.file.pred == None or self.last_model != self.model_path])
                if imagefiles:
                    self.fileManager.predictions.model_infer(self.model_path, imagefiles)
                    self.display_order.set("Confidence")
            else:
                order_menu.entryconfig("Confidence", state="normal")
                order_menu.entryconfig("Confidence", state="disabled")
        order_menu.add_checkbutton(label="Group by Prediction", variable=self.prediction, command=test)

        def toggle_statusbar():
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

        view_menu.add_checkbutton(label="Statusbar", variable=self.show_statusbar, command=toggle_statusbar)

        view_menu.add_separator()
        
        def toggle_ram_label():
            if not self.show_ram.get():
                self.ram_label.pack_forget()
            else:
                self.ram_label.pack(side=tk.LEFT, fill="y")

        def toggle_advanced_label():
            if not self.show_advanced.get():
                self.animation_stats_label.pack_forget()
                self.resource_limiter.pack_forget()
                self.frame_gen_queue_label.pack_forget()
            else:
                self.animation_stats_label.pack(side="left", fill="y")
                self.resource_limiter.pack(side="left", fill="y")
                self.frame_gen_queue_label.pack(side="left", fill="y")

        view_menu.add_separator()
        view_menu.add_command(label="Settings")
                        
        # Category
        category_menu.add_command(label="Select model", command=self.fileManager.predictions.select_model)
        category_menu.add_separator()
        category_menu.add_command(label="Automatic", command=self.fileManager.predictions.automatic_training)
        category_menu.add_command(label="Manual", command=self.fileManager.predictions.open_category_manager)
    
        # Themes
        def hints():
            height = 250
            width = int(height * 2.1)
            new = tk.Toplevel(self, width=width, height=height, bg=self.d_theme["main_colour"]) 
            new.transient(self)
            new.geometry(f"{width}x{height}+{int(self.winfo_width()/2-width/2)}+{int(self.winfo_height()/2-height/2)}")
            new.grid_rowconfigure(0, weight=1)
            new.grid_columnconfigure(0, weight=1)
            text = """\
Select model:
    Use a previously trained model.

Automatic (Recursive):
    Train from current destinations. Marks each destination as a category,
    all images inside will belong to that category.

Manual (Recursive): 
    Train from user-defined destinations.
    A marked folder counts all folders inside it as the same category
    except for other marked folders inside it, which count as their own catgories.

Group by Prediction (Order):
    Will predict each image's destination and group them together. (Uses last model used/trained as default)
    You can sort by Confidence or Nearest. Nearest uses a lightweight model estimate "similarity". 
    If you have grouping on, all sort options will sort each group individually.
            """
            # Create a Label with wraplength
            label = tk.Label(
                new,
                text=text, fg=self.d_theme["field_text_colour"], bg=self.d_theme["main_colour"],
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

        leftui = tk.Frame(toppane, name="leftui", width=self.leftpane_width, bg=self.d_theme["main_colour"])
        middlepane_frame = tk.Frame(toppane, name="middlepane", bg=self.d_theme["viewer_bg"], width = self.middlepane_width)

        middle_label = tk.Label(middlepane_frame, bg=self.d_theme["viewer_bg"], fg="white", font=("Arial", 14), justify="center",
            text="Expand/Collapse folders using Right-click\nNavigate folders using Caps-lock + Scroll or Up/Down keys.\nNavigate images via Left/Right/Up/Down or via Caps-lock + Left/Right\n\nReassign hotkeys by pressing the mouse wheel.\nMove All to actually move files.\n\nDrag to pan, Scroll to zoom\nShift+Scroll to rotate\nRight-Click for options in viewer.\n\nLeft-Click to add to selection.\nRight-click to view.\nHotkeys in () to assign, or by Clicking the buttons.", 
        )

        # 3. Use relative positioning to center it
        middle_label.place(relx=0.5, rely=0.5, anchor="center")

        imagegrid = ImageGrid(toppane, parent=self.fileManager, thumb_size=self.thumbnailsize, center=False, bg=self.d_theme["grid_background_colour"], 
                                    theme=self.d_theme)
        self.destgrid = None
        leftui.grid_propagate(False)
        self.leftui = leftui

        leftui.bind("<Button-1>", lambda e: self.focus())
        middlepane_frame.bind("<Button-1>", lambda e: self.focus())

        toppane.add(leftui, weight=0)
        toppane.add(middlepane_frame, weight=0)
        self.first_page_buttons()

        imagegrid.grid(row=0, column=0, padx = max(0, self.d_theme["gridsquare_padx"]-1), pady=max(0, self.d_theme["gridsquare_pady"]-1), sticky="NSEW")
        imagegrid.rowconfigure(1, weight=0)
        imagegrid.rowconfigure(0, weight=1)
        imagegrid.columnconfigure(1, weight=0)
        imagegrid.columnconfigure(0, weight=1)
        toppane.add(imagegrid, weight=0)

        toppane.grid(row=0, column=0, sticky="NSEW")
        toppane.configure(style='Theme_dividers.TPanedwindow')

        self.toppane = toppane
        
        self.middlepane_frame = middlepane_frame
        self.imagegrid = imagegrid

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

        new_session_b = tk.Button(self.first_frame, text="New Session", command=self.fileManager.validate)
        self.new_session_b = new_session_b
        load_session_b = tk.Button(self.first_frame, text="Load Session", command=self.fileManager.loadsession)

        if self.squares_per_page_intvar.get() < 0: self.squares_per_page_intvar.set(1)
        
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
        self.order_menu.entryconfig("Nearest", state="normal")
        filemanager = self.fileManager

        arrowkeys = ["<Up>", "<Down>", "<Left>", "<Right>", "<Return>","<space>", "<F2>", "<Control-z>", "<Control-Z>"]
        for arrowkey in arrowkeys:
            self.bind_all(f"{arrowkey}", lambda e: filemanager.navigator.bindhandler(e))

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
        
        # Store current width if it's visible
        if m_frame.winfo_width() > 1:
            self.middlepane_width = m_frame.winfo_width()
        
        self.displayed_obj = None
        self.focused_on_secondwindow = False

        # 1. CLEANUP: Safely remove panes from PanedWindow if they exist
        current_panes = [str(p) for p in toppane.panes()]
        if str(m_frame) in current_panes:
            toppane.forget(m_frame)
        if str(imagegrid) in current_panes:
            toppane.forget(imagegrid)

        # 2. DOCK VIEW LOGIC
        if self.dock_view.get():
            # Re-add in specific order based on dock_side
            if self.dock_side.get(): # Middlepane on Left
                toppane.add(m_frame)
                toppane.add(imagegrid)
            else: # Middlepane on Right
                toppane.add(imagegrid)
                toppane.add(m_frame)
            
            # Close external window if it exists
            if self.second_window_viewer:
                self.second_window_viewer.window_close()
                self.second_window_viewer = None # Clear reference
                
            # Refresh image on the internal canvas
            index = self.imagegrid.current_selection
            self.displayimage(self.imagegrid.image_items[index].file)
            
            # Link search widget to dock canvas
            if self.Image_frame:
                self.fileManager.navigator.search_widget.new_canvas(self.Image_frame.canvas)

        # 3. SECOND WINDOW LOGIC
        else:
            try:
                # We already 'forgot' m_frame in step 1, so we just handle the viewer switch
                if self.Image_frame:
                    self.Image_frame.set_image(None)
                    self.Image_frame.save_json()
                
                # Ensure imagegrid is still visible in PanedWindow
                toppane.add(imagegrid)
                
                # Refresh image (this will trigger secondary window creation)
                index = self.imagegrid.current_selection
                self.displayimage(self.imagegrid.image_items[index].file)
                
                # Link search widget to external window canvas
                if self.second_window_viewer:
                    self.fileManager.navigator.search_widget.new_canvas(self.second_window_viewer.canvas)
                    
            except Exception as e:
                print(f"Error in change_viewer (Window Mode): {e}")

        # Final UI refresh to enforce widths
        toppane.update_idletasks()

    def change_dock_side(self):
        "Change which side you want the dock"
        m_frame = self.middlepane_frame
        toppane = self.toppane
        imagegrid = self.imagegrid

        if m_frame.winfo_width() == 1:
            return
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
    
    #
    def current_view_changed(self):
        "When view is changed, send the wanted list to the gridmanager for rendering"
        fileManager = self.fileManager

        if fileManager.first_run: return
        fileManager.thumbs.flush_all()
        
        selected_option = self.current_view.get()

        if selected_option == "Unassigned":
            if self.prediction.get():
                list_to_display = []
                for i in range(0, len(fileManager.all_objs)): # the last sort
                    obj = fileManager.all_objs[i]
                    if not obj.dest and not obj.moved:
                        list_to_display.append(obj)
                self.imagegrid.clear_canvas(unload=True)
                self.fileManager.imagelist = list_to_display
                fileManager.load_more()
                return
            else:
                list_to_display = []
                for i in range(0, len(fileManager.all_objs)):
                    obj = fileManager.all_objs[i]
                    if not obj.dest and not obj.moved:
                        list_to_display.append(obj)
                self.imagegrid.clear_canvas(unload=True)
                self.fileManager.imagelist = list_to_display
                fileManager.load_more()
                return

        elif selected_option == "Assigned":
            list_to_display = list(reversed(fileManager.assigned))
        elif selected_option == "Moved":
            list_to_display = [obj for obj in fileManager.all_objs if obj.moved]
        
        
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
        
        if hasattr(self.fileManager, "navigator"):
            navigator = self.fileManager.navigator
            base = self.thumbnailsize + theme["square_border_size"] + theme["whole_box_size"]
            navigator.actual_gridsquare_width = base + theme["gridsquare_padx"] + theme["whole_box_size"]
            navigator.actual_gridsquare_height = base + theme["gridsquare_pady"] + theme["checkbox_height"]
            navigator.style.configure("Theme_square1.TCheckbutton", background=theme["square_text_box_colour"], foreground=theme["square_text_colour"])
            navigator.style.configure("Theme_square2.TCheckbutton", background=theme["square_text_box_selection_colour"], foreground=theme["square_text_colour"])
        if hasattr(self, "folder_explorer"):
            self.folder_explorer.style.configure("Theme_dividers.TFrame", background=theme["main_colour"])
            self.folder_explorer.canvas.configure(bg=theme["main_colour"])
        if hasattr(self, "Image_frame") and self.Image_frame:
            self.Image_frame.canvas.config(bg=theme["viewer_bg"])
        if hasattr(self, "second_window_viewer") and self.second_window_viewer:
            self.second_window_viewer.canvas.config(bg=theme["viewer_bg"])
        set_vals(theme)
        
        #navigator.selected(navigator.old)
        self.update()

    "Viewer"
    def displayimage(self, obj):
        "Display image in viewer"
        self.displayed_obj = obj
        self.focused_on_secondwindow = True

        if self.dock_view.get(): # Dock
            flag = False
            if not self.Image_frame:
                flag = True
                self.Image_frame = Application(self.middlepane_frame, savedata=self.viewer_prefs, gui=self)
            self.Image_frame.set_image(None if obj == None else obj.path, obj=obj)
            if flag: self.fileManager.navigator.search_widget.new_canvas(self.Image_frame.canvas)
        else: # Window
            if not self.second_window_viewer:
                self.second_window_viewer = Application(savedata=self.viewer_prefs, gui=self)
            self.second_window_viewer.master.lift()
            self.second_window_viewer.set_image(None if obj == None else obj.path, obj=obj)

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
        
        from tkinter.messagebox import askokcancel
        if hasattr(self.fileManager, "all_objs") and [x for x in self.fileManager.all_objs if x.dest] and not askokcancel("Designated but Un-Moved files, really quit?", "You have destination designated, but unmoved files. (Simply cancel and Move All if you want)"):
            return
    
        self.fileManager.thumbs.stop_background_worker()

        for id in self.fileManager.animate.running.copy():
            self.fileManager.animate.stop(id)

        # dest close
        if self.second_window_viewer: self.second_window_viewer.window_close()
        if self.Image_frame: self.Image_frame.save_json()

        self.fileManager.saveprefs(self)
        purge_cache()
        move_temp_to_trash()
        
        self.destroy()
