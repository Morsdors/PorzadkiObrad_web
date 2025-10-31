import os
import re
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin
import json
import PyPDF2
from docx import Document
import tempfile

# Base configuration
DEF_URL = "https://bip.pila.pl/2025.html"
BASE_SAVE_DIR = r"C:\Users\PC\Desktop\SesjeRady"

# OpenRouter AI configuration
OPENROUTER_API_KEY = "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"
OPENROUTER_MODEL = "nvidia/nemotron-nano-9b-v2:free"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

# Ensure directories exist
Path(BASE_SAVE_DIR).mkdir(parents=True, exist_ok=True)



HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/139.0.0.0 Safari/537.36"
}




def get_latest_sesja_url():
    """Find the latest Sesja Rady Miasta link and its number."""
    resp = requests.get(DEF_URL, headers=HEADERS)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # look for Sesja Rady Miasta links
    sesja_links = soup.find_all("a", href=True, text=re.compile(r"Sesja Rady Miasta Piły", re.I))
    if not sesja_links:
        raise RuntimeError("Nie znaleziono żadnej sesji!")

    latest = sesja_links[0]  # assume first is the latest
    sesja_text = latest.get_text(strip=True)

    # extract roman numeral (e.g. XVII)
    match = re.search(r"([IVXLCDM]+)", sesja_text)
    if not match:
        raise RuntimeError("Nie udało się znaleźć numeru sesji")
    roman_num = match.group(1)

    # Convert roman to int
    roman_map = {'I':1,'V':5,'X':10,'L':50,'C':100,'D':500,'M':1000}
    def roman_to_int(s):
        total, prev = 0, 0
        for ch in reversed(s):
            val = roman_map[ch]
            if val < prev:
                total -= val
            else:
                total += val
                prev = val
        return total
    sesja_number = roman_to_int(roman_num)

    return urljoin(DEF_URL, latest["href"]), sesja_number


def get_latest_porządek_url(sesja_url):
    """Find the latest Porządek obrad subpage inside a Sesja page."""
    resp = requests.get(sesja_url, headers=HEADERS)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Find all porządek obrad links (bez względu na wielkość liter i czy ma numer)
    porzadek_links = soup.find_all("a", href=True, text=re.compile(r"porządek obrad", re.I))
    if not porzadek_links:
        raise RuntimeError("Nie znaleziono żadnego porządku obrad")

    # Sprawdź czy są porządki z numerami arabskimi
    numbered_porzadki = []
    unnumbered_porzadki = []
    
    for link in porzadek_links:
        text = link.get_text(strip=True)
        # Szukaj numeru arabskiego (1-9)
        match = re.search(r"nr\s*([1-9])", text)
        if match:
            number = int(match.group(1))
            numbered_porzadki.append((link, number))
        else:
            # Porządek bez numeru
            unnumbered_porzadki.append(link)
    
    # Jeśli są porządki z numerami, wybierz ten z najwyższym numerem
    if numbered_porzadki:
        latest_link, latest_number = max(numbered_porzadki, key=lambda x: x[1])
        print(f"Znaleziono porządki z numerami. Wybrano porządek nr {latest_number}")
        return urljoin(sesja_url, latest_link["href"]), latest_number
    else:
        # Jeśli nie ma numerowanych, weź pierwszy bez numeru
        if unnumbered_porzadki:
            latest_link = unnumbered_porzadki[0]
            print("Znaleziono tylko porządek bez numeru")
            return urljoin(sesja_url, latest_link["href"]), 1
        else:
            raise RuntimeError("Nie znaleziono żadnego porządku obrad")


def get_druk_number_from_link(link):
    """Extract druk number from link text like 'DRUK NR 223'."""
    text = link.get_text(strip=True)
    match = re.search(r"DRUK\s+NR\s+(\d+)", text, re.I)
    if match:
        return match.group(1)
    return None


