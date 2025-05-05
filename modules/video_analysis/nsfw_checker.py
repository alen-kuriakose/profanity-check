from transformers import AutoProcessor, AutoModelForImageClassification
from PIL import Image
import torch
import os

model_name = "Falconsai/nsfw_image_detection"
processor = AutoProcessor.from_pretrained(model_name)
model = AutoModelForImageClassification.from_pretrained(model_name)



def detect_nudity_falconsai(frames_dir, threshold=0.7):
    results = []
    for fname in sorted(os.listdir(frames_dir)):
        if fname.endswith(".jpg") or fname.endswith(".png"):
            img_path = os.path.join(frames_dir, fname)
            image = Image.open(img_path).convert("RGB")
            inputs = processor(images=image, return_tensors="pt")
            with torch.no_grad():
                outputs = model(**inputs)
                print("model labels available",model.config.id2label)

                probs = torch.nn.functional.softmax(outputs.logits, dim=1)[0]
                labels = model.config.id2label
                top = torch.argmax(probs).item()
                label = labels[top]
                score = probs[top].item()

                if label in ["nsfw"] and score > threshold:
                    results.append({
                        "frame": fname,
                        "label": label,
                        "score": round(score, 3)
                    })
                    
    print("falconsai results",results)
    return results