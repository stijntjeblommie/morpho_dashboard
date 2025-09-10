#!/usr/bin/env node
"use strict";

/**
 * Morpho + Pendle Collector (single file)
 *
 * - Uses your exact GraphQL queries (unchanged).
 * - Paginates and aggregates:
 *   • All whitelisted Morpho markets (interval DAY)
 *   • Top 5 borrowers per market
 *   • All transactions per borrower in that market (paginated)
 *   • Verified curators + all vaults (paginated)
 *   • Top 5 depositors per vault (with their transactions)
 * - Identifies Morpho PT markets, matches to Pendle active markets to get marketAddress,
 *   then fetches:
 *   • /v2/{chain}/markets/{marketAddress}/data
 *   • /v1/{chain}/markets/{marketAddress}/historical-data (time_frame=day)
 *   • /v1/dashboard/positions/database/{userAddress} for top borrowers (PT markets only)
 *
 * Output
 * ------
 * 1) JSON:   --output path.json     (optional, defaults to none)
 * 2) CSV:    --csv path.csv         (one CSV file with “__sheet” column + section headers)
 * 3) Excel:  --excel path.xls       (true multi-sheet SpreadsheetML; no dependencies)
 *
 * First CLI arg for testing
 * -------------------------
 * The FIRST argument can be a testing flag:
 *   node morpho_pendle_collector.js --test [other flags...]
 * In test mode we limit markets and history for quick runs.
 *
 * Example usage
 * -------------
 * # Quick test on mainnet with minimal data:
 * node morpho_pendle_collector.js --test --chains 1 --csv morpho_pendle.csv --excel morpho_pendle.xls
 *
 * # Full run, multiple chains, all outputs:
 * node morpho_pendle_collector.js --chains 1,8453 --output data.json --csv data.csv --excel data.xls
 *
 * # Custom limits and pacing:
 * node morpho_pendle_collector.js --chains 1 --markets 10 --tx-page 200 --concurrency 4 --rate-limit 200 --max-retries 5 --max-history 90 --csv out.csv
 *
 * Requirements
 * ------------
 * - Node.js v18+ (for global fetch). No external NPM deps needed.
 */

const fs = require("fs");
const path = require("path");

function showHelp() {
  console.log(`
Morpho + Pendle Data Collector

Usage: node data_collector.js [options]

Options:
  --test                Test mode (limited data for quick runs)
  --chains <ids>        Comma-separated chain IDs (default: 1)
  --markets <n>         Max markets per chain (default: unlimited)
  --tx-page <n>         Transactions per page (default: 100)
  --concurrency <n>     Concurrent requests (default: 4)
  --rate-limit <ms>     Delay between requests (default: 200ms)
  --max-retries <n>     Max retry attempts on errors (default: 5)
  --max-history <days>  Max historical data days (default: 365)

Output Options:
  --output <file>       JSON output file
  --csv <file>          CSV output file (default: morpho_pendle_data.csv)
  --excel <file>        Excel output file

Environment Variables:
  CONCURRENCY           Default concurrency level
  RATE_LIMIT_MS         Default rate limit in milliseconds
  MAX_RETRIES           Default max retry attempts
  OUTPUT_FILE           Default JSON output file

Examples:
  # Quick test run
  node data_collector.js --test --csv test.csv

  # Full production run with enhanced error handling
  node data_collector.js --chains 1,8453 --rate-limit 300 --max-retries 8 --csv production.csv

  # Custom limits for server-friendly collection
  node data_collector.js --concurrency 2 --rate-limit 500 --max-retries 10 --csv safe.csv
`);
}

// Parse CLI args
const argv = {};
for (let i = 2; i < process.argv.length; i++) {
  const arg = process.argv[i];
  if (arg.startsWith("--")) {
    const key = arg.slice(2);
    const next = process.argv[i + 1];
    if (next && !next.startsWith("--")) {
      argv[key] = next;
      i++;
    } else {
      argv[key] = true;
    }
  }
}

// Check for help flag
if (argv.help || argv.h) {
  showHelp();
  process.exit(0);
}

// ---------- Enforce Node 18+ (fetch present) ----------
if (typeof fetch !== "function") {
  throw new Error("This script requires Node.js 18+ (global fetch).");
}

// ---------- Endpoints ----------
const MORPHO_ENDPOINT = "https://api.morpho.org/graphql";
const PENDLE_BASE_URL = "https://api-v2.pendle.finance/core";

// ---------- CLI parsing ----------
function parseArgs(argv) {
  const args = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith("--")) {
      const eq = a.indexOf("=");
      if (eq !== -1) {
        const key = a.slice(2, eq);
        const val = a.slice(eq + 1);
        args[key] = val;
      } else {
        const key = a.slice(2);
        const next = argv[i + 1];
        if (next && !next.startsWith("-")) {
          args[key] = next;
          i++;
        } else {
          args[key] = true;
        }
      }
    } else if (a.startsWith("-")) {
      const key = a.slice(1);
      const next = argv[i + 1];
      if (next && !next.startsWith("-")) {
        args[key] = next;
        i++;
      } else {
        args[key] = true;
      }
    } else {
      args._.push(a);
    }
  }
  return args;
}

