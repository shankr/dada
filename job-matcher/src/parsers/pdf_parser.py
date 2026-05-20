import pdfplumber
import re


class PDFParser:
    def __init__(self, file_path):
        self.file_path = file_path

    def parse(self):
        if not __import__("os").path.exists(self.file_path):
            raise FileNotFoundError(f"Resume file not found: {self.file_path}")

        text_parts = []
        num_pages = 0
        with pdfplumber.open(self.file_path) as pdf:
            num_pages = len(pdf.pages)
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)

        return {
            "text": "\n".join(text_parts),
            "numpages": num_pages,
        }

    def extract_resume_data(self):
        parsed = self.parse()
        return {
            "rawText": parsed["text"],
            "numPages": parsed["numpages"],
            "cleanText": self._clean_text(parsed["text"]),
        }

    @staticmethod
    def _clean_text(text):
        return re.sub(r"\n\n+", "\n", re.sub(r"\t", " ", re.sub(r" +", " ", text))).strip()
