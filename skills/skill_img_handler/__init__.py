"""
专业图片处理助手（内嵌大模型API）
提供图片识别、生成、编辑、转换等专业功能
"""

from .tools import (
    recognize_image,
    batch_recognize_images,
    generate_image,
    generate_multiple_images,
    edit_image,
    remove_background,
    enhance_image,
    convert_format,
    resize_image,
    batch_process,
    extract_text_ocr,
    extract_text_from_multiple_images,
    detect_text_regions,
    analyze_image_quality,
    compare_images
)

__all__ = [
    'recognize_image',
    'batch_recognize_images',
    'generate_image',
    'generate_multiple_images',
    'edit_image',
    'remove_background',
    'enhance_image',
    'convert_format',
    'resize_image',
    'batch_process',
    'extract_text_ocr',
    'extract_text_from_multiple_images',
    'detect_text_regions',
    'analyze_image_quality',
    'compare_images'
]
