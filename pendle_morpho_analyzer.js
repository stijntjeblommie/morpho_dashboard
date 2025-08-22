/**
 * Pendle Market Analyzer for Morpho
 * This script filters Morpho markets for Pendle PT tokens and queries Pendle API
 */

const fs = require("fs");
const path = require("path");

class PendleMorphoAnalyzer {
  constructor(configPath = "pendle_config.json") {
    this.config = this.loadConfig(configPath);
    this.pendleApiBaseUrl = this.config.apiSettings.pendleApiBaseUrl;
    this.defaultChainId = this.config.apiSettings.defaultChainId;
    this.morphoData = null;
    this.ptMarkets = [];
    this.pendleMarketData = {};
    this.borrowerPositions = {};
  }

  // Load configuration file
  loadConfig(configPath) {
    try {
      const configData = fs.readFileSync(configPath, "utf8");
      const config = JSON.parse(configData);
      console.log(`Configuration loaded from ${configPath}`);
      return config;
    } catch (error) {
      console.warn(
        `Could not load config from ${configPath}, using defaults:`,
        error.message,
      );
      return {
        apiSettings: {
          pendleApiBaseUrl: "https://api-v2.pendle.finance",
          defaultChainId: 1,
          rateLimiting: {
            delayBetweenRequests: 300,
            delayBetweenMarkets: 1000,
            delayBetweenBorrowers: 500,
          },
        },
        fileSettings: {
          morphoDataFile: "morpho_complete_analysis.json",
          outputFile: "pendle_morpho_analysis.json",
        },
        filterCriteria: {
          ptTokenIdentifiers: ["PT-", "PT ", "principal token", "pendle"],
          minUsdFilter: 100,
        },
        logging: { verbose: true },
      };
    }
  }

  // Load and parse the Morpho analysis JSON file
  async loadMorphoData(filePath = null) {
    const dataFile = filePath || this.config.fileSettings.morphoDataFile;
    try {
      console.log(`Loading Morpho data from ${dataFile}...`);
      const jsonData = fs.readFileSync(dataFile, "utf8");
      this.morphoData = JSON.parse(jsonData);
      console.log(
        `Loaded ${this.morphoData.data.length} markets from Morpho analysis`,
      );
      return this.morphoData;
    } catch (error) {
      console.error("Error loading Morpho data:", error);
      throw error;
    }
  }

  // Filter markets for Pendle PT tokens
  filterPTMarkets() {
    if (!this.morphoData || !this.morphoData.data) {
      throw new Error("Morpho data not loaded. Call loadMorphoData() first.");
    }

    console.log("Filtering for Pendle PT markets...");

    this.ptMarkets = this.morphoData.data.filter((marketData) => {
      const collateralSymbol = marketData.market.collateralAsset?.symbol || "";
      const collateralName = marketData.market.collateralAsset?.name || "";

      // Use configuration-based filtering criteria
      const identifiers = this.config.filterCriteria.ptTokenIdentifiers;

      return identifiers.some((identifier) => {
        const lowerIdentifier = identifier.toLowerCase();
        return (
          collateralSymbol.toLowerCase().includes(lowerIdentifier) ||
          collateralName.toLowerCase().includes(lowerIdentifier)
        );
      });
    });

    console.log(
      `Found ${this.ptMarkets.length} PT markets out of ${this.morphoData.data.length} total markets`,
    );

    if (this.ptMarkets.length > 0) {
      console.log("PT Markets found:");
      this.ptMarkets.forEach((marketData, index) => {
        const market = marketData.market;
        console.log(
          `  ${index + 1}. ${market.loanAsset.symbol}/${market.collateralAsset.symbol}`,
        );
        console.log(`     Collateral: ${market.collateralAsset.name}`);
        console.log(`     Address: ${market.collateralAsset.address}`);
        console.log(`     Top Borrowers: ${marketData.topBorrowers.length}`);
      });
    }

    return this.ptMarkets;
  }

  // Query Pendle API
  async queryPendleAPI(endpoint, params = {}) {
    const url = new URL(`${this.pendleApiBaseUrl}${endpoint}`);

    // Add query parameters
    Object.keys(params).forEach((key) => {
      if (params[key] !== null && params[key] !== undefined) {
        url.searchParams.append(key, params[key]);
      }
    });

    try {
      if (this.config.logging.logApiCalls) {
        console.log(`Querying Pendle API: ${url.toString()}`);
      }
      const response = await fetch(url.toString());

      if (!response.ok) {
        console.warn(
          `Pendle API request failed: ${response.status} ${response.statusText}`,
        );
        return null;
      }

      const data = await response.json();
      return data;
    } catch (error) {
      console.error(`Error querying Pendle API: ${endpoint}`, error);
      return null;
    }
  }

