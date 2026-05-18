using MongoDB.Driver;
using MongoDB.Bson;
using Microsoft.Extensions.Configuration;
using static Scraper.Program;
using static Scraper.Utilities;

namespace Scraper
{
    public partial class MongoDBHandler
    {
        private static IMongoClient? mongoClient;
        private static IMongoDatabase? mongoDatabase;
        private static IMongoCollection<BsonDocument>? productsCollection;
        private static IMongoCollection<BsonDocument>? scrapeRunsCollection;

        static string today = DateTime.Today.ToString("yyyy-MM-dd");
        static string scrapeRunId = "";
        static DateTime scrapeStartTime = DateTime.UtcNow;
        public static string StoreId { get; set; } = "paknsave-lower-hutt";

        // EstablishTestConnection()
        // ------------------------
        // For unit tests: connect directly to a provided URI without reading config.
        public static async Task EstablishTestConnection(string connectionString, string dbName)
        {
            mongoClient = new MongoClient(connectionString);
            mongoDatabase = mongoClient.GetDatabase(dbName);
            productsCollection = mongoDatabase.GetCollection<BsonDocument>("products");
            scrapeRunsCollection = mongoDatabase.GetCollection<BsonDocument>("scrape_runs");
            await mongoDatabase.RunCommandAsync<BsonDocument>(new BsonDocument("ping", 1));
        }

        // EstablishConnection()
        // ---------------------
        // Connects to MongoDB using MONGO_URI from appsettings.json or environment variables.
        public static async Task<bool> EstablishConnection()
        {
            string? connectionString = config["MONGO_URI"];
            string? dbName = config["MONGO_DB"] ?? "paknsave-pricing";

            if (string.IsNullOrWhiteSpace(connectionString))
            {
                LogError("MONGO_URI in appsettings.json or environment variables is missing");
                return false;
            }

            try
            {
                mongoClient = new MongoClient(connectionString);
                mongoDatabase = mongoClient.GetDatabase(dbName);
                productsCollection = mongoDatabase.GetCollection<BsonDocument>("products");
                scrapeRunsCollection = mongoDatabase.GetCollection<BsonDocument>("scrape_runs");

                // Test connection with a ping
                await mongoDatabase.RunCommandAsync<BsonDocument>(
                    new BsonDocument("ping", 1)
                );

                Log($"\n(Connected to MongoDB) {dbName}", ConsoleColor.Yellow);
                return true;
            }
            catch (Exception e)
            {
                LogError($"Error connecting to MongoDB: {e.Message}");
                return false;
            }
        }

        // StartStoreRun()
        // ---------------
        // Sets the active store and inserts a scrape_run document for this store's run.
        public static async Task StartStoreRun(string storeId)
        {
            StoreId = storeId;
            scrapeRunId = ObjectId.GenerateNewId().ToString();
            scrapeStartTime = DateTime.UtcNow;

            if (scrapeRunsCollection == null) return;

            await scrapeRunsCollection.InsertOneAsync(new BsonDocument
            {
                { "_id", scrapeRunId },
                { "runAt", scrapeStartTime },
                { "storeId", storeId },
                { "status", "running" },
                { "productsScraped", 0 },
                { "newProducts", 0 },
                { "priceUpdates", 0 },
                { "upToDate", 0 },
                { "failed", 0 }
            });
        }

        // TransformAndUpsertProduct()
        // ---------------------------
        // Takes a scraped Product and upserts it into MongoDB,
        // appending to priceHistory only if the price has changed.
        public static async Task<UpsertResponse> TransformAndUpsertProduct(Product scrapedProduct)
        {
            if (productsCollection == null)
            {
                LogError("MongoDB not connected");
                return UpsertResponse.Failed;
            }

            try
            {
                var filter = Builders<BsonDocument>.Filter.Eq("_id", scrapedProduct.id);
                var existing = await productsCollection.Find(filter).FirstOrDefaultAsync();

                if (existing == null)
                {
                    return await InsertNewProduct(scrapedProduct);
                }
                else
                {
                    return await UpdateExistingProduct(existing, scrapedProduct);
                }
            }
            catch (Exception e)
            {
                LogError($"MongoDB upsert error for {scrapedProduct.name}: {e.Message}");
                return UpsertResponse.Failed;
            }
        }

