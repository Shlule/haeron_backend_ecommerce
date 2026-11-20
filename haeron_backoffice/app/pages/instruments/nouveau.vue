<script setup lang="ts">
/*
 * Nouvel instrument : modèle, atelier, propriétaire, description, puis sa composition.
 * La composition peut venir d'une ligne de commande (pièces et options du configurateur, à ajuster)
 * ou être saisie à la main ; chaque pièce est neuve (fabriquée ici, avec son numéro) ou déjà fabriquée.
 * Une pièce est la pièce maîtresse : son numéro de série devient celui de l'instrument.
 */
import type { PartLine, ProductionForm } from '~/utils/production'
import { NAlert, NButton, NFormItem, NInput, NRadio, NSelect, NSpin, NTag, useMessage } from 'naive-ui'

useHead({ title: 'Nouvel instrument · Haeron Back-office' })

const message = useMessage()

const form = ref<ProductionForm | null>(null)
const loading = ref(true)
const loadError = ref<string | null>(null)

async function load() {
  loading.value = true
  loadError.value = null
  try {
    form.value = await loadProductionForm()
  }
  catch (e) {
    loadError.value = errorText(e)
  }
  finally {
    loading.value = false
  }
}
onMounted(load)

let nextKey = 1
function newLine(values: Partial<PartLine> = {}): PartLine {
  return { key: nextKey++, existingPartId: null, partModelId: null, optionIds: [], description: '', ...values }
}

const orderId = ref<string | null>(null)
const orderItemIndex = ref<number | null>(null)
const instrumentModelId = ref<string | null>(null)
const factoryId = ref<string | null>(null)
const ownerEmail = ref('')
const description = ref('')
const lines = ref<PartLine[]>([newLine()])
const masterKey = ref<number>(lines.value[0]!.key)
// un instrument fait pour une commande est déjà vendu ; sinon il part en stock
const saleStatus = ref('in_stock')
watch(orderItemIndex, (index) => {
  saleStatus.value = index === null ? 'in_stock' : 'sold'
})

watch(form, (value) => {
  if (value?.factories.length === 1)
    factoryId.value = value.factories[0]!.id
})

const order = computed(() => form.value?.orders.find(o => o.id === orderId.value) ?? null)

// une ligne de commande remplit la composition avec ses pièces à fabriquer
function useOrderItem(index: number | null) {
  orderItemIndex.value = index
  const item = order.value?.items.find(i => i.index === index)
  if (!item)
    return
  // commande passée avec un compte client : il devient le propriétaire (une commande invité n'en a pas)
  if (!ownerEmail.value && order.value?.accountEmail)
    ownerEmail.value = order.value.accountEmail
  if (item.parts.length) {
    lines.value = item.parts.map(p => newLine({ partModelId: p.partModelId, optionIds: p.optionIds, component: p.component }))
    masterKey.value = lines.value[0]!.key
  }
}
function setOrder(id: string | null) {
  orderId.value = id
  orderItemIndex.value = null
  const items = form.value?.orders.find(o => o.id === id)?.items ?? []
  if (items.length === 1)
    useOrderItem(items[0]!.index)
}

function addLine(existing: boolean) {
  lines.value.push(newLine(existing ? { existingPartId: '' } : {}))
}
function removeLine(key: number) {
  lines.value = lines.value.filter(l => l.key !== key)
  if (masterKey.value === key && lines.value.length)
    masterKey.value = lines.value[0]!.key
}

// une pièce déjà fabriquée ne peut être choisie qu'une fois
function freePartOptions(line: PartLine) {
  const taken = new Set(lines.value.filter(l => l.key !== line.key).map(l => l.existingPartId))
  return (form.value?.freeParts ?? [])
    .filter(p => !taken.has(p.id))
    .map(p => ({ value: p.id, label: `${p.serialNumber} · ${p.partModel}` }))
}

