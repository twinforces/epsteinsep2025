import os
import random
import re
import json
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
rotations_file = "rotations.json"

# Create OCR directory
os.makedirs(ocr_dir, exist_ok=True)

# Parse arguments
parser = argparse.ArgumentParser(description="OCR Epstein files")
parser.add_argument('--sample', type=int, default=100, help='Number of random images to sample for optimization (default: 100)')
parser.add_argument('--rotation-correction', action='store_true', default=True, help='Enable automatic rotation correction for rotated pages')
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

# Rotation correction functions
def load_rotations():
    if os.path.exists(rotations_file):
        with open(rotations_file, 'r') as f:
            return json.load(f)
    return {}

def save_rotations(rotations):
    with open(rotations_file, 'w') as f:
        json.dump(rotations, f, indent=2)

def is_poor_quality(text):
    if not text.strip():
        return True

    # Split into words/tokens
    tokens = re.findall(r'\b\w+\b', text)

    if len(tokens) == 0:
        return True

    # Count single letters vs multi-letter words
    single_letters = sum(1 for token in tokens if len(token) == 1)
    total_tokens = len(tokens)

    # If more than 30% are single letters, likely poor quality
    single_letter_ratio = single_letters / total_tokens

    # Also check for very short text
    word_count = len([t for t in tokens if len(t) > 1])

    return single_letter_ratio > 0.3 or word_count < 3

def rotate_image(image_path, rotation):
    img = Image.open(image_path)

    if rotation == "Left":
        rotated = img.rotate(90, expand=True)
    elif rotation == "Right":
        rotated = img.rotate(-90, expand=True)
    elif rotation == "Upside":
        rotated = img.rotate(180, expand=True)
    else:  # "Normal"
        rotated = img

    return rotated

def run_ocr_with_rotation(img_path, rotation, config):
    try:
        # Rotate image
        img = rotate_image(img_path, rotation)

        # Try raw image first
        text = pytesseract.image_to_string(img, config=config)

        if not text.strip():
            # If no text, try preprocessed
            processed_img = preprocess_image(img_path)
            # Apply rotation to preprocessed image too
            if rotation != "Normal":
                processed_img = rotate_image_for_cv2(processed_img, rotation)
            text = pytesseract.image_to_string(processed_img, config=config)

        return text.strip()
    except Exception as e:
        print(f"Error OCR'ing {img_path} with rotation {rotation}: {e}")
        return ""

def rotate_image_for_cv2(img, rotation):
    # Convert PIL to OpenCV format for preprocessing
    if isinstance(img, Image.Image):
        img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)

    if rotation == "Left":
        img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    elif rotation == "Right":
        img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    elif rotation == "Upside":
        img = cv2.rotate(img, cv2.ROTATE_180)

    return Image.fromarray(img)

# Function to process a single image
def process_image(file_info, config_or_psm, save_flag, adaptive=False, rotations=None):
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

            # Extract page number for rotation tracking
            page_num = None
            match = re.search(r'DOJ-OGR-(\d+)\.', file)
            if match:
                page_num = match.group(1)

            # Handle rotation correction if enabled
            if args.rotation_correction and rotations is not None and page_num:
                # Check if we already know the rotation
                # Note: Only non-normal rotations are stored in the file to keep it smaller
                # If page is not in rotations file, it means it should use "Normal" rotation
                if page_num in rotations:
                    best_rotation = rotations[page_num]
                    print(f"Page {page_num}: Using known rotation '{best_rotation}'")
                else:
                    # Page not in rotations file, so it should be Normal (most common case)
                    # But we still need to test it to make sure Normal works well
                    print(f"Page {page_num}: Testing rotations (not in rotations file)...")

                    # First try Normal rotation
                    normal_text = run_ocr_with_rotation(img_path, "Normal", config)
                    normal_quality_ok = not is_poor_quality(normal_text)
                    print(f"  Normal: {'OK' if normal_quality_ok else 'POOR'} ({len(normal_text)} chars)")

                    if normal_quality_ok:
                        # Normal is good enough, use it (don't save to rotations file)
                        best_rotation = "Normal"
                        text = normal_text
                        print(f"Page {page_num}: Selected rotation 'Normal' (good quality)")
                    else:
                        # Normal is poor, try other rotations
                        print(f"Page {page_num}: Normal quality poor, testing other rotations...")
                        rotation_options = ["Left", "Right", "Upside"]
                        results = {"Normal": normal_text}

                        for rotation in rotation_options:
                            rot_text = run_ocr_with_rotation(img_path, rotation, config)
                            results[rotation] = rot_text
                            quality_ok = not is_poor_quality(rot_text)
                            print(f"  {rotation}: {'OK' if quality_ok else 'POOR'} ({len(rot_text)} chars)")

                        # Find best rotation from all results
                        best_score = 0
                        best_rotation = "Normal"
                        text = normal_text

                        for rotation, rot_text in results.items():
                            if not is_poor_quality(rot_text):
                                # Score based on word count and inverse of single letter ratio
                                tokens = re.findall(r'\b\w+\b', rot_text)
                                if tokens:
                                    word_count = len([t for t in tokens if len(t) > 1])
                                    single_letters = len([t for t in tokens if len(t) == 1])
                                    score = word_count * 2 - single_letters
                                    if score > best_score:
                                        best_score = score
                                        best_rotation = rotation
                                        text = rot_text

                        print(f"Page {page_num}: Selected rotation '{best_rotation}' (best among tested)")

                        # Only save rotation info if it's NOT normal (to keep file smaller)
                        if best_rotation != "Normal":
                            rotations[page_num] = best_rotation
            else:
                # Standard OCR processing without rotation correction
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
        futures = [executor.submit(process_image, info, config, False, False, None) for info in image_files]
        total_score = sum(future.result() for future in as_completed(futures))
        print(f"PSM {psm}: total score = {total_score}")
        if total_score > best_score:
            best_score = total_score
            best_psm = psm

print(f"Best PSM: {best_psm}, score: {best_score}")

# Load rotations if rotation correction is enabled
rotations = {}
if args.rotation_correction:
    rotations = load_rotations()
    print(f"Loaded {len(rotations)} known rotations")

# Now process all images with best PSM, tweaked by contour analysis
image_files = full_image_files
processing_desc = f"Processing all {len(image_files)} images with PSM {best_psm}"
if args.rotation_correction:
    processing_desc += " (with rotation correction)"
else:
    processing_desc += " (tweaked by contour analysis)"

print(processing_desc)
with ThreadPoolExecutor(max_workers=8) as save_executor:
    futures = [save_executor.submit(process_image, info, best_psm, True, True, rotations) for info in image_files]
    for future in tqdm(as_completed(futures), total=len(image_files), desc="Processing all images"):
        pass

# Save rotations if rotation correction was enabled
if args.rotation_correction:
    save_rotations(rotations)
    print(f"Saved {len(rotations)} rotations to {rotations_file}")

print(f"OCR complete. Texts in '{ocr_dir}'.")