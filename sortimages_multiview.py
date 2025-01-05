import os
from shutil import rmtree, move as shutilmove
import json

from random import seed, random
from time import perf_counter, sleep

import logging

from threading import Thread
from concurrent.futures import ThreadPoolExecutor
from gc import collect

from hashlib import md5
from PIL import Image, ImageTk
from imageio import get_reader

import tkinter as tk
from tkinter.messagebox import askokcancel
from tkinter import filedialog as tkFileDialog

from gui import GUIManager
from navigator import Navigator

def import_pyvips():
    "This looks scary, but it just points to where 'import pyvips' can find it's files from"
    "To update this module, change vips-dev-8.16 to your new folder name here and in build.bat"
    base_path = os.path.dirname(os.path.abspath(__file__))
    vipsbin = os.path.join(base_path, "vips-dev-8.16", "bin")
    
    if not os.path.exists(vipsbin):
        raise FileNotFoundError(f"The directory {vipsbin} does not exist.")

    os.environ['PATH'] = os.pathsep.join((vipsbin, os.environ['PATH']))
    os.add_dll_directory(vipsbin)
import_pyvips()
try:
    import pyvips
except Exception as e:
    print("Couldn't import pyvips:", e)

logger = logging.getLogger("Sortimages")
logger.setLevel(logging.WARNING)  # Set to the lowest level you want to handle
handler = logging.StreamHandler()
handler.setLevel(logging.WARNING)
formatter = logging.Formatter('%(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

" Ideas "
# 1. Navigation page by page.
# 2. Lazy load to only see animations currently in canvas view. unloading those not seen currently. scroll ratio and len for example. 0.5 s retry, if not in self.running, put there.
# 3. Wait to animate to prevent lag spikes? Wait to render rather? if we slip on by like navigating, we shouldnt open a new window straight away, but after like 0.1 seconds.
# 4. Move thumbmanager or animate to own module.

"#Bugs#"
" HOT "
# move doesnt clear assigned.
# if nothing selected, should not show next oon view chagne.
# 2. several move doesnt respect order?
# 0. session no names? gen should generate them? no dest clor either.
# 1. Should test if move works, cache deletes correctly etc.
# 2. Dest_viewer adds dupes to destgrid if more than one is added # still true
# 3. Dest anim limit. Make here accoutn for dest, copy code to dest.
# 4. Calculate correct "actual gridsquare size". # fix keypress navigation in fringes.
# 5. Navigate in destpane via keys. (Bindhanadler recognizes from click that it should switch to destpane or if closes or click on grid, back to grid.)

" Easy "
" Medium "
# 1. Destsquares have no load in color ### in dest_viewer marked with ### If the modules are almost same, can merge them/make one us the other... super also?
# 3. Dest and gridsquare canvas colours when loading. investigate.
" Hard "
# 4. Investigate reducing dupe code. gridsquare, destsquare. thumb gen and reload, animate, and it is in dest viewer also the dupes.

" Long-term Polish "
# 1. Autoload, loads 1 more when 1 leaves. target is set in prefs.
# 2. Throttle anything that seems laggy with unlocked inputs.
# 3. Stats overlay. F, L, frame/framecount, frametime, size. F,B, size. Grid, thumbs, frames. Animating/max, thumbs queue. (recolor?)
# 4. Theme selector
# 5. Zooming and moving polishes. compare to authors original. Scrollbar action

" Known issues "
# Fail to allocate bitmap memory issue. Tkinter or PIL cant juggle a lot of animated images at the same time. Load less of them.
# Use self.max_concurrent_frames = 6000 to set memory limit and lower self.threads if you experience freezes.
# Phantom shutdowns every once in a while. Reason unclear.
# You cannot move an image that is being proccessed by thumbsmanager. Example: Generating frames.

# why path and dest there and not others? ###
class Imagefile:
    path = "" # Once move happens, this becomes dest, dest = "" and moved flag becomes True".
    dest = "" # Moved imgs have flag moved = True and dest = "", Assigned images have dest = "path"
    def __init__(self, name, path) -> None:
        "An Imagefile object stores data about the image to help us manage it in the program"
        "Normal attributes"
        self.name = tk.StringVar(value=name)
        self.truncated_filename = "..." # This is just a placeholder for destination destsquare truncated name. We copy it over from gridsquare and dont have to generate it again.
        self.path = path
        self.moved = False              # Used to track if img is sorted
        self.checked = tk.BooleanVar(value=False) # Checkbox checked or not.

        "Hash"
        self.id = None              # Hash of img name, mod_time and file_size. This is faster to hash than whole file binary stream.
        self.mod_time = None        # Used by sortimages. Used to hash id.
        self.file_size = None       # Used by canvasimage. Buffers if large enough. Used to hash id.

        "Animation"
        self.isanimated = False     # If extension is gif, webp, webm or mp4 and framecount > 1. Used together with other attributes to recognize different formats, static, animated, video...
        self.lazy_loading = True    # Used to tell animate to stop lazy loading animation and move to actual loop. ### POTENTIAL CULL
        self.frames = []            # PIL frames for animation with tkinter for imagegrid. Generated by ThumbManager (self.animate) for gif, webp and webm.
        self.frames_dest = []       # PIL frames for animation with tkinter for destgrid. Generated by ThumbManager (self.gui.destination_viewer.dest_thumbs) for gif, webp and webm.
        self.frametimes = []        # Used for animating at correct speed. Generated by thumbmanager.generate.
        self.framecount = 0         # could use len(frames) instead? ###
        self.index = 0              # Used to control what frame is displayed (for imgagegrid).
        self.index_dest = 0         # Used to control what frame is displayed (for destgrid).
        self.delay = 100            #Default delay. Used to fill frametimes if speed can't be extracted from file.

        "Canvasimage, video support"
        self.dimensions = None      # Used by canvasimage. VLC must know aspect ratio.

    def setdest(self, dest) -> None:
        "Sets imagefile dest and destcolor to desired."
        self.dest = dest["path"]
        self.dest_color = dest["color"]
        logger.info("Set destination of %s to %s", self.name.get(), self.dest)

    def move(self, x, fileManager) -> None:
        "Move image from self.path to self.dest and set self.dest = ''. Turn moved flag to True"
        gui = fileManager.gui
        "Early exits"
        if not self.dest: # dest = ""
            return
        if not os.path.isdir(self.dest): # If dest exists but not found in file system
            return

        "Pointers"
        filename = self.name.get() # in function, better to point  like this or call each time? ###
        old_path = self.path + "" # Perhaps unnecessary, if shutil fails, self.path wont get set to destpath. This is for clarity. This is original path of the file.
        destpath = os.path.join(self.dest, filename)

        "Check for conflicts: file with same name already in dest." "Refuse to overwrite anything"
        if os.path.exists(destpath): # path/to/dest/filename
            print(f"File {filename[:30]} already exists in destination. No action") # Make sure this stays in assigned and path unchanged ###
            return

        try:
            shutilmove(self.path, destpath) # Copy -> Delete. If either fail, do exceptions.

            gui.gridmanager.assigned.remove(x)
            gui.gridmanager.moved.append(x)
            self.guidata["frame"].configure(
                highlightbackground="green", highlightthickness=2)

            self.path = destpath
            self.dest = ""
            self.moved = True

            gui.images_left_stats.set(f"{len(gui.gridmanager.assigned)}/{len(gui.gridmanager.gridsquarelist)-len(gui.gridmanager.assigned)-len(gui.gridmanager.moved)}/{len(fileManager.imagelist)-len(gui.gridmanager.assigned)-len(gui.gridmanager.moved)}")
            gui.images_sorted.set(len(gui.gridmanager.moved))
        except Exception as e:
            "Shutil failed: Did delete old fail?"
            if os.path.exists(destpath) and os.path.exists(old_path): # This can only remove files created by shutil due to our early exits checking for anything in the way. Safe.
                os.remove(destpath)
                print(f"File {filename[:30]} is in use and is unable to delete. Removing created copy from destination.")
                return 
            else:
                print(f"Error moving/deleting: {e} {filename[:30]}, This error shouldn't be raised at all. Report/investigate")
            self.guidata["frame"].configure(highlightbackground="red", highlightthickness=2) # Notify user via gui if we get exceptions.

class SortImages:
    imagelist = [] # Store all Imagefiles
    destinations = []
    exclude = []
    def __init__(self) -> None:
        "Sortimages setups the program. It creates imagefiles from the folder given, loads and saves prefs, loads and saves sessions, and starts up the gui and other modules."
        
        "Timekeeping and throttling"
        self.timer = Timer()        # Time since creation.
        self.last_call_time = 0     # Used to throttle setdestination against too frequent calls
        self.throttle_delay = 0.19

        "Normal attributes"
        self.autosave=True
        self.threads = 4 # Roughly how much computing power you use. Thumbs use twice this amount, frames half.
        self.max_concurrent_frames = 6200 # memory overflow / bitmap allocation fix. Too many tkinter animations will crash the program. Use this to limit the amount of frames in memory.

        "Start modules"
        self.gui = GUIManager(self) # loadprefs() edits self.gui attributes. Create self.gui and attributes for loadprefs() to manipulate.
        self.loadprefs()            # Load prefs
        self.gui.initialize()       # Let GUI initialize fully now with loaded values.

        self.navigator = Navigator(self) # Navigator highlights the current selection, main use is to be able to navigate using arrow or wasd keys ### (wasd not implemented)
        self.animate = Animate(self.gui.square_colour)         # Animate module is dedicated for making things animated.
        self.thumbs = ThumbManager(self) # Thumbmanager generates thumbs, frames, truncated names and imagefile attributes, and reloads and unloads resources when needed.
        
        self.gui.show_ram_usage()

        self.validate_thumbnail_cache()
        self.gui.mainloop()

    def validate_thumbnail_cache(self):
        "Setups cache folder for thumbnails. If folder doesn't exist, it is created. If the first picture in it is not the expected size, the folder is emptied."

        "Pointers"
        data_dir = self.data_dir

        "Data folder doesn't exists: creates it"
        if not (os.path.exists(data_dir) and os.path.isdir(data_dir)):
            logger.warning(f"Data folder created")
            os.mkdir(data_dir)
            return

        "Data folder exists: do nothing if empty"
        cache = os.listdir(data_dir)
        if len(cache) < 1:
            logger.warning(f"Data folder is empty")
            return

        "Data folder not empty: empty folder if first file name is wrong"
        if not cache[0].lower().endswith('.jpg'):
            try:
                logger.warning(f"Removing data folder, first file inspected wasn't .jpg")
                rmtree(data_dir)
                os.mkdir(data_dir)
                logger.warning(f"Re-created data folder.")
            except Exception as e:
                print(f"Couldn't delete/create data folder: {e}")
            return
        
        "First image found, check whether it is the expected size (prefs.json thumbnailsize)"
        first_image_path = os.path.join(data_dir, cache[0])
        try:
            image = pyvips.Image.new_from_file(first_image_path) # Should be robust, these images are create by PIL or pyvips themselves.
            if max(image.width, image.height) != self.gui.thumbnailsize: # The larger side doesn't equal thumbnailsize in prefs.json, meaning user changed this setting.
                try:
                    logger.warning(f"Removing data folder, thumbnailsize changed")
                    rmtree(data_dir)
                    os.mkdir(data_dir)
                    logger.warning(f"Re-created data folder.")
                except Exception as e:
                    print(f"Couldn't delete/create data folder: {e}")
        except Exception as e:
            logger.error(f"Couldn't load first image in data folder {e}")
        finally:
            del image
            
    def loadprefs(self):
        "Loads prefs.json. Needs self.gui to be created. This edits self.gui attributes."
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_dir = os.path.join(script_dir, "data")
        self.prefs_path = os.path.join(os.getcwd(), "prefs.json")
        hotkeys = "" # manual checking at end of this method

        try:
            with open(self.prefs_path, "r") as prefsfile:

                jdata = prefsfile.read()
                jprefs = json.loads(jdata)

                "Paths"
                self.gui.source_folder = jprefs["paths"]["source"]
                self.gui.destination_folder = jprefs["paths"]["destination"]
                self.gui.sessionpathvar.set(jprefs["paths"]['lastsession'])
                self.exclude = jprefs["paths"]["exclude"]
        
                "Preferences"
                self.gui.thumbnailsize = int(jprefs["preferences"]["user"]["thumbnailsize"])
                hotkeys = jprefs["preferences"]["user"]["hotkeys"]
                self.gui.extra_buttons = jprefs["preferences"]["user"]["extra_buttons"]
                self.gui.force_scrollbar = jprefs["preferences"]["user"]["force_scrollbar"]
                self.gui.interactive_buttons = jprefs["preferences"]["user"]["interactive_buttons"]
                self.gui.page_mode = jprefs["preferences"]["user"]["page_mode"]

                "Technical preferences"
                self.gui.filter_mode = jprefs["preferences"]["technical"]["quick_preview_filter"]
                self.gui.quick_preview_size_threshold = int(jprefs["preferences"]["technical"]["quick_preview_size_threshold"])
                self.gui.throttle_time = jprefs["preferences"]["technical"]["throttle_time"]
                self.threads = jprefs["preferences"]["technical"]['threads']
                self.autosave = jprefs["preferences"]["technical"]['autosave_session']

                "Customization"
                self.gui.checkbox_height = int(jprefs["appearance"]["image_container"]["checkbox_height"])
                self.gui.gridsquare_padx = int(jprefs["appearance"]["image_container"]["gridsquare_padx"])
                self.gui.gridsquare_pady = int(jprefs["appearance"]["image_container"]["gridsquare_pady"])
                self.gui.text_box_colour = jprefs["appearance"]["image_container"]["text_box_colour"]
                self.gui.text_box_selection_colour = jprefs["appearance"]["image_container"]["text_box_selection_colour"]

                self.gui.imageborder_default_colour = jprefs["appearance"]["image_container"]["imageborder_default_colour"]
                self.gui.imageborder_selected_colour = jprefs["appearance"]["image_container"]["imageborder_selected_colour"]
                self.gui.imageborder_locked_colour = jprefs["appearance"]["image_container"]["imageborder_locked_colour"]

                "Window colours"
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

                "GUI CONTROLLED PREFRENECES"
                self.gui.squaresperpage.set(jprefs["qui"]["squaresperpage"])
                self.gui.sortbydatevar.set(jprefs["qui"]["sortbydate"])
                self.gui.viewer_x_centering = jprefs["qui"]["viewer_x_centering"]
                self.gui.viewer_y_centering = jprefs["qui"]["viewer_y_centering"]
                self.gui.show_next.set(jprefs["qui"]["show_next"])
                self.gui.dock_view.set(jprefs["qui"]["dock_view"])
                self.gui.dock_side.set(jprefs["qui"]["dock_side"])

                "Window positions"
                self.gui.main_geometry = jprefs["window_settings"]["main_geometry"]
                self.gui.viewer_geometry = jprefs["window_settings"]["viewer_geometry"]
                self.gui.destpane_geometry = jprefs["window_settings"]["destpane_geometry"]
                self.gui.leftpane_width = int(jprefs["window_settings"]["leftpane_width"])
                self.gui.middlepane_width = int(jprefs["window_settings"]["middlepane_width"])
                self.gui.images_sorted.set(jprefs["window_settings"]["images_sorted"])

                self.gui.actual_gridsquare_width = self.gui.thumbnailsize + self.gui.gridsquare_padx + self.gui.square_border_size*2 + self.gui.whole_box_size*2
                self.gui.actual_gridsquare_height = self.gui.thumbnailsize + self.gui.gridsquare_pady + self.gui.square_border_size*2 + self.gui.whole_box_size*2 + self.gui.checkbox_height

            if len(hotkeys) > 1:
                self.gui.hotkeys = hotkeys

            "Make sure middlepane doesnt become 'hidden', fooled me!"
            "If the thumbnail grid becomes too small, reset it to an acceptable size."
            win_width, discard = self.gui.main_geometry.split("x")
            win_width = int(win_width)
            l_pan = self.gui.leftpane_width
            m_pan = self.gui.middlepane_width
            if win_width - l_pan-m_pan < self.gui.thumbnailsize+35:
                space = int(win_width) - int(self.gui.leftpane_width)
                self.gui.middlepane_width = space-self.gui.thumbnailsize-35 # actual gridsqaure width? ###

        except Exception as e:
            logger.error(f"Error loading prefs.json: {e}")
    def saveprefs(self, gui):
        "Saves all customizable stuff to prefs.json."
        if gui.middlepane_frame.winfo_width() == 1: # Do not try to save invalid value
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

        "Save to prefs.json"
        try:
            with open(self.prefs_path, "w+") as json_file:
                json.dump(save, json_file, indent=4)
                logger.debug(save)
        except Exception as e:
            logger.error(("Failed to save prefs:", e))

        "Save session"
        try:
            if self.autosave:
                self.savesession(asksavelocation=False)
        except Exception as e:
            logger.error(("Failed to save session:", e))
    def savesession(self,asksavelocation):
        "Saves session. Includes some imagefile data and assigned list ids. Sessions do not support thumbnail_cache_validation. So you cannot change thumbnailsize during one."

        "If there is nothing to save"
        if len(self.imagelist) < 1:
            return

        "Prompt"
        if asksavelocation:
            filet=[("Javascript Object Notation","*.json")]
            savelocation=tkFileDialog.asksaveasfilename(confirmoverwrite=True,defaultextension=filet,filetypes=filet,initialdir=os.getcwd(),initialfile=self.gui.sessionpathvar.get())
        else:
            savelocation = self.gui.sessionpathvar.get()
        
        "Construct save file"
        imagesavedata = []
        "Save imagefile attributes"
        for obj in self.imagelist:

            if hasattr(obj, 'thumbnail'): thumb = obj.thumbnail
            else: thumb = ""

            if obj.isanimated: isanimated = True
            else: isanimated = False

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

            if hasattr(obj, "dimensions"):
                if obj.dimensions != None:
                    imagesavedata[-1]["dimensions"] = obj.dimensions

        "We save the order of the assigned list"
        freshest_moves = [x.obj.id for x in self.gui.gridmanager.assigned if x.obj.dest] # add moved in the future if want to track that too ### separate list to track this order were moved is not removed?
        freshest_moves2 = [x.obj.id for x in self.gui.gridmanager.moved if x.obj.moved]
        save = {"dest": self.ddp, "source": self.sdp, "thumbnailsize":self.gui.thumbnailsize,
                "imagelist": imagesavedata, "freshest_moves": freshest_moves, "freshest_moves2": freshest_moves2}
    
        with open(savelocation, "w+") as json_file:
            json.dump(save, json_file, indent=4)    
    def loadsession(self):
        "Loads session"
        sessionpath = self.gui.sessionpathvar.get()

        "If there is no last session, early exit"
        if not (os.path.exists(sessionpath) and os.path.isfile(sessionpath)):
            logger.warning("No Last Session!")
            return
        
        with open(sessionpath, "r") as json_file:
            sdata = json_file.read()
            savedata = json.loads(sdata)

        self.sdp = savedata['source']
        self.ddp = savedata['dest']
        self.setup(savedata['dest'])

        print("")
        print(f'Using session:  "{sessionpath}"')
        print(f'Source:   "{self.sdp}"')
        print(f'Target:   "{self.ddp}"')

        self.gui.thumbnailsize=savedata['thumbnailsize']

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
                    d = line['dimensions']
                    obj.dimensions=(int(d[0]), int(d[1]))
                except Exception as e:
                    pass
                self.imagelist.append(obj)

        moved_ids = set()
        for line in savedata['freshest_moves2']:
            moved_ids.add(line)
        moved_list = [x for x in self.imagelist if x.id in moved_ids]

        assigned_ids = set()
        for line in savedata['freshest_moves']:
            assigned_ids.add(line)
        assigned_list = [x for x in self.imagelist if x.id in assigned_ids]

        self.gui.initial_dock_setup()
        self.gui.guisetup(self.destinations)

        self.gui.gridmanager.load_session(assigned_list, moved_list) 
        self.gui.destination_viewer.get_paths()

        self.gui.images_left_stats.set(f"{len(self.gui.gridmanager.assigned)}/{len(self.gui.gridmanager.gridsquarelist)-len(self.gui.gridmanager.assigned)-len(self.gui.gridmanager.moved)}/{len(self.imagelist)-len(self.gui.gridmanager.assigned)-len(self.gui.gridmanager.moved)}")
        self.gui.images_sorted.set(len(self.gui.gridmanager.moved))

    def moveall(self):
        temp = self.gui.gridmanager.assigned.copy()
        reopen = "none"
        old = None
        if hasattr(self.gui, "second_window") and hasattr(self.gui, "Image_frame"):
            #self.gui.close_second_window()
            old = self.gui.Image_frame.obj
            self.gui.middlepane_frame.grid_forget()
            self.gui.Image_frame.destroy() # After needed so player closes correctly, idk why.
            self.gui.unbind("<Configure>")
            del self.gui.Image_frame
            reopen = "window"
        elif hasattr(self.gui, "Image_frame"):
            old = self.gui.Image_frame.obj
            self.gui.middlepane_frame.grid_forget()
            self.gui.Image_frame.destroy()
            self.gui.unbind("<Configure>")
            del self.gui.Image_frame
            reopen = "dock"

        for x in temp:
            try:
                x.obj.move(x, self) # Pass functionality to happen in move so it can fail removing from the sorted lists when shutil.move fails.
            except Exception as e:
                print("Fail in move", e)
        temp.clear()
        
        if reopen == "window":
            self.gui.displayimage(old)
        elif reopen =="dock":
            self.gui.displayimage(old)

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
        if hasattr(self.gui.destination_viewer, "destwindow"):
            displayedset = self.gui.gridmanager.displayedset.union(self.gui.destination_viewer.displayedset)
        else: displayedset = self.gui.gridmanager.displayedset # Current list being compared

        try:
            wid = args[1].widget
        except AttributeError:
            wid = args[1]["widget"]
        if isinstance(wid, tk.Entry):
            pass

        # Return all images whose checkbox is checked (And currently in view by image viewer, so you can just press a hotkey and not have to check a checkbox everytime) (If interacting with other squares, it will cancel itself out. This is so user wont accidentally move anything.)
        else:
            marked = [x for x in displayedset if x.obj.checked.get()] # All checked are now in marked list.

            "Current selection is added to marked if focus never lost"
            if self.navigator.old and self.gui.focused_on_secondwindow and self.navigator.old in displayedset: # to see if we have clicked elsewhere as to not move the displayed image anymore.
                if self.navigator.old not in marked:
                    marked.append(self.navigator.old)

            #Handle lists
            to_remove_from_grid = []
            to_refresh_from_grid = []
            remove = []
            add = []
            for x in marked: #set background to button colour
                x.obj.setdest(dest)
                x.obj.guidata["frame"]['background'] = dest['color']
                x.obj.guidata["canvas"]['background'] = dest['color']
                x.obj.checked.set(False)


                if hasattr(self.gui.destination_viewer, "destwindow"):
                    if x.obj.dest:
                        if x.obj.id in self.gui.destination_viewer.displayedlist_ids:
                            remove.append(x)
                        else:
                            add.append(x.obj)
                if remove:
                    self.gui.destination_viewer.remove_squares(remove)
                if add:
                    self.gui.destination_viewer.add_squares(add)

                # Move from list to list
                if self.gui.current_view.get() == "Show Unassigned":
                    if x in self.gui.gridmanager.displayedset:
                        self.gui.gridmanager.unassigned.remove(x)
                        self.gui.gridmanager.assigned.append(x)
                        to_remove_from_grid.append(x)

                # Moving from assigned to assigned
                elif self.gui.current_view.get() == "Show Assigned":
                    if x in self.gui.gridmanager.displayedset:
                        self.gui.gridmanager.assigned.remove(x)
                        self.gui.gridmanager.assigned.append(x)
                        to_refresh_from_grid.append(x) # Means we want to update pos so it lines up with assigned list order.
                        #dest, dest may be changed, check if destsquare is same as gridsquare, if not, nothing, if yes, remove.

                # Moving from moved to assigned
                elif self.gui.current_view.get() == "Show Moved":
                    if x in self.gui.gridmanager.displayedset:
                        self.gui.gridmanager.moved.remove(x)
                        self.gui.gridmanager.assigned.append(x)
                        to_remove_from_grid.append(x)
                
                elif self.gui.current_view.get() == "Show Animated":
                    if x in self.gui.gridmanager.displayedset:
                        self.gui.gridmanager.assigned.append(x)
                        to_remove_from_grid.append(x)
    
            self.gui.gridmanager.remove_squares(to_remove_from_grid, unload=True) # For moved and Unassigned
            "Assigned view: end of list is 'newest' and is displayed first, remove from list and add it back so it shows up as first."
            self.gui.gridmanager.remove_squares(to_refresh_from_grid, unload=False)
            self.gui.gridmanager.add_squares(to_refresh_from_grid)

            #    gridsquare_ids = [x.obj.id for x in combined_list]
            #    # remove
            #    dest_ids = [x.obj.id for x in self.gui.destination_viewer.displayedlist]
            #    add = [x for x in gridsquare_ids if x not in dest_ids]
            #    # check if in the list. if in list check old and new dest
            #    remove = [x for x in gridsquare_ids if x in dest_ids and ]
            #    self.gui.destination_viewer.changed_squares(matched_destsquares_to_gridsquares)


        "If show next option checked, and next exists, and viewer is open, show next image"
        if self.gui.show_next.get() and len(self.gui.gridmanager.displayedset) >= 1 and hasattr(self.gui, "Image_frame"):
            self.navigator.select_next(self.gui.gridmanager.displayedlist)

        "Update stat tracker"
        self.gui.images_left_stats.set(f"{len(self.gui.gridmanager.assigned)}/{len(self.gui.gridmanager.gridsquarelist)-len(self.gui.gridmanager.assigned)-len(self.gui.gridmanager.moved)}/{len(self.imagelist)-len(self.gui.gridmanager.assigned)-len(self.gui.gridmanager.moved)}")
        self.gui.images_sorted.set(len(self.gui.gridmanager.moved))

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
            self.gui.destination_viewer.get_paths()
            gui.sessionpathvar.set(os.path.basename(
                self.sdp)+"-"+os.path.basename(self.ddp)+".json")
            print("")
            print(f'New session:  "{self.gui.sessionpathvar.get()}"')
            print(f'Source:   "{self.sdp}"')
            print(f'Target:   "{self.ddp}"')
            self.walk(self.sdp)
            self.gui.initial_dock_setup()
            self.timer.start()
            self.gui.gridmanager.load_more()
            self.gui.images_left_stats.set(f"{len(self.gui.gridmanager.assigned)}/{len(self.gui.gridmanager.gridsquarelist)-len(self.gui.gridmanager.assigned)-len(self.gui.gridmanager.moved)}/{len(self.imagelist)-len(self.gui.gridmanager.assigned)-len(self.gui.gridmanager.moved)}")
            gui.images_sorted.set(len(self.gui.gridmanager.moved))

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
    "Thumbmanager class to manage memory usage of images in grid."
    def __init__(self, fileManager):
        self.animate = fileManager.animate
        self.threads = fileManager.threads
        self.data_dir = fileManager.data_dir
        self.gui = fileManager.gui
        self.fileManager = fileManager
        self.thread = None
        self.gen_thread = None
        self.gen_queue = []
        self.queue = []
    def generate(self, gridsquares):
        "Generate thumbnails, generate frames, start animation of frames"
        filelist = [x.obj for x in gridsquares]
        def multithread():
            animated = [obj for obj in filelist if obj.isanimated]
            try:
                max_workers = max(1,self.threads*2)
                a = perf_counter()
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    executor.map(makethumb, filelist)
                print(f"Thumbnails generated in: {perf_counter()-a:.2f}")

                max_workers = max(1,self.threads)

                a = perf_counter()
                self.gui.queue_track = len(animated)
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    executor.map(makeframes, animated)
                print(f"Thumbframes generated in: {perf_counter()-a:.2f}")
                if self.gen_queue:
                    self.gui.queue_track = len(self.gen_queue)
                    Thread(target=queue_emptier, daemon=True).start()
            except Exception as e:
                print("Error in generating thumbs and frames", e)
            finally: self.gen_thread = None

        def queue_emptier():
            with ThreadPoolExecutor(max_workers=max(1,self.threads*2)) as executor:
                while self.gen_queue:
                    obj = self.gen_queue[0]
                    frames_loaded = 0
                    if len(self.gui.gridmanager.displayedlist) == 0:
                        self.gen_queue.pop(0)
                        skip = True
                        future = executor.submit(makeframes, obj, skip, queue=True)
                    else:# Count currently loaded frames
                        for x in self.animate.running:
                            frames_loaded += len(x.obj.frametimes)

                        # Check if we can load more frames
                        if frames_loaded + len(obj.frametimes) < self.fileManager.max_concurrent_frames:
                            self.gen_queue.pop(0)
                            show_objs = [x.obj for x in self.gui.gridmanager.displayedlist]  # show flag would be fire here.
                            skip = obj not in show_objs  # Simplified skip logic
                            future = executor.submit(makeframes, obj, skip, queue=True)
                        sleep(0.3)  # Sleep to avoid busy waiting

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
                imagefile.id = hash.hexdigest()
            def lazy_load_thumb():
                def makename(obj):
                    frame = obj.guidata['frame']
                    obj.truncated_filename = self.gui.gridmanager.truncate_text(obj)
                    frame.obj2.set(obj.truncated_filename)
                try:
                    #this is faster
                    buffer = pyvips.Image.new_from_file(imagefile.thumbnail)
                    img = ImageTk.PhotoImage(Image.frombuffer(
                        "RGB", [buffer.width, buffer.height], buffer.write_to_memory()))
                except:  # PIL fallback
                    try:
                        logger.warning("Pillow fallback")
                        img = ImageTk.PhotoImage(Image.open(imagefile.thumbnail))
                    except:
                        logger.error(f"Pillow and Pyvips failed to generate thumbnail for {imagefile.name.get()[:30]}")
                finally:
                    imagefile.guidata['img'] = img
                    canvas = imagefile.guidata['canvas']
                    frame = imagefile.guidata['frame']
                    canvas.image = img
                    canvas.itemconfig(frame.canvas_image_id, image=img)
                    makename(imagefile) # Quite expensive name truncation! # So I threaded it!

            gen_img_attributes()

            thumbpath = os.path.join(self.data_dir, imagefile.id+os.extsep+"jpg")

            "Early exit if thumb already exists, generates dimensions for mp4 and webm if needed (canvasimage functionality)"
            if (os.path.exists(thumbpath)): # Already exists, just point to it.
                imagefile.thumbnail = thumbpath
                lazy_load_thumb() # Gen ImageTK from this..

                "Get dimensions for mp4 and webm."
                if imagefile.path.lower().endswith((".mp4",".webm")) and not imagefile.dimensions: # Ignored if loadsession loaded them already.
                    try: # Pyvips is fast
                        image = pyvips.Image.new_from_file(imagefile.thumbnail)
                        imagefile.dimensions = (image.width, image.height)
                    except: # Pillow fallback
                        try:
                            logger.warning("Pillow fallback")
                            with Image.open(imagefile.thumbnail) as image:
                                imagefile.dimensions = image.size
                        except:
                            logger.error(f"Pillow and Pyvips failed to load get dimensions for {imagefile.name.get()[:30]}")
            
                "Early exit if file is mp4 or webm. Generate thumb and dimensions for them."
            elif imagefile.path.lower().endswith((".mp4",".webm")):
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

                "Generate thumb for regular static image"
            else:
                try: # Pyvips is fast
                    image = pyvips.Image.thumbnail(imagefile.path, self.gui.thumbnailsize)
                    image.write_to_file(thumbpath)
                    imagefile.thumbnail = thumbpath
                    lazy_load_thumb()
                except: # Pillow fallback
                    try:
                        logger.warning("Pillow fallback")
                        with Image.open(imagefile.path) as image:
                            image.thumbnail((self.gui.thumbnailsize,self.gui.thumbnailsize))
                            if image.mode in ("RGBA", "P"):
                                image = image.convert("RGB")
                            image.save(thumbpath)
                        imagefile.thumbnail = thumbpath
                        lazy_load_thumb()
                    except Exception as e:
                        print(f"Pillow and Pyvips failed to generate thumbnail for {imagefile.name.get()[:30]}")
        def makeframes(obj, skip=False, queue=False): # Creates frames and frametimes for gifs and webps
            # Load frames for WEBM impepelemnt with vlc? can take a long time to load.
            self.gui.queue_track -= 1
            if obj.path.lower().endswith(".mp4"): # Handled by vlc, not needed, here just to catch them from entering else.
                return
            
            frames_loaded = 0
            for x in self.animate.running:
                frames_loaded += len(x.obj.frametimes)
            if not frames_loaded + len(obj.frametimes) < self.fileManager.max_concurrent_frames:
                self.gen_queue.append(obj)
                
                return
            
            obj.frames = []
            if not skip:
                show_objs = [x.obj for x in self.gui.gridmanager.displayedlist]  # show flag would be fire here.
                skip = obj not in show_objs  # Simplified skip logic
            if obj.path.lower().endswith(".webm"):
                try:
                    reader = get_reader(obj.path)
                    fps = (reader.get_meta_data().get('fps', 24))
                    obj.delay = int(round((1 / fps)*1000))
                    f = True
                    for frame in reader:
                        if not skip:
                            image = Image.fromarray(frame)
                            image.thumbnail((self.gui.thumbnailsize,self.gui.thumbnailsize))
                            tk_image = ImageTk.PhotoImage(image)

                            obj.frames.append(tk_image)
                        obj.framecount += 1
                        obj.frametimes.append(obj.delay)
                        if f and not skip:
                            self.animate.add_animation(obj)
                            f = False
                    obj.lazy_loading = False
                except Exception as e:
                    print(f"Error in frame generation for grid: {e}")
                finally:
                    self.gen_thread = None
                    if reader:
                        reader.close()
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
                        f = True
                        for i in range(temp):
                            img.seek(i)  # Move to the ith frame
                            frame = img.copy()
                            frame_frametime = img.info.get('duration',obj.delay)
                            obj.frametimes.append(frame_frametime)
                            if not skip:
                                frame.thumbnail((self.gui.thumbnailsize, self.gui.thumbnailsize), Image.Resampling.LANCZOS)
                                tk_image = ImageTk.PhotoImage(frame)
                                obj.frames.append(tk_image)
                            obj.framecount += 1
                            if f and not skip:
                                self.animate.add_animation(obj)
                                f = False

                        if all(i == 0 for i in obj.frametimes):
                            for i in range(len(obj.frametimes)):
                                obj.frametimes[i] = obj.delay
                            print(f"Bugged animation frametimes. Using default_delay. {obj.name.get()[:30]}")
                        obj.lazy_loading = False
                        logger.info(f"All frames loaded for: {obj.name.get()[:30]}")
                except Exception as e: #fallback to static.
                    logger.error(f"Error in load_thumbframes: {e}")
                    obj.isanimated = False
            show_objs = [x.obj for x in self.gui.gridmanager.displayedlist]  # show flag would be fire here.
            skip = obj not in show_objs
            if skip:
                obj.frames = []
                gridsquare = obj.guidata["frame"]
                self.animate.remove_animation(gridsquare, self.gui.square_colour)
            
        self.gen_thread = Thread(target=multithread, daemon=True)
        self.gen_thread.start()
    def reload(self, gridsquares):
        #queue system. executor global, submit/map to it def concurrent(squares, workers) 1 persistent thread for it. no daemon
        def multithread():
            self.thread = new_thread
            a = perf_counter()
            animated = [x for x in gridsquares if x.obj.isanimated and len(x.obj.frametimes) != 0]
            if self.gui.current_view.get() == "Show Assigned" or self.gui.current_view.get() == "Show Moved":
                if len(gridsquares) > 1:
                    gridsquares.reverse()
            try:
                max_workers = max(1,self.threads*2)
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    executor.map(reload_static, gridsquares)
                print(f"Thumbnails loaded in: {perf_counter()-a:.2f}")
                max_workers = max(1,self.threads)
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    executor.map(reload_animated, animated)
                print(f"Thumbframes loaded in: {perf_counter()-a:.2f}")
                if self.queue:
                    queue_emptier()
            except Exception as e:
                print("Error reloading thumbs and frames", e)
        def queue_emptier():
            with ThreadPoolExecutor(max_workers=max(1,self.threads)) as executor:
                while self.queue:
                    gridsquare = self.queue[0]
                    frames_loaded = 0
                    if len(self.gui.gridmanager.displayedlist) == 0:
                        skip = True
                        self.queue.pop(0)
                        future = executor.submit(reload_animated, gridsquare, skip)
                    else:  # Count currently loaded frames
                        for x in self.animate.running:
                            frames_loaded += len(x.obj.frametimes)

                        # Check if we can load more frames
                        if frames_loaded + len(gridsquare.obj.frametimes) < self.fileManager.max_concurrent_frames:
                            self.queue.pop(0)
                            skip = gridsquare not in self.gui.gridmanager.displayedset  # Simplified skip logic
                            future = executor.submit(reload_animated, gridsquare, skip)
                        sleep(0.3)  # Sleep to avoid busy waiting
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
                    imageobj.guidata['img'] = img
                    gridsquare.canvas.image = img
                    gridsquare.canvas.itemconfig(gridsquare.canvas_image_id, image=img)
            except Exception as e:
                print(f"Error in load_thumb: {e}")
        def reload_animated(gridsquare, skip=False):
            obj = gridsquare.obj
            if obj.path.lower().endswith(".mp4"):
                return
            #gridsquare in self.animate.running
            if len(obj.frames) == obj.framecount: # we switched to a view where the gif is already playing, skip
                return
            if len(obj.frames) != obj.framecount and len(obj.frames) > 0: #another thread is active
                return
            frames_loaded = 0
            for x in self.animate.running: ### account for dest running.
                frames_loaded += len(x.obj.frametimes)
            if not frames_loaded + len(obj.frametimes) < self.fileManager.max_concurrent_frames:
                if gridsquare not in self.queue:
                    self.queue.append(gridsquare)
                return
            
            obj.frames = [] #make sure it is empty for sure
            obj.lazy_loading = True
            if skip:
                return
            if obj.path.lower().endswith(".webm"):
                reader = None
                try:
                    reader = get_reader(obj.path)
                    fps = (reader.get_meta_data().get('fps', 24))
                    obj.delay = int(round((1 / fps)*1000))
                    f = True
                    for frame in reader:
                        if not skip:
                            image = Image.fromarray(frame)
                            image.thumbnail((self.gui.thumbnailsize,self.gui.thumbnailsize))
                            tk_image = ImageTk.PhotoImage(image)
                        obj.frames.append(tk_image)
                        if f:
                            self.animate.add_animation(obj)
                            f = False

                    obj.lazy_loading = False
                except Exception as e:
                    print(f"Error in frame generation for grid: {e}")
                finally:
                    reader.close()
            # Load frames for GIF, WEBP
            else:
                try:
                    with Image.open(obj.path) as img:
                        if obj.framecount == 0: # Static
                            return
                        f = True
                        for i in range(obj.framecount):
                            img.seek(i)  # Move to the ith frame
                            frame = img.copy()
                            frame.thumbnail((self.gui.thumbnailsize, self.gui.thumbnailsize), Image.Resampling.LANCZOS)
                            tk_image = ImageTk.PhotoImage(frame)
                            obj.frames.append(tk_image)
                            if f:
                                self.animate.add_animation(obj)
                                f = False

                        obj.lazy_loading = False
                        logger.info(f"All frames loaded for: {obj.name.get()[:30]}")
                except Exception as e: #fallback to static.
                    logger.error(f"Error in reload_thumbframes: {e}")
                    obj.isanimated = False
            skip = gridsquare not in self.gui.gridmanager.displayedset
            if skip:
                gridsquare.obj.frames = []
                self.animate.remove_animation(gridsquare, self.gui.square_colour)

        if not (self.gen_thread and self.gen_thread.is_alive()) and gridsquares:
            new_thread = Thread(target=multithread, daemon=True)
            new_thread.start()
            print("(Thread) Reloading:", len(gridsquares))
    def unload(self, gridsquares): # thread? ### need thread because unload is very slow for 1000 pics.
        def multithread():
            a = perf_counter()
            animated = [x for x in gridsquares if x.obj.frames]
            try:
                max_workers = max(1,self.threads*2)
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                   executor.map(unload_animated, animated)
                print(f"Thumbframes unloaded in: {perf_counter()-a:.2f}")
                max_workers = max(1,self.threads*2)
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                   executor.map(unload_static, gridsquares)
                print(f"Thumbnails unloaded in: {perf_counter()-a:.2f}")
                
            except Exception as e:
                print("Error unloading thumbs and frames", e)
            finally:
                collect()
                print(f"GC  in: {perf_counter()-a:.2f}")
        def unload_static(gridsquare):
            gridsquare.canvas.itemconfig(gridsquare.canvas_image_id, image=None)
            gridsquare.canvas.image = None
            gridsquare.obj.guidata['img'] = None
        def unload_animated(gridsquare):
            self.animate.remove_animation(gridsquare, self.gui.square_colour)
            gridsquare.obj.index = 0
            gridsquare.obj.frames = []
            gridsquare.obj.lazy_loading = True
        new_thread = Thread(target=multithread, daemon=True)
        new_thread.start()
        #collect() # gc takes long. maybe we can tell it what to do? why is gc necessary even? something STILL pointing to the image? ###
        # see if we can have tkinter reference the images from imagefile context.

class Animate:
    "Animate class to keep track of and manage animations in grid"
    def __init__(self, square_colour):
        self.running = set() # Stores every frame going to be animated or animating.
        self.square_colour = square_colour
    def add_animation(self, obj):
        gridsquare = obj.guidata["frame"]
        if gridsquare in self.running:
            return
        self.running.add(gridsquare)
        self.start_animations(gridsquare)
    def remove_animation(self, gridsquare, square_colour):
        if gridsquare in self.running:
            try:
                gridsquare.obj.guidata["canvas"]["background"] = square_colour
                self.running.remove(gridsquare)
            except Exception as e:
                print(e)
    def start_animations(self, gridsquare):
        def lazy(gridsquare):
            i = gridsquare
            i.obj.guidata["canvas"]['background'] = "red"
            if i not in self.running: # Stop if not in "view" or in self.running
                return
            if not i.obj.frames: # No frames have been initialized. This handles the event when frames are cleared but obj gridsquare is in self.running.
                #print("Error, lazy called with no frames") # must be removed from self.running because we clear the frames if they try to be loaded while gridsqaure is not in displayedlist (shown)
                # This is because thread thinks the view being loaded away means it is still in view, so it is appended to self.running.
                # It then loses its frames, and stops here. We could try show=True show=false flag for imagefile and the loop checks that continuously. but eh.
                self.remove_animation(i, self.square_colour)
                return
            if not i.obj.lazy_loading and len(i.obj.frames) != i.obj.framecount: # All frames generated doesnt match expected (only webm, dead?)
                print("Error, frames generated doesnt match expected")
                self.remove_animation(i, self.square_colour)
                return
            if not i.obj.lazy_loading and len(i.obj.frames) == i.obj.framecount: # All frames ready. (second part only webm, dead)
                i.obj.guidata["canvas"]['background'] = "green"
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
                    self.running.remove(i)
                    print("Error in lazy:",)
        def loop(gridsquare):
            "Indefinite loop on a seperate thread until it just ends"
            if not gridsquare in self.running:
                return
            i = gridsquare
            
            if len(i.obj.frames) >= i.obj.index:
                i.canvas.itemconfig(i.canvas_image_id, image=i.obj.frames[i.obj.index]) #change the frame
                i.obj.index = (i.obj.index + 1) % i.obj.framecount
                i.canvas.after(i.obj.frametimes[i.obj.index], lambda: loop(i)) #run again.
        lazy(gridsquare) # Non threaded #lazy load dest lazy load...
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

if __name__ == '__main__':
    mainclass = SortImages()
