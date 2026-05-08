using EphemeralMongo;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using MongoDB.Bson;
using MongoDB.Driver;
using static Scraper.MongoDBHandler;
using static Scraper.Program;

namespace ScraperTests
{
    [TestClass]
    public class MongoDBTests
    {
        private static IMongoRunner? _runner;
        private static IMongoCollection<BsonDocument>? _products;
        private static IMongoCollection<BsonDocument>? _runs;

        private static Product ChickenBreast(float price = 8.00f) => new Product(
            id: "P0001",
            name: "Chicken Breast 1kg",
            size: "1kg",
            category: "chicken",
            sourceSite: "paknsave",
            currentPrice: price,
            unitPrice: $"{price}/kg"
        );

        [ClassInitialize]
        public static async Task Init(TestContext _)
        {
            var options = new MongoRunnerOptions { UseSingleNodeReplicaSet = false };
            _runner = MongoRunner.Run(options);

            var client = new MongoClient(_runner.ConnectionString);
            var db = client.GetDatabase("paknsave-pricing");
            _products = db.GetCollection<BsonDocument>("products");
            _runs = db.GetCollection<BsonDocument>("scrape_runs");

            await EstablishTestConnection(_runner.ConnectionString, "paknsave-pricing");
        }

        [ClassCleanup]
        public static void Cleanup()
        {
            try { _runner?.Dispose(); } catch { /* EphemeralMongo7/Driver3 version mismatch on shutdown */ }
        }

        [TestInitialize]
        public void DropCollections()
        {
            _products!.DeleteMany(FilterDefinition<BsonDocument>.Empty);
            _runs!.DeleteMany(FilterDefinition<BsonDocument>.Empty);
        }

        // ── InsertNewProduct ────────────────────────────────────────

        [TestMethod]
        public async Task InsertNewProduct_CreatesStorePriceMap()
        {
            await StartStoreRun("paknsave-lower-hutt");
            var result = await TransformAndUpsertProduct(ChickenBreast());

            Assert.AreEqual(UpsertResponse.NewProduct, result);

            var doc = _products!.Find(Builders<BsonDocument>.Filter.Eq("_id", "P0001")).FirstOrDefault();
            Assert.IsNotNull(doc);
            Assert.IsTrue(doc.Contains("storePrice"));
            Assert.IsTrue(doc["storePrice"].AsBsonDocument.Contains("paknsave-lower-hutt"));
        }

        [TestMethod]
        public async Task InsertNewProduct_SetsCorrectPrice()
        {
            await StartStoreRun("paknsave-lower-hutt");
            await TransformAndUpsertProduct(ChickenBreast(8.00f));

            var doc = _products!.Find(Builders<BsonDocument>.Filter.Eq("_id", "P0001")).FirstOrDefault();
            var storeData = doc["storePrice"]["paknsave-lower-hutt"].AsBsonDocument;
            Assert.AreEqual(8.00, storeData["currentPrice"].AsDouble, 0.01);
        }

        [TestMethod]
        public async Task InsertNewProduct_SetsIsSpecialFalseInitially()
        {
            await StartStoreRun("paknsave-lower-hutt");
            await TransformAndUpsertProduct(ChickenBreast());

            var doc = _products!.Find(Builders<BsonDocument>.Filter.Eq("_id", "P0001")).FirstOrDefault();
            var storeData = doc["storePrice"]["paknsave-lower-hutt"].AsBsonDocument;
            Assert.IsFalse(storeData["isSpecial"].AsBoolean);
        }

        [TestMethod]
        public async Task InsertNewProduct_SameProductDifferentStore_AddsSeparateEntry()
        {
            await StartStoreRun("paknsave-lower-hutt");
            await TransformAndUpsertProduct(ChickenBreast(8.00f));

            await StartStoreRun("paknsave-porirua");
            await TransformAndUpsertProduct(ChickenBreast(9.00f));

            var doc = _products!.Find(Builders<BsonDocument>.Filter.Eq("_id", "P0001")).FirstOrDefault();
            var storePriceMap = doc["storePrice"].AsBsonDocument;

            Assert.IsTrue(storePriceMap.Contains("paknsave-lower-hutt"));
            Assert.IsTrue(storePriceMap.Contains("paknsave-porirua"));
            Assert.AreEqual(8.00, storePriceMap["paknsave-lower-hutt"]["currentPrice"].AsDouble, 0.01);
            Assert.AreEqual(9.00, storePriceMap["paknsave-porirua"]["currentPrice"].AsDouble, 0.01);
        }

        // ── UpdateExistingProduct ───────────────────────────────────

