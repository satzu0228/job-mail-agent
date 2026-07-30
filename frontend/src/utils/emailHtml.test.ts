import { beforeAll, describe, expect, it } from 'vitest'

import {
  countRemoteEmailImages,
  enhanceSanitizedEmailLinks,
  normalizeContentId,
  revealRemoteEmailImages,
} from './emailHtml'

class FakeStyle {
  private readonly values = new Map<string, string>()

  setProperty(name: string, value: string): void {
    this.values.set(name, value)
  }

  getPropertyValue(name: string): string {
    return this.values.get(name) ?? ''
  }

  get position(): string {
    return this.getPropertyValue('position')
  }

  get inset(): string {
    return this.getPropertyValue('inset')
  }

  get height(): string {
    return this.getPropertyValue('height')
  }
}

class FakeElement {
  readonly tagName: string = 'DIV'
  children: FakeElement[] = []
  parentElement: FakeElement | null = null
  readonly style = new FakeStyle()

  constructor(
    public textContent: string,
    private readonly width: number,
    private readonly height: number,
  ) {}

  getBoundingClientRect(): DOMRect {
    return { width: this.width, height: this.height } as DOMRect
  }
}

class FakeAnchor extends FakeElement {
  override readonly tagName: string = 'A'
  target = ''
  rel = ''

  constructor(
    public href: string,
    textContent: string,
    width: number,
    height: number,
    public display = 'block',
  ) {
    super(textContent, width, height)
  }

  hasAttribute(name: string): boolean {
    return name === 'href'
  }
}

function fakeDocument(links: FakeAnchor[]): Document {
  return {
    querySelectorAll: (selector: string) => (selector === 'a[href]' ? links : []),
    defaultView: {
      getComputedStyle: (element: FakeAnchor) => ({ display: element.display }),
    },
  } as unknown as Document
}

function fakeImageDocument(images: Array<{ dataset: { jmRemoteSrc?: string }; src: string }>): Document {
  return {
    querySelectorAll: (selector: string) =>
      selector === 'img[data-jm-remote-src]' ? images : [],
  } as unknown as Document
}

beforeAll(() => {
  Object.defineProperty(globalThis, 'HTMLAnchorElement', {
    configurable: true,
    value: FakeAnchor,
  })
})

describe('邮件图片辅助逻辑', () => {
  it('规范化 Content-ID 并统计外部图片', () => {
    const document = fakeImageDocument([
      { dataset: { jmRemoteSrc: 'https://example.com/a.png' }, src: '' },
      { dataset: { jmRemoteSrc: 'https://example.com/b.png' }, src: '' },
    ])

    expect(normalizeContentId(' <company-logo> ')).toBe('company-logo')
    expect(countRemoteEmailImages(document)).toBe(2)
  })

  it('仅显示 http 和 https 外部图片', () => {
    const safe = { dataset: { jmRemoteSrc: 'https://example.com/a.png' }, src: '' }
    const dangerous = { dataset: { jmRemoteSrc: 'javascript:alert(1)' }, src: '' }
    const document = fakeImageDocument([safe, dangerous])

    revealRemoteEmailImages(document)

    expect(safe.src).toBe('https://example.com/a.png')
    expect(dangerous.src).toBe('')
  })
})

describe('enhanceSanitizedEmailLinks', () => {
  it('把按钮容器中的零高度安全链接恢复为局部覆盖层', () => {
    const container = new FakeElement('查看安全活动', 160, 44)
    const link = new FakeAnchor('https://example.com/security', '', 160, 0)
    link.parentElement = container
    container.children = [link]

    enhanceSanitizedEmailLinks(fakeDocument([link]))

    expect(container.style.position).toBe('relative')
    expect(link.style.position).toBe('absolute')
    expect(link.style.inset).toBe('0')
    expect(link.style.height).toBe('100%')
    expect(link.target).toBe('_blank')
    expect(link.rel).toContain('noopener')
  })

  it('不增强危险协议或普通正文链接', () => {
    const container = new FakeElement('危险按钮', 160, 44)
    const danger = new FakeAnchor('javascript:alert(1)', '', 160, 0)
    const normal = new FakeAnchor('https://example.com', '普通链接', 80, 20)
    danger.parentElement = container
    container.children = [danger]

    enhanceSanitizedEmailLinks(fakeDocument([danger, normal]))

    expect(container.style.position).toBe('')
    expect(danger.style.position).toBe('')
    expect(normal.style.position).toBe('')
    expect(normal.target).toBe('_blank')
  })
})
