set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🚀 Starting Drive File Sharing API...${NC}"

export PYTHONDONTWRITEBYTECODE=1  
export PYTHONPYCACHEPREFIX="$HOME/.cache/python-pycache"  

mkdir -p "$HOME/.cache/python-pycache"

export PYTHONPATH="${PYTHONPATH}:$(pwd)"
export FASTAPI_ENV="${FASTAPI_ENV:-production}"

if [ ! -d "venv" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment not found. Creating one...${NC}"
    python3 -m venv venv
fi

echo -e "${BLUE}📦 Activating virtual environment...${NC}"
source venv/bin/activate

pip install --upgrade pip

echo -e "${BLUE}📚 Installing dependencies...${NC}"
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo -e "${RED}❌ requirements.txt not found!${NC}"
    exit 1
fi

echo -e "${BLUE}🧹 Cleaning Python cache files...${NC}"
find . -type f -name "*.pyc" -delete
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

echo -e "${BLUE}📁 Creating necessary directories...${NC}"
mkdir -p storage/files
mkdir -p logs

if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  .env file not found. Creating template...${NC}"
    cat > .env << EOF
# Database
DATABASE_URL=sqlite:///./drive.db

# Security
SECRET_KEY=your-secret-key-change-this-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Storage
UPLOAD_DIR=storage/files
MAX_FILE_SIZE=104857600  # 100MB

# Server
HOST=0.0.0.0
PORT=8000
WORKERS=4
EOF
    echo -e "${YELLOW}📝 Please edit .env file with your configuration${NC}"
fi

if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Check database connection
echo -e "${BLUE}🗄️  Checking database...${NC}"
python3 -c "
from app.database import engine
try:
    with engine.connect() as conn:
        print('✅ Database connection successful')
except Exception as e:
    print(f'❌ Database connection failed: {e}')
    exit(1)
" || exit 1

# Start the server
echo -e "${GREEN}🎯 Starting FastAPI server...${NC}"
echo -e "${GREEN}📍 Server will be available at: http://${HOST:-0.0.0.0}:${PORT:-8000}${NC}"
echo -e "${GREEN}📖 API Documentation: http://${HOST:-0.0.0.0}:${PORT:-8000}/docs${NC}"
echo -e "${GREEN}🔄 ReDoc Documentation: http://${HOST:-0.0.0.0}:${PORT:-8000}/redoc${NC}"

if [ "$FASTAPI_ENV" = "production" ]; then
    echo -e "${BLUE}🏭 Starting in production mode with Gunicorn...${NC}"
    gunicorn app.main:app \
        --workers ${WORKERS:-4} \
        --worker-class uvicorn.workers.UvicornWorker \
        --bind ${HOST:-0.0.0.0}:${PORT:-8000} \
        --access-logfile logs/access.log \
        --error-logfile logs/error.log \
        --log-level info \
        --preload
else
    echo -e "${BLUE}🔧 Starting in development mode with Uvicorn...${NC}"
    uvicorn app.main:app \
        --host ${HOST:-0.0.0.0} \
        --port ${PORT:-8000} \
        --reload \
        --log-level debug \
        --access-log
fi