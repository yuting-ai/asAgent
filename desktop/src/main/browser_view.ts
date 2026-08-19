import type { Session, WebContentsViewConstructorOptions } from 'electron'

import { parseBrowserWebUrl } from './external_url'

export const MAX_BROWSER_TABS = 16
export const BROWSER_HOME_URL = 'about:blank'
export const BROWSER_CONTROL_ACTIONS = ['back', 'forward', 'reload', 'home'] as const

export type BrowserControlAction = (typeof BROWSER_CONTROL_ACTIONS)[number]

export type BrowserTabState = {
  tabId: string
  url: string
  title: string
  canGoBack: boolean
  canGoForward: boolean
}

export type BrowserPageContent = {
  title: string
  url: string
  text: string
}

export type BrowserClickResult = {
  action: 'clicked'
  url: string
  title: string
  page?: BrowserPageContent
}

export type BrowserWaitResult = {
  changed: boolean
  page: BrowserPageContent
}

export type BrowserInteractiveElement = {
  target_id: string
  name: string
  role: string
  tag: string
  disabled: boolean
}

export type BrowserInteractiveSnapshot = {
  url: string
  elements: BrowserInteractiveElement[]
}

export const BROWSER_PAGE_TITLE_LIMIT = 512
export const BROWSER_PAGE_TEXT_LIMIT = 32 * 1024
export const BROWSER_CLICK_SELECTOR_LIMIT = 512
export const BROWSER_TARGET_ID_LIMIT = 80
export const BROWSER_INTERACTIVE_SCAN_LIMIT = 1000
export const BROWSER_INTERACTIVE_RETURN_LIMIT = 80
export const BROWSER_AGENT_POINTER_ID = 'asagent-agent-pointer'
export const BROWSER_TARGET_ATTR = 'data-asagent-target-id'
export const BROWSER_CLICK_POINTER_DELAY_MS = 150
export const BROWSER_CLICK_SETTLE_TIMEOUT_MS = 1_000
export const BROWSER_CLICK_SETTLE_QUIET_MS = 250
export const BROWSER_WAIT_POLL_INTERVAL_MS = 500
export const BROWSER_WAIT_SETTLE_QUIET_MS = 500

export const BROWSER_OPERATION_ERRORS = [
  'target was not found',
  'target is not visible',
  'target is obscured',
  'page changed; inspect interactive elements again',
  'current browser tab is not visible'
] as const

export type BrowserOperationError = (typeof BROWSER_OPERATION_ERRORS)[number]

export type BrowserFrame = {
  url: string
  frames: readonly BrowserFrame[]
  isDestroyed(): boolean
  executeJavaScript(code: string): Promise<unknown>
}

type InteractionTargetRecord = {
  frame: BrowserFrame
  selector: string
  name: string
  role: string
  tag: string
}

const BROWSER_PAGE_EXTRACT_SCRIPT = `(() => {
  const STRUCTURED_TEXT_LIMIT = 8 * 1024
  function isVisible(element) {
    if (!(element instanceof HTMLElement)) {
      return false
    }
    const style = window.getComputedStyle(element)
    return (
      style.display !== 'none' &&
      style.visibility !== 'hidden' &&
      Number(style.opacity) !== 0
    )
  }
  function normalizedText(value) {
    return String(value || '').replace(/\\s+/g, ' ').trim()
  }
  function structuredValue(element) {
    const label = normalizedText(
      element.getAttribute('aria-label') || element.getAttribute('aria-valuetext'),
    )
    const text = normalizedText(element.innerText || element.textContent)
    if (label && text && label !== text) {
      return label + ': ' + text
    }
    return label || text
  }
  const structuredValues = []
  const seen = new Set()
  for (const element of document.querySelectorAll(
    'table th, table td, [role="gridcell"], [role="cell"], [role="columnheader"], [role="rowheader"], [aria-valuetext]',
  )) {
    if (!isVisible(element)) {
      continue
    }
    const value = structuredValue(element)
    if (value && !seen.has(value)) {
      seen.add(value)
      structuredValues.push(value)
    }
    if (structuredValues.join('\\n').length >= STRUCTURED_TEXT_LIMIT) {
      break
    }
  }
  const title = String(document.title || '')
  const text = String(document.body && document.body.innerText ? document.body.innerText : '')
  return {
    title,
    text,
    structured_text: structuredValues.join('\\n').slice(0, STRUCTURED_TEXT_LIMIT),
  }
})()`

const BROWSER_REMOVE_POINTER_SCRIPT = `(() => {
  const existing = document.getElementById(${JSON.stringify(BROWSER_AGENT_POINTER_ID)})
  if (existing) {
    existing.remove()
  }
  return true
})()`

export type BrowserViewBounds = {
  x: number
  y: number
  width: number
  height: number
}

export type BrowserNavigationEvent = {
  preventDefault(): void
  url?: string
}

