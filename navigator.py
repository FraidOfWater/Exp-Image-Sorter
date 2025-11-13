from tkinter import Entry
from tkinter import ttk
class Navigator:
    #if focus on destviewer, use dest displayedlist for indexing. how to check... have variable that updates based on what is focused and check that for every action.
    "Presets"
    def __init__(self, fileManager):
        " This module handles key-presses and mouse-clicks. It is responsible for turning on and off the colored frame around images if they are selected."
        "Also handles special events, such as changing views and select next"
        self.gui = fileManager.gui
        gui = self.gui
        self.imagegrid = gui.imagegrid
        self.gridmanager = gui.gridmanager
        self.fileManager = fileManager
        self.displayedlist = self.imagegrid.image_items
        style = ttk.Style()
        self.style = style

        self.index = 0
        self.old = None # Last changed frame / Default PREVIOUS / Always current selection (for showing next upon moves)
        self.pointers = tuple()

        self.arrow_action = None
        self.arrow_action_reversed = None

        self.window_focused = "GRID"

        self.actual_gridsquare_width = self.gui.thumbnailsize + self.gui.square_padx
        self.actual_gridsquare_height = self.gui.thumbnailsize + self.gui.square_pady + self.gui.textbox_size

    def select(self, new):
        "From a click event, removes highlight from previous frame, adds it to the clicked one"
        #if new == self.old and self.old: #show next scenario <- what? this breaks, and doesnt seem to have anything in common with show next.
        #    return #### test
        self.window_focused = "GRID"
        self.displayedlist = self.imagegrid.image_items
        if new == None: return
        if self.old:
            self.default(self.old)
        if new:
            self.selected(new)
            self.index = self.displayedlist.index(new.frame) #updates index
            self.gui.displayimage(new)
            self.old = new #updates old
        self.gui.update()
                    
    def dest_select(self, new):
        "From a click event, removes highlight from previous frame, adds it to the clicked one"
        self.window_focused = "DEST"
        self.displayedlist = self.imagegrid.image_items
        if new == self.old and self.old: #show next scenario
            return
        if self.old:
            self.default(self.old)
        self.selected(new)
        self.old = new #updates old
        
        self.index = self.gui.destination_viewer.displayedlist.index(new) #updates index
        
        self.gui.displayimage(new.file)

    def view_change(self):
        "When view is changed, remove highlight from previous frame, adds it to the first frame"
        lista = self.displayedlist
        if self.old:
            self.default(self.old)
            self.old = None ###
        if not self.gui.show_next.get() or len(lista) == 0:
            return
        if self.gui.current_view.get() == "Show Assigned" or self.gui.current_view.get() == "Show Moved":
            if self.gui.Image_frame != None or self.gui.Image_frame1 != None:
                # Assigned list is *displayed* in "last added"-manner. (by tkinter, so here we use [-1], as that is newest in list)
                self.selected(lista[-1].file)
                self.old = lista[-1].file
                self.gui.displayimage(lista[-1].file)
        else:
            if self.gui.Image_frame != None or self.gui.Image_frame1 != None:
                self.selected(lista[0].file)
                self.old = lista[0].file
                self.gui.displayimage(lista[0].file)

    def select_next(self, lista):
        "Called by setdestination, removes highlight from previous frame, adds it to the one entering index"

        if self.old == lista[self.index].file: return
        if self.old: self.default(self.old)
        else: return
        if self.gui.Image_frame == None and self.gui.Image_frame1 == None: return

        self.old = None
        if len(lista) == 0: return # no images left
        
        if self.index < len(lista): # in limits
            self.old = lista[self.index].file
        
        self.selected(self.old)
        self.gui.imagegrid._update_scrollregion()
        if self.gui.show_next.get():
            self.gui.displayimage(self.old)

    def bindhandler(self, event):
        #updownleftright = 38,40,37,39
        def scroll_up(reverse=None):
            if self.window_focused == "GRID":
                target_grid = self.gui.imagegrid.canvas
                columns = self.gui.imagegrid.cols
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
                target_grid = self.gui.imagegrid.canvas
                columns = self.gui.imagegrid.cols
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
            self.selected(self.displayedlist[self.index].file)
            self.old = self.displayedlist[self.index].file
            if reverse: scroll_up(reverse=True)
            else: scroll_down()
        def highlight_left(reverse=None):
            check_bound = self.index-1
            if check_bound < 0:
                return
            self.index = check_bound
            self.default(self.old)
            self.selected(self.displayedlist[self.index].file)
            self.old = self.displayedlist[self.index].file
            if reverse: scroll_down(reverse=True)
            else: scroll_up()
        def highlight_up(reverse=None):
            # consider also destgrid bounds for this to function on destgrid.
            if self.window_focused == "GRID":
                columns = self.gui.imagegrid.cols
            elif self.window_focused == "DEST":
                columns = int(max(1, (self.gui.destination_viewer.destgrid.winfo_width()+1) / self.actual_gridsquare_width))

            check_upper_bound = self.index-columns
            if check_upper_bound < 0:
                return
            self.index = check_upper_bound
            self.default(self.old)
            self.selected(self.displayedlist[self.index].file)
            self.old = self.displayedlist[self.index].file
            if reverse: scroll_down(reverse=True)
            else: scroll_up()
        def highlight_down(reverse=None):
            if self.window_focused == "GRID":
                columns = self.gui.imagegrid.cols
            elif self.window_focused == "DEST":
                columns = int(max(1, (self.gui.destination_viewer.destgrid.winfo_width()+1) / self.actual_gridsquare_width))

            check_lower_bound = self.index+columns
            if check_lower_bound > len(self.displayedlist)-1:
                return
            self.index = check_lower_bound
            self.default(self.old)
            self.selected(self.displayedlist[self.index].file)
            self.old = self.displayedlist[self.index].file
            if reverse: scroll_up(reverse=True)
            else: scroll_down()
        def spacebar():
            self.gui.displayimage(self.old)
        def enter():
            self.gui.displayimage(self.old)

        if isinstance(event.widget, Entry):
            return

        if not self.arrow_action:
            self.arrow_action = {
                "Right": highlight_right,
                "Left": highlight_left,
                "Up": highlight_up,
                "Down": highlight_down,
                "space": spacebar,
                "Return": enter
            }
        if not self.arrow_action_reversed:
            self.arrow_action_reversed = {
                "Left": lambda: highlight_right(reverse=True),
                "Right": lambda: highlight_left(reverse=True),
                "Down": lambda: highlight_up(reverse=True),
                "Up": lambda: highlight_down(reverse=True),
                "space": spacebar,
                "Return": enter
            }

        if self.gui.current_view.get() == "Show Assigned":
            arrow_action = self.arrow_action_reversed
        else:
            arrow_action = self.arrow_action

        if self.window_focused == "DEST":
            self.displayedlist = self.gui.destination_viewer.displayedlist
            arrow_action = self.arrow_action_reversed
        else:
            self.displayedlist = self.imagegrid.image_items
        
        old = self.old
        key = event.keysym
        arrow_action[key]()
        #self.gui.imagegridframe.update()
        if old != self.old and (self.gui.Image_frame != None or self.gui.Image_frame1 != None) and self.gui.show_next.get() and key not in ("space","Return"):
            self.gui.displayimage(self.old, caller="arrow")

    def default(self, obj):
        "Reverts colour back to default"
        if not obj or not obj.frame: return

        is_square = obj.thumb.width() ==  obj.thumb.height()
        if self.pointers:
            for p in self.pointers:
                self.gui.imagegrid.canvas.delete(p)
            self.pointers = tuple()
        """if is_square:
            self.imagegrid.canvas.move(obj.frame.ids["txt_rect"], 1, 0)
            coords = self.imagegrid.canvas.coords(obj.frame.ids["txt_rect"])

            new_x1 = coords[0]
            new_y1 = coords[1]
            new_x2 = coords[2] - 2
            new_y2 = coords[3]
        
            self.imagegrid.canvas.coords(obj.frame.ids["txt_rect"], new_x1, new_y1, new_x2, new_y2)
            """
        f_color = self.gui.square_outline if obj.dest == "" else obj.color
        f_color1 = self.gui.square_default if obj.dest == "" else obj.color

        self.imagegrid.canvas.itemconfig(
            obj.frame.ids["rect"], 
            outline=f_color, 
            fill=f_color1)
        """self.imagegrid.canvas.itemconfig(
            obj.frame.ids["txt_rect"],
            outline=f_color,
            fill=self.gui.square_default)
        """
        
        
    def selected(self, obj):
        if not obj: return

        is_square = obj.thumb.width() ==  obj.thumb.height()
        """if is_square:
            self.imagegrid.canvas.move(obj.frame.ids["txt_rect"], -1, 0)
            coords = self.imagegrid.canvas.coords(obj.frame.ids["txt_rect"])

            new_x1 = coords[0]
            new_y1 = coords[1]
            new_x2 = coords[2] + 2
            new_y2 = coords[3]
        
            self.imagegrid.canvas.coords(obj.frame.ids["txt_rect"], new_x1, new_y1, new_x2, new_y2)
            """

        self.imagegrid.canvas.itemconfig(
            obj.frame.ids["rect"],
            outline=self.gui.active_outline, 
            fill=self.gui.square_selected)
        """self.imagegrid.canvas.itemconfig(
            obj.frame.ids["txt_rect"],
            width=0,
            outline=self.gui.square_selected,
            fill=self.gui.square_selected)"""
        
        if self.gui.square_cutoff:
            size = self.gui.square_cutoff_size
            coords = self.gui.imagegrid.canvas.coords(obj.frame.ids["rect"])
            x0 = coords[0]
            x = coords[2]
            y0 = coords[1]
            y = coords[3]

            t = self.gui.outline_thickness
            t1 = t // 2
            t2 = t // 2
            t3 = t2-1

            top_left1 = self.imagegrid.canvas.create_polygon(
                x0-t, y0-t,
                x0+size+t1, y0-t,
                x0-t, y0+size+t1,
                width=0,
                outline=self.gui.grid_bg,
                fill=self.gui.grid_bg,
                tags=obj.frame.tag
                )
            top_right1 = self.imagegrid.canvas.create_polygon(
                x-size-t1, y0-t,
                x+t, y0-t,
                x+t, y0 + size+t1,
                width=0,
                outline=self.gui.grid_bg,
                fill=self.gui.grid_bg,
                tags=obj.frame.tag
                )
            bot_right1 = self.imagegrid.canvas.create_polygon(
                x+t, y-size-t1,
                x+t, y+t,
                x-size-t1, y+t,
                width=0,
                outline=self.gui.grid_bg,
                fill=self.gui.grid_bg,
                tags=obj.frame.tag
                )
            bot_left1 = self.imagegrid.canvas.create_polygon(
                x0-t, y-size-t1,
                x0+size+t1, y+t,
                x0-t, y+t,
                width=0,
                outline=self.gui.grid_bg,
                fill=self.gui.grid_bg,
                tags=obj.frame.tag
                )

            top_left = self.imagegrid.canvas.create_line(
                x0+size+t2, y0,
                x0, y0+size+t2,
                width=t,
                fill=self.gui.active_outline,
                tags=obj.frame.tag
                )
            top_right = self.imagegrid.canvas.create_line(
                x-size-t3-1, y0-1,
                x, y0+size+t3,
                width=t,
                fill=self.gui.active_outline,
                tags=obj.frame.tag
                )
            bot_left = self.imagegrid.canvas.create_line(
                x0, y-size-t2,
                x0+size+t2, y,
                width=t,
                fill=self.gui.active_outline,
                tags=obj.frame.tag
                )
            bot_right = self.imagegrid.canvas.create_line(
                x-size-t3, y,
                x, y-size-t3,
                width=t,
                fill=self.gui.active_outline,
                tags=obj.frame.tag
                )
        
            self.pointers = (top_left1, top_right1, bot_left1, bot_right1, top_left, top_right, bot_left, bot_right)
