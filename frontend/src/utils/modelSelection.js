export const hasModelOption = (options, value) => Boolean(value) && options.some(option => option.value === value && !option.disabled)

export const filterModelOption = (input, option) => [option.label, option.value]
  .some(value => String(value ?? '').toLocaleLowerCase().includes(input.trim().toLocaleLowerCase()))
