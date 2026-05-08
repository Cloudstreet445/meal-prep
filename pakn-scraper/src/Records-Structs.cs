public record Product(
    string id,
    string name,
    string? size,
    string category,
    string sourceSite,
    float currentPrice,
    string unitPrice
);

public record DBProduct(
    string id,
    string name,
    string? size,
    string category,
    string sourceSite,
    Dictionary<string, StorePrice> storePrice
);

public record StorePrice(
    float currentPrice,
    string unitPrice,
    bool isSpecial,
    DatedPrice[] priceHistory,
    string firstSeen,
    string lastChecked,
    string lastPriceChange,
    float avgPrice90d,
    float minPrice90d,
    float maxPrice90d
);

public record DatedPrice(
    string date,
    float price
);
public enum UpsertResponse
{
    NewProduct,
    PriceUpdated,
    NonPriceUpdated,
    AlreadyUpToDate,
    Failed
}

public struct ProductResponse
{
    public UpsertResponse upsertResponse;
    public DBProduct dbProduct;

    public ProductResponse(UpsertResponse upsertResponse, DBProduct dbProduct) : this()
    {
        this.upsertResponse = upsertResponse;
        this.dbProduct = dbProduct;
    }
}