// const argv = parseArgs(process.argv.slice(2));
const firstArg = process.argv[2] || "";
const firstArgIsTest = firstArg === "--test" || firstArg === "-t";
const testMode = firstArgIsTest || argv.test === true || argv.t === true;

const CONFIG = {
  chains: (argv.chains || argv.c || process.env.PENDLE_CHAINS || "1")
    .split(",")
    .map((c) => c.trim())
    .filter(Boolean),
  morphoPageSize: parseInt(
    argv["page-size"] ?? process.env.MORPHO_PAGE_SIZE ?? "50",
    10,
  ),
  txPageSize: parseInt(
    argv["tx-page"] ?? process.env.TX_PAGE_SIZE ?? "200",
    10,
  ),
  pendleMinUsd: parseFloat(
    argv["pendle-min-usd"] ?? process.env.PENDLE_MIN_USD ?? "100",
  ),
  concurrency: Math.max(
    1,
    parseInt(argv.concurrency ?? process.env.CONCURRENCY ?? "4", 10),
  ),
  rateLimitMs: Math.max(
    0,
    parseInt(argv["rate-limit"] ?? process.env.RATE_LIMIT_MS ?? "200", 10),
  ),
  maxRetries: Math.max(
    1,
    parseInt(argv["max-retries"] ?? process.env.MAX_RETRIES ?? "5", 10),
  ),
  outputJson: argv.output || process.env.OUTPUT_FILE || null,
  csvPath: argv.csv || "morpho_pendle_data.csv",
  excelPath: argv.excel || argv.xlsx || null,
  marketsLimit: argv.markets ? parseInt(argv.markets, 10) : testMode ? 3 : null,
  maxHistory: argv["max-history"]
    ? parseInt(argv["max-history"], 10)
    : testMode
      ? 30
      : null,
};

// In test mode, soften defaults for faster runs
if (testMode) {
  CONFIG.concurrency = Math.min(CONFIG.concurrency, 2);
  CONFIG.morphoPageSize = Math.min(CONFIG.morphoPageSize, 25);
  CONFIG.txPageSize = Math.min(CONFIG.txPageSize, 50);
}

// ---------- Small utils ----------
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function pLimit(concurrency) {
  const queue = [];
  let active = 0;
  const next = () => {
    active--;
    if (queue.length) queue.shift()();
  };
  return (fn) =>
    new Promise((resolve, reject) => {
      const run = () => {
        active++;
        Promise.resolve()
          .then(fn)
          .then((v) => {
            next();
            resolve(v);
          })
          .catch((e) => {
            next();
            reject(e);
          });
      };
      if (active < concurrency) run();
      else queue.push(run);
    });
}

function normalizeAddress(addr) {
  return (addr || "").toLowerCase();
}

function isLikelyPTTokenSymbolOrName(symbol, name) {
  const s = (symbol || "").toLowerCase();
  const n = (name || "").toLowerCase();
  return (
    s.startsWith("pt-") ||
    s.startsWith("pt ") ||
    s.includes("pendle") ||
    n.includes("pendle") ||
    n.includes("principal token")
  );
}

function extractPtAddressFromPendleActive(ptField) {
  if (typeof ptField === "string") {
    const parts = ptField.split("-");
    return normalizeAddress(parts[parts.length - 1]);
  }
  if (ptField && typeof ptField === "object") {
    if (ptField.address) return normalizeAddress(ptField.address);
    if (ptField.token) return normalizeAddress(ptField.token);
    if (ptField.id) return normalizeAddress(ptField.id);
  }
  return "";
}

// ---------- Network helpers ----------
async function fetchJsonWithRetry(url, opts = {}, tryNum = 1) {
  const res = await fetch(url, opts);
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    if (
      tryNum < CONFIG.maxRetries &&
      [429, 500, 502, 503, 504].includes(res.status)
    ) {
      // Exponential backoff with jitter for server overload
      const baseDelay = Math.min(1000 * Math.pow(2, tryNum), 30000);
      const jitter = Math.random() * 1000;
      const delay = baseDelay + jitter;

      console.warn(
        `[Retry ${tryNum}/${CONFIG.maxRetries}] HTTP ${res.status} - Waiting ${Math.round(delay)}ms before retry...`,
      );
      await sleep(delay);
      return fetchJsonWithRetry(url, opts, tryNum + 1);
    }
    throw new Error(`HTTP ${res.status} ${res.statusText} - ${url} - ${body}`);
  }
  return res.json();
}

