import os
import fitz  # PyMuPDF
from tqdm import tqdm

# Directories
extract_dir = "epstein_files"
ocr_dir = "epstein_ocr_texts"
pdf_dir = "epstein_pdfs"
os.makedirs(pdf_dir, exist_ok=True)

# Function to create PDF for a subfolder
def create_pdf(subfolder):
    sub_root = os.path.join(extract_dir, subfolder)
    ocr_sub = os.path.join(ocr_dir, subfolder)
    pdf_path = os.path.join(pdf_dir, f"{subfolder}.pdf")
    doc = fitz.open()
    
    # Collect and sort files for progress
    image_files = []
    for root, _, files in os.walk(sub_root):
        for file in sorted(files):  # Sort for page order
            if file.lower().endswith((".jpg", ".jpeg")):
                image_files.append((root, file))
    
    for root, file in tqdm(image_files, desc=f"Building PDF for {subfolder}"):
        img_path = os.path.join(root, file)
        txt_path = os.path.join(ocr_sub, file + ".txt")
        if os.path.exists(txt_path):
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

# Process each subfolder with progress
subfolders = [f for f in os.listdir(extract_dir) if os.path.isdir(os.path.join(extract_dir, f))]
for subfolder in tqdm(subfolders, desc="Processing subfolders for PDFs"):
    create_pdf(subfolder)

print("PDF creation complete.")