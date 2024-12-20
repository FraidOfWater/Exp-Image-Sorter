# -*- coding: utf-8 -*-
from math import log, pow
from warnings import catch_warnings, simplefilter
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
from threading import Thread, Event
from time import time, perf_counter
import logging
import vlc
from os.path import getsize
#import only thread and event, import only time, import only some math.
#First launch second_window_viewer doesn't work.
#Videos broken on second_viewer.
#Navigator not implemented.
#First frame of gif bugged.
#Resizing for all others too beside video.
#Zooming for all others besides static.
#Zooming for video? Experimental, not needed.
#White flicker when starting video players from scratch. has to do with resizer, persistent vlc session?
logger = logging.getLogger("Canvasimage")
logger.setLevel(logging.ERROR) 
handler = logging.StreamHandler()
handler.setLevel(logging.ERROR)
formatter = logging.Formatter('%(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

class Timer:
    "Timer for benchmarking"
    def __init__(self):
        self.creation_time = None
    def start(self):
        self.creation_time = perf_counter()
    def stop(self):
        current_time = perf_counter()
        elapsed_time = current_time - self.creation_time
        return elapsed_time

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
    def __init__(self, master, imagewindowgeometry, viewer_colour, imageobj, gui):
        self.timer = Timer()
        self.timer.start()
        self.obj = imageobj
        self.gui = gui
        # Lists, attributes and other flags.
        self.frames = []            # Stores loaded frames for .Gif, .Webp
        self.original_frames = []   # Could be used for zooming logic
        self.default_delay = tk.BooleanVar()    # Frame refresh time. Unique for each frame, or use singular, default reported by image?
        self.default_delay.set(True)            # Fallback to default_delay. This is linked to the button in GUI: default_delay_button.
        self.viewer_x_centering = gui.viewer_x_centering
        self.viewer_y_centering = gui.viewer_y_centering
        self.lazy_index = 0
        self.lazy_loading = True    # Flag that turns off when all frames have been loaded to frames.
        filter_mode = gui.filter_mode
        self.viewer_colour = viewer_colour
        # Navigator locking mechanism
        self.og_posx = 0
        self.og_posy = 0
        self.last_state = ""
        self.exit_lock = False
        # Logic for quick displaying of first frame.
        self.first = True           # Flag that turns off when the initial picture has been rendered.
        self.replace_first = True   # Flag that turns off when the pyramid has created the same picture in higher quality and rendered it.
        self.replace_await = False
        # Picture sizes
        self.file_size = round(self.obj.file_size/1.048576/1000000,2) #file size in MB
        # The initial quality of placeholder image, used to display the image just a bit faster.
        accepted_modes = ["NEAREST", "BILINEAR", "BICUBIC", "LANCZOS"]
        if filter_mode.upper() in accepted_modes:
            self.__first_filter = getattr(Image.Resampling, filter_mode.upper())
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
        self.count = 0
        self.count1 = 3
        # Video handling
        if hasattr(self.obj, 'video_thumb_path'):
            self.path = self.obj.video_thumb_path
        else:
            self.path = self.obj.path
        # Window
        geometry_width, geometry_height = imagewindowgeometry.split('x',1)

        """Opening the image""" #fix
        Image.MAX_IMAGE_PIXELS = 1000000000  # suppress DecompressionBombError for the big image
        with catch_warnings():  # suppress DecompressionBombWarning
            simplefilter('ignore')
            self.image = Image.open(self.path)  # open image, but down't load it
        self.imwidth, self.imheight = self.image.size  # public for outer classes
        self.image = self.image
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

        """ Initialization of frame in master widget"""
        self.__imframe = ttk.Frame(master)
        # Vertical and horizontal scrollbars for __imframe
        hbar = AutoScrollbar(self.__imframe, orient='horizontal')
        vbar = AutoScrollbar(self.__imframe, orient='vertical')
        # Create canvas and bind it with scrollbars. Public for outer classes
        self.canvas = tk.Canvas(self.__imframe, bg=self.viewer_colour,
                                highlightthickness=0, xscrollcommand=hbar.set,
                                yscrollcommand=vbar.set, width=geometry_width, height = geometry_height)  # Set canvas dimensions to remove scrollbars
        self.canvas.grid(row=0, column=0, sticky='nswe') # Place into grid
        #self.canvas.grid_propagate(True) #Experimental
        self.canvas_height = int(geometry_height)
        self.canvas_width = int(geometry_width)
        self.__pyramid = []
        self.pyramid = []
        if not self.obj.path.endswith((".mp4",".webm")):
            self.__pyramid = [self.smaller()] if self.__huge else [Image.open(self.path)]
        
        self.canvas.update()
        # Handle static images
        self.file_type = ["STATIC", "VIDEO", "ANIMATION"]
        if not self.obj.isanimated:
            self.file_type = self.file_type[0]
            self.handle_static()
            self.canvas.bind('<Configure>', lambda event: (self.__show_image()))  # canvas is resized from displayimage, time to show image.
        # Handle .mp4, .webm - VLC (audio)
        elif self.obj.name.get().endswith((".mp4", ".webm")):
            self.file_type = self.file_type[1]
            self.handle_video()
        # Handle .gif, .webp - Custom renderer
        else:
            self.file_type = self.file_type[2]
            self.handle_gif()
            self.canvas.bind('<Configure>', lambda event: (self.__show_image()))  # canvas is resized from displayimage, time to show image.

        # Bind events to the Canvas
        self.canvas.bind('<ButtonPress-1>', self.__move_from)  # remember canvas position / panning
        #self.canvas.bind('<ButtonRelease-1>', lambda event: self.time_set(event))  # remember canvas position / panning (navigator)
        self.canvas.bind('<B1-Motion>',     self.__move_to)  # move canvas to the new position / panning
        self.canvas.bind('<MouseWheel>', self.__wheel)  # zoom for Windows and MacOS, but not Linux / zoom pyramid.
        self.canvas.bind('<Button-5>',   self.__wheel)  # zoom for Linux, wheel scroll down
        self.canvas.bind('<Button-4>',   self.__wheel)  # zoom for Linux, wheel scroll up

        # Navigation
    
    "Video"
    def handle_video(self):
        "Handles videos"
        # Create a VLC instance
        self.vlc_instance = vlc.Instance('--quiet')
        self.media_list_player = self.vlc_instance.media_list_player_new()
        self.media_list = self.vlc_instance.media_list_new()
        media = self.vlc_instance.media_new(self.obj.path)
        self.media_list.add_media(media)
        self.media_list_player.set_media_list(self.media_list)
        self.player = self.media_list_player.get_media_player()
        
        self.video_frame = tk.Canvas(self.canvas,width=self.gui.middlepane_width, bg=self.viewer_colour, highlightbackground="black",highlightthickness=0, borderwidth=0)
        self.canvas.grid_rowconfigure(0, weight=1)  # Allow row to expand
        self.canvas.grid_columnconfigure(0, weight=1)  # Allow column to expand
        self.canvas.update()  # Wait until the canvas has finished creating.
        new_width = self.canvas_width
        new_height = self.canvas_height
        width, height = self.image.size
        aspect_ratio = width / height
        if self.canvas_width / self.canvas_height > aspect_ratio:
            new_height = self.canvas_height
            new_width = int(new_height * aspect_ratio)
        else:
            new_width = self.canvas_width
            new_height = int(new_width / aspect_ratio)
        new_width -= 4 #divider
        self.video_frame.config(width=new_width, height=new_height)
        self.video_frame.grid(pady=((self.canvas_height - new_height) // 2), sticky="nsew")
        self.video_frame_id = self.video_frame.winfo_id()
        self.player.set_hwnd(self.video_frame_id)
        self.media_list_player.set_playback_mode(vlc.PlaybackMode.loop)
        self.media_list_player.play()
        self.canvas.update()  # Wait until the canvas has finished creating.
        self.container = self.canvas.create_rectangle((0, 0, self.imwidth, self.imheight), width=0)
        Thread(target=media.parse, daemon=True).start()
        total_seconds = int(media.get_duration()/1000)
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        
        print(f"Size: {getsize(self.obj.path)/(1024*1024):.2f} MB. Duration: {minutes}:{seconds}")
        print(f"F:  {self.timer.stop()}\n")
        self.gui.bind("<Configure>", lambda event: (self.resize_to_window(self.file_type)))

    def resize_to_window(self, file_type):
        "Canvas resizer"
        # Get the current width of the middle pane
        new_width = self.gui.middlepane_frame.winfo_width()
        original_width, original_height = self.image.size
        aspect_ratio = original_width / original_height
        # Calculate the new height to maintain the aspect ratio
        new_height = int(new_width / aspect_ratio)

        if file_type == "VIDEO":
            # Update the video frame size
            self.video_frame.config(width=new_width, height=new_height)
            self.video_frame.grid(pady=((self.canvas_height - new_height) // 2), sticky="nsew")
            pass
            # Optionally, you can also update the canvas size if needed
            #self.canvas.config(width=new_width, height=new_height)
        elif file_type == "ANIMATION":
            pass
        else: # STATIC
            pass
        #self.media_player.video_set_scale(1)  # Set scale to 1 (100%)
        #self.player.video_set_size(self.gui.middlepane_width, 100)  # Set video size

    "Static"
    def handle_static(self):
        "Handles static images"
        w, h = self.__pyramid[-1].size
        self.pyramid_ready = Event()
        Thread(target=lambda:self.lazy_pyramid(w,h), daemon=True).start()
        #self.canvas.update()  # Wait until the canvas has finished creating.
        self.container = self.canvas.create_rectangle((0, 0, self.imwidth, self.imheight), width=0)
    def lazy_pyramid(self,w,h):
        "Generates zoom pyramid"
        try:
            Thread(target=self.helperr, daemon=True).start()
            self.pyramid = [Image.open(self.path)]
            self.replace_first = True
            while w > 512 and h > 512:
                w /= self.__reduction
                h /= self.__reduction
                self.pyramid.append(self.pyramid[-1].resize((int(w), int(h)), self.__filter))
            self.__pyramid = self.pyramid # pass the whole zoom pyramid when it is ready.
        except Exception as e:
            self.pyramid_ready.set() #failsafe
            logger.info("Thread caught:", e)
    def helperr(self):
        self.pyramid_ready.wait()
        self.replace_first = False
        self.replace_await = True
        try:
            self.__show_image()
        except Exception as e:
            print(e)

    "GIF"
    def handle_gif(self):
        "Handles gifs"
        try:
            self.length = self.obj.framecount
            new_width = self.canvas_width
            new_height = self.canvas_height
            width, height = self.image.size
            aspect_ratio = width / height
            if new_width / new_height > aspect_ratio:
                new_width = int(new_height*aspect_ratio)
            else:
                new_height = int(new_width / aspect_ratio)
            self.new_size = (new_width, new_height)
            self.load_frames_thread = Thread(target=self.load_frames, daemon=True).start()
            self.lazy_load()
            self.canvas.update()  # Wait until the canvas has finished creating.
            self.container = self.canvas.create_rectangle((0, 0, self.imwidth, self.imheight), width=0)
        except Exception as e:
            logger.error(f"Can't access imageinfo. {e}")
    def load_frames(self):
        "Generates frames for gif, webp"
        try:
            frame = ImageTk.PhotoImage(self.image.resize(self.new_size), Image.Resampling.LANCZOS)
            canvas_width = self.canvas_width
            canvas_height = self.canvas_height
            frame_width = frame.width()
            frame_height = frame.height()
            x_offset = (canvas_width - frame_width) // 2
            y_offset = (canvas_height - frame_height) // 2
            self.imageid = self.canvas.create_image(x_offset, y_offset, anchor='nw', image=frame)
            self.frames.append(frame)
            print(f"Size: {self.file_size} MB. Frames: {self.obj.framecount}")
            print(f"F:  {self.timer.stop()}\n")
            self.first = False # Flags that the first has been created
            for i in range(1, self.obj.framecount):
                self.image.seek(i)
                logger.debug(f"Load: {self.lazy_index+1}/{self.obj.framecount} ({self.obj.frametimes[self.lazy_index]})")
                frame = ImageTk.PhotoImage(self.image.resize(self.new_size), Image.Resampling.LANCZOS)
                self.frames.append(frame)
            self.lazy_loading = False # Lower the lazy_loading flag so animate can take over.
            return
        except Exception as e:
            if hasattr(self, 'frames'): # This wont let the error display if the window is being closed.
                logger.error(f"Error loading frames: {e}")
    def lazy_load(self):
        "Display new frames as soon as possible, when all loaded, switch to simple looping method"
        if not self.lazy_loading: # When all frames are loaded, we switch to just looping
            logger.debug("All frames loaded, stopping lazy_load")
            self.animate_image()
            return
        elif not self.frames or not len(self.frames) > self.lazy_index: #if the list is still empty. Wait.
            logger.debug("Buffering") #Ideally 0 buffering, update somethng so frames is initialzied quaranteed.
            self.canvas.after(self.obj.delay, self.lazy_load)
            return
        elif self.lazy_index != self.obj.framecount:
            #Checks if more frames than index is trying and less than max allowed.
            self.canvas.itemconfig(self.imageid, image=self.frames[self.lazy_index])
            if self.default_delay.get():
                logger.debug(f"Lazy: {self.lazy_index+1}/{self.obj.framecount} ({self.obj.delay}) ###")
                self.lazy_index = (self.lazy_index + 1) % self.obj.framecount
                self.canvas.after(self.obj.delay, self.lazy_load)
                return
            else:
                logger.debug(f"Lazy: {self.lazy_index+1}/{self.obj.framecount} ({self.obj.frametimes[self.lazy_index]}) ###")
                self.lazy_index = (self.lazy_index + 1) % self.obj.framecount
                self.canvas.after(self.obj.frametimes[self.lazy_index], self.lazy_load)
                return
        else:
            logger.error("Error in lazy load, take a look")
            self.canvas.after(self.obj.delay, self.lazy_load)
    def animate_image(self):
        "Simple gif looper"
        self.canvas.itemconfig(self.imageid, image=self.frames[self.lazy_index])
        
        if self.default_delay.get():
            logger.debug(f"{self.lazy_index+1}/{self.obj.framecount} ({self.obj.delay})")
            self.lazy_index = (self.lazy_index + 1) % len(self.frames)
            self.canvas.after(self.obj.delay, self.animate_image)

        else:
            logger.debug(f"{self.lazy_index+1}/{self.obj.framecount} ({self.obj.frametimes[self.lazy_index]})")
            self.lazy_index = (self.lazy_index + 1) % len(self.frames)
            self.canvas.after(self.obj.frametimes[self.lazy_index], self.animate_image)
    
    "Display"
    def __show_image(self):
        "Heavily modified to support gif"
        try:
            if self.obj.isanimated: #Let another function handle if animated
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
                self.canvas.configure(scrollregion=tuple(map(int, box_scroll)))  # set scroll region
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
                        if self.count < self.count1: # fixes lag on movign rescaled picture.
                                self.manual_wheel()
                                #logger.debug(f"scroll event {self.__curr_img}, {(max(0, self.__curr_img))} {self.count} {self.count1}")
                                self.count += 1
                        if self.first:
                            self.first = False
                            image = self.__pyramid[0]
                            if self.file_size < self.gui.quick_preview_size_threshold: # if small render high quality
                                print(f"Size (small): {self.file_size} MB. Frames: {self.obj.framecount}")
                                imagetk = ImageTk.PhotoImage(image.resize((int(x2 - x1), int(y2 - y1)), self.__filter))
                            else:
                                print(f"Size: {self.file_size} MB. Frames: {self.obj.framecount}")
                                imagetk = ImageTk.PhotoImage(image.resize((int(x2 - x1), int(y2 - y1)), self.__first_filter))
                            self.imageid = self.canvas.create_image(max(box_canvas[0], box_img_int[0]),
                                                       max(box_canvas[1], box_img_int[1]),
                                                    anchor='nw', image=imagetk)
                            
                            print(f"F:  {self.timer.stop()}")
                            self.canvas.lower(self.imageid)  # set image into background
                            self.canvas.imagetk = imagetk  # keep an extra reference to prevent garbage-collection
                            self.pyramid_ready.set() #tell threading that second picture is allowed to render.

                        elif self.replace_await and self.file_size > self.gui.quick_preview_size_threshold: # only render second time if needed.
                            self.replace_await = False
                            image = self.__pyramid[(max(0, self.__curr_img))]
                            imagetk = ImageTk.PhotoImage(image.resize((int(x2 - x1), int(y2 - y1)), self.__filter))
                            self.imageid = self.canvas.create_image(max(box_canvas[0], box_img_int[0]),
                                                       max(box_canvas[1], box_img_int[1]),
                                                    anchor='nw', image=imagetk)

                            print(f"B:  {self.timer.stop()}")
                            self.canvas.lower(self.imageid)  # set image into background
                            self.canvas.imagetk = imagetk

                        else:
                            image = self.__pyramid[(max(0, self.__curr_img))].crop(  # crop current img from pyramid
                                            (int(x1 / self.__scale), int(y1 / self.__scale),
                                             int(x2 / self.__scale), int(y2 / self.__scale)))
                            imagetk = ImageTk.PhotoImage(image.resize((int(x2 - x1), int(y2 - y1)), self.__filter)) #new resize for no reason?
                            self.imageid = self.canvas.create_image(max(box_canvas[0], box_img_int[0]),
                                                       max(box_canvas[1], box_img_int[1]),
                                                    anchor='nw', image=imagetk)
                            self.canvas.lower(self.imageid)  # set image into background
                            self.canvas.imagetk = imagetk
        except Exception as e:
            logger.info("Thread caught.")
            print(e)

    "Dont touch"
    def __move_from(self, event):
        "Remember previous coordinates for scrolling with the mouse"
        self.time_from_click = time() #NAVIGATOR
        self.og_posx = event.x
        self.og_posy = event.y
        self.canvas.focus_set()
        self.canvas.scan_mark(event.x, event.y)
    def __move_to(self, event):
        "Drag (move) canvas to the new position"
        self.canvas.scan_dragto(event.x, event.y, gain=1)
        self.__show_image()  # zoom tile and show it on the canvas
    
    def __wheel(self, event=None, direction=None):
        "Zoom with mouse wheel"
        print("activation")
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
        x = self.canvas_width
        y = self.canvas_height
        scale = 1.0

        k = self.imscale * self.__ratio # temporary coefficient
        self.__curr_img = min((-1) * int(log(k, self.__reduction)), len(self.__pyramid) - 1) #presumably changes the displayed image. Yes. We need pyramid to change the iterated frames.
        self.__scale = k * pow(self.__reduction, max(0, self.__curr_img)) #positioning dont change
        self.canvas.scale('all', x, y, scale, scale)  # rescale all objects

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
        self.__imframe.grid(**kw)  # place CanvasImage widget on the grid
        self.__imframe.grid(sticky='nswe')  # make frame container sticky
        self.__imframe.rowconfigure(0, weight=0)  # make frame expandable
        self.__imframe.columnconfigure(0, weight=0) #weight = to remove scrollbars
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
        if  not self.obj.isanimated:
            self.__scale=scale
            self.imscale=scale

            self.canvas.scale('all', self.canvas_width, 0, scale, scale)  # rescale all objects
            #self.canvas.update_idletasks()
    def center_image(self):
        """ Center the image on the canvas """
        if not self.obj.isanimated:
            canvas_width = self.canvas_width
            canvas_height = self.canvas_height

            # Calculate scaled image dimensions
            scaled_image_width = self.imwidth * self.imscale
            scaled_image_height = self.imheight * self.imscale

            # Calculate offsets to center the image
            if self.viewer_x_centering:
                x_offset = (canvas_width - scaled_image_width)-(canvas_width - scaled_image_width)/2
            else:
                x_offset = 0
            if self.viewer_y_centering:
                y_offset = (canvas_height - scaled_image_height)/2
            else:
                y_offset = 0

            # Update the position of the image container
            self.canvas.coords(self.container, (x_offset), (y_offset), (x_offset + scaled_image_width), (y_offset + scaled_image_height))
    def destroy(self):
        "ImageFrame destructor"
        self.frames.clear()
        self.original_frames.clear()
        del self.frames
        del self.original_frames
        self.image.close()
        del self.image

        # Video
        if hasattr(self, "player"):
            try:
                if self.player.is_playing():
                    self.player.stop()
                self.player.release()
            except Exception as e:
                print(e)
        try:
            for img in self.pyramid:
                img.close()
            self.pyramid.clear()
            del self.pyramid
        except Exception as e:
            logger.error(f"Error in closing pyramid : {e}")
        try:
            for img in self.__pyramid:
                img.close()
            self.__pyramid.clear()
            del self.__pyramid
        except Exception as e:
            logger.error(f"Error in closing __pyramid: {e}")

        self.canvas.destroy()
        self.__imframe.destroy()
"""
def rescale_gif_frames(self, scale): # Unused logic for now. Should be used for zooming
    if self.obj.isanimated:
        new_size = (int(self.new_size[0] * scale), int(self.new_size[1] * scale))
        for i in range(self.obj.framecount):
            self.frames[i] = ImageTk.PhotoImage(self.image.resize(new_size, Image.Resampling.LANCZOS))
        self.canvas.itemconfig(self.imageid, image=self.frames[self.lazy_index])  # Update the current frame on canvas   
"""         
