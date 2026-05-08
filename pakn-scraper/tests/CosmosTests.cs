using Microsoft.VisualStudio.TestTools.UnitTesting;
using static Scraper.CosmosDB;

namespace ScraperTests
{
    [TestClass]
    public class CosmosTests
    {
        static string storeId = "paknsave-lower-hutt";
        static string yesterday = DateTime.Today.AddDays(-1).ToString("yyyy-MM-dd");
        static string today = DateTime.Today.ToString("yyyy-MM-dd");

        // Existing DB product with one price entry from yesterday
        static DBProduct MakeDbProduct(float price, string date) => new DBProduct(
            id: "1234",
            name: "milk",
            size: "2l",
            category: "dairy",
            sourceSite: "paknsave.co.nz",
            storePrice: new Dictionary<string, StorePrice>
            {
                [storeId] = new StorePrice(
                    currentPrice: price,
                    unitPrice: "1.82/L",
                    isSpecial: false,
                    priceHistory: [new DatedPrice(date: date, price: price)],
                    firstSeen: date,
                    lastChecked: date,
                    lastPriceChange: date,
                    avgPrice90d: price,
                    minPrice90d: price,
                    maxPrice90d: price
                )
            }
        );

        static Product MakeScrapedProduct(float price) => new Product(
            id: "1234",
            name: "milk",
            size: "2l",
            category: "dairy",
            sourceSite: "paknsave.co.nz",
            currentPrice: price,
            unitPrice: "1.82/L"
        );

        [TestMethod]
        public void BuildUpdatedProduct_SamePrice_ReturnsAlreadyUpToDate()
        {
            var db = MakeDbProduct(3.65f, yesterday);
            var scraped = MakeScrapedProduct(3.65f);

            var response = BuildUpdatedProduct(db, scraped);

            Assert.AreEqual(UpsertResponse.AlreadyUpToDate, response.upsertResponse);
        }

        [TestMethod]
        public void BuildUpdatedProduct_PriceChanged_ReturnsPriceUpdated()
        {
            var db = MakeDbProduct(3.65f, yesterday);
            var scraped = MakeScrapedProduct(5.20f);

            var response = BuildUpdatedProduct(db, scraped);

            Assert.AreEqual(UpsertResponse.PriceUpdated, response.upsertResponse);
        }

        [TestMethod]
        public void BuildUpdatedProduct_PriceChanged_HistoryGrows()
        {
            var db = MakeDbProduct(3.65f, yesterday);
            var scraped = MakeScrapedProduct(5.20f);

            var response = BuildUpdatedProduct(db, scraped);
            var updatedStore = response.dbProduct.storePrice[storeId];

            Assert.AreEqual(2, updatedStore.priceHistory.Length);
            Assert.AreEqual(5.20f, updatedStore.currentPrice, 0.01f);
        }

        [TestMethod]
        public void BuildUpdatedProduct_PriceChanged_SameDay_ReturnsAlreadyUpToDate()
        {
            // If price changed but was already recorded today, don't add a duplicate entry
            var db = MakeDbProduct(3.65f, today);
            var scraped = MakeScrapedProduct(5.20f);

            var response = BuildUpdatedProduct(db, scraped);

            Assert.AreEqual(UpsertResponse.AlreadyUpToDate, response.upsertResponse);
        }

        [TestMethod]
        public void BuildUpdatedProduct_NewStore_ReturnsNewProduct()
        {
            // Product exists in DB but this store hasn't seen it before
            var db = new DBProduct(
                id: "9999",
                name: "bread",
                size: "700g",
                category: "bakery",
                sourceSite: "paknsave.co.nz",
                storePrice: new Dictionary<string, StorePrice>()  // no entry for this store
            );
            var scraped = MakeScrapedProduct(2.50f);

            var response = BuildUpdatedProduct(db, scraped);

            Assert.AreEqual(UpsertResponse.NewProduct, response.upsertResponse);
            Assert.IsTrue(response.dbProduct.storePrice.ContainsKey(storeId));
        }
    }
}