function onBatchCreated(partModelId: string, batch: { id: string, name: string, code: string }) {
  const model = form.value?.partModels.find(pm => pm.id === partModelId)
  if (model)
    model.activeBatch = batch
}

const missing = computed(() => {
  if (!instrumentModelId.value)
    return 'Choisis le modèle d\'instrument.'
  if (!factoryId.value)
    return 'Choisis l\'atelier.'
  if (!lines.value.length)
    return 'Ajoute au moins une pièce.'
  if (lines.value.some(l => l.existingPartId === '' || (l.existingPartId === null && !l.partModelId)))
    return 'Chaque ligne doit avoir un modèle de pièce ou une pièce existante.'
  const noBatch = lines.value.find(l => l.existingPartId === null && !form.value?.partModels.find(pm => pm.id === l.partModelId)?.activeBatch)
  if (noBatch)
    return 'Une pièce neuve n\'a pas de lot actif : crée le lot dans sa ligne.'
  return null
})

const saving = ref(false)
async function submit() {
  if (missing.value)
    return
  saving.value = true
  try {
    const { backoffice } = await gql<{ backoffice: { buildInstrument: { id: string, serialNumber: string } } }>(
      'mutation ($data: BoBuildInstrumentInput!) { backoffice { buildInstrument(data: $data) } }',
      {
        data: {
          instrumentModelId: instrumentModelId.value,
          factoryId: factoryId.value,
          ownerEmail: ownerEmail.value.trim() || null,
          description: description.value,
          orderId: orderItemIndex.value === null ? null : orderId.value,
          orderItemIndex: orderItemIndex.value,
          status: saleStatus.value,
          masterIndex: lines.value.findIndex(l => l.key === masterKey.value),
          parts: lines.value.map(l => l.existingPartId
            ? { existingPartId: l.existingPartId }
            : { partModelId: l.partModelId, optionIds: l.optionIds, description: l.description }),
        },
      },
    )
    message.success(`Instrument ${backoffice.buildInstrument.serialNumber} créé`)
    await navigateTo(`/instruments/${backoffice.buildInstrument.id}`)
  }
  catch (e) {
    message.error(errorText(e))
  }
  finally {
    saving.value = false
  }
}
</script>

