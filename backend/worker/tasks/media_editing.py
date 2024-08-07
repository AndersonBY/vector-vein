# @Author: Bi Ying
# @Date:   2024-08-05 00:26:36
import uuid

from worker.tasks import task, timer
from utilities.workflow import Workflow
from utilities.general import align_elements
from utilities.media_processing import ImageProcessor
from utilities.text_processing import extract_image_url
from utilities.file_processing import static_file_server


@task
@timer
def image_editing(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)

    input_image = workflow.get_node_field_value(node_id, "input_image")
    crop = workflow.get_node_field_value(node_id, "crop")
    crop_method = workflow.get_node_field_value(node_id, "crop_method")
    crop_position = workflow.get_node_field_value(node_id, "crop_position")
    crop_x = workflow.get_node_field_value(node_id, "crop_x")
    crop_y = workflow.get_node_field_value(node_id, "crop_y")
    crop_width = workflow.get_node_field_value(node_id, "crop_width")
    crop_height = workflow.get_node_field_value(node_id, "crop_height")
    crop_width_ratio = workflow.get_node_field_value(node_id, "crop_width_ratio")
    crop_height_ratio = workflow.get_node_field_value(node_id, "crop_height_ratio")
    scale = workflow.get_node_field_value(node_id, "scale")
    scale_method = workflow.get_node_field_value(node_id, "scale_method")
    scale_ratio = workflow.get_node_field_value(node_id, "scale_ratio")
    scale_width = workflow.get_node_field_value(node_id, "scale_width")
    scale_height = workflow.get_node_field_value(node_id, "scale_height")
    compress = workflow.get_node_field_value(node_id, "compress")
    rotate = workflow.get_node_field_value(node_id, "rotate")
    output_type = workflow.get_node_field_value(node_id, "output_type")

    input_image = input_image[0] if len(input_image) == 1 else input_image

    (
        has_list,
        (
            input_images,
            crops,
            crop_methods,
            crop_positions,
            crop_xs,
            crop_ys,
            crop_widths,
            crop_heights,
            crop_width_ratios,
            crop_height_ratios,
            scales,
            scale_methods,
            scale_ratios,
            scale_widths,
            scale_heights,
            compresss,
            rotates,
            output_types,
        ),
    ) = align_elements(
        (
            input_image,
            crop,
            crop_method,
            crop_position,
            crop_x,
            crop_y,
            crop_width,
            crop_height,
            crop_width_ratio,
            crop_height_ratio,
            scale,
            scale_method,
            scale_ratio,
            scale_width,
            scale_height,
            compress,
            rotate,
            output_type,
        )
    )

    image_folder = static_file_server.static_folder_path / "images"

    outputs = []
    for index, current_input_image in enumerate(input_images):
        current_input_image = extract_image_url(current_input_image)
        image_processor = ImageProcessor(current_input_image, max_size=None)
        current_crop = crops[index]
        current_crop_method = crop_methods[index]
        current_crop_position = crop_positions[index]
        current_crop_x = crop_xs[index]
        current_crop_y = crop_ys[index]
        current_crop_width = crop_widths[index]
        current_crop_height = crop_heights[index]
        current_crop_width_ratio = crop_width_ratios[index]
        current_crop_height_ratio = crop_height_ratios[index]
        current_scale = scales[index]
        current_scale_method = scale_methods[index]
        current_scale_ratio = scale_ratios[index]
        current_scale_width = scale_widths[index]
        current_scale_height = scale_heights[index]
        current_compress = compresss[index]
        current_rotate = rotates[index]
        current_output_type = output_types[index]

        if current_crop:
            image_processor.crop(
                method=current_crop_method,
                width_ratio=current_crop_width_ratio,
                height_ratio=current_crop_height_ratio,
                position=current_crop_position,
                x=current_crop_x,
                y=current_crop_y,
                width=current_crop_width,
                height=current_crop_height,
            )

        if current_scale:
            image_processor.scale(
                method=current_scale_method,
                ratio=current_scale_ratio,
                width=current_scale_width,
                height=current_scale_height,
            )

        if current_compress < 100:
            image_processor.compress(quality=current_compress)

        if current_rotate > 0:
            image_processor.rotate(angle=current_rotate)

        mime_type = image_processor.mime_type
        extension = mime_type.split("/")[1].lower()
        image_name = f"{uuid.uuid4().hex}.{extension}"
        local_file = image_folder / image_name
        with open(local_file, "wb") as file:
            file.write(image_processor.bytes)

        image_url = static_file_server.get_file_url(f"images/{image_name}")

        if current_output_type == "only_link":
            outputs.append(image_url)
        elif current_output_type == "markdown":
            outputs.append(f"![{image_url}]({image_url})")
        elif current_output_type == "html":
            outputs.append(f'<img src="{image_url}"/>')

    output = outputs[0] if not has_list else outputs
    workflow.update_node_field_value(node_id, "output", output)
    return workflow.data


