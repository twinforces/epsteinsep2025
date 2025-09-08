import os
from PIL import Image
import sys

def convert_tiff_to_jpg(directory):
    """
    Convert all .tif and .tiff files in the given directory and subdirectories to .jpg
    """
    converted_count = 0
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(('.tif', '.tiff')):
                tiff_path = os.path.join(root, file)
                jpg_path = os.path.splitext(tiff_path)[0] + '.jpg'

                try:
                    # Open the TIFF image
                    with Image.open(tiff_path) as img:
                        # Convert to RGB if necessary (TIFF might be in other modes)
                        if img.mode != 'RGB':
                            img = img.convert('RGB')
                        # Save as JPG
                        img.save(jpg_path, 'JPEG', quality=95)
                        print(f"Converted: {tiff_path} -> {jpg_path}")
                        converted_count += 1

                        # Optionally remove the original TIFF file
                        # os.remove(tiff_path)
                        # print(f"Removed original: {tiff_path}")

                except Exception as e:
                    print(f"Error converting {tiff_path}: {e}")

    print(f"Conversion complete. {converted_count} files converted.")

if __name__ == "__main__":
    # Default directory
    target_dir = "epstein_files"

    # Allow command line argument for directory
    if len(sys.argv) > 1:
        target_dir = sys.argv[1]

    if not os.path.exists(target_dir):
        print(f"Directory {target_dir} does not exist.")
        sys.exit(1)

    convert_tiff_to_jpg(target_dir)