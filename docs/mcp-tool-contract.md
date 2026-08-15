# Swiggy MCP — live tool contract

> Fetched: `2026-08-15T05:03:17.571616+00:00` from live `tools/list`.
> Source of truth for Nexus wiring. Do not invent tool names.

## Inventory

| Server | Tools |
| --- | ---: |
| `food` | 18 |
| `im` | 14 |
| `dineout` | 12 |
| **Total** | **44** |

## Tools by server

### food

#### `get_addresses` (read)

Swiggy (Instamart/Food): Get saved delivery addresses for the authenticated Swiggy user, sorted by last order date (most recent first). This tool works for Swiggy Instamart and Food services. Addresses are returned WITHOUT coordinates (latitude/longitude) for privacy protection. Authentication is ha

| Param | Required | Type |
| --- | --- | --- |
| `page` | no | `number` |

| `pageSize` | no | `number` |

#### `search_restaurants` (read)

Search and order food from restaurants for delivery. PRIMARY FOOD DELIVERY SERVICE - Use this when user wants to order food, get food delivered, or search restaurants for delivery. Swiggy Food delivery service. NOT for restaurant reservations or dine-out.

| Param | Required | Type |
| --- | --- | --- |
| `addressId` | yes | `string` |

| `query` | yes | `string` |

| `offset` | no | `number` |

#### `search_menu` (read)

Search for dishes and menu items to order for food delivery. PRIMARY FOOD DELIVERY SERVICE - Use this when user wants to find specific dishes, browse menu items, see what a restaurant offers, or order food. Swiggy Food delivery. Returns items with their customizations. The text response includes var

| Param | Required | Type |
| --- | --- | --- |
| `addressId` | yes | `string` |

| `query` | yes | `string` |

| `restaurantIdOfAddedItem` | no | `string` |

| `vegFilter` | no | `number` |

| `offset` | no | `number` |

#### `get_restaurant_menu` (read)

Get the complete menu of a restaurant, paginated by category. Use this to BROWSE a restaurant menu and see what is available. This is the PRIMARY tool for showing MORE options — use page/pageSize to navigate categories when user asks for more items or wants to explore the menu. All items within each

| Param | Required | Type |
| --- | --- | --- |
| `addressId` | yes | `string` |

| `restaurantId` | yes | `string` |

| `page` | no | `number` |

| `pageSize` | no | `number` |

#### `get_food_cart` (read)

Get current food delivery cart with all items. PRIMARY FOOD DELIVERY SERVICE - Use this to view cart contents when ordering food for delivery. Swiggy Food delivery. Response includes valid_addons field for each item which shows which addons are valid based on the selected variants. Use this to deter

| Param | Required | Type |
| --- | --- | --- |
| `addressId` | yes | `string` |

| `restaurantName` | no | `string` |

#### `update_food_cart` (write)

Add items to food delivery cart or update cart contents. PRIMARY FOOD DELIVERY SERVICE - Use this when user wants to add food items, dishes, or meals to their delivery cart. Swiggy Food delivery. Supports variants, variantsV2, and addons for customizing menu items. CRITICAL: Each menu item uses EITH

| Param | Required | Type |
| --- | --- | --- |
| `restaurantId` | yes | `string` |

| `cartItems` | yes | `array` |

| `addressId` | yes | `string` |

| `restaurantName` | no | `string` |

| `cutleryOptIn` | no | `boolean` |

#### `flush_food_cart` (write)

Clear or empty the food delivery cart. PRIMARY FOOD DELIVERY SERVICE - Use this to remove all items from the food delivery cart. Swiggy Food delivery. NOT for groceries.

_No input parameters (or schema empty)._

#### `place_food_order` (write MONEY)

Place food delivery order and confirm order placement. PRIMARY FOOD DELIVERY SERVICE - Use this when user wants to place order, confirm order, or complete food delivery order. Swiggy Food delivery. Requires delivery address ID (coordinates are fetched automatically). NOT for groceries or restaurant 

| Param | Required | Type |
| --- | --- | --- |
| `addressId` | yes | `string` |

| `paymentMethod` | no | `string` |

| `intentApp` | no | `string` |

| `generateUPIQR` | no | `boolean` |