  // Get active Pendle markets for chain
  async getActivePendleMarkets(chainId = null) {
    const chain = chainId || this.defaultChainId;
    const endpoint = `/v1/${chain}/markets/active`;

    console.log(`Fetching active Pendle markets for chain ${chain}...`);
    const data = await this.queryPendleAPI(endpoint);

    if (data && data.markets && data.markets.length) {
      console.log(
        `Found ${data.markets.length} active Pendle markets on chain ${chain}`,
      );
    }

    return data ? data.markets : null;
  }

  // Get market data by address
  async getPendleMarketData(marketAddress, chainId = null, timestamp = null) {
    const chain = chainId || this.defaultChainId;
    const endpoint = `/v2/${chain}/markets/${marketAddress}/data`;

    const params = {};
    if (timestamp) {
      params.timestamp = timestamp;
    }

    console.log(`Fetching Pendle market data for ${marketAddress}...`);
    const data = await this.queryPendleAPI(endpoint, params);

    return data;
  }

  // Get market historical data
  async getPendleMarketHistory(
    marketAddress,
    chainId = null,
    timeFrame = "day",
    timestampStart = null,
    timestampEnd = null,
  ) {
    const chain = chainId || this.defaultChainId;
    const endpoint = `/v1/${chain}/markets/${marketAddress}/historical-data`;

    const params = {
      time_frame: timeFrame,
    };

    if (timestampStart) {
      params.timestamp_start = timestampStart;
    }
    if (timestampEnd) {
      params.timestamp_end = timestampEnd;
    }

    console.log(`Fetching Pendle market history for ${marketAddress}...`);
    const data = await this.queryPendleAPI(endpoint, params);

    return data;
  }

  // Get user positions from Pendle dashboard
  async getPendleUserPositions(userAddress, filterUsd = null) {
    const endpoint = `/v1/dashboard/positions/database/${userAddress}`;

    const params = {};
    const minFilter = filterUsd || this.config.filterCriteria.minUsdFilter;
    if (minFilter) {
      params.filterUsd = minFilter;
    }

    console.log(`Fetching Pendle positions for user ${userAddress}...`);
    const data = await this.queryPendleAPI(endpoint, params);

    // Handle 404 gracefully - dashboard endpoint might not be available
    if (data === null) {
      console.log(
        `  No position data available for user ${userAddress} (endpoint may not be accessible)`,
      );
      return { positions: [], error: "Dashboard endpoint not accessible" };
    }

    return data;
  }

