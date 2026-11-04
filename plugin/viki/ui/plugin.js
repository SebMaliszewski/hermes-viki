/**
 * Viki — Rakuten Viki (UK) drama search with Hermes, on its own page (sidebar row "Viki" below Szachy).
 * Source: ~/.hermes/plugins/viki/ui/plugin.js → installed by ui/build.sh to ~/.hermes/desktop-plugins/viki/plugin.js
 * Each genre (combination) has ONE persistent Hermes chat 'Viki: <Gatunek>' (gateway JSON-RPC session.resume/
 * session.create/prompt.submit, like Szachy). Backend: /api/plugins/viki/* (genres, history, search, session, reset).
 */
import { host, PALETTE_AREA, ROUTES_AREA, SIDEBAR_NAV_AREA } from '@hermes/plugin-sdk'
import { useEffect, useRef, useState } from 'react'
import { jsx } from 'react/jsx-runtime'

// ── i18n: every panel UI string (labels, buttons, statuses, countries) per panel language ──
const C_EN = { kr: 'South Korea', cn: 'China', jp: 'Japan', tw: 'Taiwan', th: 'Thailand', ph: 'Philippines', hk: 'Hong Kong', us: 'USA', in: 'India', id: 'Indonesia', vn: 'Vietnam', my: 'Malaysia' }
const MESSAGES = {
  en: {
    name: 'Viki', desc: 'Search Rakuten Viki (UK) dramas with Hermes: genres, verified happy endings, per-genre history.',
    title: 'Viki — drama search', genres: 'Genres (several = all must match)', happyEnd: 'Happy ending required',
    yes: 'yes', no: 'no', minRating: 'Min. rating', count: 'Results', country: 'Country', any: 'Any',
    search: 'Search', more: 'Next 3', newSearch: 'New search', clear: 'Clear genre history',
    clearConfirm: n => `Clear the history of "${n}"? Already shown titles may appear again and a new chat will be started.`,
    history: 'History', noHistory: 'No searches yet.', error: 'Could not reach Hermes', pickGenre: 'Pick at least one genre.',
    empty: 'Pick genres and press Search.', shown: (s, r) => `${s} shown · ${r} rejected`, outLang: 'Output language',
    uiLang: 'Panel language', selecting: 'Picking titles and verifying endings… (first search in a genre can take 1–3 min)',
    translating: 'Hermes is translating descriptions…', happyTag: 'happy end', minTag: 'min', countries: C_EN
  },
  pl: {
    name: 'Viki', desc: 'Wyszukiwarka dram Rakuten Viki (UK) z Hermes: gatunki, zweryfikowany happy-end, historia per gatunek.',
    title: 'Viki — wyszukiwarka dram', genres: 'Gatunki (kilka = muszą pasować wszystkie)', happyEnd: 'Wymagany happy-end',
    yes: 'tak', no: 'nie', minRating: 'Min. ocena', count: 'Wyników', country: 'Kraj', any: 'Dowolny',
    search: 'Wyszukaj', more: 'Kolejne 3', newSearch: 'Nowe wyszukiwanie', clear: 'Wyczyść historię gatunku',
    clearConfirm: n => `Wyczyścić historię „${n}”? Pokazane tytuły mogą wrócić, zostanie założony nowy czat.`,
    history: 'Historia', noHistory: 'Brak wyszukiwań.', error: 'Nie udało się połączyć z Hermes', pickGenre: 'Wybierz co najmniej jeden gatunek.',
    empty: 'Wybierz gatunki i naciśnij Wyszukaj.', shown: (s, r) => `pokazane ${s} · odrzucone ${r}`, outLang: 'Język wyników',
    uiLang: 'Język panelu', selecting: 'Wybieram tytuły i sprawdzam zakończenia… (pierwsze wyszukiwanie w gatunku może potrwać 1–3 min)',
    translating: 'Hermes tłumaczy opisy…', happyTag: 'happy-end', minTag: 'min',
    countries: { kr: 'Korea Płd.', cn: 'Chiny', jp: 'Japonia', tw: 'Tajwan', th: 'Tajlandia', ph: 'Filipiny', hk: 'Hongkong', us: 'USA', in: 'Indie', id: 'Indonezja', vn: 'Wietnam', my: 'Malezja' }
  },
  ja: {
    name: 'Viki', desc: 'Hermes と Rakuten Viki（英国）のドラマを検索：ジャンル、ハッピーエンド確認、ジャンル別履歴。',
    title: 'Viki — ドラマ検索', genres: 'ジャンル（複数＝すべて一致）', happyEnd: 'ハッピーエンド必須',
    yes: 'はい', no: 'いいえ', minRating: '最低評価', count: '件数', country: '国', any: 'すべて',
    search: '検索', more: '次の3件', newSearch: '新しい検索', clear: 'ジャンル履歴を消去',
    clearConfirm: n => `「${n}」の履歴を消去しますか？表示済みの作品が再表示され、新しいチャットが作成されます。`,
    history: '履歴', noHistory: '検索履歴はありません。', error: 'Hermes に接続できませんでした', pickGenre: 'ジャンルを1つ以上選んでください。',
    empty: 'ジャンルを選んで「検索」を押してください。', shown: (s, r) => `表示 ${s} · 除外 ${r}`, outLang: '出力言語',
    uiLang: 'パネル言語', selecting: '作品を選び、結末を確認しています…（初回は1〜3分かかることがあります）',
    translating: 'Hermes があらすじを翻訳しています…', happyTag: 'ハッピーエンド', minTag: '最低',
    countries: { kr: '韓国', cn: '中国', jp: '日本', tw: '台湾', th: 'タイ', ph: 'フィリピン', hk: '香港', us: 'アメリカ', in: 'インド', id: 'インドネシア', vn: 'ベトナム', my: 'マレーシア' }
  },
  zh: {
    name: 'Viki', desc: '与 Hermes 一起搜索 Rakuten Viki（英国）剧集：类型、已验证的大团圆结局、按类型记录历史。',
    title: 'Viki — 剧集搜索', genres: '类型（多选＝须全部符合）', happyEnd: '必须大团圆结局',
    yes: '是', no: '否', minRating: '最低评分', count: '结果数', country: '国家', any: '全部',
    search: '搜索', more: '下3部', newSearch: '新搜索', clear: '清除该类型历史',
    clearConfirm: n => `清除“${n}”的历史？已显示的剧集可能再次出现，并将新建聊天。`,
    history: '历史', noHistory: '暂无搜索记录。', error: '无法连接 Hermes', pickGenre: '请至少选择一个类型。',
    empty: '选择类型后点击“搜索”。', shown: (s, r) => `已显示 ${s} · 已排除 ${r}`, outLang: '输出语言',
    uiLang: '面板语言', selecting: '正在挑选剧集并核实结局…（首次搜索可能需要1–3分钟）',
    translating: 'Hermes 正在翻译简介…', happyTag: '大团圆', minTag: '最低',
    countries: { kr: '韩国', cn: '中国', jp: '日本', tw: '台湾', th: '泰国', ph: '菲律宾', hk: '香港', us: '美国', in: '印度', id: '印度尼西亚', vn: '越南', my: '马来西亚' }
  }
}
// Rendered-result fallback text (by OUTPUT language)
const NO_RESULTS = { en: 'No results matching the criteria.', pl: 'Brak wyników spełniających kryteria.', ja: '条件に合う作品はありません。', zh: '没有符合条件的结果。' }
const UI_LANGS = [['en', 'EN'], ['pl', 'PL'], ['ja', 'JP'], ['zh', 'ZH']]
const UI_KEY = 'viki.uiLang'
const DATE_LOCALE = { en: 'en-GB', pl: 'pl-PL', ja: 'ja-JP', zh: 'zh-CN' }
const loc = () => { try { const v = globalThis.localStorage?.getItem(UI_KEY); return MESSAGES[v] ? v : 'en' } catch { return 'en' } }
const T = () => MESSAGES[loc()]
function isDark() {
  const d = globalThis.document; if (!d) return true
  const h = d.documentElement, bd = d.body, cls = (h.className + ' ' + (bd?.className || '')).toLowerCase()
  if (/\bdark\b/.test(cls) || h.dataset.theme === 'dark' || h.dataset.mode === 'dark') return true
  if (/\blight\b/.test(cls) || h.dataset.theme === 'light' || h.dataset.mode === 'light') return false
  const c = getComputedStyle(bd || h).backgroundColor.match(/\d+/g)
  return c ? (+c[0] + +c[1] + +c[2]) / 3 < 128 : true
}
const AGENT_PROFILE = 'default'
const ROUTE = '/viki'
const PREFIX = '[Viki-panel]'
const OUT_LANGS = [['pl', 'PL'], ['en', 'EN'], ['ja', 'JP'], ['zh', 'ZH']]
const LANG_KEY = 'viki.outLang'
const readLang = () => { try { return globalThis.localStorage?.getItem(LANG_KEY) || 'en' } catch { return 'en' } }
const writeLang = v => { try { globalThis.localStorage?.setItem(LANG_KEY, v) } catch { /* ignore */ } }
const sleep = ms => new Promise(r => setTimeout(r, ms))
let rest = null
const esc = t => String(t ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c])
const safeUrl = u => /^https?:\/\//i.test(u) ? u : '#'
const msgText = m => { const c = m?.display_content ?? m?.content ?? m?.text; if (typeof c === 'string') return c; if (Array.isArray(c)) return c.map(x => typeof x === 'string' ? x : (x?.text || '')).join(''); return '' }

