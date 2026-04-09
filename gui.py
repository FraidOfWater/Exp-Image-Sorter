import os, tkinter as tk
from tkinter import ttk
from tkinter.ttk import Panedwindow

class Bindhandler:
    def __init__(self, gui):
        "Binds that touch multiple modules"
        self.gui = gui
        self.fileManager = gui.fileManager
        self.window_focused = "GRID"
        from search_overlay import SearchOverlay
        self.search_widget = SearchOverlay(self)
        self.stop_loop = False

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

    def undo(self, event=None):
        if event and isinstance(event.widget, tk.Entry): return
        if self.fileManager.assigned and self.gui.current_view.get() in ("Unassigned",) :
            last = self.fileManager.assigned.pop(0)
            self.gui.displayimage(last)
            self.gui.imagegrid.insert_first([last], last.pos) # should add to ALL grids.
            last.color, last.dest = None, ""

    def enter(self, event):
        if isinstance(event.widget, tk.Entry): return
        caps_lock = (event.state & 0x0002) != 0
        if caps_lock and not self.search_widget.search_active:
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
            if isinstance(event.widget.winfo_toplevel(), tk.Toplevel):
                old = self.gui.second_window_viewer.statusbar_mode.get()
                self.gui.second_window_viewer.statusbar_mode.set(get_next(old))
            else:
                old = self.gui.Image_frame.statusbar_mode.get()
                self.gui.Image_frame.statusbar_mode.set(get_next(old))
        def helper6():
            frame = self.gui.Image_frame if self.gui.dock_view.get() else self.gui.second_window_viewer
            if frame:
                frame.show_ram.set(not frame.show_ram.get())

        def helper7():
            frame = self.gui.Image_frame if self.gui.dock_view.get() else self.gui.second_window_viewer
            frame.menu_reveal_in_file_explorer_clicked()

        checkmark = "✓ " if self.gui.show_next.get() else ""
        frame = self.gui.Image_frame if self.gui.dock_view.get() else self.gui.second_window_viewer
        if not frame: return
        checkmark_show_ram = "✓ " if frame.show_ram.get() else ""
        options = [("Detach" if is_middle else "Dock", helper)]

        if is_middle:
            options.append(("Switch Sides", helper2))
        options.append((f"{checkmark}Show Next", helper3))
        options.append((f"Cycle statusbar", helper5))
        options.append((f"{checkmark_show_ram}Show RAM", helper6))
        options.append((f"Open in Explorer", helper7))
        

        y += 10
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

            def on_delete(e, bt=bg_tag, c=cmd):
                canvas.config(cursor="")
                canvas.delete("canvas_menu")
                c()

            canvas.tag_bind(row_tag, "<Enter>", on_enter)
            canvas.tag_bind(row_tag, "<Leave>", on_leave)
            canvas.tag_bind(row_tag, "<Button-1>", on_delete)

    def ps4controller_loop(self):
        from time import perf_counter
        
        self.r3_timer = perf_counter()
        def loop():
            os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
            import pygame
            pygame.init()

            # Initialize the first controller found
            
            ignore_first = True
            ignore_first_r = True
            initialized = False
            explorer = None
            imagegrid = None
            side = "L"
            self.last_val = None
            self.last_was_skip = False
            self.running = True
            pygame.joystick.init()
            if pygame.joystick.get_count() != 0:
                self.controller = pygame.joystick.Joystick(0)
                self.controller.init()
                print(f"Detected: {self.controller.get_name()}")
            else:
                pygame.joystick.quit()
                pygame.quit()
                return
            while self.running:
                if self.stop_loop:
                    self.running = False
                    break
                for event in pygame.event.get():
                    if not initialized:
                        if hasattr(self.gui, "folder_explorer"):
                            explorer = self.gui.folder_explorer
                            imagegrid = self.gui.imagegrid
                            initialized = True
                            pygame.time.wait(333)
                        if event.type == pygame.JOYBUTTONDOWN and event.button == 6: # start button
                            self.gui.after_idle(self.fileManager.validate)
                        if initialized:
                            self.gui.after(0, explorer.caps_lock, None, "L")
                        continue

                    if event.type == pygame.QUIT:
                        self.running = False
                        break
                    
                    # Capture Button Presses
                    if event.type == pygame.JOYBUTTONDOWN:
                        match event.button:
                            case 15:
                                btn, selected_path, _, _, _ = explorer.buttons[explorer.selected_index]
                                self.gui.after(0, explorer.toggle_folder, selected_path)
                                self.last_was_skip = False
                            case 4: # option, move all
                                self.fileManager.moveall()
                                self.last_was_skip = False
                            case 9: #L1, change to navigating dest
                                btn, selected_path, _, _, _ = explorer.buttons[explorer.selected_index]
                                color = btn.default_c
                                self.gui.after(0, self.fileManager.setDestination, {"path": selected_path, "color": color}, event)
                                self.last_was_skip = False
                            case 10: #R1, change to navigating grid
                                btn, selected_path, _, _, _ = explorer.buttons[explorer.selected_index]
                                color = btn.default_c
                                self.gui.after(0, self.fileManager.setDestination, {"path": selected_path, "color": color}, event)
                                self.last_was_skip = False
                            #    side = "R"
                            #    if mode: self.gui.after(0, explorer.event_generate, "<Delete>")
                            #    else:
                            #        btn, selected_path, _, _, _ = explorer.buttons[explorer.selected_index]
                            #        color = btn.default_c
                            #        self.gui.after(0, self.fileManager.setDestination, {"path": selected_path, "color": color}, event)


                            case 11: #up
                                if side == "R":
                                    self.gui.after(0, imagegrid.navigate, "Up", False, True)
                                    self.last_was_skip = False
                                else:
                                    self.gui.after(0, explorer.nav, "Up")
                                
                            case 14: #right
                                self.gui.after(0, imagegrid.navigate, "Right", False, True)
                                self.last_was_skip = False
                            case 12: #down
                                if side == "R":
                                    self.gui.after(0, imagegrid.navigate, "Down", False, True)
                                    self.last_was_skip = False
                                else:
                                    self.gui.after(0, explorer.nav, "Down")
                            case 13: #left
                                self.gui.after(0, imagegrid.navigate, "Left", False, True)
                                self.last_was_skip = False


                            case 0: #x, assign
                                btn, selected_path, _, _, _ = explorer.buttons[explorer.selected_index]
                                color = btn.default_c
                                self.gui.after(0, self.fileManager.setDestination, {"path": selected_path, "color": color}, event)
                                self.last_was_skip = False
                            case 1 | 7: #o L3, undo
                                if self.last_was_skip:
                                    self.gui.after(0, imagegrid.navigate, "Left", False, True)
                                    self.last_was_skip = True
                                else:
                                    self.gui.after(0, self.undo)
                            case 2: #square, Trash
                                self.gui.after(0, explorer.event_generate, "<Delete>")
                                self.last_was_skip = False

                                #self.gui.after(0, imagegrid.toggle_entry, imagegrid.current_selection_entry)

                            case 3: #triangle, SKIP
                                self.last_was_skip = True
                                self.gui.after(0, imagegrid.navigate, "Right", False, True)
                        
                    # Capture Joystick/Trigger Movement
                    if event.type == pygame.JOYAXISMOTION:
                        if abs(event.value) > 0.2: # Small deadzone
                            match event.axis:
                                case 4: #left
                                    if ignore_first: 
                                        ignore_first = False
                                        continue
                                    
                                    if round(event.value, 2) == -1.0:
                                        self.gui.after(0, explorer.event_generate, "<Delete>")
                                        self.last_was_skip = False
                                        """side = "L"
                                        self.gui.after(0, explorer.caps_lock, None, "L")eeee
                                        print("Left")"""
                                case 5: # right
                                    if ignore_first_r: 
                                        ignore_first_r = False
                                        continue
                                    
                                    if round(event.value, 2) == -1.0:
                                        self.gui.after(0, explorer.event_generate, "<Delete>")
                                        self.last_was_skip = False
                                        """side = "R"
                                        self.gui.after(0, imagegrid.navigate, None, False, True)
                                        print("Right")"""
                                case 3:
                                    elapsed = perf_counter()-self.r3_timer
                                    comparison = round(event.value, 2) == round(self.last_val) if self.last_val else False
                                    if not comparison and elapsed < 0.250:
                                        pass
                                    else:
                                        self.gui.after(0, explorer.nav, "Up" if event.value < 0.0 else "Down")
                                        self.r3_timer = perf_counter()
                                        self.last_val = round(event.value, 2)
                    if event.type == pygame.JOYDEVICEREMOVED:
                        print("Hardware disconnected!")
                        pygame.time.wait(500)
                        continue
                        #self.running = False
                        #break

                    if event.type == pygame.JOYDEVICEADDED:
                        self.controller = pygame.joystick.Joystick(event.device_index)
                        self.controller.init() 
                        print(f"Connected to: {self.controller.get_name()}")
                #if self.controller is None:
                #    pygame.joystick.quit()

                pygame.time.wait(10)

            pygame.joystick.quit()
            pygame.quit()

        import threading
        thread = threading.Thread(target=loop, daemon=True)
        thread.start()
            


