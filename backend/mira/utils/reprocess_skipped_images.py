import pickle
from tqdm import tqdm
skipped_log_path="../venv/skipped_images.log"

def reprocess_skipped_images(skipped_log_path, drive_service, model, preprocess, caption_model, caption_processor):
    with open(skipped_log_path, "r") as log_file:
        skipped_images = [
            {"id": line.split(",")[0].split(":")[1].strip(), "name": line.split(",")[1].split(":")[1].strip()}
            for line in log_file.readlines()
        ]

    all_data = []
    for img in tqdm(skipped_images, desc="🧠 Re-Embedding Skipped Images"):
        try:
            pil_img = download_image(drive_service, img["id"])
            embed = generate_embedding(pil_img, model, preprocess)
            caption = generate_caption(pil_img, caption_model, caption_processor)

            all_data.append({
                "id": img["id"],
                "name": img["name"],
                "embedding": embed.tolist(),
                "caption": caption
            })
        except Exception as e:
            print(f"❌ Could not reprocess image {img['name']} (ID: {img['id']}): {e}")

    return all_data