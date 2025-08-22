#!/usr/bin/env python3
"""
Data Checker for Morpho Blue Pool Analyzer
Updated to handle exact JSON structures from the data collection scripts
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

def print_header(title: str):
    """Print a formatted header"""
    print("\n" + "=" * 70)
    print(f" {title}")
    print("=" * 70)

def print_section(title: str):
    """Print a formatted section header"""
    print(f"\n📋 {title}")
    print("-" * 50)

def format_timestamp(timestamp_str: str) -> str:
    """Format timestamp for display"""
    try:
        if 'T' in timestamp_str:
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d %H:%M:%S UTC')
        return timestamp_str
    except:
        return timestamp_str

def check_file_exists(file_path: str) -> tuple:
    """Check if file exists and return status and size"""
    path = Path(file_path)
    if path.exists():
        size_mb = path.stat().st_size / (1024 * 1024)
        return True, size_mb
    return False, 0

def load_json_safely(file_path: str) -> tuple:
    """Safely load JSON file and return data and error status"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data, None
    except json.JSONDecodeError as e:
        return None, f"JSON decode error: {e}"
    except Exception as e:
        return None, f"Error loading file: {e}"

def check_morpho_complete_analysis(data: Dict) -> Dict[str, Any]:
    """Analyze morpho_complete_analysis.json structure"""
    results = {
        'valid': True,
        'issues': [],
        'stats': {}
    }

    # Check metadata
    metadata = data.get('metadata', {})
    results['stats']['total_markets'] = metadata.get('totalMarkets', 'Missing')
    results['stats']['generated_at'] = metadata.get('generatedAt', 'Missing')
    results['stats']['data_structure'] = metadata.get('dataStructure', 'Missing')

    if not metadata:
        results['issues'].append("Missing metadata section")

    # Check data array
    market_data = data.get('data', [])
    if not market_data:
        results['valid'] = False
        results['issues'].append("No market data found in 'data' array")
        return results

    results['stats']['actual_markets'] = len(market_data)

    # Analyze markets
    valid_markets = 0
    pt_markets = 0
    borrower_counts = []
    markets_with_borrowers = 0
    markets_with_transactions = 0
    total_borrowers = 0

    for i, market_entry in enumerate(market_data):
        # Check market structure
        market = market_entry.get('market', {})
        if not market:
            results['issues'].append(f"Market {i}: Missing 'market' object")
            continue

        # Check required market fields
        unique_key = market.get('uniqueKey')
        loan_asset = market.get('loanAsset', {})
        collateral_asset = market.get('collateralAsset', {})

        if not unique_key:
            results['issues'].append(f"Market {i}: Missing uniqueKey")
            continue

        if not loan_asset.get('symbol') or not collateral_asset.get('symbol'):
            results['issues'].append(f"Market {i}: Missing asset symbols")
            continue

        valid_markets += 1

        # Check for PT tokens
        collateral_symbol = collateral_asset.get('symbol', '')
        if any(collateral_symbol.startswith(prefix) for prefix in ['PT-', 'pt-', 'PT_']):
            pt_markets += 1

        # Check state
        state = market.get('state', {})
        required_state_fields = ['borrowApy', 'totalLiquidityUsd', 'utilization']
        for field in required_state_fields:
            if field not in state:
                results['issues'].append(f"Market {i}: Missing state.{field}")

        # Check topBorrowers
        borrowers = market_entry.get('topBorrowers', [])
        borrower_count = len(borrowers)
        borrower_counts.append(borrower_count)
        total_borrowers += borrower_count

        if borrower_count > 0:
            markets_with_borrowers += 1

            # Check borrower structure
            for j, borrower in enumerate(borrowers[:3]):  # Check first 3 borrowers
                user = borrower.get('user', {})
                borrower_state = borrower.get('state', {})

                if not user.get('address'):
                    results['issues'].append(f"Market {i}, Borrower {j}: Missing user.address")

                if not borrower_state.get('borrowAssetsUsd'):
                    results['issues'].append(f"Market {i}, Borrower {j}: Missing state.borrowAssetsUsd")

                # Check transactions
                transactions = borrower.get('transactions', [])
                if transactions:
                    markets_with_transactions += 1

    results['stats']['valid_markets'] = valid_markets
    results['stats']['pt_markets'] = pt_markets
    results['stats']['markets_with_borrowers'] = markets_with_borrowers
    results['stats']['markets_with_transactions'] = markets_with_transactions
    results['stats']['total_borrowers'] = total_borrowers
    results['stats']['avg_borrowers_per_market'] = round(sum(borrower_counts) / len(borrower_counts), 2) if borrower_counts else 0

    if valid_markets == 0:
        results['valid'] = False
        results['issues'].append("No valid markets found")

    return results

