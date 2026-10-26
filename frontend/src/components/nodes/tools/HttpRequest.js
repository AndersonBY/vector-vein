export function createTemplateData() {
  const field = (name, type, field_type, value, extra = {}) => ({
    name, display_name: name, type, field_type, value,
    required: false, placeholder: '', show: false, list: false,
    ...extra,
  })
  const advanced = { group: 'default', group_collpased: true }
  const output = { is_output: true }
  return {
    description: 'description',
    task_name: 'tools.http_request',
    has_inputs: true,
    template: {
      method: field('method', 'str', 'select', 'GET', {
        required: true,
        options: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'].map(value => ({ value, label: value })),
      }),
      url: field('url', 'str', 'input', '', { required: true, placeholder: 'https://example.com/api' }),
      headers: field('headers', 'dict|str', 'textarea', '{}', { ...advanced, has_tooltip: true }),
      query_params: field('query_params', 'dict|str', 'textarea', '{}', { ...advanced, has_tooltip: true }),
      body_type: field('body_type', 'str', 'select', 'none', {
        ...advanced,
        options: ['none', 'json', 'text', 'form'].map(value => ({ value, label: value })),
      }),
      body: field('body', 'any', 'textarea', '', { ...advanced, has_tooltip: true }),
      timeout: field('timeout', 'number', 'number', 30, { ...advanced, min: 1, max: 300 }),
      follow_redirects: field('follow_redirects', 'bool', 'checkbox', false, { ...advanced }),
      fail_on_http_error: field('fail_on_http_error', 'bool', 'checkbox', true, { ...advanced, has_tooltip: true }),
      status_code: field('status_code', 'int', '', 0, output),
      response_headers: field('response_headers', 'dict', '', {}, output),
      response_body: field('response_body', 'str', '', '', output),
      response_json: field('response_json', 'any', '', null, { ...output, has_tooltip: true }),
    },
  }
}
