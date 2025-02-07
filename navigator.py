from math import ceil

from tkinter import ttk

class Navigator:
    #if focus on destviewer, use dest displayedlist for indexing. how to check... have variable that updates based on what is focused and check that for every action.
    "Presets"
    def __init__(self, fileManager):
        self.gui = fileManager.gui
        gui = self.gui
        self.gridmanager = gui.gridmanager
        self.fileManager = fileManager
        self.displayedlist = self.gridmanager.displayedlist
        style = ttk.Style()
        self.style = style
        style.configure("Theme_square1.TCheckbutton", background=gui.square_text_box_colour, foreground=gui.square_text_colour) # Theme for Square
        style.configure("Theme_square2.TCheckbutton", background=gui.square_text_box_selection_colour, foreground=gui.square_text_colour) # Theme for Square (selected)

        self.index = 0
        self.old = None # Last changed frame / Default PREVIOUS / Always current selection (for showing next upon moves)

        self.arrow_action = None
        self.arrow_action_reversed = None

        self.window_focused = "GRID"

    def select(self, new):
        "From a click event, removes highlight from previous frame, adds it to the clicked one"
        #if new == self.old and self.old: #show next scenario <- what? this breaks, and doesnt seem to have anything in common with show next.
        #    return #### test
        self.window_focused = "GRID"
        self.displayedlist = self.gridmanager.displayedlist
        if new == None:
            return
        if self.old:
            self.default(self.old)
        if new:
            self.selected(new)
            
            self.index = self.displayedlist.index(new) #updates index
            self.gui.displayimage(new.obj)
            self.old = new #updates old
                    
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
        if self.gui.current_view.get() == "Show Assigned" or self.gui.current_view.get() == "Show Moved":
            if hasattr(self.gui, "Image_frame"):
                # Assigned list is *displayed* in "last added"-manner. (by tkinter, so here we use [-1], as that is newest in list)
                self.selected(lista[-1])
                self.old = lista[-1]
                self.gui.displayimage(lista[-1].obj)
        else:
            if hasattr(self.gui, "Image_frame"):
                self.selected(lista[0])
                self.old = lista[0]
                self.gui.displayimage(lista[0].obj)

    def select_next(self, lista):
        "Called by setdestination, removes highlight from previous frame, adds it to the one entering index"
        if self.old: # default old
            self.default(self.old)
        if len(lista) == 0: # last image [0], len == 0.
            self.old = None
            return
        elif len(lista) == self.index: # last image assigned [-1].
            self.old = lista[self.index-1]
            self.index -= 1
        elif len(lista) > self.index: # new image enters index
            self.old = lista[self.index]
        self.selected(self.old)
        if self.gui.show_next.get():
            self.gui.displayimage(self.old.obj) ## omly display in viewer if show_next is on., otherwise allow this function to run.

    def bindhandler(self, event):
        #updownleftright = 38,40,37,39
        def scroll_up():
            columns = int(max(1, self.gui.imagegrid.winfo_width() / self.gui.actual_gridsquare_width))
            rows = ceil(len(lista) / columns)
            current_row = self.index // columns
            first_visible_row = round(self.gui.imagegrid.yview()[0] * rows)  # Index of the first visible item
            #print(f"In a row: {columns}, rows: {rows}, current_row: {current_row}, first visible row: {first_visible_row}, last visible row: {last_visible_row}")
            if first_visible_row > current_row: # Scroll up
                target_scroll = (first_visible_row-1) / rows
                self.gui.imagegrid.yview_moveto(target_scroll)
        def scroll_down():
            columns = int(max(1, self.gui.imagegrid.winfo_width() / self.gui.actual_gridsquare_width))
            rows = ceil(len(lista) / columns)
            current_row = self.index // columns
            first_visible_row = round(self.gui.imagegrid.yview()[0] * rows)  # Index of the first visible item
            last_visible_row = round(self.gui.imagegrid.yview()[1] * rows)  # Index of the last visible item
            if last_visible_row <= current_row: # Scroll down
                target_scroll = (first_visible_row+1) / rows
                self.gui.imagegrid.yview_moveto(target_scroll)
        def highlight_right():
            check_bound = self.index+1
            if check_bound >= len(self.displayedlist):
                return
            self.default(self.old)
            self.index = check_bound
            self.selected(self.displayedlist[self.index])
            self.old = self.displayedlist[self.index]
            scroll_down()
            if self.gui.show_next.get():
                self.gui.displayimage(self.old.obj)
        def highlight_left():
            check_bound = self.index-1
            if check_bound < 0:
                return
            self.index = check_bound
            self.default(self.old)
            self.selected(self.displayedlist[self.index])
            self.old = self.displayedlist[self.index]
            scroll_up()
            if self.gui.show_next.get():
                self.gui.displayimage(self.old.obj)
        def highlight_up():
            columns = int(max(1, self.gui.imagegrid.winfo_width() / self.gui.actual_gridsquare_width))
            check_upper_bound = self.index-columns
            if check_upper_bound < 0:
                return
            self.index = check_upper_bound
            self.default(self.old)
            self.selected(self.displayedlist[self.index])
            self.old = self.displayedlist[self.index]
            scroll_up()
            if self.gui.show_next.get():
                self.gui.displayimage(self.old.obj)
        def highlight_down():
            columns = int(max(1, self.gui.imagegrid.winfo_width() / self.gui.actual_gridsquare_width))
            check_lower_bound = self.index+columns
            if check_lower_bound > len(self.displayedlist)-1:
                return
            self.index = check_lower_bound
            self.default(self.old)
            self.selected(self.displayedlist[self.index])
            self.old = self.displayedlist[self.index]
            scroll_down()
            if self.gui.show_next.get():
                self.gui.displayimage(self.old.obj)
        def spacebar():
            self.gui.displayimage(self.old.obj)
        def enter():
            self.gui.displayimage(self.old.obj)

        if self.gui.focused_on_field:
            return
        if not self.arrow_action:
            self.arrow_action = {
                "Right": lambda: highlight_right(),
                "Left": lambda: highlight_left(),
                "Up": lambda: highlight_up(),
                "Down": lambda: highlight_down(),
                "space": lambda: spacebar(),
                "Return": lambda: enter()
            }
        if not self.arrow_action_reversed:
            self.arrow_action_reversed = {
                "Left": lambda: highlight_right(),
                "Right": lambda: highlight_left(),
                "Down": lambda: highlight_up(),
                "Up": lambda: highlight_down(),
                "space": lambda: spacebar(),
                "Return": lambda: enter()
            }

        

        if self.gui.current_view.get() == "Show Assigned":
            arrow_action = self.arrow_action_reversed
        else:
            arrow_action = self.arrow_action

        if self.window_focused == "DEST":
            lista = self.gui.destination_viewer.displayedlist
            self.displayedlist = self.gui.destination_viewer.displayedlist
            arrow_action = self.arrow_action_reversed
        else:
            self.displayedlist = self.gridmanager.displayedlist
            lista = self.gridmanager.displayedlist
        key = event.keysym
        try:
            arrow_action[key]()
        except:
            if lista:
                if self.gui.current_view.get() in ("Show Assigned", "Show Moved"):
                    gridsquare = lista[-1]
                else:
                    gridsquare = lista[0]
                self.select(gridsquare)

    def default(self, frame):
        "Reverts colour back to default"
        if not frame:
            return
        if frame.obj.dest != "":
            alt = frame.obj.dest_color
            exists = frame.obj.guidata.get("destframe", None)
            if exists:
                frame.configure(highlightcolor = alt,  highlightbackground = alt) # Trying to access destroyed destsquare? # If dest is closed, remove self.old if any frame was there.
                frame.canvas.configure(bg=alt, highlightcolor=alt, highlightbackground = alt)
                frame.c.configure(style="Theme_square1.TCheckbutton")
                frame.cf.configure(bg=self.gui.square_text_box_colour)
        else:
            frame.configure(highlightcolor = self.gui.square_default,  highlightbackground = self.gui.square_default)
            frame.canvas.configure(bg=self.gui.square_default, highlightcolor=self.gui.square_default, highlightbackground = self.gui.square_default)
            frame.c.configure(style="Theme_square1.TCheckbutton")
            frame.cf.configure(bg=self.gui.square_text_box_colour)
    def selected(self, frame):
        if frame:
            frame.configure(highlightbackground = self.gui.square_selected, highlightcolor = self.gui.square_selected)
            frame.canvas.configure(bg=self.gui.square_selected, highlightbackground = self.gui.square_selected, highlightcolor = self.gui.square_selected)
            frame.c.configure(style="Theme_square2.TCheckbutton")
            frame.cf.configure(bg=self.gui.square_text_box_selection_colour)