| `noteToRestaurant` | no | `string` |

**HITL only — never probe without user Approve.**

#### `fetch_food_coupons` (read)

Get available coupons and offers for food delivery order. PRIMARY FOOD DELIVERY SERVICE - Use this to find discounts, coupons, or offers when ordering food for delivery. Swiggy Food delivery. IMPORTANT: Only recommend coupons that are valid for Cash on Delivery (COD) payment. Filter out any offers t

| Param | Required | Type |
| --- | --- | --- |
| `restaurantId` | yes | `string` |

| `addressId` | yes | `string` |

| `couponCode` | no | `string` |

#### `apply_food_coupon` (write)

Apply coupon code or discount to food delivery order. PRIMARY FOOD DELIVERY SERVICE - Use this when user wants to apply a coupon, discount code, or offer to their food delivery order. Swiggy Food delivery. Returns the updated cart with coupon applied, including new pricing, discounts, and savings in

| Param | Required | Type |
| --- | --- | --- |
| `couponCode` | yes | `string` |

| `addressId` | yes | `string` |

| `cartId` | no | `string` |

#### `get_food_orders` (read)

Swiggy Food order history - Use this to fetch ORDER HISTORY, past orders, or active orders. PRIMARY FOOD DELIVERY SERVICE - Use this FIRST when user asks: "show my food orders", "my food order history", "past food orders", "recent food orders", "what did I order", "my previous food orders", "list my

| Param | Required | Type |
| --- | --- | --- |
| `addressId` | yes | `string` |

| `activeOnly` | no | `boolean` |

#### `get_food_order_details` (read)

Get detailed information about a specific food delivery order. PRIMARY FOOD DELIVERY SERVICE - Use this when user asks about order details, order information, or wants to see what they ordered. Swiggy Food delivery. Returns comprehensive order details including items, variants, pricing breakdown, de

| Param | Required | Type |
| --- | --- | --- |
| `orderId` | yes | `string` |

#### `track_food_order` (read)

Track food delivery order status and delivery progress. PRIMARY FOOD DELIVERY SERVICE - Use this when user asks to track order, check delivery status, or see where their food order is. Swiggy Food delivery. Returns current status, ETA, and progress for orders that are being prepared or in delivery. 

| Param | Required | Type |
| --- | --- | --- |
| `orderId` | no | `string` |

#### `get_food_delivery_status` (read)

Internal: live delivery ETA for the Food order-success widget (not for conversational use). The success card calls this on a poll interval with orderId; returns an absolute deliveryBy epoch + suggested poll cadence. Gated by FOOD_LIVE_ETA. Prefer track_food_order for user-facing "where is my order" 

| Param | Required | Type |
| --- | --- | --- |
| `orderId` | yes | `string` |

#### `report_error` (read)

Generate an error report to share with the Swiggy MCP team. Use this when the user encounters an error and wants to report it. Returns a pre-filled mailto: link and a human-readable summary. The user can click the link to open their email client with the report ready to send. This also logs the repo

| Param | Required | Type |
| --- | --- | --- |
| `tool` | yes | `string` |

| `domain` | no | `string` |

| `errorMessage` | yes | `string` |

| `flowDescription` | no | `string` |

| `toolContext` | no | `object` |

| `userNotes` | no | `string` |

#### `get_payment_options` (read)

Fetch live payment options for the current cart. The live list will not include UPI methods if the user isn't yet eligible for UPI payments, or if UPI is temporarily unavailable for this business line.

| Param | Required | Type |
| --- | --- | --- |
| `cartAmount` | no | `number` |

| `addressId` | no | `string` |

#### `check_payment_status` (read)

Check status of an in-flight UPI payment (one status read).

| Param | Required | Type |
| --- | --- | --- |
| `paasId` | yes | `string` |

| `orderId` | no | `string` |

| `addressId` | no | `string` |

| `cartId` | no | `string` |

| `lat` | no | `number` |

| `lng` | no | `number` |

| `finalize` | no | `boolean` |

#### `confirm_order` (write MONEY)

Finalize a pre-PLACED order to PLACED state. ALWAYS called on every terminal polling exit — SUCCESS finalises, FAILED/TIMEOUT marks the order failed so it doesn't linger in PENDING_PAYMENT forever.

