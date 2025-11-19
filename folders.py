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
BD = 4
RELIEF = "flat"

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
        self.hovered_btn = None
        self.scroll_enabled = True
        self.current_reassign = None
        self.start = time.perf_counter()
        self.root_path = None
        self.hotkeys = hotkeys

        # Thread management
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="Folders")
        self.color_cache = {}

        # State
        self.buttons = []  # (btn, path, depth, frame, marker)
        self.expanded = {}
        self.selected_index = 0
        self.button_width = 40

        # --- Layout ---
        main_colour = self.winfo_toplevel().main_colour
        self.config(style="Theme_dividers.TFrame")
        self.style = ttk.Style(self)
        self.style.configure("Theme_dividers.TFrame", background=main_colour)

        container = ttk.Frame(self, style="Theme_dividers.TFrame")
        container.pack(fill="both", expand=True)
        self.container = container
        
        self.canvas = tk.Canvas(container, highlightthickness=0, bg=main_colour)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)

        # Frame inside canvas
        self.scroll_frame = ttk.Frame(self.canvas, style="Theme_dividers.TFrame")
        self.scroll_window = self.canvas.create_window(
            (0, 0),
            window=self.scroll_frame,
            anchor="nw"
        )
        text = "Middle-Mouse+Key to assign hotkey.\rLeft click to assign destination, \rRight click to explore folder."
        self.text = tk.Label(self.scroll_frame, justify="left", text=text)
        self.text.pack(side="top", fill="both")

        # Scroll bindings
        self.scroll_frame.bind(
            "<Configure>",
            lambda e: (self.canvas.configure(scrollregion=self.canvas.bbox("all")), self.text.configure(wraplength=self.scroll_frame.winfo_width()))
        )
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(self.scroll_window, width=e.width)
        )

        # Pack canvas and scrollbar
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
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
        if event.state == 2 and event.keysym == "Caps_Lock":
            self.focus()
        self.update_selection(event)

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
        self.clear_all_folders()

    def reassign_hotkey(self, event=None, btn=None):
        if self.current_reassign:
            new_title = self.current_reassign["text"].removesuffix(" (?)")
            self.current_reassign.config(text=new_title)
            self.unbind_all("<KeyPress>")
            for x in self.buttons:
                if x[0].hotkey:
                    master = event.widget.winfo_toplevel()
                    self.bind_all(f"<KeyPress-{x[0].hotkey}>", lambda e, x=x: master.fileManager.setDestination({"path": x[0].folder_path, "color": x[0].default_c}, event))
            
            if self.current_reassign == btn:
                self.current_reassign = None
                return

        if not self.buttons:
            return
        if not self.hovered_btn or self.hovered_btn == "ttk::frame": return
        if not btn:
            index = self.selected_index
            btn, _, _, _, _ = self.buttons[index]
        if btn:
            print("test")
            for x in self.buttons:
                if x[0].hotkey:
                    self.unbind_all(f"<KeyPress-{x[0].hotkey}>")
            btn.hotkey = None
            title = btn["text"]
            folder_path = btn.folder_path
            new_title = ""
            if "▶" in title:
                new_title = "▶ "
            elif "▼" in title:
                new_title = "▼ "
            btn_text = f"{os.path.basename(folder_path)}"
            new_title += btn_text
            new_title += f" (?)"
            btn.config(text=new_title)
            self.current_reassign = btn

            def key_press(event):
                new_hotkey = event.keysym

                if new_hotkey in ("Shift_L","Control_L", "Shift_R","Control_R"): return
                self.unbind_all("<KeyPress>")
                
                for x in self.buttons:
                    if new_hotkey == x[0].hotkey:
                        self.unbind_all(f"<KeyPress-{new_hotkey}>")
                        x[0].hotkey = None
                        title = x[0]["text"]
                        new_title = ""
                        if "▶" in title:
                            new_title = "▶ "
                        elif "▼" in title:
                            new_title = "▼ "
                        btn_text = f"{os.path.basename(x[0].folder_path)}"
                        new_title += btn_text
                        x[0].config(text=new_title)

                btn.hotkey = new_hotkey
                title = btn["text"]
                folder_path = btn.folder_path
                new_title = ""
                if "▶" in title:
                    new_title = "▶ "
                elif "▼" in title:
                    new_title = "▼ "
                btn_text = f"{os.path.basename(folder_path)}"
                new_title += btn_text
                new_title += f" ({new_hotkey.capitalize()})"
                btn.config(text=new_title)
                for x in self.buttons:
                    if x[0].hotkey:
                        master = event.widget.winfo_toplevel()
                        self.bind_all(f"<KeyPress-{x[0].hotkey}>", lambda e, x=x: master.fileManager.setDestination({"path": x[0].folder_path, "color": x[0].default_c}, event))
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
            hotkey = None if depth == 0 and len(self.hotkeys) <= i else self.hotkeys[i]
            if folder == trash_dir: hotkey = "Delete"
            self.add_folder_button(full_path, depth, hotkey=hotkey)

    def get_set_color(self, path, btn=None, square=None):
        """try:
            start = time.perf_counter()
            images = load_images(path)
           
            #hex_dom = get_dominant_center_color_hex_folder(images, crop_ratio=0.1, similarity_threshold=0)
            #hex_med = get_median_center_color_hex_folder(images, crop_ratio=0.1, min_variation=0)
            #hex_vip = median_center_color_vips(images, crop_size=0.2, contrast_boost=1.3, min_variation=0)
            
            hex_dom = get_dominant_center_color_hex_folder(images, crop_ratio=0.1, similarity_threshold=0)
            print(1, time.perf_counter()-start)

            start = time.perf_counter()
            hex_dom1 = get_median_center_color_hex_folder(images, crop_ratio=0.1, min_variation=0)
            print(2, time.perf_counter()-start)

            start = time.perf_counter()
            hex_dom2 = median_center_color_vips(images, crop_size=0.2, contrast_boost=1.3, min_variation=0)
            print(3, time.perf_counter()-start)


            for hex_val, label in zip(
                [hex_dom2, hex_dom1, hex_dom],
                ["D", "M", "V"]
            ):
                swatch = tk.Label(btn, text=label, bg=hex_val, width=2, relief="solid", borderwidth=1)
                swatch.pack(side="right", padx=2)
        except Exception as e:
            print("Color extraction failed for:", path, e)"""
        try:
            hex_vip = self.color_cache.get(path, None)
            if hex_vip: pass
            elif path == self.winfo_toplevel().fileManager.trash_dir:
                hex_vip = "#888BF8"
            else:
                images = load_images(path)
                hex_vip = median_center_color_vips(images)
                #hex_vip = median_center_color_vips(images)
            self.color_cache[path] = hex_vip

            # Schedule the UI update in the main thread
            if btn:
                btn.after_idle(self._apply_color, btn, hex_vip)
            elif square:
                square.after_idle(self._apply_color_2_sqr, square, hex_vip)
        except Exception as e:
            print("Color extraction failed for:", path, e)

    def _apply_color_2_sqr(self, sqr, hex_vip):
        name = sqr.obj.pred
        sqr.canvas.itemconfig(sqr.text_id2, text=name, fill=hex_vip)

    def _apply_color(self, btn, hex_vip):
        if btn.winfo_exists():
            btn.default_c = hex_vip
            btn.darkened_c = self.darken_color(btn.default_c)
            btn.config(bg=hex_vip)

    def add_folder_button(self, folder_path, depth, index=None, hotkey=None):
        frame = ttk.Frame(self.scroll_frame, style="Theme_dividers.TFrame")
        marker = "▶" if self.has_subfolders(folder_path) else ""
        btn_text = f"{marker} {os.path.basename(folder_path)}"
        if hotkey: btn_text += f" ({hotkey.capitalize()})"
        padx = depth * 20
        btn = tk.Button(frame, text=btn_text, anchor="w", width=self.button_width, bd=BD, relief=RELIEF)
        btn.pack(fill="x", expand=True)
        if index is None or index >= len(self.buttons):
            frame.pack(fill="x", pady=1, padx=(padx, 0), expand=True)
            self.buttons.append((btn, folder_path, depth, frame, marker))
        else:
            self.buttons.insert(index, (btn, folder_path, depth, frame, marker))
            frame.pack(before=self.buttons[index + 1][3] if index + 1 < len(self.buttons) else None,
                       fill="x", pady=1, padx=(padx, 0), expand=True)
        
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
            if hotkey == "Delete":
                btn.bind_all(f"<KeyPress-{hotkey}>", lambda e, btn=btn: self.on_hotkey(e, btn))
            else:
                btn.bind_all(f"<KeyPress-{hotkey.lower()}>", lambda e, btn=btn: self.on_hotkey(e, btn))
                btn.bind_all(f"<KeyPress-{hotkey.upper()}>", lambda e, btn=btn: self.on_hotkey(e, btn))
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
        if self.expanded.get(folder_path):
            self.collapse_folder(folder_path)
        else:
            self.expand_folder(folder_path)

    def expand_folder(self, folder_path):
        index = self.get_button_index(folder_path)
        if index is None:
            return
        self.expanded[folder_path] = True
        depth = self.buttons[index][2] + 1
        subfolders = [f for f in os.listdir(folder_path) if os.path.isdir(os.path.join(folder_path, f))]
        for i, sub in enumerate(subfolders):
            full_path = os.path.join(folder_path, sub)
            self.add_folder_button(full_path, depth, index + i + 1)
        if subfolders:
            # Update marker to show expanded
            btn, path, depth, frame, marker = self.buttons[index]
            self.buttons[index] = (btn, path, depth, frame, "▼")
            btn_text = f"▼ {os.path.basename(folder_path)}"
            if btn.hotkey: btn_text += f" ({btn.hotkey.capitalize()})"
            btn.configure(text=btn_text)

    def collapse_folder(self, folder_path):
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
        marker = "▶" if self.has_subfolders(folder_path) else ""
        btn_text = f"{marker} {os.path.basename(folder_path)}"
        if btn.hotkey: btn_text += f" ({btn.hotkey.capitalize()})"
        self.buttons[index] = (btn, path, depth, frame, marker)
        btn.configure(text=btn_text)

    def get_button_index(self, folder_path):
        for i, (_, path, _, _, _) in enumerate(self.buttons):
            if path == folder_path:
                return i
        return None

    def on_mouse_wheel(self, event):
        #(2, 34, 35, 38, 39, 131106, 131110, 131107, 131111, 3, 6, 131074, 131078, 7, 131079, 131075):
        if not self.scroll_enabled:
            return
        outside_canvas = not event.widget._w.startswith(self.canvas._w)
        caps_lock_off = event.state not in (2,)
        outside_canvas = True # dont allow interaction without capslock
        if outside_canvas and (caps_lock_off or event.widget.widgetName == "scrollbar"):
            return
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

    def update_selection(self, event=None):
        def clear():
            for i, (btn, _, _, _, _) in enumerate(self.buttons):
                if btn["bg"] != btn.default_c or btn["fg"] != "black" or btn["relief"] != RELIEF:
                    btn.configure(bg=btn.default_c, fg="black", relief=RELIEF)
        def highlight(selected_btn=None):
                if not (self.selected_index < len(self.buttons)): return
                selected_btn = selected_btn or self.buttons[self.selected_index][0]
                selected_btn.configure(
                    bg=selected_btn.darkened_c,   # vivid blue
                    fg="white",
                    relief=RELIEF,
                    bd=BD,
                    highlightbackground="black"
                )
        if not self.buttons: return
        if not event:
            clear()
            highlight()
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
            self.scroll_enabled = False
            clear()
            event.widget.configure(bg=event.widget.darkened_c, fg="white")
            return
        elif event.type == tk.EventType.Leave and event.widget.widgetName == "ttk::frame":
            self.scroll_enabled = True
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
                    self.scroll_enabled = True
                    clear()
                    if event.state == 2:
                        highlight()
            return

    def on_left_click(self, event, btn=None):
        ignored_events = ("ttk::panedwindow", "tk_optionMenu", 'entry', "ttk::entry", "ttk::button", "ttk::frame", "ttk::checkbutton", "scrollbar")
        if event.widget._w.startswith(self.canvas._w): self.focus()

        if "!toplevel" in event.widget._w: return
        master = event.widget.winfo_toplevel()
        if "!folderexplorer" in event.widget._w and event.widget.widgetName == "button" and btn: 
            if event.state in (1,4,3,6): os.startfile(btn.folder_path)
            else: 
                master.fileManager.setDestination({"path": btn.folder_path, "color": btn.default_c}, event)
            return
        elif event.widget.widgetName in ignored_events: return
        elif event.state in (2, 3, 6) and event.widget.widgetName != "button":
            btn, selected_path, _, _, _ = self.buttons[self.selected_index]
            if event.state == 2:
                color = btn.default_c
                master.fileManager.setDestination({"path": selected_path, "color": color}, event)
            elif event.state in (3,6):
                os.startfile(btn.folder_path)

    def on_right_click(self, event, btn=None):
        ignored_events = ("ttk::panedwindow", "tk_optionMenu", 'entry', "ttk::entry", "ttk::button", "ttk::frame", "ttk::checkbutton", "scrollbar")
        if isinstance(event.widget, str): return # buttonpress event
        if event.widget._w.startswith(self.canvas._w): self.focus()
        
        master = event.widget.winfo_toplevel()
        
        if "!folderexplorer" in event.widget._w and event.widget.widgetName == "button" and btn:
            if event.state in (1,4,3,6): master.destination_viewer.create_window(event, {"path": btn.folder_path, "color": btn.default_c})
            else: self.toggle_folder(btn.folder_path) # (path, color)
        elif event.widget.widgetName in ignored_events: return
        elif event.state in (2, 3, 6) and event.widget.widgetName != "button":
            btn, selected_path, _, _, _ = self.buttons[self.selected_index]
            if event.state == 2:
                self.toggle_folder(selected_path)
            elif event.state in (3,6):
                master.destination_viewer.create_window(event, {"path": btn.folder_path, "color": btn.default_c})
                
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
