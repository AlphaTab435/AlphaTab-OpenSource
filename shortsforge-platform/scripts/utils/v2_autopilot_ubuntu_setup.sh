#!/bin/bash
# ═══════════════════════════════════════════════════════════
# ShortsForge — V2 Autopilot Ubuntu Server Setup (Cloud-Init)
# Target: Ubuntu 22.04 LTS (AMD or ARM)
# Usage: Paste this entire script into the "User Data" or "Cloud-init" 
#        box when creating a new Compute Instance (Oracle, AWS, DigitalOcean).
# ═══════════════════════════════════════════════════════════

set -e

# 1. Add Deadsnakes PPA for Python 3.13
add-apt-repository -y ppa:deadsnakes/ppa
apt-get update -y
apt-get upgrade -y

# 2. Install Core Dependencies
apt-get install -y \
    python3.13 \
    python3.13-venv \
    python3.13-dev \
    python3-pip \
    ffmpeg \
    unzip \
    curl \
    git \
    sqlite3

# 3. Create Project Directory for the 'ubuntu' user
PROJECT_DIR="/home/ubuntu/shortsforge"
mkdir -p "$PROJECT_DIR"
chown ubuntu:ubuntu "$PROJECT_DIR"

# 4. Set up placeholder directory for deployment package
mkdir -p "$PROJECT_DIR/data/credentials"
chown -R ubuntu:ubuntu "$PROJECT_DIR/data"

echo "ShortsForge pre-deployment setup completed successfully."
