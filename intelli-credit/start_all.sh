#!/bin/bash

# =========================================
# Starting Intelli-Credit Application Stack
# =========================================

echo "This script will launch 4 services in parallel tmux panes."
echo "You need to have 'tmux' installed (sudo apt install tmux)."
echo "Press Ctrl+C to cancel or Enter to continue..."
read

# Start a new tmux session in detached mode
tmux new-session -d -s intellicredit

# Pane 0: Frontend
tmux send-keys -t intellicredit:0.0 "cd frontend && npm run dev" C-m

# Split horizontally, Pane 1: Backend
tmux split-window -h -t intellicredit:0
tmux send-keys -t intellicredit:0.1 "cd backend && npm run dev" C-m

# Split first pane vertically, Pane 2: AI Service
tmux split-window -v -t intellicredit:0.0
# Note: Ensure your conda/venv is activated if needed before running this script
tmux send-keys -t intellicredit:0.2 "cd ai-service && uvicorn main:app --reload --port 8000" C-m

# Split second pane vertically, Pane 3: Go Service
tmux split-window -v -t intellicredit:0.1
tmux send-keys -t intellicredit:0.3 "cd go-service && go run main.go" C-m

# Attach to the tmux session
tmux attach-session -t intellicredit
