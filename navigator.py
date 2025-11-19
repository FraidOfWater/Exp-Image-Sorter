from tkinter import Entry
from tkinter import ttk

import tkinter as tk
from tkinter import simpledialog
import os
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

    #if focus on destviewer, use dest displayedlist for indexing. how to check... have variable that updates based on what is focused and check that for every action.
    "Presets"
    def __init__(self, fileManager):
        " This module handles key-presses and mouse-clicks. It is responsible for turning on and off the colored frame around images if they are selected."
        "Also handles special events, such as changing views and select next"
        self.gui = fileManager.gui
        gui = self.gui
        self.gridmanager = gui.gridmanager
        self.fileManager = fileManager
        self.displayedlist = self.gridmanager.displayedlist
        style = ttk.Style()
        self.style = style
        style.configure("Theme_square1.TCheckbutton", background=gui.square_text_box_colour, foreground=gui.square_text_colour) # Theme for Square
        style.configure("Theme_square2.TCheckbutton", background=gui.square_text_box_selection_colour, foreground=gui.square_text_colour) # Theme for Square (selected)
        
        self.toggle = False
        self.gui.bind_all("<Button-2>", self.middle_mouse_button)
        self.gui.bind_all("<MouseWheel>", self.scroll_imagegrid)
        self.index = 0
        self.old = None # Last changed frame / Default PREVIOUS / Always current selection (for showing next upon moves)

        self.window_focused = "GRID"

        self.actual_gridsquare_width = self.gui.thumbnailsize + self.gui.gridsquare_padx + self.gui.square_border_size + self.gui.whole_box_size
        self.actual_gridsquare_height = self.gui.thumbnailsize + self.gui.gridsquare_pady + self.gui.square_border_size + self.gui.whole_box_size + self.gui.checkbox_height
    
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

    def select(self, new, event):
        if event.state == 2:
            return
        "From a click event, removes highlight from previous frame, adds it to the clicked one"
        #if new == self.old and self.old: #show next scenario <- what? this breaks, and doesnt seem to have anything in common with show next.
        #    return #### test
        self.window_focused = "GRID"
        self.displayedlist = self.gridmanager.displayedlist
        if new == None: return
        if self.old:
            self.default(self.old)
        if new:
            self.selected(new)
            self.index = self.displayedlist.index(new) #updates index
            self.gui.displayimage(new.obj)
            self.old = new #updates old
        self.gui.update()
    
    def open_file(self, frame, event):
        if event.state == 2:
            return
        obj = frame.obj
        #os.startfile(obj.path)
        import subprocess
        subprocess.Popen(r'explorer /select,"{}"'.format(os.path.abspath(obj.path)))

    def first(self):
        self.window_focused = "GRID"
        self.displayedlist = self.gridmanager.displayedlist
        if not self.displayedlist: return
        self.index = 0
        self.old = self.displayedlist[0]
        self.selected(self.old)
        self.gui.displayimage(self.old.obj)

    def dest_select(self, new):
        "From a click event, removes highlight from previous frame, adds it to the clicked one"
        self.window_focused = "DEST"
        self.displayedlist = self.gridmanager.displayedlist
        if new == self.old and self.old: #show next scenario
            return
        if self.old:
            self.default(self.old)
        self.selected(new)
        self.old = new #updates old
        
        self.index = self.gui.destination_viewer.displayedlist.index(new) #updates index
        
        self.gui.displayimage(new.obj)

    def view_change(self):
        "When view is changed, remove highlight from previous frame, adds it to the first frame"
        lista = self.displayedlist
        if self.old:
            self.default(self.old)
            self.old = None
        if not self.gui.show_next.get() or len(lista) == 0:
            return
        if self.gui.current_view.get() == "Assigned" or self.gui.current_view.get() == "Moved":
            if self.gui.Image_frame != None or self.gui.second_window_viewer != None:
                # Assigned list is *displayed* in "last added"-manner. (by tkinter, so here we use [-1], as that is newest in list)
                self.selected(lista[-1])
                self.old = lista[-1]
                self.gui.displayimage(lista[-1].obj)
        else:
            if self.gui.Image_frame != None or self.gui.second_window_viewer != None:
                self.selected(lista[0])
                self.old = lista[0]
                self.gui.displayimage(lista[0].obj)

    def select_next(self, lista):
        "Called by setdestination, removes highlight from previous frame, adds it to the one entering index"

        if self.old: self.default(self.old)
        else: return

        self.old = None
        if len(lista) == 0: return # no images left

        if self.window_focused == "DEST":
            if  self.index >= len(lista):
                self.old = lista[-1]
            elif self.index == 0:
                self.old = lista[self.index]
            else:
                self.old = lista[self.index-1]

        else:
            if self.index < len(lista): # in limits
                self.old = lista[self.index]
        
        if self.old:
            self.selected(self.old)
            if self.gui.show_next.get() and (self.gui.Image_frame or self.gui.second_window_viewer):
                self.gui.displayimage(self.old.obj)

    def ask_prefilled_text(self, parent, title, message, default_text=""):
        dialog = PrefilledInputDialog(parent, title, message, default_text)
        return dialog.result
    
    def bindhandler(self, event):
        #print("registered:", event)
        def advance():
            if self.gui.show_next.get() and old != self.old and ((self.gui.Image_frame != None and self.gui.Image_frame.filename) or self.gui.second_window_viewer != None):
                self.gui.displayimage(self.old.obj)
        def undo():
            # move last from assigned to unassigned if any.
            if self.gridmanager.assigned and self.gui.current_view.get() in ("Unassigned",) :
                index, listindex, last = self.gridmanager.undo.pop()
                self.gridmanager.assigned.remove(last)
                self.gridmanager.unassigned.insert(listindex, last)
                #self.displayedlist.insert(listindex, last)
                last.obj.dest = ""
                self.gridmanager.add_squares([(last)], insert=(index, listindex))
                self.default(self.old)
                self.selected(self.displayedlist[listindex])
                self.old = self.displayedlist[listindex]
                if self.gui.show_next.get():
                    if self.old:
                        self.gui.displayimage(self.old.obj)
                self.gui.update()
        #updownleftright = 38,40,37,39
        def scroll_up(reverse=None):
            if self.window_focused == "GRID":
                target_grid = self.gui.imagegrid
                columns = int(max(1, (target_grid.winfo_width()+2) / self.actual_gridsquare_width))
            elif self.window_focused == "DEST":
                target_grid = self.gui.destination_viewer.destgrid
                columns = int(max(1, (target_grid.winfo_width()+1) / self.actual_gridsquare_width))

            rows = int((len(self.displayedlist) + columns - 1) / columns)
            if reverse:
                current_row = (len(self.displayedlist)-self.index-1) // columns
            else:
                current_row = self.index // columns
            first_visible_row = round(target_grid.yview()[0] * rows)  # Index of the first visible item
            #print(f"In a row: {columns}, rows: {rows}, current_row: {current_row}, first visible row: {first_visible_row}, last visible row: {last_visible_row}")
            if first_visible_row > current_row: # Scroll up
                target_scroll = (first_visible_row-1) / rows
                target_grid.yview_moveto(target_scroll)
        def scroll_down(reverse=None):
            if self.window_focused == "GRID":
                target_grid = self.gui.imagegrid
                columns = int(max(1, (target_grid.winfo_width()+2) / self.actual_gridsquare_width))
            elif self.window_focused == "DEST":
                target_grid = self.gui.destination_viewer.destgrid
                columns = int(max(1, (target_grid.winfo_width()+1) / self.actual_gridsquare_width))
                
            rows = int((len(self.displayedlist) + columns - 1) / columns)
            if reverse:
                current_row = (len(self.displayedlist)-self.index-1) // columns
            else:
                current_row = self.index // columns
            first_visible_row = round(target_grid.yview()[0] * rows)  # Index of the first visible item
            last_visible_row = round(target_grid.yview()[1] * rows)  # Index of the last visible item
            if last_visible_row <= current_row: # Scroll down
                target_scroll = (first_visible_row+1) / rows
                target_grid.yview_moveto(target_scroll)
        def highlight_right(reverse=None):
            check_bound = self.index+1
            if check_bound >= len(self.displayedlist):
                return
            self.index = check_bound
            self.default(self.old) 
            self.selected(self.displayedlist[self.index])
            self.old = self.displayedlist[self.index]
            if reverse: scroll_up(reverse=True)
            else: scroll_down()
            advance()
        def highlight_left(reverse=None):
            check_bound = self.index-1
            if check_bound < 0:
                return
            self.index = check_bound
            self.default(self.old)
            self.selected(self.displayedlist[self.index])
            self.old = self.displayedlist[self.index]
            if reverse: scroll_down(reverse=True)
            else: scroll_up()
            advance()
        def highlight_up(reverse=None):
            if ((self.gui.second_window_viewer and hasattr(self.gui.second_window_viewer, "app2") and self.gui.second_window_viewer.app2.search_active) or (self.gui.Image_frame and hasattr(self.gui.Image_frame, "app2") and self.gui.Image_frame.app2.search_active)): return
            if self.window_focused == "GRID":
                columns = int(max(1, (self.gui.imagegrid.winfo_width()+2) / self.actual_gridsquare_width))
            elif self.window_focused == "DEST":
                columns = int(max(1, (self.gui.destination_viewer.destgrid.winfo_width()+1) / self.actual_gridsquare_width))

            check_upper_bound = self.index-columns
            if check_upper_bound < 0:
                return
            self.index = check_upper_bound
            self.default(self.old)
            self.selected(self.displayedlist[self.index])
            self.old = self.displayedlist[self.index]
            if reverse: scroll_down(reverse=True)
            else: scroll_up()
            advance()
        def highlight_down(reverse=None):
            if ((self.gui.second_window_viewer and hasattr(self.gui.second_window_viewer, "app2") and self.gui.second_window_viewer.app2.search_active) or (self.gui.Image_frame and hasattr(self.gui.Image_frame, "app2") and self.gui.Image_frame.app2.search_active)): return
            if self.window_focused == "GRID":
                columns = int(max(1, (self.gui.imagegrid.winfo_width()+2) / self.actual_gridsquare_width))
            elif self.window_focused == "DEST":
                columns = int(max(1, (self.gui.destination_viewer.destgrid.winfo_width()+1) / self.actual_gridsquare_width))

            check_lower_bound = self.index+columns
            if check_lower_bound > len(self.displayedlist)-1:
                return
            self.index = check_lower_bound
            self.default(self.old)
            self.selected(self.displayedlist[self.index])
            self.old = self.displayedlist[self.index]
            if reverse: scroll_up(reverse=True)
            else: scroll_down()
            advance()
        def space(reverse=None):
            if self.gui.second_window_viewer: 
                self.gui.second_window_viewer.master.focus()
        def autosort():
            if self.old:
                """if self.old.obj != self.gui.displayed_obj:
                    self.gui.displayimage(self.old.obj)"""
                
                if self.old.obj.predicted_path:
                    print("Sent:", self.old.obj.name[:20], "to", self.old.obj.predicted_path)
                    c =  "#FFFFFF" #self.gui.folder_explorer.color_cache[self.old.obj.predicted_path]
                    dest = {"path": self.old.obj.predicted_path, "color": c}
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

        reverse = True if self.gui.current_view.get() == "Assigned" or self.window_focused == "DEST" else False
        self.displayedlist = self.gui.destination_viewer.displayedlist if self.window_focused == "DEST" else self.gridmanager.displayedlist

        if event.state == 4 and event.keysym in ("z", "Z"):
            undo()
        elif event.keysym == "Return":
            #if self.gui.current_view.get() == "Predictions":
            autosort()
        elif event.keysym == "F2":
            rename()
        elif event.keysym == "Delete":
            trash()
            """elif event.keysym == "Escape":
                if self.gui.second_window_viewer:
                    self.gui.displayed_obj = None
                    self.gui.second_window_viewer.window_close()
                if self.gui.Image_frame: self.gui.Image_frame.filename = None"""
        else:
            action = {"Left": highlight_right,
                    "Right": highlight_left,
                    "Down": highlight_up,
                    "Up": highlight_down,
                    "space": space
                } if reverse else {
                    "Left": highlight_left,
                    "Right": highlight_right,
                    "Down": highlight_down,
                    "Up": highlight_up,
                    "space": space
                }
            old = self.old
            action[event.keysym](reverse)
            self.gui.imagegrid.update()
    def default(self, frame):
        "Reverts colour back to default"
        if not frame:
            return
        
        f_color = frame.obj.dest_color if frame.obj.dest != "" else self.gui.square_default
        f_color = frame.obj.color if self.gui.prediction.get() else f_color
        try:
            frame.configure(highlightcolor = f_color,  highlightbackground = f_color) # Trying to access destroyed destsquare? # If dest is closed, remove self.old if any frame was there.
            frame.canvas.configure(bg=f_color, highlightcolor=f_color, highlightbackground = f_color)
            frame.c.configure(style="Theme_square1.TCheckbutton")
            frame.cf.configure(bg=self.gui.square_text_box_colour)
        except:
            pass
    def selected(self, frame):
        if not frame:
            return

        frame.configure(highlightbackground = self.gui.square_selected, highlightcolor = self.gui.square_selected)
        frame.canvas.configure(bg=self.gui.square_selected, highlightbackground = self.gui.square_selected, highlightcolor = self.gui.square_selected)
        frame.c.configure(style="Theme_square2.TCheckbutton")
        frame.cf.configure(bg=self.gui.square_text_box_selection_colour)
