# Rada Miasta Document Downloader with AI Analysis

🌐 **Responsive Web Application** for downloading and managing documents from the Piła City Council website with AI-powered intelligent file naming.

## 🚀 Web Application Features

- **📱 Responsive Design**: Works perfectly on desktop, tablet, and mobile devices
- **🎯 One-Click Downloads**: Simple buttons for different download scenarios
- **📊 Real-time Progress**: Live progress tracking during downloads
- **📁 File Management**: Browse, search, and download files directly from the web interface
- **📈 Statistics Dashboard**: Overview of downloaded files, sessions, and storage usage
- **📜 Activity History**: Complete log of all download activities
- **⚡ Smart Duplicate Detection**: Avoids re-downloading existing files

## 🔧 Core Features

- **Automatic Session Detection**: Finds the latest council session (Sesja Rady Miasta)
- **Agenda Discovery**: Locates the most recent agenda (Porządek obrad) 
- **Document Download**: Downloads all PDF, DOC, DOCX, XLS, XLSX, and GML files
- **AI Content Analysis**: Uses OpenRouter's nvidia/nemotron-nano-9b-v2 model to analyze document content
- **Smart File Naming**: Generates filenames with format `DRUK_NR{number}_{ai_keywords}.{extension}`

## Example Output

The script generates files with meaningful names like:
- `DRUK_NR248_edukacja_informacja_realizacja.pdf` (education information implementation)  
- `DRUK_NR250_wynagrodzenie_prezydent_rada.pdf` (salary president council)
- `DRUK_NR253_interpelacje_radni_zapytania.pdf` (interpellations councilors inquiries)

## Requirements

Install dependencies with:
```bash
pip install -r requirements.txt
```

## Configuration

The script is pre-configured with:
- **OpenRouter API Key**: `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`
- **AI Model**: `nvidia/nemotron-nano-9b-v2:free`
- **Download Directory**: `C:\Users\PC\Desktop\SesjeRady`

## 🌐 Web Application Usage

### Quick Start
1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Launch the web application:**
   ```bash
   python run_app.py
   ```

3. **Open in browser:**
   - Local access: http://localhost:5000
   - Network access: http://[YOUR_IP]:5000

### 📱 Main Functions

- **🟢 "Pobierz Najnowsze"** - Downloads files from the latest session and agenda
- **🔄 "Aktualizuj Istniejące"** - Updates ONLY the sessions you already have downloaded  
- **☁️ "Pobierz Wszystkie"** - Downloads ALL sessions from the very first one (complete archive)
- **🔍 "Wybierz Sesję"** - Download a specific session by number
- **📁 Album Selection** - Choose which folder/album to save files to
- **📁 Files Tab** - Browse, search, and download saved files
- **📜 History Tab** - View download activity log
- **📊 Statistics Tab** - See file counts, storage usage, etc.

## 💻 Command Line Usage (Original Script)

You can still use the original command-line version:
```bash
python script.py
```

The script will:
1. Find the latest session
2. Locate the most recent agenda
3. Download all attachments
4. Analyze each file's content with AI
5. Rename files with descriptive keywords

## File Structure

Downloads are organized as:
```
SesjeRady/
├── Sesja20/
│   └── Porzadek2/
│       ├── DRUK_NR248_edukacja_informacja_realizacja.pdf
│       ├── DRUK_NR249_Zgodę_Przetarg_Najmu.pdf
│       └── ...
```

## AI Analysis

The AI model analyzes the first 1500 characters of each document to generate exactly 3 Polish words that best describe the document's main topic or purpose. These keywords are then incorporated into the filename for easy identification and organization.

## 🌍 Remote Access for Family

The web application is designed for easy family access from any device:

- **📱 Mobile Friendly**: Works perfectly on smartphones and tablets
- **🏠 Home Network**: Accessible from any device on the same WiFi network  
- **🔒 Simple Interface**: No technical knowledge required
- **⚡ Real-time Updates**: See progress and status in real-time
- **📂 Easy File Access**: Download files directly through the browser

### Network Setup
1. Run `python run_app.py` on your computer
2. Find your computer's IP address (e.g., 192.168.1.100)
3. Share the link: `http://192.168.1.100:5000`
4. Family members can access from any device on the same network

## 📁 Supported File Types

- **PDF (.pdf)** - Full text extraction and AI analysis
- **Word documents (.docx)** - Text extraction and AI analysis  
- **Legacy formats (.doc, .xls, .xlsx, .gml)** - Downloaded with basic naming

## 🛡️ Error Handling

The application includes robust error handling for:
- Network connectivity issues
- File parsing errors
- AI service unavailability
- Invalid file formats
- Server errors and timeouts

If AI analysis fails for any document, the file is still saved with the basic `DRUK_NR{number}` naming convention.

## 🔧 Technical Details

- **Backend**: Flask (Python)
- **Frontend**: Bootstrap 5 + Vanilla JavaScript
- **AI Integration**: OpenRouter API
- **File Processing**: PyPDF2, python-docx
- **Real-time Updates**: AJAX polling
- **Responsive Design**: Mobile-first approach
