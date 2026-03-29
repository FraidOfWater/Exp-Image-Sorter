import os, tkinter as tk, threading, queue
from tkinter import simpledialog
from time import perf_counter
from typing import Literal

# the scrollbar flickers on resize, the divider flickers on resize...
class dummy:
    theme = {}
    def __init__(self, file, ids, tag, row, col, center_x, center_y, canvas, image_items, make_selection):
        self.file = file
        self.ids = ids
        self.img_id = ids["img"]
        self.tag = tag
        self.row = row
        self.col = col
        self.center_x = center_x
        self.center_y = center_y
        self.canvas = canvas
        self.image_items = image_items
        self.make_selection = make_selection

    def change_color(self, color=None):
        if color:
            self.file.color = color
        c = self.file.color if color else self.theme.get("grid_background_colour", None)
        txt_box_c = self.theme.get("grid_background_colour", None)
        # it needs to compare itself to the last item of image_items. if it is there, it should cahnge color.
        if self.canvas.master.current_selection_entry != None and self.canvas.master.current_selection_entry.file == self.file:
            self.make_selection(self)
        else: self.canvas.itemconfig(self.ids["rect"], outline=c, fill=c)
        self.canvas.itemconfig(self.ids["txt_rect"], outline=txt_box_c, fill=txt_box_c)

    def change_image(self, image):
        self.canvas.itemconfig(self.img_id, image=image)

