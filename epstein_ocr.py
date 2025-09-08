import os
import random
import re
import argparse
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

# Parse arguments
parser = argparse.ArgumentParser(description="OCR Epstein files")
parser.add_argument('--sample', type=int, default=100, help='Number of random images to sample for optimization (default: 100)')
args = parser.parse_args()

# Load English words
english_words = set()
if os.path.exists('english_words.txt'):
    with open('english_words.txt', 'r') as f:
        english_words = set(line.strip().lower() for line in f)

# Function to detect and correct skew
def deskew_image(image):
    coords = np.column_stack(np.where(image > 0))
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return rotated

# Function to pre-process image for better OCR on redacted scans
def preprocess_image(img_path):
    # Load with OpenCV
    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError("Could not load image")

    # Apply CLAHE for contrast enhancement
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    img = clahe.apply(img)

    # Deskew
    img = deskew_image(img)

    # Adaptive thresholding to handle varying lighting/redactions
    img = cv2.medianBlur(img, 3)  # Reduce noise
    img = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                cv2.THRESH_BINARY, 11, 2)  # Binarize, ignores black bars

    # Convert back to PIL for Tesseract
    return Image.fromarray(img)

# Function to choose PSM based on contour analysis
def choose_psm(img_path):
    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return 3  # default

    # Apply CLAHE
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    img = clahe.apply(img)

    # Median blur
    img = cv2.medianBlur(img, 3)

    # Adaptive threshold
    img = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)

    # Find contours
    contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return 12  # sparse

    # Filter small contours
    boxes = [cv2.boundingRect(c) for c in contours if cv2.contourArea(c) > 100]
    if not boxes:
        return 12

    # Calculate areas
    img_area = img.shape[0] * img.shape[1]
    total_box_area = sum(w * h for _, _, w, h in boxes)

    if total_box_area > 0.5 * img_area:
        # Dense text
        max_area = max(w * h for _, _, w, h in boxes)
        if max_area > 0.7 * total_box_area:
            return 6  # uniform block
        else:
            return 3  # auto
    else:
        return 12  # sparse

# Function to process a single image
def process_image(file_info, config_or_psm, save_flag, adaptive=False):
    root, file = file_info
    if file.lower().endswith((".jpg", ".jpeg", ".png", ".tif", ".tiff")):
        img_path = os.path.join(root, file)
        try:
            if adaptive:
                best_psm = config_or_psm
                contour_psm = choose_psm(img_path)
                psm = best_psm if contour_psm == best_psm else contour_psm
                config = f'--oem 3 --psm {psm}'
            else:
                config = config_or_psm
                psm = int(config.split()[-1])  # extract psm for logging

            # Try raw image first
            try:
                raw_img = Image.open(img_path)
                text = pytesseract.image_to_string(raw_img, config=config)
                if not text.strip():
                    # If no text, try preprocessed
                    img = preprocess_image(img_path)
                    text = pytesseract.image_to_string(img, config=config)
            except:
                img = preprocess_image(img_path)
                text = pytesseract.image_to_string(img, config=config)

            if save_flag:
                # Save text
                relative_path = os.path.relpath(root, extract_dir)
                txt_filename = file + ".txt"
                txt_path = os.path.join(ocr_dir, relative_path, txt_filename)
                os.makedirs(os.path.dirname(txt_path), exist_ok=True)
                with open(txt_path, "w", encoding="utf-8") as txt_file:
                    txt_file.write(text)
                #print(f"Saved OCR for {file} (PSM {psm})")
            # Compute score
            words = set(re.findall(r'\b\w+\b', text.lower()))
            score = len(words & english_words)
            #if save_flag:
            #    print(f"OCR for {file}: score={score}, text={text[:200]}...")
            return score
        except Exception as e:
            print(f"Error processing {file}: {e}")
            return 0
    return 0

# Collect all image files
image_files = []
for root, _, files in os.walk(extract_dir):
    for file in files:
        if file.lower().endswith((".jpg", ".jpeg", ".png", ".tif", ".tiff")):
            image_files.append((root, file))

full_image_files = image_files[:]

if args.sample:
    image_files = random.sample(full_image_files, min(args.sample, len(full_image_files)))

# Define PSM modes to test
psms = [3, 6, 8, 11, 12, 13]

best_score = 0
best_psm = 3

print(f"Optimizing PSM on {len(image_files)} sample images...")
with ThreadPoolExecutor(max_workers=8) as executor:
    for psm in psms:
        config = f'--oem 3 --psm {psm}'
        print(f"Testing PSM {psm}")
        futures = [executor.submit(process_image, info, config, False, False) for info in image_files]
        total_score = sum(future.result() for future in as_completed(futures))
        print(f"PSM {psm}: total score = {total_score}")
        if total_score > best_score:
            best_score = total_score
            best_psm = psm

print(f"Best PSM: {best_psm}, score: {best_score}")

# Now process all images with best PSM, tweaked by contour analysis
image_files = full_image_files
print(f"Processing all {len(image_files)} images with PSM {best_psm} (tweaked by contour analysis)...")
with ThreadPoolExecutor(max_workers=8) as save_executor:
    futures = [save_executor.submit(process_image, info, best_psm, True, True) for info in image_files]
    for future in tqdm(as_completed(futures), total=len(image_files), desc="Processing all images"):
        pass

print(f"OCR complete. Texts in '{ocr_dir}'.")