export type BrowserPageView = {
  setBounds(bounds: BrowserViewBounds): void
  setVisible(visible: boolean): void
  webContents: {
    loadURL(url: string): Promise<void>
    close(): void
    getURL(): string
    getTitle(): string
    canGoBack(): boolean
    canGoForward(): boolean
    goBack(): void
    goForward(): void
    reload(): void
    executeJavaScript(code: string): Promise<unknown>
    mainFrame: BrowserFrame
    sendInputEvent(event: {
      type: 'mouseMove' | 'mouseDown' | 'mouseUp'
      x: number
      y: number
      button?: 'left'
      clickCount?: number
    }): void
    setWindowOpenHandler(handler: (details?: { url?: string }) => { action: 'deny' }): void
    on(
      event:
        | 'will-navigate'
        | 'will-redirect'
        | 'will-frame-navigate'
        | 'did-frame-navigate'
        | 'did-navigate'
        | 'did-navigate-in-page'
        | 'page-title-updated',
      listener: (event: BrowserNavigationEvent, urlOrTitle?: string) => void
    ): void
  }
}

export type BrowserHostWindow = {
  isDestroyed(): boolean
  contentView: {
    children: readonly unknown[]
    addChildView(view: BrowserPageView): void
    removeChildView(view: BrowserPageView): void
  }
}

export type VisibleBrowserOptions = {
  session: Session
  createView: (options: WebContentsViewConstructorOptions) => BrowserPageView
  onTabState?: (state: BrowserTabState) => void
}

export function parseBrowserViewBounds(value: unknown): BrowserViewBounds {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new Error('Browser view bounds are invalid.')
  }

  const input = value as Record<string, unknown>
  const x = input['x']
  const y = input['y']
  const width = input['width']
  const height = input['height']
  if (
    typeof x !== 'number' ||
    !Number.isFinite(x) ||
    typeof y !== 'number' ||
    !Number.isFinite(y) ||
    typeof width !== 'number' ||
    !Number.isFinite(width) ||
    width < 0 ||
    typeof height !== 'number' ||
    !Number.isFinite(height) ||
    height < 0
  ) {
    throw new Error('Browser view bounds are invalid.')
  }

  return {
    x: Math.round(x),
    y: Math.round(y),
    width: Math.round(width),
    height: Math.round(height)
  }
}

export function parseBrowserControlAction(value: unknown): BrowserControlAction {
  if (value === 'back' || value === 'forward' || value === 'reload' || value === 'home') {
    return value
  }

  throw new Error('Browser control is invalid.')
}

export function parseBrowserTabId(value: unknown): string {
  if (typeof value !== 'string' || value.trim() === '') {
    throw new Error('Browser tab is invalid.')
  }

  const tabId = value.trim()
  if (tabId.length > 80 || !/^[A-Za-z0-9_-]+$/.test(tabId)) {
    throw new Error('Browser tab is invalid.')
  }

  return tabId
}

export function parseBrowserClickSelector(value: unknown): string {
  if (typeof value !== 'string') {
    throw new Error('Browser click selector is invalid.')
  }

  const selector = value.trim()
  if (selector === '') {
    throw new Error('Browser click selector is invalid.')
  }
  if (selector.length > BROWSER_CLICK_SELECTOR_LIMIT) {
    throw new Error('Browser click selector is too long.')
  }

  return selector
}

export function parseBrowserTargetId(value: unknown): string {
  if (typeof value !== 'string') {
    throw new Error('page changed; inspect interactive elements again')
  }

  const targetId = value.trim()
  if (
    targetId === '' ||
    targetId.length > BROWSER_TARGET_ID_LIMIT ||
    !/^target_[0-9]+$/.test(targetId)
  ) {
    throw new Error('page changed; inspect interactive elements again')
  }

  return targetId
}

export function normalizeBrowserOperationError(error: unknown): BrowserOperationError {
  const message = error instanceof Error ? error.message : String(error)
  for (const known of BROWSER_OPERATION_ERRORS) {
    if (message === known || message.includes(known)) {
      return known
    }
  }
  if (/not visible|Browser page is not visible/i.test(message)) {
    return 'current browser tab is not visible'
  }
  if (/obscured/i.test(message)) {
    return 'target is obscured'
  }
  if (/not found|not available|could not be clicked/i.test(message)) {
    return 'target was not found'
  }
  if (/page changed|inspect interactive/i.test(message)) {
    return 'page changed; inspect interactive elements again'
  }
  return 'target was not found'
}

