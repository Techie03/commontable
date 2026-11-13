# Denton, TX Restaurant Census

Best-effort census of restaurants in Denton, TX, built 2026-11-12 for the CommonTable
food-delivery pilot (pilot zone: Denton). Companion files:

- `denton-restaurants.json` — full structured data (288 restaurants)
- `denton-restaurants.csv` — same data, one row per restaurant

**Status of the restaurants in this file:** they are prospects for CommonTable
outreach. They are NOT partners, NOT orderable, and nothing here implies any
relationship with CommonTable. One demo restaurant remains the only orderable
restaurant in the pilot slice.

## Totals

- **288 unique Denton restaurants** (deduplicated by place ID across 128 searches)
- **58 place records excluded** (see below)
- Field coverage across the 288: ZIP 288, phone 276, website 266, hours 284,
  rating 134, price level 271. Missing fields are null in the JSON (empty in the
  CSV) — nothing was guessed.

## Counts by primary category (top 15)

| # | Category | Count |
|---|----------|-------|
| 1 | Fast Food Restaurant | 31 |
| 2 | Pizza Place | 18 |
| 3 | Mexican Restaurant | 14 |
| 4 | Sandwich Shop | 13 |
| 5 | Coffee Shop | 12 |
| 6 | Food Truck | 10 |
| 6 | Restaurant (generic) | 10 |
| 6 | Indian Restaurant | 10 |
| 6 | Bakery | 10 |
| 10 | Barbecue Restaurant | 9 |
| 10 | Italian Restaurant | 9 |
| 12 | Thai Restaurant | 7 |
| 12 | Seafood Restaurant | 7 |
| 14 | Tex-Mex Restaurant | 6 |
| 14 | Deli | 6 |

65 distinct primary categories in total. The long tail includes 5 each of Japanese,
Mediterranean, Burger, Bar & Grill, Sushi, Smoothie & Juice Bar, Steakhouse and
Chinese; 4 each of Ice Cream Shop, Dessert Shop, Diner and Breakfast & Brunch;
3 each of American, Cajun & Creole, Chicken Joint, Brewery, Taco and
Vegetarian/Vegan; and 32 categories with 1–2 each (incl. Ramen, Vietnamese,
Korean, Lebanese, African, Hawaiian, Soul Food, Hyderabadi, South Indian,
Dumpling, Salad Bar, Tea Room, Bistro, Butcher Shop, Cake Shop, Hot Dog Joint).

## Counts by ZIP (5-digit)

| ZIP | Count |
|-----|-------|
| 76201 (Downtown / UNT / central) | 182 |
| 76205 (south-central / I-35E / Loop 288) | 54 |
| 76210 (southwest / Teasley / Wind River) | 24 |
| 76209 (east) | 15 |
| 76203 (UNT campus) | 5 |
| 76208 (northwest) | 5 |
| 76207 (north / I-35W) | 3 |

Note: the `zip` field keeps the source value, which is ZIP+4 for 37 records
(e.g. `76201-1600`); the counts above roll those up to 5 digits. The 76201
skew partly reflects real density (Downtown + UNT) and partly the search
engine's downtown weighting — outlying ZIPs are the most likely to be
undercounted.

## Method

1. Ran 128 Google Maps-backed place searches (`browser.search`), varying by
   cuisine/type, by neighborhood/corridor (Downtown/Square, UNT, Fry St, Hickory
   St, Oak St, Teasley Ln, Loop 288, I-35, Bonnie Brae, Fort Worth Dr, Golden
   Triangle Mall, Rayzor Ranch, Robson Ranch), by ZIP (76201, 76203, 76205,
   76207, 76208, 76209, 76210), and by name for chains and named leads.
2. Deduplicated by numeric place ID across all queries. Search was used for
   discovery only: place ID, name, address, coordinates, and rating (when shown)
   were recorded per record.
3. Enriched all 288 place IDs with `places details --summary` (6 batches of 48),
   which supplied ZIP codes (missing from every search result), phone, website,
   categories, price level, hours, and ratings. Where the details rating and the
   search-shown rating both existed they were the same rating (details carries
   full precision; values were rounded to 1 decimal). Details rating took
   precedence; the search rating was the fallback (in practice the two rating
   sets coincided exactly, so no fallback was needed).
