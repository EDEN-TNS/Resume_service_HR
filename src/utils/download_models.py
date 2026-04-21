from pathlib import Path

from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.utils import model_downloader

# Example string path
path_str = "/artifacts"

# Convert string to Path object
path_obj = Path(path_str)


# model_downloader.download_models(output_dir=path_obj)
model_downloader.download_models()


# artifacts_path = "/artifacts"
# pipeline_options = PdfPipelineOptions(artifacts_path=artifacts_path)
pipeline_options = PdfPipelineOptions()
converter = DocumentConverter(
    format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
)

# Downloads into Docling’s cache as well

pipeline_options = PdfPipelineOptions()
pipeline_options.ocr_options.lang = ["ko", "en"]
pipeline_options.do_table_structure = True
pipeline_options.table_structure_options.do_cell_matching = True
pipeline_options.accelerator_options = AcceleratorOptions(
    num_threads=4, device=AcceleratorDevice.AUTO
)

# ✅ OCR
pipeline_options.do_ocr = True
# Cut the Picture element in the document and create it as an image
pipeline_options.generate_picture_images = True  # 그림/도표를 개별 이미지로 저장
pipeline_options.generate_page_images = False  # 페이지 전체 이미지는 필요 시 True
pipeline_options.images_scale = 2.0  # 해상도 배율 (기본 1.0)

doc_converter = DocumentConverter(
    format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
)

result = doc_converter.convert("test.pdf")
print(result.document.export_to_markdown())
