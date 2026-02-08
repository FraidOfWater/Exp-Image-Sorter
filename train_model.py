def main(data=None, epochs=10, name="latest_model", model="yolo11s-cls.pt", output_dir="models"):
    """Train YOLO model. Can be called directly or via command line."""
    import os, json, argparse, shutil, torch
    from ultralytics import YOLO
    
    # If called from command line, parse args
    if data is None:
        parser = argparse.ArgumentParser()
        parser.add_argument("--data", required=True)
        parser.add_argument("--epochs", type=int, default=10)
        parser.add_argument("--name", default="latest_model")
        parser.add_argument("--model", default="yolo11s-cls.pt")
        parser.add_argument("--output_dir", default="models")
        args = parser.parse_args()
        data = args.data
        epochs = args.epochs
        name = args.name
        model = args.model
        output_dir = args.output_dir
    
    run_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "classify")
    if os.path.exists(run_dir):
        shutil.rmtree(run_dir)
        
    os.makedirs(output_dir, exist_ok=True)
    model_path = os.path.join(output_dir, model)
    model_obj = YOLO(model_path)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model_obj.to(device)
    model_obj.model.to(device)

    print("Training on", device)
    print("Dataset:", data)
    from ultralytics.utils import SETTINGS
    SETTINGS['runs_dir'] = output_dir

    model_obj.train(
        data=data,
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
    save_path = os.path.join(output_dir, f"{name}.pt")
    model_obj.save(save_path)
    with open(os.path.join(output_dir, f"{name}.json"), "w") as f:
        json_dict = {}
        json_dict["id_2_name"] = model_obj.names
        json.dump(json_dict, f, indent=4)

    print("Training complete ✅")
    print("Saved model to:", save_path)

if __name__ == "__main__":
    import multiprocessing  as mp
    mp.freeze_support()
    main()
