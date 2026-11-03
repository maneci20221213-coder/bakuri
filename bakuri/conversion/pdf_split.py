"""Copy selected PDF pages without rasterizing text or recompressing images."""

from pathlib import Path
import tempfile
import fitz
from bakuri.application.control import JobControl
from bakuri.domain.pdf_selection import page_groups


def pdf_page_count(path):
    with fitz.open(path) as document:
        if not document.is_pdf:
            raise ValueError("PDF 파일을 선택해 주세요.")
        if document.needs_pass:
            raise ValueError("암호가 있는 PDF입니다. 암호를 해제한 복사본을 사용해 주세요.")
        if not len(document):
            raise ValueError("페이지가 없는 PDF입니다.")
        return len(document)


def split_pdf(source, mode="interval", every=1, selection="", separate=False, control=None):
    source = Path(source).resolve()
    control = control or JobControl()
    control.check()
    pdf_page_count(source)
    with fitz.open(source) as original, tempfile.TemporaryDirectory() as directory:
        if original.needs_pass:
            raise ValueError("암호를 해제한 PDF 복사본을 사용해 주세요.")
        groups = page_groups(len(original), mode, every, selection, separate)
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
                    control.update(90 * copied / total, f"PDF 페이지 복사 · {copied}/{total}쪽")
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
                for level, title, page in original.get_toc():
                    if page - 1 in mapping:
                        level = min(level, toc[-1][0] + 1 if toc else 1)
                        toc.append([level, title, mapping[page - 1] + 1])
                if toc:
                    output.set_toc(toc)
                output.set_metadata(
                    {
                        key: value
                        for key, value in original.metadata.items()
                        if key not in {"format", "encryption"}
                    }
                )
                temp = Path(directory) / "pages.pdf"
                control.check()
                output.save(temp, garbage=4, deflate=True)
            width = max(3, len(str(len(original))))
            if mode == "extract" and not separate:
                name = f"{source.stem}_추출본.pdf"
            else:
                first, last = group[0] + 1, group[-1] + 1
                label = (
                    f"{first:0{width}}" if first == last else f"{first:0{width}}-{last:0{width}}"
                )
                name = f"{source.stem}_{label}쪽.pdf"
            control.publish(temp, source.with_name(name))
    control.complete()
    return list(control.outputs)
