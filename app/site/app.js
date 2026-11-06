/* 诗笺 · static poetry reader. Data: github.com/wujinpai/chinese-classics. */
(() => {
'use strict';
const $ = (s, r = document) => r.querySelector(s);
const app = $('#app');
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const cache = new Map();
function fetchRetry(u, tries = 3) {
  const once = () => { const ac = new AbortController(); const t = setTimeout(() => ac.abort(), 15000);
    return fetch(u, { signal: ac.signal }).then(r => { clearTimeout(t); if (!r.ok) throw new Error(r.status + ' ' + u); return r; }, e => { clearTimeout(t); throw e; }); };
  return once().catch(e => tries > 1 ? new Promise(r => setTimeout(r, 400 * (4 - tries))).then(() => fetchRetry(u, tries - 1)) : Promise.reject(e));
}
const DV = 'v=16';
function getJSON(u) {
  if (u.startsWith('/data/')) u += (u.includes('?') ? '&' : '?') + DV;
  if (!cache.has(u)) cache.set(u, fetchRetry(u).then(r => r.json()).catch(e => { cache.delete(u); throw e; }));
  return cache.get(u);
}
let M, POP, AUTH;
const meta = () => M ? Promise.resolve(M) : getJSON('/data/meta.json').then(m => (M = m));
const b64u = x => { const b = atob(x); const u = new Uint8Array(b.length); for (let i = 0; i < b.length; i++) u[i] = b.charCodeAt(i); return u; };
let DYN = null, DYNL = [];  // 每篇自己的朝代（作者归一后），合集标签只作后备
const pop = () => POP ? Promise.resolve(POP) : getJSON('/data/pop.json').then(o => { if (o.db) { DYN = b64u(o.db); DYNL = o.dl; } return (POP = b64u(o.b)); });
const dynOf = id => (DYN && DYN[id]) ? DYNL[DYN[id]] : (collOf(id) || {}).dyn;
const authors = () => AUTH ? Promise.resolve(AUTH) : getJSON('/data/authors.json').then(a => (AUTH = a));
const segsOf = c => [[c.start, c.mc != null ? c.mc : c.count], ...(c.ext || [])];  // 合集可有多段 id（并入的补遗篇目在追加段）
const collOf = id => M.colls.find(c => segsOf(c).some(([s, n]) => id >= s && id < s + n));
const segOf = (c, id) => segsOf(c).find(([s, n]) => id >= s && id < s + n);
const genresOf = c => { const o = []; const ix = {}; for (const [g, s, n] of (c.genres || [])) { if (!(g in ix)) { ix[g] = o.length; o.push([g, [], 0]); } const e = o[ix[g]]; e[1].push([s, n]); e[2] += n; } return o; };
const OLD_BUYI = [790000, 868000];  // 旧「历代补遗」id 段，已并入各合集，用 moved.json 跳转
const movedId = async id => { try { const mg = await getJSON('/data/merged.json?v=1'); if (mg[id]) return mg[id]; } catch (e) {} if (id < OLD_BUYI[0] || id >= OLD_BUYI[1]) return 0; try { const mv = await getJSON('/data/moved.json'); return mv[id - OLD_BUYI[0]] || 0; } catch (e) { return 0; } };
const collBy = code => M.colls.find(c => c.code === code);
const grp = d => (d === '唐' || d === '五代') ? '唐' : d;
async function stub(id) { const k = Math.floor(id / M.CH); const a = await getJSON(`/data/s/${k}.json`); return a[id - k * M.CH]; }
async function poem(id) { const k = Math.floor(id / M.PS); const a = await getJSON(`/data/p/${k}.json`); return a[id - k * M.PS]; }
const prefetchPoem = id => { if (M && id >= 0) poem(id).catch(() => {}); };
const idle = f => (window.requestIdleCallback || (cb => setTimeout(cb, 600)))(f);
function toast(t) { const el = $('#toast'); el.textContent = t; el.classList.add('show'); clearTimeout(toast._t); toast._t = setTimeout(() => el.classList.remove('show'), 2600); }
function setTitle(t) { document.title = t ? `${t} · 诗笺` : '诗笺 · 古典诗文阅读'; }
const fmt = n => n >= 10000 ? (n / 10000).toFixed(n >= 100000 ? 0 : 1) + ' 万' : String(n);
const favs = () => { try { return JSON.parse(localStorage.getItem('shici.fav') || '[]'); } catch (e) { return []; } };
const setFavs = a => localStorage.setItem('shici.fav', JSON.stringify(a));

/* ---------- crc32 + postings decode (matches tools/index.py) ---------- */
const CRC = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
const enc8 = new TextEncoder();
function crc32(str) { const b = enc8.encode(str); let c = 0xFFFFFFFF; for (let i = 0; i < b.length; i++) c = CRC[(c ^ b[i]) & 255] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; }
const B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';
const B64I = new Int16Array(128).fill(-1); for (let i = 0; i < 64; i++) B64I[B64.charCodeAt(i)] = i;
function decode(s) {
  const out = []; let v = 0, sh = 0, acc = 0;
  for (let i = 0; i < s.length; i++) { const d = B64I[s.charCodeAt(i)]; v |= (d & 31) << sh; if (d & 32) sh += 5; else { acc += v; out.push(acc); v = 0; sh = 0; } }
  return out;
}
async function postings(tok) { const sh = crc32(tok) % 2048; const o = await getJSON(`/data/i/${sh}.json`); return o[tok] ? decode(o[tok]) : []; }
function inter(a, b) { const o = []; let i = 0, j = 0; while (i < a.length && j < b.length) { if (a[i] === b[j]) { o.push(a[i]); i++; j++; } else if (a[i] < b[j]) i++; else j++; } return o; }
const CJK = /[\u3400-\u9fff]/;
const cjkOnly = s => (s.match(/[\u3400-\u9fff]/g) || []).join('');

/* ---------- card rendering ---------- */
function hl(text, terms) {
  let h = esc(text);
  for (const t of terms || []) if (t && t.length) h = h.split(esc(t)).join(`<mark>${esc(t)}</mark>`);
  return h;
}
function cardHTML(id, s, terms, snip) {
  if (!s) return '';
  const c = collOf(id); const [t, a, f, g, sel] = s;
  const meta2 = [c ? c.name : '', g && g !== c?.name ? g : ''].filter(Boolean).map(x => `<span>${esc(x)}</span>`).join('');
  return `<a class="card" href="/p/${id}">${sel ? `<span class="stamp">${esc(sel.replace('三百首', '三百'))}</span>` : ''}
    <div class="t">${hl(t, terms)}</div><div class="a">${hl(a, terms)}${c ? ' · ' + esc(dynOf(id)) : ''}</div>
    <div class="f snip" data-id="${id}">${hl(snip || f, terms)}</div><div class="m">${meta2}</div></a>`;
}
const skel = n => Array.from({ length: n }, () => '<div class="skel"></div>').join('');

/* ---------- views ---------- */
const DAY = Math.floor((Date.now() - new Date().getTimezoneOffset() * 60000) / 86400000);
async function viewHome() {
  setTitle('');
  const m = await meta();
  const did = m.pool[DAY % m.pool.length];
  const total = m.colls.reduce((s, c) => s + c.count, 0);
  app.innerHTML = `
  <section class="hero">
    <article class="daily" id="daily"><div class="tag">每 日 一 首</div><div class="skel" style="height:180px;margin-top:12px;border:none"></div></article>
    <div class="stats">
      <div class="stat"><b>${fmt(total)}</b><span>篇诗文</span></div>
      <div class="stat"><b>${fmt(m.authors)}</b><span>位作者</span></div>
      <div class="stat"><b>${m.colls.length}</b><span>部合集</span></div>
      <div class="stat"><b>${m.lists.reduce((s, l) => s + l.count, 0)}</b><span>首选本名篇</span></div>
      <a class="stat" href="javascript:void 0" id="rndBtn" style="grid-column:span 2;text-align:center"><b style="font-size:20px">随机一首 ↻</b><span>从精选中随意翻一页</span></a>
    </div>
  </section>
  <div class="sec-h"><h2>精选</h2></div>
  <div class="colls">${m.lists.map(l => `<a class="coll" href="/l/${l.code}"><span class="nm">${esc(l.name)}</span><span class="dy">${l.count} 首</span><div class="ds">${esc(l.desc)}</div></a>`).join('')}</div>
  <div class="sec-h"><h2>合集</h2><a href="/c">全部 ›</a></div>
  <div class="colls">${m.colls.map(collCard).join('')}</div>
  <div class="sec-h"><h2>名家</h2><a href="/authors">全部作者 ›</a></div>
  <div class="chips">${m.famous.map(e => `<a class="chip" href="${authorHref(e)}">${esc(e[0])}<small>${esc(e[1])}</small></a>`).join('')}</div>`;
  $('#rndBtn').onclick = () => { go('/p/' + m.pool[Math.floor(Math.random() * m.pool.length)]); };
  const nav = NAV; const r = await poem(did); if (nav !== NAV) return; const [t, a, g, p, x, ref, dyn] = r;
  const lines = p.slice(0, 6);
  $('#daily').innerHTML = `<div class="tag">每 日 一 首 · ${new Date().toLocaleDateString('zh-CN', { month: 'long', day: 'numeric' })}</div>
    <h1>${esc(t)}</h1><div class="by">〔${esc(dyn)}〕${esc(a)}</div>
    <div class="verse">${lines.map(l => `<p>${esc(l)}</p>`).join('')}${p.length > 6 ? '<p class="muted">……</p>' : ''}</div>
    <div class="acts"><a class="btn pri" href="/p/${did}">读全文</a><a class="btn" href="/p/${m.pool[(DAY + 1) % m.pool.length]}">换一首</a></div>`;
}
const collCard = c => `<a class="coll" href="/c/${c.code}"><span class="nm">${esc(c.name)}</span><span class="dy">${esc(c.dyn)}</span><div class="ct">${fmt(c.count)} 篇</div><div class="ds">${esc(c.desc)}</div></a>`;
const authorHref = e => `/a/${e[3]}/${encodeURIComponent(grp(e[1]) + '|' + e[0])}`;

async function viewColls() {
  setTitle('合集'); const m = await meta();
  app.innerHTML = `<div class="ph"><h1>合集</h1><p class="lead">按合集浏览，唐诗、宋诗可按体裁筛选。</p></div>
   <div class="sec-h"><h2>精选</h2></div><div class="colls">${m.lists.map(l => `<a class="coll" href="/l/${l.code}"><span class="nm">${esc(l.name)}</span><span class="dy">${l.count} 首</span><div class="ds">${esc(l.desc)}</div></a>`).join('')}</div>
   <div class="sec-h"><h2>全部合集</h2></div><div class="colls">${m.colls.map(collCard).join('')}</div>`;
}

// generic paged id list renderer
function pager(listEl, moreEl, ids, getStub, per = 24, terms) {
  let pos = 0, busy = false;
  async function next() {
    if (busy || pos >= ids.length) return; busy = true;
    const slice = ids.slice(pos, pos + per); pos += slice.length;
    const ph = document.createElement('div'); ph.style.display = 'contents'; ph.innerHTML = skel(Math.min(slice.length, 6)); listEl.append(ph);
    const [stubs] = await Promise.all([Promise.all(slice.map(id => getStub(id).catch(() => null))), pop().catch(() => null)]);
    ph.outerHTML = slice.map((id, i) => cardHTML(id, stubs[i], terms)).join('');
    moreEl.innerHTML = pos < ids.length ? `<button class="btn">加载更多（${pos}/${ids.length}）</button>` : (ids.length > per ? `<span class="muted">已全部加载 · ${ids.length} 篇</span>` : '');
    const b = moreEl.querySelector('button'); if (b) b.onclick = next;
    busy = false;
    if (pos < ids.length) idle(() => stub(ids[pos]).catch(() => {}));
  }
  const io = new IntersectionObserver(es => { if (es[0].isIntersecting) next(); }, { rootMargin: '600px' });
  io.observe(moreEl); viewCleanup.push(() => io.disconnect());
  return next();
}
const range = (a, n) => Array.from({ length: n }, (_, i) => a + i);

async function viewColl(code, qs) {
  const m = await meta(); const c = collBy(code); if (!c) return notFound();
  setTitle(c.name);
  const gi = qs.get('g'); const G = genresOf(c);
  const sel = gi != null && G[+gi] ? G[+gi] : null;
  app.innerHTML = `<div class="ph"><div class="crumb"><a href="/">首页</a> › <a href="/c">合集</a></div>
    <h1>${esc(c.name)} <span class="muted">${esc(c.dyn)} · ${c.count} 篇</span></h1><p class="lead">${esc(c.desc)}</p></div>
    ${G.length > 1 ? `<div class="filters"><div class="row"><span class="lbl">${['tang', 'songshi', 'jiuti'].includes(code) ? '体裁' : '分类'}</span><div class="chips">
      <a class="chip ${sel ? '' : 'on'}" href="/c/${code}">全部</a>${G.map((g, i) => `<a class="chip ${sel === g ? 'on' : ''}" href="/c/${code}?g=${i}">${esc(g[0])}<small>${fmt(g[2])}</small></a>`).join('')}</div></div></div>
      ${['tang', 'songshi'].includes(code) ? '<p class="hint">体裁按句数与字数推断；各体裁内按流传度排序。</p>' : code === 'jiuti' ? '<p class="hint">体裁按词牌与句式推断。</p>' : ''}` : ''}
    ${['songci'].includes(code) ? '<p class="hint">按流传度排序。可在搜索框输入词牌名（如「水调歌头」）查找。</p>' : ''}
    <div class="grid" id="list"></div><div class="more" id="more"></div>`;
  const ids = (sel ? sel[1] : segsOf(c)).flatMap(([s, n]) => range(s, n));
  pager($('#list'), $('#more'), ids, stub);
}

async function viewList(code) {
  const m = await meta(); const l = m.lists.find(x => x.code === code); if (!l) return notFound();
  setTitle(l.name);
  const L = await getJSON(`/data/l/${code}.json`);
  const byG = {}; L.forEach(e => { const k = e[4] || '其他'; (byG[k] = byG[k] || []).push(e); });
  const S = new Map(L.map(e => [e[0], [e[1], e[2], e[3], e[4], l.name]]));
  app.innerHTML = `<div class="ph"><div class="crumb"><a href="/">首页</a> › 精选</div><h1>${esc(l.name)} <span class="muted">${L.length} 首</span></h1><p class="lead">${esc(l.desc)}</p></div>
   <div class="filters"><div class="row"><span class="lbl">筛选</span><div class="chips" id="gch"><a class="chip on" data-g="">全部</a>${Object.keys(byG).sort((a, b) => byG[b].length - byG[a].length).slice(0, 40).map(g => `<a class="chip" data-g="${esc(g)}">${esc(g)}<small>${byG[g].length}</small></a>`).join('')}</div></div></div>
   <div class="grid" id="list"></div><div class="more" id="more"></div>`;
  const draw = g => { $('#list').innerHTML = ''; $('#more').innerHTML = ''; viewCleanup.splice(0).forEach(f => f()); pager($('#list'), $('#more'), (g ? byG[g] : L).map(e => e[0]), id => Promise.resolve(S.get(id)), 36); };
  $('#gch').onclick = e => { const a = e.target.closest('.chip'); if (!a) return; $('#gch').querySelectorAll('.chip').forEach(x => x.classList.toggle('on', x === a)); draw(a.dataset.g); };
  draw('');
}

// 维基百科来源署名（CC BY-SA 4.0）
const wikiSrc = a => a && a.bw ? `<p class="muted" style="font-size:12px;margin-top:6px">摘自维基百科<a href="${esc(a.bw)}" target="_blank" rel="noopener" style="color:inherit;text-decoration:underline">《${esc(a.bt || '')}》</a>，<a href="https://creativecommons.org/licenses/by-sa/4.0/deed.zh-hans" target="_blank" rel="noopener" style="color:inherit">CC BY-SA 4.0</a></p>` : '';
async function loadAuthor(ref, key, page = 0) {
  if (String(ref).startsWith('x')) { const o = await getJSON(`/data/a/${ref}-${page}.json`); return o; }
  const o = await getJSON(`/data/a/${ref}.json`); const a = o[key]; if (a) a.pages = 1; return a;
}
async function viewAuthor(ref, key) {
  await meta();
  const a = await loadAuthor(ref, key, 0); if (!a) return notFound();
  setTitle(a.n);
  app.innerHTML = `<div class="ph"><div class="crumb"><a href="/">首页</a> › <a href="/authors">作者</a></div>
   <div class="acard" style="margin:0"><span class="seal">${esc(a.n[0])}</span><div style="flex:1;min-width:0"><h3>${esc(a.n)} <span class="muted">〔${esc(a.d)}〕 · 共 <span id="acnt">${a.pages > 1 ? '约 ' + (a.pages * 500) : a.L.length}</span> 篇</span></h3>
   ${a.b ? `<div class="bio" id="bio">${paras(a.b)}</div><button class="linkbtn" id="bioT">展开简介</button>${wikiSrc(a)}` : (['佚名', '无名氏'].includes(a.n) ? '<p class="nodata">作者佚名，生平不详。</p>' : '<p class="nodata">暂无简介。</p>')}</div></div></div>
   <div class="toolbar"><input id="af" class="chip" style="cursor:text;min-width:200px;border:1px solid var(--line)" placeholder="在 ${esc(a.n)} 的作品中筛选标题"></div>
   <div class="grid" id="list"></div><div class="more" id="more"></div>`;
  const bt = $('#bioT'); if (bt) { const b = $('#bio'); if (b.scrollHeight <= b.clientHeight + 4) { bt.remove(); b.classList.add('open'); } else bt.onclick = () => { b.classList.toggle('open'); bt.textContent = b.classList.contains('open') ? '收起' : '展开简介'; }; }
  let all = a.L.slice();
  const c0 = id => collOf(id);
  const mk = L => { const S = new Map(L.map(e => [e[0], [e[1], a.n, e[2], (c0(e[0]) || {}).name]])); return S; };
  let S = mk(all);
  const draw = () => { const f = $('#af').value.trim(); viewCleanup.splice(0).forEach(fn => fn()); $('#list').innerHTML = ''; $('#more').innerHTML = '';
    const ids = all.filter(e => !f || e[1].includes(f) || e[2].includes(f)).map(e => e[0]); if (!ids.length) $('#list').innerHTML = '<div class="empty">没有匹配的作品</div>';
    pager($('#list'), $('#more'), ids, id => Promise.resolve(S.get(id)), 36, f ? [f] : []); };
  draw();
  $('#af').oninput = () => { clearTimeout(draw._t); draw._t = setTimeout(draw, 200); };
  if (a.pages > 1) { // load remaining pages in background
    const rest = await Promise.all(range(1, a.pages - 1).map(p => loadAuthor(ref, key, p)));
    rest.forEach(o => all.push(...o.L)); S = mk(all); $('#acnt').textContent = all.length; draw();
  }
}

async function viewAuthors(qs) {
  setTitle('作者'); await meta();
  app.innerHTML = `<div class="ph"><div class="crumb"><a href="/">首页</a> › 作者</div><h1>作者</h1><p class="lead">共 ${fmt(M.authors)} 位，按作品数排序。</p></div>
   <div class="toolbar"><input id="af" class="chip" style="cursor:text;min-width:220px;border:1px solid var(--line)" placeholder="输入作者名" value="${esc(qs.get('q') || '')}"></div>
   <div class="filters"><div class="row"><span class="lbl">朝代</span><div class="chips" id="dch"></div></div></div>
   <div class="alist" id="al"><div class="skel"></div></div>`;
  const A = await authors();
  const dyns = {}; A.forEach(e => dyns[e[1]] = (dyns[e[1]] || 0) + 1);
  let dsel = qs.get('d') || '';
  $('#dch').innerHTML = `<a class="chip ${dsel ? '' : 'on'}" data-d="">全部</a>` + Object.keys(dyns).sort((a, b) => dyns[b] - dyns[a]).map(d => `<a class="chip ${d === dsel ? 'on' : ''}" data-d="${esc(d)}">${esc(d)}<small>${dyns[d]}</small></a>`).join('');
  const draw = () => { const f = $('#af').value.trim();
    const L = A.filter(e => (!dsel || e[1] === dsel) && (!f || e[0].includes(f))).slice(0, 300);
    $('#al').innerHTML = L.length ? L.map(e => `<a href="${authorHref(e)}"><b>${esc(e[0])}</b><span>${esc(e[1])} · ${e[2]} 篇</span></a>`).join('') : '<div class="empty">没有找到</div>'; };
  $('#dch').onclick = e => { const c = e.target.closest('.chip'); if (!c) return; dsel = c.dataset.d; $('#dch').querySelectorAll('.chip').forEach(x => x.classList.toggle('on', x === c)); draw(); };
  $('#af').oninput = draw; draw();
}

/* ---------- poem page ---------- */
const GENRE_INFO = {
  '五言绝句': '四句，每句五字。近体诗，讲究平仄、押韵。', '七言绝句': '四句，每句七字。近体诗，讲究平仄、押韵。',
  '五言律诗': '八句，每句五字。中间两联通常对仗。', '七言律诗': '八句，每句七字。中间两联通常对仗。',
  '五言长篇': '八句以上、每句五字，多为五言古诗或五言排律。', '七言长篇': '八句以上、每句七字，多为七言古诗或歌行、排律。',
  '四言': '每句四字。', '六言': '每句六字。', '杂言': '句子长短不一，多为古体、乐府或歌行。', '残句': '仅存一两句的残篇或断句。', '词': '按词牌填写的长短句，题目开头即词牌名。'
};
function renderBody(p, x, isProse) {
  if (x && x.py && x.py.length === p.length) {
    return p.map((l, i) => { const sy = x.py[i].split(/\s+/); const ch = [...l]; let k = 0;
      return '<p>' + ch.map(c => CJK.test(c) ? `<ruby>${esc(c)}<rt>${esc(sy[k++] || '')}</rt></ruby>` : esc(c)).join('') + '</p>'; }).join('');
  }
  return p.map(l => /^〔.*〕$/.test(l) ? `<p class="subh">${esc(l)}</p>` : `<p>${esc(l)}</p>`).join('');
}
const paras = t => [...new Set(String(t).split(/\u3000\u3000|\n+|--+/).map(s => s.trim()))].join('\n').split(/\n/).map(s => s.trim()).filter(Boolean).map(s => `<p>${esc(s)}</p>`).join('');
async function viewPoem(id) {
  id = +id; const nav = NAV; const live = () => nav === NAV; const m = await meta(); const c = collOf(id); if (!c) { const n = await movedId(id); if (n && live()) { history.replaceState(null, '', '/p/' + n); const f = favs(); if (f.includes(id)) setFavs(f.map(v => v === id ? n : v)); return viewPoem(n); } return notFound(); }
  app.innerHTML = `<div class="poem-wrap"><div class="poem"><div class="skel" style="height:300px;border:none"></div></div><aside class="side"></aside></div>`;
  const r = await poem(id); if (!live()) return; if (!r) { const n = await movedId(id); if (n && n !== id && live()) { history.replaceState(null, '', '/p/' + n); const f = favs(); if (f.includes(id)) setFavs([...new Set(f.map(v => v === id ? n : v))]); return viewPoem(n); } return notFound(); }
  const [t, a, g, p, x0, ref, dyn] = r; const x = x0 || {};
  setTitle(`${t} · ${a}`);
  const prose = !!x.f;
  const gi = genresOf(c).findIndex(e => e[0] === g);
  const isShi = ['tang', 'songshi', 'shuimo', 'jiuti'].includes(c.code) || (c.code === 'mengxue' && g === '千家诗');
  const isCi = ['songci', 'huajian', 'nantang', 'nalan'].includes(c.code);
  const fav = favs().includes(id);
  const aKey = grp(dyn) + '|' + a;
  const notes = [];
  if (x.n && x.n.length) notes.push(`<div class="panel"><h3>注释</h3><ol>${x.n.map(n => `<li>${esc(String(n).replace(/^\d+[.、]\s*/, ''))}</li>`).join('')}</ol></div>`);
  if (x.pr) notes.push(`<div class="panel"><h3>赏析</h3>${paras(x.pr)}</div>`);
  if (x.cm && x.cm.length) notes.push(`<div class="panel"><h3>评点</h3>${x.cm.map(s => `<p>${esc(s)}</p>`).join('')}</div>`);
  if (x.og && x.og.length) notes.push(`<div class="panel"><h3>郡望</h3><div class="og">${x.og.map(o => `<span><b>${esc(o[0])}</b>${esc(o[1])}</span>`).join('')}</div></div>`);
  if (x.ab) notes.push(`<div class="panel"><h3>题解</h3>${paras(x.ab)}</div>`);
  const info = [];
  info.push(['合集', `<a href="/c/${c.code}">${esc(c.name)}</a>`]);
  if (g && g !== c.name) info.push([isCi ? '词牌' : c.code === 'yuanqu' ? '曲牌' : isShi ? '体裁' : '分类', gi >= 0 ? `<a href="/c/${c.code}?g=${gi}">${esc(g)}</a>` : `<a href="/s?q=${encodeURIComponent(g)}">${esc(g)}</a>`]);
  if (x.s) info.push(['篇章', esc(x.s)]);
  if (x.src) info.push(['出处', esc(x.src)]);
  if (x.sel) info.push(['选本', `<a href="/l/${x.sel === '唐诗三百首' ? 'ts300' : 'sc300'}">${esc(x.sel)}</a>`]);
  if (x.tg && x.tg.length) info.push(['标签', x.tg.filter(s => s !== x.sel && s !== g).map(esc).join('、') || '—']);
  const ginfo = isShi && GENRE_INFO[g] ? `<p class="nodata" style="margin-top:8px">${esc(g)}：${esc(GENRE_INFO[g])}（体裁据句式推断）</p>` : isCi && g ? `<p class="nodata" style="margin-top:8px">词牌「${esc(g)}」：<a href="/s?q=${encodeURIComponent(g)}" style="color:var(--accent)">查看同词牌作品</a></p>` : '';
  const sg = segOf(c, id); const prevOK = id > sg[0], nextOK = id < sg[0] + sg[1] - 1;
  app.innerHTML = `<div class="crumb"><a href="/">首页</a> › <a href="/c/${c.code}">${esc(c.name)}</a>${gi >= 0 ? ` › <a href="/c/${c.code}?g=${gi}">${esc(g)}</a>` : ''}</div>
  <div class="poem-wrap"><div>
   <article class="poem" id="poem">
     <h1>${esc(t)}</h1>
     <div class="by">〔${esc(dyn)}〕<a href="/a/${ref}/${encodeURIComponent(aKey)}">${esc(a)}</a></div>
     ${x.s ? `<div class="sub">${esc(x.s)}</div>` : ''}
     <div class="vscroll" id="vscroll"><div class="verse-body ${prose ? 'prose' : ''}" id="vbody">${renderBody(p, x, prose)}</div></div>
     <div class="poem-acts" role="toolbar" aria-label="阅读工具">
       <button class="tb" id="bTts" title="朗读"><i>▶</i><span>朗读</span></button>
       <button class="tb" id="bPy" title="拼音"><i>拼</i><span>拼音</span></button>
       ${!prose && p.join('').length < 1200 ? '<button class="tb" id="bVert" title="竖排"><i>⫼</i><span>竖排</span></button>' : ''}
       <button class="tb" id="bSm" title="缩小字号"><i>A</i><span>小字</span></button><button class="tb" id="bLg" title="放大字号"><i style="font-size:19px">A</i><span>大字</span></button>
       <button class="tb" id="bCopy" title="复制"><i>⧉</i><span>复制</span></button><button class="tb" id="bShare" title="分享"><i>↗</i><span>分享</span></button>
       <button class="tb ${fav ? 'on' : ''}" id="bFav" title="收藏"><i>${fav ? '★' : '☆'}</i><span>收藏</span></button>
     </div>
     <div class="ttsbar" id="ttsBar" hidden><span id="ttsMsg">正在朗读…</span><button class="btn" id="ttsPause">暂停</button><button class="btn" id="ttsStop">停止</button></div>
   </article>
   <div class="notes">${notes.join('')}</div>
   <div class="nav2">${prevOK ? `<a href="/p/${id - 1}" id="pv"><small>‹ 上一篇</small><span id="pvt">…</span></a>` : '<span style="flex:1"></span>'}${nextOK ? `<a class="r" href="/p/${id + 1}" id="nx"><small>下一篇 ›</small><span id="nxt">…</span></a>` : '<span style="flex:1"></span>'}</div>
  </div>
  <aside class="side">
    <div class="panel"><h3>作者</h3><div id="bioBox"><p class="nodata">加载中…</p></div></div>
    <div class="panel"><h3>信息</h3><div class="kv">${info.map(([k, v]) => `<b>${k}</b><span>${v}</span>`).join('')}</div>${ginfo}</div>
  </aside></div>`;
  // prev/next titles
  if (prevOK) stub(id - 1).then(s => { if (s && live() && $('#pvt')) $('#pvt').textContent = s[0]; });
  if (nextOK) stub(id + 1).then(s => { if (s && live() && $('#nxt')) $('#nxt').textContent = s[0]; });
  // author bio
  loadAuthor(ref, aKey).then(au => {
    const box = $('#bioBox'); if (!box || !live()) return;
    const nm = `<p><a href="/a/${ref}/${encodeURIComponent(aKey)}" style="color:var(--ink);font-weight:700;font-size:17px">${esc(a)}</a> <span class="muted">〔${esc(dyn)}〕</span></p>`;
    box.innerHTML = nm + (au && au.b ? `<div class="bio" id="bio">${paras(au.b)}</div><button class="linkbtn" id="bioT">展开</button>${wikiSrc(au)}` : (['佚名', '无名氏'].includes(a) ? '<p class="nodata">作者佚名，生平不详。</p>' : '<p class="nodata">暂无简介。</p>')) + `<p style="margin-top:8px"><a class="linkbtn" href="/a/${ref}/${encodeURIComponent(aKey)}">查看作品 ›</a></p>`;
    const bt = $('#bioT'); if (bt) { const b = $('#bio'); if (b.scrollHeight <= b.clientHeight + 4) { bt.remove(); b.classList.add('open'); } else bt.onclick = () => { b.classList.toggle('open'); bt.textContent = b.classList.contains('open') ? '收起' : '展开'; }; }
  }).catch(() => { const box = $('#bioBox'); if (box && live()) box.innerHTML = '<p class="nodata">简介加载失败</p>'; });
  // actions
  const text = `${t}\n〔${dyn}〕${a}\n${p.join('\n')}`;
  $('#bCopy').onclick = () => copy(text + `\n—— ${location.href}`, '已复制全文');
  const shareLink = async () => { if (navigator.share) { try { await navigator.share({ title: `${t} · ${a}`, text: p.slice(0, 2).join(''), url: location.href }); } catch (e) {} } else copy(location.href, '已复制链接'); };
  $('#bShare').onclick = () => posterModal(t, a, dyn, p, prose, shareLink);
  $('#bFav').onclick = () => { let f = favs(); if (f.includes(id)) { f = f.filter(v => v !== id); toast('已取消收藏'); } else { f.unshift(id); toast('已收藏'); } setFavs(f); const on = f.includes(id); $('#bFav').classList.toggle('on', on); $('#bFav').querySelector('i').textContent = on ? '★' : '☆'; };
  const pe = $('#poem'), bv = $('#bVert'), bp = $('#bPy');
  const setVert = v => { pe.classList.toggle('vert', v); if (bv) { bv.classList.toggle('on', v); bv.querySelector('span').textContent = v ? '横排' : '竖排'; } fitVert(); };
  const fitVert = () => { const vb = $('#vbody'), vs = $('#vscroll'); if (!vb) return; vb.style.fontSize = ''; vb.style.height = '';
    if (!pe.classList.contains('vert')) { const hn = $('#vhint'); if (hn) hn.remove(); return; }
    const L = Math.max(...p.map(l => [...l].length)), H = Math.round(Math.min(520, Math.max(300, Math.max(screen.width, screen.height) * 0.55)));
    const base = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--fs')) || 1;
    let f = Math.max(15, Math.min(22 * base, H / (L * 1.12 + 0.5)));
    vb.style.fontSize = f + 'px'; vb.style.height = Math.min(H, (L * 1.12 + 1) * f) + 'px';
    requestAnimationFrame(() => { const more = vs.scrollWidth > vs.clientWidth + 4; let hn = $('#vhint'); if (more && !hn) { vs.insertAdjacentHTML('afterend', '<p class="hint" id="vhint" style="text-align:center">← 向左滑动查看后续</p>'); } else if (!more && hn) hn.remove(); vs.scrollLeft = vs.scrollWidth; /* RTL origin: show first column */ if (vs.scrollLeft === 0) vs.scrollLeft = 0; }); };
  if (bv) { setVert(localStorage.getItem('shici.vert') === '1' && localStorage.getItem('shici.py') !== '1'); bv.onclick = () => { const v = !pe.classList.contains('vert'); if (v && pyOn) { setPy(false); toast('竖排时暂不显示拼音'); } setVert(v); localStorage.setItem('shici.vert', v ? '1' : '0'); }; }
  // pinyin (lazy-loaded pinyin-pro)
  let pyOn = false;
  const setPy = async on => { pyOn = on; bp.classList.toggle('on', on); localStorage.setItem('shici.py', on ? '1' : '0');
    if (on) { if (pe.classList.contains('vert')) { setVert(false); toast('拼音模式下自动切换为横排'); }
      bp.querySelector('span').textContent = '加载中'; try { await loadPinyin(); } catch (e) { bp.querySelector('span').textContent = '拼音'; toast('拼音组件加载失败，请检查网络后再试'); pyOn = false; bp.classList.remove('on'); localStorage.setItem('shici.py', '0'); return; } bp.querySelector('span').textContent = '拼音';
      if (!live() || !pyOn) return;
      $('#vbody').innerHTML = p.map(l => /^〔.*〕$/.test(l) ? `<p class="subh">${esc(l)}</p>` : `<p>${rubyLine(l)}</p>`).join(''); $('#vbody').classList.add('py');
    } else { $('#vbody').innerHTML = renderBody(p, x, prose); $('#vbody').classList.remove('py'); } };
  bp.onclick = () => setPy(!pyOn);
  if (localStorage.getItem('shici.py') === '1') setPy(true);
  let lastW = document.documentElement.clientWidth; const onRs = () => { const w = document.documentElement.clientWidth; if (w !== lastW) { lastW = w; fitVert(); } }; addEventListener('resize', onRs); viewCleanup.push(() => removeEventListener('resize', onRs));
  // read aloud
  setupTTS(t, a, dyn, p, live);
  // prefetch neighbours + author
  idle(() => { if (live()) { prefetchPoem(id + 1); prefetchPoem(id - 1); } });
  const fs = d => { let v = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--fs')) || 1; v = Math.min(1.5, Math.max(.85, Math.round((v + d) * 100) / 100)); document.documentElement.style.setProperty('--fs', v); localStorage.setItem('shici.fs', v); fitVert(); };
  $('#bSm').onclick = () => fs(-.1); $('#bLg').onclick = () => fs(.1);
  keyNav = e => { if (e.target.matches('input')) return; if (e.key === 'ArrowLeft' && prevOK) go('/p/' + (id - 1)); if (e.key === 'ArrowRight' && nextOK) go('/p/' + (id + 1)); };
}
let PYP = null;
function loadPinyin() { if (window.pinyinPro) return Promise.resolve(); if (PYP) return PYP;
  const once = n => new Promise((res, rej) => { const sc = document.createElement('script'); sc.src = '/vendor/pinyin-pro.js?v=3.29.5' + (n ? '&r=' + n : ''); sc.async = true;
    const t = setTimeout(() => { sc.remove(); rej(new Error('timeout')); }, 25000);
    sc.onload = () => { clearTimeout(t); window.pinyinPro ? res() : rej(new Error('empty')); }; sc.onerror = () => { clearTimeout(t); sc.remove(); rej(new Error('net')); }; document.head.append(sc); });
  PYP = once(0).catch(() => new Promise(r => setTimeout(r, 800)).then(() => once(1))).catch(() => new Promise(r => setTimeout(r, 1500)).then(() => once(2))).catch(e => { PYP = null; throw e; });
  return PYP; }
function rubyLine(l) { const ch = [...l]; let py; try { py = pinyinPro.pinyin(l, { type: 'array', toneType: 'symbol' }); } catch (e) { py = []; }
  if (py.length !== ch.length) py = ch.map(c => CJK.test(c) ? pinyinPro.pinyin(c) : c);
  return ch.map((c, i) => CJK.test(c) ? `<ruby>${esc(c)}<rt>${esc(py[i])}</rt></ruby>` : esc(c)).join(''); }
function setupTTS(t, a, dyn, p, live) {
  const btn = $('#bTts'), bar = $('#ttsBar'), msg = $('#ttsMsg'), bPause = $('#ttsPause'), bStop = $('#ttsStop');
  const S = window.speechSynthesis;
  if (!S || !window.SpeechSynthesisUtterance) { btn.onclick = () => toast('当前浏览器不支持朗读'); return; }
  let state = 'idle';
  const lines = () => [...document.querySelectorAll('#vbody p')];
  const clearHL = () => lines().forEach(el => el.classList.remove('reading'));
  const voice = () => { const v = S.getVoices(); return v.find(x => /zh[-_]CN/i.test(x.lang)) || v.find(x => /^zh/i.test(x.lang) && !/HK|TW/i.test(x.lang)) || v.find(x => /^zh/i.test(x.lang)) || null; };
  const ui = () => { bar.hidden = state === 'idle'; btn.classList.toggle('on', state !== 'idle'); btn.querySelector('i').textContent = state === 'playing' ? '❚❚' : '▶';
    bPause.textContent = state === 'paused' ? '继续' : '暂停'; msg.textContent = state === 'paused' ? '已暂停' : '正在朗读…'; };
  const stop = () => { S.cancel(); state = 'idle'; clearHL(); ui(); };
  const play = () => {
    S.cancel(); const vo = voice(); if (!vo && !S.getVoices().length) {} // voices may load lazily; browser picks default for lang
    const items = [[`${t}。${dyn}，${a}。`, -1], ...p.map((l, i) => [l.replace(/^〔|〕$/g, ''), i])];
    items.forEach(([txt, i], k) => { const u = new SpeechSynthesisUtterance(txt); u.lang = 'zh-CN'; if (vo) u.voice = vo; u.rate = 0.82; u.pitch = 1;
      u.onstart = () => { if (!live()) return S.cancel(); clearHL(); const el = lines()[i]; if (el) { el.classList.add('reading'); if (!document.getElementById('poem').classList.contains('vert')) el.scrollIntoView({ block: 'center', behavior: 'smooth' }); } };
      if (k === items.length - 1) u.onend = () => { if (state !== 'idle') { state = 'idle'; clearHL(); ui(); } };
      u.onerror = e => { if (e.error !== 'interrupted' && e.error !== 'canceled') { toast('朗读出错：' + e.error); } };
      S.speak(u); });
    state = 'playing'; ui();
    setTimeout(() => { if (state === 'playing' && !S.speaking && !S.pending) { state = 'idle'; ui(); toast('未能开始朗读，请检查设备是否有中文语音'); } }, 2500);
  };
  btn.onclick = () => { if (state === 'idle') play(); else if (state === 'playing') { S.pause(); state = 'paused'; ui(); } else { S.resume(); state = 'playing'; ui(); } };
  bPause.onclick = () => { if (state === 'playing') { S.pause(); state = 'paused'; } else if (state === 'paused') { S.resume(); state = 'playing'; } ui(); };
  bStop.onclick = stop;
  viewCleanup.push(() => { if (state !== 'idle') S.cancel(); });
}
function copy(s, msg) { (navigator.clipboard ? navigator.clipboard.writeText(s) : Promise.reject()).then(() => toast(msg), () => { const ta = document.createElement('textarea'); ta.value = s; document.body.append(ta); ta.select(); try { document.execCommand('copy'); toast(msg); } catch (e) { toast('复制失败'); } ta.remove(); }); }

/* ---------- search ---------- */
async function viewSearch(qs) {
  const q = (qs.get('q') || '').trim(); const fc = qs.get('c') || ''; const fd = qs.get('d') || ''; const forceText = qs.get('t') === '1';
  $('#q').value = q; setTitle(q ? `搜索：${q}` : '搜索');
  await meta();
  if (!q) { app.innerHTML = '<div class="empty">输入标题、作者或诗句开始搜索，例如：李白、静夜思、明月</div>'; return; }
  app.innerHTML = `<div class="ph"><h1>搜索「${esc(q)}」</h1><p class="lead" id="sinfo">检索中…</p></div><div id="acards"></div><div class="filters" id="facets"></div><div class="grid" id="list">${skel(6)}</div><div class="more" id="more"></div>`;
  const nav = NAV; const [A, P] = await Promise.all([authors(), pop()]); if (nav !== NAV) return;
  const terms = q.split(/\s+/).map(s => s.trim()).filter(Boolean);
  const authorTerms = [], textTerms = [];
  for (const t of terms) {
    const hits = A.filter(e => e[0] === t);
    if (hits.length && !(forceText && terms.length === 1)) authorTerms.push([t, hits]); else textTerms.push(t);
  }
  // author cards
  const allHits = authorTerms.flatMap(x => x[1]);
  const partial = !allHits.length && terms.length === 1 && q.length >= 2 ? A.filter(e => e[0].includes(q) && e[0] !== q).slice(0, 6) : [];
  if (allHits.length || partial.length) {
    $('#acards').innerHTML = `<div class="sec-h" style="margin-top:6px"><h2>作者</h2></div><div class="alist" style="margin-bottom:10px">${[...allHits, ...partial].slice(0, 12).map(e => `<a href="${authorHref(e)}"><b>${esc(e[0])}</b><span>${esc(e[1])} · ${e[2]} 篇</span></a>`).join('')}</div>`;
  }
  let ids = null; const textTok = [];
  for (const t of textTerms) {
    const s = cjkOnly(t); if (!s) continue; textTok.push(s);
    let L;
    if (s.length === 1) L = await postings('^' + s);
    else { const bg = []; for (let i = 0; i < s.length - 1; i++) bg.push(s.slice(i, i + 2)); const ls = await Promise.all([...new Set(bg)].map(postings)); ls.sort((a, b) => a.length - b.length); L = ls.reduce((acc, l) => inter(acc, l)); }
    ids = ids ? inter(ids, L) : L;
  }
  if (authorTerms.length) {
    let aid = null;
    for (const [, hits] of authorTerms) {
      let set = [];
      for (const e of hits.slice(0, 3)) { const key = grp(e[1]) + '|' + e[0]; const first = await loadAuthor(e[3], key, 0); if (!first) continue; let L = first.L.map(v => v[0]);
        if (first.pages > 1) { const rest = await Promise.all(range(1, first.pages - 1).map(p => loadAuthor(e[3], key, p))); rest.forEach(o => L.push(...o.L.map(v => v[0]))); }
        set = set.concat(L); }
      set.sort((a, b) => a - b); aid = aid ? inter(aid, set) : set;
    }
    ids = ids ? inter(ids, aid) : aid;
  }
  ids = ids || []; if (nav !== NAV) return;
  // title-match boost (all chars appear in title) for text terms
  let titleSet = new Set();
  if (textTok.length === 1 && textTok[0].length >= 2 && textTok[0].length <= 6 && ids.length) {
    const ls = await Promise.all([...new Set(textTok[0])].map(ch => postings('^' + ch)));
    let tl = ls.reduce((acc, l) => inter(acc, l)); tl = inter(tl, ids); titleSet = new Set(tl);
  }
  if (nav !== NAV) return;
  // facets
  const byC = {}; for (const id of ids) { const c = collOf(id); if (c) byC[c.code] = (byC[c.code] || 0) + 1; }
  const byD = {}; for (const id of ids) { const d = dynOf(id); if (d) byD[d] = (byD[d] || 0) + 1; }
  let fids = ids.filter(id => { const c = collOf(id); return c && (!fc || c.code === fc) && (!fd || dynOf(id) === fd); });
  fids.sort((a, b) => (titleSet.has(b) - titleSet.has(a)) || (P[b] - P[a]) || (a - b));
  const link = (k, v) => { const u = new URLSearchParams(qs); if (v) u.set(k, v); else u.delete(k); return '/s?' + u.toString(); };
  $('#sinfo').textContent = ids.length ? `共 ${ids.length} 条结果${fc || fd ? `，筛选后 ${fids.length} 条` : ''}${textTok.some(t => t.length > 2) ? '（多字检索按字对匹配，个别结果可能不连续）' : ''}` : '没有找到结果';
  if (Object.keys(byC).length > 1 || fc || fd) $('#facets').innerHTML = `
    <div class="row"><span class="lbl">朝代</span><div class="chips"><a class="chip ${fd ? '' : 'on'}" href="${link('d', '')}">全部</a>${Object.entries(byD).sort((a, b) => b[1] - a[1]).map(([d, n]) => `<a class="chip ${fd === d ? 'on' : ''}" href="${link('d', d)}">${esc(d)}<small>${n}</small></a>`).join('')}</div></div>
    <div class="row"><span class="lbl">合集</span><div class="chips"><a class="chip ${fc ? '' : 'on'}" href="${link('c', '')}">全部</a>${Object.entries(byC).sort((a, b) => b[1] - a[1]).map(([c, n]) => `<a class="chip ${fc === c ? 'on' : ''}" href="${link('c', c)}">${esc(collBy(c).name)}<small>${n}</small></a>`).join('')}</div></div>`;
  $('#list').innerHTML = fids.length ? '' : (allHits.length ? '' : '<div class="empty">换个关键词试试，比如作者名、诗题或一句诗。</div>');
  if (authorTerms.length && !textTerms.length && allHits.length === 1 && !forceText) {
    $('#more').insertAdjacentHTML('afterend', `<p class="hint" style="text-align:center"><a href="/s?q=${encodeURIComponent(q)}&t=1" style="color:var(--accent)">搜索正文中含「${esc(q)}」的诗文 ›</a></p>`);
  }
  const hlTerms = [...textTok, ...authorTerms.map(x => x[0])];
  pager($('#list'), $('#more'), fids, stub, 24, hlTerms);
  // enrich visible cards with the matching verse line
  if (textTok.length) {
    const seen = new WeakSet();
    const enrich = () => document.querySelectorAll('.snip[data-id]').forEach(el => { if (seen.has(el)) return; seen.add(el); const id = +el.dataset.id;
      poem(id).then(r => { if (!r) return; const lines = r[3]; const tk = textTok[0]; let best = lines.find(l => l.includes(tk));
        if (!best && tk.length > 1) { best = lines.find(l => l.includes(tk.slice(0, 2))); }
        if (best && !lines[0].startsWith(best)) el.innerHTML = hl(best.length > 40 ? best.slice(Math.max(0, best.indexOf(tk) - 12), best.indexOf(tk) + 28) : best, textTok); else if (best) el.innerHTML = hl(best.slice(0, 40), textTok); }).catch(() => {}); });
    const mo = new MutationObserver(enrich); mo.observe($('#list'), { childList: true }); viewCleanup.push(() => mo.disconnect()); enrich();
  }
}

async function viewFav() {
  setTitle('收藏'); await meta(); let f = favs();
  if (f.length) { const mg = await getJSON('/data/merged.json?v=1').catch(() => ({})); if (f.some(id => mg[id])) { f = [...new Set(f.map(id => mg[id] || id))]; setFavs(f); } }
  if (f.some(id => id >= OLD_BUYI[0] && id < OLD_BUYI[1])) { const n = await Promise.all(f.map(async id => (await movedId(id)) || id)); f = [...new Set(n)]; setFavs(f); }
  app.innerHTML = `<div class="ph"><h1>收藏 <span class="muted">${f.length} 篇</span></h1><p class="lead">收藏保存在本机浏览器中。</p></div><div class="grid" id="list"></div><div class="more" id="more"></div>`;
  if (!f.length) { $('#list').innerHTML = '<div class="empty" style="grid-column:1/-1">还没有收藏。读到喜欢的诗，点「收藏」即可。</div>'; return; }
  pager($('#list'), $('#more'), f, stub, 36);
}
async function viewAbout() {
  setTitle('关于'); const m = await meta();
  const withNotes = { huajian: '注释', nantang: '注释', shuimo: '赏析', youmeng: '评点', tang: '唐诗三百首标签；部分篇目附《水墨唐诗》赏析', songci: '宋词三百首标签', mengxue: '千字文拼音、百家姓郡望、题解', guwen: '出处', xiantang: '朝代分类', xinshi: '部分作者简介' };
  app.innerHTML = `<div class="ph"><h1>关于本站</h1></div><div class="panel" style="max-width:760px">
   <p>本站收录的古典诗词与典籍数据来自 <a href="https://github.com/wujinpai/chinese-classics" target="_blank" rel="noopener" style="color:var(--accent)">chinese-classics</a>。「古人说」的精选句由本站从上述原文中整理，每句都链到原文。原文为繁体者已用 OpenCC 转为简体，个别异体字可能保留原貌。本站另提供<a href="/api" style="color:var(--accent)">开放 API</a>。</p>
   <p>注释、赏析、评点与作者简介均来自数据源，没有的篇目不另行生成。部分作者简介摘自<a href="https://zh.wikipedia.org/" target="_blank" rel="noopener" style="color:var(--accent)">中文维基百科</a>，依 <a href="https://creativecommons.org/licenses/by-sa/4.0/deed.zh-hans" target="_blank" rel="noopener" style="color:var(--accent)">CC BY-SA 4.0</a> 使用，并在简介下注明条目出处。唐诗、宋诗的体裁按句数与字数推断，排序参考数据集中的搜索引擎热度。</p>
   <h3 style="margin-top:14px">收录合集</h3>
   ${m.cats ? `<div class="kv">${m.cats.cats.map(([n, v]) => `<b>${esc(n)}</b><span>${v.toLocaleString()} 篇</span>`).join('')}</div>
   <p class="muted" style="margin-top:8px">共 ${m.cats.total.toLocaleString()} 篇。</p>`
   : `<div class="kv">${m.colls.map(c => `<b>${esc(c.name)}</b><span>${c.count} 篇 · ${esc(c.dyn)}${withNotes[c.code] ? ' · 含' + withNotes[c.code] : ''}</span>`).join('')}</div>`}
   <p style="margin-top:14px">字体：Noto Serif SC（SIL Open Font License）。数据构建日期：${esc(m.built)}。</p></div>`;
}

/* ---------- 古人说（本站自建句库） ---------- */
let SAIDP = null;
const loadSaid = () => SAIDP || (SAIDP = getJSON('/said.json?v=2').catch(e => { SAIDP = null; throw e; }));
// 本站自建句库：现代说法 → 标签 → 精选句；不调用 AI
function saidMatch(S, q, limit = 6) {
  const t = q.toLowerCase().replace(/\s+/g, ''), raw = cjkOnly(q); const ts = {};
  for (const [tag, ws] of Object.entries(S.kw)) for (const w of ws) if (t.includes(w.toLowerCase())) ts[tag] = Math.max(ts[tag] || 0, w.length + 1);
  let seed = 0; for (const ch of t) seed = (seed * 31 + ch.charCodeAt(0)) >>> 0;
  const sc = S.q.map((x, i) => { let v = 0; for (const g of x[5]) v += ts[g] || 0;
    if (raw.length >= 2 && cjkOnly(x[0]).includes(raw)) v += 100;
    if (x[1].length >= 2 && t.includes(x[1])) v += 30;
    return [v, ((i + 1) * 2654435761 ^ seed) >>> 0, x]; }).filter(e => e[0] > 0);
  sc.sort((a, b) => b[0] - a[0] || a[1] - b[1]);
  const out = [], seen = new Set();
  for (const [, , x] of sc) { if (seen.has(x[4])) continue; seen.add(x[4]); out.push({ quote: x[0], author: x[1], title: x[2], dynasty: x[3], pid: x[4] }); if (out.length >= limit) break; }
  return out;
}
// 精选不足时，从全站诗文按关键词检索补足（同样只用本站原文）
const SAID_STOP = new Set('我你他她它的了吗呢吧啊呀哦嘛好太真很都也就还又再在是有没不这那个们么啥怎想要会能得着过给让把被和跟'.split(''));
async function saidWide(S, q, need, have) {
  const t = q.toLowerCase().replace(/\s+/g, ''), raw = cjkOnly(q), terms = new Set();
  const tags = Object.entries(S.kw).filter(([, ws]) => ws.some(w => t.includes(w.toLowerCase()))).map(e => e[0]);
  // 先按意思：命中标签的古语说法（如「打死你」→ 愤怒 → 怒发、拔剑…），再按字面二字组
  for (const tg of tags) for (const w of ((S.cw || {})[tg] || [])) { const c = cjkOnly(w); if (c.length >= 2) terms.add(c.slice(0, 2)); }
  for (let i = 0; i < raw.length - 1; i++) { const b = raw.slice(i, i + 2); if (!SAID_STOP.has(b[0]) || !SAID_STOP.has(b[1])) if (!(SAID_STOP.has(b[0]) && SAID_STOP.has(b[1]))) terms.add(b); }
  const T = [...terms].slice(0, 8);
  const [P, ...ls] = await Promise.all([pop(), ...T.map(postings)]);
  const sc = new Map(); ls.forEach(l => { for (const id of l) sc.set(id, (sc.get(id) || 0) + 1); });
  if (!sc.size) { // 二字词都没命中：退到单字（正文按字检索太宽，改用题目单字索引 + 正文含该字）
    const cs = [...new Set(raw.split('').filter(c => !SAID_STOP.has(c)))].slice(0, 4);
    const tl = await Promise.all(cs.map(c => postings('^' + c)));
    tl.forEach(l => { for (const id of l) sc.set(id, (sc.get(id) || 0) + 1); });
    cs.forEach(c => T.push(c));
  }
  if (!sc.size) return [];
  const ids = [...sc.keys()].filter(id => !have.has(id)).sort((a, b) => sc.get(b) - sc.get(a) || (P[b] - P[a]) || a - b).slice(0, need * 3);
  const out = [], seenQ = new Set();
  for (const id of ids) {
    const r = await poem(id).catch(() => null); if (!r) continue; const [ti, a, , pl, x] = r; if (x && x.f) continue;
    let best = null, bv = 0;
    for (const line of pl || []) { const L = cjkOnly(line); const v = T.filter(w => L.includes(w)).length; if (v > bv && line.length <= 40) { bv = v; best = line; } }
    if (!best || seenQ.has(best)) continue; seenQ.add(best);
    out.push({ quote: best, author: a, title: ti, dynasty: dynOf(id) || '', pid: id, wide: 1 }); if (out.length >= need) break;
  }
  return out;
}
function saidCard(x, i) {
  return `<div class="said" data-i="${i}"><p class="sq">${esc(x.quote)}</p><p class="sa">〔${esc(x.dynasty || '')}〕${esc(x.author)}${x.title ? `《${esc(x.title)}》` : ''}</p>
    <div class="sb"><span class="sl"><a href="/p/${x.pid}" style="color:var(--accent)">阅读全文 ›</a></span><button class="btn" data-card>生成卡片</button></div></div>`;
}
async function viewSaid(qs) {
  const q = (qs.get('q') || '').trim(); setTitle(q ? `古人说：${q}` : '古人说');
  const ex = ['我爱你', '你真好看', '我 emo 了', '太卷了，想躺平', '想家了', '这事包的', '算了，不内耗了', '好久不见'];
  app.innerHTML = `<div class="ph"><h1>古人说</h1><p class="lead">输入一句现代话或网络热梗，找古人说过的原句。</p></div>
    <form class="saidf" id="saidf"><input id="sq" type="search" maxlength="60" placeholder="比如：我 emo 了" value="${esc(q)}" enterkeyhint="search" autocomplete="off"><button class="btn pri">找一句</button></form>
    <div class="chips" style="margin:12px 0 4px">${ex.map(e => `<a class="chip" href="/said?q=${encodeURIComponent(e)}">${esc(e)}</a>`).join('')}</div>
    <div id="sres"></div><div id="sai"></div><div id="sraw"></div>`;
  $('#saidf').onsubmit = e => { e.preventDefault(); const v = $('#sq').value.trim(); if (v) go('/said?q=' + encodeURIComponent(v)); };
  if (!q) return;
  const nav = NAV; let S; try { S = await loadSaid(); } catch (e) { $('#sres').innerHTML = '<p class="muted">句库加载失败，请稍后再试。</p>'; return; } if (nav !== NAV) return;
  const list = saidMatch(S, q, 6); const box = $('#sres');
  if (list.length < 3) { box.innerHTML = '<p class="muted" style="margin-top:14px">正在从全站诗文中查找…</p>'; try { list.push(...await saidWide(S, q, 6 - list.length, new Set(list.map(x => x.pid)))); } catch (e) {} if (nav !== NAV) return; }
  if (list.length) {
    box.innerHTML = `<div class="sec-h"><h2>古人这样说</h2></div><div class="saidl">${list.map((x, i) => saidCard(x, i)).join('')}</div>`;
    box.querySelectorAll('.said').forEach(el => { const x = list[+el.dataset.i];
      el.querySelector('[data-card]').onclick = () => { const lines = x.quote.replace(/([。！？；])/g, '$1\n').split('\n').map(s => s.trim()).filter(Boolean);
        const url = location.origin + '/p/' + x.pid;
        posterModal(x.title || x.author, x.author, x.dynasty || '', lines, false, async () => { if (navigator.share) { try { await navigator.share({ title: `古人说 · ${q}`, text: x.quote, url }); } catch (e) {} } else copy(url, '已复制链接'); }); };
    });
  } else box.innerHTML = '<p class="muted" style="margin-top:14px">全站诗文里没找到贴切的句子，换个说法试试。</p>';
  const raw = cjkOnly(q); if (!list.length && raw.length >= 2 && raw.length <= 8) $('#sraw').innerHTML = `<p class="hint" style="text-align:center;margin-top:18px"><a href="/s?q=${encodeURIComponent(raw)}&t=1" style="color:var(--accent)">在诗文中搜索含「${esc(raw)}」的原句 ›</a></p>`;
}
/* ---------- share sheet & poster ---------- */
function sheet(items) {
  const ov = document.createElement('div'); ov.className = 'ov';
  ov.innerHTML = `<div class="sheet" role="dialog" aria-label="分享">${items.map((it, i) => `<button data-i="${i}">${esc(it[0])}</button>`).join('')}<button class="cancel">取消</button></div>`;
  const close = () => ov.remove();
  ov.onclick = e => { const b = e.target.closest('button'); if (e.target === ov || (b && b.classList.contains('cancel'))) return close(); if (b) { close(); items[+b.dataset.i][1](); } };
  document.body.appendChild(ov);
}
async function drawPoster(t, a, dyn, p, prose) {
  const W = 1080, PAD = 96, F = "'ShiciSerif','Noto Serif SC','Songti SC','STSong',serif";
  let lines = p.map(l => l.replace(/^〔(.*)〕$/, '$1')).filter(Boolean);
  if (lines.join('').length > 1200) { const o = []; let n = 0; for (const l of lines) { if (n && n + l.length > 1200) break; o.push(n ? l : l.slice(0, 1200)); n += l.length; } o.push('……（节选）'); lines = o; }
  const body = lines.join('');
  const fs = body.length > 900 ? 34 : body.length > 400 ? 38 : 44, lh = Math.round(fs * 1.9);
  const all = t + a + dyn + body + '诗笺〔〕·shijian.jisu.cn';
  const fl = () => Promise.all([`700 60px`, `400 ${fs}px`, `400 32px`, `700 30px`, `400 26px`].map(z => document.fonts.load(`${z} ShiciSerif`, all)));
  try { await fl(); await document.fonts.ready; for (let i = 0; i < 6 && !(document.fonts.check(`400 ${fs}px ShiciSerif`, all) && document.fonts.check(`700 60px ShiciSerif`, all)); i++) { await new Promise(r => setTimeout(r, 400)); await fl(); } await document.fonts.ready; } catch (e) {}
  const c = document.createElement('canvas'); const x = c.getContext('2d');
  const maxW = W - PAD * 2 - 40;
  const wrap = (str, font) => { x.font = font; const out = []; let cur = '';
    for (const ch of str) { if (x.measureText(cur + ch).width > maxW && cur) { if (/^[，。、；：？！”’）》」』,.;:?!]$/.test(ch)) { cur += ch; continue; } out.push(cur); cur = ch; } else cur += ch; }
    if (cur) out.push(cur); return out; };
  const tF = `700 ${body.length > 900 ? 50 : 60}px ${F}`, bF = `400 ${fs}px ${F}`;
  const tL = wrap(t, tF); const bL = []; for (const l of lines) bL.push(...wrap(l, bF));
  const left = !!prose;
  const H = PAD + 70 + tL.length * 82 + 30 + 50 + 70 + bL.length * lh + 90 + 120 + PAD;
  const S = Math.min(2, 16000 / H); c.width = W * S; c.height = Math.round(H * S); x.scale(S, S);
  x.fillStyle = '#f5efe3'; x.fillRect(0, 0, W, H);
  const cx = 48, cw = W - 96, cy = 48, ch = H - 96;
  x.fillStyle = '#fbf8f1'; x.strokeStyle = '#e2d7c3'; x.lineWidth = 2;
  x.beginPath(); x.roundRect ? x.roundRect(cx, cy, cw, ch, 28) : x.rect(cx, cy, cw, ch); x.fill(); x.stroke();
  x.textBaseline = 'alphabetic'; x.textAlign = 'center';
  let y = PAD + 100;
  x.fillStyle = '#2a2622'; x.font = tF; for (const l of tL) { x.fillText(l, W / 2, y); y += 82; }
  y += 6; x.font = `400 32px ${F}`; x.fillStyle = '#8d8273'; const by = `〔${dyn}〕`; const bw = x.measureText(by).width; x.font = `400 32px ${F}`;
  const aw = x.measureText(a).width; x.textAlign = 'left'; const bx = W / 2 - (bw + aw) / 2; x.fillText(by, bx, y); x.fillStyle = '#a83a2a'; x.fillText(a, bx + bw, y);
  y += 70; x.fillStyle = '#2a2622'; x.font = bF; x.textAlign = left ? 'left' : 'center';
  for (const l of bL) { y += lh; x.fillText(l, left ? PAD + 20 : W / 2, y - lh * 0.3); }
  y += 60; x.strokeStyle = '#d8ccb6'; x.setLineDash([8, 8]); x.beginPath(); x.moveTo(PAD + 20, y); x.lineTo(W - PAD - 20, y); x.stroke(); x.setLineDash([]);
  y += 70; const sz = 56, label = '诗笺', dom = 'shijian.jisu.cn';
  x.font = `700 30px ${F}`; const lw = x.measureText(label).width; x.font = `400 26px ${F}`; const dw = x.measureText(dom).width;
  const tw = sz + 20 + Math.max(lw, dw); const sx = W / 2 - tw / 2;
  x.fillStyle = '#a83a2a'; x.beginPath(); x.roundRect ? x.roundRect(sx, y - 6, sz, sz, 10) : x.rect(sx, y - 6, sz, sz); x.fill();
  x.fillStyle = '#fff8ee'; x.font = `700 34px ${F}`; x.textAlign = 'center'; x.fillText('诗', sx + sz / 2, y + 34);
  x.textAlign = 'left'; x.fillStyle = '#2a2622'; x.font = `700 30px ${F}`; x.fillText(label, sx + sz + 20, y + 20);
  x.fillStyle = '#8d8273'; x.font = `400 26px ${F}`; x.fillText(dom, sx + sz + 20, y + 50);
  return c;
}
async function posterModal(t, a, dyn, p, prose, shareLink) {
  const ov = document.createElement('div'); ov.className = 'ov';
  ov.innerHTML = `<div class="pmod" role="dialog" aria-label="分享海报"><button class="pclose" data-x aria-label="关闭">×</button><div class="pimg"><div class="skel" style="height:360px;border:none"></div></div>
    <div class="pact"><button class="btn pri" data-d disabled>下载海报</button><button class="btn" data-s>${navigator.share ? '分享链接' : '复制链接'}</button></div><p class="phint">也可以长按图片保存到相册</p></div>`;
  const close = () => { ov.remove(); if (url) URL.revokeObjectURL(url); };
  let url = null, blob = null;
  ov.onclick = e => { if (e.target === ov || e.target.closest('[data-x]')) close(); };
  ov.querySelector('[data-s]').onclick = () => shareLink();
  document.body.appendChild(ov);
  try {
    const c = await drawPoster(t, a, dyn, p, prose);
    blob = await new Promise(r => c.toBlob(r, 'image/png'));
    url = URL.createObjectURL(blob);
    ov.querySelector('.pimg').innerHTML = `<img src="${url}" alt="${esc(t)} 海报">`;
    const d = ov.querySelector('[data-d]'); d.disabled = false;
    const name = `${t.replace(/[\\/:*?"<>|\s]+/g, '').slice(0, 30) || '诗笺'}-诗笺.png`;
    d.onclick = async () => {
      const f = new File([blob], name, { type: 'image/png' });
      if (/iP(hone|ad|od)/.test(navigator.userAgent) && navigator.canShare && navigator.canShare({ files: [f] })) { try { await navigator.share({ files: [f] }); return; } catch (e) { if (e.name === 'AbortError') return; } }
      const l = document.createElement('a'); l.href = url; l.download = name; document.body.appendChild(l); l.click(); l.remove();
    };
  } catch (e) { ov.querySelector('.pimg').innerHTML = '<div class="empty">海报生成失败</div>'; }
}
function notFound() { setTitle('页面不存在'); app.innerHTML = '<div class="nf"><div class="c">四〇四 · 页面不存在</div><p class="v">只在此山中，云深不知处。</p><p class="b">〔唐〕贾岛《寻隐者不遇》</p><a class="pri" href="/">回到首页</a><a href="/api">开放 API</a></div>'; }

/* ---------- 开放 API：文档与调试台（站内路由，不刷新页面） ---------- */
const apiBar = on => `<div class="apibar"><a href="/api" class="${on === 'doc' ? 'on' : ''}">接口文档</a><a href="/api/test" class="${on === 'test' ? 'on' : ''}">调试台</a></div>`;
let apiDocHTML = null;
async function viewApi() {
  setTitle('开放 API');
  if (!apiDocHTML) {
    const d = new DOMParser().parseFromString(await (await fetch('/api-doc.html')).text(), 'text/html'), m = d.querySelector('main');
    m.querySelectorAll('script,.try,#out').forEach(x => x.remove());
    m.querySelectorAll('a[href="/api/v1"]').forEach(a => a.setAttribute('href', '/api/test'));
    apiDocHTML = m.innerHTML.replace(/<h3>在线试用<\/h3>/, '<h3>在线试用</h3><p><a href="/api/test">打开调试台 ›</a>，在页面里直接调用全部接口。</p>');
  }
  app.innerHTML = `<div class="apidoc">${apiBar('doc')}${apiDocHTML}</div>`;
}
const API_ERA = ['', '先秦', '秦汉', '魏晋南北朝', '隋', '唐', '五代', '宋', '辽金', '元', '明', '清', '近代'], API_KIND = ['', '诗', '词', '曲', '典籍'];
const apiSel = (n, list, lab) => `<label>${lab}<select name="${n}">${list.map(v => `<option value="${v}">${v || '不限'}</option>`).join('')}</select></label>`;
const apiInp = (n, lab, ph, t = 'text') => `<label>${lab}<input name="${n}" type="${t}" placeholder="${ph || ''}"></label>`;
const API_EP = {
  search: { name: '搜索', main: ['q', '标题、正文，如 床前明月光'], opts: () => `<label>范围<select name="in"><option value="">标题+正文</option><option value="title">只搜标题</option><option value="content">只搜正文</option></select></label>${apiInp('author', '作者', '如 李白')}${apiSel('era', API_ERA, '朝代分区')}${apiInp('dynasty', '具体朝代', '如 南宋')}${apiSel('kind', API_KIND, '体裁')}${apiInp('size', '每页条数', '20', 'number')}`, path: () => '/api/v1/search' },
  poem: { name: '取全文', main: ['id', '作品 id，如 41910', 'number'], path: v => '/api/v1/poems/' + encodeURIComponent(v.id || ''), skip: ['id'] },
  random: { name: '随机', opts: () => `${apiSel('era', API_ERA, '朝代分区')}${apiInp('dynasty', '具体朝代', '如 北宋')}${apiSel('kind', API_KIND, '体裁')}<label class="ck"><input type="checkbox" name="famous" value="1">只从唐诗三百首</label>`, path: () => '/api/v1/random' },
  authors: { name: '找作者', main: ['q', '作者名，如 苏轼'], opts: () => apiInp('size', '条数', '20', 'number'), path: () => '/api/v1/authors' },
  author: { name: '作者详情', main: ['id', '作者 id，如 2692', 'number'], opts: () => apiInp('size', '每页作品数', '50', 'number'), path: v => '/api/v1/authors/' + encodeURIComponent(v.id || ''), skip: ['id'] },
  stats: { name: '统计', path: () => '/api/v1/stats' },
};
async function viewApiTest(qs) {
  setTitle('API 调试台');
  let cur = API_EP[qs.get('ep')] ? qs.get('ep') : 'search', page = +qs.get('page') || 1;
  const nav = NAV;
  app.innerHTML = `<div class="apit">${apiBar('test')}<div class="tabs"></div><form></form><div class="rq"></div><div class="res"></div><div class="raw"></div></div>`;
  const root = $('.apit'), F = $('form', root), T = $('.tabs', root), RQ = $('.rq', root), RS = $('.res', root), RW = $('.raw', root);
  const tabs = () => T.innerHTML = Object.entries(API_EP).map(([k, e]) => `<button type="button" data-k="${k}" class="${k === cur ? 'on' : ''}">${e.name}</button>`).join('');
  const form = (vals = {}) => {
    const e = API_EP[cur];
    F.innerHTML = `<div class="row">${e.main ? `<input name="${e.main[0]}" type="${e.main[2] || 'search'}" placeholder="${e.main[1]}" enterkeyhint="search" autocomplete="off">` : `<span class="mute" style="flex:1;align-self:center">${cur === 'random' ? '每次随机返回一首' : '收录总数与各朝代、体裁篇数'}</span>`}<button class="go">${cur === 'random' ? '再来一首' : '调用'}</button></div>${e.opts ? `<div class="opts">${e.opts()}</div>` : ''}`;
    for (const [k, v] of Object.entries(vals)) { const el = F.elements[k]; if (el) el.type === 'checkbox' ? el.checked = !!v : el.value = v; }
  };
  const values = () => { const o = {}; for (const el of F.elements) if (el.name && (el.type !== 'checkbox' || el.checked) && String(el.value).trim()) o[el.name] = String(el.value).trim(); return o; };
  const render = (j, ok) => {
    if (!j) return RS.innerHTML = '<div class="empty">返回的不是 JSON</div>';
    if (!ok || j.error) return RS.innerHTML = `<div class="empty">${esc(j.error ? j.error.message : '请求失败')}</div>`;
    const d = j.data, pager = (prev, next) => `<div class="pager">${prev ? '<button data-pg="-1">上一页</button>' : ''}${next ? '<button data-pg="1">下一页</button>' : ''}</div>`;
    const poem = d => `<div class="panel"><h2 style="margin:0">${esc(d.title)}</h2><p class="mute">〔${esc(d.dynasty || '')}〕<button class="lnk" data-a="${d.author_id}">${esc(d.author)}</button>${d.rhythmic ? ' · ' + esc(d.rhythmic) : ''}${d.book ? ' · ' + esc(d.book) + (d.chapter ? '·' + esc(d.chapter) : '') : ''} · ${esc(d.kind || '')} · id ${d.id}</p>${(d.paragraphs || []).map(x => `<p style="margin:4px 0">${esc(x)}</p>`).join('')}<p style="margin-top:10px"><a class="lnk" href="/s?q=${encodeURIComponent(d.title)}">在诗笺中查看 ›</a></p></div>`;
    if (cur === 'search') RS.innerHTML = d.length ? `<p class="mute" style="margin:6px 0">第 ${j.page} 页，本页 ${d.length} 条${j.has_more ? '，还有更多' : ''}</p>` + d.map(x => `<div class="item" data-p="${x.id}"><b>${esc(x.title)}</b> <span class="meta">〔${esc(x.dynasty || '')}〕${esc(x.author)} · ${esc(x.kind || '')} · id ${x.id}</span><div>${esc(x.excerpt || '')}</div></div>`).join('') + pager(j.page > 1, j.has_more) : '<div class="empty">没有结果</div>';
    else if (cur === 'poem' || cur === 'random') RS.innerHTML = d ? poem(d) : '<div class="empty">没有结果</div>';
    else if (cur === 'authors') RS.innerHTML = d.length ? d.map(x => `<div class="item" data-a="${x.id}"><b>${esc(x.name)}</b> <span class="meta">〔${esc(x.dynasty || '')}〕 · ${x.works} 篇 · id ${x.id}</span></div>`).join('') : '<div class="empty">没有找到作者</div>';
    else if (cur === 'author') RS.innerHTML = `<div class="panel"><h2 style="margin:0">${esc(d.name)}</h2><p class="mute">〔${esc(d.dynasty || '')}〕 · ${d.works} 篇 · id ${d.id}</p>${d.intro ? `<p>${esc(d.intro)}</p>` : ''}</div>` + (d.list || []).map(x => `<div class="item" data-p="${x.id}"><b>${esc(x.title)}</b> <span class="meta">${esc(x.kind || '')} · id ${x.id}</span></div>`).join('') + pager(d.page > 1, d.page * d.size < d.works);
    else if (cur === 'stats') { const by = {}; (d.by_era || []).forEach(r => { (by[r.era] = by[r.era] || {})[r.kind] = r.n; });
      RS.innerHTML = `<div class="panel"><div class="kv2"><b>作品</b><span>${(+d.works).toLocaleString()} 篇</span><b>作者</b><span>${(+d.authors).toLocaleString()} 位</span>${Object.entries(by).map(([e, k]) => `<b>${esc(e)}</b><span>${Object.entries(k).map(([a, n]) => `${esc(a)} ${(+n).toLocaleString()}`).join('　')}</span>`).join('')}</div></div>`; }
  };
  const API_BASE = location.origin;
  const call = async (p = 1) => {
    const e = API_EP[cur], v = values(); page = p;
    if (e.main && !v[e.main[0]]) { F.elements[e.main[0]].focus(); return; }
    const q = new URLSearchParams(); for (const [k, x] of Object.entries(v)) if (!(e.skip || []).includes(k)) q.set(k, x);
    if (p > 1) q.set('page', p);
    const url = e.path(v) + (q.toString() ? '?' + q : '');
    history.replaceState(null, '', '/api/test?' + new URLSearchParams({ ep: cur, ...v, ...(p > 1 ? { page: p } : {}) }));
    RQ.innerHTML = `<div class="req"><code>GET ${esc(url)}</code><span class="mute">请求中…</span></div>`; RS.innerHTML = RW.innerHTML = '';
    const t0 = performance.now(); let r, j, txt;
    try { r = await fetch(API_BASE + url, { headers: { accept: 'application/json' } }); txt = await r.text(); try { j = JSON.parse(txt); } catch (_) {} }
    catch (err) { if (nav === NAV) RQ.innerHTML = `<div class="req"><code>GET ${esc(url)}</code><span class="st bad">网络错误</span></div>`; return; }
    if (nav !== NAV) return;
    RQ.innerHTML = `<div class="req"><code>GET ${esc(url)}</code><span class="st ${r.ok ? '' : 'bad'}">${r.status}</span><span class="mute">${Math.round(performance.now() - t0)} ms</span><button type="button" class="lnk cp">复制链接</button><a class="lnk" href="${esc(API_BASE + url)}" target="_blank" rel="noopener">新窗口打开</a></div>`;
    $('.cp', RQ).onclick = ev => navigator.clipboard && navigator.clipboard.writeText(API_BASE + url).then(() => ev.target.textContent = '已复制');
    render(j, r.ok);
    RW.innerHTML = `<details${r.ok ? '' : ' open'}><summary class="mute" style="cursor:pointer;margin-top:12px">原始 JSON</summary><pre>${esc(j ? JSON.stringify(j, null, 2) : txt)}</pre></details>`;
  };
  const go = (k, vals) => { cur = k; tabs(); form(vals); call(); scrollTo(0, 0); };
  T.onclick = e => { const b = e.target.closest('button'); if (!b) return; cur = b.dataset.k; tabs(); form(); RQ.innerHTML = RS.innerHTML = RW.innerHTML = ''; history.replaceState(null, '', '/api/test?ep=' + cur); if (!API_EP[cur].main) call(); else F.elements[API_EP[cur].main[0]].focus(); };
  F.onsubmit = e => { e.preventDefault(); call(1); };
  RS.onclick = e => { const pg = e.target.closest('[data-pg]'); if (pg) return call(page + +pg.dataset.pg);
    const a = e.target.closest('[data-a]'); if (a) return go('author', { id: a.dataset.a });
    const p = e.target.closest('[data-p]'); if (p) return go('poem', { id: p.dataset.p }); };
  const init = Object.fromEntries([...qs].filter(([k]) => k !== 'ep' && k !== 'page'));
  tabs();
  if (qs.get('ep')) { form(init); if (!API_EP[cur].main || init[API_EP[cur].main[0]]) call(page); }
  else form({ q: '床前明月光' });
}

/* ---------- router ---------- */
let viewCleanup = [], routeCleanup = [], keyNav = null, NAV = 0;
document.addEventListener('keydown', e => keyNav && keyNav(e));
const pf = e => { const a = e.target.closest && e.target.closest('a[href^="/p/"]'); if (a) prefetchPoem(+a.getAttribute('href').slice(3)); };
document.addEventListener('touchstart', pf, { passive: true }); document.addEventListener('mouseover', pf);
$('#q').addEventListener('focus', () => { authors().catch(() => {}); pop().catch(() => {}); });
idle(() => setTimeout(() => { authors().catch(() => {}); pop().catch(() => {}); }, 2500));
if ('serviceWorker' in navigator) addEventListener('load', () => navigator.serviceWorker.register('/sw.js').catch(() => {}));
if (location.pathname === '/index.html') history.replaceState(null, '', '/' + location.search);
async function route() {
  viewCleanup.splice(0).forEach(f => f()); routeCleanup.splice(0).forEach(f => f()); keyNav = null; NAV++;
  if (location.hash.startsWith('#/')) return notFound();
  const h = location.pathname + location.search;
  const [path, qstr] = h.split('?'); const qs = new URLSearchParams(qstr || ''); const seg = path.split('/').filter(Boolean).map(decodeURIComponent);
  try {
    if (!seg.length) await viewHome();
    else if (seg[0] === 'p') await viewPoem(seg[1]);
    else if (seg[0] === 'c' && seg[1]) await viewColl(seg[1], qs);
    else if (seg[0] === 'c') await viewColls();
    else if (seg[0] === 'l') await viewList(seg[1]);
    else if (seg[0] === 'a') await viewAuthor(seg[1], seg.slice(2).join('/'));
    else if (seg[0] === 'authors') await viewAuthors(qs);
    else if (seg[0] === 's') await viewSearch(qs);
    else if (seg[0] === 'fav') await viewFav();
    else if (seg[0] === 'about') await viewAbout();
    else if (seg[0] === 'said') await viewSaid(qs);
    else if (seg[0] === 'api') await (seg[1] === 'test' ? viewApiTest(qs) : viewApi());
    else notFound();
  } catch (e) { console.error(e); app.innerHTML = `<div class="empty">加载失败，请检查网络后刷新。<br><small>${esc(e.message)}</small></div>`; }
}
let lastPath = '';
function go(u, rep) { u = String(u).replace(/^\/?#\//, '/'); if (u === location.pathname + location.search && !rep) return route(); history[rep ? 'replaceState' : 'pushState'](null, '', u); onNav(); }
function onNav() { const p = location.pathname; route(); if (p !== lastPath || !p.startsWith('/s')) window.scrollTo(0, 0); lastPath = p; }
window.addEventListener('popstate', onNav);
document.addEventListener('click', e => { if (e.defaultPrevented || e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return; const a = e.target.closest && e.target.closest('a[href]'); if (!a || a.target || a.hasAttribute('download')) return; const h = a.getAttribute('href'); if (!h.startsWith('/') || h.startsWith('//') || /^\/(api\/v1|data|fonts|vendor)(\/|$)|\.[a-z0-9]+(\?|$)/i.test(h)) return; e.preventDefault(); go(h); });
lastPath = location.pathname;
$('#qform').addEventListener('submit', e => { e.preventDefault(); const v = $('#q').value.trim(); if (v) { go('/s?q=' + encodeURIComponent(v)); $('#q').blur(); } });
$('#themeBtn').onclick = () => { const r = document.documentElement; const dark = r.dataset.theme ? r.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches; r.dataset.theme = dark ? 'light' : 'dark'; localStorage.setItem('shici.theme', r.dataset.theme); };
route();
})();
