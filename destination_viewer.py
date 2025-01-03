import os
from time import perf_counter

from PIL import Image, ImageTk
from imageio import get_reader
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

from threading import Thread
import concurrent.futures as concurrent

import tkinter as tk
from tkinter import ttk

import gc
#This module is more or less contained. It has its own thumbmanager and animate methods as it is its own program, and I dont want to complicate'
# original method in sortimages. Maybe in the future do subclasses or inheritance or similar to replace these.
class Destination_Viewer():
    def __init__(self, fileManager):
        self.fileManager = fileManager
        self.animate_dest = Animate()
        self.dest_thumbs = ThumbManager(self)
        self.gui = fileManager.gui
        style = ttk.Style()
        style.configure("Theme_square.TCheckbutton", background=self.gui.grid_background_colour, foreground=self.gui.text_colour)

    def get_paths(self, loadsession: bool):
        "Create a list for every buttondest" "If loadsession=True, sort everything from assigned and moved to the lists"
        # Dest lists are created at load time from loadsession. If no loadsession, lists are still constructed, but destsquares added to them via setdest
        self.paths = []
        for x in self.gui.buttons:
            #x['bg'] refers to tkinter background color. x.dest['path'] to path name.
            self.paths.append(x.dest['path'])
        if loadsession:
            moved = [x for x in self.fileManager if x.moved]
            assigned = [x for x in self.fileManager if x.dest]
            generate = moved+assigned
            for obj in generate:
                self.makedestsquare(obj)

    def create_window(self, *args):
        if hasattr(self, 'destwindow'):
            self.close_window()
        button_info = args[1]
        self.dest_path = button_info['path']
        self.dest_color = button_info['color']
        self.displayedlist = []
        self.displayedlist_ids = []
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
            if x.obj.dest:
                create_list.append(x.obj)
            elif x.obj.moved and x.obj.path == dest:
                create_list.append(x.obj)
        self.add_squares(create_list)

    def add_squares(self, imageobjects: list) -> None:
        "Adds squares to grid, displayedlist, and reloads them"
        # we get obj make square and add it.
        new = []
        regen = []
        for obj in imageobjects:
            if obj.dest == self.dest_path:
                new.append(self.makedestsquare(obj))
        for gridsquare in new:
            self.destgrid.window_create(
                "insert", window=gridsquare, padx=self.gui.gridsquare_padx, pady=self.gui.gridsquare_pady)
            if gridsquare.obj.guidata['destimg'] == None: # Checks if img is unloaded
                regen.append(gridsquare)
            self.displayedlist.append(gridsquare)
            self.displayedlist_ids.append(gridsquare.obj.id)
            self.displayedset.add(gridsquare)
        if regen:
            self.dest_thumbs.reload(regen) # Threads the reloading process. #need private attribute for dest and grid separate.

    def remove_squares(self, squares: list) -> None:
        "Removes square from grid, displayedlist, and can unload it from memory"
        remove = []
        # DETECTED CHANGE, BUT OBJ ID ALREADY IN LIST. THIS MEANS REMOVE IF WIDNOW DEST AND OBJ DEST NOT SAME. (OBJ DEST CHANGED)
        for square in squares:
            if self.dest_path != square.obj.dest: #old vs new dest
                a = self.displayedlist_ids.index(square.obj.id)
                remove.append(self.displayedlist[a])

        for gridsquare in remove:
            self.destgrid.window_configure(gridsquare, window="")
            self.displayedlist.remove(gridsquare)
            self.displayedlist_ids.remove(gridsquare.obj.id)
            self.displayedset.discard(gridsquare)
        self.dest_thumbs.unload(remove)
        print("Unloading:", len(remove))

    def makedestsquare(self, imageobj):

        "Use same photoimages as gridviewer" "Just add this version to unload"
        "Created by setdest and loadsession" "loadsession will sort into buttonlists, otherwise setdest will sort one by one"

        frame = tk.Frame(self.destgrid, borderwidth=0,
                         highlightthickness = self.gui.whole_box_size, highlightcolor=self.gui.imageborder_default_colour,highlightbackground=self.gui.imageborder_default_colour, padx = 0, pady = 0)
        #search from dict or generate again.
        frame.obj = imageobj
        truncated_filename = imageobj.truncated_filename
        truncated_name_var = tk.StringVar(frame, value=truncated_filename)
        frame.obj2 = truncated_name_var # This is needed or it is garbage collected I guess
        frame.grid_propagate(True)

        try:
            canvas = tk.Canvas(frame, width=self.gui.thumbnailsize,
                               height=self.gui.thumbnailsize,bg=self.gui.square_colour, highlightthickness=self.gui.square_border_size, highlightcolor=self.gui.imageborder_default_colour, highlightbackground = self.gui.imageborder_default_colour) #The gridbox color.
            canvas.grid(column=0, row=0, sticky="NSEW")
            img = None
            canvas.image = img
