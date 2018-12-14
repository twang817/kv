<template>
  <v-app>
    <v-toolbar app>
      <v-toolbar-title class="headline text-uppercase">
        <span>Memcache Monitor</span>
      </v-toolbar-title>
      <v-spacer></v-spacer>
      <v-menu offset-y>
        <v-btn
          flat
          slot="activator"
        >
          <span class="mr-2">Quick Links</span>
        </v-btn>
        <v-list>
          <v-list-tile v-for="item in quicklinks" :href="item.href" target="_blank">
            <v-list-tile-title>{{ item.name }}</v-list-tile-title>
          </v-list-tile>
        </v-list>
      </v-menu>
    </v-toolbar>

    <v-content>
      <Monitor/>
    </v-content>
  </v-app>
</template>

<script>
import Monitor from './components/Monitor'

export default {
  name: 'App',
  components: {
    Monitor
  },
  created() {
    this.quicklinks = [
      {"name": "Prometheus", "href": "http://localhost:9090"},
      {"name": "cAdvisor", "href": "http://localhost:9000"},
      {"name": "node-exporter", "href": "http://localhost:9100"},
      {"name": "Grafana", "href": "http://localhost:3000"},
      {"name": "Kibana", "href": "http://localhost:5601"}
    ]
  },
  data () {
    return {
    }
  }
}
</script>
