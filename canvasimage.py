from math import log, pow
from time import perf_counter
from warnings import catch_warnings, simplefilter
from threading import Thread, Event
from gc import collect
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import ttk
import vlc
import os
from random import randint
from pymediainfo import MediaInfo

class VLCPlayer(tk.Frame):
    def __init__(self, parent, volume, color, button_bg):
        self.volume = volume
        self.button_color = button_bg
        self.color = color
        super().__init__(parent)
        self.configure(bg="#000000")

        self.parent = parent
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        
        self.instance = vlc.Instance("--quiet")

        self.media_list = None
        self.media_list_player = self.instance.media_list_player_new()
        self.media_list_player.set_playback_mode(vlc.PlaybackMode.loop)  # repeats current item only

        self.player = self.media_list_player.get_media_player()

        self.user_dragging_slider = False

        self.create_widgets()
    
    def set(self, path):
        self.video_path = path

        self.grid(sticky="nsew")

        self.media_list = self.instance.media_list_new()
        self.media = self.instance.media_new(self.video_path)
        self.media_list.add_media(self.media)
        self.media_list_player.set_media_list(self.media_list)

        self.player.set_media(self.media)
        self.change_volume(self.volume)

    def change_volume(self, value):
        "Callback to adjust the audio level."
        new_volume = int(float(value))
        self.player.audio_set_volume(new_volume)
        self.volume = new_volume

    def create_widgets(self):
        def set_position(slider_value):
            position = float(slider_value) / 1000.0
            self.player.set_position(position)
        def update_slider():
            if not self.user_dragging_slider:
                pos = self.player.get_position()
                if pos == -1:
                    pos = 0
                self.position_slider.configure(command=lambda *args, **kwargs: None)
                self.position_slider.set(int(pos * 1000))
                self.position_slider.configure(command=set_position)
            self.after(200, update_slider)
        def slider_drag(event):
            if self.user_dragging_slider:
                val = self.position_slider.get()
                self.set_position(val)
        def slider_release(event):
            self.user_dragging_slider = False
        def slider_click(event):
            if self.user_dragging_slider: return
            self.user_dragging_slider = True
            slider = self.position_slider
            slider_length = slider.winfo_width()
            clicked_val = int((event.x / slider_length) * slider["to"])
            
            if "slider" in slider.identify(event.x, event.y):
                return
            slider.set(clicked_val)
        def volume_click(event):
            slider = event.widget
            slider_width = slider.winfo_width()
            click_fraction = event.x / slider_width
            new_value = float(slider.cget("from")) + (float(slider.cget("to")) - float(slider.cget("from"))) * click_fraction
            slider.set(new_value)
            self.change_volume(new_value)

        def create_pause_icon(size=20, bar_width=4, spacing=4):
            icon = tk.PhotoImage(width=size, height=size)
            bg = self.button_color  # or transparent if using PNG with alpha
            icon.put(bg, to=(0, 0, size, size))

            bar_color = "#888BF8"
            # Left bar
            icon.put(bar_color, to=(4, 4, 4 + bar_width, size - 4))
            # Right bar
            icon.put(bar_color, to=(4 + bar_width + spacing, 4, 4 + 2 * bar_width + spacing, size - 4))

            return icon
        def create_play_icon(size=20, margin=4):
            icon = tk.PhotoImage(width=size, height=size)
            bg = self.button_color  # or any background color you want
            icon.put(bg, to=(0, 0, size, size))

            triangle_color = "#888BF8"

            # Define triangle points (a right-pointing triangle)
            p1 = (margin, margin)
            p2 = (size - margin, size // 2)
            p3 = (margin, size - margin)

            # Rasterize triangle manually (basic scanline fill)
            for y in range(size):
                for x in range(size):
                    # Barycentric technique — simple point-in-triangle check
                    def sign(p1, p2, p3):
                        return (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])

                    pt = (x, y)
                    b1 = sign(pt, p1, p2) < 0.0
                    b2 = sign(pt, p2, p3) < 0.0
                    b3 = sign(pt, p3, p1) < 0.0

                    if (b1 == b2) and (b2 == b3):
                        icon.put(triangle_color, (x, y))

            return icon
        # Video panel
        self.video_panel = tk.Frame(self, bg=self.color)
        self.video_panel.columnconfigure(0, weight=1)
        self.video_panel.rowconfigure(0, weight=1)
        self.video_panel.grid(row = 0, column = 0, sticky="nsew")

        # Controls panel
        ctrl_panel = tk.Frame(self, bg=self.color)
        ctrl_panel.grid(row = 1, column = 0, sticky="ew")

        self.pause_icon = create_pause_icon()
        self.play_icon = create_play_icon()
        self.pause_button = tk.Button(ctrl_panel, image=self.pause_icon, command=self.pause, bg=self.button_color, activebackground=self.button_color, activeforeground=self.button_color, fg=self.button_color)
        self.pause_button.grid(row=0, column=0, sticky="nsew")

        # Timeline slider
        style = ttk.Style()
        style.configure("Horizontal.TScale",
                background=self.color)
        self.position_slider = ttk.Scale(ctrl_panel, from_=0, to=1000, orient=tk.HORIZONTAL,style="Horizontal.TScale",
                                         command=set_position)
        ctrl_panel.columnconfigure(1, weight=10)
        ctrl_panel.columnconfigure(2, weight=2)
        self.position_slider.grid(row = 0, column = 1, sticky="nsew")

        # Volume slider: range from 0 to 100
        self.volume_slider = ttk.Scale(ctrl_panel,from_=0,to=100, value=self.volume, orient=tk.HORIZONTAL,style="Horizontal.TScale",
                                      command=self.change_volume)
        #self.volume_slider.set(self.volume)
        self.volume_slider.grid(row=0, column=2, sticky="ew", padx=(2, 5), pady=5)
        self.volume_slider.bind("<Button-1>", volume_click)

        self.position_slider.bind("<ButtonPress-1>", slider_click)
        self.position_slider.bind("<ButtonRelease-1>", slider_release)
        self.video_panel.rowconfigure(0, weight=1)
        self.video_panel.columnconfigure(0, weight=1)

        win_id = self.video_panel.winfo_id()
        self.player.set_hwnd(win_id)

        update_slider()

    def play(self):
        self.player.play()

    def pause(self):
        if self.pause_button["image"] == self.pause_icon.name:
            self.pause_button.config(image=self.play_icon)
        else:
            self.pause_button.config(image=self.pause_icon)
        self.player.pause()

    def stop(self):
        self.position_slider.set(0)
        self.player.audio_set_volume(0)
        self.player.pause()
        self.player.stop()
        self.player.release()
        self.player = None

        self.media_list_player.stop()
        self.media_list_player.release()
        self.media_list_player = None

        self.media_list.release()
        self.media_list = None

        self.media.release()
        self.media = None

        self.instance.release()
        self.instance = None

    def on_close(self):
        self.parent.gui.volume = self.volume_slider.get()
        self.stop()
        self.destroy()

