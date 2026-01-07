#!/bin/bash

# Neo4j Text2SQL - 전체 시스템 시작 스크립트

echo "🚀 Starting Neo4j Text2SQL System..."
echo ""

# 1. Docker Compose (Neo4j + PostgreSQL)
echo "1️⃣ Starting Docker services (Neo4j + PostgreSQL)..."
docker-compose up -d
sleep 5
echo "   ✅ Docker services started"
echo ""

# 2. Backend API (FastAPI)
echo "2️⃣ Starting Backend API (port 8001)..."
cd /Users/uengine/neo4j_text2sql
uv run uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload > api.log 2>&1 &
API_PID=$!
sleep 5
echo "   ✅ Backend API started (PID: $API_PID)"
echo ""