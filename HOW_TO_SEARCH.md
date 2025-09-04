# How to Search

GitHub indexes the TXT files for full-text search, making it easy to find keywords without downloading everything.

- Go to the repo on GitHub.com. (Where you are reading this)
- Use the search bar at the top (or click "Go to file" > search icon).
- Enter your query, e.g., "victim name" or "specific date".
- Filter to this repo if needed (via the dropdown).
- Results will show matching TXT files from `epstein_ocr_texts/` or `epstein_objects/`.

### Mapping Search Results Back to Source Files
Each processed file corresponds directly to a source file:
- **For Documents (OCR Texts)**: A result like `epstein_ocr_texts/IMAGES001/DOJ-OGR-00000001.jpg.txt` maps to the original JPEG `epstein_files/IMAGES001/DOJ-OGR-00000001.jpg`.
  - The TXT contains extracted text (with redactions handled).
  - View the raw JPEG for visuals/context.
- **For Videos (Object Logs)**: A result like `epstein_objects/DOJ-OGR-00015624.MP4.txt` maps to the original MP4 `epstein_files/VIDEOS/DOJ-OGR-00015624.MP4` (assuming subfolder structure).
  - The TXT logs detected objects (e.g., "person at [box coords]") with timestamps, skipping blurry/redacted frames.
  - Annotated frames (e.g., `DOJ-OGR-00015624.MP4_t5.jpg`) show bounding boxes if detections occurred.
  - in other words from a file match, you can see the frame where the object was found. Known types of objects to search for are:
    -  person, bicycle, car, motorcycle, airplane, bus,
    train, truck, boat, traffic light, fire hydrant,stop sign,
    parking meter, bench, bird, cat, dog, horse, sheep, cow,
    elephant, bear, zebra, giraffe, backpack, umbrella, 
    handbag, tie, suitcase, frisbee, skis, snowboard,
    sports ball, kite, baseball bat, baseball glove, skateboard,
    surfboard, tennis racket, bottle, wine glass, cup, fork,
    knife, spoon, bowl, banana, apple, sandwich, orange,
    broccoli, carrot, hot dog, pizza, donut, cake, chair, couch,
    potted plant, bed, dining table, toilet, 
    tv, laptop, mouse, remote, keyboard, cell phone, microwave,
    oven, toaster, sink, refrigerator,  book, clock, vase,
    scissors, teddy bear, hair drier, toothbrush

If you have the raw files locally, use tools like `grep` or a text editor to search the TXTs alongside the originals.
