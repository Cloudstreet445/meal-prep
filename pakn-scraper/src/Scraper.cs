#nullable enable
using System.Text.RegularExpressions;
using Microsoft.Playwright;
using PlaywrightExtraSharp;
using PlaywrightExtraSharp.Models;
using PlaywrightExtraSharp.Plugins.ExtraStealth;
using static Scraper.Utilities;

namespace Scraper
{
    public partial class Program
    {
        public static async Task EstablishPlaywright(bool headless)
        {
            try
            {
                var playwrightExtra = new PlaywrightExtra(BrowserTypeEnum.Chromium);
                playwrightExtra.Install();
                playwrightExtra.Use(new StealthExtraPlugin());
                await playwrightExtra.LaunchAsync(new() { Headless = headless });
                playwrightPage = await playwrightExtra.NewPageAsync(new BrowserNewPageOptions() { });
                await RoutePlaywrightExclusions();
            }
            catch (Exception e)
            {
                LogError(e.Message);
                throw;
            }
        }

        public async static Task<string> GetHiresImageUrl(IElementHandle productElement)
        {
            var imgDiv = await productElement.QuerySelectorAllAsync("a > div > img");
            string? imgUrl = await imgDiv.Last().GetAttributeAsync("src");

            if (!imgUrl!.Contains("fsimg.co.nz/product/retail/fan/image/")) return "";

            imgUrl = Regex.Replace(imgUrl, @"\d00x\d00", "master");
            return imgUrl;
        }

        private async static Task<Product?> DOMElementToProduct(
            IElementHandle productElement,
            string category
        )
        {
            string name = "", size = "", dollarString = "", centString = "", imageUrl = "";

            var allPElements = await productElement.QuerySelectorAllAsync("p");
            foreach (var p in allPElements)
            {
                string? pType = "";
                try
                {
                    pType = await p.GetAttributeAsync("data-testid");
                }
                catch (Exception)
                {
                    continue;
                }

                switch (pType)
                {
                    case "product-title":
                        name = await p.InnerTextAsync();
                        break;
                    case "product-subtitle":
                        size = await p.InnerTextAsync();
                        size = size.Replace("l", "L");
                        if (size == "kg") size = "per kg";
                        break;
                    case "price-dollars":
                        dollarString = await p.InnerTextAsync();
                        break;
                    case "price-cents":
                        centString = await p.InnerTextAsync();
                        break;
                    default:
                        break;
                }
            }

            float currentPrice;
            try
            {
                currentPrice = float.Parse(dollarString.Trim() + "." + centString.Trim());
            }
            catch (NullReferenceException)
            {
                return null;
            }
            catch (Exception e)
            {
                LogError($"{name} - Couldn't scrape price info\n{e.GetType()}");
                return null;
            }

            string id;
            try
            {
                var imgDiv = await productElement.QuerySelectorAllAsync("a > div > img");
                string? imgUrl = await imgDiv.Last().GetAttributeAsync("src");
                imageUrl = imgUrl ?? "";
                var imageFilename = imgUrl!.Split("/").Last();
                imageFilename = imageFilename.Split("?").First();
                id = "P" + imageFilename.Split(".").First();
            }
            catch (Exception e)
            {
                LogError($"{name} - Couldn't scrape image URL\n{e.GetType()}");
                return null;
            }

            string? unitName = null;
            float? unitNum = null;
            string unitPrice = "";
            try
            {
                string scrapedUnitPriceString = "";
                for (int index = allPElements.Count - 1; index >= 0; index--)
                {
                    var pTag = allPElements[index];
                    string innerText = await pTag.InnerTextAsync();
                    if (Regex.Match(innerText, @"\$\d*.?\d*/").Success)
                    {
                        scrapedUnitPriceString = innerText;
                        break;
                    }
                }

                if (scrapedUnitPriceString != "")
                {
                    string amountString = scrapedUnitPriceString.Split("/")[0].Replace("$", "");
                    unitNum = float.Parse(amountString);
                    unitName = scrapedUnitPriceString.Split("/")[1];

                    if (Regex.IsMatch(unitName, @"\d*(ml|mL)"))
                    {
                        int mlAmount = int.Parse(unitName.ToLower().Replace("ml", ""));
                        float multiplierToGet1L = 1000 / mlAmount;
                        unitNum = (float)Math.Round((decimal)(unitNum * multiplierToGet1L), 2);
                        unitName = "L";
                    }

                    if (Regex.IsMatch(unitName, @"\d+g\b"))
                    {
                        int gramAmount = int.Parse(unitName.ToLower().Replace("g", ""));
                        float multiplierToGet1kg = 1000 / gramAmount;
                        unitNum = (float)Math.Round((decimal)(unitNum * multiplierToGet1kg), 2);
                        unitName = "kg";
                    }

                    if (unitName == "1L") unitName = "L";
                    if (unitName == "1kg") unitName = "kg";

                    unitPrice = unitName.Length > 0 ? unitNum + "/" + unitName : "";

                    if (size == "")
                    {
                        double derivedSize2decimal = Math.Round((double)(currentPrice / unitNum), 2);
                        double derivedSize1decimal = Math.Round((double)(currentPrice / unitNum), 1);
                        double derivedSize = Math.Round((double)(currentPrice / unitNum), 0);

                        if (Math.Abs(derivedSize1decimal - derivedSize2decimal) < 0.03)
                            size = derivedSize1decimal.ToString() + unitName;
                        else
                            size = derivedSize2decimal.ToString() + unitName;

                        if (unitName == "ea" || unitName == "each")
                            size = Math.Round(derivedSize, 0).ToString() + "pk";

                        if (Regex.Match(size, @"0.\d*kg").Success)
                        {
                            float kgFloatSize = float.Parse(size.Replace("kg", ""));
                            double gramSize = Math.Round(kgFloatSize * 1000, 0);
                            size = gramSize.ToString() + "g";
                        }

                        if (Regex.Match(size, @"0.\d*L").Success)
                        {
                            float litreFloatSize = float.Parse(size.Replace("L", ""));
                            double mlSize = Math.Round(litreFloatSize * 1000, 0);
                            size = mlSize.ToString() + "ml";
                        }
                    }
                }
            }
            catch (Exception e)
            {
                LogError($"{name} - Couldn't process unit price\n{e.GetType()}");
                return null;
            }

            try
            {
                SizeAndCategoryOverride overrides = CheckProductOverrides(id);

                if (overrides.category == "invalid")
                    throw new Exception(name + " is overridden as an invalid product.");

                if (overrides.size != "")
                {
                    size = overrides.size;
                    unitPrice = DeriveUnitPriceString(size, currentPrice)!;
                }
                if (overrides.category != "") category = overrides.category;

                Product product = new Product(
                    id: id, name: name, size: size, category: category,
                    sourceSite: "paknsave.co.nz", currentPrice: currentPrice, unitPrice: unitPrice,
                    brand: ExtractBrand(name),
                    sizeGrams: ParseSizeToGrams(size),
                    pricePerUnit: unitNum,
                    pricePerUnitName: unitName,
                    imageUrl: imageUrl
                );

                if (IsValidProduct(product)) return product;
                else throw new Exception(product.name);
            }
            catch (Exception e)
            {
                LogError($"{name} - Price scrape error: \n{e.GetType()}");
                return null;
            }
        }

