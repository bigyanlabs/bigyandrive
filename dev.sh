set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔧 Starting Drive API in Development Mode...${NC}"

export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

find . -type f -name "*.pyc" -delete
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

if [ -d "venv" ]; then
    source venv/bin/activate
fi

if [ -f "requirements.txt" ] && [ ! -f "venv/pyvenv.cfg" ]; then
    pip install -r requirements.txt
fi

mkdir -p storage/files
mkdir -p logs

echo -e "${GREEN}🚀 Starting development server...${NC}"
python3 -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    --log-level debug