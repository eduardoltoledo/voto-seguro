import React, { useEffect, useState } from 'react'
import { get } from '../api.js'
import { Alerta, Selo } from '../ui.jsx'

export default function Monitor() {
  const [s, setS] = useState(null)
  const [erro, setErro] = useState('')
  useEffect(() => {
    const ler = () => get('/monitor/status').then(setS).catch(e => setErro(e.message))
    ler(); const t = setInterval(ler, 5000); return () => clearInterval(t)
  }, [])
  if (!s) return <><h1>Monitoramento</h1><Alerta>{erro}</Alerta></>
  const prim = s.banco_primario, rep = s.banco_replica
  return (
    <>
      <h1>Monitoramento e redundância</h1>
      <Alerta>{erro}</Alerta>
      <p className="nota">Atualiza a cada 5 s. Você está conectado à instância <b>{s.instancia_atual}</b>.</p>
      <section className="grade">
        <div className="cartao"><h2>Instâncias do backend</h2>
          <ul className="nos">{s.nos_backend.length ? s.nos_backend.map(n => <li key={n.url}>
            <Selo ok={n.online} textoOk="no ar" textoErro="fora do ar" /> <b>{n.instancia || n.url}</b></li>) : <li>Nenhum nó configurado.</li>}</ul>
          <p className="nota">Se uma instância cair, o balanceador envia as requisições às demais.</p></div>
        <div className="cartao"><h2>Banco de dados</h2>
          <p><Selo ok={prim.online} textoOk="no ar" textoErro="fora do ar" /> Primário</p>
          {prim.replicas && <ul>{prim.replicas.length ? prim.replicas.map(r => <li key={r.nome}>Réplica <b>{r.nome}</b>: {r.estado}, atraso {r.atraso_s}s</li>) : <li>Nenhuma réplica conectada ao primário.</li>}</ul>}
          {rep.configurado
            ? <p><Selo ok={rep.online} textoOk="no ar" textoErro="fora do ar" /> Réplica de leitura{rep.online && rep.atraso_s != null ? ` · atraso ${rep.atraso_s.toFixed(2)}s` : ''}</p>
            : <p>Réplica de leitura não configurada.</p>}
          <p className="nota">Leituras (candidatos, logs) usam a réplica; se ela falhar, o sistema volta ao primário sem interromper.</p></div>
      </section>
    </>
  )
}
