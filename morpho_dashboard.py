import streamlit as st
import pandas as pd
import numpy as np
import json
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import requests
from typing import Dict, List, Optional, Any
import os

# Page config
st.set_page_config(
    page_title="Morpho Blue Pool Analyzer",
    page_icon="🔵",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
.metric-card {
    background-color: #f0f2f6;
    padding: 1rem;
    border-radius: 0.5rem;
    border-left: 4px solid #1f77b4;
}

.profit-positive {
    background-color: #d4edda !important;
    color: #155724 !important;
}

.profit-moderate {
    background-color: #fff3cd !important;
    color: #856404 !important;
}

.profit-negative {
    background-color: #f8d7da !important;
    color: #721c24 !important;
}

.stDataFrame [data-testid="stTable"] {
    font-size: 12px;
}
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_config(config_path: str = "config.json") -> Dict:
    """Load configuration settings"""
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                return json.load(f)
        else:
            return {}
    except Exception as e:
        st.error(f"Error loading config: {e}")
        return {}

@st.cache_data(ttl=300)
def load_morpho_data(file_path: str = "morpho_complete_analysis.json") -> Dict:
    """Load Morpho data from JSON file"""
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                return json.load(f)
        else:
            st.error(f"File {file_path} not found. Please run get_morpho_data.js first.")
            return {"data": []}
    except Exception as e:
        st.error(f"Error loading Morpho data: {e}")
        return {"data": []}

@st.cache_data(ttl=300)
def load_pendle_summary(file_path: str = "pendle_morpho_summary.json") -> Dict:
    """Load Pendle summary data from JSON file"""
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                return json.load(f)
        else:
            return {"ptMarkets": [], "overview": {}, "topBorrowersByMarket": {}}
    except Exception as e:
        st.warning(f"Error loading Pendle summary: {e}")
        return {"ptMarkets": [], "overview": {}, "topBorrowersByMarket": {}}

@st.cache_data(ttl=300)
def load_pendle_analysis(file_path: str = "pendle_morpho_analysis.json") -> Dict:
    """Load Pendle analysis data from JSON file"""
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                return json.load(f)
        else:
            return {"ptMarketsData": {}, "borrowerPositions": {}, "metadata": {}}
    except Exception as e:
        st.warning(f"Error loading Pendle analysis: {e}")
        return {"ptMarketsData": {}, "borrowerPositions": {}, "metadata": {}}

def calculate_external_yield_apy(loan_asset_symbol: str, config: Dict = None) -> float:
    """Calculate external yield APY for common assets using config"""
    if config and 'external_yields' in config:
        assets = config['external_yields'].get('assets', {})
        if loan_asset_symbol in assets:
            return assets[loan_asset_symbol].get('apy', 0)
        return config['external_yields'].get('default_apy', 2.0)

    # Fallback external yields
    external_yields = {
        "WETH": 3.2, "USDC": 4.5, "USDT": 4.2, "DAI": 4.0, "USDe": 15.0,
        "wstETH": 3.5, "WBTC": 1.5, "ezETH": 4.0, "weETH": 3.8, "sUSDe": 15.0,
        "rETH": 3.1, "cbETH": 3.0, "stETH": 3.2, "rsETH": 3.4, "sfrxETH": 3.3
    }
    return external_yields.get(loan_asset_symbol, 2.0)

def calculate_net_apy_spread(morpho_borrow_apy: float, external_yield_apy: float) -> float:
    """Calculate net APY spread"""
    return external_yield_apy - morpho_borrow_apy

def get_status_color(net_spread: float, config: Dict = None) -> str:
    """Get status color based on net APY spread using config thresholds"""
    if config and 'color_thresholds' in config:
        high_threshold = config['color_thresholds'].get('high_profit_threshold', 5.0)
        moderate_threshold = config['color_thresholds'].get('moderate_profit_threshold', 0.0)
    else:
        high_threshold, moderate_threshold = 5.0, 0.0

    if net_spread > high_threshold:
        return "🟢 High"
    elif net_spread > moderate_threshold:
        return "🟡 Moderate"
    else:
        return "🔴 Negative"

def is_pendle_pt_token(symbol: str) -> bool:
    """Check if a token is a Pendle PT token"""
    pt_prefixes = ['PT-', 'pt-', 'PT_', 'pt_']
    return any(symbol.startswith(prefix) for prefix in pt_prefixes)

def get_pendle_data_for_market(market_unique_key: str, pendle_analysis: Dict) -> Optional[Dict]:
    """Get Pendle market data for a given Morpho market unique key"""
    pt_markets_data = pendle_analysis.get('ptMarketsData', {})

    for pt_key, pt_data in pt_markets_data.items():
        morpho_market = pt_data.get('morphoMarket', {})
        if morpho_market.get('uniqueKey') == market_unique_key:
            return pt_data

    return None

def process_morpho_data(morpho_data: Dict, pendle_summary: Dict, pendle_analysis: Dict, config: Dict = None) -> pd.DataFrame:
    """Process raw data into dashboard format"""
    processed_data = []

    # Create lookup for Pendle summary data
    pendle_markets_lookup = {}
    for pt_market in pendle_summary.get('ptMarkets', []):
        if pt_market.get('ptTokenAddress'):
            pendle_markets_lookup[pt_market['ptTokenAddress'].lower()] = pt_market

    for market_entry in morpho_data.get('data', []):
        market = market_entry.get('market', {})

        if not market.get('loanAsset') or not market.get('collateralAsset'):
            continue

        loan_asset = market['loanAsset']
        collateral_asset = market['collateralAsset']

        loan_symbol = loan_asset.get('symbol', 'Unknown')
        collateral_symbol = collateral_asset.get('symbol', 'Unknown')

        # Check if this is a Pendle PT market
        is_pendle_pt = is_pendle_pt_token(collateral_symbol)
        pt_implied_apy = None
        pt_aggregated_apy = None

        if is_pendle_pt:
            # Try to get Pendle data
            pendle_data = get_pendle_data_for_market(market.get('uniqueKey', ''), pendle_analysis)
            if pendle_data:
                pendle_market = pendle_data.get('pendleMarket', {})
                market_details = pendle_data.get('marketDetails', {})

                if pendle_market and pendle_market.get('details'):
                    pt_implied_apy = pendle_market['details'].get('impliedApy', 0)
                    pt_aggregated_apy = pendle_market['details'].get('aggregatedApy', 0)
                elif market_details:
                    pt_implied_apy = market_details.get('impliedApy', 0)
                    pt_aggregated_apy = market_details.get('aggregatedApy', 0)

        # Get market state
        state = market.get('state', {})

        # Calculate APYs - convert from decimal to percentage
        morpho_borrow_apy = state.get('borrowApy', 0) * 100

        # For PT tokens, use PT Implied APY instead of external yield
        if is_pendle_pt and pt_implied_apy:
            comparison_apy = pt_implied_apy * 100  # PT Implied APY
        else:
            comparison_apy = calculate_external_yield_apy(loan_symbol, config)  # External yield

        net_apy_spread = calculate_net_apy_spread(morpho_borrow_apy, comparison_apy)

        # Get liquidity data
        total_liquidity_usd = state.get('totalLiquidityUsd', 0)

        # Get borrower data
        top_borrowers = market_entry.get('topBorrowers', [])

        # Create market links
        morpho_link = f"https://app.morpho.org/ethereum/market/{market.get('uniqueKey', '')}/eth-weth"
        pendle_link = None

        if is_pendle_pt:
            # Try to get Pendle market address from the analysis data
            pendle_data = get_pendle_data_for_market(market.get('uniqueKey', ''), pendle_analysis)
            if pendle_data:
                pendle_market = pendle_data.get('pendleMarket', {})
                pendle_address = pendle_market.get('address')
                if pendle_address:
                    pendle_link = f"https://app.pendle.finance/trade/markets/{pendle_address}/swap?view=pt&chain=ethereum"

        processed_data.append({
            'Pool': f"{collateral_symbol} / {loan_symbol}",
            'Collateral Asset': collateral_symbol,
            'Borrow Asset': loan_symbol,
            'Pool Size ($M)': round(total_liquidity_usd / 1_000_000, 2) if total_liquidity_usd else 0,
            'Morpho Borrow APY (%)': round(morpho_borrow_apy, 2),
            'Yield APY (%)': round(comparison_apy, 2),
            'Net APY Spread (%)': round(net_apy_spread, 2),
            'Status': get_status_color(net_apy_spread, config),
            'Is Pendle PT': is_pendle_pt,
            'PT Implied APY (%)': round(pt_implied_apy * 100, 2) if pt_implied_apy else None,
            'PT Aggregated APY (%)': round(pt_aggregated_apy * 100, 2) if pt_aggregated_apy else None,
            'Utilization (%)': round(state.get('utilization', 0) * 100, 2),
            'LLTV (%)': round(float(market.get('lltv', 0)) * 100, 2) if market.get('lltv') else None,
            'Unique Key': market.get('uniqueKey', ''),
            'Top Borrowers': top_borrowers,
            'Historical Data': market.get('historicalState', {}),
            'Market Data': market,
            'Collateral Address': collateral_asset.get('address', ''),
            'Loan Address': loan_asset.get('address', ''),
            'Borrow Assets USD': state.get('borrowAssetsUsd', 0),
            'Supply Assets USD': state.get('supplyAssetsUsd', 0),
            'Morpho Link': morpho_link,
            'Pendle Link': pendle_link,
        })

    return pd.DataFrame(processed_data)

def create_historical_chart(historical_data: Dict, pool_name: str) -> go.Figure:
    """Create historical APY comparison chart"""
    fig = make_subplots(
        rows=1, cols=1,
        subplot_titles=[f'Historical Borrow APY - {pool_name}']
    )

    # Process historical data
    monthly_borrow = historical_data.get('monthlyBorrowApy', [])
    quarterly_borrow = historical_data.get('quarterlyBorrowApy', [])

    data_added = False

    if monthly_borrow and len(monthly_borrow) > 0:
        try:
            timestamps = []
            values = []
            for point in monthly_borrow:
                if isinstance(point, dict) and 'x' in point and 'y' in point:
                    try:
                        ts = datetime.fromtimestamp(point['x'])
                        val = point['y'] * 100  # Convert to percentage
                        timestamps.append(ts)
                        values.append(val)
                    except:
                        continue

            if timestamps and values:
                fig.add_trace(
                    go.Scatter(
                        x=timestamps,
                        y=values,
                        mode='lines+markers',
                        name='Monthly Borrow APY',
                        line=dict(color='#1f77b4', width=2),
                        marker=dict(size=4)
                    )
                )
                data_added = True
        except Exception as e:
            print(f"Error processing monthly data: {e}")

    if quarterly_borrow and len(quarterly_borrow) > 0:
        try:
            timestamps = []
            values = []
            for point in quarterly_borrow:
                if isinstance(point, dict) and 'x' in point and 'y' in point:
                    try:
                        ts = datetime.fromtimestamp(point['x'])
                        val = point['y'] * 100  # Convert to percentage
                        timestamps.append(ts)
                        values.append(val)
                    except:
                        continue

            if timestamps and values:
                fig.add_trace(
                    go.Scatter(
                        x=timestamps,
                        y=values,
                        mode='lines+markers',
                        name='Quarterly Borrow APY',
                        line=dict(color='#ff7f0e', width=2),
                        marker=dict(size=4)
                    )
                )
                data_added = True
        except Exception as e:
            print(f"Error processing quarterly data: {e}")

    if not data_added:
        # Create a sample chart to show structure
        fig.add_annotation(
            text="No historical data available<br>This will show APY trends over time when data is present",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="gray")
        )

    fig.update_layout(
        height=400,
        xaxis_title='Date',
        yaxis_title='Borrow APY (%)',
        hovermode='x unified',
        showlegend=data_added,
        plot_bgcolor='white',
        paper_bgcolor='white'
    )

    return fig