class CanvasImage(tk.Frame):
    """ Display and zoom image """
    def __init__(self, master, gui, imagewindowgeometry, color):
        self.creation_time = perf_counter()
        #permanent
        self.exiting = False
        Image.MAX_IMAGE_PIXELS = 1000000000
        super().__init__(master)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.gui = gui
        self.color = color
        self.timer = gui.fileManager.timer
        
        # Image scaling defaults
        self.imscale = 1.0  # Scale for the canvas image zoom
        self.__delta = 1.15  # Zoom step magnitude
        self.imageid = None
        #resettable
        geometry_width, geometry_height = imagewindowgeometry.split('x',1)
        self.canvas_height = int(geometry_height)
        self.canvas_width = int(geometry_width)

        self.canvas = tk.Canvas(self, bg=self.color,
                                highlightthickness=0, width=geometry_width, height = geometry_height)  # Set canvas dimensions to remove scrollbars
        self.canvas.grid(row=0, column=0, sticky='nswe') # Place into grid
        self.canvas.rowconfigure(0, weight=1)
        self.canvas.columnconfigure(0, weight=1)

        self.image = None
        self.frames = []
        self.frametimes = []
        self.pyramid = []
        self.sizes = []
        self.pyramid_thread = None
        self.load_frames_thread = None
        self.vlcplayer = None

        self.replace_await = False  # Flag tells whether we want to render a second better quality on top
        self.first_rendered = Event()
        self.after_id = None
        
    def set(self, obj):
        def rescale():
            "Rescales the image to fit image viewer"
            scale = min(int(self.canvas_width) / self.imwidth, int(self.canvas_height) / self.imheight)
            self.imscale=scale
            self.canvas.scale('all', self.canvas_width, 0, scale, scale)  # rescale all objects
        def center_image():
            """ Center the image on the canvas """
            canvas_width = self.canvas_width
            canvas_height = self.canvas_height

            # Calculate scaled image dimensions
            scaled_image_width = self.imwidth * self.imscale
            scaled_image_height = self.imheight * self.imscale

            # Calculate offsets to center the image
            if self.gui.viewer_x_centering:
                x_offset = int((canvas_width - scaled_image_width)-(canvas_width - scaled_image_width)/2)
            else:
                x_offset = 0
            if self.gui.viewer_y_centering:
                y_offset = int((canvas_height - scaled_image_height)/2)
            else:
                y_offset = 0

            # Update the position of the image container
            self.canvas.coords(self.container, (x_offset), (y_offset), (x_offset + scaled_image_width), (y_offset + scaled_image_height))           
        def resize(event):
            if "toplevel" not in event.widget._w: return
            width = event.width
            height = event.height
            if width == self.canvas_width or height == self.canvas_height: return
            if width <=1 or height <= 1 or self.imwidth == None: return
            self.canvas_width = width
            self.canvas_height = height

            self.canvas.config(width=event.width, height=event.height)
            
            self.canvas.xview_moveto(0)
            self.canvas.yview_moveto(0)
            
            rescale()
            center_image()

            k = self.imscale * self.__ratio
            self.__curr_img = min(
                (-1) * int(log(k, self.__reduction)),
                len(self.sizes) - 1
            )
            self.scale11 = k * pow(self.__reduction, max(0, self.__curr_img))
            self.__show_image()
        def binds():
            self.canvas.bind('<ButtonPress-1>', self.__move_from)  # remember canvas position / panning
            self.canvas.bind('<B1-Motion>',     self.__move_to)  # move canvas to the new position / panning
            self.canvas.bind("<Double-Button-1>", mouse_double_click_left)
            if self.file_type == "STATIC":
                self.canvas.bind('<MouseWheel>', self.__wheel)  # zoom for Windows and MacOS, but not Linux / zoom pyramid.
                self.canvas.bind('<Button-5>',   self.__wheel)  # zoom for Linux, wheel scroll down
                self.canvas.bind('<Button-4>',   self.__wheel)  # zoom for Linux, wheel scroll up
            self.canvas.bind("<KeyPress-p>", self.__show_image)  # canvas is resized from displayimage, time to show image.
        def mouse_double_click_left(*args):
             # Reset zoom scale to 1.0
            self.canvas.xview_moveto(0)
            self.canvas.yview_moveto(0)
            
            rescale()
            center_image()

            k = self.imscale * self.__ratio
            self.__curr_img = max(0, min((-1) * int(log(k, self.__reduction)), len(self.sizes) - 1)
            )
            self.scale11 = k * pow(self.__reduction, max(0, self.__curr_img))

            self.__show_image()      
        def misc(path):
            def method_pymediainfo(filepath):
                media_info = MediaInfo.parse(filepath)
                video_track = next((track for track in media_info.tracks if track.track_type == 'Video'), None)
                width = int(video_track.width) if video_track and video_track.width else self.imwidth
                height = int(video_track.height) if video_track and video_track.height else self.imheight

                return width, height
            self.imwidth, self.imheight = method_pymediainfo(path)
            a = f"{self.imwidth}x{self.imheight}"
            self.gui.info.set(f"Size: {self.file_size:>6.2f} MB {a:>10}")
        
        self.start = perf_counter()
        self.timer.start()
        
        self.file_type = ""
        self.lazy_index = 0
        self.lazy_loading = True
        path = obj.path
        
        self.file_size = round(((obj.file_size or os.stat(path).st_size))/1.048576/1000000,2) #file size in MB #os.stat is for edge cases, where this cant be retrieved from obj.
        self.gui.first_render.set("F:")
        self.gui.frameinfo.set(f"F/D: -") 
        aa = ""
        self.gui.frametimeinfo.set(f"{aa:>4}")

        if obj.ext in ("mp4","webm"):
            self.file_type = "VIDEO"
            self.master.configure(bg = "#000000")
            self.vlcplayer = VLCPlayer(self, self.gui.volume, self.color, self.gui.button_bg)
            self.handle_video(path)

            self.after_idle(misc, path)
        
        elif obj.ext in ("png", "jpg", "jpeg", "gif", "webp"):
            self.master.configure(bg = self.color)
            self.__first_filter = getattr(Image.Resampling, self.gui.filter_mode.upper()) if hasattr(self.gui, "filter_mode") else Image.Resampling.BILINEAR
            self.__filter = Image.Resampling.NEAREST  # The end qualtiy of the image. #NEAREST, BILINEAR, BICUBIC
            self.file_type = "STATIC"
            with catch_warnings():  # suppress DecompressionBombWarning
                simplefilter('ignore')
                self.image = Image.open(path)
                self.is_pixel_art = self.image.width <= 256 or self.image.height <= 256 or self.image.mode in ("P",)
                if hasattr(self.image, "n_frames"):
                    n = self.image.n_frames
                else:
                    n = 1

            self.imwidth, self.imheight = self.image.size  # public for outer classes
            self.__min_side = min(self.imwidth, self.imheight)  # get the smaller image side
            self.__ratio = 1.0
            self.scale11 = self.imscale * self.__ratio  # image pyramid scale
            self.__curr_img = 0  # current image from the pyramid
            self.__reduction = 2 # reduction degree of image pyramid

            a = f"{self.imwidth}x{self.imheight}"
            self.gui.info.set(f"Size: {obj.file_size/(1024*1024):>6.2f} MB {a:>10}")

            pil = None
            if self.image.mode not in ("RGB", "RGBA"):
                pil = self.image.convert("RGBA")
            self.pyramid = [pil or self.image]

            if n <= 1:
                self.handle_static()
                binds()
                rescale()  # Scales to the window
                center_image()
                self.__show_image(pil=pil)
                self.master.bind('<Configure>', resize)
            else:
                self.handle_static()
                self.file_type = "VIDEO"
                binds()
                self.file_type = "STATIC"
                rescale()
                center_image()
                self.__show_image(no_pyramid=True, pil=pil)
                self.master.bind('<Configure>', resize)
                self.file_type = "VIDEO"
                self.handle_gif(n)
        self.master.update()

    ######
    def handle_video(self, path):
        "Handles videos"
        self.vlcplayer.set(path)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.vlcplayer.rowconfigure(0, weight=1)
        self.vlcplayer.columnconfigure(0, weight=1)
        self.vlcplayer.grid(row=0, column=0, sticky="nsew")
        self.vlcplayer.play()
        
    def lazy_pyramid(self):
        "Generates zoom pyramid"
        if self.pyramid[0] == None:
            self.pyramid[0] = self.image.copy()
        for i in range(1, len(self.sizes)):
            if self.pyramid[i] == None:
                w_target, h_target = self.sizes[i]
                img = self.image.resize((w_target, h_target))
                if self.exiting: return
                self.pyramid[i] = img
            
    def handle_static(self, skip_pyramid=False):
        "Handles static images"
        if not skip_pyramid:
            w, h = self.imwidth, self.imheight
            self.sizes = [(w, h)]
            while w > 512 and h > 512:
                w = int(w / 2)
                h = int(h / 2)
                self.sizes.append((w, h))
            
            self.pyramid.extend([None]*len(self.sizes))

        self.container = self.canvas.create_rectangle((0, 0, self.imwidth, self.imheight), width=0, tags="rect")

    def handle_gif(self, n):
        "Handles gifs"
        from PIL import Image, ImageTk

        def load_frames():
            try:
                for i in range(self.image.n_frames):
                    if self.exiting: return    
                    self.image.seek(i) # convert? make sure all framse have same mode at the end.
                    im = self.image.copy()
                    if im.mode not in ("RGB", "RGBA"):
                        im = im.convert("RGBA")
                    orig_w, orig_h = im.size
                    target_w, target_h = self.canvas_width, self.canvas_height

                    # Calculate aspect ratio-preserving size
                    scale = min(target_w / orig_w, target_h / orig_h)
                    new_w = int(orig_w * scale)
                    new_h = int(orig_h * scale)

                    if self.is_pixel_art: resampling_filter = Image.Resampling.NEAREST
                    else: resampling_filter = Image.Resampling.LANCZOS
                    im = im.resize((new_w, new_h), resampling_filter)
                    self.frames.append(ImageTk.PhotoImage(im))
                    self.frametimes.append(im.info.get('duration', 100))
            except AttributeError as e: # out of scope catch / exiting
                return
            except ValueError as e:
                if e.args and e.args[0] == "Operation on closed image": # exiting
                    pass
                else:
                    print(e)
                return
            except Exception as e:
                print(e)
                return

            self.lazy_loading = False
            self.gui.first_render.set(f"{self.gui.first_render.get()}+{self.timer.stop()}")
            self.image.close()
            
        def lazy_load():
            def animate_image():
                "Simple gif looper"
                if self.exiting: return
                try:
                    self.canvas.itemconfig(self.imageid, image=self.frames[self.lazy_index])
                    self.canvas.after(self.frametimes[self.lazy_index], animate_image)
                    self.lazy_index = (self.lazy_index + 1) % len(self.frames)
                    a = f"{self.lazy_index}/{len(self.frames)}/{n}"
                    self.gui.frameinfo.set(f"F/D: {a:>4}")
                    b = f"{self.frametimes[self.lazy_index]} ms"
                    self.gui.frametimeinfo.set(f"{b:>4}")
                except Exception as e:
                    return
            if self.exiting:
                return
            try:
                "Display new frames as soon as possible, when all loaded, switch to simple looping method"
                if not self.lazy_loading: # When all frames are loaded, we switch to just looping
                    animate_image()
                    return
                elif not len(self.frames) > self.lazy_index: #if the list is still empty. Wait.
                    #Ideally 0 buffering, update somethng so frames is initialzied quaranteed.
                    self.canvas.after(self.delay, lazy_load)
                    return
                elif self.lazy_index != n:

                    #Checks if more frames than index is trying and less than max allowed.
                    self.canvas.itemconfig(self.imageid, image=self.frames[self.lazy_index])
                    self.canvas.after(self.frametimes[self.lazy_index], lazy_load)

                    a = f"{self.lazy_index}/{len(self.frames)}/{n}"
                    self.gui.frameinfo.set(f"F/D: {a:>4}")
                    b = f"{self.frametimes[self.lazy_index]} ms"
                    self.gui.frametimeinfo.set(f"{b:>4}")

                    self.lazy_index = (self.lazy_index + 1) % n
                    return
                else:
                    print("Error in lazy load, take a look")
                    self.canvas.after(self.delay, lazy_load, id)
            except Exception as e:
                return
        
        self.gui.frameinfo.set(f"F/D: {0}/{0}/{n}")
        self.frametimes = []
        self.delay = 100
        self.frames = []            # Stores loaded frames for .Gif, .Webp

        self.lazy_loading = True # not used?
        self.load_frames_thread = Thread(target=load_frames, name="frames", daemon=True)
        self.load_frames_thread.start()
        lazy_load()
    
    ###
    def __show_image(self, no_pyramid=False, pil=None):
        if self.file_type == "VIDEO": return
        box_image = self.canvas.coords(self.container)  # get image area
        box_canvas = (self.canvas.canvasx(0),  # get visible area of the canvas
                        self.canvas.canvasy(0),
                        self.canvas.canvasx(self.canvas_width),
                        self.canvas.canvasy(self.canvas_height))
        box_img_int = tuple(map(int, box_image))  # convert to integer or it will not work properly
        # Get scroll region box
        box_scroll = [min(box_img_int[0], box_canvas[0]), min(box_img_int[1], box_canvas[1]),
                        max(box_img_int[2], box_canvas[2]), max(box_img_int[3], box_canvas[3])]
        # Horizontal part of the image is in the visible area
        if  box_scroll[0] == box_canvas[0] and box_scroll[2] == box_canvas[2]:
            box_scroll[0]  = box_img_int[0]
            box_scroll[2]  = box_img_int[2]
        # Vertical part of the image is in the visible area
        if  box_scroll[1] == box_canvas[1] and box_scroll[3] == box_canvas[3]:
            box_scroll[1]  = box_img_int[1]
            box_scroll[3]  = box_img_int[3]
        # Convert scroll region to tuple and to integer
        #self.canvas.configure(scrollregion=tuple(map(int, box_scroll)))  # set scroll region
        x1 = max(box_canvas[0] - box_image[0], 0)  # get coordinates (x1,y1,x2,y2) of the image tile
        y1 = max(box_canvas[1] - box_image[1], 0)
        x2 = min(box_canvas[2], box_image[2]) - box_image[0]
        y2 = min(box_canvas[3], box_image[3]) - box_image[1]
        
        if not (int(x2 - x1) > 0 and int(y2 - y1) > 0): return
        
        if not self.first_rendered.is_set() and self.file_size > self.gui.quick_preview_size_threshold:
            self.replace_await = True


        # this is slowing us down. do pyramid creation AFTER, just resize normally for the first image at low filter, then high pass, then pyramid.
        # this causes slight misalignment problem?
        if not self.first_rendered.is_set() and self.sizes:
            k = self.imscale * self.__ratio  # temporary coefficient
            self.__curr_img = max(0,min((-1) * int(log(k, self.__reduction)), len(self.sizes) - 1))
            self.scale11 = k * pow(self.__reduction, max(0, self.__curr_img))
            """w_target, h_target = self.sizes[self.__curr_img]
            
            if self.imwidth == w_target and self.imheight == h_target:
                if pil:
                    self.pyramid[self.__curr_img] = pil
                else:
                    self.pyramid[self.__curr_img] = self.image.copy()
                img = self.pyramid[self.__curr_img]
            else:
                if pil:
                    img = pil.resize((w_target, h_target))
                else:
                    img = self.image.resize((w_target, h_target))
                self.pyramid[self.__curr_img] = img"""
            img = self.pyramid[0] # swap this with """""" to generate it to pyramid, so there is no resizing problems at all. Turned off for now becasue it is 100 ms slower for large images.
        else:
            if self.pyramid[self.__curr_img] != None:
                img = self.pyramid[self.__curr_img]
            else:
                img = self.pyramid[0]

        if self.is_pixel_art:                            f = Image.Resampling.NEAREST
        elif self.file_size > self.gui.quick_preview_size_threshold and not self.first_rendered.is_set(): f = self.__first_filter
        else:                                                                       f = self.__filter
        if not self.first_rendered.is_set() or self.replace_await:
            pass
        else:
            img = img.crop((int(x1 / self.scale11), int(y1 / self.scale11),
                                int(x2 / self.scale11), int(y2 / self.scale11)))

        imagetk = ImageTk.PhotoImage(img.resize((round(x2 - x1), round(y2 - y1)), f))
        if not self.first_rendered.is_set():
            
            self.imageid = self.canvas.create_image(max(box_canvas[0], box_img_int[0]),
                                                        max(box_canvas[1], box_img_int[1]),
                                                        anchor='nw', image=imagetk, tags="_IMG")
            
            self.first_rendered.set()  # Signal that the quick preview is done.
            self.gui.first_render.set(f"F: {self.timer.stop()}")
            
            if self.replace_await and not no_pyramid:
                self.after_id = self.after_idle(self.__show_image)
            elif not no_pyramid:
                self.pyramid_thread = Thread(target=self.lazy_pyramid, name="pyramid", daemon=True)
                self.pyramid_thread.start()
                
        elif self.replace_await: # only render second time if needed.
            self.canvas.itemconfig(self.imageid, image=imagetk)
            self.gui.first_render.set(f"{self.gui.first_render.get()}+{self.timer.stop()}")
            self.replace_await = False
            if not no_pyramid:
                self.pyramid_thread = Thread(target=self.lazy_pyramid, name="pyramid", daemon=True)
                self.pyramid_thread.start()
            
        else:
            self.canvas.itemconfig(self.imageid, image=imagetk)
            self.canvas.coords(self.imageid, max(box_canvas[0], box_img_int[0]), max(box_canvas[1], box_img_int[1]))

        self.canvas.imagetk = imagetk
        print(perf_counter()-self.creation_time)
    
    def close(self):
        def delayed():
            if self.vlcplayer != None:
                self.vlcplayer.on_close()
                self.vlcplayer = None
                del self.vlcplayer
            
            self.exiting = None
            self.creation_time = None
            self.gui = None
            self.color = None
            self.imscale = None
            self.__delta = None
            self.canvas_height = None
            self.canvas_width = None
            self.pyramid_thread = None
            self.load_frames_thread = None
            self.replace_await = None
            self.first_rendered = None
            self.after_id = None
            self.start = None
            self.timer = None
            self.file_type = None
            self.lazy_index = None
            self.lazy_loading = None
            self.imwidth = None
            self.imheight = None
            self.__min_side = None
            self.__ratio = None
            self.scale11 = None
            self.__curr_img = None
            self.__reduction = None
            self.__first_filter = None
            self.__filter = None
            self.file_size = None

            del self.exiting
            del self.creation_time
            del self.gui
            del self.color
            del self.imscale
            del self.__delta
            del self.canvas_height
            del self.canvas_width
            del self.pyramid_thread
            del self.load_frames_thread
            del self.replace_await
            del self.first_rendered
            del self.after_id
            del self.start
            del self.timer
            del self.file_type
            del self.lazy_index
            del self.lazy_loading
            del self.imwidth
            del self.imheight 
            del self.__min_side
            del self.__ratio
            del self.scale11
            del self.__curr_img
            del self.__reduction
            del self.__first_filter
            del self.__filter
            del self.file_size

            self.canvas.delete("rect")
            self.canvas.delete("_IMG")
            self.canvas.delete("all")

            if hasattr(self.canvas, "imagetk"):
                del self.canvas.imagetk
            self.canvas.destroy()
            del self.canvas
            del self.imageid

            self.container = None
            del self.container

            self.frames.clear()
            self.frametimes.clear()
            self.sizes.clear()
            self.pyramid.clear()
            del self.frames
            del self.frametimes
            del self.sizes
            del self.pyramid
           
            
            if self.image:
                try:
                    self.image.close()
                except Exception as e:
                    print(e)
                del self.image
        
            self.destroy()
            collect() ###
        
        self.exiting = True
        if self.pyramid_thread != None and self.pyramid_thread.is_alive():
            self.pyramid_thread.join()
        # we cant join load_frames_thread because it interacts with tkinter mainloop. We use try block for it to kill it when stuff goes out of scope for it.
        self.after_idle(delayed)
        
    def __move_from(self, event):
        "Remember previous coordinates for scrolling with the mouse"
        self.canvas.focus_set()
        self.canvas.scan_mark(event.x, event.y)
    
    def __move_to(self, event):
        "Drag (move) canvas to the new position"
        self.canvas.scan_dragto(event.x, event.y, gain=1)
        self.__show_image()  # zoom tile and show it on the canvas
    
    def __wheel(self, event=None, direction=None, redraw=False):
        "Zoom with mouse wheel"
        if self.file_type == "VIDEO": return
        if event:
            x = self.canvas.canvasx(event.x)
            y = self.canvas.canvasy(event.y)
        else:
            x = self.canvas.canvasx(self.canvas_width // 2)
            y = self.canvas.canvasy(self.canvas_height // 2)
        scale = 1.0

        # Respond to Linux (event.num) or Windows (event.delta) wheel event
        if (event and (event.num == 5 or event.delta == -120)) or direction == "down":  # scroll down, smaller
            if round(self.__min_side * self.imscale) < 30: return  # image is less than 30 pixels
            self.imscale /= self.__delta
            scale        /= self.__delta
        elif (event and (event.num == 4 or event.delta == 120)) or direction == "up":  # scroll up, bigger
            i = min(self.canvas_width, self.canvas_height) >> 1
            if i < self.imscale: return  # 1 pixel is bigger than the visible area
            self.imscale *= self.__delta
            scale        *= self.__delta

        # Take appropriate image from the pyramid
        k = self.imscale * self.__ratio  # temporary coefficient
        self.__curr_img = max(0, min((-1) * int(log(k, self.__reduction)), len(self.sizes) - 1))
        self.scale11 = k * pow(self.__reduction, max(0, self.__curr_img))

        self.canvas.scale('all', x, y, scale, scale)  # rescale all objects
        if not redraw:
            self.__show_image()
    