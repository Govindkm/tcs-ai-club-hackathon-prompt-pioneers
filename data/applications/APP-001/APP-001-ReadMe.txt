Text Extraction 

=============================

from google.colab import files
from src.ingestion.document_reader import extract_text

uploaded = files.upload()
filename = next(iter(uploaded))

text = extract_text(filename, uploaded[filename])
print(text)

===========================

Files:

1) PDF => Done
2) Image => Done (2 and more minutes to process)
3) Docx => Done
4) XLSX => Done
5) PPTX => Done
