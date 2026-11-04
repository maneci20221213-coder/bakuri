"""One outcome boundary for conversion, compression and cooperative cancellation."""

from typing import Callable
from .control import JobControl, Cancelled
from bakuri.domain.models import (
    ConversionRequest,
    CompressionRequest,
    PdfPagesRequest,
    CompressionRow,
    JobKind,
    JobOutcome,
    JobReport,
)

Request = ConversionRequest | CompressionRequest | PdfPagesRequest
Operation = Callable[[JobControl], object]


def execute(request: Request, control: JobControl):
    """Lazy imports keep engine libraries out of capability checks and UI setup."""
    if isinstance(request, PdfPagesRequest):
        from bakuri.conversion.pdf_split import split_pdf

        from pathlib import Path

        source = Path(request.file.path)
        args = request.mode, request.every, request.selection, request.separate, control
        if source.suffix.lower() == ".pdf":
            return split_pdf(source, *args)

        from tempfile import TemporaryDirectory
        from bakuri.domain.formats import PAGE_SPLIT_INPUTS
        from bakuri.conversion.office import OfficeSession

        if source.suffix.lower() not in PAGE_SPLIT_INPUTS:
            raise ValueError("PDF, 한글 또는 Word 문서를 선택해 주세요.")
        control.update(0, "문서에서 PDF 페이지 준비 중")
        with TemporaryDirectory() as directory:
            pdf = Path(directory) / "document.pdf"
            with OfficeSession() as session:
                session.control = control
                session.export(source, pdf, "pdf")
            control.update(20, "PDF 페이지 준비 완료")
            return split_pdf(pdf, *args, output_source=source)
    from bakuri.conversion.multi_image import resolve_selections, process_selected_images

    selections = resolve_selections(request.files, request.multi_images)
    if selections:
        return process_selected_images(request, selections, control)
    paths = tuple(item.path for item in request.files)
    if isinstance(request, ConversionRequest):
        from bakuri.conversion.service import convert

        return convert(
            paths,
            request.output.value,
            request.merge,
            dpi=request.options.dpi,
            image_mode=request.options.image_mode,
            control=control,
        )
    if isinstance(request, CompressionRequest):
        from bakuri.compression.service import compress

        return compress(paths, control=control, **request.options.as_kwargs())
    raise TypeError("Unknown job request")


def run_job(
    operation: Request | Operation,
    control: JobControl,
    kind: JobKind | str,
    error_message: Callable[[Exception, str], str],
) -> JobReport:
    kind = JobKind(kind)
    outcome = JobOutcome.DONE
    error = ""
    try:
        if callable(operation):
            operation(control)
        else:
            execute(operation, control)
    except Cancelled:
        outcome = JobOutcome.CANCELLED
    except Exception as exc:
        outcome = JobOutcome.FAILED
        error = error_message(exc, "compression" if kind == JobKind.COMPRESS else "conversion")
    return JobReport(
        kind,
        outcome,
        tuple(control.outputs),
        tuple(CompressionRow(**row) for row in control.rows),
        error,
        tuple(control.notes),
    )
