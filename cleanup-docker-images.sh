#!/bin/bash

# Script to remove all Docker images with <none> repository/tag
# This removes dangling images and intermediate layers

echo "Removing dangling Docker images..."
docker image prune -f

echo ""
echo "Removing all images with <none> repository or tag..."
docker images | grep '<none>' | awk '{print $3}' | xargs -r docker rmi -f

echo ""
echo "Cleaning up build cache..."
docker builder prune -f

echo ""
echo "Docker cleanup completed!"
echo ""
echo "Remaining images:"
docker images
