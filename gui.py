from os import path, getcwd
from random import seed
from math import floor,sqrt
import logging

from functools import partial
from time import time, perf_counter
from operator import indexOf

import psutil

import vlc

import tkinter as tk
import tkinter.font as tkfont
import tkinter.scrolledtext as tkst
from tkinter.messagebox import askokcancel
from tkinter import filedialog as tkFileDialog
from tkinter.ttk import Panedwindow
from tkinter import ttk
from tktooltip import ToolTip

from canvasimage import CanvasImage

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
flag1 = []
flag_len = 1
last_row_length = 0
import objgraph

class GUIManager(tk.Tk):
    "Initialization"
    def __init__(self, fileManager) -> None:
        super().__init__()
        def get_memory_usage():
            # Get the current process
            process = psutil.Process()

            # Get memory info
            memory_info = process.memory_info()

            # Return the RSS (Resident Set Size) in bytes
            return (memory_info.rss)
        def show_ram_usage():
            self.current_ram.set(f"{get_memory_usage() / (1024 ** 2):.2f} MB")
            #print("")
            #objgraph.show_growth()

            self.after(333, show_ram_usage)
        self.fileManager = fileManager
        self.vlc_instance = vlc.Instance('--quiet')
        #DEFAULT VALUES FOR PREFS.JSON. This is essentially the preference file the program creates at the very start.
        #paths
        self.source_folder = ""
        self.destination_folder = ""
        self.sessionpathvar = tk.StringVar()

        self.images_sorted = tk.StringVar(value="0")
        self.images_left = tk.StringVar(value="0")
        self.images_left_and_assigned = tk.StringVar(value="0/0")
        self.current_ram = tk.StringVar(value="0")
        show_ram_usage()

        #Preferences
        self.thumbnailsize = 256
        self.hotkeys = "123456qwerty7890uiopasdfghjklzxcvbnm"
        self.extra_buttons = False
        self.force_scrollbar = True
        self.interactive_buttons = True # Color change on hover
        self.page_mode = False # Scroll a whole page or no?

        #Technical preferences
        self.filter_mode =  "BILINEAR"
        self.quick_preview_size_threshold = 5 # Size at which we start to buffer the image to load the displayimage faster. We use NEAREST, then when LANCZOS is ready, we swap it to that.
        self.throttle_time = None
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
        self.squaresperpage = tk.IntVar(value=120)
        self.sortbydatevar = tk.BooleanVar()
        self.default_delay = tk.BooleanVar(value=True)    # Whether to use global delay from a gif or a per frame delay.
        self.viewer_x_centering = True
        self.viewer_y_centering = True
        self.show_next = tk.BooleanVar(value=True)
        self.dock_view = tk.BooleanVar(value=True)
        self.dock_side = tk.BooleanVar(value=True)
        #Default window positions and sizes
        self.main_geometry = (str(self.winfo_screenwidth()-5)+"x" + str(self.winfo_screenheight()-120)+"+0+60")
        self.viewer_geometry = str(int(self.winfo_screenwidth()*0.80)) + "x" + str(self.winfo_screenheight()-120)+"+365+60"
        self.destpane_geometry = 0
        self.leftpane_width = 363
        self.middlepane_width = 363
        ##END OF PREFS

        # Flags
        self.fix = True
        self.started_not_integrated = False
        self.old_img_frame = []

        # Tracking index
        self.focused_on_secondwindow = False

        self.track_animated = []
        #Destwindow lists
        self.dest_squarelist = [] # List to hold all gridsquares destined for the destination
        self.destgrid_updateslist = [] # List to hold all gridsquare refreshes from setdestination
        self.render_refresh = [] # List to hold all gridsquares refreshes from setdestination
        self.queue = []
        #Buttons list
        self.buttons = []

        self.actual_gridsquare_width = self.thumbnailsize + self.gridsquare_padx + self.square_border_size*2 + self.whole_box_size*2
        self.actual_gridsquare_height = self.thumbnailsize + self.gridsquare_pady + self.square_border_size*2 + self.whole_box_size*2 + self.checkbox_height

    def initialize(self): #Initializating GUI
        global throttle_time
        throttle_time = self.throttle_time

        self.geometry(self.main_geometry)
        #Styles
        self.smallfont = tkfont.Font(family='Helvetica', size=10)

        style = ttk.Style()
        self.style = style
        style.configure('Theme_dividers.TPanedwindow', background=self.pane_divider_colour)  # Panedwindow, the divider colour.
        style.configure("Theme_checkbox.TCheckbutton", background=self.main_colour, foreground=self.text_colour, highlightthickness = 0) # Theme for checkbox
        style.configure("Theme_square.TCheckbutton", background=self.grid_background_colour, foreground=self.text_colour)
        # Paned window that holds the almost top level stuff.
        self.toppane = Panedwindow(self, orient="horizontal")

        # Frame for the left hand side that holds the setup and also the destination buttons.
        self.leftui = tk.Frame(self.toppane, width=self.leftpane_width, bg=self.main_colour)
        self.leftui.grid_propagate(False) #to turn off auto scaling.
        self.leftui.columnconfigure(0, weight=1)

        self.toppane.add(self.leftui, weight=0) # 0 here, it stops the divider from moving itself. The divider pos is saved by prefs, this complicates it, so auto scaling based on text amount in source and dest folder is disabled.

        # This setups all the buttons and text
        self.first_page_buttons()

        # Start the grid setup
        self.middlepane_frame = tk.Frame(self.toppane, bg=self.canvasimage_background, width = self.middlepane_width)

        imagegridframe = tk.Frame(self.toppane,bg=self.grid_background_colour)
        imagegridframe.grid(row=0, column=2, sticky="NSEW") #this is in second so content frame inside this.
        self.imagegridframe = imagegridframe

        self.imagegrid = tk.Text(imagegridframe, wrap='word', borderwidth=0,
                                 highlightthickness=0, state="normal", background=self.grid_background_colour)

        self.imagegrid.bind("<Up>", lambda e: "break")
        self.imagegrid.bind("<Down>", lambda e: "break")

        vbar = tk.Scrollbar(imagegridframe, orient='vertical',command=lambda *args: throttled_yview(self.imagegrid, self.page_mode, *args))
        self.vbar = vbar

        self.imagegrid.configure(state="disabled")
        self.imagegrid.bind("<MouseWheel>", lambda e: "break")
        self.imagegrid.bind("<MouseWheel>", partial(
                bindhandler, self.imagegrid, "scroll1"))
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

        self.gridmanager = GridManager(self.fileManager)

    def first_page_buttons(self):
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

        self.buttonframe = tk.Frame(master=self.leftui,bg=self.main_colour)
        self.buttonframe.grid(column=0, row=3, sticky="NSEW")
        self.buttonframe.columnconfigure(0, weight=1)

        self.leftui.rowconfigure(300, weight=1)
        self.counterframe = tk.Frame(self.leftui, bg=self.main_colour)
        self.counterframe.grid(column=0, row=300, sticky="NSEW")
        self.counterframe.columnconfigure(0, weight=1)
        self.counterframe.rowconfigure(0, weight=1)

        self.counter = tk.Frame(self.counterframe, bg="yellow", width = 50, height = 25)
        self.counter.grid(column=0, row=0, sticky="se")
        self.counter.columnconfigure(0, weight=1)
        self.counter.rowconfigure(0, weight=1)

        self.panel11 = tk.Label(self.counter, justify="left", bg="purple",fg=self.text_colour, text="Images sorted  :   ")
        self.panel11.grid(column = 0, row = 0, sticky="NSEW")

        self.panel1 = tk.Label(self.counter, justify="left", bg="purple",fg=self.text_colour, textvariable=self.images_sorted)
        self.panel1.grid(column = 1, row = 0, sticky="NSEW")

        self.panel22 = tk.Label(self.counter, justify="left", bg="purple",fg=self.text_colour, text="Images left    :   ")
        self.panel22.grid(column = 0, row = 1, sticky="NSEW")

        self.panel2 = tk.Label(self.counter, justify="left", bg="purple",fg=self.text_colour, textvariable=self.images_left_and_assigned)
        self.panel2.grid(column = 1, row = 1, sticky="NSEW")
        
        self.panel33 = tk.Label(self.counter, justify="left", bg="purple",fg=self.text_colour, text="RAM usage    :   ")
        self.panel33.grid(column = 0, row = 2, sticky="NSEW")
        
        self.panel3 = tk.Label(self.counter, justify="left", bg="purple",fg=self.text_colour, textvariable=self.current_ram)
        self.panel3.grid(column = 1, row = 2, sticky = "NSEW")
        
        self.entryframe = tk.Frame(master=self.leftui,bg=self.main_colour)
        self.entryframe.columnconfigure(1, weight=1)
        self.entryframe.grid(row=0, column=0, sticky="ew")

        self.excludebutton = tk.Button(self.entryframe, text="Manage Exclusions", command=self.excludeshow,
                                       bg=self.button_colour, fg=self.text_colour, activebackground = self.button_press_colour, activeforeground=self.pressed_text_colour)
        self.excludebutton.grid(row=0, column=2)

        self.sdpEntry = tk.Entry(self.entryframe, takefocus=False,
                                 background=self.text_field_colour, foreground=self.text_field_text_colour)  # scandirpathEntry
        self.sdpEntry.grid(row=0, column=1, sticky="ew", padx=2)
        self.sdpEntry.insert(0, self.source_folder)

        self.sdplabel = tk.Button(self.entryframe, text="Source Folder:", command=partial(self.filedialogselect, self.sdpEntry, "d"),
                                  bg=self.button_colour, fg=self.text_colour, activebackground = self.button_press_colour, activeforeground=self.pressed_text_colour)
        self.sdplabel.grid(row=0, column=0, sticky="e")

        self.ddpEntry = tk.Entry(self.entryframe, takefocus=False,
                                 background=self.text_field_colour, foreground=self.text_field_text_colour)  # dest dir path entry
        self.ddpEntry.grid(row=1, column=1, sticky="ew", padx=2)
        self.ddpEntry.insert(0, self.destination_folder)

        self.ddplabel = tk.Button(self.entryframe, text="Destination Folder:", command=partial(self.filedialogselect, self.ddpEntry, "d"),
                                  bg=self.button_colour, fg=self.text_colour, activebackground = self.button_press_colour, activeforeground=self.pressed_text_colour)
        self.ddplabel.grid(row=1, column=0, sticky="e")

        self.activebutton = tk.Button(self.entryframe, text="New Session", command=partial(self.fileManager.validate, self),
                                      bg=self.button_colour, fg=self.text_colour, activebackground = self.button_press_colour, activeforeground=self.pressed_text_colour)
        ToolTip(self.activebutton,delay=1,msg="Start a new Session with the entered source and destination")
        self.activebutton.grid(row=1, column=2, sticky="ew")

        self.loadpathentry = tk.Entry(self.entryframe, takefocus=False, textvariable=self.sessionpathvar,
                                      background=self.text_field_colour, foreground=self.text_field_text_colour)
        self.loadpathentry.grid(row=3, column=1, sticky='ew', padx=2)

        self.loadbutton = tk.Button(self.entryframe, text="Load Session", command=self.fileManager.loadsession,
                                    bg=self.button_colour, fg=self.text_colour, activebackground = self.button_press_colour, activeforeground=self.pressed_text_colour)
        ToolTip(self.loadbutton,delay=1,msg="Load and start the selected session data.")
        self.loadbutton.grid(row=3, column=2, sticky='ew')

        self.loadfolderbutton = tk.Button(self.entryframe, text="Session Data:", command=partial(self.filedialogselect, self.loadpathentry, "f"),
                                          bg=self.button_colour, fg=self.text_colour, activebackground = self.button_press_colour, activeforeground=self.pressed_text_colour)
        ToolTip(self.loadfolderbutton,delay=1,msg="Select a session json file to open.")
        self.loadfolderbutton.grid(row=3, column=0, sticky='e')

        # Add a button for sortbydate option
        self.sortbydate_button = ttk.Checkbutton(self.leftui, text="Sort by Date", variable=self.sortbydatevar, onvalue=True, offvalue=False,
                                                 command=self.sortbydatevar,style="Theme_checkbox.TCheckbutton")
        self.sortbydate_button.grid(row=2, column=0, sticky="w", padx=25)

        #If it is set in prefs, this makes the buttons blink when hovered over.
        if self.interactive_buttons:
            #Option for making the buttons change color on hover
            self.excludebutton.bind("<Enter>", lambda e: self.excludebutton.config(bg=self.button_press_colour, fg=self.pressed_text_colour))
            self.excludebutton.bind("<Leave>", lambda e: self.excludebutton.config(bg=self.button_colour, fg=self.text_colour))
        
            self.activebutton.bind("<Enter>", lambda e: self.activebutton.config(bg=self.button_press_colour, fg=self.pressed_text_colour))
            self.activebutton.bind("<Leave>", lambda e: self.activebutton.config(bg=self.button_colour, fg=self.text_colour))

            self.sdpEntry.bind("<FocusIn>", lambda e: self.sdpEntry.config(bg=self.text_field_activated_colour, fg=self.text_field_activated_text_colour))
            self.sdpEntry.bind("<FocusOut>", lambda e: self.sdpEntry.config(bg=self.text_field_colour, fg=self.text_field_text_colour))

            self.ddpEntry.bind("<FocusIn>", lambda e: self.ddpEntry.config(bg=self.text_field_activated_colour, fg=self.text_field_activated_text_colour))
            self.ddpEntry.bind("<FocusOut>", lambda e: self.ddpEntry.config(bg=self.text_field_colour, fg=self.text_field_text_colour))

            self.sdplabel.bind("<Enter>", lambda e: self.sdplabel.config(bg=self.button_press_colour, fg=self.pressed_text_colour))
            self.sdplabel.bind("<Leave>", lambda e: self.sdplabel.config(bg=self.button_colour, fg=self.text_colour))

            self.ddplabel.bind("<Enter>", lambda e: self.ddplabel.config(bg=self.button_press_colour, fg=self.pressed_text_colour))
            self.ddplabel.bind("<Leave>", lambda e: self.ddplabel.config(bg=self.button_colour, fg=self.text_colour))

            self.loadbutton.bind("<Enter>", lambda e: self.loadbutton.config(bg=self.button_press_colour, fg=self.pressed_text_colour))
            self.loadbutton.bind("<Leave>", lambda e: self.loadbutton.config(bg=self.button_colour, fg=self.text_colour))

            self.loadfolderbutton.bind("<Enter>", lambda e: self.loadfolderbutton.config(bg=self.button_press_colour, fg=self.pressed_text_colour))
            self.loadfolderbutton.bind("<Leave>", lambda e: self.loadfolderbutton.config(bg=self.button_colour, fg=self.text_colour))

            self.loadpathentry.bind("<FocusIn>", lambda e: self.loadpathentry.config(bg=self.text_field_activated_colour, fg=self.text_field_activated_text_colour))
            self.loadpathentry.bind("<FocusOut>", lambda e: self.loadpathentry.config(bg=self.text_field_colour, fg=self.text_field_text_colour))
    def initial_dock_setup(self):
        #Left
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
        #Right
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
    def guisetup(self, destinations):
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
        self.sortbydate_button.destroy() # Hide sortbydate button after it is no longer needed
        sdpEntry = self.sdpEntry
        ddpEntry = self.ddpEntry
        sdpEntry.config(state=tk.DISABLED)
        ddpEntry.config(state=tk.DISABLED)
        panel = self.panel
        buttonframe = self.buttonframe
        hotkeys = self.hotkeys
        for key in hotkeys:
            self.unbind_all(key)
        for x in self.buttons:
            x.destroy()  # clear the gui

        panel.destroy()
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
        arrowkeys = ["<Up>", "<Down>", "<Left>", "<Right>"]
        for arrowkey in arrowkeys: # Binding arrow keys to navigator
            self.bind_all(f"{arrowkey}", partial(self.fileManager.navigator.bindhandler))
        for x in destinations:
            color = x['color']
            if x['name'] != "SKIP" and x['name'] != "BACK":
                if(itern < len(hotkeys)):
                    newbut = tk.Button(buttonframe, text=hotkeys[itern] + ": " + x['name'], command=partial(
                        self.fileManager.setDestination, x, {"widget": None}), anchor="w", wraplength=(self.leftui.winfo_width()/columns)-1)
                    seed(x['name'])
                    self.bind_all(f"<KeyPress-{self.hotkeys[itern]}>", partial(
                        self.fileManager.setDestination, x))
                    #self.bind_all(f"<KeyRelease-{hotkeys[itern]}>", partial(
                    #    self.handle_setdestination_call, False, None))
                    #canvas.bind('<Right>', lambda event: (canvas.after_idle(self.navigator, event), self.navigation_key_pressed_toggle(True)))
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
            ToolTip(newbut,msg="Rightclick to show images assigned to this destination",delay=1)
            if len(x['name']) > 20:
                newbut.config(font=smallfont)
            newbut.dest = x
            if guirow > ((self.leftui.winfo_height()/35)-2):
                guirow = 1
                guicol += 1
            newbut.grid(row=guirow, column=guicol, sticky="nsew")
            newbut.bind("<Button-3>", partial(self.showthisdest, x))

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
            self.entryframe.grid_remove()
        # options frame
        optionsframe = tk.Frame(self.leftui,bg=self.main_colour)
        optionsframe.columnconfigure(0, weight=1)
        optionsframe.columnconfigure(1, weight=3)
        optionsframe.grid(row=0, column=0, sticky="ew")

        self.squaresperpageentry = tk.Entry(
            optionsframe, textvariable=self.squaresperpage, takefocus=False, background=self.text_field_colour, foreground=self.text_field_text_colour)
        if self.squaresperpage.get() < 0: #this wont let you save -1
            self.squaresperpage.set(1)
        ToolTip(self.squaresperpageentry,delay=1,msg="How many more images to add when Load Images is clicked")
        self.squaresperpageentry.grid(row=1, column=0, sticky="EW",)
        for n in range(0, itern):
            self.squaresperpageentry.unbind(hotkeys[n])

        self.addpagebut = tk.Button(
            optionsframe, text="Load More Images", command=self.gridmanager.load_more,bg=self.button_colour, fg=self.text_colour, activebackground = self.button_press_colour, activeforeground=self.pressed_text_colour)
        ToolTip(self.addpagebut,msg="Add another batch of files from the source folders.", delay=1)
        self.addpagebut.grid(row=1, column=1, sticky="EW")
        self.addpagebutton = self.addpagebut

        # save button
        self.savebutton = tk.Button(optionsframe,text="Save Session",command=partial(self.fileManager.savesession,True),bg=self.button_colour, fg=self.text_colour, activebackground = self.button_press_colour, activeforeground=self.pressed_text_colour)
        ToolTip(self.savebutton,delay=1,msg="Save this image sorting session to a file, where it can be loaded at a later time. Assigned destinations and moved images will be saved.")
        self.savebutton.grid(column=0,row=0,sticky="ew")
        self.savebutton.configure(relief = tk.RAISED)

        self.moveallbutton = tk.Button(
            optionsframe, text="Move All", command=self.fileManager.moveall,bg=self.button_colour, fg=self.text_colour, activebackground = self.button_press_colour, activeforeground=self.pressed_text_colour)
        ToolTip(self.moveallbutton,delay=1,msg="Move all images to their assigned destinations, if they have one.")
        self.moveallbutton.grid(column=1, row=2, sticky="EW")

        self.clearallbutton = tk.Button(
            optionsframe, text="Clear Selection", command=self.fileManager.clear,bg=self.button_colour, fg=self.text_colour, activebackground = self.button_press_colour, activeforeground=self.pressed_text_colour)
        ToolTip(self.clearallbutton,delay=1,msg="Clear your selection on the grid and any other windows with checkable image grids.")
        self.clearallbutton.grid(row=0, column=1, sticky="EW")

        if self.interactive_buttons:
            #Option for making the buttons change color on hover
            self.clearallbutton.bind("<Enter>", lambda e: self.clearallbutton.config(bg=self.button_press_colour, fg=self.pressed_text_colour))
            self.clearallbutton.bind("<Leave>", lambda e: self.clearallbutton.config(bg=self.button_colour, fg=self.text_colour))

            self.addpagebut.bind("<Enter>", lambda e: self.addpagebut.config(bg=self.button_press_colour, fg=self.pressed_text_colour))
            self.addpagebut.bind("<Leave>", lambda e: self.addpagebut.config(bg=self.button_colour, fg=self.text_colour))

            self.moveallbutton.bind("<Enter>", lambda e: self.moveallbutton.config(bg=self.button_press_colour, fg=self.pressed_text_colour))
            self.moveallbutton.bind("<Leave>", lambda e: self.moveallbutton.config(bg=self.button_colour, fg=self.text_colour))

            self.savebutton.bind("<Enter>", lambda e: self.savebutton.config(bg=self.button_press_colour, fg=self.pressed_text_colour))
            self.savebutton.bind("<Leave>", lambda e: self.savebutton.config(bg=self.button_colour, fg=self.text_colour))

            self.squaresperpageentry.bind("<FocusIn>", lambda e: self.squaresperpageentry.config(bg=self.text_field_activated_colour, fg=self.text_field_activated_text_colour))
            self.squaresperpageentry.bind("<FocusOut>", lambda e: self.squaresperpageentry.config(bg=self.text_field_colour, fg=self.text_field_text_colour))

        custom_buttons_frame  = tk.Frame(self.leftui,bg=self.main_colour)
        custom_buttons_frame.grid(row = 1, column = 0, sticky = "ew")
        custom_buttons_frame.columnconfigure(0, weight = 1)
        custom_buttons_frame.columnconfigure(1, weight = 1)
        custom_buttons_frame.columnconfigure(2, weight = 1)
        custom_buttons_frame.columnconfigure(3, weight = 1)
        custom_buttons_frame.columnconfigure(4, weight = 1)

        self.show_next_button = ttk.Checkbutton(custom_buttons_frame, text="Show next", variable=self.show_next, onvalue=True, offvalue=False)
        self.dock_view_button = ttk.Checkbutton(custom_buttons_frame, text="Dock view", variable=self.dock_view, onvalue=True, offvalue=False, command=lambda: (self.change_viewer()))
        self.dock_side_button = ttk.Checkbutton(custom_buttons_frame, text="Dock side", variable=self.dock_side, onvalue=True, offvalue=False, command=lambda: (self.change_dock_side()))

        if self.dock_view.get():
            self.dock_side_button.state(['!disabled'])
        else:
            self.dock_side_button.state(['disabled'])

        self.show_next_button.grid(row=0, column=1, sticky="ew")
        self.dock_view_button.grid(row=0, column=2, sticky="ew")
        self.dock_side_button.grid(row=0, column=3, sticky="ew")

        self.show_next_button.configure(style="Theme_checkbox.TCheckbutton")
        self.dock_view_button.configure(style="Theme_checkbox.TCheckbutton")
        self.dock_side_button.configure(style="Theme_checkbox.TCheckbutton")

        view_options = ["Show Unassigned", "Show Assigned", "Show Moved", "Show Animated"]
        self.current_view = tk.StringVar()
        self.current_view.trace_add("write", lambda *args: self.current_view_changed(self.current_view.get()))
        self.current_view.set(view_options[0])

        option_menu = tk.OptionMenu(optionsframe, self.current_view, *view_options)
        option_menu.config(bg=self.button_colour, fg=self.text_colour,activebackground=self.button_press_colour, activeforeground=self.pressed_text_colour, highlightbackground=self.button_colour, highlightthickness=1)
        option_menu.grid(row = 2, column = 0, sticky = "EW")


        centering_options = ["Center", "Only x centering", "Only y centering", "No centering"]
        centering_preference = tk.StringVar()
        centering_preference.trace_add("write", lambda *args: self.change_centering(centering_preference.get()))
        centering_preference.set(centering_options[0])

        self.centering_options_button = tk.OptionMenu(custom_buttons_frame, centering_preference, *centering_options)
        self.centering_options_button.config(bg=self.button_colour, fg=self.text_colour,activebackground=self.button_press_colour, activeforeground=self.pressed_text_colour, highlightbackground=self.main_colour, highlightthickness=1)


        if self.extra_buttons:
            self.centering_options_button.grid(row=0, column=4, sticky="ew")
            # If extra buttons is true, we should load the correct text for the centering button.
            if self.viewer_x_centering and self.viewer_y_centering:
                centering_preference.set("Center")
            elif self.viewer_x_centering and not self.viewer_y_centering:
                centering_preference.set("Only x centering")
            elif not self.viewer_x_centering and self.viewer_y_centering:
                centering_preference.set("Only y centering")
            else:
                centering_preference.set("No centering")

        self.bind_all("<Button-1>", self.setfocus)
    
    "Exclude window"
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
    
    "Navigation / options"
    def uncheck_show_next(self):
        self.focused_on_secondwindow = False
    def change_viewer(self):
        other_viewer_is_open = hasattr(self, 'second_window') and self.second_window and self.second_window.winfo_exists()
        if self.middlepane_frame.winfo_width() != 1:
            self.middlepane_width = self.middlepane_frame.winfo_width() #this updates it before middlepane is closed.

        self.middlepane_frame.configure(width = self.middlepane_width)
        self.focused_on_secondwindow = False

        if self.started_not_integrated:
            self.toppane.forget(self.middlepane_frame)
            self.started_not_integrated = False

        if self.dock_view.get():
            self.dock_side_button.state(['!disabled'])
            if other_viewer_is_open: # This also means dock_view was changed, so we should open the previous image displayed, if show_next is on.
                self.close_second_window() # Closes it
                self.displayimage(self.fileManager.navigator.old)

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
                        self.Image_frame.destroy()
                        del self.Image_frame
                        self.displayimage(self.fileManager.navigator.old) # If something was displayed, we want to display it in standalone viewer.
            except Exception as e:
                pass
        bindhandler_1(self.imagegrid)
    def change_dock_side(self):
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
            self.displayimage(self.fileManager.navigator.old)
    def current_view_changed(self, selected_option):
        if self.fix:
            self.fix = False
            return
        "When view is changed, tells grid to display that view"
        new_squares = []
        if selected_option == "Show Unassigned":
            list_to_display = self.gridmanager.unassigned
        elif selected_option == "Show Assigned":
            list_to_display = self.gridmanager.assigned
        elif selected_option == "Show Moved":
            list_to_display = self.gridmanager.moved
        elif selected_option == "Show Animated":
            list_to_display = [x for x in self.gridmanager.unassigned if x.obj.isanimated]
        self.gridmanager.current_list = list_to_display
        self.gridmanager.change_view(list_to_display)
        self.fileManager.navigator.view_change(self.gridmanager.displayedlist)
    def setfocus(self, event):
        event.widget.focus_set()
    
    "CanvasImage"        
    def displayimage(self, frame): #Create secondary window for image viewing
        imageobj = frame.obj
        items_per_row = int(max(1, self.imagegrid.winfo_width() / self.actual_gridsquare_width))
        row, col = map(int, self.imagegrid.index(tk.INSERT).split('.'))
        logger.debug(f"Row: {items_per_row}, Column: {col}, and {self.thumbnailsize} and {self.imagegrid.winfo_width()}")

        # This makes sure the initial view is set up correctly
        if self.middlepane_frame.winfo_width() != 1:
                self.middlepane_width = self.middlepane_frame.winfo_width()
        
        path = imageobj.path
        # Close already open windows, IF: integrated viewer option is on, BUT KEEP OPEN IF show next is on. (Calls not made by user)
        if hasattr(self, 'second_window') and self.second_window and not self.show_next.get(): # Call not made by user, but sortimages
            self.close_second_window()
        elif hasattr(self, 'second_window') and self.second_window and self.dock_view.get():
            self.close_second_window()

        if self.dock_view.get(): # This handles the middlepane viewer. Runs, IF second window is closed.
            geometry = str(self.middlepane_width) + "x" + str(self.winfo_height())
            self.Image_frame = CanvasImage(self.middlepane_frame, geometry, self.canvasimage_background, imageobj, self)
            self.Image_frame.grid(row = 0, column = 0, sticky = "NSEW")
            self.Image_frame.default_delay.set(self.default_delay.get()) #tell imageframe if animating, what delays to use
            self.Image_frame.rescale(min(self.middlepane_width / self.Image_frame.imwidth, self.winfo_height() / self.Image_frame.imheight))  # Scales to the window
            self.Image_frame.center_image()
            logger.debug("Rescaled and Centered")

            self.focused_on_secondwindow = True

            self.Image_frame.canvas.focus_set()
            self.old_img_frame.append(self.Image_frame)
            return

        # Standalone image viewer
        if not hasattr(self, 'second_window') or not self.second_window or not self.second_window.winfo_exists():
            # No window exists, create one

            self.second_window = tk.Toplevel(background=self.main_colour) #create a new window
            second_window = self.second_window
            second_window.rowconfigure(0, weight=1)
            second_window.columnconfigure(0, weight=1)
            second_window.geometry(self.viewer_geometry)
            second_window.bind("<Button-3>", self.close_second_window)
            second_window.protocol("WM_DELETE_WINDOW", self.close_second_window)
            second_window.obj = imageobj
            second_window.transient(self)

        self.second_window.title("Image: " + path)
        geometry = self.viewer_geometry.split('+')[0]
        x, y = geometry.split('x')
        self.Image_frame = CanvasImage(self.second_window, geometry, self.canvasimage_background, imageobj, self)
        self.Image_frame.default_delay.set(self.default_delay.get()) #tell imageframe if animating, what delays to use
        self.Image_frame.grid(row = 0, column = 0, sticky = "NSEW")  # Initialize Frame grid statement in canvasimage, Add to main window grid
        self.Image_frame.rescale(min(int(x) / self.Image_frame.imwidth, int(y) / self.Image_frame.imheight))  # Scales to the window
        self.Image_frame.center_image()

        logger.debug("Rescaled and Centered")
        self.focused_on_secondwindow = True
        self.old_img_frame.append(self.Image_frame)

        if not self.show_next.get():
            self.second_window.after(0, lambda: self.Image_frame.canvas.focus_set())
        else:
            self.second_window.after(0, lambda: self.Image_frame.canvas.focus_set())
        pass
        

    "DESTINATION WINDOW"
    def showthisdest(self, dest, *args): #If a destination window is already open, just update it.

        self.dest = dest['path']
        if not hasattr(self, 'destwindow') or not self.destwindow or not self.destwindow.winfo_exists():
            #Make new window
            self.destwindow = tk.Toplevel()
            self.destwindow.columnconfigure(0, weight=1)
            self.destwindow.rowconfigure(0, weight=1)
            self.destwindow.winfo_toplevel().title("Files designated for " + dest['path'])
            self.destwindow.geometry(str(int(self.winfo_screenwidth() * 0.80)) + "x" + str(self.winfo_screenheight() - 120) + "+365+60")
            self.destwindow.bind("<Button-3>", self.close_destination_window)
            self.destwindow.protocol("WM_DELETE_WINDOW", self.close_destination_window)
            self.destwindow.transient(self)

            if self.destpane_geometry != 0:
                try:
                    self.destwindow.geometry(self.destpane_geometry)
                except Exception as e:
                    logger.error(f"Couldn't load destwindow geometry")

            self.destgrid = tk.Text(self.destwindow, wrap='word', borderwidth=0,
                                    highlightthickness=0, state="disabled", background=self.main_colour)
            self.destgrid.grid(row=0, column=0, sticky="NSEW")

            #scrollbars
            vbar = tk.Scrollbar(self.destwindow, orient='vertical',
                                command=lambda *args: throttled_yview(self.destgrid, self.page_mode, *args))
            vbar.grid(row=0, column=1, sticky='ns')
            self.destgrid['yscrollcommand'] = vbar.set  # Link scrollbar to text widget
        else:
            pass

        # Refresh the destinations and set the active window
        self.filtered_images = []
        self.refresh_destinations()
    def refresh_destinations(self): #so when view changes, squarelist is updated, the

        if hasattr(self, 'destgrid') and self.destgrid: #If a destination window is open
            destgrid = self.destgrid
            dest_path = self.dest
            #make a list of destination pics to compare current squarelist against.
            #to rollback to this just delete self.combined_squarelists from sortimages.
            combined_squarelist = self.gridmanager.assigned + self.gridmanager.moved
            #combined_squarelist = self.combined_squarelist
            temp = False
            #here jut replace filtere_images with unique dest list.
            #what if just 1 list like this, add only if dest is same. So we generate it once per switch ,then just add to it.
            if not self.filtered_images:
                temp = True
                self.filtered_images = [gridsquare.obj for gridsquare in combined_squarelist if gridsquare.obj.dest == dest_path]
            filtered_images = self.filtered_images


            #this basically regenerates squares that we want to change place in the gridview.

            try:
                for gridsquare in self.destgrid_updateslist: #the list to remove.
                    if gridsquare.obj in filtered_images:
                        try: #remove old placement
                            self.destgrid.window_configure(gridsquare, window="")
                        except Exception as e:
                            logger.error(f"Error configuring window for image {gridsquare.obj}: {e}")
                        self.dest_squarelist.remove(gridsquare) ##remove pic from squarelist  so it is generated again!
                        self.queue.append(gridsquare) #this adds to the queue to be generated along new ones.
                        self.destgrid_updateslist.remove(gridsquare) # remove from updateslist as the task is compelte
            except Exception as e:
                logger.error(f"Error in refresh_destinations {e}")

            # Add new images to the destination grid #-- we can still add a changed_ list here.
            #basically at initial load, check the whole list, then subsequently, we can only check the changed.
            #initial load filtere_images

            #updates only queue?
            if temp:
                for img in filtered_images:
                    if not any(gridsquare.obj == img for gridsquare in self.dest_squarelist):
                        new_frame = self.makegridsquare(self.destgrid, img, False, True)
                        color = next((d['color'] for d in self.fileManager.destinations if d['path'] == img.dest), None)
                        if color:
                            new_frame['background'] = color
                            new_frame.children['!canvas']['background'] = color  # Assuming the canvas is the first child

                        canvas_window_id = self.destgrid.window_create("1.0", window=new_frame)
                        new_frame.canvas_id = canvas_window_id
                        self.dest_squarelist.append(new_frame)
                        new_frame.obj.isvisibleindestination = True
            else:
                for square in self.queue:
                    new_frame = self.makegridsquare(self.destgrid, square.obj, False, True)
                    color = next((d['color'] for d in self.fileManager.destinations if d['path'] == square.obj.dest), None)
                    if color:
                        new_frame['background'] = color
                        new_frame.children['!canvas']['background'] = color  # Assuming the canvas is the first child

                    canvas_window_id = self.destgrid.window_create("1.0", window=new_frame)
                    new_frame.canvas_id = canvas_window_id
                    self.dest_squarelist.append(new_frame)
                    new_frame.obj.isvisibleindestination = True
                    self.queue.remove(square)
            # Remove images no longer present #this can be done like filtered list too. just record all deletes.
            to_remove = [] #OPTIMIZE
            for gridsquare in self.dest_squarelist:
                if gridsquare.obj not in filtered_images:
                    try:
                        self.destgrid.window_configure(gridsquare, window="")
                    except Exception as e:
                        logger.error(f"Error configuring window for image {gridsquare.obj}: {e}")
                    to_remove.append(gridsquare)

            # Remove gridsquares from the list
            for gridsquare in to_remove:
                self.dest_squarelist.remove(gridsquare)
                gridsquare.obj.isvisibleindestination = False
            self.start_gifs_destination()
    def start_gifs_destination(self): # Check if images in the current destination view are animated or not.
        for i in self.dest_squarelist:
            if i.obj.isanimated and i.obj.isvisibleindestination: # This prevents the same .gif or .webp having two or more loops at the same time, causing the index counting to double in speed.
                self.animate_destination(i, 0)
    def animate_destination(self, i, index):  # Frame by frame animation
        if i in self.track_animated: return
        if not i.obj.isvisibleindestination: 
            self.track_animated.remove(i)
            return
        self.track_animated.append(i)
        print(index)
        i.canvas.itemconfig(i.canvas_image_id, image=i.obj.frames[index])  # Change the frame
        index = (index + 1) % i.obj.framecount
        i.canvas.after(i.obj.frametimes[index], lambda: self.animate_destination(i, index)) #run again.

    "Exit function"
    def closeprogram(self):
        if len(self.gridmanager.assigned) != 0:
            if askokcancel("Designated but Un-Moved files, really quit?","You have destination designated, but unmoved files. (Simply cancel and Move All if you want)"):
                self.close_second_window()
                self.close_destination_window()
                self.fileManager.saveprefs(self)
                self.destroy()
        else:
            self.close_second_window()
            self.close_destination_window()
            self.fileManager.saveprefs(self)
            self.destroy()
    def close_second_window(self, event=None):
        if hasattr(self, 'Image_frame'):
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
            d = tkFileDialog.askopenfile(initialdir=getcwd(
            ), title="Select Session Data File", filetypes=(("JavaScript Object Notation", "*.json"),))
            path = d.name
        if isinstance(target, tk.Entry):
            target.delete(0, tk.END)
            target.insert(0, path)
    def close_destination_window(self, event=None):
        if event:
            for square in self.dest_squarelist:
                if square.winfo_x() <= event.x <= square.winfo_x() + square.winfo_width() and \
                   square.winfo_y() <= event.y <= square.winfo_y() + square.winfo_height():
                    logger.debug("Click inside a square, not closing.")
                    return  # Click is inside a square, do not close

        try:
            if hasattr(self, 'destwindow'):
                self.destpane_geometry = self.destwindow.winfo_geometry()
                self.destgrid.destroy()
                del self.destgrid
                self.destwindow.destroy()
                self.destwindow = None
                del self.destwindow
                self.dest_squarelist = []
                self.filtered_images = []
                self.queue = []
        except Exception as e:
            pass

