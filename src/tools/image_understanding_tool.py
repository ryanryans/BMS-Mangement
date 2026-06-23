"""Image understanding tool — mock implementation for development.

In production, this would use VLM (Vision Language Model) or OCR services.
For now, provides deterministic mock descriptions based on filename and metadata.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from src.core.settings import get_settings

logger = logging.getLogger(__name__)


class ImageUnderstandingTool:
    """Provides image understanding capabilities.

    Current version (mock):
    - Reads image metadata (filename, size)
    - Generates mock descriptions based on filename patterns
    - Can be replaced with real VLM/OCR later

    Future: replace with OpenAI Vision, GPT-4V, or local VLM.
    """

    def __init__(self, images_dir: Path | None = None):
        settings = get_settings()
        self._images_dir = images_dir or settings.uploaded_images_dir

    def understand(self, query: str, image_path: str | None = None) -> str:
        """Generate an understanding of an image."""
        if not image_path:
            image_path = self._find_image_file()
            if not image_path:
                return "未找到可分析的图片文件。请上传图片文件（PNG/JPG）到系统。"

        try:
            metadata = self._get_image_metadata(image_path)
            description = self._generate_mock_description(image_path, metadata)
            return self._format_response(description, metadata, query)
        except Exception as e:
            logger.error("Image understanding failed for %s: %s", image_path, e)
            return f"图片分析失败: {e}"

    def _find_image_file(self) -> str | None:
        """Find an image file in the images directory."""
        for ext in [".png", ".jpg", ".jpeg", ".gif", ".bmp"]:
            for path in self._images_dir.rglob(f"*{ext}"):
                if path.is_file():
                    return str(path)
        return None

    def _get_image_metadata(self, image_path: str) -> dict[str, Any]:
        """Extract basic image metadata."""
        path = Path(image_path)
        metadata = {
            "filename": path.name,
            "extension": path.suffix.lower(),
            "size_bytes": path.stat().st_size if path.exists() else 0,
            "file_path": str(path),
        }

        # Try to get image dimensions if PIL is available
        try:
            from PIL import Image
            with Image.open(image_path) as img:
                metadata["width"] = img.width
                metadata["height"] = img.height
                metadata["mode"] = img.mode
                metadata["format"] = img.format
        except ImportError:
            metadata["width"] = "unknown"
            metadata["height"] = "unknown"
            metadata["note"] = "PIL not installed for dimension extraction"
        except Exception as e:
            metadata["error"] = str(e)

        return metadata

    def _generate_mock_description(self, image_path: str,
                                    metadata: dict) -> dict[str, str]:
        """Generate a mock description based on filename patterns."""
        filename = metadata.get("filename", "").lower()

        # Detect content type from filename
        patterns = {
            "电池": "这是一张电池相关的图片。可能包含电池外观、规格参数或测试场景。",
            "测试": "这是一张测试相关的图片。可能展示测试设备、测试流程或测试结果。",
            "图表": "这是一张数据图表。可能展示趋势线、统计数据或对比分析。",
            "流程图": "这是一张流程图。可能描述工艺流程、系统架构或决策逻辑。",
            "架构": "这是一张系统架构图。可能展示组件关系、数据流或部署拓扑。",
            "产品": "这是一张产品图片。可能包含产品外观、规格说明或使用场景。",
            "电路": "这是一张电路图或PCB设计图。可能包含元器件布局、走线或原理图。",
            "示意图": "这是一张示意图。用于说明某个概念、结构或流程。",
        }

        description = ""
        for keyword, desc in patterns.items():
            if keyword in filename or keyword in image_path.lower():
                description = desc
                break

        if not description:
            description = f"图片文件 '{metadata['filename']}'。建议查看原文件获取详细内容。"

        return {
            "description": description,
            "mock": "true",
            "note": "当前使用mock描述。接入VLM后可获得更准确的图片理解。",
        }

    def _format_response(self, description: dict, metadata: dict,
                         query: str) -> str:
        """Format the image understanding response."""
        dims = f"{metadata.get('width', '?')}x{metadata.get('height', '?')}"
        size_kb = metadata.get("size_bytes", 0) / 1024

        lines = [
            "## 图片理解结果",
            "",
            f"**文件**: {metadata['filename']}",
            f"**格式**: {metadata.get('format', metadata.get('extension', 'unknown'))}",
            f"**尺寸**: {dims}",
            f"**文件大小**: {size_kb:.1f} KB",
            "",
            "### 内容描述",
            "",
            description["description"],
        ]

        if description.get("mock") == "true":
            lines.extend([
                "",
                "> ⚠️ **注意**: 当前使用mock描述模式。如需准确的图片内容分析，请配置VLM服务。",
            ])

        return "\n".join(lines)
