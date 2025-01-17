import os

from gc import collect

import tkinter as tk
from tkinter import ttk

def import_pyvips():
    base_path = os.path.dirname(os.path.abspath(__file__))
    vipsbin = os.path.join(base_path, "vips-dev-8.16", "bin")
    
    # Check if the vipsbin directory exists
    if not os.path.exists(vipsbin):
        raise FileNotFoundError(f"The directory {vipsbin} does not exist.")

    os.environ['PATH'] = os.pathsep.join((vipsbin, os.environ['PATH']))
    os.add_dll_directory(vipsbin)
import_pyvips()
try:
    import pyvips
except Exception as e:
    print("Couldn't import pyvips:", e)

#This module is more or less contained. It has its own thumbmanager and animate methods as it is its own program, and I dont want to complicate'
# original method in sortimages. Maybe in the future do subclasses or inheritance or similar to replace these.
class Destination_Viewer():
    def __init__(self, fileManager):
        self.fileManager = fileManager
        self.gui = fileManager.gui
        style = ttk.Style()
        style.configure("Theme_square.TCheckbutton", background=self.gui.grid_background_colour, foreground=self.gui.button_text_colour)
        self.displayedlist = []
        self.window_is_closing = False

    def set_thumbmanager_and_animate(self):
        self.animate = self.fileManager.animate
        self.thumbs = self.fileManager.thumbs
    def get_paths(self):
        "Create a list for every buttondest" "If loadsession=True, sort everything from assigned and moved to the lists"
        # Dest lists are created at load time from loadsession. If no loadsession, lists are still constructed, but destsquares added to them via setdest
        self.paths = []
        for x in self.gui.buttons:
            #x['bg'] refers to tkinter background color. x.dest['path'] to path name.
            self.paths.append(x.dest['path'])

    def create_window(self, *args):
        if hasattr(self, 'destwindow'):
            self.close_window(reopenargs=args, reopen=True)
            return
        self.window_is_closing = False
        button_info = args[1]
        self.dest_path = button_info['path']
        self.dest_color = button_info['color']
        self.displayedlist = []
        self.displayedlist_ids = [] #make set?
        self.displayedset = set()
        self.animated = []
        self.destwindow = tk.Toplevel()
        self.destwindow.columnconfigure(0, weight=1)
        self.destwindow.rowconfigure(0, weight=1)
        self.destwindow.geometry(self.gui.destpane_geometry)
        self.destwindow.bind("<Button-3>", lambda a: self.close_window(a, event=True))
        self.destwindow.protocol("WM_DELETE_WINDOW", self.close_window)
        self.destwindow.transient(self.gui)
        self.destgrid = tk.Text(self.destwindow, wrap='word', borderwidth=0,
                                 highlightthickness=0, state="disabled", background=self.gui.main_colour)
        self.destgrid.pack(expand=True, fill='both')
            #self.destwindow.update()
            #self.destgrid.update()
        self.destwindow.winfo_toplevel().title(f"Files designated for {self.dest_path}")
        #method to populate according to dest_path
        self.change_view(self.dest_path)

    def change_view(self, dest) -> None:
        # Check all in assigned and moved lists. If the path matches (assigned), and for moved, path matches, makedestsquare.
        create_list = []
        for x in self.gui.gridmanager.gridsquarelist:
            if x.obj.dest == self.dest_path:
                create_list.append((x.obj, "add"))
            elif x.obj.moved and x.obj.path == dest:
                create_list.append((x.obj, "add"))
        self.add_squares(create_list)

    def add_squares(self, imagetuples: list) -> None:
        "Adds squares to grid, displayedlist, and reloads them"
        # we get obj make square and add it. # 0 is obj, 1 is action
        new = []
        regen = []
        for obj in imagetuples:
            if obj[1] == "add":
                new.append((self.makedestsquare(obj[0]), "add"))
            elif obj[1] == "refresh":
                new.append((obj[0], "refresh")) # add destsquare

        for gridsquare in new:
            if gridsquare[1] == "add":
                self.destgrid.window_create(
                "1.0", window=gridsquare[0], padx=self.gui.gridsquare_padx, pady=self.gui.gridsquare_pady)
                self.displayedlist.append(gridsquare[0])
                self.displayedlist_ids.append(gridsquare[0].obj.id)
                self.displayedset.add(gridsquare[0])
                
            elif gridsquare[1] == "refresh":
                self.destgrid.window_configure(gridsquare[0], window="")
                self.displayedlist.remove(gridsquare[0])
                self.displayedlist_ids.remove(gridsquare[0].obj.id)
                self.destgrid.window_create(
                "1.0", window=gridsquare[0], padx=self.gui.gridsquare_padx, pady=self.gui.gridsquare_pady)
                self.displayedlist.append(gridsquare[0])
                self.displayedlist_ids.append(gridsquare[0].obj.id)
            
            if gridsquare[0].canvas.image == None: # Checks if img is unloaded
                regen.append(gridsquare[0])
            
        if regen:
            self.thumbs.generate(regen, dest=True) # Threads the reloading process. #need private attribute for dest and grid separate.

    def remove_squares(self, squares: list, unload) -> None:
        "Removes square from grid, displayedlist, and can unload it from memory"
        
        unload_list = []
        for gridsquare in squares:
            if gridsquare in self.displayedset:
                self.destgrid.window_configure(gridsquare, window="")
                self.displayedlist.remove(gridsquare)
                self.displayedlist_ids.remove(gridsquare.obj.id)
                self.displayedset.discard(gridsquare)
                if unload:
                    unload_list.append(gridsquare)
        if unload:
            self.thumbs.unload(unload_list)
            print("Unloading:", len(unload_list))

    def makedestsquare(self, imageobj):

        frame = tk.Frame(self.destgrid, borderwidth=0,
                         highlightthickness = self.gui.whole_box_size, highlightcolor=self.gui.square_default,highlightbackground=self.gui.square_default, padx = 0, pady = 0)
        #search from dict or generate again.
        frame.obj = imageobj
        truncated_filename = imageobj.truncated_filename
        truncated_name_var = tk.StringVar(frame, value=truncated_filename)
        frame.obj2 = truncated_name_var # This is needed or it is garbage collected I guess
        frame.grid_propagate(True)

        try:
            canvas = tk.Canvas(frame, width=self.gui.thumbnailsize,
                               height=self.gui.thumbnailsize,bg=self.gui.square_default, highlightthickness=self.gui.square_border_size, highlightcolor=self.gui.square_default, highlightbackground = self.gui.square_default) #The gridbox color.
            canvas.grid(column=0, row=0, sticky="NSEW")

            img = None
            canvas.image = img
