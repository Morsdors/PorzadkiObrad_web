from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import threading
import time
from datetime import datetime
import json
from pathlib import Path
import sys

# Import our existing functions (we'll refactor script.py)
from rada_scraper import (
    get_latest_sesja_url, get_latest_porządek_url, download_attachments,
    get_all_sesja_urls, download_specific_sesja, get_existing_sessions
)

app = Flask(__name__)

# Configuration
# Prefer environment variable when available (works on Render and locally)
DEFAULT_DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "./data")
SETTINGS_FILE = "app_settings.json"
LOG_FILE = "download_log.json"

# Global settings
app_settings = {
    "download_base_dir": DEFAULT_DOWNLOAD_DIR,
    "available_albums": ["SesjeRady", "Archiwum", "Backup", "Dokumenty"]
}

# Global variables for status tracking
download_status = {
    "is_running": False,
    "current_task": "",
    "progress": 0,
    "last_update": None,
    "error": None
}

def log_action(action, details=""):
    """Log actions to JSON file"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "details": details
    }
    
    try:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                logs = json.load(f)
        else:
            logs = []
        
        logs.append(log_entry)
        # Keep only last 100 entries
        if len(logs) > 100:
            logs = logs[-100:]
            
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error logging action: {e}")

def update_status(task, progress=0, error=None):
    """Update global download status"""
    global download_status
    download_status.update({
        "current_task": task,
        "progress": progress,
        "last_update": datetime.now().isoformat(),
        "error": error
    })


def load_settings():
    """Load settings from JSON file"""
    global app_settings
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                saved_settings = json.load(f)
                app_settings.update(saved_settings)
    except Exception as e:
        print(f"Error loading settings: {e}")


def save_settings():
    """Save settings to JSON file"""
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(app_settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving settings: {e}")


def get_current_download_dir():
    """Get current download directory"""
    return app_settings.get("download_base_dir", DEFAULT_DOWNLOAD_DIR)


def set_download_dir(new_dir):
    """Set new download directory"""
    global app_settings
    app_settings["download_base_dir"] = new_dir
    save_settings()
    # Ensure directory exists
    Path(new_dir).mkdir(parents=True, exist_ok=True)


@app.route('/api/settings/folder/set_path', methods=['POST'])
def set_folder_absolute_path():
    """Set download folder to an absolute path provided by the user"""
    try:
        data = request.get_json() or {}
        raw_path = str(data.get('path', '')).strip()
        if not raw_path:
            return jsonify({"error": "Ścieżka nie może być pusta"}), 400

        # Expand user (~) and make absolute
        expanded = os.path.expanduser(raw_path)
        absolute_path = os.path.abspath(expanded)

        # Create directory if needed
        Path(absolute_path).mkdir(parents=True, exist_ok=True)

        # Update settings
        set_download_dir(absolute_path)
        log_action("Zmieniono folder (ścieżka)", absolute_path)

        return jsonify({
            "message": "Folder zmieniony pomyślnie",
            "new_download_dir": absolute_path
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/settings/folder/pick', methods=['POST'])
def pick_folder_via_dialog():
    """Open a native folder selection dialog (local use only). Not supported on Render."""
    try:
        # Disallow on headless/server environments
        if os.environ.get('RENDER') or not (sys.platform.startswith('win') or sys.platform.startswith('darwin') or sys.platform.startswith('linux')):
            return jsonify({"error": "Ta funkcja jest dostępna tylko lokalnie (nie na serwerze)."}), 400

        # Try to open a native dialog using Tkinter
        try:
            import tkinter as tk
            from tkinter import filedialog
        except Exception:
            return jsonify({"error": "Brak wsparcia dla interfejsu graficznego."}), 400

        # Create hidden root window
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        selected = filedialog.askdirectory(title='Wybierz folder zapisu plików')
        root.destroy()

        if not selected:
            return jsonify({"cancelled": True})

        # Normalize and set
        absolute_path = os.path.abspath(os.path.expanduser(selected))
        Path(absolute_path).mkdir(parents=True, exist_ok=True)
        set_download_dir(absolute_path)
        log_action("Zmieniono folder (dialog)", absolute_path)

        return jsonify({
            "message": "Folder zmieniony pomyślnie",
            "new_download_dir": absolute_path
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    """Get current download status"""
    try:
        # Get latest session info
        sesja_url, sesja_number = get_latest_sesja_url()
        porzadek_url, porzadek_number = get_latest_porządek_url(sesja_url)
        
        # Get existing sessions info
        current_dir = get_current_download_dir()
        existing_sessions = get_existing_sessions(current_dir)
        
        status_info = {
            "latest_sesja": sesja_number,
            "latest_porzadek": porzadek_number,
            "sesja_url": sesja_url,
            "porzadek_url": porzadek_url,
            "download_status": download_status,
            "base_url": "https://bip.pila.pl/2025.html",
            "current_download_dir": current_dir,
            "existing_sessions": existing_sessions,
            "existing_sessions_count": len(existing_sessions),
            "available_albums": app_settings["available_albums"]
        }
        return jsonify(status_info)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/download/latest', methods=['POST'])
def download_latest():
    """Download latest files (current script functionality)"""
    if download_status["is_running"]:
        return jsonify({"error": "Download already in progress"}), 400
    
    def run_download():
        global download_status
        download_status["is_running"] = True
        try:
            update_status("Szukam najnowszej sesji...", 10)
            sesja_url, sesja_number = get_latest_sesja_url()
            
            update_status("Szukam najnowszego porządku...", 30)
            porzadek_url, porzadek_number = get_latest_porządek_url(sesja_url)
            
            # Create directories
            current_download_dir = get_current_download_dir()
            sesja_dir = os.path.join(current_download_dir, f"Sesja{sesja_number}")
            porzadek_dir = os.path.join(sesja_dir, f"Porzadek{porzadek_number}")
            Path(porzadek_dir).mkdir(parents=True, exist_ok=True)
            
            update_status(f"Pobieranie plików z Sesji {sesja_number}, Porządek {porzadek_number}...", 50)
            download_attachments(porzadek_url, porzadek_dir)
            
            update_status("Zakończono pomyślnie!", 100)
            log_action("Pobrano najnowsze pliki", f"Sesja {sesja_number}, Porządek {porzadek_number}")
            
        except Exception as e:
            update_status("Błąd podczas pobierania", 0, str(e))
            log_action("Błąd", str(e))
        finally:
            download_status["is_running"] = False
    
    thread = threading.Thread(target=run_download)
    thread.start()
    
    return jsonify({"message": "Download started"})

@app.route('/api/download/all', methods=['POST'])
def download_all():
    """Update only existing sessions (download latest porządek from sessions we already have)"""
    if download_status["is_running"]:
        return jsonify({"error": "Download already in progress"}), 400
    
    def run_download_all():
        global download_status
        download_status["is_running"] = True
        try:
            current_download_dir = get_current_download_dir()
            update_status("Sprawdzanie istniejących sesji...", 5)
            
            existing_sessions = get_existing_sessions(current_download_dir)
            if not existing_sessions:
                update_status("Brak istniejących sesji do aktualizacji", 100, "Nie znaleziono żadnych sesji")
                log_action("Brak sesji do aktualizacji", "Folder jest pusty")
                return
            
            update_status("Wyszukiwanie wszystkich sesji online...", 10)
            all_sessions = get_all_sesja_urls()
            
            # Filter to only existing sessions
            sessions_to_update = []
            for sesja_url, sesja_number in all_sessions:
                if sesja_number in existing_sessions:
                    sessions_to_update.append((sesja_url, sesja_number))
            
            total_sessions = len(sessions_to_update)
            update_status(f"Znaleziono {total_sessions} sesji do aktualizacji", 15)
            
            for i, (sesja_url, sesja_number) in enumerate(sessions_to_update):
                progress = int((i / total_sessions) * 80) + 15
                update_status(f"Aktualizacja Sesji {sesja_number}...", progress)
                
                try:
                    download_specific_sesja(sesja_url, sesja_number, current_download_dir)
                except Exception as e:
                    print(f"Error updating session {sesja_number}: {e}")
                    continue
            
            update_status("Zakończono aktualizację istniejących sesji!", 100)
            log_action("Zaktualizowano istniejące sesje", f"Zaktualizowane {total_sessions} sesji")
            
        except Exception as e:
            update_status("Błąd podczas aktualizacji", 0, str(e))
            log_action("Błąd aktualizacji istniejących", str(e))
        finally:
            download_status["is_running"] = False
    
    thread = threading.Thread(target=run_download_all)
    thread.start()
    
    return jsonify({"message": "Update existing sessions started"})

@app.route('/api/download/session/<int:session_number>', methods=['POST'])
def download_session(session_number):
    """Download specific session"""
    if download_status["is_running"]:
        return jsonify({"error": "Download already in progress"}), 400
    
    def run_download_session():
        global download_status
        download_status["is_running"] = True
        try:
            update_status(f"Szukam Sesji {session_number}...", 20)
            
            # Find specific session
            all_sessions = get_all_sesja_urls()
            target_session = None
            for sesja_url, sesja_num in all_sessions:
                if sesja_num == session_number:
                    target_session = (sesja_url, sesja_num)
                    break
            
            if not target_session:
                raise Exception(f"Sesja {session_number} nie została znaleziona")
            
            update_status(f"Pobieranie Sesji {session_number}...", 50)
            current_download_dir = get_current_download_dir()
            download_specific_sesja(target_session[0], target_session[1], current_download_dir)
            
            update_status(f"Zakończono pobieranie Sesji {session_number}!", 100)
            log_action(f"Pobrano Sesję {session_number}")
            
        except Exception as e:
            update_status("Błąd podczas pobierania sesji", 0, str(e))
            log_action("Błąd pobierania sesji", str(e))
        finally:
            download_status["is_running"] = False
    
    thread = threading.Thread(target=run_download_session)
    thread.start()
    
    return jsonify({"message": f"Download session {session_number} started"})


@app.route('/api/download/from_first', methods=['POST'])
def download_from_first():
    """Download all sessions from the first session available online"""
    if download_status["is_running"]:
        return jsonify({"error": "Download already in progress"}), 400
    
    def run_download_from_first():
        global download_status
        download_status["is_running"] = True
        try:
            update_status("Wyszukiwanie wszystkich sesji...", 5)
            all_sessions = get_all_sesja_urls()
            total_sessions = len(all_sessions)
            current_download_dir = get_current_download_dir()
            
            update_status(f"Znaleziono {total_sessions} sesji do pobrania", 10)
            
            for i, (sesja_url, sesja_number) in enumerate(all_sessions):
                progress = int((i / total_sessions) * 85) + 10
                update_status(f"Pobieranie Sesji {sesja_number}...", progress)
                
                try:
                    download_specific_sesja(sesja_url, sesja_number, current_download_dir)
                except Exception as e:
                    print(f"Error downloading session {sesja_number}: {e}")
                    continue
            
            update_status("Zakończono pobieranie wszystkich sesji od pierwszej!", 100)
            log_action("Pobrano wszystkie sesje od pierwszej", f"Pobrane {total_sessions} sesji")
            
        except Exception as e:
            update_status("Błąd podczas pobierania od pierwszej sesji", 0, str(e))
            log_action("Błąd pobierania od pierwszej", str(e))
        finally:
            download_status["is_running"] = False
    
    thread = threading.Thread(target=run_download_from_first)
    thread.start()
    
    return jsonify({"message": "Download all sessions from first started"})


@app.route('/api/files')
def list_files():
    """List all downloaded files"""
    try:
        files_info = []
        current_download_dir = get_current_download_dir()
        if os.path.exists(current_download_dir):
            for sesja_folder in os.listdir(current_download_dir):
                sesja_path = os.path.join(current_download_dir, sesja_folder)
                if os.path.isdir(sesja_path) and sesja_folder.startswith("Sesja"):
                    
                    for porzadek_folder in os.listdir(sesja_path):
                        porzadek_path = os.path.join(sesja_path, porzadek_folder)
                        if os.path.isdir(porzadek_path) and porzadek_folder.startswith("Porzadek"):
                            
                            for filename in os.listdir(porzadek_path):
                                file_path = os.path.join(porzadek_path, filename)
                                if os.path.isfile(file_path):
                                    file_info = {
                                        "filename": filename,
                                        "sesja": sesja_folder,
                                        "porzadek": porzadek_folder,
                                        "size": os.path.getsize(file_path),
                                        "modified": datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat(),
                                        "path": os.path.relpath(file_path, current_download_dir)
                                    }
                                    files_info.append(file_info)
        
        return jsonify(files_info)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/logs')
def get_logs():
    """Get download logs"""
    try:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                logs = json.load(f)
            return jsonify(logs[-20:])  # Last 20 entries
        else:
            return jsonify([])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/download/<path:filename>')
def download_file(filename):
    """Download a specific file"""
    try:
        current_download_dir = get_current_download_dir()
        return send_from_directory(current_download_dir, filename, as_attachment=True)
    except Exception as e:
        return jsonify({"error": str(e)}), 404


@app.route('/api/settings/folder', methods=['GET'])
def get_folder_settings():
    """Get current folder settings"""
    return jsonify({
        "current_download_dir": get_current_download_dir(),
        "available_albums": app_settings["available_albums"]
    })


@app.route('/api/settings/folder', methods=['POST'])
def set_folder_settings():
    """Set new download folder"""
    try:
        data = request.get_json()
        album_name = data.get('album_name', 'SesjeRady')
        
        # Create new directory path
        base_dir = os.path.dirname(get_current_download_dir())
        new_dir = os.path.join(base_dir, album_name)
        
        # Set new directory
        set_download_dir(new_dir)
        
        log_action("Zmieniono folder", f"Nowy folder: {album_name}")
        
        return jsonify({
            "message": "Folder zmieniony pomyślnie",
            "new_download_dir": new_dir
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/settings/folder/add', methods=['POST'])
def add_album():
    """Add new album to available list"""
    try:
        data = request.get_json()
        album_name = data.get('album_name', '').strip()
        
        if not album_name:
            return jsonify({"error": "Nazwa albumu nie może być pusta"}), 400
        
        if album_name not in app_settings["available_albums"]:
            app_settings["available_albums"].append(album_name)
            save_settings()
            
        return jsonify({
            "message": f"Album '{album_name}' dodany",
            "available_albums": app_settings["available_albums"]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    # Load settings
    load_settings()
    
    # Ensure download directory exists
    current_dir = get_current_download_dir()
    Path(current_dir).mkdir(parents=True, exist_ok=True)
    
    # Run the app
    app.run(host='0.0.0.0', port=5000, debug=True)
