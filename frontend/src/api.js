// Cliente da API. O access token (JWT curto) vive só em memória; o refresh token é cookie HttpOnly.
let accessToken = null
let aoExpirar = () => {}

export const definirToken = t => { accessToken = t }
export const aoSessaoExpirar = fn => { aoExpirar = fn }

const lerCookie = nome => document.cookie.split('; ').find(c => c.startsWith(nome + '='))?.split('=')[1]

export class ErroApi extends Error {
  constructor(status, detail) { super(typeof detail === 'string' ? detail : 'Erro na requisição'); this.status = status }
}

async function bruto(caminho, { metodo = 'GET', corpo, extra = {} } = {}) {
  const headers = { Accept: 'application/json', ...extra }
  if (corpo !== undefined) headers['Content-Type'] = 'application/json'
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`
  return fetch('/api' + caminho, { method: metodo, headers, credentials: 'same-origin',
    body: corpo !== undefined ? JSON.stringify(corpo) : undefined })
}

async function ler(r) {
  if (r.status === 204) return null
  let d = null
  try { d = await r.json() } catch { /* corpo vazio */ }
  if (!r.ok) {
    const detail = Array.isArray(d?.detail) ? d.detail.map(x => x.msg).join('; ') : d?.detail
    throw new ErroApi(r.status, detail || 'Falha na requisição')
  }
  return d
}

export async function renovar() {
  const r = await fetch('/api/auth/refresh', { method: 'POST', credentials: 'same-origin',
    headers: { 'X-CSRF-Token': lerCookie('csrf_token') || '' } })
  if (!r.ok) return null
  const d = await r.json()
  accessToken = d.access_token
  return d
}

export async function api(caminho, opcoes) {
  let r = await bruto(caminho, opcoes)
  if (r.status === 401 && accessToken) {           // access token expirou: tenta renovar uma vez
    const nova = await renovar()
    if (nova) r = await bruto(caminho, opcoes)
    else { accessToken = null; aoExpirar() }
  }
  return ler(r)
}

export const get = c => api(c)
export const post = (c, corpo) => api(c, { metodo: 'POST', corpo: corpo ?? {} })
