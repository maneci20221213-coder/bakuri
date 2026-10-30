"""One outcome boundary for conversion, compression and cooperative cancellation."""

from typing import Callable
from .control import JobControl, Cancelled
from bakuri.domain.models import (
    ConversionRequest,
    CompressionRequest,
    CompressionRow,
    JobKind,
    JobOutcome,
    JobReport,
)

Request = ConversionRequest | CompressionRequest
Operation = Callable[[JobControl], object]


def execute(request: Request, control: JobControl):
    """Lazy imports keep engine libraries out of capability checks and UI setup."""
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
    )
