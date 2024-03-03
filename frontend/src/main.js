/**
 * @Author: Bi Ying
 * @Date:   2022-12-18 00:42:28
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-03-03 23:57:01
 */
import { createApp } from 'vue'
import { createPinia } from 'pinia'

import Antd from 'ant-design-vue'
import hljs from 'highlight.js'
import cronAnt from '@vue-js-cron/ant'
import '@vue-js-cron/ant/dist/ant.css'

import App from "./App.vue"
import router from "./router"
import i18n from '@/locales/index'
import { getPageTitle } from '@/utils/title'

import 'ant-design-vue/dist/reset.css'
import 'github-markdown-css'
import 'highlight.js/styles/monokai-sublime.css'
import '@icon-park/vue-next/styles/index.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(Antd)
app.use(i18n)
app.use(cronAnt)

app.mount('#app')

app.directive('highlight', function (el) {
  let blocks = el.querySelectorAll('pre code')
  blocks.forEach((block) => {
    hljs.highlightElement(block)
  })
})

router.beforeEach(async (to, from, next) => {
  if (to.meta.title) {
    document.title = getPageTitle(i18n.global.te, i18n.global.t, to.meta.title)
  }
  next()
})