/** Tiny markdown → HTML (headings, images, links, bold, italics, code, lists, paragraphs). */
export function md(src) {
  const inline = s => esc(s)
    .replace(/!\[([^\]]*)\]\(([^)\s]+)\)/g, (_, a, u) => `<img class="vk-img" alt="${a}" src="${safeUrl(u.replace(/&amp;/g, '&'))}">`)
    .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_, t, u) => `<a href="${safeUrl(u.replace(/&amp;/g, '&'))}" target="_blank" rel="noopener noreferrer">${t}</a>`)
    .replace(/`([^`]+)`/g, '<span class="vk-badge">$1</span>')
    .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>').replace(/(^|\W)\*([^*]+)\*(?=\W|$)/g, '$1<i>$2</i>')
  const out = []; let list = false
  for (const raw of String(src || '').replace(/<!--[\s\S]*?-->/g, '').split('\n')) {
    const l = raw.trimEnd(); let m
    if (list && !/^\s*[-*] /.test(l)) { out.push('</ul>'); list = false }
    if (!l.trim()) continue
    if ((m = l.match(/^(#{1,4})\s+(.*)$/))) out.push(`<h${m[1].length + 1} class="vk-h${m[1].length}">${inline(m[2])}</h${m[1].length + 1}>`)
    else if ((m = l.match(/^\s*[-*] (.*)$/))) { if (!list) { out.push('<ul>'); list = true } out.push(`<li>${inline(m[1])}</li>`) }
    else if (/^-{3,}$/.test(l.trim())) out.push('<hr>')
    else out.push(`<p>${inline(l)}</p>`)
  }
  if (list) out.push('</ul>')
  return out.join('')
}

const CSS = `
.vk-root{display:flex;height:100%;min-height:0;gap:12px;padding:12px;box-sizing:border-box;font-size:14px}
.vk-dark{--vk-bg:#1d1f23;--vk-card:#26292e;--vk-fg:#e6e6e6;--vk-mute:#9aa0a6;--vk-bd:#3a3e45;--vk-acc:#5ab0ff;--vk-in:#2b2f35;color-scheme:dark}
.vk-light{--vk-bg:#fafafa;--vk-card:#fff;--vk-fg:#1f2328;--vk-mute:#656d76;--vk-bd:#d0d7de;--vk-acc:#0969da;--vk-in:#fff;color-scheme:light}
.vk-root{color:var(--vk-fg)}
.vk-side{width:230px;flex:0 0 230px;display:flex;flex-direction:column;min-height:0;border:1px solid var(--vk-bd);border-radius:8px;background:var(--vk-card)}
.vk-side h3{margin:0;padding:10px 12px;font-size:13px;border-bottom:1px solid var(--vk-bd)}
.vk-hist{overflow:auto;flex:1;min-height:0}
.vk-hi{padding:8px 12px;cursor:pointer;border-bottom:1px solid var(--vk-bd)}
.vk-hi:hover,.vk-hi.on{background:var(--vk-in)}
.vk-hi small{display:block;color:var(--vk-mute)}
.vk-main{flex:1;display:flex;flex-direction:column;min-width:0;min-height:0}
.vk-top{flex:0 0 auto;display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:8px}
.vk-top h2{margin:0 auto 0 0;font-size:16px}
.vk-uil{color:var(--vk-mute);font-size:12px;margin-left:8px}
.vk-ui{background:var(--vk-in);color:var(--vk-fg);border:1px solid var(--vk-bd);border-radius:6px;padding:4px 6px;font:inherit}
.vk-ui option{background:var(--vk-in);color:var(--vk-fg)}
.vk-btn{background:var(--vk-in);color:var(--vk-fg);border:1px solid var(--vk-bd);border-radius:6px;padding:5px 12px;cursor:pointer;font:inherit}
.vk-btn.pri{background:var(--vk-acc);border-color:var(--vk-acc);color:#fff}
.vk-btn:disabled{opacity:.5;cursor:default}
.vk-form{flex:0 0 auto;border:1px solid var(--vk-bd);border-radius:8px;padding:10px 12px;background:var(--vk-card);margin-bottom:8px}
.vk-form label{color:var(--vk-mute);font-size:12px;display:block;margin:6px 0 4px}
.vk-gl{display:flex;flex-wrap:wrap;gap:4px;max-height:110px;overflow:auto}
.vk-chip{border:1px solid var(--vk-bd);border-radius:12px;padding:2px 9px;cursor:pointer;user-select:none;background:var(--vk-in);font-size:12px}
.vk-chip.on{background:var(--vk-acc);border-color:var(--vk-acc);color:#fff}
.vk-row{display:flex;gap:14px;flex-wrap:wrap;align-items:flex-end}
.vk-form select,.vk-form input{background:var(--vk-in);color:var(--vk-fg);border:1px solid var(--vk-bd);border-radius:6px;padding:4px 6px;font:inherit}
.vk-form option{background:var(--vk-in);color:var(--vk-fg)}
.vk-res{flex:1;min-height:0;overflow:auto;border:1px solid var(--vk-bd);border-radius:8px;padding:4px 16px 16px;background:var(--vk-card)}
.vk-res img.vk-img{max-width:100%;width:560px;border-radius:8px;display:block;margin:6px 0}
.vk-res a{color:var(--vk-acc)}
.vk-res .vk-h2{font-size:17px;margin:16px 0 6px}.vk-res .vk-h3{font-size:15px;margin:18px 0 4px}
.vk-res p{margin:4px 0;line-height:1.45}
.vk-badge{background:#2e7d32;color:#fff;border-radius:10px;padding:1px 8px;font-size:12px;white-space:nowrap}
.vk-q{color:var(--vk-mute);font-size:12px;border-top:1px dashed var(--vk-bd);margin-top:14px;padding-top:8px}
.vk-info{color:var(--vk-mute);padding:12px 0}

.vk-dark select,.vk-dark option,.vk-dark optgroup,.vk-dark input{color-scheme:dark}
.vk-light select,.vk-light option,.vk-light optgroup,.vk-light input{color-scheme:light}
.vk-root select{background-color:var(--vk-in);color:var(--vk-fg);border:1px solid var(--vk-bd);border-radius:6px;padding:4px 6px;font:inherit}
.vk-root select option,.vk-root select optgroup{background-color:var(--vk-in);color:var(--vk-fg)}
.vk-root select option:checked{background-color:var(--vk-acc);color:#fff}
.vk-root select:focus{outline:1px solid var(--vk-acc)}
`
function injectStyle() {
  const d = globalThis.document; if (!d || d.getElementById('vk-style')) return
  const el = d.createElement('style'); el.id = 'vk-style'; el.textContent = CSS; d.head.appendChild(el)
}

class VikiPanel {
  constructor(root) {
    this.root = root; this.genres = []; this.countries = {}; this.hist = []; this.sel = new Set(['romance'])
    this.he = null; this.minRating = ''; this.count = 3; this.country = ''; this.lang = readLang()
    this.cur = null; this.runtime = ''; this.items = []; this.live = null; this.running = false; this.info = ''
    this.view = 'form'; this.unsubs = []; this.disposed = false
    for (const type of ['message.start', 'message.delta', 'message.complete', 'error']) {
      try { const u = host.onEvent?.(type, ev => this.onEvent(type, ev)); if (typeof u === 'function') this.unsubs.push(u) } catch { /* old shell */ }
    }
    this.build(); void this.load()
  }
  async load() {
    try { const g = await rest('/genres'); this.genres = g.genres || []; this.countries = g.countries || {} } catch { this.info = T().error }
    await this.loadHist(); this.renderForm(); this.render()
  }
  async loadHist() { try { this.hist = (await rest('/history')).items || [] } catch { this.hist = [] } this.renderHist() }
  build() {
    this.root.innerHTML = `<div class="vk-root"><div class="vk-side"><h3 class="vk-ht"></h3><div class="vk-hist"></div></div>
<div class="vk-main"><div class="vk-top"><h2 class="vk-title"></h2><button class="vk-btn vk-more"></button><button class="vk-btn vk-new"></button><button class="vk-btn vk-clear"></button><label class="vk-uil"></label><select class="vk-ui"></select></div>
<div class="vk-form"></div><div class="vk-res"></div></div></div>`
    const q = s => this.root.querySelector(s)
    this.box = q('.vk-root'); this.histEl = q('.vk-hist'); this.formEl = q('.vk-form'); this.resEl = q('.vk-res')
    this.bMore = q('.vk-more'); this.bNew = q('.vk-new'); this.bClear = q('.vk-clear')
    this.bMore.onclick = () => this.cur && this.search(true)
    this.bNew.onclick = () => { this.view = 'form'; this.render() }
    this.bClear.onclick = () => this.clear()
    this.uiSel = q('.vk-ui')
    this.uiSel.onchange = e => { try { globalThis.localStorage?.setItem(UI_KEY, e.target.value) } catch { /* ignore */ } this.renderForm(); this.renderHist(); this.render() }
    this.texts()
  }
  texts() {
    const m = T(), dark = isDark()
    this.box.classList.toggle('vk-dark', dark); this.box.classList.toggle('vk-light', !dark)
    this.root.querySelector('.vk-ht').textContent = m.history
    this.root.querySelector('.vk-title').textContent = this.cur ? `Viki: ${this.gname(this.cur.key)}` : m.title
    this.bMore.textContent = m.more; this.bNew.textContent = m.newSearch; this.bClear.textContent = m.clear
    this.root.querySelector('.vk-uil').textContent = m.uiLang
    this.uiSel.innerHTML = UI_LANGS.map(([k, v]) => `<option value="${k}"${k === loc() ? ' selected' : ''}>${v}</option>`).join('')
  }
  gname(key) {
    const l = loc()
    return String(key || '').split('+').map(k => { const g = this.genres.find(x => x.key === k); return g ? (g.names?.[l] || g.name_en) : k }).join(' + ')
  }
  heDefault() { return [...this.sel].some(k => this.genres.find(g => g.key === k)?.happy_end_default) }
  renderForm() {
    const m = T(), he = this.he ?? this.heDefault()
    const name = g => g.names?.[loc()] || g.name_en
    this.formEl.innerHTML = `<label>${esc(m.genres)}</label><div class="vk-gl">${[...this.genres].sort((a, b) => name(a).localeCompare(name(b), DATE_LOCALE[loc()])).map(g =>
      `<span class="vk-chip${this.sel.has(g.key) ? ' on' : ''}" data-k="${esc(g.key)}">${esc(name(g))}</span>`).join('')}</div>
<div class="vk-row"><div><label>${esc(m.happyEnd)}</label><select class="vk-he"><option value="1"${he ? ' selected' : ''}>${m.yes}</option><option value="0"${he ? '' : ' selected'}>${m.no}</option></select></div>
<div><label>${esc(m.minRating)}</label><input class="vk-mr" type="number" min="0" max="10" step="0.1" style="width:70px" value="${esc(this.minRating)}"></div>
<div><label>${esc(m.count)}</label><select class="vk-cnt">${[1, 2, 3].map(n => `<option${n === this.count ? ' selected' : ''}>${n}</option>`).join('')}</select></div>
<div><label>${esc(m.country)}</label><select class="vk-cc"><option value="">${esc(m.any)}</option>${Object.keys(this.countries).map(k => [k, m.countries[k] || C_EN[k] || k]).map(([k, v]) =>
      `<option value="${k}"${k === this.country ? ' selected' : ''}>${esc(v)}</option>`).join('')}</select></div>
<div><label>${esc(m.outLang)}</label><select class="vk-lang">${OUT_LANGS.map(([k, v]) => `<option value="${k}"${k === this.lang ? ' selected' : ''}>${v}</option>`).join('')}</select></div>
<div><button class="vk-btn pri vk-go">${esc(m.search)}</button></div></div>`
    this.formEl.querySelectorAll('.vk-chip').forEach(c => c.onclick = () => {
      const k = c.dataset.k; this.sel.has(k) ? this.sel.delete(k) : this.sel.add(k); this.he = null; this.renderForm()
    })
    const q = s => this.formEl.querySelector(s)
    q('.vk-he').onchange = e => { this.he = e.target.value === '1' }
    q('.vk-mr').onchange = e => { this.minRating = e.target.value }
    q('.vk-cnt').onchange = e => { this.count = +e.target.value }
    q('.vk-cc').onchange = e => { this.country = e.target.value }
    q('.vk-lang').onchange = e => { this.lang = e.target.value; writeLang(this.lang) }
    q('.vk-go').onclick = () => {
      if (!this.sel.size) { this.info = m.pickGenre; this.render(); return }
      this.cur = null; void this.search(false)
    }
  }
  renderHist() {
    const m = T()
    this.histEl.innerHTML = this.hist.length ? this.hist.map(h => {
      const last = h.searches?.[h.searches.length - 1]
      const when = h.updated ? new Date(h.updated * 1000).toLocaleString(DATE_LOCALE[loc()], { dateStyle: 'short', timeStyle: 'short' }) : ''
      return `<div class="vk-hi${this.cur?.key === h.key ? ' on' : ''}" data-k="${esc(h.key)}"><b>Viki: ${esc(this.gname(h.key))}</b><small>${esc(m.shown(h.shown, h.rejected))}</small><small>${esc(when)}${last?.happy_end ? ' · ' + m.happyTag : ''}</small></div>`
    }).join('') : `<div class="vk-info" style="padding:12px">${esc(m.noHistory)}</div>`
    this.histEl.querySelectorAll('.vk-hi').forEach(el => el.onclick = () => this.open(this.hist.find(h => h.key === el.dataset.k)))
  }
  /** Restore a genre from history: show its stored rendered searches; 'Next 3' continues the same genre session. */
  open(h) {
    if (!h) return
    const last = h.searches?.[h.searches.length - 1] || {}
    this.cur = { key: h.key, name_pl: h.name_pl, sid: h.session_id, settings: last }
    this.sel = new Set(h.key.split('+')); this.he = last.happy_end ?? null; this.minRating = last.min_rating ?? ''; this.country = last.country || ''
    this.runtime = ''; this.view = 'results'; this.info = ''; this.running = false
    this.items = (h.searches || []).filter(e => e.markdown).map(e => ({ label: this.label(h.key, e), md: e.markdown }))
    this.renderHist(); this.render()
  }
  label(key, e) {
    const m = T()
    const bits = [this.gname(key), e.happy_end ? m.happyTag : '', e.min_rating ? `${m.minTag} ${e.min_rating}` : '', e.country ? (m.countries[e.country] || e.country) : '', (e.lang || 'pl').toUpperCase().replace('JA', 'JP')]
    const when = e.at ? new Date(e.at * 1000).toLocaleString(DATE_LOCALE[loc()], { dateStyle: 'short', timeStyle: 'short' }) : ''
    return `${bits.filter(Boolean).join(' · ')} — ${when}`
  }
  async ensure() {
    if (this.runtime) return this.runtime
    let res = null
    if (this.cur.sid) { try { res = await host.request('session.resume', { session_id: this.cur.sid, profile: AGENT_PROFILE }, 180_000) } catch { res = null } }
    let fresh = false
    if (!res?.session_id) { res = await host.request('session.create', { profile: AGENT_PROFILE }); fresh = true }
    this.runtime = res.session_id
    const stored = res.stored_session_id || res.info?.stored_session_id || this.cur.sid || res.session_id
    if (stored !== this.cur.sid) { this.cur.sid = stored; try { await rest('/session', { method: 'POST', body: { key: this.cur.key, session_id: stored } }) } catch { /* ignore */ } }
    if (fresh) this.retitle()
    return this.runtime
  }
  retitle() { const t = `Viki: ${this.gname(this.cur.key)}`, s = this.runtime; for (const ms of [0, 4000, 15000]) setTimeout(() => host.request('session.title', { session_id: s, title: t }).catch(() => {}), ms) }
  /** Economy flow: backend selects + verifies titles (job), Hermes only translates missing descriptions (no tools). */
  async search(more) {
    const m = T()
    if (this.running) return
    const body = more && this.cur ? { key: this.cur.key, more: true, lang: this.lang }
      : { genres: [...this.sel], happy_end: this.he ?? this.heDefault(), min_rating: this.minRating, count: this.count, country: this.country, more: false, lang: this.lang }
    this.running = true; this.info = m.selecting; this.view = 'results'; this.render()
    try {
      const { job_id } = await rest('/search', { method: 'POST', body })
      let j = null
      for (let k = 0; k < 400 && !this.disposed; k++) { await sleep(1500); j = await rest(`/job?id=${job_id}`); if (j.status !== 'running') break }
      if (j?.status !== 'done') throw new Error(j?.error || 'timeout')
      const r = j.result
      if (!this.cur || this.cur.key !== r.key) { this.cur = { key: r.key, name_pl: r.name_pl, sid: r.session_id }; this.runtime = ''; this.items = [] }
      this.cur.settings = r.settings; this.texts()
      let text = ''
      if (!r.ids.length) {
        this.items.push({ label: this.label(r.key, r.settings), md: `${r.header}\n\n${NO_RESULTS[r.lang] || NO_RESULTS.en}` })
        this.running = false; this.info = ''; this.render(); return
      }
      if (r.prompt) {
        this.info = m.translating; this.render()
        await this.ensure()
        const done = new Promise(res => { this.waiter = res })
        try { await host.request('prompt.submit', { session_id: this.runtime, text: r.prompt }) }
        catch { this.runtime = ''; await this.ensure(); await host.request('prompt.submit', { session_id: this.runtime, text: r.prompt }) }
        text = await Promise.race([done, sleep(300_000).then(() => '')])
      }
      const out = await rest('/render', { method: 'POST', body: { key: r.key, ids: r.ids, header: r.header, text, happy_end: r.settings.happy_end, search_at: r.search_at, lang: r.lang } })
      this.items.push({ label: this.label(r.key, r.settings), md: out.markdown })
      this.info = ''
    } catch (e) { this.info = m.error + (e?.message ? `: ${e.message}` : '') }
    this.running = false; this.waiter = null; this.render(); void this.loadHist()
  }
  async clear() {
    const m = T(); const key = this.cur?.key || [...this.sel].sort().join('+'); if (!key) return
    const name = this.gname(key)
    if (!globalThis.confirm?.(m.clearConfirm(name))) return
    try {
      const r = await rest('/reset', { method: 'POST', body: { key } })
      if (r.old_session_id) host.request('session.archive', { session_id: r.old_session_id, archived: true }).catch(() => {})
    } catch { /* ignore */ }
    this.cur = null; this.runtime = ''; this.items = []; this.view = 'form'; await this.loadHist(); this.render()
  }
  mine(ev) { const id = ev?.session_id; return !!id && !!this.cur && (id === this.runtime || id === this.cur.sid) }
  onEvent(type, ev) {
    if (this.disposed || !this.waiter || !this.mine(ev)) return
    const t = ev?.payload?.text
    if (type === 'message.start') this.liveText = ''
    else if (type === 'message.delta') this.liveText = (this.liveText || '') + (typeof t === 'string' ? t : '')
    else {
      const fin = typeof t === 'string' && t ? t : (typeof ev?.payload?.rendered === 'string' ? ev.payload.rendered : this.liveText || '')
      if (fin.trim() || type === 'error') { const w = this.waiter; this.waiter = null; w(fin) }
    }
  }
  render() {
    if (this.disposed) return
    const m = T(); this.texts()
    this.formEl.style.display = this.view === 'form' ? '' : 'none'
    this.bMore.style.display = this.bNew.style.display = this.view === 'results' && this.cur ? '' : 'none'
    this.bMore.disabled = this.running
    const html = this.items.map(i => `<div class="vk-q">🔎 ${esc(i.label)}</div><div class="vk-a">${md(i.md)}</div>`).join('')
    const info = this.info || (!this.items.length ? m.empty : '')
    this.resEl.innerHTML = html + (info ? `<div class="vk-info">${esc(info)}</div>` : '')
    this.resEl.scrollTop = this.resEl.scrollHeight
  }
  dispose() { this.disposed = true; for (const u of this.unsubs) try { u() } catch { /* ignore */ } this.unsubs = [] }
}

function Page() {
  const box = useRef(null)
  const [, setTick] = useState(0)
  useEffect(() => {
    if (!box.current || !rest) return
    const p = new VikiPanel(box.current)
    let mo = null
    if (typeof MutationObserver === 'function') {
      mo = new MutationObserver(() => { p.renderForm(); p.renderHist(); p.render(); setTick(x => x + 1) })
      mo.observe(document.documentElement, { attributes: true, attributeFilter: ['lang', 'class', 'data-theme', 'data-mode', 'style'] })
      if (document.body) mo.observe(document.body, { attributes: true, attributeFilter: ['class', 'data-theme', 'data-mode'] })
    }
    return () => { mo?.disconnect(); p.dispose() }
  }, [])
  injectStyle()
  return jsx('div', { ref: box, style: { height: '100%', minHeight: 0, display: 'flex', flexDirection: 'column' } })
}

export default {
  id: 'viki', // must match the Python plugin name (ctx.rest → /api/plugins/viki/)
  name: MESSAGES[loc()].name,
  description: MESSAGES[loc()].desc,
  defaultEnabled: true,
  register(ctx) {
    rest = (path, opts) => ctx.rest(path, opts)
    ctx.register({ id: 'page', area: ROUTES_AREA, data: { path: ROUTE }, render: () => jsx(Page, {}) })
    // Sidebar row directly below Szachy (order 89).
    ctx.register({ id: 'nav', area: SIDEBAR_NAV_AREA, order: 90, data: { path: ROUTE, label: 'Viki', codicon: 'device-camera-video' } })
    ctx.register({ id: 'open', area: PALETTE_AREA, data: { id: 'viki.open', label: 'Open Viki', keywords: ['viki', 'drama', 'hermes'], run: () => host.navigate(ROUTE) } })
    ctx.onDispose(() => { rest = null })
  }
}
