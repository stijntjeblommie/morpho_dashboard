import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import numpy as np
import os
import csv
from typing import Dict, List, Optional, Tuple
import json

# Try to import networkx for network graphs
try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False
    nx = None

CHAIN_CONFIG = {
    1: {'name': 'ethereum', 'explorer_base': 'https://etherscan.io'},
    8453: {'name': 'base', 'explorer_base': 'https://basescan.org'},
    137: {'name': 'polygon', 'explorer_base': 'https://polygonscan.com'},
    42161: {'name': 'arbitrum', 'explorer_base': 'https://arbiscan.io'},
    # Katana and Unichain would be added here with their respective chain IDs.
}
DEFAULT_CHAIN_ID = 1
DEFAULT_CHAIN_INFO = CHAIN_CONFIG[DEFAULT_CHAIN_ID]

# ======================================================
# Configuration
# ======================================================

APP_TITLE = "🔵 Morpho Blue + Pendle PT Analytics"
APP_SUBTITLE = "Advanced yield looping opportunity analysis with transaction flows"
CSV_FILE = "data.csv"

# ======================================================
# Utility Functions
# ======================================================

def safe_get(d: Optional[dict], keys: List, default=None):
    """Safely access nested dictionary values"""
    if not d or not isinstance(d, dict):
        return default
    current = d
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current

def safe_float(value, default: float = 0.0) -> float:
    """Safely convert value to float"""
    if pd.isna(value) or value == '' or value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def format_usd(value) -> str:
    """Format USD values with appropriate suffixes"""
    try:
        val = float(value) if value is not None and value != '' else 0.0
    except (ValueError, TypeError):
        return "$0"

    if pd.isna(val) or val == 0:
        return "$0"

    if abs(val) >= 1_000_000:
        return f"${val / 1_000_000:.1f}M"
    elif abs(val) >= 1_000:
        return f"${val / 1_000:.1f}K"
    else:
        return f"${val:.2f}"

def format_percentage(value: Optional[float]) -> str:
    """Format percentage values"""
    if value is None or pd.isna(value):
        return "—"
    return f"{value:.2f}%"

def is_pt_token(symbol) -> bool:
    """Check if symbol is a Pendle PT token"""
    if not symbol or pd.isna(symbol):
        return False
    symbol_str = str(symbol)
    return symbol_str.startswith('PT-') or 'PT' in symbol_str.upper()

def estimate_external_yield(symbol) -> Optional[float]:
    """Estimate external yield for non-PT tokens"""
    if not symbol or pd.isna(symbol):
        return None
    yield_estimates = {
        'WETH': 3.5, 'ETH': 3.5, 'USDC': 4.5, 'USDT': 4.2, 'DAI': 4.0,
        'WSTETH': 4.2, 'RETH': 4.1, 'CBETH': 3.8,
    }
    return yield_estimates.get(str(symbol).upper())

# ======================================================
# Data Loading
# ======================================================

def load_csv_data() -> Dict[str, pd.DataFrame]:
    """Load all sheets from the multi-section CSV file into DataFrames"""
    try:
        if not os.path.exists(CSV_FILE):
            st.error(f"CSV file '{CSV_FILE}' not found!")
            return {}

        sheets = {}
        current_sheet = None
        current_data = []
        headers = []

        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                if line.startswith('# sheet:'):
                    # Save previous sheet if it exists
                    if current_sheet and current_data and headers:
                        try:
                            df = pd.DataFrame(current_data, columns=headers)
                            sheets[current_sheet] = df
                        except Exception:
                            pass

                    # Start new sheet
                    current_sheet = line.replace('# sheet:', '').strip()
                    current_data = []
                    headers = []
                    continue

                if line.startswith('#'):
                    continue

                # Parse CSV line
                try:
                    reader = csv.reader([line], quotechar='"', quoting=csv.QUOTE_MINIMAL)
                    row = next(reader)

                    if not headers and current_sheet:
                        headers = row
                        if '__sheet' in headers:
                            headers.remove('__sheet')
                    elif headers and current_sheet:
                        if len(row) > len(headers):
                            row = row[1:]  # Assume first column is __sheet
                        while len(row) < len(headers):
                            row.append('')
                        row = row[:len(headers)]
                        current_data.append(row)
                except Exception:
                    continue

        # Save last sheet
        if current_sheet and current_data and headers:
            try:
                df = pd.DataFrame(current_data, columns=headers)
                sheets[current_sheet] = df
            except Exception:
                pass

        return sheets
    except Exception as e:
        st.error(f"Error loading CSV file: {str(e)}")
        return {}

# ======================================================
# Routing Functions
# ======================================================

def set_route(**params):
    """Set URL parameters for navigation using session state"""
    for key, value in params.items():
        if value is not None:
            if isinstance(value, list):
                st.session_state[f"route_{key}"] = value[0] if value else None
            else:
                st.session_state[f"route_{key}"] = str(value)
        else:
            st.session_state[f"route_{key}"] = None

def get_route() -> Dict[str, List[str]]:
    """Get current URL parameters from session state"""
    route = {}
    for key in st.session_state:
        if key.startswith("route_"):
            param_key = key[6:]  # Remove 'route_' prefix
            value = st.session_state[key]
            route[param_key] = [value] if value is not None else [None]
    return route

# ======================================================
# Data Processing Functions
# ======================================================

