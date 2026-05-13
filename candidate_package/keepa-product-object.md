About:
The product object contains all of our price history data and basic product information.

Returned by:
The product object is returned by the following requests:
Product Searches and Product Request.

Important:
Always evaluate the productType field first. This field determines what data for the product is available.

Format:

{
    "productType": Integer,
    "asin": String,
    "domainId": Integer,
    "title": String,
    "trackingSince": Integer,
    "listedSince": Integer,
    "lastUpdate": Integer,
    "lastRatingUpdate": Integer, 
    "lastPriceChange": Integer,
    "lastEbayUpdate": Integer,
    "lastStockUpdate": Integer,
    "images": Image array,
    "rootCategory": Integer,
    "categories": Long array,
    "categoryTree": Object array,
    "parentAsin": String,
    "parentAsinHistory": String array,
    "frequentlyBoughtTogether": String array,
    "bundleItems": String array,
    "eanList": String array,
    "upcList": String array,
    "gtinList": String array,
    "manufacturer": String,
    "brand": String,
    "brandStoreName": String,
    "brandStoreUrl": String,
    "brandStoreUrlName": String,
    "websiteDisplayGroup": String,
    "websiteDisplayGroupName": String,
    "salesRankDisplayGroup": String,
    "type": String,
    "partNumber": String,
    "binding": String,
    "scent": String,
    "shortDescription": String,
    "activeIngredients": String,
    "specialIngredients": String,
    "itemForm": String,
    "itemTypeKeyword": String,
    "recommendedUsesForProduct": String,
    "pattern": String,
    "specificUsesForProduct": String array,
    "businessDiscount": Integer,
    "lastBusinessDiscountUpdate": Integer,
    "safetyWarning": String,
    "productBenefit": String,
    "batteriesRequired": Boolean,
    "batteriesIncluded": Boolean,
    "targetAudienceKeyword": String,
    "style": String,
    "includedComponents": String,
    "materials": String array,
    "numberOfItems": Integer,
    "numberOfPages": Integer,
    "publicationDate": Integer,
    "releaseDate": Integer,
    "contributors": two dimensional String array,
    "languages":  two dimensional String array,
    "model": String,
    "color": String,
    "size": String,
    "edition": String,
    "format": String,
    "features": String array,
    "description": String,
    "hazardousMaterials": Object array,
    "videos": Object array,
    "aPlus": Object array,
    "deals": Deal Details Object array,
    "packageHeight": Integer,
    "packageLength": Integer,
    "packageWidth": Integer,
    "packageWeight": Integer,
    "packageQuantity": Integer,
    "itemHeight": Integer,
    "itemLength": Integer,
    "itemWidth": Integer,
    "itemWeight": Integer,
    "availabilityAmazon": Integer,
    "availabilityAmazonDelay": Integer array,
    "buyBoxEligibleOfferCounts": Integer array,
    "competitivePriceThreshold": Integer,
    "suggestedLowerPrice": Integer,
    "ebayListingIds": Long array,
    "isEligibleForTradeIn": Boolean,
    "isAdultProduct": Boolean,
    "isHeatSensitive": Boolean,
    "isMerchOnDemand": Boolean,
    "isHaul": Boolean,
    "launchpad": Boolean,
    "audienceRating": String,
    "ingredients": String,
    "urlSlug": String,
    "returnRate": Integer,
    "isEligibleForSuperSaverShipping": Boolean,
    "fbaFees": Object,
    "variableClosingFee": Integer,
    "referralFeePercentage": Double,
    "variations": Object array,
    "historicalVariations": String array,
    "coupon": Integer array,
    "couponHistory": Integer array,
    "promotions": Promotion Object array,
    "unitCount": Object,
    "stats": Statistics Object,
    "salesRankReference": Long,
    "salesRankReferenceHistory": Long array,
    "salesRanks": Object,
    "lastSoldUpdate": Integer,
    "monthlySold": Integer,
    "monthlySoldHistory": Integer array,
    "reviews": Review Object,
    "offers": Marketplace Offer Object array,
    "liveOffersOrder": Integer array,
    "buyBoxSellerIdHistory": String array,
    "buyBoxUsedHistory": String array,
    "isRedirectASIN": Boolean,
    "isSNS": Boolean,
    "offersSuccessful": Boolean,
    "csv": two dimensional Integer array
}
productType
Must always be evaluated first. Determines what data for the product is available. Possible values:

0 - STANDARD: Everything accessible
1 - DOWNLOADABLE: No price, rating and offers data accessible. Data is updated less frequently.
2 - EBOOK: No price, rating and offers data accessible. Data is updated less frequently.
3 - INACCESSIBLE: No price, rating and offers data accessible. Sales rank and offer count data is updated less frequently. Some fields may be missing.
4 - INVALID: No current data available due to invalid or deprecated ASIN, or other issues. Might be temporary.
5 - VARIATION_PARENT: Product is a parent ASIN. variations is set.
asin
The ASIN of the product.
Example: B00M0QVG3W

