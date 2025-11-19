from ultralytics import YOLO
import torch
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms
import os, json
from time import perf_counter
import concurrent.futures

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
        from torchvision.transforms import ToPILImage
        import os

        SAVE_TRANSFORMED = False
        if SAVE_TRANSFORMED:
            SAVE_DIR = "center_crop"
            os.makedirs(SAVE_DIR, exist_ok=True)
        to_pil = ToPILImage()
        
        from PIL import ImageDraw
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
        self.fm.gui.after_idle(self.fm.gui.sort_imagelist)
