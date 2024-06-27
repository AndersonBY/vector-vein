/**
 * @Author: Bi Ying
 * @Date:   2022-12-18 00:42:28
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-06-25 17:07:21
 */
import { createApp, h } from 'vue'
import { createPinia } from 'pinia'

import Antd from 'ant-design-vue'
import { Typography } from 'ant-design-vue'
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
    if (block.parentNode.classList.contains('code-block')) {
      // Skip if header already added
      return;
    }

    hljs.highlightElement(block)
    block.classList.add('custom-scrollbar')
    block.classList.add('hljs')

    // Create new elements
    let wrapper = document.createElement('div');
    let header = document.createElement('div');
    let lang = document.createElement('span');
    let copyContainer = document.createElement('div');

    // Set classes and attributes
    wrapper.className = 'code-block';
    header.className = 'header';
    lang.className = 'language';
    copyContainer.className = 'copy-container';

    // Get language from classList
    let blockClassList = Array.from(block.classList);
    let language = blockClassList.find(c => c.startsWith('language-'));
    lang.textContent = language ? language.split('-')[1] : '';

    // Create Vue app for copy button
    const CopyApp = createApp({
      render() {
        return h(Typography.Paragraph, {
          copyable: { text: block.textContent },
        })
      }
    });

    // Put elements together
    header.appendChild(lang);
    header.appendChild(copyContainer);
    wrapper.appendChild(header);
    block.parentNode.insertBefore(wrapper, block);
    wrapper.appendChild(block);

    // Mount Vue app
    CopyApp.mount(copyContainer);
  })
})

router.beforeEach(async (to, from, next) => {
  if (to.meta.title) {
    document.title = getPageTitle(i18n.global.te, i18n.global.t, to.meta.title)
  }
  next()
})