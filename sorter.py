import os
import tkinter as tk

class ImageViewer:
    def __init__(self, root, canvas=None):
        self.root = root
        
        if canvas:
            self.canvas = canvas
        else:
            self.root.title("Simple Image Viewer")
            self.canvas = tk.Canvas(root, bg="black", highlightthickness=0)
            self.canvas.pack(fill=tk.BOTH, expand=True)

        self.queue = None
        self.image = None
        self.tk_img = None
        self.include_folder = None
        self.exclude_folder = set()
        self.cached_dirs = []
        self.available_hotkeys = list("1234567890qwertyuiopasdfghjklzxcvbnm")
        self.hotkey_memory = []

        # search state
        self.search_minimized = False
        self.locked_search_index = 0  # remembers selected index when minimized
        self.search_memory = {}
        self.search_active = False
        self.search_text = ""
        self.search_results = []
        self.selected_index = 0
        self.scroll_offset = 0
        self.max_visible = 6
        self.search_ui = {}

        self.hotkey_box = {}  # similar structure to search_ui
        self.hotkey_box_pos = [50, 50]
        self.hotkey_box_size = [300, 60]
        self.hotkey_active = False
        self.hotkeys = {}

        # remember search box position/size
        self.search_box_pos = [30, 30]
        self.search_box_size = [340, 60]

        # dragging / resizing
        self.dragging = False
        self.resizing = False
        self.drag_offset = (0, 0)

        # bindings
        root.bind("<Configure>", self.on_resize)
        root.bind("<Control-a>", self.clear_search)
        #root.bind("<Control-i>", self.show_hotkeys)

        root.bind("<Key>", self.on_key_press)

        # mouse events
        #self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        #self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        #self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        #self.canvas.bind("<Motion>", self.on_mouse_move)

        self.display_instructions()

    # ----------------------------
    # Basic display
    # ----------------------------
    def display_instructions(self):
        self.canvas.delete("sorter")
        msg = "Press Ctrl+F to select inclusion folder.\nCtrl+E for exclusion folder."
        self.canvas.create_text(
            self.root.winfo_width()//2,
            self.root.winfo_height()//2,
            text=msg, tags="sorter", fill="white", font=("Arial", 14), justify="center"
        )

    def show_image(self):
        w, h = self.root.winfo_width(), self.root.winfo_height()
        self.canvas.delete("sorter")
        self.canvas.create_image(w//2, h//2, image=self.tk_img, tags="sorter", anchor="center")
        self.search_ui = {}
        if self.search_active:
            self.draw_search_box()
        if self.hotkey_active:
            self.create_hotkey_box()

    def show_hotkeys(self, event=None):
        if self.hotkey_active:
            self.close_hotkeys()
            return

        self.hotkey_active = True
        self.create_hotkey_box()
        
        if self.search_active:
            self.close_search()

    def update_hotkey_box(self, event=None):
        self.close_hotkeys()
        self.create_hotkey_box()
        self.hotkey_active = True

    def close_hotkeys(self):
        if not self.hotkey_active:
            return
        for item in self.hotkey_box.values():
            if isinstance(item, list):
                for x in item:
                    self.canvas.delete(x)
            else:
                self.canvas.delete(item)
        self.hotkey_box.clear()
        self.hotkey_active = False

    def create_hotkey_box(self):
        layout_order = "1234567890qwertyuiopasdfghjklzxcvbnm"
        hotkeys = self.hotkeys
        hotkeys.clear()
        seen = set()
        for rel in self.hotkey_memory:
            name = os.path.basename(rel).lower()
            if name[0] not in seen: # if hotkey taken assign random.
                hotkeys[name[0]] = rel # first used path gets the hotkey.
                seen.add(name[0])
            elif self.available_hotkeys:
                hotkey = self.available_hotkeys.pop().lower()
                hotkeys[hotkey] = rel
                seen.add(hotkey)
        """h1 = []
        for key, path in hotkeys.items():
            name = os.path.basename(path)
            hotkey = key
            if key in layout_order
            h1.append((hotkey, name))
        h1.sort(key=lambda x: layout_order)
        hotkeys = sorted(hotkeys.items(), key=lambda kv: layout_order.index(kv[0]))"""
        hotkeys = list(hotkeys.items())
        x, y = self.hotkey_box_pos
        w, h = self.hotkey_box_size

        # Box background
        bg = self.canvas.create_rectangle(x, y, x + w, y + h, fill="#222", outline="#555", width=2)
        # Title
        title = self.canvas.create_text(x + 10, y + 10, anchor="nw", tags="sorter", text="Hotkeys",
                                        fill="white", font=("Arial", 14, "bold"))

        items = []
        y_offset = 35
        for k, v in hotkeys:
            t = self.canvas.create_text(x + 10, y + y_offset, anchor="nw", tags="sorter", text=f"{k}: {os.path.basename(v)}",
                                        fill="white", font=("Arial", 12))
            items.append(t)
            y_offset += 24

        # Resize box to fit content
        new_h = max(60, y_offset + 10)
        self.canvas.coords(bg, x, y, x + w, y + new_h)
        self.hotkey_box = {"box": bg, "title": title, "items": items}
        self.hotkey_box_size[1] = new_h

    def on_resize(self, event):
        if self.queue:
            self.canvas.after_cancel(self.queue)
        self.queue = self.canvas.after_idle(self.show_image)

    # ----------------------------
    # Folder logic
    # ----------------------------
    def set_inclusion(self, inclusion):
        folder = os.path.normpath(inclusion)
        if folder:
            self.include_folder = folder
            self.cache_folders()

    def set_exclusion(self, exclusions=None, folder=None):
        if folder:
            basename, dirname = folder
            folder = os.path.join(self.include_folder, dirname, basename)
            folder = os.path.normpath(folder)
            if folder:
                self.exclude_folder.add(folder)
        elif exclusions:
            for x in exclusions:
                folder = os.path.normpath(x)
                if folder:
                    self.exclude_folder.add(folder)
        self.cache_folders()
        self.update_search()

    def cache_folders(self):
        self.cached_dirs = []
        for root, dirs, _ in os.walk(self.include_folder):
            for d in dirs:
                p = os.path.join(root, d)
                if any(x.lower() in p.lower() for x in self.exclude_folder):
                    continue
                rel = os.path.relpath(p, self.include_folder)
                self.cached_dirs.append((d, rel))
        pass

    # ----------------------------
    # Search logic
    # ----------------------------
    def on_key_press(self, e):
        def select_result():
            name, rel = self.search_results[self.locked_search_index]
            full_path = os.path.join(self.include_folder, rel, name)
            print(f"Selected folder: {full_path}")
            if hasattr(self.root.winfo_toplevel(), "fileManager"):
                self.root.winfo_toplevel().fileManager.setDestination({"path": full_path, "color": "#FFFFFF"}, caller="sorter")

        # space: open search / update search
        # keypress: update search / open search
        # return: select search
        # up down: navigate search
        # escape: close search
        # control-i: open hotkey menu, close search
        # control-i again: close hotkey menu
        # htokey menu open: search opens only with space.
        # tab: works like space?

        if not self.include_folder or e.keysym == "Control_L": # ignore events
            return
        
        # activate search by space or tab, otherwise all keypresses activate hotkeys
        if (not self.search_active and e.keysym in ("space", "Tab")):# or (not self.search_active and not self.hotkey_active and len(e.char) == 1 and e.char.isprintable()):
            e.char = e.char if e.keysym not in ("space", "Tab") else ""
            self.start_search(e.char)
        elif self.hotkey_active and not self.search_active: # only hotkeybox open.
            if e.keysym == "Delete": # send to trash
                print("Trash")
            elif e.keysym == "Return": # Autosort
                print("Autosort")
            else:
                for h, name in self.hotkeys.items():
                    if e.keysym.lower() == h:
                        print(f"Selected folder: {name}")
                        self.root.winfo_toplevel().fileManager.setDestination({"path": name, "color": "#FFFFFF"}, caller="sorter")
        elif self.search_active:
            if self.search_minimized and ((len(e.char) == 1 and e.char.isprintable()) or e.keysym in ("Return", "BackSpace", "Up", "Down", "Tab", "space")): # behavior keypresses reset, space resets, nav unminimizes, backspace unminimizes
                if e.keysym == "Return":
                    select_result()
                    return
                
                self.search_minimized = False
                self.update_search_box()
                
                if e.keysym == "BackSpace":
                    pass
                elif e.keysym in ("Up", "Down"):
                    self.navigate(e.keysym)
                elif e.keysym in ("space", "Tab"):
                    self.search_text = ""
                    self.search_minimized = False
                    self.update_search()
                elif len(e.char) == 1 and e.char.isprintable():
                    self.search_text =  e.char
                    self.search_minimized = False
                    self.update_search()
            else:
                if e.keysym == "Return":
                    if self.selected_index > len(self.search_results) - 1: 
                        return
                        
                    name, rel = self.search_results[self.selected_index]
                    #q = self.search_text.lower().replace("/", "\\")
                    
                    partial = self.search_text.lower().replace("/", "\\")
                    full = name.lower().replace("/", "\\")

                    self.search_memory[partial] = (name, self.selected_index)
                    self.search_memory[full] = (name, self.selected_index)
                    rel = os.path.join(self.include_folder, rel, name)
                    if rel not in self.hotkey_memory:
                        self.hotkey_memory.append(rel)
                        if self.hotkey_active:
                            self.update_hotkey_box()
                    
                    self.search_text = name

                    self.locked_search_index = self.selected_index

                    self.search_minimized = True
                    self.update_search_box()
                    if self.search_results:
                        select_result()
                elif e.keysym == "Escape":
                    self.close_search()
                elif e.keysym == "BackSpace":
                    if self.search_text == "":
                        self.close_search()
                    else:
                        self.search_text = self.search_text[:-1]
                        self.update_search()
                elif e.keysym == "Delete":
                    if self.search_minimized: 
                        return
                    self.set_exclusion(folder=self.search_results[self.selected_index])
                elif e.keysym in ("Up", "Down"):
                    self.navigate(e.keysym)

                elif len(e.char) == 1 and e.char.isprintable():
                    self.search_text += e.char
                    self.update_search()

    def start_search(self, first_char):
        self.search_active = True
        self.search_text = first_char
        self.scroll_offset = 0
        self.selected_index = 0
        self.search_results = []
        self.create_search_box()
        self.update_search()

    def clear_search(self, event=None):
        self.search_minimized = False
        self.search_text = ""
        self.update_search()

    def close_search(self):
        self.search_active = False
        self.search_minimized = False
        for item in self.search_ui.values():
            if isinstance(item, list):
                for i in item:
                    self.canvas.delete(i)
            else:
                self.canvas.delete(item)
        self.search_ui.clear()
        self.search_text = ""

    def update_search(self):
        q = self.search_text.lower().replace("/", "\\")
        qs = q.split(" ")

        # if all true, if / in relative and if not in basename
        self.search_results = []
        for n, r in self.cached_dirs:
            r = os.path.dirname(r)
            if all((("\\" in q or "/" in q) and q in r.lower()) or (("\\" not in q or "/" not in q) and q in n.lower()) for q in qs): # rel
                self.search_results.append((n, r))

        self.search_results.sort(key=lambda x: (len(x[0]), x[0])) # sort based on name length and alphabetically.
        self.search_results.sort(key=lambda x: len(x[1].split("\\"))) # sort based on path length

        os.path.split

        # restore remembered index if available
        # ignore for multi variable searches
        if self.search_results and qs[0] and len(qs) == 1:
            query_length = len(q)
            for x in sorted(list(self.search_memory.keys()), key=lambda x: len(x)-query_length): # find closest match.
                if q in x:
                    idx = self.search_memory[x][1]
                    if idx < len(self.search_results):
                        self.selected_index = idx
                    else:
                        self.selected_index = 0
                    break
                else:
                    if self.selected_index > len(self.search_results) - 1:
                        self.selected_index = 0
                        self.scroll_offset = 0

        self.update_search_box()
    
    def navigate(self, direction):
        if not self.search_results:
            return
        if direction == "Down":
            self.selected_index = min(self.selected_index + 1, len(self.search_results) - 1)
        else:
            self.selected_index = max(self.selected_index - 1, 0)
        if self.selected_index >= self.scroll_offset + self.max_visible:
            self.scroll_offset += 1
        elif self.selected_index < self.scroll_offset:
            self.scroll_offset -= 1
        self.update_search_box()

    # ----------------------------
    # Drawing and interaction
    # ----------------------------
    def create_search_box(self):
        x, y = self.search_box_pos
        w, h = self.search_box_size
        bg = self.canvas.create_rectangle(x, y, x + w, y + h, tags="sorter", fill="#222", outline="#555", width=2)
        txt = self.canvas.create_text(x + 10, y + 15, anchor="w", tags="sorter", text=f"> {self.search_text}",
                                      fill="white", font=("Consolas", 13))
        self.search_ui = {"box": bg, "text": txt, "results": []}

    def draw_search_box(self):
        if not self.search_ui:
            self.create_search_box()
            self.update_search_box()

    def update_search_box(self):
        if not self.search_ui:
            return
        # If minimized, only show the search bar, not results
        if self.search_minimized:
            x1, y1 = self.search_box_pos
            w, _ = self.search_box_size
            h = 40  # minimal height
            self.canvas.coords(self.search_ui["box"], x1, y1, x1 + w, y1 + h)
            self.canvas.itemconfig(self.search_ui["text"], text=f"> {self.search_text}")
            # Delete any previous result items
            for i in self.search_ui.get("results", []):
                self.canvas.delete(i)
            self.search_ui["results"] = []
            return

        x1, y1, x2, y2 = self.canvas.coords(self.search_ui["box"])
        visible_count = min(len(self.search_results), self.max_visible)
        total_height = 40 + visible_count * 34
        self.canvas.coords(self.search_ui["box"], x1, y1, x1 + self.search_box_size[0], y1 + total_height)
        self.search_box_size[1] = total_height - y1
        self.canvas.itemconfig(self.search_ui["text"], text=f"> {self.search_text}")
        
        for i in self.search_ui["results"]:
            self.canvas.delete(i)
        self.search_ui["results"].clear()
        start = self.scroll_offset
        end = start + visible_count
        y = y1 + 35
        for i, (name, rel) in enumerate(self.search_results[start:end], start):
            fg = "#00ff99" if i == self.selected_index else "white"
            name_id = self.canvas.create_text(x1 + 10, y, anchor="nw", tags="sorter", text=name,
                                              fill=fg, font=("Arial", 12, "bold"))
            rel_id = self.canvas.create_text(x1 + 15, y + 18, anchor="nw", tags="sorter", text=rel,
                                             fill="#888", font=("Arial", 9))
            self.search_ui["results"].extend([name_id, rel_id])
            y += 34

    # ----------------------------
    # Drag / Resize handling
    # ----------------------------
    def on_mouse_down(self, e):
        if not self.search_active:
            return
        if not self.search_ui:
            return
        x1, y1, x2, y2 = self.canvas.coords(self.search_ui["box"])
        if x1 <= e.x <= x2 and y1 <= e.y <= y2:
            if e.x >= x2 - 10 and e.y >= y2 - 10:
                self.resizing = True
                self.drag_offset = (x2 - e.x, y2 - e.y)
            else:
                self.dragging = True
                self.drag_offset = (e.x - x1, e.y - y1)

    def on_mouse_up(self, e):
        if self.dragging or self.resizing:
            # store current position and size
            x1, y1, x2, y2 = self.canvas.coords(self.search_ui["box"])
            self.search_box_pos = [x1, y1]
            self.search_box_size = [x2 - x1, y2 - y1]
        self.dragging = False
        self.resizing = False

    def on_mouse_drag(self, e):
        if not self.search_active or not self.search_ui:
            return
        x1, y1, x2, y2 = self.canvas.coords(self.search_ui["box"])
        if self.dragging:
            dx, dy = self.drag_offset
            nx, ny = e.x - dx, e.y - dy
            self.search_box_pos = [nx, ny]
            self.canvas.coords(self.search_ui["box"], nx, ny, nx + self.search_box_size[0], ny + self.search_box_size[1])
            self.canvas.coords(self.search_ui["text"], nx + 10, ny + 15)
            self.update_search_box()
        elif self.resizing:
            ox, oy = self.drag_offset
            new_w = max(200, e.x + ox - x1)
            new_h = max(40, e.y + oy - y1)
            self.search_box_size = [new_w, new_h]
            self.canvas.coords(self.search_ui["box"], x1, y1, x1 + new_w, y1 + new_h)
            self.update_search_box()

    def on_mouse_move(self, e):
        if not self.search_active or not self.search_ui:
            self.root.config(cursor="")
            return
        x1, y1, x2, y2 = self.canvas.coords(self.search_ui["box"])
        if x2 - 10 <= e.x <= x2 and y2 - 10 <= e.y <= y2:
            self.root.config(cursor="sizing")
        elif x1 <= e.x <= x2 and y1 <= e.y <= y2:
            self.root.config(cursor="fleur")
        else:
            self.root.config(cursor="")

# --- run
if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("800x600")
    app = ImageViewer(root)

    root.mainloop()