function browserInspectScript(firstTargetNumber: number, maxElements: number): string {
  const firstNumber = Math.max(1, Math.floor(firstTargetNumber))
  const returnLimit = Math.max(0, Math.floor(maxElements))
  return `(() => {
  const ATTR = ${JSON.stringify(BROWSER_TARGET_ATTR)};
  const SCAN_LIMIT = ${BROWSER_INTERACTIVE_SCAN_LIMIT};
  const RETURN_LIMIT = ${returnLimit};
  const FIRST_TARGET_NUMBER = ${firstNumber};
  document.querySelectorAll('[' + ATTR + ']').forEach((node) => {
    node.removeAttribute(ATTR);
  });

  function isSemanticallyVisible(el) {
    if (!(el instanceof HTMLElement)) {
      return false;
    }
    const style = window.getComputedStyle(el);
    if (
      style.display === 'none' ||
      style.visibility === 'hidden' ||
      Number(style.opacity) === 0
    ) {
      return false;
    }
    return true;
  }

  function isPointerVisible(el) {
    if (!isSemanticallyVisible(el)) {
      return false;
    }
    if (window.getComputedStyle(el).pointerEvents === 'none') {
      return false;
    }
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  function resolveLabelledBy(el) {
    const ids = (el.getAttribute('aria-labelledby') || '')
      .split(/\\s+/)
      .filter(Boolean);
    if (ids.length === 0) {
      return '';
    }
    return ids
      .map((id) => {
        const node = document.getElementById(id);
        return node ? String(node.innerText || node.textContent || '').trim() : '';
      })
      .filter(Boolean)
      .join(' ')
      .trim();
  }

  function elementName(el) {
    const labelled = resolveLabelledBy(el);
    if (labelled) {
      return labelled.slice(0, 120);
    }
    for (const attr of ['aria-label', 'title', 'alt', 'placeholder']) {
      const value = (el.getAttribute(attr) || '').trim();
      if (value) {
        return value.slice(0, 120);
      }
    }
    if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement || el instanceof HTMLSelectElement) {
      const value = String(el.value || '').trim();
      if (value) {
        return value.slice(0, 120);
      }
    }
    const text = String(el.innerText || el.textContent || '')
      .replace(/\\s+/g, ' ')
      .trim();
    return text.slice(0, 120);
  }

  function elementRole(el) {
    const explicit = (el.getAttribute('role') || '').trim().toLowerCase();
    if (explicit) {
      return explicit.slice(0, 40);
    }
    const tag = el.tagName.toLowerCase();
    if (tag === 'a') {
      return 'link';
    }
    if (tag === 'button') {
      return 'button';
    }
    if (tag === 'input') {
      return ((el.getAttribute('type') || 'text') + '').slice(0, 40);
    }
    if (tag === 'label' && el instanceof HTMLLabelElement) {
      if (el.control instanceof HTMLInputElement) {
        return ((el.control.getAttribute('type') || 'checkbox') + '').slice(0, 40);
      }
      if (el.control instanceof HTMLSelectElement) {
        return 'combobox';
      }
      if (el.control instanceof HTMLTextAreaElement) {
        return 'textbox';
      }
      return 'label';
    }
    if (tag === 'select') {
      return 'combobox';
    }
    if (tag === 'textarea') {
      return 'textbox';
    }
    return 'clickable';
  }

  function isCandidate(el) {
    if (!(el instanceof HTMLElement) || !isSemanticallyVisible(el)) {
      return false;
    }
    const tag = el.tagName.toLowerCase();
    if (tag === 'html' || tag === 'body' || tag === 'iframe') {
      return false;
    }
    if (tag === 'label') {
      return elementName(el) !== '';
    }
    if (!isPointerVisible(el)) {
      return false;
    }
    if (tag === 'a' && el.hasAttribute('href')) {
      return true;
    }
    if (tag === 'button' || tag === 'select' || tag === 'textarea') {
      return true;
    }
    if (tag === 'input') {
      const type = (el.getAttribute('type') || 'text').toLowerCase();
      return type !== 'hidden';
    }
    const role = (el.getAttribute('role') || '').toLowerCase();
    if (
      ['button', 'link', 'checkbox', 'radio', 'switch', 'menuitemcheckbox', 'menuitemradio', 'option'].includes(
        role,
      )
    ) {
      return true;
    }
    if (el.hasAttribute('onclick') || el.tabIndex >= 0) {
      return true;
    }
    try {
      if (
        ['div', 'span', 'li', 'section', 'article'].includes(tag) &&
        window.getComputedStyle(el).cursor === 'pointer' &&
        elementName(el) !== ''
      ) {
        return true;
      }
    } catch (_) {}
    return false;
  }

  function isSemanticControl(el) {
    const tag = el.tagName.toLowerCase();
    const role = (el.getAttribute('role') || '').toLowerCase();
    return (
      ['a', 'button', 'input', 'select', 'textarea', 'label'].includes(tag) ||
      ['button', 'link', 'checkbox', 'radio', 'switch', 'menuitemcheckbox', 'menuitemradio', 'option'].includes(role)
    );
  }

  const all = Array.from(document.querySelectorAll('body *')).slice(0, SCAN_LIMIT);
  const raw = [];
  for (const el of all) {
    if (isCandidate(el)) {
      raw.push(el);
    }
  }
  const candidates = raw.filter((el) =>
    !raw.some(
      (other) =>
        other !== el &&
        other.contains(el) &&
        (!isSemanticControl(el) || isSemanticControl(other)),
    ),
  );
  const priority = (el) => {
    if (isSemanticControl(el)) {
      return 0;
    }
    if (el.hasAttribute('onclick') || el.tabIndex >= 0) {
      return 1;
    }
    return 2;
  };
  candidates.sort((left, right) => priority(left) - priority(right));

  const elements = [];
  for (let index = 0; index < candidates.length && elements.length < RETURN_LIMIT; index += 1) {
    const el = candidates[index];
    const targetId = 'target_' + (FIRST_TARGET_NUMBER + elements.length);
    el.setAttribute(ATTR, targetId);
    elements.push({
      target_id: targetId,
      name: elementName(el),
      role: elementRole(el),
      tag: el.tagName.toLowerCase(),
      disabled: Boolean(
        el.disabled ||
          el.getAttribute('aria-disabled') === 'true' ||
          el.getAttribute('disabled') !== null,
      ),
    });
  }
  return { elements };
})()`
}

function browserIframeClickScript(selector: string): string {
  const encodedSelector = JSON.stringify(selector)
  return `(() => {
    const selector = ${encodedSelector};
    const target = document.querySelector(selector);
    if (!(target instanceof HTMLElement)) {
      throw new Error('target was not found');
    }
    const topElement = document.elementFromPoint(
      Math.round(target.getBoundingClientRect().left + target.getBoundingClientRect().width / 2),
      Math.round(target.getBoundingClientRect().top + target.getBoundingClientRect().height / 2),
    );
    if (topElement === null || (topElement !== target && !target.contains(topElement))) {
      throw new Error('target is obscured');
    }
    target.click();
    return true;
  })()`
}

