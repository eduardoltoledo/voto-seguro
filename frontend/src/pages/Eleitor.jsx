import React, { useEffect, useState } from 'react'
import { get, post } from '../api.js'
import { Alerta, Copiavel } from '../ui.jsx'

// Etapas: carregando -> inicio -> escolha -> confirmar -> recibo
export default function Eleitor() {
  const [etapa, setEtapa] = useState('carregando')
  const [info, setInfo] = useState(null)
  const [cands, setCands] = useState([])
  const [digitos, setDigitos] = useState('')
  const [branco, setBranco] = useState(false)
  const [recibo, setRecibo] = useState(null)
  const [erro, setErro] = useState('')
  const [ocupado, setOcupado] = useState(false)

  const carregar = async () => {
    try {
      const [s, c] = await Promise.all([get('/votacao/situacao'), get('/votacao/candidatos')])
      setInfo(s); setCands(c.candidatos)
      // token já emitido mas voto não concluído (ex.: página recarregada)
      setEtapa(sessionStorage.getItem('token_voto') ? 'escolha' : 'inicio')
    } catch (e) { setErro(e.message); setEtapa('inicio') }
  }
  useEffect(() => { carregar() }, [])

  const escolhido = branco ? null : cands.find(c => String(c.numero) === digitos)

  const iniciar = async () => {
    setErro(''); setOcupado(true)
    try { const { token } = await post('/votacao/token'); sessionStorage.setItem('token_voto', token); setEtapa('escolha') }
    catch (e) { setErro(e.message) } finally { setOcupado(false) }
  }

  const confirmar = async () => {
    setErro(''); setOcupado(true)
    try {
      const r = await post('/votacao/votar', { token: sessionStorage.getItem('token_voto'),
        tipo: branco ? 'branco' : 'candidato', candidato_id: escolhido?.id ?? null })
      sessionStorage.removeItem('token_voto'); setRecibo(r); setEtapa('recibo')
    } catch (e) { setErro(e.message) } finally { setOcupado(false) }
  }

  const tecla = n => { setBranco(false); setDigitos(d => (d.length < 2 ? d + n : d)) }

  if (etapa === 'carregando') return <p className="carregando">Carregando…</p>

  if (etapa === 'inicio') return (
    <section className="cartao">
      <h1>Eleição para Presidente da República</h1>
      {info?.ja_votou ? <Alerta tipo="ok">Seu voto já foi registrado. Obrigado por participar. Guarde o recibo para conferir depois.</Alerta>
        : !info?.sessao_aberta ? <Alerta tipo="aviso">A votação não está aberta no momento.</Alerta>
        : !info?.elegivel ? <Alerta>Seu título não está apto a votar nesta sessão.</Alerta>
        : <>
          <p>Seu voto é secreto: depois que você iniciar, o sistema separa sua identidade do seu voto. Ninguém, nem o administrador do banco de dados, consegue ligar um ao outro.</p>
          <Alerta>{erro}</Alerta>
          <button className="btn btn-primario grande" onClick={iniciar} disabled={ocupado}>Iniciar votação</button>
        </>}
      <p className="rodape-cartao"><a href="#/conferir">Já votou? Confira seu recibo</a></p>
    </section>
  )

  if (etapa === 'recibo') return (
    <section className="cartao">
      <h1>Voto registrado</h1>
      <div className="comprovante">
        <h2>Comprovante de votação</h2>
        <dl>
          <dt>Código do recibo</dt><dd className="segredo">{recibo.recibo}</dd>
          <dt>Posição na urna</dt><dd>{recibo.posicao}</dd>
          <dt>Hash do registro</dt><dd className="mono">{recibo.hash}</dd>
        </dl>
        <Copiavel valor={recibo.recibo} rotulo="Copiar código" />
      </div>
      <Alerta tipo="aviso">Anote o código do recibo agora. Ele é a única prova do seu voto e não pode ser recuperado. Ele não revela em quem você votou.</Alerta>
      <p><a href="#/conferir">Conferir se meu voto foi contado</a></p>
    </section>
  )

  // escolha e confirmação: tela inspirada na urna
  const confirmando = etapa === 'confirmar'
  return (
    <section className="urna" aria-labelledby="t-urna">
      <h1 id="t-urna">Presidente da República</h1>
      <div className="tela">
        <div className="seu-voto">Seu voto para</div>
        <div className="numero" aria-live="polite">
          {[0, 1].map(i => <span key={i} className="digito">{branco ? '' : digitos[i] || ''}</span>)}
        </div>
        {branco ? <p className="nome-cand">VOTO EM BRANCO</p>
          : escolhido ? <div className="dados"><p className="nome-cand">{escolhido.nome}</p><p>{escolhido.partido}</p></div>
          : digitos.length === 2 ? <p className="nome-cand nulo">Número inexistente. Corrija ou escolha outro.</p>
          : <p className="dica-tela">Digite o número do candidato ou escolha na lista.</p>}
      </div>

      {!confirmando && <>
        <ul className="lista-cands">
          {cands.map(c => (
            <li key={c.id}><button onClick={() => { setBranco(false); setDigitos(String(c.numero)) }}
              aria-pressed={!branco && digitos === String(c.numero)}>
              <b>{c.numero}</b><span>{c.nome}<small>{c.partido}</small></span></button></li>))}
        </ul>
        <div className="teclado" role="group" aria-label="Teclado numérico">
          {[1, 2, 3, 4, 5, 6, 7, 8, 9, 0].map(n => <button key={n} onClick={() => tecla(n)}>{n}</button>)}
        </div>
      </>}

      <Alerta>{erro}</Alerta>
      <div className="acoes-urna">
        {!confirmando ? <>
          <button className="u-branco" onClick={() => { setBranco(true); setDigitos('') }}>BRANCO</button>
          <button className="u-corrige" onClick={() => { setBranco(false); setDigitos('') }}>CORRIGE</button>
          <button className="u-confirma" disabled={!branco && !escolhido} onClick={() => { setErro(''); setEtapa('confirmar') }}>CONFIRMA</button>
        </> : <>
          <button className="u-corrige" onClick={() => setEtapa('escolha')} disabled={ocupado}>VOLTAR</button>
          <button className="u-confirma" onClick={confirmar} disabled={ocupado}>{ocupado ? 'ENVIANDO…' : 'CONFIRMAR VOTO'}</button>
        </>}
      </div>
      {confirmando && <p className="aviso-final">Depois de confirmar, o voto não pode ser alterado.</p>}
    </section>
  )
}
