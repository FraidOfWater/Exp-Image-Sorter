import os
import tkinter as tk

class ImageViewer:
    def __init__(self, root):
        self.root = root
        self.canvas = None

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
        self.recent_searches = []
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

    # ----------------------------
    # Basic display
    # ----------------------------
    def new_canvas(self, canvas):
        print("new canvas binding")
        "make new canvas according to what navigator says is current viewer"
        self.canvas = canvas
        # bindings
        if "middlepane" in canvas._w:
            root = canvas.master.master.master
        else:
            root = canvas.master.master
            canvas.master.bind("<Control-a>", self.clear_search)
            canvas.master.bind("<Control-i>", self.show_hotkeys)

            canvas.master.bind("<Key>", self.on_key_press)
            canvas.master.bind("<Key>", self.on_key_press)
        root.bind("<Control-a>", self.clear_search)
        root.bind("<Control-i>", self.show_hotkeys)

        root.bind("<Key>", self.on_key_press)
        root.bind("<Key>", self.on_key_press)
        
        self.search_active = False
        self.search_minimized = False
        self.search_ui.clear()
        self.search_text = ""

        # mouse events
        #self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        #self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        #self.canvas.bind("<B1-Motion>", self.on_mouse_drag)

        self.display_instructions()

    def display_instructions(self):
        self.canvas.delete("sorter")
        msg = "Press Spacebar to activate search.\nType to search.\n↑, ↓ to Navigate.\nEnter to Confirm.\nCtrl+a to Clear.\nEscape to Exit."
        self.canvas.create_text(
            self.canvas.winfo_width()//2,
            self.canvas.winfo_height()//2,
            text=msg, tags="sorter", fill="white", font=("Arial", 14), justify="center"
        )

    def close(self):
        if ".!toplevel" in self.root._w:
            self.canvas.destroy()
    
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
        #hotkeys.clear()
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
            t = self.canvas.create_text(x + 10, y + y_offset, anchor="nw", tags="sorter", text=f"{k}: {os.path.basename(v[1])}",
                                        fill="white", font=("Arial", 12))
            items.append(t)
            y_offset += 24

        # Resize box to fit content
        new_h = max(60, y_offset + 10)
        self.canvas.coords(bg, x, y, x + w, y + new_h)
        self.hotkey_box = {"box": bg, "title": title, "items": items}
        self.hotkey_box_size[1] = new_h

    # ----------------------------
    # Folder logic
    # ----------------------------
    def set_inclusion(self, inclusion):
        folder = os.path.normpath(inclusion)
        if folder:
            self.include_folder = folder
            self.search_memory.clear()
            self.recent_searches.clear()
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
                print(d, rel)
        pass

    # ----------------------------
    # Search logic
    # ----------------------------
    def on_key_press(self, e):
        def select_result():
            name, rel = self.search_results[self.locked_search_index]
            partial = rel
            full_path = os.path.join(self.include_folder, partial)
            print(f"Selected folder: {full_path}")
            print("1", name, rel, full_path)
            self.root.fileManager.setDestination({"path": full_path, "color": "#FFFFFF"}, caller="sorter")
            self.root.gui.folder_explorer.set_current(full_path)
            print(name, rel, full_path)
            

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
        if (not self.search_active and e.keysym in ("space", "Tab")): # or (not self.search_active and not self.hotkey_active and len(e.char) == 1 and e.char.isprintable()):
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
                        full_path = os.path.join(self.include_folder, name[1])
                        print(f"Selected folder: {name}")
                        print("ERROR INVESTIAGTE")
                        self.root.gui.fileManager.setDestination({"path": full_path, "color": "#FFFFFF"}, caller="sorter")
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
                    if self.search_results[self.selected_index] in self.recent_searches:
                        self.recent_searches.remove(self.search_results[self.selected_index])
                    self.recent_searches.append(self.search_results[self.selected_index])
                    if len(self.recent_searches) > 100:
                        self.recent_searches.pop(0)

                    
                    self.locked_search_index = self.selected_index

                    # partial like flu, flut, flutt or t, cel will know what full path they should be.
                    for i in range(1, len(self.search_text)+1):
                        self.search_memory[self.search_text[:i]] = self.recent_searches[-1]
                    self.search_text = self.recent_searches[-1][0]

                    self.hotkeys[self.search_text[0]] = self.recent_searches[-1]
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
        # 1. Handle Empty Search (History View)
        if not q:
            self.search_results = list(reversed(self.recent_searches))
            # Add everything else, avoiding duplicates
            seen = set(self.search_results)
            for item in self.cached_dirs:
                if item not in seen:
                    self.search_results.append(item)
            self.update_search_box()
            return

        # 2. Filtering Phase
        filtered_cache = []
        is_path_search = "\\" in q or "/" in q
        clean_q = q.replace("/", "").replace("\\", "").lower()

        for name, rel_path in self.cached_dirs:
            # Check if all terms in 'qs' match
            match = True
            for term in qs:
                term = term.lower()
                if is_path_search:
                    if term not in rel_path.lower():
                        match = False; break
                else:
                    if term not in name.lower():
                        match = False; break
            
            if match:
                filtered_cache.append((name, rel_path))

        # 3. Sorting Phase (Base Sorting)
        # Sort by: 1. Path Depth (shallow first), 2. Name Length, 3. Alphabetical
        filtered_cache.sort(key=lambda x: (len(x[1].split("\\")), len(x[0]), x[0]))

        # 4. Prioritization Phase (The "Recents on Top" logic)
        # Move matching items that are in 'recent_searches' to the very top
        final_results = []
        recent_paths = [r for n, r in self.recent_searches]
        
        # First, pull matches that were recently used
        matching_recents = [item for item in filtered_cache if item[1] in recent_paths]
        partial_result = self.search_memory.get(self.search_text, None) # what the partial search points to
        if partial_result:
            for i in range(0, len(matching_recents)):
                if partial_result[1] == matching_recents[i][1]:
                    matching_recents.pop(i)
                    matching_recents.append(partial_result)
                    break
        matching_recents.reverse()
        # Second, everything else
        other_matches = [item for item in filtered_cache if item[1] not in recent_paths]

        self.search_results = matching_recents + other_matches

        # 5. Handle Selection Index
        # If the previous selection is still in the new list, try to keep it.
        # Otherwise, default to 0.
        if not self.search_results:
            self.selected_index = 0
        elif self.selected_index >= len(self.search_results):
            self.selected_index = 0

        self.update_search_box()
    
    def navigate(self, direction):
        if not self.search_results: return
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
    
    def bring_forth(self):
        if self.search_ui:
            self.canvas.lift(self.search_ui["box"])
            self.canvas.lift(self.search_ui["text"])
            for x in self.search_ui.get("results", []):
                self.canvas.lift(x)

    def update_search_box(self):
        if not self.search_ui:
            return

        x1, y1 = self.search_box_pos
        w = self.search_box_size[0]
        
        # 1. Handle Minimized State
        if self.search_minimized:
            h = 40
            self.canvas.coords(self.search_ui["box"], x1, y1, x1 + w, y1 + h)
            self.canvas.itemconfig(self.search_ui["text"], text=f"> {self.search_text}")
            # Hide pool items instead of deleting
            for item_id in self.search_ui.get("results", []):
                self.canvas.itemconfigure(item_id, state='hidden')
            return

        # 2. Calculate Dimensions (Matches your original math exactly)
        visible_count = min(len(self.search_results), self.max_visible)
        total_height = 40 + visible_count * 34
        self.canvas.coords(self.search_ui["box"], x1, y1, x1 + w, y1 + total_height)
        self.search_box_size[1] = total_height # Sync size variable
        self.canvas.itemconfig(self.search_ui["text"], text=f"> {self.search_text}")

        # 3. Manage the Pool (The Performance Boost)
        needed_pool_size = self.max_visible * 2
        if "results" not in self.search_ui:
            self.search_ui["results"] = []

        # Only create if we don't have enough; never delete
        while len(self.search_ui["results"]) < needed_pool_size:
            # Create as hidden placeholders
            tid = self.canvas.create_text(0, 0, anchor="nw", tags="sorter", state='hidden')
            self.search_ui["results"].append(tid)

        # 4. Update the Content
        start = self.scroll_offset
        end = start + visible_count
        y = y1 + 35
        
        pool = self.search_ui["results"]
        
        for i in range(self.max_visible):
            name_id = pool[i * 2]
            rel_id = pool[i * 2 + 1]
            
            result_idx = start + i
            if result_idx < len(self.search_results) and i < visible_count:
                name, rel = self.search_results[result_idx]
                fg = "#00ff99" if result_idx == self.selected_index else "white"
                
                # Update Name (Explicitly stating font to prevent "fucking up")
                self.canvas.coords(name_id, x1 + 10, y)
                self.canvas.itemconfig(name_id, text=name, fill=fg, 
                                    font=("Arial", 12, "bold"), state='normal')
                
                # Update Relation
                self.canvas.coords(rel_id, x1 + 15, y + 18)
                self.canvas.itemconfig(rel_id, text=rel, fill="#888", 
                                    font=("Arial", 9), state='normal')
                y += 34
            else:
                # Hide unused pool items
                self.canvas.itemconfigure(name_id, state='hidden')
                self.canvas.itemconfigure(rel_id, state='hidden')

        # Ensure search box is always on top
        #self.bring_forth()

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
            # Update the position variable
            self.search_box_pos = [e.x - dx, e.y - dy]
            # Redraw using the new fast pool logic
            self.update_search_box()
            
        elif self.resizing:
            ox, oy = self.drag_offset
            self.search_box_size[0] = max(200, e.x + ox - x1)
            self.update_search_box()

# --- run
if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("800x600")
    app = ImageViewer(root)

    root.mainloop()