class GUIManager(tk.Tk):
    fileManager = None
    Image_frame = None
    second_window_viewer = None
    displayed_obj = None
    model_path = None
    last_model = None
    last_displayed = None
    first_render = True
    def __init__(self, jprefs: dict={}, jthemes: dict={}) -> None:
        super().__init__()
        self.jprefs, self.themes = jprefs, jthemes
        
        paths = jprefs.get("paths", {}) # No prefs file, uses "", etc as default.
        user = jprefs.get("user", {})
        technical = jprefs.get("technical", {})
        self.viewer_prefs = jprefs.get("viewer", {})

        self.source_folder = paths.get("source", "")
        self.destination_folder = paths.get("destination", "")
        self.lastsession = paths.get("lastsession", "")
        self.categories = paths.get("categories", [])
        self.excludes = paths.get("excludes", [])
        self.model_path = paths.get("model", None)
        
        self.thumbnailsize = int(technical.get("thumbnailsize", 256))
        self.squares_per_page_intvar = tk.IntVar(value=int(technical.get("squares_per_page", 500)))
        self.hotkeys = technical.get("hotkeys", "123456qwerty7890uiopasdfghjklzxcvbnm")
        self.do_debug = tk.BooleanVar(value=technical.get("do_debug", False))

        self.theme = tk.StringVar(value=user.get("theme", "Midnight"))
        self.d_theme = self.themes[self.theme.get()] 
        name = user.get("display_order")
        self.display_order = tk.StringVar(value=name if name in ("Smart", "Filename", "Date", "Type", "Size", "Dimensions", "Histogram") else "Smart")
        self.show_next = tk.BooleanVar(value=bool(user.get("show_next", True)))
        self.dock_view = tk.BooleanVar(value=bool(user.get("dock_view", True)))
        self.dock_side = tk.BooleanVar(value=bool(user.get("dock_side", True)))
        self.main_geometry = user.get("main_geometry", "zoomed")
        self.viewer_geometry = user.get("viewer_geometry", f"{int(self.winfo_screenwidth()*0.5)}x{int(self.winfo_screenheight()*0.5)}+{-8+365}+60")
        self.destpane_geometry = user.get("destpane_geometry", f"{int(self.winfo_screenwidth()*0.5)}x{int(self.winfo_screenheight()-120)}+{-8+365}+60")
        self.leftpane_width = int(user.get("leftpane_width", 363))
        self.middlepane_width = int(user.get("middlepane_width", 363))
        self.images_sorted = int(user.get("images_sorted", 0))

        viewer_defaults = { # Aliases
            "canvas": self.d_theme["viewer_bg"],
            "statusbar": self.d_theme["main_colour"],
            "statusbar_divider": self.d_theme.get("main_accent", self.d_theme["main_colour"]),
            "button": self.d_theme["button_colour"],
            "active_button": self.d_theme["button_colour_when_pressed"],
            "text": self.d_theme["field_text_colour"]
        }
        self.viewer_prefs["colors"] = self.viewer_prefs.get("colors", viewer_defaults)

        self.animation_stats_var = tk.StringVar(value="Anim: 0/100") # Anim: displayedlist with frames/displayedlist with framecount/(queue)
        self.resource_limiter_var = tk.StringVar(value="0/1000") # Frames: frames + frames_dest / max
        self.frame_gen_queue_var = tk.StringVar(value="Q:")
        self.train_status_var = tk.StringVar(value="")

        self.winfo_toplevel().title(f"")
        self.state("zoomed") if self.main_geometry == "zoomed" else self.geometry(self.main_geometry)
        self.protocol("WM_DELETE_WINDOW", self.closeprogram)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

    def initialize(self):
        self.bindhandler = Bindhandler(self)
        self.bindhandler.ps4controller_loop()
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

        self.animation_stats_label = tk.Label(statusbar, textvariable=self.animation_stats_var, bg=statusbar_bg, fg=txt_color, anchor="e", padx=5)
        self.resource_limiter = tk.Label(statusbar, textvariable=self.resource_limiter_var, bg=statusbar_bg, fg=txt_color, anchor="e", padx=5)
        self.frame_gen_queue_label = tk.Label(statusbar, textvariable=self.frame_gen_queue_var, bg=statusbar_bg, fg=txt_color, anchor="e", padx=5)
        self.ram_label = tk.Label(statusbar, text="RAM: 0.0 MB", bg=statusbar_bg, fg=txt_color, anchor="e", padx=5)
        self.train_status = tk.Label(statusbar, textvariable=self.train_status_var, bg=statusbar_bg , fg=txt_color, anchor="w", padx=10)

        self.train_status.pack(side="right", fill="y")
        if self.do_debug.get():
            self.animation_stats_label.pack(side="left", fill="y")
            self.resource_limiter.pack(side="left", fill="y")
            self.frame_gen_queue_label.pack(side="left", fill="y")
            self.ram_label.pack(side="left", fill="y")

        # Menus
        menu_bar = tk.Menu(self.master)
        file_menu = tk.Menu(menu_bar, tearoff=tk.OFF)
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
        # Configuration for column widths
        L_WIDTH = 25
        R_WIDTH = 20
        total_w = L_WIDTH + R_WIDTH

        def fmt(label, action):
            # Pads label to the left and action to the right to fill the total width
            return f"{label:<{L_WIDTH}}{action:>{R_WIDTH}}\n"

        help_text = (
            f"{'--- NAVIGATION & SELECTION ---':^{total_w}}\n"
            f"{fmt('Left-Click', 'Mark')}"
            f"{fmt('Arrows', 'Navigate Images')}"
            "\n"
            f"{'--- FOLDERS & ASSIGNING ---':^{total_w}}\n"
            f"{fmt('Left-Click, Hotkey', 'Assign Highlighted')}"
            f"{fmt('Right-Click', 'Expand/Collapse')}"
            f"{fmt('Shift + L-Click', 'View Assigned')}"
            f"{fmt('Shift + R-Click', 'Open Explorer')}"
            f"{fmt('Mid-Click + Key', 'Reassign')}"
            f"{fmt('Caps + Scroll', 'Nav Destination')}"
            f"{fmt('Caps + Enter', 'Assign Highlighted')}"
            f"{fmt('Control + Z', 'Undo')}"
            "\n"
            f"{'--- VIEWER CONTROLS ---':^{total_w}}\n"
            f"{fmt('L-Click (Drag)', 'Pan')}"
            f"{fmt('Scroll', 'Zoom')}"
            f"{fmt('Shift + Scroll', 'Rotate')}"
            f"{fmt('R-Click', 'Options')}"
            "\n"
            f"{'--- FINAL ACTIONS ---':^{total_w}}\n"
            f"{fmt('Move All', 'Transfer files')}"
            "\n"
            f"{'--- OTHER ---':^{total_w}}\n"
            "Grey dividers can be Moved/Resized.\n"
            "Highlighted item assigned if none marked."
        )

        # When displaying in your UI:
        # anchor='center', justify='center'
        print(help_text)
        canvas = tk.Canvas(middlepane_frame, bg=self.d_theme["viewer_bg"],highlightthickness=0,width=self.middlepane_width,height=600)
        canvas.place(relx=0.5, rely=0.5, anchor="center")
        self.middlepane_canvas = canvas
        canvas.bind("<Button-1>", lambda e: self.focus())

        ascii_art = """"""
        ascii_art2 = """"""
        self.ascii_art_id = canvas.create_text(self.middlepane_width//2, 300, text=ascii_art,fill="#525252",font=("Consolas", 12),justify="left", anchor="center")
        self.ascii_art_id2 = canvas.create_text(self.middlepane_width//2, 0, text=ascii_art2,fill="#525252",font=("Consolas", 6),justify="left", anchor="center")
        self.help_text_id = canvas.create_text(self.middlepane_width//2, 300, text=help_text,fill="white",font=font_style, anchor="center", justify="center")
        canvas.pack(fill="both", expand=True)

        def redraw(event):
            w = event.width
            h = event.height
            
            # Position both in the center of the current canvas area
            canvas.coords(self.help_text_id, w // 2, h // 2-100)
            canvas.coords(self.ascii_art_id, w // 2+25, 850)
            canvas.coords(self.ascii_art_id2, w // 2+150, 110)

            #canvas.config(scrollregion=canvas.bbox("all"))
        
        canvas.bind("<Configure>", redraw)
        self.middle_label = canvas
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

        self.source_entry_field.bind("<Return>", lambda e: self.fileManager.validate())
        self.destination_entry_field.bind("<Return>", lambda e: self.fileManager.validate())

        s_b = tk.Button(self.first_frame, text="Source", command=lambda: self.filedialog(self.source_entry_field, type="src"))
        d_b = tk.Button(self.first_frame, text="Destination", command=lambda: self.filedialog(self.destination_entry_field, type="dst"))
        self.ses_b = tk.Button(self.first_frame, text="Session", command=lambda: self.filedialog(self.session_entry_field, type="session"))

        self.source_entry_field.insert(0, self.source_folder or "Right click to Select Source Folder")
        self.source_entry_field.xview_moveto(1.0)
        self.destination_entry_field.insert(0, self.destination_folder or "Right click to Select Destination Folder")
        self.destination_entry_field.xview_moveto(1.0)
        self.session_entry_field.insert(0, os.path.basename(self.lastsession) or "No last Session")
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
        self.toppane.forget(self.middlepane_frame) if not self.dock_view.get() else None
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

        self.Image_frame = None
        self.second_window_viewer = None

        self.change_theme(self.theme.get())
        
    def filedialog(self, entry, event=None, type=None):
        from tkinter import filedialog as tkFileDialog
        match type:
            case "session": path = tkFileDialog.askopenfile(initialdir=os.getcwd(), title="Select Session Data File", filetypes=(("JavaScript Object Notation", "*.json"),))
            case "src": path = tkFileDialog.askdirectory(initialdir=self.source_entry_field.get(), title="Select Source folder")
            case "dst": path = tkFileDialog.askdirectory(initialdir=self.destination_entry_field.get(), title="Select Destination folder")
        if path == "" or path == None: return
        entry.delete(0, tk.END)
        entry.insert(0, path.name if type == "session" else os.path.normpath(path))
        entry.xview_moveto(1.0)
        if type == "dst" and hasattr(self, "folder_explorer") and self.folder_explorer:
            self.folder_explorer.set_view(path)
            self.fileManager.validate("button")
        elif type == "src": self.fileManager.validate("button")

    "Navigation / options"
    def change_viewer(self):
        """Change which viewer is in use. Dock or secondary window"""
        from viewer import Application
        m_frame, toppane, imagegrid = self.middlepane_frame, self.toppane, self.imagegrid, 
        current_panes = [str(p) for p in toppane.panes()]
        if m_frame.winfo_width() > 1: self.middlepane_width = m_frame.winfo_width()
        self.displayed_obj = None
        self.first_render = True
        if self.dock_view.get(): # close immediately
            if self.second_window_viewer: # hide, reset, dont close.
                self.displayed_obj = None
                self.second_window_viewer.save_json()
                if self.Image_frame:
                    self.Image_frame.set_vals(self.second_window_viewer.savedata)
                self.second_window_viewer.master.attributes("-alpha", 0.0)
                self.second_window_viewer.master.withdraw()
                self.update_idletasks()

        if str(m_frame) in current_panes: toppane.forget(m_frame)
        if str(imagegrid) in current_panes: toppane.forget(imagegrid)

        if self.dock_view.get():
            if self.dock_side.get(): # Middlepane on Left
                toppane.add(m_frame)
                toppane.add(imagegrid)
            else: # Middlepane on Right
                toppane.add(imagegrid)
                toppane.add(m_frame)
            toppane.update_idletasks()
            if not self.Image_frame:
                self.Image_frame = Application(self.middlepane_frame, savedata=self.viewer_prefs, gui=self)
            self.Image_frame.canvas.update()
            self.bindhandler.search_widget.new_canvas(self.Image_frame.canvas)
            if self.bindhandler.search_widget.search_active: self.bindhandler.search_widget.draw_search_box()
            if self.imagegrid.current_selection_entry:
                self.displayimage(self.imagegrid.current_selection_entry.file)
                self.Image_frame.canvas.update()
                
            self.bind("<Control-s>", lambda e: self.Image_frame.toggle_statusbar(True))
            self.bind("<Control-S>", lambda e: self.Image_frame.toggle_statusbar(True))
            self.second_window_viewer.set_image(None)
        else:
            self.title(self.title().split(" -", 1)[0])
            if not self.second_window_viewer: 
                self.second_window_viewer = Application(savedata=self.viewer_prefs, gui=self)
            if self.Image_frame:
                self.Image_frame.save_json()
                self.second_window_viewer.set_vals(self.Image_frame.savedata)
            
            self.bindhandler.search_widget.new_canvas(self.second_window_viewer.canvas)
            if self.bindhandler.search_widget.search_active: self.bindhandler.search_widget.draw_search_box()
            if self.imagegrid.current_selection_entry: self.displayimage(self.imagegrid.current_selection_entry.file)
            if self.second_window_viewer.master.state() not in ("normal", "zoomed"): self.second_window_viewer.master.deiconify()
            self.second_window_viewer.master.attributes("-alpha", 1.0)
            toppane.add(imagegrid)

            self.update()
            def safe_call(event=None):
                if self.second_window_viewer and hasattr(self.second_window_viewer, "statusbar"):
                    self.second_window_viewer.statusbar.set(not self.second_window_viewer.statusbar.get())
            self.bind("<Control-s>", safe_call)
            self.bind("<Control-S>", safe_call)
            if self.Image_frame: self.Image_frame.set_image(None)

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
        self.imagegrid.thumbs.stop_background_worker()
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
        def _apply_theme_to_children(parent_widget, theme):
            """Recursively traverses the widget tree and applies the theme based on widget class."""
            for child in parent_widget.winfo_children():
                if not child.winfo_exists(): continue

                w_class = child.winfo_class().lower()
                match w_class:
                    case "frame":
                        if child != self.leftui and child.widgetName != "ttk::frame":
                            child.configure(bg=theme["grid_background_colour"])
                    case "button":
                        if "!folderexplorer" not in str(child._w):
                            child.configure(bg=theme["button_colour"], fg=theme["button_text_colour"], activebackground=theme["button_colour_when_pressed"], activeforeground=theme["button_text_colour_when_pressed"])
                            child.bind("<Enter>", lambda e, w=child: w.config(bg=self.d_theme["button_colour_when_pressed"], fg=self.d_theme["button_text_colour_when_pressed"]))
                            child.bind("<Leave>", lambda e, w=child: w.config(bg=self.d_theme["button_colour"], fg=self.d_theme["button_text_colour"]))
                    case "menubutton":
                        child.config(bg=theme["button_colour"], fg=theme["button_text_colour"],activebackground=theme["button_colour_when_pressed"], activeforeground=theme["button_text_colour_when_pressed"])
                    case "entry":
                        child.config(bg=theme["field_colour"], fg=theme["field_text_colour"])
                        child.bind("<FocusIn>", lambda e, w=child: w.config(bg=self.d_theme["field_activated_colour"], fg=self.d_theme["field_text_activated_colour"]))
                        child.bind("<FocusOut>", lambda e, w=child: w.config(bg=self.d_theme["field_colour"], fg=self.d_theme["field_text_colour"]))
                
                if child.winfo_children():
                    _apply_theme_to_children(child, theme)

        new_theme = self.themes[theme_name]
        self.d_theme = new_theme

        self.config(bg=new_theme["main_colour"])
        self.style.configure('Theme_dividers.TPanedwindow', background=new_theme["pane_divider_colour"])

        self.leftui.configure(bg=new_theme["main_colour"])
        self.middlepane_frame.configure(bg=new_theme["viewer_bg"])
        if self.Image_frame and self.middlepane_canvas: 
            self.middlepane_canvas.destroy()
            self.middlepane_canvas = None
        elif self.middlepane_canvas and self.middlepane_canvas.winfo_exists():
            self.middlepane_canvas.config(bg=new_theme["viewer_bg"])
        self.imagegrid.change_theme(theme=new_theme)

        colors = {"canvas": self.d_theme["viewer_bg"],"statusbar": self.d_theme["main_colour"],"statusbar_divider": self.d_theme.get("main_accent", self.d_theme["main_colour"]),"button": self.d_theme["button_colour"],"active_button": self.d_theme["button_colour_when_pressed"],"text": self.d_theme["field_text_colour"]}
        if self.Image_frame: self.Image_frame.change_theme(colors)
        if self.second_window_viewer: self.second_window_viewer.change_theme(colors)

        if hasattr(self, "folder_explorer"): # we are deleting tk tk each time and destw, maybe make them persistent
            self.folder_explorer.style.configure("Theme_dividers.TFrame", background=new_theme["main_colour"])
            self.folder_explorer.canvas.configure(bg=new_theme["main_colour"])
            if hasattr(self.folder_explorer, "destw") and self.folder_explorer.destw != None and self.folder_explorer.destw.winfo_exists():
                self.folder_explorer.destw.configure(bg=new_theme["grid_background_colour"])
                self.folder_explorer.destw.change_theme(theme=new_theme)            
            
        _apply_theme_to_children(self.toppane, new_theme)
        self.update()
    
       
    "Viewer"
    def displayimage(self, obj):
        from viewer import Application
        search_widget = self.bindhandler.search_widget
        if self.middle_label != None: # Clean up keybinding guide
            self.middle_label.destroy()
            self.middle_label = None
        
        if self.dock_view.get(): # Initialize the viewer
            if not self.Image_frame: 
                self.Image_frame = Application(self.middlepane_frame, savedata=self.viewer_prefs, gui=self)
                search_widget.new_canvas(self.Image_frame.canvas)
                if self.first_render: search_widget.display_instructions()
        else:
            if not self.second_window_viewer: 
                self.second_window_viewer = Application(savedata=self.viewer_prefs, gui=self)
                search_widget.new_canvas(self.second_window_viewer.canvas)
                if self.first_render: search_widget.display_instructions()

        adjacent = self.imagegrid.get_items_adjacent_to_selection() # Tells viewer what images to precache
        path = None if obj is None else obj.path
        if self.dock_view.get(): self.Image_frame.set_image(path, obj, adjacent)
        else:
            if self.second_window_viewer.master.state() not in ("normal", "zoomed"): self.second_window_viewer.master.deiconify()
            self.second_window_viewer.master.lift()
            self.second_window_viewer.master.attributes("-alpha", 1.0)
            self.second_window_viewer.set_image(path, obj, adjacent)

        self.displayed_obj = obj
        
        if not self.first_render and search_widget.guide_text_id: search_widget.remove_instruction() # Cleanup keybindining guide of search_widget after first_render
        self.first_render = False        

    "Exit function"
    def closeprogram(self):
        from tkinter.messagebox import askokcancel
        if self.fileManager.assigned and not askokcancel("Designated but Un-Moved files, really quit?", "You have destination designated, but unmoved files. (Simply cancel and Move All if you want)"):
            return

        if self.fileManager.assigned:
            self.fileManager.last_assigned_list_for_autosave = self.fileManager.assigned.copy()
            self.fileManager.savesession()
        self.imagegrid.thumbs.stop_background_worker()
        if hasattr(self, "folder_explorer") and self.folder_explorer:
            self.folder_explorer.executor.shutdown()
        if self.dock_view.get(): 
            if self.Image_frame: self.Image_frame.save_json()
        else:
            if self.second_window_viewer: self.second_window_viewer.save_json()

        self.fileManager.saveprefs(self)
        self.bindhandler.stop_loop = True
        self.destroy()
        self.fileManager.purge_cache()
        self.fileManager.move_temp_to_trash()
        
