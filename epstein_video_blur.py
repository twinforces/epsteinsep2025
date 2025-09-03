import os
import cv2
import torch
from torchvision import models, transforms
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from tqdm import tqdm

# Directories
extract_dir = "epstein_files"
objects_dir = "epstein_objects"
os.makedirs(objects_dir, exist_ok=True)

# Load pre-trained model with updated weights param
model = models.detection.fasterrcnn_resnet50_fpn(weights="DEFAULT")
model.eval()

# Full COCO labels (91 categories including background)
COCO_LABELS = [
    '__background__', 'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus',
    'train', 'truck', 'boat', 'traffic light', 'fire hydrant', 'N/A', 'stop sign',
    'parking meter', 'bench', 'bird', 'cat', 'dog', 'horse', 'sheep', 'cow',
    'elephant', 'bear', 'zebra', 'giraffe', 'N/A', 'backpack', 'umbrella', 'N/A',
    'N/A', 'handbag', 'tie', 'suitcase', 'frisbee', 'skis', 'snowboard',
    'sports ball', 'kite', 'baseball bat', 'baseball glove', 'skateboard',
    'surfboard', 'tennis racket', 'bottle', 'N/A', 'wine glass', 'cup', 'fork',
    'knife', 'spoon', 'bowl', 'banana', 'apple', 'sandwich', 'orange',
    'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair', 'couch',
    'potted plant', 'bed', 'N/A', 'dining table', 'N/A', 'N/A', 'toilet', 'N/A',
    'tv', 'laptop', 'mouse', 'remote', 'keyboard', 'cell phone', 'microwave',
    'oven', 'toaster', 'sink', 'refrigerator', 'N/A', 'book', 'clock', 'vase',
    'scissors', 'teddy bear', 'hair drier', 'toothbrush'
]

transform = transforms.Compose([transforms.ToTensor()])

# Function to check if frame is too blurry (variance threshold; lower = blurrier)
def is_blurry(frame, threshold=100):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    variance = cv2.Laplacian(gray, cv2.CV_64F).var()
    return variance < threshold

# Function to detect objects in frame
def detect_objects(frame):
    img = transform(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))).unsqueeze(0)
    with torch.no_grad():
        preds = model(img)[0]
    return preds

# Process a video
def process_video(video_path):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error opening {video_path}")
        return
    
    base_name = os.path.basename(video_path)
    log_path = os.path.join(objects_dir, base_name + ".txt")
    with open(log_path, "w") as log:
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration_sec = frame_count / fps if fps > 0 else 0
        frame_interval_sec = 5
        num_intervals = int(duration_sec // frame_interval_sec) + 1
        
        for t_sec in tqdm(range(0, int(duration_sec), frame_interval_sec), 
                          desc=f"Processing frames in {base_name}", total=num_intervals):
            t_ms = t_sec * 1000
            cap.set(cv2.CAP_PROP_POS_MSEC, t_ms)
            ret, frame = cap.read()
            if not ret:
                continue
            
            if is_blurry(frame):
                log.write(f"Time {t_sec}s: Skipped (too blurry/redacted)\n")
                continue
            
            preds = detect_objects(frame)
            
            # Filter high-confidence detections (>0.7 for blurred content)
            detections = []
            frame_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            for i in range(len(preds["boxes"])):
                if preds["scores"][i] > 0.7:
                    label_idx = int(preds["labels"][i])
                    if label_idx < len(COCO_LABELS):
                        label = COCO_LABELS[label_idx]
                    else:
                        label = "Unknown"
                    box = preds["boxes"][i].tolist()
                    detections.append(f"{label} at {box}")
                    
                    # Annotate frame
                    draw = ImageDraw.Draw(frame_pil)
                    draw.rectangle(box, outline="red", width=3)
                    draw.text((box[0], box[1]), label, fill="red")
            
            if detections:
                log.write(f"Time {t_sec}s: {', '.join(detections)}\n")
            else:
                log.write(f"Time {t_sec}s: No high-confidence objects detected\n")
            
            # Save annotated frame only if detections
            if detections:
                frame_pil.save(os.path.join(objects_dir, f"{base_name}_t{t_sec}.jpg"))
    
    cap.release()
    print(f"Processed {base_name}")

# Collect all video paths first
video_paths = []
for root, _, files in os.walk(extract_dir):
    for file in files:
        if file.lower().endswith((".mpg", ".mp4")):
            video_paths.append(os.path.join(root, file))

# Process videos with progress bar
for path in tqdm(video_paths, desc="Processing videos"):
    print("starting", path)
    process_video(path)

print("Object recognition complete.")