# ── Stage 1: Build ────────────────────────────────────────────────
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /build

COPY PaknScraper.sln .
COPY src/ ./src/
COPY tests/ ./tests/

RUN dotnet restore
RUN dotnet publish src/ -c Release -o /app --no-restore

# ── Stage 2: Runtime ───────────────────────────────────────────────
FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime

RUN apt-get update && apt-get install -y \
    wget ca-certificates fonts-liberation libappindicator3-1 \
    libasound2 libatk-bridge2.0-0 libatk1.0-0 libcups2 \
    libdbus-1-3 libdrm2 libgbm1 libgtk-3-0 libnspr4 libnss3 \
    libx11-6 libxcomposite1 libxdamage1 libxext6 libxfixes3 \
    libxrandr2 libxshmfence1 xdg-utils \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=build /app .

RUN dotnet tool install --global Microsoft.Playwright.CLI 2>/dev/null || true
ENV PATH="$PATH:/root/.dotnet/tools"
RUN playwright install chromium --with-deps 2>/dev/null || true

ENTRYPOINT ["dotnet", "PakScraper.dll", "db"]
