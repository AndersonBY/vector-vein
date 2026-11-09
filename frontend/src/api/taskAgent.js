import baseAPI from './base'


export async function taskAgentAPI(action, parameter = {}) {
  return await baseAPI(`task_agent__${action}`, parameter)
}
