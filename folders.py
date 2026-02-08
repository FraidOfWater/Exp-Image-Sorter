import time
import os, tkinter as tk
from tkinter import ttk, simpledialog
from concurrent.futures import ThreadPoolExecutor

vipsbin = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vips-dev-8.17", "bin")
os.environ['PATH'] = os.pathsep.join((vipsbin, os.environ['PATH']))
os.add_dll_directory(vipsbin)

THUMBSIZE = 256
CROP_RATIO = 0.4
MAX_IMAGES_PER_FOLDER = 25
HSV_SATURATION_BOOST = 1.75
HSV_VALUE_BOOST = 1.75
MIN_VARIATION = 30
BD = 2
RELIEF = "flat"

import os
import numpy as np
import pyvips
import colorsys
import os
import numpy as np
import pyvips
import colorsys

#movable folders? shift drag for example?
def get_method_a_color(folder_path):
    all_pixels = []
    supported_exts = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff")
    
    # Values from sliders/variables
    limit = 32
    crop_ratio = 0.3
    min_var = 40
    sat_boost = 1.4
    val_boost = 1.9

    # 1. Recursive Walk
    # topdown=True ensures we process the root folder's images before subdirs
    for root, _, filenames in os.walk(folder_path):
        for fname in filenames:
            if fname.lower().endswith(supported_exts):
                img_path = os.path.join(root, fname)
                try:
                    # Using pyvips thumbnail for speed
                    vips_img = pyvips.Image.thumbnail(img_path, 256)
                    
                    # --- FIX 1: Robust Band Handling ---
                    if vips_img.bands == 4:
                        vips_img = vips_img[:3]
                    elif vips_img.bands == 1:
                        # Ensure grayscale images become RGB for stacking
                        vips_img = vips_img.bandjoin([vips_img, vips_img, vips_img])
                    
                    arr = np.ndarray(
                        buffer=vips_img.write_to_memory(), 
                        dtype=np.uint8,
                        shape=(vips_img.height, vips_img.width, vips_img.bands)
                    )
                    
                    h, w, _ = arr.shape
                    ch, cw = max(1, int(h * crop_ratio)), max(1, int(w * crop_ratio))
                    top, left = (h - ch) // 2, (w - cw) // 2
                    crop = arr[top:top+ch, left:left+cw, :3]
                    
                    # --- FIX 2: Explicit cast to avoid uint8 wrap-around ---
                    max_c = crop.max(axis=2).astype(np.int16)
                    min_c = crop.min(axis=2).astype(np.int16)
                    variation = max_c - min_c
                    
                    mask = (variation > min_var)
                    
                    if np.any(mask):
                        all_pixels.append(crop[mask].reshape(-1, 3))
                    
                    # Check limit: Stop processing files in this folder
                    if len(all_pixels) >= limit:
                        break
                        
                except Exception as e:
                    print(f"Error processing {fname}: {e}")
                    continue
        
        # Check limit again: Stop walking into further subdirectories
        if len(all_pixels) >= limit:
            break

    if not all_pixels: 
        return "#F0F0F0"
    
    # 2. Final Calculation
    pixels = np.vstack(all_pixels)
    median = np.median(pixels, axis=0).astype(np.uint8)
    
    # Boost colorsys
    r, g, b = median / 255.0
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    s, v = min(s * sat_boost, 1.0), min(v * val_boost, 1.0)
    final_r, final_g, final_b = colorsys.hsv_to_rgb(h, s, v)
    
    return f'#{int(final_r*255):02x}{int(final_g*255):02x}{int(final_b*255):02x}'


