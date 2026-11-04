"""Copy selected PDF pages without rasterizing text or recompressing images."""

from pathlib import Path
import tempfile
import fitz
from bakuri.application.control import JobControl
from bakuri.domain.pdf_selection import page_groups, page_output_path


def pdf_page_count(path):
    with fitz.open(path) as document:
        return _page_count(document)


def _page_count(document):
    if not document.is_pdf:
        raise ValueError("PDF 파일을 선택해 주세요.")
    if document.needs_pass:
        raise ValueError("암호가 있는 PDF입니다. 암호를 해제한 복사본을 사용해 주세요.")
    if not len(document):
        raise ValueError("페이지가 없는 PDF입니다.")
    return len(document)


def split_pdf(
    source,
    mode="interval",
    every=1,
    selection="",
    separate=False,
    control=None,
):
    source = Path(source).resolve()
    control = control or JobControl()
    control.check()
    with fitz.open(source) as original, tempfile.TemporaryDirectory() as directory:
        groups = page_groups(_page_count(original), mode, every, selection, separate)
        bookmarks = original.get_toc()
        metadata = {
            key: value
            for key, value in original.metadata.items()
            if key not in {"format", "encryption"}
        }
        start_percent = control.percent
        total = sum(map(len, groups))
        copied = 0
        for group in groups:
            control.check()
            with fitz.open() as output:
                mapping = {page: index for index, page in enumerate(group)}
                for index, page in enumerate(group):
                    control.check()
                    output.insert_pdf(
                        original,
                        from_page=page,
                        to_page=page,
                        links=False,
                        final=int(index == len(group) - 1),
                    )
                    copied += 1
                    control.update(
                        start_percent + (98 - start_percent) * copied / total,
                        f"PDF 페이지 복사 · {copied}/{total}쪽",
                    )
                # Remap links after all selected pages exist, including links across
                # disjoint input ranges. Omit destinations outside this new document.
                for page, index in mapping.items():
                    control.check()
                    for link in original[page].get_links():
                        link = {
                            key: value for key, value in link.items() if key not in {"xref", "id"}
                        }
                        if "from" in link:
                            link["from"] = link["from"] * original[page].derotation_matrix
                        if link["kind"] == fitz.LINK_GOTO:
                            if link.get("page") not in mapping:
                                continue
                            if isinstance(link.get("to"), fitz.Point):
                                link["to"] = link["to"] * original[link["page"]].derotation_matrix
                            link["page"] = mapping[link["page"]]
                        if link["kind"] != fitz.LINK_NONE:
                            output[index].insert_link(link)
                toc = []
                for level, title, page in bookmarks:
                    if page - 1 in mapping:
                        level = min(level, toc[-1][0] + 1 if toc else 1)
                        toc.append([level, title, mapping[page - 1] + 1])
                if toc:
                    output.set_toc(toc)
                output.set_metadata(metadata)
                temp = Path(directory) / "pages.pdf"
                control.check()
                output.save(
                    temp,
                    garbage=4,
                    deflate=True,
                    deflate_images=True,
                    deflate_fonts=True,
                    use_objstms=1,
                )
            destination = page_output_path(
                source, len(original), group, mode == "extract" and not separate
            )
            control.publish(temp, destination)
    control.complete()
    return list(control.outputs)
