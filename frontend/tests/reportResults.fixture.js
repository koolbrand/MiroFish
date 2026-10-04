// Informe inventado para pruebas. No contiene datos de clientes ni encuestados.
const ref = { section_index: 1, section_title: 'Conclusiones del ensayo ficticio', quote: 'La claridad de las condiciones reduce la fricción de la propuesta.' }
const trustRef = { ...ref, quote: 'Las voces simuladas plantean dudas sobre la continuidad de la propuesta.' }
const interestRef = { ...ref, quote: 'La propuesta despierta interés entre las voces del ensayo ficticio.' }
const limitRef = { ...ref, quote: 'El ensayo ficticio no demuestra demanda real ni ventas futuras.' }
export const resultsFixture = () => ({ version: 2, status: 'ready', report_sha256: 'a'.repeat(64), locale: 'es', data: {
  headline: { text: ref.quote, refs: [ref] },
  findings: [
    { id: 'clarity', text: ref.quote, refs: [ref] },
    { id: 'trust', text: trustRef.quote, refs: [trustRef] }
  ],
  contrasts: [{ id: 'positions', left: interestRef.quote, right: trustRef.quote, refs: [interestRef, trustRef] }],
  limitations: [{ text: limitRef.quote, refs: [limitRef] }]
} })
