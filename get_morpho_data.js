/**
 * Complete Morpho Markets Data Builder
 * This script fetches all markets, top borrowers, and their transactions
 */

class MorphoDataBuilder {
  constructor(graphqlEndpoint, apiKey = null) {
    this.endpoint = graphqlEndpoint;
    this.apiKey = apiKey;
    this.allMarketsData = [];
  }

  async query(query, variables = {}) {
    const headers = {
      "Content-Type": "application/json",
    };

    if (this.apiKey) {
      headers["Authorization"] = `Bearer ${this.apiKey}`;
    }

    const response = await fetch(this.endpoint, {
      method: "POST",
      headers,
      body: JSON.stringify({
        query,
        variables,
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const result = await response.json();
    if (result.errors) {
      throw new Error(`GraphQL errors: ${JSON.stringify(result.errors)}`);
    }

    return result.data;
  }

  // Step 1: Get all Morpho markets
  async getAllMarkets() {
    console.log("Fetching all Morpho markets...");

    const query = `
      query GetAllMorphoMarkets($first: Int, $skip: Int) {
        markets(
          first: $first
          skip: $skip
          orderBy: TotalLiquidityUsd
          orderDirection: Desc
          where: {
            whitelisted: true
          }
        ) {
          items {
            uniqueKey
            id
            loanAsset {
              symbol
              name
              address
              decimals
              priceUsd
            }
            collateralAsset {
              symbol
              name
              address
              decimals
              priceUsd
            }
            lltv
            state {
              borrowApy
              netBorrowApy
              supplyApy
              sizeUsd
              totalLiquidityUsd
              utilization
              borrowAssetsUsd
              supplyAssetsUsd
              fee
              timestamp
            }
            historicalState {
              monthlyBorrowApy {
                x
                y
              }
              quarterlyBorrowApy {
                x
                y
              }
              monthlyNetBorrowApy {
                x
                y
              }
              quarterlyNetBorrowApy {
                x
                y
              }
            }
          }
          pageInfo {
            count
            countTotal
          }
        }
      }
    `;

    let allMarkets = [];
    let skip = 0;
    const batchSize = 100;
    let hasMore = true;

    while (hasMore) {
      const data = await this.query(query, { first: batchSize, skip });
      //const data = await this.query(query, { first: 20, skip: 0 });
      const markets = data.markets.items;

      allMarkets = allMarkets.concat(markets);
      console.log(
        `Fetched ${markets.length} markets (total: ${allMarkets.length})`,
      );

      hasMore = markets.length === batchSize;
      skip += batchSize;

      // Add small delay to avoid rate limiting
      await new Promise((resolve) => setTimeout(resolve, 100));
    }

    console.log(`Total markets fetched: ${allMarkets.length}`);
    return allMarkets;
  }

  // Step 2: Get top 5 borrowers for a specific market
  async getTopBorrowersForMarket(marketUniqueKey) {
    const query = `
      query GetTop5BorrowersForMarket($marketUniqueKey: String!) {
        marketPositions(
          first: 5
          orderBy: BorrowShares
          orderDirection: Desc
          where: {
            marketUniqueKey_in: [$marketUniqueKey]
            borrowShares_gte: "1"
          }
        ) {
          items {
            user {
              address
              id
              tag
            }
            healthFactor
            priceVariationToLiquidationPrice
            state {
              borrowShares
              borrowAssets
              borrowAssetsUsd
              supplyShares
              supplyAssets
              supplyAssetsUsd
              collateral
              collateralUsd
              timestamp
            }
          }
          pageInfo {
            count
            countTotal
          }
        }
      }
    `;

    const data = await this.query(query, { marketUniqueKey });
    return data.marketPositions.items;
  }

  // Step 3: Get transactions for a specific user
  async getUserTransactions(userAddress, marketUniqueKey = null) {
    const query = `
      query GetUserTransactions($userAddress: String!, $marketUniqueKey_in: [String!], $first: Int, $skip: Int) {
        transactions(
          first: $first
          skip: $skip
          orderBy: Timestamp
          orderDirection: Desc
          where: {
            userAddress_in: [$userAddress]
            marketUniqueKey_in: $marketUniqueKey_in
          }
        ) {
          items {
            id
            hash
            blockNumber
            timestamp
            type
            data {
              ... on MarketCollateralTransferTransactionData {
                assets
                assetsUsd
                market {
                  uniqueKey
                  loanAsset { symbol }
                  collateralAsset { symbol }
                }
              }
              ... on MarketTransferTransactionData {
                assets
                assetsUsd
                shares
                market {
                  uniqueKey
                  loanAsset { symbol }
                  collateralAsset { symbol }
                }
              }
              ... on MarketLiquidationTransactionData {
                repaidAssets
                repaidAssetsUsd
                seizedAssets
                seizedAssetsUsd
                liquidator
                market {
                  uniqueKey
                  loanAsset { symbol }
                  collateralAsset { symbol }
                }
              }
            }
          }
          pageInfo {
            count
            countTotal
          }
        }
      }
    `;

    // The pagination loop remains the same
    let allTransactions = [];
    let skip = 0;
    const batchSize = 100;
    let hasMore = true;

    while (hasMore) {
      const variables = {
        userAddress,
        marketUniqueKey_in: marketUniqueKey ? [marketUniqueKey] : null,
        first: batchSize,
        skip: skip,
      };

      const data = await this.query(query, variables);
      const transactions = data.transactions.items;

      allTransactions = allTransactions.concat(transactions);

      if (
        transactions.length < batchSize ||
        allTransactions.length >= data.transactions.pageInfo.countTotal
      ) {
        hasMore = false;
      }

      skip += batchSize;

      await new Promise((resolve) => setTimeout(resolve, 100));
    }

    return allTransactions;
  }

  // Main function to build complete dataset
  async buildCompleteDataset() {
    console.log("Starting complete Morpho markets analysis...");

    try {
      // Step 1: Get all markets
      const markets = await this.getAllMarkets();

      // Step 2: For each market, get top borrowers and their transactions
      for (let i = 0; i < markets.length; i++) {
        const market = markets[i];
        if (!market.loanAsset || !market.collateralAsset) {
          console.warn(
            `Skipping market at index ${i} due to missing asset data. Market ID: ${market.id || "N/A"}`,
          );
          continue; // Skips to the next market
        }

        console.log(`Market Unique Key: ${market.uniqueKey}`);
        console.log(typeof market.uniqueKey);

        console.log(
          `Processing market ${i + 1}/${markets.length}: ${market.loanAsset.symbol}/${market.collateralAsset.symbol}`,
        );

        try {
          // Get top 5 borrowers for this market
          const topBorrowers = await this.getTopBorrowersForMarket(
            market.uniqueKey,
          );

          // For each borrower, get their transactions
          const borrowersWithTransactions = [];

          for (let j = 0; j < topBorrowers.length; j++) {
            const borrower = topBorrowers[j];

            console.log(
              `  Fetching transactions for borrower ${j + 1}/${topBorrowers.length}: ${borrower.user.address}`,
            );

            try {
              // Get all transactions for this user in this market
              const transactions = await this.getUserTransactions(
                borrower.user.address,
                market.uniqueKey,
              );

              borrowersWithTransactions.push({
                ...borrower,
                transactions,
              });

              // Add delay between requests
              await new Promise((resolve) => setTimeout(resolve, 200));
            } catch (error) {
              console.error(
                `Error fetching transactions for ${borrower.user.address}:`,
                error,
              );
              borrowersWithTransactions.push({
                ...borrower,
                transactions: [],
                error: error.message,
              });
            }
          }

          // Add the complete market data
          this.allMarketsData.push({
            market,
            topBorrowers: borrowersWithTransactions,
            fetchedAt: new Date().toISOString(),
          });

          console.log(
            `  Completed market ${market.loanAsset.symbol}/${market.collateralAsset.symbol}`,
          );
        } catch (error) {
          console.error(`Error processing market ${market.uniqueKey}:`, error);

          this.allMarketsData.push({
            market,
            topBorrowers: [],
            error: error.message,
            fetchedAt: new Date().toISOString(),
          });
        }

        // Add delay between markets to avoid rate limiting
        await new Promise((resolve) => setTimeout(resolve, 500));
      }

      console.log("Complete dataset built successfully!");
      return this.allMarketsData;
    } catch (error) {
      console.error("Error building complete dataset:", error);
      throw error;
    }
  }

  // Export data to JSON
  exportToJSON(filename = "morpho_complete_analysis.json") {
    const dataToExport = {
      metadata: {
        totalMarkets: this.allMarketsData.length,
        generatedAt: new Date().toISOString(),
        dataStructure: "markets -> topBorrowers -> transactions",
      },
      data: this.allMarketsData,
    };

    // In browser environment
    if (typeof window !== "undefined") {
      const blob = new Blob([JSON.stringify(dataToExport, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    }
    // In Node.js environment
    else if (typeof require !== "undefined") {
      const fs = require("fs");
      fs.writeFileSync(filename, JSON.stringify(dataToExport, null, 2));
    }

    return dataToExport;
  }

  // Generate summary statistics
  generateSummary() {
    const summary = {
      totalMarkets: this.allMarketsData.length,
      totalBorrowers: this.allMarketsData.reduce(
        (sum, market) => sum + market.topBorrowers.length,
        0,
      ),
      totalTransactions: this.allMarketsData.reduce(
        (sum, market) =>
          sum +
          market.topBorrowers.reduce(
            (borrowerSum, borrower) =>
              borrowerSum +
              (borrower.transactions ? borrower.transactions.length : 0),
            0,
          ),
        0,
      ),
      marketsBySize: this.allMarketsData
        .sort(
          (a, b) =>
            (b.market.state.totalLiquidityUsd || 0) -
            (a.market.state.totalLiquidityUsd || 0),
        )
        .slice(0, 10)
        .map((m) => ({
          pair: `${m.market.loanAsset.symbol}/${m.market.collateralAsset.symbol}`,
          liquidityUsd: m.market.state.totalLiquidityUsd,
          borrowApy: m.market.state.borrowApy,
          utilization: m.market.state.utilization,
        })),
    };

    return summary;
  }
}

// Usage Example
async function main() {
  const builder = new MorphoDataBuilder("https://api.morpho.org/graphql");

  try {
    // Build complete dataset
    const completeData = await builder.buildCompleteDataset();

    // Export to JSON
    builder.exportToJSON("morpho_complete_analysis.json");

    // Generate summary
    const summary = builder.generateSummary();
    console.log("Dataset Summary:", summary);

    return completeData;
  } catch (error) {
    console.error("Error in main:", error);
  }
}

// Export for use
if (typeof module !== "undefined" && module.exports) {
  module.exports = { MorphoDataBuilder, main };
}

// Run if this is the main file
if (typeof window === "undefined" && require.main === module) {
  main();
}
