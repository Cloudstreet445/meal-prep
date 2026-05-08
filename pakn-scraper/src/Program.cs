#nullable enable
using System.Diagnostics;
using Microsoft.Playwright;
using Microsoft.Extensions.Configuration;
using static Scraper.MongoDBHandler;
using static Scraper.Utilities;
using System.Text.RegularExpressions;
using System.Web;

// Pak Scraper
// -----------
// Scrapes product info and pricing from Pak n Save NZ's website.

namespace Scraper
{
    public partial class Program
    {
        static readonly int secondsDelayBetweenPageScrapes = 11;
        static bool uploadToDatabase = false;
        static bool uploadImages = false;
        static bool useHeadlessBrowser = true;

        record StoreConfig(string id, float lat, float lng);

        static Stopwatch globalStopwatch = new Stopwatch();

        // Singletons for Playwright
        public static IPlaywright? playwright;
        public static IPage? playwrightPage;
        public static IBrowser? browser;
        public static HttpClient httpclient = new HttpClient();

        // Get config from appsettings.json
        public static IConfiguration config = new ConfigurationBuilder()
            .AddJsonFile("appsettings.json", optional: false, reloadOnChange: true)      //load base settings
            .AddJsonFile("appsettings.local.json", optional: true, reloadOnChange: true) //load local settings
            .AddEnvironmentVariables()
            .Build();