def check_pendle_morpho_summary(data: Dict) -> Dict[str, Any]:
    """Analyze pendle_morpho_summary.json structure"""
    results = {
        'valid': True,
        'issues': [],
        'stats': {}
    }

    # Check overview
    overview = data.get('overview', {})
    if not overview:
        results['issues'].append("Missing 'overview' section")
    else:
        results['stats']['total_pt_markets_found'] = overview.get('totalPTMarketsFound', 'Missing')
        results['stats']['markets_with_pendle_data'] = overview.get('marketsWithPendleData', 'Missing')
        results['stats']['total_unique_borrowers'] = overview.get('totalUniqueBorrowers', 'Missing')
        results['stats']['total_borrowers_analyzed'] = overview.get('totalBorrowerAnalyzed', 'Missing')

    # Check PT markets
    pt_markets = data.get('ptMarkets', [])
    results['stats']['pt_markets_array_length'] = len(pt_markets)

    if not pt_markets and overview.get('totalPTMarketsFound', 0) > 0:
        results['issues'].append("ptMarkets array is empty despite overview indicating markets exist")

    # Analyze PT markets structure
    markets_with_valid_data = 0
    for i, market in enumerate(pt_markets[:5]):  # Check first 5
        required_fields = ['pair', 'ptTokenName', 'ptTokenAddress', 'morphoLiquidity']
        for field in required_fields:
            if field not in market:
                results['issues'].append(f"PT Market {i}: Missing '{field}'")
            elif market.get('hasPendleData'):
                markets_with_valid_data += 1

    results['stats']['markets_with_valid_data'] = markets_with_valid_data

    # Check topBorrowersByMarket
    borrower_data = data.get('topBorrowersByMarket', {})
    results['stats']['markets_with_borrower_data'] = len(borrower_data)

    # Check structure of borrower data
    sample_markets = list(borrower_data.keys())[:3]  # Check first 3 markets
    for market_key in sample_markets:
        borrowers = borrower_data[market_key]
        if not isinstance(borrowers, list):
            results['issues'].append(f"Market '{market_key}': borrowers should be an array")
            continue

        for j, borrower in enumerate(borrowers[:2]):  # Check first 2 borrowers
            required_borrower_fields = ['address', 'borrowAmountUsd', 'collateralUsd', 'healthFactor']
            for field in required_borrower_fields:
                if field not in borrower:
                    results['issues'].append(f"Market '{market_key}', Borrower {j}: Missing '{field}'")

    if len(pt_markets) == 0 and overview.get('totalPTMarketsFound', 0) == 0:
        results['issues'].append("No PT markets found - may indicate Pendle integration issues")

    return results

