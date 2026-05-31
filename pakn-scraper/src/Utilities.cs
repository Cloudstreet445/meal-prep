using System.Text.RegularExpressions;
using static Scraper.Program;

namespace Scraper
{
    // Struct for manual overriding scraped product size and category found in 'ProductOverrides.txt'
    public struct SizeAndCategoryOverride
    {
        public string size;
        public string category;

        public SizeAndCategoryOverride(string size, string category)
        {
            this.size = size;
            this.category = category;
        }
    }

    // Struct for parsing URLs and additional data stored in 'Urls.txt'
    public struct CategorisedURL
    {
        public string url;
        public string category;

        public CategorisedURL(string url, string category)
        {
            this.url = url;
            this.category = category;
        }
    }

    public partial class Utilities
    {
        // ParseTexLinesIntoCategorisedURLs()
        // ----------------------------------
        // Takes a string array of text lines containing urls and params, 
        // and parses them into a list of validated and categorised URLs.

        public static List<CategorisedURL> ParseTextLinesIntoCategorisedURLs(
            List<string> textLines,
            string urlShouldContain,
            string replaceQueryParamsWith,
            string queryOptionForEachPage,
            int incrementEachPageBy = 1 // could be pg=1, pg=2, or items=32, items=64, etc.
        )
        {
            List<CategorisedURL> categorisedUrls = new List<CategorisedURL>();

            foreach (string textLine in textLines)
            {
                // If textLine is a comment or invalid, skip 
                if (textLine.StartsWith("#") || textLine.StartsWith("//"))
                {
                }
                else if (textLine.Contains(urlShouldContain))
                {
                    // Sample textLine = website.co.nz/category/bakery/sliced-bread category=bread pages=2
                    // Get url from the first split section
                    string url = textLine.Split(' ').First();

                    // Optimise query parameters
                    url = OptimiseURLQueryParameters(url, replaceQueryParamsWith);

                    // Derive default product category from url
                    string category = DeriveCategoryFromURL(url);

                    // Get any parameters placed after the url
                    string[] additionalParams = textLine.Split(' ');
                    additionalParams = additionalParams.Skip(1).ToArray();

                    // Default the numPages to scrape per url to 1
                    int numPages = 1;

                    foreach (string param in additionalParams)
                    {
                        // If overridden category is provided, override the scraped category
                        if (param.Contains("category="))
                        {
                            category = param.Replace("category=", "");
                        }

                        // Override numPages if specified
                        if (param.Contains("pages="))
                        {
                            try
                            {
                                numPages = int.Parse(param.Replace("pages=", ""));

                                // Ensure parsed numPages is within reasonable range
                                if (numPages <= 1 || numPages >= 20)
                                {
                                    throw new Exception();
                                }
                            }
                            catch (Exception)
                            {
                                // If invalid numPages was specified, reset back to 1
                                Log("Invalid number of pages: " + numPages);
                                numPages = 1;
                            }
                        }
                    }

                    // Add each page as an individual URL to scrape.
                    for (int page = 1; page <= numPages; page++)
                    {
                        string newUrl;

                        // For page1, just add the URL as-is.
                        if (page == 1)
                        {
                            newUrl = url;
                        }
                        else
                        {
                            // For page2 and up, add the associated query option plus the increment to the URL

                            // Examples: pg=2, pg=4, pg=6, etc, or 
                            int pageIndex = incrementEachPageBy * page;

                            // If incrementEachPageBy uses a high index, multiply by (page-1)
                            // Examples: page1 = '', page2 = 'start=32', page3 = 'start=64', etc.
                            if (incrementEachPageBy > 1)
                            {
                                pageIndex = incrementEachPageBy * (page - 1);
                            }
                            newUrl = url + queryOptionForEachPage + pageIndex.ToString();
                        }

                        CategorisedURL perPageUrl = new CategorisedURL(
                            newUrl,
                            category
                        );
                        categorisedUrls.Add(perPageUrl);
                    }
                }
            }

            return categorisedUrls;
        }

        // OptimiseURLQueryParameters
        // --------------------------
        // Parses urls and optimises query options for best results
        // Returns null if invalid

