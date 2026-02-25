import os
import shutil
import cv2

# ==========================================
# COLOR HISTOGRAM ALGORITHM
# ==========================================

def extract_hist_features(image_paths):
    """Pre-calculates HSV histograms for color similarity."""
    features = {}
    for path in image_paths:
        try:
            cv_img = cv2.imread(path)
            if cv_img is None: 
                continue
            
            # Convert to HSV to better represent how humans perceive color
            cv_img = cv2.cvtColor(cv_img, cv2.COLOR_BGR2HSV)
            
            # Calculate a 3D histogram (8 bins for H, S, and V each)
            hist = cv2.calcHist([cv_img], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
            cv2.normalize(hist, hist)
            features[path] = hist.flatten()
            
        except Exception as e:
            print(f"Skipping {os.path.basename(path)} due to error: {e}")
            
    return features

def sort_by_histogram(image_paths, features, output_dir):
    """Sorts images using a greedy chain based on color similarity."""
    valid_paths = [p for p in image_paths if p in features]
    if not valid_paths:
        return

    unvisited = set(valid_paths)
    current = valid_paths[0]
    ordered_chain = [current]
    unvisited.remove(current)

    while unvisited:
        best_match = None
        min_dist = float('inf')
        
        for candidate in unvisited:
            # Bhattacharyya distance: 0 is a perfect match, 1 is completely different
            dist = cv2.compareHist(features[current], features[candidate], cv2.HISTCMP_BHATTACHARYYA)
            if dist < min_dist:
                min_dist = dist
                best_match = candidate
        
        ordered_chain.append(best_match)
        unvisited.remove(best_match)
        current = best_match

    # Create directory and copy files
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for i, path in enumerate(ordered_chain):
        original_name = os.path.basename(path)
        new_name = f"{i:04d}_{original_name}" 
        shutil.copy(path, os.path.join(output_dir, new_name))
    
    print(f"✅ Sorted {len(ordered_chain)} images into: {output_dir}")

def main():
    # --- YOUR PATH ---
    input_dir = os.getcwd() 
    # ------------------
    
    valid_exts = {'.png', '.jpg', '.jpeg', '.bmp', '.webp'}
    if not os.path.exists(input_dir):
        print(f"Error: Directory '{input_dir}' not found.")
        return

    image_paths = [os.path.join(input_dir, f) for f in os.listdir(input_dir) 
                   if os.path.splitext(f)[1].lower() in valid_exts]
    
    if not image_paths:
        print("No valid images found.")
        return

    print(f"Found {len(image_paths)} images. Processing color histograms...")
    
    features = extract_hist_features(image_paths)
    output_folder = os.path.join(input_dir, "sorted_by_color_histogram")
    
    sort_by_histogram(image_paths, features, output_folder)

if __name__ == "__main__":
    main()