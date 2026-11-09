// Preserve button semantics in Task Agent renderer tests without mounting Ant tooltips.
export const iconButtonFixture = `
import { h, resolveComponent } from 'vue'
export default {
  inheritAttrs: false,
  props: { text: String, disabled: Boolean, loading: Boolean, danger: Boolean, size: String, type: { type: String, default: 'text' } },
  setup(props, { attrs, slots }) {
    return () => h(resolveComponent('AButton'), {
      ...attrs, disabled: props.disabled, loading: props.loading, danger: props.danger,
      size: props.size, type: props.type, 'aria-label': attrs['aria-label'] || props.text,
    }, { default: () => slots.icon?.() })
  },
}
`
