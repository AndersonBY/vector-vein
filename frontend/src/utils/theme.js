/**
 * @Author: Bi Ying
 * @Date:   2024-07-13 13:51:30
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-07-13 13:59:46
 */

export function setTheme(theme) {
  loadMarkdownThemeCSS(theme);
}

async function loadMarkdownThemeCSS(theme) {
  const existingStyles = document.querySelectorAll('style[data-theme-markdown-style]');
  existingStyles.forEach(style => style.remove());

  try {
    if (theme === 'dark') {
      const darkCSS = await import('github-markdown-css/github-markdown-dark.css?inline');
      injectCSS(darkCSS.default, 'dark');
    } else {
      const lightCSS = await import('github-markdown-css/github-markdown-light.css?inline');
      injectCSS(lightCSS.default, 'light');
    }
  } catch (error) {
    console.error('Failed to load theme CSS:', error);
  }
}

function injectCSS(cssContent, theme) {
  const style = document.createElement('style');
  style.textContent = cssContent;
  style.setAttribute('data-theme-markdown-style', theme);
  document.head.appendChild(style);
}

export function initTheme(theme) {
  loadMarkdownThemeCSS(theme);
}