import React, { useState } from 'react'
import { post } from '../api.js'
import { Alerta, Campo } from '../ui.jsx'

export default function Conferir() {
  const [codigo, setCodigo] = useState('')
  const [res, setRes] = useState(null)
  const [erro, setErro] = useState('')

  const enviar = async e => {
    e.preventDefault(); setErro(''); setRes(null)
    try { setRes(await post('/votacao/recibo/verificar', { recibo: codigo.trim() })) } catch (x) { setErro(x.message) }
  }
  return (
    <section className="cartao estreito">
      <h1>Conferir recibo</h1>
      <p>Informe o código do seu comprovante. Você verá se o voto está na urna e em que posição, sem que ninguém possa saber em quem você votou.</p>
      <form onSubmit={enviar}>
        <Campo rotulo="Código do recibo" value={codigo} onChange={e => setCodigo(e.target.value)} required minLength={20} autoComplete="off" />
        <Alerta>{erro}</Alerta>
        <button className="btn btn-primario">Conferir</button>
      </form>
      {res && (res.encontrado
        ? <Alerta tipo="ok">Seu voto foi computado: posição {res.posicao} da sessão {res.sessao_id}.
            <span className="mono bloco">hash {res.hash}</span><span className="mono bloco">anterior {res.hash_anterior}</span></Alerta>
        : <Alerta tipo="aviso">Nenhum voto encontrado com esse código. Confira se digitou corretamente.</Alerta>)}
    </section>
  )
}
