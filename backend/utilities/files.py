# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-15 11:17:29
# @Last Modified by:   Bi Ying
# @Last Modified time: 2023-05-17 19:55:01
import json
import shutil
from pathlib import Path

import pypdf
import mammoth
import openpyxl
from pptx import Presentation

from utilities.print_utils import mprint_error


def try_load_json_file(file_path: str, default=dict):
    if Path(file_path).exists():
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            mprint_error(f"Failed to load json file: {file_path}, {e}")
    return default()


def get_files_contents(files: list):
    results = []
    for file in files:
        if file.endswith(".docx"):
            with open(file, "rb") as docx_file:
                docx_data = mammoth.convert_to_markdown(docx_file)
                markdown_text = docx_data.value
                results.append(markdown_text)
        elif file.endswith(".pdf"):
            with open(file, "rb") as pdf_file_obj:
                pdf_reader = pypdf.PdfReader(pdf_file_obj)
                pdf_contents = [page.extract_text() for page in pdf_reader.pages]
                results.append("\n\n".join(pdf_contents))
        elif file.endswith(".pptx"):
            ppt = Presentation(file)
            ppt_contents = []
            for slide in ppt.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text:
                        ppt_contents.append(shape.text.strip())
            results.append("\n\n".join(ppt_contents))
        elif file.endswith(".xlsx"):
            wb = openpyxl.load_workbook(file, data_only=True)
            ws = wb.active
            csv_contents = []
            for row in ws.rows:
                csv_contents.append(",".join([str(cell.value) if cell.value else "" for cell in row]))
            results.append("\n\n".join(csv_contents))
        elif file.endswith((".txt", ".md", ".html", ".json", ".csv")):
            with open(file, "r", encoding="utf-8-sig") as txt_file:
                txt_contents = txt_file.read()
                results.append(txt_contents)

    return results


def copy_file(src, dst):
    if Path(src).exists():
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dst)
        return True
    return False
