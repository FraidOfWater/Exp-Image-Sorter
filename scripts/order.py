import os
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import concurrent.futures

class ResponsiveReorderer:
    def __init__(self, root, directory):
        self.root = root
        self.root.title("Responsive Image Organizer")
        self.root.geometry("1250x900")
        self.root.configure(bg="#1a1a1a")
        self.root.update()

        self.directory = directory
        self.valid_exts = ('.png', '.jpg', '.jpeg', '.bmp', '.webp')
        self.image_paths = [os.path.join(directory, f) for f in os.listdir(directory) 
                            if f.lower().endswith(self.valid_exts)]
        self.image_paths.sort()
        
        # --- FIXED GEOMETRY SETTINGS ---
        self.thumb_max_size = (160, 160)
        self.cell_w = 160  # Fixed slot width
        self.cell_h = 190  # Fixed slot height
        self.cols = 1      # Will be calculated dynamically
        
        self.widgets = [] 
        self.dragging_item = None
        self.ghost = None

        self.setup_ui()
        self.load_images_async()
        
        # Bind resize event
        self.on_window_resize()
        self.root.bind("<Configure>", self.on_window_resize)

    def setup_ui(self):
        header = tk.Frame(self.root, bg="#252526", height=50)
        header.pack(side=tk.TOP, fill=tk.X)
        header.pack_propagate(False)

        self.save_btn = tk.Button(header, text="SAVE ORDER", command=self.save_changes, 
                                  bg="#007acc", fg="white", font=("Arial", 9, "bold"),
                                  relief=tk.FLAT, state=tk.DISABLED, padx=20)
        self.save_btn.pack(side=tk.RIGHT, padx=20, pady=8)

        self.canvas = tk.Canvas(self.root, bg="#1a1a1a", highlightthickness=0)
        self.scroll_y = tk.Scrollbar(self.root, orient="vertical", command=self.canvas.yview)
        self.container = tk.Frame(self.canvas, bg="#1a1a1a")

        self.canvas.create_window((0, 0), window=self.container, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scroll_y.set)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        self.root.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

    def load_images_async(self):
        def load_proc(path):
            try:
                img = Image.open(path).convert("RGB")
                img.thumbnail(self.thumb_max_size, Image.Resampling.LANCZOS)
                return path, img
            except: return path, None

        with concurrent.futures.ThreadPoolExecutor() as executor:
            results = list(executor.map(load_proc, self.image_paths))
            
            for path, img_obj in results:
                if not img_obj: continue
                photo = ImageTk.PhotoImage(img_obj)
                
                frame = tk.Frame(self.container, bg="#1a1a1a", width=self.cell_w, height=self.cell_h)
                frame.pack_propagate(False) 
                
                img_container = tk.Frame(frame, bg="#1a1a1a", height=self.thumb_max_size[1] + 10)
                img_container.pack(fill=tk.X, side=tk.TOP)
                img_container.pack_propagate(False)

                lbl = tk.Label(img_container, image=photo, bg="#2d2d2d", bd=0, cursor="fleur")
                lbl.image = photo 
                lbl.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
                
                name_lbl = tk.Label(frame, text=os.path.basename(path)[:18], 
                                    fg="#888888", bg="#1a1a1a", font=("Arial", 8))
                name_lbl.pack(side=tk.TOP, pady=2)

                lbl.bind("<ButtonPress-1>", self.start_drag)
                lbl.bind("<B1-Motion>", self.do_drag)
                lbl.bind("<ButtonRelease-1>", self.stop_drag)
                
                self.widgets.append({'path': path, 'frame': frame, 'label': lbl})
        
        self.save_btn.config(state=tk.NORMAL)
        self.render_grid()

    def on_window_resize(self, event=None):
        # Only trigger if the main window resized
        if event == None or event.widget == self.root:
            new_cols = max(1, self.canvas.winfo_width() // self.cell_w)
            if new_cols != self.cols:
                self.cols = new_cols
                self.render_grid()

    def render_grid(self):
        """Dynamic grid placement based on calculated columns."""
        for i, item in enumerate(self.widgets):
            item['frame'].grid(row=i // self.cols, column=i % self.cols, padx=2, pady=2)
        
        self.container.update_idletasks()
        self.canvas.config(scrollregion=self.canvas.bbox("all"))

    # --- DRAG LOGIC ---
    def start_drag(self, event):
        clicked_widget = event.widget
        self.dragging_item = next(item for item in self.widgets if item['label'] == clicked_widget)
        self.dragging_item['label'].config(bg="#007acc")

        self.ghost = tk.Toplevel()
        self.ghost.overrideredirect(True)
        self.ghost.attributes("-alpha", 0.7)
        self.ghost.attributes("-topmost", True)
        
        g_lbl = tk.Label(self.ghost, image=self.dragging_item['label'].image, bg="#007acc", bd=1)
        g_lbl.pack()
        self.do_drag(event)

    def do_drag(self, event):
        if self.ghost:
            self.ghost.geometry(f"+{event.x_root+15}+{event.y_root+15}")

    def stop_drag(self, event):
        if self.ghost:
            self.ghost.destroy()
            self.ghost = None
        
        self.dragging_item['label'].config(bg="#2d2d2d")
        target_widget = self.root.winfo_containing(event.x_root, event.y_root)
        
        try:
            target_frame = None
            curr = target_widget
            while curr and curr != self.container:
                if curr in [w['frame'] for w in self.widgets]:
                    target_frame = curr
                    break
                curr = curr.master

            if target_frame:
                start_idx = self.widgets.index(self.dragging_item)
                target_item = next(item for item in self.widgets if item['frame'] == target_frame)
                new_idx = self.widgets.index(target_item)
                
                if start_idx != new_idx:
                    item = self.widgets.pop(start_idx)
                    self.widgets.insert(new_idx, item)
                    self.render_grid()
        except:
            pass

    def save_changes(self):
        if not messagebox.askyesno("Confirm", "Rename files?"): return
        try:
            for i, item in enumerate(self.widgets):
                old_path = item['path']
                folder, filename = os.path.split(old_path)
                if "_" in filename and filename[:4].isdigit(): filename = filename[5:]
                new_path = os.path.join(folder, f"{i:04d}_{filename}")
                if old_path != new_path:
                    os.rename(old_path, new_path)
                    item['path'] = new_path
            messagebox.showinfo("Success", "Files renamed!")
        except Exception as e:
            messagebox.showerror("Error", str(e))

if __name__ == "__main__":
    root = tk.Tk()
    path = os.getcwd()
    input_dir = os.path.join(os.getcwd(), "sorted_by_color_histogram")
    input_dir = input_dir if os.path.exists(input_dir) else path
    
    if os.path.exists(input_dir):
        app = ResponsiveReorderer(root, input_dir)
        root.mainloop()
