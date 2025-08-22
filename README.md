# 🔵 Morpho Blue Pool Analyzer Dashboard

A comprehensive Streamlit-based dashboard for analyzing Morpho Blue lending pools, identifying profitable yield strategies, and monitoring leveraged looping opportunities. Special emphasis on Pendle Principal Token (PT) markets for advanced yield strategies.

![Dashboard](https://img.shields.io/badge/Framework-Streamlit-red) ![Status](https://img.shields.io/badge/Status-Active-green) ![Version](https://img.shields.io/badge/Version-1.0-blue)

## 🎯 Overview

This dashboard provides a **real-time, color-coded heatmap** of Morpho Blue pools, highlighting the most profitable opportunities for yield strategies and leveraged looping. The primary goal is to identify pools where the **Net APY Spread** (External Yield APY - Morpho Borrow APY) presents profitable arbitrage opportunities.

### Key Value Proposition
- **Visual Profitability Analysis**: Instantly identify high-opportunity pools through color coding
- **Pendle PT Specialization**: Advanced analysis of Principal Token looping strategies  
- **Interactive Drill-Down**: Deep dive into pool metrics, borrower behavior, and historical performance
- **Risk Assessment**: Health factor monitoring and position analysis for top borrowers

## 🚀 Features

### 📊 1. Heatmap Dashboard (Main View)
- **Color-Coded Rows**: 
  - 🟢 **Bright Green**: High positive spread (>5%) - Strong opportunities
  - 🟡 **Yellow**: Moderate positive spread (0-5%) - Moderate opportunities  
  - 🔴 **Red**: Negative spread - Currently unprofitable
- **Sortable Columns**: Pool size, APY spreads, utilization rates
- **Advanced Filtering**: Asset types, pool sizes, profitability thresholds
- **Real-Time Data**: Auto-refresh with configurable intervals

### 🎯 2. Pendle PT Market Analysis
- **PT Pool Identification**: Automatically detects Pendle Principal Token collaterals
- **PT Implied APY**: Shows fixed yield rates for PT tokens
- **Looping Profitability**: Calculates PT Implied APY vs Morpho Borrow APY spread
- **Special PT Columns**: Additional metrics specific to PT strategies

### 🔍 3. Interactive Drill-Down Views
When you click on any pool:
- **Pool Parameters**: LLTV, oracle type, interest rate model
- **Historical Charts**: 30/60/90-day APY trends and spread evolution
- **Top 5 Borrowers**: Detailed borrower analysis with strategy detection
- **Risk Metrics**: Health factors, position sizes, estimated profitability

### 📈 4. Top Borrowers Analysis
- **Strategy Detection**: Identifies looping, yield farming, leverage trading
- **Profitability Estimates**: PnL calculations based on transaction analysis
- **Risk Assessment**: Health factors and liquidation proximity
- **Etherscan Integration**: Direct links to borrower addresses

## 🛠️ Installation & Setup

### Prerequisites
- Python 3.8 or higher
- Node.js (for data collection scripts)
- Git (optional, for cloning)

### Step 1: Install Python Dependencies
```bash
cd tool/
pip install -r requirements.txt
```

### Step 2: Data Collection
You need to run the JavaScript data collection scripts first to generate the required JSON files:

```bash
# Collect Morpho Blue market data (REQUIRED)
node get_morpho_data.js

# Run Pendle analysis (OPTIONAL, but highly recommended for PT insights)
node pendle_morpho_analyzer.js
```

This will generate:
- `morpho_complete_analysis.json` - Complete Morpho market data with top borrowers and transactions
- `pendle_morpho_summary.json` - PT market summary with basic metrics (if Pendle script runs)
- `pendle_morpho_analysis.json` - Detailed PT market analysis with borrower positions (if Pendle script runs)

### Step 3: Launch Dashboard

#### Option A: Using the Runner Script (Recommended)
```bash
# Full pipeline: data collection + dashboard
python run_analysis.py --mode full

# Dashboard only (if you already have data)
python run_analysis.py --mode dashboard

# Data collection only
python run_analysis.py --mode collect
```

#### Option B: Direct Launch
```bash
streamlit run morpho_dashboard.py
```

### Step 4: Access Dashboard
Open your browser to: `http://localhost:8501`

## 📁 File Structure

```
tool/
├── morpho_dashboard.py          # Main Streamlit dashboard
├── run_analysis.py              # Utility runner script
├── get_morpho_data.js           # Morpho data collection
├── pendle_morpho_analyzer.js    # Pendle analysis script
├── config.json                  # Configuration settings
├── requirements.txt             # Python dependencies
├── morpho_complete_analysis.json # Generated Morpho data
├── pendle_morpho_summary.json    # Generated Pendle summary data
├── pendle_morpho_analysis.json   # Generated Pendle detailed analysis
└── README.md                    # This file
```

## 📊 Dashboard Usage Guide

### Main Heatmap View

The central feature showing all pools with key metrics:

| Column | Description | Source |
|--------|-------------|--------|
| **Pool** | Pool identifier (e.g., "PT-ezETH / WETH") | Morpho market data |
| **Collateral Asset** | Token used as collateral | Market configuration |
| **Borrow Asset** | Token being borrowed | Market configuration |
| **Pool Size ($M)** | Total liquidity in millions USD | Real-time pool state |
| **Morpho Borrow APY (%)** | Current variable borrow rate | Real-time market data |
| **Yield APY (%)** | PT Implied APY (PT markets) or External Yield (others) | Pendle data / Config file |
| **Net APY Spread (%)** | **KEY METRIC**: Yield APY - Morpho APY | Calculated differently for PT |
| **Status** | Color-coded profitability indicator | Derived from spread |
| **PT Implied APY (%)** | Fixed yield for PT collaterals | Pendle API data |
| **Utilization (%)** | Pool utilization rate | Real-time pool state |

### Filtering & Sorting

**Sidebar Filters:**
- **Asset Filters**: Filter by specific collateral or borrow assets
- **APY Spread Range**: Set minimum profitability threshold
- **Pool Size Range**: Filter by total pool value
- **Pendle PT Only**: Show only Principal Token pools

**Sorting Options:**
- Click column headers to sort
- Choose ascending/descending order
- Default sort by Net APY Spread (highest first)

### Detailed Pool Analysis

Click any pool row to access:

**📋 Pool Parameters:**
- LLTV (Loan-to-Liquidation-Threshold-Value)
- Current utilization and supply rates
- Technical configuration details

**📈 Historical Performance:**
- Interactive charts showing APY trends
- **Net spread evolution over time
- **Profitability timeline analysis

**🔗 Direct Market Access:**
- **Morpho Market Links**: Click to open pool directly in Morpho app
- **Pendle Market Links**: Direct access to PT trading on Pendle (for PT markets)

**👥 Top 5 Borrowers:**
- Largest positions in the selected pool
- Position sizes and collateral amounts
- Health factor and liquidation risk
- **Strategy Detection**: 
  - "Likely Looping" if collateral >> borrowed amount
  - Transaction pattern analysis
  - Estimated P&L calculations
- **Etherscan Links**: Direct access to borrower addresses

## 🎯 Pendle PT Strategy Guide

### Understanding Principal Tokens
Principal Tokens (PT) represent the principal component of yield-bearing assets, providing **fixed yields** until maturity.

### PT Looping Strategy
1. **Supply PT tokens** as collateral on Morpho
2. **Borrow the underlying asset** (e.g., borrow WETH against PT-wstETH)
3. **Convert borrowed WETH** to more wstETH
4. **Deposit wstETH** to get more PT-wstETH
5. **Repeat the cycle** to amplify exposure
6. **Profit from the spread** between PT Implied APY and Morpho Borrow APY

**🎯 Net APY Calculation for PT Markets:**
- For PT markets: `Net APY Spread = PT Implied APY - Morpho Borrow APY`
- This shows the direct profitability of PT looping strategies
- Uses actual PT market data, not external yield estimates

### PT Opportunity Identification
The dashboard automatically:
- 🎯 **Flags PT Pools**: Special indicators for all PT markets
- 📊 **Shows PT APY**: Displays the fixed yield component
- 💰 **Calculates Looping Spread**: PT APY - Borrow APY (used for Net APY Spread)
- 🔗 **Provides Direct Links**: Click to open in Morpho or Pendle apps
- 🔍 **Ranks Opportunities**: Sorts PT markets by profitability

### PT Risk Considerations
- **Maturity Risk**: PT tokens have expiration dates
- **Liquidity Risk**: PT markets may have limited depth
- **Price Risk**: PT prices converge to underlying at maturity
- **Smart Contract Risk**: Additional protocol dependencies

## ⚙️ Configuration

### External Yield Rates
Update yield rates in `config.json`:

```json
{
  "external_yields": {
    "assets": {
      "WETH": {
        "apy": 3.2,
        "source": "Lido Staking",
        "confidence": "high"
      },
      "USDC": {
        "apy": 4.5,
        "source": "Lending protocols average",
        "confidence": "medium"
      }
    }
  }
}
```

### Dashboard Settings
Customize behavior in `config.json`:

```json
{
  "dashboard_settings": {
    "refresh_interval_minutes": 5,
    "default_sort_column": "Net APY Spread (%)",
    "default_sort_ascending": false
  },
  "color_thresholds": {
    "high_profit_threshold": 5.0,
    "moderate_profit_threshold": 0.0
  }
}
```

### Data Sources
Configure API endpoints:

```json
{
  "data_sources": {
    "morpho_api": "https://api.morpho.org/graphql",
    "pendle_api": "https://api.pendle.finance/core",
    "etherscan_base_url": "https://etherscan.io/address/"
  }
}
```

## 🔧 Troubleshooting

### Common Issues

**❌ Dashboard won't start:**
```bash
# Check Python version
python --version  # Should be 3.8+

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall

# Try direct launch
streamlit run morpho_dashboard.py --server.port 8502
```

**❌ No data loading:**
```bash
# Verify data files exist
ls -la *.json

# Check data file integrity
python check_data.py

# Re-run data collection if needed
node get_morpho_data.js
node pendle_morpho_analyzer.js  # Optional but recommended
```

**❌ Empty or error screens:**
- Ensure JSON files are valid (not corrupted)
- Check JavaScript scripts completed successfully
- Verify Node.js is installed for data collection
- Review terminal output for error messages

**❌ Performance issues:**
- Reduce data collection scope in JS scripts
- Increase cache TTL in dashboard settings
- Close other resource-intensive applications
- Check available RAM (dashboard is memory intensive)

### Debug Mode
Add debug information temporarily:

```python
# In morpho_dashboard.py, add after data loading:
if st.sidebar.checkbox("Debug Mode"):
    st.write("Morpho data keys:", list(morpho_data.keys()))
    st.write("Sample market:", morpho_data.get('data', [])[:1])
    st.write("DataFrame shape:", df.shape)
    st.write("DataFrame columns:", df.columns.tolist())
```

## 📊 Data Requirements

### Input Files

**1. morpho_complete_analysis.json**
Generated by `get_morpho_data.js`, contains:
```json
{
  "metadata": {
    "totalMarkets": 156,
    "generatedAt": "2024-03-01T10:30:00Z"
  },
  "data": [
    {
      "market": {
        "uniqueKey": "0x123...",
        "loanAsset": {"symbol": "WETH", "address": "0x..."},
        "collateralAsset": {"symbol": "PT-ezETH", "address": "0x..."},
        "state": {
          "borrowApy": 0.045,
          "totalLiquidityUsd": 25000000,
          "utilization": 0.75
        }
      },
      "topBorrowers": [...]
    }
  ]
}
```

**2. pendle_morpho_summary.json** (Optional)
Generated by `pendle_morpho_analyzer.js`, contains:
```json
{
  "overview": {
    "totalPTMarketsFound": 25,
    "marketsWithPendleData": 18,
    "totalUniqueBorrowers": 450
  },
  "ptMarkets": [
    {
      "pair": "DAI/PT-USDe-25SEP2025",
      "ptTokenAddress": "0x...",
      "morphoBorrowApy": 0.045,
      "hasPendleData": true
    }
  ]
}
```

**3. pendle_morpho_analysis.json** (Optional)
Generated by `pendle_morpho_analyzer.js`, contains detailed analysis:
```json
{
  "metadata": {
    "totalPTMarkets": 25,
    "totalBorrowers": 450,
    "generatedAt": "2024-03-01T10:30:00Z"
  },
  "ptMarketsData": {
    "market_key": {
      "morphoMarket": {...},
      "pendleMarket": {
        "impliedApy": 8.5,
        "ptPrice": 0.95,
        "liquidity": {"usd": 2500000}
      }
    }
  },
  "borrowerPositions": {
    "0x123...": {
      "pendlePositions": {
        "ptPositions": [...],
        "ytPositions": [...]
      }
    }
  }
}
```

**4. config.json**
Configuration file with yield rates and settings (provided)

### Data Freshness
- **Morpho Data**: Refresh every 5-10 minutes for active monitoring  
- **Pendle Summary**: Refresh every few hours for PT market updates
- **Pendle Analysis**: Refresh daily for detailed borrower position analysis
- **Config**: Update yields weekly or when market conditions change significantly

### Data Validation
Use the data checker to verify file integrity:
```bash
python check_data.py
```
This will validate all JSON files and show detailed statistics about your data.

## 🚀 Advanced Features

### Net APY Spread Calculation
The dashboard uses different yield sources depending on market type:

```python
# PT Markets: Use PT Implied APY
if is_pendle_pt and pt_implied_apy:
    comparison_apy = pt_implied_apy * 100  # PT Implied APY
else:
    comparison_apy = calculate_external_yield_apy(loan_symbol, config)  # External yield

net_apy_spread = comparison_apy - morpho_borrow_apy
```

### Strategy Detection Algorithm
The dashboard analyzes borrower transactions to identify strategies:

```python
# Simplified strategy detection logic
if total_collateral > total_borrowed * 1.5:
    strategy = "Likely Looping"
    estimated_pnl = calculate_looping_pnl(transactions)
elif has_farming_patterns(transactions):
    strategy = "Yield Farming"
else:
    strategy = "Simple Leverage"
```

### Historical Analysis
- **APY Trends**: Track borrow rates and external yields over time
- **Spread Evolution**: Monitor profitability changes
- **Volatility Analysis**: Assess strategy stability
- **Seasonal Patterns**: Identify recurring opportunities

### Risk Metrics
- **Health Factor Monitoring**: Track borrower safety margins
- **Utilization Warnings**: Alert on high pool utilization
- **Concentration Risk**: Monitor large position holders
- **Liquidity Depth**: Assess market depth for strategies

## 🔄 Data Pipeline

### Automated Updates (Future Enhancement)
```bash
# Cron job for automated data refresh
0 */10 * * * cd /path/to/tool && node get_morpho_data.js
0 6 * * * cd /path/to/tool && node pendle_morpho_analyzer.js
```

### API Integration Roadmap
- [ ] Real-time Morpho GraphQL integration
- [ ] Live Pendle API connection
- [ ] DeFiLlama yield aggregation
- [ ] Webhook support for alerts
- [ ] Historical data persistence

## 📈 Usage Examples

### Finding High-Yield Opportunities
1. **Filter for high spreads**: Set minimum APY spread to 3%
2. **Sort by profitability**: Order by Net APY Spread descending
3. **Check pool size**: Ensure sufficient liquidity for your capital
4. **Click market links**: Open directly in Morpho or Pendle apps
5. **Analyze top borrowers**: Learn from successful strategies

### PT Looping Analysis
1. **Enable PT-only view**: Check "Show only Pendle PT markets"
2. **Compare PT APY vs Borrow APY**: Net spread uses PT Implied APY directly
3. **Click Pendle links**: Open PT markets directly in Pendle app
4. **Check maturity dates**: Ensure sufficient time horizon
5. **Assess liquidity**: Verify adequate PT market depth

### Risk Assessment
1. **Monitor health factors**: Focus on borrowers with HF > 1.2
2. **Check utilization**: Avoid pools with >90% utilization
3. **Analyze borrower strategies**: Understand successful approaches
4. **Track historical performance**: Verify strategy consistency

## ⚠️ Risk Disclaimers

**IMPORTANT: This tool is for informational purposes only and does not constitute financial advice.**

### DeFi Risks
- **Smart Contract Risk**: Bugs or exploits in protocols
- **Liquidation Risk**: Collateral value declining below threshold
- **Oracle Risk**: Price feed manipulation or failures
- **Governance Risk**: Protocol parameter changes
- **Market Risk**: High volatility and correlation

### Strategy-Specific Risks
- **Looping Risk**: Amplified exposure to underlying asset
- **PT Maturity Risk**: Token value convergence at expiration
- **Liquidity Risk**: Insufficient market depth for exits
- **Gas Cost Risk**: Transaction costs eating into profits

### Best Practices
1. **Start Small**: Test strategies with small amounts
2. **Diversify**: Don't concentrate all funds in one strategy
3. **Monitor Continuously**: Check positions and health factors regularly
4. **Set Limits**: Define maximum acceptable losses
5. **Understand Protocols**: Research all involved smart contracts

## 🤝 Contributing

### Development Setup
```bash
git clone <repository>
cd tool/
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Adding New Features
1. **New Yield Sources**: Update `config.json` external_yields section
2. **New Metrics**: Modify `process_morpho_data()` function in morpho_dashboard.py
3. **New Visualizations**: Add charts in drill-down views using Plotly
4. **New Filters**: Extend sidebar filter options
5. **New Data Sources**: Update data loading functions to handle additional JSON structures

### Code Structure
```
morpho_dashboard.py/
├── load_config()           # Configuration management
├── load_morpho_data()      # Data loading utilities
├── process_morpho_data()   # Data transformation
├── create_historical_chart() # Visualization components
├── display_borrower_analysis() # Borrower analysis
└── main()                  # Main dashboard logic

### Utility Scripts
```
check_data.py               # Data validation utility
start_dashboard.py          # Simple dashboard launcher  
run_analysis.py            # Full pipeline runner
```
```

## 📄 License

MIT License - see LICENSE file for details.

## 🙏 Acknowledgments

- **Morpho Protocol**: Revolutionary lending infrastructure
- **Pendle Finance**: Innovative yield tokenization
- **Streamlit**: Excellent Python web framework
- **Plotly**: Beautiful interactive visualizations
- **DeFi Community**: Open source collaboration

---

**🔵 Start analyzing Morpho Blue opportunities today with this comprehensive dashboard!**

## 🔧 Quick Start Commands

```bash
# 1. Check if you have required data
python check_data.py

# 2. If you need data, collect it
node get_morpho_data.js                    # Required
node pendle_morpho_analyzer.js             # Recommended

# 3. Launch dashboard (choose one)
python start_dashboard.py                  # Guided launcher
python run_analysis.py --mode dashboard    # Advanced launcher  
streamlit run morpho_dashboard.py          # Direct launch
```

## 🆘 Getting Help

If you encounter issues:

1. **Check data files**: Run `python check_data.py`
2. **Verify dependencies**: Run `pip install -r requirements.txt`
3. **Test Node.js**: Run `node --version` (should be 14+ for data scripts)
4. **Check file permissions**: Ensure scripts are executable
5. **Review logs**: Look for error messages in terminal output

*For questions, issues, or contributions, please open an issue in the repository.*

*Last Updated: March 2024*