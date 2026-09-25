"""Task 1 - Collect and validate the legal source documents."""

from __future__ import annotations

from pathlib import Path


DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "legal"
SOURCE_PAGE = (
    "https://www.baovietnhantho.com.vn/san-pham/dau-tu/"
    "an-khang-hanh-phuc"
)

# The product page publishes the policy documents in a RAR archive. They were
# downloaded and extracted manually because Python cannot portably extract RAR
# files without an external binary. Keeping this manifest makes the collection
# step deterministic and lets us detect missing or damaged inputs early.
REQUIRED_DOCUMENTS = (
    "DK CUVL02 - AN KHANG HANH PHUC - CAO CAP_10 09 2024.pdf",
    "DK CUVL03 - AN KHANG HANH PHUC - NANG CAO_10 09 2024.pdf",
    "DK CUVL05 - AN KHANG HANH PHUC - CO BAN_04 09 2024.pdf",
)


def setup_directory() -> None:
    """Create the directory used for original legal documents."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def validate_pdf(path: Path) -> None:
    """Raise a clear error when a collected file is not a usable PDF."""
    if path.stat().st_size < 1_024:
        raise ValueError(f"Document is unexpectedly small: {path}")
    with path.open("rb") as stream:
        if stream.read(5) != b"%PDF-":
            raise ValueError(f"Document does not have a PDF signature: {path}")


def download_documents() -> list[Path]:
    """Return the manually collected documents after validating the corpus.

    Bao Viet distributes these files inside a RAR archive on ``SOURCE_PAGE``.
    The repository therefore stores the extracted originals directly instead
    of downloading and unpacking the archive on every run.
    """
    missing = [name for name in REQUIRED_DOCUMENTS if not (DATA_DIR / name).is_file()]
    if missing:
        names = "\n".join(f"  - {name}" for name in missing)
        raise FileNotFoundError(
            "Missing legal documents:\n"
            f"{names}\n"
            f"Download the policy archive from {SOURCE_PAGE}, extract it, "
            f"and place the PDFs in {DATA_DIR}."
        )

    documents = [DATA_DIR / name for name in REQUIRED_DOCUMENTS]
    for document in documents:
        validate_pdf(document)
        print(f"Ready: {document.name} ({document.stat().st_size:,} bytes)")
    return documents


def main() -> None:
    setup_directory()
    documents = download_documents()
    print(f"Validated {len(documents)} legal documents from {SOURCE_PAGE}")


if __name__ == "__main__":
    main()
