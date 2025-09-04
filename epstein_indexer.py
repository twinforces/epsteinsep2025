import os
import json
import re
from collections import defaultdict
from mako.template import Template
import unicodedata  # For accent removal
import inflect  # For lemmatization

# Directories
ocr_dir = "epstein_ocr_texts"
objects_dir = "epstein_objects"
video_pages_dir = "epstein_video_pages"
concordance_pages_dir = "epstein_concordance_pages"
index_file = "concordance.json"
dictionary_file = "common_english_words.txt"  # Google 10k word list
os.makedirs(concordance_pages_dir, exist_ok=True)
os.makedirs(video_pages_dir, exist_ok=True)

# Download URL for dictionary (if not present)
DICTIONARY_URL = "https://raw.githubusercontent.com/first20hours/google-10000-english/master/google-10000-english-no-swears.txt"

# Static English stop words (including your additions)
STATIC_STOP_WORDS = {
    # Basic stop words (pronouns, prepositions, determiners, etc.)
    'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from', 'has', 'he',
    'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the', 'to', 'was', 'were', 'will',
    'with', 'i', 'you', 'we', 'they', 'this', 'but', 'or', 'not', 'if', 'so',
    'all', 'any', 'can', 'do', 'had', 'have', 'her', 'him', 'his', 'how', 'me',
    'my', 'no', 'our', 'out', 'she', 'their', 'them', 'then', 'there', 'these',
    'those', 'up', 'what', 'when', 'where', 'which', 'who', 'why', 'would',
    # Common adverbs
    'also', 'always', 'never', 'often', 'sometimes', 'usually', 'generally', 'really',
    'very', 'quite', 'rather', 'too', 'almost', 'nearly', 'just', 'still', 'yet',
    'already', 'soon', 'now', 'again', 'once', 'twice', 'ever', 'seldom', 'rarely',
    'frequently', 'quickly', 'slowly', 'easily', 'carefully', 'clearly', 'probably',
    'perhaps', 'maybe', 'surely', 'certainly', 'possibly', 'definitely', 'truly',
    # Common adjectives
    'good', 'bad', 'big', 'small', 'large', 'little', 'great', 'high', 'low', 'new',
    'old', 'young', 'first', 'last', 'next', 'previous', 'same', 'different', 'many',
    'few', 'some', 'several', 'own', 'other', 'another', 'each', 'every', 'certain',
    'such', 'whole', 'full', 'empty', 'long', 'short', 'wide', 'narrow', 'strong',
    'weak', 'hot', 'cold', 'warm', 'cool', 'heavy', 'light', 'dark', 'bright',
    'true', 'false', 'real', 'main', 'important', 'clear', 'simple', 'common',
    # Common conjunctions
    'nor', 'although', 'because', 'since', 'unless', 'while', 'whereas', 'whenever',
    'wherever', 'until', 'before', 'after',
    # Boring lawyer stuff (your additions + more legal terms)
    'overrule', 'inferably', 'incontrovertbile', 'recross', 'yeah', 'recess', 'summations',
    'partiality', 'biases', 'peremptory', 'sequestered', 'built', 'dynamics', 'claimant',
    'elicit', 'courtrooms', 'respondents', 'unreliable', 'testifies', 'remembers', 'booking',
    'tha', 'thoroughness', 'peer', 'sidebar', 'crossed', 'stipulate', 'comp',
    'revision', 'incoming', 'suppose', 'push', 'mainly', 'revisions', 'redirect', 'varying',
    'recounted', 'rea', 'blank', 'departmental', 'inferences', 'recalls', 'commences', 'boe',
    'stipulations', 'vote', 'prevalence', 'zip', 'sender', 'ref', 'yee', 'inflammatory',
    'probative', 'distinction', 'nae', 'subpoenaed', 'ise', 'conjecture', 'declarant', 'ale',
    'rle', 'retrieve', 'tab', 'interrogatories', 'recalled', 'incrimination', 'const', 'ability',
    'able', 'about', 'attorney', 'testimony', 'objection', 'affidavit', 'deposition', 'plaintiff',
    'defendant', 'motion', 'hearing', 'trial', 'evidence', 'witness', 'counsel', 'judge', 'jury'
}

