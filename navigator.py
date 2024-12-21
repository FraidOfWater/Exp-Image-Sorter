from math import floor
from time import time
from tkinter import ttk

#Highlight_frame
#click on frame, highlights it -> Get frame data upon click
# move over by keys, highlights it ->Get frame data by moving up and down in the list. (from array). Must keep index in memory. (default 0)
# press setdest and the next in line is highlighted. -> Lookup current index of the array and highlight it.



class Navigator:
    "Presets"
    def __init__(self, fileManager, gui):
        self.gui = gui
        self.fileManager = fileManager
        style = ttk.Style()
        self.style = style
        style.configure("Theme_square.TCheckbutton", background=gui.square_text_box_colour, foreground=gui.square_text_colour) # Theme for Square
        style.configure("Theme_square2.TCheckbutton", background=gui.square_text_box_selection_colour, foreground=gui.square_text_colour) # Theme for Square (selected)
        style.configure("Theme_square3.TCheckbutton", background=gui.square_text_box_locked_colour, foreground=gui.square_text_colour) # Theme for Square (locked)

        self.index = 0
        self.old = None # Last changed frame / Default PREVIOUS / Always current selection (for showing next upon moves)
        self.dest_keys_pressed = False

    def highlight_click(self, new, lista):
        "From a click event, changes old colour to default, then changes new colour to activated"
        if new == self.old:
            return
        if self.old:
            self.default(self.old)
        self.selected(new)
        self.old = new #updates old
        self.index = lista.index(new) #updates index
        
    def view_change(self, lista):
        "Default old and select first frame upon changing views"
        # Some lists are displayed in a different manner
        # Unassigned/animated list is displayed as sorted
        # Assigned/move list is displayed backwards (newest moved)
        self.default(self.old)
        if self.gui.show_assigned.get() or self.gui.show_moved.get():
            self.selected(lista[-1])
            self.gui.displayimage(lista[-1])
        else:
            self.selected(lista[0])
            self.gui.displayimage(lista[0])

    def select_next(self, lista):
        "Called by setdestination, just selects the current index again"
        if self.old: # default old
            self.default(self.old)
        if len(lista) > self.index: # select image in OLD index.
            self.old = lista[self.index]
            self.selected(self.old)
            #index doesnt change
        elif len(lista)-1 > self.index and len(lista) != 0: # if index-1 exists (means we are at the end of the list and trying to "next", we go backwards)
            self.old = lista[self.index-1]
            self.selected(self.old)
            self.index -= 1
        else: # last pic,
            return
        self.gui.displayimage(self.old)

    #updownleftright = 38,40,37,39
    def highlight_right(self, lista):
        self.default(self.old)
        self.index += 1
        self.selected(lista[self.index])
        self.old = lista[self.index]
    def highlight_left(self, lista):
        self.default(self.old)
        self.index -= 1
        self.selected(lista[self.index])
        self.old = lista[self.index]
    def highlight_up(self, lista, pics_per_row):
        self.items_per_row = int(max(1, self.gui.imagegrid.winfo_width() / self.gui.actual_gridsquare_width))
        self.items_per_rowy = int(max(1, self.gui.imagegrid.winfo_height() / self.gui.actual_gridsquare_height))
        self.last_row = max(0,floor((self.index) / self.items_per_row))
        self.list_length = len(self.gui.displayedlist)
        self.current_row = max(0,floor((self.index) / self.items_per_row))
        self.total_rows = self.list_length / self.items_per_row

        # Calculate the index for the first and last visible items in the current bounding box
        self.first_visible_index = self.gui.imagegrid.yview()[0] * self.total_rows  # Index of the first visible item
        self.last_visible_index = self.gui.imagegrid.yview()[1] * self.total_rows  # Index of the last visible item
        if self.gui.page_mode:
            
            if self.last_row < self.current_row:  # Down (S, Down)
                if self.current_row >= self.list_length-self.items_per_rowy:
                    self.gui.imagegrid.yview_moveto(1)
                    return
                if self.current_row > floor(self.last_visible_index):  # If we're at the bottom of the visible area
                    target_scroll = (self.current_row-1) / self.total_rows
                    self.gui.imagegrid.yview_moveto(target_scroll)
            return
        else:
            if self.last_row < self.current_row:
                if self.current_row == 1: #
                    self.gui.imagegrid.yview_moveto(0)
                    return

                if self.current_row < floor(self.first_visible_index)+1:
                    #self.imagegrid.yview_scroll(-1, "units")
                    target_scroll = (self.current_row) / self.total_rows
                    self.gui.imagegrid.yview_moveto(target_scroll)
                return
        self.default(self.old)
        self.index = self.index+pics_per_row
        self.selected(lista[self.index])
    def highlight_down(self, lista, pics_per_row):
        self.items_per_row = int(max(1, self.gui.imagegrid.winfo_width() / self.gui.actual_gridsquare_width))
        self.items_per_rowy = int(max(1, self.gui.imagegrid.winfo_height() / self.gui.actual_gridsquare_height))
        self.last_row = max(0,floor((self.index) / self.items_per_row))
        self.list_length = len(self.gui.displayedlist)
        self.current_row = max(0,floor((self.index) / self.items_per_row))
        self.total_rows = self.list_length / self.items_per_row

        # Calculate the index for the first and last visible items in the current bounding box
        self.first_visible_index = self.gui.imagegrid.yview()[0] * self.total_rows  # Index of the first visible item
        self.last_visible_index = self.gui.imagegrid.yview()[1] * self.total_rows  # Index of the last visible item
        if self.gui.page_mode:
            if self.last_row < self.current_row:
                if self.current_row >= self.list_length-self.items_per_rowy:
                    self.gui.imagegrid.yview_moveto(1)
                    return

                if self.current_row > floor(self.last_visible_index):
                    target_scroll = (self.current_row-self.items_per_rowy) / self.total_rows
                    self.gui.imagegrid.yview_moveto(target_scroll)
            return
        else:
            if self.last_row < self.current_row or self.current_row == 0:  # Up (W, Up)
                if self.current_row == 1: #
                    self.gu.imagegrid.yview_moveto(0)
                    return

                if self.current_row < floor(self.first_visible_index):  # If we're at the top of the visible area
                    target_scroll = (self.current_row-self.items_per_rowy+1) / self.total_rows
                    self.gui.imagegrid.yview_moveto(target_scroll)
        self.default(self.old)
        self.index = self.index-pics_per_row
        self.selected(lista[self.index])

    def default(self, frame):
        "Reverts colour back to default"
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