| Param | Required | Type |
| --- | --- | --- |
| `orderId` | yes | `string` |

| `transactionId` | no | `string` |

| `paasId` | no | `string` |

| `addressId` | no | `string` |

| `cartId` | no | `string` |

| `lat` | no | `number` |

| `lng` | no | `number` |

**HITL only — never probe without user Approve.**

### im

#### `get_addresses` (read)

Swiggy (Instamart/Food): Get saved delivery addresses for the authenticated Swiggy user, sorted by last order date (most recent first). This tool works for Swiggy Instamart and Food services. Addresses are returned WITHOUT coordinates (latitude/longitude) for privacy protection. Authentication is ha

| Param | Required | Type |
| --- | --- | --- |
| `page` | no | `number` |

| `pageSize` | no | `number` |

#### `search_products` (read)

Search for products available at the selected address. Returns products with their variants (e.g., different pack sizes, quantities). When a user asks to add a product, ALWAYS search first to see available variants, then ask the user which specific variant they want before adding to cart. Authentica

| Param | Required | Type |
| --- | --- | --- |
| `addressId` | yes | `string` |

| `query` | yes | `string` |

| `offset` | no | `number` |

#### `your_go_to_items` (read)

Fetch the user's Your Go To Items (frequently or recently ordered items) for the selected delivery address. Use addressId from get_addresses. Returns products with variants; pass BOTH spinId and skuId from the chosen variant when adding to cart via update_cart.

| Param | Required | Type |
| --- | --- | --- |
| `addressId` | yes | `string` |

| `offset` | no | `number` |

#### `get_cart` (read)

Swiggy Instamart (Grocery): Get current Swiggy Instamart grocery cart with all items and bill breakdown. Use this for Instamart grocery orders, NOT for Food delivery. Authentication is handled automatically.

_No input parameters (or schema empty)._

#### `update_cart` (write)

Swiggy Instamart (Grocery): Update Swiggy Instamart grocery cart with items. Replaces entire cart with the provided items. Use this for Instamart grocery orders, NOT for Food delivery. Authentication is handled automatically. Use addressId from get_addresses.

| Param | Required | Type |
| --- | --- | --- |
| `selectedAddressId` | yes | `string` |

| `items` | yes | `array` |

#### `clear_cart` (write)

Clear (remove all items from) the Instamart cart. Authentication is handled automatically.

_No input parameters (or schema empty)._

#### `checkout` (write MONEY)

Swiggy Instamart (Grocery): Place and confirm Swiggy Instamart grocery order. Creates order and confirms payment in a single operation. Use this for Instamart grocery orders, NOT for Food delivery.

| Param | Required | Type |
| --- | --- | --- |
| `addressId` | yes | `string` |

| `paymentMethod` | no | `string` |

| `intentApp` | no | `string` |

| `generateUPIQR` | no | `boolean` |

**HITL only — never probe without user Approve.**

#### `get_orders` (read)

Swiggy Instamart order history - Use this to fetch ORDER HISTORY, past orders, or order preferences. Use this FIRST when user asks: "show my orders", "get my orders", "my last order", "order history", "past orders", "recent orders", "list my orders", "what did I order before", "my previous orders", 

| Param | Required | Type |
| --- | --- | --- |
| `count` | no | `number` |

| `orderType` | no | `string` |

| `activeOnly` | no | `boolean` |

#### `track_order` (read)

Track Swiggy Instamart order status in real-time. PRIMARY TOOL for order tracking - Use this FIRST when user asks: "where is my order", "track my order", "order status", "what's the status of my order", "when will my order arrive", "ETA for my order", "is my order on the way", "has my order been del

| Param | Required | Type |
| --- | --- | --- |
| `orderId` | yes | `string` |

| `lat` | yes | `number` |

| `lng` | yes | `number` |

#### `get_delivery_status` (read)

Internal: live delivery ETA for the order-success widget (not for conversational use). The success card calls this on a poll interval with orderId + addressId; returns an absolute deliveryBy epoch + suggested poll cadence. Gated by IM_LIVE_ETA. Prefer track_order for user-facing "where is my order" 

