/**
 * @Author: Bi Ying
 * @Date:   2023-12-10 17:17:56
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-06-09 23:45:03
 */
import baseAPI from './base'


export async function conversationAPI(action, parameter) {
  return await baseAPI(`conversation__${action}`, parameter)
}

export async function messageAPI(action, parameter) {
  return await baseAPI(`message__${action}`, parameter)
}

export async function agentAPI(action, parameter) {
  return await baseAPI(`agent__${action}`, parameter)
}

export async function audioAPI(action, parameter) {
  return await baseAPI(`audio__${action}`, parameter)
}