function browserClickPrepareScript(selector: string, semanticActivation: boolean): string {
  const encodedSelector = JSON.stringify(selector)
  const pointerId = JSON.stringify(BROWSER_AGENT_POINTER_ID)
  const useSemanticActivation = JSON.stringify(semanticActivation)
  return `(() => {
    const selector = ${encodedSelector};
    const pointerId = ${pointerId};
    const semanticActivation = ${useSemanticActivation};
    const target = document.querySelector(selector);
    if (!(target instanceof HTMLElement)) {
      throw new Error('target was not found');
    }
    function isSemanticallyVisible(el) {
      const style = window.getComputedStyle(el);
      return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) !== 0;
    }
    function usablePoint(el) {
      if (!isSemanticallyVisible(el) || window.getComputedStyle(el).pointerEvents === 'none') {
        return null;
      }
      const rect = el.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) {
        return null;
      }
      const x = Math.round(rect.left + rect.width / 2);
      const y = Math.round(rect.top + rect.height / 2);
      if (x < 0 || y < 0 || x > window.innerWidth || y > window.innerHeight) {
        return null;
      }
      const topElement = document.elementFromPoint(x, y);
      if (topElement === null || (topElement !== el && !el.contains(topElement) && !topElement.contains(el))) {
        return null;
      }
      return { x, y };
    }
    if (!isSemanticallyVisible(target)) {
      throw new Error('target is not visible');
    }
    target.scrollIntoView({ block: 'center', inline: 'center' });
    let point = usablePoint(target);
    if (point === null && semanticActivation) {
      const related = [
        ...Array.from(target.querySelectorAll('*')),
        target.parentElement,
      ];
      for (const element of related) {
        if (element instanceof HTMLElement) {
          element.scrollIntoView({ block: 'center', inline: 'center' });
          point = usablePoint(element);
          if (point !== null) {
            break;
          }
        }
      }
    }
    if (point === null) {
      throw new Error(semanticActivation ? 'target is not visible' : 'target is obscured');
    }
    const existing = document.getElementById(pointerId);
    if (existing) {
      existing.remove();
    }
    const pointer = document.createElement('div');
    pointer.id = pointerId;
    pointer.setAttribute('aria-hidden', 'true');
    pointer.style.cssText = [
      'pointer-events:none',
      'position:fixed',
      'z-index:2147483647',
      'left:' + (point.x - 10) + 'px',
      'top:' + (point.y - 10) + 'px',
      'width:20px',
      'height:20px',
      'border-radius:50%',
      'border:2px solid #12968c',
      'background:rgba(18,150,140,0.28)',
      'box-shadow:0 0 0 6px rgba(18,150,140,0.16)',
      'transition:opacity 120ms ease',
      'opacity:0'
    ].join(';');
    document.documentElement.appendChild(pointer);
    requestAnimationFrame(() => {
      pointer.style.opacity = '1';
    });
    return { x: point.x, y: point.y, activation: semanticActivation ? 'click' : 'mouse' };
  })()`
}

function browserSemanticClickScript(selector: string): string {
  const encodedSelector = JSON.stringify(selector)
  return `(() => {
    const target = document.querySelector(${encodedSelector});
    if (!(target instanceof HTMLElement)) {
      throw new Error('target was not found');
    }
    const style = window.getComputedStyle(target);
    if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity) === 0) {
      throw new Error('target is not visible');
    }
    target.click();
    return true;
  })()`
}

function browserClickConfirmScript(selector: string, x: number, y: number): string {
  const encodedSelector = JSON.stringify(selector)
  return `(() => {
    const selector = ${encodedSelector};
    const x = ${Math.round(x)};
    const y = ${Math.round(y)};
    const target = document.querySelector(selector);
    if (!(target instanceof HTMLElement)) {
      throw new Error('target was not found');
    }
    const topElement = document.elementFromPoint(x, y);
    if (topElement === null || (topElement !== target && !target.contains(topElement))) {
      throw new Error('target is obscured');
    }
    return { x, y };
  })()`
}

async function delay(ms: number): Promise<void> {
  await new Promise<void>((resolve) => {
    setTimeout(resolve, ms)
  })
}

function navigationTarget(event: BrowserNavigationEvent, url?: string): string {
  if (typeof url === 'string') {
    return url
  }

  return typeof event.url === 'string' ? event.url : ''
}

function isBlankBrowserUrl(url: string): boolean {
  return url === '' || url === BROWSER_HOME_URL
}

export function browserDisplayUrl(url: string): string {
  if (isBlankBrowserUrl(url)) {
    return ''
  }

  try {
    const parsed = new URL(url)
    parsed.username = ''
    parsed.password = ''
    return parsed.toString()
  } catch {
    return ''
  }
}

function truncateBrowserText(value: string, limit: number): string {
  return value.length <= limit ? value : value.slice(0, limit)
}

async function loadTabUrl(view: BrowserPageView, url: string): Promise<void> {
  try {
    await view.webContents.loadURL(url)
  } catch {
    throw new Error('Browser page could not be opened.')
  }
}