@task
@timer
def image_watermark(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)

    input_image = workflow.get_node_field_value(node_id, "input_image")
    image_or_text = workflow.get_node_field_value(node_id, "image_or_text")
    watermark_image = workflow.get_node_field_value(node_id, "watermark_image")
    watermark_image_width_ratio = workflow.get_node_field_value(node_id, "watermark_image_width_ratio")
    watermark_image_height_ratio = workflow.get_node_field_value(node_id, "watermark_image_height_ratio")
    watermark_text = workflow.get_node_field_value(node_id, "watermark_text")
    watermark_text_font = workflow.get_node_field_value(node_id, "watermark_text_font")
    watermark_text_font_size = workflow.get_node_field_value(node_id, "watermark_text_font_size")
    watermark_text_font_color = workflow.get_node_field_value(node_id, "watermark_text_font_color")
    opacity = workflow.get_node_field_value(node_id, "opacity")
    position = workflow.get_node_field_value(node_id, "position")
    vertical_gap = workflow.get_node_field_value(node_id, "vertical_gap")
    horizontal_gap = workflow.get_node_field_value(node_id, "horizontal_gap")
    output_type = workflow.get_node_field_value(node_id, "output_type")

    input_image = input_image[0] if len(input_image) == 1 else input_image
    if isinstance(watermark_image, list):
        if len(watermark_image) == 0:
            watermark_image = None
        else:
            watermark_image = watermark_image[0] if len(watermark_image) == 1 else watermark_image
    if isinstance(watermark_text_font, list):
        if len(watermark_text_font) == 0:
            watermark_text_font = None
        else:
            watermark_text_font = watermark_text_font[0] if len(watermark_text_font) == 1 else watermark_text_font

    (
        has_list,
        (
            input_images,
            image_or_texts,
            watermark_images,
            watermark_image_width_ratios,
            watermark_image_height_ratios,
            watermark_texts,
            watermark_text_fonts,
            watermark_text_font_sizes,
            watermark_text_font_colors,
            opacitys,
            positions,
            vertical_gaps,
            horizontal_gaps,
            output_types,
        ),
    ) = align_elements(
        (
            input_image,
            image_or_text,
            watermark_image,
            watermark_image_width_ratio,
            watermark_image_height_ratio,
            watermark_text,
            watermark_text_font,
            watermark_text_font_size,
            watermark_text_font_color,
            opacity,
            position,
            vertical_gap,
            horizontal_gap,
            output_type,
        )
    )

    outputs = []
    image_folder = static_file_server.static_folder_path / "images"
    for index, image in enumerate(input_images):
        image = extract_image_url(image)
        image_processor = ImageProcessor(image, max_size=None)
        current_image_or_text = image_or_texts[index]
        if current_image_or_text == "image":
            watermark_images[index] = extract_image_url(watermark_images[index])
            watermark_image_processor = ImageProcessor(watermark_images[index], max_size=None)
            image_processor.add_image_watermark(
                watermark_image=watermark_image_processor.image,
                width_ratio=watermark_image_width_ratios[index],
                height_ratio=watermark_image_height_ratios[index],
                opacity=opacitys[index],
                position=positions[index],
                vertical_gap=vertical_gaps[index],
                horizontal_gap=horizontal_gaps[index],
            )
        elif current_image_or_text == "text":
            image_processor.add_text_watermark(
                watermark_text=watermark_texts[index],
                watermark_text_font=watermark_text_fonts[index],
                watermark_text_font_size=watermark_text_font_sizes[index],
                watermark_text_font_color=watermark_text_font_colors[index],
                opacity=opacitys[index],
                position=positions[index],
                vertical_gap=vertical_gaps[index],
                horizontal_gap=horizontal_gaps[index],
            )

        mime_type = image_processor.mime_type
        extension = mime_type.split("/")[1].lower()
        image_name = f"{uuid.uuid4().hex}.{extension}"
        local_file = image_folder / image_name
        with open(local_file, "wb") as file:
            file.write(image_processor.bytes)

        image_url = static_file_server.get_file_url(f"images/{image_name}")

        current_output_type = output_types[index]
        if current_output_type == "only_link":
            outputs.append(image_url)
        elif current_output_type == "markdown":
            outputs.append(f"![{image_url}]({image_url})")
        elif current_output_type == "html":
            outputs.append(f'<img src="{image_url}"/>')

    output = outputs[0] if not has_list else outputs
    workflow.update_node_field_value(node_id, "output", output)
    return workflow.data
