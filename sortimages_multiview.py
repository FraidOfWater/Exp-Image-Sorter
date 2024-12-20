import os
import sys
from time import time
from random import seed
from shutil import rmtree, move as shutilmove
import json
import tkinter as tk
from tkinter.messagebox import askokcancel
from tkinter import filedialog as tkFileDialog
import concurrent.futures as concurrent
from hashlib import md5
from PIL import Image, ImageTk
from imageio import get_reader
import logging
#get persistent selections working again.
#get show next working again. show next.
#is iamgeio[ffmpeg] required?
if getattr(sys, 'frozen', False):  # Check if running as a bundled executable
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(os.path.abspath(__file__))
vipsbin = os.path.join(base_path, "vips-dev-8.16", "bin")
os.environ['PATH'] = os.pathsep.join((vipsbin, os.environ['PATH']))
if os.path.exists(vipsbin):
    os.add_dll_directory(vipsbin)

import pyvips
from gui import GUIManager, randomColor
from navigator import Navigator

#interesting borderwidth adds padding but it is friendly.
logger = logging.getLogger("Sortimages")
logger.setLevel(logging.WARNING)  # Set to the lowest level you want to handle
handler = logging.StreamHandler()
handler.setLevel(logging.WARNING)
formatter = logging.Formatter('%(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# The imagefile class. It holds all information about the image and the state its container is in.
class Imagefile:
    path = ""
    dest = ""
    dupename=False
    def __init__(self, name, path) -> None:
        self.name = tk.StringVar()
        self.name.set(name)
        self.path = path
        self.mod_time = None
        self.file_size = None
        self.checked = tk.BooleanVar(value=False)
        self.destchecked = tk.BooleanVar(value=False)
        self.moved = False
        self.assigned = False
        self.isanimated = False
        self.isvisible = False
        self.isvisibleindestination = False
        self.lazy_loading = True
        self.frames = []
        self.frametimes = []
        self.framecount = 0
        self.index = 0
        self.delay = 100 #Default delay
        self.id = None
    
    def setid(self, id):
        self.id = id
    def setguidata(self, data):
        self.guidata = data
    
    def setdest(self, dest):
        self.dest = dest["path"]
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
                self.assigned = False
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
        self.last_call_time = 0
        self.throttle_delay = 0.19
        self.existingnames = set()
        self.duplicatenames=[]
        self.autosave=True
        self.threads = os.cpu_count()
        self.gui = GUIManager(self)

        self.loadprefs()
        self.gui.initialize()
        self.validate_data_dir_thumbnailsize()

        self.gui.mainloop()

    def validate_data_dir_thumbnailsize(self): #Deletes data directory if the first picture doesnt match the thumbnail size from prefs. (If user changes thumbnailsize, we want to generate thumbnails again)

        data_dir = self.data_dir
        if(os.path.exists(data_dir) and os.path.isdir(data_dir)):
            temp = os.listdir(data_dir)
            image_files = [f for f in temp if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.tiff', '.pcx', '.psd', '.jfif', '.webm'))]
            if image_files:
                first_image_path = os.path.join(data_dir, image_files[0])
                try:
                    image = pyvips.Image.new_from_file(first_image_path)

                    width = image.width
                    height = image.height

                    # The size doesnt match what is wanted in prefs
                    if max(width, height) != self.gui.thumbnailsize:
                        rmtree(data_dir)
                        logger.warning(f"Removing data folder, thumbnailsize changed")
                        os.mkdir(data_dir)
                        logger.warning(f"Re-created data folder.")
                except Exception as e:
                    logger.warning(f"Couldn't load first image in data folder")
            else:
                logger.warning(f"Data folder is empty")
                pass
            pass
        else:
            os.mkdir(data_dir)
    def loadprefs(self):

        # Figure out script and data directory locations
        if getattr(sys, 'frozen', False):  # Check if running as a bundled executable
            script_dir = os.path.dirname(sys.executable)
            self.prefs_path = os.path.join(script_dir, "prefs.json")
        else:
            script_dir = os.path.dirname(os.path.abspath(__file__)) # Else if a ran as py script
            self.prefs_path = os.path.join(script_dir, "prefs.json")
        self.data_dir = os.path.join(script_dir, "data")

        hotkeys = ""
        # todo: replace this with some actual prefs manager that isn't a shittone of ifs
        try:
            with open(self.prefs_path, "r") as prefsfile:

                jdata = prefsfile.read()
                jprefs = json.loads(jdata)

                #paths
                if "source" in jprefs:
                    self.gui.source_folder = jprefs["source"]
                if "destination" in jprefs:
                    self.gui.destination_folder = jprefs["destination"]
                if "lastsession" in jprefs:
                    self.gui.sessionpathvar.set(jprefs['lastsession'])
                if "exclude" in jprefs:
                    self.exclude = jprefs["exclude"]

                #Preferences
                if 'thumbnailsize' in jprefs:
                    self.gui.thumbnailsize = int(jprefs["thumbnailsize"])
                if 'hotkeys' in jprefs:
                    hotkeys = jprefs["hotkeys"]
                if "extra_buttons" in jprefs:
                    self.gui.extra_buttons = jprefs["extra_buttons"]
                if "force_scrollbar" in jprefs:
                    self.gui.force_scrollbar = jprefs["force_scrollbar"]
                if "interactive_buttons" in jprefs:
                    self.gui.interactive_buttons = jprefs["interactive_buttons"]
                if "page_mode" in jprefs:
                    self.gui.page_mode = jprefs["page_mode"]
                if "flicker_free_dock_view" in jprefs:
                    self.gui.flicker_free_dock_view = jprefs["flicker_free_dock_view"]

                #Technical preferences
                if "filter_mode" in jprefs:
                    self.gui.filter_mode = jprefs["filter_mode"]
                if "quick_preview_size_threshold" in jprefs:
                    self.gui.quick_preview_size_threshold = int(jprefs["quick_preview_size_threshold"])
                if "throttle_time" in jprefs:
                    self.gui.throttle_time = jprefs["throttle_time"]
                if 'threads' in jprefs:
                    self.threads = jprefs['threads']
                if 'autosave_session' in jprefs:
                    self.autosave = jprefs['autosave_session']

                #Customization
                if "checkbox_height" in jprefs:
                    self.gui.checkbox_height = int(jprefs["checkbox_height"])
                if "gridsquare_padx" in jprefs:
                    self.gui.gridsquare_padx = int(jprefs["gridsquare_padx"])
                if "gridsquare_pady" in jprefs:
                    self.gui.gridsquare_pady = int(jprefs["gridsquare_pady"])

                if "text_box_colour" in jprefs:
                    self.gui.text_box_colour = jprefs["text_box_colour"]
                if "text_box_selection_colour" in jprefs:
                    self.gui.text_box_selection_colour = jprefs["text_box_selection_colour"]
                    
                if "imageborder_default_colour" in jprefs:
                    self.gui.imageborder_default_colour = jprefs["imageborder_default_colour"]
                if "imageborder_selected_colour" in jprefs:
                    self.gui.imageborder_selected_colour = jprefs["imageborder_selected_colour"]
                if "imageborder_locked_colour" in jprefs:
                    self.gui.imageborder_locked_colour = jprefs["imageborder_locked_colour"]

                #Window colours
                if "main_colour" in jprefs:
                    self.gui.main_colour = jprefs["main_colour"]
                if "grid_background_colour" in jprefs:
                    self.gui.grid_background_colour = jprefs["grid_background_colour"]
                if "canvasimage_background" in jprefs:
                    self.gui.canvasimage_background = jprefs["canvasimage_background"]

                if "whole_box_size" in jprefs:
                    self.gui.whole_box_size = jprefs["whole_box_size"]
                if "square_border_size" in jprefs:
                    self.gui.square_border_size = int(jprefs["square_border_size"])
                if "square_colour" in jprefs:
                    self.gui.square_colour = jprefs["square_colour"]
                if "square_text_colour" in jprefs:
                    self.gui.square_text_colour = jprefs["square_text_colour"]

                if "square_text_box_colour" in jprefs:
                    self.gui.square_text_box_colour = jprefs["square_text_box_colour"]
                if "square_text_box_selection_colour" in jprefs:
                    self.gui.square_text_box_selection_colour = jprefs["square_text_box_selection_colour"]
                if "square_text_box_locked_colour" in jprefs:
                    self.gui.square_text_box_locked_colour = jprefs["square_text_box_locked_colour"]

                if "imagebox_default_colour" in jprefs:
                    self.gui.imagebox_default_colour = jprefs["imagebox_default_colour"]
                if "imagebox_selection_colour" in jprefs:
                    self.gui.imagebox_selection_colour = jprefs["imagebox_selection_colour"]
                if "imagebox_locked_colour" in jprefs:
                    self.gui.imagebox_locked_colour = jprefs["imagebox_locked_colour"]

                if "button_colour" in jprefs:
                    self.gui.button_colour = jprefs["button_colour"]
                if "button_press_colour" in jprefs:
                    self.gui.button_press_colour = jprefs["button_press_colour"]
                if "text_colour" in jprefs:
                    self.gui.text_colour = jprefs["text_colour"]
                if "pressed_text_colour" in jprefs:
                    self.gui.pressed_text_colour = jprefs["pressed_text_colour"]

                if "text_field_colour" in jprefs:
                    self.gui.text_field_colour = jprefs["text_field_colour"]
                if "text_field_text_colour" in jprefs:
                    self.gui.text_field_text_colour = jprefs["text_field_text_colour"]
                if "text_field_activated_colour" in jprefs:
                    self.gui.text_field_activated_colour = jprefs["text_field_activated_colour"]
                if "text_field_activated_text_colour" in jprefs:
                    self.gui.text_field_activated_text_colour = jprefs["text_field_activated_text_colour"]

                if "pane_divider_colour" in jprefs:
                    self.gui.pane_divider_colour = jprefs["pane_divider_colour"]
                #GUI CONTROLLED PREFRENECES
                if "squaresperpage" in jprefs:
                    self.gui.squaresperpage.set(jprefs["squaresperpage"])
                if "sortbydate" in jprefs:
                    self.gui.sortbydatevar.set(jprefs["sortbydate"])
                if "default_delay" in jprefs:
                    self.gui.default_delay.set(jprefs["default_delay"])
                if "viewer_x_centering" in jprefs:
                    self.gui.viewer_x_centering = jprefs["viewer_x_centering"]
                if "viewer_y_centering" in jprefs:
                    self.gui.viewer_y_centering = jprefs["viewer_y_centering"]
                if "show_next" in jprefs:
                    self.gui.show_next.set(jprefs["show_next"])
                if "dock_view" in jprefs:
                    self.gui.dock_view.set(jprefs["dock_view"])
                if "dock_side" in jprefs:
                    self.gui.dock_side.set(jprefs["dock_side"])

                #Window positions
                if "main_geometry" in jprefs:
                    self.gui.main_geometry = jprefs["main_geometry"]
                if "viewer_geometry" in jprefs:
                    self.gui.viewer_geometry = jprefs["viewer_geometry"]
                if "destpane_geometry" in jprefs:
                    self.gui.destpane_geometry = jprefs["destpane_geometry"]
                if "leftpane_width" in jprefs:
                    self.gui.leftpane_width = int(jprefs["leftpane_width"])
                if "middlepane_width" in jprefs:
                    self.gui.middlepane_width = int(jprefs["middlepane_width"])
                if "images_sorted" in jprefs:
                    self.gui.images_sorted.set(jprefs["images_sorted"])

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
            #paths
            "--#--#--#--#--#--#--#---#--#--#--#--#--#--#--#--#--PATHS": "--#--",
            "source": sdp,
            "destination": ddp,
            "lastsession": gui.sessionpathvar.get(),
            "exclude": self.exclude,

            #Preferences
            "--#--#--#--#--#--#--#---#--#--#--#--#--#--#--#--#--USER PREFERENCES":"--#--",
            "thumbnailsize": gui.thumbnailsize,
            "hotkeys": gui.hotkeys,
            "extra_buttons": gui.extra_buttons,
            "force_scrollbar": gui.force_scrollbar,
            "interactive_buttons":gui.interactive_buttons,
            "page_mode": gui.page_mode,

            #Technical preferences
            "--#--#--#--#--#--#--#---#--#--#--#--#--#--#--#--#--TECHNICAL PREFERENCES": "--#--",
            "quick_preview_filter": gui.filter_mode,
            "quick_preview_size_threshold": gui.quick_preview_size_threshold,
            "throttle_time": gui.throttle_time,
            "flicker_free_dock_view": gui.flicker_free_dock_view,
            "threads": self.threads,
            "autosave_session":self.autosave,

            #Customization
            "--#--#--#--#--#--#--#---#--#--#--#--#--#--#--#--#--PADDING AND COLOR FOR IMAGE CONTAINER": "--#--",
            "checkbox_height":gui.checkbox_height,

            "gridsquare_padx":gui.gridsquare_padx,
            "gridsquare_pady":gui.gridsquare_pady,

            "text_box_colour":gui.text_box_colour,
            "text_box_selection_colour":gui.text_box_selection_colour,

            "imageborder_default_colour":gui.imageborder_default_colour,
            "imageborder_selected_colour":gui.imageborder_selected_colour,
            "imageborder_locked_colour":gui.imageborder_locked_colour,

            #Window colours
            "--#--#--#--#--#--#--#---#--#--#--#--#--#--#--#--#--CUSTOMIZATION FOR WINDOWS": "--#--",

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

            #GUI CONTROLLED PREFRENECES
            "--#--#--#--#--#--#--#---#--#--#--#--#--#--#--#--#--SAVE DATA FROM GUI" : "--#--",
            "squaresperpage": gui.squaresperpage.get(),
            "sortbydate": gui.sortbydatevar.get(),
            "default_delay": gui.default_delay.get(),
            "viewer_x_centering": gui.viewer_x_centering,
            "viewer_y_centering": gui.viewer_y_centering,
            "show_next": gui.show_next.get(),
            "dock_view": gui.dock_view.get(),
            "dock_side": gui.dock_side.get(),

            #Window positions
            "--#--#--#--#--#--#--#---#--#--#--#--#--#--#--#--#--SAVE DATA FOR WINDOWS": "--#--",
            "main_geometry": gui.winfo_geometry(),
            "viewer_geometry": gui.viewer_geometry,
            "destpane_geometry":gui.destpane_geometry,
            "leftpane_width":gui.leftui.winfo_width(),
            "middlepane_width":gui.middlepane_width,
            "images_sorted":gui.images_sorted.get(),

            }

        try: #Try to save the preference to prefs.json
            with open(self.prefs_path, "w+") as savef:
                json.dump(save, savef,indent=4, sort_keys=False)
                logger.debug(save)
        except Exception as e:
            logger.warning(("Failed to save prefs:", e))

        try: #Attempt to save the session if autosave is enabled
            if self.autosave:
                self.savesession(False)
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
                if hasattr(obj, 'video_thumb_path'):
                    video_thumb_path = obj.video_thumb_path
                else:
                    video_thumb_path = ""
                if hasattr(obj, 'isanimated'):
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
                    "checked": obj.checked.get(),
                    "moved": obj.moved,
                    "thumbnail": thumb,
                    "video_thumb_path": video_thumb_path,
                    "dupename": obj.dupename,
                    "isanimated": isanimated,
                    })
    
            save = {"dest": self.ddp, "source": self.sdp,
                    "imagelist": imagesavedata,"thumbnailsize":self.gui.thumbnailsize,'existingnames':list(self.existingnames)}
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

            if 'existingnames' in savedata:
                self.existingnames = set(savedata['existingnames'])
            for line in savedata['imagelist']:
                if os.path.exists(line['path']):
                    obj = Imagefile(line['name'], line['path'])
                    obj.thumbnail = line['thumbnail']
                    obj.video_thumb_path = line['video_thumb_path']
                    obj.dest=line['dest']
                    obj.id=line['id']
                    obj.file_size=line['file_size']
                    obj.checked.set(line['checked'])
                    obj.moved = line['moved']
                    obj.dupename=line['dupename']

                    try:
                        obj.isanimated=line['isanimated']
                    except Exception as e:
                        logger.debug(f"No value isanimated: {e}")
                    self.imagelist.append(obj)

            self.gui.thumbnailsize=savedata['thumbnailsize']
            listmax = min(gui.squaresperpage.get(), len(self.imagelist))
            self.gui.initial_dock_setup()
            gui.displaygrid(self.imagelist, range(0, min(gui.squaresperpage.get(),listmax)))
            self.gui.images_left.set(len(self.imagelist))
            self.gui.images_left_and_assigned.set(f"{len(self.gui.assigned_squarelist)}/{self.gui.images_left.get()}")
            gui.guisetup(self.destinations)
        else:
            logger.warning("No Last Session!")
    def get_current_list(self): # Communicates to setdestination what list is selected
        if self.gui.show_unassigned.get():
            unassign = self.gui.unassigned_squarelist
            if self.gui.show_animated.get():
                unassigned_animated = [item for item in unassign if item.obj.isanimated]
                return unassigned_animated
            else:
                return unassign

        elif self.gui.show_assigned.get():
            assign = self.gui.assigned_squarelist
            return assign

        elif self.gui.show_moved.get():
            moved = self.gui.moved_squarelist
            return moved
    def moveall(self):
        loglist = []

        assigned = self.gui.assigned_squarelist
        moved = self.gui.moved_squarelist
        temp = self.gui.assigned_squarelist.copy()
        reopen = "none"
        if hasattr(self.gui, "second_window"):
            self.gui.save_viewer_geometry()
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
        if reopen == "window":
            self.gui.displayimage(self.gui.current_selection)
        elif reopen =="dock":
            self.gui.displayimage(self.gui.current_selection)

        try:
            if len(loglist) > 0:
                with open("filelog.txt", "a") as logfile:
                    logfile.writelines(loglist)

        except Exception as e:
            logger.error(f"Failed to write filelog.txt: {e}")

    def setDestination(self, *args):
        current_time = time()
        if not self.gui.key_pressed:
            pass
        elif current_time - self.last_call_time >= self.throttle_delay: #and key pressed down... so you can tap as fast as you like.
            self.last_call_time = current_time
        else:
            #print("Victim of throttling")
            return

        dest = args[0]
        marked = []
        current_list = []
        current_list = self.get_current_list()

        try:
            wid = args[1].widget
        except AttributeError:
            wid = args[1]["widget"]
        if isinstance(wid, tk.Entry):
            pass
        # Return all images whose checkbox is checked (And currently in view by image viewer, so you can just press a hotkey and not have to check a checkbox everytime) (If interacting with other squares, it will cancel itself out. This is so user wont accidentally move anything.)
        else:
            marked = [x for x in current_list if x.obj.checked.get()]
            if self.gui.current_selection and self.gui.focused_on_secondwindow: # to see if we have clicked elsewhere as to not move the displayed image anymore.
                for x in current_list:
                    if self.gui.current_selection.obj.id == x.obj.id:
                        if x not in marked:
                            marked.append(x)

            for x in marked:
                x.obj.setdest(dest)
                x.obj.guidata["frame"]['background'] = dest['color']
                x.obj.guidata["canvas"]['background'] = dest['color']
                x.obj.checked.set(False)

                # Move from unasssigned to assigned
                if self.gui.show_unassigned.get():
                    x.obj.assigned = True
                    if x.obj.assigned and x not in self.gui.assigned_squarelist:
                        self.gui.unassigned_squarelist.remove(x)
                        self.gui.assigned_squarelist.append(x)

                        # Destination view different behaviour
                        if x.obj.dest == dest['path']:
                            if hasattr(self.gui, 'destwindow'): # if we have new assigned.
                                if self.gui.dest == dest['path']: #the path is here because we only want to append when path is the same as current dest
                                    self.gui.filtered_images.append(x.obj)
                                    #imageobject eventually
                                    self.gui.queue.append(x)

                        # Stop animations
                        if x in self.gui.running:
                            self.gui.running.remove(x)
                        if x in self.gui.track_animated:
                            self.gui.track_animated.remove(x)

                # Moving from assigned to assigned
                elif self.gui.show_assigned.get():

                    # Different behaviour for destination view
                    if hasattr(self.gui, 'destwindow'): # if we have the dest window open
                        if self.gui.dest == dest['path']: # if the dest chosen and current dest window point to same dest
                            if x.obj not in self.gui.filtered_images:
                                self.gui.filtered_images.append(x.obj) # this makes is refresh the pos. but now getting stuff out of dest win or new into it no working.
                                self.gui.queue.append(x)
                            else:
                                x.obj.checked.set(True)
                                x.obj.destchecked.set(True)

                        else:
                            if x.obj in self.gui.filtered_images:
                                self.gui.filtered_images.remove(x.obj)

                # Moving from moved to assigned
                elif self.gui.show_moved.get():
                    x.obj.assigned = True
                    x.obj.moved = True
                    if x.obj.assigned and x not in self.gui.assigned_squarelist:
                        self.gui.moved_squarelist.remove(x)
                        self.gui.assigned_squarelist.append(x)
                        if x.obj.dest == dest['path']:
                            if hasattr(self.gui, 'destwindow'): # if we have new assigned.
                                if self.gui.dest == dest['path']:
                                    self.gui.filtered_images.append(x.obj)
                                    self.gui.queue.append(x)

                        # Stop animations
                        if x in self.gui.running:
                            self.gui.running.remove(x)
                        if x in self.gui.track_animated:
                            self.gui.track_animated.remove(x)

        # Check for destination view changes separately. Note, We use destchecked here, not checked.
        marked = []
        marked = [square for square in self.gui.dest_squarelist if square.obj.destchecked.get()]
        temp = self.gui.assigned_squarelist.copy()

        # Returns all images that are marked, but who are already assigned
        # Why? IDK. It has to do with the behaviour of how items add to the list.
        # Likely so we can update their positions in the list!
        for square in marked:
            if self.gui.show_assigned.get():
                for gridsquare in self.gui.assigned_squarelist:
                    if gridsquare.obj.id == square.obj.id:
                        if not(square.obj.destchecked.get() and square.obj.checked.get()):
                            self.gui.render_refresh.append(gridsquare)
                            break

            #we check against the main assigned list to find the key, then we remove it and add it again, so the order is saved.
            # What the fuck is this? I think it had something to do with how I couldnt use the same gridsquare for dest and imagegrid, so this has to match them.
            for item in temp:
                if item.obj.id == square.obj.id and dest['path'] == square.obj.dest:
                    if not (square.obj.destchecked.get() and square.obj.checked.get()):
                        self.gui.assigned_squarelist.remove(item)
                        self.gui.assigned_squarelist.append(item)
                    square.obj.checked.set(False)
                    self.gui.destgrid_updateslist.append(square)
                    self.gui.filtered_images.remove(square.obj)
                    self.gui.filtered_images.append(square.obj) # going to the same destnation, just refresh, update pos.
                    break
                elif item.obj.id == square.obj.id:
                    self.gui.assigned_squarelist.remove(item)
                    self.gui.assigned_squarelist.append(item)
                    self.gui.filtered_images.remove(square.obj)

                    break

            square.obj.setdest(dest)
            square.obj.guidata["frame"]['background'] = dest['color']
            square.obj.guidata["canvas"]['background'] = dest['color']
            square.obj.destchecked.set(False) #Not .checked for purposes of having different actions take place independent of current view. So
            #For example... I dont remember
            #Very helpful!

        #Updates main and destination windows.
        self.gui.refresh_rendered_list()
        self.gui.images_left_and_assigned.set(f"{len(self.gui.assigned_squarelist)}/{int(self.gui.images_left.get())}")
        if hasattr(self.gui, 'destwindow'): #only refresh dest list if destwindow active.
            self.gui.refresh_destinations()
        self.navigator.update_navigator(self.gui.displayedlist)
        self.navigator.select_next()

    
    def setup(self, dest): # scan the destination
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
            listmax = min(gui.squaresperpage.get(), len(self.imagelist))
            sublist = self.imagelist[0:listmax]
            print(f'Loading: {len(sublist)}')
            self.generatethumbnails(sublist)
            self.gui.initial_dock_setup()
            gui.displaygrid(self.imagelist, range(0, min(len(self.imagelist), gui.squaresperpage.get())))
            self.gui.images_left.set(len(self.imagelist))
            self.gui.images_left_and_assigned.set(f"{len(self.gui.assigned_squarelist)}/{self.gui.images_left.get()}")
            self.navigator = Navigator(self, self.gui)

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
        

    def extract_video_thumbnail(self, imagefile, thumbpath, time='00:00:00'):
        reader = get_reader(imagefile.path)
        tempn = thumbpath.rfind(".jpg")
        temp = thumbpath[:tempn] + '_video_thumb.jpg'

        for frame in reader:
            image = Image.fromarray(frame)
            image.save(temp)
            imagefile.video_thumb_path = temp
            image.thumbnail((self.gui.thumbnailsize,self.gui.thumbnailsize))
            image.save(thumbpath)
            imagefile.thumbnail = thumbpath
            break
    def walk(self, src):
        duplicates = self.duplicatenames
        existing = self.existingnames
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
                    if name in existing:
                        duplicates.append(imgfile)
                        imgfile.dupename=True
                    else:
                        existing.add(name)
                    self.imagelist.append(imgfile)

        # Sort by date modificated
        if self.gui.sortbydatevar.get():
            self.imagelist.sort(key=lambda img: os.path.getmtime(img.path), reverse=True)
        return self.imagelist
    def makethumb(self, imagefile):
            file_name1 = imagefile.path.replace('\\', '/').split('/')[-1]
            if not imagefile.file_size or not imagefile.mod_time:
                file_stats = os.stat(imagefile.path)
                imagefile.file_size = file_stats.st_size
                imagefile.mod_time = file_stats.st_mtime
            id = file_name1 + " " +str(imagefile.file_size)+ " " + str(imagefile.mod_time)

            #dramatically faster hashing.
            hash = md5()
            hash.update(id.encode('utf-8'))

            imagefile.setid(hash.hexdigest())

            thumbpath = os.path.join(self.data_dir, imagefile.id+os.extsep+"jpg")
            

            if(os.path.exists(thumbpath)):
                imagefile.thumbnail = thumbpath
                if imagefile.path.lower().endswith(".mp4") or imagefile.path.lower().endswith(".webm"):
                    tempn = thumbpath.rfind(".jpg")
                    temp = thumbpath[:tempn] + '_video_thumb.jpg'
                    if(os.path.exists(temp)):
                        imagefile.video_thumb_path = temp
                return

            try:
                if imagefile.path.lower().endswith(".mp4"):
                    self.extract_video_thumbnail(imagefile, thumbpath)
                    return
                elif imagefile.path.lower().endswith(".webm"):
                    self.extract_video_thumbnail(imagefile, thumbpath)
                    return
                    
                im = pyvips.Image.thumbnail(imagefile.path, self.gui.thumbnailsize)
                im.write_to_file(thumbpath)
                imagefile.thumbnail = thumbpath
            except Exception as e:
                logger.error("Error in thumbnail generation: %s", e)
    def generatethumbnails(self, images):
        #logger.info("md5 hashing %s files", len(images))
        max_workers = max(1,self.threads)
        with concurrent.ThreadPoolExecutor(max_workers=max_workers) as executor:
            executor.map(self.makethumb, images)
    def load_frames(self, gridsquare): # Creates frames and frametimes for gifs and webps
        if gridsquare.obj.path.lower().endswith(".webm"):
            reader = get_reader(gridsquare.obj.path)
            fps = (reader.get_meta_data().get('fps', 24))
            gridsquare.obj.delay = int(round((1 / fps)*1000))
            for frame in reader:
                image = Image.fromarray(frame)
                image.thumbnail((self.gui.thumbnailsize,self.gui.thumbnailsize))
                tk_image = ImageTk.PhotoImage(image)
                gridsquare.obj.frames.append(tk_image)
                gridsquare.obj.framecount += 1
                gridsquare.obj.frametimes.append(gridsquare.obj.delay)
            gridsquare.obj.lazy_loading = False     
            return
        elif gridsquare.obj.path.lower().endswith(".mp4"):
            reader = get_reader(gridsquare.obj.path)
            fps = (reader.get_meta_data().get('fps', 24))
            gridsquare.obj.delay = int(round((1 / fps)*1000))
            for frame in reader:
                gridsquare.obj.framecount += 1
                gridsquare.obj.frametimes.append(gridsquare.obj.delay)
            gridsquare.obj.lazy_loading = False     
            return
        try:
            with Image.open(gridsquare.obj.path) as img:
                gridsquare.obj.framecount = img.n_frames

                if gridsquare.obj.framecount == 1: #Only one frame, cannot animate
                    print(f"Found static gif/webp: {gridsquare.obj.name.get()[:30]}")
                    gridsquare.obj.isanimated = False
                    return
                
                frame_frametime = img.info.get('duration',gridsquare.obj.delay)

                if frame_frametime == 0:
                    pass
                else:
                    gridsquare.obj.delay = frame_frametime
                
                logger.debug(f"Found animated: {gridsquare.obj.name.get()[:30]} with {gridsquare.obj.framecount} frames.")

                for i in range(gridsquare.obj.framecount):
                    img.seek(i)  # Move to the ith frame
                    frame = img.copy()
                    frame_frametime = img.info.get('duration',gridsquare.obj.delay)

                    gridsquare.obj.frametimes.append(frame_frametime)

                    frame.thumbnail((self.gui.thumbnailsize, self.gui.thumbnailsize), Image.Resampling.LANCZOS)
                    tk_image = ImageTk.PhotoImage(frame)
                    gridsquare.obj.frames.append(tk_image)
                if all(i == 0 for i in gridsquare.obj.frametimes):
                    for i in range(len(gridsquare.obj.frametimes)):
                        gridsquare.obj.frametimes[i] = gridsquare.obj.delay
                    print(f"Bugged animation frametimes. Using default_delay. {gridsquare.obj.name.get()[:30]}")
                gridsquare.obj.lazy_loading = False
                logger.info(f"All frames loaded for: {gridsquare.obj.name.get()[:30]}")
        except Exception as e: #fallback to static.
            logger.error(f"Error in load_frames: {e}")
            gridsquare.obj.isanimated = False

    def checkdupefilenames(self, imagelist):
        duplicates: list[Imagefile] = []
        existing: set[str] = set()

        for item in imagelist:
            if item.name.get() in existing:
                duplicates.append(item)
                item.dupename=True
            else:
                existing.add(item.name)
        return duplicates
    def clear(self, *args):
        if askokcancel("Confirm", "Really clear your selection?"):
            for x in self.imagelist:
                x.checked.set(False)

# Run Program
if __name__ == '__main__':
    mainclass = SortImages()