domainId
The domainId of the product’s Amazon locale.
Possible values: [ 1: com | 2: co.uk | 3: de | 4: fr | 5: co.jp | 6: ca | 8: it | 9: es | 10: in | 11: com.mx ]

title
Title of the product. Caution: may contain unescaped HTML markup in rare cases.
Example: Canon PowerShot SX400 Digital Camera with 30x Optical Zoom (Black)

trackingSince
States the time we have started tracking this product, in Keepa Time minutes.
Example: 2711319

listedSince
States the time the item was first listed on Amazon, in Keepa Time minutes. This timestamp is only available for some products. If not available, the field has the value 0 or -1.
Example: 2711319

lastUpdate
States the last time we have updated the information for this product, in Keepa Time minutes.
Example: 2711319

lastRatingUpdate
States the last time we have updated the product rating and review count, in Keepa Time minutes.
Example: 2711319

lastPriceChange
States the last time we have registered a price change (any price type), in Keepa Time minutes.
Example: 2711319

lastEbayUpdate
States the last time we have updated the eBay prices for this product, in Keepa Time minutes. If no matching products were found, the integer is negative.
Example: 2711319

lastStockUpdate
The most recent update of the stock data for this product’s offers, in Keepa Time minutes. This field is undefined unless the stock parameter was used and stock data was collected at least once. Not all offers are necessarily updated. Refer to the lastStockUpdate field of the individual offers.
Example: 2711319

images
Provides metadata for images associated with the product. The images field is an array of image objects, each containing up to two resolutions for the same image (if available). These are used in the product image carousel on Amazon. undefined if unavailable. Each object in the array represents the metadata for a single image in various sizes (large and medium).

Field Descriptions:

l (String): Large image filename.
lH (Integer): Height of the large image, in pixels.
lW (Integer): Width of the large image, in pixels.
m (String): Medium image filename.
mH (Integer): Height of the medium image, in pixels.
mW (Integer): Width of the medium image, in pixels.
Example:

"images": [{
    "l": "81bRlmLRyPL.jpg",
    "lH": 1500,
    "lW": 1500,
    "m": "g1dlEmb2mq3.jpg",
    "mH": 500,
    "mW": 500
}]
Full Amazon image path:
https://m.media-amazon.com/images/I/<image name>

rootCategory
Category node ID of the product’s root category. 0 if no root category known. The ID 9223372036854775807 (max signed long value) denotes a blank category with the name “?”. We use this in cases where a product is listed in no or non-existent categories.
Example: 562066

categories
Array of Amazon category node IDs this product is listed in. Can be empty.
Example: [569604]

categoryTree
Represents the category tree as an ordered array of objects, each consisting of two fields:

catId - Long - the category ID
name - String - the name of the category
parentAsin
The ASIN of the parent product (if the product has variations, otherwise null).
Example: B00M0QVG3W

parentAsinHistory
The history of the parentAsin field. This array has the format: [keepaTime, previous parent ASIN, …]. The timestamp indicates when the previously associated parentAsin ceased to be valid.
For the current parent ASIN, use the parentAsin field. undefined if the parentAsin field never changed. We started tracking parentAsin changes on March 18th 2024.
Example: [2711319, B00M0QVG3W]

variations
Contains up to 4000 variations of this product. Each object in the array represents a single variation. A variation object consists of the variation ASIN, an swatch image, and an attributes array, where each entry represents one variation theme, including a dimension and its corresponding value. To request live data for this field, the offers parameter must be used. Not all variations have a swatch image. Only available variations are provided.

Example:

"variations": [{
   "asin": "B07GFPNJL9",
   "image": "55DVdLc1oBC.jpg",
   "attributes": [{
      "dimension": "Size",
           "value": "7.24 LB"
      }, {
           "dimension": "FlavorName",
           "value": "Cheddar"
      }
   ]
}]
historicalVariations
Provides unlisted (historical and out of stock) variation ASINs of this product. undefined if no data is available or the historical-variations parameter was not specified.

videos
Provides metadata for videos associated with the product. The videos parameter is mandatory for access. Each object in the array represents the metadata for a single video. Metadata can be retrieved for all image carousel videos and up to 10 (community) videos from the product listing’s Videos section. To request live data for this field, the offers parameter must also be included. undefined if unavailable.

Example:

