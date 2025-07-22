set -e

echo "🛑 Stopping Drive API server..."

pkill -f "uvicorn.*app.main:app" || echo "No uvicorn processes found"
pkill -f "gunicorn.*app.main:app" || echo "No gunicorn processes found"

echo "✅ Server stopped successfully"