        // InsertNewProduct()
        // ------------------
        private static async Task<UpsertResponse> InsertNewProduct(Product scrapedProduct)
        {
            try
            {
                var storePriceEntry = new BsonDocument
                {
                    { "currentPrice", scrapedProduct.currentPrice },
                    { "unitPrice", scrapedProduct.unitPrice ?? "" },
                    { "isSpecial", false },
                    { "priceHistory", new BsonArray { new BsonDocument { { "date", today }, { "price", scrapedProduct.currentPrice } } } },
                    { "firstSeen", today },
                    { "lastChecked", today },
                    { "lastPriceChange", today },
                    { "avgPrice90d", scrapedProduct.currentPrice },
                    { "minPrice90d", scrapedProduct.currentPrice },
                    { "maxPrice90d", scrapedProduct.currentPrice }
                };

                var newProduct = new BsonDocument
                {
                    { "_id", scrapedProduct.id },
                    { "name", scrapedProduct.name },
                    { "size", scrapedProduct.size ?? "" },
                    { "category", scrapedProduct.category },
                    { "sourceSite", scrapedProduct.sourceSite },
                    // searchTokens — precomputed fuzzy-match tokens (MEA-111)
                    { "searchTokens", new BsonArray(GenerateSearchTokens(scrapedProduct.name)) },
                    { "storePrice", new BsonDocument { { StoreId, storePriceEntry } } }
                };

                await productsCollection!.InsertOneAsync(newProduct);

                Log(
                    $"  New Product: {scrapedProduct.id,-8} | " +
                    $"{scrapedProduct.name.PadRight(40).Substring(0, Math.Min(40, scrapedProduct.name.Length))}" +
                    $" | ${scrapedProduct.currentPrice,5} | {scrapedProduct.size}"
                );

                return UpsertResponse.NewProduct;
            }
            catch (Exception e)
            {
                LogError($"MongoDB insert error: {e.Message}");
                return UpsertResponse.Failed;
            }
        }

        // UpdateExistingProduct()
        // -----------------------
        private static async Task<UpsertResponse> UpdateExistingProduct(
            BsonDocument existing,
            Product scrapedProduct
        )
        {
            var filter = Builders<BsonDocument>.Filter.Eq("_id", scrapedProduct.id);

            // Backfill searchTokens on products that predate MEA-111.
            // Tokens derive only from the name, so this is a one-time write.
            if (!existing.Contains("searchTokens"))
            {
                await productsCollection!.UpdateOneAsync(
                    filter,
                    Builders<BsonDocument>.Update.Set(
                        "searchTokens",
                        new BsonArray(GenerateSearchTokens(existing["name"].AsString))
                    )
                );
            }

            // Migrate legacy flat-schema documents to storePrice map on first encounter
            if (!existing.Contains("storePrice"))
            {
                return await MigrateAndUpdateProduct(existing, scrapedProduct, filter);
            }

            // Read per-store data from storePrice map
            var storePriceMap = existing["storePrice"].AsBsonDocument;
            BsonDocument? storeData = storePriceMap.Contains(StoreId)
                ? storePriceMap[StoreId].AsBsonDocument
                : null;

            float lastPrice = storeData != null && storeData.Contains("currentPrice")
                ? (float)storeData["currentPrice"].AsDouble
                : 0f;

            string lastChecked = storeData != null && storeData.Contains("lastChecked")
                ? storeData["lastChecked"].AsString
                : "";

            float priceDifference = Math.Abs(lastPrice - scrapedProduct.currentPrice);
            bool priceHasChanged = priceDifference > 0.05f;

            string storePrefix = $"storePrice.{StoreId}";

            if (storeData == null)
            {
                // First time seeing this product at this store — add a new storePrice entry
                var storePriceEntry = new BsonDocument
                {
                    { "currentPrice", scrapedProduct.currentPrice },
                    { "unitPrice", scrapedProduct.unitPrice ?? "" },
                    { "isSpecial", false },
                    { "priceHistory", new BsonArray { new BsonDocument { { "date", today }, { "price", scrapedProduct.currentPrice } } } },
                    { "firstSeen", today },
                    { "lastChecked", today },
                    { "lastPriceChange", today },
                    { "avgPrice90d", scrapedProduct.currentPrice },
                    { "minPrice90d", scrapedProduct.currentPrice },
                    { "maxPrice90d", scrapedProduct.currentPrice }
                };

                var update = Builders<BsonDocument>.Update.Set(storePrefix, storePriceEntry);
                await productsCollection!.UpdateOneAsync(filter, update);
                return UpsertResponse.NewProduct;
            }
            else if (priceHasChanged && lastChecked != today)
            {
                var newEntry = new BsonDocument { { "date", today }, { "price", scrapedProduct.currentPrice } };

                var history = storeData["priceHistory"].AsBsonArray
                    .Select(e => (float)e["price"].AsDouble)
                    .ToList();
                history.Add(scrapedProduct.currentPrice);

                // Keep only last 90 days worth (approx 3 scrapes/week = ~39 entries)
                var recentHistory = history.TakeLast(39).ToList();
                float avg = recentHistory.Average();
                float min = recentHistory.Min();
                float max = recentHistory.Max();

                bool isSpecial = scrapedProduct.currentPrice < (avg * 0.90f);

                var update = Builders<BsonDocument>.Update
                    .Push($"{storePrefix}.priceHistory", newEntry)
                    .Set($"{storePrefix}.currentPrice", scrapedProduct.currentPrice)
                    .Set($"{storePrefix}.unitPrice", scrapedProduct.unitPrice ?? "")
                    .Set($"{storePrefix}.isSpecial", isSpecial)
                    .Set($"{storePrefix}.lastChecked", today)
                    .Set($"{storePrefix}.lastPriceChange", today)
                    .Set($"{storePrefix}.avgPrice90d", Math.Round(avg, 2))
                    .Set($"{storePrefix}.minPrice90d", Math.Round(min, 2))
                    .Set($"{storePrefix}.maxPrice90d", Math.Round(max, 2));

                await productsCollection!.UpdateOneAsync(filter, update);

                bool priceTrendingDown = scrapedProduct.currentPrice < lastPrice;
                Log(
                    $"  Price {(priceTrendingDown ? "Down " : "Up   ")}: " +
                    $"{existing["name"].AsString.PadRight(51).Substring(0, 51)} | " +
                    $"${lastPrice} > ${scrapedProduct.currentPrice}" +
                    (isSpecial ? " 🔥 SPECIAL" : ""),
                    priceTrendingDown ? ConsoleColor.Green : ConsoleColor.Red
                );

                return UpsertResponse.PriceUpdated;
            }
            else
            {
                var update = Builders<BsonDocument>.Update.Set($"{storePrefix}.lastChecked", today);
                await productsCollection!.UpdateOneAsync(filter, update);
                return UpsertResponse.AlreadyUpToDate;
            }
        }

