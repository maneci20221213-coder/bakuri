"""One outcome boundary for conversion, compression and cooperative cancellation."""

from typing import Callable
from pathlib import Path
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
    first = (
        request.file if isinstance(request, PdfPagesRequest) else next(iter(request.files), None)
    )
    if first is None:
        return _execute(request, control)
    location = (
        request.options.location if isinstance(request, ConversionRequest) else request.location
    )
    with control.save_to(location, Path(first.path).resolve().parent):
        _execute(request, control)
    return list(control.outputs)


def _execute(request: Request, control: JobControl):
    """Lazy imports keep engine libraries out of capability checks and UI setup."""
    if isinstance(request, PdfPagesRequest):
        from bakuri.conversion.pdf_split import split_pdf

        source = Path(request.file.path)
        args = request.mode, request.every, request.selection, request.separate, control
        if source.suffix.lower() == ".pdf":
            return split_pdf(source, *args)

        from bakuri.conversion.office_split import split_office

        return split_office(source, *args)
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
            control=control,
            **request.options.as_kwargs(include_location=False),
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
