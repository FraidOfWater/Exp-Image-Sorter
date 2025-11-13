from time import perf_counter
import os
from threading import Thread
from random import shuffle, seed

import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
import tkinter.scrolledtext as tkst
from tkinter.ttk import Panedwindow

from destination_viewer import Destination_Viewer
from canvasimage import CanvasImage
from middle2 import ImageDisplayApp

# use thumbs for color checks, resize instead of thumbs, also...
class GUIManager(tk.Tk): #Main window
    "Initialization"
    debounce = None
    last_call_time = 0.0
    second_window = None
    Image_frame = None
    Image_frame1 = None
    focused_on_secondwindow = False # Helper attribute for navigator
    viewer_prefs = {}
    color_i = 0
    after_id = None

    def __init__(self, fileManager, jprefs) -> None:
        super().__init__()
        self.fileManager = fileManager

        "INITIALIZE USING PREFS: THEME"
        if True:
            self.themes = fileManager.jthemes #overrides defaults
            default = self.themes.get("Midnight", {})

            self.main_bg =      default.get("main_bg") or "#202041"
            self.viewer_bg =    default.get("viewer_bg") or "#141433"
            self.grid_bg =      default.get("grid_bg") or "#303276"
            
            self.divider_colour =   default.get("divider_colour") or "grey"

            self.button_bg =    default.get("button_bg") or "#24255C",
            self.button_bg_pressed =    default.get("button_bg_pressed") or "#303276",
            self.button_text =          default.get("button_text") or "white"
            self.button_text_pressed =  default.get("button_text_pressed") or "white"

            self.field_colour =             default.get("field_colour") or "#303276"
            self.field_activated_colour =   default.get("field_activated_colour") or "#888BF8"
            self.field_text =        default.get("field_text") or "white"
            self.field_text_pressed =  default.get("field_text_pressed") or "black"

            self.square_default =   default.get("square_default") or "#303276"
            self.square_selected =  default.get("square_selected") or "#888BF8"
            self.square_text =      default.get("square_text") or "white"
            self.square_outline =   default.get("square_outline") or "white"
            self.active_outline =   default.get("active_outline") or "white"
            self.outline_thickness =int(default.get("outline_thickness")) or 2
            self.textbox_size = int(default.get("textbox_size")) or 25
            self.square_padx =  int(default.get("square_padx")) or 2
            self.square_pady =  int(default.get("square_pady")) or 2
            self.square_cutoff =  bool(default.get("square_cutoff")) or False
            self.square_cutoff_size =  int(default.get("square_cutoff_size")) or 11
            
        "INITIALIZE USING PREFS: SETTINGS"
        if True:
            "VALIDATION"
            expected_keys = ["paths", "user", "technical", "qui", "window_settings", "viewer"]
            missing_keys = [key for key in expected_keys if jprefs and key not in jprefs]
            if missing_keys: print(f"Missing a key(s) in prefs: {missing_keys}, defaults will be used.")

            paths = jprefs.get("paths", {})
            self.source_folder = paths.get("source", "")
            self.destination_folder = paths.get("destination", "")
            self.lastsession = tk.StringVar(value=paths.get("lastsession", ""))

            user = jprefs.get("user", {})
            self.thumbnailsize = int(user.get("thumbnailsize", 256))
            self.hotkeys = user.get("hotkeys", "123456qwerty7890uiopasdfghjklzxcvbnm")
            self.centering_button = bool(user.get("centering_button", True))
            self.force_scrollbar = bool(user.get("force_scrollbar", True))
            self.auto_load = bool(user.get("auto_load", True))
            self.do_anim_loading_colors = bool(user.get("do_anim_loading_colors", False))
            self.do_debug_terminal = bool(user.get("do_debug_terminal", True))

            tech = jprefs.get("technical", {})
            self.filter_mode = tech.get("quick_preview_filter") if tech.get("quick_preview_filter") in ["NEAREST", "BILINEAR", "BICUBIC", "LANCZOS"] else "BILINEAR"
            self.quick_preview_size_threshold = int(tech.get("quick_preview_size_threshold", 5))
            #threads                # Exlusively for fileManager
            #max_concurrent_frames  # Exlusively for fileManager
            #autosave               # Exlusively for fileManager

            gui = jprefs.get("qui", {}) # should be spelled gui XD
            self.squares_per_page_intvar = tk.IntVar(value=int(gui.get("squares_per_page", 40)))
            self.sort_by_date_boolvar = tk.BooleanVar(value=bool(gui.get("sort_by_date", True)))
            self.viewer_x_centering = bool(user.get("viewer_x_centering", True))
            self.viewer_y_centering = bool(user.get("viewer_y_centering", True))
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

            #Viewer
            ##END OF PREFS

        "INITIALIZE GUI"
        if True:
            if self.main_geometry: self.geometry(self.main_geometry)
            else: 
                self.state('zoomed')
                self.main_geometry = f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+-8+0"
            
            self.columnconfigure(0, weight=1)
            self.rowconfigure(0, weight=1)
            
            self.protocol("WM_DELETE_WINDOW", self.closeprogram)
            self.winfo_toplevel().title("Simple Image Sorter: QOL")

            self.current_ram_strvar = tk.StringVar(value="RAM: 0 MB") # RAM: 95.34 MB
            self.animation_stats = tk.StringVar(value="Anim: 0/100") # Anim: displayedlist with frames/displayedlist with framecount/(queue)
            self.resource_limiter = tk.StringVar(value="0/1000") # Frames: frames + frames_dest / max

    def show_ram_usage(self, old=None):
        filemanager = self.fileManager
        if not self.do_debug_terminal:
            return
        import psutil
        def get_memory_usage():
            # Get the current process
            process = psutil.Process()

            # Get memory info
            memory_info = process.memory_info()

            # Return the RSS (Resident Set Size) in bytes
            return (memory_info.rss)
        
        self.current_ram_strvar.set(f"RAM: {get_memory_usage() / (1024 ** 2):.2f} MB")

        "Anim: displayedlist with frames/displayedlist with framecount/(queue)"
        held_animations = [x for x in self.gridmanager.displayedset if x.file.frametimes]
        self.animation_stats.set(f"Anim: {len(filemanager.animate.running)}/{len(held_animations)}")

        "Frames: frames + frames_dest / max"
        c = 0
        for x in held_animations:
            c += len(x.file.frames)

        self.resource_limiter.set(f"{c}/{filemanager.max_concurrent_frames}")

        self.fileManager.concurrent_frames = c

        self.after(333, self.show_ram_usage)
    
    def manage_lines(self, input=None, clear=False):
        text_widget = self.text_widget
        text_widget.configure(state="normal")
        if clear:
            text_widget.delete("1.0", tk.END)
            if input:
                text_widget.insert(tk.END, f"{input}\n") 
            text_widget.configure(state="disabled")
            return

        if input:
            text_widget.insert(tk.END, f"{input}\n") 
            lines = text_widget.get("1.0", tk.END).strip().split("\n")

            if len(lines) > 5: # Remove old lines
                lines = lines[-5:]
                text_widget.delete("1.0", tk.END)
                text_widget.insert(tk.END, "\n".join(lines) + "\n")

            #text_widget.see(tk.END)
            text_widget.configure(state="disabled")
    
    def initialize(self):
        "Initializating GUI after we get the prefs from filemanager."

        self.smallfont = tkfont.Font(family='Helvetica', size=10)
        style = ttk.Style()
        style.configure('Theme_dividers.TPanedwindow', background=self.divider_colour)  # Panedwindow, the divider colour.
        style.configure("Theme_checkbox.TCheckbutton", background=self.main_bg, foreground=self.button_text, highlightthickness = 0) # Theme for checkbox
        self.style = style
        
        # PANED
        toppane = Panedwindow(self, orient="horizontal")
        self.toppane = toppane

        # FRAMES
        leftui = tk.Frame(toppane, name="leftui", width=self.leftpane_width, bg=self.main_bg)
        middlepane_frame = tk.Frame(toppane, name="middlepane", bg=self.viewer_bg, width = self.middlepane_width)

        self.leftui = leftui
        self.middlepane_frame = middlepane_frame
 
        # IMAGEGRID
        imagegrid = ImageDisplayApp(toppane, thumb_size=self.thumbnailsize, center=False, bg=self.grid_bg, 
                                    theme={"square_default": self.square_default,
                                           "square_selected": self.square_selected,
                                           "grid_bg": self.grid_bg,
                                           "square_text": self.square_text, 
                                           "square_outline": self.square_outline,
                                           "outline_thickness": self.outline_thickness,
                                           "textbox_size": self.textbox_size,
                                           "square_padx": self.square_padx, 
                                           "square_pady": self.square_pady
                                           })
                                           
        self.imagegrid = imagegrid

        # COLLECT ELEMENTS FOR THEME CHANGER
        leftui.grid_propagate(False) #to turn off auto scaling.
        leftui.columnconfigure(0, weight=1)
        leftui.rowconfigure(5, weight=1)
        
        #imagegrid.configure(state="disabled")
        #imagegrid.bind("<Up>", lambda e: "break")
        #imagegrid.bind("<Down>", lambda e: "break")
        #imagegrid.bind("<MouseWheel>", lambda e: "break")
        #imagegrid.bind("<MouseWheel>", lambda e: scroll(imagegrid, ("scroll_s", e)))

        imagegrid.pack(fill="both", expand=True)
        
        toppane.add(self.leftui, weight=0)
        
        self.first_page_buttons() # This setups all the buttons and text

        #imagegrid.pack(fill="both", expand=True)
        
        toppane.add(imagegrid, weight=1)

        toppane.grid(row=0, column=0, sticky="NSEW")
        toppane.configure(style='Theme_dividers.TPanedwindow')

        self.destination_viewer = Destination_Viewer(self.fileManager)
        self.gridmanager = GridManager(self.fileManager)

    def first_page_buttons(self):
        "Creates and places the buttons for the first page"
        self.first_page = []

        panel = tk.Label(self.leftui, wraplength=350, justify="left", bg=self.main_bg,fg=self.button_text, text="""

                Select a Source Directory:
Choose a folder to search for images,
All subfolders will be scanned as well.

                Set the Destination Directory:
Choose a folder to sort into,
The folder must contain subfolders, these are the folders you sort into.
You can now press "New Session".

                Exclusions:
Full path. One path per line, no commas.

                Amount of images:
Input a number in the smaller box after pressing New Session.
The grid will be populated by this amount at all times. (if you want to load manually, turn off "auto_load" in prefs.json)

                Assigning:
Right-Click to highlight and view an image.
Arrowkeys to highlight and view an image (viewing only when "Show Next" is on) (Enter / Space, When "Show Next" is off)
Hotkeys to assign to destinations, or left-click the destination button.

                Viewing destinations:
Right-click on a destination button to see what is assigned there.
Moved images do not show here.
       
                Preferences:
Choose preferences inside prefs.json,
This file will be generated on each run, if missing.
You can change the hotkeys.
You can change thumbnailsize
You can force scrollbars on/off for the grid.

                Acknowledgments:
Special thanks to FooBar167 on Stack Overflow for the advanced and memory-efficient Zoom and Pan Tkinter class.
        """
                              )
        panel.grid(row=3, column=0, columnspan=200, rowspan=200, sticky="NSEW")

        # Initial view buttons
        if True: 
            # Initial buttons you see are in this frame
            first_frame = tk.Frame(self.leftui,bg=self.main_bg)
            
            first_frame.columnconfigure(1, weight=1)
            first_frame.grid(row=0, column=0, sticky="ew")

            # Third column
            if True:
                but_t = self.button_text
                but_c = self.button_bg
                but_c_a = self.button_bg_pressed
                but_c_a_t = self.button_text_pressed
                # Manage exlusions
                exclusions_b = tk.Button(first_frame, text="Manage Exclusions", command=self.excludeshow,
                    bg=but_c, fg=but_t, activebackground = but_c_a, activeforeground=but_c_a_t,)
                
                # New Session
                new_session_b = tk.Button(first_frame, text="New Session", command=self.fileManager.validate,
                    bg=but_c, fg=but_t, activebackground = but_c_a, activeforeground=but_c_a_t,)
                
                # Load Session
                load_session_b = tk.Button(first_frame, text="Load Session", command=self.fileManager.loadsession,
                    bg=but_c, fg=but_t, activebackground = but_c_a, activeforeground=but_c_a_t,)
                
                exclusions_b.grid(row=0, column=2, sticky="ew")
                new_session_b.grid(row=1, column=2, sticky="ew")
                load_session_b.grid(row=3, column=2, sticky='ew')
                
                self.first_page.extend([panel, exclusions_b, new_session_b, load_session_b])

            # Second column
            if True:
                # Source field
                self.source_entry_field = tk.Entry(first_frame, takefocus=False,
                    bg=self.field_colour, fg=self.field_text)  # scandirpathEntry
                       
                # Dest field
                self.destination_entry_field = tk.Entry(first_frame, takefocus=False,
                    bg=self.field_colour, fg=self.field_text)  # dest dir path entry
                      
                # Session field
                session_entry_field = tk.Entry(first_frame, takefocus=False, textvariable=self.lastsession,
                    bg=self.field_colour, fg=self.field_text)
                
                self.source_entry_field.grid(row=0, column=1, sticky="ew", padx=2)
                self.destination_entry_field.grid(row=1, column=1, sticky="ew", padx=2)
                session_entry_field.grid(row=3, column=1, sticky='ew', padx=2)

                self.source_entry_field.insert(0, self.source_folder)
                self.destination_entry_field.insert(0, self.destination_folder)
            # First column
            if True:
                # Source folder button
                source_b = tk.Button(first_frame, text="Source Folder:", command=lambda: self.filedialogselect(self.source_entry_field, "d"),
                    bg=but_c, fg=but_t, activebackground = but_c_a, activeforeground=but_c_a_t,)
                
                # Destination folder button
                destination_b = tk.Button(first_frame, text="Destination Folder:", command=lambda: self.filedialogselect(self.destination_entry_field, "d"),
                    bg=but_c, fg=but_t, activebackground = but_c_a, activeforeground=but_c_a_t,)
                
                # Session file button
                session_b = tk.Button(first_frame, text="Session Data:", command=lambda: self.filedialogselect(session_entry_field, "f"),
                    bg=but_c, fg=but_t, activebackground = but_c_a, activeforeground=but_c_a_t,)
                
                source_b.grid(row=0, column=0, sticky="e")
                destination_b.grid(row=1, column=0, sticky="e")
                session_b.grid(row=3, column=0, sticky='e')


            # Sort by date checkbox
            self.sort_by_date_b = ttk.Checkbutton(self.leftui, text="Sort by Date", variable=self.sort_by_date_boolvar, onvalue=True, offvalue=False, style="Theme_checkbox.TCheckbutton")
            self.sort_by_date_b.grid(row=4, column=0, sticky="w", padx=25)

        # Option for making the buttons change color on hover. Can be set in prefs. 
        if True:
            # Third column
            exclusions_b.bind("<Enter>", lambda e: exclusions_b.config(bg=but_c_a, fg=but_c_a_t,))
            exclusions_b.bind("<Leave>", lambda e: exclusions_b.config(bg=but_c, fg=but_t))

            new_session_b.bind("<Enter>", lambda e: new_session_b.config(bg=but_c_a, fg=but_c_a_t,))
            new_session_b.bind("<Leave>", lambda e: new_session_b.config(bg=but_c, fg=but_t))

            load_session_b.bind("<Enter>", lambda e: load_session_b.config(bg=but_c_a, fg=but_c_a_t,))
            load_session_b.bind("<Leave>", lambda e: load_session_b.config(bg=but_c, fg=but_t))

            # Second column
            self.source_entry_field.bind("<FocusIn>", lambda e: self.source_entry_field.config(bg=self.field_activated_colour, fg=self.field_text_pressed))
            self.source_entry_field.bind("<FocusOut>", lambda e: self.source_entry_field.config(bg=self.field_colour, fg=self.field_text))

            self.destination_entry_field.bind("<FocusIn>", lambda e: self.destination_entry_field.config(bg=self.field_activated_colour, fg=self.field_text_pressed))
            self.destination_entry_field.bind("<FocusOut>", lambda e: self.destination_entry_field.config(bg=self.field_colour, fg=self.field_text))

            session_entry_field.bind("<FocusIn>", lambda e: session_entry_field.config(bg=self.field_activated_colour, fg=self.field_text_pressed))
            session_entry_field.bind("<FocusOut>", lambda e: session_entry_field.config(bg=self.field_colour, fg=self.field_text))

            # Third column
            source_b.bind("<Enter>", lambda e: source_b.config(bg=but_c_a, fg=but_c_a_t,))
            source_b.bind("<Leave>", lambda e: source_b.config(bg=but_c, fg=but_t))

            destination_b.bind("<Enter>", lambda e: destination_b.config(bg=but_c_a, fg=but_c_a_t,))
            destination_b.bind("<Leave>", lambda e: destination_b.config(bg=but_c, fg=but_t))

            session_b.bind("<Enter>", lambda e: session_b.config(bg=but_c_a, fg=but_c_a_t,))
            session_b.bind("<Leave>", lambda e: session_b.config(bg=but_c, fg=but_t))

        # Debug Terminal and Stats
        if True:
            statsframe = tk.Frame(self.leftui,name="stats", bg=self.main_bg)
            
            statsframe.grid(column=0, row=6, sticky="SW")
            statsframe.columnconfigure(0, weight=1)
            statsframe.rowconfigure(0, weight=1)
            statsframe.columnconfigure(1, weight=1)
            statsframe.rowconfigure(1, weight=1)
            statsframe.columnconfigure(2, weight=1)
            statsframe.rowconfigure(2, weight=1)


            "TERMINAL"
            terminal_frame = tk.Frame(statsframe, bg=self.main_bg)
            self.terminal_frame = terminal_frame
            terminal_frame.grid(row = 1, sticky="NSEW")
            terminal_frame.columnconfigure(0, weight=1)#
            terminal_frame.rowconfigure(0, weight=1)#
            terminal_frame.columnconfigure(1, weight=1)#
            terminal_frame.rowconfigure(1, weight=1)#
            terminal_frame.columnconfigure(2, weight=1)#
            terminal_frame.rowconfigure(2, weight=1)#
            

            # Create a Text widget for terminal output
            "Debug stuff"
            
            if self.do_debug_terminal:
                self.text_widget = tk.Text(terminal_frame, name="terminal", width=10000, height=6, bg="#03070b", fg = "#6a858a", state="disabled")
                self.text_widget.grid(row = 0, sticky="EW")

                "LABELS" # Main frame
                label_frame = tk.Frame(statsframe, bg=self.main_bg)
                label_frame.grid(row = 0, sticky="NSEW")
                label_frame.columnconfigure(0, weight=0)
                label_frame.rowconfigure(0, weight=1)

                # Secondary column:
                left_column = tk.Frame(label_frame, bg="#03070b")
                left_column.grid(row = 0, column = 0, sticky="EW")
                left_column.columnconfigure(0, weight=1)
                left_column.rowconfigure(0, weight=1)
                left_column.columnconfigure(1, weight=0)
                left_column.rowconfigure(1, weight=1)

                left_column2 = tk.Frame(left_column, bg="#03070b")
                left_column2.grid(row = 0, column = 0, sticky="W")
                left_column2.columnconfigure(0, weight=0)
                left_column2.rowconfigure(0, weight=1)
                left_column2.columnconfigure(1, weight=0)
                left_column2.rowconfigure(1, weight=1)
                left_column2.columnconfigure(2, weight=0)
                left_column2.rowconfigure(2, weight=1)

                # Actual labels: Left
                ram_label = tk.Label(left_column2, justify="left", bg="#03070b", fg="#6a858a", textvariable=self.current_ram_strvar) # RAN
                ram_label.grid(row = 2, column = 0, sticky = "W")

                sorted_label = tk.Label(left_column2, justify="left", bg="#03070b", fg="#6a858a", textvariable=self.images_sorted_strvar) # SORTED
                sorted_label.grid(row = 0, column = 0, sticky="W")

                self.images_left_stats_strvar = tk.StringVar(value="Left: NaN/NaN/NaN") # Assigned/Displayed/Imagelist
                left_label = tk.Label(left_column2, justify="left", bg="#03070b", fg="#6a858a", textvariable=self.images_left_stats_strvar) # LISTS
                left_label.grid(row = 1, column = 0, sticky="W")

                # Actual labels: Middle
                self.info = tk.StringVar(value="Size:")
                self.name_label = tk.Label(left_column2, width=24, anchor="w", bg="#03070b", fg="#6a858a", textvariable=self.info) # INFO
                self.name_label.grid(row=0, column=1, sticky="ew")

                container_frameinfo = tk.Frame(left_column2, bg="#03070b")
                container_frameinfo.grid(row=1, column=1, sticky = "W")

                self.frameinfo = tk.StringVar(value="F/D: 0/0/0")
                size_label = tk.Label(container_frameinfo, justify="left", bg="#03070b", fg="#6a858a", textvariable=self.frameinfo) # FRAMEINFO
                size_label.grid(row = 0, column = 0, sticky = "W")

                self.frametimeinfo = tk.StringVar(value="0/0")
                size_label2 = tk.Label(container_frameinfo, justify="left", bg="#03070b", fg="#6a858a", textvariable=self.frametimeinfo) # FRAMETIME
                size_label2.grid(row = 0, column = 1, sticky = "W")
                

                self.first_render = tk.StringVar(value="0") # F: 1.543s
                rendertime = tk.Label(left_column2, justify="left", bg="#03070b", fg="#6a858a", textvariable=self.first_render) # FRAMETIME
                rendertime.grid(row=2, column=1, sticky="W")

                self.name_ext_size = tk.StringVar(value="0")

                # Actual labels: Right
                panel333 = tk.Label(left_column2, justify="left", bg="#03070b", fg="#6a858a", textvariable=self.animation_stats)
                panel333.grid(column = 2, row = 1, sticky = "W")

                panel3333 = tk.Label(left_column2, justify="left", bg="#03070b", fg="#6a858a", textvariable=self.resource_limiter)
                panel3333.grid(row = 2, column = 2, sticky = "W")

                self.debugs = [self.text_widget, label_frame, left_column, left_column2, ram_label, 
                                   sorted_label, left_label, self.name_label,
                                   container_frameinfo, size_label, size_label2, rendertime, panel333, panel3333]

    def guisetup(self, destinations): # 
        "Happens after we press new session or load session. Does the buttons etc"
        filemanager = self.fileManager
        def get_folder_color(dest, formats, sample_size):
            from PIL import Image
            import numpy as np
            from io import BytesIO
            import colorsys
            from colorthief import ColorThief
            from sklearn.cluster import KMeans #2 seconds!!!
            def get_fur_color(colors):
                def hex_to_rgb(hex_color):
                    hex_color = hex_color.lstrip('#')
                    return [int(hex_color[i:i+2], 16) for i in (0, 2, 4)]
                if isinstance(colors[0], str) and colors[0].startswith('#'):
                    colors = np.array([hex_to_rgb(color) for color in colors])

                def rgb_to_hsv(rgb):
                    return colorsys.rgb_to_hsv(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255)

                def rgb_distance(color1, color2):
                    return np.linalg.norm(np.array(color1) - np.array(color2))

                kmeans = KMeans(n_clusters=5)
                kmeans.fit(colors)
                centers, labels = kmeans.cluster_centers_, kmeans.labels_
                unique, counts = np.unique(labels, return_counts=True)
                largest_cluster = unique[np.argmax(counts)]

                cluster_center = centers[largest_cluster]
                distances = np.array([rgb_distance(color, cluster_center) for color in colors])
                threshold = np.percentile(distances, 70)
                inlier_colors = colors[distances <= threshold]

                def get_vibrancy(color):
                    hsv = rgb_to_hsv(color)
                    return hsv[1] * hsv[2]

                vibrancy_scores = [get_vibrancy(color) for color in inlier_colors]
                vibrant_colors = [color for color, score in zip(inlier_colors, vibrancy_scores)
                                  if score >= np.median(vibrancy_scores)]

                final_color = np.mean(vibrant_colors, axis=0) if vibrant_colors else np.mean(inlier_colors, axis=0)
                a = final_color.astype(int)
                return ('kMEANS', '#{:02x}{:02x}{:02x}'.format(*a))
            
            def process_image(img, resize, q):
                try:
                    image = Image.open(img).convert('RGB')
                    if resize is not None and (image.width > resize or image.height > resize):
                        image = image.resize((resize, resize))

                    image_bytes = BytesIO()
                    image.save(image_bytes, format='png')
                    image_bytes.seek(0)

                    color_thief = ColorThief(image_bytes)
                    dominant_color = color_thief.get_color(quality=q)
                    ct_tuple = ('ColorThief', '#{:02x}{:02x}{:02x}'.format(*dominant_color))

                    pixels = np.array(image).reshape(-1, 3)
                    median_color = np.median(pixels, axis=0).astype(int)
                    median_tuple = ('Median', '#{:02x}{:02x}{:02x}'.format(*median_color))

                    image.close()
                    image_bytes.close()
                    return (img, ct_tuple, median_tuple)
                except Exception as e:
                    print(f"Error processing {img}: {e}")
                    return None
            def extract_colors(image_files, resize=125, q=4, how_many=25):
                colors_list = []
                colors_list2 = []
                import concurrent.futures 
                with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                    futures = {executor.submit(process_image, img, resize, q): img for img in image_files[:how_many]}
                    for future in concurrent.futures.as_completed(futures):
                        result = future.result()
                        if result is not None:
                            img, ct_tuple, median_tuple = result
                            colors_list.append((img, [ct_tuple]))
                            colors_list2.append((img, [median_tuple]))

                colours = [x[1][0][1] for x in colors_list]
                colours2 = [x[1][0][1] for x in colors_list2]

                def hex_to_rgb_tuple(hex_color):
                    return tuple(int(hex_color[i:i+2], 16) for i in (1, 3, 5))

                def rgb_to_hex(rgb):
                    return '#{:02x}{:02x}{:02x}'.format(*rgb)

                def median_color(hex_colors):
                    rgb_colors = [hex_to_rgb_tuple(c) for c in hex_colors]
                    median_rgb = tuple(int(np.median([c[i] for c in rgb_colors])) for i in range(3))
                    return "Median", rgb_to_hex(median_rgb)

                median_c = median_color(colours)
                kmeans = get_fur_color(colours)
                c_kmeans = get_fur_color(colours2)

                l = [median_c, kmeans, c_kmeans]
                colors_list = []
                return [colors_list], l
            def get_image_files(folder, supported_formats, how_many):
                image_files = []
                subfolder_images = []

                for f in os.listdir(folder):
                    if f.lower().endswith(supported_formats):
                        image_files.append(os.path.join(folder, f))

                if len(image_files) < how_many:
                    for root_dir, _, files in os.walk(folder):
                        if root_dir == folder:
                            continue
                        for f in files:
                            if f.lower().endswith(supported_formats):
                                subfolder_images.append(os.path.join(root_dir, f))
                    image_files.extend(subfolder_images[:max(0, how_many - len(image_files))])
                shuffle(image_files)
                return image_files
            files = get_image_files(dest, formats, sample_size)
            if len(files) == 0:
                return None
            wanted_colors = extract_colors(files, resize=125, q=4, how_many=sample_size)
            wanted_colors1 = [x[1] for x in wanted_colors[1]]
            def hex_to_rgb(hex_color):
                hex_color = hex_color.lstrip('#')
                return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

            def rgb_to_hex(rgb):
                return '#{:02x}{:02x}{:02x}'.format(*rgb)
            
            def enhance_hsv(hex_color, sat_boost):
                r, g, b = [x/255.0 for x in hex_to_rgb(hex_color)]
                h, s, v = colorsys.rgb_to_hsv(r, g, b)
                
                # Boost saturation and clamp to 1.0
                s = min(s * sat_boost, 1.0)
                
                r, g, b = colorsys.hsv_to_rgb(h, s, v)
                return rgb_to_hex((int(r*255), int(g*255), int(b*255)))

            def enhance_bold(hex_color, contrast_factor, sat_boost):
                def boost_contrast(rgb, factor):
                   # Adjust contrast: move each channel away from 128
                   return tuple(max(0, min(255, int(128 + factor*(c - 128)))) for c in rgb)
                # First, boost contrast in RGB space
                rgb = hex_to_rgb(hex_color)
                rgb_contrast = boost_contrast(rgb, contrast_factor)

                # Now convert to HLS to increase saturation further
                r, g, b = [x/255.0 for x in rgb_contrast]
                h, l, s = colorsys.rgb_to_hls(r, g, b)
                s = min(s * sat_boost, 1.0)
                r, g, b = colorsys.hls_to_rgb(h, l, s)

                return rgb_to_hex((int(r*255), int(g*255), int(b*255)))
            
            later = None
            #now = wanted_colors1[1]
            
            lis = []
            
            for x in wanted_colors1:
                x = enhance_hsv(x, sat_boost=1.9)
                x = enhance_bold(x, contrast_factor=1.4, sat_boost=1.7)
                lis.append(x)
            
            #later = enhance_hsv(now, sat_boost=1.9)
            #later = enhance_bold(later, contrast_factor=1.4, sat_boost=1.7)
            # 1.5, 1.3, 1.3 
            # 1.9, 1.4, 1.7
            return lis
        def luminance(hexin):
            color = tuple(int(hexin.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
            r = color[0]
            g = color[1]
            b = color[2]
            hsp = (0.299 * (r**2) + 0.587 * (g**2) + 0.114 * (b**2)) ** 0.5
            if hsp > 210:
                return 'light'
            else:
                return 'dark'
        def darken_color(color, factor=0.8): #Darken a given color by a specified factor
            # Convert hex color to RGB
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)

            # Darken the color
            r = int(r * factor)
            g = int(g * factor)
            b = int(b * factor)

            # Convert back to hex

            return f'#{r:02x}{g:02x}{b:02x}'   
        def reassign_hotkey(d, btn):
            def key_press(event):
                new_hotkey = event.keysym
                for x in destinations:
                    if new_hotkey == x["hotkey"]:
                        return
                        
                self.unbind_all("<KeyPress>")
                d['hotkey'] = new_hotkey
                self.bind_all(f"<KeyPress-{new_hotkey}>", lambda e: filemanager.setDestination(d, e))
                btn.config(text=f"{new_hotkey}: {d['name']}")
                
            old_hotkey = d['hotkey']
            d['hotkey'] = None
            self.unbind_all(f"<KeyPress-{old_hotkey}>")
            btn.config(text=f"?: {d['name']}")

            self.unbind_all("<KeyPress>")
            self.bind_all("<KeyPress>", key_press)         
        
        self.source_entry_field.config(state=tk.DISABLED)
        self.destination_entry_field.config(state=tk.DISABLED)

        for x in self.first_page: # Clear old page buttons from memory.
            x.destroy()

        self.sort_by_date_b.destroy() # Hide sortbydate button after it is no longer needed

         # Bind arrow keys to Navigator.
        arrowkeys = ["<Up>", "<Down>", "<Left>", "<Right>", "<space>", "<Return>"]
        for arrowkey in arrowkeys: # Binding arrow keys to navigator
            self.bind_all(f"{arrowkey}", lambda e: filemanager.navigator.bindhandler(e))

        # Frame to hold the buttons
        buttonframe = tk.Frame(self.leftui,bg=self.main_bg)
        buttonframe.grid(column=0, row=5, sticky="NSEW", pady=5)
        buttonframe.columnconfigure(0, weight=1)
        self.buttonframe = buttonframe

        # Get the destinations and make them buttons!
        if True:
            hotkeys = self.hotkeys
            for key in hotkeys:
                self.unbind_all(key)
    
            if len(destinations) > int((self.leftui.winfo_height()/35)-2):
                buttonframe.columnconfigure(1, weight=1)
            if len(destinations) > int((self.leftui.winfo_height()/15)-4):
                buttonframe.columnconfigure(2, weight=1)
            original_colors = {} #Used to return their color when hovered off
            self.color_change_buttons = []
            
            def change_button_color(*args):
                if not self.color_change_buttons[0][1].get("lis"):
                    return
                color_index = (color_index + 1) % len(self.color_change_buttons[0][1]["lis"])  # Cycle through colors
                for x1 in self.color_change_buttons:
                    x1[0].config(bg=x1[1]["lis"][color_index])  # Change button color
                print("Using option:", color_index)
            def regen_button_color(*args):
                def helper():
                    print("Regenerating buttons.")
                    for x in destinations:
                        try:
                            lis = get_folder_color(x["path"],('.png','.jpg','.jpeg','.webp','.gif'),25)
                            if lis == None:
                                continue
                        except:
                            continue 
                        coolor = lis[0]
                        x["lis"] = lis
                        #coolor = "#000000"
                        if luminance(coolor) == 'dark':
                            fg = self.button_text
                        else:
                            fg = "black"
                        x["btn"].configure(bg=coolor, fg=fg)
                        original_colors[x["btn"]] = {'bg': coolor, 'fg': fg}  # Store both colors
                        original_colors[x["btn"]] = {'bg': x["btn"].cget("bg"), 'fg': x["btn"].cget("fg")}  # Store both colors
                        
                        # Bind hover events for each button
                        x["btn"].bind("<Enter>", lambda e, btn=x["btn"]: btn.config(bg=darken_color(original_colors[btn]['bg']), fg='white'))
                        x["btn"].bind("<Leave>", lambda e, btn=x["btn"]: btn.config(bg=original_colors[btn]['bg'], fg=original_colors[btn]['fg']))  # Reset to original colors
                        buttonframe.update_idletasks()
                    print("Regenerated all buttons.")
                
                Thread(target=helper, daemon=True).start()
        
            self.bind("<KeyPress-k>", change_button_color)
            self.bind("<KeyPress-l>", regen_button_color)
            def test():
                guirow = 1
                guicol = 0
                itern = 0
                for x in destinations:
                    if(itern < len(hotkeys)):
                        newbut = tk.Button(buttonframe, text=hotkeys[itern] + ": " + x['name'], command=lambda x=x: filemanager.setDestination(x, None), anchor="w")
                        newbut.tag = "dest_button"
                        seed(x['name'])
                        self.bind_all(f"<KeyPress-{self.hotkeys[itern]}>", lambda e, x=x: filemanager.setDestination(x, e))
                        x['hotkey'] = self.hotkeys[itern]
                        
                        fg = self.button_text
                        coolor = x["color"]
                        if luminance(coolor) == 'dark':
                            fg = self.button_text
                        else:
                            fg = "black"
                        x["btn"] = newbut
                        newbut.configure(bg=coolor, fg=fg)
                        original_colors[newbut] = {'bg': coolor, 'fg': fg}  # Store both colors
                        newbut.config(font=("Courier", 12))
                    else:
                        newbut = tk.Button(buttonframe, text=x['name'], command=lambda x=x: filemanager.setDestination(x, None), anchor="w")
                    itern += 1

                    newbut.dest = x
                    if guirow > ((self.leftui.winfo_height()/35)-2):
                        guirow = 1
                        guicol += 1
                    newbut.grid(row=guirow, column=guicol, sticky="nsew")
                    newbut.bind("<Button-2>", lambda e, x=x, btn=newbut: (reassign_hotkey(e,x, btn), setattr(self, 'focused_on_secondwindow', False)))
                    newbut.bind("<Button-3>", lambda e, x=x: self.destination_viewer.create_window(e,x))

                    self.color_change_buttons.append((newbut, x))
                    guirow += 1
                    # Store the original colors for all buttons
                    original_colors[newbut] = {'bg': newbut.cget("bg"), 'fg': newbut.cget("fg")}  # Store both colors

                    # Bind hover events for each button
                    newbut.bind("<Enter>", lambda e, btn=newbut: btn.config(bg=darken_color(original_colors[btn]['bg']), fg='white'))
                    newbut.bind("<Leave>", lambda e, btn=newbut: btn.config(bg=original_colors[btn]['bg'], fg=original_colors[btn]['fg']))  # Reset to original colors
            test()
            
        # Make second page buttons
        if True:
            but_t = self.button_text
            but_c = self.button_bg
            but_c_a = self.button_bg_pressed
            but_c_a_t = self.button_text_pressed
            # Frame to hold all new the buttons
            second_frame = tk.Frame(self.leftui,bg=self.main_bg)
            self.second_frame = second_frame
            second_frame.columnconfigure(0, weight=1)
            second_frame.columnconfigure(1, weight=3)
            second_frame.grid(row=0, column=0, sticky="ew")

            # First column
            if True:
                # Save Session BUTTON
                save_session_b = tk.Button(second_frame,text="Save Session",command=lambda: filemanager.savesession(True),
                    bg=but_c, fg=but_t, activebackground = but_c_a, activeforeground=but_c_a_t, relief = tk.RAISED)
                save_session_b.grid(column=0,row=0,sticky="ew")
                
                # Squares Per Page FIELD
                squares_per_page_b = tk.Entry(second_frame, textvariable=self.squares_per_page_intvar, 
                    takefocus=False, bg=self.field_colour, fg=self.field_text)
                if self.squares_per_page_intvar.get() < 0: self.squares_per_page_intvar.set(1) # Won't let you save -1.
                squares_per_page_b.grid(row=1, column=0, sticky="EW",)

            # Second column
            if True:
                # Clear Selection BUTTON
                clear_all_b = tk.Button(second_frame, text="Clear Selection", command=self.fileManager.clear,
                    bg=but_c, fg=but_t, activebackground = but_c_a, activeforeground=but_c_a_t,)
                clear_all_b.grid(row=0, column=1, sticky="EW")
                # Load More Images BUTTON
                load_more_b = tk.Button(second_frame, text="Load More Images", command=self.gridmanager.load_more,
                    bg=but_c, fg=but_t, activebackground = but_c_a, activeforeground=but_c_a_t,)
                load_more_b.grid(row=1, column=1, sticky="EW")
                self.load_more_b = load_more_b
                #self.tooltip = ToolTip(self.load_more_b, msg="test", delay=1, x_offset=10, y_offset=2)
                # Move All BUTTON
                move_all_b = tk.Button(second_frame, text="Move All", command=self.fileManager.moveall,
                    bg=but_c, fg=but_t, activebackground = but_c_a, activeforeground=but_c_a_t,)
                move_all_b.grid(column=1, row=2, sticky="EW")
                
            # Third column
            if True:
                # Frame to hold the buttons in
                toggleable_b  = tk.Frame(self.leftui,bg=self.main_bg)
                self.toggleable_b = toggleable_b
                toggleable_b.grid(row = 1, column = 0, sticky = "ew")
                toggleable_b.columnconfigure(0, weight = 1)
                toggleable_b.columnconfigure(1, weight = 1)
                toggleable_b.columnconfigure(2, weight = 1)
                toggleable_b.columnconfigure(3, weight = 1)
                toggleable_b.columnconfigure(4, weight = 1)


                # Show next BUTTON
                show_next_button = ttk.Checkbutton(toggleable_b, text="Show next", variable=self.show_next, onvalue=True, offvalue=False)
                show_next_button.grid(row=0, column=0, sticky="ew")
                show_next_button.configure(style="Theme_checkbox.TCheckbutton")
                
                # Dock view BUTTON
                dock_view_button = ttk.Checkbutton(toggleable_b, text="Dock view", variable=self.dock_view, onvalue=True, offvalue=False, command=self.change_viewer)
                dock_view_button.grid(row=0, column=1, sticky="ew")
                dock_view_button.configure(style="Theme_checkbox.TCheckbutton")
                
                # Dock side BUTTON
                self.dock_side_button = ttk.Checkbutton(toggleable_b, text="Dock side", variable=self.dock_side, onvalue=True, offvalue=False, command=self.change_dock_side)
                self.dock_side_button.grid(row=0, column=2, sticky="ew")
                self.dock_side_button.configure(style="Theme_checkbox.TCheckbutton")
                
                if self.dock_view.get(): 
                    self.dock_side_button.state(['!disabled'])
                else: 
                    self.dock_side_button.state(['disabled'])

                view_options = ["Show Unassigned", "Show Assigned", "Show Moved", "Show Animated"]
                self.current_view = tk.StringVar(value="Show Unassigned")
                self.current_view.trace_add("write", lambda *args: self.current_view_changed(self.current_view.get()))

                view_menu = tk.OptionMenu(second_frame, self.current_view, *view_options)
                view_menu.config(bg=but_c, fg=but_t,activebackground=but_c_a, activeforeground=but_c_a_t, highlightbackground=but_c, highlightthickness=1)
                view_menu.grid(row = 2, column = 0, sticky = "EW")
            
            # Button to control how image is centered
            if self.centering_button:
                options = ["Center", "Only x centering", "Only y centering", "No centering"]
                preference = tk.StringVar()
                
                centering_b = tk.OptionMenu(toggleable_b, preference, *options)
                centering_b.config(bg=but_c, fg=but_t, activebackground=but_c_a, 
                    activeforeground=but_c_a_t, highlightbackground=self.main_bg, highlightthickness=1)
                centering_b.grid(row=0, column=3, sticky="ew") #0,4

                # If extra buttons is true, we should load the correct text for the centering button.
                if self.viewer_x_centering and self.viewer_y_centering:
                    preference.set("Center")
                elif self.viewer_x_centering and not self.viewer_y_centering:
                    preference.set("Only x centering")
                elif not self.viewer_x_centering and self.viewer_y_centering:
                    preference.set("Only y centering")
                else:
                    preference.set("No centering")
                
                preference.trace_add("write", lambda *args: self.change_centering(preference.get())) # Start tracking for changes
            
            
            if True:
                self.theme_b = tk.OptionMenu(toggleable_b, self.theme, *self.themes.keys())
                self.theme_b.config(bg=but_c, fg=but_t, activebackground=but_c_a, 
                    activeforeground=but_c_a_t, highlightbackground=self.main_bg, highlightthickness=1)
                
                self.theme_b.grid(row=0, column=4, sticky="ew") #0,5
                
                self.theme.trace_add("write", lambda *args: self.change_theme(self.theme.get())) # Start tracking for changes

                

            if True:
                regen_buttons_button = tk.Button(toggleable_b, text="Colors", command=regen_button_color,
                    bg=but_c, fg=but_t, activebackground = but_c_a, activeforeground=but_c_a_t,)
                regen_buttons_button.grid(row=0, column=5, sticky="ew")

        if True:
            #Option for making the buttons change color on hover
            clear_all_b.bind("<Enter>", lambda e: clear_all_b.config(bg=but_c_a, fg=but_c_a_t,))
            clear_all_b.bind("<Leave>", lambda e: clear_all_b.config(bg=but_c, fg=but_t))

            load_more_b.bind("<Enter>", lambda e: load_more_b.config(bg=but_c_a, fg=but_c_a_t,))
            load_more_b.bind("<Leave>", lambda e: load_more_b.config(bg=but_c, fg=but_t))

            move_all_b.bind("<Enter>", lambda e: move_all_b.config(bg=but_c_a, fg=but_c_a_t,))
            move_all_b.bind("<Leave>", lambda e: move_all_b.config(bg=but_c, fg=but_t))

            save_session_b.bind("<Enter>", lambda e: save_session_b.config(bg=but_c_a, fg=but_c_a_t,))
            save_session_b.bind("<Leave>", lambda e: save_session_b.config(bg=but_c, fg=but_t))

            squares_per_page_b.bind("<FocusIn>", lambda e: squares_per_page_b.config(bg=self.field_activated_colour, fg=self.field_text_pressed))
            squares_per_page_b.bind("<FocusOut>", lambda e: (squares_per_page_b.config(bg=self.field_colour, fg=self.field_text), self.focus()))
        
        if self.dock_view.get():
            self.change_viewer()
            self.update()
    
    "Navigation / options" # button actions
    def change_viewer(self):
        "Change which viewer is in use. Dock or secondary window"
        if hasattr(self.fileManager.navigator, "old") and self.fileManager.navigator.old != None:
            old = self.fileManager.navigator.old

        m_frame = self.middlepane_frame
        toppane = self.toppane
        imagegridframe = self.imagegrid
        other_viewer_is_open = self.second_window != None and self.second_window.winfo_exists()
        if m_frame.winfo_width() != 1:
            self.middlepane_width = m_frame.winfo_width() #this updates it before middlepane is closed.

        m_frame.configure(width = self.middlepane_width)
        self.focused_on_secondwindow = False

        if self.dock_view.get():
            self.dock_side_button.state(['!disabled'])
            if other_viewer_is_open: # This also means dock_view was changed, so we should open the previous image displayed, if show_next is on.
                self.close_second_window() # Closes it
                self.displayimage(old)

            self.toppane.forget(imagegridframe) # Reset the GUI.

            if self.dock_side.get():
                toppane.add(m_frame, weight = 0) #readd the middpane
                toppane.add(imagegridframe, weight = 1) #readd imagegrid
            else:
                toppane.add(imagegridframe, weight = 1) #readd imagegrid
                toppane.add(m_frame, weight = 0) #readd the middpane

            # Use standalone viewer
        else:
            self.dock_side_button.state(['disabled'])
            try:
                # Remove and forget the dock viewer pane and image_frame.
                if "middlepane" in [x.rsplit(".", 1)[1] for x in self.toppane.panes()]:
                    self.toppane.forget(m_frame)
                if self.Image_frame1 != None:
                    m_frame.grid_forget()
                    self.Image_frame1.canvas.unbind("<Configure>")
                    self.Image_frame1.close()
                    self.Image_frame1 = None
                    self.displayimage(old) # If something was displayed, we want to display it in standalone viewer.
            except Exception as e:
                print(f"Error in change_viewer: {e}")

    def change_dock_side(self):
        "Change which side you want the dock"
        m_frame = self.middlepane_frame
        toppane = self.toppane
        imagegridframe = self.imagegrid
        imagegrid = self.imagegrid
        if m_frame.winfo_width() == 1:
            return
        #Pane remains at desired width when forgotten from view. It still exists!
        self.middlepane_width = m_frame.winfo_width()
        m_frame.configure(width = self.middlepane_width)
        if self.dock_view.get():
            toppane.forget(m_frame)
            toppane.forget(imagegridframe)
            if self.dock_side.get():
                if self.force_scrollbar:

                    #self.vbar.grid(row=0, column=1, sticky='ns')
                    #imagegrid.configure(yscrollcommand=self.vbar.set)
                    imagegrid.grid(row=0, column=0, padx = max(0, self.square_padx-1), sticky="NSEW")

                    imagegridframe.columnconfigure(1, weight=0)
                    imagegridframe.columnconfigure(0, weight=1)

                toppane.add(m_frame, weight = 0) #readd the middpane
                toppane.add(imagegridframe, weight = 1) #readd imagegrid
            else:
                if self.force_scrollbar:

                    #self.vbar.grid(row=0, column=0, sticky='ns')
                    #imagegrid.configure(yscrollcommand=self.vbar.set)
                    imagegrid.grid(row=0, column=1, padx = max(0, self.square_padx-1), sticky="NSEW")

                    imagegridframe.columnconfigure(0, weight=0)
                    imagegridframe.columnconfigure(1, weight=1)

                toppane.add(imagegridframe, weight = 1) #readd imagegrid
                toppane.add(m_frame, weight = 0) #readd the middpane
    
    def change_centering(self, selected_option): # "Center", "Only x centering", "Only y centering", "No centering"
        "Choose how the image centers itself in the grid"
        if selected_option == "Center":
            self.viewer_x_centering = True
            self.viewer_y_centering = True
        if selected_option == "Only x centering":
            self.viewer_x_centering = True
            self.viewer_y_centering = False
        if selected_option == "Only y centering":
            self.viewer_x_centering = False
            self.viewer_y_centering = True
        if selected_option == "No centering":
            self.viewer_x_centering = False
            self.viewer_y_centering = False
        if self.Image_frame != None or self.Image_frame1 != None:
            self.displayimage(self.fileManager.navigator.old.obj)

    def current_view_changed(self, selected_option):
        "When view is changed, send the wanted list to the gridmanager for rendering"

        mgr = self.gridmanager
        fileManager = self.fileManager
        "When view is changed, tells grid to display that view"
        if selected_option == "Show Unassigned":
            list_to_display = mgr.unassigned
        elif selected_option == "Show Assigned":
            list_to_display = mgr.assigned
        elif selected_option == "Show Moved":
            list_to_display = mgr.moved
        elif selected_option == "Show Animated":
            list_to_display = [x for x in mgr.unassigned if x.ext in fileManager.thumbs.animated_thumb_formats]
        self.gridmanager.change_view(list_to_display)
        fileManager.navigator.view_change()   
    
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

            self.button_text = dict["button_text"]
            self.button_text_pressed = dict["button_text_pressed"]
            # Main
            self.main_bg = dict["main_bg"]
            self.grid_bg = dict["grid_bg"]
            self.viewer_bg = dict["viewer_bg"]
            #Buttons
            self.button_bg = dict["button_bg"]
            self.button_bg_pressed = dict["button_bg_pressed"]
            #Fields
            self.field_colour = dict["field_colour"]
            self.field_text = dict["field_text"]
            self.field_activated_colour = dict["field_activated_colour"]
            self.field_text_pressed = dict["field_text_pressed"]
            #Divider
            self.divider_colour = dict["divider_colour"]
            #Gridsquares
            self.square_text = dict["square_text"]

            self.textbox_size = dict["textbox_size"]
            self.square_padx = dict["square_padx"] # should update imagegrid
            self.square_pady = dict["square_pady"] # should update imagegrid

            but_t = self.button_text
            but_c = self.button_bg
            but_c_a = self.button_bg_pressed
            but_c_a_t = self.button_text_pressed

            self.square_default = dict["square_default"]
            self.square_selected = dict["square_selected"]

            #Main
            self.config(bg=self.main_bg)
            #Recolor frames (main_bg, text_colour)
            self.style.configure("Theme_checkbox.TCheckbutton", background=self.main_bg, foreground=but_t) # Theme for checkbox
            for x in all_children["frame"]:
                if x.winfo_exists():
                    x.config(bg=self.main_bg)

            #Recolor grid (grid_bg, text_colour)
            for x in all_children["frame"]:
                if x.winfo_exists():
                    x.configure(bg=self.grid_bg)
            self.toggleable_b.configure(bg = self.main_bg)
            self.second_frame.configure(bg = self.main_bg)
            self.terminal_frame.configure(bg = self.main_bg)
            self.buttonframe.configure(bg = self.main_bg)
            self.leftui.configure(bg = self.main_bg)
            self.imagegrid.canvas.configure(bg = self.grid_bg)
            
            for x in self.imagegrid.image_items:
                self.imagegrid.canvas.itemconfig(x.ids["rect"], outline=self.square_default, fill=self.square_default)
                self.imagegrid.canvas.itemconfig(x.ids["txt_rect"], outline=self.square_default, fill=self.square_default)
                x.file.color = self.square_default

            for x in self.second_frame.children:
                if "button" in x:
                    widget = self.second_frame.children[x]
                    widget.bind("<Enter>", lambda e, widget=widget: widget.config(bg=but_c_a, fg=but_c_a_t,))
                    widget.bind("<Leave>", lambda e, widget=widget: widget.config(bg=but_c, fg=but_t))

            for x in self.debugs:
                x.configure(bg="#03070b")
            
            #Recolor dock background (canvasimage_background)
            self.middlepane_frame.configure(bg = self.viewer_bg)
            
            #Recolor buttons (button_bg, button_press_colour)
            
            for x in all_children["button"]:
                if x.winfo_exists() and not getattr(x, "tag", None) == "dest_button":
                    x.config(bg = but_c, fg = but_t, activebackground = but_c_a)
    
            for x in all_children["optionmenu"]:
                if x.winfo_exists():
                    x.config(bg = but_c, fg = but_t, 
                        activebackground = but_c_a, activeforeground=but_c_a_t)

            #Recolor fields (text_field_colour, field_text)
            for x in all_children["entry"]:
                if x.winfo_exists():
                    x.config(bg = self.field_colour, fg = self.field_text)
            
            if self.Image_frame != None:
                self.Image_frame.style.configure("bg.TFrame", background=self.viewer_bg)
                self.Image_frame.canvas.config(bg = self.viewer_bg)
                
            #Pane divider (divider_colour)
            self.style.configure('Theme_dividers.TPanedwindow', background=self.divider_colour)  # Panedwindow, the divider colour.
            
            base = self.thumbnailsize
            navigator.actual_gridsquare_width = base + self.square_padx
            navigator.actual_gridsquare_height = base + self.square_pady + self.textbox_size
        
        theme = self.themes[theme_name]
        set_vals(theme)
        navigator.selected(navigator.old)
        self.update()

    def setfocus(self, event):
        event.widget.focus_set()

    "CanvasImage" # Viewers
    def displayimage(self, obj, caller=None):
        "Display image in viewer"
        if obj is None: return
        
        if caller == "arrow":
            if self.debounce:
                self.after_cancel(self.debounce)
                self.debounce = None

            elapsed = perf_counter() - self.last_call_time
            if elapsed > 0.25:
                print(elapsed)
                self.last_call_time = perf_counter()
                pass
            else:
                self.last_call_time = perf_counter()
                self.debounce = self.after(250, self.displayimage, obj, "last")
                return
        elif caller == "last": pass
        else: pass
        
        # Middlepane width refresh
        m_frame = self.middlepane_frame
        if m_frame.winfo_width() != 1:
            self.middlepane_width = m_frame.winfo_width()

        if self.dock_view.get(): # Dock viewer
            # do rescale and center inside canvasimage, not here.
            # pass all needed info to canvasimage in a dict, not self, gui, etc.
            if self.Image_frame1 != None:
                if self.after_id:
                    self.after_cancel(self.after_id)
                    self.after_id = None
                if self.Image_frame1.after_id:
                    self.Image_frame1.after_cancel(self.Image_frame1.after_id)
                    self.Image_frame1.after_id = None
                self.Image_frame1.unbind('<Configure>')
                if self.Image_frame1 != None:
                    self.Image_frame1.grid_forget()
                    #m_frame.update()
                    self.Image_frame1.close()
                    self.Image_frame1 = None

            Image_frame1 = CanvasImage(m_frame, self, f"{self.middlepane_width}x{self.winfo_height()}", self.viewer_bg)
            Image_frame1.grid(row = 0, column = 0, sticky = "NSEW")
            self.after_id = self.after_idle(Image_frame1.set, obj)
            self.Image_frame1 = Image_frame1
            
                
        else: # Standalone image viewer
            start = perf_counter()
            if self.second_window != None and self.second_window.winfo_exists():
                self.viewer_geometry = self.second_window.winfo_geometry()
                if self.after_id:
                    self.after_cancel(self.after_id)
                    self.after_id = None
                    print("after id cancelled")
                if self.Image_frame.after_id:
                    self.Image_frame.after_cancel(self.Image_frame.after_id)
                    self.Image_frame.after_id = None
                    print("after id cancelled2")

                self.second_window.unbind('<Configure>')
                if self.Image_frame != None:
                    self.Image_frame.grid_forget()
                    self.Image_frame.close()
                    self.Image_frame = None
            else:
                self.second_window = tk.Toplevel() #create a new window

                second_window = self.second_window
                second_window.geometry(self.viewer_geometry)
                second_window.configure(bg = self.main_bg)
                second_window.transient(self)
                second_window.update()
                second_window.bind("<Button-3>", self.close_second_window)
                second_window.protocol("WM_DELETE_WINDOW", self.close_second_window)

            self.second_window.title("Image: " + obj.path)
            geo = self.viewer_geometry.split('+', 1)[0]
            new = CanvasImage(self.second_window, self, geo, self.main_bg)
            new.grid(row = 0, column = 0, sticky = "NSEW")
            #new.set(obj)
            #new.update()
            self.after_id = self.after_idle(new.set, obj)
            self.Image_frame = new

        self.focused_on_secondwindow = True
        

    "Exit function" # How we exit the program and close windows
    def closeprogram(self): ### thread???
        from tkinter.messagebox import askokcancel
        def purge_cache():
            if os.path.isdir(data_dir):
                with os.scandir(data_dir) as entries:
                    ids = {x.id for x in gridmanager.gridsquarelist}
                    for entry in entries:
                        if entry.is_file():
                            id = entry.name.rsplit(".", 1)[0]
                            if id not in ids:
                                try:
                                    os.remove(entry.path)
                                except Exception as e:
                                    print("Failed to remove old cached thumbnails from the data directory.", e)
        def test():
            if thumbs.gen_thread != None and thumbs.gen_thread.is_alive():
                thumbs.gen_thread.join()
            if gridmanager.assigned and not askokcancel("Designated but Un-Moved files, really quit?", "You have destination designated, but unmoved files. (Simply cancel and Move All if you want)"):
                return
                
            self.close_second_window()
            if hasattr(dest_viewer, "destwindow"):
                dest_viewer.close_window()
            filemanager.saveprefs(self)
            purge_cache()
            self.quit()
            #os._exit(0) # Emergencies

        gridmanager = self.gridmanager
        filemanager = self.fileManager
        dest_viewer = filemanager.gui.destination_viewer
        thumbs = filemanager.thumbs
        animate = filemanager.animate
        data_dir = filemanager.data_dir

        filemanager.thread_is_exiting = True
        filemanager.shut_down = True
        thumbs.block.set()
        animate.running.clear()
        Thread(target=test, daemon=True).start()   
    
    def close_second_window(self, event=None):
        def close(a ,b):
            if a != None:
                a.grid_forget()
                a.close()
            self.after_idle(b.destroy)

        if hasattr(self, 'Image_frame1'):
            self.middlepane_frame.grid_forget()
            if self.Image_frame1 != None:
                self.Image_frame1.close()
                self.Image_frame1 = None

        if self.second_window != None and self.second_window.winfo_exists():
            self.second_window.unbind('<Configure>')
            self.viewer_geometry = self.second_window.winfo_geometry()
            if self.after_id:
                self.after_cancel(self.after_id)
                self.after_id = None
            if self.Image_frame.after_id:
                self.Image_frame.after_cancel(self.Image_frame.after_id)
                self.Image_frame.after_id = None

            Thread(target=close, args=(self.Image_frame, self.second_window), daemon=True).start()

    def filedialogselect(self, target, type):
        from tkinter import filedialog as tkFileDialog
        if type == "d":
            path = tkFileDialog.askdirectory()
        elif type == "f":
            d = tkFileDialog.askopenfile(initialdir=os.getcwd(
            ), title="Select Session Data File", filetypes=(("JavaScript Object Notation", "*.json"),))
            path = d.name
        if path == "":
            return
        if isinstance(target, tk.Entry):
            target.delete(0, tk.END)
            target.insert(0, path)

    "Exclusions window" # Exclusions window
    def excludeshow(self):
        excludewindow = tk.Toplevel()
        excludewindow.winfo_toplevel().title(
            "Folder names to ignore, one per line. This will ignore sub-folders too.")
        excludetext = tkst.ScrolledText(excludewindow, bg=self.main_bg, fg=self.button_text)
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

class GridManager:
    "Handles the gridsqures in the imagegrid"
    def __init__(self, fileManager):
        self.fileManager = fileManager
        self.gui = fileManager.gui

        self.gridsquarelist = set()
        self.displayedset = set() # quick identity checks
        self.unassigned = set()
        self.assigned = set()
        self.moved = set()

        self.style = ttk.Style()
    
    def load_session(self, unassigned, moved_or_assigned):
        self.fileManager.timer.start()
        gui = self.gui
        for obj in moved_or_assigned:
            gridsquare = self.makegridsquare(gui.imagegrid, obj)
            self.gridsquarelist.add(gridsquare)
            if obj.moved:
                self.moved.add(gridsquare) ### make them have green border, but correct color canvas?
            elif obj.dest:
                self.assigned.add(gridsquare)
            else:
                print("error, session list moved or append is in unassigned")
                self.unassigned.add(gridsquare)

        for obj in unassigned:
            gridsquare = self.makegridsquare(gui.imagegrid, obj)
            self.gridsquarelist.add(gridsquare)
            self.unassigned.add(gridsquare)

        self.add_squares(self.unassigned) # Will load thumbs from cache and generate framedata & frames
        
        for square in self.assigned:
            for dest in self.fileManager.destinations:
                if square.obj.dest == dest['path']:
                    square.obj.setdest(dest)
                    square.obj.color = dest['color']
                    self.change_square_color(obj, obj.color)
                    break

        for square in self.moved:
            for dest in self.fileManager.destinations:
                if dest['path'] in square.obj.path: #if dest["path"] in folder
                    square.obj.setdest(dest)
                    square.obj.color = dest['color']
                    self.change_square_color(obj, obj.color)
                    break
    
    def load_more(self, amount=None) -> None:
        gui = self.gui
        filemanager = self.fileManager
        filelist = filemanager.imagelist

        if gui.current_view.get() not in ("Show Unassigned", "Show Animated"): return
        
        amount = amount if amount else gui.squares_per_page_intvar.get()
        items = min(len(filelist), amount) # Cap to remaining filelist length.

        if amount == 0: return
        if items == 0:
            gui.load_more_b.configure(text="No More Images!",bg = "#DD3333")
            return
        
        sublist = filelist[-items:]
        sublist.reverse()
        del filelist[-items:]

        gui.imagegrid.update()
        self.unassigned.update(sublist)
        self.gridsquarelist.update(sublist)
        temp = len(self.displayedset)
        bypass_update = True if gui.current_view.get() == "Show Animated" else False
        self.add_squares(sublist, bypass_update)

        gui.images_left_stats_strvar.set(
            f"Left: {len(self.assigned)}/{len(self.gridsquarelist)-len(self.assigned)-len(self.moved)}/{len(filelist)}")
        
        if gui.current_view.get() == "Show Animated":
            not_animated = [x.frame for x in sublist if (x.ext not in self.fileManager.thumbs.animated_thumb_formats and x.ext not in self.fileManager.thumbs.video_formats)]
            self.remove_squares(not_animated, unload=True, reflow=False)
            self.gui.imagegrid.reflow_from_index(temp)

    def change_view(self, squares) -> None:
        "Remove all squares from grid, but add them back without unloading according how they should be ordered."
        self.fileManager.thread_is_exiting = True
        self.fileManager.thumbs.block.set()
        not_in_new_list = [x for x in self.displayedset if x.file not in squares] # Unload their thumbs and frames.
        in_both_lists = [x for x in self.displayedset if x.file in squares] # Remove them from gridview. But dont unload

        if not_in_new_list: # Normal remove
            self.remove_squares(not_in_new_list, unload=True)
        if in_both_lists: # Remove but without unloading from memory. We want to readd these.
            self.remove_squares(in_both_lists, unload=False)
        if squares: # Read all
            self.add_squares(squares) # This will know if thumb is loaded or not and will reload as needed.
 
    def add_squares(self, sublist, bypass_update=False) -> None:
        "Adds squares to grid, displayedlist, and reloads them"
        self.gui.imagegrid.load_images(sublist, bypass_update)
        self.displayedset.update(self.gui.imagegrid.image_items)
        self.fileManager.thumbs.generate(sublist) # Threads the reloading process.
    def remove_squares(self, squares: list, unload, reflow=True) -> None:
        """
        Remove frame from GRID, DISPLAYEDIST.
        Unload thumbs and frames from memory.
        Removes imagefile.thumb, the only ref file of the thumbnail, to let it get garbage collected.
        Removes imagefile.frames, frametimes, sets lazy_loading to False (To stop animate.add_animation.lazy)
        """
        fileManager = self.fileManager

        for gridsquare in squares:
            self.displayedset.remove(gridsquare)

            start_idx = None
            obj = gridsquare.file                
            obj.frame = None
            index = self.gui.imagegrid.image_items.index(gridsquare)
            if start_idx == None: start_idx = index
            start_idx = min(index, start_idx)

            self.gui.imagegrid.canvas.delete(gridsquare.tag)
            self.gui.imagegrid.image_items.remove(gridsquare)
            del self.gui.imagegrid.item_to_entry[gridsquare.ids["rect"]]

            if unload and not obj.destframe:
                obj.thumb = None
                if obj.frames:
                    obj.frames.clear()
                    obj.frametimes.clear()
                    obj.lazy_loading = False # control flag in animate.

        start_idx = 0 if not unload else start_idx
        if start_idx != None and reflow:
            self.gui.imagegrid.reflow_from_index(start_idx)

        if fileManager.concurrent_frames >= fileManager.max_concurrent_frames:
            fileManager.thumbs.block.set() # thumbs.gen_frames halts if max_concurrent frames is reached. block.wait() keeps the thread open and alive.
                                                # block.set() allows the thread to continue,

    def change_square_color(self, obj, color, outline=False, fill=False):
        if obj.frame:
            if outline:
                self.gui.imagegrid.canvas.itemconfig(obj.frame.ids["rect"], outline=color)
            if fill:
                self.gui.imagegrid.canvas.itemconfig(obj.frame.ids["rect"], fill=color)
        if obj.destframe:
            obj.destframe.configure(highlightcolor = color,  highlightbackground = color) # Trying to access destroyed destsquare? # If dest is closed, remove self.old if any frame was there.
            obj.destframe.canvas.configure(bg=color, highlightcolor=color, highlightbackground = color)
