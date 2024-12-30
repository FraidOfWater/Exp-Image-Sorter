import os
import sys
import json
import logging

from time import perf_counter
from random import seed, random
from shutil import rmtree, move as shutilmove

from hashlib import md5
from PIL import Image, ImageTk
from imageio import get_reader

from threading import Thread
import concurrent.futures as concurrent
import gc

import tkinter as tk
from tkinter.messagebox import askokcancel
from tkinter import filedialog as tkFileDialog

from gui import GUIManager
from navigator import Navigator

def import_pyvips():
    base_path = os.path.dirname(os.path.abspath(__file__))
    vipsbin = os.path.join(base_path, "vips-dev-8.16", "bin")
    os.environ['PATH'] = os.pathsep.join((vipsbin, os.environ['PATH']))
    if os.path.exists(vipsbin):
        os.add_dll_directory(vipsbin)
import_pyvips()
import pyvips


#Ideas:
# cleanup (animate), move # do testing, catch errors in move with actualy error messages.
# Reimplement destination window. Whole shebang
# Stats for img creation speed, if buffered, size, framecount, (0 and 1 static), type, second render, displayedlist
# page mode, throttling
#test empty folder, test folder with size change.

# Bugs
# actual gridsquare width not correct
# does second render even work anymore? pyramid was broken for so long.
# Still appears to be a small memory leak somewhere. Happesn when loading through alot of imgs.

# fail to allocate bitmap memory issue? Just dont load too many anims. prob due to tkinter not able to handle so many gifs.
# exp with another lib? that can do gifs and webp or webm by default? must also support vlc or mp4 and webm natively. must support PIL and pyvips.

