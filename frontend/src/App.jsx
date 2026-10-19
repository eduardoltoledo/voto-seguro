import React, { useCallback, useEffect, useState } from 'react'
import { aoSessaoExpirar, definirToken, post, renovar } from './api.js'
import Entrar from './pages/Entrar.jsx'
import Cadastro from './pages/Cadastro.jsx'
import Eleitor from './pages/Eleitor.jsx'
import Conferir from './pages/Conferir.jsx'
import Admin from './pages/Admin.jsx'
import Auditoria from './pages/Auditoria.jsx'
import Monitor from './pages/Monitor.jsx'

const ROTULO = { ELEITOR: 'Eleitor', ADMIN: 'Mesário', AUDITOR: 'Fiscal' }

function useRota() {
  const ler = () => window.location.hash.replace(/^#\/?/, '') || ''
  const [rota, setRota] = useState(ler)
  useEffect(() => { const f = () => setRota(ler()); window.addEventListener('hashchange', f); return () => window.removeEventListener('hashchange', f) }, [])
  return [rota, r => { window.location.hash = '/' + r }]
}

export default function App() {
  const [sessao, setSessao] = useState(null)
  const [pronto, setPronto] = useState(false)
  const [rota, ir] = useRota()

  const sair = useCallback(async (silencioso) => {
    if (!silencioso) { try { await post('/auth/logout') } catch { /* já expirou */ } }
    definirToken(null); sessionStorage.clear(); setSessao(null); ir('')
  }, [])

  useEffect(() => {
    aoSessaoExpirar(() => { setSessao(null); ir('') })
    renovar().then(d => { if (d) setSessao(d) }).finally(() => setPronto(true))
  }, [])

  const entrou = d => { definirToken(d.access_token); setSessao(d); ir('') }
  if (!pronto) return <p className="carregando">Carregando…</p>

  let tela
  if (rota === 'cadastro') tela = <Cadastro voltar={() => ir('')} />
  else if (rota === 'conferir') tela = <Conferir />
  else if (!sessao) tela = <Entrar aoEntrar={entrou} irCadastro={() => ir('cadastro')} />
  else if (sessao.papel === 'ELEITOR') tela = <Eleitor />
  else {
    const abas = [...(sessao.papel === 'ADMIN' ? [['mesa', 'Mesa']] : []), ['auditoria', 'Auditoria'], ['monitor', 'Monitoramento']]
    const atual = abas.some(a => a[0] === rota) ? rota : abas[0][0]
    tela = (
      <>
        <nav className="abas" aria-label="Seções">
          {abas.map(([k, t]) => <a key={k} href={`#/${k}`} aria-current={atual === k ? 'page' : undefined}>{t}</a>)}
        </nav>
        {atual === 'mesa' && <Admin />}
        {atual === 'auditoria' && <Auditoria />}
        {atual === 'monitor' && <Monitor />}
      </>
    )
  }

  return (
    <>
      <a className="pular" href="#principal">Ir para o conteúdo</a>
      <header className="topo">
        <a className="marca" href="#/">Voto Seguro <span>Eleições 2026</span></a>
        <div className="topo-dir">
          <a href="#/conferir">Conferir recibo</a>
          {sessao && <>
            <span className="quem">{sessao.nome} · {ROTULO[sessao.papel]}</span>
            <button className="btn btn-leve" onClick={() => sair(false)}>Sair</button>
          </>}
        </div>
      </header>
      <main id="principal" className={sessao && sessao.papel !== 'ELEITOR' ? 'larga' : ''}>{tela}</main>
      <footer className="rodape">Projeto acadêmico – Segurança e Auditoria de Sistemas. Dados e candidatos fictícios.</footer>
    </>
  )
}
