import Vue from 'vue'
import './plugins/vuetify'
import VueAxiosPlugin from 'vue-axios-plugin'
import App from './App.vue'

Vue.config.productionTip = false

Vue.use(VueAxiosPlugin, {
  baseURL: 'http://localhost:8000/api/'
})

new Vue({
  render: h => h(App),
}).$mount('#app')
