public record Product(
    string id,
    string name,
    string? size,
    string category,
    string sourceSite,
    float currentPrice,
    string unitPrice,
    // Enrichment fields (MEA-129 follow-up). Optional so existing call sites
    // and tests that construct a Product with the original 7 fields still compile.
    string? brand = null,            // leading brand token, e.g. "Pams" (null if unrecognised)
    float? sizeGrams = null,         // pack size normalised to grams/ml, e.g. 1kg -> 1000
    float? pricePerUnit = null,      // numeric price per kg/L (companion to unitPrice string)
    string? pricePerUnitName = null, // unit for pricePerUnit, e.g. "kg" or "L"
    string? imageUrl = null          // product image URL
);


public enum UpsertResponse
{
    NewProduct,
    PriceUpdated,
    NonPriceUpdated,
    AlreadyUpToDate,
    Failed
}