function titleFromUrl(url: string): string {
  if (isBlankBrowserUrl(url)) {
    return 'New Tab'
  }

  try {
    const hostname = new URL(url).hostname.replace(/^www\./u, '')
    return hostname === '' ? 'New Tab' : hostname
  } catch {
    return 'New Tab'
  }
}

function denyUnsafeNavigation(event: BrowserNavigationEvent, url?: string): void {
  const target = navigationTarget(event, url)
  if (isBlankBrowserUrl(target)) {
    return
  }

  try {
    parseBrowserWebUrl(target)
  } catch {
    event.preventDefault()
  }
}

export class VisibleBrowser {
  private readonly session: Session
  private readonly createView: (options: WebContentsViewConstructorOptions) => BrowserPageView
  private readonly onTabState: ((state: BrowserTabState) => void) | undefined
  private readonly tabs = new Map<string, BrowserPageView>()
  private readonly interactionSnapshots = new Map<string, Map<string, InteractionTargetRecord>>()
  private readonly lastActionPageText = new Map<string, string>()
  private hostWindow: BrowserHostWindow | undefined
  private lastBounds: BrowserViewBounds | undefined
  private visibleTabId: string | undefined
  private disposed = false

  constructor(options: VisibleBrowserOptions) {
    this.session = options.session
    this.createView = options.createView
    this.onTabState = options.onTabState
  }

  show(window: BrowserHostWindow, bounds: BrowserViewBounds, tabId: string): void {
    this.assertNotDisposed()
    const nextTabId = parseBrowserTabId(tabId)
    const view = this.ensureView(nextTabId)
    this.lastBounds = bounds
    if (this.visibleTabId !== undefined && this.visibleTabId !== nextTabId) {
      this.detachVisibleView()
    }

    if (
      this.hostWindow !== undefined &&
      this.hostWindow !== window &&
      !this.hostWindow.isDestroyed()
    ) {
      this.hostWindow.contentView.removeChildView(view)
    }

    this.hostWindow = window
    if (!window.contentView.children.includes(view)) {
      window.contentView.addChildView(view)
    }

    view.setBounds(bounds)
    view.setVisible(true)
    this.visibleTabId = nextTabId
  }

  hide(): void {
    if (this.disposed) {
      return
    }

    this.detachVisibleView()
  }

  async navigate(tabId: string, url: string): Promise<string> {
    this.assertNotDisposed()
    const safeUrl = parseBrowserWebUrl(url)
    await loadTabUrl(this.ensureView(parseBrowserTabId(tabId)), safeUrl)
    return browserDisplayUrl(safeUrl)
  }

  async control(tabId: string, action: BrowserControlAction): Promise<void> {
    this.assertNotDisposed()
    const id = parseBrowserTabId(tabId)
    const view = action === 'home' ? this.ensureView(id) : this.tabs.get(id)
    if (view === undefined) {
      return
    }

    switch (action) {
      case 'back':
        if (view.webContents.canGoBack()) {
          view.webContents.goBack()
        }
        break
      case 'forward':
        if (view.webContents.canGoForward()) {
          view.webContents.goForward()
        }
        break
      case 'reload':
        if (!isBlankBrowserUrl(view.webContents.getURL())) {
          view.webContents.reload()
        }
        break
      case 'home':
        await loadTabUrl(view, BROWSER_HOME_URL)
        break
    }
  }

  closeTab(tabId: string): void {
    this.assertNotDisposed()
    const closedTabId = parseBrowserTabId(tabId)
    const view = this.tabs.get(closedTabId)
    if (view === undefined) {
      return
    }

    if (this.visibleTabId === closedTabId) {
      this.detachVisibleView()
    }

    if (this.hostWindow !== undefined && !this.hostWindow.isDestroyed()) {
      this.hostWindow.contentView.removeChildView(view)
    }

    view.webContents.close()
    this.tabs.delete(closedTabId)
    this.interactionSnapshots.delete(closedTabId)
    this.lastActionPageText.delete(closedTabId)
  }

  isVisibleTab(tabId: string): boolean {
    if (this.disposed) {
      return false
    }

    return this.visibleTabId === parseBrowserTabId(tabId)
  }

  async readCurrentPage(tabId: string): Promise<BrowserPageContent> {
    this.assertNotDisposed()
    const id = parseBrowserTabId(tabId)
    if (this.visibleTabId !== id) {
      throw new Error('current browser tab is not visible')
    }

    const view = this.tabs.get(id)
    if (view === undefined) {
      throw new Error('current browser tab is not visible')
    }

    const frames = this.framesFor(view)
    const textParts: string[] = []
    let title = ''

    for (const [index, frame] of frames.entries()) {
      let extracted: unknown
      try {
        extracted = await frame.executeJavaScript(BROWSER_PAGE_EXTRACT_SCRIPT)
      } catch {
        if (index === 0) {
          throw new Error('target was not found')
        }
        continue
      }

      if (typeof extracted !== 'object' || extracted === null || Array.isArray(extracted)) {
        if (index === 0) {
          throw new Error('target was not found')
        }
        continue
      }

      const record = extracted as Record<string, unknown>
      if (typeof record.title !== 'string' || typeof record.text !== 'string') {
        if (index === 0) {
          throw new Error('target was not found')
        }
        continue
      }

      if (index === 0) {
        title = record.title
      }
      const structuredText =
        typeof record.structured_text === 'string' ? record.structured_text.trim() : ''
      const frameText = [
        record.text.trim(),
        structuredText === '' ? '' : `[Structured table content]\n${structuredText}`
      ]
        .filter(Boolean)
        .join('\n\n')
      if (frameText !== '') {
        textParts.push(index === 0 ? frameText : `[Embedded page content]\n${frameText}`)
      }
    }

    return {
      title: truncateBrowserText(title, BROWSER_PAGE_TITLE_LIMIT),
      url: browserDisplayUrl(view.webContents.getURL()),
      text: truncateBrowserText(textParts.join('\n\n'), BROWSER_PAGE_TEXT_LIMIT)
    }
  }

