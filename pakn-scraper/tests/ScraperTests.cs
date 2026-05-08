using Microsoft.VisualStudio.TestTools.UnitTesting;
using Microsoft.Playwright;
using static Scraper.Program;

namespace ScraperTests
{
    [TestClass]
    public class ScraperTests
    {
        [TestMethod]
        [Ignore("Requires 'playwright install' — run manually for integration testing")]
        public async Task EstablishPlaywright_BrowserConnected()
        {
            await EstablishPlaywright(headless: true);
            Assert.IsTrue(browser!.IsConnected);
        }

        [TestMethod]
        [Ignore("Requires 'playwright install' and network — run manually for integration testing")]
        public async Task EstablishPlaywright_GoogleConnected()
        {
            await EstablishPlaywright(headless: true);
            await playwrightPage!.GotoAsync("http://www.google.com");
            Assert.IsNotNull(playwrightPage);
        }
    }
}