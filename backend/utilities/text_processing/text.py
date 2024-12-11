# @Author: Bi Ying
# @Date:   2024-04-01 19:16:42
import re
import io
import csv
from typing import List, Union, overload, Literal, TypedDict

from markdownify import MarkdownConverter, chomp
from langchain_text_splitters import (
    TokenTextSplitter,
    MarkdownTextSplitter,
)

from utilities.file_processing import static_file_server


url_pattern = re.compile(r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+")
email_pattern = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")

markdown_image_pattern = re.compile(r"!\[.*\]\(.*\)")
markdown_image_url_pattern = re.compile(r"!\[.*?\]\((.*?)\)")

local_image_re = re.compile(r"http://localhost:\d+/images/(.*)")


def contains_chinese(text):
    return re.search("[\u4e00-\u9fff]", text) is not None


def remove_url_and_email(text: str):
    text = url_pattern.sub("", text)
    return email_pattern.sub("", text)


def remove_markdown_image(text: str, max_length: int = 300):
    def replace_func(match):
        # 如果匹配到的图片链接文本长度超过max_length，则替换
        if len(match.group(0)) > max_length:
            return "![]()"
        else:
            # 如果不超过，则返回原文本
            return match.group(0)

    # 使用sub函数的repl参数传入一个替换函数
    return markdown_image_pattern.sub(replace_func, text)


def replace_local_image_url(url: str):
    image_folder = static_file_server.static_folder_path / "images"
    match = local_image_re.match(url)
    if match:
        image_path = image_folder / match.group(1)
        if image_path.exists():
            return str(image_path)
        else:
            return url
    else:
        return url


def extract_image_url(text: str):
    # 如果已经是正常的图片链接，则直接返回
    if url_pattern.match(text):
        return replace_local_image_url(text)
    else:
        # 否则匹配markdown图片链接，返回第一个匹配到的图片链接
        match = markdown_image_url_pattern.search(text)
        if match:
            # 返回Markdown里的链接
            return replace_local_image_url(match.group(1))
        else:
            return replace_local_image_url(text)


class ParagraphInfo(TypedDict):
    index: int
    text: str
    word_counts: int


@overload
def split_text(text: str, rules: dict, flat: Literal[False]) -> List[ParagraphInfo]: ...


@overload
def split_text(text: str, rules: dict, flat: Literal[True]) -> List[str]: ...


@overload
def split_text(text: str, rules: dict, flat: bool = False) -> Union[List[ParagraphInfo], List[str]]: ...


def split_text(text: str, rules: dict, flat: bool = False) -> Union[List[ParagraphInfo], List[str]]:
    split_method = rules.get("split_method", "general")
    chunk_length = rules.get("chunk_length", 1000)
    chunk_overlap = rules.get("chunk_overlap", 30)
    model_name = rules.get("model_name", "gpt-3.5-turbo")
    delimiter = rules.get("delimiter", "\n")
    need_remove_url_and_email = rules.get("remove_url_and_email", False)

    if need_remove_url_and_email:
        text = remove_url_and_email(text)

    if split_method == "general":
        text_splitter = TokenTextSplitter(
            chunk_size=chunk_length,
            chunk_overlap=chunk_overlap,
            model_name=model_name,
        )
        paragraphs = [paragraph.page_content for paragraph in text_splitter.create_documents([text])]
    elif split_method == "delimiter":
        delimiter = delimiter.encode().decode("unicode_escape").encode("latin1").decode("utf-8")
        paragraphs = re.split(delimiter, text)
    elif split_method == "markdown":
        text_splitter = MarkdownTextSplitter(chunk_size=chunk_length, chunk_overlap=chunk_overlap)
        paragraphs = [paragraph.page_content for paragraph in text_splitter.create_documents([text])]
    elif split_method == "table":
        reader = csv.DictReader(io.StringIO(text))
        paragraphs = []
        for row in reader:
            paragraphs.append("\n".join([f"{key}: {value}" for key, value in row.items()]))
    else:
        raise ValueError(f"Invalid split_method: {split_method}")

    if flat:
        return paragraphs
    else:
        return [
            {"index": index, "text": paragraph, "word_counts": len(paragraph)}
            for index, paragraph in enumerate(paragraphs)
        ]


class CustomMarkdownConverter(MarkdownConverter):
    def convert_b(self, el, text, convert_as_inline):
        return self.custom_bold_conversion(el, text, convert_as_inline)

    convert_strong = convert_b

    def custom_bold_conversion(self, el, text, convert_as_inline):
        markup = 2 * self.options["strong_em_symbol"]
        prefix, suffix, text = chomp(text)
        if not text:
            return ""
        return "%s%s%s%s%s " % (prefix, markup, text, markup, suffix)


def markdownify(html, **options):
    return CustomMarkdownConverter(**options).convert(html)


def clean_markdown(text: str):
    content = "\n\n".join([s.strip() for s in text.split("\n") if s.strip()])
    content = content.replace("![]()", "").replace("*\n", "")
    content = "\n\n".join([s.strip() for s in content.split("\n") if s.strip()])
    return content
