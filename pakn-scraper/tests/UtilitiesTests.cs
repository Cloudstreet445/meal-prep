using Microsoft.VisualStudio.TestTools.UnitTesting;
using static Scraper.Utilities;

namespace ScraperTests
{
    [TestClass]
    public class UtilitiesTests
    {
        [TestMethod]
        public void DeriveCategoryFromURL_ExcludesQueryParameters()
        {
            string url = "https://www.paknsave.co.nz/shop/category/fresh-foods-and-bakery/dairy--eggs/fresh-milk?pg=1&asdf=123f";
            var result = DeriveCategoryFromURL(url);
            Assert.AreEqual<string>(result, "fresh-milk");
        }

        [TestMethod]
        public void DeriveCategoryFromURL_GetsCorrectCategories()
        {
            string url =
                "https://www.paknsave.co.nz/shop/category/fresh-foods-and-bakery/dairy--eggs/fresh-milk?pg=1";
            var result = DeriveCategoryFromURL(url);
            Assert.AreEqual<string>(result, "fresh-milk");
        }

        [TestMethod]
        public void DeriveCategoryFromURL_WorksWithoutHttpSlash()
        {
            string url = "www.paknsave.co.nz/shop/category/fresh-foods-and-bakery/dairy--eggs/fresh-milk?pg=1";
            var result = DeriveCategoryFromURL(url);
            Assert.AreEqual<string>(result, "fresh-milk");
        }

        [TestMethod]
        public void ExtractProductSize_1kg()
        {
            string productName = "Anchor Blue Milk Powder 1kg";
            Assert.AreEqual<string>(ExtractProductSize(productName), "1kg");
        }

        [TestMethod]
        public void ExtractProductSize_255g()
        {
            string productName = "Lee Kum Kee Panda Oyster Sauce 255g";
            Assert.AreEqual<string>(ExtractProductSize(productName), "255g");
        }

        [TestMethod]
        public void ExtractProductSize_NoSize()
        {
            string productName = "Anchor Blue Milk Powder";
            Assert.AreEqual<string>(ExtractProductSize(productName), "");
        }

        [TestMethod]
        public void ExtractProductSize_400ml()
        {
            string productName = "Trident Premium Coconut Cream 400ml";
            Assert.AreEqual<string>(ExtractProductSize(productName), "400ml");
        }

        [TestMethod]
        public void DeriveUnitPriceString_2L()
        {
            string? unitPriceString = DeriveUnitPriceString("Bottle 2L", 6.5f);
            Assert.AreEqual<string>("3.25/L/2", unitPriceString);
        }

        [TestMethod]
        public void DeriveUnitPriceNoodles()
        {
            string? unitPriceString = DeriveUnitPriceString("72g each 5pack", 4.5f);
            Assert.AreEqual<string>("12.5/g/360", unitPriceString);
        }

        [TestMethod]
        public void DeriveUnitPriceString_Multiplier()
        {
            string? unitPriceString = DeriveUnitPriceString("Pouch 4 x 107mL", 6.5f);
            Assert.AreEqual<string>("15.19/L/428", unitPriceString);
        }

        [TestMethod]
        public void DeriveUnitPriceString_Decimal()
        {
            string? unitPriceString = DeriveUnitPriceString("Bottle 1.5L", 3f);
            Assert.AreEqual<string>("2/L/1.5", unitPriceString);
        }

        [TestMethod]
        public void DeriveUnitPriceString_SimpleKg()
        {
            string? unitPriceString = DeriveUnitPriceString("kg", 3f);
            Assert.AreEqual<string>("3/kg/1", unitPriceString);
        }

        [TestMethod]
        public void CheckProductOverrides_SizeMatch()
        {
            var result = CheckProductOverrides("P5022829");
            Assert.AreEqual<string>(result.size, "800g");
        }

        [TestMethod]
        public void CheckProductOverrides_NoMatch()
        {
            var result = CheckProductOverrides("P501234");
            Assert.AreEqual<string>(result.size, "");
        }

        // ── GenerateSearchTokens (MEA-111) ──────────────────────────

        [TestMethod]
        public void GenerateSearchTokens_StripsBrandsQualifiersAndUnits()
        {
            var tokens = GenerateSearchTokens("Pams Fresh NZ Chicken Drumsticks 1kg");
            CollectionAssert.AreEqual(new List<string> { "chicken", "drumsticks" }, tokens);
        }

        [TestMethod]
        public void GenerateSearchTokens_StripsPunctuation()
        {
            var tokens = GenerateSearchTokens("Wattie's Tomato Paste");
            CollectionAssert.AreEqual(new List<string> { "tomato", "paste" }, tokens);
        }

        [TestMethod]
        public void GenerateSearchTokens_DeduplicatesPreservingOrder()
        {
            var tokens = GenerateSearchTokens("Chicken Chicken Stock");
            CollectionAssert.AreEqual(new List<string> { "chicken", "stock" }, tokens);
        }

        [TestMethod]
        public void GenerateSearchTokens_EmptyNameReturnsEmptyList()
        {
            Assert.AreEqual(0, GenerateSearchTokens("").Count);
        }

        // ── ExtractBrand ────────────────────────────────────────────

        [TestMethod]
        public void ExtractBrand_RecognisesLeadingBrand()
        {
            Assert.AreEqual<string?>("Pams", ExtractBrand("Pams Fresh NZ Chicken Drumsticks 1kg"));
        }

        [TestMethod]
        public void ExtractBrand_StripsPunctuation()
        {
            // "Wattie's" → apostrophe stripped → "watties" (a known brand token)
            Assert.AreEqual<string?>("Watties", ExtractBrand("Wattie's Tomato Sauce 560ml"));
        }

        [TestMethod]
        public void ExtractBrand_UnknownBrandReturnsNull()
        {
            Assert.IsNull(ExtractBrand("Fresh Broccoli Each"));
        }

        [TestMethod]
        public void ExtractBrand_EmptyNameReturnsNull()
        {
            Assert.IsNull(ExtractBrand(""));
        }

        // ── ParseSizeToGrams ────────────────────────────────────────

        [TestMethod]
        public void ParseSizeToGrams_Kg()
        {
            Assert.AreEqual(1000f, ParseSizeToGrams("1kg"));
        }

        [TestMethod]
        public void ParseSizeToGrams_Grams()
        {
            Assert.AreEqual(400f, ParseSizeToGrams("400g"));
        }

        [TestMethod]
        public void ParseSizeToGrams_Litres()
        {
            Assert.AreEqual(2000f, ParseSizeToGrams("2L"));
        }

        [TestMethod]
        public void ParseSizeToGrams_Millilitres()
        {
            Assert.AreEqual(500f, ParseSizeToGrams("500ml"));
        }

        [TestMethod]
        public void ParseSizeToGrams_Decimal()
        {
            Assert.AreEqual(1500f, ParseSizeToGrams("1.5kg"));
        }

        [TestMethod]
        public void ParseSizeToGrams_NoUnitReturnsNull()
        {
            Assert.IsNull(ParseSizeToGrams("each"));
        }

        [TestMethod]
        public void ParseSizeToGrams_EmptyReturnsNull()
        {
            Assert.IsNull(ParseSizeToGrams(""));
        }
    }
}