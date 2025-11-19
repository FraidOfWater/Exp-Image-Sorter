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
