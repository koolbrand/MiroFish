import { ref, computed } from 'vue'

/**
 * Ejemplos de la portada: cinco situaciones distintas para que cada visitante se reconozca en alguna.
 * Todo es inventado (escenario, cifras, frases) y está rotulado como ejemplo en la interfaz.
 *
 * Cada caso alimenta dos piezas a la vez —«La multitud» (120 personas que cambian de opinión) y el informe de
 * ejemplo (gráfico, grupos, entrevista)— y las dos cuentan lo mismo: el reparto final de la multitud es el
 * del último punto del gráfico. Los textos viven en `home.cases.<id>.*` (es/en/zh).
 *
 * final   → personas de las 120 que acaban a favor / dudando / en contra (suman 120)
 * favor / against → % a favor y en contra en las rondas R0…R10 (el resto, indecisos); el último punto es el final
 * groups  → % a favor / dudando / en contra por grupo (el informe)
 * look    → aspecto de la Bianka que da la entrevista
 */
export const CASES = [
  {
    id: 'padel',
    final: { favor: 46, undecided: 49, against: 25 },
    favor: [8, 14, 12, 19, 17, 26, 24, 31, 29, 35, 38],
    against: [5, 4, 11, 10, 17, 14, 19, 16, 20, 19, 21],
    groups: [{ f: 58, u: 27, a: 15 }, { f: 34, u: 41, a: 25 }, { f: 22, u: 38, a: 40 }],
    look: { ears: 'flop', head: 'beanie', body: 'coffee' },
  },
  {
    id: 'b2b',
    final: { favor: 52, undecided: 48, against: 20 },
    favor: [9, 14, 18, 22, 26, 30, 33, 36, 39, 41, 43],
    against: [4, 5, 6, 8, 9, 11, 12, 14, 15, 16, 17],
    groups: [{ f: 62, u: 24, a: 14 }, { f: 41, u: 38, a: 21 }, { f: 18, u: 37, a: 45 }],
    look: { ears: 'up', face: 'glasses', body: 'tie' },
  },
  {
    id: 'precio',
    final: { favor: 24, undecided: 46, against: 50 },
    favor: [10, 12, 13, 15, 16, 17, 18, 19, 19, 20, 20],
    against: [8, 14, 20, 25, 28, 31, 34, 37, 39, 41, 42],
    groups: [{ f: 34, u: 38, a: 28 }, { f: 14, u: 33, a: 53 }, { f: 12, u: 45, a: 43 }],
    look: { ears: 'flop', head: 'cap', body: 'scarf' },
  },
  {
    id: 'crisis',
    final: { favor: 41, undecided: 55, against: 24 },
    favor: [6, 9, 14, 18, 22, 25, 28, 30, 32, 33, 34],
    against: [4, 8, 12, 14, 16, 17, 18, 19, 20, 20, 20],
    groups: [{ f: 49, u: 36, a: 15 }, { f: 21, u: 45, a: 34 }, { f: 31, u: 42, a: 27 }],
    look: { ears: 'flop', head: 'bun', body: 'baby' },
  },
  {
    id: 'publico',
    final: { favor: 38, undecided: 30, against: 52 },
    favor: [15, 18, 22, 25, 27, 28, 30, 30, 31, 32, 32],
    against: [6, 12, 18, 24, 29, 33, 37, 39, 41, 42, 43],
    groups: [{ f: 18, u: 22, a: 60 }, { f: 58, u: 24, a: 18 }, { f: 20, u: 30, a: 50 }],
    look: { ears: 'up', head: 'hardhat', body: 'stripes' },
  },
]

export const CASE_IDS = CASES.map(c => c.id)
export const byId = (id) => CASES.find(c => c.id === id) || CASES[0]

// El caso elegido es de toda la página: las pestañas de «La multitud» y las del informe van a la vez.
const current = ref(CASES[0].id)

export function useExampleCase() {
  return {
    currentId: current,
    current: computed(() => byId(current.value)),
    select: (id) => { if (CASE_IDS.includes(id)) current.value = id },
  }
}
