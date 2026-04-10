import { reactive } from 'vue'

export const searchState = reactive({
    mode: 'timeline', // 'timeline' or 'search'
    results: [],
    loading: false,
    query: '',
    translatedQuery: null,

    duration: 0,

    // Actions
    setResults(results, query, duration = 0, translatedQuery = null) {
        this.results = results
        this.query = query
        this.translatedQuery = translatedQuery
        this.duration = duration
        this.mode = 'search'
        this.loading = false
    },

    reset() {
        this.mode = 'timeline'
        this.results = []
        this.query = ''
        this.translatedQuery = null
        this.loading = false
    },

    setLoading(isLoading) {
        this.loading = isLoading
    },

    // On This Day State
    onThisDayData: [],
    onThisDayLoaded: false,

    // People State
    peopleData: [],
    peopleLoaded: false,

    // Tags State
    tagsData: [],
    tagsLoaded: false
})