def check_pendle_morpho_analysis(data: Dict) -> Dict[str, Any]:
    """Analyze pendle_morpho_analysis.json structure"""
    results = {
        'valid': True,
        'issues': [],
        'stats': {}
    }

    # Check metadata
    metadata = data.get('metadata', {})
    if not metadata:
        results['issues'].append("Missing 'metadata' section")
    else:
        results['stats']['total_pt_markets'] = metadata.get('totalPTMarkets', 'Missing')
        results['stats']['total_borrowers'] = metadata.get('totalBorrowers', 'Missing')
        results['stats']['generated_at'] = metadata.get('generatedAt', 'Missing')
        results['stats']['description'] = metadata.get('description', 'Missing')

    # Check ptMarketsData
    pt_markets_data = data.get('ptMarketsData', {})
    results['stats']['detailed_pt_markets'] = len(pt_markets_data)

    if not pt_markets_data:
        results['issues'].append("Missing or empty 'ptMarketsData'")
    else:
        # Analyze market data structure
        markets_with_morpho = 0
        markets_with_pendle = 0
        markets_with_details = 0
        markets_with_history = 0

        sample_markets = list(pt_markets_data.keys())[:3]  # Check first 3
        for market_key in sample_markets:
            market_data = pt_markets_data[market_key]

            # Check morphoMarket
            if 'morphoMarket' in market_data:
                markets_with_morpho += 1
                morpho_market = market_data['morphoMarket']
                if not morpho_market.get('uniqueKey'):
                    results['issues'].append(f"Market {market_key}: morphoMarket missing uniqueKey")

            # Check pendleMarket
            if 'pendleMarket' in market_data:
                markets_with_pendle += 1
                pendle_market = market_data['pendleMarket']
                if not pendle_market.get('address'):
                    results['issues'].append(f"Market {market_key}: pendleMarket missing address")

            # Check marketDetails
            if 'marketDetails' in market_data:
                markets_with_details += 1
                market_details = market_data['marketDetails']
                important_fields = ['impliedApy', 'aggregatedApy', 'liquidity']
                for field in important_fields:
                    if field not in market_details:
                        results['issues'].append(f"Market {market_key}: marketDetails missing {field}")

            # Check marketHistory
            if 'marketHistory' in market_data:
                markets_with_history += 1

        results['stats']['markets_with_morpho_data'] = markets_with_morpho
        results['stats']['markets_with_pendle_data'] = markets_with_pendle
        results['stats']['markets_with_details'] = markets_with_details
        results['stats']['markets_with_history'] = markets_with_history

    # Check borrowerPositions
    borrower_positions = data.get('borrowerPositions', {})
    results['stats']['borrowers_with_positions'] = len(borrower_positions)

    if borrower_positions:
        # Analyze borrower position structure
        borrowers_with_morpho = 0
        borrowers_with_pendle = 0

        sample_borrowers = list(borrower_positions.keys())[:3]  # Check first 3
        for borrower_addr in sample_borrowers:
            borrower_data = borrower_positions[borrower_addr]

            # Each borrower can have multiple market positions
            for market_key, market_position in borrower_data.items():
                if isinstance(market_position, dict):
                    if 'morphoBorrowerData' in market_position:
                        borrowers_with_morpho += 1

                    if 'pendlePositions' in market_position:
                        borrowers_with_pendle += 1
                        pendle_pos = market_position['pendlePositions']
                        if 'positions' not in pendle_pos:
                            results['issues'].append(f"Borrower {borrower_addr}: pendlePositions missing 'positions' array")

        results['stats']['borrowers_with_morpho_data'] = borrowers_with_morpho
        results['stats']['borrowers_with_pendle_data'] = borrowers_with_pendle

    # Check originalMorphoMarkets
    original_markets = data.get('originalMorphoMarkets', [])
    results['stats']['original_markets_count'] = len(original_markets)

    if len(pt_markets_data) == 0:
        results['issues'].append("No detailed PT market data found")

    return results

