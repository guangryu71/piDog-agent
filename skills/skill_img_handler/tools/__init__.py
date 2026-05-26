"""
图片处理工具集 - 提供完整的图片操作能力

统一入口:
    from tools.image_handler import ImageHandler as Ih
    Ih.recognize("photo.jpg", "里面有什么？")
    Ih.generate("一只可爱的小猫")

各功能仍可作为独立函数导入（向后兼容）:
    from tools.image_handler import recognize_image, generate_image, ...
"""

from .image_handler import (
    # 统一调度入口
    process,
    list_operations,
    # 识别
    recognize_image,
    batch_recognize_images,
    # 生成
    generate_image,
    generate_multiple_images,
    # 图生图
    img2img,
    # 编辑
    edit_image,
    remove_background,
    enhance_image,
    # 转换
    convert_format,
    resize_image,
    batch_process,
    # OCR
    extract_text_ocr,
    extract_text_from_multiple_images,
    detect_text_regions,
    # 分析
    analyze_image_quality,
    compare_images,
    # 统一入口类
    ImageHandler,
)

__all__ = [
    # 统一入口
    'ImageHandler',
    'process',
    'list_operations',

    # 识别
    'recognize_image',
    'batch_recognize_images',

    # 生成
    'generate_image',
    'generate_multiple_images',

    # 图生图
    'img2img',

    # 编辑
    'edit_image',
    'remove_background',
    'enhance_image',

    # 转换
    'convert_format',
    'resize_image',
    'batch_process',

    # OCR
    'extract_text_ocr',
    'extract_text_from_multiple_images',
    'detect_text_regions',

    # 分析
    'analyze_image_quality',
    'compare_images',
]
