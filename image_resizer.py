from PIL import Image
import os

folder = "loomian_images"

CANVAS_SIZE = 500
MAX_LOOMIAN_SIZE = 450

for filename in os.listdir(folder):
    if not filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        continue

    path = os.path.join(folder, filename)

    image = Image.open(path).convert("RGBA")

    # Resize proportionally so the Loomian fits inside 450x450
    image.thumbnail(
        (MAX_LOOMIAN_SIZE, MAX_LOOMIAN_SIZE),
        Image.Resampling.LANCZOS
    )

    # Create a 500x500 transparent canvas
    canvas = Image.new(
        "RGBA",
        (CANVAS_SIZE, CANVAS_SIZE),
        (0, 0, 0, 0)
    )

    # Centre the Loomian
    x = (CANVAS_SIZE - image.width) // 2
    y = (CANVAS_SIZE - image.height) // 2

    canvas.paste(image, (x, y), image)

    canvas.save(path, "WEBP")

    print(f"Processed {filename}")