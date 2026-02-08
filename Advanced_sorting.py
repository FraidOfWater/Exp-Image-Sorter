import os, json, concurrent.futures
import torch
from time import perf_counter
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms
from torchvision.transforms import ToPILImage

from PIL import ImageDraw

import tkinter as tk
from tkinter import ttk

from ultralytics import YOLO

class FolderTreeApp(tk.Toplevel):
    "With this we can choose the categories easily."
    def __init__(self, root_path, categories=None, excludes=None, func=None):
        super().__init__()
        self.title("Select all categories and exclusions and close to train.")
        self.geometry("600x400")
        self.func = func
        self.tree = ttk.Treeview(self)
        self.tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        self.model_name = "latest_model"
        self.model_name_field = None
        self.tree.bind("<<TreeviewOpen>>", self.on_open)
        self.geometry("600x400")
        self.lift()
        self.attributes('-topmost', True)
        self.after_idle(self.attributes, '-topmost', False)
        self.focus_force()

        self.button_frame = tk.Frame(self)
        self.button_frame.pack(fill=tk.Y, side=tk.RIGHT)

        self.tree.heading("#0", text="Folder Structure", anchor='w')

        self.node_to_path = {}
        self.folder_states = {}

        self.tree.tag_configure('category', background='lightgreen', foreground='darkgreen', font=('TkDefaultFont', 9, 'bold'))
        self.tree.tag_configure('exclude', background='lightcoral', foreground='darkred', font=('TkDefaultFont', 9, 'italic'))
        self.tree.tag_configure('dummy', foreground='gray')

        # Store category and exclude paths as absolute paths for comparison
        self.categories = set(os.path.abspath(p) for p in categories or [])
        self.excludes = set(os.path.abspath(p) for p in excludes or [])


        self.root_path = os.path.abspath(root_path)
        self.root_node = self.insert_folder('', self.root_path)

        # Expand all preselected categories
        for category_path in self.categories:
            self.expand_to_path(category_path)
        for category_path in self.excludes:
            self.expand_to_path(category_path)

        self.tree.bind('<<TreeviewSelect>>', self.on_select)
        self.tree.bind("<Button-3>", self.on_right_click)
    
    def expand_to_path(self, path):
        target_path = os.path.abspath(path)

        # Find the node that matches the root_path (the top of the tree)
        for node_id, node_path in self.node_to_path.items():
            if node_path == os.path.commonpath([node_path, target_path]):
                root_node = node_id
                break
        else:
            print(f"[expand_to_path] Root node for {target_path} not found.")
            return

        current_node = root_node
        current_path = self.node_to_path[current_node]

        # Go level by level down from the root to the target path
        while True:
            if current_path == target_path:
                return  # Done

            try:
                # Get next segment
                rel_path = os.path.relpath(target_path, current_path)
                next_folder = rel_path.split(os.sep)[0]
                next_path = os.path.join(current_path, next_folder)

                # Expand the current node to load children
                self.tree.item(current_node, open=True)
                self.on_open_child(current_node)

                # Find child node matching the next folder
                found = False
                for child in self.tree.get_children(current_node):
                    if self.node_to_path.get(child) == os.path.abspath(next_path):
                        current_node = child
                        current_path = self.node_to_path[current_node]
                        found = True
                        break

                if not found:
                    current_node = self.insert_folder(current_node, next_path)
                    current_path = self.node_to_path[current_node]

            except Exception as e:
                print(f"[expand_to_path] Failed to expand: {e}")
                return

    def on_open_child(self, node):
        path = self.node_to_path[node]
        children = self.tree.get_children(node)
        if children and 'dummy' in self.tree.item(children[0], 'tags'):
            self.tree.delete(children[0])
            self.load_subfolders(node, path)

    def on_right_click(self, event):
        # Identify the item clicked on
        node_id = self.tree.identify_row(event.y)
        if not node_id or node_id not in self.node_to_path:
            return  # ignore if no valid folder node clicked

        folder_path = self.node_to_path[node_id]
        current = self.folder_states.get(folder_path)

        # Cycle states: None -> category -> exclude -> None
        if current is None:
            self.folder_states[folder_path] = "category"
            self.tree.item(node_id, tags=('category',))
        elif current == "category":
            self.folder_states[folder_path] = "exclude"
            self.tree.item(node_id, tags=('exclude',))
        else:  # current == "exclude"
            self.folder_states[folder_path] = None
            self.tree.item(node_id, tags=())
        self.update_node_text(node_id)

        # Keep the item selected
        self.tree.selection_set(node_id)
    def update_node_text(self, node_id):
        path = self.node_to_path.get(node_id, "")
        base_name = os.path.basename(path) or path  # handle root

        state = self.folder_states.get(path)
        suffix = ""
        if state == "category":
            suffix = " [Category]"
        elif state == "exclude":
            suffix = " [Exclude]"

        new_text = base_name + suffix
        self.tree.item(node_id, text=new_text)
    def insert_folder(self, parent, path):
        folder_name = os.path.basename(path)
        if not folder_name:
            folder_name = path  # root folder

        node = self.tree.insert(parent, 'end', text=folder_name, open=False)
        abs_path = os.path.abspath(path)
        self.node_to_path[node] = abs_path

        # Apply category or exclude if path is in provided lists
        if abs_path in self.categories:
            self.folder_states[abs_path] = "category"
            self.tree.item(node, tags=('category',))
        elif abs_path in self.excludes:
            self.folder_states[abs_path] = "exclude"
            self.tree.item(node, tags=('exclude',))

        # Add dummy child for expansion if subfolders exist
        if self.has_subfolders(path):
            self.tree.insert(node, 'end', text='Loading...', tags=('dummy',))

        # Update node label to show suffix
        self.update_node_text(node)

        return node

    def has_subfolders(self, path):
        try:
            return any(os.path.isdir(os.path.join(path, f)) for f in os.listdir(path))
        except Exception:
            return False

    def on_open(self, event):
        node = self.tree.focus()
        path = self.node_to_path[node]

        children = self.tree.get_children(node)
        if children and 'dummy' in self.tree.item(children[0], 'tags'):
            self.tree.delete(children[0])
            self.load_subfolders(node, path)

    def load_subfolders(self, parent_node, parent_path):
        try:
            for item in os.listdir(parent_path):
                full_path = os.path.join(parent_path, item)
                if os.path.isdir(full_path):
                    self.insert_folder(parent_node, full_path)
        except Exception as e:
            print(f"Error loading subfolders: {e}")

    def on_select(self, event):
        # Clear previous buttons
        if self.model_name_field:
            self.model_name = self.model_name_field.get()
        for widget in self.button_frame.winfo_children():
            widget.destroy()

        selected_nodes = self.tree.selection()
        selected_nodes = [n for n in self.tree.selection() if n in self.node_to_path]
        if selected_nodes:
            first_path = self.node_to_path.get(selected_nodes[0], "")
            tk.Label(self.button_frame, text=f"{len(selected_nodes)} selected folders\n\nFirst: {first_path}", wraplength=150).pack(pady=10)

            # Pass all selected nodes and paths to toggle functions
            tk.Button(self.button_frame, text="Category", command=lambda: self.toggle_category(selected_nodes)).pack(pady=5)
            tk.Button(self.button_frame, text="Exclude", command=lambda: self.toggle_exclude(selected_nodes)).pack(pady=5)
            # Reset button (clears all category/exclude markings)
            tk.Button(self.button_frame, text="Clear All", command=self.reset_all_states, bg="#f0f0f0").pack(pady=5)
            tk.Button(self.button_frame, text="Train", command=self.send_info, bg="#f0f0f0").pack(pady=20)
            self.model_name_field = tk.Entry(self.button_frame, bg="#f0f0f0")
            self.model_name_field.pack(pady=20)
            self.model_name_field.insert(0, self.model_name)
    
    def send_info(self):
        self.func(self.model_name_field.get())
        
    def reset_all_states(self):
        """Reset all folders back to default (no category or exclude)."""
        for path, state in list(self.folder_states.items()):
            if state is not None:
                self.folder_states[path] = None
        for node_id, path in self.node_to_path.items():
            self.tree.item(node_id, tags=())
            self.update_node_text(node_id)
        print("[Reset] All folder states cleared.")

    def toggle_category(self, node_ids):
        for node_id in node_ids:
            folder_path = self.node_to_path.get(node_id)
            if not folder_path:
                continue  # skip nodes without a path (e.g. dummy nodes)
            current = self.folder_states.get(folder_path)
            if current == "category":
                self.folder_states[folder_path] = None
                self.tree.item(node_id, tags=())
                print(f"[Unmarked Category] {folder_path}")
            else:
                self.folder_states[folder_path] = "category"
                self.tree.item(node_id, tags=('category',))
                print(f"[Category] {folder_path}")
            self.update_node_text(node_id)
            self.tree.selection_add(node_id)

    def toggle_exclude(self, node_ids):
        for node_id in node_ids:
            folder_path = self.node_to_path.get(node_id)
            if not folder_path:
                continue
            current = self.folder_states.get(folder_path)
            if current == "exclude":
                self.folder_states[folder_path] = None
                self.tree.item(node_id, tags=())
            else:
                self.folder_states[folder_path] = "exclude"
                self.tree.item(node_id, tags=('exclude',))
            self.update_node_text(node_id)
            self.tree.selection_add(node_id)

