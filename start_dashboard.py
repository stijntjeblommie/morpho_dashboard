#!/usr/bin/env python3
"""
Simple Dashboard Launcher for Morpho Blue Pool Analyzer

This script provides an easy way to launch the dashboard with basic checks.
"""

import os
import sys
import subprocess
import json
from pathlib import Path

def print_banner():
    """Print welcome banner"""
    print("=" * 60)
    print("🔵 Morpho Blue Pool Analyzer Dashboard")
    print("=" * 60)
    print()

def check_data_files():
    """Check if required data files exist"""
    morpho_file = Path("morpho_complete_analysis.json")
    pendle_summary_file = Path("pendle_morpho_summary.json")
    pendle_analysis_file = Path("pendle_morpho_analysis.json")

    files_status = {
        "morpho": morpho_file.exists(),
        "pendle_summary": pendle_summary_file.exists(),
        "pendle_analysis": pendle_analysis_file.exists()
    }

    return files_status

def show_data_instructions():
    """Show instructions for generating data files"""
    print("📁 Data Files Required")
    print("-" * 30)
    print()
    print("Before launching the dashboard, you need to generate data files:")
    print()
    print("1️⃣  Generate Morpho data (REQUIRED):")
    print("    node get_morpho_data.js")
    print()
    print("2️⃣  Generate Pendle data (OPTIONAL, but recommended):")
    print("    node pendle_morpho_analyzer.js")
    print("    (This generates pendle_morpho_summary.json and pendle_morpho_analysis.json)")
    print()
    print("3️⃣  Then run this script again:")
    print("    python start_dashboard.py")
    print()

def launch_streamlit():
    """Launch the Streamlit dashboard"""
    print("🚀 Launching Dashboard...")
    print("-" * 30)
    print()
    print("Dashboard will open at: http://localhost:8501")
    print("Press Ctrl+C to stop the dashboard")
    print()

    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run",
            "morpho_dashboard.py",
            "--server.port", "8501",
            "--server.address", "localhost"
        ])
    except KeyboardInterrupt:
        print("\n✅ Dashboard stopped by user")
    except Exception as e:
        print(f"❌ Error launching dashboard: {e}")
        print("\nTry manual launch:")
        print("streamlit run morpho_dashboard.py")

def main():
    print_banner()

    # Check if we're in the right directory
    if not Path("morpho_dashboard.py").exists():
        print("❌ Error: morpho_dashboard.py not found")
        print("Please run this script from the tool/ directory")
        sys.exit(1)

    # Check data files
    data_status = check_data_files()

    if not data_status["morpho"]:
        print("❌ Missing required Morpho data file")
        show_data_instructions()
        sys.exit(1)

    # Show data status
    print("📊 Data File Status:")
    print(f"   ✅ Morpho data: morpho_complete_analysis.json")

    if data_status["pendle_summary"]:
        print(f"   ✅ Pendle summary: pendle_morpho_summary.json")
    else:
        print(f"   ⚠️  Pendle summary: Not found")

    if data_status["pendle_analysis"]:
        print(f"   ✅ Pendle analysis: pendle_morpho_analysis.json")
    else:
        print(f"   ⚠️  Pendle analysis: Not found")

    if not data_status["pendle_summary"] and not data_status["pendle_analysis"]:
        print(f"   ⚠️  PT market analysis will be limited without Pendle data")

    print()

    # Check if config exists
    if Path("config.json").exists():
        print("   ✅ Configuration: config.json")
    else:
        print("   ⚠️  Configuration: Using defaults (config.json not found)")

    print()

    # Launch dashboard
    input("Press Enter to launch the dashboard...")
    launch_streamlit()

if __name__ == "__main__":
    main()