| Param | Required | Type |
| --- | --- | --- |
| `orderId` | yes | `string` |

| `addressId` | yes | `string` |

#### `report_error` (read)

Generate an error report to share with the Swiggy MCP team. Use this when the user encounters an error and wants to report it. Returns a pre-filled mailto: link and a human-readable summary. The user can click the link to open their email client with the report ready to send. This also logs the repo

| Param | Required | Type |
| --- | --- | --- |
| `tool` | yes | `string` |

| `domain` | no | `string` |

| `errorMessage` | yes | `string` |

| `flowDescription` | no | `string` |

| `toolContext` | no | `object` |

| `userNotes` | no | `string` |

#### `get_payment_options` (read)

Fetch live payment options for the current cart. The live list will not include UPI methods if the user isn't yet eligible for UPI payments, or if UPI is temporarily unavailable for this business line.

| Param | Required | Type |
| --- | --- | --- |
| `cartAmount` | no | `number` |

| `addressId` | no | `string` |

#### `check_payment_status` (read)

Check status of an in-flight UPI payment (one status read).

| Param | Required | Type |
| --- | --- | --- |
| `paasId` | yes | `string` |

| `orderId` | no | `string` |

| `addressId` | no | `string` |

| `cartId` | no | `string` |

| `lat` | no | `number` |

| `lng` | no | `number` |

| `finalize` | no | `boolean` |

#### `confirm_order` (write MONEY)

Finalize a pre-PLACED order to PLACED state. ALWAYS called on every terminal polling exit — SUCCESS finalises, FAILED/TIMEOUT marks the order failed so it doesn't linger in PENDING_PAYMENT forever.

| Param | Required | Type |
| --- | --- | --- |
| `orderId` | yes | `string` |

| `transactionId` | no | `string` |

| `paasId` | no | `string` |

| `addressId` | no | `string` |

| `cartId` | no | `string` |

| `lat` | no | `number` |

| `lng` | no | `number` |

**HITL only — never probe without user Approve.**

### dineout

#### `get_saved_locations` (read)

Swiggy Dineout (Reservations): Get user's saved addresses for restaurant search. NOT for food delivery or grocery orders. Returns address IDs that can be passed to search_restaurants_dineout.

_No input parameters (or schema empty)._

#### `search_restaurants_dineout` (read)

Swiggy Dineout (Reservations): find restaurants to BOOK A TABLE at. Use when the user wants to go out and eat. NOT for food delivery or grocery orders. Returns cuisines, rating, cost for two, distance, highlights, offers and bookable deals.

| Param | Required | Type |
| --- | --- | --- |
| `query` | yes | `string` |

| `entityType` | no | `string` |

| `addressId` | no | `string` |

| `latitude` | no | `number` |

| `longitude` | no | `number` |

| `limit` | no | `number` |

| `offset` | no | `number` |

#### `get_restaurant_details` (read)

Swiggy Dineout (Reservations): Get details about a specific restaurant for TABLE BOOKING. NOT for food delivery or grocery orders. Returns ratings, deals and offers, opening/closing timings, address, menu images, and amenities (valet parking, live music, outdoor seating, etc.). Use this to show the 

| Param | Required | Type |
| --- | --- | --- |
| `restaurantId` | yes | `string` |

| `latitude` | yes | `number` |

| `longitude` | yes | `number` |

#### `render_restaurants_dineout` (read)

