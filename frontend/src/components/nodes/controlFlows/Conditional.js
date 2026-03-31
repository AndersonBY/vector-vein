export const operatorOptions = [
  {
    value: 'equal',
    label: 'equal',
    field_type: ['string', 'number'],
  },
  {
    value: 'not_equal',
    label: 'not_equal',
    field_type: ['string', 'number'],
  },
  {
    value: 'greater_than',
    label: 'greater_than',
    field_type: ['number'],
  },
  {
    value: 'less_than',
    label: 'less_than',
    field_type: ['number'],
  },
  {
    value: 'greater_than_or_equal',
    label: 'greater_than_or_equal',
    field_type: ['number'],
  },
  {
    value: 'less_than_or_equal',
    label: 'less_than_or_equal',
    field_type: ['number'],
  },
  {
    value: 'include',
    label: 'include',
    field_type: ['string'],
  },
  {
    value: 'not_include',
    label: 'not_include',
    field_type: ['string'],
  },
  {
    value: 'is_empty',
    label: 'is_empty',
    field_type: ['string'],
  },
  {
    value: 'is_not_empty',
    label: 'is_not_empty',
    field_type: ['string'],
  },
  {
    value: 'starts_with',
    label: 'starts_with',
    field_type: ['string'],
  },
  {
    value: 'ends_with',
    label: 'ends_with',
    field_type: ['string'],
  },
]

export function createOutputField(handle) {
  return {
    required: true,
    placeholder: '',
    show: false,
    value: '',
    name: handle,
    display_name: handle,
    type: 'str',
    list: false,
    field_type: '',
    is_output: true,
  }
}

export function createTemplateData() {
  return {
    description: 'description',
    task_name: 'control_flows.conditional',
    has_inputs: true,
    template: {
      field_type: {
        required: true,
        placeholder: '',
        show: false,
        value: 'string',
        options: [
          {
            value: 'string',
            label: 'Str',
          },
          {
            value: 'number',
            label: 'Number',
          },
        ],
        name: 'field_type',
        display_name: 'field_type',
        type: 'str',
        list: false,
        field_type: 'select',
      },
      left_field: {
        required: true,
        placeholder: '',
        show: false,
        value: '',
        name: 'left_field',
        display_name: 'left_field',
        type: 'str|float|int',
        list: false,
        field_type: 'input',
      },
      branches: {
        required: true,
        placeholder: '',
        show: false,
        value: [],
        name: 'branches',
        display_name: 'branches',
        type: 'list[dict]',
        list: false,
        field_type: 'input',
      },
      default_value_key: {
        required: true,
        placeholder: '',
        show: false,
        value: 'default_value',
        name: 'default_value_key',
        display_name: 'default_value_key',
        type: 'str',
        list: false,
        field_type: 'input',
      },
      default_output_handle: {
        required: true,
        placeholder: '',
        show: false,
        value: 'default_output',
        name: 'default_output_handle',
        display_name: 'default_output_handle',
        type: 'str',
        list: false,
        field_type: 'input',
      },
      default_value: {
        required: true,
        placeholder: '',
        show: false,
        value: '',
        name: 'default_value',
        display_name: 'default_value',
        type: 'str',
        list: false,
        field_type: 'input',
      },
      default_output: createOutputField('default_output'),
      output: createOutputField('output'),
    },
  }
}