def display_borrower_analysis(borrowers: List[Dict], pool_name: str, pendle_analysis: Dict, net_apy_spread: float = 0):
    """Display top borrowers analysis with profitability calculations"""
    if not borrowers:
        st.info("No borrower data available for this pool.")
        return

    st.subheader("👥 Top 5 Borrowers Analysis")

    borrower_data = []
    borrower_positions = pendle_analysis.get('borrowerPositions', {})

    for i, borrower in enumerate(borrowers[:5]):
        user = borrower.get('user', {})
        address = user.get('address', 'Unknown')
        tag = user.get('tag', '')

        # Get borrower state
        borrower_state = borrower.get('state', {})
        health_factor = borrower.get('healthFactor', 0)

        borrow_amount_usd = borrower_state.get('borrowAssetsUsd', 0)
        collateral_usd = borrower_state.get('collateralUsd', 0)

        # Calculate leverage and profitability
        leverage_ratio = collateral_usd / borrow_amount_usd if borrow_amount_usd > 0 else 0
        effective_apy = leverage_ratio * net_apy_spread if leverage_ratio > 0 else 0
        annual_profit_usd = (collateral_usd * effective_apy / 100) if collateral_usd > 0 else 0

        # Get Pendle position info
        pendle_info = "No"
        has_pendle = False

        if address in borrower_positions:
            # Look through the borrower's positions across markets
            borrower_markets = borrower_positions[address]
            for market_key, market_data in borrower_markets.items():
                if isinstance(market_data, dict) and 'pendlePositions' in market_data:
                    pendle_pos = market_data['pendlePositions']
                    positions = pendle_pos.get('positions', [])

                    if positions:
                        for pos in positions:
                            open_pos = pos.get('openPositions', [])
                            closed_pos = pos.get('closedPositions', [])
                            sy_pos = pos.get('syPositions', [])

                            if open_pos or closed_pos or sy_pos:
                                has_pendle = True
                                pendle_info = f"LP:{len(open_pos)}, Closed:{len(closed_pos)}, SY:{len(sy_pos)}"
                                break

                    if has_pendle:
                        break

        # Estimate strategy type
        strategy_type = "Unknown"
        if collateral_usd > 0 and borrow_amount_usd > 0:
            if leverage_ratio > 2.5:
                strategy_type = "Conservative"
            elif leverage_ratio > 1.8:
                strategy_type = "Moderate"
            elif has_pendle:
                strategy_type = "PT Looping"
            else:
                strategy_type = "High Leverage"
        elif has_pendle:
            strategy_type = "PT Only"

        # Get transaction count
        transactions = borrower.get('transactions', [])
        transaction_count = len(transactions) if transactions else 0

        borrower_data.append({
            'Rank': i + 1,
            'Address': address[:8] + '...' if len(address) > 8 else address,
            'Full Address': address,
            'Borrowed': f"${borrow_amount_usd:,.0f}",
            'Collateral': f"${collateral_usd:,.0f}",
            'Leverage': f"{leverage_ratio:.1f}x",
            'Effective APY': f"{effective_apy:.2f}%",
            'Est. Annual Profit': f"${annual_profit_usd:,.0f}",
            'Health Factor': f"{health_factor:.2f}" if health_factor else 'N/A',
            'Strategy': strategy_type,
            'Pendle': "Yes" if has_pendle else "No",
            'Has Pendle': has_pendle
        })

    borrower_df = pd.DataFrame(borrower_data)

    # Create a clean dataframe for display without background styling issues
    display_df = borrower_df.drop(['Full Address', 'Has Pendle'], axis=1)

    # Display the dataframe with better styling
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True
    )

    # Add profitability explanation
    st.markdown("**💡 Profitability Calculation:**")
    st.markdown(f"""
    - **Leverage** = Collateral Value ÷ Borrowed Amount
    - **Effective APY** = Leverage × Net APY Spread ({net_apy_spread:.2f}%)
    - **Est. Annual Profit** = Collateral Value × Effective APY
    """)

    # Add Etherscan links
    st.markdown("**🔗 Etherscan Links:**")
    cols = st.columns(min(5, len(borrower_df)))
    for idx, (_, row) in enumerate(borrower_df.iterrows()):
        if idx < len(cols):
            with cols[idx]:
                if row['Full Address'] != 'Unknown' and row['Full Address'] != '':
                    st.markdown(f"[{row['Address']}](https://etherscan.io/address/{row['Full Address']})")

    # Show detailed Pendle positions
    pendle_borrowers = borrower_df[borrower_df['Has Pendle'] == True]
    if not pendle_borrowers.empty:
        st.markdown("**🎯 Borrowers with Pendle Positions:**")
        for _, row in pendle_borrowers.iterrows():
            st.markdown(f"• **{row['Address']}** - Strategy: {row['Strategy']}")

