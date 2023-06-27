/**
 * @Author: Bi Ying
 * @Date:   2022-02-09 03:05:56
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2023-06-27 16:42:56
 */
export function zip(rows) {
  return rows[0].map((_, c) => rows.map(row => row[c]))
}

export function timeLength(length) {
  const hours = parseInt(length / 1000 / 60 / 60)
  const minutes = parseInt(length / 1000 / 60 % 60)
  if (store.state.userSettings.language == 'zh-CN') {
    return `${hours}小时${minutes}分钟`
  } else {
    return `${hours} hour${hours > 1 ? 's' : ''} ${minutes} minute${minutes > 1 ? 's' : ''}`
  }
}

export function timeLengthSeconds(length) {
  const minutes = parseInt(length / 1000 / 60)
  const seconds = parseInt(length / 1000 % 60)
  if (store.state.userSettings.language == 'zh-CN') {
    return `${minutes}分钟${seconds}秒`
  } else {
    return `${minutes} min${minutes > 1 ? 's' : ''} ${seconds} s`
  }
}

export function getFullUrl(path, querys) {
  let url = path
  if (querys) {
    url += '?'
    for (let key in querys) {
      url += `${key}=${querys[key]}&`
    }
    url = url.slice(0, -1)
  }
  return url
}

export function getRandomInt(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min
}

export function getRandomBackgroundImg() {
  const random = getRandomInt(1, 5)
  return new URL(`/src/assets/imgs/basic-layout-background/img${random}.svg`, import.meta.url).href
}

export function hashObject(obj) {
  const str = JSON.stringify(obj);
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) - hash) + str.charCodeAt(i);
    hash &= hash; // Convert to 32bit integer
  }
  return hash;
}