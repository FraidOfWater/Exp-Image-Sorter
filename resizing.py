import vlc, tkinter as tk, numpy as np, math, os, json, queue
from time import perf_counter
from PIL import Image, ImageTk
from collections import OrderedDict
from threading import Thread, Lock, Event
from tkinter import ttk
from sorter import ImageViewer
Image.MAX_IMAGE_PIXELS = 346724322
vipsbin = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vips-dev-8.17", "bin")
os.environ['PATH'] = os.pathsep.join((vipsbin, os.environ['PATH']))
os.add_dll_directory(vipsbin)
import pyvips

class AsyncImageLoader:
    def __init__(self, viewer):
        self.viewer = viewer
        self.queue = queue.Queue()
        self.thread = Thread(target=self._worker, name="(Thread) Viewer Asynch Tasks", daemon=True)
        self.stop_flag = False
        self.thread.start()  # Only one thread ever

    def _worker(self):
        while not self.stop_flag:
            try:
                path, token = self.queue.get(timeout=0.1)
                # Skip any older queued requests
                while not self.queue.empty():
                    path, token = self.queue.get_nowait()
                
                if token != self.viewer.current_load_token or not path:
                    continue

                img = self.viewer._load_full_image_in_background(path)

                # hand off to main thread
                self.viewer.master.after(0, lambda p=path, i=img, t=token: self.viewer._on_async_image_ready(p, i, t))

            except queue.Empty:
                continue
            except Exception as e:
                print("Async loader error:", e)

    def request_load(self, path):
        token = object()
        self.viewer.current_load_token = token
        self.queue.put((path, token))

    def stop(self):
        self.stop_flag = True
        self.queue.put((None, None))

from collections import OrderedDict
class LRUCache(OrderedDict):
    """A lightweight LRU (Least Recently Used) cache with adjustable maxsize."""
    
    def __init__(self, maxsize=128, name="default"):
        super().__init__()
        self.maxsize = maxsize
        self.name = name

    def __getitem__(self, key):
        """Get an item and mark it as recently used."""
        if key not in self: return None
        value = super().__getitem__(key)
        self.move_to_end(key)
        return value

    def __setitem__(self, key, value):
        """Insert/Update an item and enforce maxsize."""
        if self.maxsize == 0: return
        if key in self:
            self.move_to_end(key)
        super().__setitem__(key, value)
        self._enforce_limit()
    
    def _enforce_limit(self):
        """Ensure cache size does not exceed maxsize."""
        while len(self) > self.maxsize:
            item = self.popitem(last=False)  # remove least recently used (oldest)
            pass

    def set_maxsize(self, new_maxsize: int):
        """Change maxsize dynamically and trim if needed."""
        self.maxsize = new_maxsize
        self._enforce_limit()

    def last(self):
        """Return (key, value) of the most recently used item."""
        try:
            key = next(reversed(self))
            return key, self[key]
        except StopIteration:
            raise KeyError("Cache is empty")

    def __repr__(self):
        return f"<LRUCache size={len(self)}/{self.maxsize}>"

from tkinter import simpledialog
class PrefilledInputDialog(simpledialog.Dialog):
    def __init__(self, parent, title, message, default_text=""):
        self.message = message
        self.default_text = default_text
        self.result = None
        super().__init__(parent, title)

    def body(self, master):
        base_name = os.path.basename(self.default_text)
        if base_name.startswith(".") and "." not in base_name[1:]:
            name_part, ext_part = base_name, ""
        elif "." in base_name:
            name_part, ext_part = base_name.rsplit(".", 1)
            ext_part = "." + ext_part
        else:
            name_part, ext_part = base_name, ""

        tk.Label(master, text=self.message, justify="left", wraplength=300).pack(padx=10, pady=(10, 5))

        frame = tk.Frame(master)
        frame.pack(padx=10, pady=(0, 10))

        self.entry = tk.Entry(frame, width=30)
        self.entry.insert(0, name_part)
        self.entry.pack(side="left")

        tk.Label(frame, text=ext_part, width=len(ext_part) + 1, anchor="w").pack(side="left")

        self.ext_part = ext_part
        return self.entry  # initial focus

    def apply(self):
        name = self.entry.get().strip()
        if not name:
            self.result = None
        else:
            self.result = name + self.ext_part

