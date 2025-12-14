#!/bin/bash

# Emergency disk space cleanup script for EC2
# Run this on the EC2 server to free up disk space

echo "=========================================="
echo "Emergency Disk Space Cleanup"
echo "=========================================="
echo ""

echo "Step 1: Checking current disk usage..."
df -h /
echo ""

echo "Step 2: Stopping all containers..."
docker-compose -f ~/surveyProj/docker-compose.yml down 2>/dev/null || true
docker stop $(docker ps -aq) 2>/dev/null || true
echo ""

echo "Step 3: Removing all stopped containers..."
docker container prune -f
echo ""

echo "Step 4: Removing unused images (including tagged ones)..."
docker image prune -a -f
echo ""

echo "Step 5: Removing build cache..."
docker builder prune -a -f
echo ""

echo "Step 6: Removing unused volumes..."
docker volume prune -f
echo ""

echo "Step 7: Removing unused networks..."
docker network prune -f
echo ""

echo "Step 8: Full system cleanup..."
docker system prune -a -f --volumes
echo ""

echo "Step 9: Checking disk usage after cleanup..."
df -h /
echo ""

echo "Step 10: Removing old Docker images with <none> tag..."
docker images | grep '<none>' | awk '{print $3}' | xargs -r docker rmi -f 2>/dev/null || true
echo ""

echo "=========================================="
echo "Cleanup completed!"
echo "=========================================="
echo ""
echo "Disk space freed. You can now try deployment again."
echo ""
