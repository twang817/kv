<template>
  <v-container fluid>
    <v-layout row>
      <v-flex>
        <v-expansion-panel expand>
          <v-expansion-panel-content v-for="group in '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'" :key="group">
            <template v-if="keys[group]">
            <div slot="header" class="subheading">{{ group }}</div>
            <v-container fluid pt-1 grid-list-sm>
              <v-layout row wrap>
                <v-flex xs2 v-for="key in keys[group]" :key="key">
                  <v-card>
                    <v-card-title @click="getValue(key)">{{ key }}</v-card-title>
                    <v-card-text v-if="values[key]">{{ values[key] }}</v-card-text>
                  </v-card>
                </v-flex>
              </v-layout>
            </v-container>
            </template>
          </v-expansion-panel-content>
        </v-expansion-panel>
      </v-flex>
    </v-layout>
  </v-container>
</template>

<script>
  import _ from 'lodash'

  export default {
    data: () => ({
      keys: {},
      values: {}
    }),
    methods: {
      getValue: function(key) {
        var self = this
        this.$http.get('values/' + key).then(resp => {
          self.$set(self.values, key, resp.data.value)
        })
      }
    },
    mounted() {
      this.$http.get('keys').then(resp => {
        var r = _.groupBy(resp.data.keys, k => {
          return k[0].toUpperCase()
        })
        for (var key in r) {
          this.$set(this.keys, key, _.sortBy(r[key]))
        }
      })
    }
  }
</script>

<style>

</style>