<template>
  <div>
    <NuxtLink to="/instruments" class="text-xs text-white/50 tracking-[0.2em] font-mono uppercase hover:text-white">
      ← Instruments
    </NuxtLink>
    <h1 class="text-3xl font-semibold m-0 mb-8 mt-4">
      Nouvel instrument
    </h1>

    <NAlert v-if="loadError" type="error" class="mb-6">
      {{ loadError }}
      <NButton size="small" class="ml-3" @click="load">
        Réessayer
      </NButton>
    </NAlert>

    <NSpin :show="loading">
      <form v-if="form" class="flex flex-col gap-8" @submit.prevent="submit">
        <section class="p-5 border border-white/10 rounded-xl">
          <h2 class="text-xs text-white/40 tracking-[0.15em] font-mono m-0 mb-4 uppercase">
            Configuration de départ (facultatif)
          </h2>
          <div class="gap-4 grid sm:grid-cols-2">
            <NFormItem label="Commande" :show-feedback="false">
              <NSelect
                :value="orderId"
                :options="form.orders.map(o => ({ value: o.id, label: `${o.reference} · ${o.customer}` }))"
                filterable
                clearable
                placeholder="Aucune : composition saisie à la main"
                @update:value="setOrder"
              />
            </NFormItem>
            <NFormItem v-if="order" label="Article de la commande" :show-feedback="false">
              <NSelect
                :value="orderItemIndex"
                :options="order.items.map(i => ({ value: i.index, label: `${i.name} (${i.parts.length} pièce${i.parts.length > 1 ? 's' : ''} à fabriquer)` }))"
                placeholder="Choisir l'article"
                @update:value="useOrderItem"
              />
            </NFormItem>
          </div>
          <p class="text-xs text-white/40 m-0 mt-3">
            Les pièces et options de l'article remplissent la composition ci-dessous ; tu peux encore les changer.
          </p>
        </section>

        <section class="p-5 border border-white/10 rounded-xl">
          <h2 class="text-xs text-white/40 tracking-[0.15em] font-mono m-0 mb-4 uppercase">
            Instrument
          </h2>
          <div class="mb-4 gap-4 grid lg:grid-cols-4 sm:grid-cols-2">
            <NFormItem label="Modèle d'instrument" :show-feedback="false">
              <NSelect
                v-model:value="instrumentModelId"
                :options="form.instrumentModels.map(m => ({ value: m.id, label: `${m.name} · ${label(m.instrumentType)}` }))"
                filterable
                placeholder="Choisir"
              />
            </NFormItem>
            <NFormItem label="Atelier" :show-feedback="false">
              <NSelect v-model:value="factoryId" :options="form.factories.map(f => ({ value: f.id, label: `${f.name} (${f.code})` }))" placeholder="Choisir" />
            </NFormItem>
            <NFormItem label="Propriétaire (e-mail du compte client)" :show-feedback="false">
              <NInput v-model:value="ownerEmail" placeholder="Facultatif" />
            </NFormItem>
            <NFormItem label="Statut" :show-feedback="false">
              <NSelect v-model:value="saleStatus" :options="saleStatusOptions" />
            </NFormItem>
          </div>
          <NFormItem label="Description" :show-feedback="false">
            <NInput
              v-model:value="description"
              type="textarea"
              :autosize="{ minRows: 3, maxRows: 10 }"
              placeholder="Finition, particularités, réglages de sortie d'atelier, dédicace…"
            />
          </NFormItem>
        </section>

        <section>
          <div class="mb-4 flex flex-wrap gap-3 items-end justify-between">
            <div>
              <h2 class="text-lg font-semibold m-0">
                Composition
              </h2>
              <p class="text-sm text-white/50 m-0 mt-1">
                Les pièces neuves reçoivent leur numéro de série à l'enregistrement.
              </p>
            </div>
            <div class="flex gap-2">
              <NButton @click="addLine(false)">
                + Pièce neuve
              </NButton>
              <NButton :disabled="!form.freeParts.length" @click="addLine(true)">
                + Pièce déjà fabriquée
              </NButton>
            </div>
          </div>

          <div class="flex flex-col gap-4">
            <div v-for="(line, index) in lines" :key="line.key" class="p-5 border border-white/10 rounded-xl">
              <div class="mb-4 flex flex-wrap gap-3 items-center">
                <span class="text-xs text-white/40 font-mono">PIÈCE {{ index + 1 }}</span>
                <NTag v-if="line.component" size="small" :bordered="false">
                  {{ label(line.component) }}
                </NTag>
                <NTag size="small" :bordered="false" :type="line.existingPartId === null ? 'info' : 'default'">
                  {{ line.existingPartId === null ? 'Neuve' : 'Déjà fabriquée' }}
                </NTag>
                <NRadio :checked="masterKey === line.key" @update:checked="masterKey = line.key">
                  Pièce maîtresse
                </NRadio>
                <NButton quaternary size="small" class="ml-auto" :disabled="lines.length === 1" @click="removeLine(line.key)">
                  Retirer
                </NButton>
              </div>

              <NFormItem v-if="line.existingPartId !== null" label="Pièce" :show-feedback="false">
                <NSelect v-model:value="line.existingPartId" :options="freePartOptions(line)" filterable placeholder="N° de série" />
              </NFormItem>
              <PartFields v-else v-model="lines[index]!" :part-models="form.partModels" @batch-created="onBatchCreated" />
            </div>
          </div>
        </section>

        <div class="flex gap-4 items-center">
          <NButton attr-type="submit" type="primary" size="large" :loading="saving" :disabled="!!missing">
            Créer l'instrument
          </NButton>
          <span v-if="missing" class="text-sm text-white/50">{{ missing }}</span>
        </div>
      </form>
    </NSpin>
  </div>
</template>
