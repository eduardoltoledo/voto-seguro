import React, { useState } from 'react'

export function Alerta({ tipo = 'erro', children }) {
  if (!children) return null
  return <div className={`alerta alerta-${tipo}`} role={tipo === 'erro' ? 'alert' : 'status'}>{children}</div>
}

export function Campo({ rotulo, dica, ...props }) {
  return (
    <label className="campo">
      <span className="campo-rotulo">{rotulo}</span>
      <input {...props} />
      {dica && <span className="campo-dica">{dica}</span>}
    </label>
  )
}

export function Copiavel({ valor, rotulo = 'Copiar' }) {
  const [ok, setOk] = useState(false)
  return (
    <button type="button" className="btn btn-leve" onClick={async () => {
      try { await navigator.clipboard.writeText(valor); setOk(true); setTimeout(() => setOk(false), 1500) } catch { /* sem permissão */ }
    }}>{ok ? 'Copiado' : rotulo}</button>
  )
}

export const hora = iso => iso ? new Date(iso.endsWith('Z') || iso.includes('+') ? iso : iso + 'Z').toLocaleString('pt-BR') : '—'
export const curto = (h, n = 10) => h ? `${h.slice(0, n)}…${h.slice(-6)}` : '—'

export function Selo({ ok, textoOk = 'Íntegra', textoErro = 'Violação detectada' }) {
  return <span className={`selo ${ok ? 'selo-ok' : 'selo-erro'}`}>{ok ? textoOk : textoErro}</span>
}