  async waitForCurrentPage(tabId: string, seconds: number): Promise<BrowserWaitResult> {
    this.assertNotDisposed()
    const id = parseBrowserTabId(tabId)
    this.assertVisibleTab(id)

    const deadline = Date.now() + seconds * 1_000
    let latestPage = await this.readCurrentPage(id)
    let observedText = this.lastActionPageText.get(id) ?? latestPage.text
    let changed = latestPage.text !== observedText
    let lastChangeAt = changed ? Date.now() : undefined
    observedText = latestPage.text

    while (Date.now() < deadline) {
      const remaining = deadline - Date.now()
      await delay(Math.min(BROWSER_WAIT_POLL_INTERVAL_MS, remaining))
      this.assertVisibleTab(id)

      try {
        latestPage = await this.readCurrentPage(id)
      } catch {
        continue
      }

      const now = Date.now()
      if (latestPage.text !== observedText) {
        observedText = latestPage.text
        changed = true
        lastChangeAt = now
      } else if (
        changed &&
        lastChangeAt !== undefined &&
        now - lastChangeAt >= BROWSER_WAIT_SETTLE_QUIET_MS
      ) {
        break
      }
    }

    this.lastActionPageText.set(id, latestPage.text)
    return { changed, page: latestPage }
  }

  async inspectInteractive(tabId: string): Promise<BrowserInteractiveSnapshot> {
    this.assertNotDisposed()
    const id = parseBrowserTabId(tabId)
    if (this.visibleTabId !== id) {
      throw new Error('current browser tab is not visible')
    }

    const view = this.tabs.get(id)
    if (view === undefined) {
      throw new Error('current browser tab is not visible')
    }

    const targets = new Map<string, InteractionTargetRecord>()
    const elements: BrowserInteractiveElement[] = []

    for (const frame of this.framesFor(view)) {
      if (elements.length >= BROWSER_INTERACTIVE_RETURN_LIMIT) {
        break
      }

      const remaining = BROWSER_INTERACTIVE_RETURN_LIMIT - elements.length
      let extracted: unknown
      try {
        extracted = await frame.executeJavaScript(
          browserInspectScript(elements.length + 1, remaining)
        )
      } catch {
        continue
      }

      if (typeof extracted !== 'object' || extracted === null || Array.isArray(extracted)) {
        continue
      }

      const record = extracted as Record<string, unknown>
      if (!Array.isArray(record.elements)) {
        continue
      }

      for (const item of record.elements) {
        if (elements.length >= BROWSER_INTERACTIVE_RETURN_LIMIT) {
          break
        }
        if (typeof item !== 'object' || item === null || Array.isArray(item)) {
          continue
        }
        const entry = item as Record<string, unknown>
        if (
          typeof entry.target_id !== 'string' ||
          typeof entry.name !== 'string' ||
          typeof entry.role !== 'string' ||
          typeof entry.tag !== 'string' ||
          typeof entry.disabled !== 'boolean'
        ) {
          continue
        }
        let targetId: string
        try {
          targetId = parseBrowserTargetId(entry.target_id)
        } catch {
          continue
        }
        if (targets.has(targetId)) {
          continue
        }
        const selector = `[${BROWSER_TARGET_ATTR}="${targetId}"]`
        targets.set(targetId, {
          frame,
          selector,
          name: truncateBrowserText(entry.name, 120),
          role: truncateBrowserText(entry.role, 40),
          tag: truncateBrowserText(entry.tag, 40)
        })
        elements.push({
          target_id: targetId,
          name: truncateBrowserText(entry.name, 120),
          role: truncateBrowserText(entry.role, 40),
          tag: truncateBrowserText(entry.tag, 40),
          disabled: entry.disabled
        })
      }
    }

    this.interactionSnapshots.set(id, targets)
    return {
      url: browserDisplayUrl(view.webContents.getURL()),
      elements
    }
  }