async function gqlRequest(query, variables, tryNum = 1) {
  const res = await fetch(MORPHO_ENDPOINT, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ query, variables }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    if (
      tryNum < CONFIG.maxRetries &&
      [429, 500, 502, 503, 504].includes(res.status)
    ) {
      // Enhanced exponential backoff for GraphQL errors
      const baseDelay = Math.min(1500 * Math.pow(2, tryNum), 45000);
      const jitter = Math.random() * 1500;
      const delay = baseDelay + jitter;

      console.warn(
        `[GraphQL Retry ${tryNum}/${CONFIG.maxRetries}] ${res.status} - Waiting ${Math.round(delay)}ms before retry...`,
      );
      await sleep(delay);
      return gqlRequest(query, variables, tryNum + 1);
    }
    throw new Error(`GraphQL ${res.status} ${res.statusText}: ${text}`);
  }
  const json = await res.json();
  if (json.errors) {
    if (tryNum < 3) {
      await sleep(200 * tryNum);
      return gqlRequest(query, variables, tryNum + 1);
    }
    if (json.errors) {
      // Check if errors indicate server overload
      const errorMessage = JSON.stringify(json.errors);
      if (
        errorMessage.includes("Internal server error") &&
        tryNum < CONFIG.maxRetries
      ) {
        const delay = 2000 * Math.pow(2, tryNum) + Math.random() * 1000;
        console.warn(
          `[GraphQL Error Retry ${tryNum}/${CONFIG.maxRetries}] Server error - Waiting ${Math.round(delay)}ms...`,
        );
        await sleep(delay);
        return gqlRequest(query, variables, tryNum + 1);
      }
      throw new Error(`GraphQL errors: ${errorMessage}`);
    }
  }

  // Enhanced rate limiting with jitter to prevent thundering herd
  await sleep(CONFIG.rateLimitMs + Math.random() * 50);
  return json.data;
}

const GET_ALL_MARKETS = `
query GetAllMorphoMarkets($first: Int, $skip: Int, $interval: TimeseriesInterval!) {
  markets(
    first: $first
    skip: $skip
    orderBy: SupplyAssetsUsd
    orderDirection: Desc
    where: { whitelisted: true }
  ) {
    items {
      uniqueKey
      lltv
      creationTimestamp
      loanAsset { symbol name address yield {
        apr
      }}
      collateralAsset { symbol name address yield {
        apr
      }}
      state {
        borrowApy
        netBorrowApy
        dailyBorrowApy
        totalLiquidityUsd
        utilization
        borrowAssetsUsd
        supplyAssetsUsd
        timestamp
      }
      historicalState {
        dailyNetBorrowApy(options: {
        interval: $interval
          }) {
          x
          y
        }
      }
      supplyingVaults {
        address
      }
    }
    pageInfo { count countTotal }
  }
}
`.replace("$.first", "$first"); // tiny safe fix: prevent accidental $first typo in template merges

const GET_TOP_5_BORROWERS = `
query GetTop5BorrowersForMarket($marketUniqueKey: String!) {
  marketPositions(
    first: 5
    orderBy: BorrowShares
    orderDirection: Desc
    where: { marketUniqueKey_in: [$marketUniqueKey], borrowShares_gte: "1" }
  ) {
    items {
      user { address}
      healthFactor
      priceVariationToLiquidationPrice
      state {
        borrowShares borrowAssets borrowAssetsUsd
        supplyShares supplyAssets supplyAssetsUsd
        collateral collateralUsd
        pnlUsd roeUsd marginPnlUsd marginRoeUsd collateralRoeUsd collateralPnlUsd borrowPnlUsd borrowRoeUsd
        timestamp
      }
    }
    pageInfo { count countTotal }
  }
}
`;

const GET_USER_TRANSACTIONS = `
query GetUserTransactions($userAddress: String!, $marketUniqueKey_in: [String!], $first: Int, $skip: Int) {
  transactions(
    first: $first
    skip: $skip
    orderBy: Timestamp
    orderDirection: Desc
    where: { userAddress_in: [$userAddress], marketUniqueKey_in: $marketUniqueKey_in }
  ) {
    items {
      hash timestamp type
      data {
        ... on MarketCollateralTransferTransactionData {
          assets assetsUsd
        }
        ... on MarketTransferTransactionData {
          assets assetsUsd shares
        }
        ... on MarketLiquidationTransactionData {
          repaidAssets repaidAssetsUsd seizedAssets seizedAssetsUsd liquidator
        }
        ... on VaultTransactionData {
          assetsUsd
          vault {
            address
          }
        }
      }
    }
    pageInfo { count countTotal }
  }
}
`;

const CURATORS_AND_VAULTS = `
query CuratorsAndVaults($vFirst:Int,$vSkip:Int,$where: CuratorFilters) {
  curators(where:$where){
    items { addresses {
      address
    } name socials {
      type url
    } state {
      aum
    }
    }
  }
  vaults(first:$vFirst, skip:$vSkip, orderBy: TotalAssetsUsd, orderDirection: Desc){
    items {
      address symbol name whitelisted
      state {
        curators {
               name
             }
        totalAssetsUsd
        fee
        dailyApy
      }
      asset { symbol address yield {
        apr
      } }
    }
    pageInfo { count countTotal }
  }
}`;

