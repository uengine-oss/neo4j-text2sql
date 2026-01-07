#!/bin/bash

# Neo4j Text2SQL - 전체 시스템 종료 스크립트

echo "🛑 Stopping Neo4j Text2SQL System..."
echo ""

# 1. Backend API
echo "3️⃣ Stopping Backend API..."
lsof -i :8001 | grep LISTEN | awk '{print $2}' | xargs kill -9 2>/dev/null
sleep 2
echo "   ✅ Backend API stopped"

# 2. Docker (optional)
read -p "4️⃣ Stop Docker services? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
    docker-compose down
    echo "   ✅ Docker services stopped"
else
    echo "   ⏭️  Docker services kept running"
fi

echo ""
echo "✅ All services stopped!"

