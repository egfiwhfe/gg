#!/bin/bash

echo "🎲 Starting PolyMix Odds Monitor..."
echo ""
echo "📊 Dashboard will be available at: http://localhost:5001"
echo "📈 Paper Trading at: http://localhost:5001/paper"
echo "🔄 Auto-refresh every 30 seconds"
echo "⏱️  Monitoring duration displayed in real-time"
echo ""
echo "Press Ctrl+C to stop the monitor"
echo ""

cd "$(dirname "$0")"
python3 api.py
