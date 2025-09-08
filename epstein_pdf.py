import os
import re
import json
import argparse
import fitz  # PyMuPDF
from tqdm import tqdm

# Parse arguments
parser = argparse.ArgumentParser(description="Create chunked PDFs from Epstein files")
parser.add_argument('--pages', type=int, default=500, help='Number of pages per PDF chunk (default: 500)')
args = parser.parse_args()

# Directories
extract_dir = "epstein_files"
ocr_dir = "epstein_ocr_texts"
pdf_dir = "epstein_pdfs"
sections_file = "sections.json"
os.makedirs(pdf_dir, exist_ok=True)

# Function to create PDF for a chunk
def create_pdf_chunk(image_files, start_page, end_page, chunk_name):
    # Ensure chunk_name is a string
    chunk_name = str(chunk_name)
    # Sanitize name for filename
    safe_name = re.sub(r'[^\w\-_]', '_', chunk_name)
    pdf_path = os.path.join(pdf_dir, f"{safe_name}_{start_page:03d}_{end_page:03d}.pdf")
    doc = fitz.open()

    for root, file in tqdm(image_files, desc=f"Building PDF chunk {chunk_name}"):
        img_path = os.path.join(root, file)
        # Find corresponding txt path
        txt_path = None
        for ocr_root, _, txt_files in os.walk(ocr_dir):
            for txt_file in txt_files:
                if txt_file == file + ".txt":
                    txt_path = os.path.join(ocr_root, txt_file)
                    break
            if txt_path:
                break

        if txt_path and os.path.exists(txt_path):
            with open(txt_path, "r", encoding="utf-8") as txt_file:
                text = txt_file.read()
        else:
            text = ""

        # Add page with image
        img = fitz.open(img_path)
        rect = img[0].rect
        page = doc.new_page(width=rect.width, height=rect.height)
        page.insert_image(rect, filename=img_path)

        # Add invisible text layer
        if text:
            page.insert_textbox(rect, text, fontsize=0,  # Invisible but searchable
                                fontname="helv", color=(0,0,0), overlay=True)
        img.close()

    doc.save(pdf_path)
    doc.close()
    print(f"Created {pdf_path}")

# Check for sections
if os.path.exists(sections_file):
    with open(sections_file, 'r') as f:
        sections = json.load(f)
    
    # Collect all pages in sections
    section_pages = set()
    for start_page, end_page in sections.values():
        section_pages.update(range(start_page, end_page + 1))
    
    # Process each section
    for section_name, (start_page, end_page) in tqdm(sections.items(), desc="Processing sections"):
        # Collect images in this range
        image_files = []
        for root, _, files in os.walk(extract_dir):
            for file in files:
                if file.lower().endswith((".jpg", ".jpeg", ".tif", ".tiff")):
                    match = re.search(r'DOJ-OGR-(\d+)\.(jpg|jpeg|tif|tiff)$', file)
                    if match:
                        page_num = int(match.group(1))
                        if start_page <= page_num <= end_page:
                            image_files.append((root, file))
        
        if image_files:
            create_pdf_chunk(image_files, start_page, end_page, section_name)
    
    # Process remaining pages not in sections
    remaining_images = []
    for root, _, files in os.walk(extract_dir):
        for file in files:
            if file.lower().endswith((".jpg", ".jpeg", ".tif", ".tiff")):
                match = re.search(r'DOJ-OGR-(\d+)\.(jpg|jpeg|tif|tiff)$', file)
                if match:
                    page_num = int(match.group(1))
                    if page_num not in section_pages:
                        remaining_images.append((page_num, root, file))
    
    if remaining_images:
        remaining_images.sort(key=lambda x: x[0])
        # Group remaining into chunks
        chunk_size = args.pages
        chunks = []
        for i in range(0, len(remaining_images), chunk_size):
            chunk = remaining_images[i:i + chunk_size]
            if chunk:
                start_page = chunk[0][0]
                end_page = chunk[-1][0]
                chunks.append((chunk, start_page, end_page))
        
        for idx, (chunk_files, start_page, end_page) in enumerate(tqdm(chunks, desc="Processing remaining chunks")):
            image_files = [(root, file) for _, root, file in chunk_files]
            create_pdf_chunk(image_files, start_page, end_page, f"unassigned_{idx + 1}")
    
    print("PDF creation complete using sections and remaining pages.")
else:
    # Fallback to chunked PDFs
    # Collect all image files across all subfolders
    all_image_files = []
    for root, _, files in os.walk(extract_dir):
        for file in files:
            if file.lower().endswith((".jpg", ".jpeg", ".tif", ".tiff")):
                # Extract page number
                match = re.search(r'DOJ-OGR-(\d+)\.(jpg|jpeg|tif|tiff)$', file)
                if match:
                    page_num = int(match.group(1))
                    all_image_files.append((page_num, root, file))

    # Sort by page number
    all_image_files.sort(key=lambda x: x[0])

    # Group into chunks
    chunk_size = args.pages
    chunks = []
    for i in range(0, len(all_image_files), chunk_size):
        chunk = all_image_files[i:i + chunk_size]
        if chunk:
            start_page = chunk[0][0]
            end_page = chunk[-1][0]
            chunks.append((chunk, start_page, end_page))

    # Process each chunk
    for idx, (chunk_files, start_page, end_page) in enumerate(tqdm(chunks, desc="Processing PDF chunks")):
        # Extract (root, file) from chunk
        image_files = [(root, file) for _, root, file in chunk_files]
        create_pdf_chunk(image_files, start_page, end_page, str(idx + 1))

    print("PDF creation complete.")