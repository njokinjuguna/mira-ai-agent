import torch
import open_clip
from transformers import BlipProcessor, BlipForConditionalGeneration

def load_openclip():
    model, _, preprocess = open_clip.create_model_and_transforms("ViT-B-32", pretrained="laion2b_s34b_b79k")
    tokenizer = open_clip.get_tokenizer("ViT-B-32")
    model.eval()
    return model, preprocess, tokenizer

def load_blip(fine_tuned_path=None):
    processor = BlipProcessor.from_pretrained(fine_tuned_path if fine_tuned_path else "Salesforce/blip-image-captioning-base")
    model = BlipForConditionalGeneration.from_pretrained(fine_tuned_path if fine_tuned_path else "Salesforce/blip-image-captioning-base")
    model.eval()
    return model, processor

def generate_embedding(image, model, preprocess):
    image_input = preprocess(image).unsqueeze(0)
    with torch.no_grad():
        image_features = model.encode_image(image_input)
    return image_features[0].cpu().numpy()

def generate_caption(image, model, processor):
    inputs = processor(images=image, return_tensors="pt")
    with torch.no_grad():
        output = model.generate(**inputs)
    return processor.decode(output[0], skip_special_tokens=True)