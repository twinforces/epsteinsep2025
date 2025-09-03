import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image
import pytesseract
from tqdm import tqdm
import cv2  # For pre-processing
import numpy as np

# Directories
extract_dir = "epstein_files"
ocr_dir = "epstein_ocr_texts"

# Create OCR directory
os.makedirs(ocr_dir, exist_ok=True)

# Function to pre-process image for better OCR on redacted scans
def preprocess_image(img_path):
    # Load with OpenCV
    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError("Could not load image")
    
    # Adaptive thresholding to handle varying lighting/redactions
    img = cv2.medianBlur(img, 3)  # Reduce noise
    img = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                cv2.THRESH_BINARY, 11, 2)  # Binarize, ignores black bars
    
    # Convert back to PIL for Tesseract
    return Image.fromarray(img)

# Function to process a single image
def process_image(file_info):
    root, file = file_info
    if file.lower().endswith((".jpg", ".jpeg", ".png")):
        img_path = os.path.join(root, file)
        try:
            # Pre-process
            img = preprocess_image(img_path)
            
            # OCR with config for docs
            text = pytesseract.image_to_string(img, config='--oem 3 --psm 3')
            
            # Save text
            relative_path = os.path.relpath(root, extract_dir)
            txt_filename = file + ".txt"
            txt_path = os.path.join(ocr_dir, relative_path, txt_filename)
            os.makedirs(os.path.dirname(txt_path), exist_ok=True)
            with open(txt_path, "w", encoding="utf-8") as txt_file:
                txt_file.write(text)
            return f"OCR completed for {file}"
        except Exception as e:
            return f"Error processing {file}: {e}"
    return None

# Collect all image files
image_files = []
for root, _, files in os.walk(extract_dir):
    for file in files:
        image_files.append((root, file))

print(f"Found {len(image_files)} potential images. Starting OCR...")
with ThreadPoolExecutor(max_workers=8) as executor:  # Tune for M4 Pro
    futures = [executor.submit(process_image, info) for info in image_files]
    for future in tqdm(as_completed(futures), total=len(image_files), desc="Processing images"):
        result = future.result()
        if result:
            print(result)

print(f"OCR complete. Texts in '{ocr_dir}'.")