"videos": [{
    "title": "Compressed Air Duster", // string
    "image": "31XBcVI7oTL.jpg", // string
    "duration": 36, // short, in seconds
    "creator": "Seller", // string
    "name": "Innovation", // string, public name of the creator
    "url": "https://m.media-amazon.com/images/S/vse-vms-transcoding-artifact-us-east-1-prd/d8d8f97e-aa42-42d2-aa4c-6ab1b006edb5/default.jobtemplate.hls.m3u8" // string
}]
Note: The creator field represents the creator type and can have the following values:
Main, Customer, Seller, Influencer, Vendor, ThirdParty, Amazon, Merchant and Brand.
Main is used for all product image carousel videos for which no duration, title and name are available.
aPlus
Provides enhanced A+ content from Amazon product listings. The aplus parameter is mandatory for access. Each A+ content object consists of one or more modules containing descriptive text, images, and videos to further illustrate product features. undefined if unavailable.

Example:

"aPlus": [{
    "module": [{
        "text": [
            "Experience premium quality and design.",
            "Engineered for performance and style."
        ], // array of strings, each representing a block of descriptive text
        "image": [
            "https://m.media-amazon.com/images/S/aplus-media-library-service-media/47ac6642-83d5-4ebf-867b-ae890ef135d4.png"
        ], // array of strings, each representing a full image URL
        "imageAltText": [
           "Healthy delicious recipes",
        ], // an array of strings, each the alt text of the image.
        "video": [
             "https://m.media-amazon.com/images/S/aplus-media/vc/e07d60fa-d3dd-49fa-90d0-b07e05a3f783.mp4"
        ] // array of strings, each representing a full video URL
        "asin": [
             "B000K11CAA"
        ] // array of strings, each representing a comparison table module's product ASIN
    }],
    "fromManufacturer": true // boolean; indicates whether the A+ content is provided by the manufacturer/vendor
}]
Note:
The module array contains one or more A+ content modules. Each module object includes:
text: An array of strings with descriptive text blocks.
image: An array of strings, each a full URL to an image.
imageAltText: An array of strings, each the alt text of the corresponding image (same index as image).
video: An array of strings, each a full URL to a video.
The fromManufacturer field is a boolean that indicates if the A+ content originates from the manufacturer or vendor (true) or from another source (false).
deals
Provides metadata for active deals associated with the product’s buy box. undefined if unavailable. Only updated when the offers parameter is used.

Deal Details Object fields

accessType — String
Who can access the deal. New access types can be added at any time. Currently one of:

ALL
PRIME_EARLY_ACCESS
PRIME_EXCLUSIVE
dealType — String
The type of the deal badge. New deal types can be added at any time. Currently one of:

PRIME_DAY
PRIME_DAY_EARLY
EARLY_ACCESS_WITH_PRIME
PRIME_EXCLUSIVE
SELLING_FAST
PRIME_SELLING_FAST
LIMITED_TIME_DEAL
COUNTDOWN_ENDS_IN
APP_ONLY
CLEARANCE_NO_RETURNS
SPECIAL_EVENT_SALE
GENERIC_OFFER_PROMO
UNKNOWN
badge — String
The badge string as shown on the product page.
Example: “Early Prime Deal”.

Example

"deals": [
  {
    "accessType": "PRIME_EXCLUSIVE",
    "badge": "Early Prime Deal",
    "dealType": "EARLY_ACCESS_WITH_PRIME"
  }
]
frequentlyBoughtTogether
One or two “Frequently Bought Together” ASINs. null if not available. Field is updated when the offers parameter was used.
Example: [ “B00M0QVG3W”, “B00T85PMWY” ]

bundleItems
A list of ASINs this product bundle consists of. Only available for virtual product bundles. null if not available.
Example: [ “B00M0QVG3W”, “B00T85PMWY” ]

eanList
A list of EANs assigned to this product. The first index is the primary EAN. null if not available.
Example: [ “8806088624952” ]

upcList
A list of UPCs assigned to this product. The first index is the primary UPC. null if not available.
Example: [ “045496590086” ]

gtinList
A list of GTINs assigned to this product. The first index is the primary GTIN. null if not available.
Example: [ “00614141000012” ]

manufacturer
Name of the manufacturer. null if not available.
Example: Canon

brand
An item’s brand. null if not available.
Example: Sony

brandStoreName
The store name of the item’s brand. Never available for digital products, movie rentals, product bundles, Amazon Fresh, and Amazon Pantry. undefined if not available.
Example: Hot Wheels

