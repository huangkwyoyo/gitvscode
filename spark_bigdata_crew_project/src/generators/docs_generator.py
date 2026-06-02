"""
文档生成器
汇总全流程产出，生成标准化交付文档与版本记录。
"""
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class DocsGenerator:
    """标准化交付文档生成器"""

    def generate_delivery_package(
        self,
        run_id: str,
        artifacts: dict,
        output_dir: str = "output/docs",
    ) -> str:
        """
        生成完整交付文档包。

        Args:
            run_id: 运行标识
            artifacts: 各阶段产出物字典 {stage_name: content}
            output_dir: 输出目录

        Returns:
            交付文档路径
        """
        out_path = Path(output_dir) / f"{run_id}_delivery.md"
        out_path.parent.mkdir(parents=True, exist_ok=True)

        sections = [
            f"# Spark大数据项目交付文档\n",
            f"**运行ID**: {run_id}",
            f"**生成时间**: {datetime.now().isoformat()}",
            f"**版本**: 2.0.0\n",
            "---\n",
        ]

        for stage, content in artifacts.items():
            sections.append(f"## {stage}\n")
            sections.append(str(content)[:5000])
            sections.append("\n---\n")

        doc_content = "\n".join(sections)
        out_path.write_text(doc_content, encoding="utf-8")
        logger.info("交付文档已生成: %s", out_path)
        return str(out_path)
