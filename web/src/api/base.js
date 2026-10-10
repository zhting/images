/**
 * API base: always same-origin `/api`.
 *
 * - Dev: Vite serves the page and proxies /api to the backend (vite.config.js).
 * - Packaged desktop: the backend serves the page itself on :8001.
 * - Phone on the LAN: whichever of the two the phone loaded the page from
 *   also answers /api, so no host/port guessing is needed.
 *
 * The previous absolute `http://localhost:8001` broke every one of these
 * except plain desktop dev: a phone's "localhost" is the phone, and the
 * packaged app's page origin (127.0.0.1:8001) differed from it, so requests
 * needed CORS. VITE_API_BASE still overrides for unusual setups.
 */
export const API_BASE = import.meta.env.VITE_API_BASE || '/api'

export default API_BASE