# Static stop word regex patterns
STATIC_STOP_RE = [
    re.compile(r'\w+\d+'),  # Matches 'state1', 'document123', etc.
    re.compile(r'\w+ing'),  # Matches words ending in 'ing' (gerunds/participles)
    re.compile(r'\w+ly'),   # Matches words ending in 'ly' (adverbs)
    re.compile(r'subpoena\w*'),  # Matches 'subpoena', 'subpoenaed', etc.
    re.compile(r'affidavit\w*'),  # Matches 'affidavit', 'affidavits', etc.
    re.compile(r'deposition\w*'),  # Matches 'deposition', 'depositions', etc.
    re.compile(r'([a-z])\1{2,}'),  # Repeated letters 3+
]

# Mako template for main word HTML (pager with iframe)
main_word_template_str = """
<!DOCTYPE html>
<html>
<head>
    <title>Concordance for "${word}"</title>
    <script>
        function loadPage(pageNum) {
            document.getElementById('imageFrame').src = '${word}' + pageNum + '.html';
        }
    </script>
</head>
<body>
    <h1>Pages containing "${word}" (${len(paths)} total)</h1>
    <div id="pager">
    % for i in range(1, num_pages + 1):
        <a href="#" onclick="loadPage(${i}); return false;">${i}</a>
    % endfor
    </div>
    <iframe id="imageFrame" src="${word}1.html" width="100%" height="800px"></iframe>
</body>
</html>
"""

# Mako template for subpage HTML (group of 10 images with text context)
subpage_template_str = """
<!DOCTYPE html>
<html>
<head>
    <title>${word} - Page ${page_num}</title>
</head>
<body>
    <h2>Group ${page_num} (${(page_num-1)*10 + 1} - ${min(page_num*10, len(group))})</h2>
    % for path, text_snippet in group:
        <p><strong>${path}</strong>: ${text_snippet}</p>
        <img src="../epstein_files/${path.replace(os.sep, '/')}" alt="${path}" style="max-width: 100%;"><br>
    % endfor
</body>
</html>
"""

# Mako template for index HTML (list of words)
index_template_str = """
<!DOCTYPE html>
<html>
<head>
    <title>Epstein Concordance Index</title>
</head>
<body>
    <h1>Concordance Index</h1>
    <p>Click a word to see pages where it appears (filtered: min len 3, no numbers/stop words/dynamic stops, <=20k pages).</p>
    <ul>
    % for word in sorted_words:
        <li><a href="${word}.html">${word}</a></li>
    % endfor
    </ul>
</body>
</html>
"""

# Mako template for video HTML (with thumbnails and hover zoom)
video_template_str = """
<!DOCTYPE html>
<html>
<head>
    <title>${base_name} - Detected Objects</title>
    <style>
        .thumbnail {
            width: 100px;
            transition: transform 0.3s;
        }
        .thumbnail:hover {
            transform: scale(2.0);
        }
    </style>
    <script>
        function jumpToTime(seconds) {
            document.getElementById('video').currentTime = seconds;
        }
    </script>
</head>
<body>
    <h1>${base_name}</h1>
    <video id="video" controls width="640" height="480">
        <source src="${video_path}" type="video/mp4">
        Your browser does not support the video tag.
    </video>
    <h2>Detected Objects (COCO Labels)</h2>
    <ul>
    % for label, times in sorted(detections_by_label.items()):
        <li><strong>${label}</strong>:
            <ul>
            % for t in sorted(set(times)):
                <li><a href="#" onclick="jumpToTime(${t}); return false;">${t}s</a>
                % if os.path.exists("../epstein_objects/${base_name}_t${t}.jpg"):
                    <br><img src="../epstein_objects/${base_name}_t${t}.jpg" class="thumbnail" alt="Frame at ${t}s">
                % endif
                </li>
            % endfor
            </ul>
        </li>
    % endfor
    </ul>
</body>
</html>
"""

