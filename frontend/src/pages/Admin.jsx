import React, { useCallback, useEffect, useState } from 'react'
import { get, post } from '../api.js'
import { Alerta, Selo, hora } from '../ui.jsx'

export default function Admin() {
  const [p, setP] = useState(null)
  const [bol, setBol] = useState(null)
  const [erro, setErro] = useState('')
  const [titulo, setTitulo] = useState('Eleição Presidencial 2026 - 1º turno')
  const [ocupado, setOcupado] = useState(false)

  const carregar = useCallback(async () => {
    try {
      const d = await get('/admin/painel'); setP(d)
      if (d.sessao?.status === 'FECHADA') setBol(await get(`/admin/boletim/${d.sessao.id}`)); else setBol(null)
    } catch (e) { setErro(e.message) }
  }, [])
  useEffect(() => { carregar(); const t = setInterval(carregar, 10000); return () => clearInterval(t) }, [carregar])

  const agir = async (fn) => { setErro(''); setOcupado(true); try { await fn(); await carregar() } catch (e) { setErro(e.message) } finally { setOcupado(false) } }
  const aberta = p?.sessao?.status === 'ABERTA'

  return (
    <>
      <h1>Mesa de votação</h1>
      <Alerta>{erro}</Alerta>
      {p && <section className="grade">
        <div className="cartao"><h2>Sessão</h2>
          {p.sessao ? <><p><b>{p.sessao.titulo}</b></p>
            <p><Selo ok={aberta} textoOk="Aberta" textoErro="Fechada" /></p>
            <p>Abertura: {hora(p.sessao.aberta_em)}<br />Fechamento: {hora(p.sessao.fechada_em)}</p></> : <p>Nenhuma sessão criada.</p>}
          {aberta
            ? <button className="btn btn-perigo" disabled={ocupado} onClick={() => confirm('Fechar a votação? Esta ação encerra a sessão e gera o boletim.') && agir(() => post('/admin/sessao/fechar').then(setBol))}>Fechar votação e apurar</button>
            : <>
              <label className="campo"><span className="campo-rotulo">Título da nova sessão</span>
                <input value={titulo} onChange={e => setTitulo(e.target.value)} maxLength={120} /></label>
              <button className="btn btn-primario" disabled={ocupado || titulo.length < 3} onClick={() => agir(() => post('/admin/sessao/abrir', { titulo }))}>Abrir nova sessão</button>
            </>}
        </div>
        <div className="cartao"><h2>Participação</h2>
          <dl className="numeros">
            <div><dt>Eleitores cadastrados</dt><dd>{p.eleitores_cadastrados}</dd></div>
            <div><dt>Já iniciaram a votação</dt><dd>{p.eleitores_que_votaram}</dd></div>
            <div><dt>Votos registrados</dt><dd>{p.votos_registrados}</dd></div>
          </dl>
          <p className="nota">Resultados por candidato ficam ocultos até o fechamento.</p>
        </div>
      </section>}

      {bol && <section className="cartao">
        <h2>Boletim de urna – sessão {bol.sessao_id}</h2>
        <p>Assinatura do boletim: <Selo ok={bol.assinatura_valida} textoOk="válida" textoErro="inválida" /> · Fechada em {hora(bol.fechada_em)}</p>
        <table className="tabela"><thead><tr><th>Nº</th><th>Candidato</th><th>Partido</th><th className="n">Votos</th><th className="n">% válidos</th></tr></thead>
          <tbody>{bol.resultado.candidatos.map(c => <tr key={c.numero}><td>{c.numero}</td><td>{c.nome}</td><td>{c.partido}</td><td className="n">{c.votos}</td><td className="n">{c.percentual_validos.toFixed(2)}%</td></tr>)}
            <tr><td></td><td>Em branco</td><td></td><td className="n">{bol.resultado.brancos}</td><td></td></tr></tbody>
          <tfoot><tr><td></td><td colSpan="2">Total de votos</td><td className="n">{bol.resultado.total_votos}</td><td></td></tr></tfoot></table>
        <p className="mono bloco">hash final da cadeia: {bol.hash_final}</p>
        <p>Conciliação (votos × tokens usados): <Selo ok={bol.conciliacao.ok} textoOk="confere" textoErro="diverge" /></p>
      </section>}
    </>
  )
}
