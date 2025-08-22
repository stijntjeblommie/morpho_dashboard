#!/usr/bin/env python3
"""
Morpho Blue Pool Analysis - Main Runner Script

This script coordinates the data collection and dashboard launch for Morpho Blue pool analysis.
"""

import os
import sys
import subprocess
import argparse
import time
import json
from pathlib import Path

def check_dependencies():
    """Check if required dependencies are installed"""
    print("Checking dependencies...")

    # Check Node.js
    try:
        result = subprocess.run(['node', '--version'], capture_output=True, text=True)
        print(f"✓ Node.js: {result.stdout.strip()}")
    except FileNotFoundError:
        print("✗ Node.js not found. Please install Node.js to run data collection scripts.")
        return False

    # Check Python dependencies
    try:
        import streamlit
        import pandas
        import plotly
        print("✓ Python dependencies installed")
    except ImportError as e:
        print(f"✗ Missing Python dependency: {e}")
        print("Please run: pip install -r requirements.txt")
        return False

    return True

def run_morpho_data_collection():
    """Run the Morpho data collection script"""
    print("\n🔍 Collecting Morpho Blue market data...")

    script_path = Path("get_morpho_data.js")
    if not script_path.exists():
        print(f"✗ Script not found: {script_path}")
        return False

    try:
        result = subprocess.run(
            ['node', str(script_path)],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        if result.returncode == 0:
            print("✓ Morpho data collection completed successfully")

            # Check if output file exists
            if Path("morpho_complete_analysis.json").exists():
                with open("morpho_complete_analysis.json", 'r') as f:
                    data = json.load(f)
                    print(f"✓ Generated data for {data['metadata']['totalMarkets']} markets")
            return True
        else:
            print(f"✗ Morpho data collection failed:")
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        print("✗ Morpho data collection timed out (5 minutes)")
        return False
    except Exception as e:
        print(f"✗ Error running Morpho data collection: {e}")
        return False

def run_pendle_analysis():
    """Run the Pendle analysis script"""
    print("\n🎯 Running Pendle PT market analysis...")

    script_path = Path("pendle_morpho_analyzer.js")
    if not script_path.exists():
        print(f"✗ Script not found: {script_path}")
        return False

    try:
        result = subprocess.run(
            ['node', str(script_path)],
            capture_output=True,
            text=True,
            timeout=180  # 3 minute timeout
        )

        if result.returncode == 0:
            print("✓ Pendle analysis completed successfully")

            # Check if output files exist
            summary_exists = Path("pendle_morpho_summary.json").exists()
            analysis_exists = Path("pendle_morpho_analysis.json").exists()

            if summary_exists:
                with open("pendle_morpho_summary.json", 'r') as f:
                    data = json.load(f)
                    pt_markets = data.get('ptMarkets', [])
                    print(f"✓ Generated summary for {len(pt_markets)} PT markets")

            if analysis_exists:
                with open("pendle_morpho_analysis.json", 'r') as f:
                    data = json.load(f)
                    pt_data = data.get('ptMarketsData', {})
                    print(f"✓ Generated detailed analysis for {len(pt_data)} PT markets")
            return True
        else:
            print(f"✗ Pendle analysis failed:")
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        print("✗ Pendle analysis timed out (3 minutes)")
        return False
    except Exception as e:
        print(f"✗ Error running Pendle analysis: {e}")
        return False

def launch_dashboard():
    """Launch the Streamlit dashboard"""
    print("\n🚀 Launching Morpho Blue Pool Analyzer Dashboard...")

    dashboard_path = Path("morpho_dashboard.py")
    if not dashboard_path.exists():
        print(f"✗ Dashboard not found: {dashboard_path}")
        return False

    try:
        # Launch Streamlit
        subprocess.run([
            'streamlit', 'run', str(dashboard_path),
            '--server.port', '8501',
            '--server.address', 'localhost',
            '--theme.base', 'light'
        ])
        return True
    except KeyboardInterrupt:
        print("\n✓ Dashboard closed by user")
        return True
    except Exception as e:
        print(f"✗ Error launching dashboard: {e}")
        return False

def check_data_freshness():
    """Check if existing data files are recent enough"""
    morpho_file = Path("morpho_complete_analysis.json")
    pendle_summary_file = Path("pendle_morpho_summary.json")
    pendle_analysis_file = Path("pendle_morpho_analysis.json")

    max_age_hours = 6  # Data older than 6 hours is considered stale
    current_time = time.time()

    results = {}

    files_to_check = [
        (morpho_file, "Morpho"),
        (pendle_summary_file, "Pendle Summary"),
        (pendle_analysis_file, "Pendle Analysis")
    ]

    for file_path, name in files_to_check:
        if file_path.exists():
            file_age_hours = (current_time - file_path.stat().st_mtime) / 3600
            results[name] = {
                'exists': True,
                'fresh': file_age_hours < max_age_hours,
                'age_hours': file_age_hours
            }
        else:
            results[name] = {'exists': False, 'fresh': False, 'age_hours': None}

    return results

def main():
    parser = argparse.ArgumentParser(
        description="Morpho Blue Pool Analysis - Data Collection and Dashboard"
    )
    parser.add_argument(
        '--mode',
        choices=['collect', 'dashboard', 'full', 'check'],
        default='full',
        help='Operation mode: collect (data only), dashboard (launch only), full (both), check (check data)'
    )
    parser.add_argument(
        '--force-refresh',
        action='store_true',
        help='Force data collection even if recent data exists'
    )
    parser.add_argument(
        '--skip-pendle',
        action='store_true',
        help='Skip Pendle analysis (faster, but limited PT market insights)'
    )

    args = parser.parse_args()

    print("🔵 Morpho Blue Pool Analyzer")
    print("=" * 50)

    # Check dependencies first
    if not check_dependencies():
        sys.exit(1)

    if args.mode == 'check':
        print("\n📊 Checking data freshness...")
        freshness = check_data_freshness()

        for name, info in freshness.items():
            if info['exists']:
                status = "✓ Fresh" if info['fresh'] else "⚠ Stale"
                age = f"({info['age_hours']:.1f}h old)" if info['age_hours'] else ""
                print(f"{status} {name} data {age}")
            else:
                print(f"✗ No {name} data found")

        return

    # Check data freshness unless forcing refresh
    need_morpho_data = True
    need_pendle_data = not args.skip_pendle

    if not args.force_refresh:
        print("\n📊 Checking existing data...")
        freshness = check_data_freshness()

        if freshness['Morpho']['fresh']:
            print("✓ Fresh Morpho data found, skipping collection")
            need_morpho_data = False

        if freshness.get('Pendle Summary', {}).get('fresh') and freshness.get('Pendle Analysis', {}).get('fresh'):
            print("✓ Fresh Pendle data found, skipping collection")
            need_pendle_data = False

    # Data collection phase
    if args.mode in ['collect', 'full']:
        success = True

        if need_morpho_data:
            if not run_morpho_data_collection():
                print("⚠ Morpho data collection failed, dashboard may have limited functionality")
                success = False

        if need_pendle_data:
            if not run_pendle_analysis():
                print("⚠ Pendle analysis failed, PT market insights will be limited")

        if args.mode == 'collect':
            if success:
                print("\n✅ Data collection completed successfully!")
            else:
                print("\n⚠ Data collection completed with errors")
            return

    # Dashboard launch phase
    if args.mode in ['dashboard', 'full']:
        # Check if we have at least basic data
        if not Path("morpho_complete_analysis.json").exists():
            print("✗ No Morpho data found. Please run data collection first.")
            print("Usage: python run_analysis.py --mode collect")
            sys.exit(1)

        # Check for Pendle data (not required but recommended)
        has_pendle_summary = Path("pendle_morpho_summary.json").exists()
        has_pendle_analysis = Path("pendle_morpho_analysis.json").exists()

        if not has_pendle_summary and not has_pendle_analysis:
            print("ℹ️  Note: No Pendle data found. PT market analysis will be limited.")
            print("   Run: python run_analysis.py --mode collect (without --skip-pendle)")

        print("\n" + "=" * 50)
        print("Dashboard will open in your browser at: http://localhost:8501")
        print("Press Ctrl+C to stop the dashboard")
        print("=" * 50)

        time.sleep(2)  # Give user time to read
        launch_dashboard()

if __name__ == "__main__":
    main()
