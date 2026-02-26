import os, json, shutil, torch
from ultralytics import YOLO

def start_training(training_dir, model_dir, epochs, name, model="yolo11s-cls.pt", output_dir="models"):
    run_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "classify")
    if os.path.exists(run_dir):
        shutil.rmtree(run_dir)
        
    os.makedirs(model_dir, exist_ok=True)
    model_path = os.path.join(model_dir, model)
    model = YOLO(model_path)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.model.to(device)

    print("Training on", device)
    print("Dataset:", training_dir)
    from ultralytics.utils import SETTINGS
    SETTINGS['runs_dir'] = model_dir

    model.train(
        data=training_dir,
        epochs=epochs,
        imgsz=224,
        batch=56,
        workers=8,  # ✅ multiprocessing OK here
        name="latest_run",
        fliplr=0.5,
        flipud=0.01,
        hsv_h=0.015,
        hsv_s=0.7,
        hsv_v=0.4,
        erasing=0.4,
        auto_augment="autoaugment"
    )

    # Save model and classes
    save_path = os.path.join(model_dir, f"{name}.pt")
    model.save(save_path)
    with open(os.path.join(model_dir, f"{name}.json"), "w") as f:
        json_dict = {}
        json_dict["id_2_name"] = model.names
        json.dump(json_dict, f, indent=4)

    print("Training complete ✅")
    print("Saved model to:", save_path)
