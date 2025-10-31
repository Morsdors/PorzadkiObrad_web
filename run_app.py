"""
Simple launcher for the web application
Run this file to start the web server
"""

if __name__ == '__main__':
    from app import app
    print("🚀 Uruchamianie aplikacji Rada Miasta Piły...")
    print("📱 Aplikacja będzie dostępna pod adresem:")
    print("   http://localhost:5000")
    print("   http://127.0.0.1:5000") 
    print("🌐 Aby udostępnić w sieci lokalnej, użyj IP tego komputera")
    print("⚠️  Aby zatrzymać aplikację, naciśnij Ctrl+C")
    print("-" * 50)
    
    app.run(host='0.0.0.0', port=5000, debug=False)