  // Main analysis function
  async analyzeAllPTMarkets() {
    console.log("Starting complete Pendle-Morpho analysis...");

    try {
      // First, get active Pendle markets to cross-reference
      const activePendleMarkets = await this.getActivePendleMarkets();

      // Process each PT market found in Morpho data
      for (let i = 0; i < this.ptMarkets.length; i++) {
        const marketData = this.ptMarkets[i];
        const market = marketData.market;
        const collateralAddress = market.collateralAsset.address;

        console.log(
          `\n--- Processing PT Market ${i + 1}/${this.ptMarkets.length} ---`,
        );
        console.log(
          `Market: ${market.loanAsset.symbol}/${market.collateralAsset.symbol}`,
        );
        console.log(`PT Token Address: ${collateralAddress}`);

        // Try to find this PT token in active Pendle markets
        let matchingPendleMarket = null;
        if (activePendleMarkets) {
          matchingPendleMarket = activePendleMarkets.find((pm) => {
            if (!pm.pt) return false;
            // Pendle API returns PT in format "1-0x..." where 1 is chainId
            const ptAddress = pm.pt.includes("-") ? pm.pt.split("-")[1] : pm.pt;
            return (
              ptAddress &&
              ptAddress.toLowerCase() === collateralAddress.toLowerCase()
            );
          });
        }

        if (matchingPendleMarket) {
          console.log(
            `Found matching Pendle market: ${matchingPendleMarket.address}`,
          );

          // Get detailed market data from Pendle
          const marketDetails = await this.getPendleMarketData(
            matchingPendleMarket.address,
          );
          const marketHistory = await this.getPendleMarketHistory(
            matchingPendleMarket.address,
            null,
            "day",
          );

          this.pendleMarketData[market.uniqueKey] = {
            morphoMarket: market,
            pendleMarket: matchingPendleMarket,
            marketDetails: marketDetails,
            marketHistory: marketHistory,
            fetchedAt: new Date().toISOString(),
          };

          await new Promise((resolve) =>
            setTimeout(
              resolve,
              this.config.apiSettings.rateLimiting.delayBetweenRequests,
            ),
          );
        } else {
          console.log(
            `No matching Pendle market found for PT token ${collateralAddress}`,
          );

          this.pendleMarketData[market.uniqueKey] = {
            morphoMarket: market,
            pendleMarket: null,
            error: "No matching Pendle market found",
            fetchedAt: new Date().toISOString(),
          };
        }

        // Process top borrowers for this market
        console.log(
          `Processing ${marketData.topBorrowers.length} top borrowers...`,
        );

        for (let j = 0; j < marketData.topBorrowers.length; j++) {
          const borrower = marketData.topBorrowers[j];
          const userAddress = borrower.user.address;

          console.log(
            `  Fetching Pendle positions for borrower ${j + 1}: ${userAddress}`,
          );

          try {
            // Get user's Pendle positions
            const userPositions =
              await this.getPendleUserPositions(userAddress);

            if (!this.borrowerPositions[userAddress]) {
              this.borrowerPositions[userAddress] = {};
            }

            this.borrowerPositions[userAddress][market.uniqueKey] = {
              morphoBorrowerData: borrower,
              pendlePositions: userPositions,
              fetchedAt: new Date().toISOString(),
            };

            await new Promise((resolve) =>
              setTimeout(
                resolve,
                this.config.apiSettings.rateLimiting.delayBetweenBorrowers,
              ),
            );
          } catch (error) {
            console.error(
              `Error fetching Pendle positions for ${userAddress}:`,
              error,
            );

            if (!this.borrowerPositions[userAddress]) {
              this.borrowerPositions[userAddress] = {};
            }

            this.borrowerPositions[userAddress][market.uniqueKey] = {
              morphoBorrowerData: borrower,
              pendlePositions: null,
              error: error.message,
              fetchedAt: new Date().toISOString(),
            };
          }
        }

        console.log(
          `Completed processing market ${market.loanAsset.symbol}/${market.collateralAsset.symbol}`,
        );
        await new Promise((resolve) =>
          setTimeout(
            resolve,
            this.config.apiSettings.rateLimiting.delayBetweenMarkets,
          ),
        );
      }

      console.log("\nPendle-Morpho analysis completed successfully!");
      return {
        ptMarkets: this.pendleMarketData,
        borrowerPositions: this.borrowerPositions,
      };
    } catch (error) {
      console.error("Error in Pendle-Morpho analysis:", error);
      throw error;
    }
  }

  // Export complete analysis to JSON
  exportAnalysis(filename = null) {
    const outputFile = filename || this.config.fileSettings.outputFile;
    const analysisData = {
      metadata: {
        totalPTMarkets: this.ptMarkets.length,
        totalBorrowers: Object.keys(this.borrowerPositions).length,
        generatedAt: new Date().toISOString(),
        description:
          "Analysis of Pendle PT tokens used as collateral in Morpho markets",
      },
      ptMarketsData: this.pendleMarketData,
      borrowerPositions: this.borrowerPositions,
      originalMorphoMarkets: this.ptMarkets.map((m) => ({
        uniqueKey: m.market.uniqueKey,
        loanAsset: m.market.loanAsset.symbol,
        collateralAsset: m.market.collateralAsset.symbol,
        collateralAddress: m.market.collateralAsset.address,
        topBorrowersCount: m.topBorrowers.length,
        liquidityUsd: m.market.state?.totalLiquidityUsd || 0,
      })),
    };

    try {
      fs.writeFileSync(outputFile, JSON.stringify(analysisData, null, 2));
      console.log(`Analysis exported to ${outputFile}`);

      // Also export summary if configured
      if (this.config.fileSettings.summaryFile) {
        const summary = this.generateSummaryReport();
        fs.writeFileSync(
          this.config.fileSettings.summaryFile,
          JSON.stringify(summary, null, 2),
        );
        console.log(
          `Summary exported to ${this.config.fileSettings.summaryFile}`,
        );
      }

      return analysisData;
    } catch (error) {
      console.error("Error exporting analysis:", error);
      throw error;
    }
  }