def build_pools_df(sheets: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Build main pools dataframe from loaded sheets"""
    if 'morpho_markets' not in sheets:
        return pd.DataFrame()

    markets_df = sheets['morpho_markets'].copy()
    pendle_matches = sheets.get('pendle_pt_matches', pd.DataFrame())
    pendle_data = sheets.get('pendle_market_data', pd.DataFrame())

    rows = []

    for _, market in markets_df.iterrows():
        # Basic market info
        unique_key = market.get('uniqueKey', '')
        loan_symbol = market.get('loanAsset.symbol', '—')
        coll_symbol = market.get('collateralAsset.symbol', '—')

        # Financial metrics
        borrow_apy = safe_float(market.get('state.dailyBorrowApy', 0)) * 100
        supply_assets = safe_float(market.get('state.supplyAssetsUsd', 0))
        borrow_assets = safe_float(market.get('state.borrowAssetsUsd', 0))
        utilization = safe_float(market.get('state.utilization', 0)) * 100
        lltv = safe_float(market.get('lltv', 0))/10e15
        available_borrow = max(supply_assets - borrow_assets, 0)

        # Check if PT market and get implied APY
        is_pt_market = is_pt_token(coll_symbol)
        implied_apy = None
        pendle_link = None

        if is_pt_market and not pendle_data.empty and not pendle_matches.empty:
            match = pendle_matches[pendle_matches['marketUniqueKey'] == unique_key]
            if not match.empty:
                pendle_address = match.iloc[0].get('pendleMarketAddress', '')
                pendle_market_data = pendle_data[pendle_data['pendleMarketAddress'] == pendle_address]
                if not pendle_market_data.empty:
                    implied_apy = safe_float(pendle_market_data.iloc[0].get('marketData.impliedApy', 0)) * 100
                    pendle_link = f"https://app.pendle.finance/trade/markets/{pendle_address}/swap?view=pt&chain=ethereum"

        # Use external yield estimate if not PT market
        if implied_apy is None:
            implied_apy = estimate_external_yield(coll_symbol)

        # Calculate spread and status
        spread = None
        status = "⚪ Neutral"
        if borrow_apy and implied_apy:
            spread = implied_apy - borrow_apy
            if spread > 5:
                status = "🟢 High Opportunity"
            elif spread > 0:
                status = "🟡 Moderate Opportunity"
            else:
                status = "🔴 Unprofitable"

        rows.append({
            'Pool': f"{coll_symbol} / {loan_symbol}",
            'Collateral Asset': coll_symbol,
            'Borrow Asset': loan_symbol,
            'Supply Assets ($M)': supply_assets / 1_000_000,
            'Available Borrow ($M)': available_borrow / 1_000_000,
            'Morpho Borrow APY (%)': borrow_apy,
            'PT/External APY (%)': implied_apy,
            'Net APY Spread (%)': spread,
            'Status': status,
            'Utilization (%)': utilization,
            'LLTV (%)': lltv,
            'Is PT Market': is_pt_market,
            'Unique Key': unique_key,
            'Morpho Link': f"https://app.morpho.org/ethereum/market/{unique_key}", #note hardcoded to ethereum
            'Pendle Link': pendle_link,
        })

    return pd.DataFrame(rows)

def build_curators_df(sheets: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Build curators dataframe with enhanced vault mapping"""
    if 'morpho_curators' not in sheets:
        return pd.DataFrame()

    curators_df = sheets['morpho_curators'].copy()
    vaults_df = sheets.get('morpho_vaults', pd.DataFrame())
    rows = []

    for _, curator in curators_df.iterrows():
        # Parse socials for URL
        socials_str = curator.get('socials', '{}')
        socials_dict = {} # Initialize an empty dictionary to hold the results

        if socials_str and isinstance(socials_str, str):
            try:
                # First, try to parse the string as JSON
                parsed_data = json.loads(socials_str)
                if isinstance(parsed_data, dict):
                    socials_dict = parsed_data

            except (json.JSONDecodeError, TypeError):
                # If it's not JSON, parse the pipe-separated "key:value" format
                social_entries = socials_str.split('|')
                for entry in social_entries:
                    # Split each entry on the first colon to separate key from value
                    parts = entry.split(':', 1)
                    if len(parts) == 2:
                        # Assign to the dictionary, stripping any extra whitespace
                        key = parts[0].strip()
                        value = parts[1].strip()
                        socials_dict[key] = value


        morpho_url = socials_dict.get('forum', '')
        morpho_twitter = socials_dict.get('twitter', '')
        morpho_main = socials_dict.get('url', '')

        # Get AUM directly from the curator data, but also calculate from vaults
        curator_address = curator.get('addresses', '')
        curator_name = curator.get('name', 'Unknown')
        aum_from_sheet = safe_float(curator.get('aum', 0))

        # Calculate AUM from managed vaults using enhanced curator name matching
        vault_aum = 0
        managed_vaults = []
        if not vaults_df.empty and curator_name:
            # First build the vaults dataframe to get processed data
            processed_vaults = build_vaults_df({'morpho_vaults': vaults_df})
            if not processed_vaults.empty:
                # Match by curator name in the list of curator names
                curator_vaults = processed_vaults[
                    processed_vaults['Curator Names List'].apply(
                        lambda x: curator_name in x if isinstance(x, list) else False
                    )
                ]
                if curator_vaults.empty and curator_address:
                    # Fallback to address matching
                    curator_vaults = processed_vaults[processed_vaults['Curator'] == curator_address]

                if not curator_vaults.empty:
                    # Remove duplicate vaults by address
                    curator_vaults_unique = curator_vaults.drop_duplicates(subset=['Address'])
                    vault_aum = curator_vaults_unique['TVL'].sum()
                    managed_vaults = curator_vaults_unique[['Vault', 'TVL', 'APY', 'Address']].to_dict('records')

        # Use the higher value between sheet AUM and calculated vault AUM
        total_aum = max(aum_from_sheet, vault_aum)

        rows.append({
            'Curator': curator.get('name', 'Unknown'),
            'Address': curator_address,
            'Total AUM': total_aum,
            'Vault Count': len(managed_vaults),
            'Managed Vaults': managed_vaults,
            'Morpho URL': morpho_url,
            'twitter': morpho_twitter,
            'main': morpho_main
        })

    df = pd.DataFrame(rows)
    # Sort by descending AUM and filter out zero AUM curators
    if not df.empty:
        df = df[df['Total AUM'] > 0]  # Only show curators with AUM > 0
        df = df.sort_values('Total AUM', ascending=False)
    return df

def build_vaults_df(sheets: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Build vaults dataframe"""
    if 'morpho_vaults' not in sheets:
        return pd.DataFrame()

    vaults_df = sheets['morpho_vaults'].copy()
    rows = []
    assets = 0
    for _, vault in vaults_df.iterrows():
        # Parse curator names from JSON list format
        curator_names = []
        curators_str = vault.get('state.curators', '')
        assets_str = vault.get('state.totalAssetsUsd', "0") # Get the string value

        assets_value = 0.0 # Default to 0.0
        try:
            assets_value = float(str(assets_str).replace('$', '').replace(',', ''))
        except (ValueError, TypeError):
            pass
        try:
            if curators_str and assets_value >= 50:
                curators_data = json.loads(curators_str) if isinstance(curators_str, str) else curators_str
                if isinstance(curators_data, list):
                    curator_names = [c.get('name', '') for c in curators_data if isinstance(c, dict)]
        except:
            pass

        curator_name_str = ', '.join(curator_names) if curator_names else ''

        rows.append({
            'Vault': vault.get('name', 'Unknown'),
            'Symbol': vault.get('symbol', '—'),
            'Address': vault.get('address', ''),
            'TVL': safe_float(vault.get('state.totalAssetsUsd', 0)),
            'APY': safe_float(vault.get('state.dailyApy', 0)) * 100,
            'Fee': safe_float(vault.get('state.fee', 0)) * 100,
            'Asset': vault.get('asset.symbol', '—'),
            'Curator': vault.get('state.curator', ''),
            'Curator Name': curator_name_str,
            'Curator Names List': curator_names,
            'Whitelisted': vault.get('whitelisted', False),
        })

    return pd.DataFrame(rows)

def get_top_borrowers(sheets: Dict[str, pd.DataFrame], unique_key: str) -> pd.DataFrame:
    """Get top borrowers for a specific market"""
    if 'morpho_top_borrowers' not in sheets:
        return pd.DataFrame()

    borrowers_df = sheets['morpho_top_borrowers']
    market_borrowers = borrowers_df[borrowers_df['marketUniqueKey'] == unique_key].copy()

    if market_borrowers.empty:
        return pd.DataFrame()

    # Add calculated columns
    market_borrowers['Collateral USD'] = [safe_float(x) for x in market_borrowers['state.collateralUsd']]
    market_borrowers['Borrow USD'] = [safe_float(x) for x in market_borrowers['state.borrowAssetsUsd']]
    market_borrowers['Health Factor'] = [safe_float(x) for x in market_borrowers['healthFactor']]
    market_borrowers['PnL USD'] = [safe_float(x) for x in market_borrowers['state.pnlUsd']]
    market_borrowers['Morpho PnL'] = [safe_float(x) for x in market_borrowers['state.marginPnlUsd']]

    return market_borrowers[['userAddress', 'Collateral USD', 'Borrow USD', 'Health Factor', 'PnL USD', 'Morpho PnL']].head(5)

def process_positions_for_display(raw_positions_json: str):
    """
    Processes the raw JSON and returns aggregated stats and a detailed DataFrame.

    Returns:
        A tuple containing:
        1. A dictionary of aggregated stats (for metrics and charts).
        2. A pandas DataFrame with details of each open position.
    """
    aggregated_stats = {
        'total_pt_value': 0,
        'total_yt_value': 0,
        'total_lp_value': 0,
        'total_open_value': 0,
        'position_count': 0,
    }
    detailed_positions = []

    if not isinstance(raw_positions_json, str):
        return aggregated_stats, pd.DataFrame(detailed_positions)

    try:
        data = json.loads(raw_positions_json)
    except json.JSONDecodeError:
        return aggregated_stats, pd.DataFrame(detailed_positions)

    for chain_data in data:
        for pos in chain_data.get('openPositions', []):
            pt_val = pos.get('pt', {}).get('valuation', 0)
            yt_val = pos.get('yt', {}).get('valuation', 0)
            lp_val = pos.get('lp', {}).get('valuation', 0)
            position_total = pt_val + yt_val + lp_val

            if position_total > 0:
                # Add to aggregates
                aggregated_stats['total_pt_value'] += pt_val
                aggregated_stats['total_yt_value'] += yt_val
                aggregated_stats['total_lp_value'] += lp_val
                aggregated_stats['position_count'] += 1

                # Add to detailed list for the DataFrame
                detailed_positions.append({
                    "Market ID": pos.get('marketId', 'N/A'),
                    "PT Value": pt_val,
                    "YT Value": yt_val,
                    "LP Value": lp_val,
                    "Total Value": position_total
                })

    aggregated_stats['total_open_value'] = (
        aggregated_stats['total_pt_value'] +
        aggregated_stats['total_yt_value'] +
        aggregated_stats['total_lp_value']
    )

    return aggregated_stats, pd.DataFrame(detailed_positions)

def get_pendle_positions(sheets: Dict[str, pd.DataFrame], user_address: str, unique_key: str) -> pd.DataFrame:
    """
    Get Pendle positions for a specific user and calculate the total valuation from raw.positions.
    """
    if 'pendle_user_positions' not in sheets:
        return pd.DataFrame()

    positions_df = sheets['pendle_user_positions']
    user_positions = positions_df[
        (positions_df['userAddress'] == user_address) &
        (positions_df['marketUniqueKey'] == unique_key)
    ].copy()

    if user_positions.empty or 'raw.positions' not in user_positions.columns:
        return user_positions

    def calculate_total_valuation(positions_json_str: str) -> float:
        """
        Parses a JSON string from a single row and calculates the sum of all open valuations.
        """
        total_valuation = 0.0
        # Handle cases where the cell might be empty or not a valid JSON string
        if not isinstance(positions_json_str, str):
            return 0.0

        try:
            data = json.loads(positions_json_str)
        except json.JSONDecodeError:
            return 0.0

        # The JSON data is a list of chains
        for chain_data in data:
            # Loop through each open position in the chain
            for position in chain_data.get('openPositions', []):
                pt_valuation = position.get('pt', {}).get('valuation', 0)
                yt_valuation = position.get('yt', {}).get('valuation', 0)
                lp_valuation = position.get('lp', {}).get('valuation', 0)
                total_valuation += pt_valuation + yt_valuation + lp_valuation

        return total_valuation

    # Correctly apply the function to each row in the 'raw.positions' column
    user_positions['totalBalance'] = user_positions['raw.positions'].apply(calculate_total_valuation)

    return user_positions

def get_user_transactions(sheets: Dict[str, pd.DataFrame], unique_key: str, user_address: str = None) -> pd.DataFrame:
    """Get transaction history for market or specific user"""
    if 'morpho_user_transactions' not in sheets:
        return pd.DataFrame()

    tx_df = sheets['morpho_user_transactions']
    market_txs = tx_df[tx_df['marketUniqueKey'] == unique_key].copy()

    if user_address:
        market_txs = market_txs[market_txs['userAddress'] == user_address]

    if market_txs.empty:
        return pd.DataFrame()

    # Process transactions
    market_txs['USD Value'] = [safe_float(x) for x in market_txs['data.assetsUsd']]
    market_txs['Assets'] = [safe_float(x) for x in market_txs['data.assets']]
    market_txs['Timestamp'] = pd.to_datetime(market_txs['timestamp'], unit='s', errors='coerce')

    return market_txs

def calculate_borrower_pnl(sheets: Dict[str, pd.DataFrame], unique_key: str, user_address: str, pool_info: Dict) -> float:
    """Calculate estimated PnL using leverage and looping calculations"""
    tx_df = get_user_transactions(sheets, unique_key, user_address)
    if tx_df.empty:
        return 0.0

    # Calculate net positions
    supply_total = tx_df[tx_df['type'].astype(str).str.contains('supply', case=False, na=False)]['USD Value'].sum()
    borrow_total = tx_df[tx_df['type'].astype(str).str.contains('borrow', case=False, na=False)]['USD Value'].sum()
    repay_total = tx_df[tx_df['type'].astype(str).str.contains('repay', case=False, na=False)]['USD Value'].sum()
    withdraw_total = tx_df[tx_df['type'].astype(str).str.contains('withdraw', case=False, na=False)]['USD Value'].sum()

    net_supplied = supply_total - withdraw_total
    net_borrowed = borrow_total - repay_total

    if net_supplied <= 0 or net_borrowed <= 0:
        return 0.0

    # Calculate leverage: L = total_collateral / net_deposits
    leverage = net_supplied / max(net_supplied - net_borrowed, 1)

    # Get APY values
    implied_apy = pool_info.get('PT/External APY (%)', 0) / 100
    borrow_apy = pool_info.get('Morpho Borrow APY (%)', 0) / 100

    if leverage <= 1 or implied_apy == 0:
        return 0.0

    # Calculate net APR: L × Y - (L-1) × B
    net_apr = leverage * implied_apy - (leverage - 1) * borrow_apy

    # Estimate PnL based on position size and time
    position_size = net_supplied - net_borrowed
    estimated_pnl = position_size * net_apr

    return estimated_pnl

def get_vault_depositors(sheets: Dict[str, pd.DataFrame], vault_address: str) -> pd.DataFrame:
    """Get depositors for a specific vault"""
    if 'morpho_vault_top_depositors' not in sheets:
        return pd.DataFrame()

    depositors_df = sheets['morpho_vault_top_depositors']
    vault_depositors = depositors_df[depositors_df['vaultAddress'] == vault_address].copy()

    if vault_depositors.empty:
        return pd.DataFrame()

    # Process depositor amounts and transactions
    processed_depositors = []
    for _, depositor in vault_depositors.iterrows():
        user_addr = depositor['userAddress']
        raw_amount = safe_float(depositor.get('assetsUsd', 0))

        # Parse user transactions to get actual amounts if raw amount is 0
        transactions_str = depositor.get('userTransactions', '[]')
        calculated_amount = 0
        transaction_data = []

        try:
            if isinstance(transactions_str, str):
                transactions = json.loads(transactions_str)
            else:
                transactions = transactions_str if isinstance(transactions_str, list) else []

            for tx in transactions:
                if isinstance(tx, dict):
                    tx_hash = tx.get('hash', '')
                    tx_type = tx.get('type', '')
                    tx_timestamp = tx.get('timestamp', 0)
                    tx_data = tx.get('data', {})
                    tx_amount = safe_float(tx_data.get('assetsUsd', 0))

                    transaction_data.append({
                        'hash': tx_hash,
                        'type': tx_type,
                        'timestamp': tx_timestamp,
                        'amount_usd': tx_amount
                    })

                    # Sum deposits for calculated amount
                    if 'deposit' in tx_type.lower() or tx_amount > 0:
                        calculated_amount += tx_amount
        except:
            pass

        # Use calculated amount if raw amount is 0 or very small
        final_amount = calculated_amount if raw_amount < 1000 and calculated_amount > raw_amount else raw_amount

        processed_depositors.append({
            'userAddress': user_addr,
            'Assets USD': final_amount,
            'Raw Amount': raw_amount,
            'Calculated Amount': calculated_amount,
            'Transactions': transaction_data,
            'Transaction Count': len(transaction_data)
        })

    result_df = pd.DataFrame(processed_depositors)
    return result_df.sort_values('Assets USD', ascending=False).head(10)

def get_vault_depositors_by_curator(sheets: Dict[str, pd.DataFrame], curator_name: str) -> pd.DataFrame:
    """Get top depositors for all vaults managed by a specific curator"""
    if 'morpho_vault_top_depositors' not in sheets or 'morpho_vaults' not in sheets:
        return pd.DataFrame()

    depositors_df = sheets['morpho_vault_top_depositors']
    vaults_df = build_vaults_df(sheets)

    # Get vaults managed by this curator
    curator_vaults = vaults_df[
        vaults_df['Curator Names List'].apply(
            lambda x: curator_name in x if isinstance(x, list) else False
        )
    ]

    # Remove duplicate vaults
    curator_vaults = curator_vaults.drop_duplicates(subset=['Address'])

    if curator_vaults.empty:
        return pd.DataFrame()

    curator_vault_addresses = curator_vaults['Address'].tolist()

    # Filter depositors for curator's vaults
    curator_depositors = depositors_df[
        depositors_df['vaultAddress'].isin(curator_vault_addresses)
    ].copy()

    if curator_depositors.empty:
        return pd.DataFrame()

    # Add vault names
    vault_name_map = dict(zip(curator_vaults['Address'], curator_vaults['Vault']))
    curator_depositors['Vault Name'] = curator_depositors['vaultAddress'].map(vault_name_map)

    return curator_depositors.sort_values('assetsUsd', ascending=False).head(20)

def parse_historical_apy_data(historical_data_str: str) -> pd.DataFrame:
    """Parse historical APY data from JSON string format"""
    try:
        if not historical_data_str or historical_data_str == '':
            return pd.DataFrame()

        # Parse the JSON string
        data = json.loads(historical_data_str) if isinstance(historical_data_str, str) else historical_data_str

        if isinstance(data, list):
            df_data = []
            for point in data:
                if isinstance(point, dict) and 'x' in point and 'y' in point:
                    timestamp = point['x']
                    apy = point['y']
                    # Convert timestamp to datetime
                    date = pd.to_datetime(timestamp, unit='s')
                    df_data.append({
                        'date': date,
                        'apy': float(apy) * 100,  # Convert to percentage
                        'timestamp': timestamp
                    })

            return pd.DataFrame(df_data).sort_values('date')
    except Exception as e:
        st.error(f"Error parsing historical APY data: {str(e)}")

    return pd.DataFrame()

def get_pendle_yield_data(sheets: Dict[str, pd.DataFrame], market_key: str) -> pd.DataFrame:
    """
    Gets Pendle historical APY by reading the flattened 'point.*' columns 
    from the 'pendle_market_history' sheet.
    """
    # Ensure the necessary sheets are loaded
    if 'pendle_pt_matches' not in sheets or 'pendle_market_history' not in sheets:
        return pd.DataFrame()

    matches_df = sheets['pendle_pt_matches']
    history_df = sheets['pendle_market_history']

    # Step 1: Find the Pendle Market Address (this is unchanged)
    match = matches_df[matches_df['marketUniqueKey'] == market_key]
    if match.empty:
        return pd.DataFrame()
    pendle_address = match.iloc[0].get('pendleMarketAddress')
    if not pendle_address:
        return pd.DataFrame()

    # Step 2: Filter the history for the correct market (this is unchanged)
    market_history = history_df[history_df['pendleMarketAddress'] == pendle_address].copy()
    if market_history.empty:
        return pd.DataFrame()

    # --- CORRECTED LOGIC STARTS HERE ---

    # Step 3: Check if the required flattened columns exist.
    if 'point.timestamp' not in market_history.columns or 'point.apy' not in market_history.columns:
        st.warning("Pendle history data is missing the expected 'point.timestamp' or 'point.apy' columns.")
        return pd.DataFrame()

    # Step 4: Create the final DataFrame directly from the flattened columns.
    # No more JSON parsing is needed.
    pendle_df = market_history[['point.timestamp', 'point.apy']].copy()
    
    # Rename columns for consistency
    pendle_df.rename(columns={'point.timestamp': 'timestamp', 'point.apy': 'apy'}, inplace=True)

    # Convert to the correct data types for plotting
    pendle_df['date'] = pd.to_datetime(pendle_df['timestamp'], unit='s', errors='coerce')
    pendle_df['apy'] = pd.to_numeric(pendle_df['apy'], errors='coerce') * 100 # Convert to percentage

    # Drop any rows where conversion might have failed
    pendle_df.dropna(subset=['date', 'apy'], inplace=True)

    if pendle_df.empty:
        return pd.DataFrame()

    return pendle_df[['date', 'apy']].sort_values('date')

def create_depositor_distribution_chart(depositors_df: pd.DataFrame) -> go.Figure:
    """Create depositor distribution pie chart"""
    if depositors_df.empty:
        return go.Figure()

    fig = px.pie(
        values=depositors_df['Assets USD'],
        names=[f"{addr[:10]}..." for addr in depositors_df['userAddress']],
        title="Depositor Distribution by Amount"
    )
    fig.update_layout(height=400)
    return fig

def create_depositor_sankey(depositors_df: pd.DataFrame, vault_info: Dict) -> go.Figure:
    """Create Sankey diagram for vault depositors"""
    if depositors_df.empty:
        return go.Figure()

    # Create nodes: depositors -> vault -> asset
    depositors = [f"{addr[:10]}..." for addr in depositors_df['userAddress'][:5]]  # Top 5
    vault_name = vault_info.get('Vault', 'Vault')
    asset_name = vault_info.get('Asset', 'Asset')

    nodes = depositors + [vault_name, f"{asset_name} Pool"]
    node_idx = {node: i for i, node in enumerate(nodes)}

    sources, targets, values = [], [], []

    for i, (_, depositor) in enumerate(depositors_df.head(5).iterrows()):
        depositor_short = f"{depositor['userAddress'][:10]}..."
        amount = depositor['Assets USD']

        # Depositor -> Vault
        sources.append(node_idx[depositor_short])
        targets.append(node_idx[vault_name])
        values.append(amount)

        # Vault -> Asset Pool
        sources.append(node_idx[vault_name])
        targets.append(node_idx[f"{asset_name} Pool"])
        values.append(amount * 0.9)  # Assume 90% deployed

    if not values:
        return go.Figure()

    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15, thickness=20,
            line=dict(color="black", width=0.5),
            label=nodes
        ),
        link=dict(source=sources, target=targets, value=values)
    )])

    fig.update_layout(title_text="Depositor Flow Analysis", height=400)
    return fig

# ======================================================
# Visualization Functions
# ======================================================

def create_pool_performance_chart(sheets: Dict[str, pd.DataFrame], pool_key: str) -> go.Figure:
    """Create line chart with dual Y-axes for comparing historical APY data."""
    
    # MODIFICATION 1: Initialize the figure with a secondary y-axis
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Get market data
    if 'morpho_markets' not in sheets:
        st.error("No market data available")
        return fig

    markets_df = sheets['morpho_markets']
    market_data = markets_df[markets_df['uniqueKey'] == pool_key]

    if market_data.empty:
        st.error(f"Market {pool_key} not found")
        return fig

    market = market_data.iloc[0]
    collateral_symbol = market.get('collateralAsset.symbol', 'Unknown')
    loan_symbol = market.get('loanAsset.symbol', 'Unknown')

    # Parse historical Morpho APY data
    historical_data_str = market.get('historicalState.dailyNetBorrowApy', '')
    historical_df = parse_historical_apy_data(historical_data_str)

    # Add Morpho APY trace to the primary (left) y-axis
    if not historical_df.empty:
        fig.add_trace(
            go.Scatter(
                x=historical_df['date'],
                y=historical_df['apy'],
                name='Morpho borrow rate',
                line=dict(color='#00D2FF', width=2)
            ),
            secondary_y=False,
        )

    # Check if it's a PT token and add Pendle data
    if is_pt_token(collateral_symbol):
        pendle_df = get_pendle_yield_data(sheets, pool_key)
        if not pendle_df.empty:
            # MODIFICATION 2: Add the Pendle APY trace to the secondary (right) y-axis
            fig.add_trace(
                go.Scatter(
                    x=pendle_df['date'],
                    y=pendle_df['apy'],
                    name='Pendle APY',
                    line=dict(color='#FF6B6B', width=2, dash='dash')
                ),
                secondary_y=True, # This is the key change
            )
        else:
            st.info(f"PT Token Detected, but no historical Pendle data was found in the CSV.")
            
    # Current APY as reference line on the primary axis
    current_apy = safe_float(market.get('state.netBorrowApy', 0)) * 100
    fig.add_hline(
        y=current_apy,
        line_dash="dot",
        line_color="red",
        annotation_text=f"Current Morpho: {current_apy:.2f}%",
        secondary_y=False
    )
    
    # MODIFICATION 3: Update layout and set titles for both y-axes
    fig.update_layout(
        title_text=f"Historical APY Performance: {collateral_symbol}/{loan_symbol}",
        xaxis_title="Date",
        hovermode='x unified',
        height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    # Add titles to each y-axis, colored to match their lines
    fig.update_yaxes(title_text="<b>Morpho borrow rate (%)</b>", secondary_y=False, color='#00D2FF')
    fig.update_yaxes(title_text="<b>Pendle APY (%)</b>", secondary_y=True, color='#FF6B6B')

    # Add range selector (unchanged)
    fig.update_layout(
        xaxis=dict(
            rangeselector=dict(
                buttons=list([
                    dict(count=7, label="7d", step="day", stepmode="backward"),
                    dict(count=30, label="30d", step="day", stepmode="backward"),
                    dict(count=90, label="3m", step="day", stepmode="backward"),
                    dict(step="all")
                ])
            ),
            rangeslider=dict(visible=True),
            type="date"
        )
    )

    return fig

def create_sankey_diagram(tx_df: pd.DataFrame, pool_info: Dict, user_address: str = None) -> Optional[go.Figure]:
    """Create Sankey flow diagram for transactions based on the simple.py logic."""
    if tx_df.empty:
        return None

    # Get unique borrowers (or a single user if specified)
    if user_address:
        borrowers = [user_address]
        title = f"Transaction Flow - {user_address[:10]}..."
    else:
        # Limit to top 10 unique borrowers for readability
        borrowers = sorted(tx_df['userAddress'].dropna().unique().tolist())[:10]
        title = "Transaction Flow - Top Borrowers"

    loan = pool_info.get('Borrow Asset', 'Loan')
    coll = pool_info.get('Collateral Asset', 'Collateral')

    # Use shortened addresses for node labels to keep the chart clean
    borrower_labels = {b: f"{b[:6]}...{b[-4:]}" for b in borrowers}

    # Define nodes: Borrowers first, then assets, to group them on one side
    nodes = list(borrower_labels.values()) + [f"Loan: {loan}", f"Collateral: {coll}"]
    if pool_info.get('Is PT Market'):
        nodes.append("Pendle PT")

    idx = {n: i for i, n in enumerate(nodes)}

    # Build links (source, target, value)
    links_s, links_t, links_v = [], [], []

    for b in borrowers:
        sub = tx_df[tx_df['userAddress'] == b]
        borrower_label = borrower_labels[b]

        # 1. Borrow Flow: Borrower -> Loan Asset (Represents debt obligation)
        v_borrow = sub[sub["type"].str.contains("borrow", case=False, na=False)]["USD Value"].sum()
        if v_borrow and v_borrow > 0:
            links_s.append(idx[borrower_label])
            links_t.append(idx[f"Loan: {loan}"])
            links_v.append(abs(v_borrow))

        # 2. Repay Flow: Loan Asset -> Borrower (Represents paying back debt)
        v_repay = sub[sub["type"].str.contains("repay", case=False, na=False)]["USD Value"].sum()
        if v_repay and v_repay > 0:
            links_s.append(idx[f"Loan: {loan}"])
            links_t.append(idx[borrower_label])
            links_v.append(abs(v_repay))

        # 3. Supply Flow: Borrower -> Collateral Asset
        v_sup = sub[sub["type"].str.contains("supply|collateral", case=False, na=False)]["USD Value"].sum()
        if v_sup and v_sup > 0:
            links_s.append(idx[borrower_label])
            links_t.append(idx[f"Collateral: {coll}"])
            links_v.append(abs(v_sup))

        # 4. Withdraw Flow: Collateral Asset -> Borrower
        v_wd = sub[sub["type"].str.contains("withdraw", case=False, na=False)]["USD Value"].sum()
        if v_wd and v_wd > 0:
            links_s.append(idx[f"Collateral: {coll}"])
            links_t.append(idx[borrower_label])
            links_v.append(abs(v_wd))

        # 5. Pendle Flow (if applicable): Collateral Asset -> Pendle PT
        if pool_info.get('Is PT Market') and v_sup and v_sup > 0:
            links_s.append(idx[f"Collateral: {coll}"])
            links_t.append(idx["Pendle PT"])
            # Use the 80% heuristic from the simple script
            links_v.append(abs(v_sup) * 0.8)

    if not links_v:
        return None

    # Create the figure using the generated nodes and links
    fig = go.Figure(data=[go.Sankey(
        node=dict(
            label=nodes,
            pad=20,
            thickness=14,
            line=dict(color="black", width=0.5)
        ),
        link=dict(
            source=links_s,
            target=links_t,
            value=links_v
        )
    )])

    fig.update_layout(title_text=title, height=420)
    return fig

def create_transaction_frequency_chart(tx_df: pd.DataFrame) -> go.Figure:
    """Create transaction frequency chart"""
    if tx_df.empty:
        return go.Figure()

    # Group by date and count transactions
    tx_df['Date'] = tx_df['Timestamp'].dt.date
    freq_data = tx_df.groupby('Date').size().reset_index(name='Transaction Count')

    fig = px.bar(freq_data, x='Date', y='Transaction Count',
                title="Transaction Frequency Over Time")
    fig.update_layout(height=300)
    return fig

def create_cumulative_net_position_chart(tx_df: pd.DataFrame) -> go.Figure:
    """Create cumulative net borrow position chart"""
    if tx_df.empty:
        return go.Figure()

    # Calculate cumulative net position
    tx_df_sorted = tx_df.sort_values('Timestamp')
    tx_df_sorted['Net Amount'] = 0

    for idx, row in tx_df_sorted.iterrows():
        tx_type = str(row['type']).lower()
        amount = row['USD Value']

        if 'borrow' in tx_type:
            tx_df_sorted.loc[idx, 'Net Amount'] = amount
        elif 'repay' in tx_type:
            tx_df_sorted.loc[idx, 'Net Amount'] = -amount
        elif 'supply' in tx_type:
            tx_df_sorted.loc[idx, 'Net Amount'] = amount
        elif 'withdraw' in tx_type:
            tx_df_sorted.loc[idx, 'Net Amount'] = -amount

    tx_df_sorted['Cumulative Position'] = tx_df_sorted['Net Amount'].cumsum()

    fig = px.line(tx_df_sorted, x='Timestamp', y='Cumulative Position',
                 title="Cumulative Net Position Over Time")
    fig.update_layout(height=300)
    return fig

def create_pnl_comparison_chart(borrowers_df: pd.DataFrame, sheets: Dict[str, pd.DataFrame], unique_key: str, pool_info: Dict) -> go.Figure:
    """Create clear PnL comparison chart"""
    if borrowers_df.empty:
        return go.Figure()

    # Calculate estimated PnL for each borrower
    estimated_pnls = []
    for _, borrower in borrowers_df.iterrows():
        est_pnl = calculate_borrower_pnl(sheets, unique_key, borrower['userAddress'], pool_info)
        estimated_pnls.append(est_pnl)

    borrowers_df = borrowers_df.copy()
    borrowers_df['Estimated PnL'] = estimated_pnls

    # Create comparison chart
    fig = go.Figure()

    # Add estimated PnL
    fig.add_trace(go.Bar(
        name='My Calculation (Leverage Formula)',
        x=[f"User {i+1}" for i in range(len(borrowers_df))],
        y=borrowers_df['Estimated PnL'],
        marker_color='lightblue'
    ))

    # Add Morpho PnL for comparison
    fig.add_trace(go.Bar(
        name='Morpho Platform Data',
        x=[f"User {i+1}" for i in range(len(borrowers_df))],
        y=borrowers_df['Morpho PnL'],
        marker_color='orange'
    ))

    fig.update_layout(
        title='PnL Comparison: My Calculation vs Morpho Platform',
        xaxis_title='Top Borrowers',
        yaxis_title='PnL (USD)',
        barmode='group',
        height=400
    )

    return fig

# ======================================================
# Main Application
# ======================================================

def main():
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon="🔵",
        layout="wide"
    )

    st.title(APP_TITLE)
    st.markdown(APP_SUBTITLE)

    # Load data
    with st.spinner("Loading data from CSV file..."):
        sheets = load_csv_data()

    if not sheets:
        st.error("Failed to load data. Please ensure morpho_pendle.csv exists and is accessible.")
        return

    # Build dataframes
    pools_df = build_pools_df(sheets)
    curators_df = build_curators_df(sheets)
    vaults_df = build_vaults_df(sheets)

    # Initialize routing if not exists
    if 'route_view' not in st.session_state:
        st.session_state.route_view = 'list'

    # Routing
    route = get_route()
    view = route.get('view', ['list'])[0] if route.get('view') else 'list'

    # Sidebar filters
    with st.sidebar:
        st.header("🎛️ Filters")

        if view == 'list':
            # Pool filters
            st.subheader("Pool Filters")

            # Asset filters
            all_collateral = ['All'] + sorted(pools_df['Collateral Asset'].unique().tolist()) if not pools_df.empty else ['All']
            all_borrow = ['All'] + sorted(pools_df['Borrow Asset'].unique().tolist()) if not pools_df.empty else ['All']

            filter_collateral = st.selectbox("Collateral Asset", all_collateral)
            filter_borrow = st.selectbox("Borrow Asset", all_borrow)

            # Numeric filters
            supply_filter = st.slider("Min Supply Assets ($M)", 0.0, 100.0, 0.0, 0.1)
            min_available = st.slider("Min Available Borrow ($M)", 0.0, 50.0, 0.0, 0.1)
            only_pt = st.checkbox("🎯 Only PT Markets", value=False)
            min_spread = st.slider("Min APY Spread (%)", -50.0, 50.0, -50.0, 0.5)

    # Main content based on view
    if view == 'list':
        # Main tabs
        tab1, tab2, tab3 = st.tabs(["📊 Pools", "🧑‍🏫 Curators", "🏦 Vaults"])

        # POOLS TAB
        with tab1:
            if pools_df.empty:
                st.warning("No pool data available.")
            else:
                # Apply filters
                filtered_pools = pools_df.copy()

                if filter_collateral != 'All':
                    filtered_pools = filtered_pools[filtered_pools['Collateral Asset'] == filter_collateral]
                if filter_borrow != 'All':
                    filtered_pools = filtered_pools[filtered_pools['Borrow Asset'] == filter_borrow]
                if supply_filter > 0:
                    filtered_pools = filtered_pools[filtered_pools['Supply Assets ($M)'] >= supply_filter]
                if min_available > 0:
                    filtered_pools = filtered_pools[filtered_pools['Available Borrow ($M)'] >= min_available]
                if only_pt:
                    filtered_pools = filtered_pools[filtered_pools['Is PT Market'] == True]
                if min_spread > -50:
                    filtered_pools = filtered_pools[filtered_pools['Net APY Spread (%)'].fillna(-999) >= min_spread]

                # Sort by descending supply assets
                filtered_pools = filtered_pools.sort_values('Supply Assets ($M)', ascending=False)

                # Display table
                st.subheader(f"📋 Pool Details ({len(filtered_pools)} pools)")

                if filtered_pools.empty:
                    st.info("No pools match the current filters.")
                else:
                    # Format display columns
                    display_cols = ['Pool', 'Supply Assets ($M)', 'Available Borrow ($M)',
                                  'Morpho Borrow APY (%)', 'PT/External APY (%)', 'Net APY Spread (%)',
                                  'Status', 'Utilization (%)', 'LLTV (%)']

                    # Create dataframe with color styling based on status
                    def style_rows(df):
                        def color_status(row):
                            if '🟢' in str(row['Status']):
                                return ['background-color: #d4edda'] * len(row)  # Light green
                            elif '🟡' in str(row['Status']):
                                return ['background-color: #fff3cd'] * len(row)  # Light yellow
                            elif '🔴' in str(row['Status']):
                                return ['background-color: #f8d7da'] * len(row)  # Light red
                            else:
                                return [''] * len(row)
                        return df.style.apply(color_status, axis=1)

                    # Interactive table
                    selected = st.dataframe(
                        filtered_pools[display_cols],
                        use_container_width=True,
                        hide_index=True,
                        on_select="rerun",
                        selection_mode="single-row"
                    )

                    # Handle pool selection
                    if hasattr(selected, 'selection') and selected.selection and selected.selection.rows:
                        selected_idx = selected.selection.rows[0]
                        selected_pool = filtered_pools.iloc[selected_idx]
                        set_route(view='pool', key=selected_pool['Unique Key'])
                        st.rerun()

        # CURATORS TAB
        with tab2:
            if curators_df.empty:
                st.warning("No curator data available.")
            else:
                st.subheader("🧑‍🏫 Curators")
                
                selected_curator = st.dataframe(
                    curators_df,
                    column_order=['Curator', 'Total AUM', 'Vault Count'],
                    column_config={
                        "Total AUM": st.column_config.NumberColumn(
                            "Total AUM", format="$%d"
                        ),
                        "Address": None,
                        "Managed Vaults": None,
                        "Morpho URL": None,
                        "twitter": None,
                        "main": None,
                    },
                    use_container_width=True,
                    hide_index=True,
                    on_select="rerun",
                    selection_mode="single-row"
                )

                # Handle curator selection
                if hasattr(selected_curator, 'selection') and selected_curator.selection and selected_curator.selection.rows:
                    selected_idx = selected_curator.selection.rows[0]
                    curator_info = curators_df.iloc[selected_idx]
                    set_route(view='curator', curator=curator_info['Curator'])
                    st.rerun()

        # VAULTS TAB
        with tab3:
            if vaults_df.empty:
                st.warning("No vault data available.")
            else:
                st.subheader("🏦 All Vaults")

                selected_vault = st.dataframe(
                    vaults_df,
                    column_order=['Vault', 'Symbol', 'TVL', 'APY', 'Fee', 'Asset'],
                    column_config={
                        "TVL": st.column_config.NumberColumn("TVL", format="$%d"),
                        "APY": st.column_config.NumberColumn("APY (%)", format="%.2f"),
                        "Fee": st.column_config.NumberColumn("Fee (%)", format="%.2f"),
                        "Address": None,
                        "Curator": None,
                        "Curator Name": None,
                        "Curator Names List": None,
                        "Whitelisted": None,
                    },
                    use_container_width=True,
                    hide_index=True,
                    on_select="rerun",
                    selection_mode="single-row"
                )

                # Handle vault selection
                if hasattr(selected_vault, 'selection') and selected_vault.selection and selected_vault.selection.rows:
                    selected_idx = selected_vault.selection.rows[0]
                    vault_info = vaults_df.iloc[selected_idx]
                    set_route(view='vault', address=vault_info['Address'])
                    st.rerun()

    elif view == 'pool':
        # Pool detail page
        pool_key = route.get('key', [None])[0]
        if not pool_key:
            set_route(view='list')
            st.rerun()
            return

        if st.button("← Back to Pools"):
            set_route(view='list')
            st.rerun()

        # Find the pool
        pool_info = pools_df[pools_df['Unique Key'] == pool_key]
        if pool_info.empty:
            st.error("Pool not found")
            return

        pool_info = pool_info.iloc[0]
        st.header(f"📊 {pool_info['Pool']}")

        # Pool metrics (removed Pool Size)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Morpho Borrow APY", format_percentage(pool_info['Morpho Borrow APY (%)']))
        with col2:
            st.metric("PT/External APY", format_percentage(pool_info['PT/External APY (%)']))
        with col3:
            spread = pool_info['Net APY Spread (%)']
            st.metric("Net Spread", format_percentage(spread),
                     delta=None if pd.isna(spread) else f"{spread:.2f}% opportunity")

        # Additional metrics
        col4, col5, col6 = st.columns(3)
        with col4:
            st.metric("Supply Assets", format_usd(pool_info['Supply Assets ($M)'] * 1_000_000))
        with col5:
            st.metric("Available Borrow", format_usd(pool_info['Available Borrow ($M)'] * 1_000_000))
        with col6:
            st.metric("Utilization", format_percentage(pool_info['Utilization (%)']))

        # Links
        link_col1, link_col2 = st.columns(2)
        with link_col1:
            if pool_info['Morpho Link']:
                st.markdown(f"🔗 [View on Morpho]({pool_info['Morpho Link']})")
        with link_col2:
            if pool_info['Pendle Link']:
                st.markdown(f"🔗 [View on Pendle]({pool_info['Pendle Link']})")

        # Historical APY Performance Chart
        st.subheader("📈 Historical APY Performance")
        performance_chart = create_pool_performance_chart(sheets, pool_key)
        st.plotly_chart(performance_chart, use_container_width=True)

        # Show summary statistics if historical data exists
        if 'morpho_markets' in sheets:
            markets_df = sheets['morpho_markets']
            market_data = markets_df[markets_df['uniqueKey'] == pool_key]
            if not market_data.empty:
                market = market_data.iloc[0]
                historical_data_str = market.get('historicalState.dailyNetBorrowApy', '')
                historical_df = parse_historical_apy_data(historical_data_str)

                if not historical_df.empty:
                    col1, col2, col3, col4 = st.columns(4)
                    current_apy = safe_float(market.get('state.netBorrowApy', 0)) * 100
                    avg_apy = historical_df['apy'].mean()
                    max_apy = historical_df['apy'].max()
                    min_apy = historical_df['apy'].min()

                    with col1:
                        st.metric("Current APY", f"{current_apy:.2f}%")
                    with col2:
                        st.metric("Average APY", f"{avg_apy:.2f}%")
                    with col3:
                        st.metric("Maximum APY", f"{max_apy:.2f}%")
                    with col4:
                        st.metric("Minimum APY", f"{min_apy:.2f}%")

        # Sub-tabs for detailed analysis
        pool_tabs = st.tabs(["👥 Top Borrowers", "📈 Transactions", "🕸️ Flow Analysis"])

        # TOP BORROWERS TAB
        with pool_tabs[0]:
            borrowers_df = get_top_borrowers(sheets, pool_key)
            if borrowers_df.empty:
                st.info("No borrower data available for this pool.")
            else:
                st.subheader("🏆 Top 5 Borrowers")

                # Calculate estimated PnL for each borrower
                estimated_pnls = []
                for _, borrower in borrowers_df.iterrows():
                    est_pnl = calculate_borrower_pnl(sheets, pool_key, borrower['userAddress'], pool_info.to_dict())
                    estimated_pnls.append(est_pnl)

                borrowers_df['Estimated PnL'] = estimated_pnls

                # Format borrowers data for display with Etherscan links
                display_borrowers = borrowers_df.copy()
                display_borrowers['Collateral'] = [format_usd(x) for x in display_borrowers['Collateral USD']]
                display_borrowers['Borrowed'] = [format_usd(x) for x in display_borrowers['Borrow USD']]
                display_borrowers['Health'] = [f"{x:.2f}" if not pd.isna(x) else "—" for x in display_borrowers['Health Factor']]
                display_borrowers['Est. PnL'] = [format_usd(x) if not pd.isna(x) else "—" for x in display_borrowers['Estimated PnL']]
                display_borrowers['Morpho PnL'] = [format_usd(x) if not pd.isna(x) else "—" for x in display_borrowers['Morpho PnL']]
                display_borrowers['Address'] = [f"{addr[:10]}...{addr[-6:]}" for addr in display_borrowers['userAddress']]

                # Create proper table with headers
                header_cols = st.columns([2, 1, 1, 1, 1, 1, 1])
                with header_cols[0]:
                    st.write("**Address**")
                with header_cols[1]:
                    st.write("**Collateral**")
                with header_cols[2]:
                    st.write("**Borrowed**")
                with header_cols[3]:
                    st.write("**Health Factor**")
                with header_cols[4]:
                    st.write("**Est. PnL**")
                with header_cols[5]:
                    st.write("**Morpho PnL**")
                with header_cols[6]:
                    st.write("**Action**")

                # Create table with etherscan links
                for idx, row in display_borrowers.iterrows():
                    cols = st.columns([2, 1, 1, 1, 1, 1, 1])
                    with cols[0]:
                        st.write(f"[{row['Address']}](https://etherscan.io/address/{row['userAddress']})")
                    with cols[1]:
                        st.write(row['Collateral'])
                    with cols[2]:
                        st.write(row['Borrowed'])
                    with cols[3]:
                        st.write(row['Health'])
                    with cols[4]:
                        st.write(row['Est. PnL'])
                    with cols[5]:
                        st.write(row['Morpho PnL'])
                    with cols[6]:
                        if st.button("Analyze", key=f"analyze_{pool_key}_{idx}"):
                            set_route(view='borrower', key=pool_key, addr=row['userAddress'])
                            st.rerun()

                # PnL comparison chart
                if len(borrowers_df) > 1:
                    st.subheader("📊 PnL Comparison")
                    pnl_chart = create_pnl_comparison_chart(borrowers_df, sheets, pool_key, pool_info.to_dict())
                    st.plotly_chart(pnl_chart, use_container_width=True)

        # TRANSACTIONS TAB
        with pool_tabs[1]:
            tx_df = get_user_transactions(sheets, pool_key)
            if tx_df.empty:
                st.info("No transaction data available for this pool.")
            else:
                st.subheader("📈 Transaction Analysis")

                # Transaction summary metrics
                total_volume = tx_df['USD Value'].sum()
                unique_users = tx_df['userAddress'].nunique()
                avg_tx_size = tx_df['USD Value'].mean()

                tx_col1, tx_col2, tx_col3 = st.columns(3)
                with tx_col1:
                    st.metric("Total Volume", format_usd(total_volume))
                with tx_col2:
                    st.metric("Unique Users", unique_users)
                with tx_col3:
                    st.metric("Avg Transaction", format_usd(avg_tx_size))

                # Transaction frequency chart
                freq_chart = create_transaction_frequency_chart(tx_df)
                st.plotly_chart(freq_chart, use_container_width=True)

                # Cumulative net position chart
                cumulative_chart = create_cumulative_net_position_chart(tx_df)
                st.plotly_chart(cumulative_chart, use_container_width=True)

        # FLOW ANALYSIS TAB
        with pool_tabs[2]:
            tx_df = get_user_transactions(sheets, pool_key)
            if tx_df.empty:
                st.info("No transaction data available for flow analysis.")
            else:
                st.subheader("🌊 Transaction Flow Analysis")

                # Sankey diagram positioned on the left
                col1, col2 = st.columns([2, 1])
                with col1:
                    sankey_fig = create_sankey_diagram(tx_df, pool_info.to_dict())
                    if sankey_fig:
                        st.plotly_chart(sankey_fig, use_container_width=True)
                    else:
                        st.info("Not enough transaction data to create flow diagram.")

    elif view == 'borrower':
        # Borrower detail page
        pool_key = route.get('key', [None])[0]
        borrower_addr = route.get('addr', [None])[0]

        if not pool_key or not borrower_addr:
            set_route(view='list')
            st.rerun()
            return

        if st.button("← Back to Pool"):
            set_route(view='pool', key=pool_key)
            st.rerun()

        # Find pool info
        pool_info = pools_df[pools_df['Unique Key'] == pool_key]
        if pool_info.empty:
            st.error("Pool not found")
            return
        pool_info = pool_info.iloc[0]

        st.header(f"👤 Borrower Analysis")
        st.subheader(f"Address: {borrower_addr[:10]}...{borrower_addr[-6:]}")
        st.markdown(f"**Pool**: {pool_info['Pool']}")

        # Links
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"🔗 [View on Etherscan](https://etherscan.io/address/{borrower_addr})")
        with col2:
            st.markdown(f"🔗 [Morpho Activity](https://app.morpho.org/ethereum/market/{pool_key})")

        # Get borrower's transactions
        user_tx = get_user_transactions(sheets, pool_key, borrower_addr)
        if user_tx.empty:
            st.info("No transaction data available for this borrower.")
            return

        # Get Pendle positions for this user
        pendle_positions = get_pendle_positions(sheets, borrower_addr, pool_key)
        if not pendle_positions.empty:
            st.markdown("---")
            st.subheader("📊 Pendle Position Dashboard")

            position_info = pendle_positions.iloc[0]

            raw_positions = position_info.get('raw.positions', '')

            # Process the data using our new helper function
            stats, details_df = process_positions_for_display(raw_positions)

            if not details_df.empty:
                # 1. Display Key Metrics in columns
                col1, col2, col3 = st.columns(3)
                col1.metric("Total Open Value", format_usd(stats['total_open_value']))
                col2.metric("Active Positions", stats['position_count'])
                col3.metric("LP Value", format_usd(stats['total_lp_value']))

                st.markdown("<br>", unsafe_allow_html=True) # Add some space

                # 2. Display Pie Chart and Data Table side-by-side
                col_chart, col_table = st.columns([2, 3]) # Give more space to the table

                with col_chart:
                    st.write("**Portfolio Composition**")
                    labels = ['Principal Tokens (PT)', 'Yield Tokens (YT)', 'Liquidity Positions (LP)']
                    values = [stats['total_pt_value'], stats['total_yt_value'], stats['total_lp_value']]

                    # Create pie chart only if there's value
                    if sum(values) > 0:
                        fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.3, pull=[0, 0, 0.05])])
                        fig.update_layout(margin=dict(l=20, r=20, t=30, b=20), height=350)
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("No assets to chart.")

                with col_table:
                    st.write("**Detailed Positions**")
                    # Format the columns for display in the dataframe
                    display_df = details_df.copy()
                    for col in ["PT Value", "YT Value", "LP Value", "Total Value"]:
                        display_df[col] = display_df[col].apply(format_usd)

                    st.dataframe(display_df, use_container_width=True, hide_index=True)


            else:
                st.info("No open positions with value were found for this user.")

        # Borrower metrics
        borrow_mask = user_tx['type'].astype(str).str.contains('borrow', case=False, na=False)
        supply_mask = user_tx['type'].astype(str).str.contains('supply', case=False, na=False)
        repay_mask = user_tx['type'].astype(str).str.contains('repay', case=False, na=False)

        total_borrowed = user_tx[borrow_mask]['USD Value'].sum()
        total_supplied = user_tx[supply_mask]['USD Value'].sum()
        total_repaid = user_tx[repay_mask]['USD Value'].sum()
        net_position = total_supplied - total_borrowed + total_repaid

        met_col1, met_col2, met_col3, met_col4 = st.columns(4)
        with met_col1:
            st.metric("Total Borrowed", format_usd(abs(total_borrowed)))
        with met_col2:
            st.metric("Total Supplied", format_usd(total_supplied))
        with met_col3:
            st.metric("Total Repaid", format_usd(abs(total_repaid)))
        with met_col4:
            st.metric("Net Position", format_usd(net_position))

        # Transaction frequency chart for this user
        freq_chart = create_transaction_frequency_chart(user_tx)
        st.plotly_chart(freq_chart, use_container_width=True)

        # Cumulative net position chart for this user
        cumulative_chart = create_cumulative_net_position_chart(user_tx)
        st.plotly_chart(cumulative_chart, use_container_width=True)

        # Individual user flow analysis
        st.subheader("🌊 Personal Flow Analysis")
        personal_sankey = create_sankey_diagram(user_tx, pool_info.to_dict(), borrower_addr)
        if personal_sankey:
            st.plotly_chart(personal_sankey, use_container_width=True)

    elif view == 'curator':
        # Curator detail page
        curator_name = route.get('curator', [None])[0]
        if not curator_name:
            set_route(view='list')
            st.rerun()
            return

        if st.button("← Back to Curators"):
            set_route(view='list')
            st.rerun()

        curator_info = curators_df[curators_df['Curator'] == curator_name]
        if curator_info.empty:
            st.error("Curator not found")
            return

        curator_info = curator_info.iloc[0]
        st.header(f"🧑‍🏫 {curator_name}")

        # Curator metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total AUM", format_usd(curator_info['Total AUM']))
        with col2:
            st.metric("Number of Vaults", curator_info['Vault Count'])
        with col3:
            if curator_info['Morpho URL']:
                st.markdown(f"🔗 [Website]({curator_info['main']}) [Morphoforum]({curator_info['Morpho URL']}) [X]({curator_info['twitter']}) ")
                url_name = curator_name.replace(' ', '-')
                st.markdown(f"🔗 [Morpho link](https://app.morpho.org/ethereum/curator/{url_name})")

        # Managed Vaults
        st.subheader("🏦 Managed Vaults")
        managed_vaults_list = curator_info['Managed Vaults']
        if managed_vaults_list:
            managed_vaults_df = pd.DataFrame(managed_vaults_list)
            
            # Use a dataframe with selection to navigate
            selected_vault = st.dataframe(
                managed_vaults_df,
                column_order=['Vault', 'TVL', 'APY'],
                column_config={
                    "Vault": "Vault Name",
                    "TVL": st.column_config.NumberColumn("TVL", format="$%d"),
                    "APY": st.column_config.NumberColumn("APY (%)", format="%.2f"),
                    "Address": None  # Hide address from view
                },
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row"
            )

            if hasattr(selected_vault, 'selection') and selected_vault.selection and selected_vault.selection.rows:
                selected_idx = selected_vault.selection.rows[0]
                vault_address = managed_vaults_df.iloc[selected_idx]['Address']
                set_route(view='vault', address=vault_address)
                st.rerun()
        else:
            st.info("No vault data available for this curator")


    elif view == 'vault':
        # Vault detail page
        vault_addr = route.get('address', [None])[0]
        if not vault_addr:
            set_route(view='list')
            st.rerun()
            return

        if st.button("← Back to Vaults"):
            set_route(view='list')
            st.rerun()

        vault_info = vaults_df[vaults_df['Address'] == vault_addr]
        if vault_info.empty:
            st.error("Vault not found")
            return

        vault_info = vault_info.iloc[0]
        st.header(f"🏦 {vault_info['Vault']}")
        # Curator information
        if vault_info['Curator Name']:
            st.info(f"👨‍🏫 Managed by: {vault_info['Curator Name']}")
        # Vault metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total TVL", format_usd(vault_info['TVL']))
        with col2:
            st.metric("APY", f"{vault_info['APY']:.2f}%")
        with col3:
            st.metric("Fee", f"{vault_info['Fee']:.2f}%")
        with col4:
            st.metric("Asset", vault_info['Asset'])

        # Additional info
        st.markdown(f"**Symbol**: {vault_info['Symbol']}")
        st.markdown(f"**Whitelisted**: {'Yes' if vault_info['Whitelisted'] else 'No'}")
        name = vault_info['Vault']
        url_name = name.replace(' ', '-')
        st.markdown(f"🔗 [View on Morpho](https://app.morpho.org/ethereum/vault/{vault_addr}/{url_name})")

        # Get depositors data
        vault_depositors = get_vault_depositors(sheets, vault_addr)
        if not vault_depositors.empty:
            st.subheader("👥 Top Depositors")

            # Similar analysis as borrowers - user distribution, sankey flow, line charts
            display_depositors = vault_depositors.copy()
            display_depositors['Amount'] = [format_usd(x) for x in display_depositors['Assets USD']]
            display_depositors['Address'] = [f"{addr[:10]}...{addr[-6:]}" for addr in display_depositors['userAddress']]

            # Create proper table headers for depositors
            header_cols = st.columns([3, 2, 2])
            with header_cols[0]:
                st.write("**Address**")
            with header_cols[1]:
                st.write("**Amount**")
            with header_cols[2]:
                st.write("**Action**")

            # Create table with etherscan links for depositors
            for idx, row in display_depositors.iterrows():
                cols = st.columns([3, 2, 2])
                with cols[0]:
                    st.write(f"[{row['Address']}](https://etherscan.io/address/{row['userAddress']})")
                with cols[1]:
                    col_text = f"{row['Amount']} (Raw: {format_usd(row.get('Raw Amount', 0))}, Calc: {format_usd(row.get('Calculated Amount', 0))})"
                    st.write(col_text)
                with cols[2]:
                    if st.button("Analyze", key=f"analyze_depositor_{vault_addr}_{idx}"):
                        set_route(view='depositor', vault_addr=vault_addr, addr=row['userAddress'])
                        st.rerun()

            # Enhanced depositor analytics
            st.subheader("📊 Depositor Analytics")

            # User distribution pie chart
            if len(vault_depositors) > 1:
                dist_chart = create_depositor_distribution_chart(vault_depositors)
                st.plotly_chart(dist_chart, use_container_width=True)

            # Depositor sankey flow
            sankey_chart = create_depositor_sankey(vault_depositors, vault_info.to_dict())
            if sankey_chart:
                st.plotly_chart(sankey_chart, use_container_width=True)

            # Depositor metrics
            total_deposited = vault_depositors['Assets USD'].sum()
            avg_deposit = vault_depositors['Assets USD'].mean()
            largest_deposit = vault_depositors['Assets USD'].max()

            dep_col1, dep_col2, dep_col3 = st.columns(3)
            with dep_col1:
                st.metric("Total Deposited", format_usd(total_deposited))
            with dep_col2:
                st.metric("Average Deposit", format_usd(avg_deposit))
            with dep_col3:
                st.metric("Largest Deposit", format_usd(largest_deposit))

    elif view == 'depositor':
        # Depositor detail page
        vault_addr = route.get('vault_addr', [None])[0]
        depositor_addr = route.get('addr', [None])[0]

        if not vault_addr or not depositor_addr:
            set_route(view='list')
            st.rerun()
            return

        if st.button("← Back to Vault"):
            set_route(view='vault', address=vault_addr)
            st.rerun()

        # Find vault info
        vault_info = vaults_df[vaults_df['Address'] == vault_addr]
        if vault_info.empty:
            st.error("Vault not found")
            return
        vault_info = vault_info.iloc[0]

        st.header(f"👤 Depositor Analysis")
        st.subheader(f"Address: {depositor_addr[:10]}...{depositor_addr[-6:]}")
        st.markdown(f"**Vault**: {vault_info['Vault']}")

        # Links
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"🔗 [View on Etherscan](https://etherscan.io/address/{depositor_addr})")
        with col2:
            st.markdown(f"🔗 [Morpho Activity](https://app.morpho.org/ethereum/vault/{vault_addr})")

        # Get depositor data
        vault_depositors = get_vault_depositors(sheets, vault_addr)
        depositor_data = vault_depositors[vault_depositors['userAddress'] == depositor_addr]

        if not depositor_data.empty:
            depositor_info = depositor_data.iloc[0]

            # Depositor metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Deposited Amount", format_usd(depositor_info['Assets USD']))
            with col2:
                st.metric("Raw Amount", format_usd(depositor_info.get('Raw Amount', 0)))
            with col3:
                transaction_count = depositor_info.get('Transaction Count', 0)
                st.metric("Transaction Count", transaction_count)

            # Show transaction details
            transactions = depositor_info.get('Transactions', [])
            if transactions:
                tx_df = pd.DataFrame(transactions)
                tx_df['timestamp'] = pd.to_datetime(tx_df['timestamp'], unit='s')
                tx_df['amount_usd'] = pd.to_numeric(tx_df['amount_usd'])
                
                st.subheader("📊 Transaction Visuals")

                # Cumulative deposits chart
                tx_df_sorted = tx_df.sort_values('timestamp')
                tx_df_sorted['Cumulative Amount'] = tx_df_sorted['amount_usd'].cumsum()
                cumulative_fig = px.line(
                    tx_df_sorted, x='timestamp', y='Cumulative Amount', 
                    title="Cumulative Deposit Value Over Time", markers=True
                )
                st.plotly_chart(cumulative_fig, use_container_width=True)

                # Frequency chart
                tx_df_sorted['Date'] = tx_df_sorted['timestamp'].dt.date
                freq_data = tx_df_sorted.groupby('Date').size().reset_index(name='Transaction Count')
                freq_fig = px.bar(
                    freq_data, x='Date', y='Transaction Count', 
                    title="Transaction Frequency"
                )
                st.plotly_chart(freq_fig, use_container_width=True)

                # Show transaction details in expanders
                st.subheader("💼 Transaction History")

                for i, tx in enumerate(transactions):
                    with st.expander(f"Transaction {i+1} - {tx.get('type', 'Unknown')}"):
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.write(f"**Hash**: [{tx.get('hash', '')[:10]}...](https://etherscan.io/tx/{tx.get('hash', '')})")
                        with col2:
                            st.write(f"**Type**: {tx.get('type', 'Unknown')}")
                        with col3:
                            st.write(f"**Amount**: {format_usd(tx.get('amount_usd', 0))}")
                        with col4:
                            import datetime
                            timestamp = tx.get('timestamp', 0)
                            if timestamp:
                                date_str = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M')
                                st.write(f"**Date**: {date_str}")

            # Individual depositor flow analysis
            st.subheader("🌊 Personal Flow Analysis")
            individual_sankey = create_depositor_sankey(depositor_data, vault_info.to_dict())
            if individual_sankey:
                st.plotly_chart(individual_sankey, use_container_width=True)
        else:
            st.info("No detailed data available for this depositor.")

if __name__ == "__main__":
    main()
