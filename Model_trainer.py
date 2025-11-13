# Model_trainer.py
import os, json, argparse, shutil, numpy as np, torch
from ultralytics import YOLO
from ultralytics.data.dataset import ClassificationDataset

class WeightedClassificationDataset(ClassificationDataset):
    def __init__(self, *args, mode='train', **kwargs):
        
        """
        Initialize the WeightedClassificationDataset.
        Args:
            class_weights (list or numpy array): A list or array of weights corresponding to each class.
        """
        
        super(WeightedClassificationDataset, self).__init__(*args, **kwargs)

        self.train_mode = "train" in self.prefix

        self.count_instances()
        class_weights = np.sum(self.counts) / self.counts

        # Aggregation function
        self.agg_func = np.mean

        self.class_weights = np.array(class_weights)
        self.weights = self.calculate_weights()
        self.probabilities = self.calculate_probabilities()

    def count_instances(self):
        
        """
        Count the number of instances per class
        Returns:
            dict: A dict containing the counts for each class.
        """
        
        self.counts = [0 for i in range(len(self.base.classes))]
        for _, class_idx, _, _ in self.samples:
            self.counts[class_idx] += 1
        self.counts = np.array(self.counts)
        self.counts = np.where(self.counts == 0, 1, self.counts)

    def calculate_weights(self):
        
        """
        Calculate the aggregated weight for each label based on class weights.
        Returns:
            list: A list of aggregated weights corresponding to each label.
        """
        
        weights = []
        for _, class_idx, _, _ in self.samples:
            weight = self.agg_func(self.class_weights[class_idx])
            weights.append(weight)
        return weights

    def calculate_probabilities(self):
        
        """
        Calculate and store the sampling probabilities based on the weights.
        Returns:
            list: A list of sampling probabilities corresponding to each label.
        """
        
        total_weight = sum(self.weights)
        probabilities = [w / total_weight for w in self.weights]
        return probabilities

    def __getitem__(self, index):
        
        """
        Return transformed label information based on the sampled index.
        """
        
        if self.train_mode:
            index = np.random.choice(len(self.samples), p=self.probabilities)

        return super(WeightedClassificationDataset, self).__getitem__(index)


# --- Monkey-patch Ultralytics to use our custom dataset ---
#import ultralytics.data.dataset
#ultralytics.data.dataset.ClassificationDataset = WeightedClassificationDataset

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--name", default="latest_model")
    parser.add_argument("--model", default="yolo11s-cls.pt")
    parser.add_argument("--output_dir", default="models")
    args = parser.parse_args()
    
    run_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "classify")
    if os.path.exists(run_dir):
        shutil.rmtree(run_dir)
        
    os.makedirs(args.output_dir, exist_ok=True)
    model_path = os.path.join(args.output_dir, args.model)
    model = YOLO(model_path)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.model.to(device)

    print("Training on", device)
    print("Dataset:", args.data)
    from ultralytics.utils import SETTINGS
    SETTINGS['runs_dir'] = args.output_dir

    model.train(
        data=args.data,
        epochs=args.epochs,
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
    save_path = os.path.join(args.output_dir, f"{args.name}.pt")
    model.save(save_path)
    with open(os.path.join(args.output_dir, f"{args.name}.json"), "w") as f:
        json_dict = {}
        json_dict["id_2_name"] = model.names
        json.dump(json_dict, f, indent=4)

    print("Training complete ✅")
    print("Saved model to:", save_path)

if __name__ == "__main__":
    main()
