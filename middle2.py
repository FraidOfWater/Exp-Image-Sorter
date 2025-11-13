import tkinter as tk
from PIL import Image, ImageTk
import os
from time import perf_counter
import psutil
process = psutil.Process(os.getpid())

# encapsulate the image processing here. 
# 1. load, save thumb, display. (add_paths_to_canvas(paths) (must generate frame for threaded load/gen) -> load(path)//gen(path) -> 
# 2. Delete thumb(s), delete thumb ref, (saved on disk). (delete photoimage refs from self.images, delete frame) (move pathref from displayedlist to moved)
# 3. Holds a list of all paths, sorted in 1 master list, "sorted". "moved", "assigned" and "animated"(unsorted)
# buttons for columns
# Tidier button, effect on off, on buttons get added to a set, off buttons removed from it. Removing the btn removes from set also.

class dummy:
    def __init__(self, file, ids, tag, row, col, center_x, center_y, canvas):
        self.file = file
        self.ids = ids
        self.tag = tag
        self.row = row
        self.col = col
        self.center_x = center_x
        self.center_y = center_y
        self.canvas = canvas

class imgfile:
    def __init__(self, imgtk, filename):
        self.thumb = imgtk
        self.truncated_filename = filename
        self.frame = None

class ImageDisplayApp(tk.Frame):
    def __init__(self, master, thumb_size=256, center=False, 
                 bg="blue", 
                 theme={"square_default": "white",
                        "square_selected": "white",
                        "grid_bg": "white",
                        "textbox_size": 25, 
                        "square_padx": 4, 
                        "square_pady": 4, 
                        "square_outline": "white",
                        "outline_thickness": 2,
                        "square_text": "white"
                        }):
        super().__init__(master)
        # thumb size MUST be set in PREFS. This only loads the generated thumbs from cache, never resizes or creates them.
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        if hasattr(master, "master") and hasattr(master.master, "fileManager"):
            self.btn_thumbs = master.master.fileManager.btn_thumbs
        else:
            self.btn_thumbs = {"default": ImageTk.PhotoImage(Image.open(os.path.join(script_dir, "button.png"))), "pressed": ImageTk.PhotoImage(Image.open(os.path.join(script_dir, "button_pressed.png")))}

        self.configure(borderwidth=0, border=0, bd=0, padx=0, pady=0)
        self.thumb_size = (thumb_size, thumb_size)
        self.center = center
        
        self.theme = theme
        
        self.sqr_padding = (theme["square_padx"] + 1,theme["square_pady"] + 2)
        self.grid_padding = (theme["square_padx"] + 1,theme["square_pady"] + 1)
        self.btn_size = (theme["textbox_size"])
        # if paddin2 exists, we must change some functions....
        # padding controls space between containers
        # paddding2 controls the space of all containers between the edges of the frame.
        self.sqr_size = (self.thumb_size[0]+1, self.thumb_size[1]+1) # thumb_w + padx, etc
        
        self.cols = 0
        self.rows = 0

        self.bg = bg

        self.id_index = 0

        self.image_items = []
        self.item_to_entry = {}  # Mapping from canvas item ID to entry
        self.selected = set()

        self.canvas = tk.Canvas(self, highlightthickness=0, bg="blue", highlightbackground="blue",highlightcolor="blue")
        self.v_scroll = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.v_scroll.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.v_scroll.pack(side="left", fill="y")
        #port theme from gui
        self.canvas.configure(bg=self.bg)  # Force recolor, otherwise managed automatically by tb.Window

        self.canvas.bind("<MouseWheel>",    self._on_mousewheel)
        self.canvas.bind("<Button-1>",      self._on_canvas_click)
        self.canvas.bind("<Button-3>",      self._on_canvas_click)
    
        self.pack(fill="both", expand=True)

        self.canvas.update()
        self.canvas.bind("<Configure>", self._on_resize)
        
        def ram():
            mem = process.memory_info().rss / 1024 / 1024  # RSS = Resident Set Size in bytes
            print(f"Memory used: {mem:.2f} MB", end="\r", flush=True)
            self.after(100, ram)
        #ram()

    def load_images(self, new_images, bypass_update):
        "Add images to the end of the self.image_items list."
        thumb_w, thumb_h = self.thumb_size
        sqr_w, sqr_h = self.sqr_size
        sqr_padx, sqr_pady = self.sqr_padding
        grid_padx, grid_pady = self.grid_padding

        btn_size = self.btn_size

        canvas_w = self.canvas.winfo_width()
        self.cols = max(1, canvas_w // sqr_w)
        cols = self.cols

        center_offset = 0 if not self.center else max((canvas_w - cols * sqr_w) // 2, 0)
        temp = len(self.image_items)
        for i, file in enumerate(new_images, temp): # starting index is self.image_items length.
            row = i // cols
            col = i % cols

            current_col = center_offset + col * (sqr_w + sqr_padx) + grid_padx
            current_row = row * (sqr_h + sqr_pady + btn_size) + grid_pady
            # col * (sqr_w+<number>) to add padding between containers.
            # this is already done in sqr_size definition.
            
            x_center = current_col + thumb_w // 2 + 1
            y_center = current_row + thumb_h // 2 + 1

            tag = f"img_{self.id_index}"
            
            w = self.theme.get("outline_thickness")
            rect = self.canvas.create_rectangle(
                current_col,
                current_row,
                current_col + sqr_w+w-1,
                current_row + sqr_h+1,
                width=w,
                outline=self.theme.get("square_outline"),
                fill=self.theme.get("square_default"),
                tags=tag)
                
            txt_rect = self.canvas.create_rectangle(
                current_col + 1,
                current_row + sqr_h + 1 + w,
                current_col + sqr_w,
                current_row + sqr_h + btn_size,
                outline=self.theme.get("grid_bg"),
                fill=self.theme.get("grid_bg"),
                tags=tag)
            
            img = self.canvas.create_image(
                x_center, 
                y_center, 
                image=file.thumb, 
                anchor="center", 
                tags=tag)
            
            label = self.canvas.create_text(
                current_col + 26,
                current_row + thumb_h+4,
                text=file.truncated_filename,
                anchor="nw",
                fill=self.theme.get("square_text"),
                tags=tag)

            but_offset = current_row + thumb_h
            btn_img = self.btn_thumbs["default"]
            but = self.canvas.create_image(
                current_col + btn_img.width()//2+5, 
                but_offset + btn_img.height()//2+6, 
                image=btn_img,
                anchor="center",
                tags=tag)
            
            item_ids = {"rect":rect, "img":img, "label":label, "but":but, "txt_rect":txt_rect}
            entry = dummy(file, item_ids, tag, row, col, x_center, y_center, self.canvas)
            file.color = file.color or self.theme.get("square_default")
            self.image_items.append(entry)
            self.item_to_entry[rect] = entry
            self.item_to_entry[txt_rect] = entry

            file.frame = entry
            self.id_index += 1
        if not bypass_update:
            self._update_scrollregion()
    
    def reflow_from_index(self, start_idx=0):
        thumb_w, thumb_h = self.thumb_size
        sqr_w, sqr_h = self.sqr_size
        sqr_padx, sqr_pady = self.sqr_padding
        grid_padx, grid_pady = self.grid_padding
        btn_size = self.btn_size
        
        cols = self.cols
        center_offset = 0 if not self.center else max((self.canvas.winfo_width() - cols * sqr_w) // 2, 0)

        for i in range(start_idx, len(self.image_items)):
            item = self.image_items[i]

            new_row = i // cols
            new_col = i % cols

            current_col = center_offset + new_col * (sqr_w + sqr_padx) + grid_padx
            current_row = new_row * (sqr_h + sqr_pady + btn_size) + grid_pady

            x_center = current_col + thumb_w // 2 + 1
            y_center = current_row + thumb_h // 2 + 1

            dx = x_center - item.center_x
            dy = y_center - item.center_y

            item.row = new_row
            item.col = new_col
            item.center_x = x_center
            item.center_y = y_center

            self.canvas.move(item.tag, dx, dy)

            self._update_scrollregion()

    def _on_canvas_click(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        overlapping = self.canvas.find_overlapping(x, y, x, y)

        for item_id in overlapping:
            entry = self.item_to_entry.get(item_id) # overlapping might find img and rect, item_to_entry only contains id to rect, though.

            # delete
            if not entry:
                continue
            if event.num == 1:
                if entry in self.selected:
                    self.canvas.itemconfig(entry.ids["but"], image=self.btn_thumbs["default"])
                    self.selected.remove(entry)
                else:
                    self.selected.add(entry)
                    self.canvas.itemconfig(entry.ids["but"], image=self.btn_thumbs["pressed"])

            elif event.num == 3:
                self.master.master.fileManager.navigator.select(entry.file)
            
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
        
        if event.num == 4 or event.delta > 0:
            direction = -1
        elif event.num == 5 or event.delta < 0:
            direction  = 1
        
        current = self.canvas.yview()
        scrollregion = self.canvas.cget("scrollregion").split()
        scrollregion_height = int(scrollregion[3]) if len(scrollregion) == 4 else 1
        if scrollregion_height == 0:
            return

        fraction_per_pixel = 1 / scrollregion_height
        move_fraction = direction * (sqr_h + sqr_pady + self.btn_size) * fraction_per_pixel
        new_top = max(0, min(1, current[0] + move_fraction))
        self.canvas.yview_moveto(new_top)

    # Helpers
    def _update_scrollregion(self):
        cols = self.cols
        sqr_w, sqr_h = self.sqr_size
        sqr_padx, sqr_pady = self.sqr_padding
        grid_padx, grid_pady = self.grid_padding

        total_rows = (len(self.image_items) + cols - 1) // cols # ceil
        total_width = cols * (sqr_w + sqr_padx) - sqr_padx + 2*grid_padx
        total_height = total_rows * (sqr_h + sqr_pady + self.btn_size) + grid_pady
        self.canvas.config(scrollregion=(0, 0, total_width, total_height))

if __name__ == "__main__":
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
    def load_images_from_folder(folder):
        return [
            os.path.join(folder, f) for f in os.listdir(folder)
            if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
        ][:100]
    
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

    folder = r"C:\\Users\\4f736\\Documents\\Programs\\Portable\\Own programs\\Exp-Img-Sorter\\original\\data"
    thumb_size = 256
    center = False

    images = load_images(load_images_from_folder(folder), thumb_size)
    app = ImageDisplayApp(root, thumb_size=thumb_size)
    app.load_images(images)
    root.mainloop()