  async clickCurrentPage(tabId: string, targetId: string): Promise<BrowserClickResult> {
    this.assertNotDisposed()
    const id = parseBrowserTabId(tabId)
    if (this.visibleTabId !== id) {
      throw new Error('current browser tab is not visible')
    }

    const view = this.tabs.get(id)
    if (view === undefined) {
      throw new Error('current browser tab is not visible')
    }

    const snapshot = this.interactionSnapshots.get(id)
    const safeTargetId = parseBrowserTargetId(targetId)
    const target = snapshot?.get(safeTargetId)
    if (target === undefined) {
      throw new Error('page changed; inspect interactive elements again')
    }

    if (target.frame.isDestroyed()) {
      this.interactionSnapshots.delete(id)
      throw new Error('page changed; inspect interactive elements again')
    }

    const safeSelector = target.selector
    const frame = target.frame
    const isMainFrame = frame === view.webContents.mainFrame
    let pointerInstalled = false
    let textBeforeClick: string | undefined

    try {
      textBeforeClick = (await this.readCurrentPage(id)).text
    } catch {
      // Click remains available when a page cannot be read for settling.
    }

    try {
      let prepared: unknown
      try {
        prepared = await frame.executeJavaScript(
          browserClickPrepareScript(safeSelector, target.tag === 'label')
        )
      } catch (error) {
        throw new Error(normalizeBrowserOperationError(error))
      }

      if (typeof prepared !== 'object' || prepared === null || Array.isArray(prepared)) {
        throw new Error('target was not found')
      }

      const preparedPoint = prepared as Record<string, unknown>
      if (
        typeof preparedPoint.x !== 'number' ||
        typeof preparedPoint.y !== 'number' ||
        (preparedPoint.activation !== 'mouse' && preparedPoint.activation !== 'click')
      ) {
        throw new Error('target was not found')
      }

      pointerInstalled = true
      await delay(BROWSER_CLICK_POINTER_DELAY_MS)

      if (preparedPoint.activation === 'click') {
        try {
          await frame.executeJavaScript(browserSemanticClickScript(safeSelector))
        } catch (error) {
          throw new Error(normalizeBrowserOperationError(error))
        }
      } else if (isMainFrame) {
        let confirmed: unknown
        try {
          confirmed = await frame.executeJavaScript(
            browserClickConfirmScript(safeSelector, preparedPoint.x, preparedPoint.y)
          )
        } catch (error) {
          throw new Error(normalizeBrowserOperationError(error))
        }

        if (typeof confirmed !== 'object' || confirmed === null || Array.isArray(confirmed)) {
          throw new Error('target was not found')
        }

        const point = confirmed as Record<string, unknown>
        if (typeof point.x !== 'number' || typeof point.y !== 'number') {
          throw new Error('target was not found')
        }

        const x = Math.round(point.x)
        const y = Math.round(point.y)
        view.webContents.sendInputEvent({ type: 'mouseMove', x, y })
        view.webContents.sendInputEvent({
          type: 'mouseDown',
          x,
          y,
          button: 'left',
          clickCount: 1
        })
        view.webContents.sendInputEvent({
          type: 'mouseUp',
          x,
          y,
          button: 'left',
          clickCount: 1
        })
      } else {
        try {
          await frame.executeJavaScript(browserIframeClickScript(safeSelector))
        } catch (error) {
          throw new Error(normalizeBrowserOperationError(error))
        }
      }

      const page =
        textBeforeClick !== undefined && textBeforeClick !== ''
          ? await this.settleAfterClick(id, textBeforeClick)
          : undefined

      if (page !== undefined) {
        this.lastActionPageText.set(id, page.text)
      }

      return {
        action: 'clicked',
        url: browserDisplayUrl(view.webContents.getURL()),
        title: truncateBrowserText(
          view.webContents.getTitle().trim() || titleFromUrl(view.webContents.getURL()),
          BROWSER_PAGE_TITLE_LIMIT
        ),
        ...(page === undefined ? {} : { page })
      }
    } finally {
      if (pointerInstalled) {
        try {
          await frame.executeJavaScript(BROWSER_REMOVE_POINTER_SCRIPT)
        } catch {
          // Best-effort pointer cleanup after navigation or script failure.
        }
      }
    }
  }

  getVisibleTabId(): string | undefined {
    return this.visibleTabId
  }

  listPersistedTabs(): Array<{ tabId: string; url: string }> {
    this.assertNotDisposed()
    return [...this.tabs.entries()].map(([tabId, view]) => ({
      tabId,
      url: browserDisplayUrl(view.webContents.getURL())
    }))
  }

  async restorePersistedTabs(
    tabs: ReadonlyArray<{ tabId: string; url: string }>,
    visibleTabId: string
  ): Promise<void> {
    this.assertNotDisposed()
    const limited = tabs.slice(0, MAX_BROWSER_TABS)
    if (limited.length === 0) {
      const fallbackId = parseBrowserTabId(visibleTabId)
      this.ensureView(fallbackId)
      this.visibleTabId = fallbackId
      return
    }

    for (const tab of limited) {
      const tabId = parseBrowserTabId(tab.tabId)
      const view = this.ensureView(tabId)
      const url = tab.url.trim()
      if (url !== '') {
        try {
          await loadTabUrl(view, parseBrowserWebUrl(url))
        } catch {
          // Keep the restored tab shell even if the page fails to load.
        }
      }
      this.publishTabState(tabId, view)
    }

    try {
      this.visibleTabId = parseBrowserTabId(visibleTabId)
      if (!this.tabs.has(this.visibleTabId)) {
        this.visibleTabId = limited[0]!.tabId
      }
    } catch {
      this.visibleTabId = limited[0]!.tabId
    }
  }

  dispose(): void {
    if (this.disposed) {
      return
    }

    this.disposed = true
    for (const view of this.tabs.values()) {
      if (this.hostWindow !== undefined && !this.hostWindow.isDestroyed()) {
        this.hostWindow.contentView.removeChildView(view)
      }
      view.webContents.close()
    }

    this.tabs.clear()
    this.interactionSnapshots.clear()
    this.lastActionPageText.clear()
    this.visibleTabId = undefined
    this.hostWindow = undefined
    this.lastBounds = undefined
  }