def load_images(folder):
    import numpy as np
    import pyvips
    supported_exts = (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp")
    images = []

    for root, _, files in os.walk(folder):
        for fname in files[:MAX_IMAGES_PER_FOLDER]:
            if not fname.lower().endswith(supported_exts):
                continue
            path = os.path.join(root, fname)
            try:
                vips_img = pyvips.Image.thumbnail(path, THUMBSIZE, size="both")
                # Drop alpha if present, ensure 3 bands
                if vips_img.bands == 1:
                    vips_img = vips_img.bandjoin([vips_img, vips_img])
                elif vips_img.bands == 4:
                    vips_img = vips_img[:3]
                arr = np.ndarray(buffer=vips_img.write_to_memory(), dtype=np.uint8,
                                 shape=(vips_img.height, vips_img.width, vips_img.bands))
                images.append(arr)
            except Exception as e:
                print("Failed to load:", path, e)
            if len(images) >= MAX_IMAGES_PER_FOLDER:
                break
        if len(images) >= MAX_IMAGES_PER_FOLDER:
            break
    return images

def median_center_color_vips(images):
    import numpy as np
    all_pixels = []

    for img in images:
        try:
            h, w, _ = img.shape

            # Handle crop_size as either ratio or fixed pixel size
            if CROP_RATIO < 1:
                ch, cw = int(h * CROP_RATIO), int(w * CROP_RATIO)
            else:
                ch, cw = min(int(CROP_RATIO), h), min(int(CROP_RATIO), w)

            top, left = (h - ch) // 2, (w - cw) // 2
            crop = img[top:top+ch, left:left+cw, :3].astype(np.float32)


            # Apply contrast boost
            if HSV_SATURATION_BOOST != 1.0:
                from skimage import exposure
                crop = exposure.adjust_gamma(crop / 255.0, gamma=1.0/HSV_SATURATION_BOOST) * 255.0

            # Mask low-variation pixels and combine with GrabCut
            variation = (crop.max(axis=2) - crop.min(axis=2))
            mask = (variation > MIN_VARIATION)
            if np.any(mask):
                pixels = crop[mask].reshape(-1, 3)
                all_pixels.append(pixels)
        except Exception as e:
            print("median_center_color_vips failed:", e)
            continue

    if not all_pixels:
        return "#F0F0F0"

    pixels = np.vstack(all_pixels)
    median = np.median(pixels, axis=0).astype(np.uint8)

    # Normalize to 0–1 for colorsys
    import colorsys
    r, g, b = np.array(median) / 255.0
    h, s, v = colorsys.rgb_to_hsv(r, g, b)

    # Boost and clamp
    s = min(s * HSV_SATURATION_BOOST, 1.0)
    v = min(v * HSV_VALUE_BOOST, 1.0)

    # Convert back to RGB 0–255
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    rgb = np.array([int(r * 255), int(g * 255), int(b * 255)], dtype=np.uint8)

    return f'#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}'

class FolderExplorer(ttk.Frame):
    "The folder view tree. Manages navigation by it. Binds right, left click and hotkeys. Possible to navigate using scrollwheel currently."
    def __init__(self, parent, hotkeys):
        super().__init__(parent)
        assets_path = os.path.join(os.path.dirname(__file__), "assets")

        def load_svg(file_path, size=(18, 18)):
            import pyvips
            from PIL import Image, ImageTk
            vips_img = pyvips.Image.thumbnail(file_path, size[0], height=size[1], size="both")
            if vips_img.bands == 3:
                vips_img = vips_img.bandjoin(255)
            mem_vips = vips_img.write_to_memory()
            pil_img = Image.frombytes("RGBA", (vips_img.width, vips_img.height), mem_vips)
            
            return ImageTk.PhotoImage(pil_img)
        self.icon_folder = load_svg(os.path.join(assets_path, "icon_folder.svg"))
        self.icon_inspect = load_svg(os.path.join(assets_path, "icon_inspect.svg"))

        self.a = None
        self.destw = None
        self.parent = parent.master.master
        self.hovered_btn = None
        self.scroll_enabled = False
        self.current_reassign = None
        self.start = time.perf_counter()
        self.root_path = None
        self.hotkeys = hotkeys
        self.assigned_hotkeys = {}
        # Thread management
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="Folders")
        self.color_cache = {}

        # State
        self.buttons = []  # (btn, path, depth, frame, marker)
        self.expanded = {}
        self.selected_index = 0
        self.button_width = 40

        # --- Layout ---
        main_colour = self.winfo_toplevel().d_theme["main_colour"]
        self.config(style="Theme_dividers.TFrame")
        self.style = ttk.Style(self)
        self.style.configure("Theme_dividers.TFrame", background=main_colour)

        container = ttk.Frame(self, style="Theme_dividers.TFrame")
        container.pack(fill="both", expand=True)
        self.container = container
        
        self.canvas = tk.Canvas(container, highlightthickness=0, bg=main_colour)
        #scrollbar = ttk.Scrollbar(container, orient="vertical", style="Custom.Vertical.TScrollbar", command=self.canvas.yview)

        """self.v_scroll = ttk.Scrollbar(self, orient="vertical", 
                                      style="Custom.Vertical.TScrollbar",
                                      command=self.canvas.yview)"""

        # Frame inside canvas
        self.scroll_frame = ttk.Frame(self.canvas, style="Theme_dividers.TFrame")
        self.scroll_window = self.canvas.create_window(
            (0, 0),
            window=self.scroll_frame,
            anchor="nw"
        )

        # Scroll bindings
        self.scroll_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            )
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(self.scroll_window, width=e.width)
        )

        # Pack canvas and scrollbar
        self.canvas.pack(side="left", fill="both", expand=True)
        #scrollbar.pack(side="right", fill="y")
        
        # --- Bindings ---
        #self.bind_all("<MouseWheel>", self.on_mouse_wheel)
        self.bind_all("<Button-3>", self.on_right_click)
        #self.bind_all("<Button-2>", self.hide_selected_folder)
        
        self.bind_all("<Button-1>", self.on_left_click)
        self.bind_all("<Control-N>", self.create_new_folder)
        self.bind_all("<Control-r>", self.clear_all_folders)
        self.bind_all("<Control-R>", self.clear_all_folders)
        self.bind_all("<Caps_Lock>", self.caps_lock)
        container.bind("<Enter>", self.update_selection)
        container.bind("<Leave>", self.update_selection)
        self.canvas.bind("<Motion>", self.update_selection)
        

        self.update_selection()

    def caps_lock(self, event):
        # if outside this widget, allow to activate the scrolling behaviour. If inside, hide the "selection" and let mouse actions do their thing.
        if event.state == 0 and event.keysym == "Caps_Lock":
            self.focus()
            self.scroll_enabled = True
            print("enabled")
            self.update_selection(event)
        else:
            self.scroll_enabled = False
            print("disabled")
            self.update_selection(just_clear=True)
    
    def clear_all_folders(self, event=None):
        """Destroy all current folder buttons and clear internal state."""
        for _, _, _, frame, _ in self.buttons:
            frame.destroy()
        self.buttons.clear()
        self.expanded.clear()
        self.selected_index = 0
        
        self.update_selection()
        self.populate_buttons(self.root_path, 0)

    
    def set_view(self, path):
        self.root_path = path
        self.parent.fileManager.navigator.search_widget.set_inclusion(self.parent.fileManager.gui.destination_entry_field.get())
        self.clear_all_folders()

    def set_current(self, full_path):
        if not self.root_path:
            return

        full_path = os.path.normpath(full_path)
        root_path = os.path.normpath(self.root_path)

        if not full_path.startswith(root_path):
            return

        # 1. Calculate the direct lineage (parent paths)
        rel_path = os.path.relpath(full_path, root_path)
        if rel_path == ".":
            parts = []
        else:
            folders = rel_path.split(os.sep)
            parts = [os.path.join(root_path, *folders[:i+1]) for i in range(len(folders))]

        # 2. COLLAPSE LOGIC: Close everything that isn't in our target's lineage
        # We create a set of the paths we WANT to keep open for fast lookup
        keep_open = set(parts)
        
        # Iterate over a copy of the expanded keys to avoid 'dictionary changed size' errors
        for path in list(self.expanded.keys()):
            if path not in keep_open and self.expanded[path]:
                # Call your existing collapse logic to remove buttons from UI
                self.collapse_folder(path) 

        # 3. Expand necessary parents downwards
        for path_segment in parts:
            if path_segment != full_path:
                if not self.expanded.get(path_segment, False):
                    self.expand_folder(path_segment)
                    self.update_idletasks()

        # 4. Final Selection
        target_index = self.get_button_index(full_path)
        if target_index is not None:
            self.selected_index = target_index
            self.update_selection()
            self.scroll_to_selected()

    def reassign_hotkey(self, event=None, btn=None):
        if self.current_reassign:
            if self.current_reassign.winfo_exists() == 1:
                new_title = self.current_reassign["text"].replace("?: ", "")
                self.current_reassign.config(text=new_title)
            self.unbind_all("<KeyPress>")
            for x in self.buttons:
                if x[0].hotkey and len(x[0].hotkey) == 1:
                    self.bind_all(f"<KeyPress-{x[0].hotkey.lower()}>", lambda e, x=x: self.parent.fileManager.setDestination({"path": x[0].folder_path, "color": x[0].default_c}, event))
                    self.bind_all(f"<KeyPress-{x[0].hotkey.upper()}>", lambda e, x=x: self.parent.fileManager.setDestination({"path": x[0].folder_path, "color": x[0].default_c}, event))
                elif x[0] == "Delete":
                    self.bind_all(f"<KeyPress-{x[0].hotkey}>", lambda e, x=x: self.parent.fileManager.setDestination({"path": x[0].folder_path, "color": x[0].default_c}, event))
            
            if self.current_reassign == btn:
                self.current_reassign = None
                return

        if not self.buttons:
            return
        if not self.hovered_btn or self.hovered_btn == "ttk::frame": return
        if not btn: return
        if btn:
            for x in self.buttons:
                if x[0].hotkey and len(x[0].hotkey) == 1:
                    self.unbind_all(f"<KeyPress-{x[0].hotkey.lower()}>")
                    self.unbind_all(f"<KeyPress-{x[0].hotkey.upper()}>")
                elif x[0].hotkey:
                    self.unbind_all(f"<KeyPress-{x[0].hotkey}>")
            btn.hotkey = None
            title = btn["text"]
            folder_path = btn.folder_path
            if self.assigned_hotkeys.get(folder_path) != None:
                del self.assigned_hotkeys[folder_path]
            suffix = ""
            if "▶" in title:
                suffix = "▶ "
            elif "▼" in title:
                suffix = "▼ "
            btn_text = f"{suffix}?: {os.path.basename(folder_path)}"
            btn.config(text=btn_text)
            self.current_reassign = btn

            def key_press(event):
                if event.keysym in ("Shift_L","Control_L", "Shift_R","Control_R"): return
                new_hotkey = event.keysym.upper()

                self.unbind_all("<KeyPress>")
                
                for x in self.buttons:
                    if new_hotkey == x[0].hotkey:
                        if len(new_hotkey) == 1:
                            self.unbind_all(f"<KeyPress-{new_hotkey.lower()}>")
                            self.unbind_all(f"<KeyPress-{new_hotkey.upper()}>")
                        else:
                            self.unbind_all(f"<KeyPress-{new_hotkey}>")
                        x[0].hotkey = None
                        title = x[0]["text"]
                        suffix = ""
                        if "▶" in title:
                            suffix = "▶ "
                        elif "▼" in title:
                            suffix = "▼ "
                        prefix = f"{x[0].hotkey}: " if x[0].hotkey else ""
                        btn_text = f"{suffix}{prefix}{os.path.basename(x[0].folder_path)}"
                        x[0].config(text=btn_text)

                btn.hotkey = new_hotkey
                title = btn["text"]
                folder_path = btn.folder_path
                self.assigned_hotkeys[folder_path] = new_hotkey
                prefix = f"{new_hotkey}: " if new_hotkey else ""
                suffix = ""
                if "▶" in title:
                    suffix = "▶ "
                elif "▼" in title:
                    suffix = "▼ "
                btn_text = f"{suffix}{prefix}{os.path.basename(btn.folder_path)}"

                btn.config(text=btn_text)
                for x in self.buttons:
                    if x[0].hotkey and len(x[0].hotkey) == 1:
                        self.bind_all(f"<KeyPress-{x[0].hotkey.lower()}>", lambda e, x=x: self.parent.fileManager.setDestination({"path": x[0].folder_path, "color": x[0].default_c}, event))
                        self.bind_all(f"<KeyPress-{x[0].hotkey.upper()}>", lambda e, x=x: self.parent.fileManager.setDestination({"path": x[0].folder_path, "color": x[0].default_c}, event))
                    elif x[0] == "Delete":
                        self.bind_all(f"<KeyPress-{x[0].hotkey}>", lambda e, x=x: self.parent.fileManager.setDestination({"path": x[0].folder_path, "color": x[0].default_c}, event))
                self.current_reassign = None
            self.bind_all("<KeyPress>", key_press)  
        return
    
    def hide_selected_folder(self, event=None, btn=None):
        index = self.selected_index
        if btn and event.state != 2:
            folder_path, frame = btn.folder_path, btn.frame
            self.collapse_folder(folder_path)
            for x in self.buttons:
                _, f_path, _, frame, _ = x
                if f_path == folder_path:
                    self.buttons.remove(x)
                    break
            frame.destroy()
            self.selected_index = 0
        elif not btn and event.state == 2:
            # Remove only the selected folder button
            _, folder_path, _, frame, _ = self.buttons[index]
            self.collapse_folder(folder_path)
            del self.buttons[index]
            frame.destroy()

            # Adjust selection to the next button, or previous if at the end
            if index >= len(self.buttons):
                self.selected_index = len(self.buttons) - 1
            else:
                self.selected_index = index

            self.update_selection()

    def has_subfolders(self, path):
        return any(os.path.isdir(os.path.join(path, f)) for f in os.listdir(path))

    def populate_buttons(self, path, depth):
        folders = [f for f in os.listdir(path) if os.path.isdir(os.path.join(path, f))]
        trash_dir = self.winfo_toplevel().fileManager.trash_dir
        folders.append(trash_dir)
        for i, folder in enumerate(folders):
            full_path = os.path.join(path, folder)
            hotkey = None if depth == 0 and len(self.hotkeys) <= i else self.hotkeys[i].upper()
            if folder == trash_dir: hotkey = "Delete"
            #self.after_idle(lambda full_path= full_path, depth=depth, hotkey=hotkey: self.add_folder_button(full_path, depth, hotkey=hotkey))
            hotkey = self.assigned_hotkeys[full_path] if self.assigned_hotkeys.get(full_path, None) != None else hotkey
            self.add_folder_button(full_path, depth, hotkey=self.assigned_hotkeys[full_path] if self.assigned_hotkeys.get(full_path, None) != None else hotkey)
            self.assigned_hotkeys[full_path] = hotkey
            
    def get_set_color(self, path, btn=None, square=None):
        try:
            hex_vip = self.color_cache.get(path, None)
            if hex_vip: pass
            elif path == self.winfo_toplevel().fileManager.trash_dir:
                hex_vip = "#888BF8"
            else:
                images = load_images(path)
                hex_vip = median_center_color_vips(images)
            self.color_cache[path] = hex_vip

            # Schedule the UI update in the main thread
            if btn:
                btn.after_idle(self._apply_color, btn, hex_vip)
            elif square:
                self.parent.after_idle(self._apply_color_2_sqr, square, hex_vip)
        except Exception as e:
            print("Color extraction failed for:", path, e)

    def _apply_color_2_sqr(self, sqr, hex_vip):
        self.parent.imagegrid.canvas.itemconfig(sqr, fill=hex_vip)

    def _apply_color(self, btn, hex_vip):
        if btn.winfo_exists():
            btn.default_c = hex_vip
            btn.darkened_c = self.darken_color(btn.default_c)
            btn.config(bg=hex_vip)
            self.update_selection()
    
    def add_folder_button(self, folder_path, depth, index=None, hotkey=None):
        if depth == 0: pass
        elif not self.expanded.get(os.path.dirname(folder_path), False): return
        frame = ttk.Frame(self.scroll_frame, style="Theme_dividers.TFrame")

        prefix = f"{hotkey}: " if hotkey else ""
        suffix = "▶ " if self.has_subfolders(folder_path) else ""
        btn_text = f"{suffix}{prefix}{os.path.basename(folder_path)}"
        
        padx = depth * 20

        # 1. Pack the secondary button to the RIGHT first
        # We give it a small width so it doesn't take up too much space

        btn2 = tk.Button(frame, image=self.icon_folder, bg="green", width=10, bd=BD, relief=RELIEF)
        btn2.pack(side="right", fill="both", padx=(1, 0))

        btn1 = tk.Button(frame, image=self.icon_inspect, bg="aqua", width=10, bd=BD, relief=RELIEF)
        btn1.pack(side="right", fill="both", padx=(1, 0)) 
        
        # 2. Pack the primary folder button to the LEFT
        # Use expand=True and fill="both" so it takes up all remaining space
        btn = tk.Button(frame, text=btn_text, anchor="w", bd=BD, relief=RELIEF)
        btn.config(font=("Courier", 12), fg="black")
        btn.pack(side="left", fill="both", expand=True)

        # ... rest of your logic for packing the frame into the scroll container ...
        if index is None or index >= len(self.buttons):
            frame.pack(fill="x", pady=1, padx=(padx, 0), expand=True)
            self.buttons.append((btn, folder_path, depth, frame, suffix))
        else:
            self.buttons.insert(index, (btn, folder_path, depth, frame, suffix))
            frame.pack(before=self.buttons[index + 1][3] if index + 1 < len(self.buttons) else None,
                    fill="x", pady=1, padx=(padx, 0), expand=True)

        btn2.config(command=lambda:show_folder())
        btn1.config(command=lambda:show_assigned())
        master = self.parent
        def show_assigned():
            def close_window(event=None):
                if event:
                    if not self.destw.canvas_clicked(event):
                        return
                self.destw.clear_canvas(unload=True)
                self.destw.destroy()
                self.destw = None
                self.a.destroy()
                self.a = None
            if self.a != None:
                close_window()

            self.a = tk.Toplevel()
            self.a.title(f"Files designated for {btn.folder_path}")
            self.a.columnconfigure(0, weight=1)
            self.a.rowconfigure(0, weight=1)
            self.a.geometry(master.fileManager.gui.destpane_geometry)
            self.a.bind("<Button-3>", lambda e: close_window(e))
            self.a.protocol("WM_DELETE_WINDOW", close_window)
            self.a.transient(master.fileManager.gui)
            
            from imagegrid import ImageGrid
            self.destw = ImageGrid(self.a, parent=master.fileManager, thumb_size=master.thumbnailsize, center=False, dest=True, destination=btn.folder_path, bg=master.d_theme["grid_background_colour"], 
                                    theme=master.d_theme)
            
            self.destw.add([obj for obj in reversed(master.fileManager.assigned) if os.path.normpath(obj.dest) == os.path.normpath(btn.folder_path)])
        def show_folder():
            os.startfile(btn.folder_path)
            
        btn.hotkey = hotkey
        btn.folder_path = folder_path
        btn.btn = btn
        btn.frame = frame
        btn.default_c = "#F0F0F0"
        btn.darkened_c = self.darken_color(btn.default_c)
        btn.bind("<Button-1>", lambda e, btn=btn: self.on_left_click(e, btn=btn))
        btn.bind("<Button-2>", lambda e, btn=btn: self.reassign_hotkey(e, btn=btn))
        btn.bind("<Button-3>", lambda e, btn=btn: self.on_right_click(e, btn=btn))
        btn.bind("<Enter>", self.update_selection)
        btn.bind("<Leave>", self.update_selection)
        if hotkey:
            if len(hotkey) == 1:
                btn.bind_all(f"<KeyPress-{hotkey.lower()}>", lambda e, btn=btn: self.on_hotkey(e, btn))
                btn.bind_all(f"<KeyPress-{hotkey.upper()}>", lambda e, btn=btn: self.on_hotkey(e, btn))
            else:
                btn.bind_all(f"<KeyPress-{hotkey}>", lambda e, btn=btn: self.on_hotkey(e, btn))
                
        self.update()
        if self.color_cache.get(folder_path, None):
            hex_vip = self.color_cache[folder_path]
            self._apply_color(btn, hex_vip)
        else:
            self.after_idle(self.executor.submit, self.get_set_color, folder_path, btn)
    
    def on_hotkey(self, e, btn):
        master = e.widget.winfo_toplevel()
        if "toplevel" in e.widget._w:
            master = e.widget.master
        master.fileManager.setDestination({"path": btn.folder_path, "color": btn.default_c}, e)
                    
    def toggle_folder(self, folder_path):
        folder_path = os.path.normpath(folder_path)
        if self.expanded.get(folder_path):
            self.collapse_folder(folder_path)
        else:
            self.expand_folder(folder_path)

    def expand_folder(self, folder_path):
        folder_path = os.path.normpath(folder_path)
        index = self.get_button_index(folder_path)
        if index is None:
            return
        self.expanded[folder_path] = True
        depth = self.buttons[index][2] + 1
        subfolders = [f for f in os.listdir(folder_path) if os.path.isdir(os.path.join(folder_path, f))]
        for i, sub in enumerate(subfolders):
            full_path = os.path.join(folder_path, sub)
            self.add_folder_button(full_path, depth, index + i + 1, self.assigned_hotkeys.get(full_path, None))
        if subfolders:
            # Update marker to show expanded
            btn, path, depth, frame, marker = self.buttons[index]
            self.buttons[index] = (btn, path, depth, frame, "▼ ")
            
            prefix = f"{btn.hotkey}: " if btn.hotkey else "?: " if "?" in btn["text"] else ""
            suffix = self.buttons[index][4]
            btn_text = f"{suffix}{prefix}{os.path.basename(btn.folder_path)}"
            btn.configure(text=btn_text)

    def collapse_folder(self, folder_path):
        self.reassign_hotkey()
        folder_path = os.path.normpath(folder_path)
        self.expanded[folder_path] = False
        index = self.get_button_index(folder_path)
        if index is None:
            return
        depth = self.buttons[index][2]
        i = index + 1
        while i < len(self.buttons) and self.buttons[i][2] > depth:
            _, _, _, frame, _ = self.buttons.pop(i)
            frame.destroy()
        # Update marker to show collapsed
        btn, path, depth, frame, _ = self.buttons[index]
        prefix = f"{btn.hotkey}: " if btn.hotkey else "?: " if "?" in btn["text"] else ""
        suffix = "▶ " if self.has_subfolders(folder_path) else ""
        btn_text = f"{suffix}{prefix}{os.path.basename(folder_path)}"
        self.buttons[index] = (btn, path, depth, frame, suffix)
        btn.configure(text=btn_text)

    def get_button_index(self, folder_path):
        for i, (_, path, _, _, _) in enumerate(self.buttons):
            if os.path.normpath(path) == os.path.normpath(folder_path):
                return i
        return None

    def nav(self, d):
        if not self.scroll_enabled: return
        rollover = False
        if d == "Down":
            if rollover: self.selected_index = min(self.selected_index + 1, len(self.buttons) - 1)
            else:
                self.selected_index += 1
                if self.selected_index >= len(self.buttons):
                    self.selected_index = 0
        
        elif d == "Up":
            if rollover: self.selected_index = max(self.selected_index - 1, 0)
            else:
                self.selected_index -= 1
                if self.selected_index < 0:
                    self.selected_index = len(self.buttons) - 1

        self.update_selection()
        self.scroll_to_selected()

    def on_mouse_wheel(self, event):
        if "!imagegrid" in event.widget._w: return
        #(2, 34, 35, 38, 39, 131106, 131110, 131107, 131111, 3, 6, 131074, 131078, 7, 131079, 131075):
        if not self.scroll_enabled: return
        hovering_buttons = event.widget._w.startswith(self.canvas._w) and (".!frame.!canvas.!frame" in event.widget._w or "!button" in event.widget._w)
        if hovering_buttons: return

        rollover = False
        if event.delta < 0:
            if rollover: self.selected_index = min(self.selected_index + 1, len(self.buttons) - 1)
            else:
                self.selected_index += 1
                if self.selected_index >= len(self.buttons):
                    self.selected_index = 0
        
        else:
            if rollover: self.selected_index = max(self.selected_index - 1, 0)
            else:
                self.selected_index -= 1
                if self.selected_index < 0:
                    self.selected_index = len(self.buttons) - 1

        self.update_selection()
        self.scroll_to_selected()

    def scroll_to_selected(self):
        if not self.buttons:
            return
        btn_widget = self.buttons[self.selected_index][0]
        canvas_top = self.canvas.canvasy(0)
        canvas_bottom = canvas_top + self.canvas.winfo_height()
        btn_top = btn_widget.winfo_rooty() - self.canvas.winfo_rooty() + self.canvas.canvasy(0)
        btn_bottom = btn_top + btn_widget.winfo_height()
        if btn_top < canvas_top:
            self.canvas.yview_moveto(btn_top / self.scroll_frame.winfo_height())
        elif btn_bottom > canvas_bottom:
            self.canvas.yview_moveto((btn_bottom - self.canvas.winfo_height()) / self.scroll_frame.winfo_height())

    
    def update_selection(self, event=None, just_clear=False):
        def clear():
            for i, (btn, _, _, _, _) in enumerate(self.buttons):
                if btn["bg"] != btn.default_c or btn["fg"] != "black" or btn["relief"] != RELIEF:
                    btn.configure(
                        bg=btn.default_c,
                        fg="black")
                #'TkDefaultFont'
        def highlight(selected_btn=None):
                if not (self.selected_index < len(self.buttons)): return
                selected_btn = selected_btn or self.buttons[self.selected_index][0]
                selected_btn.configure(
                    bg="blue",   # vivid blue
                    fg="white"
                ) # flat, groove, raised, ridge, solid, or sunken
        if just_clear: 
            clear()
            return
        if not self.buttons: return
        if not event: # when caps lock is called.
            clear()
            highlight() # selects selected_index
            return
        if event.type == tk.EventType.KeyPress:
            if event.state == 0 and event.keysym == "Caps_Lock":
                clear()
                highlight()
            elif event.state == 2 and event.keysym == "Caps_Lock":
                clear()
            return
        if event.widget._w.startswith(self.canvas._w) and event.widget.widgetName == "ttk::frame": return
        if event and event.type == tk.EventType.Enter and event.widget.widgetName == "button":
            self.selected_index = [x[0] for x in self.buttons].index(event.widget)
            self.hovered_btn = self.buttons[self.selected_index]
            clear()
            event.widget.configure(bg=event.widget.darkened_c, fg="white")
            return
        elif event.type == tk.EventType.Leave and event.widget.widgetName == "ttk::frame":
            clear()
            if event.state == 2:
                highlight()
        # --- When leaving a button (or moving in canvas gaps) ---
        if event and event.type == tk.EventType.Motion:
            # Check if cursor is not over any button
            x, y = event.x, event.y
            widget_under_mouse = event.widget.winfo_containing(event.widget.winfo_pointerx(), event.widget.winfo_pointery())
            if not (widget_under_mouse and getattr(widget_under_mouse, "widgetName", "") == "button"):
                if self.hovered_btn:
                    self.hovered_btn = None
                    clear()
                    if event.state == 2:
                        highlight()
            return

    def on_left_click(self, event, btn=None):
        ignored_events = ("ttk::panedwindow", "tk_optionMenu", 'entry', "ttk::entry", "ttk::button", "ttk::frame", "ttk::checkbutton", "scrollbar")
        if event.widget._w.startswith(self.canvas._w): self.focus()

        """is_toplevel_canvas = "toplevel" in event.widget._w and "canvas" in event.widget._w
        is_middle_canvas = "middlepane" in event.widget._w and "canvas" in event.widget._w
        
        if is_toplevel_canvas or is_middle_canvas:
            canvas = event.widget  # The specific canvas that was clicked
            canvas.delete("detach_ui")"""
        
        if "!imagegrid" in event.widget._w: return
        if "!toplevel" in event.widget._w: return
        master = event.widget.winfo_toplevel()
        if "!folderexplorer" in event.widget._w and event.widget.widgetName == "button" and btn: 
            master.fileManager.setDestination({"path": btn.folder_path, "color": btn.default_c}, event)
        elif event.widget.widgetName in ignored_events: return
        elif event.state in (2, 3, 6) and event.widget.widgetName != "button":
            btn, selected_path, _, _, _ = self.buttons[self.selected_index]
            if event.state == 2:
                color = btn.default_c
                master.fileManager.setDestination({"path": selected_path, "color": color}, event)

    def on_right_click(self, event, btn=None):
        ignored_events = ("ttk::panedwindow", "tk_optionMenu", 'entry', "ttk::entry", "ttk::button", "ttk::frame", "ttk::checkbutton", "scrollbar")
        if isinstance(event.widget, str): return # buttonpress event
        if event.widget._w.startswith(self.canvas._w): self.focus()
        
        if "!imagegrid" in event.widget._w: return
        if "!folderexplorer" in event.widget._w and event.widget.widgetName == "button" and btn:
            self.toggle_folder(btn.folder_path) # (path, color)
        elif event.widget.widgetName in ignored_events: return
        elif event.state in (2, 3, 6) and event.widget.widgetName != "button":
            btn, selected_path, _, _, _ = self.buttons[self.selected_index]
            if event.state == 2:
                self.toggle_folder(selected_path)
        elif ("toplevel" in event.widget._w and "canvas" in event.widget._w) or "middlepane" in event.widget._w and "canvas" in event.widget._w:
            self.handle_canvas_menu(event)
    
    def handle_canvas_menu(self, event):
        is_toplevel = "toplevel" in event.widget._w and "canvas" in event.widget._w
        is_middle = "middlepane" in event.widget._w and "canvas" in event.widget._w
        
        if not (is_toplevel or is_middle):
            return

        canvas = event.widget
        if "!canvas.!frame.!canvas.!frame" in event.widget._w: return # video cant draw over it
        canvas.delete("canvas_menu") 

        x, y = event.x, event.y
        btn_w, btn_h = 150, 35  # Slightly wider to fit the checkmark
        
        BG_NORMAL = "#2b2b2b"
        BG_HOVER = "#4a4a4a"
        TEXT_COLOR = "white"
        ACCENT_COLOR = "#00ff00" # Green for the checkmark
        BORDER_COLOR = "#666666"

        def helper():
            self.parent.dock_view.set(not self.parent.dock_view.get())
            self.parent.change_viewer() # Execute your detach logic
        def helper2():
            self.parent.dock_side.set(not self.parent.dock_side.get())
            self.parent.change_dock_side() # Execute your detach logic
        def helper3():
            self.parent.show_next.set(not self.parent.show_next.get())
        def helper4():
            self.parent.viewer_prefs["unbound_pan"] = not self.parent.viewer_prefs["unbound_pan"]
            if self.parent.Image_frame.canvas == event.widget:
                self.parent.Image_frame.unbound_var.set(self.parent.viewer_prefs["unbound_pan"])
            elif self.parent.second_window_viewer:
                self.parent.second_window_viewer.unbound_var.set(self.parent.viewer_prefs["unbound_pan"])

        # --- 1. Define Options List (Show Next is now first) ---
        # format: (Label, Command, Show_Checkmark)
        
        checkmark = "✓ " if self.parent.show_next.get() else "  "
        checkmark1 = "✓ " if self.parent.viewer_prefs["unbound_pan"] else "  "
        options = [
            ("Detach" if is_middle else "Dock", helper)
        ]
        
        if is_middle:
            options.append(("Switch Sides", helper2))
        options.append((f"{checkmark}Show Next", helper3))
        options.append((f"{checkmark1}Unbound Pan", helper4))

        # --- 2. Draw and Bind ---
        for i, (label, cmd) in enumerate(options):
            btn_y = y + (i * btn_h)
            row_tag = f"row_{i}"
            bg_tag = f"bg_{i}"

            # Draw Background
            canvas.create_rectangle(
                x, btn_y, x + btn_w, btn_y + btn_h,
                fill=BG_NORMAL, outline=BORDER_COLOR,
                tags=("canvas_menu", row_tag, bg_tag)
            )
            
            # Draw Text (Anchor 'w' for left-alignment to keep checkmarks lined up)
            text_item = canvas.create_text(
                x + 10, btn_y + (btn_h / 2),
                text=label, fill=TEXT_COLOR,
                anchor="w",
                font=("Segoe UI", 10),
                tags=("canvas_menu", row_tag)
            )

            # Apply green color specifically to the checkmark part if active
            if "✓" in label:
                # Note: canvas.itemconfig can't color partial text, 
                # so we just keep the whole string white or green for the 'Active' row
                canvas.itemconfig(text_item, fill=ACCENT_COLOR)

            # --- Interactive Hover Logic ---
            def on_enter(e, bt=bg_tag):
                canvas.itemconfig(bt, fill=BG_HOVER)
                canvas.config(cursor="hand2")

            def on_leave(e, bt=bg_tag):
                canvas.itemconfig(bt, fill=BG_NORMAL)
                canvas.config(cursor="")

            canvas.tag_bind(row_tag, "<Enter>", on_enter)
            canvas.tag_bind(row_tag, "<Leave>", on_leave)

            # --- Click Action ---
            canvas.tag_bind(row_tag, "<Button-1>", lambda e, c=cmd: [canvas.delete("canvas_menu"), c()])

        # Auto-dismiss on canvas click elsewhere
        canvas.after(100, lambda: canvas.bind("<Button-1>", lambda e: canvas.delete("canvas_menu"), add="+"))

    def create_new_folder(self, event):
        if not self.buttons:
            parent_path = self.root_path
            parent_depth = 0
            index = 0
        else:
            parent_path = self.buttons[self.selected_index][1]
            parent_depth = self.buttons[self.selected_index][2]
            index = self.selected_index + 1

        name = simpledialog.askstring("New Folder", "Enter folder name:", parent=self)
        if not name:
            return

        new_folder_path = os.path.join(parent_path, name)
        try:
            os.makedirs(new_folder_path, exist_ok=False)
        except Exception as e:
            print("Couldn't create folder:", e)
            return

        # Make sure parent folder is marked as expanded
        if parent_path != self.root_path:
            self.expanded[parent_path] = True
            parent_index = self.get_button_index(parent_path)
            if parent_index is not None:
                btn, path, depth, frame, _ = self.buttons[parent_index]
                self.buttons[parent_index] = (btn, path, depth, frame, "▼")
                btn.configure(text=f"▼ {os.path.basename(parent_path)}")

        # Add new folder button after currently selected folder
        self.add_folder_button(new_folder_path, parent_depth + 1, index)

    def darken_color(self, hex_color, warmth=0.04, richness=0.15, dim=0.1):
        def darken_color1(hex_color, shadow_strength=0.15):
            import colorsys
            """
            Return a visually pleasing 'shadowed' version of a given hex color.
            Slightly reduces brightness, adds a hint of complementary hue,
            and boosts saturation for richness.
            """
            if not hex_color or not hex_color.startswith("#") or len(hex_color) != 7:
                return "#444444"

            # Convert hex → RGB (0–1)
            r = int(hex_color[1:3], 16) / 255.0
            g = int(hex_color[3:5], 16) / 255.0
            b = int(hex_color[5:7], 16) / 255.0

            # Convert RGB → HSV
            h, s, v = colorsys.rgb_to_hsv(r, g, b)

            # Artistic tweaks:
            h = (h + 0.02) % 1.0  # tiny hue shift (warmer or cooler shadow)
            s = min(s * 1.1, 1.0)  # slightly more saturated
            v = max(v * (1 - shadow_strength), 0)  # darker but not dead

            # Convert back → RGB
            r, g, b = colorsys.hsv_to_rgb(h, s, v)
            return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
        
        import colorsys
        """
        Return a warmer and richer version of the given hex color.
        warmth: how much to shift hue toward red/orange (0–1 fraction of hue circle)
        richness: how much to increase saturation
        dim: how much to slightly lower brightness (value)
        """
        # Convert from hex to RGB [0–1]
        hex_color = hex_color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i+2], 16)/255 for i in (0, 2, 4))

        # Convert to HSV
        h, s, v = colorsys.rgb_to_hsv(r, g, b)

        # Shift hue toward red/orange
        h = (h - warmth) % 1.0
        # Boost saturation
        s = min(1.0, s + richness)
        # Slightly lower brightness for depth
        v = max(0.0, v - dim)

        # Convert back to RGB
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        t = darken_color1(f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}")
        return t

if __name__ == "__main__":
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title("Main Window")
    root.geometry("600x600")

    # Create a resizable main layout
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    # Create the FolderExplorer inside the main window
    explorer = FolderExplorer(root, root_path=r"E:\AntiDupl\All things pony\Royalty")
    explorer.grid(row=0, column=0, sticky="nsew")

    root.mainloop()