#
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
            check = ttk.Checkbutton(check_frame, textvariable=truncated_name_var, variable=imageobj.checked, onvalue=True, offvalue=False, command=lambda: (self.gui.uncheck_show_next()), style="Theme_square.TCheckbutton")
            check.grid(sticky="NSEW")
#
            ## save the data to the image obj to both store a reference and for later manipulation
            imageobj.guidata["destframe"] = frame
            imageobj.guidata["destimg"] = img
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

    def close_window(self, *args, event=False):
        "Safely close everything"
        if event:
            event = args[0] # reappoint event variable to mouseEvent
            for square in self.displayedlist:
                if square.winfo_x() <= event.x <= square.winfo_x() + square.winfo_width() and \
                   square.winfo_y() <= event.y <= square.winfo_y() + square.winfo_height():
                    print("Click inside a square, not closing.")
                    return  # Click is inside a square, do not close
        self.dest_thumbs.unload(self.displayedlist)
        for x in self.displayedlist:
            x.canvas.destroy()
            x.destroy()
            del x.canvas
            del x
        if hasattr(self, "destgrid"):
            self.destgrid.destroy()
            del self.destgrid
        if hasattr(self, "destwindow"):
            self.gui.destpane_geometry = self.destwindow.winfo_geometry()
            self.destwindow.destroy()
            del self.destwindow
        del self.displayedlist_ids
        del self.animated
        del self.displayedlist
        del self.displayedset
        gc.collect()

class ThumbManager:
    def __init__(self, dest_viewer):
        self.animate_dest = dest_viewer.animate_dest
        self.threads = dest_viewer.fileManager.threads
        self.data_dir = dest_viewer.fileManager.data_dir
        self.gui = dest_viewer.fileManager.gui
        self.thread = None
        self.gen_thread = None

    def reload(self, gridsquares):
        #queue system. executor global, submit/map to it def concurrent(squares, workers) 1 persistent thread for it. no daemon
        def multithread():
            self.thread = new_thread
            a = perf_counter()
            animated = [x for x in gridsquares if x.obj.isanimated and x.obj.framecount != 0]
            try:
                max_workers = max(1,self.threads*2)
                with concurrent.ThreadPoolExecutor(max_workers=max_workers) as executor:
                    executor.map(reload_static, gridsquares)
                print(f"Thumbnails loaded in: {perf_counter()-a:.2f}")
                max_workers = max(1,self.threads)
                with concurrent.ThreadPoolExecutor(max_workers=max_workers) as executor:
                    executor.map(reload_animated, animated)
                print(f"Thumbframes loaded in: {perf_counter()-a:.2f}")
            except Exception as e:
                print("Error reloading thumbs and frames", e)
        def reload_static(gridsquare):
            imageobj = gridsquare.obj
            img = None
            try:
                try:

                    #this is faster
                    buffer = pyvips.Image.new_from_file(imageobj.thumbnail)
                    img = ImageTk.PhotoImage(Image.frombuffer(
                        "RGB", [buffer.width, buffer.height], buffer.write_to_memory()))
                    
                except:  # Pyvips fallback
                    img = ImageTk.PhotoImage(Image.open(imageobj.thumbnail))
                finally:
                    imageobj.guidata["destimg"] = img
                    gridsquare.canvas.image = img
                    gridsquare.canvas.itemconfig(gridsquare.canvas_image_id, image=img)
            except Exception as e:
                print(f"Error in load_thumb: {e}")
        def reload_animated(gridsquare):
            obj = gridsquare.obj
            #gridsquare in self.animate.running
            if len(obj.frames_dest) == obj.framecount: # we switched to a view where the gif is already playing, skip
                return
            if len(obj.frames_dest) != obj.framecount and len(obj.frames_dest) > 0: #another thread is active
                return
            obj.frames_dest = [] #make sure it is empty for sure
            if obj.path.lower().endswith(".webm"):
                reader = None
                try:
                    reader = get_reader(obj.path)
                    fps = (reader.get_meta_data().get('fps', 24))
                    obj.delay = int(round((1 / fps)*1000))
                    for frame in reader:
                        image = Image.fromarray(frame)
                        image.thumbnail((self.gui.thumbnailsize,self.gui.thumbnailsize))
                        tk_image = ImageTk.PhotoImage(image)
                        obj.frames_dest.append(tk_image)
                        self.animate_dest.add_animation(obj)

                    obj.lazy_loading = False
                except Exception as e:
                    print(f"Error in frame generation for grid: {e}")
                finally:
                    reader.close()
                return
            elif obj.path.lower().endswith(".mp4"):
                return
            # Load frames for GIF, WEBP
            else:
                try:
                    with Image.open(obj.path) as img:
                        if obj.framecount == 0: # Static
                            return
                        for i in range(obj.framecount):
                            img.seek(i)  # Move to the ith frame
                            frame = img.copy()
                            frame.thumbnail((self.gui.thumbnailsize, self.gui.thumbnailsize), Image.Resampling.LANCZOS)
                            tk_image = ImageTk.PhotoImage(frame)
                            obj.frames_dest.append(tk_image)
                            self.animate_dest.add_animation(obj)

                        obj.lazy_loading = False
                        print(f"All frames loaded for: {obj.name.get()[:30]}")
                except Exception as e: #fallback to static.
                    print(f"Error in reload_thumbframes (): {e}")
                    obj.isanimated = False
        if gridsquares:
            new_thread = Thread(target=multithread, daemon=True)
            new_thread.start()
            print("(Thread) Reloading:", len(gridsquares))

    def unload(self, gridsquares): # thread?
        def unload_static(i):
            i.canvas.itemconfig(i.canvas_image_id, image=None)
            i.canvas.image = None
            i.obj.guidata["destimg"] = None
        def unload_animated(i):
            self.animate_dest.remove_animation(i, self.gui.square_colour)
            i.obj.index_dest = 0
            i.obj.frames_dest = []
            i.obj.lazy_loading = True
        for gridsquare in gridsquares:
            if gridsquare.obj.frames_dest:
                unload_animated(gridsquare)
            unload_static(gridsquare)
        gc.collect() # gc takes long. maybe we can tell it what to do? why is gc necessary even? something STILL pointing to the image?
        # see if we can have tkinter reference the images from imagefile context.
    #setdest, moveall to thumbmanager? walk here?

