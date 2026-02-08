from tkinter import Entry
from tkinter import ttk

import tkinter as tk
from tkinter import simpledialog
import os
from sorter import ImageViewer

class PrefilledInputDialog(simpledialog.Dialog):
    def __init__(self, parent, title, message, default_text=""):
        self.message = message
        self.default_text = default_text
        self.result = None
        super().__init__(parent, title)

    def body(self, master):
        # Extract filename and extension safely
        base_name = os.path.basename(self.default_text)
        if base_name.startswith(".") and "." not in base_name[1:]:
            name_part, ext_part = base_name, ""
        elif "." in base_name:
            name_part, ext_part = base_name.rsplit(".", 1)
            ext_part = "." + ext_part
        else:
            name_part, ext_part = base_name, ""

        tk.Label(master, text=self.message, justify="left", wraplength=300).pack(padx=10, pady=(10, 5))

        # Frame to hold entry + extension label
        frame = tk.Frame(master)
        frame.pack(padx=10, pady=(0, 10))

        # Entry for the name
        self.entry = tk.Entry(frame, width=30)
        self.entry.insert(0, name_part)
        self.entry.pack(side="left")

        # Label for the extension
        tk.Label(frame, text=ext_part, width=len(ext_part) + 1, anchor="w").pack(side="left")

        self.ext_part = ext_part
        return self.entry  # initial focus

    def apply(self):
        name = self.entry.get().strip()
        if not name:
            self.result = None
        else:
            self.result = name + self.ext_part