class ImagePathDataset(Dataset):
    def __init__(self, images, thumbs, transform=None):
        self.images = images
        self.thumbs = thumbs
        self.transform = transform

    def __len__(self):
        return len(self.images)

    def __getitem__(self, index):
        thumb = self.thumbs[index]
        path = self.images[index].path
        id = self.images[index].id
        
        if thumb == None or path == None or id == None: print("error")
        if self.transform: thumb = self.transform(thumb)
        
        return thumb, path, id

import os, shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from sortimages_multiview import Imagefile

class ThumbData(Imagefile):
    def __init__(self, name, path, ext, label):
        super().__init__(name, path, ext)
        self.label = label
        self.gen_id()

class Dataset_gen:
    def __init__(self, train_dir, labels, thumbsize, filemanager):
        self.filemanager = filemanager
        self.train_dir = train_dir
        self.labels = labels
        self.thumbsize = thumbsize

    def gen_thumbs(self):
        self.unsplit()
        
        path_hash_lookup = {}
        seen = set()

        files1 = []
        a = [(label, label_list) for label, label_list in self.labels.items()]
        a.sort(key=lambda x: len(x[1]))
        for label, label_list in a:
            os.makedirs(os.path.join(self.train_dir, label), exist_ok=True)
            for path in label_list:
                if os.path.dirname(path) not in seen:
                    seen.add(os.path.dirname(path))
                name = os.path.basename(path)
                parts = name.rsplit(".", 1)
                if len(parts) == 2:
                    n, ext = parts
                    ext = ext.lower()
                else:
                    n = parts[0]
                    ext = ""
                files1.append(ThumbData(name, path, ext, label))

        i = 0
        with ThreadPoolExecutor(max_workers=max(1,self.filemanager.threads-1), thread_name_prefix="thumbs") as executor:
            futures = []
            for obj in files1:
                cache_dir = os.path.join(self.train_dir, obj.label)
                futures.append(executor.submit(self.filemanager.thumbs.gen_thumb, obj, size=self.thumbsize, cache_dir=cache_dir, user="train", mode="as_is")) #name is for filename truncation, done along the thumbnail.
            for f in as_completed(futures):
                i += 1
                if i % 100 == 0:
                    print(i)
                self.filemanager.gui.train_status_var.set(str(i))

        ids = set(x.id for x in files1)
        for root, dirs, files in os.walk(self.train_dir):
            for file in files:
                file_id = os.path.splitext(file)[0]
                if file_id not in ids:
                    os.remove(os.path.join(root, file))
        
        for x in files1:
            path_hash_lookup[x.id] = {
                            "original_path": x.path,
                            "prediction_thumb_path": x.thumbnail,
                            "label": x.label
                        } 
        return path_hash_lookup
    
    def split(self, ratio):
        import random
        os.makedirs(os.path.join(self.train_dir, "train"), exist_ok=True)
        os.makedirs(os.path.join(self.train_dir, "val"), exist_ok=True)
        train = {}
        val = {}
        testing = {}
        dirs = [os.path.join(self.train_dir, item) for item in os.listdir(self.train_dir) if os.path.isdir(os.path.join(self.train_dir, item)) and len(os.listdir(os.path.join(self.train_dir, item))) != 0]
        for d in dirs:
            dir_name = os.path.basename(d)
            files = os.listdir(d)
            if len(files) >= 18:
                testing[dir_name] = []
                for x in files:
                    testing[dir_name].append(os.path.join(d, x))
            
        for label in testing.keys():
            train[label] = []
            val[label] = []
            files = testing[label]
            random.seed(42)
            random.shuffle(files)
            for file in files:
                if len(val[label]) < len(files)*(1-ratio):
                    val[label].append(file)
                else:
                    train[label].append(file)

        i = 0
        for label in train:
            i += len(train[label])
        j = 0
        for label in val:
            j += len(val[label])
        print(i, j)

        print("[usplit movensplit]")
        for label in train.keys():
            for path in train[label]:
                cat_folder = os.path.join(self.train_dir, "train", label)
                os.makedirs(cat_folder, exist_ok=True)
                shutil.move(path, os.path.join(cat_folder, os.path.basename(path)))
        for label in val.keys():
            for path in val[label]:
                cat_folder = os.path.join(self.train_dir, "val", label)
                os.makedirs(cat_folder, exist_ok=True)
                shutil.move(path, os.path.join(cat_folder, os.path.basename(path)))

        print("[rmtree]")
        dirs = [os.path.join(self.train_dir, dir) for dir in os.listdir(self.train_dir)]
        for dir in dirs:
            if os.path.isdir(dir):
                if len(os.listdir(dir)) == 0:
                    shutil.rmtree(dir)

    def unsplit(self):
        train_dir = os.path.join(self.train_dir, "train")
        val_dir = os.path.join(self.train_dir, "val")
        folders = []
        if os.path.isdir(train_dir):
            folders.extend([os.path.join(train_dir, x) for x in os.listdir(train_dir)])
        if os.path.isdir(val_dir):
            folders.extend([os.path.join(val_dir, x) for x in os.listdir(val_dir)])

        for folder in folders:
            files = os.listdir(folder)
            os.makedirs(os.path.join(self.train_dir, os.path.basename(folder)), exist_ok=True)
            for path in files:
                shutil.move(os.path.join(folder, path), os.path.join(self.train_dir, os.path.basename(folder), os.path.basename(path)))
            if len(os.listdir(folder)) == 0:
                shutil.rmtree(folder)
        if os.path.isdir(train_dir) and len(os.listdir(train_dir)) == 0:
            shutil.rmtree(train_dir)
        if os.path.isdir(val_dir) and len(os.listdir(val_dir)) == 0:
            shutil.rmtree(val_dir)

