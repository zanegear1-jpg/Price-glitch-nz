# Price Glitch NZ

Mobile-friendly NZ retail deal dashboard starter.

## Defaults
- Retailer: All stores
- Deal type: All deals
- Minimum discount: 40%
- Home screen convenience password: `zaneg`

## Status
Front-end starter only. Live retailer feeds, price history, scheduled scanning, notifications and resale-margin calculations are not yet connected. The dashboard deliberately does not display fabricated deals.

## Security
The current password check is client-side and is not real security; it can be found by inspecting source. Use server-side authentication before protecting private information or deploying publicly. Never commit API keys, cookies, or retailer credentials.

## Retailer feeds
Integrate approved documented APIs for Mitre 10, Kmart, The Warehouse and Farmers. Respect permission scope, rate limits and access controls; do not bypass anti-bot controls.