def extract_text_from_pdf(file_path):
    """Extract text from PDF file."""
    try:
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            # Read first page to get title/beginning
            if len(pdf_reader.pages) > 0:
                page = pdf_reader.pages[0]
                text = page.extract_text()
            # Limit to first 35 words
            words = text.split()[:35]
            return " ".join(words)
    except Exception as e:
        print(f"Error reading PDF {file_path}: {e}")
        return ""


def extract_text_from_docx(file_path):
    """Extract text from DOCX file."""
    try:
        doc = Document(file_path)
        text = ""
        # Read first few paragraphs
        for paragraph in doc.paragraphs[:10]:
            text += paragraph.text + " "
            # Stop if we have enough words
            if len(text.split()) >= 35:
                break
        # Limit to first 35 words
        words = text.split()[:35]
        return " ".join(words)
    except Exception as e:
        print(f"Error reading DOCX {file_path}: {e}")
        return ""


def get_file_content_preview(file_path):
    """Extract preview text from various file types."""
    file_ext = os.path.splitext(file_path)[1].lower()
    
    if file_ext == ".pdf":
        return extract_text_from_pdf(file_path)
    elif file_ext in [".docx"]:
        return extract_text_from_docx(file_path)
    elif file_ext in [".doc", ".xls", ".xlsx", ".gml"]:
        # For other formats, return empty (could be extended later)
        return ""
    else:
        return ""


