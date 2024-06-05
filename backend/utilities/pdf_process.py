# @Author: Bi Ying
# @Date:   2024-06-05 23:22:25
from pathlib import Path

import fitz


def calculate_zoom(page, min_dimension=1920):
    bbox = page.rect
    width, height = bbox.width, bbox.height
    zoom_x = zoom_y = max(min_dimension / width, min_dimension / height)
    return zoom_x, zoom_y


def pdf_to_images(pdf_path, output_folder):
    print(pdf_path)
    print(output_folder)
    if not Path(output_folder).exists():
        Path(output_folder).mkdir(parents=True, exist_ok=True)

    images = []
    pdf_document = fitz.open(pdf_path)
    for page_num in range(len(pdf_document)):
        page = pdf_document.load_page(page_num)
        zoom_x, zoom_y = calculate_zoom(page, 1920)
        mat = fitz.Matrix(zoom_x, zoom_y)
        pix = page.get_pixmap(matrix=mat)
        image_path = Path(output_folder) / Path(f"page_{page_num + 1}.png")
        pix.save(str(image_path.absolute()))
        images.append(str(image_path.absolute()))

    return images


def process_pdf(input_data, action: str, output_folder: str | Path):
    if action == "render_images":
        images = pdf_to_images(input_data, output_folder)
        return images
