from pypdf import PdfReader
from docx import Document


def extract_text(file_path, extension):

    pages = []

    if extension == ".pdf":

        reader = PdfReader(file_path)

        for number, page in enumerate(reader.pages):

            text = page.extract_text() or ""

            if text.strip():

                pages.append({
                    "page": number + 1,
                    "text": text
                })


    elif extension == ".docx":

        document = Document(file_path)

        text = "\n".join(
            paragraph.text
            for paragraph in document.paragraphs
        )

        if text.strip():

            pages.append({
                "page": 1,
                "text": text
            })


    elif extension == ".txt":

        with open(
            file_path,
            "r",
            encoding="utf-8"
        ) as file:

            text = file.read()

        if text.strip():

            pages.append({
                "page": 1,
                "text": text
            })


    return pages


def split_text(text, chunk_size=500):

    words = text.split()

    chunks = []

    for i in range(
        0,
        len(words),
        chunk_size
    ):

        chunk = " ".join(
            words[i:i + chunk_size]
        )

        if chunk.strip():

            chunks.append(chunk)

    return chunks