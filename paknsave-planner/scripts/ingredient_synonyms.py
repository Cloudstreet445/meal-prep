"""
NZ ingredient synonyms (MEA-111).

Seed data for the `ingredient_synonyms` collection in the `paknsave-pricing`
database. The fuzzy matcher resolves synonyms before searching, so a recipe
that says "cilantro" also tries "coriander", and "ground beef" also tries
"beef mince" — the names PAK'nSAVE actually uses on shelf.

`canonical` is the NZ supermarket term. `variants` are UK/US/regional names
and common alternates a recipe (or another country's prompt) might use.

Edit this list, then re-run `pricing_enhance.py --synonyms` to reseed.
"""

# canonical (NZ shelf term) -> variants (alternate names that map to it)
SYNONYMS = [
    {"canonical": "capsicum",        "variants": ["bell pepper", "red pepper", "green pepper", "sweet pepper", "capsicum red", "capsicum green"]},
    {"canonical": "coriander",       "variants": ["cilantro", "dhania", "chinese parsley"]},
    {"canonical": "beef mince",      "variants": ["ground beef", "mince beef", "premium mince", "prime mince", "minced beef"]},
    {"canonical": "pork mince",      "variants": ["ground pork", "minced pork"]},
    {"canonical": "chicken mince",   "variants": ["ground chicken", "minced chicken"]},
    {"canonical": "spring onion",    "variants": ["scallion", "green onion", "salad onion"]},
    {"canonical": "courgette",       "variants": ["zucchini", "courgettes"]},
    {"canonical": "eggplant",        "variants": ["aubergine"]},
    {"canonical": "kumara",          "variants": ["sweet potato", "orange kumara"]},
    {"canonical": "silverbeet",      "variants": ["swiss chard", "chard"]},
    {"canonical": "rocket",          "variants": ["arugula", "rocket lettuce"]},
    {"canonical": "snow peas",       "variants": ["mangetout", "sugar snap peas"]},
    {"canonical": "swede",           "variants": ["rutabaga"]},
    {"canonical": "beetroot",        "variants": ["beet", "beets"]},
    {"canonical": "chickpeas",       "variants": ["garbanzo beans", "garbanzo", "ceci beans"]},
    {"canonical": "cannellini beans","variants": ["white beans", "white kidney beans"]},
    {"canonical": "butter beans",    "variants": ["lima beans"]},
    {"canonical": "green beans",     "variants": ["french beans", "string beans", "runner beans"]},
    {"canonical": "wombok",          "variants": ["napa cabbage", "chinese cabbage", "wong bok"]},
    {"canonical": "bok choy",        "variants": ["pak choi", "pak choy", "bok choi"]},
    {"canonical": "telegraph cucumber","variants": ["english cucumber", "continental cucumber", "long cucumber"]},
    {"canonical": "cos lettuce",     "variants": ["romaine lettuce", "romaine"]},
    {"canonical": "mesclun",         "variants": ["salad greens", "mixed greens", "mixed leaves"]},
    {"canonical": "rockmelon",       "variants": ["cantaloupe", "musk melon"]},
    {"canonical": "mandarin",        "variants": ["tangerine", "clementine"]},
    {"canonical": "prawns",          "variants": ["shrimp"]},
    {"canonical": "tasty cheese",    "variants": ["cheddar", "cheddar cheese", "sharp cheese", "colby"]},
    {"canonical": "edam cheese",     "variants": ["edam"]},
    {"canonical": "feta",            "variants": ["feta cheese"]},
    {"canonical": "haloumi",         "variants": ["halloumi", "grilling cheese"]},
    {"canonical": "yoghurt",         "variants": ["yogurt", "natural yoghurt", "greek yoghurt"]},
    {"canonical": "cream",           "variants": ["pouring cream", "fresh cream", "single cream"]},
    {"canonical": "tomato paste",    "variants": ["tomato concentrate", "tomato puree double concentrate"]},
    {"canonical": "passata",         "variants": ["tomato passata", "sieved tomatoes", "tomato puree"]},
    {"canonical": "tomato sauce",    "variants": ["ketchup", "tomato ketchup"]},
    {"canonical": "icing sugar",     "variants": ["powdered sugar", "confectioners sugar"]},
    {"canonical": "caster sugar",    "variants": ["superfine sugar", "castor sugar"]},
    {"canonical": "white sugar",     "variants": ["granulated sugar", "raw sugar"]},
    {"canonical": "plain flour",     "variants": ["all purpose flour", "all-purpose flour"]},
    {"canonical": "self raising flour","variants": ["self-rising flour", "self rising flour"]},
    {"canonical": "wholemeal flour", "variants": ["whole wheat flour", "wholewheat flour"]},
    {"canonical": "cornflour",       "variants": ["cornstarch", "corn starch"]},
    {"canonical": "baking soda",     "variants": ["bicarbonate of soda", "bicarb soda", "bicarb"]},
    {"canonical": "chilli flakes",   "variants": ["red pepper flakes", "crushed chilli", "crushed red pepper"]},
    {"canonical": "chilli",          "variants": ["chili", "chile", "chillies", "chilli peppers"]},
    {"canonical": "soy sauce",       "variants": ["shoyu", "light soy sauce"]},
    {"canonical": "fish sauce",      "variants": ["nam pla"]},
    {"canonical": "mixed herbs",     "variants": ["italian herbs", "italian seasoning", "dried mixed herbs"]},
    {"canonical": "stock",           "variants": ["broth", "bouillon", "stock cubes"]},
    {"canonical": "vanilla essence", "variants": ["vanilla extract"]},
    {"canonical": "desiccated coconut","variants": ["shredded coconut", "dried coconut"]},
    {"canonical": "raisins",         "variants": ["sultanas"]},
    {"canonical": "rolled oats",     "variants": ["oats", "porridge oats", "wholegrain oats"]},
    {"canonical": "treacle",         "variants": ["molasses", "black treacle"]},
    {"canonical": "cider vinegar",   "variants": ["apple cider vinegar"]},
    {"canonical": "balsamic vinegar","variants": ["balsamic"]},
    {"canonical": "canola oil",      "variants": ["rapeseed oil", "vegetable oil"]},
    {"canonical": "worcestershire sauce","variants": ["worcester sauce"]},
    {"canonical": "bacon",           "variants": ["streaky bacon", "rashers", "middle bacon"]},
    {"canonical": "lamb forequarter","variants": ["lamb shoulder", "forequarter chops"]},
    {"canonical": "agria potatoes",  "variants": ["floury potatoes", "baking potatoes", "roasting potatoes"]},
    {"canonical": "yeast",           "variants": ["dried yeast", "instant yeast", "active dry yeast", "surebake"]},
    {"canonical": "ginger",          "variants": ["fresh ginger", "root ginger"]},
]


def build_lookup() -> dict:
    """
    Flatten SYNONYMS into a {term -> canonical} map. Every variant AND the
    canonical itself map to the canonical, so a lookup always normalises.
    """
    lookup = {}
    for entry in SYNONYMS:
        canonical = entry["canonical"]
        lookup[canonical.lower()] = canonical
        for variant in entry["variants"]:
            lookup[variant.lower()] = canonical
    return lookup


def expand(term: str, lookup: dict = None) -> list:
    """
    Given a search term, return the canonical plus every known variant — the
    full set of strings worth trying against the price database.

      expand("cilantro") -> ["coriander", "cilantro", "dhania", "chinese parsley"]
      expand("unknown")  -> ["unknown"]
    """
    if not term:
        return []
    key = term.lower().strip()
    for entry in SYNONYMS:
        if key == entry["canonical"].lower() or key in (
            v.lower() for v in entry["variants"]
        ):
            return [entry["canonical"]] + list(entry["variants"])
    return [term]
