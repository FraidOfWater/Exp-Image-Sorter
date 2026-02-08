import tkinter as tk
from PIL import Image, ImageTk
import os
from time import perf_counter
import psutil
process = psutil.Process(os.getpid())

# Img processing here?
# Virtual?

class dummy:
    def __init__(self, file, ids, tag, row, col, center_x, center_y, canvas):
        self.file = file
        self.ids = ids
        self.img_id = ids["img"]
        self.tag = tag
        self.row = row
        self.col = col
        self.center_x = center_x
        self.center_y = center_y
        self.canvas = canvas
    
    def change_image(self, image):
        self.canvas.itemconfig(self.img_id, image=image)

class imgfile:
    def __init__(self, imgtk, filename):
        self.thumb = imgtk
        self.truncated_filename = filename
        self.frame = None
        self.color = None

class ImageGrid(tk.Frame):
    def __init__(self, master, parent=None, thumb_size=256, center=False, 
                 bg="blue", dest=False, destination=None, 
                 theme={"square_default": "white",
                        "square_selected": "white",
                        "grid_background_colour": "white",
                        "textbox_size": 25, 
                        "square_padx": 4, 
                        "square_pady": 4, 
                        "square_outline": "white",
                        "square_border_size": 2,
                        "square_text": "white"
                        }):
        super().__init__(master)
        self.config(bg=bg)
        self.dest = dest
        self.fileManager = parent
        self.destination = destination
        # thumb size MUST be set in PREFS. This only loads the generated thumbs from cache, never resizes or creates them.
        script_dir = os.path.dirname(os.path.abspath(__file__))
        assets_dir = os.path.join(script_dir, "assets")
        
        self.btn_thumbs = {"default": ImageTk.PhotoImage(Image.open(os.path.join(assets_dir, "button.png"))), "pressed": ImageTk.PhotoImage(Image.open(os.path.join(assets_dir, "button_pressed.png")))}

        self.configure(borderwidth=0, border=0, bd=0, padx=0, pady=0)
        self.thumb_size = (thumb_size, thumb_size)
        self.center = center
        
        self.theme = theme
        self.theme["square_border_size"] = 3
        w = self.theme["square_border_size"]
        theme["square_padx"] = 2
        theme["square_pady"] = 1

        self.sqr_padding = (theme["square_padx"]+w,theme["square_pady"]+w)
        self.grid_padding = (2,2)
        self.btn_size = (theme["checkbox_height"])
        self.btn_size = 18
        
        self.sqr_size = (self.thumb_size[0]+self.theme.get("square_border_size"), self.thumb_size[1]+self.theme.get("square_border_size")) # thumb_w + padx, etc
        
        self.cols = 0
        self.rows = 0

        self.bg = bg

        self.id_index = 0

        self.image_items = []
        self.item_to_entry = {}  # Mapping from canvas item ID to entry
        self.selected = []
        self.current_selection = None

        self.canvas = tk.Canvas(self, highlightthickness=0, bg="blue", highlightbackground="blue",highlightcolor="blue")

        from tkinter import ttk
        # --- NEW: BETTER SCROLLBAR STYLE ---
        self.style = ttk.Style(self)
        self.style.theme_use("default")
        self.style.configure("Custom.Vertical.TScrollbar", 
                             background="black", 
                             troughcolor=bg, 
                             borderwidth=0, 
                             arrowsize=0) # Removing arrows for cleaner look
        self.style.map("Custom.Vertical.TScrollbar",
                       background=[("pressed", "#616161"), ("active", "#4B4B4B")])
        
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(self, highlightthickness=0, bg=bg)
        
        # Apply the TTK Scrollbar with the custom style
        self.v_scroll = ttk.Scrollbar(self, orient="vertical", 
                                      style="Custom.Vertical.TScrollbar",
                                      command=self.canvas.yview)
        
        self.canvas.configure(yscrollcommand=self.v_scroll.set)

        # Use Grid here to prevent the 'packing' lag during window resize
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.v_scroll.grid(row=0, column=1, sticky="ns")

        self.canvas.configure(bg=self.bg)  # Force recolor, otherwise managed automatically by tb.Window

        self.canvas.bind("<MouseWheel>",    self._on_mousewheel)
        self.canvas.bind("<Button-1>",      self._on_canvas_click)
        self.canvas.bind("<Button-3>",      self._on_canvas_click)
        self.canvas.bind("<Button-2>",      self._on_canvas_middle_mouse)
    
        self.pack(fill="both", expand=True)

        self.canvas.update()
        self.canvas.bind("<Configure>", self._on_resize)
        
        def ram():
            mem = process.memory_info().rss / 1024 / 1024  # RSS = Resident Set Size in bytes
            print(f"Memory used: {mem:.2f} MB", end="\r", flush=True)
            self.after(100, ram)
        #ram()

    def load_more(self, filelist) -> None:
        "Load the given images into the grid."
        if not filelist: return
        self.add(filelist)
    
    def clear_canvas(self, unload=False):
        "Remove all items from canvas, but dont unload thumbnails or animations from memory."
        grid_objects = [entry.file for entry in self.image_items]
        self.selected.clear()
        self.current_selection = None

        for obj in grid_objects:
            entry = obj.frame
            
            self.item_to_entry.clear()
            
            if not self.dest:
                obj.frame = None
                if not obj.destframe and unload:
                    self.fileManager.animate.stop(obj.id)
                    obj.thumb = None
                    obj.clear_frames()
            else:
                obj.destframe = None
                if not obj.frame and unload:
                    self.fileManager.animate.stop(obj.id)
                    obj.thumb = None
                    obj.clear_frames()
        
        self.image_items.clear()
        self.canvas.delete("all")

    def insert_first(self, new_images, pos=None):
        """
        Insert new image squares at the top of the grid.
        """
        if not new_images: return
        if not type(new_images) == list: new_images = [new_images]
        
        objs_w_no_thumbs = [obj for obj in new_images if not obj.thumb]

        thumb_w, thumb_h = self.thumb_size
        sqr_w, sqr_h = self.sqr_size
        sqr_padx, sqr_pady = self.sqr_padding
        grid_padx, grid_pady = self.grid_padding
        btn_size = self.btn_size

        canvas_w = self.canvas.winfo_width()
        cols = max(1, canvas_w // sqr_w)
        self.cols = cols
        center_offset = 0 if not self.center else max((canvas_w - cols * sqr_w) // 2, 0)

        w = self.theme.get("square_border_size")
        default_bg = self.theme.get("square_default")
        text_c = self.theme.get("square_text_colour")
        grid_background_colour = self.theme.get("grid_background_colour")

        btn_img = self.btn_thumbs["default"]
        btn_offset_x = w
        btn_offset_y = w * 2
        text_offset_x = btn_offset_x + btn_img.width() + 2
        text_offset_y = btn_offset_y + 1

        # --- Step 1: shift all existing items down (by number of rows inserted) ---
        rows_to_insert = (len(new_images) + cols - 1) // cols
        shift_y = rows_to_insert * (sqr_h + sqr_pady + btn_size)

        for item in self.image_items:
            self.canvas.move(item.tag, 0, shift_y)
            item.center_y += shift_y  # update logical center

        # --- Step 2: Create new entries at the top positions ---
        new_entries = []
        for i, file in enumerate(new_images):
            row = i // cols
            col = i % cols

            current_col = center_offset + col * (sqr_w + sqr_padx) + grid_padx
            current_row = row * (sqr_h + sqr_pady + btn_size) + grid_pady

            x_center = current_col + thumb_w // 2 + (w + 1) // 2
            y_center = current_row + thumb_h // 2 + (w + 1) // 2

            tag = f"img_{self.id_index}"
            self.id_index += 1

            file.color = file.color or default_bg

            rect = self.canvas.create_rectangle(
                current_col, current_row,
                current_col + sqr_w, current_row + sqr_h,
                width=w, outline=file.color, fill=file.color,
                tags=tag
            )

            img = self.canvas.create_image(
                x_center, y_center,
                image=file.thumb, anchor="center",
                tags=tag
            )

            txt_rect = self.canvas.create_rectangle(
                current_col, current_row + sqr_w,
                current_col + sqr_w, current_row + sqr_h + btn_size,
                width=w, outline=grid_background_colour, fill=grid_background_colour,
                tags=tag
            )

            but = self.canvas.create_image(
                current_col + btn_offset_x,
                current_row + thumb_h + btn_offset_y,
                image=btn_img, anchor="nw",
                tags=tag
            )

            label = self.canvas.create_text(
                current_col + text_offset_x,
                current_row + thumb_h + text_offset_y,
                text=file.truncated_filename,
                anchor="nw",
                fill=text_c,
                tags=tag
            )

            item_ids = {
                "rect": rect, "img": img, "label": label,
                "but": but, "txt_rect": txt_rect
            }
            entry = dummy(file, item_ids, tag, row, col, x_center, y_center, self.canvas)
            if not self.dest:
                file.frame = entry
            else:
                file.destframe = entry

            new_entries.append(entry)

            self.item_to_entry[rect] = entry
            self.item_to_entry[txt_rect] = entry

        # --- Step 3: Prepend the new entries to the list ---

        if pos:
            self.image_items.insert(pos, entry)
        else:
            self.image_items = new_entries + self.image_items

        # --- Step 4: Reflow everything to recompute correct rows/cols ---
        if objs_w_no_thumbs: self.fileManager.thumbs.generate(objs_w_no_thumbs)
        if pos:
            self.reflow_from_index(pos)
        else:
            self.reflow_from_index(0)

    def insert(self, pos, obj):
        self.image_items.insert(pos, obj)
        min_index = pos
        if min_index != len(self.image_items): self.reflow_from_index(pos)
        
    def add(self, new_images): # adds squares
        "Add images to the end of the self.image_items list."
        thumb_w, thumb_h = self.thumb_size
        sqr_w, sqr_h = self.sqr_size
        sqr_padx, sqr_pady = self.sqr_padding # distance between squares
        grid_padx, grid_pady = self.grid_padding # distance from the borders
        btn_size = self.btn_size
        canvas_w = self.canvas.winfo_width()
        self.cols = max(1, canvas_w // sqr_w)
        cols = self.cols
        center_offset = 0 if not self.center else max((canvas_w - cols * sqr_w) // 2, 0)
        temp = len(self.image_items)
        objs_w_no_thumbs = [obj for obj in new_images if not obj.thumb]
        
        w = self.theme.get("square_border_size")
        btn_img = self.btn_thumbs["default"]
        btn_offset_x = w
        btn_offset_y = w*2 # btn_img.height()
        text_offset_x = btn_offset_x+btn_img.width()+2
        text_offset_y = btn_offset_y+1
        default_bg = self.theme.get("square_default")
        grid_background_colour = self.theme.get("grid_background_colour")
        text_c = self.theme.get("square_text_colour")
        for i, file in enumerate(new_images, temp): # starting index is self.image_items length.
            row = i // cols
            col = i % cols
            
            current_col = center_offset + col * (sqr_w + sqr_padx) + grid_padx 
            current_row = row * (sqr_h + sqr_pady + btn_size) + grid_pady
            # col * (sqr_w+<number>) to add padding between containers.
            # this is already done in sqr_size definition.
            x_center = current_col + thumb_w // 2 + (w + 1) // 2
            y_center = current_row + thumb_h // 2 + (w + 1) // 2

            tag = f"img_{self.id_index}"
            
            if file.dest == "":
                file.color = default_bg

            rect = self.canvas.create_rectangle(
                current_col,
                current_row,
                current_col + sqr_w,
                current_row + sqr_h,
                width=w,
                outline=file.color,
                fill=file.color,
                tags=tag)
            
            img = self.canvas.create_image(
                x_center, 
                y_center, 
                image=file.thumb, 
                anchor="center", 
                tags=tag)
            
            txt_rect = self.canvas.create_rectangle(
                current_col,
                current_row + sqr_h+w,
                current_col + sqr_w,
                current_row + sqr_h + btn_size,
                width=w,
                outline=grid_background_colour,
                fill=grid_background_colour,
                tags=tag)
            
            but_offset = current_row + thumb_h
            but = self.canvas.create_image(
                current_col + btn_offset_x, 
                but_offset + btn_offset_y, 
                image=btn_img,
                anchor="nw",
                tags=tag)
            
            label = self.canvas.create_text(
                current_col + text_offset_x,
                current_row + thumb_h + text_offset_y,
                text=file.truncated_filename,
                anchor="nw",
                fill=text_c,
                tags=tag)

            item_ids = {"rect":rect, "img":img, "label":label, "but":but, "txt_rect":txt_rect}
            entry = dummy(file, item_ids, tag, row, col, x_center, y_center, self.canvas)
            if not self.dest:
                file.frame = entry
            else:
                file.destframe = entry

            if self.fileManager.gui.prediction.get():
                if file.conf:
                    if file.conf < 0.5: r, g, b = (255, int(510 * file.conf), 0)
                    else: r, g, b = (int(255 * (1 - file.conf)), 255, 0)
                    t_color = f"#{r:02x}{g:02x}{b:02x}"

                    path = self.fileManager.names_2_path[file.pred]
                    file.predicted_path = path
                    color = self.fileManager.gui.folder_explorer.color_cache.get(path, None)

                    # --- Create overlay labels (confidence + prediction name) ---
                    confidence_text = f"{file.conf:.2f}"
                    prediction_text = file.pred

                    # Padding and styling
                    overlay_pad_x = 6
                    overlay_pad_y = 4
                    overlay_font = ("Arial", 12, "bold")
                    overlay_fg = "white"
                    overlay_bg = self.fileManager.gui.main_colour  # black background

                    # Create group for overlays
                    # Confidence (bottom-right corner)
                    text_id = self.canvas.create_text(
                        current_col + thumb_w - overlay_pad_x,
                        current_row + thumb_h - overlay_pad_y,
                        anchor="se",
                        text=confidence_text,
                        fill=t_color,
                        font=overlay_font,
                        tags=tag
                    )
                    bbox = self.canvas.bbox(text_id)
                    rect_id = self.canvas.create_rectangle(
                        bbox[0] - 4, bbox[1] - 2, bbox[2] + 4, bbox[3] + 2,
                        fill=overlay_bg, outline="", stipple="gray50", tags=tag
                    )
                    self.canvas.tag_lower(rect_id, text_id)

                    # Prediction name (top-left corner)
                    text_id2 = self.canvas.create_text(
                        current_col + overlay_pad_x+2,
                        current_row + overlay_pad_y+4,
                        anchor="nw",
                        text=prediction_text,
                        fill=color or "white",
                        font=overlay_font,
                        tags=tag
                    )
                    bbox2 = self.canvas.bbox(text_id2)
                    rect_id2 = self.canvas.create_rectangle(
                        bbox2[0] - 4, bbox2[1] - 2, bbox2[2] + 4, bbox2[3] + 2,
                        fill=overlay_bg, outline="", stipple="gray50", tags=tag
                    )
                    self.canvas.tag_lower(rect_id2, text_id2)

                if color is None: 
                    self.fileManager.gui.folder_explorer.executor.submit(self.fileManager.gui.folder_explorer.get_set_color, path, square=text_id2)
                
            self.image_items.append(entry)
            self.item_to_entry[rect] = entry
            self.item_to_entry[txt_rect] = entry

            self.id_index += 1
        if objs_w_no_thumbs: self.fileManager.thumbs.generate(objs_w_no_thumbs)
        self._update_scrollregion()
    
    def remove(self, sublist, unload=True): # removes squares
        "Remove these items from canvas, internal lists, remove obj reference,"
        "stop their animations, remove their thumbnail if not used elsewhere,"
        "and initiate a canvas reflow event."

        min_reflow_i = len(self.image_items)
        for obj in sublist:
            entry = obj.destframe if self.dest else obj.frame
            index = self.image_items.index(entry)
            min_reflow_i = min(min_reflow_i, index)
            obj.pos = index
            self.image_items.pop(index)

            self.canvas.delete(entry.tag)
            del self.item_to_entry[entry.ids["rect"]]
            del self.item_to_entry[entry.ids["txt_rect"]]
            
            if not self.dest:
                obj.frame = None
                if not obj.destframe and unload:
                    self.fileManager.animate.stop(obj.id)
                    obj.thumb = None
                    obj.clear_frames()
            else:
                obj.destframe = None
                if not obj.frame and unload:
                    self.fileManager.animate.stop(obj.id)
                    obj.thumb = None
                    obj.clear_frames()
                    
        if min_reflow_i != len(self.image_items): self.reflow_from_index(min_reflow_i)
        print(min_reflow_i)
    
    def change_theme(self, theme):
        self.theme = theme
        for i in range(0, len(self.image_items)):
            item = self.image_items[i]
            
            w = theme.get("square_border_size")
            default_bg = theme.get("square_default")
            grid_background_colour = theme.get("grid_background_colour")
            text_c = theme.get("square_text_colour")
            self.bg = theme.get("grid_background_colour")

            self.canvas.configure(bg=self.bg)
            if item.file.dest == "":
                item.file.color = default_bg

            self.canvas.itemconfig(
                item.ids["rect"],
                width=w,
                outline=item.file.color, 
                fill=item.file.color)
            
            self.canvas.itemconfig(
                item.ids["label"],
                fill=text_c)
            
            self.canvas.itemconfig(
                item.ids["txt_rect"],
                width=w,
                outline=grid_background_colour,
                fill=grid_background_colour)
            
    def reflow_from_index(self, start_idx=0):
        start = perf_counter()
        thumb_w, thumb_h = self.thumb_size
        sqr_w, sqr_h = self.sqr_size
        sqr_padx, sqr_pady = self.sqr_padding
        grid_padx, grid_pady = self.grid_padding
        btn_size = self.btn_size
        
        cols = self.cols
        center_offset = 0 if not self.center else max((self.canvas.winfo_width() - cols * sqr_w) // 2, 0)

        w = self.theme.get("square_border_size")
        
        for i in range(start_idx, len(self.image_items)):
            item = self.image_items[i]

            new_row = i // cols
            new_col = i % cols

            current_col = center_offset + new_col * (sqr_w + sqr_padx) + grid_padx
            current_row = new_row * (sqr_h + sqr_pady + btn_size) + grid_pady

            x_center = current_col + thumb_w // 2 + (w + 1) // 2
            y_center = current_row + thumb_h // 2 + (w + 1) // 2

            dx = x_center - item.center_x
            dy = y_center - item.center_y

            item.row = new_row
            item.col = new_col
            item.center_x = x_center
            item.center_y = y_center

            #self.canvas.move(item.tag, dx, dy)
            self.canvas.move(item.tag, dx, dy)
            #self.after_idle(self.canvas.move, item.tag, dx, dy)
            #self.update()

        self._update_scrollregion()
        print(perf_counter()-start)
    
    def make_selection(self, entry):
        if self.current_selection is not None:
            c_entry = self.image_items[self.current_selection]
            if c_entry:
                self.canvas.itemconfig(c_entry.ids["rect"], 
                                       outline=self.theme.get("square_default"), fill=self.theme.get("square_default"))
        self.canvas.itemconfig(entry.ids["rect"], outline=self.theme.get("square_selected"), fill=self.theme.get("square_selected"))
        self.current_selection = self.image_items.index(entry)
        self.fileManager.navigator.window_focused = "DEST" if self.dest else "GRID"

    def canvas_clicked(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        overlapping = self.canvas.find_overlapping(x, y, x, y)

        return not bool(overlapping)

    def _on_canvas_click(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        overlapping = self.canvas.find_overlapping(x, y, x, y)

        for item_id in overlapping:
            entry = self.item_to_entry.get(item_id) # overlapping might find img and rect, item_to_entry only contains id to rect, though.

            # delete
            if not entry: continue
            if event.num == 1:
                self.toggle_entry(entry)

            elif event.num == 3:
                self.make_selection(entry)
                self.fileManager.gui.displayimage(entry.file)

        """if ".!toplevel." in event.widget._w and not overlapping and event.num == 3:
            self.clear_canvas(unload=True)
            self.destroy()
            self.master.destroy()"""
            
    def _on_canvas_middle_mouse(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        overlapping = self.canvas.find_overlapping(x, y, x, y)

        for item_id in overlapping:
            entry = self.item_to_entry.get(item_id) # overlapping might find img and rect, item_to_entry only contains id to rect, though.
            
            # delete
            if not entry: continue
            import pyperclip
            import subprocess
            import os

            path = os.path.abspath(entry.file.path)
            pyperclip.copy(path)
            subprocess.Popen(r'explorer /select,"{}"'.format(path))
            
    def _on_resize(self, event):
        sqr_w, sqr_h = self.sqr_size
        sqr_padx, sqr_pady = self.sqr_padding
        grid_padx, grid_pady = self.grid_padding
        displayed_cols = self.cols

        #canvas_w = self.canvas.winfo_width()
        #cols = max(1, canvas_w // sqr_w)

        #center_offset = 0 if not self.center else max((canvas_w - cols * sqr_w) // 2, 0)

        possible_cols = max(1, (event.width-2*grid_padx+sqr_padx-1) // (sqr_w+sqr_padx))
        #print(f"Displayed: {displayed_cols}/{possible_cols} Info: {(event.width-2*grid_padx+sqr_padx)-possible_cols*(sqr_w+sqr_padx)} {(sqr_w+grid_padx)}")
        
        if possible_cols == displayed_cols: 
            return
        elif possible_cols > displayed_cols or possible_cols < displayed_cols: # increase
            self.cols = possible_cols
            old_pos = self.canvas.yview()[0]
            self.reflow_from_index()
            self.canvas.yview_moveto(old_pos)
    
    def _on_mousewheel(self, event, direction=None):
        sqr_w, sqr_h = self.sqr_size
        sqr_padx, sqr_pady = self.sqr_padding
        
        # 1. Direction Handling
        if direction is None:
            if event.num == 4 or event.delta > 0: direction = -1
            elif event.num == 5 or event.delta < 0: direction = 1
            else: return

        # 2. Geometry Setup
        # Ensure row_height matches your grid layout perfectly
        row_height = sqr_h + sqr_pady + self.btn_size
        
        scrollregion = self.canvas.cget("scrollregion").split()
        if not scrollregion or len(scrollregion) < 4: return
        scroll_h = int(scrollregion[3])
        view_h = self.canvas.winfo_height()

        # 3. Calculate Boundaries
        # The absolute maximum pixels we can scroll down
        max_scroll_pixels = max(0, scroll_h - view_h)
        
        # The last row index that can actually be at the TOP of the canvas
        # This prevents the "shifting" at the end of the list
        max_row_index = max_scroll_pixels // row_height

        # 4. Current Position Logic
        current_fraction = self.canvas.yview()[0]
        current_pixel_top = current_fraction * scroll_h
        
        # Identify which row we are currently snapped to
        current_row_index = round(current_pixel_top / row_height)
        
        # 5. Target and Clamp
        target_row_index = current_row_index + direction
        target_row_index = max(0, min(target_row_index, max_row_index))
        
        # Calculate the exact pixel for that row
        target_pixel = target_row_index * row_height
        
        # 6. Final Alignment Check
        # If the target_pixel is very close to the bottom limit, 
        # we decide whether to snap to the limit or keep the row alignment.
        if target_pixel > max_scroll_pixels:
            target_pixel = max_scroll_pixels

        # Move the canvas
        new_top_fraction = target_pixel / scroll_h
        self.canvas.yview_moveto(new_top_fraction)
    
    def navigate(self, keysym, reverse=False):
        cols = self.cols
        rows = int((len(self.image_items) + cols - 1) / cols)
        first_visible_row = round(self.canvas.yview()[0] * rows)
        last_visible_row = round(self.canvas.yview()[1] * rows)
        
        if self.current_selection == None: 
            index = 0
            new_selection = self.image_items[index]
            self.make_selection(new_selection)
            self.current_selection = index
            return
        else:
            index = self.current_selection
            scroll_dir = None
        
            if keysym == "Left":
                index -= 1
                if index < 0: return
                scroll_dir = "Up" if not reverse else "Down"
            elif keysym == "Right":
                index += 1
                if index >= len(self.image_items): return
                scroll_dir = "Up" if reverse else "Down"
            elif keysym == "Up":
                index -= cols
                if index < 0: return
                scroll_dir = "Up" if not reverse else "Down"
            else:
                index += cols
                if index >= len(self.image_items): return
                scroll_dir = "Up" if reverse else "Down"

        new_selection = self.image_items[index]
        self.make_selection(new_selection)
        self.current_selection = index

        new_row = (len(self.image_items)-self.current_selection-1) // cols if reverse else self.current_selection // cols

        if first_visible_row <= new_row <= last_visible_row:
            if scroll_dir == "Up":
                if new_row < first_visible_row: # Scroll up
                    target_scroll = (first_visible_row-1) / rows
                    self.canvas.yview_moveto(target_scroll)
            else:
                if last_visible_row <= new_row: # Scroll down
                    target_scroll = (first_visible_row+1) / rows
                    self.canvas.yview_moveto(target_scroll)
        else:
            target_scroll = (new_row) / rows
            self.canvas.yview_moveto(target_scroll)
        
    # Helpers
    def unmark_entry(self, entry):
        self.canvas.itemconfig(entry.ids["but"], image=self.btn_thumbs["default"])
        self.selected.remove(entry)

    def mark_entry(self, entry):
        self.selected.append(entry)
        self.canvas.itemconfig(entry.ids["but"], image=self.btn_thumbs["pressed"])

    def toggle_entry(self, entry):
        if entry in self.selected:
            self.unmark_entry(entry)
        else:
            self.mark_entry(entry)
      
    def _update_scrollregion(self):
        cols = self.cols
        sqr_w, sqr_h = self.sqr_size
        sqr_padx, sqr_pady = self.sqr_padding
        grid_padx, grid_pady = self.grid_padding

        total_rows = (len(self.image_items) + cols - 1) // cols # ceil
        total_width = cols * (sqr_w + sqr_padx) - sqr_padx + 2*grid_padx
        
        # Calculate the actual height of the content
        content_height = total_rows * (sqr_h + sqr_pady + self.btn_size) + grid_pady
        
        # Add the height of the canvas window as extra padding
        # This allows the last row to be scrolled to the very top
        view_h = self.canvas.winfo_height()
        total_height = content_height + view_h - (view_h//(sqr_h + sqr_pady + self.btn_size))*(sqr_h + sqr_pady + self.btn_size)
        
        self.canvas.config(scrollregion=(0, 0, total_width, total_height))

if __name__ == "__main__":
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
    def load_images_from_folder(folder):
        return [
            os.path.join(folder, f) for f in os.listdir(folder)
            if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
        ][:1000]
    
    def load_images(paths, thumb_size):
        imgs = []
        for path in paths:
            try:
                filename = os.path.basename(path)
                img = Image.open(path)
                img.thumbnail((thumb_size,thumb_size))
                img_tk = ImageTk.PhotoImage(img)
                imgs.append(imgfile(img_tk, filename))
            except Exception as e:
                print(f"Error loading image {path}: {e}")
        return imgs
    
    root = tk.Tk()

    root.title("Image Viewer: Canvas")
    root.geometry("1200x1200")

    folder = r"C:\Users\4f736\Documents\Programs\Portable\Own programs\Exp-Img-Sorter\using resizing\data"
    thumb_size = 256
    center = False

    images = load_images(load_images_from_folder(folder), thumb_size)
    app = ImageGrid(root, thumb_size=thumb_size)
    app.load_images(images, False)
    root.mainloop()