def load_thumbs_parallel(images, thumbsize, gen_thumb):
    """Parallel thumbnail generation with deterministic order."""
    thumbs = [None] * len(images)
    objs = [None] * len(images)

    with concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="gen_for_model") as executor:
        futures = {executor.submit(gen_thumb, obj, size=thumbsize, cache_dir=None, user="classify", mode="as_is"): i
                   for i, obj in enumerate(images)}
        for f in concurrent.futures.as_completed(futures):
            i = futures[f]
            result = f.result()
            if isinstance(result, tuple):
                img, obj = result
                if img is not None and obj is not None:
                    thumbs[i] = img
                    objs[i] = obj

    # Filter out failed loads while preserving order
    valid = [(img, obj) for img, obj in zip(thumbs, objs) if img is not None and obj is not None]
    if not valid:
        return [], []
    thumbs, objs = zip(*valid)
    return list(thumbs), list(objs)

class Model_inferer:
    def __init__(self, fm, model, thumbsize=224):
        self.path = os.path.dirname(os.path.abspath(__file__))
        self.model_path = model or os.path.join(self.path, "models", "latest_model.pt")
        self.fm = fm
        self.gen_thumb = fm.thumbs.gen_thumb
        
        self.thumbsize = thumbsize

    def infer(self, images, lookup):
        "Paths to the images, inferring size, path to model."
        start = perf_counter()
        MODEL_PATH = self.model_path
        DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        images = sorted(images, key=lambda x: x.name)

        model = YOLO(MODEL_PATH)
        model.to(DEVICE)
        model.eval()
        
        if self.fm.model_classes:
            pass
        else:
            base = f"{MODEL_PATH.rsplit('.', 1)[0]}" if model else "latest_model"
            json1 = base + ".json"
            json2 = base + "_paths.json"
            with open(json1, "r") as f:
                json_dict = json.load(f)
                class_dict = {int(k): v for k, v in json_dict["id_2_name"].items()}
                self.fm.model_classes = class_dict
            with open(json2, "r") as f:
                json_dict = json.load(f)
                path_dict = json_dict["names_2_path"]
                self.fm.names_2_path = path_dict

        transform = transforms.Compose([
            transforms.Resize(224),
            transforms.CenterCrop(224),
            transforms.ToTensor()
        ])
        """transform = transforms.Compose([
            transforms.Resize((224,224)),
            transforms.ToTensor()
        ])"""
        
        thumbs, objs = load_thumbs_parallel(images, self.thumbsize, self.gen_thumb)
        dataset = ImagePathDataset(images=images, thumbs=thumbs, transform=transform)
        loader = DataLoader(dataset, batch_size=32, shuffle=False)

        results_list = []

        SAVE_TRANSFORMED = False
        if SAVE_TRANSFORMED:
            SAVE_DIR = "center_crop"
            os.makedirs(SAVE_DIR, exist_ok=True)
        to_pil = ToPILImage()
        
        with torch.no_grad():
            for batch_i, (images, paths, ids) in enumerate(loader):
                images = images.to(DEVICE)
                results = model(images)

                for i, result in enumerate(results):
                    pred = result.probs.top1
                    conf = result.probs.top1conf.item()

                    if SAVE_TRANSFORMED:
                        name = self.fm.model_classes.get(pred, pred)
                        img = to_pil(images[i].cpu())
                        draw = ImageDraw.Draw(img)
                        draw.text((5, 5), f"{name} ({conf:.2f})", fill=(255, 255, 0))

                        folder = os.path.join(SAVE_DIR, str(name))
                        os.makedirs(folder, exist_ok=True)
                        img.save(os.path.join(folder, f"{ids[i]}.jpg"))

                    results_list.append({
                        "pred": pred,
                        "conf": conf,
                        "path": paths[i],
                        "id": ids[i]
                    })

        # Sort by confidence
        results_list.sort(key=lambda d: d["conf"], reverse=True)
        print("inferred in:", perf_counter()-start)

        for res in results_list:
            imagefile = lookup[res["id"]]
            imagefile.conf = res["conf"]
            imagefile.pred = self.fm.model_classes.get(res["pred"], res["pred"])
        self.fm.gui.display_order.set("Confidence")
        self.fm.reorder_as_nearest(images, optimization=(thumbs, objs))
        self.fm.gui.after_idle(self.fm.sort_imagelist)