  // Generate summary report
  generateSummaryReport() {
    const summary = {
      overview: {
        totalPTMarketsFound: this.ptMarkets.length,
        marketsWithPendleData: Object.keys(this.pendleMarketData).filter(
          (key) => this.pendleMarketData[key].pendleMarket !== null,
        ).length,
        totalUniqueBorrowers: Object.keys(this.borrowerPositions).length,
        totalBorrowerAnalyzed: Object.values(this.borrowerPositions).reduce(
          (sum, userPositions) => sum + Object.keys(userPositions).length,
          0,
        ),
      },
      ptMarkets: this.ptMarkets.map((marketData) => {
        const market = marketData.market;
        const pendleData = this.pendleMarketData[market.uniqueKey];

        return {
          pair: `${market.loanAsset.symbol}/${market.collateralAsset.symbol}`,
          ptTokenName: market.collateralAsset.name,
          ptTokenAddress: market.collateralAsset.address,
          morphoLiquidity: market.state?.totalLiquidityUsd || 0,
          morphoBorrowApy: market.state?.borrowApy || 0,
          morphoUtilization: market.state?.utilization || 0,
          hasPendleData: pendleData?.pendleMarket !== null,
          topBorrowersCount: marketData.topBorrowers.length,
        };
      }),
      topBorrowersByMarket: {},
    };

    // Add top borrower analysis
    this.ptMarkets.forEach((marketData) => {
      const market = marketData.market;
      const marketKey = `${market.loanAsset.symbol}/${market.collateralAsset.symbol}`;

      summary.topBorrowersByMarket[marketKey] = marketData.topBorrowers.map(
        (borrower) => ({
          address: borrower.user.address,
          tag: borrower.user.tag,
          borrowAmountUsd: borrower.state?.borrowAssetsUsd || 0,
          collateralUsd: borrower.state?.collateralUsd || 0,
          healthFactor: borrower.healthFactor,
          hasPendlePositions:
            this.borrowerPositions[borrower.user.address] &&
            this.borrowerPositions[borrower.user.address][market.uniqueKey] &&
            this.borrowerPositions[borrower.user.address][market.uniqueKey]
              .pendlePositions !== null,
        }),
      );
    });

    return summary;
  }
}

// Main execution function
async function main(configPath = null) {
  console.log("=== Pendle-Morpho Market Analyzer ===\n");

  const analyzer = new PendleMorphoAnalyzer(configPath);

  try {
    // Load Morpho data
    await analyzer.loadMorphoData();

    // Filter for PT markets
    const ptMarkets = analyzer.filterPTMarkets();

    if (ptMarkets.length === 0) {
      console.log("No PT markets found in the Morpho data. Exiting.");
      return;
    }

    // Perform complete analysis
    const analysisResults = await analyzer.analyzeAllPTMarkets();

    // Export results
    const exportedData = analyzer.exportAnalysis();

    // Generate and display summary
    const summary = analyzer.generateSummaryReport();

    if (analyzer.config.logging.verbose) {
      console.log("\n=== Analysis Summary ===");
      console.log(JSON.stringify(summary.overview, null, 2));

      console.log("\n=== PT Markets Found ===");
      summary.ptMarkets.forEach((market, index) => {
        console.log(`${index + 1}. ${market.pair}`);
        console.log(`   PT Token: ${market.ptTokenName}`);
        console.log(
          `   Morpho Liquidity: $${market.morphoLiquidity.toLocaleString()}`,
        );
        console.log(
          `   Has Pendle Data: ${market.hasPendleData ? "Yes" : "No"}`,
        );
        console.log(`   Top Borrowers: ${market.topBorrowersCount}`);
      });
    } else {
      console.log(
        `\nAnalysis completed: ${summary.overview.totalPTMarketsFound} PT markets, ${summary.overview.totalUniqueBorrowers} unique borrowers analyzed.`,
      );
    }

    return analysisResults;
  } catch (error) {
    console.error("Error in main execution:", error);
    process.exit(1);
  }
}

// Export for use as module
module.exports = { PendleMorphoAnalyzer, main };

// Run if this is the main file
if (require.main === module) {
  main("pendle_config.json");
}
