#!/bin/bash
# Georgian RAG - Docker Build & Publish Script

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="georgian-rag"
DOCKER_USERNAME="${DOCKER_USERNAME:-yourusername}"
VERSION="${VERSION:-latest}"

echo -e "${GREEN}Georgian RAG - Build & Publish${NC}"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Docker is not running. Please start Docker and try again.${NC}"
    exit 1
fi

# Step 1: Build the image
echo -e "\n${YELLOW}Building Docker image...${NC}"
docker build -t ${IMAGE_NAME}:${VERSION} .

if [ $? -eq 0 ]; then
    echo -e "${GREEN} Build successful!${NC}"
else
    echo -e "${RED} Build failed!${NC}"
    exit 1
fi

# Step 2: Tag for Docker Hub
echo -e "\n${YELLOW}  Tagging image for Docker Hub...${NC}"
docker tag ${IMAGE_NAME}:${VERSION} ${DOCKER_USERNAME}/${IMAGE_NAME}:${VERSION}

if [ "${VERSION}" != "latest" ]; then
    docker tag ${IMAGE_NAME}:${VERSION} ${DOCKER_USERNAME}/${IMAGE_NAME}:latest
fi

echo -e "${GREEN} Tagged as ${DOCKER_USERNAME}/${IMAGE_NAME}:${VERSION}${NC}"

# Step 3: Login to Docker Hub (if not already logged in)
echo -e "\n${YELLOW} Logging in to Docker Hub...${NC}"
docker login

if [ $? -ne 0 ]; then
    echo -e "${RED}Docker Hub login failed!${NC}"
    exit 1
fi

# Step 4: Push to Docker Hub
echo -e "\n${YELLOW} Pushing to Docker Hub...${NC}"
docker push ${DOCKER_USERNAME}/${IMAGE_NAME}:${VERSION}

if [ "${VERSION}" != "latest" ]; then
    docker push ${DOCKER_USERNAME}/${IMAGE_NAME}:latest
fi

if [ $? -eq 0 ]; then
    echo -e "${GREEN} Successfully pushed to Docker Hub!${NC}"
else
    echo -e "${RED} Push failed!${NC}"
    exit 1
fi

# Summary
echo -e "${GREEN} Success!${NC}"
echo -e "Image: ${DOCKER_USERNAME}/${IMAGE_NAME}:${VERSION}"
echo -e "\nTo pull and run:"
echo -e "  ${YELLOW}docker pull ${DOCKER_USERNAME}/${IMAGE_NAME}:${VERSION}${NC}"
echo -e "  ${YELLOW}docker run -p 8000:8000 --env-file .env ${DOCKER_USERNAME}/${IMAGE_NAME}:${VERSION}${NC}"
echo -e "\nDocker Hub: ${YELLOW}https://hub.docker.com/r/${DOCKER_USERNAME}/${IMAGE_NAME}${NC}"
