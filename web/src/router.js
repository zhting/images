import { createRouter, createWebHistory } from 'vue-router'
import Timeline from './components/Timeline.vue'
import Settings from './components/Settings.vue'

const routes = [
    { path: '/', redirect: '/timeline' },
    { path: '/timeline', component: Timeline },
    { path: '/settings', component: Settings },
    { path: '/best-shots', component: () => import('./views/BestShots.vue') },
    { path: '/documents', component: () => import('./views/Documents.vue') },
    { path: '/places', component: () => import('./views/Places.vue') },
    { path: '/people', component: () => import('./views/People.vue') },
    { path: '/tags', component: () => import('./views/Tags.vue') },
    { path: '/on-this-day', component: () => import('./views/OnThisDay.vue') },
    { path: '/travel', component: () => import('./views/Travel.vue') },
    { path: '/trash', component: () => import('./views/Trash.vue') },
    { path: '/logs', component: () => import('./views/Logs.vue') },
    { path: '/folders', component: () => import('./views/Folders.vue') }
]

const router = createRouter({
    history: createWebHistory(),
    routes,
})

export default router