Swiggy Dineout: display restaurant cards in a rich UI widget. Call this AFTER search_restaurants_dineout, once you have decided which restaurants to show and in what order. Pass restaurantIds (from the search results) in display order, plus searches — the list of search(es) you ran ({ query, latitud

| Param | Required | Type |
| --- | --- | --- |
| `restaurantIds` | yes | `array` |

| `searches` | yes | `array` |

#### `get_available_slots` (read)

Swiggy Dineout (Reservations): Check available time slots for TABLE BOOKING at a restaurant. NOT for food delivery or grocery orders. Returns breakfast, lunch, and dinner slots for up to 7 DAYS starting from the requested date in a single call. The widget handles date switching client-side — do NOT 

| Param | Required | Type |
| --- | --- | --- |
| `restaurantId` | yes | `string` |

| `date` | yes | `string` |

| `latitude` | yes | `number` |

| `longitude` | yes | `number` |

#### `book_table` (write MONEY)

Swiggy Dineout (Reservations): Book a table at a restaurant for a specific time slot. NOT for food delivery or grocery orders. Books FREE reservations directly, and PAID prebook deals via UPI. FREE deal (isFree=true): pass slot details only — book_table creates the cart and confirms in one step. PAI

| Param | Required | Type |
| --- | --- | --- |
| `restaurantId` | yes | `string` |

| `slotId` | yes | `number` |

| `itemId` | yes | `string` |

| `reservationTime` | yes | `number` |

| `guestCount` | yes | `number` |

| `latitude` | yes | `number` |

| `longitude` | yes | `number` |

| `paymentMethod` | no | `string` |

| `cartKey` | no | `string` |

| `intentApp` | no | `string` |

| `generateUPIQR` | no | `boolean` |

| `tidOverride` | no | `string` |

**HITL only — never probe without user Approve.**

#### `create_cart` (write)

Swiggy Dineout (Reservations): Create a booking cart. NOT for food delivery or grocery orders. Use this for PAID prebook deals (isFree=false): call with cartType="DEAL_TICKET_PURCHASE" + slot details + guest count. It returns the cartKey and shows a Booking Summary card. STOP after this — wait for t

| Param | Required | Type |
| --- | --- | --- |
| `restaurantId` | yes | `string` |

| `cartType` | yes | `string` |

| `latitude` | yes | `number` |

| `longitude` | yes | `number` |

| `slotId` | no | `number` |

| `itemId` | no | `string` |

| `reservationTime` | no | `number` |

| `guestCount` | no | `number` |

| `billAmount` | no | `number` |

| `source` | no | `string` |

#### `get_booking_status` (read)

Swiggy Dineout (Reservations): Get booking status and details for a dineout reservation. NOT for food delivery or grocery orders. Returns restaurant name, booking date and time, guest count, deal title, and current status (confirmed/cancelled/completed). Use this when the user asks about their reser

| Param | Required | Type |
| --- | --- | --- |
| `orderId` | yes | `string` |

#### `report_error` (read)

Generate an error report to share with the Swiggy MCP team. Use this when the user encounters an error and wants to report it. Returns a pre-filled mailto: link and a human-readable summary. The user can click the link to open their email client with the report ready to send. This also logs the repo

| Param | Required | Type |
| --- | --- | --- |
| `tool` | yes | `string` |

| `domain` | no | `string` |

| `errorMessage` | yes | `string` |

| `flowDescription` | no | `string` |

| `toolContext` | no | `object` |

| `userNotes` | no | `string` |

#### `get_payment_options` (read)

Fetch live payment options for the current cart. The live list will not include UPI methods if the user isn't yet eligible for UPI payments, or if UPI is temporarily unavailable for this business line.

| Param | Required | Type |
| --- | --- | --- |
| `cartAmount` | no | `number` |

| `addressId` | no | `string` |

#### `check_payment_status` (read)

Check status of an in-flight UPI payment (one status read).

| Param | Required | Type |
| --- | --- | --- |
| `paasId` | yes | `string` |

| `orderId` | no | `string` |

| `addressId` | no | `string` |

| `cartId` | no | `string` |

| `lat` | no | `number` |

| `lng` | no | `number` |

| `finalize` | no | `boolean` |

#### `confirm_order` (write MONEY)

Finalize a pre-PLACED order to PLACED state. ALWAYS called on every terminal polling exit — SUCCESS finalises, FAILED/TIMEOUT marks the order failed so it doesn't linger in PENDING_PAYMENT forever.

| Param | Required | Type |
| --- | --- | --- |
| `orderId` | yes | `string` |

| `transactionId` | no | `string` |

| `paasId` | no | `string` |

| `addressId` | no | `string` |

| `cartId` | no | `string` |

| `lat` | no | `number` |

| `lng` | no | `number` |

**HITL only — never probe without user Approve.**

## Call shape

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": { "name": "<canonical>", "arguments": { } },
  "id": 1
}
```

Prefer `result.structuredContent` over prose `content[].text`.
Address field is often `id` — Nexus normalizes to `addressId`.