4. Excluded closed places and non-Denton places (see below). Missing fields stay
   null — nothing was invented, guessed, or filled in.
5. `maps_search_url` is built only from the verified name + address
   (`https://www.google.com/maps/search/?api=1&query=<url-encoded name, address>`).
   The numeric place IDs are the search provider's IDs, not Google's — no Google
   place ID or maps URL was invented from them.

## Queries run (128)

Batch 1 (cuisine): restaurants in Denton TX; Mexican restaurants in Denton TX;
pizza restaurants in Denton TX; Indian restaurants in Denton TX; Chinese
restaurants in Denton TX; BBQ restaurants in Denton TX; burger restaurants in
Denton TX; breakfast restaurants in Denton TX.

Batch 2 (cuisine): Thai restaurants in Denton TX; Vietnamese restaurants in
Denton TX; Japanese sushi restaurants in Denton TX; Korean restaurants in Denton
TX; Mediterranean restaurants in Denton TX; Italian restaurants in Denton TX;
seafood restaurants in Denton TX; sandwich shops in Denton TX.

Batch 3 (type): coffee shops in Denton TX; cafes in Denton TX; bakeries in Denton
TX; dessert ice cream shops in Denton TX; vegan vegetarian restaurants in Denton
TX; steakhouse restaurants in Denton TX; Southern soul food restaurants in Denton
TX; food trucks in Denton TX.

Batch 4 (area/ZIP): restaurants in Denton TX 76201; restaurants in Denton TX
76205; restaurants in Denton TX 76207; restaurants in Denton TX 76208;
restaurants in Denton TX 76209; restaurants in Denton TX 76210; restaurants near
UNT campus Denton TX; restaurants Downtown Denton TX Denton Square.

Batch 5 (named): GreenHouse Restaurant Denton TX 600 N Locust; Oldwest Cafe
Denton TX; Rooster's Roadhouse Denton TX; Seven Mile Cafe Denton TX; Frilly's
Seafood Bayou Kitchen Denton TX; El Taco H Denton TX; 940's Kitchen and Cocktails
Denton TX; Union Bear Brewing Company Denton TX.

Batch 6 (named): Thai Ocha Denton TX restaurant; La Rustica Italiano Denton TX;
Spiral Diner Bakery Denton TX; Pepita's Vegan Taqueria Denton TX; Chestnut Tree
Bistro Denton TX; Denton County Brewing Company Denton TX; Wildhorse Grill Denton
TX; L'Amitie Bistro Denton TX Bolivar.

Batch 7 (type): fast food restaurants in Denton TX; diners in Denton TX; delis in
Denton TX; brunch restaurants in Denton TX; bars with food Denton TX; tacos in
Denton TX; Middle Eastern restaurants in Denton TX; Milpa Kitchen Cantina Denton
TX.

Batch 8 (named/area): Viet Bites Denton TX; La Fondita Denton TX Mexican
restaurant; La Laguna restaurant Denton TX; BJ's Restaurant Brewhouse Denton TX;
La Rustica Italiano Denton TX restaurant address; restaurants Fry Street Denton
TX; restaurants Teasley Lane Denton TX; restaurants Loop 288 Denton TX.

Batch 9 (area): restaurants Rayzor Ranch Denton TX; restaurants Golden Triangle
Mall Denton TX; restaurants Robson Ranch Denton TX; restaurants Bonnie Brae
Denton TX; restaurants Fort Worth Drive Denton TX; restaurants Hickory Street
Denton TX; restaurants Oak Street Denton TX; restaurants I-35 Denton TX.

Batch 10 (chains): Taco Cabana Denton TX; HTeaO Denton TX; Chick-fil-A Denton TX;
Whataburger Denton TX; Raising Cane's Denton TX; KFC Denton TX; Popeyes Denton
TX; Subway Denton TX.

Batch 11 (chains): Chili's Denton TX; Applebee's Denton TX; Buffalo Wild Wings
Denton TX; Jimmy John's Denton TX; Crumbl Cookies Denton TX; Dutch Bros Denton
TX; Little Caesars Denton TX; Marco's Pizza Denton TX.