class Animate:
    def __init__(self):
        self.running = set() # Stores every frame going to be animated or animating.
    def add_animation(self, obj):
        gridsquare = obj.guidata["destframe"]
        if gridsquare in self.running:
            return
        self.running.add(gridsquare)
        self.start_animations(gridsquare)

    def remove_animation(self, gridsquare, square_colour):
        if gridsquare in self.running:
            gridsquare.obj.guidata["canvas"]["background"] = square_colour
            self.running.remove(gridsquare)

    def start_animations(self, gridsquare):
        def lazy(gridsquare):
            i = gridsquare
            i.obj.guidata["canvas"]['background'] = "red"
            if i not in self.running: # Stop if not in "view" or in self.running
                return
            if not i.obj.frames_dest: # No frames have been initialized. Shouldn't happen ever. Dead code?
                print("Error, lazy called with no frames")
                return
            if not i.obj.lazy_loading and len(i.obj.frames_dest) != i.obj.framecount: # All frames generated doesnt match expected (only webm, dead?)
                print("Error, frames generated doesnt match expected")
                return
            if not i.obj.lazy_loading and len(i.obj.frames_dest) == i.obj.framecount: # All frames ready. (second part only webm, dead)
                loop(i)
            else:
                try:
                    if len(i.obj.frames_dest) > i.obj.index_dest: # When next frame is available, but not all of them exist yet.
                        i.canvas.itemconfig(i.canvas_image_id, image=i.obj.frames_dest[i.obj.index_dest])
                        i.obj.index_dest = (i.obj.index_dest + 1) % i.obj.framecount
                        i.canvas.after(i.obj.frametimes[i.obj.index_dest], lambda: lazy(i))
                    else: # Frame must wait to ge generated, wait.
                        i.canvas.after(i.obj.delay, lambda: lazy(i))  #default delay instead 100 ms.
                except Exception as e:
                    print("Error in lazy:",)
        def loop(gridsquare):
            "Indefinite loop on a seperate thread until it just ends"
            if not gridsquare in self.running:
                return
            i = gridsquare
            i.obj.guidata["canvas"]['background'] = "green" # move to laZY?
            if len(i.obj.frames_dest) >= i.obj.index_dest:
                i.canvas.itemconfig(i.canvas_image_id, image=i.obj.frames_dest[i.obj.index_dest]) #change the frame
                i.obj.index_dest = (i.obj.index_dest + 1) % i.obj.framecount
                i.canvas.after(i.obj.frametimes[i.obj.index_dest], lambda: loop(i)) #run again.
        lazy(gridsquare) # Non threaded
    def stop_animations(self, gridsquare):
        self.running.clear()
        self.thread = None
