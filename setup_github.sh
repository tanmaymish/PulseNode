#!/bin/bash
# PulseNode setup script

echo "Initializing PulseNode Repository for GitHub..."

# 1. Remove the old Netdata .git history
echo "Removing old .git directory..."
rm -rf .git

# 2. Re-initialize a blank git repository
echo "Initializing new .git repository..."
git init

# 3. Add all files
echo "Staging files..."
git add .

# 4. Create an initial commit
echo "Committing..."
git commit -m "Initial commit: PulseNode Telemetry Engine Core & Custom Python Anomaly Modules"

echo ""
echo "=========================================================="
echo "✅ PulseNode is now a completely fresh local Git repository!"
echo "=========================================================="
echo ""
echo "To push this to your GitHub account as your own project, run:"
echo "  1. Go to github.com and create a new empty repository named 'PulseNode'"
echo "  2. Run the following commands:"
echo "     git branch -M main"
echo "     git remote add origin https://github.com/tanmaymish/PulseNode.git"
echo "     git push -u origin main"
echo "=========================================================="