        public static string OptimiseURLQueryParameters(string url, string replaceQueryParamsWith)
        {
            // Ensure https:// is at the start
            url = url.Replace("http://", "https://");
            if (!url.Contains("https://")) url = "https://" + url;

            // If url contains 'search?' or similar search queries, keep all query parameters
            if (Regex.Match(url.ToLower(), @"(search\?|f\=tags|q\=|refinementlist)").Success)
            {
                return url;
            }

            // Else strip all query parameters
            else if (url.Contains('?'))
            {
                url = url.Substring(0, url.IndexOf('?')) + "?";
            }

            // If there were no existing query parameters, ensure a ? is added
            else url += "?";

            // Replace query parameters with optimised ones,
            //  such as limiting to certain sellers,
            //  or showing a higher number of products
            url += replaceQueryParamsWith;

            // Return cleaned url
            return url;
        }

        // UploadImageUsingRestAPI()
        // -------------------------
        // Sends an image url to an Azure Function API, where it will be uploaded.

        public async static Task UploadImageUsingRestAPI(string imgUrl, Product product)
        {
            // Get AZURE_FUNC_URL from appsettings.json
            // Example format:
            // https://<func-app-name>.azurewebsites.net/api/ImageToS3?code=<func-auth-code>&destination=s3://<bucket>/<optional-path>/
            string? funcUrl = config!.GetSection("IMAGE_PROCESS_API_URL").Value;

            // Check funcUrl is valid
            if (!funcUrl!.Contains("http"))
                throw new Exception("AZURE_FUNC_URL in appsettings.json invalid. Should be in format:\n\n" +
                "\"AZURE_FUNC_URL\": \"https://<func-app-name>.azurewebsites.net/api/ImageToS3?code=<func-auth-code>&destination=s3://<bucket>/<optional-path>/\"");

            // Perform http get
            string restUrl = funcUrl + product.id + "&source=" + imgUrl;
            var response = await httpclient.GetAsync(restUrl);
            var responseMsg = await response.Content.ReadAsStringAsync();

            // Log for successful upload of new image
            if (responseMsg.Contains("S3 Upload of Full-Size and Thumbnail WebPs"))
            {
                Log(
                    $"  New Image  : {product.id,8} | {product.name.PadRight(50).Substring(0, 50)}",
                    ConsoleColor.Gray
                );
            }
            else if (responseMsg.Contains("already exists"))
            {
                // Do not log for existing images
            }
            else if (responseMsg.Contains("greyscale"))
            {
                Log($"  Image {product.id} is greyscale, skipping...", ConsoleColor.Gray);
            }
            else
            {
                // Log any other errors that may have occurred
                Console.Write(restUrl + "\n" + responseMsg);
            }
            return;
        }

        // IsValidProduct()
        // ----------------
        // Validates product values are within reasonable ranges

        public static bool IsValidProduct(Product product)
        {
            try
            {
                if (product.name.Length < 4 || product.name.Length > 100) return false;
                if (product.id.Length < 2 || product.id.Length > 20) return false;
                if (product.currentPrice <= 0 || product.currentPrice > 999) return false;
            }
            catch (Exception)
            {
                return false;
            }
            return true;
        }

        // ReadLinesFromFile()
        // -------------------
        // Reads lines from a txt file, then returns as a List

        public static List<string>? ReadLinesFromFile(string fileName)
        {
            try
            {
                List<string> result = new List<string>();
                string[] lines = File.ReadAllLines(@fileName);

                if (lines.Length == 0) throw new Exception("No lines found in " + fileName);

                foreach (string line in lines)
                {
                    if (line != null && !line.StartsWith("#")) result.Add(line.Trim());
                }

                return result;
            }
            catch (Exception)
            {
                LogError("Unable to read file " + fileName + "\n");
                return null;
            }
        }

        // ExtractProductSize()
        // --------------------
        // Extract potential product size from product name
        // 'Anchor Blue Milk Powder 1kg' returns '1kg'