# Initialize inflect engine for lemmatization
inflect_engine = inflect.engine()

# Function to remove accents/diacritics
def remove_accents(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')

# Function to lemmatize a word (verbs to base form, nouns to singular)
def lemmatize_word(word, dictionary):
    # Try singularizing first (for nouns)
    singular = inflect_engine.singular_noun(word)
    if singular:
        return singular.lower() if singular.lower() in dictionary else word.lower()
    # If not a noun, try verb lemmatization (simplified, assumes past/present to base)
    if word.endswith('ed') or word.endswith('ing') or word.endswith('es'):
        # Simple heuristic: strip common verb endings
        if word.endswith('ing'):
            base = word[:-3]
            if base.endswith('e'):
                base = base[:-1]  # e.g., running -> run
            return base if base in dictionary else word
        if word.endswith('ed'):
            base = word[:-2]
            return base if base in dictionary else word
        if word.endswith('es'):
            base = word[:-2]
            return base if base in dictionary else word
    return word.lower()

# Function to extract text context around a word
def get_text_context(txt_path, word, max_chars=50):
    with open(txt_path, "r", encoding="utf-8") as f:
        content = remove_accents(f.read().lower())
    # Find first occurrence of word
    word_re = re.compile(rf'\b{re.escape(word)}\b', re.IGNORECASE)
    match = word_re.search(content)
    if not match:
        return ""
    start = max(0, match.start() - max_chars // 2)
    end = min(len(content), match.end() + max_chars // 2)
    text_snippet = content[start:end].replace('\n', ' ').strip()
    return f"...{text_snippet}..." if start > 0 or end < len(content) else text_snippet

# Function to build concordance index with dynamic stop words
def build_concordance():
    if not os.path.exists(dictionary_file):
        print(f"Dictionary not found. Download from {DICTIONARY_URL} and place in the same directory as this script.")
        return {}
    
    # Load dictionary (lowercased)
    with open(dictionary_file, "r", encoding="utf-8") as f:
        dictionary = set(line.strip().lower() for line in f)
    
    # First pass: Collect original (pre-lowercase) words for istitle check
    total_pages = 0
    word_freq = defaultdict(int)  # word -> number of pages it appears on
    title_words = set()  # Words that pass istitle()
    for root, _, files in os.walk(ocr_dir):
        for file in files:
            if file.endswith(".txt"):
                total_pages += 1
                txt_path = os.path.join(root, file)
                with open(txt_path, "r", encoding="utf-8") as f:
                    content = f.read()  # Keep original case for istitle()
                    words = set(re.findall(r'\b\w+\b', content))  # Original words
                    for word in words:
                        if word.istitle():
                            title_words.add(word.lower())  # Store lowercase version
                    content_lower = remove_accents(content.lower())
                    words_lower = set(re.findall(r'\b\w+\b', content_lower))  # Lowercase for freq
                    for word in words_lower:
                        lemma = lemmatize_word(word, dictionary)
                        word_freq[lemma] += 1
    
    # Dynamic stop words: Words appearing on >50% of pages (e.g., headers like 'doj', 'ogr', 'court')
    dynamic_stop_threshold = total_pages * 0.5
    dynamic_stop_words = {word for word, count in word_freq.items() if count > dynamic_stop_threshold}
    stop_words = STATIC_STOP_WORDS.union(dynamic_stop_words)
    print(f"Generated {len(dynamic_stop_words)} dynamic stop words. Total stop words: {len(stop_words)}.")
    
    # Identify potential run-together words: Low freq words (<5 pages) that start with a high freq word (>100 pages)
    high_freq_words = {word for word, count in word_freq.items() if count > 100 and word in dictionary}
    run_together_candidates = set()
    for word, count in word_freq.items():
        if count < 5 and len(word) > 10:  # Arbitrary threshold for "long" words
            for hf_word in high_freq_words:
                if word.startswith(hf_word) and word[len(hf_word):] in dictionary:  # Second part is also a word
                    run_together_candidates.add(word)
                    break
    
    # Second pass: Build concordance excluding stops, regex, run-together, and non-dictionary (except proper names)
    concordance = defaultdict(set)  # word -> set of relative paths to original files
    for root, _, files in os.walk(ocr_dir):
        for file in files:
            if file.endswith(".txt"):
                txt_path = os.path.join(root, file)
                with open(txt_path, "r", encoding="utf-8") as f:
                    content = f.read()  # Original for istitle()
                    content_lower = remove_accents(content.lower())
                    words = re.findall(r'\b\w+\b', content)  # Original words
                    words_lower = re.findall(r'\b\w+\b', content_lower)  # Lowercase words
                    relative_dir = os.path.relpath(root, ocr_dir)
                    original_file = file[:-4]  # Remove .txt, e.g., DOJ-OGR-00000001.jpg
                    original_path = os.path.join(relative_dir, original_file) if relative_dir != '.' else original_file
                    for word, word_lower in zip(words, words_lower):  # Pair original and lowercase
                        lemma = lemmatize_word(word_lower, dictionary)
                        if (len(lemma) >= 3 and
                            not lemma.isdigit() and
                            lemma not in stop_words and
                            lemma not in run_together_candidates and
                            not any(pattern.match(lemma) for pattern in STATIC_STOP_RE) and
                            (lemma in dictionary or word.istitle() or lemma in title_words)):  # Include if titled or lowercase of titled
                            concordance[lemma].add(original_path)
    
    # Filter out words appearing on fewer than 5 or more than 20,000 pages
    filtered_concordance = {word: sorted(list(paths)) for word, paths in concordance.items() if 5 <= len(paths) <= 20000}
    
    # Save as JSON for reference
    with open(index_file, "w", encoding="utf-8") as f:
        json.dump(filtered_concordance, f, indent=2)
    
    print(f"Concordance built and saved to {index_file}.")
    return filtered_concordance

# Function to generate concordance HTML pages
def generate_concordance_pages(concordance):
    main_word_template = Template(main_word_template_str)
    subpage_template = Template(subpage_template_str)
    
    for word, paths in concordance.items():
        # Group into pages of 10
        page_size = 10
        groups = []
        for i in range(0, len(paths), page_size):
            group_paths = paths[i:i + page_size]
            group = []
            for path in group_paths:
                txt_path = os.path.join(ocr_dir, f"{path}.txt")
                text_snippet = get_text_context(txt_path, word) if os.path.exists(txt_path) else "No text_snippet available"
                group.append((path, text_snippet))
            groups.append(group)
        num_pages = len(groups)
        
        # Generate subpages
        for page_num, group in enumerate(groups, 1):
            html_content = subpage_template.render(
                word=word,
                page_num=page_num,
                group=group,
                len=len,  # For min in template
                min=min,
                os=os
            )
            
            sub_html_path = os.path.join(concordance_pages_dir, f"{word}{page_num}.html")
            with open(sub_html_path, "w", encoding="utf-8") as html:
                html.write(html_content)
            
            print(f"Generated subpage for '{word}' page {page_num} at {sub_html_path}.")
        
        # Generate main page with pager and iframe
        html_content = main_word_template.render(
            word=word,
            num_pages=num_pages,
            len=len,  # Ensure len is passed for ${len(paths)}
            paths=paths
        )
        
        main_html_path = os.path.join(concordance_pages_dir, f"{word}.html")
        with open(main_html_path, "w", encoding="utf-8") as html:
            html.write(html_content)
        
        print(f"Generated main HTML for '{word}' at {main_html_path}.")

# Function to generate index HTML, paginated by letter
def generate_index(concordance):
    index_template = Template(index_template_str)
    sorted_words = sorted(concordance.keys())
    
    # Group words by first letter
    words_by_letter = defaultdict(list)
    for word in sorted_words:
        first_letter = word[0].upper() if word else '?'
        words_by_letter[first_letter].append(word)
    
    # Generate letter pages
    for letter, letter_words in sorted(words_by_letter.items()):
        html_content = index_template.render(
            sorted_words=letter_words
        )
        
        letter_path = os.path.join(concordance_pages_dir, f"index_{letter}.html")
        with open(letter_path, "w", encoding="utf-8") as html:
            html.write(html_content)
        
        print(f"Generated index for letter '{letter}' at {letter_path}.")
    
    # Generate main index with letter links
    main_index_str = """
<!DOCTYPE html>
<html>
<head>
    <title>Epstein Concordance Main Index</title>
</head>
<body>
    <h1>Main Index by Letter</h1>
    <ul>
    % for letter in sorted_letters:
        <li><a href="index_${letter}.html">${letter}</a></li>
    % endfor
    </ul>
</body>
</html>
    """
    main_index_template = Template(main_index_str)
    sorted_letters = sorted(words_by_letter.keys())
    main_html_content = main_index_template.render(
        sorted_letters=sorted_letters
    )
    
    main_index_path = os.path.join(concordance_pages_dir, "index.html")
    with open(main_index_path, "w", encoding="utf-8") as html:
        html.write(main_html_content)
    
    print(f"Generated main index HTML at {main_index_path}.")

# Function to generate video HTML pages using Mako, filtering weird numbers
def generate_video_pages():
    os.makedirs(video_pages_dir, exist_ok=True)
    video_template = Template(video_template_str)
    
    for root, _, files in os.walk(objects_dir):
        for file in files:
            if file.endswith(".txt"):
                log_path = os.path.join(root, file)
                base_name = file[:-4]  # e.g., DOJ-OGR-00015624.MP4
                video_path = os.path.join("..", "epstein_files", base_name)  # Relative to HTML dir
                
                # Read log and group by object label, filtering weird numbers
                detections_by_label = defaultdict(list)
                number_re = re.compile(r'^\d+\.\d+$')  # Matches like '1.5085511207580566'
                with open(log_path, "r") as f:
                    for line in f:
                        if "No high-confidence" in line or "Skipped" in line:
                            continue
                        # Parse: Time Xs: label at [box], ...
                        if ':' in line:
                            time_str, dets = line.split(':', 1)
                            try:
                                time_sec = int(time_str.split()[1][:-1])  # e.g., 5 from "Time 5s"
                                for det in dets.split(', '):
                                    label = det.split(' at ')[0]
                                    if number_re.match(label) or not re.match(r'^[a-zA-Z][a-zA-Z0-9]*$', label):  # Filter invalid labels
                                        continue
                                    detections_by_label[label].append(time_sec)
                            except (IndexError, ValueError):
                                continue  # Skip malformed lines
                
                # Render HTML with Mako
                html_content = video_template.render(
                    base_name=base_name,
                    video_path=video_path,
                    detections_by_label=detections_by_label,
                    os=os
                )
                
                html_path = os.path.join(video_pages_dir, f"{base_name}.html")
                with open(html_path, "w", encoding="utf-8") as html:
                    html.write(html_content)
                
                print(f"Generated HTML for {base_name} at {html_path}.")

# Function to generate concordance.md
def generate_concordance_md(concordance):
    md_path = "concordance.md"
    with open(md_path, "w") as md:
        md.write("# Concordance Review\n\n| Word | Count |\n|------|-------|\n")
        for word in sorted(concordance.keys()):
            count = len(concordance[word])
            md.write(f"| {word} | {count} |\n")
    print(f"Generated {md_path}")

# Main
if __name__ == "__main__":
    concordance = build_concordance()
    generate_concordance_pages(concordance)
    generate_index(concordance)
    generate_concordance_md(concordance)
    generate_video_pages()