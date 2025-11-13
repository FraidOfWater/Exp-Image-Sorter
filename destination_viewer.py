import tkinter as tk
from tkinter import ttk
import os

class Destination_Viewer():
    def __init__(self, fileManager):
        self.fileManager = fileManager
        self.gui = fileManager.gui
        style = ttk.Style()
        style.configure("Theme_square.TCheckbutton", background=self.gui.grid_background_colour, foreground=self.gui.button_text_colour)
        self.displayedlist = []

    def create_window(self, *args):
        if hasattr(self, 'destwindow'):
            self.close_window(reopenargs=args, reopen=True)
            return
        button_info = args[1]
        self.dest_path = button_info['path']
        self.dest_color = button_info['color']
        self.displayedlist = []
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

        self.destwindow.winfo_toplevel().title(f"Files designated for {self.dest_path}")
        #method to populate according to dest_path
        self.change_view(self.dest_path)

    def change_view(self, dest) -> None:
        squares = self.gui.gridmanager.assigned + self.gui.gridmanager.moved # should be ordered...
        in_view = [x.obj for x in squares if os.path.normpath(x.obj.dest) == os.path.normpath(dest) or os.path.normpath(dest) in os.path.normpath(x.obj.path)]
        self.add_objs(in_view)

    def add_objs(self, objs):
        for obj in objs:
            square = self.makedestsquare(obj)
            self.destgrid.window_create(
            "1.0", window=square, padx=self.gui.gridsquare_padx, pady=self.gui.gridsquare_pady)
            self.displayedlist.append(square)
        objs = [obj for obj in objs if obj.thumb == None]
        if objs:
            self.fileManager.thumbs.generate(objs, dest=True)

    def add_squares(self, squares) -> None:
        "Adds squares to grid, displayedlist, and reloads them"
        # we get obj make square and add it. # 0 is obj, 1 is action
        for square in squares:
            self.destgrid.window_create(
            "1.0", window=square, padx=self.gui.gridsquare_padx, pady=self.gui.gridsquare_pady)
            self.displayedlist.append(square)
        squares = [square for square in squares if square.obj.thumb == None]
        if squares:
            self.fileManager.thumbs.generate(squares, dest=True) # Threads the reloading process. #need private attribute for dest and grid separate.

    def remove_squares(self, squares: list, unload=True) -> None:
        "Removes square from grid, displayedlist, and can unload it from memory"
        for gridsquare in squares:
            obj = gridsquare.obj
            self.destgrid.window_configure(gridsquare, window="")
            self.displayedlist.remove(gridsquare)
            if unload:
                gridsquare.canvas.itemconfig(gridsquare.canvas_image_id, image=None) # remove ref from current
                obj.destframe = None
                if not obj.frame: # only instance
                    obj.thumb = None
                    if obj.frames:
                        obj.clear_frames()
                obj.destsquare = None
            
    def refresh_squares(self, squares):
        self.remove_squares(squares, unload=False)
        self.add_squares(squares)

    def makedestsquare(self, imageobj):
        frame = tk.Frame(self.destgrid, borderwidth=0,
                         highlightthickness = self.gui.whole_box_size, highlightcolor=self.gui.square_default,highlightbackground=self.gui.square_default, padx = 0, pady = 0)
        #search from dict or generate again.
        frame.obj = imageobj
        truncated_filename = imageobj.truncated_filename
        truncated_name_var = tk.StringVar(frame, value=truncated_filename)
        frame.obj2 = truncated_name_var
        frame.grid_propagate(True)

        try:
            canvas = tk.Canvas(frame, width=self.gui.thumbnailsize,
                               height=self.gui.thumbnailsize,bg=self.gui.square_default, highlightthickness=self.gui.square_border_size, highlightcolor=self.gui.square_default, highlightbackground = self.gui.square_default) #The gridbox color.
            canvas.grid(column=0, row=0, sticky="NSEW")
#
            frame.canvas = canvas
            frame.type = "DEST"
            frame.rowconfigure(0, weight=4)
            frame.rowconfigure(1, weight=1)

            #Added reference for animation support. We use this to refresh the frame 1/20, 2/20..
            canvas_image_id = canvas.create_image(
                self.gui.thumbnailsize/2+self.gui.square_border_size, self.gui.thumbnailsize/2+self.gui.square_border_size, anchor="center", image=frame.obj.thumb) #If you use gridboxes, you must +1 to thumbnailsize/2, so it counteracts the highlighthickness.
            frame.canvas_image_id = canvas_image_id

            check_frame = tk.Frame(frame, height=self.gui.checkbox_height, padx= 2, bg=self.gui.square_text_box_colour)
            check_frame.grid_propagate(False)
            check_frame.grid(column=0, row=1, sticky="EW")  # Place the frame in the grid

            frame.cf = check_frame

            #Create different dest for destinations to control view better. These also call a command to cancel the viewer image from being moved by keypresses, if we interact with other gridsquares first.
            checked = tk.BooleanVar(value=False)
            check = ttk.Checkbutton(check_frame, textvariable=truncated_name_var, variable=checked, onvalue=True, offvalue=False, command=lambda: (setattr(self.gui, 'focused_on_secondwindow', False)), style="Theme_square.TCheckbutton")
            check.grid(sticky="EW")
#
            ## save the data to the image obj to both store a reference and for later manipulation
            imageobj.destframe = frame
            frame.c = check
            frame.checked = checked
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
            imageobj.destsquare = frame

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
                
        fileManager = self.fileManager
                
        for gridsquare in self.displayedlist:
            obj = gridsquare.obj

            obj.destframe = None
            if not obj.frame:
                obj.thumb = None
                if obj.frames:
                    obj.clear_frames()
            gridsquare.obj.destsquare = None
    
        for x in self.displayedlist:
            x.canvas.itemconfig(x.canvas_image_id, image=None)
            x.canvas.destroy()
            x.destroy()
            del x.canvas
            del x
        del self.displayedlist
        if hasattr(self, "destgrid"):
            self.destgrid.destroy()
            del self.destgrid
        if hasattr(self, "destwindow"):
            self.gui.destpane_geometry = self.destwindow.winfo_geometry()
            self.destwindow.destroy()
            del self.destwindow

        if reopen == True:
            a, b = reopenargs
            self.create_window(a, b)
            fileManager.navigator.window_focused = "DEST"
            pass
        else:
            fileManager.navigator.window_focused = "GRID"
            fileManager.navigator.displayedlist = self.gui.gridmanager.displayedlist