        public static string ExtractProductSize(string productName)
        {
            // \b = word boundary, \d+ = 1 or more digits, \. period, 
            // (g|kg|l|ml) = any of these words, \s = whitespace, ? optional

            string name = productName.ToLower();

            // First try match 4 x 40ml style multiplied units
            string multiplierPattern = @"\d+\s?x\s?\d+\s?(g|kg|l|ml)\b";
            string multiplierResult =
                Regex.Match(name, multiplierPattern).ToString();

            if (multiplierResult.Length > 0)
            {
                // Split by 'x' into '4' and '40ml' sections
                int packSize = int.Parse(Regex.Match(multiplierResult.Split('x')[0], @"\d+").ToString());
                int quantity = int.Parse(Regex.Match(multiplierResult.Split('x')[1], @"\d+").ToString());

                // Get unit name 
                string unitName = Regex.Match(multiplierResult, @"(g|kg|l|ml)").ToString().ToLower();

                // Parse to int and multiply together
                float total = packSize * quantity;

                // If units are in grams, normalize quantity and convert to /kg
                if (unitName == "g")
                {
                    total = total / 1000;
                    unitName = "kg";
                }

                // If units are in mL, normalize quantity and convert to /L
                if (unitName == "ml")
                {
                    total = total / 1000;
                    unitName = "L";
                }

                if (unitName == "l") unitName = unitName.Replace("l", "L");

                // Return original name '4 x 40ml' as '160ml'
                return Math.Round(total, 2) + unitName;
            }

            // Try match '100ml 24pack' or '24 pack 100ml' style names
            string packPattern = @"(\d+\s?(l|ml)\s\d+\s?pack\b|\d+\s?pack\s\d+\s?(l|ml))";
            string packResult =
                Regex.Match(name, packPattern).ToString();

            if (packResult.Length > 0)
            {
                // Match 24 pack and parse to int
                string packSizeString = Regex.Match(packResult, @"\d+\s?pack").ToString();
                int packSize = int.Parse(packSizeString.Replace("pack", "").Trim());

                // Match 100ml quantity
                string quantityString = Regex.Match(packResult, @"\d+\s?(l|ml)").ToString();
                int quantity = int.Parse(Regex.Match(quantityString, @"\d+").ToString());

                // Get unit name
                string unitName = Regex.Match(packResult, @"(l|ml)").ToString();

                // Parse to int and multiply together
                float total = packSize * quantity;

                // If units are in mL, normalize quantity and convert to /L
                if (unitName == "ml")
                {
                    total = total / 1000;
                    unitName = "L";
                }

                if (unitName == "l") unitName = unitName.Replace("l", "L");

                // Return original name '100ml 24pack' as '2.4L'
                return Math.Round(total, 2) + unitName;
            }

            // Try match ordinary styled names such as Milk 350ml
            string pattern = @"\d+(\.\d+)?(g|kg|l|ml)\b";

            string result = Regex.Match(productName.ToLower(), pattern).ToString().Trim();

            return result.Replace("l", "L").Replace("mL", "ml");
        }

        // KnownBrands — leading brand tokens we can confidently lift out of a
        // product name into a structured `brand` field. Subset of TokenStopWords;
        // only single-word brands we are confident appear first in the name.
        public static readonly HashSet<string> KnownBrands = new HashSet<string>
        {
            "pams", "anchor", "meadow", "dairyworks", "hellers", "wattie",
            "watties", "homebrand", "mainland", "tegel", "value", "essentials",
            "budget",
        };

        // ExtractBrand()
        // --------------
        // Returns the leading brand token of a product name if it is recognised,
        // otherwise null. 'Pams Fresh NZ Chicken Drumsticks 1kg' returns 'Pams'.
        public static string? ExtractBrand(string name)
        {
            if (string.IsNullOrWhiteSpace(name)) return null;
            string first = Regex.Replace(name.Trim().Split(' ')[0].ToLower(), "[^a-z0-9]", "");
            if (first.Length == 0 || !KnownBrands.Contains(first)) return null;
            return char.ToUpper(first[0]) + first.Substring(1);
        }

        // ParseSizeToGrams()
        // ------------------
        // Converts a size tag ('1kg', '400g', '500ml', '2L') to a numeric
        // grams/ml value (kg -> g, L -> ml). Returns null when no unit parses.
        public static float? ParseSizeToGrams(string? size)
        {
            if (string.IsNullOrWhiteSpace(size)) return null;
            var m = Regex.Match(size.ToLower(), @"(\d+(?:\.\d+)?)\s*(kg|g|ml|l)\b");
            if (!m.Success) return null;
            float val = float.Parse(m.Groups[1].Value);
            switch (m.Groups[2].Value)
            {
                case "kg": return val * 1000;
                case "g":  return val;
                case "l":  return val * 1000;
                case "ml": return val;
                default:   return null;
            }
        }

