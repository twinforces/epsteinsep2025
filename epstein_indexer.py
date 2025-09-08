import os
import json
import re
import traceback
from collections import defaultdict
from mako.template import Template
import unicodedata
import inflect
from fuzzywuzzy import fuzz

# Directories
ocr_dir = "epstein_ocr_texts"
objects_dir = "epstein_objects"
video_pages_dir = "epstein_video_pages"
concordance_pages_dir = "epstein_concordance_pages"
index_file = "concordance.json"
dictionary_file = "common_english_words.txt"
extract_dir = "epstein_files"
os.makedirs(concordance_pages_dir, exist_ok=True)
os.makedirs(video_pages_dir, exist_ok=True)

# Download URL for dictionary
DICTIONARY_URL = "https://raw.githubusercontent.com/first20hours/google-10000-english/master/google-10000-english-no-swears.txt"

# Static stop words
STATIC_STOP_WORDS = {
    'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from', 'has', 'he',
    'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the', 'to', 'was', 'were', 'will',
    'with', 'i', 'you', 'we', 'they', 'this', 'but', 'or', 'not', 'if', 'so',
    'all', 'any', 'can', 'do', 'had', 'have', 'her', 'him', 'his', 'how', 'me',
    'my', 'no', 'our', 'out', 'she', 'their', 'them', 'then', 'there', 'these',
    'those', 'up', 'what', 'when', 'where', 'which', 'who', 'why', 'would',
    'also', 'always', 'never', 'often', 'sometimes', 'usually', 'generally', 'really',
    'very', 'quite', 'rather', 'too', 'almost', 'nearly', 'just', 'still', 'yet',
    'already', 'soon', 'now', 'again', 'once', 'twice', 'ever', 'seldom', 'rarely',
    'frequently', 'quickly', 'slowly', 'easily', 'carefully', 'clearly', 'probably',
    'perhaps', 'maybe', 'surely', 'certainly', 'possibly', 'definitely', 'truly',
    'good', 'bad', 'big', 'small', 'large', 'little', 'great', 'high', 'low', 'new',
    'old', 'young', 'first', 'last', 'next', 'previous', 'same', 'different', 'many',
    'few', 'some', 'several', 'own', 'other', 'another', 'each', 'every', 'certain',
    'such', 'whole', 'full', 'empty', 'long', 'short', 'wide', 'narrow', 'strong',
    'weak', 'hot', 'cold', 'warm', 'cool', 'heavy', 'light', 'dark', 'bright',
    'true', 'false', 'real', 'main', 'important', 'clear', 'simple', 'common',
    'nor', 'although', 'because', 'since', 'unless', 'while', 'whereas', 'whenever',
    'wherever', 'until', 'before', 'after',
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

# Always include words (salacious or controversial)
ALWAYS_INCLUDE_WORDS = {
    'trump', 'penis', 'vagina', 'orgasm', 'seduction', 'sex', 'rape', 'massage', 'island', 'clinton',
    'prince', 'andrew', 'bill', 'gates', 'child', 'minor', 'prostitute', 'traffick', 'trafficking',
    'victim', 'abuse', 'assault', 'harass', 'porn', 'nude', 'naked', 'slave', 'master', 'dominate',
    'submit', 'bondage', 'mar-a-lago', 'alessi', "wexner", 'maxwell', 'employee', 'kellen',
    'rodriguez', 'figueroa','jongh','dershowitz','brunel','richardson','dubin','copperfield','jackson',
    'black','giuffre','sjoberg','spacey','tucker','hawking','musk','hoffman','zuckerberg','ito','jongh',
    'siegal','ferguson','althorp','andersson','minksy','weinstein','araoz'
}

# Static stop word regex patterns
STATIC_STOP_RE = [
    re.compile(r'\w*\d+\w*'),  # Any word with digits
    re.compile(r'\w+ing'),
    re.compile(r'\w+ly'),
    re.compile(r'subpoena\w*'),
    re.compile(r'affidavit\w*'),
    re.compile(r'deposition\w*'),
    re.compile(r'([a-z])\1{3,}'),
    re.compile(r'^\d+\w*'),
    re.compile(r'^[a-z]{1,3}$'),
    re.compile(r'^[aeiou]{2,}[a-z]*$'),
    re.compile(r'[bcdfghjklmnpqrstvwxyz]{4,}'),
    re.compile(r'[aeiou]{3,}'),
    re.compile(r'([aeiou][bcdfghjklmnpqrstvwxyz]){3,}'),
    re.compile(r'([a-z])\1{2,}'),
    re.compile(r'^[a-z]{15,}$'),
    re.compile(r'[aeiou]{2,}[bcdfghjklmnpqrstvwxyz]{2,}')
]

# Mako template for main word HTML
main_word_template_str = """
<!DOCTYPE html>
<html>
<head>
    <title>Concordance for "${word or 'Unknown'}"</title>
    <style>
        .pager { margin: 10px 0; }
        .run { display: inline-block; margin-right: 10px; }
        .nav-arrow { cursor: pointer; font-size: 1.2em; margin: 0 5px; }
        .nav-arrow:disabled { color: grey; cursor: not-allowed; }
        .context-hint { font-style: italic; color: #555; }
        .container { display: flex; }
        .image { flex: 1; }
        .text { flex: 1; font-family: monospace; white-space: pre-wrap; overflow: auto; height: 800px; padding-left: 10px; }
        img { width: 8.5in; height: auto; }
        .highlight { background-color: yellow; }
    </style>
    <script>
        let currentRun = 0;
        let currentPageIndex = 0;
        const runs = ${runs_json};
        const pageToPath = ${page_to_path_json};
        const textData = ${text_data_json};
        const word = '${word}';
        <%text>
        function loadPage(runIndex, pageIndex) {
            if (!runs || runs.length === 0 || !runs[runIndex] || !runs[runIndex].pages || runs[runIndex].pages.length === 0) {
                document.getElementById('contextHint').innerText = 'No pages available';
                return;
            }
            const pageNum = runs[runIndex].pages[pageIndex];
            const pagePath = pageToPath[pageNum];
            if (pagePath) {
                document.getElementById('imageFrame').src = '../epstein_files/' + pagePath;
                const fullText = textData[pagePath] || 'No text available';
                document.getElementById('pageText').innerHTML = fullText;
            }
            currentRun = runIndex;
            currentPageIndex = pageIndex;
            updateNavigation();
            updateContextHint();
        }
        function prevPage() {
            if (!runs || runs.length === 0) return;
            if (currentPageIndex > 0) {
                loadPage(currentRun, currentPageIndex - 1);
            } else if (currentRun > 0) {
                currentRun--;
                currentPageIndex = (runs[currentRun].pages || []).length - 1;
                loadPage(currentRun, currentPageIndex);
            }
        }
        function nextPage() {
            if (!runs || runs.length === 0) return;
            if (currentPageIndex < (runs[currentRun].pages || []).length - 1) {
                loadPage(currentRun, currentPageIndex + 1);
            } else if (currentRun < runs.length - 1) {
                currentRun++;
                currentPageIndex = 0;
                loadPage(currentRun, currentPageIndex);
            }
        }
        function updateNavigation() {
            if (!runs || runs.length === 0) {
                document.getElementById('prevArrow').disabled = true;
                document.getElementById('nextArrow').disabled = true;
                document.getElementById('contextHint').innerText = 'No pages available';
                return;
            }
            document.getElementById('prevArrow').disabled = currentRun === 0 && currentPageIndex === 0;
            document.getElementById('nextArrow').disabled = currentRun === runs.length - 1 && currentPageIndex === (runs[currentRun].pages || []).length - 1;
        }
        function updateContextHint() {
            if (!runs || runs.length === 0) {
                document.getElementById('contextHint').innerText = 'No pages available';
                return;
            }
            const run = runs[currentRun] || {};
            const pages = run.pages || [];
            const currentPage = pages[currentPageIndex] || 1;
            const before = currentPageIndex;
            const after = pages.length - 1 - currentPageIndex;
            document.getElementById('contextHint').innerText = 'Showing page ' + currentPage + ' of run ' + (run.start || 0) + '-' + (run.end || 0) + ', can navigate ' + before + ' pages before, ' + after + ' pages after';
        }
        </%text>
    </script>
</head>
<body onload="loadPage(0, 0);">
    <h1>Pages containing "${word or 'Unknown'}" (${len(paths or [])} total)</h1>
    <div class="pager">
    % if runs and len(runs or []) > 0:
        % for i, run in enumerate(runs or []):
            <div class="run">
                <a href="#" onclick="loadPage(${i}, 0); return false;">${run.get('start', 0)}-${run.get('end', 0)}</a>
            </div>
        % endfor
    % else:
        <p>No pages available</p>
    % endif
    </div>
    <div>
        <button id="prevArrow" class="nav-arrow" onclick="prevPage()">&larr;</button>
        <button id="nextArrow" class="nav-arrow" onclick="nextPage()">&rarr;</button>
    </div>
    <p id="contextHint" class="context-hint"></p>
    <div class="container">
        <div class="image">
            <img id="imageFrame" src="" alt="Page image">
        </div>
        <div class="text" id="pageText"></div>
    </div>
</body>
</html>
"""

# Mako template for subpage HTML
subpage_template_str = """
<!DOCTYPE html>
<html>
<head>
    <title>${word or 'Unknown'} - Page ${page_num}</title>
    <style>
        img { width: auto; height: auto; max-width: 100%; }
    </style>
</head>
<body>
    <h2>Group ${page_num} (${(page_num-1)*10 + 1} - ${min(page_num*10, len(group or []))})</h2>
    % for path, text_snippet in group or []:
        <p><strong>${path}</strong>: ${text_snippet}</p>
        <img src="../epstein_files/${path.replace(os.sep, '/')}" alt="${path}"><br>
    % endfor
</body>
</html>
"""

# Mako template for index HTML
index_template_str = """
<!DOCTYPE html>
<html>
<head>
    <title>Epstein Concordance Index</title>
</head>
<body>
    <h1>Concordance Index</h1>
    <p>Click a word to see pages where it appears (top 1000 dictionary words, top 100 proper nouns, and always-included terms).</p>
    <ul>
    % for word in sorted_words or []:
        <li><a href="${word}.html">${word}</a></li>
    % endfor
    </ul>
</body>
</html>
"""

# Mako template for video HTML
video_template_str = """
<!DOCTYPE html>
<html>
<head>
    <title>${base_name} - Detected Objects</title>
    <style>
        .thumbnail { width: 100px; transition: transform 0.3s; }
        .thumbnail:hover { transform: scale(4.0); }
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
                % if thumbnail_paths[t]:
                    <br><img src="${thumbnail_paths[t]}" class="thumbnail" alt="Frame at ${t}s">
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

# Initialize inflect engine
inflect_engine = inflect.engine()

# Function to remove accents/diacritics
def remove_accents(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')

# Function to clean OCR text
def clean_ocr_text(text):
    text = text.replace('1', 'l').replace('0', 'o')
    text = re.sub(r'l{2,}', 'll', text)
    text = re.sub(r't{2,}', 't', text)
    text = re.sub(r'i{2,}', 'i', text)
    text = re.sub(r'aa+', 'a', text)
    text = re.sub(r'ow', 'ou', text)
    text = re.sub(r'ti$', 't', text)
    return text

# Function to lemmatize a word
def lemmatize_word(word, dictionary):
    if word.lower() in ALWAYS_INCLUDE_WORDS:
        return word.lower()
    try:
        singular = inflect_engine.singular_noun(word)
    except:
        singular = None
    if singular:
        return singular.lower() if singular.lower() in dictionary else word.lower()
    if word.endswith('ed') or word.endswith('ing') or word.endswith('es'):
        if word.endswith('ing'):
            base = word[:-3]
            if base.endswith('e'):
                base = base[:-1]
            return base if base in dictionary else word
        if word.endswith('ed'):
            base = word[:-2]
            return base if base in dictionary else word
        if word.endswith('es'):
            base = word[:-2]
            return base if base in dictionary else word
    return word.lower()

# Function to extract full OCR text
def get_full_ocr_text(txt_path):
    with open(txt_path, "r", encoding="utf-8") as f:
        content = clean_ocr_text(remove_accents(f.read()))
    return content

# Function to group sequential pages
def group_sequential_pages(paths):
    if not paths:
        return []
    # Deduplicate paths and extract page numbers
    page_numbers = []
    for path in set(paths):
        # Extract the page number from the filename (e.g., 'DOJ-OGR-00000519.jpg' -> 519)
        filename = os.path.basename(path)
        match = re.search(r'DOJ-OGR-(\d+)\.(jpg|jpeg|tif|tiff)$', filename)
        if not match:
            print(f"Warning: Invalid page number in path {path}, skipping")
            continue
        try:
            page_num = int(match.group(1))
            page_numbers.append((page_num, path))
        except ValueError:
            print(f"Warning: Invalid page number in path {path}, skipping")
            continue
    # Sort by page number
    page_numbers.sort(key=lambda x: x[0])
    
    runs = []
    current_run = []
    last_num = None
    for page_num, path in page_numbers:
        if last_num is None or page_num <= last_num + 5:
            current_run.append(page_num)
        else:
            if current_run:
                runs.append({"start": current_run[0], "end": current_run[-1], "pages": sorted(set(current_run))})
            current_run = [page_num]
        last_num = page_num
    if current_run:
        runs.append({"start": current_run[0], "end": current_run[-1], "pages": sorted(set(current_run))})
    
    return runs

# Function to consolidate similar words
def consolidate_concordance(concordance, dictionary):
    consolidated = defaultdict(set)
    word_counts = {word: len(paths) for word, paths in concordance.items()}
    words = sorted(word_counts.keys(), key=lambda w: word_counts[w], reverse=True)
    merged_mapping = {}
    merged_words = set()
    
    for i, word in enumerate(words):
        if word in merged_words:
            continue
        consolidated[word].update(concordance[word])
        merged_mapping[word] = set([word])
        for other in words[i+1:]:
            if other in merged_words:
                continue
            if word in ALWAYS_INCLUDE_WORDS or other in ALWAYS_INCLUDE_WORDS:
                continue  # Do not merge ALWAYS_INCLUDE words
            threshold = 95  # Increased for less aggressive merging
            if abs(len(word) - len(other)) <= 1:
                try:
                    if fuzz.ratio(word, other) > threshold:
                        target = word if (word in dictionary or word in ALWAYS_INCLUDE_WORDS or word_counts[word] >= word_counts[other]) else other
                        consolidated[target].update(concordance[other])
                        merged_mapping[target].add(other)
                        merged_words.add(other if target == word else word)
                except Exception as e:
                    print(f"Error in fuzzy matching {word} vs {other}: {e}")
                    continue
                target = word if (word in dictionary or word in ALWAYS_INCLUDE_WORDS or word_counts[word] >= word_counts[other]) else other
                consolidated[target].update(concordance[other])
                merged_mapping[target].add(other)
                merged_words.add(other if target == word else word)
    
    consolidated_concordance = {k: sorted(list(v)) for k, v in consolidated.items() if k not in merged_words}
    final_merged_mapping = {k: sorted(list(v)) for k, v in merged_mapping.items() if k in consolidated_concordance}
    
    print(f"Words after fuzzy matching: {len(consolidated_concordance)}")
    print(f"Merged words (first 10): {dict(list({k: v for k, v in final_merged_mapping.items() if len(v) > 1}.items())[:10])}")
    return consolidated_concordance, final_merged_mapping

# Function to build concordance
def build_concordance():
    if not os.path.exists(dictionary_file):
        print(f"Dictionary not found. Download from {DICTIONARY_URL} and place in the same directory as this script.")
        return {}, set(), set(), {}, {}
    
    with open(dictionary_file, "r", encoding="utf-8") as f:
        dictionary = set(line.strip().lower() for line in f)
    
    total_pages = 0
    word_freq = defaultdict(int)
    title_words = set()
    non_dict_words = set()
    rejected_words = defaultdict(lambda: defaultdict(int))
    rejected_proper_nouns = defaultdict(lambda: defaultdict(int))
    
    # First pass
    for root, _, files in os.walk(ocr_dir):
        for file in files:
            if file.endswith(".txt"):
                total_pages += 1
                txt_path = os.path.join(root, file)
                with open(txt_path, "r", encoding="utf-8") as f:
                    content = clean_ocr_text(remove_accents(f.read()))
                    words = set(re.findall(r'\b[\w-]+(?:\'\w+)?\b', content))
                    for word in words:
                        if (word.istitle() or word.isupper()) and len(word.lower()) >= 9 and len(word.lower()) <= 14:
                            if re.search(r'[bcdfghjklmnpqrstvwxyz][aeiou]*[bcdfghjklmnpqrstvwxyz][aeiou]*[bcdfghjklmnpqrstvwxyz]', word.lower(), re.IGNORECASE):
                                title_words.add(word.lower())
                    content_lower = content.lower()
                    words_lower = set(re.findall(r'\b[\w-]+(?:\'\w+)?\b', content_lower))
                    for word in words_lower:
                        lemma = lemmatize_word(word, dictionary)
                        word_freq[lemma] += 1
                        if lemma not in dictionary and (lemma in title_words or word.istitle() or word.isupper()):
                            non_dict_words.add(lemma)
    
    print(f"Total pages processed: {total_pages}")
    
    dynamic_stop_threshold = total_pages * 0.5
    dynamic_stop_words = {word for word, count in word_freq.items() if count > dynamic_stop_threshold}
    stop_words = STATIC_STOP_WORDS.union(dynamic_stop_words) - ALWAYS_INCLUDE_WORDS
    print(f"Generated {len(dynamic_stop_words)} dynamic stop words. Total stop words: {len(stop_words)}.")
    
    always_included = {word: count for word, count in word_freq.items() if word in ALWAYS_INCLUDE_WORDS}
    print(f"Always included words: {dict(always_included)}")
    
    high_freq_words = {word for word, count in word_freq.items() if count > 100 and word in dictionary}
    run_together_candidates = set()
    for word, count in word_freq.items():
        if count < 5 and len(word) > 15:
            for hf_word in high_freq_words:
                if word.startswith(hf_word) and word[len(hf_word):] in dictionary:
                    run_together_candidates.add(word)
                    break
    
    # Precompute fuzzy similarity for all unique lemmas
    lemma_similarity = {}
    for lemma in word_freq.keys():
        if lemma in ALWAYS_INCLUDE_WORDS:
            lemma_similarity[lemma] = True
            continue
        dict_candidates = [d for d in dictionary if abs(len(d) - len(lemma)) <= 2 and d]
        try:
            lemma_similarity[lemma] = any(fuzz.ratio(lemma, d) > 80 for d in dict_candidates)
        except Exception as e:
            print(f"Error in fuzzy matching for {lemma}: {e}")
            lemma_similarity[lemma] = False
    
    # Second pass
    concordance = defaultdict(set)
    word_sources = defaultdict(set)
    accepted_words = set()
    accepted_proper_nouns = defaultdict(int)
    for root, _, files in os.walk(ocr_dir):
        for file in files:
            if file.endswith(".txt"):
                txt_path = os.path.join(root, file)
                with open(txt_path, "r", encoding="utf-8") as f:
                    content = clean_ocr_text(remove_accents(f.read()))
                    words = re.findall(r'\b[\w-]+(?:\'\w+)?\b', content)
                    words_lower = re.findall(r'\b[\w-]+(?:\'\w+)?\b', content.lower())
                    relative_dir = os.path.relpath(root, ocr_dir)
                    original_file = file[:-4]
                    original_path = os.path.join(relative_dir, original_file) if relative_dir != '.' else original_file
                    for word, word_lower in zip(words, words_lower):
                        lemma = lemmatize_word(word_lower, dictionary)
                        is_always_include = lemma in ALWAYS_INCLUDE_WORDS
                        # Vowel-to-consonant ratio check
                        vowels = sum(1 for c in lemma if c in 'aeiou')
                        consonants = sum(1 for c in lemma if c in 'bcdfghjklmnpqrstvwxyz')
                        # Dictionary similarity check (precomputed)
                        is_similar_to_dict = lemma_similarity.get(lemma, False)
                        is_proper_noun = (len(lemma) >= 9 and len(lemma) <= 14 and
                                          re.search(r'[bcdfghjklmnpqrstvwxyz][aeiou]*[bcdfghjklmnpqrstvwxyz][aeiou]*[bcdfghjklmnpqrstvwxyz]', lemma, re.IGNORECASE) and
                                          not re.search(r'[aeiou]{3,}', lemma, re.IGNORECASE) and
                                          not re.search(r'([a-z])\1{2,}', lemma, re.IGNORECASE) and
                                          not re.search(r'[bcdfghjklmnpqrstvwxyz]{3,}', lemma, re.IGNORECASE) and
                                          vowels <= consonants and
                                          word_freq[lemma] >= 20 and
                                          (is_similar_to_dict or '-' in lemma) and
                                          (word.istitle() or word.isupper() or lemma in title_words))
                        if lemma.isdigit() or re.search(r'\w*\d+\w*', lemma):
                            rejected_words[lemma]['digit'] += 1
                            continue
                        if is_always_include:
                            concordance[lemma].add(original_path)
                            word_sources[lemma].add("always_include")
                            if lemma in dictionary:
                                word_sources[lemma].add("dictionary")
                            if word.istitle():
                                word_sources[lemma].add("title_case")
                            if word.isupper():
                                word_sources[lemma].add("all_caps")
                            if lemma in title_words:
                                word_sources[lemma].add("title_words")
                            accepted_words.add(lemma)
                            continue
                        if len(lemma) < 9 or len(lemma) > 14:
                            rejected_words[lemma]['length'] += 1
                            continue
                        if lemma in stop_words:
                            rejected_words[lemma]['stop_word'] += 1
                            continue
                        if lemma in run_together_candidates:
                            rejected_words[lemma]['run_together'] += 1
                            continue
                        if any(pattern.match(lemma) for pattern in STATIC_STOP_RE):
                            rejected_words[lemma]['regex'] += 1
                            if is_proper_noun:
                                rejected_proper_nouns[lemma]['regex'] += 1
                            continue
                        if not (lemma in dictionary or is_proper_noun):
                            rejected_words[lemma]['not_dict_or_proper'] += 1
                            continue
                        concordance[lemma].add(original_path)
                        if lemma in dictionary:
                            word_sources[lemma].add("dictionary")
                        if word.istitle():
                            word_sources[lemma].add("title_case")
                        if word.isupper():
                            word_sources[lemma].add("all_caps")
                        if lemma in title_words:
                            word_sources[lemma].add("title_words")
                        accepted_words.add(lemma)
                        if is_proper_noun:
                            accepted_proper_nouns[lemma] += 1
    
    print(f"Words in initial concordance: {len(concordance)}")
    print(f"Accepted proper nouns (first 10): {dict(list({k: v for k, v in accepted_proper_nouns.items()}.items())[:10])}")
    print(f"Rejected proper nouns (first 10): {dict(list({k: dict(v) for k, v in rejected_proper_nouns.items()}.items())[:10])}")
    
    filtered_concordance = {word: sorted(list(paths)) for word, paths in concordance.items() if 1 <= len(paths) <= 50000}
    print(f"Words after frequency filter: {len(filtered_concordance)}")
    
    consolidated_concordance = filtered_concordance
    merged_mapping = {}
    
    dict_words = {word: paths for word, paths in consolidated_concordance.items() if word in dictionary or word in ALWAYS_INCLUDE_WORDS}
    proper_nouns = {word: paths for word, paths in consolidated_concordance.items() if word not in dictionary and word not in ALWAYS_INCLUDE_WORDS}
    top_dict_words = dict(sorted(dict_words.items(), key=lambda x: len(x[1]), reverse=True)[:1000])
    top_proper_nouns = dict(sorted(proper_nouns.items(), key=lambda x: len(x[1]), reverse=True)[:100])
    final_concordance = {**top_dict_words, **top_proper_nouns}
    print(f"Words after limiting to top 1000 dictionary + 100 proper nouns: {len(final_concordance)}")
    
    final_word_sources = {word: ",".join(sorted(word_sources.get(word, ["unknown"]))) for word in final_concordance}
    final_merged_mapping = {word: merged_mapping.get(word, [word]) for word in final_concordance}
    
    with open(index_file, "w", encoding="utf-8") as f:
        json.dump(final_concordance, f, indent=2)
    
    print(f"Concordance built and saved to {index_file}.")
    print(f"Sample non-dictionary words flagged as proper nouns: {list(proper_nouns.keys())[:10]}")
    
    thumbnail_files = [f for f in os.listdir(objects_dir) if f.endswith(('.jpg', '.jpeg', '.tif', '.tiff'))]
    print(f"Available thumbnails in {objects_dir}: {thumbnail_files[:10]}")
    
    return final_concordance, title_words, non_dict_words, final_word_sources, final_merged_mapping

# Function to generate concordance HTML pages
def generate_concordance_pages(concordance):
    try:
        main_word_template = Template(main_word_template_str)
        subpage_template = Template(subpage_template_str)
    except Exception as e:
        print(f"Error compiling templates: {traceback.format_exc()}")
        return
    
    for word, paths in concordance.items():
        print(f"Generating pages for word: {word}, paths: {len(paths)}")
        page_size = 10
        groups = []
        for i in range(0, len(paths), page_size):
            group_paths = paths[i:i + page_size]
            group = []
            for path in group_paths:
                txt_path = os.path.join(ocr_dir, f"{path}.txt")
                text_snippet = get_full_ocr_text(txt_path) if os.path.exists(txt_path) else "No text available"
                group.append((path, text_snippet))
            groups.append(group)
        runs = group_sequential_pages(paths)
        print(f"Runs for {word}: {runs}")
        
        # Validate runs
        if not runs or not all('start' in run and 'end' in run and 'pages' in run and run['pages'] for run in runs):
            print(f"Warning: Invalid runs for {word}: {runs}, skipping HTML generation")
            continue
        
        # Pre-serialize runs to JSON
        runs_json = json.dumps(runs or [], ensure_ascii=False)
    
        # Create pageToPath and textData
        page_to_path = {}
        text_data = {}
        for path in paths:
            match = re.search(r'DOJ-OGR-(\d+)\.(jpg|jpeg|tif|tiff)$', path)
            if match:
                page_num = int(match.group(1))
                page_to_path[page_num] = path
                txt_path = os.path.join(ocr_dir, f"{path}.txt")
                full_text = get_full_ocr_text(txt_path) if os.path.exists(txt_path) else "No text available"
                # Pre-highlight the word
                highlighted_text = re.sub(r'\b' + re.escape(word) + r'\b', '<span class="highlight">\\g<0></span>', full_text, flags=re.IGNORECASE)
                text_data[path] = highlighted_text
        page_to_path_json = json.dumps(page_to_path, ensure_ascii=False)
        text_data_json = json.dumps(text_data, ensure_ascii=False)
    
        try:
            html_content = main_word_template.render(
                word=word,
                runs=runs,
                paths=paths,
                runs_json=runs_json,
                page_to_path_json=page_to_path_json,
                text_data_json=text_data_json,
                len=len,
                min=min
            )
            print(f"Rendered main template for {word}: {len(html_content)} characters")
            main_html_path = os.path.join(concordance_pages_dir, f"{word}.html")
            with open(main_html_path, "w", encoding="utf-8") as html:
                html.write(html_content)
        except Exception as e:
            print(f"Error rendering main page for {word}: {traceback.format_exc()}")
            with open(f"debug_{word}.html", "w", encoding="utf-8") as debug_file:
                debug_file.write(html_content if 'html_content' in locals() else "No content rendered")
            continue

# Function to generate index HTML
def generate_index(concordance):
    try:
        index_template = Template(index_template_str)
    except Exception as e:
        print(f"Error compiling index template: {traceback.format_exc()}")
        return
    
    sorted_words = sorted(concordance.keys())
    
    words_by_letter = defaultdict(list)
    for word in sorted_words:
        first_letter = word[0].upper() if word else '?'
        words_by_letter[first_letter].append(word)
    
    for letter, letter_words in sorted(words_by_letter.items()):
        try:
            html_content = index_template.render(
                sorted_words=letter_words
            )
            letter_path = os.path.join(concordance_pages_dir, f"index_{letter}.html")
            with open(letter_path, "w", encoding="utf-8") as html:
                html.write(html_content)
        except Exception as e:
            print(f"Error rendering index for letter {letter}: {traceback.format_exc()}")
            continue
    
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
    try:
        main_index_template = Template(main_index_str)
    except Exception as e:
        print(f"Error compiling main index template: {traceback.format_exc()}")
        return
    
    sorted_letters = sorted(words_by_letter.keys())
    try:
        main_html_content = main_index_template.render(
            sorted_letters=sorted_letters
        )
        main_index_path = os.path.join(concordance_pages_dir, "index.html")
        with open(main_index_path, "w", encoding="utf-8") as html:
            html.write(main_html_content)
    except Exception as e:
        print(f"Error rendering main index: {traceback.format_exc()}")

# Function to generate concordance.md
def generate_concordance_md(concordance, title_words, non_dict_words, word_sources, merged_mapping):
    md_path = "concordance3.md"
    total_words = sum(len(paths) for paths in concordance.values())
    unique_words = len(concordance)
    proper_nouns = sum(1 for word in concordance if word.islower() and word in title_words)
    avg_pages = total_words / unique_words if unique_words > 0 else 0

    # Categorize words
    always_include = {}
    possible_names = {}
    everything_else = {}

    for word in concordance:
        count = len(concordance[word])
        source = word_sources.get(word, "unknown")

        if word in ALWAYS_INCLUDE_WORDS:
            always_include[word] = (count, source)
        elif any(tag in source for tag in ['title_case', 'all_caps', 'title_words']):
            possible_names[word] = (count, source)
        else:
            everything_else[word] = (count, source)

    try:
        with open(md_path, "w", encoding="utf-8") as md:
            md.write("# Concordance Review\n\n")
            md.write(f"## Stats\n")
            md.write(f"- Total word occurrences: {total_words}\n")
            md.write(f"- Unique words: {unique_words}\n")
            md.write(f"- Estimated proper nouns: {proper_nouns}\n")
            md.write(f"- Average pages per word: {avg_pages:.2f}\n")
            md.write(f"- Top 10 non-dictionary words flagged as proper nouns: {list(non_dict_words)[:10]}\n\n")

            # Table 1: The Good Stuff
            md.write("## The Good Stuff\n")
            md.write("| Word | Count | Source |\n|------|-------|--------|\n")
            for word, (count, source) in sorted(always_include.items(), key=lambda x: x[1][0], reverse=True):
                md.write(f"| {word} | {count} | {source} |\n")
            md.write("\n")

            # Table 2: Possible Names
            md.write("## Possible Names\n")
            md.write("| Word | Count | Source |\n|------|-------|--------|\n")
            for word, (count, source) in sorted(possible_names.items(), key=lambda x: x[1][0], reverse=True):
                md.write(f"| {word} | {count} | {source} |\n")
            md.write("\n")

            # Table 3: Everything Else
            md.write("## Everything Else\n")
            md.write("| Word | Count | Source |\n|------|-------|--------|\n")
            for word, (count, source) in sorted(everything_else.items(), key=lambda x: x[1][0], reverse=True):
                md.write(f"| {word} | {count} | {source} |\n")
    except Exception as e:
        print(f"Error generating concordance3.md: {traceback.format_exc()}")

# Function to generate video HTML pages
def generate_video_pages():
    try:
        video_template = Template(video_template_str)
    except Exception as e:
        print(f"Error compiling video template: {traceback.format_exc()}")
        return
    
    thumbnail_files = [f for f in os.listdir(objects_dir) if f.endswith(('.jpg', '.jpeg', '.tif', '.tiff'))]
    found_thumbnails = 0
    missing_thumbnails = 0
    html_files_generated = 0
    
    for root, _, files in os.walk(objects_dir):
        for file in files:
            if file.endswith(".txt"):
                log_path = os.path.join(root, file)
                base_name = file[:-4]
                video_full_path = None
                for root_files, _, video_files in os.walk(extract_dir):
                    if base_name in video_files:
                        video_full_path = os.path.join(root_files, base_name)
                        break
                if not video_full_path:
                    print(f"Warning: Video file {base_name} not found in {extract_dir}")
                    continue
                video_path = os.path.relpath(video_full_path, video_pages_dir).replace(os.sep, '/')
                
                detections_by_label = defaultdict(list)
                number_re = re.compile(r'^\d+\.\d+$')
                with open(log_path, "r") as f:
                    for line in f:
                        if "No high-confidence" in line or "Skipped" in line:
                            continue
                        if ':' in line:
                            time_str, dets = line.split(':', 1)
                            try:
                                time_sec = int(time_str.split()[1][:-1])
                                for det in dets.split(', '):
                                    label = det.split(' at ')[0]
                                    if number_re.match(label) or not re.match(r'^[a-zA-Z][a-zA-Z0-9]*$', label):
                                        continue
                                    detections_by_label[label].append(time_sec)
                            except (IndexError, ValueError):
                                continue
                
                thumbnail_paths = {}
                for t in sorted(set(sum(detections_by_label.values(), []))):
                    thumbnail_path = os.path.join("epstein_objects", f"{base_name}_t{t}.jpg")
                    full_thumbnail_path = os.path.join(os.getcwd(), thumbnail_path)
                    for fname in [f"{base_name}_t{t}.jpg", f"{base_name}_t{t}.jpeg", f"{base_name}_t{t}.tif", f"{base_name}_t{t}.tiff",
                                  f"{base_name.lower()}_t{t}.jpg", f"{base_name.lower()}_t{t}.jpeg", f"{base_name.lower()}_t{t}.tif", f"{base_name.lower()}_t{t}.tiff"]:
                        full_path = os.path.join(os.getcwd(), "epstein_objects", fname)
                        if os.path.exists(full_path):
                            thumbnail_paths[t] = f"../epstein_objects/{fname}".replace(os.sep, '/')
                            found_thumbnails += 1
                            break
                    else:
                        print(f"Warning: Thumbnail not found for {base_name}_t{t} (.jpg/.jpeg/.tif/.tiff) at {full_thumbnail_path}")
                        missing_thumbnails += 1
                
                try:
                    html_content = video_template.render(
                        base_name=base_name,
                        video_path=video_path,
                        detections_by_label=detections_by_label,
                        thumbnail_paths=thumbnail_paths,
                        os=os
                    )
                    html_path = os.path.join(video_pages_dir, f"{base_name}.html")
                    with open(html_path, "w", encoding="utf-8") as html:
                        html.write(html_content)
                    html_files_generated += 1
                except Exception as e:
                    print(f"Error rendering video page for {base_name}: {traceback.format_exc()}")
                    continue
    
    print(f"Video HTML summary: {html_files_generated} files generated, {found_thumbnails} thumbnails found, {missing_thumbnails} thumbnails missing")

# Main
if __name__ == "__main__":
    concordance, title_words, non_dict_words, word_sources, merged_mapping = build_concordance()
    generate_concordance_pages(concordance)
    generate_index(concordance)
    generate_concordance_md(concordance, title_words, non_dict_words, word_sources, merged_mapping)
    generate_video_pages()