const GET_VAULT_DEPOSITORS = `
query GetVaultDepositors($vaultAddress: String!) {
  vaultPositions(
    first: 5,
    skip: 0,
    orderBy: Shares,
    orderDirection: Desc,
    where: { vaultAddress_in: [$vaultAddress] }
  ) {
    items {
      state {
        assetsUsd
      }

      user {
        address
        transactions{
          hash
          type
          timestamp
          data {
            ... on VaultTransactionData {
              assetsUsd
            }
            ... on MarketCollateralTransferTransactionData {
              assetsUsd
            }
            ... on MarketTransferTransactionData {
              assetsUsd
            }
            ... on MarketLiquidationTransactionData {
              repaidAssetsUsd
              badDebtAssetsUsd
            }
          }
        }
      }
    }
  }
}
`;

// ---------- Morpho fetchers ----------
async function fetchAllMorphoMarkets() {
  const first = CONFIG.morphoPageSize;
  let skip = 0;
  const all = [];
  let total = null;

  for (;;) {
    const data = await gqlRequest(GET_ALL_MARKETS, {
      first,
      skip,
      interval: "DAY",
    });
    const page = data.markets;
    const items = page.items || [];
    all.push(...items);

    if (total === null) total = page.pageInfo?.countTotal ?? items.length;
    skip += items.length;

    if (!items.length || skip >= total) break;
  }
  return CONFIG.marketsLimit ? all.slice(0, CONFIG.marketsLimit) : all;
}

async function fetchTopBorrowersForMarket(marketUniqueKey) {
  const data = await gqlRequest(GET_TOP_5_BORROWERS, { marketUniqueKey });
  return data.marketPositions?.items || [];
}

async function fetchAllUserTransactionsForMarket(userAddress, marketUniqueKey) {
  const first = CONFIG.txPageSize;
  let skip = 0;
  const out = [];
  let total = null;

  for (;;) {
    const data = await gqlRequest(GET_USER_TRANSACTIONS, {
      userAddress,
      marketUniqueKey_in: [marketUniqueKey],
      first,
      skip,
    });

    const page = data.transactions;
    const items = page.items || [];
    out.push(...items);

    if (total === null) total = page.pageInfo?.countTotal ?? items.length;
    skip += items.length;

    if (!items.length || skip >= total) break;
  }
  return out;
}

async function fetchCuratorsAndAllVaults() {
  const where = { verified: true };
  const vFirst = 100;
  let vSkip = 0;
  const allVaults = [];

  const firstPage = await gqlRequest(CURATORS_AND_VAULTS, {
    vFirst,
    vSkip,
    where,
  });

  const curators = firstPage.curators?.items || [];
  const firstVaultsPage = firstPage.vaults;
  allVaults.push(...(firstVaultsPage.items || []));

  let total = firstVaultsPage.pageInfo?.countTotal ?? allVaults.length;
  vSkip += (firstVaultsPage.items || []).length;

  while (vSkip < total) {
    const page = await gqlRequest(CURATORS_AND_VAULTS, {
      vFirst,
      vSkip,
      where,
    });
    const vaults = page.vaults;
    const items = vaults.items || [];
    allVaults.push(...items);

    vSkip += items.length;
    total = vaults.pageInfo?.countTotal ?? vSkip;
  }

  return { curators, vaults: allVaults };
}

async function fetchVaultDepositors(vaultAddress) {
  try {
    const data = await gqlRequest(GET_VAULT_DEPOSITORS, { vaultAddress });
    return data.vaultPositions?.items || [];
  } catch (error) {
    console.error(
      `Error fetching depositors for vault ${vaultAddress}:`,
      error.message,
    );
    // Return empty array on error instead of crashing
    return [];
  }
}

// ---------- Pendle fetchers ----------
async function pendleGetActiveMarkets(chain) {
  const url = `${PENDLE_BASE_URL}/v1/${chain}/markets/active`;
  const data = await fetchJsonWithRetry(url);
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.markets)) return data.markets;
  if (Array.isArray(data?.data)) return data.data;
  return [];
}
async function pendleGetMarketData(chain, marketAddress) {
  const url = `${PENDLE_BASE_URL}/v2/${chain}/markets/${marketAddress}/data`;
  return fetchJsonWithRetry(url);
}
async function pendleGetMarketHistory(chain, marketAddress) {
  const url = new URL(
    `${PENDLE_BASE_URL}/v1/${chain}/markets/${marketAddress}/historical-data`,
  );
  url.searchParams.set("time_frame", "day");
  return fetchJsonWithRetry(url.toString());
}
async function pendleGetUserDashboardPositions(userAddress, filterUsd) {
  const url = new URL(
    `${PENDLE_BASE_URL}/v1/dashboard/positions/database/${userAddress}`,
  );
  if (filterUsd != null && !Number.isNaN(filterUsd)) {
    url.searchParams.set("filterUsd", String(filterUsd));
  }
  try {
    return await fetchJsonWithRetry(url.toString());
  } catch (e) {
    if ((e.message || "").includes("HTTP 404")) {
      return { positions: [], error: "Not found" };
    }
    throw e;
  }
}

