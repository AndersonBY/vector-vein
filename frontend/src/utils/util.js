/**
 * @Author: Bi Ying
 * @Date:   2022-02-09 03:05:56
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-06-17 14:15:10
 */
import { useUserSettingsStore } from "@/stores/userSettings"

export function zip(rows) {
  return rows[0].map((_, c) => rows.map(row => row[c]))
}

export function timeLength(length) {
  const hours = parseInt(length / 1000 / 60 / 60)
  const minutes = parseInt(length / 1000 / 60 % 60)
  if (useUserSettingsStore().language == 'zh-CN') {
    return `${hours}小时${minutes}分钟`
  } else {
    return `${hours} hour${hours > 1 ? 's' : ''} ${minutes} minute${minutes > 1 ? 's' : ''}`
  }
}

export function timeLengthSeconds(length) {
  const minutes = parseInt(length / 1000 / 60)
  const seconds = parseInt(length / 1000 % 60)
  if (useUserSettingsStore().language == 'zh-CN') {
    return `${minutes}分钟${seconds}秒`
  } else {
    return `${minutes} min${minutes > 1 ? 's' : ''} ${seconds} s`
  }
}

export function formatTime(time, showSeconds = false) {
  const timeFormatOptions = {
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  }
  if (showSeconds) {
    timeFormatOptions.second = '2-digit'
  }
  return new Date(parseInt(time)).toLocaleString(useUserSettingsStore().language, timeFormatOptions)
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

export class ObjectHasher {
  constructor(ignoreKeys = []) {
    this.ignoreKeys = ignoreKeys;
  }

  processObject(obj, currentPath = '') {
    if (Array.isArray(obj)) {
      for (let i = 0; i < obj.length; i++) {
        this.processObject(obj[i], `${currentPath}[]`);
      }
    } else if (typeof obj === 'object' && obj !== null) {
      for (const key in obj) {
        const newPath = currentPath ? `${currentPath}.${key}` : key;
        if (this.shouldIgnore(newPath)) {
          delete obj[key];
        } else {
          this.processObject(obj[key], newPath);
        }
      }
    }
  }

  shouldIgnore(path) {
    return this.ignoreKeys.some(ignoreKey => {
      const ignoreKeyParts = ignoreKey.split('.');
      const pathParts = path.split('.');

      if (ignoreKeyParts.length !== pathParts.length) return false;

      for (let i = 0; i < ignoreKeyParts.length; i++) {
        if (ignoreKeyParts[i] === '[]' && pathParts[i].endsWith('[]')) {
          continue;
        }
        if (ignoreKeyParts[i] !== pathParts[i] && ignoreKeyParts[i] !== '[]') {
          return false;
        }
      }
      return true;
    });
  }

  hash(obj) {
    const objCopy = JSON.parse(JSON.stringify(obj));
    this.processObject(objCopy);
    const str = JSON.stringify(objCopy);
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      hash = ((hash << 5) - hash) + str.charCodeAt(i);
      hash &= hash;
    }
    return hash;
  }
}

export function hashObject(obj, ignoreKeys = []) {
  const hasher = new ObjectHasher(ignoreKeys);
  return hasher.hash(obj);
}

export function deepCopy(obj) {
  return JSON.parse(JSON.stringify(obj))
}

export function navigateToElementBottom(element) {
  if (element) {
    element.scrollTop = element.scrollHeight - element.clientHeight;
  }
}

export function jsonToPythonDict(jsonObj, indentLevel = 0) {
  const indentBase = ' '.repeat(4);
  let currentIndent = indentBase.repeat(indentLevel);
  let childIndent = indentBase.repeat(indentLevel + 1);

  function convertValue(value, indentLevel) {
    if (value === null) {
      return 'None';
    } else if (value === true) {
      return 'True';
    } else if (value === false) {
      return 'False';
    } else if (typeof value === 'object') {
      return jsonToPythonDict(value, indentLevel);
    } else if (typeof value === 'string') {
      return `"${value}"`;
    }
    return value.toString();
  }

  if (typeof jsonObj === 'object' && !Array.isArray(jsonObj)) {
    const entries = Object.entries(jsonObj).map(([key, val]) => {
      return `${childIndent}"${key}": ${convertValue(val, indentLevel + 1)}`;
    });
    return `{\n${entries.join(',\n')}\n${currentIndent}}`;
  } else if (Array.isArray(jsonObj)) {
    return '[\n' + jsonObj.map(v => childIndent + convertValue(v, indentLevel + 1)).join(',\n') + '\n' + currentIndent + ']';
  }
}