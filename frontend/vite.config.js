/**
 * @Author: Bi Ying
 * @Date:   2022-12-18 00:42:28
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2023-05-16 11:09:12
 */
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'


const defaultConfig = {
  plugins: [vue({
    script: {
      defineModel: true
    }
  })],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  optimizeDeps: {
    include: [
      'ant-design-vue',
      '@ant-design/icons-vue',
    ],
  },
  define: {
    __VUE_I18N_FULL_INSTALL__: false,
    __VUE_I18N_LEGACY_API__: false,
    __INTLIFY_PROD_DEVTOOLS__: false,
  },
}

export default defineConfig(({ command, mode, ssrBuild }) => {
  if (command == 'serve') {
    return {
      ...defaultConfig,
      server: {
        proxy: {
          '/api': {
            target: `http://127.0.0.1:8888/api`,
            ws: true,
            changeOrigin: true,
            rewrite: (path) => path.replace(/^\/api/, ""),
          }
        }
      },
    }
  } else {
    return {
      ...defaultConfig,
      base: '/',
    }
  }
});