// ---------- Flattening & export helpers ----------
function flatten(obj, prefix = "", out = {}) {
  if (obj === null || obj === undefined) {
    if (prefix) out[prefix] = "";
    return out;
  }
  if (Array.isArray(obj)) {
    // For arrays of primitives -> join; arrays of objects -> JSON
    if (obj.length && typeof obj[0] === "object") {
      out[prefix || "json"] = JSON.stringify(obj);
    } else {
      out[prefix || "list"] = obj.join("|");
    }
    return out;
  }
  if (typeof obj === "object") {
    for (const [k, v] of Object.entries(obj)) {
      const key = prefix ? `${prefix}.${k}` : k;
      flatten(v, key, out);
    }
    return out;
  }
  out[prefix] = obj;
  return out;
}

function csvEscape(v) {
  if (v === null || v === undefined) return "";
  let s =
    typeof v === "string"
      ? v
      : typeof v === "object"
        ? JSON.stringify(v)
        : String(v);
  s = s.replace(/\r?\n/g, "\n");
  const needsQuote = /[",\n]/.test(s);
  if (s.includes('"')) s = s.replace(/"/g, '""');
  return needsQuote ? `"${s}"` : s;
}

function toMultiSheetCSVString(sheets) {
  let out = "";
  const names = Object.keys(sheets);
  names.forEach((name, idx) => {
    const rows = sheets[name] || [];
    const flatRows = rows.map((r) => flatten(r));
    const headerSet = new Set();
    flatRows.forEach((r) => Object.keys(r).forEach((k) => headerSet.add(k)));
    const headers = ["__sheet", ...Array.from(headerSet)];
    out += `# sheet: ${name}\n`;
    out += headers.map(csvEscape).join(",") + "\n";
    for (const row of flatRows) {
      const arr = [
        name,
        ...headers.slice(1).map((h) => (row[h] === undefined ? "" : row[h])),
      ];
      out += arr.map(csvEscape).join(",") + "\n";
    }
    if (idx < names.length - 1) out += "\n";
  });
  return out;
}

// Minimal Excel 2003 XML (SpreadsheetML) writer (no deps)
function escapeXml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
function toSpreadsheetXML(sheets) {
  let xml = `<?xml version="1.0"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:html="http://www.w3.org/TR/REC-html40">
 <Styles>
   <Style ss:ID="sText"><NumberFormat ss:Format="@"/></Style>
 </Styles>
`;
  for (const [name, rows] of Object.entries(sheets)) {
    const safeName = escapeXml(name.slice(0, 31) || "Sheet1");
    const flatRows = rows.map((r) => flatten(r));
    const headerSet = new Set();
    flatRows.forEach((r) => Object.keys(r).forEach((k) => headerSet.add(k)));
    const headers = Array.from(headerSet);

    xml += ` <Worksheet ss:Name="${safeName}"><Table>\n  <Row>`;
    headers.forEach((h) => {
      xml += `<Cell ss:StyleID="sText"><Data ss:Type="String">${escapeXml(h)}</Data></Cell>`;
    });
    xml += `</Row>\n`;

    for (const row of flatRows) {
      xml += `  <Row>`;
      for (const h of headers) {
        let v = row[h];
        if (v === undefined || v === null) v = "";
        if (typeof v === "object") v = JSON.stringify(v);
        xml += `<Cell ss:StyleID="sText"><Data ss:Type="String">${escapeXml(v)}</Data></Cell>`;
      }
      xml += `</Row>\n`;
    }
    xml += ` </Table></Worksheet>\n`;
  }
  xml += `</Workbook>`;
  return xml;
}

// ---------- Core run ----------
async function run() {
  const startedAt = new Date().toISOString();
  const limit = pLimit(CONFIG.concurrency);

  console.error(
    `Starting Morpho+Pendle collection ${testMode ? "(TEST MODE)" : ""}`,
  );
  console.error(`Chains: ${CONFIG.chains.join(", ")}`);

  // 1) Morpho markets
  const markets = await fetchAllMorphoMarkets();
  console.error(`Fetched ${markets.length} whitelisted Morpho markets`);

  // 2) For each market -> top borrowers -> their transactions
  const marketsWithBorrowers = await Promise.all(
    markets.map((mkt, idx) =>
      limit(async () => {
        console.error(
          `[${idx + 1}/${markets.length}] Market ${mkt.loanAsset?.symbol}/${mkt.collateralAsset?.symbol} - ${mkt.uniqueKey}`,
        );
        const topBorrowers = await fetchTopBorrowersForMarket(mkt.uniqueKey);
        const enriched = [];
        for (const b of topBorrowers) {
          const userAddress = b?.user?.address;
          const txs = userAddress
            ? await fetchAllUserTransactionsForMarket(
                userAddress,
                mkt.uniqueKey,
              )
            : [];
          enriched.push({ ...b, transactions: txs });
        }
        return { market: mkt, topBorrowers: enriched };
      }),
    ),
  );

  // 3) Curators + all vaults -> top depositors
  const { curators, vaults } = await fetchCuratorsAndAllVaults();
  console.error(`Curators: ${curators.length}, Vaults: ${vaults.length}`);

  const vaultDepositors = {};
  // Vault top depositors (all vaults) with enhanced error recovery
  let failureCount = 0;
  let consecutiveFailures = 0;
  const maxConsecutiveFailures = 5;

  for (let i = 0; i < vaults.length; i++) {
    const va = vaults[i].address;
    const progress = `${i + 1}/${vaults.length}`;
    const progressPercent = (((i + 1) / vaults.length) * 100).toFixed(1);

    console.error(
      `[Vault ${progress} (${progressPercent}%)] ${va} top depositors`,
    );

    // Circuit breaker: if too many consecutive failures, increase delay
    if (consecutiveFailures >= maxConsecutiveFailures) {
      const breakerDelay = 5000 + Math.random() * 2000;
      console.warn(
        `Circuit breaker: ${consecutiveFailures} consecutive failures, waiting ${Math.round(breakerDelay)}ms...`,
      );
      await sleep(breakerDelay);
      consecutiveFailures = 0; // Reset after break
    }

    try {
      vaultDepositors[va] = await fetchVaultDepositors(va);
      consecutiveFailures = 0; // Reset on success
    } catch (error) {
      failureCount++;
      consecutiveFailures++;

      console.error(
        `Failed to fetch depositors for vault ${va} (failure ${failureCount}):`,
        error.message,
      );

      // Set empty array on failure
      vaultDepositors[va] = [];

      // Additional backoff on repeated failures
      if (consecutiveFailures > 2) {
        const backoffDelay = 1000 * consecutiveFailures + Math.random() * 1000;
        console.warn(
          `Additional backoff: ${Math.round(backoffDelay)}ms after ${consecutiveFailures} failures`,
        );
        await sleep(backoffDelay);
      }
    }

    // Enhanced rate limiting between vault requests to prevent server overload
    await sleep(CONFIG.rateLimitMs + Math.random() * 100);

    // Progress indicator every 50 vaults
    if ((i + 1) % 50 === 0) {
      console.log(
        `Progress: ${progress} vaults processed, ${failureCount} failures so far`,
      );
    }

    if (testMode) {
      if (i > 3) {
        break;
      }
    }
  }

  console.log(
    `Vault processing completed: ${vaults.length} total, ${failureCount} failures (${((failureCount / vaults.length) * 100).toFixed(1)}% failure rate)`,
  );

  // 4) Pendle mapping: load active markets per chain
  const activeByChain = {};
  for (const chain of CONFIG.chains) {
    try {
      const act = await pendleGetActiveMarkets(chain);
      activeByChain[chain] = act;
      console.error(`Pendle active markets on chain ${chain}: ${act.length}`);
    } catch (e) {
      console.warn(
        `Failed loading Pendle active markets for ${chain}: ${e.message}`,
      );
      activeByChain[chain] = [];
    }
    await sleep(CONFIG.rateLimitMs);
  }

  // Identify PT markets; match PT token address to Pendle active market
  const ptIndexes = [];
  marketsWithBorrowers.forEach((entry, idx) => {
    const ca = entry.market?.collateralAsset || {};
    if (isLikelyPTTokenSymbolOrName(ca.symbol, ca.name)) ptIndexes.push(idx);
  });

  for (const idx of ptIndexes) {
    const entry = marketsWithBorrowers[idx];
    const ptAddr = normalizeAddress(entry.market?.collateralAsset?.address);
    let matching = null;
    let matchedChain = null;

    for (const chain of CONFIG.chains) {
      const list = activeByChain[chain] || [];
      for (const m of list) {
        const ptActive = extractPtAddressFromPendleActive(m.pt);
        if (ptActive && ptActive === ptAddr) {
          matching = m;
          matchedChain = chain;
          break;
        }
      }
      if (matching) break;
    }

    if (matching && matchedChain) {
      const pendleMarketAddress =
        matching.address || matching.market || matching.id || null;
      let marketData = null;
      let historicalData = null;
      try {
        if (pendleMarketAddress) {
          marketData = await pendleGetMarketData(
            matchedChain,
            pendleMarketAddress,
          );
          console.log(pendleMarketAddress, marketData, matchedChain);
          await sleep(CONFIG.rateLimitMs);
          console.log();
          historicalData = await pendleGetMarketHistory(
            matchedChain,
            pendleMarketAddress,
          );
        }
      } catch (e) {
        console.warn(
          `Pendle data/history failed for ${pendleMarketAddress} on chain ${matchedChain}: ${e.message}`,
        );
      }

      entry.pendle = {
        chainId: matchedChain,
        matchedFromPtAddress: ptAddr,
        activeMarket: matching,
        marketAddress: pendleMarketAddress,
        marketData,
        historicalData,
      };

      // For each top borrower: dashboard positions
      for (const b of entry.topBorrowers) {
        const user = b?.user?.address;
        if (!user) continue;
        try {
          const pos = await pendleGetUserDashboardPositions(
            user,
            CONFIG.pendleMinUsd,
          );
          b.pendleDashboardPositions = pos;
        } catch (e) {
          b.pendleDashboardPositions = { positions: [], error: e.message };
        }
        await sleep(CONFIG.rateLimitMs);
      }
    } else {
      entry.pendle = {
        chainId: null,
        matchedFromPtAddress: ptAddr,
        activeMarket: null,
        marketAddress: null,
        marketData: null,
        historicalData: null,
        note: "No matching Pendle market found for this PT token",
      };
    }
  }

  const finishedAt = new Date().toISOString();

  // ---------- Build datasets (“sheets”) ----------
  const sheets = {};

  // 1) Morpho markets (raw market rows)
  sheets.morpho_markets = marketsWithBorrowers.map((x) => x.market);

  // 2) Top borrowers (one row per borrower per market)
  sheets.morpho_top_borrowers = [];
  for (const entry of marketsWithBorrowers) {
    const mk = entry.market?.uniqueKey;
    for (const b of entry.topBorrowers) {
      sheets.morpho_top_borrowers.push({
        marketUniqueKey: mk,
        userAddress: b?.user?.address,
        healthFactor: b?.healthFactor,
        priceVariationToLiquidationPrice: b?.priceVariationToLiquidationPrice,
        transactions_count: Array.isArray(b?.transactions)
          ? b.transactions.length
          : 0,
        state: b?.state || null,
      });
    }
  }

  // 3) Borrower transactions (one row per tx)
  sheets.morpho_user_transactions = [];
  for (const entry of marketsWithBorrowers) {
    const mk = entry.market?.uniqueKey;
    for (const b of entry.topBorrowers) {
      const ua = b?.user?.address;
      const txs = b?.transactions || [];
      for (const tx of txs) {
        sheets.morpho_user_transactions.push({
          marketUniqueKey: mk,
          userAddress: ua,
          hash: tx.hash,
          timestamp: tx.timestamp,
          type: tx.type,
          data: tx.data || null,
        });
      }
    }
  }

  // 4) Curators (flatten addresses/socials)
  sheets.morpho_curators = (curators || []).map((c) => ({
    name: c?.name,
    addresses: (c?.addresses || []).map((a) => a.address).join("|"),
    socials: (c?.socials || []).map((s) => `${s.type}:${s.url}`).join("|"),
    aum: c?.state?.aum,
  }));

  // 5) Vaults
  sheets.morpho_vaults = (vaults || []).map((v) => v);

  // 6) Vault top depositors
  sheets.morpho_vault_top_depositors = [];
  for (const [va, items] of Object.entries(vaultDepositors)) {
    for (const it of items || []) {
      const allTransactions = it?.user?.transactions || [];

      // Helper function to safely extract the USD value from different transaction types
      const extractAssetsUsd = (tx) => {
        if (!tx.data) return 0;
        return parseFloat(
          tx.data.assetsUsd || 
          tx.data.repaidAssetsUsd || 
          0
        );
      };

    // Sort transactions by their USD value in descending order
    const sortedTransactions = allTransactions.sort((a, b) => {
      return extractAssetsUsd(b) - extractAssetsUsd(a);
    });

    // Keep only the top 5 transactions
    const top5Transactions = sortedTransactions.slice(0, 5);

    sheets.morpho_vault_top_depositors.push({
      vaultAddress: va,
      userAddress: it?.user?.address,
      assetsUsd: it?.state?.assetsUsd,
      userTransactions: top5Transactions, // Use the trimmed list
    });
  }
}

  // 7) Pendle mapping/match summary
  sheets.pendle_pt_matches = [];
  for (const entry of marketsWithBorrowers) {
    const pendle = entry.pendle || {};
    sheets.pendle_pt_matches.push({
      marketUniqueKey: entry.market?.uniqueKey,
      morphoPair: `${entry.market?.loanAsset?.symbol || ""}/${entry.market?.collateralAsset?.symbol || ""}`,
      ptTokenAddress: pendle.matchedFromPtAddress || "",
      chainId: pendle.chainId,
      pendleMarketAddress: pendle.marketAddress || "",
      matched: !!pendle.marketAddress,
      note: pendle.note || "",
    });
  }

  // 8) Pendle market data (one row per matched market)
  sheets.pendle_market_data = [];
  for (const entry of marketsWithBorrowers) {
    const p = entry.pendle || {};
    if (p.marketAddress && p.marketData) {
      sheets.pendle_market_data.push({
        marketUniqueKey: entry.market?.uniqueKey,
        chainId: p.chainId,
        pendleMarketAddress: p.marketAddress,
        marketData: p.marketData,
      });
    }
  }

  // 9) Pendle market history
  sheets.pendle_market_history = [];
  for (const entry of marketsWithBorrowers) {
    const p = entry.pendle || {};

    // This correctly skips markets where a Pendle match was not found
    if (!p.marketAddress || !p.historicalData) {
      console.log(`Skipping Pendle market history for ${entry.market?.uniqueKey} as no match was found`);
      continue;
    }

    const hd = p.historicalData;
    let rows = [];

    if (hd && Array.isArray(hd.timestamp) && Array.isArray(hd.impliedApy)) {
        // Transform the data from separate arrays into a single array of point-objects
        for (let i = 0; i < hd.timestamp.length; i++) {
            rows.push({
                timestamp: hd.timestamp[i],
                // Use 'apy' as the primary key for consistency in the dashboard
                apy: parseFloat(hd.impliedApy[i] || 0),
                impliedApy: parseFloat(hd.impliedApy[i] || 0),
                baseApy: parseFloat(hd.baseApy?.[i] || 0),
                maxApy: parseFloat(hd.maxApy?.[i] || 0),
                tvl: parseFloat(hd.tvl?.[i] || 0)
            });
        }
        console.log(`Found ${rows.length} historical data points for ${entry.market?.uniqueKey}`);
    } else {
        // Fallback for other potential structures (keeps original logic for safety)
        if (Array.isArray(hd)) rows = hd;
        else if (Array.isArray(hd?.results)) rows = hd.results;
        else if (Array.isArray(hd?.data)) rows = hd.data;
        else if (Array.isArray(hd?.history)) rows = hd.history;
        console.log(`No timestamp/impliedApy arrays in ${entry.market?.uniqueKey}`);
    }


    for (const r of rows) {
      console.log(`Found data point for ${entry.market?.uniqueKey}: ${JSON.stringify(r)}`);
      sheets.pendle_market_history.push({
        marketUniqueKey: entry.market?.uniqueKey,
        chainId: p.chainId,
        pendleMarketAddress: p.marketAddress,
        point: r,
      });
    }
  }

  // 10) Pendle user positions (top borrowers in PT markets)
  sheets.pendle_user_positions = [];
  for (const entry of marketsWithBorrowers) {
    if (!entry.pendle || !entry.pendle.marketAddress) continue; // PT markets only
    for (const b of entry.topBorrowers) {
      if (!b?.user?.address) continue;
      const pos = b.pendleDashboardPositions || null;
      sheets.pendle_user_positions.push({
        marketUniqueKey: entry.market?.uniqueKey,
        userAddress: b.user.address,
        positionsCount: Array.isArray(pos?.positions)
          ? pos.positions.length
          : undefined,
        raw: pos,
      });
    }
  }

  // ---------- Output JSON (optional) ----------
  const result = {
    metadata: {
      startedAt,
      finishedAt,
      testMode,
      chains: CONFIG.chains,
      morpho: {
        marketsCount: markets.length,
        interval: "DAY",
        pageSize: CONFIG.morphoPageSize,
        txPageSize: CONFIG.txPageSize,
      },
      pendle: {
        dashboardFilterUsd: CONFIG.pendleMinUsd,
      },
    },
    markets: marketsWithBorrowers,
    curators,
    vaults,
    vaultDepositors,
  };

  if (CONFIG.outputJson) {
    fs.writeFileSync(
      path.resolve(CONFIG.outputJson),
      JSON.stringify(result, null, 2),
    );
    console.error(`Saved JSON: ${path.resolve(CONFIG.outputJson)}`);
  }

  // ---------- Output single CSV (sections emulate “sheets”) ----------
  if (CONFIG.csvPath) {
    const csv = toMultiSheetCSVString(sheets);
    fs.writeFileSync(path.resolve(CONFIG.csvPath), csv);
    console.error(`Saved CSV (multi-section): ${path.resolve(CONFIG.csvPath)}`);
  }

  // ---------- Optional multi-sheet Excel (SpreadsheetML) ----------
  if (CONFIG.excelPath) {
    const xml = toSpreadsheetXML(sheets);
    fs.writeFileSync(path.resolve(CONFIG.excelPath), xml);
    console.error(
      `Saved Excel workbook (SpreadsheetML): ${path.resolve(CONFIG.excelPath)}`,
    );
  }

  // // Also print JSON to stdout if no --output given (so it’s still easy to pipe)
  // if (!CONFIG.outputJson) {
  //   process.stdout.write(JSON.stringify(result, null, 2) + "\n");
  // }
}

// ---------------------------- RUN ----------------------------
run().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
