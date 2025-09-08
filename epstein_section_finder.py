import os
import re
import json
import logging
from flask import Flask, render_template_string, request, jsonify, send_from_directory
from copy import deepcopy

# Set up logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)

# Directories
extract_dir = "epstein_files"
ocr_dir = "epstein_ocr_texts"
sections_file = "sections.json"

# Get all page numbers
def get_all_pages():
    pages = []
    for root, _, files in os.walk(extract_dir):
        for file in files:
            if file.lower().endswith((".jpg", ".jpeg", ".tif", ".tiff")):
                match = re.search(r'DOJ-OGR-(\d+)\.(jpg|jpeg|tif|tiff)$', file)
                if match:
                    pages.append(int(match.group(1)))
    return sorted(pages)

all_pages = get_all_pages()
min_page = min(all_pages)
max_page = max(all_pages)

# Load existing sections
def load_sections():
    if os.path.exists(sections_file):
        with open(sections_file, 'r') as f:
            return json.load(f)
    return {}

def save_sections(sections):
    with open(sections_file, 'w') as f:
        json.dump(sections, f, indent=2)

sections = load_sections()

# Template
template = """
<!DOCTYPE html>
<html>
<head>
    <title>Epstein Section Finder</title>
    <style>
        .container { display: flex; flex-direction: row; }
        .nav-controls { display: flex; justify-content: center; align-items: center; margin-bottom: 10px; }
        .nav-arrow { cursor: pointer; font-size: 1.2em; margin: 0 10px; }
        .nav-arrow:disabled { color: grey; cursor: not-allowed; }
        #pageLabel { font-weight: bold; margin: 0 20px; }
        .image { flex: 1; text-align: center; }
        .text { flex: 1; font-family: monospace; white-space: pre-wrap; overflow: auto; height: 800px; padding-left: 10px; }
        img { width: 8.5in; height: auto; }
        .highlight { background-color: yellow; }
    </style>
</head>
<body>
    <h1>Epstein Section Finder</h1>
    <h2>Existing Sections</h2>
    <ul>
    {% for name, pages in sections.items() %}
        <li>{{ name }}: {{ pages[0] }} - {{ pages[1] }}</li>
    {% endfor %}
    </ul>

    <div id="sectionInfo" style="display: none;">
        <h2>Section Found</h2>
        <p id="sectionRange"></p>
        <label>Name: <input type="text" id="sectionName"></label>
        <button onclick="saveSection()">Save Section</button>
        <pre id="jsonOutput"></pre>
    </div>
    <div>
        <label>Go to Page: <input type="number" id="startPage" value="{{ start_page }}" min="{{ min_page }}" max="{{ max_page }}"></label>
        <button onclick="loadPageFromInput()">Load Page</button>
        <label>Jump: <input type="number" id="jumpPages" value="10" min="-1000" max="1000"></label>
        <button onclick="jumpPages()">Jump</button>
    </div>
    <div>
        <button onclick="binarySearchStart()">Find Section Start</button>
        <span id="currentStart">Start: Not set</span>
        <button onclick="binarySearchEnd()">Find Section End</button>
        <span id="currentEnd">End: Not set</span>
    </div>
    <div id="pageDisplay">
        <div class="nav-controls">
            <button id="prevPageBtn" class="nav-arrow" onclick="prevPage()" disabled>&larr;</button>
            <button onclick="setAsStart()">Set as Start</button>
            <span id="pageLabel">Page {{ start_page }}</span>
            <button onclick="setAsEnd()">Set as End</button>
            <button id="nextPageBtn" class="nav-arrow" onclick="nextPage()" disabled>&rarr;</button>
        </div>
        <div class="container">
            <div class="image">
                <img id="imageFrame" src="" alt="Page image">
            </div>
            <div class="text" id="pageText"></div>
        </div>
    </div>
    <div id="searchUI" style="display: none;">
        <h3 id="searchQuestion">Is this page in the section?</h3>
        <button onclick="searchYes()">Yes</button>
        <button onclick="searchNo()">No</button>
        <button onclick="restart()">Restart</button>
        <div class="container">
            <div class="nav-controls">
                <button id="searchPrevBtn" class="nav-arrow" onclick="searchPrev()" disabled>&larr;</button>
                <button onclick="setAsStart()">Set as Start</button>
                <span id="searchPageLabel">Page</span>
                <button onclick="setAsEnd()">Set as End</button>
                <button id="searchNextBtn" class="nav-arrow" onclick="searchNext()" disabled>&rarr;</button>
            </div>
            <div class="image">
                <img id="searchImageFrame" src="" alt="Search page image">
            </div>
            <div class="text" id="searchPageText"></div>
        </div>
    </div>
    <div id="finalChoice" style="display: none;">
        <h3>Choose the exact page:</h3>
        <div id="choiceImages"></div>
    </div>
    <script>
        let currentPage = {{ start_page }};
        let sectionStart = null;
        let sectionEnd = null;
        let low, high, currentCandidate, searchType;

        function loadPage(page = currentPage) {
            // Validate page number
            if (page < {{ min_page }} || page > {{ max_page }}) {
                alert(`Page number must be between {{ min_page }} and {{ max_page }}`);
                return;
            }
            fetch(`/page/${page}`)
            .then(response => response.json())
            .then(data => {
                document.getElementById('imageFrame').src = data.image;
                document.getElementById('pageText').innerHTML = data.text;
                document.getElementById('pageLabel').innerText = `Page ${page}`;
                currentPage = page;
                updateNavigation();
            })
            .catch(error => {
                console.error('Error loading page:', error);
                alert('Error loading page. Please check the page number.');
            });
        }

        function loadPageFromInput() {
            const pageInput = document.getElementById('startPage');
            const pageNum = parseInt(pageInput.value);
            if (isNaN(pageNum)) {
                alert('Please enter a valid page number');
                return;
            }
            loadPage(pageNum);
        }

        function jumpPages() {
            const jumpInput = document.getElementById('jumpPages');
            const jumpAmount = parseInt(jumpInput.value);
            if (isNaN(jumpAmount)) {
                alert('Please enter a valid jump amount');
                return;
            }
            const newPage = currentPage + jumpAmount;
            loadPage(newPage);
        }

        function prevPage() {
            loadPage(currentPage - 1);
        }

        function nextPage() {
            loadPage(currentPage + 1);
        }

        function updateNavigation() {
            document.getElementById('prevPageBtn').disabled = currentPage <= {{ min_page }};
            document.getElementById('nextPageBtn').disabled = currentPage >= {{ max_page }};
        }

        function setAsStart() {
            let pageToSet = document.getElementById('searchUI').style.display === 'block' ? currentCandidate : currentPage;
            sectionStart = pageToSet;
            document.getElementById('currentStart').innerText = `Start: ${sectionStart}`;
            updateSectionInfo();
        }

        function setAsEnd() {
            let pageToSet = document.getElementById('searchUI').style.display === 'block' ? currentCandidate : currentPage;
            sectionEnd = pageToSet;
            document.getElementById('currentEnd').innerText = `End: ${sectionEnd}`;
            updateSectionInfo();
        }

        function updateSectionInfo() {
            if (sectionStart !== null && sectionEnd !== null) {
                document.getElementById('sectionRange').innerText = `Pages ${sectionStart} to ${sectionEnd}`;
                document.getElementById('sectionInfo').style.display = 'block';
            }
        }

        function binarySearchStart() {
            document.getElementById('pageDisplay').style.display = 'none';
            document.getElementById('searchUI').style.display = 'block';
            low = {{ min_page }};
            high = currentPage;
            searchType = 'start';
            doBinaryStep();
        }

        function binarySearchEnd() {
            document.getElementById('pageDisplay').style.display = 'none';
            document.getElementById('searchUI').style.display = 'block';
            low = currentPage;
            high = {{ max_page }};
            searchType = 'end';
            doBinaryStep();
        }

        function doBinaryStep() {
            if (high - low <= 3) {
                showFinalChoice();
                return;
            }
            let mid = Math.floor((low + high) / 2);
            if (searchType === 'end') {
                mid = Math.floor((low + high + 1) / 2);
            }
            currentCandidate = mid;
            loadSearchImage(mid);
        }

        function loadSearchImage(page) {
            document.getElementById('searchQuestion').innerText = `Is page ${page} in the section?`;
            fetch(`/page/${page}`)
            .then(response => response.json())
            .then(data => {
                document.getElementById('searchImageFrame').src = data.image;
                document.getElementById('searchPageText').innerHTML = data.text;
                document.getElementById('searchPageLabel').innerText = `Page ${page}`;
                currentCandidate = page;
                updateSearchNavigation();
            });
        }

        function searchPrev() {
            if (currentCandidate > low) {
                loadSearchImage(currentCandidate - 1);
            }
        }

        function searchNext() {
            if (currentCandidate < high) {
                loadSearchImage(currentCandidate + 1);
            }
        }

        function updateSearchNavigation() {
            document.getElementById('searchPrevBtn').disabled = currentCandidate <= low;
            document.getElementById('searchNextBtn').disabled = currentCandidate >= high;
        }

        function searchYes() {
            if (searchType === 'start') {
                high = currentCandidate;
            } else {
                low = currentCandidate;
            }
            doBinaryStep();
        }

        function searchNo() {
            if (searchType === 'start') {
                low = currentCandidate + 1;
            } else {
                high = currentCandidate - 1;
            }
            doBinaryStep();
        }

        function showFinalChoice() {
            document.getElementById('searchUI').style.display = 'none';
            document.getElementById('finalChoice').style.display = 'block';
            let choices = [];
            for (let i = low; i <= high; i++) {
                choices.push(i);
            }
            let html = '';
            choices.forEach(page => {
                html += `<img src="/image/${page}" style="width: 2in; margin: 5px; cursor: pointer;" onclick="selectPage(${page})" alt="Page ${page}">`;
            });
            document.getElementById('choiceImages').innerHTML = html;
        }

        function selectPage(page) {
            if (searchType === 'start') {
                sectionStart = page;
                document.getElementById('currentStart').innerText = `Start: ${sectionStart}`;
            } else {
                sectionEnd = page;
                document.getElementById('currentEnd').innerText = `End: ${sectionEnd}`;
            }
            updateSectionInfo();
            document.getElementById('finalChoice').style.display = 'none';
            document.getElementById('pageDisplay').style.display = 'block';
        }

        function saveSection() {
            const name = document.getElementById('sectionName').value;
            fetch('/save_section', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: name, start: sectionStart, end: sectionEnd })
            })
            .then(response => response.json())
            .then(data => {
                document.getElementById('jsonOutput').textContent = JSON.stringify(data, null, 2);
                location.reload();  // Reload to show updated list
            });
        }

        function restart() {
            currentPage = {{ start_page }};
            sectionStart = null;
            sectionEnd = null;
            document.getElementById('currentStart').innerText = 'Start: Not set';
            document.getElementById('currentEnd').innerText = 'End: Not set';
            document.getElementById('sectionInfo').style.display = 'none';
            document.getElementById('searchUI').style.display = 'none';
            document.getElementById('finalChoice').style.display = 'none';
            document.getElementById('pageDisplay').style.display = 'block';
            loadPage();
        }

        // Add keyboard support
        document.getElementById('startPage').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                loadPageFromInput();
            }
        });

        document.getElementById('jumpPages').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                jumpPages();
            }
        });

        loadPage();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    start_page = request.args.get('start', min_page, type=int)
    return render_template_string(template, start_page=start_page, min_page=min_page, max_page=max_page, sections=sections)

@app.route('/page/<int:page_num>')
def get_page(page_num):
    logging.info(f"Requesting page {page_num}")
    # Find image and text for page_num
    image_path = None
    text = ""
    for root, _, files in os.walk(extract_dir):
        for file in files:
            match = re.search(r'DOJ-OGR-(\d+)\.(jpg|jpeg|tif|tiff)$', file)
            if match and int(match.group(1)) == page_num:
                image_path = os.path.join(root, file)
                logging.info(f"Found image file: {image_path}")
                break
        if image_path:
            break
    if not image_path:
        logging.warning(f"No image file found for page {page_num}")

    if image_path:
        # Handle different extensions for text files
        base_path = image_path.replace(extract_dir, ocr_dir)
        txt_path = base_path + '.txt'
        if not os.path.exists(txt_path):
            # Try other extensions if .txt doesn't exist
            for ext in ['.jpg', '.jpeg', '.tif', '.tiff']:
                alt_txt_path = base_path.replace(ext, '.txt')
                if os.path.exists(alt_txt_path):
                    txt_path = alt_txt_path
                    break
        if os.path.exists(txt_path):
            with open(txt_path, 'r', encoding='utf-8') as f:
                text = f.read()

    return jsonify({
        'image': f'/image/{page_num}' if image_path else '',
        'text': text
    })

@app.route('/image/<int:page_num>')
def get_image(page_num):
    logging.info(f"Requesting image for page {page_num}")
    for root, _, files in os.walk(extract_dir):
        for file in files:
            match = re.search(r'DOJ-OGR-(\d+)\.(jpg|jpeg|tif|tiff)$', file)
            if match and int(match.group(1)) == page_num:
                logging.info(f"Serving image file: {os.path.join(root, file)}")
                return send_from_directory(root, file)
    logging.error(f"Image file not found for page {page_num}")
    return '', 404

@app.route('/save_section', methods=['POST'])
def save_section():
    data = request.json
    name = data['name']
    start = data['start']
    end = data['end']
    global sections
    sections[name] = [start, end]
    save_sections(sections)
    return jsonify(sections)

if __name__ == '__main__':
    app.run(debug=True)