def analyze_content_with_ai(content_text):
    """Use OpenRouter AI to analyze content and return 3-word summary."""
    if not content_text or len(content_text.strip()) < 10:
        return ""
    
    prompt = f"""
    Analyze this Polish document text (first 35 words) and provide exactly 3 words that best describe its main topic or purpose. 
    The response should be in Polish and contain ONLY the 3 words, separated by spaces, no punctuation.
    
    Document text:
    {content_text}
    
    Respond with exactly 3 Polish words:"""
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 10,
        "temperature": 0.3
    }
    
    try:
        response = requests.post(OPENROUTER_BASE_URL, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        
        if 'choices' in result and len(result['choices']) > 0:
            ai_response = result['choices'][0]['message']['content'].strip()
            # Clean up the response - take only first 3 words
            words = ai_response.split()[:3]
            return "_".join(words) if words else ""
        else:
            print(f"Unexpected AI response format: {result}")
            return ""
            
    except Exception as e:
        print(f"Error calling OpenRouter AI: {e}")
        return ""

def generate_new_filename(link, original_filename, ai_keywords=""):
    """Generate new filename based on druk number, AI keywords, and file type."""
    druk_number = get_druk_number_from_link(link)
    
    if not druk_number:
        # If no druk number found, return original filename
        return original_filename
    
    file_ext = os.path.splitext(original_filename)[1].lower()
    
    # Build base name with druk number
    base_name = f"DRUK{druk_number}"
    
    # Add AI keywords if available
    if ai_keywords:
        base_name += f"_{ai_keywords}"
    
    if file_ext == ".gml":
        return f"{base_name}_załącznik.gml"
    elif file_ext in [".pdf", ".doc", ".docx", ".xls", ".xlsx"]:
        return f"{base_name}{file_ext}"
    else:
        # For unknown extensions, keep original name but add druk number and keywords
        name_without_ext = os.path.splitext(original_filename)[0]
        return f"{base_name}_{name_without_ext}{file_ext}"

def check_druk_exists_in_directory(save_dir, druk_number):
    """Check if a file with the given druk number already exists in the directory.
    Returns: (exists, has_keywords, existing_filename)
    - exists: True if any file with this druk number exists
    - has_keywords: True if the existing file already has AI keywords
    - existing_filename: filename of the existing file (if exists)
    """
    if not druk_number:
        return False, False, None
    
    for filename in os.listdir(save_dir):
        if filename.startswith(f"DRUK{druk_number}"):
            # Check if file has AI keywords (more than just druk number and extension)
            name_without_ext = os.path.splitext(filename)[0]
            
            # Pattern analysis:
            # DRUK248.pdf -> no keywords
            # DRUK248_keywords.pdf -> has keywords  
            # DRUK248_załącznik.gml -> special case, treated as having keywords
            
            if name_without_ext == f"DRUK{druk_number}":
                # Just basic druk number, no keywords
                return True, False, filename
            elif "_załącznik" in filename:
                # Special GML case - treated as having keywords
                return True, True, filename
            else:
                # Has some additional text - likely AI keywords
                return True, True, filename
    
    return False, False, None


def download_attachments(porzadek_url, save_dir):
    """Download all file attachments from Porządek obrad page."""
    resp = requests.get(porzadek_url, headers=HEADERS)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    for link in soup.find_all("a", href=True):
        href = link["href"]
        if href.lower().endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx", ".gml")):
            file_url = urljoin(porzadek_url, href)
            original_filename = os.path.basename(file_url.split("?")[0])  # clean ?params
            
            # Extract druk number first to check for duplicates
            druk_number = get_druk_number_from_link(link)
            
            # Check if file with this druk number already exists
            exists, has_keywords, existing_filename = check_druk_exists_in_directory(save_dir, druk_number)
            
            if exists and has_keywords:
                print(f"Plik DRUK{druk_number} z słowami kluczowymi już istnieje - pomijam {original_filename}")
                continue
            
            # Download to temporary file (either new file or to analyze existing one)
            temp_filepath = os.path.join(save_dir, f"temp_{original_filename}")
            print(f"Pobieram {file_url} -> temp file")
            file_resp = requests.get(file_url, headers=HEADERS)
            file_resp.raise_for_status()
            with open(temp_filepath, "wb") as f:
                f.write(file_resp.content)
            
            # Analyze content with AI
            ai_keywords = ""
            print(f"Analizuję zawartość pliku {original_filename}...")
            content_text = get_file_content_preview(temp_filepath)
            if content_text:
                ai_keywords = analyze_content_with_ai(content_text)
                print(f"AI wygenerował słowa kluczowe: {ai_keywords}")
            else:
                print("Nie udało się wyciągnąć tekstu z pliku")
            
            if exists and not has_keywords:
                # File exists but without keywords - rename existing file and remove temp
                print(f"Plik DRUK{druk_number} istnieje bez słów kluczowych - dodaję słowa kluczowe")
                existing_filepath = os.path.join(save_dir, existing_filename)
                
                # Generate new filename with AI keywords using existing file extension
                existing_ext = os.path.splitext(existing_filename)[1]
                if ai_keywords:
                    new_filename = f"DRUK{druk_number}_{ai_keywords}{existing_ext}"
                else:
                    new_filename = existing_filename  # Keep original if AI failed
                
                new_filepath = os.path.join(save_dir, new_filename)
                
                # Rename existing file
                os.rename(existing_filepath, new_filepath)
                print(f"Przemianowano istniejący plik: {existing_filename} -> {new_filename}")
                
                # Remove temporary file
                os.remove(temp_filepath)
            else:
                # New file - generate filename and save
                final_filename = generate_new_filename(link, original_filename, ai_keywords)
                final_filepath = os.path.join(save_dir, final_filename)
                
                # Rename temp file to final name
                os.rename(temp_filepath, final_filepath)
                print(f"Zapisano jako: {final_filepath}")
            
            print("---")


def main():
    # Step 1: find latest sesja
    sesja_url, sesja_number = get_latest_sesja_url()
    sesja_dir = os.path.join(BASE_SAVE_DIR, f"Sesja{sesja_number}")
    Path(sesja_dir).mkdir(parents=True, exist_ok=True)
    print(f"Najświeższa sesja: {sesja_number}, URL: {sesja_url}")

    # Step 2: find latest porządek obrad
    porzadek_url, porzadek_number = get_latest_porządek_url(sesja_url)
    porzadek_dir = os.path.join(sesja_dir, f"Porzadek{porzadek_number}")
    Path(porzadek_dir).mkdir(parents=True, exist_ok=True)
    print(f"Najświeższy porządek: {porzadek_number}, URL: {porzadek_url}")

    # Step 3: download files
    download_attachments(porzadek_url, porzadek_dir)


if __name__ == "__main__":
    main()
