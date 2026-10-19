import React, { useEffect, useState } from 'react'
import { get } from '../api.js'
import { Alerta, Selo, curto, hora } from '../ui.jsx'

const GRAVES = new Set(['TENTATIVA_VOTO_DUPLICADO', 'TENTATIVA_VOTO_REJEITADA', 'REFRESH_REUTILIZADO', 'FECHAMENTO_ABORTADO'])

export default function Auditoria() {
  const [logs, setLogs] = useState([])
  const [integ, setInteg] = useState(null)
  const [rel, setRel] = useState(null)
  const [filtro, setFiltro] = useState('')
  const [erro, setErro] = useState('')
  const [verificando, setVerificando] = useState(false)

  const carregarLogs = () => get('/auditoria/logs?limite=100' + (filtro ? `&evento=${encodeURIComponent(filtro)}` : '')).then(setLogs).catch(e => setErro(e.message))
  useEffect(() => { carregarLogs() }, [filtro])
  useEffect(() => { get('/auditoria/relatorio').then(setRel).catch(e => setErro(e.message)) }, [])

  const verificar = async () => {
    setVerificando(true); setErro('')
    try { setInteg(await get('/auditoria/verificar')) } catch (e) { setErro(e.message) } finally { setVerificando(false) }
  }
  const baixar = () => {
    const blob = new Blob([JSON.stringify({ gerado_em: new Date().toISOString(), relatorio: rel, verificacao: integ }, null, 2)], { type: 'application/json' })
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'relatorio-auditoria.json'; a.click(); URL.revokeObjectURL(a.href)
  }

  return (
    <>
      <h1>Auditoria</h1>
      <Alerta>{erro}</Alerta>
      <section className="cartao">
        <h2>Verificação de integridade</h2>
        <p>Recalcula todos os hashes da cadeia de votos e da trilha de eventos e confere contagens e âncoras de fechamento.</p>
        <button className="btn btn-primario" onClick={verificar} disabled={verificando}>{verificando ? 'Verificando…' : 'Verificar agora'}</button>
        {rel && <button className="btn btn-leve" onClick={baixar}>Baixar relatório (JSON)</button>}
        {integ && <div className="resultado-integ">
          <p>Resultado geral: <Selo ok={integ.ok} /></p>
          <ul>
            <li>Cadeia de eventos: <Selo ok={integ.cadeia_logs.ok} /> ({integ.cadeia_logs.total} registros){!integ.cadeia_logs.ok && ` – quebra no registro #${integ.cadeia_logs.quebra_em_seq}: ${integ.cadeia_logs.motivo}`}</li>
            {integ.sessoes.map(s => <li key={s.sessao_id}>Sessão {s.sessao_id} ({s.status}): votos <Selo ok={s.cadeia_votos.ok} /> ({s.cadeia_votos.total} votos)
              {!s.cadeia_votos.ok && ` – quebra na posição ${s.cadeia_votos.quebra_em_seq}: ${s.cadeia_votos.motivo}`}
              {s.ancora && <> · âncora de fechamento <Selo ok={s.ancora.ok} textoOk="confere" textoErro="diverge" /></>}
              {s.conciliacao && <> · conciliação <Selo ok={s.conciliacao.ok} textoOk="confere" textoErro="diverge" /></>}</li>)}
          </ul>
        </div>}
      </section>

      {rel && <section className="cartao">
        <h2>Resumo para fiscais</h2>
        <table className="tabela"><thead><tr><th>Sessão</th><th>Situação</th><th>Abertura</th><th>Fechamento</th><th className="n">Votos</th></tr></thead>
          <tbody>{rel.sessoes.map(s => <tr key={s.sessao_id}><td>{s.sessao_id} – {s.titulo}</td><td>{s.status}</td><td>{hora(s.aberta_em)}</td><td>{hora(s.fechada_em)}</td><td className="n">{s.total_votos}</td></tr>)}</tbody></table>
        <p className="nota">Eleitores cadastrados: {rel.eleitores_cadastrados} · Eventos: {Object.entries(rel.eventos).map(([k, v]) => `${k} (${v})`).join(', ') || 'nenhum'}</p>
      </section>}

      <section className="cartao">
        <h2>Trilha de eventos</h2>
        <label className="campo curto"><span className="campo-rotulo">Filtrar por evento</span>
          <select value={filtro} onChange={e => setFiltro(e.target.value)}>
            <option value="">Todos</option>
            {['LOGIN_FALHA', 'LOGIN_SUCESSO', 'MFA_FALHA', 'TOKEN_EMITIDO', 'TENTATIVA_VOTO_DUPLICADO', 'TENTATIVA_VOTO_REJEITADA', 'SESSAO_ABERTA', 'SESSAO_FECHADA', 'ELEITOR_CADASTRADO', 'REFRESH_REUTILIZADO']
              .map(e => <option key={e}>{e}</option>)}
          </select></label>
        <div className="rolagem"><table className="tabela"><thead><tr><th className="n">#</th><th>Data/hora</th><th>Evento</th><th>Ator</th><th>IP</th><th>Detalhes</th><th>Hash</th></tr></thead>
          <tbody>{logs.map(l => <tr key={l.seq} className={GRAVES.has(l.evento) ? 'grave' : ''}>
            <td className="n">{l.seq}</td><td>{hora(l.ts)}</td><td>{l.evento}</td><td>{l.ator_tipo ? `${l.ator_tipo} ${l.ator_id ?? ''}` : '—'}</td>
            <td>{l.ip || '—'}</td><td className="mono">{l.detalhes === '{}' ? '' : l.detalhes}</td><td className="mono">{curto(l.hash, 8)}</td></tr>)}</tbody></table></div>
      </section>
    </>
  )
}
