import sys
try:
    import pypdf
except ImportError:
    pass

reader = pypdf.PdfReader(sys.argv[1])
text = ""
for page in reader.pages:
    text += page.extract_text() + "\n"
with open("C:\\Users\\soura\\OneDrive\\Desktop\\My Apps\\Overlay Cutex\\Overlay\\personas.txt", "w", encoding="utf-8") as f:
    f.write(text)
print("Done extracting to personas.txt")
