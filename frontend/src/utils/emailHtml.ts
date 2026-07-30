const SAFE_LINK_PROTOCOLS = new Set(['http:', 'https:', 'mailto:'])

function isSafeEmailLink(link: HTMLAnchorElement): boolean {
  try {
    return SAFE_LINK_PROTOCOLS.has(new URL(link.href).protocol)
  } catch {
    return false
  }
}

function hasUsableBox(element: Element): boolean {
  const rect = element.getBoundingClientRect()
  return rect.width >= 16 && rect.height >= 16
}

/**
 * 恢复部分邮件模板依赖绝对定位实现的按钮链接。
 *
 * 安全清洗会移除不可信的绝对定位，某些邮件因此只剩下可见按钮和同级的零高度链接。
 * 此处只允许安全协议，并把链接限制在包含它的可见按钮容器内，不恢复邮件原始定位能力。
 */
export function enhanceSanitizedEmailLinks(document: Document): void {
  const links = [...document.querySelectorAll<HTMLAnchorElement>('a[href]')].filter(
    isSafeEmailLink,
  )

  for (const link of links) {
    link.target = '_blank'
    link.rel = 'nofollow noopener noreferrer'
  }

  const repairedContainers = new Set<HTMLElement>()
  for (const link of links) {
    if (link.textContent?.trim() || hasUsableBox(link)) continue

    const container = link.parentElement
    if (
      !container ||
      repairedContainers.has(container) ||
      !container.textContent?.trim() ||
      !hasUsableBox(container)
    ) {
      continue
    }

    const directLinks = [...container.children].filter(
      (child): child is HTMLAnchorElement =>
        child.tagName.toLowerCase() === 'a' &&
        child.hasAttribute('href') &&
        isSafeEmailLink(child as HTMLAnchorElement),
    )
    const activeLink =
      directLinks.find((candidate) => {
        const style = document.defaultView?.getComputedStyle(candidate)
        const rect = candidate.getBoundingClientRect()
        return style?.display !== 'none' && (rect.width > 0 || rect.height > 0)
      }) ?? directLinks[0]

    if (!activeLink) continue

    container.style.setProperty('position', 'relative', 'important')
    activeLink.style.setProperty('position', 'absolute', 'important')
    activeLink.style.setProperty('inset', '0', 'important')
    activeLink.style.setProperty('display', 'block', 'important')
    activeLink.style.setProperty('width', '100%', 'important')
    activeLink.style.setProperty('height', '100%', 'important')
    activeLink.style.setProperty('cursor', 'pointer', 'important')
    activeLink.style.setProperty('z-index', '1', 'important')
    repairedContainers.add(container)
  }
}

export function normalizeContentId(value: unknown): string {
  return String(value ?? '')
    .trim()
    .replace(/^<|>$/g, '')
}

export function countRemoteEmailImages(document: Document): number {
  return document.querySelectorAll('img[data-jm-remote-src]').length
}

export function revealRemoteEmailImages(document: Document): void {
  for (const image of document.querySelectorAll<HTMLImageElement>(
    'img[data-jm-remote-src]',
  )) {
    const source = image.dataset.jmRemoteSrc
    if (!source) continue
    try {
      const protocol = new URL(source).protocol
      if (protocol !== 'http:' && protocol !== 'https:') continue
      image.src = source
    } catch {
      // 清洗后的异常地址保持不加载。
    }
  }
}
