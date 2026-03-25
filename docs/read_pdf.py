import sys

def extract_text(pdf_path):
    try:
        import PyPDF2
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ""
            for page_num in range(len(reader.pages)):
                text += f"\n--- Page {page_num + 1} ---\n"
                text += reader.pages[page_num].extract_text()
            return text
    except ImportError:
        return "PyPDF2 is not installed."
    except Exception as e:
        return f"Error reading PDF: {e}"

if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open("pdf_content.txt", "w", encoding="utf-8") as out_file:
            for path in sys.argv[1:]:
                out_file.write(f"\n==================== {path} ====================\n")
                out_file.write(extract_text(path))
        print("Successfully wrote to pdf_content.txt")
    else:
        print("Please provide PDF paths.")
