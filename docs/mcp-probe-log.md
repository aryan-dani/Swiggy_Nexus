# MCP live probe log

Started: `2026-08-15T05:04:33.244702+00:00`

| Step | Server | Tool | Status | ms | Notes |
| --- | --- | --- | --- | ---: | --- |
| 0a | `food` | `tools/list` | OK | 513 | 18 tools |
| 0b | `im` | `tools/list` | OK | 308 | 14 tools |
| 0c | `dineout` | `tools/list` | OK | 353 | 12 tools |
| 1a | `food` | `get_addresses` | OK | 423 | 3 addresses |
| 1b | `im` | `get_addresses` | OK | 382 | 3 addresses |
| 2 | `food` | `search_restaurants` | OK | 1553 | 10 restaurants |
| 3 | `food` | `search_menu` | OK | 2003 | ok |
| 4 | `food` | `get_restaurant_menu` | OK | 1180 | ok |
| 5 | `food` | `get_food_cart` | OK | 797 | ok |
| 6a | `food` | `update_food_cart` | OK | 423 | reversible add |
| 6b | `food` | `fetch_food_coupons` | OK | 300 | ok |
| 6c | `food` | `flush_food_cart` | OK | 526 | cleared |
| 7a | `food` | `get_food_orders` | OK | 335 | order=none |
| 7b | `food` | `get_food_order_details` | SKIP | 0 | no orderId |
| 7c | `food` | `track_food_order` | SKIP | 0 | no orderId |
| 8a | `im` | `search_products` | OK | 1013 | ok |
| 8b | `im` | `your_go_to_items` | OK | 782 | ok |
| 9a | `im` | `update_cart` | SKIP | 0 | no spinId |
| 9b | `im` | `get_cart` | OK | 601 | ok |
| 9c | `im` | `clear_cart` | OK | 656 | cleared |
| 10 | `im` | `get_orders` | OK | 466 | order=none |
| 10b | `im` | `track_order` | SKIP | 0 | no orderId |
| 11 | `dineout` | `get_saved_locations` | OK | 390 | ok |
| 12 | `dineout` | `search_restaurants_dineout` | OK | 466 | ok |
| 13a | `dineout` | `get_restaurant_details` | SKIP | 0 | no dineout rid |
| 13b | `dineout` | `get_available_slots` | SKIP | 0 | no dineout rid |
| 14 | `food` | `get_payment_options` | OK | 561 | ok |
| skip | `*` | `book_table` | WIRED_NOT_PROBED | 0 | money/HITL |
| skip | `*` | `checkout` | WIRED_NOT_PROBED | 0 | money/HITL |
| skip | `*` | `confirm_order` | WIRED_NOT_PROBED | 0 | money/HITL |
| skip | `*` | `create_address` | WIRED_NOT_PROBED | 0 | money/HITL |
| skip | `*` | `delete_address` | WIRED_NOT_PROBED | 0 | money/HITL |
| skip | `*` | `place_food_order` | WIRED_NOT_PROBED | 0 | money/HITL |

## Not probed (read/misc — wire only or needs prior state)

