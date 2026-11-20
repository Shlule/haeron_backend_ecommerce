// Atelier : instruments et pièces fabriqués, leur historique, et ce dont les formulaires ont besoin.

export interface OptionGroup {
  id: string
  name: string
  values: { id: string, name: string, code: string, priceDelta: number }[]
}

export interface FormPartModel {
  id: string
  name: string
  code: string
  status: string
  partType: string
  activeBatch: { id: string, name: string, code: string } | null
  options: OptionGroup[]
}

export interface ProductionForm {
  eventTypes: { value: string, label: string }[]
  factories: { id: string, name: string, code: string }[]
  instrumentTypes: { id: string, name: string, code: string }[]
  instrumentModels: { id: string, name: string, instrumentType: string }[]
  partModels: FormPartModel[]
  freeParts: { id: string, serialNumber: string, partModelId: string, partModel: string }[]
  orders: {
    id: string
    reference: string
    customer: string
    email: string
    accountEmail: string | null
    items: { index: number, name: string, parts: { component: string, partModelId: string, optionIds: string[] }[] }[]
  }[]
}

export interface HistoryEvent {
  id: string
  eventType: string
  eventLabel: string
  title: string
  description: string
  createdAt: string
  author: string
  part: { id: string, serialNumber: string, partModel: string } | null
}

export interface PartRow {
  id: string
  serialNumber: string
  partModel: { id: string, name: string, code: string }
  partType: string
  isMaster: boolean
  status: string
  soldAt: string | null
  description: string
  options: { option: string, value: string }[]
  batch: { name: string, code: string }
  createdAt: string
  instrument: { id: string, model: string } | null
  owner: string | null
}

export interface PartSheet extends PartRow {
  history: HistoryEvent[]
}

export interface InstrumentSheet {
  id: string
  serialNumber: string
  model: string
  instrumentType: string
  owner: string | null
  description: string
  status: string
  soldAt: string | null
  configuration: { source?: string, orderId?: string, reference?: string, product?: string }
  createdAt: string
  parts: PartRow[]
  history: HistoryEvent[]
}

// une ligne de pièce dans les formulaires : nouvelle pièce à fabriquer, ou pièce déjà fabriquée
export interface PartLine {
  key: number
  existingPartId: string | null
  partModelId: string | null
  optionIds: string[]
  description: string
  component?: string
}

// vendu ou non : vendre un instrument vend aussi ses pièces
export const saleStatusOptions = [
  { value: 'in_stock', label: 'En stock', type: 'default' as const },
  { value: 'reserved', label: 'Réservé', type: 'warning' as const },
  { value: 'sold', label: 'Vendu', type: 'success' as const },
]

export function saleStatusOf(value: string) {
  return saleStatusOptions.find(s => s.value === value) ?? { value, label: value, type: 'default' as const }
}

export const PRODUCTION_FORM = 'query { backoffice { productionForm } }'

export async function loadProductionForm() {
  const { backoffice } = await gql<{ backoffice: { productionForm: ProductionForm } }>(PRODUCTION_FORM)
  return backoffice.productionForm
}

export function errorText(e: unknown) {
  return e instanceof Error ? e.message : String(e)
}

const eventColors: Record<string, 'default' | 'info' | 'success' | 'warning' | 'error'> = {
  fabrication: 'info',
  assemblage: 'info',
  controle: 'success',
  reglage: 'default',
  reparation: 'warning',
  modification: 'warning',
  vente: 'success',
  transfert: 'default',
}

export function eventColor(type: string) {
  return eventColors[type] ?? 'default'
}

export const dateTimeFormat = new Intl.DateTimeFormat('fr-FR', { dateStyle: 'medium', timeStyle: 'short' })
