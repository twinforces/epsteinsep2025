# Epstein Files Processor

This repository processes the 33,295-page Epstein records released by the House Oversight Committee on September 2, 2025 (via DOJ). The files are JPEG scans (with some MP4 videos), downloaded from the official Google Drive or Dropbox links.

The scripts download (optional), perform OCR on images (handling redactions), create searchable PDFs, and run object detection on videos (with blur/redaction skipping).

## Setup

1. **Dependencies**: Install via `pip install requests pillow pytesseract opencv-python fitz pymupdf torch torchvision torchaudio tqdm flask`.
   - Also install Tesseract OCR system-wide (e.g., `brew install tesseract` on macOS).
   - For videos: Ensure FFmpeg is installed if cv2 has issues (optional).

2. **Directory Structure**:
   - `epstein_files/`: Symlink or folder with raw downloads (JPEGs/MP4s in subfolders like IMAGES001).
   - Outputs: `epstein_ocr_texts/` (TXT files), `epstein_pdfs/` (searchable PDFs), `epstein_objects/` (video logs/annotated frames).

## Scripts

- **epstein_ocr.py**: Multithreaded OCR on images with automatic rotation correction (enabled by default). Run: `python epstein_ocr.py`. Use `--no-rotation-correction` to disable.
- **epstein_pdf.py**: Creates searchable PDFs from images + OCR text. Can use sections from epstein_section_finder.py for better division. Run: `python epstein_pdf.py`.
- **epstein_section_finder.py**: Interactive tool to find document section breaks. Creates sections.json for better PDF division. Run: `python epstein_section_finder.py`.
- **epstein_indexer.py**: Creates searchable concordance pages with highlighted text. Run: `python epstein_indexer.py`.
- **epstein_tiff_converter.py**: Converts TIFF images to JPG format for web compatibility. Run: `python epstein_tiff_converter.py`.

## Quick Start Recipe

For the impatient, here's the complete workflow to get from downloaded files to searchable documents:

```bash
# 1. Download all files using JDownloader (see detailed instructions below)
# 2. Convert TIFF files to JPG for web compatibility (if you have TIFF files)
python epstein_tiff_converter.py

# 3. Extract text from all images (rotation correction enabled by default), also does object detection on the videos.
python epstein_ocr.py

# 4. Build searchable concordance pages
python epstein_indexer.py

# 5. Open search interface in your browser
open epstein_concordance_pages/index.html

# Optional: Create searchable PDFs with better section divisions
python epstein_section_finder.py  # Find document sections
python epstein_pdf.py            # Create PDFs using section boundaries
```

## Usage

1. **Download Files Using JDownloader**:
    - Download and install JDownloader (free, open-source) from https://jdownloader.org/.
    - Open JDownloader and go to the "LinkGrabber" tab.
    - Paste the official folder URL: https://drive.google.com/drive/folders/1TrGxDGQLDLZu1vvvZDBAh-e7wN3y6Hoz (Google Drive) or https://www.dropbox.com/scl/fo/98fthv8otekjk28lcrnc5/AIn3egnE58MYe4Bn4fliVBw?rlkey=m7p8e9omml96fgxl13kr2nuyt&st=0xvm0p08&dl=0 (Dropbox).
    - JDownloader will crawl the folder recursively and list all files (it handles pagination for thousands of files).
    - Select all items, right-click, and choose "Start Downloads." Set the output directory to `epstein_files/` (it preserves subfolder structure).
    - Monitor progress; downloads may take hours for ~5-10GB. Resumes interruptions automatically.
    - Tip: If rate-limited, pause and resume later, or use a VPN.

2. **Convert Image Formats** (optional):
    - If you have TIFF files, convert them to JPG: `python epstein_tiff_converter.py`
    - This creates JPG versions of all TIFF files for better web compatibility.

3. **Run OCR Processing**:
    - Run `python epstein_ocr.py` for text extraction from images.
    - **Rotation correction is enabled by default** - automatically detects and corrects upside down or sideways pages.
    - The system creates `rotations.json` to remember corrections for future runs.
    - To disable rotation correction: `python epstein_ocr.py --no-rotation-correction`

4. **View Concordance Pages**:
    - Run `python epstein_indexer.py` to create searchable concordance pages.
    - Open `epstein_concordance_pages/index.html` in your web browser to search and view documents with highlighted text.

5. **Create Searchable PDFs** (optional):
    - Run `python epstein_pdf.py` to create searchable PDFs from the extracted text and images.
    - PDFs are divided into 500-page chunks by default.

6. **Find Document Sections** (optional):
    - Run `python epstein_section_finder.py` to interactively find logical section breaks in the documents.
    - This creates `sections.json` that `epstein_pdf.py` can use to divide PDFs at more meaningful boundaries instead of fixed 500-page chunks.

7. **Video Analysis** (Optional):
    - Run `python epstein_video_blur.py` for video analysis with blur detection.

Progress bars (tqdm) show status. Tune threads in scripts for your hardware (e.g., M4 Mac Pro).

## Notes

- **Rotation Correction**: Some pages are scanned upside down or sideways. **Enabled by default** in epstein_ocr.py - automatically detects and corrects these. The system remembers corrections in `rotations.json` for future runs. Use `--no-rotation-correction` to disable.
- **Redactions**: Handled via adaptive thresholding in OCR and blur detection in videos.
- **TIFF Images**: Converted to JPG format for web compatibility using epstein_tiff_converter.py.
- **Section Finding**: Use epstein_section_finder.py to identify logical document breaks, then epstein_pdf.py will use these for better PDF division instead of fixed 500-page chunks.
- **Search Interface**: Open `epstein_concordance_pages/index.html` in your browser for the searchable concordance with highlighted text.
- **GitHub**: Upload outputs (TXT/PDF/logs) for searchability; raw files are large (~10GB). Use Git LFS for large files (setup: `brew install git-lfs`, `git lfs install`, then track patterns like `git lfs track "*.jpg"`).
- **Source**: Official release from https://oversight.house.gov/release/oversight-committee-releases-epstein-records-provided-by-the-department-of-justice/.

For issues, open a GitHub issue.