        [TestMethod]
        public async Task UpdateExistingProduct_PriceChanged_UpdatesCurrentPrice()
        {
            await StartStoreRun("paknsave-lower-hutt");
            await TransformAndUpsertProduct(ChickenBreast(8.00f));

            // Reset lastChecked so the second upsert is treated as a new day
            _products!.UpdateOne(
                Builders<BsonDocument>.Filter.Eq("_id", "P0001"),
                Builders<BsonDocument>.Update.Set("storePrice.paknsave-lower-hutt.lastChecked", "2026-01-01")
            );

            await TransformAndUpsertProduct(ChickenBreast(6.00f));

            var doc = _products!.Find(Builders<BsonDocument>.Filter.Eq("_id", "P0001")).FirstOrDefault();
            var storeData = doc["storePrice"]["paknsave-lower-hutt"].AsBsonDocument;
            Assert.AreEqual(6.00, storeData["currentPrice"].AsDouble, 0.01);
        }

        [TestMethod]
        public async Task UpdateExistingProduct_PriceDropBelow90PctAvg_SetsIsSpecialTrue()
        {
            await StartStoreRun("paknsave-lower-hutt");
            await TransformAndUpsertProduct(ChickenBreast(10.00f));

            // Patch price history so avg = 10.00 and lastChecked is stale
            var history = new BsonArray(Enumerable.Repeat(10.00, 10).Select(p =>
                new BsonDocument { { "date", "2026-01-01" }, { "price", p } }
            ));
            _products!.UpdateOne(
                Builders<BsonDocument>.Filter.Eq("_id", "P0001"),
                Builders<BsonDocument>.Update
                    .Set("storePrice.paknsave-lower-hutt.priceHistory", history)
                    .Set("storePrice.paknsave-lower-hutt.avgPrice90d", 10.0)
                    .Set("storePrice.paknsave-lower-hutt.lastChecked", "2026-01-01")
            );

            // 8.50 is 85% of avg — should be flagged as special
            await TransformAndUpsertProduct(ChickenBreast(8.50f));

            var doc = _products!.Find(Builders<BsonDocument>.Filter.Eq("_id", "P0001")).FirstOrDefault();
            var storeData = doc["storePrice"]["paknsave-lower-hutt"].AsBsonDocument;
            Assert.IsTrue(storeData["isSpecial"].AsBoolean, "Price below 90% of avg should be special");
        }

        [TestMethod]
        public async Task UpdateExistingProduct_PriceAbove90PctAvg_IsSpecialFalse()
        {
            await StartStoreRun("paknsave-lower-hutt");
            await TransformAndUpsertProduct(ChickenBreast(10.00f));

            var history = new BsonArray(Enumerable.Repeat(10.00, 10).Select(p =>
                new BsonDocument { { "date", "2026-01-01" }, { "price", p } }
            ));
            _products!.UpdateOne(
                Builders<BsonDocument>.Filter.Eq("_id", "P0001"),
                Builders<BsonDocument>.Update
                    .Set("storePrice.paknsave-lower-hutt.priceHistory", history)
                    .Set("storePrice.paknsave-lower-hutt.avgPrice90d", 10.0)
                    .Set("storePrice.paknsave-lower-hutt.lastChecked", "2026-01-01")
            );

            // 9.50 is 95% of avg — not special
            await TransformAndUpsertProduct(ChickenBreast(9.50f));

            var doc = _products!.Find(Builders<BsonDocument>.Filter.Eq("_id", "P0001")).FirstOrDefault();
            var storeData = doc["storePrice"]["paknsave-lower-hutt"].AsBsonDocument;
            Assert.IsFalse(storeData["isSpecial"].AsBoolean, "Price at 95% of avg should NOT be special");
        }

        [TestMethod]
        public async Task UpdateExistingProduct_NoChange_ReturnsAlreadyUpToDate()
        {
            await StartStoreRun("paknsave-lower-hutt");
            await TransformAndUpsertProduct(ChickenBreast(8.00f));

            // Same price, same day — should be up to date
            var result = await TransformAndUpsertProduct(ChickenBreast(8.00f));

            Assert.AreEqual(UpsertResponse.AlreadyUpToDate, result);
        }

        // ── ScrapeRun ───────────────────────────────────────────────

        [TestMethod]
        public async Task StartStoreRun_CreatesRunDocument()
        {
            await StartStoreRun("paknsave-lower-hutt");

            var run = _runs!.Find(FilterDefinition<BsonDocument>.Empty).FirstOrDefault();
            Assert.IsNotNull(run);
            Assert.AreEqual("paknsave-lower-hutt", run["storeId"].AsString);
            Assert.AreEqual("running", run["status"].AsString);
        }

        [TestMethod]
        public async Task FinaliseRun_UpdatesStatusToCompleted()
        {
            await StartStoreRun("paknsave-lower-hutt");
            await FinaliseRun(10, 2, 3, 5, 0, 45);

            var run = _runs!.Find(FilterDefinition<BsonDocument>.Empty).FirstOrDefault();
            Assert.AreEqual("completed", run["status"].AsString);
            Assert.AreEqual(10, run["productsScraped"].AsInt32);
        }
    }
}