class GridManager:
    def __init__(self, fileManager):
        self.fileManager = fileManager
        self.gui = fileManager.gui
        self.gridsquarelist = []
        self.displayedlist = [] #could be dict
        self.unassigned = []
        self.assigned = []
        self.moved = []
        self.animated = []
        self.current_list = []
    def truncate_text(self, imageobj): #max_length must be over 3+extension or negative indexes happen.
            filename = imageobj.name.get()
            base_name, ext = path.splitext(filename)
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
    
    def makegridsquare(self, parent, imageobj, setguidata, dest):
        
        def tooltiptext(imageobject):
            text=""
            text += "Leftclick to select this for assignment. Rightclick to open full view"
            return text 
    
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
            #tooltiptext=tk.StringVar(frame,self.gui.tooltiptext(imageobj)) #CHECK PROFILE
            #ToolTip(canvas,msg=tooltiptext.get,delay=1) #CHECK PROFILE
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

            #Create different dest for destinations to control view better. These also call a command to cancel the viewer image from being moved by keypresses, if we interact with other gridsquares first.
            if not dest:
                check = ttk.Checkbutton(check_frame, textvariable=truncated_name_var, variable=imageobj.checked, onvalue=True, offvalue=False, command=lambda: (self.gui.uncheck_show_next()), style="Theme_square.TCheckbutton")
            else:
                check = ttk.Checkbutton(check_frame, textvariable=truncated_name_var, variable=imageobj.destchecked, onvalue=True, offvalue=False, command=lambda: (self.gui.uncheck_show_next()), style="Theme_square.TCheckbutton")
            check.grid(sticky="NSEW")

            if(setguidata):  # save the data to the image obj to both store a reference and for later manipulation
                imageobj.setguidata(
                    {"img": img, "frame": frame, "canvas": canvas, "check": check, "show": True}) #"tooltip":tooltiptext
            frame.c = check
            # anything other than rightclicking toggles the checkbox, as we want.
            canvas.bind("<Button-1>", partial(bindhandler, check, "invoke"))
            canvas.bind("<Button-3>", lambda e: (self.fileManager.navigator.select(frame)))
            check.bind("<Button-3>", lambda e: (self.fileManager.navigator.select(frame)))

            #make blue if only one that is blue, must remove other blue ones. blue ones are stored the gridsquare in a global list.
            canvas.bind("<MouseWheel>", partial(
                bindhandler, parent, "scroll"))
            frame.bind("<MouseWheel>", partial(
                bindhandler, self.gui.imagegrid, "scroll"))

            check.bind("<MouseWheel>", partial(
                bindhandler, self.gui.imagegrid, "scroll"))

            if imageobj.moved:
                frame.configure(
                    highlightbackground="green", highlightthickness=2)
                if path.dirname(imageobj.path) in self.fileManager.destinationsraw:
                    color = self.fileManager.destinations[indexOf(
                        self.fileManager.destinationsraw,path.dirname(imageobj.path))]['color']
                    frame['background'] = color
                    canvas['background'] = color
        except Exception as e:
            logger.error(e)
        return frame

    def load_session(self, imagefiles):
        for obj in imagefiles:
            gridsquare = self.makegridsquare(self.gui.imagegrid, obj, True, False)
            if obj.dest != "":
                self.assigned.append(gridsquare)
            elif obj.moved:
                self.moved.append(gridsquare)
        self.gridsquarelist.extend(self.assigned)
        self.gridsquarelist.extend(self.moved)
        print(f"gg{len(self.gridsquarelist)}: {len(self.assigned)}: {len(self.moved)}: {len(self.animated)}")
        self.initialize()
   
    def initialize(self):
        self.load_more(True)
    def load_more(self, initialize=False) -> None:
        a = perf_counter()
        # 1. get list of the loadable items
        # 2. make gridsquares for them
        # 3. display them in grid (placeholders).
        # 4. generate thumbnails for them. (Threaded)
        filelist = self.fileManager.imagelist
        items = min(self.gui.squaresperpage.get(), len(filelist)-len(self.gridsquarelist)) # How many we want to load or can load.
        print("Load more attempt:", items)
        if items == 0:
            self.gui.addpagebutton.configure(text="No More Images!",background="#DD3333")
            return
        print("Load more attempt::", items)
        sublist = filelist[len(self.gridsquarelist):len(self.gridsquarelist)+items] # List from current up to new desired limit. This slice contains the next x imageobjects.
        generated = [] # Store created gridsquares
        for obj in sublist:
            gridsquare = self.makegridsquare(self.gui.imagegrid, obj, True, False)
            generated.append(gridsquare)
        #self.imagegridframe.update() #necessary?
        self.unassigned.extend(generated)
        self.gridsquarelist.extend(generated)
        self.add_squares(generated, reload=False)
        print(f"Displayed grid in: {perf_counter()-a:.2f}")
        self.fileManager.thumbs.generate(generated) # This thread shouldnt be stopped at any time. Used to get info on frames and such that reload wont do.
        
        print(f"{len(self.gridsquarelist)}: {len(self.assigned)}: {len(self.moved)}: {len(self.animated)}")
    
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
            if gridsquare.obj.guidata['img'] == None: # Checks if img is unloaded
                regen.append(gridsquare)
        if regen and reload:
            self.fileManager.thumbs.reload(regen) # Threads the reloading process.

    def remove_squares(self, squares: list, unload) -> None:
        "Removes square from grid, displayedlist, and can unload it from memory"
        for gridsquare in squares:
            self.gui.imagegrid.window_configure(gridsquare, window="")
            self.displayedlist.remove(gridsquare)
            if unload:
                self.fileManager.thumbs.unload(gridsquare)
        if unload:
            print("Unloading:", len(squares))

    def change_view(self, squares) -> None:
        "Remove all squares from grid, but add them back without unloading according how they should be ordered."
        # This is called when the view is called to avoid old frames in the new list from not being deleted
        # Squares is the whole new list to be displayed
        not_in_new_list = [x for x in self.displayedlist if x not in squares] # Unload their thumbs and frames.
        in_both_lists = [x for x in self.displayedlist if x in squares] # Remove them from gridview. But dont unload
        if not_in_new_list: # Normal remove
            self.remove_squares(not_in_new_list, unload=True)
        if in_both_lists: # Remove but without unloading from memory. We want to readd these.
            self.remove_squares(in_both_lists, unload=False)
        if squares: # Only try if there is a need.
            self.add_squares(squares) # This will know if thumb is loaded or not and will reload as needed.

    def display_squares(self, squarelist):
        "Displays the given list."
        print(f"{len(self.gridsquarelist)}: {len(self.assigned)}: {len(self.moved)}: {len(self.animated)} : d: {len(self.displayedlist)}")




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