#
            frame.canvas = canvas
            frame.type = "DEST"
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
            check = ttk.Checkbutton(check_frame, textvariable=truncated_name_var, variable=imageobj.checked, onvalue=True, offvalue=False, command=lambda: (setattr(self.gui, 'focused_on_secondwindow', False)), style="Theme_square.TCheckbutton")
            check.grid(sticky="NSEW")
#
            ## save the data to the image obj to both store a reference and for later manipulation
            imageobj.guidata["destframe"] = frame
            frame.c = check
            # anything other than rightclicking toggles the checkbox, as we want.
            canvas.bind("<Button-1>", lambda e: check.invoke())
            canvas.bind("<Button-3>", lambda e: (self.fileManager.navigator.dest_select(frame)))
            check.bind("<Button-3>", lambda e: (self.fileManager.navigator.dest_select(frame)))

            #make blue if only one that is blue, must remove other blue ones. blue ones are stored the gridsquare in a global list.
            canvas.bind("<MouseWheel>", lambda e: self.destgrid.yview_scroll(-1*int(e.delta/120), "units"))
            frame.bind("<MouseWheel>", lambda e: self.destgrid.yview_scroll(-1*int(e.delta/120), "units"))
            check.bind("<MouseWheel>", lambda e: self.destgrid.yview_scroll(-1*int(e.delta/120), "units")) #checkcrame too?

            frame['background'] = self.dest_color
            canvas['background'] = self.dest_color

        except Exception as e:
            print("Makedestsquare error:", e)
        return frame

    def close_window(self, *args, event=False, reopenargs=None, reopen=False):
        "Safely close everything"
        if event:
            event = args[0] # reappoint event variable to mouseEvent
            for square in self.displayedlist:
                if square.winfo_x() <= event.x <= square.winfo_x() + square.winfo_width() and \
                   square.winfo_y() <= event.y <= square.winfo_y() + square.winfo_height():
                    print("Click inside a square, not closing.")
                    return  # Click is inside a square, do not close
        self.window_is_closing = True

        for x in self.displayedlist:
            frame = x.obj.guidata.get("frame", None) # remove frame  from guidata.
            if not frame:
                x.obj.guidata['img'] = None
                if x.obj.frames:
                    self.fileManager.animate.remove_animation(x.obj)
                    x.obj.index = 0
                    x.obj.frames = []
                    x.obj.lazy_loading = True
            x.obj.guidata["destframe"] = None
        
        if self.fileManager.navigator.old in self.displayedset:
            self.fileManager.navigator.old = None
            
        for x in self.displayedlist:
            x.canvas.itemconfig(x.canvas_image_id, image=None)
            x.canvas.image = None
            x.canvas.destroy()
            x.destroy()
            del x.canvas
            del x
        del self.displayedlist_ids
        del self.animated
        del self.displayedlist
        del self.displayedset
        if hasattr(self, "destgrid"):
            self.destgrid.destroy()
            del self.destgrid
        if hasattr(self, "destwindow"):
            self.gui.destpane_geometry = self.destwindow.winfo_geometry()
            self.destwindow.destroy()
            del self.destwindow
        collect()

        if reopen == True:
            a, b = reopenargs
            self.create_window(a, b)
            self.fileManager.navigator.window_focused = "DEST"
            pass
        else:
            self.fileManager.navigator.window_focused = "GRID"
            self.fileManager.navigator.displayedlist = self.gui.gridmanager.displayedlist
