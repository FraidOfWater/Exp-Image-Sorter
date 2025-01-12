import os

from threading import Thread
from math import floor, sqrt
from random import seed
from time import time, perf_counter
from functools import partial

import logging
import psutil
from gc import collect

from vlc import Instance

import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
import tkinter.scrolledtext as tkst
from tkinter.ttk import Panedwindow
from tkinter.messagebox import askokcancel
from tkinter import filedialog as tkFileDialog
from tktooltip import ToolTip

from canvasimage import CanvasImage
from destination_viewer import Destination_Viewer

logger = logging.getLogger("GUI")
logger.setLevel(logging.WARNING)  # Set to the lowest level you want to handle
handler = logging.StreamHandler()
handler.setLevel(logging.WARNING)
formatter = logging.Formatter('%(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

throttle_time = None
last_scroll_time = None
last_scroll_time2 = None
current_scroll_direction = -1
flag1 = [] #?
flag_len = 1
last_row_length = 0


class GUIManager(tk.Tk): #Main window
    "Initialization"
    def __init__(self, fileManager) -> None:
        super().__init__()
        self.fileManager = fileManager
        self.vlc_instance = Instance('--quiet')

        self.focused_on_secondwindow = False # Helper attribute for navigator
        self.buttons = [] # Buttons

        "Debugging / Stats"
        if True: # move most to their dedicated spots next to their buttons.
            self.do_anim_loading_colors = True
            self.do_debug_terminal = True

            self.current_ram_strvar = tk.StringVar(value="RAM: 0 MB") # RAM: 95.34 MB
            self.images_sorted = tk.IntVar(value=0) #?
            self.images_sorted_strvar = tk.StringVar(value=f"Sorted: {self.images_sorted.get()}") # Sorted: 1953
            self.animation_stats = tk.StringVar(value="Anim: 0/100") # Anim: displayedlist with frames/displayedlist with framecount/(queue)
            self.resource_limiter = tk.StringVar(value="0/1000") # Frames: frames + frames_dest / max

            "Throttling"
            self.displayqueue = None # Stores last image called by navigator. Used for throttling of displayimage.
            self.last_time = None # Last time (perf_counter()) displayimage was called. Used for throttling of displayimage.
            self.times = [] # Stores time periods between calls of displayimage. Calculates average, length is capped at 5. Used for debugging.

        "Preferences file" #DEFAULT VALUES FOR PREFS.JSON. If there is no prefs file, prefs are generated from this.
        if True:
            #Paths
            self.source_folder = ""
            self.destination_folder = ""
            self.sessionpathvar = tk.StringVar() # Session save location

            #Preferences
            self.thumbnailsize = 256
            self.hotkeys = "123456qwerty7890uiopasdfghjklzxcvbnm"
            self.centering_button = True
            self.force_scrollbar = True
            self.page_mode = False # Scroll a whole page or no?
            self.auto_load = True

            #Technical preferences
            self.filter_mode =  "BILINEAR"
            self.quick_preview_size_threshold = 5 # Size at which we start to buffer the image to load the displayimage faster. We use NEAREST, then when LANCZOS is ready, we swap it to that.
            #threads # Exlusively for fileManager
            #autosave # Exlusively for fileManager

            #Customization (MISC) (PADDING AND COLOR FOR IMAGE CONTAINER)
            self.checkbox_height = 25
            self.gridsquare_padx = 2
            self.gridsquare_pady = 2
            self.text_box_colour =                  "white"
            self.text_box_selection_colour  =       "blue"
            self.imageborder_default_colour =       "#303276"
            self.imageborder_selected_colour =      "blue"
            self.imageborder_locked_colour =        "yellow"

            #DEFAULT Customizations
            # Dark Mode

            # Midnight Blue (BRIGHT SELECTION)
            self.main_colour =              '#202041'
            self.grid_background_colour =   '#303276'
            self.canvasimage_background =   '#141433'

            self.whole_box_size =               0 #Selection border on or off
            self.square_border_size =           0

            self.square_colour =            '#303276'
            self.square_text_colour =       'white'
            self.square_text_box_colour =   '#303276'
            self.square_text_box_selection_colour = "#888BF8"
            self.square_text_box_locked_colour =    "#202041"

            self.imagebox_default_colour =      "#303276"
            self.imagebox_selection_colour =    "#888BF8"
            self.imagebox_locked_colour =       "#202041"

            self.button_colour =            '#24255C'
            self.button_press_colour =      '#303276'
            self.text_colour =              'white'
            self.pressed_text_colour =      'white'

            self.text_field_colour =        '#303276'
            self.text_field_text_colour =   'white'
            self.text_field_activated_colour =      '#888BF8'
            self.text_field_activated_text_colour = 'black'

            self.pane_divider_colour =      'grey'

            #GUI CONTROLLED PREFRENECES
            self.squares_per_page_intvar = tk.IntVar(value=120)
            self.sort_by_date_boolvar = tk.BooleanVar()
            self.viewer_x_centering = True
            self.viewer_y_centering = True
            self.show_next = tk.BooleanVar(value=True)
            self.dock_view = tk.BooleanVar(value=True)
            self.dock_side = tk.BooleanVar(value=True)
            #Default window positions and sizes
            self.main_geometry = (str(self.winfo_screenwidth()-5)+"x" + str(self.winfo_screenheight()-120)+"+0+60")
            self.viewer_geometry = str(int(self.winfo_screenwidth()*0.80)) + "x" + str(self.winfo_screenheight()-120)+"+365+60"
            self.destpane_geometry = str(int(self.winfo_screenwidth() * 0.80)) + "x" + str(self.winfo_screenheight() - 120) + "+365+60"
            self.leftpane_width = 363
            self.middlepane_width = 363
            ##END OF PREFS

            self.actual_gridsquare_width = self.thumbnailsize + self.gridsquare_padx + self.square_border_size*2 + self.whole_box_size*2
            self.actual_gridsquare_height = self.thumbnailsize + self.gridsquare_pady + self.square_border_size*2 + self.whole_box_size*2 + self.checkbox_height
    
    def show_ram_usage(self, old=None):
        def get_memory_usage():
            # Get the current process
            process = psutil.Process()

            # Get memory info
            memory_info = process.memory_info()

            # Return the RSS (Resident Set Size) in bytes
            return (memory_info.rss)
        self.current_ram_strvar.set(f"RAM: {get_memory_usage() / (1024 ** 2):.2f} MB")
        frames = 0
        if hasattr(self.destination_viewer, "displayedlist"):
            test = self.gridmanager.gridsquarelist + self.destination_viewer.displayedlist
        else: test = self.gridmanager.gridsquarelist
        for x in test:
            frames += len(x.obj.frames)
            frames += len(x.obj.frames_dest)
        stri = f"{frames}, {len(self.fileManager.thumbs.gen_queue)}"
        if stri != old:
            print(stri)

        "Anim: displayedlist with frames/displayedlist with framecount/(queue)"
        temp = [x for x in self.gridmanager.displayedlist if x.obj.frametimes]
        self.animation_stats.set(f"Anim: {len(self.fileManager.animate.running)}/{len(temp)}")

        "Frames: frames + frames_dest / max"
        temp = [x.obj.frames for x in self.gridmanager.gridsquarelist if x.obj.frames]
        temp2 = [x.obj.frametimes for x in self.gridmanager.gridsquarelist if x.obj.frametimes]
        c = 0
        c1 = 0
        for x in temp:
            c += len(x)
        for x in temp2:
            c1 += len(x)
        self.resource_limiter.set(f"{c}/{c1}")

        self.after(333, self.show_ram_usage, stri)
    def manage_lines(self, input):
        self.text_widget.configure(state="normal")
        self.text_widget.insert(tk.END, f"{input}\n") 

        lines = self.text_widget.get("1.0", tk.END).strip().split("\n")

        if len(lines) > 5: # Remove old lines
            del lines[1]
            self.text_widget.delete("1.0", tk.END)
            self.text_widget.insert(tk.END, "\n".join(lines) + "\n")

        self.text_widget.see(tk.END)
        self.text_widget.configure(state="disabled")
    
    def manage_lines2(self, input, first=False):
        self.text_widget2.configure(state="normal")
        if first:
            self.text_widget2.delete("1.0", tk.END)
        self.text_widget2.insert(tk.END, f"{input}\n") 

        if first == False:
            lines = self.text_widget2.get("1.0", tk.END).strip().split("\n")
            if len(lines) > 2: # Remove old lines
                del lines[1]
                self.text_widget2.delete("1.0", tk.END)
                self.text_widget2.insert(tk.END, "\n".join(lines) + "\n")

        self.text_widget2.see(tk.END)
        self.text_widget2.configure(state="disabled")
    
    def manage_lines3(self, input):
        self.text_widget3.configure(state="normal")
        self.text_widget3.delete("1.0", tk.END)
        self.text_widget3.insert(tk.END, f"{input}\n") 
        self.text_widget3.see(tk.END)
        #self.text_widget3.configure(state="disabled")
    def save_text(self, *args):
        if hasattr(self, "Image_frame"):
            self.saved_text = self.text_widget3.get("1.0", tk.END).strip()
            self.text_widget3.delete("1.0", tk.END)
            self.text_widget3.insert(tk.END, f"{self.saved_text}")
            obj = self.Image_frame.obj
            if self.Image_frame:
                self.middlepane_frame.grid_forget()
                self.Image_frame.canvas.unbind("<Configure>")
                self.Image_frame.destroy()
                del self.Image_frame
                self.after(2000, lambda: obj.rename(self.saved_text, self.gridmanager))
                

    def initialize(self): #
        "Initializating GUI after we get the prefs from filemanager."
        self.geometry(self.main_geometry)

        #Styles
        self.smallfont = tkfont.Font(family='Helvetica', size=10)
        self.style = ttk.Style()
        self.style.configure('Theme_dividers.TPanedwindow', background=self.pane_divider_colour)  # Panedwindow, the divider colour.
        self.style.configure("Theme_checkbox.TCheckbutton", background=self.main_colour, foreground=self.text_colour, highlightthickness = 0) # Theme for checkbox
        self.style.configure("Theme_square.TCheckbutton", background=self.grid_background_colour, foreground=self.text_colour)
        
        # Paned window that holds the almost top level stuff.
        self.toppane = Panedwindow(self, orient="horizontal")
        self.toppane.pack(expand=True)

        # Frame for the left hand side that holds the setup and also the destination buttons.
        self.leftui = tk.Frame(self.toppane, width=self.leftpane_width, bg=self.main_colour)
        self.leftui.grid_propagate(False) #to turn off auto scaling.
        self.leftui.columnconfigure(0, weight=1)
        self.leftui.rowconfigure(5, weight=1)

        self.toppane.add(self.leftui, weight=0) # 0 here, it stops the divider from moving itself.
        #The divider pos is saved by prefs, this complicates it, so auto scaling based on text amount in source and dest folder is disabled.
        
        self.first_page_buttons() # This setups all the buttons and text

        # Start the grid setup
        self.middlepane_frame = tk.Frame(self.toppane, bg=self.canvasimage_background, width = self.middlepane_width) # holds dock

        imagegridframe = tk.Frame(self.toppane,bg=self.grid_background_colour)
        imagegridframe.grid(row=0, column=2, sticky="NSEW") #this is in second so content frame inside this.
        self.imagegridframe = imagegridframe

        self.imagegrid = tk.Text(imagegridframe, wrap='word', borderwidth=0,
                                 highlightthickness=0, state="normal", background=self.grid_background_colour)
        
        vbar = tk.Scrollbar(imagegridframe, orient='vertical',command=lambda *args: throttled_yview(self.imagegrid, self.page_mode, *args))
        self.vbar = vbar

        self.imagegrid.configure(state="disabled")

        self.imagegrid.bind("<Up>", lambda e: "break")
        self.imagegrid.bind("<Down>", lambda e: "break")
        self.imagegrid.bind("<MouseWheel>", lambda e: "break")
        self.imagegrid.bind("<MouseWheel>", partial(bindhandler, self.imagegrid, "scroll1"))

        # Set the correct side for the dock view.
        if self.force_scrollbar:
            self.vbar.grid(row=0, column=1, sticky='ns')
            self.imagegrid.configure(yscrollcommand=self.vbar.set)

        self.imagegrid.grid(row=0, column=0, padx = max(0, self.gridsquare_padx-1), sticky="NSEW")
        self.imagegridframe.rowconfigure(1, weight=0)
        self.imagegridframe.rowconfigure(0, weight=1)
        self.imagegridframe.columnconfigure(1, weight=0)
        self.imagegridframe.columnconfigure(0, weight=1)
        self.toppane.add(self.imagegridframe, weight=1)

        self.toppane.grid(row=0, column=0, sticky="NSEW")
        self.toppane.configure(style='Theme_dividers.TPanedwindow')

        self.columnconfigure(0, weight=10)
        self.columnconfigure(1, weight=0)
        self.rowconfigure(0, weight=10)
        self.rowconfigure(1, weight=0)

        self.protocol("WM_DELETE_WINDOW", self.closeprogram)
        self.winfo_toplevel().title("Simple Image Sorter: QOL")

        self.destination_viewer = Destination_Viewer(self.fileManager)
        self.gridmanager = GridManager(self.fileManager)
    def first_page_buttons(self):
        "Creates and places the buttons for the first page"
        # Description text
        first_page = []
        self.first_page = first_page

        self.panel = tk.Label(self.leftui, wraplength=350, justify="left", bg=self.main_colour,fg=self.text_colour, text="""

                Select a Source Directory:
Choose a folder to search for images,
All subfolders will be scanned as well.

                Set the Destination Directory:
Choose a folder to sort into,
The folder must contain subfolders, these are the folders you sort into.

                Exclusions:
One per line, no commas.

                Loading Images:
To load more images, press the "Add Files" button. Choose how many images are added in the program settings.

                Right-Click:
on Destination Buttons,
to see which images are assigned to them,
(Does not include moved)

                Right-Click:
on Thumbnails,
to view a zoomable full-size image,
(Note that you cannot zoom gifs or webps.)

                Enter / Left-Click:
on thumbnails or in viewer,
to lock the image, so you can
zoom and pan using navigation keys.
(ctrl, shift)

                Preferences:
Choose preferences inside prefs.json,
You can change the hotkeys.
You can customize most elements.
You can change thumbnailsize
(Adjust maximum name length suit to you).
You can force scrollbars on/off for the imagegrid.
You can do scrolling by pages.

                Acknowledgments:
Special thanks to FooBar167 on Stack Overflow for the advanced and memory-efficient Zoom and Pan Tkinter class.
        """
                              )
        self.panel.grid(row=3, column=0, columnspan=200, rowspan=200, sticky="NSEW")
        first_page.append(self.panel)

        # Initial view buttons
        if True: 
            # Initial buttons you see are in this frame
            first_frame = tk.Frame(self.leftui,bg=self.main_colour)
            first_frame.columnconfigure(1, weight=1)
            first_frame.grid(row=0, column=0, sticky="ew")

            # Third column
            if True:
                # Manage exlusions
                exclusions_b = tk.Button(first_frame, text="Manage Exclusions", command=self.excludeshow,
                    bg=self.button_colour, fg=self.text_colour, activebackground = self.button_press_colour, activeforeground=self.pressed_text_colour)
                
                # New Session
                new_session_b = tk.Button(first_frame, text="New Session", command=partial(self.fileManager.validate),
                    bg=self.button_colour, fg=self.text_colour, activebackground = self.button_press_colour, activeforeground=self.pressed_text_colour)
                
                # Load Session
                load_session_b = tk.Button(first_frame, text="Load Session", command=self.fileManager.loadsession,
                    bg=self.button_colour, fg=self.text_colour, activebackground = self.button_press_colour, activeforeground=self.pressed_text_colour)
                
                exclusions_b.grid(row=0, column=2, sticky="ew")
                new_session_b.grid(row=1, column=2, sticky="ew")
                load_session_b.grid(row=3, column=2, sticky='ew')

                first_page.append(exclusions_b)
                first_page.append(new_session_b)
                first_page.append(load_session_b)
            # Second column
            if True:
                # Source field
                self.source_entry_field = tk.Entry(first_frame, takefocus=False,
                    background=self.text_field_colour, foreground=self.text_field_text_colour)  # scandirpathEntry
                       
                # Dest field
                self.destination_entry_field = tk.Entry(first_frame, takefocus=False,
                    background=self.text_field_colour, foreground=self.text_field_text_colour)  # dest dir path entry
                      
                # Session field
                session_entry_field = tk.Entry(first_frame, takefocus=False, textvariable=self.sessionpathvar,
                    background=self.text_field_colour, foreground=self.text_field_text_colour)
                
                self.source_entry_field.grid(row=0, column=1, sticky="ew", padx=2)
                self.destination_entry_field.grid(row=1, column=1, sticky="ew", padx=2)
                session_entry_field.grid(row=3, column=1, sticky='ew', padx=2)

                self.source_entry_field.insert(0, self.source_folder)
                self.destination_entry_field.insert(0, self.destination_folder)

                first_page.append(session_entry_field)
            # First column
            if True:
                # Source folder button
                source_b = tk.Button(first_frame, text="Source Folder:", command=partial(self.filedialogselect, self.source_entry_field, "d"),
                    bg=self.button_colour, fg=self.text_colour, activebackground = self.button_press_colour, activeforeground=self.pressed_text_colour)
                
                # Destination folder button
                destination_b = tk.Button(first_frame, text="Destination Folder:", command=partial(self.filedialogselect, self.destination_entry_field, "d"),
                    bg=self.button_colour, fg=self.text_colour, activebackground = self.button_press_colour, activeforeground=self.pressed_text_colour)
                
                # Session file button
                session_b = tk.Button(first_frame, text="Session Data:", command=partial(self.filedialogselect, session_entry_field, "f"),
                    bg=self.button_colour, fg=self.text_colour, activebackground = self.button_press_colour, activeforeground=self.pressed_text_colour)
                
                source_b.grid(row=0, column=0, sticky="e")
                destination_b.grid(row=1, column=0, sticky="e")
                session_b.grid(row=3, column=0, sticky='e')

                first_page.append(source_b)
                first_page.append(destination_b)
                first_page.append(session_b)
            
            # Sort by date checkbox
            self.sort_by_date_b = ttk.Checkbutton(self.leftui, text="Sort by Date", variable=self.sort_by_date_boolvar, onvalue=True, offvalue=False, style="Theme_checkbox.TCheckbutton")
            self.sort_by_date_b.grid(row=4, column=0, sticky="w", padx=25) ### self.leftui?

        # Option for making the buttons change color on hover. Can be set in prefs. 
        if True:
            # Third column
            exclusions_b.bind("<Enter>", lambda e: exclusions_b.config(bg=self.button_press_colour, fg=self.pressed_text_colour))
            exclusions_b.bind("<Leave>", lambda e: exclusions_b.config(bg=self.button_colour, fg=self.text_colour))

            new_session_b.bind("<Enter>", lambda e: new_session_b.config(bg=self.button_press_colour, fg=self.pressed_text_colour))
            new_session_b.bind("<Leave>", lambda e: new_session_b.config(bg=self.button_colour, fg=self.text_colour))

            load_session_b.bind("<Enter>", lambda e: load_session_b.config(bg=self.button_press_colour, fg=self.pressed_text_colour))
            load_session_b.bind("<Leave>", lambda e: load_session_b.config(bg=self.button_colour, fg=self.text_colour))

            # Second column
            self.source_entry_field.bind("<FocusIn>", lambda e: self.source_entry_field.config(bg=self.text_field_activated_colour, fg=self.text_field_activated_text_colour))
            self.source_entry_field.bind("<FocusOut>", lambda e: self.source_entry_field.config(bg=self.text_field_colour, fg=self.text_field_text_colour))

            self.destination_entry_field.bind("<FocusIn>", lambda e: self.destination_entry_field.config(bg=self.text_field_activated_colour, fg=self.text_field_activated_text_colour))
            self.destination_entry_field.bind("<FocusOut>", lambda e: self.destination_entry_field.config(bg=self.text_field_colour, fg=self.text_field_text_colour))

            session_entry_field.bind("<FocusIn>", lambda e: session_entry_field.config(bg=self.text_field_activated_colour, fg=self.text_field_activated_text_colour))
            session_entry_field.bind("<FocusOut>", lambda e: session_entry_field.config(bg=self.text_field_colour, fg=self.text_field_text_colour))

            # Third column
            source_b.bind("<Enter>", lambda e: source_b.config(bg=self.button_press_colour, fg=self.pressed_text_colour))
            source_b.bind("<Leave>", lambda e: source_b.config(bg=self.button_colour, fg=self.text_colour))

            destination_b.bind("<Enter>", lambda e: destination_b.config(bg=self.button_press_colour, fg=self.pressed_text_colour))
            destination_b.bind("<Leave>", lambda e: destination_b.config(bg=self.button_colour, fg=self.text_colour))

            session_b.bind("<Enter>", lambda e: session_b.config(bg=self.button_press_colour, fg=self.pressed_text_colour))
            session_b.bind("<Leave>", lambda e: session_b.config(bg=self.button_colour, fg=self.text_colour))

        # Debug Terminal and Stats
        if self.do_debug_terminal:
            self.statsframe = tk.Frame(self.leftui, bg=self.main_colour)
            self.statsframe.grid(column=0, row=5, sticky="SW")
            self.statsframe.columnconfigure(0, weight=1)
            self.statsframe.rowconfigure(0, weight=1)
            self.statsframe.columnconfigure(1, weight=1)
            self.statsframe.rowconfigure(1, weight=1)
            self.statsframe.columnconfigure(2, weight=1)
            self.statsframe.rowconfigure(2, weight=1)


            "TERMINAL"
            terminal_frame = tk.Frame(self.statsframe, bg=self.main_colour)
            terminal_frame.grid(row = 2, sticky="NSEW")
            terminal_frame.columnconfigure(0, weight=1)#
            terminal_frame.rowconfigure(0, weight=1)#
            terminal_frame.columnconfigure(1, weight=1)#
            terminal_frame.rowconfigure(1, weight=1)#
            terminal_frame.columnconfigure(2, weight=1)#
            terminal_frame.rowconfigure(2, weight=1)#

            # Create a Text widget for terminal output
            self.text_widget = tk.Text(terminal_frame, width=10000, height=6, bg="#03070b", fg = "#6a858a")
            self.text_widget.grid(row = 0, sticky="EW")
            self.text_widget.configure(state="disabled")

            "LABELS" # Main frame
            label_frame = tk.Frame(self.statsframe, bg=self.main_colour)
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

            self.images_left_stats_strvar = tk.StringVar(value="Left: 1/100/100") # Assigned/Displayed/Imagelist
            left_label = tk.Label(left_column2, justify="left", bg="#03070b", fg="#6a858a", textvariable=self.images_left_stats_strvar) # LISTS
            left_label.grid(row = 1, column = 0, sticky="W")

            # Actual labels: Middle
            #name_label = tk.Label(left_column, justify="left", bg="#03070b", fg="#6a858a", textvariable=self.name_ext_size) # INFO
            name_label = tk.Label(left_column2, justify="left", bg="#03070b", fg="#6a858a", text="Viewer:") # INFO
            name_label.grid(row = 0, column = 1, sticky = "W")

            self.frameinfo = tk.StringVar(value="0/0/0")
            size_label = tk.Label(left_column2, justify="left", bg="#03070b", fg="#6a858a", textvariable=self.frameinfo) # FRAMEINFO
            size_label.grid(row = 1, column = 1, sticky = "W")

            self.frametimeinfo = tk.StringVar(value="0/0")
            size_label = tk.Label(left_column2, justify="left", bg="#03070b", fg="#6a858a", textvariable=self.frametimeinfo) # FRAMETIME
            size_label.grid(row = 2, column = 1, sticky = "W")
                        
            
            
            "TERMINAL2"
            terminal_frame2 = tk.Frame(left_column, bg=self.main_colour)
            terminal_frame2.grid_propagate(True)

            terminal_frame2.grid(row = 0, column= 1, sticky="EW")

            terminal_frame2.columnconfigure(0, weight=1)#
            terminal_frame2.rowconfigure(0, weight=1)#
            terminal_frame2.columnconfigure(1, weight=1)#
            terminal_frame2.rowconfigure(1, weight=1)#


            # Create a Text widget for terminal output
            self.text_widget2 = tk.Text(left_column, height= 4, width=11, bg="#03070b", fg = "#6a858a")
            self.text_widget2.grid(row = 0, column= 1, sticky="EW")
            self.text_widget2.configure(state="disabled")

            self.first_render = tk.StringVar(value="0") # F: 1.543s
            self.first_render.trace_add("write", lambda *args: self.manage_lines2(self.first_render.get(), first=True))

            self.buffered = tk.StringVar(value="0") # B: 1.754s # make terminal for these? no?
            self.buffered.trace_add("write", lambda *args: self.manage_lines2(self.buffered.get()))

            # Create a Text widget for terminal output
            self.text_widget3 = tk.Text(self.statsframe, width=10000, height= 4, bg="#03070b", fg = "#6a858a")
            self.text_widget3.grid(row = 1, column = 0, sticky="EW")
            self.text_widget3.configure(state="disabled")

            self.name_ext_size = tk.StringVar(value="0")
            self.name_ext_size.trace_add("write", lambda *args: self.manage_lines3(self.name_ext_size.get()))

            self.text_widget3.bind("<FocusIn>", lambda e: (self.text_widget3.config(), self.fileManager.navigator.select(None)))
            self.text_widget3.bind("<FocusOut>", lambda e: self.text_widget3.config)
            
            self.text_widget3.bind("<Return>", self.save_text)
            # Actual labels: Right

            #self.panel333 = tk.Label(self.counter, justify="left", bg="#03070b", fg="#6a858a", textvariable=self.animation_stats)
            #self.panel333.grid(column = 0, row = 3, sticky = "NSEW")

            #self.panel333 = tk.Label(self.counter, justify="left", bg="#03070b", fg="#6a858a", textvariable=self.resource_limiter)
            #self.panel333.grid(column = 1, row = 3, sticky = "NSEW") 
    def guisetup(self, destinations): # 
        "Happens after we press new session or load session. Does the buttons etc"
        def luminance(hexin):
            color = tuple(int(hexin.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
            r = color[0]
            g = color[1]
            b = color[2]
            hsp = sqrt(
                0.299 * (r**2) +
                0.587 * (g**2) +
                0.114 * (b**2)
            )
            if hsp > 115.6:
                return 'light'
            else:
                return 'dark'
        def darken_color(color, factor=0.5): #Darken a given color by a specified factor
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
        
        self.source_entry_field.config(state=tk.DISABLED)
        self.destination_entry_field.config(state=tk.DISABLED)

        for x in self.first_page: # Clear old page buttons from memory.
            x.destroy()

        self.sort_by_date_b.destroy() # Hide sortbydate button after it is no longer needed

         # Bind arrow keys to Navigator.
        arrowkeys = ["<Up>", "<Down>", "<Left>", "<Right>"]
        for arrowkey in arrowkeys: # Binding arrow keys to navigator
            self.bind_all(f"{arrowkey}", partial(self.fileManager.navigator.bindhandler))

        # Frame to hold the buttons
        self.buttonframe = tk.Frame(self.leftui,bg=self.main_colour)
        self.buttonframe.grid(column=0, row=4, sticky="NSEW")
        self.buttonframe.columnconfigure(0, weight=1)
        buttonframe = self.buttonframe

        # Get the destinations and make them buttons!
        if True:
            hotkeys = self.hotkeys
            for key in hotkeys:
                self.unbind_all(key)
    
            guirow = 1
            guicol = 0
            itern = 0
            smallfont = self.smallfont
            columns = 1
    
            if len(destinations) > int((self.leftui.winfo_height()/35)-2):
                columns=2
                buttonframe.columnconfigure(1, weight=1)
            if len(destinations) > int((self.leftui.winfo_height()/15)-4):
                columns = 3
                buttonframe.columnconfigure(2, weight=1)
            original_colors = {} #Used to return their color when hovered off
            
            for x in destinations:
                color = x['color']
                if x['name'] != "SKIP" and x['name'] != "BACK":
                    if(itern < len(hotkeys)):
                        newbut = tk.Button(buttonframe, text=hotkeys[itern] + ": " + x['name'], command=partial(
                            self.fileManager.setDestination, x, {"widget": None}), anchor="w", wraplength=(self.leftui.winfo_width()/columns)-1)
                        seed(x['name'])
                        self.bind_all(f"<KeyPress-{self.hotkeys[itern]}>", partial(
                            self.fileManager.setDestination, x))
                        fg = self.text_colour
                        if luminance(color) == 'light':
                            fg = self.text_colour
                        newbut.configure(bg=color, fg=fg)
                        original_colors[newbut] = {'bg': color, 'fg': fg}  # Store both colors
                        if(len(x['name']) >= 13):
                            newbut.configure(font=smallfont)
                    else:
                        newbut = tk.Button(buttonframe, text=x['name'],command=partial(
                            self.fileManager.setDestination, x, {"widget": None}), anchor="w")
                    itern += 1
    
                newbut.config(font=("Courier", 12), width=int(
                    (self.leftui.winfo_width()/12)/columns), height=1)
                if len(x['name']) > 20:
                    newbut.config(font=smallfont)
                newbut.dest = x
                if guirow > ((self.leftui.winfo_height()/35)-2):
                    guirow = 1
                    guicol += 1
                newbut.grid(row=guirow, column=guicol, sticky="nsew")
                newbut.bind("<Button-3>", lambda a, x=x: self.destination_viewer.create_window(a,x))
    
                self.buttons.append(newbut)
                guirow += 1
                # Store the original colors for all buttons
                original_colors[newbut] = {'bg': newbut.cget("bg"), 'fg': newbut.cget("fg")}  # Store both colors
    
                # Bind hover events for each button
                newbut.bind("<Enter>", lambda e, btn=newbut: btn.config(bg=darken_color(original_colors[btn]['bg']), fg='white'))
                newbut.bind("<Leave>", lambda e, btn=newbut: btn.config(bg=original_colors[btn]['bg'], fg=original_colors[btn]['fg']))  # Reset to original colors
    
            # For SKIP and BACK buttons, set hover to white
            for btn in self.buttons:
                if btn['text'] == "SKIP (Space)" or btn['text'] == "BACK":
                    btn.bind("<Enter>", lambda e, btn=btn: btn.config(bg=self.text_colour, fg=self.main_colour))
                    btn.bind("<Leave>", lambda e, btn=btn: btn.config(bg=self.button_colour, fg=self.text_colour))  # Reset to original colors
        
        # Make second page buttons
        if True:
            # Frame to hold all new the buttons
            second_frame = tk.Frame(self.leftui,bg=self.main_colour)
            second_frame.columnconfigure(0, weight=1)
            second_frame.columnconfigure(1, weight=3)
            second_frame.grid(row=0, column=0, sticky="ew")

            # First column
            if True:
                # Save Session BUTTON
                save_session_b = tk.Button(second_frame,text="Save Session",command=partial(self.fileManager.savesession,True),
                    bg=self.button_colour, fg=self.text_colour, activebackground = self.button_press_colour, activeforeground=self.pressed_text_colour, relief = tk.RAISED)
                save_session_b.grid(column=0,row=0,sticky="ew")

                # Squares Per Page FIELD
                squares_per_page_b = tk.Entry(second_frame, textvariable=self.squares_per_page_intvar, 
                    takefocus=False, background=self.text_field_colour, foreground=self.text_field_text_colour)
                if self.squares_per_page_intvar.get() < 0: self.squares_per_page_intvar.set(1) # Won't let you save -1.
                squares_per_page_b.grid(row=1, column=0, sticky="EW",)
            # Second column
            if True:
                # Clear Selection BUTTON
                clear_all_b = tk.Button(second_frame, text="Clear Selection", command=self.fileManager.clear,
                    bg=self.button_colour, fg=self.text_colour, activebackground = self.button_press_colour, activeforeground=self.pressed_text_colour)
                clear_all_b.grid(row=0, column=1, sticky="EW")

                # Load More Images BUTTON
                load_more_b = tk.Button(second_frame, text="Load More Images", command=self.gridmanager.load_more,
                    bg=self.button_colour, fg=self.text_colour, activebackground = self.button_press_colour, activeforeground=self.pressed_text_colour)
                load_more_b.grid(row=1, column=1, sticky="EW")

                # Move All BUTTON
                move_all_b = tk.Button(second_frame, text="Move All", command=self.fileManager.moveall,
                    bg=self.button_colour, fg=self.text_colour, activebackground = self.button_press_colour, activeforeground=self.pressed_text_colour)
                move_all_b.grid(column=1, row=2, sticky="EW")
            # Third column
            if True:
                # Frame to hold the buttons in
                toggleable_b  = tk.Frame(self.leftui,bg=self.main_colour)
                toggleable_b.grid(row = 1, column = 0, sticky = "ew")
                toggleable_b.columnconfigure(0, weight = 1)
                toggleable_b.columnconfigure(1, weight = 1)
                toggleable_b.columnconfigure(2, weight = 1)
                toggleable_b.columnconfigure(3, weight = 1)
                toggleable_b.columnconfigure(4, weight = 1)

                # Show next BUTTON
                show_next_button = ttk.Checkbutton(toggleable_b, text="Show next", variable=self.show_next, onvalue=True, offvalue=False)
                show_next_button.grid(row=0, column=1, sticky="ew")
                show_next_button.configure(style="Theme_checkbox.TCheckbutton")
                
                # Dock view BUTTON
                dock_view_button = ttk.Checkbutton(toggleable_b, text="Dock view", variable=self.dock_view, onvalue=True, offvalue=False, command=lambda: (self.change_viewer()))
                dock_view_button.grid(row=0, column=2, sticky="ew")
                dock_view_button.configure(style="Theme_checkbox.TCheckbutton")
                
                # Dock side BUTTON
                self.dock_side_button = ttk.Checkbutton(toggleable_b, text="Dock side", variable=self.dock_side, onvalue=True, offvalue=False, command=lambda: (self.change_dock_side()))
                self.dock_side_button.grid(row=0, column=3, sticky="ew")
                self.dock_side_button.configure(style="Theme_checkbox.TCheckbutton")
                
                if self.dock_view.get(): 
                    self.dock_side_button.state(['!disabled'])
                else: 
                    self.dock_side_button.state(['disabled'])

                view_options = ["Show Unassigned", "Show Assigned", "Show Moved", "Show Animated"]
                self.current_view = tk.StringVar(value="Show Unassigned")
                self.current_view.trace_add("write", lambda *args: self.current_view_changed(self.current_view.get()))

                view_menu = tk.OptionMenu(second_frame, self.current_view, *view_options)
                view_menu.config(bg=self.button_colour, fg=self.text_colour,activebackground=self.button_press_colour, activeforeground=self.pressed_text_colour, highlightbackground=self.button_colour, highlightthickness=1)
                view_menu.grid(row = 2, column = 0, sticky = "EW")

            # Button to control how image is centered
            if self.centering_button:
                options = ["Center", "Only x centering", "Only y centering", "No centering"]
                preference = tk.StringVar()
                
                centering_b = tk.OptionMenu(toggleable_b, preference, *options)
                centering_b.config(bg=self.button_colour, fg=self.text_colour, activebackground=self.button_press_colour, 
                    activeforeground=self.pressed_text_colour, highlightbackground=self.main_colour, highlightthickness=1)
                centering_b.grid(row=0, column=4, sticky="ew")

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
            #Option for making the buttons change color on hover
            clear_all_b.bind("<Enter>", lambda e: clear_all_b.config(bg=self.button_press_colour, fg=self.pressed_text_colour))
            clear_all_b.bind("<Leave>", lambda e: clear_all_b.config(bg=self.button_colour, fg=self.text_colour))

            load_more_b.bind("<Enter>", lambda e: load_more_b.config(bg=self.button_press_colour, fg=self.pressed_text_colour))
            load_more_b.bind("<Leave>", lambda e: load_more_b.config(bg=self.button_colour, fg=self.text_colour))

            move_all_b.bind("<Enter>", lambda e: move_all_b.config(bg=self.button_press_colour, fg=self.pressed_text_colour))
            move_all_b.bind("<Leave>", lambda e: move_all_b.config(bg=self.button_colour, fg=self.text_colour))

            save_session_b.bind("<Enter>", lambda e: save_session_b.config(bg=self.button_press_colour, fg=self.pressed_text_colour))
            save_session_b.bind("<Leave>", lambda e: save_session_b.config(bg=self.button_colour, fg=self.text_colour))

            squares_per_page_b.bind("<FocusIn>", lambda e: (squares_per_page_b.config(bg=self.text_field_activated_colour, fg=self.text_field_activated_text_colour), self.fileManager.navigator.select(None)))
            squares_per_page_b.bind("<FocusOut>", lambda e: squares_per_page_b.config(bg=self.text_field_colour, fg=self.text_field_text_colour))

        self.bind_all("<Button-1>", self.setfocus)
    def initial_dock_setup(self):
        "Setup the dock"
        #Leftside
        self.toppane.forget(self.imagegridframe)
        if self.dock_side.get() and self.dock_view.get():
            if self.force_scrollbar:
                self.vbar.grid(row=0, column=1, sticky='ns')
                self.imagegrid.configure(yscrollcommand=self.vbar.set)
            self.imagegrid.grid(row=0, column=0, padx = max(0, self.gridsquare_padx-1), sticky="NSEW")
            self.imagegridframe.rowconfigure(1, weight=0)
            self.imagegridframe.rowconfigure(0, weight=1)
            self.imagegridframe.columnconfigure(1, weight=0)
            self.imagegridframe.columnconfigure(0, weight=1)
            self.toppane.add(self.middlepane_frame, weight=0)
            self.toppane.add(self.imagegridframe, weight=1)

        #Rightside
        elif self.dock_view.get():
            if self.force_scrollbar:
                self.vbar.grid(row=0, column=0, sticky='ns')
                self.imagegrid.configure(yscrollcommand=self.vbar.set)
            self.imagegrid.grid(row=0, column=1, padx = max(0, self.gridsquare_padx-1), sticky="NSEW")
            self.imagegridframe.rowconfigure(1, weight=0)
            self.imagegridframe.rowconfigure(0, weight=1)
            self.imagegridframe.columnconfigure(0, weight=0)
            self.imagegridframe.columnconfigure(1, weight=1)
            self.toppane.add(self.imagegridframe, weight=1)
            self.toppane.add(self.middlepane_frame, weight=0)

        #No dock
        else:
            self.imagegridframe.grid_forget()
            if self.force_scrollbar:
                self.vbar.grid(row=0, column=1, sticky='ns')
                self.imagegrid.configure(yscrollcommand=self.vbar.set)
            self.imagegrid.grid(row=0, column=0, padx = max(0, self.gridsquare_padx-1), sticky="NSEW")
            self.imagegridframe.rowconfigure(1, weight=0)
            self.imagegridframe.rowconfigure(0, weight=1)
            self.imagegridframe.columnconfigure(1, weight=0)
            self.imagegridframe.columnconfigure(0, weight=1)
            self.toppane.add(self.imagegridframe, weight=1)

        if not self.force_scrollbar:
            self.vbar.grid(row=0, column=1, sticky='ns')
            self.vbar.grid_forget()
    "Navigation / options" # button actions
    def change_viewer(self):
        "Change which viewer is in use. Dock or secondary window"
        other_viewer_is_open = hasattr(self, 'second_window') and self.second_window and self.second_window.winfo_exists()
        if self.middlepane_frame.winfo_width() != 1:
            self.middlepane_width = self.middlepane_frame.winfo_width() #this updates it before middlepane is closed.

        self.middlepane_frame.configure(width = self.middlepane_width)
        self.focused_on_secondwindow = False

        if self.dock_view.get():
            self.dock_side_button.state(['!disabled'])
            if other_viewer_is_open: # This also means dock_view was changed, so we should open the previous image displayed, if show_next is on.
                self.close_second_window() # Closes it
                self.displayimage(self.fileManager.navigator.old.obj)

            self.toppane.forget(self.imagegridframe) # Reset the GUI.

            if self.dock_side.get():
                self.toppane.add(self.middlepane_frame, weight = 0) #readd the middpane
                self.toppane.add(self.imagegridframe, weight = 1) #readd imagegrid
            else:
                self.toppane.add(self.imagegridframe, weight = 1) #readd imagegrid
                self.toppane.add(self.middlepane_frame, weight = 0) #readd the middpane

            # Use standalone viewer
        else:
            self.dock_side_button.state(['disabled'])
            try:
                # Remove and forget the dock viewer pane and image_frame.
                self.toppane.forget(self.middlepane_frame)
                if hasattr(self, 'Image_frame'):
                    if self.Image_frame:
                        self.middlepane_frame.grid_forget()
                        self.Image_frame.canvas.unbind("<Configure>")
                        self.Image_frame.destroy()
                        
                        del self.Image_frame
                        self.displayimage(self.fileManager.navigator.old.obj) # If something was displayed, we want to display it in standalone viewer.
            except Exception as e:
                logger.error(f"Error in change_viewer: {e}")

        bindhandler_1(self.imagegrid)
    def change_dock_side(self):
        "Change which side you want the dock"
        if self.middlepane_frame.winfo_width() == 1:
            return
        #Pane remains at desired width when forgotten from view. It still exists!
        self.middlepane_width = self.middlepane_frame.winfo_width()
        self.middlepane_frame.configure(width = self.middlepane_width)
        if self.dock_view.get():
            self.toppane.forget(self.middlepane_frame)
            self.toppane.forget(self.imagegridframe)
            if self.dock_side.get():
                if self.force_scrollbar:

                    self.vbar.grid(row=0, column=1, sticky='ns')
                    self.imagegrid.configure(yscrollcommand=self.vbar.set)
                    self.imagegrid.grid(row=0, column=0, padx = max(0, self.gridsquare_padx-1), sticky="NSEW")

                    self.imagegridframe.columnconfigure(1, weight=0)
                    self.imagegridframe.columnconfigure(0, weight=1)

                self.toppane.add(self.middlepane_frame, weight = 0) #readd the middpane
                self.toppane.add(self.imagegridframe, weight = 1) #readd imagegrid
            else:
                if self.force_scrollbar:

                    self.vbar.grid(row=0, column=0, sticky='ns')
                    self.imagegrid.configure(yscrollcommand=self.vbar.set)
                    self.imagegrid.grid(row=0, column=1, padx = max(0, self.gridsquare_padx-1), sticky="NSEW")

                    self.imagegridframe.columnconfigure(0, weight=0)
                    self.imagegridframe.columnconfigure(1, weight=1)

                self.toppane.add(self.imagegridframe, weight = 1) #readd imagegrid
                self.toppane.add(self.middlepane_frame, weight = 0) #readd the middpane
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
        if hasattr(self, "Image_frame"):
            self.displayimage(self.fileManager.navigator.old.obj)
    def current_view_changed(self, selected_option):
        "When view is changed, send the wanted list to the gridmanager for rendering"
        self.fileManager.timer.start()
        "When view is changed, tells grid to display that view"
        if selected_option == "Show Unassigned":
            list_to_display = self.gridmanager.unassigned
        elif selected_option == "Show Assigned":
            list_to_display = self.gridmanager.assigned
        elif selected_option == "Show Moved":
            list_to_display = self.gridmanager.moved
        elif selected_option == "Show Animated":
            list_to_display = [x for x in self.gridmanager.unassigned if x.obj.framecount > 1]
        self.gridmanager.current_list = list_to_display
        self.gridmanager.change_view(list_to_display)
        self.fileManager.navigator.view_change()   
    def setfocus(self, event):
        event.widget.focus_set()

    "CanvasImage" # Viewers
    def displayimage(self, obj):
        " Throttler, calls 'test()' which is the real thing. If you edit these, make sure the memory doesnt leak after."

        "Throttle displayimage. When holding down arrow key, every image doesnt load. This reduces perceived lag."
        if self.last_time == None or perf_counter() - self.last_time > 0.19: # load normal keypresses instantly
            self.test(obj)
            self.displayqueue = obj
            self.last_time = perf_counter()
        else:
            self.displayqueue = obj
            self.after(190, lambda obj=obj: self.test(obj) if self.displayqueue == obj else None)
            time = perf_counter()-self.last_time
            self.times.append(time)
            #print(sum(self.times)/len(self.times))
        #    print(time)
            if len(self.times) > 5:
                self.times.pop(0)
            self.last_time = perf_counter()
    def test(self, obj):
        "Display image in viewer"
        def close_old():
            if hasattr(self, "Image_frame"):
                self.middlepane_frame.grid_forget()
                self.Image_frame.canvas.unbind("<Configure>")
                self.Image_frame.destroy()

                self.Image_frame = None
                del self.Image_frame
                collect()
            self.Image_frame = self.new

        # This makes sure the initial view is set up correctly
        if self.middlepane_frame.winfo_width() != 1:
            self.middlepane_width = self.middlepane_frame.winfo_width()

        if self.dock_view.get(): # This handles the middlepane viewer. Runs, IF second window is closed.
            geometry = str(self.middlepane_width) + "x" + str(self.winfo_height())
            self.new = CanvasImage(self.middlepane_frame, geometry, obj, self)
            self.new.grid(row = 0, column = 0, sticky = "NSEW")
            self.new.rescale(min(self.middlepane_width / self.new.imwidth, self.winfo_height() / self.new.imheight))  # Scales to the window
            self.new.center_image(self.viewer_x_centering, self.viewer_y_centering)
            logger.debug("Rescaled and Centered")

            self.focused_on_secondwindow = True

            self.new.canvas.focus_set()
            close_old()
        else: # Standalone image viewer
            if not hasattr(self, 'second_window') or not self.second_window or not self.second_window.winfo_exists():
                # No window exists, create one

                self.second_window = tk.Toplevel(background=self.main_colour) #create a new window
                second_window = self.second_window
                second_window.rowconfigure(0, weight=1)
                second_window.columnconfigure(0, weight=1)
                second_window.geometry(self.viewer_geometry)
                second_window.bind("<Button-3>", self.close_second_window)
                second_window.protocol("WM_DELETE_WINDOW", self.close_second_window)
                second_window.obj = obj
                second_window.transient(self)

            self.second_window.title("Image: " + obj.path)
            geometry = self.viewer_geometry.split('+')[0]
            x, y = geometry.split('x')
            self.new = CanvasImage(self.second_window, geometry, obj, self)
            self.new.grid(row = 0, column = 0, sticky = "NSEW")  # Initialize Frame grid statement in canvasimage, Add to main window grid
            self.new.rescale(min(int(x) / self.new.imwidth, int(y) / self.new.imheight))  # Scales to the window
            self.new.center_image(self.viewer_x_centering, self.viewer_y_centering)

            logger.debug("Rescaled and Centered")
            self.focused_on_secondwindow = True

            if not self.show_next.get():
                self.second_window.after(0, lambda: self.new.canvas.focus_set())
            else:
                self.second_window.after(0, lambda: self.new.canvas.focus_set())

            close_old() 
    
    "Exit function" # How we exit the program and close windows
    def closeprogram(self):
        def test():
            if hasattr(self.fileManager.thumbs, "gen_thread") and self.fileManager.thumbs.gen_thread != None and self.fileManager.thumbs.gen_thread.is_alive():
                self.fileManager.thumbs.gen_thread.join()
            if len(self.gridmanager.assigned) != 0:
                if askokcancel("Designated but Un-Moved files, really quit?","You have destination designated, but unmoved files. (Simply cancel and Move All if you want)"):
                    self.close_second_window()
                    if hasattr(self.destination_viewer, "destwindow"):
                        self.destination_viewer.close_window()
                    self.fileManager.saveprefs(self)
                    self.destroy()
            else:
                self.close_second_window()
                if hasattr(self.destination_viewer, "destwindow"):
                    self.destination_viewer.close_window()
                self.fileManager.saveprefs(self)
                self.quit()
                #self.destroy() - leaves threads running
                #os._exit(0) # This works too, but doesn't do cleanup
        self.fileManager.program_is_exiting = True
        Thread(target=test, daemon=True).start()   
    def close_second_window(self, event=None):
        if hasattr(self, 'Image_frame'):
            self.middlepane_frame.grid_forget()
            self.Image_frame.canvas.unbind("<Configure>")
            self.Image_frame.destroy()
            
            del self.Image_frame
        if hasattr(self, 'second_window') and self.second_window and self.second_window.winfo_exists():
            self.viewer_geometry = self.second_window.winfo_geometry()
            self.second_window.unbind(None)
            self.second_window.destroy()
            del self.second_window
        #if the viewer is closed when show next is on, disable show next.
    def filedialogselect(self, target, type):
        if type == "d":
            path = tkFileDialog.askdirectory()
        elif type == "f":
            d = tkFileDialog.askopenfile(initialdir=os.getcwd(
            ), title="Select Session Data File", filetypes=(("JavaScript Object Notation", "*.json"),))
            path = d.name
        if isinstance(target, tk.Entry):
            target.delete(0, tk.END)
            target.insert(0, path)

    "Exclusions window" # Exclusions window
    def excludeshow(self):
        excludewindow = tk.Toplevel()
        excludewindow.winfo_toplevel().title(
            "Folder names to ignore, one per line. This will ignore sub-folders too.")
        excludetext = tkst.ScrolledText(excludewindow, bg=self.main_colour, fg=self.text_colour)
        for x in self.fileManager.exclude:
            excludetext.insert("1.0", x+"\n")
        excludetext.pack()
        excludewindow.protocol("WM_DELETE_WINDOW", partial(
            self.excludesave, text=excludetext, toplevelwin=excludewindow))
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
            logger.error(f"Error in excludesave: {e}")

class GridManager:
    "Handles the gridsqures in the imagegrid"
    def __init__(self, fileManager):
        self.fileManager = fileManager
        self.gui = fileManager.gui
        self.gridsquarelist = []
        self.displayedlist = []
        self.displayedset = set()
        self.unassigned = []
        self.assigned = []
        self.moved = []
        self.animated = []
        self.current_list = []
    
    def truncate_text(self, imageobj): #may fail for very small thumbsizes # very inefficient
            filename = imageobj.name.get()
            base_name, ext = os.path.splitext(filename)
            smallfont = self.gui.smallfont
            text_width = smallfont.measure(filename)

            if text_width+24 <= self.gui.thumbnailsize:

                return filename # Return whole filename

            ext = ".." + ext

            while True: # Return filename that has been truncated.
                test_text = base_name + ext # Test with one less character
                text_width = smallfont.measure(test_text)
                if text_width+24 < self.gui.thumbnailsize:  # Reserve space for ellipsis
                    break
                base_name = base_name[:-2]
            return test_text
    def makegridsquare(self, parent, imageobj):

        frame = tk.Frame(parent, borderwidth=0,
                         highlightthickness = self.gui.whole_box_size, highlightcolor=self.gui.imageborder_default_colour,highlightbackground=self.gui.imageborder_default_colour, padx = 0, pady = 0)

        frame.obj = imageobj
        truncated_filename = "..."
        truncated_name_var = tk.StringVar(frame, value=truncated_filename)
        frame.obj2 = truncated_name_var # This is needed or it is garbage collected I guess
        frame.grid_propagate(True)

        try:
            canvas = tk.Canvas(frame, width=self.gui.thumbnailsize,
                               height=self.gui.thumbnailsize,bg=self.gui.square_colour, highlightthickness=self.gui.square_border_size, highlightcolor=self.gui.imageborder_default_colour, highlightbackground = self.gui.imageborder_default_colour) #The gridbox color.
            canvas.grid(column=0, row=0, sticky="NSEW")

            img = None
            canvas.image = img

            frame.canvas = canvas

            frame.rowconfigure(0, weight=4)
            frame.rowconfigure(1, weight=1)

            #Added reference for animation support. We use this to refresh the frame 1/20, 2/20..
            canvas_image_id = canvas.create_image(
                self.gui.thumbnailsize/2+self.gui.square_border_size, self.gui.thumbnailsize/2+self.gui.square_border_size, anchor="center", image=img) #If you use gridboxes, you must +1 to thumbnailsize/2, so it counteracts the highlighthickness.
            frame.canvas_image_id = canvas_image_id

            check_frame = tk.Frame(frame, height=self.gui.checkbox_height, padx= 2, bg=self.gui.square_text_box_colour)
            check_frame.grid_propagate(False)
            check_frame.grid(column=0, row=1, sticky="EW")  # Place the frame in the grid

            frame.cf = check_frame

            # Super expensive? 95 % of loadsession time is used on this XD...
            check = ttk.Checkbutton(check_frame, textvariable=truncated_name_var, variable=imageobj.checked, onvalue=True, offvalue=False, command=lambda: (setattr(self.gui, 'focused_on_secondwindow', False)), style="Theme_square.TCheckbutton")
            check.grid(sticky="NSEW")

            # save the data to the image obj to both store a reference and for later manipulation
            imageobj.guidata = {"img": img, "destimg": None, "frame": frame, "canvas": canvas, "check": check, "show": True} #"tooltip":tooltiptext
            frame.c = check
            # anything other than rightclicking toggles the checkbox, as we want.
            canvas.bind("<Button-1>", partial(bindhandler, check, "invoke"))
            canvas.bind("<Button-3>", lambda e: (self.fileManager.navigator.select(frame)))
            check.bind("<Button-3>", lambda e: (self.fileManager.navigator.select(frame)))
            check_frame.bind("<Button-3>", lambda e: (self.fileManager.navigator.select(frame))) #### test

            #make blue if only one that is blue, must remove other blue ones. blue ones are stored the gridsquare in a global list.
            canvas.bind("<MouseWheel>", partial(
                bindhandler, parent, "scroll"))
            frame.bind("<MouseWheel>", partial(
                bindhandler, self.gui.imagegrid, "scroll"))
            check.bind("<MouseWheel>", partial(
                bindhandler, self.gui.imagegrid, "scroll"))
            check_frame.bind("<MouseWheel>", partial(
                bindhandler, self.gui.imagegrid, "scroll")) #### test


            frame['background'] = self.gui.square_colour
            canvas['background'] = self.gui.square_colour
        except Exception as e:
            logger.error(e)
        return frame
    
    def load_session(self, unassigned, moved_or_assigned, change_order):
        self.fileManager.timer.start()
        ### could do gridsquares in threaded? or will this do bugs? ### just copy gridsquare to destviewer? not supported?
        for obj in moved_or_assigned:
            gridsquare = self.makegridsquare(self.gui.imagegrid, obj)
            self.gridsquarelist.append(gridsquare)
            if obj.moved:
                self.moved.append(gridsquare) ### make them have green border, but correct color canvas?
            elif obj.dest:
                self.assigned.append(gridsquare)
            else:
                print("error, session list moved or append is in unassigned")
                self.unassigned.append(gridsquare)

        for obj in unassigned:
            gridsquare = self.makegridsquare(self.gui.imagegrid, obj)
            self.gridsquarelist.append(gridsquare)
            self.unassigned.append(gridsquare)

        if change_order == "default":
            self.unassigned.sort(key=lambda gridsquare: (gridsquare.obj.name.get(), gridsquare.obj.path), reverse=True)
        elif change_order == "modification_date":
            self.unassigned.sort(key=lambda gridsquare: os.path.getmtime(gridsquare.obj.path), reverse=False)

        self.add_squares(self.unassigned, reload=True) # Will load thumbs from cache and generate framedata & frames

        for square in self.assigned:
            for dest in self.fileManager.destinations:
                if square.obj.dest == dest['path']:
                    square.obj.setdest(dest)
                    square.obj.guidata["frame"]['background'] = dest['color']
                    square.obj.guidata["canvas"]['background'] = dest['color']
                    break
    def load_more(self, amount=None) -> None:
        if not self.gui.current_view.get() == "Show Unassigned":
            return
        self.fileManager.timer.start()
        if amount == None:
            amount = self.gui.squares_per_page_intvar.get()
        # 1. get list of the loadable items
        # 2. make gridsquares for them
        # 3. display them in grid (placeholders).
        # 4. generate thumbnails for them. (Threaded)
        filelist = self.fileManager.imagelist
        items = min(amount, len(filelist)-len(self.gridsquarelist)) # How many we want to load or can load.
        if items == 0:
            self.gui.load_more_b.configure(text="No More Images!",background="#DD3333")
            return
        sublist = filelist[-items:]
        sublist.reverse()
        del filelist[-items:]
        generated = [] # Store created gridsquares
        for obj in sublist:
            gridsquare = self.makegridsquare(self.gui.imagegrid, obj) # generate concurrently in this thread? will this block? can also generate checks after the fact in thumb loader.
            generated.append(gridsquare)
        #self.imagegridframe.update() #necessary?
        self.unassigned.extend(generated)
        self.gridsquarelist.extend(generated)
        self.add_squares(generated, reload=False)
        #print(f"Displayed grid in: {self.fileManager.timer.stop()}")
        
        self.fileManager.timer.start()
        self.fileManager.thumbs.generate(generated) # This thread shouldnt be stopped at any time. Used to get info on frames and such that reload wont do.
        self.gui.images_left_stats_strvar.set(
            f"Left: {len(self.assigned)}/{len(self.gridsquarelist)-len(self.assigned)-len(self.moved)}/{len(filelist)-len(self.assigned)-len(self.moved)}")
    def change_view(self, squares) -> None:
        "Remove all squares from grid, but add them back without unloading according how they should be ordered."
        # This is called when the view is called to avoid old frames in the new list from not being deleted
        # Squares is the whole new list to be displayed
        self.fileManager.thumbs.gen_queue.clear()
        self.fileManager.program_is_exiting = True
        not_in_new_list = [x for x in self.displayedset if x not in squares] # Unload their thumbs and frames.
        in_both_lists = [x for x in self.displayedset if x in squares] # Remove them from gridview. But dont unload
        if not_in_new_list: # Normal remove
            self.remove_squares(not_in_new_list, unload=True)
        if in_both_lists: # Remove but without unloading from memory. We want to readd these.
            self.remove_squares(in_both_lists, unload=False)
        if squares: # Only try if there is a need.
            self.add_squares(squares) # This will know if thumb is loaded or not and will reload as needed.
 
    def add_squares(self, squares: list, reload=True) -> None:
        "Adds squares to grid, displayedlist, and reloads them"
        regen = []
        for gridsquare in squares:
            if self.gui.current_view.get() == "Show Assigned":
                self.gui.imagegrid.window_create(
                    "1.0", window=gridsquare, padx=self.gui.gridsquare_padx, pady=self.gui.gridsquare_pady)
            else:
                self.gui.imagegrid.window_create(
                    "insert", window=gridsquare, padx=self.gui.gridsquare_padx, pady=self.gui.gridsquare_pady)
            self.displayedlist.append(gridsquare)
            self.displayedset.add(gridsquare)
            if reload or gridsquare.obj.guidata['img'] == None: # Checks if img is unloaded
                regen.append(gridsquare)
        self.gui.manage_lines(f"Displayed grid in: {self.fileManager.timer.stop()}")
        if reload and regen:
            self.fileManager.thumbs.generate(regen) # Threads the reloading process.
    def remove_squares(self, squares: list, unload) -> None:
        "Removes square from grid, displayedlist, and can unload it from memory"
        unload_list = []
        for gridsquare in squares:
            if gridsquare in self.displayedset: # because may be in dest displayedlist insetad
                self.gui.imagegrid.window_configure(gridsquare, window="")
                self.displayedlist.remove(gridsquare)
                self.displayedset.discard(gridsquare)
                if unload:
                    unload_list.append(gridsquare)
        if unload:
            self.fileManager.thumbs.unload(unload_list)

# get rid of these eventually
def throttled_yview(widget, page_mode, *args):
    """Throttle scroll events for both MouseWheel and Scrollbar slider"""
    global flag1
    global flag_len
    #global last_scroll_time
    #global throttle_time
    #now = time()
    #if not last_scroll_time:
    #    last_scroll_time = now
    #else:
    #    if (now - last_scroll_time) > 0.0:  # 100ms throttle
    #        last_scroll_time = now
#
    #    else:
    #        print("GET THROTTLED IDIOT!!!!!")
    #        return
    #print(len(flag1))


    if len(flag1) > flag_len:
        return
    flag1.append("a")
    if args[0] == "scroll":
        current_view = widget.yview()

        if int(args[1]) > 0:
            direction = 1
        else:
            direction = -1

        new_position = current_view[0] + (direction * 0.01)
        new_position = max(0.0, min(1.0, new_position))

        if page_mode:
            widget.yview(*args)

        else:
            widget.update()
            widget.yview_moveto(new_position)

    elif args[0] == "moveto":
        moveto = float(args[1])
        widget.yview_moveto(moveto)
    widget.update()
    flag1.pop(0)
def throttled_scrollbar(*args): # Throttled scrollbar callback
    throttled_yview(args[0], 'yview', *args[1:])
def bindhandler_1(widget): # Fixes moving from dock view back to standalone view / could figure out custom values from rows, but eh.
    #global last_row_length
    #if last_row_length == 0:
    #    last_row_length = 1
    #if last_row_length % 2 == 0:
    #    #postivie goes down
    #    widget.yview_scroll(1, "units")
    #last_row_length += 1
    pass
def bindhandler(*args):
    global current_scroll_direction
    global flag1
    global flag_len
    widget = args[0]
    command = args[1]
    global last_scroll_time2
    global throttle_time
    throttle_time = 0.01
    now = time()
    if last_scroll_time2 is None or (now - last_scroll_time2) > throttle_time:  # 100ms throttle
            last_scroll_time2 = now
    if command == "scroll1":
        widget.yview_scroll(-1*floor(args[2].delta/120), "units")
        widget.yview_scroll(40*1*floor(args[2].delta/120), "pixels") # counteracts stupid scroll by tk.text get f##cked!
        #widget.update()
        """
        if len(flag1) < flag_len:
            pass
        else:
            widget.yview_scroll(-40*-1*floor(args[2].delta/120), "pixels")
            return
        total_distance = 287
        steps = 10
        # Initialize a gradual slowdown for scrolling
        initial_speed = 1  # Adjust as needed for initial scroll speed
        slowdown_factor = 1.2 # Factor to slow down each iteration
        delay = 0.01

        delta_direction = -1 if args[2].delta > 0 else 1  # Determine scroll direction based on delta
        flag1.append("a")
        if len(flag1) > flag_len:
            widget.yview_scroll(-40*-1*floor(args[2].delta/120), "pixels")
            return

        # Calculate pixel movement per step for acceleration and deceleration phases
        pixels_per_step = total_distance // steps
        accumulated_scroll = 0  # Track total scroll to ensure it reaches exactly 281

        for i in range(steps // 2):

           current_speed = initial_speed / (slowdown_factor ** i)
           scroll_amount = floor(pixels_per_step)
           widget.yview_scroll(delta_direction * scroll_amount, "pixels")
           widget.update()
           #sleep(current_speed * delay)
           accumulated_scroll += scroll_amount

        for i in range(steps // 2, steps):

            current_speed = initial_speed / (slowdown_factor ** (steps - i))
            scroll_amount = floor(pixels_per_step)
            widget.yview_scroll(delta_direction * scroll_amount, "pixels")
            widget.update()
            sleep(current_speed * delay)
            accumulated_scroll += scroll_amount

        # Correct any remaining pixels to ensure the total scroll is exactly 281
        remaining_scroll = total_distance - accumulated_scroll
        if remaining_scroll > 0:
            widget.yview_scroll(delta_direction * remaining_scroll, "pixels")


        ## Acceleration phase: Gradually increase speed
        #for i in range(9):  # Half of total steps for acceleration
        #    current_speed = initial_speed / (slowdown_factor ** i)
        #    widget.yview_scroll(-pixel * floor(args[2].delta / 120), "pixels")
        #    widget.update()
        #    sleep(current_speed * delay)
        ## Deceleration phase: Gradually decrease speed
        #for i in range(9, 18):  # Second half of steps for deceleration
        #    current_speed = initial_speed / (slowdown_factor ** (18 - i))
        #    widget.yview_scroll(-pixel * floor(args[2].delta / 120), "pixels")
        #    widget.update()
        #    print(current_speed)
        #    sleep(current_speed * delay)

        #for i in range(18):  # Number of scroll steps
        #    current_speed = initial_speed / (slowdown_factor ** i)
        #    print(current_speed)
        #    widget.yview_scroll(-pixel * floor(args[2].delta / 120), "pixels")
        #    widget.update()
        #    sleep(current_speed * delay)  # Adjust delay as needed
        widget.yview_scroll(-40*-1*floor(args[2].delta/120), "pixels")
        flag1.pop(0)

        """
        return
    if command == "scroll":
        widget.yview_scroll(-1*floor(args[2].delta/120), "units")

    elif command == "invoke":
        if last_scroll_time2 is None or (now - last_scroll_time2) < throttle_time:  # 100ms throttle
            last_scroll_time2 = now
            widget.invoke()

    elif command == "scroll1":
        pass
"""
    def switch_bg_colour(self, event):
        if self.switch_counter == len(self.op)-1:
            for x in self.displayedlist:
                x.canvas.configure(background=self.op[len(self.op)-1])
            print(len(self.op), self.op[len(self.op)-1])
            self.switch_counter = 0
        else:
            print(self.switch_counter + 1, self.op[self.switch_counter])
            for x in self.displayedlist:
                x.canvas.configure(background=self.op[self.switch_counter])
            self.switch_counter += 1

        self.configure(background=self.op[self.switch_counter])
    """