Batch 12 (named): Subway 717 S Interstate 35 Denton TX; Chick-fil-A Texas Woman's
University Denton TX; Whataburger Fort Worth Drive Denton TX; Donut Joy Denton
TX; Smoothie King Denton TX; Potbelly Denton TX; Church's Chicken Denton TX;
7 Brew Coffee Denton TX.

Batch 13 (named): Qdoba Texas Woman's University Denton TX; Oda's Indian Cuisine
Denton TX; Kurogi Denton TX restaurant; Einstein Bros Bagels Denton TX; Nothing
Bundt Cakes Denton TX; Pizza Hut 1600 Teasley Ln Denton TX; Subway 3969 Teasley
Ln Denton TX; Bunsen Tea Lab Denton TX.

Batch 14 (named): Kurume Ramen and Izakaya Denton TX; MOMO STREET Fort Worth Dr
Denton TX; KashKan desi Dhaba Denton TX; QDOBA UNT 1155 Union Circle Denton TX;
Einstein Bros Bagels 1155 Union Circle Denton TX; ACE Sushi Denton TX; Mondo Subs
Denton TX; Cultura Beer Hall Denton TX.

Batch 15 (named): Tollywood Bites Denton TX; Higuma Ramen Izakaya Denton TX;
Toasty Bros Beer Denton TX; Jamba Denton TX; On The Border Denton TX; Cheddar's
Scratch Kitchen Denton TX; Chicken Express Denton TX; Cicis Pizza Denton TX.

Batch 16 (named leads): Mochinut Denton TX; Ravi Babu Biryani Denton TX; Chuy's
Denton TX; TJ's Pizza Wings N Things Denton TX; Armadillo Ale Works Denton TX;
Black Fox Brewing Denton TX; Tropical Smoothie Cafe Denton TX; Outback Steakhouse
Denton TX.

## What was excluded and why (58 records)

**Closed places — place-record status governs (17).** The place record is the
authoritative source; where web sources conflict, the conflict is noted here so
the contested ones can be re-verified before any outreach.

- Tollywood Bites, 601 Fort Worth Dr — Permanently Closed per place record.
  Conflict: DoorDash showed it active ~10 days before the census, Postmates
  ~2 days before, and its own website listed hours (5pm–1am) ~5 days before.
- On The Border Mexican Grill & Cantina, 2829 S I-35E — Permanently Closed per
  place record. According to Yelp, this business is permanently closed. Conflict:
  MenuPix/SinglePlatform still list hours and menus, and job postings from Oct
  22–23, 2026 were hiring at this location.
- Black Fox Brewing Company of Texas, 205 N Cedar St — Permanently Closed per
  place record. Conflict: its own website (crawled 5 days before the census)
  says "NOW OPEN" with hours, and Denton Main Street lists it as active.
- Ravi Babu Biryani, 500 S Locust St (food truck) — Temporarily Closed per
  place record. Conflict: Uber Eats/Postmates showed it active ("Opens 6:00 PM")
  as recently as 3 days before the census.
- KashKan, 703 Londonderry Ln — Temporarily Closed per place record. Conflict:
  DoorDash showed it active; Instagram showed a Sept 2026 reopening; another
  listing gave 206 Fort Worth Dr.
- Milpa Kitchen & Cantina, 1115 W Hickory St #113 — Permanently Closed per
  place record. Conflict: some web sources still list it as open / takeout-only
  / cloud kitchen; its original location was 820 S I-35E Ste 101.
- Chestnut Tree Bistro, 107 W Hickory St — Permanently Closed per Yelp live
  data. Conflict: some web sources still list it as open.
- Spiral Diner & Bakery, 608 E Hickory St #100 — Permanently Closed.
- Pepitas Vegan Taqueria, 1115 W Hickory St Suite 113 — Permanently Closed per
  Yelp live data. (Fiesta Eats Hub, in the census, is at the same address.)
- Viet Bites, 1115 W Hickory St — Permanently Closed per place record + Yelp.
- Armadillo Ale Works, 221 S Bell Ave — Permanently Closed per place record;
  BeerAdvocate also lists the brewery bar closed; Union Bear took over the
  facility.
- Jackie Mays Burger, 900 Avenue C — Temporarily Closed (re-confirmed in a
  later batch).