        // DeriveCategoryFromURL()
        // -----------------------
        // Derives category name from url by taking the last /bracket/
        // 'www.domain.co.nz/c/food-pets-household/food-drink/pantry/milk-bread/milk'
        // returns 'milk'

        public static string DeriveCategoryFromURL(string url)
        {
            // If a search url is used, use the search parameter as the category
            if (url.Contains("search?"))
            {
                return url.Substring(url.IndexOf("q=") + 2);
            }
            else
            {
                int categoriesEndIndex = url.Contains("?") ? url.IndexOf("?") : url.Length;
                string categoriesString = url.Substring(0, categoriesEndIndex);
                string lastCategory = categoriesString.Split("/").Last();
                return lastCategory;
            }
        }

        // CheckProductOverrides()
        // -----------------------
        // Checks a txt file to see if the product should use a manually overridden values.
        // Returns a SizeAndCategoryOverride object

        public static SizeAndCategoryOverride CheckProductOverrides(string id)
        {
            List<string> overrideLines = ReadLinesFromFile("ProductOverrides.txt")!;

            string sizeOverrideFound = "";
            string categoryOverrideFound = "";

            foreach (string line in overrideLines)
            {
                string[] splitLine = line.Trim().Split(' ');

                // Check if 1st section matches product ID
                if (splitLine[0] == id)
                {
                    // Then loop through any additional sections
                    for (int i = 1; i < splitLine.Length; i++)
                    {
                        // If any section matches weight/size/volume symbols,
                        // use as size override
                        if (Regex.IsMatch(splitLine[i].ToLower(), @"\d+(g|kg|ml|l)"))
                        {
                            sizeOverrideFound = splitLine[i];
                        }

                        // Override any categories if found
                        if (splitLine[i].Contains("category="))
                        {
                            categoryOverrideFound = splitLine[i].Replace("category=", "");
                        }
                    }
                }
            }
            return new SizeAndCategoryOverride(sizeOverrideFound, categoryOverrideFound);
        }

        // DeriveUnitPriceString()
        // -----------------------
        // Derives unit quantity, unit name, and price per unit of a product,
        // Returns a string in format 450/ml

        public static string? DeriveUnitPriceString(string productSize, float productPrice)
        {
            // Return early if productSize is blank
            if (productSize == null || productSize.Length < 2) return null;

            string? matchedUnit = null;
            float? quantity = null;
            float? originalUnitQuantity = null;

            // If size is simply 'kg', process it as 1kg
            if (productSize == "kg" || productSize == "per kg")
            {
                quantity = 1;
                matchedUnit = "kg";
                originalUnitQuantity = 1;
            }
            else
            {
                // MatchedUnit is derived from product size tag, 450ml = ml
                matchedUnit = string.Join("", Regex.Matches(productSize.ToLower(), @"(g|kg|ml|l)\b"));

                // Quantity is derived from product size tag, 450ml = 450
                // Can include decimals, 1.5kg = 1.5
                try
                {
                    string quantityMatch = string.Join("", Regex.Matches(productSize, @"(\d|\.)"));
                    quantity = float.Parse(quantityMatch);
                    originalUnitQuantity = quantity;
                }
                catch (Exception)
                {
                    // If quantity cannot be parsed, the function will return null
                }
            }

            if (matchedUnit.Length > 0 && quantity > 0)
            {
                // Handle edge case where size contains a 'multiplier x sub-unit' - eg. 4 x 107mL
                string matchMultipliedSizeString = Regex.Match(
                    productSize, @"\d+\s?x\s?\d+").ToString();
                if (matchMultipliedSizeString.Length > 2)
                {
                    int multiplier = int.Parse(matchMultipliedSizeString.Split("x")[0].Trim());
                    int subUnitSize = int.Parse(matchMultipliedSizeString.Split("x")[1].Trim());
                    quantity = multiplier * subUnitSize;
                    originalUnitQuantity = quantity;
                    matchedUnit = matchedUnit.ToLower().Replace("x", "");
                    //Log(ConsoleColor.DarkGreen, productSize + " = (" + quantity + ") (" + matchedUnit + ")");
                }

                // Handle edge case where size is in format '72g each 5pack'
                matchMultipliedSizeString = Regex.Match(
                    productSize, @"\d+(g|ml)\seach\s\d+pack").ToString();
                if (matchMultipliedSizeString.Length > 2)
                {
                    int multiplier = int.Parse(Regex.Match(matchMultipliedSizeString.Split("each")[1], @"\d+").Value);
                    int subUnitSize = int.Parse(Regex.Match(matchMultipliedSizeString.Split("each")[0], @"\d+").Value);
                    quantity = multiplier * subUnitSize;
                    originalUnitQuantity = quantity;
                    matchedUnit = matchedUnit.ToLower().Replace("each", "");
                    //Log(ConsoleColor.DarkGreen, productSize + " = (" + quantity + ") (" + matchedUnit + ")");
                }

                // If units are in grams, normalize quantity for price calculation but keep unit as "g"
                if (matchedUnit == "g")
                {
                    quantity = quantity / 1000;
                }

                // If units are in mL, normalize quantity and convert to /L
                if (matchedUnit == "ml")
                {
                    quantity = quantity / 1000;
                    matchedUnit = "L";
                }

                // Capitalize L for Litres
                if (matchedUnit == "l") matchedUnit = "L";

                // Set per unit price, rounded to 2 decimal points
                string roundedUnitPrice = Math.Round((decimal)(productPrice / quantity), 2).ToString();

                // Return in format '{pricePerUnit}/{unit}/{rawSize}', e.g. '3.25/L/2'
                return roundedUnitPrice + "/" + matchedUnit + "/" + originalUnitQuantity;
            }
            return null;
        }

