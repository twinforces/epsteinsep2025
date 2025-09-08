import os
import shutil

def copy_tiff_ocr_to_jpg(ocr_dir):
    """
    Copy .tif.txt OCR files to .jpg.txt files so they work with the converted JPG images
    """
    copied_count = 0
    for root, dirs, files in os.walk(ocr_dir):
        for file in files:
            if file.lower().endswith('.tif.txt'):
                # Get the base name without extension
                base_name = file[:-8]  # Remove '.tif.txt'
                tiff_txt_path = os.path.join(root, file)
                jpg_txt_path = os.path.join(root, base_name + '.jpg.txt')

                try:
                    # Copy the file
                    shutil.copy2(tiff_txt_path, jpg_txt_path)
                    print(f"Copied: {tiff_txt_path} -> {jpg_txt_path}")
                    copied_count += 1
                except Exception as e:
                    print(f"Error copying {tiff_txt_path}: {e}")

    print(f"OCR copy complete. {copied_count} files copied.")

if __name__ == "__main__":
    # Default OCR directory
    ocr_dir = "epstein_ocr_texts"

    copy_tiff_ocr_to_jpg(ocr_dir)