class ImageGrid(tk.Frame):
    class PrefilledInputDialog(simpledialog.Dialog):
        def __init__(self, parent, title:str, message:str, default_text=""):
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

    class Animate:
        def __init__(self):
            self.gui = None
            self.running = set()
            self.synchronized = set()
            self.frametime = None
            self.sync_after_id = None

        def add_animation(self, obj, frametime):
            """Start per-object animation respecting frame delays."""
            if obj in self.running: return
            instances = [f for f in (obj.frame, obj.destframe) if f]
            if instances:
                for f in instances:
                    f.change_color("orange")

            obj.index = 0
            if frametime:
                start = False
                if not self.synchronized: 
                    start = True
                self.synchronized.add(obj)
                self.frametime = frametime
                if start:
                    self._step_in_sync()
            else:
                self._step(obj)
        
        def _step_in_sync(self):
            
            to_remove = set()
            self.gui.after(self.frametime, self._step_in_sync)
            for obj in self.synchronized:
                instances = [f for f in (obj.frame, obj.destframe) if f]
                if not instances or not obj.frames or obj.index > len(obj.frames):
                    to_remove.add(obj)
                else:
                    obj.index = (obj.index + 1) % len(obj.frames)
                    frame_img = obj.frames[obj.index][0]
                    for f in instances:
                        try:
                            f.canvas.itemconfig(f.img_id, image=frame_img)
                        except Exception as e:
                            print(e)
                            to_remove.add(obj)
                            continue
            self.synchronized -= to_remove
            if not self.synchronized: return

        def _step(self, obj):
            instances = [f for f in (obj.frame, obj.destframe) if f]
            if not instances or not obj.frames or obj.index > len(obj.frames):
                self.stop(obj.id)
                return
            obj.index = (obj.index + 1) % len(obj.frames)
            self.gui.after(obj.frames[obj.index][1] or 100, self._step, obj)
            frame_img = obj.frames[obj.index][0]
            for f in instances:
                try:
                    f.canvas.itemconfig(f.img_id, image=frame_img)
                except Exception as e:
                    print(e)
                    self.stop(obj.id)
                    return
            
            
        def stop(self, id):
            self.running.discard(id)
            self.synchronized.discard(id)

    class ThumbManager:
        from concurrent.futures import ThreadPoolExecutor
        from PIL import Image, ImageTk
        import numpy
        import pyvips
        import av
        class CachedTruncator:
            def __init__(self, thumbmanager):
                import tkinter.font as tkfont
                self.smallfont = tkfont.Font(family='Helvetica', size=10)
                self.thumbs = thumbmanager
                self.gui = thumbmanager.gui
                self.prefix_width_cache = {}
                self.char_width_cache = {}
                self.measure_calls = 0
                self.ellipsis = "...."
                self.padding = 0
                self.ellipsis_width = self.smallfont.measure(self.ellipsis)

            def truncate(self, filename):
                parts = filename.rsplit(".", 1)

                if len(parts) == 2:
                    base, ext = parts
                    ext_w = self.prefix_width_cache.get(ext, False)
                    if ext_w == False:
                        ext_w = self.smallfont.measure(ext)
                        self.prefix_width_cache[ext] = ext_w
                        self.measure_calls += 1
                else:
                    base = filename
                    ext = ""
                    ext_w = 0

                base_chars_w = []
                base_w = 0
                for char in base:
                    char_w = self.char_width_cache.get(char, False)
                    if char_w == False:
                        char_w = self.smallfont.measure(char)
                        self.char_width_cache[char] = char_w
                        self.measure_calls += 1

                    base_w += char_w
                    base_chars_w.append(base_w)

                if base_w + ext_w <= self.gui.thumbnailsize - self.padding:
                    return filename

                available = self.gui.thumbnailsize - self.padding - self.ellipsis_width - ext_w

                # Binary search using precomputed widths
                lo, hi = 0, len(base)
                while lo < hi:
                    if self.thumbs.stop_event.is_set(): return
                    mid = (lo + hi + 1) // 2
                    if base_chars_w[mid - 1] <= available:
                        lo = mid
                    else:
                        hi = mid - 1

                return f"{base[:lo]}{self.ellipsis}{ext}"
        class DaemonThreadPoolExecutor(ThreadPoolExecutor):
            """ThreadPoolExecutor that sets all worker threads as daemon threads."""
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._set_daemon_threads(kwargs["thread_name_prefix"])

            def _set_daemon_threads(self, name):
                """
                Replace all non-daemon threads in the executor with daemon threads.
                Called after pool creation. Compatible with Python 3.9–3.13.
                """
                old_threads = list(self._threads)
                self._threads.clear()
                for i in range(len(old_threads), self._max_workers):
                    t = threading.Thread(target=self._worker_entry, name=f"{name}_{i+1}", daemon=True)
                    t.start()
                    self._threads.add(t)

            def _worker_entry(self):
                """Our wrapper for the internal work queue processing loop."""
                while True:
                    try:
                        work_item = self._work_queue.get(block=True)
                        if work_item is None:
                            break
                        work_item.run()
                        del work_item
                    except Exception:
                        import traceback
                        traceback.print_exc()

        thumb_ext = {"png", "jpg", "jpeg", "bmp", "pcx", "tiff", "psd", "jfif", "gif", "webp", "avif"}
        anim_ext = {"gif", "webp", "webm", "mp4", "mkv", "m4v", "mov"}
        video_ext = {"webm", "mp4", "mkv", "m4v", "mov"}
        thumb_pool = None
        frame_pool = None
        def __init__(self, fileManager):
            self.fileManager = fileManager
            self.gui = fileManager.gui
            self.threads = fileManager.threads
            self.data_dir = fileManager.data_dir

            self.truncator = ImageGrid.ThumbManager.CachedTruncator(self)

            # Thread pool sizes
            self.thumb_workers = max(1, min(self.threads, 3))
            self.frame_workers = max(1, min(self.threads, 3))

            self.gif_semaphore = threading.Semaphore(1)
            self.av_semaphore = threading.Semaphore(2)

            self.thumb_after_id = None
            self.frame_after_id = None
            # Queues
            self.thumb_queue = queue.Queue()
            self.frame_queue = queue.Queue()
            # Worker threads
            self.thumb_worker = None
            self.frame_worker = None
            self.stop_event = threading.Event()
            self._cf_lock = threading.Lock()
            self._cf_cond = threading.Condition(self._cf_lock)
            self._left_lock = threading.Lock()
            self.left = 0
            self.left_f = 0

        def start_background_worker(self):
            if self.stop_event.is_set():
                self.stop_event.clear()

            # recreate executors if missing
            if not getattr(self, "thumb_pool", None):
                self.thumb_pool = ImageGrid.ThumbManager.DaemonThreadPoolExecutor(
                    thread_name_prefix="Thumb_loader", max_workers=self.thumb_workers)
            if not getattr(self, "frame_pool", None):
                self.frame_pool = ImageGrid.ThumbManager.DaemonThreadPoolExecutor(
                    thread_name_prefix="Frame_loader", max_workers=self.frame_workers)

            # start worker threads only if dead
            if not getattr(self, "_thumb_worker_running", False):
                self._thumb_worker_running = True
                self.thumb_after_id = self.gui.after(1, self._thumb_worker)

        def stop_background_worker(self):
            """Tell workers to stop, but never block the main thread."""
            self.stop_event.set()
            if self.thumb_after_id: self.gui.after_cancel(self.thumb_after_id)
            if self.frame_after_id: self.gui.after_cancel(self.frame_after_id)

            # cancel new jobs

            for pool in (self.thumb_pool, self.frame_pool):
                if pool:
                    pool.shutdown(wait=False, cancel_futures=True)

            self.thumb_pool = None
            self.frame_pool = None
            # clear queues so get() unblocks
            for q in (self.thumb_queue, self.frame_queue):
                    with q.mutex:
                        q.queue.clear()

            # schedule async cleanup on a short delay so we don't block GUI thread
            self._thumb_worker_running = False
            self._frame_worker_running = False

        def _thumb_worker(self):
            if self.stop_event.is_set():
                self._thumb_worker_running = False
                return

            while not self.thumb_queue.empty():
                try:
                    item = self.thumb_queue.get_nowait()
                    self.thumb_pool.submit(self._process_thumb, item)
                except queue.Empty: break
                except Exception as e:
                    print("Thumbnail pool submit error:", e)
                    break

            self._thumb_worker_running = False
            #self.thumb_after_id = self.gui.after(100, self._thumb_worker)

        def _process_thumb(self, obj):
            fm = self.fileManager
            gui = self.fileManager.gui
            try:
                if self.stop_event.is_set(): return
                self.gen_thumb(obj, size=gui.thumbnailsize, cache_dir=fm.data_dir)
            except Exception as e:
                print("Error encountered in Thumbmanager:", e)
            finally:
                self.thumb_queue.task_done()
            with self._left_lock:
                self.left = max(0, self.left - 1)
                thumbs_left = self.left
                frames_left = self.left_f
                gui.after(0, lambda imgs=thumbs_left, frames=frames_left: gui.frame_gen_queue_var.set(f"Ingen: {imgs}/{frames}"))

            if not self.frame_queue.empty() and self.thumb_queue.unfinished_tasks == 0:
                print(perf_counter()-self.start)
                self._frame_worker()

        def _frame_worker(self):
            if self.stop_event.is_set():
                self._frame_worker_running = False
                return
            while not self.frame_queue.empty():
                try:
                    item = self.frame_queue.get_nowait()
                    self.frame_pool.submit(self._process_frame, item)
                except queue.Empty: break
                except Exception as e:
                    print("Frame pool submit error:", e)
                    break
            self._frame_worker_running = False

        def _process_frame(self, obj):
            if self.stop_event.is_set():
                try: self.frame_queue.task_done()
                except Exception: pass
                return

            with self._cf_cond:
                # loop until slot available or stop event or shutdown
                while self.fileManager.concurrent_frames >= self.fileManager.max_concurrent_frames and not self.stop_event.is_set() \
                    and not self.stop_event.is_set():
                    self._cf_cond.wait(timeout=0.5)

                if self.stop_event.is_set():
                    try: self.frame_queue.task_done()
                    except Exception: pass
                    return

            color = "red"
            try:
                self.gen_frames(obj)
            except Exception as e:
                print("Frame generation error:", e)
            try:
                self.frame_queue.task_done()
                color = None # defaults to grid bg
            except Exception:
                print("Frame generation error (queue):", e)

            def change_color(instances, color):
                for f in instances:
                    f.change_color(color)
            with self._left_lock:
                print(perf_counter()-self.start)
                self.left_f = max(0, self.left_f - 1)
                thumbs_left = self.left
                frames_left = self.left_f
                self.gui.after(0, lambda imgs=thumbs_left, frames=frames_left: self.gui.frame_gen_queue_var.set(f"Ingen: {imgs}/{frames}"))
                instances = [f for f in (obj.frame, obj.destframe) if f]
                if instances:
                    self.gui.after(0, lambda instances=instances, color=color: change_color(instances, color))

        def flush_all(self):
            self.stop_event.set()

            if self.thumb_after_id:
                self.gui.after_cancel(self.thumb_after_id)
            if self.frame_after_id:
                self.gui.after_cancel(self.frame_after_id)
            self._thumb_worker_running = False
            self._frame_worker_running = False

            for q in (self.thumb_queue, self.frame_queue):
                with q.mutex:
                    q.queue.clear()

        def generate(self, imgfiles):
            self.start = perf_counter()
            self.stop_event.clear()
            for x in imgfiles:
                if not x.thumb:
                    self.thumb_queue.put(x)
            self.left = self.thumb_queue.qsize()

            for x in imgfiles:
                if x.ext in self.anim_ext and not x.frames:
                    self.left_f += 1
                    self.frame_queue.put(x)
                    instances = [f for f in (x.frame, x.destframe) if f]
                    for f in instances:
                        f.change_color("purple")
            self.left_f = self.frame_queue.qsize()
            self.start_background_worker()

        def gen_name(self, obj, overwrite=False):
            if self.gui.imagegrid.thumbs.stop_event.is_set(): return
            if overwrite: trunc = self.truncator.truncate(obj.name)
            else: trunc = obj.truncated_filename or self.truncator.truncate(obj.name)
            obj.truncated_filename = trunc
            if not (obj.frame or obj.destframe): return
            if obj.frame: self.gui.imagegrid.canvas.itemconfig(obj.frame.ids["label"], text=obj.truncated_filename)
            if obj.destframe: self.gui.folder_explorer.destw.canvas.itemconfig(obj.destframe.ids["label"], text=obj.truncated_filename)

        def gen_thumb(self, obj, size, cache_dir, user="default", mode="as_is"): # session just calls this for displayedlist  
            def load_thumb(thumb):
                "Loads thumb to canvas"
                def run(thumb):
                    if self.stop_event.is_set(): return
                    self.gen_name(obj)
                    instances = [f for f in (obj.frame, obj.destframe) if f]
                    if instances:
                        obj.thumb = thumb
                        for f in instances:
                            f.change_color() # defaults to grid bg
                            f.canvas.itemconfig(f.img_id, image=thumb)
                    #print(perf_counter()-self.start)

                gui.after_idle(run, thumb)

            interp = ImageGrid.ThumbManager.av.video.reformatter.Interpolation.AREA
            gui = self.fileManager.gui
            THUMB_FORMAT = self.fileManager.THUMB_FORMAT

            if self.stop_event.is_set(): return
            if user=="default" and not (obj.frame or obj.destframe): return
            elif user == "mobilenet" and obj.embed is not None and obj.color_embed is not None:
                return
            else:
                if not obj.id: obj.gen_id()

            if user == "default" and obj.thumb:
                load_thumb(obj.thumb)
                return

            pil_img = None
            failed = False

            if cache_dir:
                thumbnail_path = os.path.join(cache_dir, f"{obj.id}{THUMB_FORMAT}")
                
            if cache_dir and os.path.exists(thumbnail_path): # default and train will have cache_dir
                try:
                    if user != "default": return
                    thumb = None
                    with ImageGrid.ThumbManager.Image.open(thumbnail_path) as pil_img: # pil is faster here.
                        obj.thumbnail = thumbnail_path
                        thumb = ImageGrid.ThumbManager.ImageTk.PhotoImage(pil_img)
                    load_thumb(thumb)
                    return
                except Exception as e:
                    print(f"Pillows couldn't load thumbnail from cache: {obj.name} : Error: {e}.")
                    failed = True
            # if no found, we should generate it.
            vips_used = False

            av_formats = {"webm", "mp4", "mkv", "m4v", "mov", "gif"}
            if obj.ext in av_formats: #Webm, mp4
                pix_fmt = 'rgba' if any(f in obj.ext for f in ["webp", "gif"]) else 'rgb24'
                container = None
                try:
                    container = ImageGrid.ThumbManager.av.open(obj.path)
                    stream = container.streams.video[0]
                    w, h = stream.width, stream.height
                    max_size = 256
                    scale = max_size / max(w, h)
                    new_w = int(w * scale)
                    new_h = int(h * scale)

                    for frame in container.decode(stream):
                        resized_frame = frame.reformat(width=new_w, height=new_h, interpolation=interp, format=pix_fmt)
                        pil_img = resized_frame.to_image()
                        pil_img.save(thumbnail_path, format=THUMB_FORMAT[1:], quality=100)
                        obj.thumbnail = thumbnail_path
                        thumb = ImageGrid.ThumbManager.ImageTk.PhotoImage(pil_img)
                        load_thumb(thumb)                            
                        break
                    return
                except Exception as e:
                    print(f"PyAV thumbnail error for {obj.name}: {e}")
                    failed = True
                finally:
                    if container:
                        container.close()
            else:
                if mode == "as_is":
                    try:
                        vips_img = ImageGrid.ThumbManager.pyvips.Image.thumbnail(obj.path, size)
                        buffer = vips_img.write_to_memory()
                        pil_format = self.get_mode(vips_img)
                        pil_img =  ImageGrid.ThumbManager.Image.frombytes(pil_format, (vips_img.width, vips_img.height), buffer, "raw")
                        vips_used = True
                    except Exception as e: # Pillow fallback
                        print(f"Pyvips couldn't create thumbnail: {obj.name} : Error: {e}.")
                        failed = True
                if not vips_used or failed:
                    try:
                        with ImageGrid.ThumbManager.Image.open(obj.path) as pil_img:
                            pil_img.thumbnail((size, size))
                    except Exception as e:
                        print(f"Pillows couldn't create thumbnail, either: {obj.name} : Error: {e}")
                        failed = True
            if failed and user=="default":
                def run(obj):
                    if self.stop_event.is_set(): return
                    self.gen_name(obj)
                gui.after_idle(run, obj)
            if not pil_img:
                return

            # resize according to mode
            if mode == "as_is" and not vips_used:
                pil_img.thumbnail((size, size))
            elif mode == "letterbox":
                pil_img.thumbnail((size, size))
                w, h = pil_img.size
                new_im = ImageGrid.ThumbManager.Image.new("RGB", (size, size), (114, 114, 114))
                left = (size - w) // 2
                top = (size - h) // 2
                new_im.paste(pil_img, (left, top))
                pil_img = new_im

            format = "RGBA" if user == "default" else "RGB"
            if pil_img.mode != format: pil_img = pil_img.convert(format)

            # save it to cache if we can
            if cache_dir: # default and train
                pil_img.save(thumbnail_path, format=THUMB_FORMAT[1:], quality=100)
                thumb = None
            if user == "default": # for default, save path to imgfile and gen imgtk for it.
                obj.thumbnail = thumbnail_path
                thumb = ImageGrid.ThumbManager.ImageTk.PhotoImage(pil_img)
                load_thumb(thumb)

            if user == "classify":
                return pil_img, obj # for classify
            elif user == "mobilenet":
                return ImageGrid.ThumbManager.numpy.array(pil_img, dtype=ImageGrid.ThumbManager.numpy.uint8), obj # for mobilenet

        def gen_frames(self, obj):
            # some kind of limits here for both methods, like a time 15 seconds max or 20.
            gui = self.gui
            size, animate = gui.thumbnailsize, gui.imagegrid.animate
            if self.stop_event.is_set(): return
            def gui_enable_animation(o=obj, frametime=None):
                animate.add_animation(o, frametime)
            obj.frames.clear()
            if obj.ext in self.video_ext:
                def pick_sampling_rate(duration: float, native_fps: float,min_fps: float = 12.0, max_frames: int = 500, mode: Literal["stretch", "limit"] = "stretch"): # st
                    if duration == 0.0:  return native_fps if native_fps != 0.0 else min_fps
                    cap_rate = max_frames / duration # highest fps if we dont crop duration, but respect max_frames.
                    if mode == "stretch": # respect only max_frames.
                        if native_fps * duration <= max_frames: sampling_fps = native_fps # native fps is used if the frames would be under max_frames.
                        else: sampling_fps = cap_rate
                    elif mode == "limit": # respect min_fps.
                        if native_fps * duration <= max_frames: sampling_fps = native_fps
                        elif cap_rate >= min_fps: sampling_fps = cap_rate # prefers higher fps before min_fps
                        else: sampling_fps = min_fps # respects min_fps, but will exceed max_frames
                    sampling_fps = min(sampling_fps, native_fps) # never exceed the video's own frame-rate
                    frame_count = min(max_frames, round(duration * sampling_fps))
                    return sampling_fps, frame_count
                def get_fps_and_duration(path: str):
                    with ImageGrid.ThumbManager.av.open(path) as container:
                        stream = container.streams.video[0]
                        fps = float(stream.average_rate) if stream.average_rate else 24.0
                        duration = float(container.duration) / ImageGrid.ThumbManager.av.time_base if container.duration else 0.0
                        return fps, duration
                def extract_with_pyav(path: str, timestamps: list, frametime_ms: int):
                    interp = ImageGrid.ThumbManager.av.video.reformatter.Interpolation.AREA
                    with ImageGrid.ThumbManager.av.open(path) as container:
                        video_stream = container.streams.video[0]
                        w, h = video_stream.width, video_stream.height
                        max_size = 256
                        scale = max_size / max(w, h)
                        new_w = int(w * scale)
                        new_h = int(h * scale)
                        video_stream.thread_type = "AUTO"
                        time_base = float(video_stream.time_base)
                        target_pts_list = [int(t / time_base) for t in timestamps]
                        current_target_idx = 0
                        total_targets = len(target_pts_list)
                        last_pts = -1
                        while current_target_idx < total_targets:
                            if (self.stop_event.is_set() and not (obj.frame or obj.destframe)) or not (obj.frame or obj.destframe): 
                                break
                            target_pts = target_pts_list[current_target_idx]

                            if last_pts == -1 or (target_pts - last_pts) > (1.0 / time_base):
                                container.seek(target_pts, any_frame=False, backward=True, stream=video_stream)
                            
                            try:
                                for frame in container.decode(video_stream):
                                    if frame.pts >= target_pts:
                                        resized_frame = frame.reformat(width=new_w, height=new_h, interpolation=interp, format="rgb24")
                                        pil_img = resized_frame.to_image()
                                        obj.frames.append(((ImageGrid.ThumbManager.ImageTk.PhotoImage(pil_img)), frametime_ms if sampling_fps == min_fps else frametime_ms))

                                        if len(obj.frames) == 2:
                                            self.gui.after_idle(gui_enable_animation, obj, frametime_ms if sampling_fps == min_fps else None)
                                        
                                        last_pts = frame.pts
                                        current_target_idx += 1
                                        break # Move to the next timestamp
                            except ImageGrid.ThumbManager.av.EOFError:
                                current_target_idx = total_targets
                with self.av_semaphore:
                    try:
                        min_fps = 24
                        max_frames = 200
                        fps, duration = get_fps_and_duration(obj.path)
                        sampling_fps, n = pick_sampling_rate(duration=duration, native_fps=fps, min_fps=min_fps, max_frames=max_frames, mode="limit")
                        frametime_ms = int(round(1000.0 / sampling_fps))
                        timestamps = [(i / sampling_fps) for i in range(n)]
                        
                        extract_with_pyav(obj.path, timestamps, frametime_ms)
                    except Exception as e:
                        print("error in gen frames (av)", e)
            elif obj.ext in self.anim_ext:
                def gen_using_pil():
                    with ImageGrid.ThumbManager.Image.open(obj.path, "r") as img:
                        i = 0
                        while True:
                            if (self.stop_event.is_set() and not (obj.frame or obj.destframe)) or not (obj.frame or obj.destframe): break
                            try:
                                img.seek(i)
                                duration, frame = (img.info.get('duration', 100) or 100, img.copy().convert("RGBA"))
                                frame.thumbnail((size, size))
                                obj.frames.append((ImageGrid.ThumbManager.ImageTk.PhotoImage(frame), duration))
                                i += 1
                                if len(obj.frames) == 2: self.gui.after_idle(gui_enable_animation)
                            except EOFError: break
                            except Exception as e:
                                print("gen fraems error:", e)
                                break
                def gen_using_vips():
                    import pyvips
                    try:
                        # Load the full animation pipeline (tax paid here)
                        full_image = pyvips.Image.gifload(obj.path, n=-1)
                        # Apply the 'shrink-on-load' thumbnail logic
                        image = pyvips.Image.thumbnail_image(full_image, size, height=size, size='down')
                        
                        frame_h = image.get("page-height")
                        n_pages = image.get("n-pages")
                        
                        # Handle metadata (centiseconds to milliseconds)
                        try:
                            raw_delays = image.get("delay")
                            if not isinstance(raw_delays, list):
                                raw_delays = [raw_delays] * n_pages
                            # Standardizing: if < 20, assume centiseconds; else assume ms
                            delays = [d * 10 if d < 20 else d for d in raw_delays]
                        except:
                            delays = [100] * n_pages

                        for i in range(n_pages):
                            # Control checks matching your PIL logic
                            if (self.stop_event.is_set() and not (obj.frame or obj.destframe)) or not (obj.frame or obj.destframe):
                                break

                            # Extract current frame from the vertical strip
                            vips_frame = image.crop(0, i * frame_h, image.width, frame_h)
                            
                            # Ensure RGBA for Tkinter compatibility
                            if vips_frame.bands == 3:
                                vips_frame = vips_frame.bandjoin(255)
                            
                            # Execute the pipeline and convert to PhotoImage
                            mem = vips_frame.write_to_memory()
                            pil_img = ImageGrid.ThumbManager.Image.frombuffer(
                                'RGBA', (vips_frame.width, vips_frame.height), mem, 'raw', 'RGBA', 0, 1
                            )
                            
                            photo = ImageGrid.ThumbManager.ImageTk.PhotoImage(pil_img)
                            duration = delays[i]
                            
                            obj.frames.append((photo, duration))
                            
                            # Trigger the GUI enable on the 2nd frame, exactly like your PIL code
                            if len(obj.frames) == 2:
                                self.gui.after_idle(gui_enable_animation)

                    except Exception as e:
                        print("gen frames vips error:", e)
                        obj.clear_frames()
                        gen_using_pil()
                
                with self.gif_semaphore: #? works or no
                    gen_using_vips() # falls back to pil.
            if len(obj.frames) <= 1: gui.after_idle(obj.clear_frames)

        def get_mode(self, vips_img) -> Literal["RGB", "L", "I;16"]:
            "Return the mode needed to convert a PYVIPS.Image to a PIL.Image format via PIL.Image.frombytes()."
            "Most common formats are srgb, b-w, rgb16 and grey16."
            vips_format, pil_format = str(vips_img.interpretation).lower(), None
            match vips_format:
                case "srgb":
                    pil_format = "RGB" if vips_img.bands == 3 else "RGBA"
                case "b-w": pil_format = "L"
                case "rgb16": pil_format = "I;16"
                case "grey16": pil_format = "I;16"
            return pil_format

    animate = Animate()
    thumbs = None

    def __init__(self, master, gui, thumb_size=256, center=False,
                 bg="blue", destination=None,
                 theme={"square_default": "white",
                        "square_selected": "white",
                        "grid_background_colour": "white",
                        "checkbox_height": 25,
                        "square_padx": 4,
                        "square_pady": 4,
                        "square_outline": "white",
                        "square_border_size": 2,
                        "square_text": "white"
                        }):
        super().__init__(master)
        self.config(bg=bg)
        self.fileManager = gui.fileManager
        self.gui = gui
        self.animate.gui = gui
        self.destination = destination
        # thumb size MUST be set in PREFS. This only loads the generated thumbs from cache, never resizes or creates them.
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.assets_dir = os.path.join(self.script_dir, "assets")

        self.btn_thumbs = {}

        self.configure(borderwidth=0, border=0, bd=0, padx=0, pady=0)
        self.thumb_size = (thumb_size, thumb_size)
        self.center = center

        self.theme = theme
        dummy.theme = self.theme
        self.theme["square_border_size"] = 3
        w = self.theme["square_border_size"]
        theme["square_padx"] = 2
        theme["square_pady"] = 1

        self.sqr_padding = (theme["square_padx"]+w,theme["square_pady"]+w)
        self.grid_padding = (2,2)
        self.btn_size = (theme["checkbox_height"])
        self.btn_size = 18

        self.sqr_size = (self.thumb_size[0]+self.theme.get("square_border_size"), self.thumb_size[1]+self.theme.get("square_border_size")) # thumb_w + padx, etc

        self.cols = 0
        self.rows = 0

        self.bg = bg

        self.id_index = 0

        self.image_items = []
        self.item_to_entry = {}  # Mapping from canvas item ID to entry
        self.selected = []
        self.current_selection = None
        self.current_selection_entry = None
        from tkinter import ttk
        # --- NEW: BETTER SCROLLBAR STYLE ---
        self.style = ttk.Style(self)
        self.style.theme_use("default")
        self.style.configure("Custom.Vertical.TScrollbar",
                             background="black",
                             troughcolor=bg,
                             borderwidth=0,
                             arrowsize=0) # Removing arrows for cleaner look
        self.style.map("Custom.Vertical.TScrollbar",
                       background=[("pressed", "#616161"), ("active", "#4B4B4B")])

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(self, highlightthickness=0, bg=bg)
        # Apply the TTK Scrollbar with the custom style
        self.v_scroll = ttk.Scrollbar(self, orient="vertical",
                                      style="Custom.Vertical.TScrollbar",
                                      command=self.canvas.yview)

        self.canvas.configure(yscrollcommand=self.v_scroll.set)

        # Use Grid here to prevent the 'packing' lag during window resize
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.v_scroll.grid(row=0, column=1, sticky="ns")

        self.canvas.configure(bg=self.bg)  # Force recolor, otherwise managed automatically by tb.Window

        self.canvas.bind("<MouseWheel>",    self._on_mousewheel)
        self.canvas.bind("<Button-1>",      lambda e: (self._on_canvas_click(e), self.focus()))
        self.canvas.bind("<Button-3>",      self._on_canvas_click)
        self.winfo_toplevel().bind("<F2>",  self.rename)

        self.pack(fill="both", expand=True)

        #self.canvas.update()
        def helper():
            self.canvas.bind("<Configure>", self._on_resize)
        self.after(1, helper)
        def ram():
            import psutil
            process = psutil.Process(os.getpid())
            mem = process.memory_info().rss / 1024 / 1024  # RSS = Resident Set Size in bytes
            print(f"Memory used: {mem:.2f} MB", end="\r", flush=True)
            self.after(100, ram)
        #self.after(500, ram)

    def insert_first(self, new_images, pos=0):
        """
        Insert new image squares at the top of the grid.
        """
        if not new_images: return
        if type(new_images) == list: new_images = new_images[0]
        obj = new_images

        objs_w_no_thumbs = [obj] if not obj.thumb else []

        thumb_w, thumb_h = self.thumb_size
        sqr_w, sqr_h = self.sqr_size
        sqr_padx, sqr_pady = self.sqr_padding
        grid_padx, grid_pady = self.grid_padding
        btn_size = self.btn_size

        canvas_w = self.canvas.winfo_width()
        cols = max(1, canvas_w // sqr_w)
        self.cols = cols

        w = self.theme.get("square_border_size")
        text_c = self.theme.get("square_text_colour")

        btn_img = self.btn_thumbs.get("default", None)
        if btn_img == None:
            from PIL import Image, ImageTk
            import os
            bg_color = self.theme.get("grid_background_colour")
            def process_button_img(path, bg_hex):
                img = Image.open(path).convert("RGBA")
                background = Image.new("RGBA", img.size, bg_hex)
                combined = Image.alpha_composite(background, img)
                return ImageTk.PhotoImage(combined)

            self.btn_thumbs = {"default": process_button_img(os.path.join(self.assets_dir, "button.png"), bg_color),"pressed": process_button_img(os.path.join(self.assets_dir, "button_pressed.png"), bg_color)}
            btn_img = self.btn_thumbs["default"]

        btn_offset_x = w
        btn_offset_y = w * 2
        text_offset_x = btn_offset_x + btn_img.width() + 2
        text_offset_y = btn_offset_y + 1

        if obj.thumb == None:
            default_bg = "purple"
            grid_background_color = "purple"
        elif obj.dest != "":
            default_bg = obj.color
            grid_background_color = self.theme.get("grid_background_colour")
        else:
            default_bg = self.theme.get("square_default")
            grid_background_color = self.theme.get("grid_background_colour")

        row = pos // cols
        col = pos % cols

        current_col = (0 // cols) * (sqr_w + sqr_padx) + grid_padx
        current_row = (0 % cols) * (sqr_h + sqr_pady + btn_size) + grid_pady

        x_center = current_col + thumb_w // 2 + (w + 1) // 2
        y_center = current_row + thumb_h // 2 + (w + 1) // 2

        tag = f"img_{self.id_index}"
        self.id_index += 1

        rect = self.canvas.create_rectangle(
            current_col, current_row,
            current_col + sqr_w, current_row + sqr_h,
            width=w, outline=default_bg, fill=default_bg,
            tags=tag
        )

        img = self.canvas.create_image(
            x_center, y_center,
            image=obj.thumb, anchor="center",
            tags=tag
        )

        txt_rect = self.canvas.create_rectangle(
            current_col, current_row + sqr_w,
            current_col + sqr_w, current_row + sqr_h + btn_size,
            width=w, outline=grid_background_color, fill=grid_background_color,
            tags=tag
        )

        but = self.canvas.create_image(
            current_col + btn_offset_x,
            current_row + thumb_h + btn_offset_y,
            image=btn_img, anchor="nw",
            tags=tag
        )

        label = self.canvas.create_text(
            current_col + text_offset_x,
            current_row + thumb_h + text_offset_y,
            text=obj.truncated_filename,
            anchor="nw",
            fill=text_c,
            tags=tag
        )

        item_ids = {
            "rect": rect, "img": img, "label": label,
            "but": but, "txt_rect": txt_rect
        }
        entry = dummy(obj, item_ids, tag, row, col, x_center, y_center, self.canvas, self.image_items, self.make_selection)
        if not self.destination:
            obj.frame = entry
        else:
            obj.destframe = entry

        self.item_to_entry[rect] = entry
        self.item_to_entry[txt_rect] = entry

        self.image_items.insert(pos, entry)

        if objs_w_no_thumbs:
            self.thumbs.generate(objs_w_no_thumbs)

        self.reflow_from_index(pos)
        self.make_selection(self.image_items[pos])

    def add(self, new_images): # adds squares
        "Add images to the end of the self.image_items list."
        thumb_w, thumb_h = self.thumb_size
        sqr_w, sqr_h = self.sqr_size
        sqr_padx, sqr_pady = self.sqr_padding # distance between squares
        grid_padx, grid_pady = self.grid_padding # distance from the borders
        btn_size = self.btn_size
        canvas_w = self.canvas.winfo_width()
        self.cols = max(1, canvas_w // sqr_w)
        cols = self.cols
        center_offset = 0 if not self.center else max((canvas_w - cols * sqr_w) // 2, 0)
        temp = len(self.image_items)
        objs_w_no_thumbs = [obj for obj in new_images if not obj.thumb]

        w = self.theme.get("square_border_size")
        btn_img = self.btn_thumbs.get("default", None)
        if btn_img == None:
            from PIL import Image, ImageTk
            self.btn_thumbs = {"default": ImageTk.PhotoImage(Image.open(os.path.join(self.assets_dir, "button.png"))), "pressed": ImageTk.PhotoImage(Image.open(os.path.join(self.assets_dir, "button_pressed.png")))}
            btn_img = self.btn_thumbs["default"]
        btn_offset_x = w
        btn_offset_y = w*2 # btn_img.height()
        text_offset_x = btn_offset_x+btn_img.width()+2
        text_offset_y = btn_offset_y+1
        text_c = self.theme.get("square_text_colour")

        for i, file in enumerate(new_images, temp): # starting index is self.image_items length.
            if file.thumb == None:
                default_bg = "purple"
                grid_background_color = "purple"
            elif file.dest != "":
                default_bg = file.color
                grid_background_color = self.theme.get("grid_background_colour")
            else:
                default_bg = self.theme.get("square_default")
                grid_background_color = self.theme.get("grid_background_colour")

            row = i // cols
            col = i % cols

            current_col = center_offset + col * (sqr_w + sqr_padx) + grid_padx
            current_row = row * (sqr_h + sqr_pady + btn_size) + grid_pady
            # col * (sqr_w+<number>) to add padding between containers.
            # this is already done in sqr_size definition.
            x_center = current_col + thumb_w // 2 + (w + 1) // 2
            y_center = current_row + thumb_h // 2 + (w + 1) // 2

            tag = f"img_{self.id_index}"

            rect = self.canvas.create_rectangle(
                current_col,
                current_row,
                current_col + sqr_w,
                current_row + sqr_h,
                width=w,
                outline=default_bg,
                fill=default_bg,
                tags=tag)

            img = self.canvas.create_image(
                x_center,
                y_center,
                image=file.thumb,
                anchor="center",
                tags=tag)

            txt_rect = self.canvas.create_rectangle(
                current_col,
                current_row + sqr_h+w,
                current_col + sqr_w,
                current_row + sqr_h + btn_size,
                width=w,
                outline=grid_background_color,
                fill=grid_background_color,
                tags=tag)

            but_offset = current_row + thumb_h
            but = self.canvas.create_image(
                current_col + btn_offset_x,
                but_offset + btn_offset_y,
                image=btn_img,
                anchor="nw",
                tags=tag)

            label = self.canvas.create_text(
                current_col + text_offset_x,
                current_row + thumb_h + text_offset_y,
                text=file.truncated_filename,
                anchor="nw",
                fill=text_c,
                tags=tag)

            item_ids = {"rect":rect, "img":img, "label":label, "but":but, "txt_rect":txt_rect}
            entry = dummy(file, item_ids, tag, row, col, x_center, y_center, self.canvas, self.image_items, self.make_selection)
            if not self.destination:
                file.frame = entry
            else:
                file.destframe = entry

            if self.fileManager != None and self.gui.prediction.get():
                if file.conf:
                    if file.conf < 0.5: r, g, b = (255, int(510 * file.conf), 0)
                    else: r, g, b = (int(255 * (1 - file.conf)), 255, 0)
                    t_color = f"#{r:02x}{g:02x}{b:02x}"

                    path = self.fileManager.names_2_path[file.pred]
                    file.predicted_path = path
                    color = self.gui.folder_explorer.color_cache.get(path, None)

                    # --- Create overlay labels (confidence + prediction name) ---
                    confidence_text = f"{file.conf:.2f}"
                    prediction_text = file.pred

                    # Padding and styling
                    overlay_pad_x = 6
                    overlay_pad_y = 4
                    overlay_font = ("Arial", 12, "bold")
                    overlay_fg = "white"
                    overlay_bg = self.gui.d_theme["main_colour"]

                    # Create group for overlays
                    # Confidence (bottom-right corner)
                    text_id = self.canvas.create_text(
                        current_col + thumb_w - overlay_pad_x,
                        current_row + thumb_h - overlay_pad_y,
                        anchor="se",
                        text=confidence_text,
                        fill=t_color,
                        font=overlay_font,
                        tags=tag
                    )
                    bbox = self.canvas.bbox(text_id)
                    rect_id = self.canvas.create_rectangle(
                        bbox[0] - 4, bbox[1] - 2, bbox[2] + 4, bbox[3] + 2,
                        fill=overlay_bg, outline="", stipple="gray50", tags=tag
                    )
                    self.canvas.tag_lower(rect_id, text_id)

                    # Prediction name (top-left corner)
                    text_id2 = self.canvas.create_text(
                        current_col + overlay_pad_x+2,
                        current_row + overlay_pad_y+4,
                        anchor="nw",
                        text=prediction_text,
                        fill=color or "white",
                        font=overlay_font,
                        tags=tag
                    )
                    bbox2 = self.canvas.bbox(text_id2)
                    rect_id2 = self.canvas.create_rectangle(
                        bbox2[0] - 4, bbox2[1] - 2, bbox2[2] + 4, bbox2[3] + 2,
                        fill=overlay_bg, outline="", stipple="gray50", tags=tag
                    )
                    self.canvas.tag_lower(rect_id2, text_id2)

                #if color is None:
                #    self.fileManager.gui.folder_explorer.executor.submit(self.fileManager.gui.folder_explorer.get_set_color, path, square=text_id2)

            self.image_items.append(entry)
            self.item_to_entry[rect] = entry
            self.item_to_entry[txt_rect] = entry

            self.id_index += 1
        if objs_w_no_thumbs:
            self.thumbs.generate(objs_w_no_thumbs)
        self._update_scrollregion()

    def remove(self, sublist, unload=True): # removes squares
        "Remove these items from canvas, internal lists, remove obj reference,"
        "stop their animations, remove their thumbnail if not used elsewhere,"
        "and initiate a canvas reflow event."

        min_reflow_i = len(self.image_items)
        for obj in sublist:
            entry = obj.destframe if self.destination else obj.frame
            index = self.image_items.index(entry)
            min_reflow_i = min(min_reflow_i, index)
            obj.pos = index
            self.image_items.pop(index)
        if self.image_items:
            if self.current_selection is not None:
                i = -1 if self.current_selection >= len(self.image_items) else self.current_selection
                selected_entry = self.image_items[i]
                self.make_selection(selected_entry)
                if self.gui.show_next.get():
                    self.gui.displayimage(selected_entry.file)
        else:
            self.current_selection = None
            self.current_selection_entry = None

        for obj in sublist:
            entry = obj.destframe if self.destination else obj.frame

            self.canvas.delete(entry.tag)
            del self.item_to_entry[entry.ids["rect"]]
            del self.item_to_entry[entry.ids["txt_rect"]]

            if not self.destination:
                obj.frame = None
                if not obj.destframe and unload:
                    self.animate.stop(obj.id)
                    obj.thumb = None
                    obj.clear_frames()
            else:
                obj.destframe = None
                if not obj.frame and unload:
                    self.animate.stop(obj.id)
                    obj.thumb = None
                    obj.clear_frames()

        self.reflow_from_index(min_reflow_i)

    def move(self, sublist, dest, origin=False):
        fm = self.fileManager
        view = self.gui.current_view.get().lower()
        imagegrid = self.gui.imagegrid
        destw = self.gui.folder_explorer.destw

        if self.destination: # Dest
            is_here = os.path.dirname(dest) == self.destination
            if is_here:
                if dest == self.destination:
                    dest.remove(sublist)
                    dest.insert_first(sublist) # insert first?
                else:
                    dest.remove(sublist)
                if origin:
                    imagegrid.move(sublist, dest, origin=False) # always a "reassign". Must be in assigned by nature.
            elif not origin:
                if destw and dest == self.destination: # from moved, assigned or unassigned, always when origin = False
                    dest.insert_first(sublist)
                else:
                    pass
        else: # Main grid
            if view == "assigned": # this should work for things coming from dest no problem.
                imagegrid.remove(sublist)
                imagegrid.insert_first(sublist)
                if origin:
                    for x in sublist:
                        fm.assigned.remove(x)
                    fm.assigned = sublist + fm.assigned
                    dest.move(sublist, dest, origin=False) # this tells dest, move x to dest, dest looks up if it has x. (specifically, just looks at the path.)
            elif origin and view == "unassigned" : # we can ignore all calls from dest. but not to dest
                imagegrid.remove(sublist)
                fm.assigned = sublist + fm.assigned
                if destw and destw.destination == dest:
                    destw.move(sublist, dest, origin=False) # dest only needs to know if its dest is actually  the same
                else: pass # dest doesnt need to know
            elif origin and view == "moved":
                imagegrid.remove(sublist)
                for x in sublist:
                    fm.moved.remove(x)
                fm.assigned = sublist + fm.assigned
                if destw.destination == dest:
                    destw.move(sublist, dest, origin=False)
                else: pass # doesnt need to know

    def clear_canvas(self, unload=False, new_list=None):
        "Remove all items from canvas, but dont unload thumbnails or animations from memory."
        items = set(entry.file for entry in self.image_items)
        self.current_selection = None
        self.current_selection_entry = None
        self.selected.clear()
        self.item_to_entry.clear()
        self.image_items.clear()
        self.canvas.delete("all")

        if new_list: # list of images that will be unloaded, others are untouched
            dont_unload_set = items.copy()
            dont_unload_set = dont_unload_set.intersection(new_list)
            items.difference_update(dont_unload_set) # unload
            for obj in dont_unload_set:
                if not self.destination:
                    obj.frame = None
                else:
                    obj.destframe = None

        for obj in items:
            if not self.destination:
                obj.frame = None
                x = obj.destframe
            else:
                obj.destframe = None
                x = obj.frame
            if not x and unload:
                self.animate.stop(obj.id)
                obj.thumb = None
                obj.clear_frames()

    # Actions
    def _on_canvas_click(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        overlapping = self.canvas.find_overlapping(x, y, x, y)

        for item_id in overlapping:
            entry = self.item_to_entry.get(item_id) # overlapping might find img and rect, item_to_entry only contains id to rect, though.

            # delete
            if not entry: continue

            if event.num == 1:
                self.toggle_entry(entry)
            elif event.num == 3:
                if event.state in (1, 3, 5, 6, 7, 33, 35, 37, 39):
                    self.open_in_explorer(entry)
                self.make_selection(entry)
                self.gui.displayimage(entry.file)

    def canvas_clicked(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        overlapping = self.canvas.find_overlapping(x, y, x, y)

        return not bool(overlapping)

    def open_in_explorer(self, entry):
        import pyperclip
        import subprocess
        import os
        path = os.path.abspath(entry.file.path)
        pyperclip.copy(path)
        self.explorer_window = subprocess.Popen(r'explorer /select,"{}"'.format(path))

    def make_selection(self, entry):
        if self.current_selection_entry is not None:
            self.canvas.itemconfig(self.current_selection_entry.ids["rect"],
                                outline=self.theme.get("square_default"), fill=self.theme.get("square_default"))
        self.canvas.itemconfig(entry.ids["rect"], outline=self.theme.get("square_selected"), fill=self.theme.get("square_selected"))
        self.current_selection = self.image_items.index(entry)
        self.current_selection_entry = entry
        self.fileManager.gui.bindhandler.window_focused = "DEST" if self.destination else "GRID"

    def navigate(self, keysym, reverse=False):
        cols = self.cols
        rows = int((len(self.image_items) + cols - 1) / cols)
        first_visible_row = round(self.canvas.yview()[0] * rows)
        last_visible_row = round(self.canvas.yview()[1] * rows)

        if self.current_selection == None:
            index = 0
            new_selection = self.image_items[index]
            self.make_selection(new_selection)
            self.current_selection = index
            return
        else:
            index = self.current_selection
            scroll_dir = None

            if keysym == "Left":
                index -= 1
                if index < 0: return
                scroll_dir = "Up" if not reverse else "Down"
            elif keysym == "Right":
                index += 1
                if index >= len(self.image_items): return
                scroll_dir = "Up" if reverse else "Down"
            elif keysym == "Up":
                index -= cols
                if index < 0: return
                scroll_dir = "Up" if not reverse else "Down"
            else:
                index += cols
                if index >= len(self.image_items): return
                scroll_dir = "Up" if reverse else "Down"

        new_selection = self.image_items[index]
        self.make_selection(new_selection)
        self.current_selection = index

        new_row = (len(self.image_items)-self.current_selection-1) // cols if reverse else self.current_selection // cols

        if first_visible_row <= new_row <= last_visible_row:
            if scroll_dir == "Up":
                if new_row < first_visible_row: # Scroll up
                    target_scroll = (first_visible_row-1) / rows
                    self.canvas.yview_moveto(target_scroll)
            else:
                if last_visible_row <= new_row: # Scroll down
                    target_scroll = (first_visible_row+1) / rows
                    self.canvas.yview_moveto(target_scroll)
        else:
            target_scroll = (new_row) / rows
            self.canvas.yview_moveto(target_scroll)

    def _on_mousewheel(self, event, direction=None):
        sqr_w, sqr_h = self.sqr_size
        sqr_padx, sqr_pady = self.sqr_padding

        # 1. Direction Handling
        if direction is None:
            if event.num == 4 or event.delta > 0: direction = -1
            elif event.num == 5 or event.delta < 0: direction = 1
            else: return

        # 2. Geometry Setup
        # Ensure row_height matches your grid layout perfectly
        row_height = sqr_h + sqr_pady + self.btn_size

        scrollregion = self.canvas.cget("scrollregion").split()
        if not scrollregion or len(scrollregion) < 4: return
        scroll_h = int(scrollregion[3])
        view_h = self.canvas.winfo_height()

        # 3. Calculate Boundaries
        # The absolute maximum pixels we can scroll down
        max_scroll_pixels = max(0, scroll_h - view_h)

        # The last row index that can actually be at the TOP of the canvas
        # This prevents the "shifting" at the end of the list
        max_row_index = max_scroll_pixels // row_height

        # 4. Current Position Logic
        current_fraction = self.canvas.yview()[0]
        current_pixel_top = current_fraction * scroll_h

        # Identify which row we are currently snapped to
        current_row_index = round(current_pixel_top / row_height)

        # 5. Target and Clamp
        target_row_index = current_row_index + direction
        target_row_index = max(0, min(target_row_index, max_row_index))

        # Calculate the exact pixel for that row
        target_pixel = target_row_index * row_height

        # 6. Final Alignment Check
        # If the target_pixel is very close to the bottom limit,
        # we decide whether to snap to the limit or keep the row alignment.
        if target_pixel > max_scroll_pixels:
            target_pixel = max_scroll_pixels

        # Move the canvas
        new_top_fraction = target_pixel / scroll_h
        self.canvas.yview_moveto(new_top_fraction)

    def rename(self, event=None):
        gui = self.gui
        if not self.current_selection_entry: return
        obj = self.current_selection_entry.file
        title = "Rename Image"
        label = ""
        path = obj.path
        old_name = obj.name

        while True:
            dialog = ImageGrid.PrefilledInputDialog(gui, title, label, default_text=old_name)
            new_name = dialog.result
            if new_name:
                new_path = os.path.join(os.path.dirname(path), new_name)
                try:
                    os.rename(path, new_path)
                    obj.path = new_path
                    obj.name = os.path.basename(new_path)
                    self.thumbs.gen_name(obj, overwrite=True)
                    gui.displayimage(obj)
                    break
                except Exception as e:
                    print("Rename errors:", e)
                    label = f"{new_name} already exists in {os.path.basename(os.path.dirname(path))}"
                    old_name = new_name
            else:
                break

        pass # update square name (obj.gridsquare, obj.destsquare...), update obj.filename, truncated name...
    
    def get_items_adjacent_to_selection(self):
        current, items, cols = self.current_selection, self.image_items, self.cols
        n = 2 # Preload distance
        adjacent_indexes = []
        seen = set()
        for iteration in range(1, n+1):
            next = current+iteration
            under = current+iteration*cols
            previous = current-iteration
            above = current+iteration*cols
            for x in (next, under, previous, above):
                if x in seen or not 0<=x<len(items): continue
                seen.add(x)
                adjacent_indexes.append(x)

        return [items[i].file.path for i in adjacent_indexes]

    # Updates
    def reflow_from_index(self, start_idx=0):
        if not self.image_items: return
        thumb_w, thumb_h = self.thumb_size
        sqr_w, sqr_h = self.sqr_size
        sqr_padx, sqr_pady = self.sqr_padding
        grid_padx, grid_pady = self.grid_padding
        btn_size = self.btn_size

        cols = self.cols
        center_offset = 0 if not self.center else max((self.canvas.winfo_width() - cols * sqr_w) // 2, 0)

        w = self.theme.get("square_border_size")

        rows = int((len(self.image_items) + cols - 1) / cols)
        first_visible_row = round(self.canvas.yview()[0] * rows)
        last_visible_row = round(self.canvas.yview()[1] * rows)
        rows = last_visible_row-first_visible_row
        for i in range(start_idx, len(self.image_items)):
            item = self.image_items[i]

            new_row = i // cols
            new_col = i % cols

            current_col = center_offset + new_col * (sqr_w + sqr_padx) + grid_padx
            current_row = new_row * (sqr_h + sqr_pady + btn_size) + grid_pady

            x_center = current_col + thumb_w // 2 + (w + 1) // 2
            y_center = current_row + thumb_h // 2 + (w + 1) // 2

            dx = x_center - item.center_x
            dy = y_center - item.center_y

            item.row, item.col = new_row, new_col
            item.center_x, item.center_y = x_center, y_center
            self.canvas.move(item.tag, dx, dy)
        self._update_scrollregion()

    def _update_scrollregion(self):
        cols = self.cols
        sqr_w, sqr_h = self.sqr_size
        sqr_padx, sqr_pady = self.sqr_padding
        grid_padx, grid_pady = self.grid_padding

        total_rows = (len(self.image_items) + cols - 1) // cols # ceil
        total_width = cols * (sqr_w + sqr_padx) - sqr_padx + 2*grid_padx

        # Calculate the actual height of the content
        content_height = total_rows * (sqr_h + sqr_pady + self.btn_size) + grid_pady

        # Add the height of the canvas window as extra padding
        # This allows the last row to be scrolled to the very top
        view_h = self.canvas.winfo_height()
        total_height = content_height + view_h - (view_h//(sqr_h + sqr_pady + self.btn_size))*(sqr_h + sqr_pady + self.btn_size)-2 # 2 is a magic number to fix alignment issues.
        self.canvas.config(scrollregion=(0, 0, total_width, total_height))

    def _on_resize(self, event):
        sqr_w, sqr_h = self.sqr_size
        sqr_padx, sqr_pady = self.sqr_padding
        grid_padx, grid_pady = self.grid_padding
        displayed_cols = self.cols

        #canvas_w = self.canvas.winfo_width()
        #cols = max(1, canvas_w // sqr_w)

        #center_offset = 0 if not self.center else max((canvas_w - cols * sqr_w) // 2, 0)

        possible_cols = max(1, (event.width-2*grid_padx+sqr_padx-1) // (sqr_w+sqr_padx))
        #print(f"Displayed: {displayed_cols}/{possible_cols} Info: {(event.width-2*grid_padx+sqr_padx)-possible_cols*(sqr_w+sqr_padx)} {(sqr_w+grid_padx)}")

        if possible_cols == displayed_cols:
            return
        elif possible_cols > displayed_cols or possible_cols < displayed_cols: # increase
            self.cols = possible_cols
            old_pos = self.canvas.yview()[0]
            self.reflow_from_index()
            self.canvas.yview_moveto(old_pos)

    def change_theme(self, theme):
        self.theme = theme
        dummy.theme = theme
        self.configure(bg=theme["grid_background_colour"])
        self.canvas.configure(bg=theme["grid_background_colour"])

        for i in range(0, len(self.image_items)):
            item = self.image_items[i]

            w = theme.get("square_border_size")
            default_bg = theme.get("square_default")
            grid_background_colour = theme.get("grid_background_colour")
            text_c = theme.get("square_text_colour")
            self.bg = theme.get("grid_background_colour")

            self.canvas.configure(bg=self.bg)
            if item.file.dest == "":
                item.file.color = default_bg

            self.canvas.itemconfig(
                item.ids["rect"],
                width=w,
                outline=item.file.color,
                fill=item.file.color)

            self.canvas.itemconfig(
                item.ids["label"],
                fill=text_c)

            self.canvas.itemconfig(
                item.ids["txt_rect"],
                width=w,
                outline=grid_background_colour,
                fill=grid_background_colour)

    # Marking
    def unmark_entry(self, entry):
        self.canvas.itemconfig(entry.ids["but"], image=self.btn_thumbs["default"])
        try: self.selected.remove(entry)
        except ValueError: print("Something wrong with imagegrid selections, tried to remove from selected something that wasnt there.")

    def mark_entry(self, entry):
        self.canvas.itemconfig(entry.ids["but"], image=self.btn_thumbs["pressed"])
        if entry not in self.selected: self.selected.append(entry)

    def toggle_entry(self, entry):
        if entry in self.selected: self.unmark_entry(entry)
        else: self.mark_entry(entry)
    

class debug_imgfile:
    def __init__(self, imgtk, filename):
        self.thumb = imgtk
        self.truncated_filename = filename
        self.frame = None
        self.color = None
        self.dest = ""

if __name__ == "__main__":
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
    def load_images_from_folder(folder):
        return [
            os.path.join(folder, f) for f in os.listdir(folder)
            if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
        ][:1000]

    def load_images(paths, thumb_size):
        imgs = []
        from PIL import Image, ImageTk
        for path in paths:
            try:
                filename = os.path.basename(path)
                img = Image.open(path)
                img.thumbnail((thumb_size,thumb_size))
                img_tk = ImageTk.PhotoImage(img)
                imgs.append(debug_imgfile(img_tk, filename))
            except Exception as e:
                print(f"Error loading image {path}: {e}")
        return imgs

    root = tk.Tk()

    root.title("Image Viewer: Canvas")
    root.geometry("1200x1200")

    folder = r"C:\Users\4f736\Documents\Programs\Portable\Own programs\Exp-Img-Sorter\using resizing\data"
    thumb_size = 256
    center = False

    images = load_images(load_images_from_folder(folder), thumb_size)
    app = ImageGrid(root, thumb_size=thumb_size)
    app.add(images)
    root.mainloop()