class Application(tk.Frame):
    class VlcPlayer:
        """Handles VLC video playback and GUI embedding"""
        def __init__(self, app, geometry, path, info=None):
            self.last_click = perf_counter()
            self.f = True
            self._last_seek_time = 0
            self.app = app
            w, h = geometry.split('x', 1)
            self.w = int(w)
            self.h = int(h)
            if self.app.statusbar.get():
                self.h -= 25
            
            self.path = path
            self.info = info

            do_pack = False
            if app.vlc_frame is None:
                app.vlc_frame = ttk.Frame(app.master, style="bg.TFrame")
                do_pack = True

            self.canvas = tk.Canvas(
                app.vlc_frame,
                bg="black",
                highlightthickness=0,
                width=self.w,
                height=self.h
            )
            self.canvas.grid(row=0, column=0)

            self.handle_video()
            if do_pack:
                self.pack()
        
        def return_dimensions(self):
            try:
                w = self.player.video_get_width()
                h = self.player.video_get_height()
                return w, h
            except:
                return 0, 0
        
        def handle_video(self):
            """Set up VLC playback"""
            self.pressed = False
            self.vlc_instance = self.app.vlc_instance
            self.media_list_player = self.vlc_instance.media_list_player_new()
            self.media_list = self.vlc_instance.media_list_new()
            self.media = self.vlc_instance.media_new(self.path)
            self.media_list.add_media(self.media)
            self.media_list_player.set_media_list(self.media_list)
            self.player = self.media_list_player.get_media_player()
            self.events = self.player.event_manager()
            
            new_width = self.w
            new_height = self.h - 35

            self.video_container = tk.Frame(
                self.canvas,
                bg="black",
                width=self.w,
                height=self.h
            )
            self.video_container.grid_propagate(False)
            self.video_container.grid(row=0, column=0, sticky="nsew")

            self.video_frame = tk.Canvas(
                self.video_container,
                width=new_width,
                height=new_height,
                bg="black",
                highlightbackground="black",
                highlightthickness=0,
                borderwidth=0
            )
            self.video_frame.grid(row=0, column=0)

            self.controls_frame = tk.Frame(self.video_container, bg="black")
            self.controls_frame.grid(row=1, column=0, sticky="ew")
            self.controls_frame.grid_remove()
            self.controls_frame.columnconfigure(0, weight=30)
            self.controls_frame.columnconfigure(1, weight=1)

            self.timeline_slider = ttk.Scale(
                self.controls_frame,
                from_=0,
                to=self.media.get_duration(),
                orient=tk.HORIZONTAL,
                style="Horizontal.TScale"
            )
            self.timeline_slider.grid(row=0, column=0, sticky="ew", padx=(5,2), pady=5)

            def timeline_click(event):
                self.pressed = True
                slider = event.widget
                from_ = float(slider.cget("from"))
                to = float(slider.cget("to"))
                slider_width = slider.winfo_width()

                click_fraction = event.x / slider_width
                new_value = from_ + (to - from_) * click_fraction

                slider.set(new_value)
                self.seek_video(new_value)

            def on_drag(event):
                slider = event.widget
                from_ = float(slider.cget("from"))
                to = float(slider.cget("to"))
                slider_width = slider.winfo_width()

                x = max(0, min(event.x, slider_width))
                fraction = x / slider_width
                new_value = from_ + (to - from_) * fraction

                slider.set(new_value)       # move handle to cursor
                self.seek_video(new_value)  # update video

            def on_release(event):
                self.pressed = False

            def on_scroll(event):
                if event.state == 2:
                    return
                ctrl_pressed = (event.state & 0x0004) != 0
                step_volume = 2
                step_seek = 300  # milliseconds to jump per scroll tick

                delta = int(event.delta / 120) if event.delta else 0
                if delta == 0:
                    return

                if ctrl_pressed:
                    # Seek video
                    self.pressed = True
                    current_time = self.player.get_time()
                    new_time = current_time + delta * step_seek
                    duration = self.media.get_duration()
                    new_time = max(0, min(duration, new_time))
                    self.timeline_slider.set(new_time)
                    self.seek_video(new_time)
                else:
                    # Change volume
                    new_volume = self.app.volume + delta * step_volume
                    new_volume = max(0, min(100, new_volume))
                    self.volume_slider.set(new_volume)
                    self.change_volume(new_volume)

            # Bindings
            # puts overlay to capture bindings from vlc.
            self.overlay = tk.Frame(self.video_frame, bg="", width=self.w, height=self.h)
            self.overlay.place(x=0, y=0)
            
            self.overlay.bind("<MouseWheel>", on_scroll)

            self.timeline_slider.bind("<Button-1>", timeline_click)
            self.timeline_slider.bind("<B1-Motion>", on_drag)
            self.timeline_slider.bind("<ButtonRelease-1>", on_release)
            self.overlay.bind("<KeyRelease-Control_L>", on_release)
            self.overlay.bind("<KeyRelease-Control_R>", on_release)
            self.overlay.bind("<Button-1>", self.toggle_pause)
            # Bind hover events to the overlay
            self.video_container.bind("<Enter>", self.show)
            self.video_container.bind("<Leave>", self.hide)

            # Volume slider
            self.volume_slider = ttk.Scale(
                self.controls_frame,
                from_=0,
                to=100,
                orient=tk.HORIZONTAL,
                style="Horizontal.TScale",
                command=self.change_volume
            )
            self.volume_slider.set(self.app.volume)
            self.volume_slider.grid(row=0, column=1, sticky="ew", padx=(2, 5), pady=5)

            def volume_click(event):
                slider = event.widget
                slider_width = slider.winfo_width()
                click_fraction = event.x / slider_width
                new_value = float(slider.cget("from")) + (float(slider.cget("to")) - float(slider.cget("from"))) * click_fraction
                slider.set(new_value)
                self.change_volume(new_value)

            self.volume_slider.bind("<Button-1>", volume_click)

            self.player.set_fullscreen(True)
            self.video_frame_id = self.video_frame.winfo_id()
            self.player.set_hwnd(self.video_frame_id)

            self.media_list_player.set_playback_mode(vlc.PlaybackMode.loop)
            self.media_list_player.play()

            self.events.event_attach(vlc.EventType.MediaPlayerPlaying, self.ready)

            self.disable = False
        
        def toggle_pause(self, event=None):
            if perf_counter() - self.last_click <= 0.25:
                self.last_click = perf_counter()-0.5
                pass
            else:
                self.last_click = perf_counter()
                return
            if self.player:
                if self.player.is_playing():
                    self.player.pause()
                    self.controls_frame.config(bg="red")
                    self.timeline_slider.config(style="theme.Horizontal.TScale")
                    self.timeline_slider.config(style="theme.Horizontal.TScale")
                    self.volume_slider.config(style="theme.Horizontal.TScale")
                else:
                    self.player.play()
                    self.controls_frame.config(bg="black")
                    self.timeline_slider.config(style="Horizontal.TScale")
                    self.volume_slider.config(style="Horizontal.TScale")
        
        def ready(self, event):
            self.canvas.after_idle(self.update_timeline_slider)
            self.canvas.after_idle(self.update_info) 

        def update_info(self):
            if self.f:
                self.f = False
                if self.info:
                    w, h = self.return_dimensions()
                    text = f"{w}x{h}"
                    self.info.set(f"{text:^11}")

        def update_slider_position(self):
            try:
                if hasattr(self, "player") and self.player.is_playing():
                    if not self.pressed:
                        self.timeline_slider.set(self.player.get_time())
                    self.canvas.after(200, self.update_slider_position)
            except:
                pass

        def update_timeline_slider(self):
            try:
                duration = self.media.get_duration()
                self.timeline_slider.config(to=duration)
                self.update_slider_position()
            except:
                pass

        def seek_video(self, value, event=None):
            if perf_counter() - self._last_seek_time > 0.05:  # 100 ms throttle
                pass
            else:
                return
            self._last_seek_time = perf_counter()
            self.player.set_time(int(float(value)))

        def change_volume(self, value):
            new_volume = int(float(value))
            self.player.audio_set_volume(new_volume)
            self.app.volume = new_volume

        def pack(self, **kw):
            self.app.canvas.pack_forget()
            self.app.vlc_frame.pack(expand=True, fill=tk.BOTH)
            self.app.vlc_frame.bind("<Configure>", self.app.window_resize)
            self.app.master.update()

        def destroy(self, threaded=True):
            #self.player.set_hwnd(0)
            self.player.stop()
            self.player.release()
            if getattr(self, "events", None):
                self.events.event_detach(vlc.EventType.MediaPlayerPlaying)
                self.events.event_detach(vlc.EventType.MediaPlayerEndReached)

            if getattr(self, "media_list_player", None):
                self.media_list_player.stop()
                self.media_list_player.release()
                self.media_list_player = None

            if getattr(self, "media", None):
                self.media = None


            if getattr(self, "media_list", None):
                self.media_list.release()
                self.media_list = None

            self.events = None

            if self.video_frame:
                self.video_frame.grid_forget()
                self.video_frame.destroy()
            if self.canvas:
                self.canvas.destroy()

            self.player = None
            self.media_list_player = None
            self.media_list = None
            self.media = None
            self.events = None

        def hide(self, event=None):
            try:
                self.controls_frame.grid_remove()
            except:
                pass

        def show(self, event):
            try:
                self.controls_frame.grid()
            except:
                pass

    BUTTON_MODIFIER_CTRL = 1
    BUTTON_MODIFIER_CTRL_LEFT_CLICK = 257
    BUTTON_MODIFIER_RIGHT_CLICK = 1024
    LAST_USED_CACHED_IMG = None
    
    QUALITY = {
            "Nearest": Image.Resampling.NEAREST,
            "Bilinear": Image.Resampling.BILINEAR,
            "Bicubic": Image.Resampling.BICUBIC,
            "Lanczos": Image.Resampling.LANCZOS,
            "Pyvips": "pyvips"
        }
    
    def __init__(self, master=None, 
                 geometry: str=None, lastdir: str=None, 
                 zoom_magnitude: float=None, rotation_degrees: int=None, unbound_var: bool=None, 
                 disable_menubar: bool=None, statusbar: bool=None, 
                 initial_filter: Image.Resampling=None, drag_quality: Image.Resampling=None, anti_aliasing: bool=None, thumbnail_var: str=None,
                 filter_delay: int=None, show_advanced: bool=None, quick_render: bool=None,
                 show_ram: bool=None,
                 canvas_color=None, text_color=None, 
                 button_color=None, active_button_color=None, 
                 statusbar_color=None, volume=None, savedata={}, gui=None):
        
        self.current_load_token = None
        self.loader = AsyncImageLoader(self)
        self.draw_queue = []
        self.undo = []
        self.debug = []
        self.filename = None
        self.timer = Timer()
        self.timer.start()
        self.gui = gui
        self.savedata = savedata
        self.f = True

        self.save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "viewer_prefs.json")
        if not savedata: 
            savedata = self.load_json()
            self.savedata = savedata
        
        self.lastdir = lastdir or savedata.get("lastdir", None)

        self.standalone = True if master == None else False
        self.title = "Python Media Viewer"
        self.a = False
        if self.standalone:
            if gui:
                master = tk.Toplevel()
            else:
                master = tk.Tk()
                master.bind('<KeyPress-Left>', lambda e: self.key_press(-1))
                #master.bind('<KeyPress-Down>', lambda e: self.key_press(-1))
                master.bind('<KeyPress-Right>', lambda e: self.key_press(1))
                #master.bind('<KeyPress-Up>', lambda e: self.key_press(1))
                master.bind('<F2>', lambda e: self.rename())
                master.bind('<Delete>', lambda e: self.trash())
                master.bind('<Control-z>', lambda e: self.on_ctrl_z())
                master.bind('<Control-Z>', lambda e: self.on_ctrl_z())
            master.geometry(geometry or savedata.get("geometry", None) or "800x600")
            master.title(self.title)
            master.protocol("WM_DELETE_WINDOW", self.window_close)

        if True:
            self.zoom_magnitude = zoom_magnitude or float(savedata.get("zoom_magnitude", 1.25))
            self.rotation_degrees = rotation_degrees or int(savedata.get("rotation_degrees", -5))

            self.unbound_var = tk.BooleanVar(value=unbound_var or savedata.get("unbound_pan", False))

            self.disable_menubar = disable_menubar or savedata.get("disable_menubar", False)
            self.statusbar = statusbar or tk.BooleanVar(value=savedata.get("statusbar", True))
            self.statusbar.trace_add("write", lambda *_: self.toggle_statusbar())

            self.filter = initial_filter or Application.QUALITY.get(savedata.get("filter", "Nearest").lower().capitalize())
            self.drag_quality = drag_quality or Application.QUALITY.get(savedata.get("drag_quality", "Nearest").lower().capitalize())
            self.quick_render = tk.BooleanVar(value=quick_render or savedata.get("quick_render", True))
            self.anti_aliasing = tk.BooleanVar(value=anti_aliasing or savedata.get("anti_aliasing", True))
            self.anti_aliasing.trace_add("write", lambda *_: (self._zoom_cache.clear(), self._imagetk_cache.clear(), self.draw_image(self.pil_image)))
            self.thumbnail_var = tk.StringVar(value=thumbnail_var or savedata.get("thumbnail_var", "Quality"))
            self.filter_delay = tk.IntVar(value=filter_delay or int(savedata.get("final_filter_delay", 200)))
            self.show_advanced = tk.BooleanVar(value=show_advanced or savedata.get("show_advanced", False))
            self.show_advanced.trace_add("write", lambda *_: self.toggle_advanced())
            self.show_ram = tk.BooleanVar(value=show_ram or savedata.get("show_ram", False))
            self.show_ram.trace_add("write", lambda *_: self.toggle_ram_indicator())
            self.volume = volume or int(savedata.get("volume", 50))
                    
            self.colors = savedata.get("colors", {
                    "canvas": "#303276" or canvas_color, #141433
                    "statusbar": "#202041" or statusbar_color,
                    "button": "#24255C" or button_color,
                    "active_button": "#303276" or active_button_color,
                    "text": "#FFFFFF" or text_color
                    } or #white
                    {
                    "canvas": "#000000",
                    "statusbar": "#f0f0f0",
                    "button": "#f0f0f0",
                    "active_button": "#f0f0f0",
                    "text": "#000000"
                    }
                )
        self.bg_color = tuple(int(self.colors["canvas"][i:i+2], 16) for i in (1, 3, 5)) + (0,)
        super().__init__(master, bg=self.colors["canvas"])
        self.master = master

        self.style = ttk.Style()
        self.style.configure("bg.TFrame", background="black")
        self.style.configure("Horizontal.TScale", background="black")
        self.style.configure("theme.Horizontal.TScale", background="red")

        self.config(bg=self.colors["canvas"])
        self.master.configure(bg=self.colors["canvas"])
        self.pil_image = None
        self._last_draw_time = 0.0
        self.image_id = None
        self.drag_buffer = None
        self.save = None
        self.save1 = None
        self.memory_after_id = None
        self.gif_after_id = None
        self.gif_gen_after_id = None
        self.draw_img_id = None
        
        self._zoom_cache = LRUCache(maxsize=32, name="zoom") # saved zoom levels
        self._imagetk_cache = LRUCache(maxsize=0, name="imagetk") # saved gif imagetks.

        self.vlc_instance = vlc.Instance()
        self.vlc_frame = None
        self.old = None

        self._old = None
        self.frames = []
        self._frame_lock = Lock()
        self.lazy_index = 0
        self.scale_key = None
        self.dragging = False
        self.open_thread = None
        self._stop_thread = Event()
        self.is_gif = False
        self.first_render_info = None

        self.filenames = []
        self.filename_index = 0

        if savedata == {}: self.save_json()
        self.reset_transform()
        self.create_widgets()
    
    "UI creation"
    def create_widgets(self):
        self.create_menu()
        self.create_status_bar()
        self.create_canvas()
        self.bind_mouse_events()

    def create_menu(self):
        def hints():
            def on_resize(e):
                new_width = max(e.width - 20, 20)
                self.label.config(wraplength=new_width)

            height = 300
            width = int(height * 1.85)
            new = tk.Toplevel(self.master, width=width, height=height, bg=self.colors["canvas"])
            new.transient(self.master)
            new.geometry(f"{width}x{height}+{int(self.master.winfo_width()/2-width/2)}+{int(self.master.winfo_height()/2-height/2)}")
            new.grid_rowconfigure(0, weight=1)
            new.grid_columnconfigure(0, weight=1)
            text = """Small guide:
            
    Double-click: "Center & Resize."
    Shift or Right-click + Mouse-wheel: "Rotate."

    Show Advanced:
    Drag: The quality of the render while resizing canvas.
    Delay: The full quality is render after this delay.
                """

            self.label = tk.Label(
                new,
                text=text,
                justify='left',
                anchor='nw', wraplength=height, bg=self.colors["canvas"], fg=self.colors["text"]
            )
            self.label.pack(fill='both', expand=False, padx=10, pady=10)
            new.bind('<Configure>', on_resize)

        menu_bar = tk.Menu(self.master)

        # File menu
        file_menu = tk.Menu(menu_bar, tearoff=tk.OFF)
        
        if not self.gui:
            menu_bar.add_cascade(label="File", menu=file_menu)
            file_menu.add_command(label="Open", command=self.menu_open_clicked, accelerator="Ctrl+O")
            
            file_menu.add_command(label="Open folder", command=self.menu_open_dir_clicked, accelerator="Ctrl+D")
            file_menu.add_separator()
            file_menu.add_command(label="Rename", command=self.rename, accelerator="F2")
            file_menu.add_command(label="Trash", command=self.trash, accelerator="Delete")
            file_menu.add_separator()
            file_menu.add_command(label="Exit", command=self.window_close)

        # View menu
        view_menu = tk.Menu(menu_bar, tearoff=tk.OFF)
        menu_bar.add_cascade(label="View", menu=view_menu)

        self.unbound_var = self.unbound_var
        view_menu.add_checkbutton(
            label="Unbound Pan",
            variable=self.unbound_var)
        
        view_menu.add_separator()
        
        view_menu.add_checkbutton(
            label="Quick render",
            variable=self.quick_render)
        
        view_menu.add_checkbutton(
            label="Anti-aliasing",
            variable=self.anti_aliasing)
        
        
        thumbnail_menu = tk.Menu(view_menu, tearoff=0)
        view_menu.add_cascade(label="Thumbnails", menu=thumbnail_menu)

        thumbnail_menu.add_radiobutton(label="No", value="No thumbs", variable=self.thumbnail_var)
        thumbnail_menu.add_radiobutton(label="Fast", value="Fast", variable=self.thumbnail_var)
        thumbnail_menu.add_radiobutton(label="Quality", value="Quality", variable=self.thumbnail_var)

        view_menu.add_checkbutton(
            label="Show Advanced",
            variable=self.show_advanced)
        
        view_menu.add_separator()

        view_menu.add_checkbutton(
            label="Statusbar",
            variable=self.statusbar)
        
        view_menu.add_checkbutton(
            label="Show RAM",
            variable=self.show_ram)
        
        view_menu.add_separator()

        view_menu.add_command(label="Hints", command=hints)
        
        self.master.bind_all("<Control-o>", self.menu_open_clicked)
        self.master.bind_all("<Control-d>", self.menu_open_dir_clicked)

        if not self.disable_menubar and self.master.config().get("menu"): # disable menubar for embedded view. (not supported)
            self.master.config(menu=menu_bar)

    def create_status_bar(self):  
        def get_memory_usage():
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            self.ram_indicator.config(text=f"RAM: {memory_info.rss / (1024 ** 2):.1f} MB")
            self.memory_after_id = self.after(500, get_memory_usage)

        frame_statusbar = tk.Frame(self.master, bd=1, relief=tk.SUNKEN, background=self.colors["statusbar"])
        self.frame_statusbar = frame_statusbar

        self.label_image_format_var = tk.StringVar(value="image info")
        self.label_image_mode_var = tk.StringVar(value="")
        self.label_image_dimensions_var = tk.StringVar(value="")
        self.label_image_size_var = tk.StringVar(value="")

        font = ("Consolas", 10)
        self.label_image_format = tk.Label(
            frame_statusbar, textvariable=self.label_image_format_var, anchor=tk.E, font=font,
            background=self.colors["statusbar"], foreground=self.colors["text"]
        )
        self.label_image_mode = tk.Label(
            frame_statusbar, textvariable=self.label_image_mode_var, anchor=tk.E, font=font,
            background=self.colors["statusbar"], foreground=self.colors["text"]
        )
        self.label_image_dimensions = tk.Label(
            frame_statusbar, textvariable=self.label_image_dimensions_var, anchor=tk.E, font=font,
            background=self.colors["statusbar"], foreground=self.colors["text"]
        )
        self.label_image_size = tk.Label(
            frame_statusbar, textvariable=self.label_image_size_var, anchor=tk.E, font=font,
            background=self.colors["statusbar"], foreground=self.colors["text"]
        )
        self.label_image_pixel = tk.Label(
            frame_statusbar, text="(x, y)", anchor=tk.W, padx=5,
            background=self.colors["statusbar"], foreground=self.colors["text"]
        )
        self.ram_indicator = tk.Label(
            frame_statusbar, text="RAM:", anchor=tk.W, padx=5,
            background=self.colors["statusbar"], foreground=self.colors["text"]
        )
        self.render_info = tk.Label(
            frame_statusbar, text="R:", anchor=tk.W, padx=5,
            background=self.colors["statusbar"], foreground=self.colors["text"]
        )
        self.anim_info = tk.Label(
            frame_statusbar, text="", anchor=tk.W, padx=5,
            background=self.colors["statusbar"], foreground=self.colors["text"]
        )
        
        options = ["Nearest", "Bilinear", "Bicubic", "Lanczos", "Pyvips"]
        self.selected_option = tk.StringVar(value=self.savedata.get("filter", "Nearest").lower().capitalize())
        
        self.selected_option.trace_add("write", lambda *_: (self._zoom_cache.clear(), self._imagetk_cache.clear(), setattr(self, "filter", Application.QUALITY[self.selected_option.get()]), self.draw_image(self.pil_image)))

        self.image_quality = tk.OptionMenu(frame_statusbar, self.selected_option, *options)
        self.image_quality.configure(
            background=self.colors["statusbar"],
            activebackground=self.colors["active_button"],
            foreground=self.colors["text"],
            activeforeground=self.colors["text"],
            highlightthickness=0,
            relief="flat",
            font=('Arial', 8),
            padx=5, pady=0
        )

        options1 = ["No thumbs", "Fast", "Quality"]
        self.thumb_quality = tk.OptionMenu(frame_statusbar, self.thumbnail_var, *options1)
        self.thumb_quality.configure(
            background=self.colors["statusbar"],
            activebackground=self.colors["active_button"],
            foreground=self.colors["text"],
            activeforeground=self.colors["text"],
            highlightthickness=0,
            relief="flat",
            font=('Arial', 8),
            padx=5, pady=0
        )

        # Advanced
        self.filter_delay_input_label = tk.Label(frame_statusbar, text="Delay:", anchor=tk.W, padx=5, background=self.colors["statusbar"], foreground=self.colors["text"])
        self.filter_delay_input = tk.Entry(frame_statusbar, textvariable=self.filter_delay, width=5, font=('Arial', 8), justify=tk.CENTER)

        self.drag_quality_label = tk.Label(frame_statusbar, text="Drag:", anchor=tk.W, padx=5, background=self.colors["statusbar"], foreground=self.colors["text"])
        self.selected_option1 = tk.StringVar(value=self.drag_quality.name.lower().capitalize())
        self.selected_option1.trace_add("write", lambda *_: setattr(self, "drag_quality", Application.QUALITY[self.selected_option1.get()]))
        self.drag_quality_button = tk.OptionMenu(frame_statusbar, self.selected_option1, *options[:-1])
        self.drag_quality_button.configure(
            background=self.colors["statusbar"],
            activebackground=self.colors["active_button"],
            foreground=self.colors["text"],
            activeforeground=self.colors["text"],
            highlightthickness=0,
            relief="flat",
            font=('Arial', 8),
            padx=5, pady=0
        )

        self.label_image_mode.pack(side=tk.RIGHT)
        self.label_image_dimensions.pack(side=tk.RIGHT)
        self.label_image_size.pack(side=tk.RIGHT)
        self.label_image_format.pack(side=tk.RIGHT)
        
        self.image_quality.pack(side=tk.RIGHT, pady=0)
        self.thumb_quality.pack(side=tk.RIGHT, pady=0)
        self.label_image_pixel.pack(side=tk.LEFT)
        self.render_info.pack(side=tk.LEFT)
        self.anim_info.pack(side=tk.LEFT)
        if self.show_ram.get():
            self.ram_indicator.pack(side=tk.LEFT)
        if self.show_advanced.get():
            self.toggle_advanced()
        if self.statusbar.get():
            frame_statusbar.pack(side=tk.BOTTOM, fill=tk.X)

        get_memory_usage()

    def create_canvas(self):
        canvas = tk.Canvas(self.master, background=self.colors["canvas"], highlightthickness=0)
        canvas.pack(expand=True, fill=tk.BOTH)
        self.divider = tk.Frame(self.master, bg=self.colors["button"], height=2)
        if self.statusbar.get():
            self.divider.pack(fill=tk.X)
        canvas.update()
        self.canvas = canvas
        self.app2 = ImageViewer(self.master, self.canvas)
        
    def bind_mouse_events(self):
        canvas = self.canvas
        canvas.bind("<Button-1>", lambda event: (setattr(self, "_old", event), self.master.focus()))
        canvas.bind("<B1-Motion>", self.mouse_move_left)
        canvas.bind("<Motion>", self.mouse_move)
        canvas.bind("<Double-Button-1>", self.mouse_double_click_left)
        canvas.bind("<MouseWheel>", self.mouse_wheel)
        canvas.bind("<Configure>", self.window_resize)
        if self.standalone:
            canvas.bind("<Button-3>", self.window_close)

    "Events"
    def menu_open_clicked(self, event=None): #ui
        from tkinter import filedialog

        self.filenames = []
        temp = filedialog.askopenfilenames(
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.pcx *.tiff *.psd *.jfif *.gif *.webp *.webm *.mp4 *.avif")]
        )
        if isinstance(temp, tuple): self.filenames = list(temp)
        if not self.filenames:
            return
        self.lastdir = os.path.dirname(self.filenames[0])
        self.filename_index = 0
        self.set_image(self.filenames[self.filename_index])

    def menu_open_dir_clicked(self, event=None):
        from tkinter import filedialog
        self.lastdir = filedialog.askdirectory()
        if not self.lastdir:
            return
        file_list = []
        for root, dirs, files in os.walk(self.lastdir):
            for file in files:
                file_list.append(os.path.join(root, file))

        self.filenames = list(x for x in file_list if x.endswith((  ".png", ".jpg", ".jpeg",
                                                                                            ".bmp", ".pcx", ".tiff",
                                                                                            ".psd", ".jfif", ".gif",
                                                                                            ".webp", ".webm", ".mp4", ".avif")))
        if not self.filenames:
            return
        self.filename_index = 0
        self.set_image(self.filenames[self.filename_index])
    
    def key_press(self, delta=0): #keys
        if len(self.filenames) <= 1:
            return
        if len(self.filenames) > (self.filename_index + delta): # ENSURE INDEX IS THE LENGTH OF THE LIST
            self.filename_index += delta
            if self.filename_index < 0: # ENSURE NEGATIVES LOOP
                self.filename_index = len(self.filenames)-1
        else: # ENSURE POSITIVES LOOP
            self.filename_index = 0
        self.set_image(self.filenames[self.filename_index])
    
    def rename(self, event=None):
        def ask_prefilled_text(parent, title, message, default_text=""):
            dialog = PrefilledInputDialog(parent, title, message, default_text)
            return dialog.result
        if not self.filename: return
        title = "Rename Image"
        label = ""
        path = self.filename
        old_name = os.path.basename(path)

        while True:
            new_name = ask_prefilled_text(
            self, title, label, default_text=old_name)
            if new_name:
                new_path = os.path.join(os.path.dirname(path), new_name)
                try:
                    os.rename(path, new_path)
                    self.set_image(new_path)
                    break
                except Exception as e:
                    print("Rename errors:", e)
                    label = f"{new_name} already exists in {os.path.basename(os.path.dirname(path))}"
                    old_name = new_name
            else:
                break
    
    def trash(self, event=None):
        if not self.filename or not self.filenames: return
        path = self.filenames.pop(self.filename_index)
        self.undo.append((path, self.filename_index))
        if not self.filenames: self.set_image(None) # doesnt exist, display none
        elif self.filename_index >= len(self.filenames): # index is over, diosplay latest
            self.set_image(self.filenames[-1])
            self.filename_index = len(self.filenames)-1
        else:
            self.set_image(self.filenames[self.filename_index]) # index exists

    def on_ctrl_z(self, event=None):
        if not self.undo: return
        path, index = self.undo.pop()
        self.set_image(path)
        self.filenames.insert(index, path)
    
    def mouse_wheel(self, event): #mouse
        if event.state == 2:
            return
        if not self.pil_image:
            return
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        iw, ih = self.pil_image.width, self.pil_image.height
        s_current = self.mat_affine[0, 0]
        if event.state in (
            Application.BUTTON_MODIFIER_CTRL,
            Application.BUTTON_MODIFIER_CTRL_LEFT_CLICK,
            Application.BUTTON_MODIFIER_RIGHT_CLICK
        ):
            self.rotate_at(
                self.rotation_degrees if event.delta > 0 else -self.rotation_degrees,
                event.x, event.y
            )
        else:
            factor = self.zoom_magnitude if event.delta > 0 else (1 / self.zoom_magnitude)
            if not self.unbound_var.get():
                s_fit = min(cw / iw, ch / ih)
                if factor < 1.0:
                    factor = max(factor, s_fit / s_current)
            self.scale_at(factor, event.x, event.y)
            if not self.unbound_var.get():
                s_new = s_current * factor
                if s_new <= s_fit:
                    tx = (cw - iw * s_new) / 2
                    ty = (ch - ih * s_new) / 2
                    self.mat_affine[0, 2] = tx
                    self.mat_affine[1, 2] = ty
                else:
                    self.restrict_pan()
        self.draw_image(self.pil_image)

    def mouse_move(self, event):
        if not self.pil_image:
            return
        pt = self.to_image_point(event.x, event.y)
        self.label_image_pixel.config(
            text=f"({pt[0]:.2f}, {pt[1]:.2f})" if pt else "(--, --)"
        )

    def mouse_double_click_left(self, event=None):
        if event.state == 2:
            return
        if self.pil_image:
            self.zoom_fit(self.pil_image)
            self.draw_image(self.pil_image)

    def mouse_move_left(self, event):
        if event.state == 258:
            return
        if self.pil_image and self._old:
            dx, dy = event.x - self._old.x, event.y - self._old.y
            self.translate(dx, dy)

            if not self.unbound_var.get():
                self.restrict_pan()
            
            self.draw_image(self.pil_image)
            self._old = event
    
    def toggle_statusbar(self): #statusbar
        if not self.statusbar.get():
            self.frame_statusbar.pack_forget()
            self.divider.pack_forget()
            if self.vlc_frame:
                vlc_player = self.old 
                if vlc_player and vlc_player.video_frame:
                    w, h = self.master.winfo_geometry().split("+",1)[0].split("x", 1)
                    w = int(w)
                    h = int(h)

                    vlc_player.video_container.config(width=w, height=h)
                    vlc_player.video_frame.config(width=w, height=h - 35)  # leave space for controls
                    vlc_player.controls_frame.config(width=w)
                    self.master.update()
            elif self.pil_image:
                self.zoom_fit(self.pil_image)
        else:
            self.divider.pack(expand=False, fill=tk.X)
            self.frame_statusbar.pack(expand=False, fill=tk.X)
            if self.vlc_frame:
                vlc_player = self.old
                if vlc_player and vlc_player.video_frame:
                    w, h = self.master.winfo_geometry().split("+",1)[0].split("x", 1)
                    w = int(w)
                    h = int(h)-20

                    vlc_player.video_container.config(width=w, height=h)
                    vlc_player.video_frame.config(width=w, height=h - 35)  # leave space for controls
                    vlc_player.controls_frame.config(width=w)
            elif self.pil_image:
                self.zoom_fit(self.pil_image)

    def toggle_advanced(self):
        widgets = [
            self.filter_delay_input,
            self.filter_delay_input_label,
            self.drag_quality_button,
            self.drag_quality_label
            ]
        for x in widgets:
            if self.show_advanced.get():
                x.pack(side=tk.RIGHT, pady=0)
            else:
                x.pack_forget()
    
    def toggle_ram_indicator(self):
        if self.show_ram.get():
            self.ram_indicator.pack(side=tk.LEFT)
        else:
            self.ram_indicator.pack_forget()
    
    def window_resize(self, event): #window
        if (event.widget is self.canvas or event.widget is self.master) and self.pil_image:
            self.zoom_fit(self.pil_image)
            self.dragging = True

            self.draw_image(self.pil_image, drag=True, initial_filter=Image.Resampling.NEAREST)

            if self.save1:
                self.after_cancel(self.save1)
            
            #self.update_idletasks() # prevent lag
            self.save1 = self.after(self.filter_delay.get(), lambda: self.after_idle(lambda: (self._imagetk_cache.clear(), self._zoom_cache.clear(), self.draw_image(self.pil_image), setattr(self, "dragging", False))))
        elif self.vlc_frame:
            vlc_player = self.old  # or however you store the instance
            if vlc_player and vlc_player.video_frame:
                w = event.width
                h = event.height

                if self.statusbar.get():
                    h -= 25

                # Resize the containing frames
                vlc_player.video_container.config(width=w, height=h)
                
                vlc_player.video_frame.config(width=w, height=h - 35)  # leave space for controls
                vlc_player.controls_frame.config(width=w)

    def window_close(self, e=None):
        from send2trash import send2trash
        self.save_json()
        for x in self.undo:
            path = os.path.normpath(x[0])
            try:
                send2trash(path)
            except Exception as e:
                print("Trash errors:", e)
        if self.gui and self.gui.Image_frame:
            self.gui.Image_frame.set_vals(self.savedata)
        if self.drag_buffer:
            self.after_cancel(self.drag_buffer)
        if self.save:
            self.after_cancel(self.save)
        if self.save1:
            self.after_cancel(self.save1)
        if self.memory_after_id:
            self.after_cancel(self.memory_after_id)
        if self.gif_after_id:
            self.after_cancel(self.gif_after_id)
        if self.gif_gen_after_id:
            self.after_cancel(self.gif_gen_after_id)

        if self.pil_image:
            try:
                self.pil_image.close()
            except:
                pass
            finally:
                self.pil_image = None

        self.image = None

        self.canvas = None
        self.image_id = None
        self.frames.clear()
        with self._frame_lock:
            self._zoom_cache.clear()
            self._imagetk_cache.clear()

        if self.gui:
            self.gui.second_window_viewer = None
        
        if self.vlc_frame:
            self.old.destroy(threaded=False)
            self.vlc_frame.destroy()
            self.vlc_frame = None
            del self.old

        self.destroy()
        self.master.destroy()
     
    
    # Affine transforms
    def reset_transform(self):
        self.mat_affine = np.eye(3)

    def translate(self, ox, oy):
        m = np.eye(3)
        m[0, 2], m[1, 2] = ox, oy
        self.mat_affine = m @ self.mat_affine

        scale_up = np.eye(3)
        _, _, f = self.scale_key
        inv_f = 1.0 / f
        scale_up[0,0] = scale_up[1,1] = inv_f
        self.combined = self.mat_affine @ scale_up

    def scale(self, s):
        m = np.eye(3)
        m[0, 0], m[1, 1] = s, s
        self.mat_affine = m @ self.mat_affine
        self.get_scale_key()

    def scale_at(self, s, cx, cy):
        self.translate(-cx, -cy)
        self.scale(s)
        self.translate(cx, cy)

    def rotate(self, deg):
        a = math.radians(deg)
        cos_a, sin_a = math.cos(a), math.sin(a)
        m = np.array([
            [cos_a, -sin_a, 0],
            [sin_a, cos_a, 0],
            [0, 0, 1]
        ])
        self.mat_affine = m @ self.mat_affine

    def rotate_at(self, deg, cx, cy):
        self.translate(-cx, -cy)
        self.rotate(deg)
        self.translate(cx, cy)

    def to_image_point(self, x, y):
        try:
            inv = np.linalg.inv(self.mat_affine)
            px, py, _ = inv @ [x, y, 1.]
            if 0 <= px < self.pil_image.width and 0 <= py < self.pil_image.height:
                return px, py
        except Exception:
            pass
        return []
    
    def zoom_fit(self, handle):
        if handle == None: return
        iw, ih = handle.width, handle.height
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        if iw <= 0 or ih <= 0 or cw <= 0 or ch <= 0: return
        self.reset_transform()
        s = min(cw / iw, ch / ih)
        ox, oy = (cw - iw * s) / 2, (ch - ih * s) / 2
        self.scale(s)
        self.translate(ox, oy)

    def _load_full_image_in_background(self, path):
        """Runs in a background thread, purely for decoding."""
        try:
            from PIL import Image
            img = Image.open(path)
            # Optional: disable full load for very large files to avoid memory spikes
            img.draft("RGBA", (4096, 4096))
            if img.mode != "RGBA":
                img = img.convert("RGBA")
            return img
        except Exception as e:
            print("Background load error:", e)
            return None

    def _on_async_image_ready(self, path, image, token):
        """Called in main thread after background decode finishes."""
        if getattr(self, "current_load_token", None) != token:
            image.close()
            image = None
            return  # outdated load result, ignore

        if image is None:
            print("Image load failed for:", path)
            return

        self.pil_image = image
        self.zoom_fit(image)
        with self._frame_lock:
            self._zoom_cache.set_maxsize(32)
            self._imagetk_cache.set_maxsize(0)

        if self.quick_render.get():
            if self.drag_quality.name.lower() == self.filter.lower(): pass
            elif self.filter.lower() == "pyvips" and self.drag_quality.name.lower() == "lanczos": pass
            else:
                id1 = self.after(1, lambda: self.draw_image(self.pil_image, initial_filter=self.drag_quality))
                self.draw_queue.append(id1)

        id2 = self.after(1, self.draw_image, self.pil_image)
        self.draw_queue.append(id2)
        
    "Display"
    def _set_info(self, filename, ext, is_video=False):
        if not is_video:
            x, y = (self.pil_image.width, self.pil_image.height)
        self.master.winfo_toplevel().title(f"{self.title} - {os.path.basename(filename)} - {self.filename_index+1}/{len(self.filenames)}")

        size_mb = os.path.getsize(filename) / (1024*1024)
        self.label_image_size_var.set(f"{size_mb:^5.1f}MB")

        self.label_image_format_var.set(f"{ext.upper() if is_video else self.pil_image.format:^4}:")
        self.label_image_mode_var.set(f"{ext.upper() if is_video else self.pil_image.mode:^4}")
        
        if is_video: return # vlcplayer will set this label.
        text = f"{x}x{y}"
        self.label_image_dimensions_var.set(f"{text:^11}")
        return (x, y)
    
    def _set_thumbnail(self, thumbpath=None):
        with self._frame_lock:
            self._zoom_cache.set_maxsize(0) # wont allow thumbnail in cache
            self._imagetk_cache.set_maxsize(0)
        f1 = Image.Resampling.NEAREST if self.thumbnail_var.get() == "Fast" else Image.Resampling.LANCZOS
        
        if thumbpath:
            with Image.open(thumbpath) as thumb:
                if self.thumbnail_var.get() == "Fast":
                    resized = thumb.copy()
                else:
                    vips_img = pyvips.Image.thumbnail(thumbpath, 64)
                    buffer = vips_img.write_to_memory()
                    mode = self.get_mode(vips_img)
                    resized = Image.frombytes(mode, (vips_img.width, vips_img.height), buffer, "raw")
                    resized = resized.resize((thumb.width, thumb.height), f1)
        elif True:
            def superfast_blurry_thumbnail(filename):
                import pyvips
                from PIL import Image

                # You can adjust this; 4–8 is a good balance
                s = 16

                # Step 1️⃣ Decode a small thumbnail with correct aspect ratio
                vips_img = pyvips.Image.thumbnail(filename, self.x // s)

                # Step 2️⃣ Blur to hide compression/blockiness
                vips_img = vips_img.gaussblur(2)


                # Step 4️⃣ Convert to Pillow Image
                mode = "RGB" if vips_img.bands == 3 else "RGBA"
                buf = vips_img.write_to_memory()

                return Image.frombuffer(
                    mode,
                    (vips_img.width, vips_img.height),
                    buf,
                    "raw",
                    mode,
                    0,
                    1
                )

            resized = superfast_blurry_thumbnail(self.filename)
        if resized.mode != "RGBA":
            resized = resized.convert("RGBA")

        self.zoom_fit(resized)
        self.draw_image(resized, ignore_anti_alias=True, initial_filter=Image.Resampling.NEAREST)
      
    def _set_picture(self, filename):
        "Close the handle and load full copy to memory."
        
        self.zoom_fit(self.pil_image)
        self.a = False

        self.loader.request_load(filename)
        
    def _set_animation(self, obj=None):
        self.is_gif = True
        self.zoom_fit(self.pil_image)
        self.pil_image.close()
        self.open_thread = Thread(target=self._preload_frames, args=(self.filename,), name="(Thread) Viewer frame preload", daemon=True)
        self.open_thread.start()

        self.timer1 = perf_counter()
        

        #self._preload_frames(self.pil_image)
        #self._update_frame()
        
    def _set_video(self):
        def close_vlc():
            if self.vlc_frame != None:
                    
                self.vlc_frame.pack_forget()
                if self.canvas:
                    self.canvas.pack(expand=True, fill=tk.BOTH)
                if self.old:
                    self.old.player.pause()
                    self.old.destroy()  # Bug fix for mp4
                    self.old = None
                self.vlc_frame = None
                self.old = None

        self._set_info(self.filename, self.ext, is_video=True)
        #self.update()
        close_vlc()
        f = self.vlc_frame == None
        new = Application.VlcPlayer(self, self.master.winfo_geometry().split("+",1)[0], self.filename, self.label_image_dimensions_var)
        if f and self.statusbar.get():
            self.frame_statusbar.pack_forget()
            self.divider.pack_forget()
            self.divider.pack(expand=False, fill=tk.X)
            self.frame_statusbar.pack(expand=False, fill=tk.X)
        #self.update()
        self.a = False
        self.old = new
     
    def set_image(self, filename, obj=None):
        if self.a: # guards against vlc crashes by rejecting queued tkinter calls. dont remove
            return
        self.a = True
        self.current_load_token = object()
        " Give image path and display it "
        self.timer.start()
        
        """if hasattr(self, "loader") and self.loader:
            self.loader.stop()"""

        if not self.reset(filename): return # returns False if we cant clear the canvas or cant set the image. (unsupported format)
        
        self.filename = filename
        self.ext = filename.rsplit(".", 1)[1]
        
        thumbpath = None if not obj or self.thumbnail_var.get().lower() == "no" else obj.thumbnail
        if self.ext in ("mp4", "webm"): # is video
            if thumbpath:
                self._set_thumbnail(thumbpath=thumbpath)
            else:
                self.image = None
                self.canvas.delete("_IMG")
            id1 = self.after(1, self._set_video)
            self.draw_queue.append(id1)
            return

        self.pil_image = Image.open(self.filename) if self.ext != "avif" else self.pyvips_to_pillows(self.filename)
        self.x, self.y = self._set_info(self.filename, self.ext)
        if hasattr(obj, "thumbnail") and not self.thumbnail_var.get().lower() == "no thumbs":
            thumbpath = obj.thumbnail
        else:
            thumbpath = None

        if self.ext in ("gif", "webp"): # is animation
            if thumbpath:
                self._set_thumbnail(thumbpath=thumbpath)
            self._set_animation(obj)
            self.a = False
        else: # is picture
            #self._set_picture(obj)
            if thumbpath:
                self._set_thumbnail(thumbpath=thumbpath)

            self.zoom_fit(self.pil_image)
            self.a = False

            self.loader.request_load(filename)

    def reset(self, filename):
        def close_vlc():
            if self.vlc_frame != None:
                def close_old(frame):
                    if frame:
                        frame.player.pause()
                        frame.destroy()  # Bug fix for mp4
                        frame = None
                self.vlc_frame.pack_forget()
                if self.canvas:
                    self.canvas.pack(expand=True, fill=tk.BOTH)
                close_old(self.old)
                self.vlc_frame = None
                self.old = None
                if self.statusbar.get():
                    self.frame_statusbar.pack_forget()
                    self.divider.pack_forget()
                    self.divider.pack(expand=False, fill=tk.X)
                    self.frame_statusbar.pack(expand=False, fill=tk.X)

        for call in self.draw_queue:
            self.after_cancel(call)
        self.draw_queue.clear()
        if self.open_thread and self.open_thread.is_alive():
            self._stop_thread.set()
            self.open_thread.join(timeout=2)
            if self.open_thread.is_alive():
                print("Warning: frame loader thread didn't exit cleanly")
        if self.gif_after_id:
            self.after_cancel(self.gif_after_id)
        if self.gif_gen_after_id:
            self.after_cancel(self.gif_gen_after_id)
        if self.draw_img_id:
            self.after_cancel(self.draw_img_id)
        if self.pil_image:
            try:
                self.pil_image.close()
                self.pil_image = None
            except Exception:
                pass
        
        self.gif_after_id = None
        self.gif_gen_after_id = None
        self.open_thread = None
        self._stop_thread.clear()

        self.frames.clear()
        with self._frame_lock:
            self._zoom_cache.clear()
            self._imagetk_cache.clear()
        self.debug.clear()
        self.lazy_index = 0
        
        self.filename = None
        #self.image = None
        self.image_id = None
        self.is_gif = False
        self.first_render_info = None
        #self.canvas.delete("_IMG")
        
        if not filename or not os.path.exists(filename): 
            self.a = False
            pass
        else:
            ext = filename.rsplit(".", 1)[1]
            supported_formats = {"png", "gif", "jpg", "jpeg", "bmp", "pcx", "tiff", "webp", "psd", "jfif", "avif", "mp4", "webm"}
            if ext in supported_formats:
                if ext not in ("mp4", "webm"):
                    #self.update()
                    close_vlc()
                    #self.update()
                self.f = True
                return True
            
                
            else:
                self.image = None
                self.canvas.delete("_IMG")
                self.master.winfo_toplevel().title(self.title)
                self.label_image_format_var.set(f"image info")
                self.label_image_mode_var.set("")
                self.label_image_dimensions_var.set("")
                self.label_image_size_var.set("")
                #self.update()
                close_vlc()
                #self.update()
                self.a = False
                return False

    "ANIMATION"
    def _preload_frames(self, filename):
        def fallback():
            self.is_gif = False
            self.frames.clear()
            self._set_picture(filename)
        if self._stop_thread.is_set(): return
        try:
            with Image.open(filename, "r") as handle:
                i = 0
                while True:
                    if self._stop_thread.is_set(): break
                    if i == 1: self.after(1, self._update_frame)
                    handle.seek(i)
                    duration = handle.info.get('duration', 100) or 100
                    frame = handle.convert("RGBA")
                    i += 1
                    with self._frame_lock:
                        self.frames.append((frame, duration))
                        self._zoom_cache.set_maxsize(i)
                        self._imagetk_cache.set_maxsize(i)

        except EOFError: 
            if i == 1:
                handle.seek(0)
                self.after(0, fallback)
                print("Error in _preload_frames (eoferror), falling back as a static image.")
        
    def _update_frame(self, lazy_index=0, gif_duration1=10000000):
        if not self.is_gif: return
        self.timer.start()
        frames = self.frames
        if not frames: return
        with self._frame_lock:
            self.pil_image, gif_duration = frames[lazy_index] # Updates reference (for panning/zooming)
        self.anim_info.config(text=f"F: {lazy_index}/{len(frames)}/{gif_duration}ms")

        elapsed = perf_counter() - self.timer1
        self.timer1 = perf_counter()
        if elapsed*1000 > gif_duration1+3:
            print("Animation is running slow (3>ms)")
        """if elapsed*1000 > gif_duration1+3 and self.open_thread.is_alive():
            lazy_index = 0
        else:"""
        lazy_index = (lazy_index + 1) % len(frames)
        self.lazy_index = lazy_index
        self.gif_after_id = self.after(gif_duration, lambda: self._update_frame(lazy_index, gif_duration))
        self.after(0, self.draw_image(self.pil_image, drag=self.dragging, initial_filter=Image.Resampling.NEAREST if self.dragging else None))
        
    "Rendering"
    def draw_image(self, pil_image, drag=False, ignore_anti_alias=False, initial_filter=None):
        if self.f: 
            self.image = None
            self.canvas.delete("_IMG")
        start = perf_counter()
        def calc_transform(aa, zoom):
            matrix = self.mat_affine
            if aa and ((zoom < 1.0)): matrix = self.combined
            inv = np.linalg.inv(matrix)
            affine_inv = (inv[0,0], inv[0,1], inv[0,2], 
                        inv[1,0], inv[1,1], inv[1,2])
            return affine_inv
        def get_transform_filter(aa, gif, resize_filter):
            if aa or gif: transform_filter = Image.Resampling.NEAREST
            elif resize_filter == Image.Resampling.LANCZOS or resize_filter == "pyvips": transform_filter = Image.Resampling.BICUBIC
            else: transform_filter = resize_filter
            return transform_filter
        def get_transform_key(lazy_index, scale_key, affine_inv, cw, ch, transform_filter):
            affine_bucket = (round(affine_inv[0], 3), round(affine_inv[1], 3), int(round(affine_inv[2])), round(affine_inv[3], 3), round(affine_inv[4], 3), int(round(affine_inv[5])))
            transform_key = (lazy_index, scale_key, affine_bucket, cw, ch, int(transform_filter))
            return transform_key # pan/zoom/rotation key     
        def get_source(pil_img_variables): # movements pan/zoom/rotation
            pil_image, aa, should_blur, resize_filter = pil_img_variables
            with self._frame_lock:
                if self._zoom_cache:
                    zoom_cache = True
                else: 
                    zoom_cache = False
            if not aa or zoom >= 1.0:
                return pil_image
            elif should_blur and zoom_cache: # gen levels from cached instead for a blur effect and maybe perf?
                with self._frame_lock:
                    tupl, cached = self._zoom_cache.last()
                index, last_zoom_key = tupl
                f = last_zoom_key / 1000
                size1 = max(1, round(pil_image.width * f)), max(1, round(pil_image.height * f))
                zoom_key = (self.lazy_index, last_zoom_key)
                with self._frame_lock:
                    self._zoom_cache.clear()
                    cached = cached or pil_image.resize(size1, self.drag_quality)
                    self._zoom_cache[zoom_key] = cached
                    

                if zoom >= 1.0: # DRAGGING bigger
                    resized = cached.resize((pil_image.width, pil_image.height), self.drag_quality)
                elif zoom < 1.0:# DRAGGING smaller
                    resized = cached.resize(size, self.drag_quality)
                    if scale_key < last_zoom_key:
                        resized = pil_image.resize(size, self.drag_quality)
                        new_zoom_key = (self.lazy_index, scale_key)
                        with self._frame_lock:
                            self._zoom_cache.clear()
                            self._zoom_cache[new_zoom_key] = resized   
            elif zoom < 1.0: # thumb gen # window resize resets caches
                use_pyvips = resize_filter == "pyvips"
                if gif:
                    try:
                        f1 = Image.Resampling.LANCZOS if use_pyvips else resize_filter
                        resized = pil_image.resize(size, f1)
                    except Exception as e:
                        print("Error in draw (gif):", e)
                else:
                    try:
                        if use_pyvips:
                            vips_img = pyvips.Image.thumbnail(self.filename, max(size))
                            buffer = vips_img.write_to_memory()
                            mode = self.get_mode(vips_img)
                            resized = Image.frombytes(mode, (vips_img.width, vips_img.height), buffer, "raw")
                        else:
                            resized = pil_image.resize(size, resize_filter)
                    except Exception as e:
                        print("Error in draw:", e)
                        return
                if resized.mode != "RGBA": resized = resized.convert("RGBA")
                with self._frame_lock:
                    self._zoom_cache[(self.lazy_index, scale_key)] = resized
            return resized 
        def get_imagetk(resized_pil_img: Image.Image=None, variables=None): # static redraws for animation
            if not resized_pil_img and not variables: return
            source = resized_pil_img or get_source(variables)

            dst = source.transform((cw, ch), Image.AFFINE, affine_inv, resample=transform_filter, fillcolor=self.bg_color)
            imagetk = ImageTk.PhotoImage(dst)
            if gif and not drag: 
                with self._frame_lock:
                    self._imagetk_cache[transform_key] = imagetk
            return imagetk
        
        # prefetch values
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        if cw <= 1 or ch <= 1 or pil_image == None: return
        aa = False if ignore_anti_alias else self.anti_aliasing.get() 
        gif = self.is_gif
        lazy_index = self.lazy_index
        zoom, scale_key, f = self.scale_key # scale key is precomputed by get_scale_key each time def scale() is called.
        size = max(1, round(pil_image.width * f)), max(1, round(pil_image.height * f)) # calc desired size

        # prefs
        resize_filter = initial_filter if initial_filter is not None else self.filter
        resize_blur = True
        resize_blur_for_gif = False
        should_blur = resize_blur_for_gif and drag if gif else resize_blur and drag
        
        affine_inv = calc_transform(aa, zoom) # calculate the transform
        transform_filter = get_transform_filter(aa, gif, resize_filter) # generate keys for cache
        transform_key = get_transform_key(lazy_index, scale_key, affine_inv, cw, ch, transform_filter) # anim rame, scale, transformation, canvas size and filter determine render cache key. (imagetk)
        zoom_key = (lazy_index, scale_key) # zoom level is just frame and scale (pil_image)
        
        def clean_cache(resize_blur_for_gif, gif, zoom):
            if not resize_blur_for_gif and gif:
                if zoom > 1.0: # zoom below 1.0 shouldnt keep cache alive for gif.
                    with self._frame_lock:
                        self._zoom_cache.clear()
                elif drag: # dragging shouldnt keep any cache alive for gif.
                    with self._frame_lock:
                        self._zoom_cache.clear()
                        self._imagetk_cache.clear()
        clean_cache(resize_blur_for_gif, gif, zoom)
        with self._frame_lock:
            imagetk = self._imagetk_cache.__getitem__(transform_key) if gif else None
        if not imagetk:
            with self._frame_lock:
                cached_pil_image = self._zoom_cache.__getitem__(zoom_key)
            if cached_pil_image:
                imagetk = get_imagetk(resized_pil_img=cached_pil_image)
            else:
                imagetk = get_imagetk(variables=(pil_image, aa, should_blur, resize_filter))
        if initial_filter is not None and not drag: # removes the initial render from the cache.
            with self._frame_lock:
                self._zoom_cache.clear()
                self._imagetk_cache.clear()
        
        if self.image_id: self.canvas.itemconfig(self.image_id, image=imagetk)
        else: self.image_id = self.canvas.create_image(0, 0, anchor='nw', image=imagetk, tags="_IMG")
        self.image = imagetk
        

        if self.gui and drag: 
            pass
        else:
            self.update_idletasks() # idea is that no queue is formed.

        time = self.timer.stop()
        if self.f:
            #print("1st:", time, len(self._zoom_cache))
            self.f = False
            self.first_render_info = f"R: {time}"
            self.render_info.config(text=f"{self.first_render_info} ms")
        else:
            self.debug.append(float(self.timer.stop()))
            if len(self.debug) > 10:
                self.debug.pop(0)
            test = sum(self.debug)/len(self.debug)
            if len(self.debug) == 1:
                self.render_info.config(text=f"{self.first_render_info}, {test:.1f} ms")
            else:
                part2 = self.render_info.config("text")[-1].split(",")[1]
                part3 = (perf_counter()-start)*1000
                self.render_info.config(text=f"{self.first_render_info},{part2}, {part3:.1f} ms")

    "Helpers"
    def pyvips_to_pillows(self, filename):
        try:
            vips_img = pyvips.Image.new_from_file(filename)
            mode = self.get_mode(vips_img)
            buffer = vips_img.write_to_memory()
            pil_img = Image.frombytes(
                mode, (vips_img.width, vips_img.height), buffer, "raw")
            return pil_img
        except Exception as e:
            print(f"Pyvips couldn't load thumbnail from data: {filename} : Error: {e}.")
            return
        
    def get_scale_key(self):
        mat = self.mat_affine
        sx, sy = (mat[0, 0]**2 + mat[1, 0]**2)**0.5, (mat[0, 1]**2 + mat[1, 1]**2)**0.5

        zoom = round(min(sx, sy), 3)

        scale_key = int(zoom * 1000)
        self.scale_key = zoom, scale_key, max(0.001, zoom)

    def get_mode(self, vips_img):
        pformat = str(vips_img.interpretation).lower()

        "Most common formats are srgb, b-w, rgb16 and grey16. We get the pillows equivalent 'mode' for frombytes method"
        if pformat == "srgb":
            if vips_img.bands == 3: mode = "RGB"
            elif vips_img.bands == 4: 
                mode = "RGBA" # Transparency. Able to view photos with invisible background.
        elif pformat == "b-w":
            mode = "L"
        elif pformat == "rgb16":
            mode = "I;16"
        elif pformat == "grey16":
            mode = "I;16"
        return mode
    
    def restrict_pan(self):
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        iw, ih = self.pil_image.width, self.pil_image.height

        tw = iw * self.mat_affine[0, 0]
        th = ih * self.mat_affine[1, 1]

        tx = self.mat_affine[0, 2]
        ty = self.mat_affine[1, 2]

        if tw <= cw:
            tx_min, tx_max = 0, cw - tw
        else:
            tx_min, tx_max = cw - tw, 0
        tx = min(max(tx, tx_min), tx_max)

        if th <= ch:
            ty_min, ty_max = 0, ch - th
        else:
            ty_min, ty_max = ch - th, 0
        ty = min(max(ty, ty_min), ty_max)

        self.mat_affine[0, 2] = tx
        self.mat_affine[1, 2] = ty

        scale_up = np.eye(3)
        _, _, f = self.scale_key
        inv_f = 1.0 / f
        scale_up[0,0] = scale_up[1,1] = inv_f
        self.combined = self.mat_affine @ scale_up

    "Preferences"
    def set_vals(self, savedata):
        self.unbound_var.set(savedata.get("unbound_pan", self.unbound_var.get()))

        self.statusbar.set(savedata.get("statusbar", self.statusbar.get()))

        self.selected_option.set(savedata.get("filter", "Nearest").lower().capitalize())
        self.selected_option1.set(savedata.get("drag_quality", "Nearest").lower().capitalize())

        self.quick_render.set(savedata.get("quick_render", self.quick_render.get()))
        self.anti_aliasing.set(savedata.get("anti_aliasing", self.anti_aliasing.get()))
        self.thumbnail_var.set(savedata.get("thumbnail_var", self.thumbnail_var.get()))
        self.filter_delay.set(int(savedata.get("final_filter_delay", self.filter_delay.get())))
        self.show_advanced.set(savedata.get("show_advanced", self.show_advanced.get()))
        self.show_ram.set(savedata.get("show_ram", self.show_ram.get()))
        self.volume = int(savedata.get("volume", self.volume))
        
    def load_json(self):
        if os.path.isfile(self.save_path):
            try:
                with open(self.save_path) as f:
                    return json.load(f)
            except Exception as e:
                print("Json load error:", e)
        return {}

    def save_json(self):
        if self.filter == "pyvips":
            name = "Pyvips"
        else:
            name= self.filter.name
        data = {
                "geometry": self.master.winfo_geometry(),       # "600x800+100+100" Width x Height + x + y
                "disable_menubar": self.disable_menubar,        # Disable the menu bar
                "statusbar": self.statusbar.get(),     # Disable the statusbar
                "lastdir": self.lastdir or None,                # Last folder viewed
                "unbound_pan": self.unbound_var.get(),          # Go out of bounds
                "rotation_degrees": self.rotation_degrees,        # Rotation amount
                "zoom_magnitude": self.zoom_magnitude,                # Zoom amount
                "filter": name,                         # Default filter
                "drag_quality": self.drag_quality.name,              # 
                "quick_render": self.quick_render.get(),
                "anti_aliasing": self.anti_aliasing.get(),
                "thumbnail_var": self.thumbnail_var.get(),
                "final_filter_delay": self.filter_delay.get(),
                "show_advanced": self.show_advanced.get(),
                "show_ram": self.show_ram.get(),
                "colors": self.colors,
                "volume": self.volume,
                        }
        if self.savedata:
            for key, x in data.items():
                self.savedata[key] = data[key]
        if self.standalone and not self.gui:
            with open(self.save_path, "w") as f:
                json.dump(data, f, indent=4)

class Timer:
    "Timer for benchmarking"
    def __init__(self):
        self.creation_time = None
    def start(self):
        self.creation_time = perf_counter()
    def stop(self):
        elapsed_time = (perf_counter() - self.creation_time)*1000
        return (f"{elapsed_time:.1f}")
    
if __name__ == "__main__":
    app = Application()
    #app.set_image(path)
    app.master.mainloop() 