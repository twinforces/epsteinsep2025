# Epstein Files Processor

This repository processes the 33,295-page Epstein records released by the House Oversight Committee on September 2, 2025 (via DOJ). The files are JPEG scans (with some MP4 videos), downloaded from the official Google Drive or Dropbox links.

The scripts download (optional), perform OCR on images (handling redactions), create searchable PDFs, and run object detection on videos (with blur/redaction skipping).

## Setup

1. **Dependencies**: Install via `pip install requests pillow pytesseract opencv-python fitz pymupdf torch torchvision torchaudio tqdm`.
   - Also install Tesseract OCR system-wide (e.g., `brew install tesseract` on macOS).
   - For videos: Ensure FFmpeg is installed if cv2 has issues (optional).

2. **Directory Structure**:
   - `epstein_files/`: Symlink or folder with raw downloads (JPEGs/MP4s in subfolders like IMAGES001).
   - Outputs: `epstein_ocr_texts/` (TXT files), `epstein_pdfs/` (searchable PDFs), `epstein_objects/` (video logs/annotated frames).

## Scripts

- **epstein.py**: Initial Dropbox download/extraction (deprecated; use JDownloader for large sets).
- **epstein_gdrive.py**: Google Drive download (API-based; requires credentials.json setup).
- **epstein_ocr.py**: Multithreaded OCR on JPEGs (with redaction pre-processing). Run: `python epstein_ocr.py`.
- **epstein_pdf.py**: Creates searchable PDFs from JPEGs + OCR text. Run after OCR: `python epstein_pdf.py`.
- **epstein_video_blur.py**: Object detection on MP4/MPG videos (skips blurry frames, uses Faster R-CNN). Run: `python epstein_video_blur.py`.
- **epstein_video.py**: Earlier video script without blur handling (deprecated).

## Usage

1. **Download Files Using JDownloader**:
   - Download and install JDownloader (free, open-source) from https://jdownloader.org/.
   - Open JDownloader and go to the "LinkGrabber" tab.
   - Paste the official folder URL: https://drive.google.com/drive/folders/1TrGxDGQLDLZu1vvvZDBAh-e7wN3y6Hoz (Google Drive) or https://www.dropbox.com/scl/fo/98fthv8otekjk28lcrnc5/AIn3egnE58MYe4Bn4fliVBw?rlkey=m7p8e9omml96fgxl13kr2nuyt&st=0xvm0p08&dl=0 (Dropbox).
   - JDownloader will crawl the folder recursively and list all files (it handles pagination for thousands of files).
   - Select all items, right-click, and choose "Start Downloads." Set the output directory to `epstein_files/` (it preserves subfolder structure).
   - Monitor progress; downloads may take hours for ~5-10GB. Resumes interruptions automatically.
   - Tip: If rate-limited, pause and resume later, or use a VPN.

2. Run `python epstein_ocr.py` for text extraction.
3. Run `python epstein_pdf.py` for PDFs.
4. Run `python epstein_video_blur.py` for video analysis.

Progress bars (tqdm) show status. Tune threads in scripts for your hardware (e.g., M4 Mac Pro).

## Notes

- Redactions: Handled via adaptive thresholding in OCR and blur detection in videos.
- GitHub: Upload outputs (TXT/PDF/logs) for searchability; raw files are large (~10GB). Use Git LFS for large files (setup: `brew install git-lfs`, `git lfs install`, then track patterns like `git lfs track "*.jpg"`).
- Source: Official release from https://oversight.house.gov/release/oversight-committee-releases-epstein-records-provided-by-the-department-of-justice/.

For issues, open a GitHub issue.