- El Rincon del maiz, 1431 E McKinney St — Temporarily Closed.
- Chennai Corner Food Truck, 402 W Hickory St — Temporarily Closed.
- Spicy Wheels, 412 N Texas Blvd — Temporarily Closed (re-confirmed in a later
  batch).
- Aliboba Cafe Sushi and Grill, 5017 Teasley Ln — Temporarily Closed.
- Berry Hall, 3321 Monte Carlo Ln — Permanently Closed; also an auction house,
  not a restaurant.

**Outside Denton (39).** Returned by Denton searches but addressed in another
city: Carrollton, Coppell, Corpus Christi, Dallas, Euless, Fort Worth, Grapevine,
Houston, Hurst, Justin, Little Elm, McKinney, Nacogdoches, Northlake, Oak Point,
Pilot Point, Plano, Providence Village, Richardson, Sanger, Southlake, Watauga,
plus one Leeds (UK) and one Tokyo record. Five of the 39 were also closed
(Spiral Diner Dallas, Church's Chicken Pilot Point, ACE Sushi Corpus Christi,
Mondo Subs Houston, Mondo Subs Leeds). Notable near-misses: La Rustica Italiano
(2960 W FM 720, Oak Point — often listed as Denton); Higuma Ramen & Izakaya
(Addison and Carrollton only — no Denton location); Kurogi (Northlake/Fort
Worth/Tokyo only).

**Not a restaurant (2).** ProKitchen Supply, 1208 Fort Worth Dr (restaurant
supply store); Berry Hall (auction house — also counted above under closed).

**No usable address (1).** Carmichaelstein's Bakery — address shown only as
"Denton, TX" with no street address.

**Not counted as exclusions (no place record returned):** Potbelly Sandwich Shop,
1216 W Hickory St Ste 104 (Birdeye says permanently closed; other sources still
list hours/menus — no place record exists, so it could not be verified either
way); Church's Chicken, 3450 E McKinney St (MapQuest says permanently closed;
no place record); 7 Brew Coffee, 906 W University Dr (not open — construction
May–Oct 2027, likely late-2027 opening); Cultura Beer Hall (Ave A) and Hive Bar
(Hickory St) — a single uncorroborated Instagram post that also misplaces
Greenhouse Restaurant, treated as likely fictional.

## Known coverage gaps

- **Scale check:** TripAdvisor lists roughly 400 restaurants in Denton and
  MenuPix lists 585. At 288, this census covers roughly half to two-thirds of
  those listings. Some of the gap is closed/stale listings on those sites; some
  is real places this sweep did not surface.
- **Food trucks are likely undercounted.** Trucks move, share addresses, and
  often lack stable place records. 10 food trucks made the census; more operate
  in Denton (e.g. at Austin Street Truck Stop, which is itself in the census as
  a venue).
