import os, tkinter as tk
from tkinter import ttk, simpledialog
from concurrent.futures import ThreadPoolExecutor
from random import random, seed
seed(1234)
THUMBSIZE = 256
CROP_RATIO = 0.4
MAX_IMAGES_PER_FOLDER = 25
HSV_SATURATION_BOOST = 1.75
HSV_VALUE_BOOST = 1.75
MIN_VARIATION = 30
BD = 2
RELIEF = "flat"

# color dropper icon

"""def get_method_a_color(folder_path):
    import pyvips
    import numpy as np

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
    import colorsys
    r, g, b = median / 255.0
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    s, v = min(s * sat_boost, 1.0), min(v * val_boost, 1.0)
    final_r, final_g, final_b = colorsys.hsv_to_rgb(h, s, v)

    return f'#{int(final_r*255):02x}{int(final_g*255):02x}{int(final_b*255):02x}'
"""

class FolderExplorer(ttk.Frame):
    "The folder view tree. Manages navigation by it. Binds right, left click and hotkeys. Possible to navigate using scrollwheel currently."
    def __init__(self, parent, hotkeys):
        super().__init__(parent)
        self.assets_path = os.path.join(os.path.dirname(__file__), "assets")

        self.icon_expand = None
        self.icon_collapse = None
        self.icon_reload = None
        self.expanded_all = False

        self.a = None
        self.destw = None
        self.parent = parent.master.master
        self.hovered_btn = None
        self.scroll_enabled = False
        self.current_reassign = None
        self.root_path = None
        self.hotkeys = hotkeys
        self.assigned_hotkeys = {}
        # Thread management
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="Folder_color_context_analysis")
        self.color_cache = {}

        self.buttons = []  # (btn, path, depth, frame, marker)
        self.expanded = {}
        self.selected_index = 0
        self.button_width = 40

        main_colour = self.winfo_toplevel().d_theme["main_colour"]
        self.config(style="Theme_dividers.TFrame")
        self.style = ttk.Style(self)
        self.style.configure("Theme_dividers.TFrame", background=main_colour)

        container = ttk.Frame(self, style="Theme_dividers.TFrame")
        container.pack(fill="both", expand=True)
        self.container = container

        controls = ttk.Frame(container, style="Theme_dividers.TFrame")
        controls.pack(side="top", fill="x", padx=1, pady=1)
        self.expand_all_var = tk.BooleanVar(value=False)

        body_frame = ttk.Frame(self.container, style="Theme_dividers.TFrame")
        body_frame.pack(side="top", fill="both", expand=True, pady=0)
        self.v_scroll = ttk.Scrollbar(body_frame, orient="vertical",style="Custom.Vertical.TScrollbar",command=self.controlled_yview)

        self.canvas = tk.Canvas(body_frame, highlightthickness=0, bg=main_colour)
        self.canvas.pack(side="left", fill="both", expand=True)

        self.bind_all("<MouseWheel>", self.on_mouse_wheel)
        
        self.reload_btn = tk.Button(controls,image=self.icon_reload,bd=BD,relief=RELIEF,bg="#555",command=self.clear_all_folders)
        self.expand_btn = tk.Button(controls,image=self.icon_expand,bd=BD,relief=RELIEF,bg="#555",command=self.toggle_expand_collapse_all)
        self.recolor_btn = tk.Button(controls, image=self.icon_reload, bd=BD, relief=RELIEF, bg="#555", command=self.recolor_buttons_to_contents)
        self.new_folder_btn = tk.Button(controls, image=self.icon_reload, bd=BD, relief=RELIEF, bg="#555", command=self.create_new_folder)
        
        controls.pack(fill="x", padx=1, pady=0)
        self.reload_btn.pack(side="left", padx=(0, 4))
        self.expand_btn.pack(side="left")
        self.recolor_btn.pack(side="left", padx=(4, 0))
        self.new_folder_btn.pack(side="left", padx=(4, 0))

        def _icon_hover(btn, on=True):
            btn.config(bg="#555" if on else self.winfo_toplevel().d_theme["main_colour"])
            btn.bind("<Enter>", lambda e: _icon_hover(btn))
            btn.bind("<Leave>", lambda e: _icon_hover(btn, False))

        self.scroll_frame = ttk.Frame(self.canvas, style="Theme_dividers.TFrame")
        self.scroll_window = self.canvas.create_window((0, 0),window=self.scroll_frame,anchor="nw")

        self.dragging = None
        self.drag_placeholder = None

        self.scroll_frame.bind("<Configure>",lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>",lambda e: self.canvas.itemconfig(self.scroll_window, width=e.width))

        bg = self.winfo_toplevel().d_theme["main_colour"]
        self.style = ttk.Style(self)
        self.style.theme_use("default")
        self.style.configure("Custom.Vertical.TScrollbar",background="black",troughcolor=bg,borderwidth=0,arrowsize=0) # Removing arrows for cleaner look
        self.style.map("Custom.Vertical.TScrollbar",background=[("pressed", "#616161"), ("active", "#4B4B4B")])

        self.v_scroll.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.configure(yscrollcommand=self.v_scroll.set)

        self.bind_all("<Button-1>", self.on_left_click);
        self.bind_all("<Button-3>", self.on_right_click)
        self.bind_all("<Control-N>", self.create_new_folder)
        self.bind_all("<Control-n>", self.create_new_folder)
        self.bind_all("<Control-r>", self.clear_all_folders)
        self.bind_all("<Control-R>", self.clear_all_folders)
        self.bind_all("<Caps_Lock>", self.caps_lock)
        container.bind("<Enter>", self.update_selection)
        container.bind("<Leave>", self.update_selection)
        self.canvas.bind("<Motion>", self.update_selection)

        self.update_selection()

    def controlled_yview(self, *args):
        """Intercepts manual scrollbar dragging to prevent void-scrolling."""
        # args will be something like ('moveto', '0.0') or ('scroll', '1', 'units')

        if args[0] == "moveto":
            offset = float(args[1])
            # If the user tries to drag the bar to a negative position (the void)
            if offset < 0:
                self.canvas.yview_moveto(0)
                return "break"

            # If all folders are in view, the scrollbar 'thumb' fills the track (0 to 1).
            # We prevent moving if we are already seeing everything.
            cur_top, cur_bottom = self.canvas.yview()
            if cur_top <= 0 and cur_bottom >= 1.0 and offset != 0:
                return "break"

        # Pass valid commands to the actual canvas view
        self.canvas.yview(*args)

    def set_view(self, path):
        same = self.root_path == os.path.normpath(path)
        if same: return
        self.root_path = os.path.normpath(path)
        self.parent.bindhandler.search_widget.set_inclusion(self.parent.destination_entry_field.get())
        self.clear_all_folders()
            

    def load_svg(self, file_path, size=(12, 12)):
        import pyvips
        from PIL import Image, ImageTk
        vips_img = pyvips.Image.thumbnail(file_path, size[0], height=size[1], size="both")
        if vips_img.bands == 3:
            vips_img = vips_img.bandjoin(255)
        mem_vips = vips_img.write_to_memory()
        pil_img = Image.frombytes("RGBA", (vips_img.width, vips_img.height), mem_vips)
        return ImageTk.PhotoImage(pil_img)

    def load_svg_rotated(self, file_path, size=(12, 12)):
        from PIL import ImageTk
        base_img = self.load_svg(file_path, size)
        pil = ImageTk.getimage(base_img)
        expand_pil = pil.rotate(90)
        collapse_pil = pil.rotate(270, expand=True)
        self.icon_expand = ImageTk.PhotoImage(expand_pil)
        self.icon_collapse = ImageTk.PhotoImage(collapse_pil)
        self.expand_btn.config(image=self.icon_expand)

    def has_subfolders(self, path):
        return any(os.path.isdir(os.path.join(path, f)) for f in os.listdir(path))

    def get_button_index(self, folder_path):
        for i, (_, path, _, _, _) in enumerate(self.buttons):
            if os.path.normpath(path) == os.path.normpath(folder_path):
                return i
        return None

    # Keys
    def on_hotkey(self, e, btn):
        master = e.widget.winfo_toplevel()
        if "entry" in e.widget._w: return
        if "toplevel" in e.widget._w: master = e.widget.master
        if self.parent.bindhandler.search_widget.search_active: return
        self.parent.fileManager.setDestination({"path": btn.folder_path, "color": btn.default_c}, e)

    def reassign_hotkey(self, event=None, btn=None):
        if self.current_reassign:
            if self.current_reassign.winfo_exists() == 1:
                new_title = self.current_reassign["text"].replace("?: ", "")
                self.current_reassign.config(text=new_title)
            self.unbind_all("<KeyPress>")
            for x in self.buttons:
                if x[0].hotkey and len(x[0].hotkey) == 1:
                    for h in (x[0].hotkey.lower(), x[0].hotkey.upper()):
                        self.bind_all(f"<KeyPress-{h}>", lambda e, x=x: self.parent.fileManager.setDestination({"path": x[0].folder_path, "color": x[0].default_c}, event))
                elif event.keysym != "??":
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
                new_hotkey = event.keysym

                self.unbind_all("<KeyPress>")

                for x in self.buttons:
                    if x[0].hotkey != None and new_hotkey.upper() == x[0].hotkey.upper():
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
                btn.hotkey = new_hotkey
                btn.config(text=btn_text)
                for x in self.buttons:
                    if x[0].hotkey == None: continue
                    elif x[0].hotkey and len(x[0].hotkey) == 1:
                        for h in (x[0].hotkey.lower(), x[0].hotkey.upper()):
                            self.bind_all(f"<KeyPress-{h}>", lambda e, x=x: self.parent.fileManager.setDestination({"path": x[0].folder_path, "color": x[0].default_c}, event))
                    elif event.keysym != "??":
                        self.bind_all(f"<KeyPress-{x[0].hotkey}>", lambda e, x=x: self.parent.fileManager.setDestination({"path": x[0].folder_path, "color": x[0].default_c}, event))
                self.current_reassign = None
            self.bind_all("<KeyPress>", key_press)
        return

    def caps_lock(self, event):
        # if outside this widget, allow to activate the scrolling behaviour. If inside, hide the "selection" and let mouse actions do their thing.
        if event.state == 0 and event.keysym == "Caps_Lock":
            self.focus()
            self.scroll_enabled = True
            self.update_selection(event)
        else:
            self.scroll_enabled = False
            self.update_selection(just_clear=True)

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

    # Expand/Collapse
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

    def expand_everything(self):
        for btn, path, _, _, _ in list(self.buttons):
            if self.has_subfolders(path): self.expand_folder(path)

    def collapse_everything(self):
        for btn, path, _, _, _ in reversed(list(self.buttons)):
            if self.expanded.get(os.path.abspath(path)): self.collapse_folder(os.path.abspath(path))

    def toggle_expand_collapse_all(self):
        if self.expanded_all:
            self.collapse_everything()
            self.expand_btn.config(image=self.icon_expand)
        else:
            self.expand_everything()
            self.expand_btn.config(image=self.icon_collapse)
        self.expanded_all = not self.expanded_all

    # Events
    def open_in_explorer(self, btn):
        os.startfile(btn.folder_path)

    def show_assigned(self, btn):
        def close_window(event=None):
            if event:
                if not self.destw.canvas_clicked(event):
                    return
            self.destw.clear_canvas(unload=True)
            self.destw.destroy()
            self.destw = None
            self.a.destroy()
            self.a = None
            self.parent.bindhandler.window_focused == "GRID"
        if self.a != None:
            close_window()

        self.a = tk.Toplevel()
        self.a.title(f"Files designated for {btn.folder_path}")
        self.a.columnconfigure(0, weight=1)
        self.a.rowconfigure(0, weight=1)
        self.a.geometry(self.parent.destpane_geometry)
        self.a.bind("<Button-3>", lambda e: close_window(e))
        self.a.protocol("WM_DELETE_WINDOW", close_window)
        self.a.transient(self.parent.gui)

        from imagegrid import ImageGrid
        self.destw = ImageGrid(self.a, paguirent=self.parent, thumb_size=self.parent.thumbnailsize, center=False, destination=btn.folder_path, bg=self.parent.d_theme["grid_background_colour"],
                                theme=self.parent.d_theme)

        self.destw.add([obj for obj in reversed(self.parent.fileManager.assigned) if os.path.normpath(obj.dest) == os.path.normpath(btn.folder_path)])

    def clear_all_folders(self, event=None):
        """Destroy all current folder buttons and clear internal state."""
        for _, _, _, frame, _ in self.buttons:
            frame.destroy()
        self.buttons.clear()
        self.expanded.clear()
        self.selected_index = 0

        self.update_selection()
        self.populate_buttons(self.root_path, 0)

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

    # Adding buttons
    def randomColor(self):
        r, g, b = int(random() * 256), int(random() * 256), int(random() * 256)
        brightness = (r * 0.299 + g * 0.587 + b * 0.114)
        if brightness > 200:
            if r > g and r > b: r = max(0, r - 50)
            elif g > r and g > b: g = max(0, g - 50)
            else: b = max(0, b - 50)

        return f'#{r:02X}{g:02X}{b:02X}'
    
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

    def add_folder_button(self, folder_path, depth, index=None, hotkey=None):
        if depth == 0: pass
        elif not self.expanded.get(os.path.dirname(folder_path), False): return
        frame = ttk.Frame(self.scroll_frame, style="Theme_dividers.TFrame")
        prefix = f"{hotkey}: " if hotkey else ""
        suffix = "▶ " if self.has_subfolders(folder_path) else ""
        btn_text = f"{suffix}{prefix}{os.path.basename(folder_path)}"
        padx = depth * 20

        if self.icon_expand == None and self.icon_collapse == None: self.load_svg_rotated(os.path.join(self.assets_path, "icon_expand_collapse.svg"))
        if self.icon_reload == None:
            self.icon_reload = self.load_svg(os.path.join(self.assets_path, "icon_reload.svg"))
            self.icon_color_dropper = self.load_svg(os.path.join(self.assets_path, "icon_color_dropper.svg"))
            self.icon_plus = self.load_svg(os.path.join(self.assets_path, "icon_plus.svg"))
            self.reload_btn.config(image=self.icon_reload)
            self.recolor_btn.config(image=self.icon_color_dropper)
            self.new_folder_btn.config(image=self.icon_plus)

        default_c = self.randomColor() if folder_path != self.winfo_toplevel().fileManager.trash_dir else "#888BF8"
        darkened_c = self.darken_color(default_c)
        btn = tk.Button(frame, text=btn_text, bg=default_c, anchor="w", relief=RELIEF)
        btn.config(font=("Courier", 12), fg="black")
        grab = tk.Label(frame,text="≡",cursor="fleur",width=2,bg="#444",fg="white")
        grab.pack(side="left", fill="y", padx=(0, 0))
        grab.bind("<ButtonPress-1>", lambda e, btn=btn: self.start_drag(e, btn))
        grab.bind("<B1-Motion>", self.drag_motion)
        grab.bind("<ButtonRelease-1>", self.drag_release)
        btn.pack(side="left", fill="both", expand=True)
        btn.default_c, btn.darkened_c = default_c, darkened_c

        if index is None or index >= len(self.buttons):
            frame.pack(fill="x", pady=1, padx=(padx, 0), expand=True)
            self.buttons.append((btn, folder_path, depth, frame, suffix))
        else:
            self.buttons.insert(index, (btn, folder_path, depth, frame, suffix))
            frame.pack(before=self.buttons[index + 1][3] if index + 1 < len(self.buttons) else None,
                    fill="x", pady=1, padx=(padx, 0), expand=True)
        btn.grab = grab
        btn.hotkey = hotkey
        btn.folder_path = folder_path
        btn.btn = btn
        btn.frame = frame
        
        btn.bind("<Button-1>", lambda e, btn=btn: self.on_left_click(e, btn=btn))
        btn.bind("<Button-2>", lambda e, btn=btn: self.reassign_hotkey(e, btn=btn))
        btn.bind("<Button-3>", lambda e, btn=btn: self.on_right_click(e, btn=btn))
        btn.bind("<Enter>", self.update_selection)
        btn.bind("<Leave>", self.update_selection)
        if hotkey:
            if len(hotkey) == 1:
                btn.bind_all(f"<KeyPress-{hotkey.lower()}>", lambda e, btn=btn: self.on_hotkey(e, btn))
                btn.bind_all(f"<KeyPress-{hotkey.upper()}>", lambda e, btn=btn: self.on_hotkey(e, btn))
            else: btn.bind_all(f"<KeyPress-{hotkey}>", lambda e, btn=btn: self.on_hotkey(e, btn))
        self.update()

    def create_new_folder(self, event=None):
        if not event:
            parent_path = self.root_path
            parent_depth = 0
            index = len(self.buttons)-1
        else:
            if not self.buttons or not (event.state & 0x0002) != 0:
                parent_path = self.root_path
                parent_depth = 0
                index = 0
            else:
                parent_path = self.buttons[self.selected_index][1]
                parent_depth = self.buttons[self.selected_index][2]
                index = self.selected_index + 1
        name = simpledialog.askstring("New Folder", "Enter folder name:", parent=self)
        if not name: return
        new_folder_path = os.path.join(parent_path, name)
        try: os.makedirs(new_folder_path, exist_ok=False)
        except Exception as e:
            print("Couldn't create folder:", e)
            return
        if parent_path != self.root_path: self.expand_folder(parent_path)
        else: self.add_folder_button(new_folder_path, parent_depth + 1 if parent_depth != 0 else parent_depth, index)

    # Color
    def load_images(self, folder):
        import pyvips
        import numpy as np
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

    def median_center_color_vips(self, images):
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
                    # Normalize, apply gamma power, and scale back
                    gamma = 1.0 / HSV_SATURATION_BOOST
                    crop = ((crop / 255.0) ** gamma) * 255.0

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

    def get_set_color(self, path, btn=None, square=None):
        try:
            hex_vip = self.color_cache.get(path, None)
            if hex_vip: pass
            else:
                images = self.load_images(path)
                hex_vip = self.median_center_color_vips(images)
            self.color_cache[path] = hex_vip
            if btn: btn.after_idle(self._apply_color, btn, hex_vip)
            elif square: self.parent.after_idle(self._apply_color_2_sqr, square, hex_vip)
        except Exception as e:
            print("Color extraction failed for:", path, e)

    def _apply_color_2_sqr(self, sqr, hex_vip):
        self.parent.imagegrid.canvas.itemconfig(sqr, fill=hex_vip)

    def _apply_color(self, btn, hex_vip):
        if btn.winfo_exists():
            btn.default_c = hex_vip
            btn.darkened_c = self.darken_color(btn.default_c)
            btn.grab.config(bg=btn.darkened_c)
            if btn["bg"] != "blue": btn.config(bg=hex_vip)

    def darken_color(self, hex_color, warmth=0.04, richness=0.15, dim=0.1):
        import colorsys
        def darken_color1(hex_color, shadow_strength=0.15):
            if not hex_color or not hex_color.startswith("#") or len(hex_color) != 7: return "#444444"
            r,g,b = int(hex_color[1:3], 16) / 255.0, int(hex_color[3:5], 16) / 255.0, int(hex_color[5:7], 16) / 255.0
            h, s, v = colorsys.rgb_to_hsv(r, g, b)
            h,s,v = (h + 0.02) % 1.0, min(s * 1.1, 1.0), max(v * (1 - shadow_strength), 0)
            r, g, b = colorsys.hsv_to_rgb(h, s, v)
            return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
        hex_color = hex_color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i+2], 16)/255 for i in (0, 2, 4))
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        h,s,v = (h - warmth) % 1.0,  min(1.0, s + richness), max(0.0, v - dim)
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        return darken_color1(f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}")

    def recolor_buttons_to_contents(self):
        for entry in self.buttons:
            btn, path, depth, frame, marker = entry
            if path == self.winfo_toplevel().fileManager.trash_dir: continue
            hex_vip = self.color_cache.get(path, None)
            if hex_vip: self._apply_color(btn, hex_vip)
            else: self.after_idle(self.executor.submit, self.get_set_color, path, btn)
            
    # Mouse events
    def start_drag(self, event, btn):
        self.drag_index = next(i for i, x in enumerate(self.buttons) if x[0] == btn)
        self.drag_data = self.buttons[self.drag_index]
        self.target_index = self.drag_index

        self.drag_data[0].configure(bg="#1a1a1a", fg="#555")

        self.drag_widget = tk.Label(self.scroll_frame,text=btn["text"],bg="#444", fg="white", font=btn["font"],relief="raised", borderwidth=1, anchor="w", padx=10)
        self.drag_widget.place(x=self.drag_data[3].winfo_x(),y=self.drag_data[3].winfo_y(),width=self.drag_data[3].winfo_width())

        self.insertion_line = tk.Frame(self.scroll_frame, height=2, bg="white")

    def drag_motion(self, event):
        y = self.canvas.canvasy(event.y_root - self.canvas.winfo_rooty())
        self.drag_widget.place(y=y - 15)
        new_index = 0
        for i, item in enumerate(self.buttons):
            frame = item[3]
            if y > (frame.winfo_y() + frame.winfo_height() / 2):
                new_index = i + 1
        self.target_index = new_index
        self.insertion_line.pack_forget()
        if new_index < len(self.buttons): self.insertion_line.pack(before=self.buttons[new_index][3], fill="x", pady=2)
        else: self.insertion_line.pack(fill="x", pady=2)

    def drag_release(self, event):
        moving_item = self.buttons.pop(self.drag_index)
        actual_pos = self.target_index
        if self.target_index > self.drag_index: actual_pos -= 1
        self.buttons.insert(max(0, actual_pos), moving_item)
        moving_item[0].configure(bg="#2b2b2b", fg="white")   # Restore text color
        self.drag_widget.destroy()
        self.insertion_line.destroy()
        for item in self.buttons:
            frame = item[3]
            depth = item[2]
            frame.pack_forget()
            frame.pack(fill="x", pady=1, padx=(depth * 20, 0), expand=True)
        self.update_selection()

    def on_mouse_wheel(self, event):
        if "!imagegrid" in event.widget._w: return "break"
        if self.scroll_enabled:
            # Mode A: Caps Lock is ON -> Move the blue selection bar
            hovering_buttons = event.widget._w.startswith(self.canvas._w) and (".!frame.!canvas.!frame" in event.widget._w or "!button" in event.widget._w)
            if hovering_buttons: return "break"

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
        else:
            # Mode B: Caps Lock is OFF -> Scroll the canvas view normally
            current_pos = self.canvas.yview()

            # Only scroll up if we aren't already at the top
            if event.delta > 0 and current_pos[0] <= 0:
                return "break"
            # Only scroll down if we aren't already at the bottom
            if event.delta < 0 and current_pos[1] >= 1.0:
                return "break"
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"

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

    def on_left_click(self, event, btn=None):
        if self.parent.dock_view.get() and self.parent.Image_frame:
            canvas = self.parent.Image_frame.canvas
            items = canvas.find_withtag("canvas_menu")
            if items:
                canvas.delete("canvas_menu")
        elif self.parent.second_window_viewer is not None and self.parent.second_window_viewer.winfo_exists():
            canvas = self.parent.second_window_viewer.canvas
            items = canvas.find_withtag("canvas_menu")
            if items:
                canvas.delete("canvas_menu")

        ignored_events = ("ttk::scale", "label", "ttk::panedwindow", "tk_optionMenu", 'entry', "ttk::entry", "ttk::button", "ttk::frame", "ttk::checkbutton", "scrollbar")
        if event.widget._w.startswith(self.canvas._w): self.focus()

        if "!imagegrid" in event.widget._w: return
        if "!toplevel" in event.widget._w: return
        fm = self.parent.fileManager
        if "!folderexplorer" in event.widget._w and event.widget.widgetName == "button" and btn:
            if event.state in (1, 3, 5, 6, 7, 33, 35, 37, 39): # ctrl
                self.show_assigned(btn)
            else:
                fm.setDestination({"path": btn.folder_path, "color": btn.default_c}, event)
        elif event.widget.widgetName in ignored_events: return
        elif event.state in (2, 3, 6) and event.widget.widgetName != "button":
            btn, selected_path, _, _, _ = self.buttons[self.selected_index]
            if event.state == 2:
                color = btn.default_c
                fm.setDestination({"path": selected_path, "color": color}, event)

    def on_right_click(self, event, btn=None):
        if hasattr(self, "canvas_menu_canvas"):
            items = self.canvas_menu_canvas.find_withtag("canvas_menu")
            if items:
                self.canvas_menu_canvas.delete("canvas_menu")

        ignored_events = ("label", "ttk::panedwindow", "tk_optionMenu", 'entry', "ttk::entry", "ttk::button", "ttk::frame", "ttk::checkbutton", "scrollbar")
        if isinstance(event.widget, str): return # buttonpress event
        if event.widget._w.startswith(self.canvas._w): self.focus()

        if "!imagegrid" in event.widget._w: return
        if "!folderexplorer" in event.widget._w and event.widget.widgetName == "button" and btn:
            if event.state in (1, 3, 5, 6, 7, 33, 35, 37, 39): # ctrl
                self.open_in_explorer(btn)
            else:
                self.toggle_folder(btn.folder_path) # (path, color)
        elif event.widget.widgetName in ignored_events: return
        elif event.state in (2, 3, 6) and event.widget.widgetName != "button":
            btn, selected_path, _, _, _ = self.buttons[self.selected_index]
            if event.state == 2:
                self.toggle_folder(selected_path)
        elif ("toplevel" in event.widget._w and "canvas" in event.widget._w) or "middlepane" in event.widget._w and "canvas" in event.widget._w:
            self.parent.bindhandler.handle_canvas_menu(event)


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Main Window")
    root.geometry("600x600")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    path = ""
    explorer = FolderExplorer(root, root_path=path)
    explorer.grid(row=0, column=0, sticky="nsew")
    root.mainloop()