def main():
    print_header("Morpho Blue Pool Analyzer - Data Structure Checker")

    files_to_check = [
        ("morpho_complete_analysis.json", "Morpho Complete Analysis", check_morpho_complete_analysis),
        ("pendle_morpho_summary.json", "Pendle Summary", check_pendle_morpho_summary),
        ("pendle_morpho_analysis.json", "Pendle Analysis", check_pendle_morpho_analysis)
    ]

    all_files_ok = True
    file_statuses = {}

    # Check all files
    for file_path, file_desc, analyzer_func in files_to_check:
        print_section(f"Checking {file_desc}")

        # Check if file exists
        exists, size_mb = check_file_exists(file_path)

        if not exists:
            print(f"❌ File not found: {file_path}")
            print(f"   Generate with: node get_morpho_data.js" if "morpho" in file_path.lower() else "   Generate with: node pendle_morpho_analyzer.js")
            all_files_ok = False
            file_statuses[file_desc] = False
            continue

        print(f"✅ File exists: {file_path} ({size_mb:.2f} MB)")

        # Load and validate JSON
        data, error = load_json_safely(file_path)

        if error:
            print(f"❌ {error}")
            all_files_ok = False
            file_statuses[file_desc] = False
            continue

        print(f"✅ Valid JSON structure")

        # Run specific analysis
        if analyzer_func:
            results = analyzer_func(data)

            # Display statistics
            if results['stats']:
                print(f"\n📊 Data Statistics:")
                for key, value in results['stats'].items():
                    formatted_key = key.replace('_', ' ').title()
                    if key.endswith('_at') and isinstance(value, str) and value != 'Missing':
                        value = format_timestamp(value)
                    print(f"   • {formatted_key}: {value}")

            # Display issues
            if results['issues']:
                print(f"\n⚠️  Issues Found:")
                for issue in results['issues']:
                    print(f"   • {issue}")
                if len(results['issues']) > 5:
                    print(f"   ... and {len(results['issues']) - 5} more issues")
                all_files_ok = False
            else:
                print(f"\n✅ No structural issues found")

            file_statuses[file_desc] = results['valid'] and len(results['issues']) == 0
        else:
            file_statuses[file_desc] = True

    # Summary and recommendations
    print_header("Dashboard Readiness Assessment")

    morpho_ready = file_statuses.get("Morpho Complete Analysis", False)
    pendle_summary_ready = file_statuses.get("Pendle Summary", False)
    pendle_analysis_ready = file_statuses.get("Pendle Analysis", False)

    print("📋 File Status Summary:")
    for desc, status in file_statuses.items():
        status_icon = "✅" if status else "❌"
        print(f"   {status_icon} {desc}")

    print(f"\n🎯 Dashboard Capabilities:")
    if morpho_ready:
        print("   ✅ Basic Pool Analysis: Available")
        print("   ✅ Borrower Analysis: Available")
        print("   ✅ APY Calculations: Available")
    else:
        print("   ❌ Basic Pool Analysis: Not Available")
        return

    if pendle_summary_ready or pendle_analysis_ready:
        print("   ✅ PT Market Analysis: Available")
        print("   ✅ Pendle Integration: Available")
    else:
        print("   ⚠️  PT Market Analysis: Limited (no Pendle data)")

    if pendle_analysis_ready:
        print("   ✅ Advanced PT Analytics: Available")
        print("   ✅ Borrower Position Tracking: Available")
    else:
        print("   ⚠️  Advanced PT Analytics: Limited")

    # Launch recommendations
    print(f"\n🚀 Launch Recommendations:")
    if morpho_ready:
        print("   ✅ Ready to launch dashboard!")
        print("   📝 Launch commands:")
        print("      python start_dashboard.py")
        print("      # or #")
        print("      streamlit run morpho_dashboard.py")

        if not (pendle_summary_ready or pendle_analysis_ready):
            print("\n   💡 To enable full PT market analysis:")
            print("      node pendle_morpho_analyzer.js")
    else:
        print("   📝 Setup required:")
        print("   1. Generate Morpho data: node get_morpho_data.js")
        if not (pendle_summary_ready or pendle_analysis_ready):
            print("   2. Generate Pendle data: node pendle_morpho_analyzer.js")
        print("   3. Re-run this checker: python check_data.py")
        print("   4. Launch dashboard: python start_dashboard.py")

    print(f"\n{'='*70}")

if __name__ == "__main__":
    main()