- **Campus dining concepts largely lack place records** and are therefore not in
  the census, even though web sources confirm several are operating. Verified
  but excluded for lack of a place record: Subway, 717 S I-35E Ste 112
  (phone (940) 383-7438); Chick-fil-A, Texas Woman's University Student Center,
  420 Administration Dr; Smoothie King inside UNT Pohl Rec Center; QDOBA, UNT
  Union, 1155 Union Circle (status ambiguous — QDOBA's own site lists it,
  YellowPages says "Coming Soon"); Einstein Bros. Bagels, UNT Union, 1155 Union
  Cir; Burger King, UNT Union; Oda's Indian Cuisine, TWU Student Union at
  Hubbard Hall; Kurogi Hibachi, TWU Hubbard Hall; Bunsen Tea Lab, TWU Student
  Union (TWU lists Fall 2026 hours; TWU's dining tour page says "closed until
  further notice" — conflicting); ACE Sushi, TWU campus; Mondo Subs, TWU CFO
  building, 1315 N Bell Ave; TWU Starbucks in the Library, The Nest, The Hoot,
  The Hoot2; UNT Kitchen West, Eagle Landing, Bruce Hall, Maple Hall dining,
  Union Burger, Krispy Krunchy Chicken, Campus Chat food court.
- **Named leads never queried** (a follow-up sweep could try these): Hifi
  Bros-Indian Pizza, Burgers & Biryani; Fruteria Pa'Ti; SJ Donuts; Groovy
  Chicken and Waffles (food vendor at Toasty Bros); The Burger Den and The
  Meltdown (virtual brands at Denny's, 4007 N I-35); Brisket Burger; Subway
  6421 N I-35; Spicy Chowk; Gourmet Donuts & Bakery; Chase Elliott Chicken
  Tenders (985 S I-35 East, likely a virtual brand); RT's Neighborhood Bar;
  Logan's Roadhouse; Twin Peaks; Taco Casa; Hungry Howie's; GULLY BITES
  (3381 FM 720 — likely Oak Point, verify city before including); Taco Cabana
  2220 S Loop 288 (one listing, phone 940-230-2311 — likely stale, as Hawaiian
  Bros Island Grill is now at that address; include only if a place record
  verifies it); Indian Spice on wheel, 125 N Bonnie Brae St (MapQuest said
  "Closed" on census day, no place record). The easttexas.com Denton dining page
  (https://www.easttexas.com/cities/denton/dining/) lists nearby downtown blocks
  and could be harvested for more names.
- **Yield was still positive at the end:** the last two batches added 6 and 5
  new places. The search phase was closed after batch 16 on time/context budget,
  not because new places had stopped appearing — a follow-up sweep would likely
  find more, especially among small independents and outlying ZIPs.

## Borderline inclusions (in the census, flagged here)

- In-store grocery departments: 2× Kroger Bakery, 2× Walmart Deli.
- Snowfox (in-store sushi counter at Kroger, 5021 Teasley Ln).
- Mean Greens Cafe (UNT dining hall).
- Austin Street Truck Stop (food truck park venue, not a single restaurant).
- Breweries/taprooms where food comes via trucks or vendors: Denton County
  Brewing Company, Toasty Bros. Beer, Union Bear Brewing Company.
- Bars with food: East Side Denton, Harvest House, Oak St. Drafthouse, The
  Bearded Monk, Corazon roto cantina, The Garage, Fry Street Tavern, Dusty's
  Bar & Grill.
- La Laguna Meat Market & Kitchen (butcher shop + kitchen); Dafricana (African
  supermarket + restaurant); MLB Ballpark Bites (virtual/ghost-kitchen brand);
  Farmer's Fridge (salad vending fridge kiosk).

## Data quirks worth knowing

- **KFC, 315 W University Dr** — the place record's business description says
  "Temporarily Closed" but its Operating Status is Active, Open Now is Yes, and
  KFC's own site (crawled 2026-11-09) lists it as open. Included on the Active
  status; the conflict is noted here.
- **Little Caesars, 100 N Loop 288** — thin record (no hours, corporate phone,
  coordinates look off for that address). Recorded as shown.
- **Chick-fil-A (UNT)** — address recorded as shown in the place record
  ("11555 Union Circle Student Union Bldg"); the street number is likely 1155
  Union Cir, but the record was not corrected.
- **Buffalo Wild Wings, 1400 Loop 288** — DoorDash lists this same location as
  "1459 Loop 288"; the place record's address was used.
- **Kurume Ramen & Izakaya** — place record says suite #117, DoorDash says
  #118; the place record was used.
- **Chicken Express, 1115 S Loop 288** — web sources disagreed on the ZIP
  (DoorDash 76205; Restaurantji/menuweb 76209); the details record gives the
  ZIP in the file.
- **Bachelors Box** — two candidate place IDs circulated in working notes
  (1561346479091597 vs 1561346949091597); the details lookup confirmed
  1561346479091597 returns "Bachelors Box", and that ID is in the file.
- **Mochinut** — the canonical place-record name is "Mochinut Denton TX"; that
  is the name in the file.
- **Hours** — days with no opening-hours entry are shown as "Closed" when the
  place has hours data at all; places with no hours data have `hours: null`.
  Overnight hours (e.g. closing after midnight) are shown as given by the place
  record.
- **Ratings** — 154 records have no rating in the place system (null). Where a
  rating exists, the value is the place system's average rounded to 1 decimal
  with its review count.
- **Price level** — mapped from the place system's numeric level: 1 inexpensive,
  2 moderate, 3 expensive, 4 very expensive; null where the system has none.