class Navigator:
    class Dummy:
        def __init__(self, widget, keysym, state):
            self.widget = widget
            self.keysym = keysym
            self.state = state
    def __init__(self, fileManager):
        " This module handles key-presses and mouse-clicks. It is responsible for turning on and off the colored frame around images if they are selected."
        "Also handles special events, such as changing views and select next"
        self.gui = fileManager.gui
        gui = self.gui
        self.imagegrid = gui.imagegrid
        self.fileManager = fileManager
        style = ttk.Style()
        self.style = style
        style.configure("Theme_square1.TCheckbutton", background=gui.d_theme["square_text_box_colour"], foreground=gui.d_theme["square_text_colour"]) # Theme for Square
        style.configure("Theme_square2.TCheckbutton", background=gui.d_theme["square_text_box_selection_colour"], foreground=gui.d_theme["square_text_colour"]) # Theme for Square (selected)
        
        self.toggle = False
        self.gui.bind_all("<Button-2>", self.middle_mouse_button)
        self.gui.bind_all("<MouseWheel>", self.scroll_imagegrid)
        self.index = 0

        self.window_focused = "GRID"

        self.actual_gridsquare_width = self.gui.thumbnailsize + self.gui.d_theme["gridsquare_padx"] + self.gui.d_theme["square_border_size"] + self.gui.d_theme["whole_box_size"]
        self.actual_gridsquare_height = self.gui.thumbnailsize + self.gui.d_theme["gridsquare_pady"] + self.gui.d_theme["square_border_size"] + self.gui.d_theme["whole_box_size"] + self.gui.d_theme["checkbox_height"]

        self.search_widget = ImageViewer(self) # needs current canvas and ?
    
    def middle_mouse_button(self, event):
        if event.state != 2: return
        setattr(self, "toggle", not self.toggle if event.widget.widgetName != "button" else self.toggle)
        #self.gui.folder_explorer.search_entry.focus()

    def scroll_imagegrid(self, event):
        if not self.toggle and hasattr(self.gui, "folder_explorer"):
            self.gui.folder_explorer.on_mouse_wheel(event)
            return

        caps_lock_off = event.state not in (2,)
        if caps_lock_off or event.widget.widgetName == "scrollbar": return
        if event.delta < 0:
            self.bindhandler(Navigator.Dummy("scroll", "Right", event.state))
        else:
            self.bindhandler(Navigator.Dummy("scroll", "Left", event.state))
    
    def open_file(self, frame, event):
        if event.state == 2:
            return
        obj = frame.obj
        #os.startfile(obj.path)
        import subprocess
        subprocess.Popen(r'explorer /select,"{}"'.format(os.path.abspath(obj.path)))

    def ask_prefilled_text(self, parent, title, message, default_text=""):
        dialog = PrefilledInputDialog(parent, title, message, default_text)
        return dialog.result
    
    def bindhandler(self, event):
        #print("registered:", event)
        def undo():
            # move last from assigned to unassigned if any.
            if self.fileManager.assigned and self.gui.current_view.get() in ("Unassigned",) :
                last = self.fileManager.assigned.pop()
                last.color = None
                last.dest = ""
                self.imagegrid.insert_first(last, last.pos)
                self.gui.displayimage(last)
        #updownleftright = 38,40,37,39
        def space(reverse=None):
            if self.gui.second_window_viewer: 
                self.gui.second_window_viewer.master.focus()
        def autosort():
            if not self.gui.prediction.get(): return
            imagegrid = self.imagegrid
            s = imagegrid.current_selection
            if s is not None and s < len(imagegrid.image_items):
                a = imagegrid.image_items[s].file.predicted_path
                if a:
                    print("Sent:", imagegrid.image_items[s].file.name[:20], "to", a)
                    c =  "#FFFFFF" #self.gui.folder_explorer.color_cache[self.old.obj.predicted_path]
                    dest = {"path": a, "color": c}
                    self.fileManager.setDestination(dest, caller="autosort")
        def rename():
            if not self.old: return
            title = "Rename Image"
            label = ""
            path = self.old.obj.path
            old_name = os.path.basename(path)

            while True:
                new_name = self.ask_prefilled_text(
                self.gui, title, label, default_text=old_name)
                if new_name:
                    new_path = os.path.join(os.path.dirname(path), new_name)
                    try:
                        os.rename(path, new_path)
                        self.old.obj.path = new_path
                        self.old.obj.name = os.path.basename(new_path)
                        self.fileManager.thumbs.gen_name(self.old.obj)
                        self.gui.displayimage(self.old.obj) # link with gui.
                        break
                    except Exception as e:
                        print("Rename errors:", e)
                        label = f"{new_name} already exists in {os.path.basename(os.path.dirname(path))}"
                        old_name = new_name
                else:
                    break

            pass # update square name (obj.gridsquare, obj.destsquare...), update obj.filename, truncated name...
        def trash():
            pass # rem from display, select next, add to trashed list.
            # you can still assign from trashed list, where it will behave like unsorted...
        if isinstance(event.widget, Entry):
            return

        reverse = True if self.gui.current_view.get() == "Assigned" else False

        if event.state in (4,6) and event.keysym.lower() == "z":
            undo()
        elif event.keysym == "Return":
            #if self.gui.current_view.get() == "Predictions":
            autosort()
        elif event.keysym == "F2":
            rename()
        elif event.keysym == "Delete":
            trash()
        elif event.keysym in ("Left", "Right", "Down", "Up"):
            if ((self.gui.second_window_viewer and hasattr(self.gui.second_window_viewer, "app2") and self.gui.second_window_viewer.app2.search_active) or (self.gui.Image_frame and hasattr(self.gui.Image_frame, "app2") and self.gui.Image_frame.app2.search_active)):
                pass
            else:
                if event.state != 262147 and self.gui.folder_explorer.scroll_enabled and event.keysym in ("Up", "Down"):
                    self.gui.folder_explorer.nav(event.keysym)
                else:
                    if "toplevel" in event.widget._w and not (hasattr(self.gui.second_window_viewer, "master") and event.widget == self.gui.second_window_viewer.master):
                        self.gui.folder_explorer.destw.navigate(event.keysym)
                    else:
                        self.gui.imagegrid.navigate(event.keysym)
                    if self.gui.show_next.get():
                        if "toplevel" in event.widget._w and not (hasattr(self.gui.second_window_viewer, "master") and event.widget == self.gui.second_window_viewer.master):
                            self.gui.displayimage(self.gui.folder_explorer.destw.image_items[self.gui.folder_explorer.destw.current_selection].file)
                        else:
                            self.gui.displayimage(self.imagegrid.image_items[self.imagegrid.current_selection].file)
        else:
            action = {"space": space}
            action[event.keysym](reverse)
            self.gui.imagegrid.update()
