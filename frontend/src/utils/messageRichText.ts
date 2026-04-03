import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'

const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  breaks: true,
})

type ParsedToken = ReturnType<typeof md.parse>[number]

export type MessageRenderNode =
  | MessageParagraphNode
  | MessageListNode
  | MessageQuoteNode
  | MessageCodeNode
  | MessageTableNode
  | MessageSectionNode
  | MessageDividerNode

export interface MessageParagraphNode {
  type: 'paragraph'
  html: string
  kind: 'lead' | 'body'
}

export interface MessageListNode {
  type: 'list'
  ordered: boolean
  items: MessageListItemNode[]
}

export interface MessageListItemNode {
  children: MessageRenderNode[]
}

export interface MessageQuoteNode {
  type: 'quote'
  children: MessageRenderNode[]
}

export interface MessageCodeNode {
  type: 'code'
  lang: string
  code: string
  highlightedHtml: string
}

export interface MessageTableNode {
  type: 'table'
  rows: string[][]
}

export interface MessageSectionNode {
  type: 'section'
  titleHtml: string
  level: number
  children: MessageRenderNode[]
}

export interface MessageDividerNode {
  type: 'divider'
}

interface HeadingMarkerNode {
  type: 'heading'
  html: string
  level: number
}

type ParseNode = MessageRenderNode | HeadingMarkerNode

function escapeHtml(str: string): string {
  return md.utils.escapeHtml(str)
}

function decorateInlineHtml(html: string): string {
  return html.replace(
    /\[(\d+)\]/g,
    '<span class="msg-citation-chip" title="来源 $1">$1</span>',
  )
}

function renderInlineToken(token?: ParsedToken): string {
  if (!token) return ''
  return decorateInlineHtml(md.renderer.render([token], md.options, {}))
}

function highlightCode(code: string, lang: string): string {
  const validLang = lang && hljs.getLanguage(lang) ? lang : ''
  return validLang
    ? hljs.highlight(code, { language: validLang, ignoreIllegals: true }).value
    : escapeHtml(code)
}

function parseTable(tokens: ParsedToken[], start: number): [MessageTableNode, number] {
  const rows: string[][] = []
  let i = start + 1

  while (i < tokens.length && tokens[i].type !== 'table_close') {
    const token = tokens[i]
    if (token.type === 'tr_open') {
      const row: string[] = []
      i += 1
      while (i < tokens.length && tokens[i].type !== 'tr_close') {
        const cellToken = tokens[i]
        if (cellToken.type === 'th_open' || cellToken.type === 'td_open') {
          const inlineToken = tokens[i + 1]
          row.push(renderInlineToken(inlineToken).trim())
          i += 3
          continue
        }
        i += 1
      }
      rows.push(row)
    }
    i += 1
  }

  return [{ type: 'table', rows }, i + 1]
}

function parseList(tokens: ParsedToken[], start: number): [MessageListNode, number] {
  const open = tokens[start]
  const closeType = open.type === 'bullet_list_open' ? 'bullet_list_close' : 'ordered_list_close'
  const items: MessageListItemNode[] = []
  let i = start + 1

  while (i < tokens.length && tokens[i].type !== closeType) {
    if (tokens[i].type === 'list_item_open') {
      const [children, next] = parseBlocks(tokens, i + 1, new Set(['list_item_close']))
      items.push({ children: groupSections(children) })
      i = next + 1
      continue
    }
    i += 1
  }

  return [
    {
      type: 'list',
      ordered: open.type === 'ordered_list_open',
      items,
    },
    i + 1,
  ]
}

function parseBlocks(
  tokens: ParsedToken[],
  start = 0,
  endTypes: Set<string> = new Set(),
): [ParseNode[], number] {
  const nodes: ParseNode[] = []
  let i = start

  while (i < tokens.length) {
    const token = tokens[i]
    if (endTypes.has(token.type)) break

    switch (token.type) {
      case 'heading_open': {
        const level = Number(token.tag.replace('h', '')) || 2
        nodes.push({
          type: 'heading',
          html: renderInlineToken(tokens[i + 1]),
          level,
        })
        i += 3
        break
      }
      case 'paragraph_open': {
        const html = renderInlineToken(tokens[i + 1]).trim()
        if (html) {
          nodes.push({
            type: 'paragraph',
            html,
            kind: 'body',
          })
        }
        i += 3
        break
      }
      case 'bullet_list_open':
      case 'ordered_list_open': {
        const [listNode, next] = parseList(tokens, i)
        nodes.push(listNode)
        i = next
        break
      }
      case 'blockquote_open': {
        const [children, next] = parseBlocks(tokens, i + 1, new Set(['blockquote_close']))
        nodes.push({ type: 'quote', children: groupSections(children) })
        i = next + 1
        break
      }
      case 'fence': {
        const lang = (token.info || '').trim().split(/\s+/)[0] || 'text'
        const code = token.content || ''
        nodes.push({
          type: 'code',
          lang,
          code,
          highlightedHtml: highlightCode(code, lang),
        })
        i += 1
        break
      }
      case 'table_open': {
        const [tableNode, next] = parseTable(tokens, i)
        nodes.push(tableNode)
        i = next
        break
      }
      case 'hr': {
        nodes.push({ type: 'divider' })
        i += 1
        break
      }
      case 'inline': {
        const html = renderInlineToken(token).trim()
        if (html) {
          nodes.push({
            type: 'paragraph',
            html,
            kind: 'body',
          })
        }
        i += 1
        break
      }
      default:
        i += 1
        break
    }
  }

  return [nodes, i]
}

function groupSections(nodes: ParseNode[]): MessageRenderNode[] {
  const result: MessageRenderNode[] = []
  let currentSection: MessageSectionNode | null = null

  const pushNode = (node: MessageRenderNode) => {
    if (currentSection) currentSection.children.push(node)
    else result.push(node)
  }

  for (const node of nodes) {
    if (node.type === 'heading') {
      currentSection = {
        type: 'section',
        titleHtml: node.html,
        level: node.level,
        children: [],
      }
      result.push(currentSection)
      continue
    }

    const nextNode =
      node.type === 'paragraph' && !currentSection && result.length === 0
        ? { ...node, kind: 'lead' as const }
        : node
    pushNode(nextNode)
  }

  return result
}

export function parseMessageRichText(content: string): MessageRenderNode[] {
  if (!content.trim()) return []
  const [nodes] = parseBlocks(md.parse(content, {}))
  return groupSections(nodes)
}
