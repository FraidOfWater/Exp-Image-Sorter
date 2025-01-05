from math import ceil

from tkinter import ttk

class Navigator:
    #if focus on destviewer, use dest displayedlist for indexing. how to check... have variable that updates based on what is focused and check that for every action.
    "Presets"
    def __init__(self, fileManager):
        self.gui = fileManager.gui
        gui = self.gui
        self.fileManager = fileManager
        self.displayedlist = self.fileManager.gui.gridmanager.displayedlist
        style = ttk.Style()
        self.style = style
        style.configure("Theme_square.TCheckbutton", background=gui.square_text_box_colour, foreground=gui.square_text_colour) # Theme for Square
        style.configure("Theme_square2.TCheckbutton", background=gui.square_text_box_selection_colour, foreground=gui.square_text_colour) # Theme for Square (selected)
        style.configure("Theme_square3.TCheckbutton", background=gui.square_text_box_locked_colour, foreground=gui.square_text_colour) # Theme for Square (locked)

        self.index = 0
        self.old = None # Last changed frame / Default PREVIOUS / Always current selection (for showing next upon moves)

        self.arrow_action = None
        self.arrow_action_reversed = None

        self.window_focused = "GRID"

    def select(self, new):
        "From a click event, removes highlight from previous frame, adds it to the clicked one"
        #if new == self.old and self.old: #show next scenario <- what? this breaks, and doesnt seem to have anything in common with show next.
        #    return #### test
        if self.old:
            self.default(self.old)
        self.selected(new)
        self.old = new #updates old
        self.index = self.displayedlist.index(new) #updates index
        self.window_focused = "GRID"
        self.gui.displayimage(new.obj)
    def dest_select(self, new):
        "From a click event, removes highlight from previous frame, adds it to the clicked one"
        if new == self.old and self.old: #show next scenario
            return
        if self.old:
            self.default(self.old)
        self.selected(new)
        self.old = new #updates old
        self.index = self.gui.destination_viewer.displayedlist.index(new) #updates index
        self.window_focused = "DEST"
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
            if self.gui.displayimage:
                # Assigned list is *displayed* in "last added"-manner. (by tkinter, so here we use [-1], as that is newest in list)
                self.selected(lista[-1])
                self.old = lista[-1]
                self.gui.displayimage(lista[-1].obj)
        else:
            if self.gui.displayimage:
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
        self.gui.displayimage(self.old.obj)

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
            if check_bound >= len(lista):
                return
            self.default(self.old)
            self.index = check_bound
            self.selected(lista[self.index])
            self.old = lista[self.index]
            scroll_down()
            self.gui.displayimage(self.old.obj)
        def highlight_left():
            check_bound = self.index-1
            if check_bound < 0:
                return
            self.index = check_bound
            self.default(self.old)
            self.selected(lista[self.index])
            self.old = lista[self.index]
            scroll_up()
            self.gui.displayimage(self.old.obj)
        def highlight_up():
            columns = int(max(1, self.gui.imagegrid.winfo_width() / self.gui.actual_gridsquare_width))
            check_upper_bound = self.index-columns
            if check_upper_bound < 0:
                return
            self.index = check_upper_bound
            self.default(self.old)
            self.selected(lista[self.index])
            self.old = lista[self.index]
            scroll_up()
            self.gui.displayimage(self.old.obj)
        def highlight_down():
            columns = int(max(1, self.gui.imagegrid.winfo_width() / self.gui.actual_gridsquare_width))
            check_lower_bound = self.index+columns
            if check_lower_bound > len(lista)-1:
                return
            self.index = check_lower_bound
            self.default(self.old)
            self.selected(lista[self.index])
            self.old = lista[self.index]
            scroll_down()
            self.gui.displayimage(self.old.obj)
        lista = self.displayedlist
        if self.window_focused == "DEST":
            ### make logic to scroll the correct window...
            #lista = self.gui.destination_viewer.displayedlist
            pass
        if not self.arrow_action:
            self.arrow_action = {
                "Right": lambda: highlight_right(),
                "Left": lambda: highlight_left(),
                "Up": lambda: highlight_up(),
                "Down": lambda: highlight_down()
            }
        if not self.arrow_action_reversed:
            self.arrow_action_reversed = {
                "Left": lambda: highlight_right(),
                "Right": lambda: highlight_left(),
                "Down": lambda: highlight_up(),
                "Up": lambda: highlight_down()
            }
        if self.gui.current_view.get() == "Show Assigned":
            arrow_action = self.arrow_action_reversed
        else:
            arrow_action = self.arrow_action

        if self.old:
            key = event.keysym
            arrow_action[key]()
        else:
            print("investigate")
            if lista:
                if self.gui.current_view.get() in ("Show Assigned", "Show Moved"):
                    gridsquare = lista[-1]
                else:
                    gridsquare = lista[0]
                self.select(gridsquare)

    def default(self, frame):
        "Reverts colour back to default"
        if frame.obj.dest != "":
            alt = frame.obj.dest_color
            frame.configure(highlightcolor = alt,  highlightbackground = alt) # Trying to access destroyed destsquare? # If dest is closed, remove self.old if any frame was there.
            frame.canvas.configure(bg=alt, highlightcolor=alt, highlightbackground = alt)
            frame.c.configure(style="Theme_square.TCheckbutton")
            frame.cf.configure(bg=self.gui.square_text_box_colour)
        else:
            frame.configure(highlightcolor = self.gui.imageborder_default_colour,  highlightbackground = self.gui.imageborder_default_colour)
            frame.canvas.configure(bg=self.gui.imagebox_default_colour, highlightcolor=self.gui.imageborder_default_colour, highlightbackground = self.gui.imageborder_default_colour)
            frame.c.configure(style="Theme_square.TCheckbutton")
            frame.cf.configure(bg=self.gui.square_text_box_colour)
    def selected(self, frame):
        frame.configure(highlightbackground = self.gui.imageborder_selected_colour, highlightcolor = self.gui.imageborder_selected_colour)
        frame.canvas.configure(bg=self.gui.imagebox_selection_colour, highlightbackground = self.gui.imageborder_selected_colour, highlightcolor = self.gui.imageborder_selected_colour)
        frame.c.configure(style="Theme_square2.TCheckbutton")
        frame.cf.configure(bg=self.gui.square_text_box_selection_colour)
    def locked(self, frame):
        frame.configure(highlightbackground = self.gui.imageborder_locked_colour, highlightcolor = self.gui.imageborder_locked_colour)
        frame.canvas.configure(bg=self.gui.imagebox_locked_colour, highlightbackground = self.gui.imageborder_locked_colour, highlightcolor = self.gui.imageborder_locked_colour)
        frame.c.configure(style="Theme_square3.TCheckbutton")
        frame.cf.configure(bg=self.gui.square_text_box_locked_colour)