brandStoreUrl
The brand store URL path. To get the full URL, prepend the Amazon domain of the respective locale (e.g. https//www.amazon.com). Never available for digital products, movie rentals, product bundles, Amazon Fresh, and Amazon Pantry. undefined if not available.
Example: /stores/LEGO/page/017EF856-965D-4B56-A171-EA61CAFF45DD

brandStoreUrlName
The brand store name from the URL path. Never available for digital products, movie rentals, product bundles, Amazon Fresh, and Amazon Pantry. undefined if not available.
Example: LEGO (from the URL: /stores/LEGO/page/…)

websiteDisplayGroup
A categorization of products that behave similarly, influencing how sales rank is calculated and displayed, especially for product variations.
Example: apparel_display_on_website

websiteDisplayGroupName
A categorization name of products that behave similarly, influencing how sales rank is calculated and displayed, especially for product variations.
Example: apparel

salesRankDisplayGroup
The categorization of products for which the primary sales rank is based on.
Example: apparel_display_on_website

type
The item’s productType. null if not available.
Example: VIDEO_GAME_CONTROLLER

partNumber
The item’s partNumber. null if not available.
Example: DSC-H300/BM-RB

binding
The item’s binding. null if not available. If the item is not a book, it is usually the product category instead.
Example: Hardcover

scent
The scent of the product. Describes the fragrance associated with the product.
Example: “Lavender”

shortDescription
A brief description of the product.
Example: “A soothing lavender-scented candle.”

activeIngredients
Active ingredients present in the product.
Example: “Lavender essential oil, Soy wax”

specialIngredients
Special ingredients used in the product that may have unique properties.
Example: “Beeswax blend, Natural dyes”

itemForm
The form or physical state of the item.
Example: “Liquid”

itemTypeKeyword
Keywords describing the type or category of the item.
Example: “body-lotions”

recommendedUsesForProduct
Recommended uses for the product to guide customers.
Example: “Aromatherapy, Home Decoration”

pattern
The pattern or design featured on the product. undefined if not available.
Example: “Striped”, “Floral”

materials
The materials of the product. undefined if not available.
Example: [ “Steel”, “Wood” ]

specialFeatures
The special features of the product. undefined if not available.
Example: [ “Fast Charging”, “Lightweight” ]

specificUsesForProduct
Specific uses for the product, providing detailed applications.
Example: [ “Relaxation”, “Decoration” ]

businessDiscount
The highest business discount percentage. Undefined if no business discount data is available.
Note: The business discount data is often outdated and may not reflect current offers.
Example: 14

lastBusinessDiscountUpdate
States the last time we have updated the businessDiscount field, in Keepa Time minutes . Undefined if the businessDiscount has no value.
Example: 2711319

safetyWarning
Safety warnings associated with the product to inform users of potential hazards.
Example: “Keep away from open flames.”

productBenefit
Benefits of using the product, highlighting its advantages.
Example: “Promotes relaxation and stress relief.”

batteriesRequired
Indicates whether batteries are required for the product to function.
Example: true

batteriesIncluded
Indicates whether batteries are included with the product upon purchase.
Example: false

targetAudienceKeyword
Keywords describing the target audience for the product.
Example: “Adults, Gift for Her”

style
The style of the product, which may influence its aesthetic appeal.
Example: “Modern”, “Vintage”

includedComponents
Components included with the product, detailing what is provided upon purchase.
Example: “Candle, Wick, Box”

material
Material of the product, specifying the primary substances used in its construction.
Example: “Soy Wax, Cotton”

numberOfItems
The number of items of this product. -1 if not available.
Example: 1

numberOfPages
The number of pages of this product. -1 if not available.
Example: 514

publicationDate
The item’s publication date in one of the following three formats:
YYYY or YYYYMM or YYYYMMDD (Y = year, M = month, D = day)
-1 if not available.
Examples:
1978 = the year 1978
200301 = January 2003
20150409 = April 9th, 2015

releaseDate
The item’s release date. Same format as publicationDate. -1 if not available.

contributors
The contributors of the item. A contributor can be an author, actor, director, etc. Each contributor entry has a name and a role type.
Example: [ [ “Vin Diesel”, “actor” ] ]

languages
An item can have one or more languages. Each language entry has a name and most also have a type. null if not available.
Examples:
[ [ “English”], [ “English”, “Original Language” ] ]

model
The item’s model. null if not available.
Example: DSC-H300/BM

color
The item’s color. null if not available.
Example: Black

size
The item’s size. null if not available.
Example: S

edition
The item’s edition. null if not available.
Example: Standard Edition

format
The item’s format. null if not available.
Example: AC-3

features
A list of up to 5 product features / bullet points. null if not available. An entry can contain HTML markup in rare cases. We currently limit each entry to a maximum of 1000 characters (if the feature is longer it will be cut off). This limitation may change in the future without prior notice.
Example:
[ “6 Universal outlets, 6 ft in Length”, “Will accept most of the plug types from around the world!”, … ],

description
A description of the product. null if not available. May contain HTML markup and \n newlines. We limit the product description to a maximum of 4000 characters (if the description is longer it will be cut off). This limitation may change in the future without prior notice. To request live data for this field the offers parameter must be used.
Example (excerpt): <p><b>Why should you buy our Universal Surge Protector?<b></p> • Professional series Universal Surge Protector will accept most of the plug types from around the world, including: UK, US, all of Europe, China, Australian and more! <br />• The AC surge suppression for full protection of 220-250V workstations…

hazardousMaterials
The hazardous material types of the product. undefined if not available. Each entry consists of two fields:

aspect - String
value - String
Example:

{
  "value": "AEROSOLS",
  "aspect": "proper_shipping_name"
}, {
  "value": "UN1950",
  "aspect": "united_nations_regulatory_id"
}
packageHeight
The package’s height in millimeters. 0 or -1 if not available.
Example: 144

packageLength
The package’s length in millimeters. 0 or -1 if not available.
Example: 144

packageWidth
The package’s width in millimeters. 0 or -1 if not available.
Example: 144

packageWeight
The package’s weight in grams. 0 or -1 if not available.
Example: 1500 (= 1,5 kg)

packageQuantity
Quantity of items in the package. 0 or -1 if not available.
Example: 4

itemHeight
The item’s height in millimeters. 0 or -1 if not available.
Example: 144

itemLength
The item’s length in millimeters. 0 or -1 if not available.
Example: 144

itemWidth
The item’s width in millimeters. 0 or -1 if not available.
Example: 144

itemWeight
The item’s weight in grams. 0 or -1 if not available.
Example: 1500 (= 1,5 kg)

availabilityAmazon
Availability of the sold by Amazon offer. Possible values:
-1: no Amazon offer exists
0: Amazon offer is in stock and shippable
1: Amazon offer is currently not in stock, but will be in the future (pre-order)
2: Amazon offer availability is “unknown”
3: Amazon offer is currently not in stock, but will be in the future (back-order)
4: Amazon offer shipping is delayed - see “availabilityAmazonDelay” for more details

availabilityAmazonDelay
If availabilityAmazon has the value 4, this field will provide the delay interval in hours. null if no data is available.
Example: [ 24, 48 ] (= Available to ship in 1-2 days.)
[ 0, 288 ] (= Usually dispatched within 12 days.)
[ 732, 1464 ] (= In stock. Usually ships within 1 to 2 months.)

buyBoxEligibleOfferCounts
If buyBoxEligibleOfferCounts is available, it represents an array of integers, each entry indicating the total number of offers eligible for the Buy Box across specified offer conditions and fulfillment channels. This array contains eight elements, indexed as follows:
0: New FBA
1: New FBM
2: Used FBA
3: Used FBM
4: Collectible FBA
5: Collectible FBM
6: Refurbished FBA
7: Refurbished FBM

competitivePriceThreshold
The competitivePriceThreshold field is a price based on competitive prices from other retailers (excluding other Amazon sellers). The offer may be ineligible for the Buy Box if the seller’s price + shipping is greater than this competitive price. Undefined if it has no value.

suggestedLowerPrice
The suggested lower price of the item, including shipping. The suggested lower price is based on a range of factors, including historical selling prices, recent Buy Box-eligible prices, and input from customers. Undefined if it has no value.

ebayListingIds
Contains the lowest priced matching eBay listing Ids. Always contains two entries, the first one is the listing id of the lowest priced listing in new condition, the second in used condition. null or 0 if not available.
Example: [ 273344490183, 0 ]

isEligibleForTradeIn
Whether or not the product is eligible for trade-in.
Example: true

isAdultProduct
Indicates if the item is considered to be for adults only.
Example: true

isHeatSensitive
Indicates if the item is heat sensitive (e.g. meltable).
Example: true

isMerchOnDemand
True if this product is an Amazon Merch on Demand product. undefined otherwise.
Example: true

isHaul
True if this product is an Amazon Haul product. undefined otherwise.
Only basic product information is available for Amazon Haul products.
Example: true

ingredients
The ingredient list of the product. undefined if not available.
Example: Purified Carbonated Water, Natural Flavors

launchpad
Indicates if the item is listed in the launchpad category. If so, the salesRankReference will not be available.
Example: true

audienceRating
Audience rating. The rating suggests the age for which the media is appropriate.
Example: PG-13 (Parents Strongly Cautioned)

urlSlug
The product listing URL slug.
Example: Ring-Video-Doorbell-Satin-Nickel-2020-Release

returnRate
This field provides information about the customer return rate for a product. The possible values are:

null: The return rate is either unavailable or considered average.
1: The product has a low return rate.
2: The product has a high return rate.
isEligibleForSuperSaverShipping
Whether or not the product’s buy box is eligible for free shipping.
Example: true

fbaFees
Object containing the FBA pick & pack fee for this product and the timestamp of the last update. The fee corresponds to the FBA pick & pack charge for this product, based on its dimensions and weight, assuming a selling price equal to the current offer price. If there is no current offer, the last known offer price is assumed; if neither is available, a default selling price of 100.00 is used. Values are integers in the marketplace’s smallest currency unit (for example euro cents or yen). null if not available.

Example:

"fbaFees": {
   "lastUpdate": keepaTime,
   "pickAndPackFee": 259
}
variableClosingFee
The variable closing fee for this product. Values are integers in the marketplace’s smallest currency unit (for example euro cents or yen). Undefined if not applicable.
Example: 81

referralFeePercentage
The Amazon referral fee percentage at the assumed selling price. The selling price is taken from the current offer price, otherwise the last known offer price, otherwise a default of 100.00. null if not available.
Example: 12

coupon
Contains coupon details for the buy box offer of the product, if available. null if not available.
An integer array with two entries:

The first entry is the discount for a one-time coupon (single purchase)
The second entry is a Subscribe & Save first-order coupon (S&S initial order only).
The Subscribe & Save value represents a clickable one-time coupon that applies only to the first Subscribe & Save order. It does not represent an ongoing Subscribe & Save discount for subsequent deliveries.
Entry value is either 0 if no coupon of that type is offered, positive for an absolute discount, or negative for a percentage discount. The coupons field is always accessible, but only updated if the offers parameter was used in the Product Request.

Example:
[ 200, -15 ] - Both coupon types available: $2 one time discount or 15% for subscribe and save.
[ -7, 0 ] - Only one time coupon type is available offering a 7% discount.

couponHistory
Contains historical values for the coupon field, if available. null if not available. We started tracking coupon history on June 15th 2024.
Format: [ keepaTime, one-time coupon, subscribe and save coupon, keepaTime, … ]
Example: [2711319, 200, -15, …]

promotions
Contains an array of active promotions. Not all product promotions can be provided. Requires the offers parameter to be updated. A promotion object consists of:

type - String - The type of promotion
SNS
amount - Integer - The discounted price
discountPercent - Integer - The discount percent
snsBulkDiscountPercent - Integer - The bulk discount percent for repeat SNS deliveries. undefined if no data available, 0 if no bulk discount provided.
unitCount
Object that contains unit count data, Undefined if it has no value.

unitValue - Double - The field returns the specified weight or volume to facilitate per unit pricing. For products measured by volume, weight, or linear dimensions, it provides the total net quantity shipped for a single ASIN (e.g., a 12-pack of 6 fl oz bottles of water = 72 fl oz, or a single 2-liter bottle = 2 liters). For products sold as individual units, it returns the total number of units (e.g., a pack of 12 pens = 12).
unitType - String - In cases where the product being sold is measured in units that are relevant to the customer’s purchasing decision, the unitType specifies the type of measurement used. For example, a bottle of soda may be measured in fluid ounces, while a box of screws is measured by the number of screws in the box.
eachUnitCount - Double - The number of units in an ‘each’; where an ‘each’ refers to the smallest component of a product with a UPC, and a unit defines how this ‘each’ is measured.
stats
Optional field, set only if the stats parameter was used in the Product Request. Contains a Statistics Object.

salesRankReference
The category node id of the main sales rank. -1 if not available, -2 if listed in launchpad.
Example: 281052 - http://www.amazon.com/b/?node=281052

salesRankReferenceHistory
A long array containing the historical category node id(s) of the main sales rank. This data, if available, can be used to match historical sales ranks provided in the CSV field to their reference category.
The category id has the value -1 if not available or -2 if listed in launchpad.
Format: [ keepaTime, category node id, … ]
Example: [2711319, 281052, …]

salesRanks
An object containing sales rank histories. Each key represents the categoryId of the rank, with the history in the corresponding value. Example:

"salesRanks": {
   "281052": [ keepaTime, salesRank, ... ]
   "123112042": [ keepaTime, salesRank, ... ]
}
lastSoldUpdate
States the last time we have updated the monthlySold field, in Keepa Time minutes. Undefined if the monthlySold has no value.
Example: 2711319

monthlySold
How often this product was bought in the past month. This field represents the bought past month metric found on Amazon search result pages. It is not an estimate. Amazon only provides the data in bracketed ranges such as “10+” or “100+”, rather than as exact figures. Undefined if it has no value. Most ASINs do not have this value set. The value is variation specific.
Example: 1000 - the ASIN was bought at least 1000 times in the past month.

monthlySoldHistory
Contains historical values of the monthlySold field. Undefined if it has no value.
Format: [ keepaTime, monthlySold, … ]

reviews
This object contains variation specific review and rating counts histories as well as a last update timestamp. null if not available. It is not possible to force an update to the reviews object data. For non-variation specific ratings and review data access the csv field. Accessible only if the rating parameter was used in the Product Request.
The ratingCount history has not been updated since April 9th 2025 as that data point was removed by Amazon.

"reviews": {
   "lastUpdate": keepaTime
   "ratingCount": [ keepaTime, ratingCount, ... ]
   "reviewCount": [ keepaTime, reviewCount, ... ]
}
offers
Optional field, set only if the offers parameter was used in the Product Request. Contains Marketplace Offer Objects.

liveOffersOrder
Optional field, set only if the offers parameter was used in the Product Request. Contains an ordered array of index positions in the offers array for all Marketplace Offer Objects retrieved for this call. If no offers were found, the field will be null. The sequence of integers reflects the ordering of the offers on the Amazon offer page (for all conditions). Since the offers field contains historical offers as well as current offers, one can use this array to look up all offers that are currently listed on Amazon in the correct order. Note: If there are identical offers (same seller, same condition, same shipping type, and same condition text) we only track the lowest-priced one. If this happens, there will be duplicate offer indexes in the liveOffersOrder field at the position of the omitted duplicate (higher-priced) offer - all pointing to the lowest-priced offer’s index.
Example: [ 3, 5, 2, 18, 15 ] - The offer with the array index 3 of the offers field is currently the first one listed on the offer listings page on Amazon, followed by the offer with the index 5, and so on.
Example with duplicates: [ 3, 5, 2, 18, 5 ] - The second offer, as listed on Amazon, is a lower-priced duplicate of the 5th offer on Amazon. The lower-priced one is included in the offers field at index 5.

buyBoxSellerIdHistory
Optional field, set only if the offers or buybox parameter was used in the Product Request.
Contains a history of sellerIds that held the Buy Box in the format: Keepa time minutes, sellerId, […].
If no seller qualified for the Buy Box, the sellerId “-1” is used (suppressed Buy Box). If we were unable to identify the seller or if the product was out of stock (no seller), the sellerId is “-2”.
Example: [“2860926”, “ATVPDKIKX0DER”, …]

buyBoxUsedHistory
Optional field, set only if the offers or buybox parameter was used in the Product Request.
A history of used buy box winners, containing the sellerIds, offer sub-condition, and FBA status in the format: Keepa time minutes, seller id, condition, isFBA, […].
If no seller qualified for the used buy box, the sellerId “” (empty String) is used.

condition can have the following values:
“2” - Used - Like New, “3” - Used - Very Good, “4” - Used - Good, “5” - Used - Acceptable
isFBA is either “1” - offer is FBA or “0” - offer is merchant fulfilled.
Example: [“2860926”, “ATVPDKIKX0DER”, “4”, “1”, …]

isRedirectASIN
Valid only if the offers parameter was used in the Product Request. Boolean indicating if the ASIN will be redirected to another one on Amazon (example: the ASIN has the color black variation, which is not available and is redirected on Amazon to the color red).

isSNS
Boolean indicating if the product’s Buy Box is available for subscribe and save.

offersSuccessful
Valid only if the offers parameter was used in the Product Request. Boolean indicating if the system was able to retrieve fresh offer information. Retrieval of fresh offers will always fail if the product has no offers (compare COUNT_* csv entries).

csv
A two-dimensional history array containing the product’s historical data. Access the first dimension index using the following enum/constants:

0 - AMAZON: Amazon price history
1 - NEW: Marketplace New price history
2 - USED: Marketplace Used price history
3 - SALES: Sales Rank history (not every product has a Sales Rank; variation items usually don’t have individual sales ranks)
4 - LISTPRICE: List Price (MSRP) history
5 - COLLECTIBLE: Collectible price history
6 - REFURBISHED: Refurbished price history
7 - NEW_FBM_SHIPPING: 3rd party (not including Amazon) New price history including shipping costs, only fulfilled by merchant (FBM)
8 - LIGHTNING_DEAL: Lightning Deal price history (special, relevant information below)
9 - WAREHOUSE: Amazon Warehouse price history
10 - NEW_FBA: Price history of the lowest 3rd party (not including Amazon/Warehouse) New offer that is fulfilled by Amazon
11 - COUNT_NEW: New offer count history (= count of marketplace merchants selling the product as new)
12 - COUNT_USED: Used offer count history
13 - COUNT_REFURBISHED: Refurbished offer count history
14 - COUNT_COLLECTIBLE: Collectible offer count history
15 - EXTRA_INFO_UPDATES: History of past updates to all offers-parameter related data: offers, aPlus, videos, isSNS, isRedirectASIN, and the csv types NEW_FBM_SHIPPING, WAREHOUSE, NEW_FBA, RATING, COUNT_REVIEWS, USED_SHIPPING, COLLECTIBLE_SHIPPING, BUY_BOX_USED_SHIPPING, PRIME_EXCL and REFURBISHED_SHIPPING. As updates to those fields are infrequent, it is essential to know when our system updated them. The absolute value indicates the number of offers fetched at the given time. If the value is positive, it means all available offers were fetched. If negative, there were more offers than fetched.
16 - RATING: The product’s rating history (an integer from 0 to 50, e.g., 45 = 4.5 stars)
17 - COUNT_REVIEWS: The product’s rating count history
18 - BUY_BOX_SHIPPING: The New buy box price history, including shipping costs. If no offer qualified for the buy box (or if the buy box is a used offer), the price has the value -1
19 - USED_NEW_SHIPPING: “Used - Like New” price history, including shipping costs
20 - USED_VERY_GOOD_SHIPPING: “Used - Very Good” price history, including shipping costs
21 - USED_GOOD_SHIPPING: “Used - Good” price history, including shipping costs
22 - USED_ACCEPTABLE_SHIPPING: “Used - Acceptable” price history, including shipping costs
23 - COLLECTIBLE_NEW_SHIPPING: “Collectible - Like New” price history, including shipping costs
24 - COLLECTIBLE_VERY_GOOD_SHIPPING: “Collectible - Very Good” price history, including shipping costs
25 - COLLECTIBLE_GOOD_SHIPPING: “Collectible - Good” price history, including shipping costs
26 - COLLECTIBLE_ACCEPTABLE_SHIPPING: “Collectible - Acceptable” price history, including shipping costs
27 - REFURBISHED_SHIPPING: Refurbished price history, including shipping costs
28 - EBAY_NEW_SHIPPING: Price history of the lowest new price on the respective eBay locale, including shipping costs
29 - EBAY_USED_SHIPPING: Price history of the lowest used price on the respective eBay locale, including shipping costs
30 - TRADE_IN: Trade-in price history (Amazon trade-in is not available for every locale)
31 - RENTAL: Rental price history (requires the use of the rental and offers parameters; Amazon Rental is only available for Amazon US)
32 - BUY_BOX_USED_SHIPPING: The Used buy box price history (any sub-condition), including shipping costs. If no offer qualified for the used buy box, the price has the value -1
33 - PRIME_EXCL: Price history of the lowest Prime exclusive New offer
34 - COUNT_NEW_FBA: New FBA offer count history (includes Amazon offer)
35 - COUNT_NEW_FBM: New FBM offer count history
The second dimension contains the price/value history in the format Keepa time minutes, value, […] or, if the type includes *_SHIPPING costs, the format: Keepa time minutes, price, shipping costs, […]. If history is unavailable, it is null. The price is an integer of the respective Amazon locale’s smallest currency unit (e.g., euro cents or yen). If no offer was available in the given interval (e.g., out of stock), the price has the value -1.

Important csv information:

We only append a new entry to the history array if the price/value changed, not every time we update the product.
Shipping and Handling costs are not included unless specified.
For NEW, USED, COLLECTIBLE, and REFURBISHED time series, the pricing definition is as follows: Entries dated before Feb 23, 2026, reflect the lowest listing price. Entries dated on or after Feb 23, 2026, reflect the lowest landing price (listing price + shipping).
Amazon is considered to be part of the marketplace. If Amazon has the overall lowest new price, the marketplace new price in the corresponding time interval is identical to the Amazon price.
The following types are only set if the offers parameter was used in the Product Request: NEW_FBM_SHIPPING, WAREHOUSE, NEW_FBA, RATING, COUNT_REVIEWS, BUY_BOX_SHIPPING, USED_*_SHIPPING, COLLECTIBLE_*_SHIPPING, REFURBISHED_SHIPPING, BUY_BOX_USED_SHIPPING, and PRIME_EXCL
About Lightning deals: If a deal is currently active, the last entry of the history array will contain the end date (a future date) with a price of -1. When accessing the current deal price, handle this special case. Alternatively, use the current price array of the stats object to access the current price. If no deal is currently active but the last entry has the value -1 with a date in the future, it means an upcoming deal is announced (scheduled to start at that date).
About eBay prices: eBay listings often have incorrect information and/or product codes, causing item mismatches and incorrect pricing information. Use eBay price history information with caution and do not rely on their accuracy. We update eBay prices at different intervals than Amazon prices.
We can add new data types to the csv field from time to time without announcement. Do not expect a fixed size of the first array dimension in your implementation.
Keepa Time Minutes

Time format used for all timestamps. To convert to an uncompressed Unix epoch time:

For milliseconds: (keepaTime + 21564000) * 60000
For seconds: (keepaTime + 21564000) * 60