#Lets not do zooming, resizing to windows or imagegrid.
#Lets not do threading for frames. I like the slight lag. + No problems
#Lets not do a settings tab, json is pretty enough.
logger = logging.getLogger("Sortimages")
logger.setLevel(logging.WARNING)  # Set to the lowest level you want to handle
handler = logging.StreamHandler()
handler.setLevel(logging.WARNING)
formatter = logging.Formatter('%(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

class Imagefile:
    path = ""
    dest = ""
    def __init__(self, name, path) -> None:
        self.name = tk.StringVar()
        self.name.set(name)
        self.path = path
        self.mod_time = None
        self.file_size = None
        self.dimensions = None # for canvasimage video because pulling this info for vlc is apparently hard, we generate it and store the info here.
        self.checked = tk.BooleanVar(value=False)
        self.destchecked = tk.BooleanVar(value=False)
        self.moved = False # list name instead?
        self.isanimated = False
        self.lazy_loading = True # gif, webp could be culled, just check if max frames lower than curernt num of frames generated
        self.frames = [] # gif, webp
        self.frametimes = [] #gif, webp
        self.framecount = 0 #gif, webp
        self.index = 0 #need only for gif
        self.delay = 100 #Default delay #cull
        self.id = None #need
    
    def setid(self, id):
        self.id = id
    def setguidata(self, data):
        self.guidata = data
    
    def setdest(self, dest):
        self.dest = dest["path"]
        self.dest_color = dest["color"]
        logger.info("Set destination of %s to %s",
                      self.name.get(), self.dest)
    def move(self, x, assigned, moved, gui) -> str:
        destpath = self.dest

        if destpath != "" and os.path.isdir(destpath):
            file_name = self.name.get()

            # Check for name conflicts (source -> destination)
            exists_already_in_destination = os.path.exists(os.path.join(destpath, file_name))
            if exists_already_in_destination:
                print(f"File {self.name.get()[:30]} already exists at destination. Cancelling move.")
                return ("") # Returns if 1. Would overwrite someone
            
            try:
                new_path = os.path.join(destpath, file_name)
                old_path = self.path

                # Throws exception when image is open.
                shutilmove(self.path, new_path)

                assigned.remove(x)
                moved.append(x)

                self.moved = True
                self.show = False

                self.guidata["frame"].configure(
                    highlightbackground="green", highlightthickness=2)

                self.path = new_path
                returnstr = ("Moved:" + self.name.get() +
                             " -> " + destpath + "\n")
                destpath = ""
                self.dest = ""
                self.moved = True
                gui.images_left.set(int(gui.images_left.get())-1)
                gui.images_left_and_assigned.set(f"{len(assigned)}/{int(gui.images_left.get())}")
                gui.images_sorted.set(int(gui.images_sorted.get())+1)
                return returnstr
            except Exception as e:
                # Shutil failed. Delete the copy from destination, leaving the original at source.
                # This only runs if shutil fails, meaning the image couldn't be deleted from source.
                # It is therefore safe to delete the destination copy.
                if os.path.exists(new_path) and os.path.exists(old_path):
                    os.remove(new_path)
                    print(e)
                    print("Shutil failed. Coudln't delete from source, cancelling move (deleting copy from destination)")
                    return "Shutil failed. Coudln't delete from source, cancelling move (deleting copy from destination)"
                else:
                    logger.warning(f"Error moving/deleting: %s . File: %s {e} {self.name.get()}")

                self.guidata["frame"].configure(
                    highlightbackground="red", highlightthickness=2)
                return ("Error moving: %s . File: %s", e, self.name.get())

class SortImages:
    imagelist = []
    destinations = []
    exclude = []
    def __init__(self) -> None:
        
        self.timer = Timer()
        self.last_call_time = 0
        self.throttle_delay = 0.19
        self.autosave=True
        self.threads = 4
        self.gui = GUIManager(self)
        self.loadprefs()
        self.gui.initialize()
        self.navigator = Navigator(self)
        self.animate = Animate()
        self.thumbs = ThumbManager(self)
        self.validate_data_dir_thumbnailsize()
        self.gui.mainloop()
    def validate_data_dir_thumbnailsize(self): #Deletes data directory if the first picture doesnt match the thumbnail size from prefs. (If user changes thumbnailsize, we want to generate thumbnails again)
        #test performance
        data_dir = self.data_dir
        if(os.path.exists(data_dir) and os.path.isdir(data_dir)):
            temp = os.listdir(data_dir)
            if len(temp) >= 1 and temp[0].lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.tiff', '.pcx', '.psd', '.jfif', '.webm')):
                first_image_path = os.path.join(data_dir, temp[0])
                try:
                    image = pyvips.Image.new_from_file(first_image_path)
                    width = image.width
                    height = image.height
                    # The size doesnt match what is wanted in prefs
                    if max(width, height) != self.gui.thumbnailsize:
                        try:
                            logger.warning(f"Removing data folder, thumbnailsize changed")
                            rmtree(data_dir)
                            os.mkdir(data_dir)
                            logger.warning(f"Re-created data folder.")
                        except Exception as e:
                            print(f"Couldn't delete/create data folder")
                except Exception as e:
                    logger.warning(f"Couldn't load first image in data folder")
                finally:
                    del image
                
            else:
                logger.warning(f"Data folder is empty")
                pass
            pass
        else:
            logger.warning(f"Data folder created")
            os.mkdir(data_dir)
    def loadprefs(self):

        script_dir = os.path.dirname(os.path.abspath(__file__)) # Else if a ran as py script
        self.prefs_path = os.path.join(script_dir, "prefs.json")
        self.data_dir = os.path.join(script_dir, "data")

        hotkeys = ""
        try:
            with open(self.prefs_path, "r") as prefsfile:

                jdata = prefsfile.read()
                jprefs = json.loads(jdata)

            #paths
                self.gui.source_folder = jprefs["paths"]["source"]
                self.gui.destination_folder = jprefs["paths"]["destination"]
                self.gui.sessionpathvar.set(jprefs["paths"]['lastsession'])
                self.exclude = jprefs["paths"]["exclude"]
            #Preferences
                self.gui.thumbnailsize = int(jprefs["preferences"]["user"]["thumbnailsize"])
                
                hotkeys = jprefs["preferences"]["user"]["hotkeys"]
                self.gui.extra_buttons = jprefs["preferences"]["user"]["extra_buttons"]
                self.gui.force_scrollbar = jprefs["preferences"]["user"]["force_scrollbar"]
                self.gui.interactive_buttons = jprefs["preferences"]["user"]["interactive_buttons"]
                self.gui.page_mode = jprefs["preferences"]["user"]["page_mode"]
            #Technical preferences
                self.gui.filter_mode = jprefs["preferences"]["technical"]["quick_preview_filter"]
                self.gui.quick_preview_size_threshold = int(jprefs["preferences"]["technical"]["quick_preview_size_threshold"])
                self.gui.throttle_time = jprefs["preferences"]["technical"]["throttle_time"]
                self.threads = jprefs["preferences"]["technical"]['threads']
                self.autosave = jprefs["preferences"]["technical"]['autosave_session']
            #Customization
                self.gui.checkbox_height = int(jprefs["appearance"]["image_container"]["checkbox_height"])
                self.gui.gridsquare_padx = int(jprefs["appearance"]["image_container"]["gridsquare_padx"])
                self.gui.gridsquare_pady = int(jprefs["appearance"]["image_container"]["gridsquare_pady"])
                self.gui.text_box_colour = jprefs["appearance"]["image_container"]["text_box_colour"]
                self.gui.text_box_selection_colour = jprefs["appearance"]["image_container"]["text_box_selection_colour"]
                
                self.gui.imageborder_default_colour = jprefs["appearance"]["image_container"]["imageborder_default_colour"]
                self.gui.imageborder_selected_colour = jprefs["appearance"]["image_container"]["imageborder_selected_colour"]
                self.gui.imageborder_locked_colour = jprefs["appearance"]["image_container"]["imageborder_locked_colour"]
            #Window colours
                self.gui.main_colour = jprefs["appearance"]["window"]["main_colour"]
                self.gui.grid_background_colour = jprefs["appearance"]["window"]["grid_background_colour"]
                self.gui.canvasimage_background = jprefs["appearance"]["window"]["canvasimage_background"]
                self.gui.whole_box_size = jprefs["appearance"]["window"]["whole_box_size"]
                self.gui.square_border_size = int(jprefs["appearance"]["window"]["square_border_size"])
                self.gui.square_colour = jprefs["appearance"]["window"]["square_colour"]
                self.gui.square_text_colour = jprefs["appearance"]["window"]["square_text_colour"]
                self.gui.square_text_box_colour = jprefs["appearance"]["window"]["square_text_box_colour"]
                self.gui.square_text_box_selection_colour = jprefs["appearance"]["window"]["square_text_box_selection_colour"]
                self.gui.square_text_box_locked_colour = jprefs["appearance"]["window"]["square_text_box_locked_colour"]
                self.gui.imagebox_default_colour = jprefs["appearance"]["window"]["imagebox_default_colour"]
                self.gui.imagebox_selection_colour = jprefs["appearance"]["window"]["imagebox_selection_colour"]
                self.gui.imagebox_locked_colour = jprefs["appearance"]["window"]["imagebox_locked_colour"]
                self.gui.button_colour = jprefs["appearance"]["window"]["button_colour"]
                self.gui.button_press_colour = jprefs["appearance"]["window"]["button_press_colour"]
                self.gui.text_colour = jprefs["appearance"]["window"]["text_colour"]
                self.gui.pressed_text_colour = jprefs["appearance"]["window"]["pressed_text_colour"]
                self.gui.text_field_colour = jprefs["appearance"]["window"]["text_field_colour"]
                self.gui.text_field_text_colour = jprefs["appearance"]["window"]["text_field_text_colour"]
                self.gui.text_field_activated_colour = jprefs["appearance"]["window"]["text_field_activated_colour"]
                self.gui.text_field_activated_text_colour = jprefs["appearance"]["window"]["text_field_activated_text_colour"]
                self.gui.pane_divider_colour = jprefs["appearance"]["window"]["pane_divider_colour"]
            #GUI CONTROLLED PREFRENECES
                self.gui.squaresperpage.set(jprefs["qui"]["squaresperpage"])
                self.gui.sortbydatevar.set(jprefs["qui"]["sortbydate"])
                self.gui.default_delay.set(jprefs["qui"]["default_delay"])
                self.gui.viewer_x_centering = jprefs["qui"]["viewer_x_centering"]
                self.gui.viewer_y_centering = jprefs["qui"]["viewer_y_centering"]
                self.gui.show_next.set(jprefs["qui"]["show_next"])
                self.gui.dock_view.set(jprefs["qui"]["dock_view"])
                self.gui.dock_side.set(jprefs["qui"]["dock_side"])
            #Window positions
                #self.gui.main_geometry = jprefs["window_settings"]["main_geometry"]
                #self.gui.viewer_geometry = jprefs["window_settings"]["viewer_geometry"]
                #self.gui.destpane_geometry = jprefs["window_settings"]["destpane_geometry"]
                #self.gui.leftpane_width = int(jprefs["window_settings"]["leftpane_width"])
                #self.gui.middlepane_width = int(jprefs["window_settings"]["middlepane_width"])
                #self.gui.images_sorted.set(jprefs["window_settings"]["images_sorted"])
                
                self.gui.actual_gridsquare_width = self.gui.thumbnailsize + self.gui.gridsquare_padx + self.gui.square_border_size*2 + self.gui.whole_box_size*2
                self.gui.actual_gridsquare_height = self.gui.thumbnailsize + self.gui.gridsquare_pady + self.gui.square_border_size*2 + self.gui.whole_box_size*2 + self.gui.checkbox_height

            if len(hotkeys) > 1:
                self.gui.hotkeys = hotkeys
        except Exception as e:
            logger.error(f"Error loading prefs.json: {e}")
    def saveprefs(self, gui):
        if gui.middlepane_frame.winfo_width() == 1:
            pass
        else:
            gui.middlepane_width = gui.middlepane_frame.winfo_width()
        sdp = gui.sdpEntry.get() if os.path.exists(gui.sdpEntry.get()) else ""
        ddp = gui.ddpEntry.get() if os.path.exists(gui.ddpEntry.get()) else ""

        save = {
            "paths": {
                "source": sdp,
                "destination": ddp,
                "lastsession": gui.sessionpathvar.get(),
                "exclude": self.exclude,
            },
            "preferences": {
                "user": {
                    "thumbnailsize": gui.thumbnailsize,
                    "hotkeys": gui.hotkeys,
                    "extra_buttons": gui.extra_buttons,
                    "force_scrollbar": gui.force_scrollbar,
                    "interactive_buttons":gui.interactive_buttons,
                    "page_mode": gui.page_mode,
                },
                "technical": {
                    "quick_preview_filter": gui.filter_mode,
                    "quick_preview_size_threshold": gui.quick_preview_size_threshold,
                    "throttle_time": gui.throttle_time,
                    "threads": self.threads,
                    "autosave_session":self.autosave,
                },
            },
            "appearance": {
                "image_container": {
                    "checkbox_height":gui.checkbox_height,
                    "gridsquare_padx":gui.gridsquare_padx,
                    "gridsquare_pady":gui.gridsquare_pady,
                    "text_box_colour":gui.text_box_colour,
                    "text_box_selection_colour":gui.text_box_selection_colour,
                    "imageborder_default_colour":gui.imageborder_default_colour,
                    "imageborder_selected_colour":gui.imageborder_selected_colour,
                    "imageborder_locked_colour":gui.imageborder_locked_colour,
                },
                "window": {
                    "main_colour":gui.main_colour,
                    "grid_background_colour":gui.grid_background_colour,
                    "canvasimage_background":gui.canvasimage_background,
                    "whole_box_size":gui.whole_box_size,
                    "square_border_size":gui.square_border_size,
                    "square_colour":gui.square_colour,
                    "square_text_colour":gui.square_text_colour,
                    "square_text_box_colour":gui.square_text_box_colour,
                    "square_text_box_selection_colour":gui.square_text_box_selection_colour,
                    "square_text_box_locked_colour":gui.square_text_box_locked_colour,
                    "imagebox_default_colour":gui.imagebox_default_colour,
                    "imagebox_selection_colour":gui.imagebox_selection_colour,
                    "imagebox_locked_colour":gui.imagebox_locked_colour,
                    "button_colour":gui.button_colour,
                    "button_press_colour":gui.button_press_colour,
                    "text_colour":gui.text_colour,
                    "pressed_text_colour":gui.pressed_text_colour,
                    "text_field_colour":gui.text_field_colour,
                    "text_field_text_colour":gui.text_field_text_colour,
                    "text_field_activated_colour":gui.text_field_activated_colour,
                    "text_field_activated_text_colour":gui.text_field_activated_text_colour,
                    "pane_divider_colour":gui.pane_divider_colour,
                },
            },
            "qui": {
                "squaresperpage": gui.squaresperpage.get(),
                "sortbydate": gui.sortbydatevar.get(),
                "default_delay": gui.default_delay.get(),
                "viewer_x_centering": gui.viewer_x_centering,
                "viewer_y_centering": gui.viewer_y_centering,
                "show_next": gui.show_next.get(),
                "dock_view": gui.dock_view.get(),
                "dock_side": gui.dock_side.get(),
            },
            "window_settings": {
                "main_geometry": gui.winfo_geometry(),
                "viewer_geometry": gui.viewer_geometry,
                "destpane_geometry":gui.destpane_geometry,
                "leftpane_width":gui.leftui.winfo_width(),
                "middlepane_width":gui.middlepane_width,
                "images_sorted":gui.images_sorted.get(),
            },
        }

        try: #Try to save the preference to prefs.json
            with open(self.prefs_path, "w+") as savef:
                json.dump(save, savef,indent=4, sort_keys=False)
                logger.debug(save)
        except Exception as e:
            logger.warning(("Failed to save prefs:", e))

        try: #Attempt to save the session if autosave is enabled
            if self.autosave:
                self.savesession(asksavelocation=False)
        except Exception as e:
            logger.warning(("Failed to save session:", e))
    def savesession(self,asksavelocation):
        print("Saving session, Goodbye!")
        if asksavelocation:
            filet=[("Javascript Object Notation","*.json")]
            savelocation=tkFileDialog.asksaveasfilename(confirmoverwrite=True,defaultextension=filet,filetypes=filet,initialdir=os.getcwd(),initialfile=self.gui.sessionpathvar.get())
        else:
            savelocation = self.gui.sessionpathvar.get()

        if len(self.imagelist) > 0:
            imagesavedata = []

            for obj in self.imagelist:
                if hasattr(obj, 'thumbnail'):
                    thumb = obj.thumbnail
                else:
                    thumb = ""
                if obj.isanimated:
                    isanimated = True
                else:
                    isanimated = False
                
    
                imagesavedata.append({
                    "name": obj.name.get(),
                    "file_size": obj.file_size,
                    "id": obj.id,
                    "path": obj.path,
                    "dest": obj.dest,
                    "moved": obj.moved,
                    "thumbnail": thumb,
                    "isanimated": isanimated,
                    })
                if obj.dimensions:
                    dimensions = obj.dimensions
                    imagesavedata[0]["dimensions"] = dimensions
            assigned_list = [x.obj.id for x in self.gui.gridmanager.assigned]
            save = {"dest": self.ddp, "source": self.sdp,
                    "imagelist": imagesavedata, "assigned_list": assigned_list, "thumbnailsize":self.gui.thumbnailsize}
            with open(savelocation, "w+") as savef:
                json.dump(save, savef, indent=4)
    def loadsession(self):
        sessionpath = self.gui.sessionpathvar.get()

        if os.path.exists(sessionpath) and os.path.isfile(sessionpath):
            with open(sessionpath, "r") as savef:
                sdata = savef.read()
                savedata = json.loads(sdata)
            gui = self.gui
            self.sdp = savedata['source']
            self.ddp = savedata['dest']
            self.setup(savedata['dest'])
            print("")
            print(f'Using session:  "{sessionpath}"')
            print(f'Source:   "{self.sdp}"')
            print(f'Target:   "{self.ddp}"')

            for line in savedata['imagelist']:
                if os.path.exists(line['path']):
                    obj = Imagefile(line['name'], line['path'])
                    obj.thumbnail = line['thumbnail']
                    obj.dest=line['dest']
                    obj.id=line['id']
                    obj.file_size=line['file_size']
                    obj.moved = line['moved']

                    try:
                        obj.isanimated=line['isanimated']
                    except Exception as e:
                        print(f"No value isanimated: {e}")
                    try:
                        a = line['dimensions']
                        obj.dimensions=(int(a[0]), int(a[1]))
                    except Exception as e:
                        pass

                    self.imagelist.append(obj)
            assigned_list = []
            for line in savedata['assigned_list']:
                assigned_list.append(line)
            assigned_list = [x for x in self.imagelist if x.id in assigned_list]
            self.gui.thumbnailsize=savedata['thumbnailsize']
            self.gui.initial_dock_setup()
            gui.guisetup(self.destinations)
            gui.gridmanager.load_session(assigned_list)
            self.gui.images_left.set(len(self.imagelist))
            self.gui.images_left_and_assigned.set(f"{len(self.gui.gridmanager.assigned)}/{self.gui.images_left.get()}")
        else:
            logger.warning("No Last Session!")

    def moveall(self):
        loglist = []

        assigned = self.gui.gridmanager.assigned
        moved = self.gui.gridmanager.moved
        temp = self.gui.gridmanager.assigned.copy()
        reopen = "none"
        if hasattr(self.gui, "second_window"):
            self.gui.close_second_window()
            reopen = "window"
        elif hasattr(self.gui, "Image_frame"):
            self.gui.after(0, self.gui.Image_frame.destroy)
            del self.gui.Image_frame
            reopen = "dock"
        
        for x in temp:
            try:
                out = x.obj.move(x, assigned, moved, self.gui) # Pass functionality to happen in move so it can fail removing from the sorted lists when shutil.move fails.

                if isinstance(out, str):
                    loglist.append(out)
            except Exception as e:
                print("Carry on")
        temp.clear()
        self.gui.refresh_rendered_list()
        self.gui.refresh_destinations()
        """
        if reopen == "window":
            self.gui.displayimage(self.gui.current_selection)
        elif reopen =="dock":
            self.gui.displayimage(self.gui.current_selection)
        """
        try:
            if len(loglist) > 0:
                with open("filelog.txt", "a") as logfile:
                    logfile.writelines(loglist)

        except Exception as e:
            logger.error(f"Failed to write filelog.txt: {e}")

    def setDestination(self, *args):
        current_time = perf_counter()
        #throttling
        if current_time - self.last_call_time >= self.throttle_delay: #and key pressed down... so you can tap as fast as you like.
            self.last_call_time = current_time
        else:
            print("Victim of throttling")
            return
        
        #take multiple
        dest = args[0]
        marked = [] # List of all marked
        displayedlist = self.gui.gridmanager.displayedlist # Current list being compared
        try:
            wid = args[1].widget
        except AttributeError:
            wid = args[1]["widget"]
        if isinstance(wid, tk.Entry):
            pass
        
        # Return all images whose checkbox is checked (And currently in view by image viewer, so you can just press a hotkey and not have to check a checkbox everytime) (If interacting with other squares, it will cancel itself out. This is so user wont accidentally move anything.)
        else:
            marked = [x for x in displayedlist if x.obj.checked.get()] # All checked are now in marked list.

            "Current selection is added to marked if focus never lost"
            if self.navigator.old and self.gui.focused_on_secondwindow and self.navigator.old in displayedlist: # to see if we have clicked elsewhere as to not move the displayed image anymore.
                if self.navigator.old not in marked:
                    marked.append(self.navigator.old)

            #Handle lists
            to_remove_from_grid = []
            to_refresh_from_grid = []
            for x in marked: #set background to button colour
                x.obj.setdest(dest)
                x.obj.guidata["frame"]['background'] = dest['color']
                x.obj.guidata["canvas"]['background'] = dest['color']
                x.obj.checked.set(False)

                # Move from list to list
                if self.gui.current_view.get() == "Show Unassigned":
                    self.gui.gridmanager.unassigned.remove(x)
                    self.gui.gridmanager.assigned.append(x)
                    to_remove_from_grid.append(x)
                    
                # Moving from assigned to assigned
                elif self.gui.current_view.get() == "Show Assigned":
                    self.gui.gridmanager.assigned.remove(x)
                    self.gui.gridmanager.assigned.append(x)
                    to_refresh_from_grid.append(x) # Means we want to update pos so it lines up with assigned list order.

                # Moving from moved to assigned
                elif self.gui.current_view.get() == "Show Moved":
                    self.gui.gridmanager.moved.remove(x)
                    self.gui.gridmanager.assigned.append(x)
                    to_remove_from_grid.append(x)
                
            self.gui.gridmanager.remove_squares(to_remove_from_grid, unload=True) # For moved and Unassigned
            "Assigned view: end of list is 'newest' and is displayed first, remove from list and add it back so it shows up as first."
            self.gui.gridmanager.remove_squares(to_refresh_from_grid, unload=False)
            self.gui.gridmanager.add_squares(to_refresh_from_grid)
        #Handle destviewer
        # Check for destination view changes separately. Note, We use destchecked here, not checked.

        "If show next option checked, and next exists, and viewer is open, show next image"
        if self.gui.show_next.get() and len(self.gui.gridmanager.displayedlist) >= 1 and hasattr(self.gui, "Image_frame"):
            self.navigator.select_next(self.gui.gridmanager.displayedlist)

        "Update stat tracker"
        self.gui.images_left_and_assigned.set(f"{len(self.gui.gridmanager.assigned)}/{int(self.gui.images_left.get())}")

    def setup(self, dest): # scan the destination
        def randomColor():
            color = '#'
            hexletters = '0123456789ABCDEF'
            for i in range(0, 6):
                color += hexletters[int(random()*16)]
            return color
        self.destinations = []
        self.destinationsraw = []
        with os.scandir(dest) as it:
            for entry in it:
                if entry.is_dir():
                    seed(entry.name)
                    self.destinations.append(
                        {'name': entry.name, 'path': entry.path, 'color': randomColor()})
                    self.destinationsraw.append(entry.path)
    def validate(self, gui):
        self.sdp = self.gui.sdpEntry.get()
        self.ddp = self.gui.ddpEntry.get()
        samepath = (self.sdp == self.ddp)

        if ((os.path.isdir(self.sdp)) and (os.path.isdir(self.ddp)) and not samepath):
            self.setup(self.ddp)
            gui.guisetup(self.destinations)
            gui.sessionpathvar.set(os.path.basename(
                self.sdp)+"-"+os.path.basename(self.ddp)+".json")
            print("")
            print(f'New session:  "{self.gui.sessionpathvar.get()}"')
            print(f'Source:   "{self.sdp}"')
            print(f'Target:   "{self.ddp}"')
            self.walk(self.sdp)
            self.gui.initial_dock_setup()
            self.timer.start()
            self.gui.gridmanager.initialize()
            self.gui.images_left.set(len(self.imagelist))
            self.gui.images_left_and_assigned.set(f"{len(self.gui.gridmanager.assigned)}/{self.gui.images_left.get()}")

        elif samepath:
            self.gui.sdpEntry.delete(0, tk.END)
            self.gui.ddpEntry.delete(0, tk.END)
            self.gui.sdpEntry.insert(0, "PATHS CANNOT BE SAME")
            self.gui.ddpEntry.insert(0, "PATHS CANNOT BE SAME")
        else:
            self.gui.sdpEntry.delete(0, tk.END)
            self.gui.ddpEntry.delete(0, tk.END)
            self.gui.sdpEntry.insert(0, "ERROR INVALID PATH")
            self.gui.ddpEntry.insert(0, "ERROR INVALID PATH")   
    def walk(self, src):
        supported_formats = {"png", "gif", "jpg", "jpeg", "bmp", "pcx", "tiff", "webp", "psd", "jfif", "mp4", "webm"}
        animation_support = {"gif", "webp", "mp4", "webm"} # For clarity
        for root, dirs, files in os.walk(src, topdown=True):
            dirs[:] = [d for d in dirs if d not in self.exclude]
            for name in files:
                ext = os.path.splitext(name)[1][1:].lower()
                if ext in supported_formats:
                    imgfile = Imagefile(name, os.path.join(root, name))
                    if ext == "gif" or ext == "webp" or ext == "webm" or ext == "mp4":
                        imgfile.isanimated = True
                    self.imagelist.append(imgfile)

        # Sort by date modificated
        if self.gui.sortbydatevar.get():
            self.imagelist.sort(key=lambda img: os.path.getmtime(img.path), reverse=True)
        return self.imagelist
    def clear(self, *args):
        if askokcancel("Confirm", "Really clear your selection?"):
            for x in self.imagelist:
                x.checked.set(False)

class ThumbManager:
    def __init__(self, fileManager):
        self.animate = fileManager.animate
        self.threads = fileManager.threads
        self.data_dir = fileManager.data_dir
        self.gui = fileManager.gui
        self.thread = None
        self.gen_thread = None
    def generate(self, gridsquares):
        "Generate thumbnails, generate frames, start animation of frames"
        filelist = [x.obj for x in gridsquares]
        def multithread():
            animated = [obj for obj in filelist if obj.isanimated]
            try:
                max_workers = max(1,self.threads*2)
                a = perf_counter()
                with concurrent.ThreadPoolExecutor(max_workers=max_workers) as executor: 
                    executor.map(makethumb, filelist)
                print(f"Thumbnails generated in: {perf_counter()-a:.2f}")

                max_workers = max(1,self.threads)

                a = perf_counter()
                with concurrent.ThreadPoolExecutor(max_workers=max_workers) as executor: 
                    executor.map(makeframes, animated)
                print(f"Thumbframes generated in: {perf_counter()-a:.2f}")
            except Exception as e:
                print("Error in generating thumbs and frames", e)
            finally: self.gen_thread = None
        def makename(obj):
            frame = obj.guidata['frame']
            frame.obj2.set(self.gui.gridmanager.truncate_text(obj))
        def makethumb(imagefile):
            def gen_img_attributes():
                #Hash using name, size, mod time. Creates unique thumb name.
                file_name1 = imagefile.path.replace('\\', '/').split('/')[-1]
                if not imagefile.file_size or not imagefile.mod_time:
                    file_stats = os.stat(imagefile.path)
                    imagefile.file_size = file_stats.st_size
                    imagefile.mod_time = file_stats.st_mtime
                id = file_name1 + " " +str(imagefile.file_size)+ " " + str(imagefile.mod_time)
                hash = md5()
                hash.update(id.encode('utf-8'))
                imagefile.setid(hash.hexdigest())
                frame = imagefile.guidata['frame'] # Quite expensive name truncation!
                frame.obj2.set(self.gui.gridmanager.truncate_text(imagefile)) # So I threaded it!
            def lazy_load_thumb():
                try:
                    #this is faster
                    img = ImageTk.PhotoImage(Image.open(imagefile.thumbnail))
                except:  # Pyvips fallback
                    buffer = pyvips.Image.new_from_file(imagefile.thumbnail)
                    img = ImageTk.PhotoImage(Image.frombuffer(
                        "RGB", [buffer.width, buffer.height], buffer.write_to_memory()))
                finally:
                    imagefile.guidata['img'] = img
                    canvas = imagefile.guidata['canvas']
                    frame = imagefile.guidata['frame']
                    canvas.image = img
                    canvas.itemconfig(frame.canvas_image_id, image=img)
            gen_img_attributes()
            thumbpath = os.path.join(self.data_dir, imagefile.id+os.extsep+"jpg")
            if (os.path.exists(thumbpath)): # Already exists, just point to it.
                imagefile.thumbnail = thumbpath
                lazy_load_thumb()
                if imagefile.path.lower().endswith((".mp4",".webm")): # (canvasimage) video_get_size() needs vlc to initialize the player, or it will report 0,0. We need dims ASAP for aspect ratio, so we get it from here.
                    reader = None
                    try: 
                        reader = get_reader(imagefile.path)
                        image = Image.fromarray(reader.get_data(0))
                        imagefile.dimensions = image.size
                    except Exception as e:
                        print(f"Error in video thumbnails generation (exists): {e}")
                    finally:
                        if reader:
                            reader.close()
                return
            # Generate thumbnail for videos
            if imagefile.path.lower().endswith((".mp4",".webm")):
                reader = None
                try:
                    reader = get_reader(imagefile.path)
                    image = Image.fromarray(reader.get_data(0))
                    imagefile.dimensions = image.size
                    image.thumbnail((self.gui.thumbnailsize,self.gui.thumbnailsize))
                    if image.mode in ("RGBA", "P"):
                        image = image.convert("RGB")
                    image.save(thumbpath)
                    imagefile.thumbnail = thumbpath
                    lazy_load_thumb()
                except Exception as e:
                    print(f"Error in video thumbnails generation: {e}")
                finally:
                    if reader:
                        reader.close()
                    
            # Generate thumbnail for static images
            else:
                try:
                    with Image.open(imagefile.path) as image:
                        image.thumbnail((self.gui.thumbnailsize,self.gui.thumbnailsize))
                        if image.mode in ("RGBA", "P"):
                            image = image.convert("RGB")
                        image.save(thumbpath)
                        imagefile.thumbnail = thumbpath
                        lazy_load_thumb()
                except Exception as e:
                    print(f"Error in thumb generation: {e}")
                    # Fallback to pyvips if pillow fails
                    try:
                        image = pyvips.Image.thumbnail(imagefile.path, self.gui.thumbnailsize)
                        image.write_to_file(thumbpath)
                        imagefile.thumbnail = thumbpath
                        lazy_load_thumb()
                    except Exception as e:
                        print(f"Error in thumbnail generation (pyvips): {e}")                      
        def makeframes(obj): # Creates frames and frametimes for gifs and webps
            # Load frames for WEBM impepelemnt with vlc? can take a long time to load.
            if obj.path.lower().endswith(".webm"):
                try:
                    reader = get_reader(obj.path)
                    fps = (reader.get_meta_data().get('fps', 24))
                    obj.delay = int(round((1 / fps)*1000))
                    for frame in reader:
                        image = Image.fromarray(frame)
                        image.thumbnail((self.gui.thumbnailsize,self.gui.thumbnailsize))
                        tk_image = ImageTk.PhotoImage(image)
                        obj.frames.append(tk_image)
                        obj.framecount += 1
                        obj.frametimes.append(obj.delay)
                        self.animate.add_animation(obj)
                        
                    obj.lazy_loading = False
                except Exception as e:
                    print(f"Error in frame generation for grid: {e}")
                finally:
                    self.gen_thread = None
                    if reader:
                        reader.close()
                return
            elif obj.path.lower().endswith(".mp4"): # Handled by vlc, not needed, here just to catch them from entering else.
                return
            # Load frames for GIF, WEBP
            else:
                try:
                    with Image.open(obj.path) as img:
                        temp = img.n_frames
                        if temp == 1: # Static
                            print(f"Found static gif/webp: {obj.name.get()[:30]}")
                            obj.framecount = 0
                            obj.isanimated = False
                            return
                        frame_frametime = img.info.get('duration',obj.delay)
                        if frame_frametime == 0:
                            pass
                        else:
                            obj.delay = frame_frametime
                        logger.debug(f"Found animated: {obj.name.get()[:30]} with {temp} frames.")
                        for i in range(temp):
                            img.seek(i)  # Move to the ith frame
                            frame = img.copy()
                            frame_frametime = img.info.get('duration',obj.delay)
                            obj.frametimes.append(frame_frametime)
                            frame.thumbnail((self.gui.thumbnailsize, self.gui.thumbnailsize), Image.Resampling.LANCZOS)
                            tk_image = ImageTk.PhotoImage(frame)
                            obj.frames.append(tk_image)
                            obj.framecount += 1
                            self.animate.add_animation(obj)
                            
                        if all(i == 0 for i in obj.frametimes):
                            for i in range(len(obj.frametimes)):
                                obj.frametimes[i] = obj.delay
                            print(f"Bugged animation frametimes. Using default_delay. {obj.name.get()[:30]}")
                        obj.lazy_loading = False
                        logger.info(f"All frames loaded for: {obj.name.get()[:30]}")
                except Exception as e: #fallback to static.
                    logger.error(f"Error in load_thumbframes: {e}")
                    obj.isanimated = False
        self.gen_thread = Thread(target=multithread, daemon=True)
        self.gen_thread.start()
    def reload(self, gridsquares):
        #queue system. executor global, submit/map to it def concurrent(squares, workers) 1 persistent thread for it. no daemon
        def multithread():
            self.thread = new_thread
            a = perf_counter()
            animated = [x for x in gridsquares if x.obj.isanimated and x.obj.framecount != 0]
            if self.gui.current_view.get() == "Show Assigned" or self.gui.current_view.get() == "Show Moved":
                if len(gridsquares) > 1:
                    gridsquares.reverse()
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
                    img = ImageTk.PhotoImage(Image.open(imageobj.thumbnail))
                except:  # Pyvips fallback
                    buffer = pyvips.Image.new_from_file(imageobj.thumbnail)
                    img = ImageTk.PhotoImage(Image.frombuffer(
                        "RGB", [buffer.width, buffer.height], buffer.write_to_memory()))
                finally:
                    imageobj.guidata['img'] = img
                    gridsquare.canvas.image = img
                    gridsquare.canvas.itemconfig(gridsquare.canvas_image_id, image=img)
            except Exception as e:
                print(f"Error in load_thumb: {e}")
        def reload_animated(gridsquare):
            obj = gridsquare.obj
            #gridsquare in self.animate.running
            if len(obj.frames) == obj.framecount: # we switched to a view where the gif is already playing, skip
                return
            if len(obj.frames) != obj.framecount and len(obj.frames) > 0: #another thread is active
                return
            obj.frames = [] #make sure it is empty for sure
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
                        obj.frames.append(tk_image)
                        self.animate.add_animation(obj)
                        
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
                            obj.frames.append(tk_image)
                            self.animate.add_animation(obj)
                            
                        obj.lazy_loading = False
                        logger.info(f"All frames loaded for: {obj.name.get()[:30]}")
                except Exception as e: #fallback to static.
                    logger.error(f"Error in reload_thumbframes: {e}")
                    obj.isanimated = False
        if not (self.gen_thread and self.gen_thread.is_alive()) and gridsquares:
            new_thread = Thread(target=multithread, daemon=True)
            new_thread.start()
            print("(Thread) Reloading:", len(gridsquares))
    def unload(self, gridsquare): # thread?
        def unload_static(gridsquare):
            gridsquare.canvas.itemconfig(gridsquare.canvas_image_id, image=None)
            gridsquare.canvas.image = None
            gridsquare.obj.guidata['img'] = None
        def unload_animated(gridsquare):
            self.animate.remove_animation(gridsquare, self.gui.square_colour)
            gridsquare.obj.index = 0
            gridsquare.obj.frames = []
            gridsquare.obj.lazy_loading = True
        if gridsquare.obj.frames:
            unload_animated(gridsquare)
        unload_static(gridsquare)
        gc.collect()

class Animate:
    def __init__(self):
        self.running = set() # Stores every frame going to be animated or animating.
        self.thread = None
    def add_animation(self, obj):
        gridsquare = obj.guidata['frame']
        if gridsquare in self.running:
            return
        self.running.add(gridsquare)
        if self.thread:
            self.thread.lazy(gridsquare)
        else:
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
            if not i.obj.frames: # No frames have been initialized. Shouldn't happen ever. Dead code?
                print("Error, lazy called with no frames")
                return
            if not i.obj.lazy_loading and len(i.obj.frames) != i.obj.framecount: # All frames generated doesnt match expected (only webm, dead?)
                print("Error, frames generated doesnt match expected")
                return
            if not i.obj.lazy_loading and len(i.obj.frames) == i.obj.framecount: # All frames ready. (second part only webm, dead)
                loop(i)
            else:
                try:
                    if len(i.obj.frames) > i.obj.index: # When next frame is available, but not all of them exist yet.
                        i.canvas.itemconfig(i.canvas_image_id, image=i.obj.frames[i.obj.index])
                        i.obj.index = (i.obj.index + 1) % i.obj.framecount 
                        i.canvas.after(i.obj.frametimes[i.obj.index], lambda: lazy(i))
                    else: # Frame must wait to ge generated, wait.
                        i.canvas.after(i.obj.delay, lambda: lazy(i))  #default delay instead 100 ms.
                except Exception as e:
                    print("Error in lazy:",)
        def loop(gridsquare):
            "Indefinite loop on a seperate thread until it just ends"
            if not gridsquare in self.running:
                return
            i = gridsquare
            i.obj.guidata["canvas"]['background'] = "green"
            if len(i.obj.frames) >= i.obj.index:
                i.canvas.itemconfig(i.canvas_image_id, image=i.obj.frames[i.obj.index]) #change the frame
                i.obj.index = (i.obj.index + 1) % i.obj.framecount
                i.canvas.after(i.obj.frametimes[i.obj.index], lambda: loop(i)) #run again.
        lazy(gridsquare) # Non threaded
    def stop_animations(self, gridsquare):
        self.running.clear()
        self.thread = None  

class Timer:
    "Timer for benchmarking"
    def __init__(self):
        self.creation_time = None
    def start(self):
        self.creation_time = perf_counter()
    def stop(self):
        current_time = perf_counter()
        elapsed_time = current_time - self.creation_time
        return f"{elapsed_time:.3f} s"   
# Run Program
if __name__ == '__main__':
    mainclass = SortImages()
