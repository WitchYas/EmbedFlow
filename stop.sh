#!/bin/bash

echo "🛑 Stopping EmbeddedOps Platform..."

# stop FastAPI
pkill -f "uvicorn api.main:app" && echo "✅ FastAPI stopped" || echo "⚠️  FastAPI not running"

# stop Streamlit
pkill -f "streamlit run" && echo "✅ Streamlit stopped" || echo "⚠️  Streamlit not running"

# stop Docker services
docker-compose down && echo "✅ Docker services stopped"

echo ""
echo "✅ Platform stopped cleanly"