  private assertNotDisposed(): void {
    if (this.disposed) {
      throw new Error('Browser view has been closed.')
    }
  }

  private detachVisibleView(): void {
    if (this.visibleTabId === undefined) {
      return
    }

    const view = this.tabs.get(this.visibleTabId)
    this.visibleTabId = undefined
    if (view === undefined) {
      return
    }

    view.setVisible(false)
    if (this.hostWindow !== undefined && !this.hostWindow.isDestroyed()) {
      this.hostWindow.contentView.removeChildView(view)
    }
  }

  private framesFor(view: BrowserPageView): BrowserFrame[] {
    const result: BrowserFrame[] = []
    const visit = (frame: BrowserFrame): void => {
      if (frame.isDestroyed()) {
        return
      }
      result.push(frame)
      for (const child of frame.frames) {
        visit(child)
      }
    }
    visit(view.webContents.mainFrame)
    return result
  }

  private assertVisibleTab(tabId: string): void {
    if (this.visibleTabId !== tabId || !this.tabs.has(tabId)) {
      throw new Error('current browser tab is not visible')
    }
  }

  private async settleAfterClick(
    tabId: string,
    previousText: string
  ): Promise<BrowserPageContent | undefined> {
    const deadline = Date.now() + BROWSER_CLICK_SETTLE_TIMEOUT_MS
    let observedText = previousText
    let lastChangeAt: number | undefined
    let latestPage: BrowserPageContent | undefined

    while (Date.now() < deadline) {
      try {
        latestPage = await this.readCurrentPage(tabId)
      } catch {
        return undefined
      }

      const now = Date.now()
      const currentText = latestPage.text
      if (currentText !== observedText) {
        observedText = currentText
        lastChangeAt = now
      } else if (
        lastChangeAt !== undefined &&
        now - lastChangeAt >= BROWSER_CLICK_SETTLE_QUIET_MS
      ) {
        return latestPage
      }

      await delay(Math.min(BROWSER_CLICK_SETTLE_QUIET_MS, deadline - now))
    }

    return latestPage
  }

  private ensureView(tabId: string): BrowserPageView {
    const existing = this.tabs.get(tabId)
    if (existing !== undefined) {
      return existing
    }

    if (this.tabs.size >= MAX_BROWSER_TABS) {
      throw new Error('Too many browser tabs.')
    }

    const view = this.createView({
      webPreferences: {
        session: this.session,
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: true
      }
    })

    view.webContents.setWindowOpenHandler((details) => {
      this.handleWindowOpen(details?.url)
      return { action: 'deny' }
    })
    view.webContents.on('will-navigate', denyUnsafeNavigation)
    view.webContents.on('will-redirect', denyUnsafeNavigation)
    const clearInteractionSnapshot = (): void => {
      this.interactionSnapshots.delete(tabId)
    }
    const onFrameNavigate = (event: BrowserNavigationEvent, url?: string): void => {
      denyUnsafeNavigation(event, url)
      clearInteractionSnapshot()
    }
    view.webContents.on('will-frame-navigate', onFrameNavigate)
    const publish = (): void => {
      this.publishTabState(tabId, view)
    }
    const onNavigated = (): void => {
      clearInteractionSnapshot()
      publish()
    }
    view.webContents.on('did-frame-navigate', clearInteractionSnapshot)
    view.webContents.on('did-navigate', onNavigated)
    view.webContents.on('did-navigate-in-page', onNavigated)
    view.webContents.on('page-title-updated', publish)
    this.tabs.set(tabId, view)
    return view
  }

  private handleWindowOpen(url: unknown): void {
    let safeUrl: string
    try {
      safeUrl = parseBrowserWebUrl(url)
    } catch {
      return
    }

    if (this.tabs.size >= MAX_BROWSER_TABS) {
      const fallbackId = this.visibleTabId
      if (fallbackId === undefined) {
        return
      }

      void this.ensureView(fallbackId)
        .webContents.loadURL(safeUrl)
        .catch(() => undefined)
      return
    }

    const tabId = this.createTabId()
    const view = this.ensureView(tabId)
    void view.webContents.loadURL(safeUrl).catch(() => undefined)
    if (
      this.visibleTabId !== undefined &&
      this.hostWindow !== undefined &&
      this.lastBounds !== undefined
    ) {
      this.show(this.hostWindow, this.lastBounds, tabId)
    }

    this.onTabState?.({
      tabId,
      url: browserDisplayUrl(safeUrl),
      title: titleFromUrl(safeUrl),
      canGoBack: false,
      canGoForward: false
    })
  }

  private createTabId(): string {
    let tabId = crypto.randomUUID()
    while (this.tabs.has(tabId)) {
      tabId = crypto.randomUUID()
    }

    return tabId
  }

  private publishTabState(tabId: string, view: BrowserPageView): void {
    this.onTabState?.(this.snapshot(tabId, view))
  }

  private snapshot(tabId: string, view: BrowserPageView): BrowserTabState {
    const rawUrl = view.webContents.getURL()
    const url = browserDisplayUrl(rawUrl)
    const pageTitle = view.webContents.getTitle().trim()
    const title =
      url === '' || pageTitle === '' || isBlankBrowserUrl(pageTitle) ? titleFromUrl(url) : pageTitle

    return {
      tabId,
      url,
      title,
      canGoBack: view.webContents.canGoBack(),
      canGoForward: view.webContents.canGoForward()
    }
  }
}
