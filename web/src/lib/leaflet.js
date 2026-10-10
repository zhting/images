/**
 * Leaflet, bundled with the app instead of loaded from unpkg.
 *
 * The CDN tags in index.html made the world map depend on internet access
 * (and on unpkg being reachable, which is unreliable in mainland China):
 * offline the page was silently blank. leaflet.markercluster is a UMD
 * plugin that attaches to the global `L`, so this module publishes it
 * before the plugin is evaluated — import order guarantees that.
 */
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import './leaflet-theme.css'

window.L = L

export default L
