from math import log, pow
from time import perf_counter
from warnings import catch_warnings, simplefilter
from threading import Thread, Event

import logging
from gc import collect
from PIL import Image, ImageTk

import tkinter as tk
from tkinter import ttk
from vlc import PlaybackMode

logger = logging.getLogger("Canvasimage")
logger.setLevel(logging.ERROR)
handler = logging.StreamHandler()
handler.setLevel(logging.ERROR)
formatter = logging.Formatter('%(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

class AutoScrollbar(ttk.Scrollbar):
    """ A scrollbar that hides itself if it's not needed. Works only for grid geometry manager """
    def set(self, lo, hi):
        if float(lo) <= 0.0 and float(hi) >= 1.0:
            self.grid_remove()
        else:
            self.grid()
            ttk.Scrollbar.set(self, lo, hi)

    def pack(self, **kw):
        raise tk.TclError('Cannot use pack with the widget ' + self.__class__.__name__)

    def place(self, **kw):
        raise tk.TclError('Cannot use place with the widget ' + self.__class__.__name__)

class CanvasImage:
    """ Display and zoom image """
    "Initialization"
    
    def __init__(self, master, imagewindowgeometry, imageobj, gui):
        self.timer = gui.fileManager.timer
        self.timer.start()
        self.time1 = perf_counter()
        self.time11 = perf_counter()
        self.imageid = None
        self.obj = imageobj
        self.gui = gui
        aa = ""
        self.gui.frametimeinfo.set(f"{aa:>4}")
        self.gui.first_render.set("F:")
        # Lists, attributes and other flags.
        self.lazy_index = 0
        self.lazy_loading = True    # Flag that turns off when all frames have been loaded to frames.

        # Logic for quick displaying of first frame.
        self.first = True           # Flag that turns off when the initial picture has been rendered.
        self.replace_await = False  # Flag tells whether we want to render a second better quality on top
        # Picture sizes
        try:
            self.file_size = round(self.obj.file_size/1.048576/1000000,2) #file size in MB
        except Exception as e:
            print("ERROR IN CANVAIMAGE:", e)
            self.file_size = round(1.5)

        "Gui stats"
        self.gui.name_ext_size.set(self.obj.name)
        self.gui.frameinfo.set(f"F/D: -")
        self.gui.info.set(f"Size: {self.file_size} MB")
        # The initial quality of placeholder image, used to display the image just a bit faster.
        if gui.filter_mode.upper() in self.gui.accepted_modes:
            self.__first_filter = getattr(Image.Resampling, gui.filter_mode.upper())
        else:
            self.__first_filter = Image.Resampling.BILINEAR

        self.__filter = Image.Resampling.LANCZOS  # The end qualtiy of the image. #NEAREST, BILINEAR, BICUBIC

        # Image scaling defaults
        self.imscale = 1.0  # Scale for the canvas image zoom
        self.__delta = 1.15  # Zoom step magnitude
        # Decide if this image huge or not
        self.__huge = False # huge or not
        self.__huge_size = 14000 # define size of the huge image
        self.__band_width = 1024 # width of the tile band
        # Fix for lag in first image that is placed!
        self.lag_prevention = True
        # Video handling (if path points to video file, we must use its thumb to get its size.)
        self.path = self.obj.path
        # Window
        geometry_width, geometry_height = imagewindowgeometry.split('x',1)

        self.style = ttk.Style()
        self.style.configure("bg.TFrame", background=gui.viewer_bg) # no white flicker screens

        """ Initialization of frame in master widget"""
        if self.gui.imframe == None:
            self.gui.imframe = ttk.Frame(master, style="bg.TFrame")
            self.gui.hbar1 = None
            self.gui.vbar1 = None
        # Vertical and horizontal scrollbars for __imframe
        
        # Create canvas and bind it with scrollbars. Public for outer classes
        self.canvas = tk.Canvas(self.gui.imframe, bg=gui.viewer_bg,
                                highlightthickness=0, width=geometry_width, height = geometry_height)  # Set canvas dimensions to remove scrollbars
        self.canvas.grid(row=0, column=0, sticky='nswe') # Place into grid
        #self.canvas.grid_propagate(True) #Experimental
        self.canvas_height = int(geometry_height)
        self.canvas_width = int(geometry_width)
        #self.canvas.update() #profile

        # Handle .mp4, .webm - VLC (audio)
        if self.obj.path.lower().endswith((".mp4",".webm")): # Is video
            self.file_type = self.gui.file_types[1]
            self.imwidth, self.imheight = self.obj.dimensions
            a = f"{self.imwidth}x{self.imheight}"
            self.gui.info.set(f"Size: {self.file_size:>6.2f} MB {a:>10}")
            self.handle_video()
            self.binds(animated=True)
            return

        """Opening the image""" #fix
        Image.MAX_IMAGE_PIXELS = 1000000000  # suppress DecompressionBombError for the big image
        with catch_warnings():  # suppress DecompressionBombWarning
            simplefilter('ignore')
            self.image = Image.open(self.path)  # open image, but down't load it
        self.imwidth, self.imheight = self.image.size  # public for outer classes
        a = f"{self.imwidth}x{self.imheight}"
        self.gui.info.set(f"Size: {self.file_size:>6.2f} MB {a:>10}")
        if self.imwidth * self.imheight > self.__huge_size * self.__huge_size and \
           self.image.tile[0][0] == 'raw':  # only raw images could be tiled
            self.__huge = True  # image is huge
            self.__offset = self.image.tile[0][2]  # initial tile offset
            self.__tile = [self.image.tile[0][0],  # it have to be 'raw'
                           [0, 0, self.imwidth, 0],  # tile extent (a rectangle)
                           self.__offset,
                           self.image.tile[0][3]]  # list of arguments to the decoder
        self.__min_side = min(self.imwidth, self.imheight)  # get the smaller image side
        # Set ratio coefficient for image pyramid
        self.__ratio = max(self.imwidth, self.imheight) / self.__huge_size if self.__huge else 1.0
        self.__curr_img = 0  # current image from the pyramid
        self.__scale = self.imscale * self.__ratio  # image pyramid scale
        self.__reduction = 2 # reduction degree of image pyramid
        self.__pyramid = []
        self.pyramid = []
        


        # Handle .gif, .webp - Custom renderer
        if self.obj.path.lower().endswith((".gif",".webp")):
            self.framecount = self.image.n_frames
            if self.framecount > 1:
                self.file_type = self.gui.file_types[2]
                self.gui.frameinfo.set(f"F/D: {0}/{0}/{self.obj.framecount}")
                self.handle_gif()
            else:
                self.__pyramid = [self.smaller()] if self.__huge else [Image.open(self.path)]
                self.file_type = self.gui.file_types[0]
                self.pyramid_ready = Event()
                self.first_rendered = Event()
                self.handle_static()
            self.binds(animated=True)
        # Handle static images
        else:
            self.__pyramid = [self.smaller()] if self.__huge else [Image.open(self.path)]
            self.file_type = self.gui.file_types[0]
            self.pyramid_ready = Event()
            self.first_rendered = Event()
            self.handle_static()
            self.binds(animated=False)
        
        self.canvas.bind('<Configure>', lambda event: self.__show_image())  # canvas is resized from displayimage, time to show image.
    
    def binds(self, animated):
        # Bind events to the Canvas
        self.canvas.bind('<ButtonPress-1>', self.__move_from)  # remember canvas position / panning
        #self.canvas.bind('<ButtonRelease-1>', lambda event: self.time_set(event))  # remember canvas position / panning (navigator)
        self.canvas.bind('<B1-Motion>',     self.__move_to)  # move canvas to the new position / panning
        if not animated:
            self.canvas.bind('<MouseWheel>', self.__wheel)  # zoom for Windows and MacOS, but not Linux / zoom pyramid.
            self.canvas.bind('<Button-5>',   self.__wheel)  # zoom for Linux, wheel scroll down
            self.canvas.bind('<Button-4>',   self.__wheel)  # zoom for Linux, wheel scroll up
            "Video"
    def handle_video(self):
        "Handles videos"
        def video_print_data():
            try:
                if self.gui.dock_view.get():
                    #self.gui.bind("<Configure>", resize_video)
                    pass
                elif hasattr(self.gui, "second_window"):
                    #self.gui.second_window.bind("<Configure>", resize_video)
                    pass
                if hasattr(self, "media"):
                    self.media.parse()
                    total_seconds = int(self.media.get_duration() / 1000)
                    minutes = total_seconds // 60
                    seconds = total_seconds % 60
                    self.gui.frameinfo.set(f"F/D: {minutes}:{seconds}")
            except:
                pass  # thread closed

        def resize_video(*args):
            "Canvas resizer"
            try:
                if perf_counter() - self.time11 < 0.1:
                    return
                if self.gui.middlepane_frame.winfo_width() == 1:
                    return
                time2 = perf_counter()
                if time2 - self.time1 > 0.09:
                    self.time1 = time2
                else:
                    return
                if not hasattr(self, "imwidth"):
                    return
            except:
                pass

            try:
                if not hasattr(self, "canvas_height") or not hasattr(self, "imwidth") or not hasattr(self, "imheight"):
                    return
                if self.gui.dock_view.get():
                    new_width = self.gui.middlepane_frame.winfo_width() + 2
                    aspect_ratio = self.imwidth / self.imheight
                    new_height = int(new_width / aspect_ratio)
                    # Update the video canvas size
                    if self.video_frame.winfo_width() == new_width or self.video_frame.winfo_height() == new_height:
                        return
                    self.video_frame.config(width=new_width, height=new_height)
                    # Resize the container to include the control height as well
                    self.video_container.config(width=new_width, height=new_height + control_height)
                    pady1 = (self.canvas_height - (new_height + control_height)) // 2
                    if pady1 > 0:
                        self.video_container.grid(pady=pady1, sticky="nsew")
                else:
                    new_width = self.gui.second_window.winfo_width() + 2
                    aspect_ratio = self.imwidth / self.imheight
                    new_height = int(new_width / aspect_ratio)
                    if self.video_frame.winfo_width() == new_width or self.video_frame.winfo_height() == new_height:
                        return
                    self.video_frame.config(width=new_width, height=new_height)
                    self.video_container.config(width=new_width, height=new_height + control_height)
                    self.video_container.grid(pady=((self.canvas_height - (new_height + control_height)) // 2), sticky="nsew")
            except Exception as e:
                pass

        # Setup VLC playback as before
        path = self.obj.path
        self.vlc_instance = self.gui.vlc_instance
        self.media_list_player = self.vlc_instance.media_list_player_new()

        self.media_list = self.vlc_instance.media_list_new()
        self.media = self.vlc_instance.media_new(path)
        self.media_list.add_media(self.media)
        self.media_list_player.set_media_list(self.media_list)
        self.player = self.media_list_player.get_media_player()

        new_width = self.canvas_width
        new_height = self.canvas_height
        aspect_ratio = self.imwidth / self.imheight
        ratio = new_width / self.imwidth

        if new_width / new_height > aspect_ratio:
            new_width = int(new_height * aspect_ratio)
        else:
            new_height = int(new_width / aspect_ratio)
        new_width += 2  # divider

        # Define the control area height (for timeline and volume)
        control_height = 35

        # Create a container frame to hold the video and controls.
        self.video_container = tk.Frame(self.canvas, bg=self.gui.viewer_bg,
                                        width=new_width, height=new_height + control_height)
        self.video_container.grid_propagate(False)  # prevent automatic resizing
        try:
            self.video_container.grid(row=0, column=0,
                                  padx=(((self.canvas_width + 2) - new_width) // 2),
                                  pady=max(0,((self.canvas_height - (new_height + control_height)) // 2)),
                                  sticky="nsew")
        except:
            return

        # Create the video canvas inside the container
        self.video_frame = tk.Canvas(self.video_container,
                                     width=new_width,
                                     height=new_height,
                                     bg=self.gui.viewer_bg,
                                     highlightbackground="black",
                                     highlightthickness=0,
                                     borderwidth=0)
        self.video_frame.grid(row=0, column=0)

        style = ttk.Style()

        style.configure("Horizontal.TScale",
                background=self.gui.viewer_bg)
        
        # Create a control frame for the sliders under the video
        self.controls_frame = tk.Frame(self.video_container, bg=self.gui.viewer_bg)
        self.controls_frame.grid(row=1, column=0, sticky="ew")
        # Configure grid: timeline slider in column 0, volume slider in column 1
        self.controls_frame.columnconfigure(0, weight=3, minsize=0)
        self.controls_frame.columnconfigure(1, weight=1, minsize=0)

        # Timeline slider with click-to-seek functionality
        self.timeline_slider = ttk.Scale(self.controls_frame,
                                        from_=0,
                                        to=self.media.get_duration(),
                                        orient=tk.HORIZONTAL,
                                        style="Horizontal.TScale",
                                        command=self.seek_video)
        
        self.timeline_slider.grid(row=0, column=0, sticky="ew", padx=(5, 2), pady=5)

        def timeline_click(event):
            slider = event.widget
            slider_width = slider.winfo_width()
            click_fraction = event.x / slider_width
            new_value = float(slider.cget("from")) + (float(slider.cget("to")) - float(slider.cget("from"))) * click_fraction
            slider.set(new_value)
            self.seek_video(new_value)
        
        

        # Bind click event on the timeline slider so that clicking anywhere jumps to that point
        self.timeline_slider.bind("<Button-1>", timeline_click)

        # Volume slider: range from 0 to 100
        self.volume_slider = ttk.Scale(self.controls_frame,
                                      from_=0,
                                      to=100,
                                      orient=tk.HORIZONTAL,
                                      style="Horizontal.TScale",
                                      command=self.change_volume)
        self.volume_slider.set(self.gui.volume)
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
        self.imscale = ratio

        self.media_list_player.set_playback_mode(PlaybackMode.loop)
        self.media_list_player.play()

        self.gui.first_render.set(f"F: {self.timer.stop()}")

        Thread(target=video_print_data, daemon=True).start()

        # Start polling to update timeline slider maximum when media duration is valid
        self.disable = False
        self.canvas.after(100, self.update_timeline_slider)

    def update_slider_position(self):
        "Updates the timeline slider to match the current video position."
        if hasattr(self, "player") and self.player.is_playing():
            self.disable = True
            self.timeline_slider.set(self.player.get_time())
            self.disable = False
        
            self.canvas.after(500, self.update_slider_position)

    def update_timeline_slider(self):
        "Poll until a valid media duration is available, then update the timeline slider"
        duration = self.media.get_duration()
        if duration > 0:
            self.timeline_slider.config(to=duration)
            self.canvas.after(500, self.update_slider_position)
        else:
            self.canvas.after(100, self.update_timeline_slider)

    def seek_video(self, value):
        "Callback to jump to a specific time in the video."
        if not self.disable:
            try:
                new_time = int(float(value))
                self.player.set_time(new_time)
            except Exception as e:
                pass

    def change_volume(self, value):
        "Callback to adjust the audio level."
        try:
            new_volume = int(float(value))
            self.player.audio_set_volume(new_volume)
            self.gui.volume = new_volume
        except Exception as e:
            pass




    "Static"
    
    def handle_static(self):
        def lazy_pyramid(w, h):
            "Generates zoom pyramid"
            def render_second():
                self.first_rendered.wait(timeout=2)
                self.replace_await = True
                try:
                    self.__show_image()
                except Exception as e:
                    logger.error(f"Error rendering second: {e}")

            try:
                if self.file_size > self.gui.quick_preview_size_threshold:
                    Thread(target=render_second, daemon=True).start()
                self.pyramid = [Image.open(self.path)]
                while w > 512 and h > 512: # stop this if program closing
                    w /= self.__reduction
                    h /= self.__reduction
                    w = int(w)
                    h = int(h)
                    self.pyramid.append(self.pyramid[-1].resize((w,h), self.__filter))
                    self.pyramid_ready.set()
                self.pyramid_ready.set()
                self.__pyramid = self.pyramid # pass the whole zoom pyramid when it is ready.
                #self.pyramid.clear()
                #del self.__pyramid
            except Exception as e:
                logger.debug(f"Thread caught (lazy_pyramid): {e}")
        "Handles static images"
        w, h = self.__pyramid[-1].size
        #self.gui.size.set(f"{self.file_size} MB")
        Thread(target=lazy_pyramid, args=(w,h), daemon=True).start()
        self.container = self.canvas.create_rectangle((0, 0, self.imwidth, self.imheight), width=0)

    "GIF"
    def handle_gif(self):
        "Handles gifs"
        def load_frames(image1, new_width, new_height):
            "Generates frames for gif, webp"
            try:
                image1.seek(0) # remove if doesnt eliminate first frame bug
                frame_frametime = image1.info.get('duration', self.delay)
                if frame_frametime == 0:
                    self.delay = 100
                else:
                    self.delay = frame_frametime
                self.frametimes.append(frame_frametime)
                frame = ImageTk.PhotoImage(image1.resize((new_width, new_height)), Image.Resampling.LANCZOS)
                self.frames.append(frame)
                frame_width = frame.width()
                frame_height = frame.height()
                
                x_offset = (self.canvas_width - frame_width) // 2
                y_offset = (self.canvas_height - frame_height) // 2
                self.imageid = self.canvas.create_image(x_offset, y_offset, anchor='nw', image=frame)

                self.gui.first_render.set(f"F: {self.timer.stop()}")
                temp = self.framecount
                self.framecount = 1
                self.first = False # Flags that the first has been created
                try:
                    for i in range(1, temp): #Check here to not continue if we stop the program

                        image1.seek(i)
                        frame_frametime = image1.info.get('duration', self.delay)
                        frame = ImageTk.PhotoImage(image1.resize((new_width, new_height)), Image.Resampling.LANCZOS)
                        self.frametimes.append(frame_frametime)
                        self.frames.append(frame)
                        self.framecount += 1
                        self.gui.frameinfo.set(f"F/D: {self.lazy_index}/{len(self.frames)}/{self.framecount}")
                        self.gui.frametimeinfo.set(f"{self.frametimes[self.lazy_index]} ms")
                    if all(i == 0 for i in self.frametimes):
                        for i in range(len(self.frametimes)):
                            self.frametimes[i] = self.delay
                    self.gui.first_render.set(f"{self.gui.first_render.get()[:-2]}+{self.timer.stop()}")
                except:
                    pass
                    
                

                self.lazy_loading = False # Lower the lazy_loading flag so animate can take over.
                self.image.close()
            except AttributeError as e:
                collect()
                logger.debug(f"Error loading frames: {e}")
                pass
            except OSError as e:
                collect()
                logger.debug(f"Error loading frames: {e}")
                pass
            except ValueError as e:
                collect()
                logger.debug(f"Error loading frames: {e}")
                pass
            except Exception as e:
                collect()
                logger.debug(f"Error loading frames: {e}")
        def lazy_load():
            def animate_image():
                "Simple gif looper"
                try:
                    self.canvas.itemconfig(self.imageid, image=self.frames[self.lazy_index])
                    self.canvas.after(self.frametimes[self.lazy_index], animate_image)
                    self.lazy_index = (self.lazy_index + 1) % len(self.frames)
                    a = f"{self.lazy_index}/{len(self.frames)}/{self.framecount}"
                    self.gui.frameinfo.set(f"F/D: {a:>4}")
                    b = f"{self.frametimes[self.lazy_index]} ms"
                    self.gui.frametimeinfo.set(f"{b:>4}")
                except:
                    return

            try:  
                "Display new frames as soon as possible, when all loaded, switch to simple looping method"
                if not self.lazy_loading: # When all frames are loaded, we switch to just looping
                    logger.debug("All frames loaded, stopping lazy_load")
                    animate_image()
                    return
                elif not self.frames or not len(self.frames) > self.lazy_index: #if the list is still empty. Wait.
                    logger.debug("Buffering") #Ideally 0 buffering, update somethng so frames is initialzied quaranteed.
                    self.canvas.after(self.delay, lazy_load)
                    return
                elif self.lazy_index != self.framecount:
                    #Checks if more frames than index is trying and less than max allowed.
                    self.canvas.itemconfig(self.imageid, image=self.frames[self.lazy_index])
                    self.canvas.after(self.frametimes[self.lazy_index], lazy_load)
                    self.lazy_index = (self.lazy_index + 1) % self.framecount
                    a = f"{self.lazy_index}/{len(self.frames)}/{self.framecount}"
                    self.gui.frameinfo.set(f"F/D: {a:>4}")
                    b = f"{self.frametimes[self.lazy_index]} ms"
                    self.gui.frametimeinfo.set(f"{b:>4}")
                    return
                else:
                    logger.error("Error in lazy load, take a look")
                    self.canvas.after(self.delay, lazy_load)
            except:
                return
        self.frametimes = []
        self.delay = 0
        self.frames = []            # Stores loaded frames for .Gif, .Webp
        new_width = self.canvas_width
        new_height = self.canvas_height
        aspect_ratio = self.imwidth / self.imheight
        if new_width / new_height > aspect_ratio:
            new_width = int(new_height*aspect_ratio)
        else:
            new_height = int(new_width / aspect_ratio)
        self.imageid = None
        self.load_frames_thread = Thread(target=load_frames, args=(self.image, new_width, new_height), daemon=True).start()
        lazy_load()
        self.container = self.canvas.create_rectangle((0, 0, self.imwidth, self.imheight), width=0)

    "Display"
    def __show_image(self):
        "Heavily modified to support gif"
        try:
            if not self.file_type == "STATIC": #Let another function handle if animated
                if self.frames:
                    pass
            else:

                """ Show image on the Canvas. Implements correct image zoom almost like in Google Maps """
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

                if int(x2 - x1) > 0 and int(y2 - y1) > 0:  # show image if it in the visible area
                    if self.__huge and self.__curr_img < 0:  # show huge image
                        h = int((y2 - y1) / self.imscale)  # height of the tile band
                        self.__tile[1][3] = h  # set the tile band height
                        self.__tile[2] = self.__offset + self.imwidth * int(y1 / self.imscale) * 3
                        self.image.close()
                        self.image = Image.open(self.path)  # reopen / reset image
                        self.image.size = (self.imwidth, h)  # set size of the tile band
                        self.image.tile = [self.__tile]
                        image = self.image.crop((int(x1 / self.imscale), 0, int(x2 / self.imscale), h))
                        imagetk = ImageTk.PhotoImage(image.resize((int(x2 - x1), int(y2 - y1)), self.__filter)) #new resize for no reason?
                        imageid = self.canvas.create_image(max(box_canvas[0], box_img_int[0]),
                                                       max(box_canvas[1], box_img_int[1]),
                                                    anchor='nw', image=imagetk)
                    else:  # show normal image
                        if self.first:
                            img = self.__pyramid[max(0, self.__curr_img)]
                            if self.file_size > self.gui.quick_preview_size_threshold:
                                render_filter = self.__first_filter
                            else:
                                render_filter = self.__filter if (self.imwidth > 256 and self.imheight > 256) else Image.Resampling.NEAREST

                            rendered = img.resize((int(x2 - x1), int(y2 - y1)), render_filter)
                            imagetk = ImageTk.PhotoImage(rendered)
                            self.imageid = self.canvas.create_image(max(box_canvas[0], box_image[0]),
                                                                     max(box_canvas[1], box_image[1]),
                                                                     anchor='nw', image=imagetk)
                            self.canvas.imagetk = imagetk  # Cache reference
                            self.first = False
                            self.first_rendered.set()  # Signal that the quick preview is done.
                            self.gui.first_render.set(f"F: {self.timer.stop()}")
                        elif self.replace_await: # only render second time if needed.
                            self.replace_await = False
                            img = self.__pyramid[max(0, self.__curr_img)]
                            rendered = img.resize((int(x2 - x1), int(y2 - y1)), self.__filter)
                            imagetk = ImageTk.PhotoImage(rendered)
                            self.canvas.itemconfig(self.imageid, image=imagetk)
                            self.canvas.imagetk = imagetk
                            self.gui.first_render.set(f"{self.gui.first_render.get()[:-2]}+{self.timer.stop()}")

                        else:
                            if self.lag_prevention:
                                self.manual_wheel() ## Initially displays pos 0 from pyramid, this fixes it. Probably needed because the later entries to the pyramid arent created yet when rendering the first picture!

                                self.lag_prevention = False

                            img = self.__pyramid[max(0, self.__curr_img)]
                            cropped = img.crop((int(x1 / self.__scale), int(y1 / self.__scale),
                                                int(x2 / self.__scale), int(y2 / self.__scale)))
                            rendered = cropped.resize((int(x2 - x1), int(y2 - y1)), self.__filter)
                            imagetk = ImageTk.PhotoImage(rendered)
                            self.imageid = self.canvas.create_image(max(box_canvas[0], box_img_int[0]),
                                                       max(box_canvas[1], box_img_int[1]),
                                                    anchor='nw', image=imagetk)
                            self.canvas.imagetk = imagetk
        except AttributeError as e:
            logger.debug("Failed to render image to canvasimage. Err1. (Safe)", e)
        except Exception as e:
            logger.debug("Failed to render image to canvasimage. Err2. (Safe~)", e)
    "Dont touch"
    def __move_from(self, event):
        "Remember previous coordinates for scrolling with the mouse"
        self.canvas.focus_set()
        self.canvas.scan_mark(event.x, event.y)
    def __move_to(self, event):
        "Drag (move) canvas to the new position"
        self.canvas.scan_dragto(event.x, event.y, gain=1)
        self.__show_image()  # zoom tile and show it on the canvas
    def __wheel(self, event=None, direction=None):
        "Zoom with mouse wheel"
        if self.file_type == "VIDEO":
        #    if (event and (event.num == 5 or event.delta == -120)) or direction == "down":  # scroll down, smaller
        #        self.imscale /= self.__delta
        #    elif (event and (event.num == 4 or event.delta == 120)) or direction == "up":  # scroll up, bigger
        #        self.imscale *= self.__delta
        #    self.player.video_set_scale(self.imscale)
            return
        if event:
            x = self.canvas.canvasx(event.x)
            y = self.canvas.canvasy(event.y)

            """ re-enable this if you dont want scrolling outside the image """
            #if self.outside(x, y): return  # zoom only inside image area
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
        self.__curr_img = min((-1) * int(log(k, self.__reduction)), len(self.__pyramid) - 1)
        self.__scale = k * pow(self.__reduction, max(0, self.__curr_img))

        self.canvas.scale('all', x, y, scale, scale)  # rescale all objects

        # Redraw some figures before showing image on the screen
        self.__show_image()

        #logger.debug(f"after scroll event {self.__curr_img}, {(max(0, self.__curr_img))}")
    def manual_wheel(self):
        "Fixes laggy panning on first picture"
        k = self.imscale * self.__ratio # temporary coefficient
        self.__curr_img = min((-1) * int(log(k, self.__reduction)), len(self.__pyramid) - 1) #presumably changes the displayed image. Yes. We need pyramid to change the iterated frames.
        self.__scale = k * pow(self.__reduction, max(0, self.__curr_img)) #positioning dont change

    def smaller(self):
        "Resize image proportionally and return smaller image"
        w1, h1 = float(self.imwidth), float(self.imheight)
        w2, h2 = float(self.__huge_size), float(self.__huge_size)
        aspect_ratio1 = w1 / h1
        aspect_ratio2 = w2 / h2  # it equals to 1.0
        if aspect_ratio1 == aspect_ratio2:
            image = Image.new('RGB', (int(w2), int(h2)))
            k = h2 / h1  # compression ratio
            w = int(w2)  # band length
        elif aspect_ratio1 > aspect_ratio2:
            image = Image.new('RGB', (int(w2), int(w2 / aspect_ratio1)))
            k = h2 / w1  # compression ratio
            w = int(w2)  # band length
        else:  # aspect_ratio1 < aspect_ration2
            image = Image.new('RGB', (int(h2 * aspect_ratio1), int(h2)))
            k = h2 / h1  # compression ratio
            w = int(h2 * aspect_ratio1)  # band length
        i, j, n = 0, 1, round(0.5 + self.imheight / self.__band_width)
        while i < self.imheight:
            print('\rOpening image: {j} from {n}'.format(j=j, n=n), end='')
            band = min(self.__band_width, self.imheight - i)  # width of the tile band
            self.__tile[1][3] = band  # set band width
            self.__tile[2] = self.__offset + self.imwidth * i * 3  # tile offset (3 bytes per pixel)
            self.image.close()
            self.image = Image.open(self.path)  # reopen / reset image
            self.image.size = (self.imwidth, band)  # set size of the tile band
            self.image.tile = [self.__tile]  # set tile
            cropped = self.image.crop((0, 0, self.imwidth, band))  # crop tile band
            image.paste(cropped.resize((w, int(band * k)+1), self.__filter), (0, int(i * k)))
            i += band
            j += 1
        print('\r' + 30*' ' + '\r', end='')  # hide printed string
        return image
    def grid(self, **kw):
        """ Put CanvasImage widget on the parent widget """
        self.gui.imframe.grid(**kw)  # place CanvasImage widget on the grid
        self.gui.imframe.grid(sticky='nswe')  # make frame container sticky
        self.gui.imframe.rowconfigure(0, weight=0)  # make frame expandable
        self.gui.imframe.columnconfigure(0, weight=0) #weight = to remove scrollbars
    def pack(self, **kw):
        """ Exception: cannot use pack with this widget """
        raise Exception('Cannot use pack with the widget ' + self.__class__.__name__)
    def place(self, **kw):
        """ Exception: cannot use place with this widget """
        raise Exception('Cannot use place with the widget ' + self.__class__.__name__)
    def outside(self, x, y):
        "Checks if the point (x,y) is outside the image area"
        bbox = self.canvas.coords(self.container)  # get image area
        if bbox[0] < x < bbox[2] and bbox[1] < y < bbox[3]:
            return False  # point (x,y) is inside the image area
        else:
            return True  # point (x,y) is outside the image area
    def crop(self, bbox):
        "Crop rectangle from the image and return it"
        if self.__huge:     # image is huge and not totally in RAM
            band = bbox[3] - bbox[1]    # width of the tile band
            self.__tile[1][3] = band    # set the tile height
            self.__tile[2] = self.__offset + self.imwidth * bbox[1] * 3    # set offset of the band
            self.image.close()
            self.image = Image.open(self.path)    # reopen / reset image
            self.image.size = (self.imwidth, band)    # set size of the tile band
            self.image.tile = [self.__tile]
            return self.image.crop((bbox[0], 0, bbox[2], band))
        else:    # image is totally in RAM
            return self.__pyramid[0].crop(bbox)

    def rescale(self, scale):
        "Rescales the image to fit image viewer"
        if self.file_type == "STATIC":
            self.__scale=scale
            self.imscale=scale

            self.canvas.scale('all', self.canvas_width, 0, scale, scale)  # rescale all objects
            #self.canvas.update_idletasks()
    def center_image(self, viewer_x_centering, viewer_y_centering):
        """ Center the image on the canvas """
        if self.file_type == "STATIC":
            canvas_width = self.canvas_width
            canvas_height = self.canvas_height

            # Calculate scaled image dimensions
            scaled_image_width = self.imwidth * self.imscale
            scaled_image_height = self.imheight * self.imscale

            # Calculate offsets to center the image
            if viewer_x_centering:
                x_offset = (canvas_width - scaled_image_width)-(canvas_width - scaled_image_width)/2
            else:
                x_offset = 0
            if viewer_y_centering:
                y_offset = (canvas_height - scaled_image_height)/2
            else:
                y_offset = 0

            # Update the position of the image container
            self.canvas.coords(self.container, (x_offset), (y_offset), (x_offset + scaled_image_width), (y_offset + scaled_image_height))
    def destroy(self):
        def stop_player(player):
            try:
                player.stop()
            except Exception as e:
                print("destroying error:", e)
            try:
                player.release()
            except Exception as e:
                print("destroying error:", e)
        "ImageFrame destructor"
        # Video
        if hasattr(self, "player"):
            
            try:
                self.video_frame.grid_forget()
                aa = Thread(target=stop_player, args=(self.player,), daemon=True) # bug here
                aa.start()
                aa.join(timeout=1) ### bug here?
                self.video_frame_id = None
                self.player = None
                self.video_frame = None
                self.media_list_player = None
                self.media_list = None
                self.media = None
                del self.player


            except Exception as e:
                logger.debug("Error closing player", e)

        if hasattr(self, "frames"):
            for x in self.frames:
                del x
            self.frames.clear()
            del self.frames
            
        if hasattr(self, "frametimes"):
            for x in self.frametimes:
                del x
            self.frametimes.clear()
            del self.frametimes
            
        if hasattr(self, "imageid"):
            del self.imageid
        if hasattr(self, "container"):
            del self.container
        if hasattr(self, "image"):
            try:
                self.image.close()
            except Exception as e:
                logger.debug("Canvasimage: Img couldnt be closed")
            finally:
                del self.image
        if hasattr(self, "__pyramid"):
            try:
                self.__pyramid[0].close()
            except Exception as e:
                logger.debug(f"Error in closing __pyramid: {e}")
            finally:
                self.__pyramid.clear()
                del self.__pyramid
        if hasattr(self, "pyramid"):
            self.pyramid.clear()
            del self.pyramid
        if hasattr(self, "canvas"):
            self.canvas.unbind('<ButtonPress-1>')  # Unbind left mouse button press
            self.canvas.unbind('<ButtonRelease-1>')  # Unbind left mouse button release
            self.canvas.unbind('<B1-Motion>')  # Unbind left mouse button motion
            self.canvas.unbind('<MouseWheel>')  # Unbind mouse wheel for zoom
            self.canvas.unbind('<Button-5>')  # Unbind mouse wheel scroll down for Linux
            self.canvas.unbind('<Button-4>')  # Unbind mouse wheel scroll up for Linux
            self.canvas.destroy()
            del self.canvas
        if hasattr(self, "style"):
            del self.style
        if hasattr(self, "__curr_img"):
            del self.__curr_img
        if hasattr(self, "obj"):
            del self.obj
        if hasattr(self, "file_type"):
            del self.file_type
            del self.imwidth
            del self.imheight
            del self.canvas_height
            del self.canvas_width
            del self.imscale
        del self
        collect()
    def destroy_imframe(self):
        if hasattr(self.gui, "imframe") and self.gui.imframe != None:
            self.gui.imframe.destroy()
            self.gui.imframe=None
            if hasattr(self, "hbar"):
                self.gui.hbar1.destroy()
                del self.gui.hbar1
            if hasattr(self, "vbar"):
                self.gui.vbar1.destroy()
                del self.gui.vbar1
        # Garbage collection INFO
        #objects = gc.get_objects()
#
        ## Specify the file name
        #file_name = 'gc_objects.txt'
#
        ## Open the file in write mode with utf-8 encoding
        #with open(file_name, 'w', encoding='utf-8') as file:
        #    for obj in objects:
        #        # Write the string representation of each object to the file
        #        file.write(f'{repr(obj)}\n')
#
        #print(f'Objects have been written to {file_name}')