def main():
    st.title("🔵 Morpho Blue Pool Analyzer")
    st.markdown("Real-time analysis of Morpho Blue pools for yield strategies and leveraged looping opportunities")

    # Load configuration
    config = load_config()

    # Sidebar
    st.sidebar.title("🎛️ Controls")

    # Data refresh
    if st.sidebar.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

    # Show config status
    if config:
        last_updated = config.get('external_yields', {}).get('last_updated', 'Unknown')
        st.sidebar.caption(f"📊 Yield data updated: {last_updated}")

    # Load data
    with st.spinner("Loading data..."):
        morpho_data = load_morpho_data()
        pendle_summary = load_pendle_summary()
        pendle_analysis = load_pendle_analysis()

    if not morpho_data.get('data'):
        st.error("❌ No Morpho data available. Please run `node get_morpho_data.js` first.")
        return

    # Show data summary in sidebar
    metadata = morpho_data.get('metadata', {})
    st.sidebar.markdown("**📈 Data Summary:**")
    st.sidebar.write(f"Markets: {metadata.get('totalMarkets', 'Unknown')}")
    if metadata.get('generatedAt'):
        st.sidebar.write(f"Generated: {metadata['generatedAt'][:10]}")

    pendle_meta = pendle_analysis.get('metadata', {})
    if pendle_meta.get('totalPTMarkets'):
        st.sidebar.write(f"PT Markets: {pendle_meta['totalPTMarkets']}")

    # Process data
    df = process_morpho_data(morpho_data, pendle_summary, pendle_analysis, config)

    if df.empty:
        st.error("❌ No valid pool data found.")
        return

    # Filters
    st.sidebar.subheader("🔍 Filters")

    # Asset filters
    all_collateral = ['All'] + sorted(df['Collateral Asset'].unique().tolist())
    all_borrow = ['All'] + sorted(df['Borrow Asset'].unique().tolist())

    selected_collateral = st.sidebar.selectbox("Collateral Asset", all_collateral)
    selected_borrow = st.sidebar.selectbox("Borrow Asset", all_borrow)

    # APY spread filter
    min_spread = st.sidebar.slider("Minimum Net APY Spread (%)", -20.0, 30.0, -10.0, 0.1)

    # Pool size filter
    max_size = float(df['Pool Size ($M)'].max()) if not df.empty else 100.0
    min_pool_size = st.sidebar.slider("Minimum Pool Size ($M)", 0.0, max_size, 0.0)

    # Special filters
    show_only_pendle = st.sidebar.checkbox("🎯 Show only Pendle PT markets")
    show_only_profitable = st.sidebar.checkbox("💰 Show only profitable (spread > 0)")

    # Apply filters
    filtered_df = df.copy()

    if selected_collateral != 'All':
        filtered_df = filtered_df[filtered_df['Collateral Asset'] == selected_collateral]

    if selected_borrow != 'All':
        filtered_df = filtered_df[filtered_df['Borrow Asset'] == selected_borrow]

    filtered_df = filtered_df[filtered_df['Net APY Spread (%)'] >= min_spread]
    filtered_df = filtered_df[filtered_df['Pool Size ($M)'] >= min_pool_size]

    if show_only_pendle:
        filtered_df = filtered_df[filtered_df['Is Pendle PT'] == True]

    if show_only_profitable:
        filtered_df = filtered_df[filtered_df['Net APY Spread (%)'] > 0]

    # Main dashboard logic
    if 'selected_pool' not in st.session_state:
        st.session_state.selected_pool = None

    if st.session_state.selected_pool is None:
        # Main heatmap view
        st.header("📊 Pool Heatmap Dashboard")

        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "Total Pools",
                len(filtered_df),
                delta=f"of {len(df)} total"
            )

        with col2:
            profitable_pools = len(filtered_df[filtered_df['Net APY Spread (%)'] > 0])
            total_filtered = len(filtered_df)
            st.metric(
                "Profitable Opportunities",
                profitable_pools,
                delta=f"{profitable_pools/total_filtered*100:.1f}%" if total_filtered > 0 else "0%"
            )

        with col3:
            pendle_pools = len(filtered_df[filtered_df['Is Pendle PT'] == True])
            st.metric(
                "PT Markets",
                pendle_pools,
                delta=f"{pendle_pools/len(df)*100:.0f}% of total" if len(df) > 0 else "0%"
            )

        with col4:
            total_tvl = filtered_df['Pool Size ($M)'].sum()
            st.metric(
                "Filtered TVL",
                f"${total_tvl:,.0f}M",
                delta=f"of ${df['Pool Size ($M)'].sum():,.0f}M total"
            )

        # Add info section explaining calculation differences
        with st.expander("ℹ️ How Net APY Spread is Calculated", expanded=False):
            st.markdown("""
            **Net APY Spread** is the key profitability metric, calculated differently based on market type:

            **🎯 For Pendle PT Markets:**
            - `Net APY Spread = PT Implied APY - Morpho Borrow APY`
            - Uses the fixed yield from the Pendle Principal Token
            - Shows profitability of PT looping strategies

            **💰 For Regular Markets:**
            - `Net APY Spread = External Yield APY - Morpho Borrow APY`
            - Uses estimated yields from external DeFi protocols (Lido, Aave, etc.)
            - Shows profitability of general yield strategies

            **Color Coding:**
            - 🟢 **High Opportunity** (>5% spread): Strong profit potential
            - 🟡 **Moderate** (0-5% spread): Modest profit potential
            - 🔴 **Negative** (<0% spread): Currently unprofitable
            """)

        # Sort options
        sort_options = ['Net APY Spread (%)', 'Pool Size ($M)', 'Morpho Borrow APY (%)', 'Yield APY (%)', 'Utilization (%)']

        col1, col2 = st.columns([3, 1])
        with col1:
            sort_col = st.selectbox("Sort by:", sort_options, index=0)
        with col2:
            sort_ascending = st.checkbox("Ascending", value=False)

        # Sort dataframe
        display_df = filtered_df.sort_values(sort_col, ascending=sort_ascending)

        # Prepare display columns
        display_columns = [
            'Pool', 'Pool Size ($M)', 'Morpho Borrow APY (%)',
            'Yield APY (%)', 'Net APY Spread (%)', 'Status', 'Utilization (%)'
        ]

        # Add PT columns if relevant
        if show_only_pendle or filtered_df['Is Pendle PT'].any():
            if 'PT Implied APY (%)' in display_df.columns:
                display_columns.insert(-2, 'PT Implied APY (%)')

        # Display the main table with color coding
        st.subheader("🎯 Click on a pool row to analyze in detail")

        def style_dataframe(df):
            def highlight_profitable(row):
                net_spread = row.get('Net APY Spread (%)', 0)
                if net_spread > 5.0:
                    return ['background-color: #d4edda; color: #155724;'] * len(row)
                elif net_spread > 0:
                    return ['background-color: #fff3cd; color: #856404;'] * len(row)
                elif net_spread < 0:
                    return ['background-color: #f8d7da; color: #721c24;'] * len(row)
                else:
                    return [''] * len(row)
            return df.style.apply(highlight_profitable, axis=1)

        # Interactive table with selection
        event = st.dataframe(
            style_dataframe(display_df[display_columns]),
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row"
        )

        # Handle row selection
        if event.selection.rows:
            selected_idx = event.selection.rows[0]
            selected_pool_data = display_df.iloc[selected_idx]
            st.session_state.selected_pool = selected_pool_data.to_dict()
            st.rerun()

    else:
        # Drill-down view
        pool_data = st.session_state.selected_pool

        # Header with back button
        col1, col2 = st.columns([1, 6])
        with col1:
            if st.button("← Back"):
                st.session_state.selected_pool = None
                st.rerun()

        with col2:
            st.header(f"📈 {pool_data['Pool']} - Detailed Analysis")

            # Add market links
            col_morpho, col_pendle = st.columns(2)
            with col_morpho:
                morpho_link = pool_data.get('Morpho Link', '')
                if morpho_link:
                    st.markdown(f"🔗 [Open in Morpho]({morpho_link})")

            with col_pendle:
                pendle_link = pool_data.get('Pendle Link')
                if pendle_link:
                    st.markdown(f"🎯 [Open in Pendle]({pendle_link})")

        # Key metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            spread = pool_data['Net APY Spread (%)']
            delta_text = "Strong opportunity" if spread > 5 else "Moderate opportunity" if spread > 0 else "Not profitable"
            st.metric(
                "Net APY Spread",
                f"{spread}%",
                delta=delta_text
            )

        with col2:
            st.metric(
                "Pool Size",
                f"${pool_data['Pool Size ($M)']}M",
                delta="Total liquidity"
            )

        with col3:
            lltv = pool_data.get('LLTV (%)')
            st.metric(
                "LLTV",
                f"{lltv}%" if lltv is not None else "N/A",
                delta="Max loan-to-value"
            )

        with col4:
            st.metric(
                "Utilization",
                f"{pool_data['Utilization (%)']}%",
                delta="Pool efficiency"
            )

        # PT-specific analysis
        if pool_data.get('Is Pendle PT') and pool_data.get('PT Implied APY (%)'):
            st.markdown("### 🎯 Pendle PT Strategy Analysis")
            col1, col2, col3 = st.columns(3)

            with col1:
                pt_apy = pool_data['PT Implied APY (%)']
                st.metric("PT Implied APY", f"{pt_apy}%")

            with col2:
                looping_spread = pt_apy - pool_data['Morpho Borrow APY (%)']
                st.metric("PT Looping Spread", f"{looping_spread:.2f}%",
                         delta="PT Implied APY - Borrow APY")
            with col3:
                st.metric("Strategy Viability",
                         "✅ Profitable" if looping_spread > 0 else "❌ Not Profitable")

        # Historical APY chart
        st.subheader("📊 Historical Borrow APY")
        historical_data = pool_data.get('Historical Data', {})
        fig = create_historical_chart(historical_data, pool_data['Pool'])
        st.plotly_chart(fig, use_container_width=True)

        # Top borrowers analysis
        display_borrower_analysis(
            pool_data.get('Top Borrowers', []),
            pool_data['Pool'],
            pendle_analysis,
            pool_data.get('Net APY Spread (%)', 0)
        )

        # Additional pool details
        with st.expander("🔧 Technical Details"):
            details = {
                'Unique Key': pool_data.get('Unique Key'),
                'Collateral Asset': pool_data['Collateral Asset'],
                'Collateral Address': pool_data.get('Collateral Address'),
                'Borrow Asset': pool_data['Borrow Asset'],
                'Loan Address': pool_data.get('Loan Address'),
                'Is Pendle PT': pool_data['Is Pendle PT'],
                'LLTV': f"{pool_data.get('LLTV (%)', 'N/A')}%",
                'Borrow Assets USD': f"${pool_data.get('Borrow Assets USD', 0):,.0f}",
                'Supply Assets USD': f"${pool_data.get('Supply Assets USD', 0):,.0f}",
                'Morpho Market URL': pool_data.get('Morpho Link', 'N/A'),
                'Pendle Market URL': pool_data.get('Pendle Link', 'N/A') if pool_data.get('Pendle Link') else 'N/A'
            }

            # Add yield source info if available
            if pool_data.get('Is Pendle PT'):
                details['Yield Source'] = 'PT Implied APY (from Pendle market data)'
                details['Net Spread Calculation'] = 'PT Implied APY - Morpho Borrow APY'
            elif config and 'external_yields' in config:
                asset = pool_data['Borrow Asset']
                asset_config = config['external_yields']['assets'].get(asset, {})
                if asset_config:
                    details['Yield Source'] = asset_config.get('source', 'Unknown')
                    details['Confidence Level'] = asset_config.get('confidence', 'Unknown')
                    details['Net Spread Calculation'] = 'External Yield APY - Morpho Borrow APY'
            else:
                details['Yield Source'] = 'External Yield APY (Default estimates)'
                details['Net Spread Calculation'] = 'External Yield APY - Morpho Borrow APY'

            st.json(details)

if __name__ == "__main__":
    main()