        // Stop words for GenerateSearchTokens() — brands, NZ qualifiers,
        // descriptors, and bare unit words that add no search value.
        // MUST stay in sync with paknsave-planner/scripts/pricing_tokens.py.
        public static readonly HashSet<string> TokenStopWords = new HashSet<string>
        {
            "pams", "anchor", "meadow", "fresh", "dairyworks", "hellers",
            "wattie", "watties", "homebrand", "san", "remo", "mainland", "value",
            "tegel", "countdown", "essentials", "budget",
            "nz", "new", "zealand", "imported",
            "pack", "free", "range", "boneless", "skinless", "brushed",
            "organic", "trim", "lean", "premium", "classic", "select",
            "large", "medium", "small", "extra", "family", "bulk",
            "kg", "g", "ml", "l", "pk", "ea", "each"
        };

        // GenerateSearchTokens()
        // ----------------------
        // Normalises a product name into a deduplicated, order-preserving token
        // list stored as `searchTokens` for fuzzy ingredient matching (MEA-111).
        // 'Pams Fresh NZ Chicken Drumsticks 1kg' returns ['chicken','drumsticks'].
        // Output MUST match paknsave-planner/scripts/pricing_tokens.py tokenise().

        public static List<string> GenerateSearchTokens(string name)
        {
            List<string> tokens = new List<string>();
            if (string.IsNullOrWhiteSpace(name)) return tokens;

            string lowered = Regex.Replace(name.ToLower(), "[^a-z0-9 ]", " ");

            foreach (string token in lowered.Split(
                ' ', StringSplitOptions.RemoveEmptyEntries))
            {
                // Drop single chars, stop words, and digit-led size tokens (1kg).
                if (token.Length <= 1) continue;
                if (TokenStopWords.Contains(token)) continue;
                if (char.IsDigit(token[0])) continue;
                if (!tokens.Contains(token)) tokens.Add(token);
            }

            return tokens;
        }

        // Log()
        // -----
        // Shorthand function for logging with provided colour

        public static void Log(string text, ConsoleColor color = ConsoleColor.White)
        {
            Console.ForegroundColor = color;
            Console.WriteLine(text);
            Console.ForegroundColor = ConsoleColor.White;
        }

        // LogError()
        // ----------
        // Shorthand function for logging with red colour

        public static void LogError(string text)
        {
            Console.ForegroundColor = ConsoleColor.Red;
            Console.WriteLine(text);
            Console.ForegroundColor = ConsoleColor.White;
        }

        // LogWarn()
        // ----------
        // Shorthand function for logging with yellow colour

        public static void LogWarn(string text)
        {
            Console.ForegroundColor = ConsoleColor.Yellow;
            Console.WriteLine(text);
            Console.ForegroundColor = ConsoleColor.White;
        }
    }
}