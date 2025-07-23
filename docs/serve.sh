echo "Starting Drive API Documentation Server..."
echo "Documentation will be available at: http://localhost:8080"
echo "Press Ctrl+C to stop the server"

if command -v python3 &> /dev/null; then
    cd "$(dirname "$0")"
    python3 -m http.server 8080
elif command -v python &> /dev/null; then
    cd "$(dirname "$0")"
    python -m http.server 8080
else
    echo "Python not found. Please install Python to serve documentation."
    exit 1
fi