        public static async Task Main(string[] args)
        {
            // Handle command-line arguments 'db', 'images', 'headed'
            foreach (string arg in args)
            {
                if (arg.Contains("db"))
                {
                    uploadToDatabase = true;

                    bool connected = await MongoDBHandler.EstablishConnection();
                    if (!connected)
                    {
                        LogError("Failed to connect to MongoDB - exiting");
                        return;
                    }
                }

                // dotnet run db images - will scrape, then upload both data and images
                if (arg.Contains("images"))
                {
                    uploadImages = true;
                }

                if (arg.Contains("headed"))
                {
                    useHeadlessBrowser = false;
                }

                if (arg.Contains("headless"))
                {
                    useHeadlessBrowser = true;
                }
            }
            if (!uploadToDatabase)
            {
                // dotnet run - will scrape and display results in console
                LogWarn("(Dry Run Mode - no database writes)");
            }

            // Load store configs from appsettings.json
            var stores = config.GetSection("STORES").GetChildren()
                .Select(s => new StoreConfig(
                    id:  s["id"]  ?? "paknsave-lower-hutt",
                    lat: float.Parse(s["lat"] ?? "-41.2166"),
                    lng: float.Parse(s["lng"] ?? "174.9080")
                )).ToList();

            if (stores.Count == 0)
            {
                LogError("No stores configured in STORES — check appsettings.json");
                return;
            }

            // Start Stopwatch for logging purposes
            Stopwatch stopwatch = new Stopwatch();
            stopwatch.Start();

            // Establish Playwright browser
            await EstablishPlaywright(useHeadlessBrowser);

            // Read lines from Urls.txt file - end program if unable to read
            List<string>? lines = ReadLinesFromFile("Urls.txt");
            if (lines == null) return;

            // Parse and optimise each line into valid urls to be scraped
            List<CategorisedURL> categorisedUrls =
                ParseTextLinesIntoCategorisedURLs(
                    lines,
                    urlShouldContain: "paknsave.co.nz",
                    replaceQueryParamsWith: "",
                    queryOptionForEachPage: "pg=",
                    incrementEachPageBy: 1
                );

            LogWarn(
                $"{categorisedUrls.Count} pages to be scraped per store, " +
                $"{stores.Count} store(s), {secondsDelayBetweenPageScrapes}s delay between pages."
            );

            foreach (var store in stores)
            {
                LogWarn($"\n=== Store: {store.id} ===");
                int storeNew = 0, storePriceUpdated = 0, storeNonPriceUpdated = 0, storeUpToDate = 0;
                Stopwatch storeStopwatch = Stopwatch.StartNew();

                if (uploadToDatabase)
                    await MongoDBHandler.StartStoreRun(store.id);

                // Navigate to this store's location
                await OpenInitialPageAndSetLocation(store.lat, store.lng);

                // Open up each URL and run the scraping function
                for (int i = 0; i < categorisedUrls.Count(); i++)
                {
                try
                {
                    // Separate out url from categorisedUrl
                    string url = categorisedUrls[i].url;
                    if (url == "") continue; // skip if url is blank (invalidated earlier)

                    // Create shortened url for logging
                    string shortenedLoggingUrl = HttpUtility.UrlDecode(url)
                        .Replace("https://www.", "")
                        .Replace("shop/category/", "")
                        .Replace("&refinementList[category2NI]", " ")
                        .Trim();

                    // Log current sequence of page scrapes, the total num of pages to scrape
                    LogWarn(
                        $"\n[{i + 1}/{categorisedUrls.Count()}] {shortenedLoggingUrl}"
                    );

                    // Try load page with upto 3 retries
                    int maxLoadAttempts = 3;
                    for (int loadAttempt = 0; loadAttempt < maxLoadAttempts; loadAttempt++)
                    {
                        try
                        {
                            // Navigate to the URL
                            await playwrightPage!.GotoAsync(
                                url,
                                new PageGotoOptions() { Timeout = 8000 }
                            );

                            // Scroll down page to trigger lazy loading
                            for (int scrollLoop = 0; scrollLoop < 3; scrollLoop++)
                            {
                                await playwrightPage.Keyboard.PressAsync("PageDown");
                                Thread.Sleep(120);
                            }

                            // Wait for prices to load in
                            string price =
                                await playwrightPage.GetByTestId("price-dollars").Last.InnerHTMLAsync();

                            // If successful, break out of load attempt loop
                            break;
                        }
                        catch (Exception)
                        {
                            if (loadAttempt == maxLoadAttempts - 1)
                            {
                                throw; // re-throw exception if max attempts reached
                            }
                            LogWarn(
                                $"Retrying page load {loadAttempt + 1}/{maxLoadAttempts}..."
                            );
                        }
                    }

                    // Detect desired url page number
                    int desiredPageNumber = 1;
                    Match pageMatch = Regex.Match(url, @"[?&]pg=(\d+)");
                    if (pageMatch.Success)
                    {
                        desiredPageNumber = int.Parse(pageMatch.Groups[1].Value);
                    }

                    // Detect pagination pages available
                    int availablePages = 1;
                    try
                    {
                        var paginationElement =
                            await playwrightPage!.QuerySelectorAllAsync("nav[aria-label='pagination'] > ul");
                        availablePages =
                            (await paginationElement[0].QuerySelectorAllAsync("li")).Count - 2; // minus prev/next buttons
                    }
                    catch (Exception)
                    {
                        // No pagination found, so only 1 page is available
                        continue;
                    }

                    // Check if the next url is for the same category but with a higher page number
                    if (i + 1 < categorisedUrls.Count())
                    {
                        CategorisedURL nextCategorisedUrl = categorisedUrls[i + 1];
                        string nextUrlWithoutPageParam =
                            nextCategorisedUrl.url.Substring(0, nextCategorisedUrl.url.IndexOf("?") - 1);

                        string currentUrlWithoutPageParam =
                            url.Substring(0, url.IndexOf("?") - 1);

                        bool nextUrlIsSameCategory = nextUrlWithoutPageParam == currentUrlWithoutPageParam;

                        int nextUrlPageParam =
                            int.Parse(HttpUtility.ParseQueryString(new Uri(nextCategorisedUrl.url).Query
                            ).Get("pg") ?? "1");

                        if (nextUrlIsSameCategory && nextUrlPageParam > availablePages)
                        {
                            // If the detected available pages is less than the next desired page number,
                            // invalidate the next url to prevent unnecessary scraping attempts
                            nextCategorisedUrl.url = "";
                            categorisedUrls[i + 1] = nextCategorisedUrl;
                        }
                    }
                    // Get all div elements
                    var allDivElements =
                        await playwrightPage!.QuerySelectorAllAsync("div");

                    // Verify each element contains an attribute data-testid
                    // ending in either -EA-000 or-KGM-000"
                    var productElements = allDivElements.Where(
                        element => (
                            (element.GetAttributeAsync("data-testid").Result ?? "")
                            .Contains("-EA-000")
                            ||
                            (element.GetAttributeAsync("data-testid").Result ?? "")
                            .Contains("-KGM-000")
                        )
                    ).ToList();

                    // Log how many valid products were found on this page
                    Log(
                        $"{productElements.Count} Products Found \t".PadRight(16) +
                        $"Total Time Elapsed: {stopwatch.Elapsed.Minutes}:{stopwatch.Elapsed.Seconds.ToString().PadLeft(2, '0').PadRight(8)}\t" +
                        $"Category: {categorisedUrls[i].category}".PadRight(30) +
                        $"Page: {desiredPageNumber}/{availablePages}"
                    );

                    // Create per-page counters for logging purposes
                    int newCount = 0, priceUpdatedCount = 0, nonPriceUpdatedCount = 0, upToDateCount = 0;

                    // Loop through every found playwright element
                    foreach (var productElement in productElements)
                    {
                        // Create Product object from playwright element
                        Product? scrapedProduct =
                            await DOMElementToProduct(productElement, categorisedUrls[i].category);

                        if (uploadToDatabase && scrapedProduct != null)
                        {
                            UpsertResponse response = await MongoDBHandler.TransformAndUpsertProduct(scrapedProduct);

                            // Increment stats counters
                            switch (response)
                            {
                                case UpsertResponse.NewProduct:
                                    newCount++; storeNew++;
                                    break;
                                case UpsertResponse.PriceUpdated:
                                    priceUpdatedCount++; storePriceUpdated++;
                                    break;
                                case UpsertResponse.NonPriceUpdated:
                                    nonPriceUpdatedCount++; storeNonPriceUpdated++;
                                    break;
                                case UpsertResponse.AlreadyUpToDate:
                                    upToDateCount++; storeUpToDate++;
                                    break;
                                case UpsertResponse.Failed:
                                default:
                                    break;
                            }

                            if (uploadImages)
                            {
                                // Get hi-res image url
                                string hiResImageUrl = await GetHiresImageUrl(productElement);

                                // Use a REST API to upload product image
                                if (hiResImageUrl != "" && hiResImageUrl != null)
                                {
                                    await UploadImageUsingRestAPI(hiResImageUrl, scrapedProduct);
                                }
                            }
                        }
                        else if (!uploadToDatabase && scrapedProduct != null)
                        {
                            // In Dry Run mode, prepare a log row for every product

                            // logUnitPrice is either blank or "$ + {unitPrice}"
                            string logUnitPrice = "";
                            if (scrapedProduct.unitPrice != null)
                                if (scrapedProduct.unitPrice != "")
                                    logUnitPrice = "$ " + scrapedProduct.unitPrice;

                            // Log completed row entry
                            Console.WriteLine(
                                scrapedProduct!.id.PadLeft(9) + " | " +
                                scrapedProduct.name!.PadRight(60).Substring(0, 60) + " | " +
                                scrapedProduct.size!.PadRight(10) + " | $" +
                                scrapedProduct.currentPrice.ToString().PadLeft(5) + " | " +
                                logUnitPrice
                            );
                        }
                    }

                    if (uploadToDatabase)
                    {
                        LogWarn(
                            $"MongoDB: {newCount} new products, " +
                            $"{priceUpdatedCount} prices updated, {nonPriceUpdatedCount} info updated, " +
                            $"{upToDateCount} already up-to-date"
                        );
                    }
                }
                catch (TimeoutException)
                {
                    LogError("Unable to Load Web Page - timed out after 30 seconds");
                }
                catch (PlaywrightException e)
                {
                    if (!e.Message.Contains("ERR_ABORTED")) // Ignore aborted requests
                    {
                        LogError("Unable to Load Web Page - " + e.Message); // Log other errors
                    }
                }
                catch (Exception e)
                {
                    Console.Write(e.ToString());
                    return;
                }

                    // This page has now completed scraping. A delay is added in-between each subsequent URL
                    if (i != categorisedUrls.Count() - 1)
                    {
                        Thread.Sleep(secondsDelayBetweenPageScrapes * 1000);
                    }
                }

                storeStopwatch.Stop();
                LogWarn(
                    $"=== {store.id} done: {storeNew} new, {storePriceUpdated} updated, " +
                    $"{storeUpToDate} up-to-date ({(int)storeStopwatch.Elapsed.TotalSeconds}s) ==="
                );

                if (uploadToDatabase)
                {
                    await MongoDBHandler.FinaliseRun(
                        totalScraped: storeNew + storePriceUpdated + storeNonPriceUpdated + storeUpToDate,
                        newProducts: storeNew,
                        priceUpdates: storePriceUpdated,
                        alreadyUpToDate: storeUpToDate,
                        failed: 0,
                        durationSeconds: (int)storeStopwatch.Elapsed.TotalSeconds
                    );
                }
            }

            // Try clean up playwright browser and other resources, then end program
            try
            {
                Log("Scraping Completed \n");
                await playwrightPage!.Context.CloseAsync();
                await playwrightPage.CloseAsync();
                await browser!.CloseAsync();
            }
            catch (Exception)
            {
            }
            return;
        }

    }
}