        private static async Task OpenInitialPageAndSetLocation(float lat, float lng)
        {
            int maxAttempts = 4;
            for (int attempt = 0; attempt < maxAttempts; attempt++)
            {
                try
                {
                    await SetGeoLocation(lat, lng);
                    await playwrightPage!.GotoAsync("https://www.paknsave.co.nz/");
                    Thread.Sleep(4000);
                    await playwrightPage.WaitForSelectorAsync("div.ds-mx-auto");
                    break;
                }
                catch (Exception)
                {
                    if (attempt == maxAttempts - 1)
                    {
                        LogError("Unable to load initial page, check network connection");
                        throw new Exception("Unable to load initial page");
                    }
                    LogWarn($"Retrying Geolocation Detection {attempt + 1}/{maxAttempts}");
                }
            }

            LogWarn($"Selected Store: {await GetStoreLocationName()}");
        }

        private static async Task SetGeoLocation(float latitude, float longitude)
        {
            await playwrightPage!.Context.SetGeolocationAsync(
                new Geolocation() { Latitude = latitude, Longitude = longitude }
            );
            await playwrightPage.Context.GrantPermissionsAsync(new string[] { "geolocation" });
            LogWarn($"Geolocation set: ({latitude}, {longitude})");
        }

        private static async Task<string> GetStoreLocationName()
        {
            try
            {
                var storeLocationElement = await playwrightPage!.QuerySelectorAsync("p");
                var storeLocationText = await storeLocationElement!.InnerTextAsync();
                return storeLocationText.Replace("Collect from ", "");
            }
            catch (PlaywrightException)
            {
                LogError("Error loading playwright browser, check firewall and network settings");
                throw;
            }
            catch (Exception e)
            {
                return e.Message;
            }
        }

        private static async Task RoutePlaywrightExclusions(bool logToConsole = false)
        {
            string[] typeExclusions = { "image", "media", "font", "other" };
            string[] urlExclusions = { "googleoptimize.com", "gtm.js", "visitoridentification.js",
                "js-agent.newrelic.com", "challenge-platform" };
            List<string> exclusions = urlExclusions.ToList<string>();

            await playwrightPage!.RouteAsync("**/*", async route =>
            {
                var req = route.Request;
                bool excludeThisRequest = false;
                string trimmedUrl = req.Url.Length > 120 ? req.Url.Substring(0, 120) + "..." : req.Url;

                foreach (string exclusion in exclusions)
                    if (req.Url.Contains(exclusion)) excludeThisRequest = true;
                if (typeExclusions.Contains(req.ResourceType)) excludeThisRequest = true;

                if (excludeThisRequest)
                {
                    if (logToConsole) LogError($"{req.Method} {req.ResourceType} - {trimmedUrl}");
                    await route.AbortAsync();
                }
                else
                {
                    if (logToConsole) Log($"{req.Method} {req.ResourceType} - {trimmedUrl}");
                    await route.ContinueAsync();
                }
            });
        }
    }
}