        // MigrateAndUpdateProduct()
        // -------------------------
        // Converts a legacy flat-schema document to the storePrice map format.
        private static async Task<UpsertResponse> MigrateAndUpdateProduct(
            BsonDocument existing,
            Product scrapedProduct,
            FilterDefinition<BsonDocument> filter
        )
        {
            // Lift existing flat price fields into a storePrice entry for the current store
            var legacyPriceHistory = existing.Contains("priceHistory")
                ? existing["priceHistory"].AsBsonArray
                : new BsonArray { new BsonDocument { { "date", today }, { "price", scrapedProduct.currentPrice } } };

            var migratedStorePrice = new BsonDocument
            {
                { "currentPrice", scrapedProduct.currentPrice },
                { "unitPrice", existing.Contains("unitPrice") ? existing["unitPrice"] : scrapedProduct.unitPrice ?? "" },
                { "isSpecial", existing.Contains("isSpecial") ? existing["isSpecial"] : false },
                { "priceHistory", legacyPriceHistory },
                { "firstSeen", existing.Contains("firstSeen") ? existing["firstSeen"] : today },
                { "lastChecked", today },
                { "lastPriceChange", existing.Contains("lastPriceChange") ? existing["lastPriceChange"] : today },
                { "avgPrice90d", existing.Contains("avgPrice90d") ? existing["avgPrice90d"] : scrapedProduct.currentPrice },
                { "minPrice90d", existing.Contains("minPrice90d") ? existing["minPrice90d"] : scrapedProduct.currentPrice },
                { "maxPrice90d", existing.Contains("maxPrice90d") ? existing["maxPrice90d"] : scrapedProduct.currentPrice }
            };

            // Remove legacy flat fields and set new storePrice map
            var update = Builders<BsonDocument>.Update
                .Set($"storePrice.{StoreId}", migratedStorePrice)
                .Unset("currentPrice")
                .Unset("unitPrice")
                .Unset("isSpecial")
                .Unset("priceHistory")
                .Unset("firstSeen")
                .Unset("lastChecked")
                .Unset("lastPriceChange")
                .Unset("avgPrice90d")
                .Unset("minPrice90d")
                .Unset("maxPrice90d")
                .Unset("storeId");

            await productsCollection!.UpdateOneAsync(filter, update);

            LogWarn($"  Migrated: {existing["name"].AsString.PadRight(51).Substring(0, 51)} → storePrice.{StoreId}");

            return UpsertResponse.NonPriceUpdated;
        }

        // FinaliseRun()
        // -------------
        // Call at end of scrape to update the scrape_run document with final stats
        public static async Task FinaliseRun(
            int totalScraped, int newProducts, int priceUpdates, int alreadyUpToDate, int failed, int durationSeconds
        )
        {
            if (scrapeRunsCollection == null) return;

            try
            {
                var filter = Builders<BsonDocument>.Filter.Eq("_id", scrapeRunId);
                var duration = durationSeconds;

                var update = Builders<BsonDocument>.Update
                    .Set("status", "completed")
                    .Set("productsScraped", totalScraped)
                    .Set("newProducts", newProducts)
                    .Set("priceUpdates", priceUpdates)
                    .Set("upToDate", alreadyUpToDate)
                    .Set("failed", failed)
                    .Set("durationSeconds", duration);

                await scrapeRunsCollection.UpdateOneAsync(filter, update);
                Log($"\nScrape run saved to MongoDB ({duration}s)", ConsoleColor.Yellow);
            }
            catch (Exception e)
            {
                LogError($"Failed to finalise scrape run: {e.Message}");
            }
        }
    }
}
