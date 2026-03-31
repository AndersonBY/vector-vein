import vuePlugin from 'eslint-plugin-vue'

export default [
  {
    ignores: ['dist/**', 'node_modules/**'],
  },
  ...vuePlugin.configs['flat/essential'],
  {
    rules: {
      'vue/multi-word-component-names': 'off',
      'vue/no-mutating-props': 'off',
      'vue/no-parsing-error': 'off',
      'vue/no-ref-as-operand': 'off',
      'vue/no-unused-vars': 'off',
      'vue/require-v-for-key': 'off',
      'vue/require-valid-default-prop': 'off',
      'vue/return-in-computed-property': 'off',
      'vue/valid-v-for': 'off',
      'vue/valid-v-show': 'off',
    },
  },
]
