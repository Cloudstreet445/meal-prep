public record Product(
    string id,
    string name,
    string? size,
    string category,
    string sourceSite,
    float currentPrice,
    string unitPrice
);


public enum UpsertResponse
{
    NewProduct,
    PriceUpdated,
    NonPriceUpdated,
    AlreadyUpToDate,
    Failed
}

